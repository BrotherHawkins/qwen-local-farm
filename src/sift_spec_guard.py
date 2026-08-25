from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


STATUS_VALUES = {"Draft", "Accepted", "Implemented", "Deprecated"}
TYPE_VALUES = {"Add", "Modify", "Delete"}
CANONICAL_FOLDERS = {
    "Draft": "drafts",
    "Accepted": "accepted",
    "Implemented": "implemented",
    "Deprecated": "deprecated",
}
LEGACY_CHANGE_SPECS_WITHOUT_PLANS = {"0000"}


@dataclass(frozen=True)
class ChangeSpec:
    spec_id: str
    path: Path
    status: str | None
    change_type: str | None


@dataclass(frozen=True)
class CanonicalSpec:
    path: Path
    status: str


@dataclass(frozen=True)
class PlanSpecLink:
    path: Path
    target: Path | None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def repo_relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def metadata_value(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+?)\s*$", text)
    return match.group(1).strip() if match else None


def discover_change_specs(root: Path) -> list[ChangeSpec]:
    changes_dir = root / "docs" / "specs" / "changes"
    specs: list[ChangeSpec] = []
    for path in sorted(changes_dir.glob("*.md")):
        match = re.match(r"^(\d{4})-", path.name)
        spec_id = match.group(1) if match else ""
        text = read_text(path)
        specs.append(
            ChangeSpec(
                spec_id=spec_id,
                path=path,
                status=metadata_value(text, "Status"),
                change_type=metadata_value(text, "Type"),
            )
        )
    return specs


def discover_canonical_specs(root: Path) -> list[CanonicalSpec]:
    base = root / "docs" / "specs"
    specs: list[CanonicalSpec] = []
    for status, folder in CANONICAL_FOLDERS.items():
        spec_dir = base / folder
        if not spec_dir.exists():
            continue
        for path in sorted(spec_dir.glob("*.md")):
            specs.append(CanonicalSpec(path=path, status=status))
    return specs


def status_counts(values: list[str]) -> dict[str, int]:
    return {status: sum(1 for value in values if value == status) for status in sorted(STATUS_VALUES)}


def parse_dashboard_counts(text: str, heading: str) -> dict[str, int]:
    section = section_after_heading(text, heading)
    counts: dict[str, int] = {}
    for line in section.splitlines():
        match = re.match(r"^\|\s*(Draft|Accepted|Implemented|Deprecated)\s*\|\s*(\d+)\s*\|", line)
        if match:
            counts[match.group(1)] = int(match.group(2))
    return counts


def section_after_heading(text: str, heading: str) -> str:
    marker = f"### {heading}"
    start = text.find(marker)
    if start == -1:
        return ""
    rest = text[start + len(marker):]
    next_heading = re.search(r"(?m)^#{2,3}\s+", rest)
    return rest[: next_heading.start()] if next_heading else rest


def parse_dashboard_change_rows(text: str) -> dict[str, dict[str, str]]:
    match = re.search(r"(?m)^## Change Specs\s*$", text)
    if not match:
        return {}
    rest = text[match.end():]
    next_heading = re.search(r"(?m)^##\s+", rest)
    section = rest[: next_heading.start()] if next_heading else rest
    rows: dict[str, dict[str, str]] = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5 or not re.fullmatch(r"\d{4}", cells[0]):
            continue
        rows[cells[0]] = {
            "status": cells[1],
            "type": cells[2],
            "spec": cells[3],
            "summary": cells[4],
        }
    return rows


def discover_plan_links(root: Path) -> list[PlanSpecLink]:
    plan_dir = root / "docs" / "specs" / "plans"
    links: list[PlanSpecLink] = []
    for path in sorted(plan_dir.glob("*.md")):
        text = read_text(path)
        match = re.search(r"(?m)^(?:Spec|Change Spec):\s*\[[^\]]+\]\(([^)]+)\)", text)
        target = None
        if match:
            target = (path.parent / match.group(1)).resolve()
        links.append(PlanSpecLink(path=path, target=target))
    return links


def plan_ids(root: Path) -> set[str]:
    plan_dir = root / "docs" / "specs" / "plans"
    ids = set()
    for path in plan_dir.glob("*.md"):
        match = re.match(r"^(\d{4})-", path.name)
        if match:
            ids.add(match.group(1))
    return ids


def validate_specs(root: Path) -> list[str]:
    errors: list[str] = []
    dashboard_path = root / "docs" / "specs" / "SPEC_DASHBOARD.md"
    dashboard = read_text(dashboard_path)
    changes = discover_change_specs(root)
    canonicals = discover_canonical_specs(root)

    seen_ids: set[str] = set()
    for spec in changes:
        label = repo_relative(root, spec.path)
        if not spec.spec_id:
            errors.append(f"{label}: filename must start with a four-digit spec id.")
            continue
        if spec.spec_id in seen_ids:
            errors.append(f"{label}: duplicate change spec id {spec.spec_id}.")
        seen_ids.add(spec.spec_id)
        if spec.status not in STATUS_VALUES:
            errors.append(f"{label}: invalid or missing Status: {spec.status!r}.")
        if spec.change_type not in TYPE_VALUES:
            errors.append(f"{label}: invalid or missing Type: {spec.change_type!r}.")

    canonical_counts = status_counts([spec.status for spec in canonicals])
    change_counts = status_counts([spec.status or "" for spec in changes])
    dashboard_canonical_counts = parse_dashboard_counts(dashboard, "Canonical Specs")
    dashboard_change_counts = parse_dashboard_counts(dashboard, "Change Specs")
    compare_counts(
        errors,
        label="canonical spec",
        actual=canonical_counts,
        dashboard=dashboard_canonical_counts,
        dashboard_path=dashboard_path,
        root=root,
    )
    compare_counts(
        errors,
        label="change spec",
        actual=change_counts,
        dashboard=dashboard_change_counts,
        dashboard_path=dashboard_path,
        root=root,
    )

    rows = parse_dashboard_change_rows(dashboard)
    for spec in changes:
        if not spec.spec_id:
            continue
        row = rows.get(spec.spec_id)
        if row is None:
            errors.append(f"{repo_relative(root, dashboard_path)}: missing Change Specs row for {spec.spec_id}.")
            continue
        if row["status"] != spec.status:
            errors.append(
                f"{repo_relative(root, dashboard_path)}: status mismatch for {spec.spec_id}: "
                f"dashboard={row['status']!r}, spec={spec.status!r}."
            )
        if row["type"] != spec.change_type:
            errors.append(
                f"{repo_relative(root, dashboard_path)}: type mismatch for {spec.spec_id}: "
                f"dashboard={row['type']!r}, spec={spec.change_type!r}."
            )
        if spec.path.name not in row["spec"]:
            errors.append(
                f"{repo_relative(root, dashboard_path)}: row for {spec.spec_id} does not link "
                f"{spec.path.name}."
            )

    extra_rows = sorted(set(rows) - {spec.spec_id for spec in changes})
    for spec_id in extra_rows:
        errors.append(f"{repo_relative(root, dashboard_path)}: Change Specs row {spec_id} has no matching spec file.")

    ids_with_plans = plan_ids(root)
    for spec in changes:
        if spec.status in {"Accepted", "Implemented"} and spec.spec_id not in ids_with_plans:
            if spec.spec_id not in LEGACY_CHANGE_SPECS_WITHOUT_PLANS:
                errors.append(f"{repo_relative(root, spec.path)}: missing implementation plan for {spec.spec_id}.")

    for link in discover_plan_links(root):
        if link.target is None:
            errors.append(f"{repo_relative(root, link.path)}: missing Spec: link.")
            continue
        if not link.target.exists():
            errors.append(
                f"{repo_relative(root, link.path)}: Spec: link target does not exist: "
                f"{repo_relative(root, link.target)}."
            )

    return errors


def compare_counts(
    errors: list[str],
    *,
    label: str,
    actual: dict[str, int],
    dashboard: dict[str, int],
    dashboard_path: Path,
    root: Path,
) -> None:
    for status in sorted(STATUS_VALUES):
        actual_count = actual.get(status, 0)
        dashboard_count = dashboard.get(status)
        if dashboard_count is None:
            errors.append(f"{repo_relative(root, dashboard_path)}: missing {label} count for {status}.")
        elif dashboard_count != actual_count:
            errors.append(
                f"{repo_relative(root, dashboard_path)}: {label} {status} count mismatch: "
                f"dashboard={dashboard_count}, actual={actual_count}."
            )


def render_errors(errors: list[str]) -> str:
    if not errors:
        return "Spec guard passed."
    lines = ["Spec guard failed:"]
    lines.extend(f"- {error}" for error in errors)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    root = Path(args[0]).resolve() if args else Path(__file__).resolve().parents[1]
    errors = validate_specs(root)
    print(render_errors(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

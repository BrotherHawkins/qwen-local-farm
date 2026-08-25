from __future__ import annotations

import filecmp
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_INSTALL_REPORT_SCHEMA_VERSION = 1
SKILLS_MANIFEST_PATH = Path("skills") / "index.json"
TARGETS = {
    "codex-user": {
        "app": "codex",
        "scope": "user",
        "destination": Path(".agents") / "skills",
        "next_step": "Restart Codex if the installed skills do not appear.",
    },
    "codex-project": {
        "app": "codex",
        "scope": "project",
        "destination": Path(".agents") / "skills",
        "next_step": "Restart Codex if the installed project skills do not appear.",
    },
    "claude-user": {
        "app": "claude-code",
        "scope": "user",
        "destination": Path(".claude") / "skills",
        "next_step": "Restart Claude Code if the installed skills do not appear.",
    },
    "claude-project": {
        "app": "claude-code",
        "scope": "project",
        "destination": Path(".claude") / "skills",
        "next_step": "Restart or reload Claude Code if the installed project skills do not appear.",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def resolve_under(base: Path, *parts: str | Path) -> Path:
    resolved_base = base.resolve()
    candidate = resolved_base.joinpath(*parts).resolve()
    if candidate != resolved_base and resolved_base not in candidate.parents:
        raise ValueError(f"Resolved path escapes target root: {candidate}")
    return candidate


def target_destination_root(*, repo_root: Path, home: Path, target: str) -> Path:
    if target not in TARGETS:
        raise ValueError(f"--target must be one of: {', '.join(sorted(TARGETS))}.")
    info = TARGETS[target]
    base = home if info["scope"] == "user" else repo_root
    return resolve_under(base, info["destination"])


def load_manifest(repo_root: Path) -> dict[str, Any]:
    manifest = read_json_object(repo_root / SKILLS_MANIFEST_PATH)
    skills = manifest.get("skills")
    if not isinstance(skills, list):
        raise ValueError("skills/index.json must include a skills list.")
    return manifest


def skill_ids(manifest: dict[str, Any]) -> list[str]:
    output: list[str] = []
    for skill in manifest.get("skills") or []:
        if isinstance(skill, dict):
            skill_id = str(skill.get("id") or "").strip()
            if skill_id:
                output.append(skill_id)
    return output


def source_skill_dir(repo_root: Path, skill: dict[str, Any]) -> Path:
    path = repo_root / str(skill.get("path") or "")
    if path.name != "SKILL.md":
        raise ValueError(f"Skill path must point to SKILL.md: {skill.get('path')}")
    source = path.parent
    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"Skill source folder not found: {display_path(repo_root, source)}")
    return source


def directories_equal(left: Path, right: Path) -> bool:
    if not left.exists() or not right.exists():
        return False
    comparison = filecmp.dircmp(left, right)
    if comparison.left_only or comparison.right_only or comparison.diff_files or comparison.funny_files:
        return False
    return all(directories_equal(Path(comparison.left) / name, Path(comparison.right) / name) for name in comparison.common_dirs)


def copy_skill_dir(source: Path, destination: Path, *, replace: bool) -> None:
    if destination.exists() and replace:
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def build_skill_install_report(
    *,
    repo_root: Path,
    target: str,
    home: Path | None = None,
    write: bool = False,
    replace: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    home = (home or Path.home()).resolve()
    manifest = load_manifest(repo_root)
    destination_root = target_destination_root(repo_root=repo_root, home=home, target=target)
    target_info = TARGETS[target]
    dry_run = not write
    records: list[dict[str, Any]] = []
    warnings: list[str] = []

    for skill in manifest.get("skills") or []:
        if not isinstance(skill, dict):
            continue
        skill_id = str(skill.get("id") or "").strip()
        source = source_skill_dir(repo_root, skill)
        destination = resolve_under(destination_root, skill_id)
        record: dict[str, Any] = {
            "id": skill_id,
            "source": display_path(repo_root, source),
            "destination": str(destination),
            "action": "copy",
            "status": "planned",
            "reason": "missing",
        }

        if destination.exists():
            if directories_equal(source, destination):
                record.update({"action": "skip", "status": "up_to_date", "reason": "identical"})
            elif replace:
                record.update({"action": "replace", "status": "planned" if dry_run else "copied", "reason": "replace_requested"})
            else:
                record.update({"action": "skip", "status": "conflict", "reason": "destination_differs"})
        elif not dry_run:
            record["status"] = "copied"

        if not dry_run and record["action"] in {"copy", "replace"} and record["status"] == "copied":
            destination_root.mkdir(parents=True, exist_ok=True)
            copy_skill_dir(source, destination, replace=record["action"] == "replace")

        records.append(record)

    if target_info["scope"] == "project":
        warnings.append("Project skill installs may dirty the working tree if the destination folder is tracked.")

    report = {
        "schema_version": SKILL_INSTALL_REPORT_SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "command": "skills install",
        "target": target,
        "app": target_info["app"],
        "scope": target_info["scope"],
        "dry_run": dry_run,
        "write": write,
        "replace": replace,
        "source_root": display_path(repo_root, repo_root / "skills"),
        "destination_root": str(destination_root),
        "skills": records,
        "summary": summarize(records),
        "warnings": warnings,
        "next_steps": [target_info["next_step"], "Run `python sift.py farm doctor --json` to continue Sift setup."],
    }
    return report


def summarize(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "planned": len([record for record in records if record.get("status") == "planned"]),
        "copied": len([record for record in records if record.get("status") == "copied"]),
        "up_to_date": len([record for record in records if record.get("status") == "up_to_date"]),
        "conflicts": len([record for record in records if record.get("status") == "conflict"]),
        "skipped": len([record for record in records if record.get("status") == "skipped"]),
        "errors": len([record for record in records if record.get("status") == "error"]),
    }


def render_skill_install_report(report: dict[str, Any]) -> str:
    mode = "preview" if report.get("dry_run") else "result"
    lines = [
        f"Skill install {mode}: {report.get('target')}",
        f"Destination: {report.get('destination_root')}",
        "",
    ]
    for record in report.get("skills") or []:
        if not isinstance(record, dict):
            continue
        status = str(record.get("status") or "")
        action = str(record.get("action") or "")
        reason = str(record.get("reason") or "")
        suffix = f" ({reason})" if reason else ""
        lines.append(f"- {record.get('id')}: {action} {status}{suffix}")

    lines.append("")
    if report.get("dry_run"):
        lines.append("No files written. Re-run with --write to apply.")
    else:
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        lines.append(f"Files written for {summary.get('copied', 0)} skill(s).")

    warnings = [str(item) for item in report.get("warnings") or []]
    if warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in warnings)

    next_steps = [str(item) for item in report.get("next_steps") or []]
    if next_steps:
        lines.extend(["", "Next steps:"])
        lines.extend(f"- {step}" for step in next_steps)

    return "\n".join(lines)

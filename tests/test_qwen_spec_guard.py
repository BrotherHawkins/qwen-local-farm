from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src import qwen_spec_guard


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def valid_fixture(root: Path) -> None:
    write(
        root / "docs/specs/implemented/farm-mvp.md",
        "# Farm MVP\n\nStatus: Implemented\n",
    )
    write(
        root / "docs/specs/changes/0000-add-minimal-pr-gate.md",
        "# 0000 Add Minimal PR Gate\n\nStatus: Implemented\nType: Add\n",
    )
    write(
        root / "docs/specs/changes/0001-add-worker-farm-mvp.md",
        "# 0001 Add Worker Farm MVP\n\nStatus: Implemented\nType: Add\n",
    )
    write(
        root / "docs/specs/plans/0001-implement-worker-farm-mvp.md",
        "# 0001 Implement Worker Farm MVP\n\nStatus: Implemented\n"
        "Change Spec: [0001 Add Worker Farm MVP](../changes/0001-add-worker-farm-mvp.md)\n",
    )
    write(
        root / "docs/specs/SPEC_DASHBOARD.md",
        """# Spec Dashboard

## Counts

### Canonical Specs

| Status | Count |
| --- | ---: |
| Draft | 0 |
| Accepted | 0 |
| Implemented | 1 |
| Deprecated | 0 |

### Change Specs

| Status | Count |
| --- | ---: |
| Draft | 0 |
| Accepted | 0 |
| Implemented | 2 |
| Deprecated | 0 |

## Change Specs

| ID | Status | Type | Spec | Summary |
| --- | --- | --- | --- | --- |
| 0000 | Implemented | Add | [0000-add-minimal-pr-gate.md](changes/0000-add-minimal-pr-gate.md) | Minimal PR gate. |
| 0001 | Implemented | Add | [0001-add-worker-farm-mvp.md](changes/0001-add-worker-farm-mvp.md) | Worker farm MVP. |
""",
    )


class SpecGuardTests(unittest.TestCase):
    def test_valid_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            valid_fixture(root)

            self.assertEqual(qwen_spec_guard.validate_specs(root), [])

    def test_dashboard_count_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            valid_fixture(root)
            dashboard = root / "docs/specs/SPEC_DASHBOARD.md"
            dashboard.write_text(dashboard.read_text(encoding="utf-8").replace("| Implemented | 2 |", "| Implemented | 1 |"), encoding="utf-8")

            errors = qwen_spec_guard.validate_specs(root)

            self.assertIn("change spec Implemented count mismatch", "\n".join(errors))

    def test_missing_dashboard_row_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            valid_fixture(root)
            dashboard = root / "docs/specs/SPEC_DASHBOARD.md"
            dashboard.write_text(
                dashboard.read_text(encoding="utf-8").replace(
                    "| 0001 | Implemented | Add | [0001-add-worker-farm-mvp.md](changes/0001-add-worker-farm-mvp.md) | Worker farm MVP. |\n",
                    "",
                ),
                encoding="utf-8",
            )

            errors = qwen_spec_guard.validate_specs(root)

            self.assertIn("missing Change Specs row for 0001", "\n".join(errors))

    def test_dashboard_status_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            valid_fixture(root)
            dashboard = root / "docs/specs/SPEC_DASHBOARD.md"
            dashboard.write_text(
                dashboard.read_text(encoding="utf-8").replace("| 0001 | Implemented | Add |", "| 0001 | Draft | Add |"),
                encoding="utf-8",
            )

            errors = qwen_spec_guard.validate_specs(root)

            self.assertIn("status mismatch for 0001", "\n".join(errors))

    def test_invalid_status_and_type_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            valid_fixture(root)
            spec = root / "docs/specs/changes/0001-add-worker-farm-mvp.md"
            spec.write_text("# 0001 Add Worker Farm MVP\n\nStatus: Done\nType: Create\n", encoding="utf-8")

            errors = qwen_spec_guard.validate_specs(root)

            joined = "\n".join(errors)
            self.assertIn("invalid or missing Status", joined)
            self.assertIn("invalid or missing Type", joined)

    def test_missing_plan_fails_for_implemented_nonlegacy_change_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            valid_fixture(root)
            (root / "docs/specs/plans/0001-implement-worker-farm-mvp.md").unlink()

            errors = qwen_spec_guard.validate_specs(root)

            self.assertIn("missing implementation plan for 0001", "\n".join(errors))

    def test_broken_plan_link_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            valid_fixture(root)
            plan = root / "docs/specs/plans/0001-implement-worker-farm-mvp.md"
            plan.write_text(
                "# 0001 Implement Worker Farm MVP\n\nStatus: Implemented\n"
                "Spec: [Missing](../changes/9999-missing.md)\n",
                encoding="utf-8",
            )

            errors = qwen_spec_guard.validate_specs(root)

            self.assertIn("Spec: link target does not exist", "\n".join(errors))

    def test_explicit_spec_plan_link_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            valid_fixture(root)
            plan = root / "docs/specs/plans/0001-implement-worker-farm-mvp.md"
            plan.write_text(
                "# 0001 Implement Worker Farm MVP\n\nStatus: Implemented\n"
                "Spec: [0001 Add Worker Farm MVP](../changes/0001-add-worker-farm-mvp.md)\n",
                encoding="utf-8",
            )

            self.assertEqual(qwen_spec_guard.validate_specs(root), [])


if __name__ == "__main__":
    unittest.main()

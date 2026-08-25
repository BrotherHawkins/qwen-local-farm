from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src import sift_farm_schema, sift_skills_install


ROOT = Path(__file__).resolve().parents[1]


def make_skill_repo(root: Path) -> Path:
    repo = root / "repo"
    for skill_id in ["sift-setup", "sift-operator"]:
        source = ROOT / "skills" / skill_id / "SKILL.md"
        destination = repo / "skills" / skill_id / "SKILL.md"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    (repo / "skills" / "index.json").write_text(
        (ROOT / "skills" / "index.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return repo


class SkillInstallTests(unittest.TestCase):
    def test_preview_writes_no_files_for_user_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir) / "home"

            report = sift_skills_install.build_skill_install_report(
                repo_root=ROOT,
                target="codex-user",
                home=home,
            )

            self.assertTrue(report["dry_run"])
            self.assertFalse((home / ".agents" / "skills").exists())
            self.assertEqual(report["summary"]["planned"], 2)
            self.assertEqual({skill["status"] for skill in report["skills"]}, {"planned"})

    def test_write_copies_whole_skill_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir) / "home"

            report = sift_skills_install.build_skill_install_report(
                repo_root=ROOT,
                target="codex-user",
                home=home,
                write=True,
            )

            destination = home / ".agents" / "skills"
            self.assertTrue((destination / "sift-setup" / "SKILL.md").exists())
            self.assertTrue((destination / "sift-operator" / "SKILL.md").exists())
            self.assertEqual(report["summary"]["copied"], 2)
            self.assertEqual({skill["status"] for skill in report["skills"]}, {"copied"})

    def test_identical_existing_install_reports_up_to_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir) / "home"
            sift_skills_install.build_skill_install_report(
                repo_root=ROOT,
                target="codex-user",
                home=home,
                write=True,
            )

            report = sift_skills_install.build_skill_install_report(
                repo_root=ROOT,
                target="codex-user",
                home=home,
                write=True,
            )

            self.assertEqual(report["summary"]["up_to_date"], 2)
            self.assertEqual({skill["status"] for skill in report["skills"]}, {"up_to_date"})

    def test_conflict_does_not_overwrite_without_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir) / "home"
            destination = home / ".agents" / "skills" / "sift-setup"
            destination.mkdir(parents=True)
            marker = destination / "SKILL.md"
            marker.write_text("local changes", encoding="utf-8")

            report = sift_skills_install.build_skill_install_report(
                repo_root=ROOT,
                target="codex-user",
                home=home,
                write=True,
            )

            self.assertEqual(marker.read_text(encoding="utf-8"), "local changes")
            statuses = {skill["id"]: skill["status"] for skill in report["skills"]}
            self.assertEqual(statuses["sift-setup"], "conflict")
            self.assertEqual(statuses["sift-operator"], "copied")
            self.assertEqual(report["summary"]["conflicts"], 1)

    def test_replace_overwrites_only_selected_sift_skill_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir) / "home"
            destination = home / ".agents" / "skills" / "sift-setup"
            destination.mkdir(parents=True)
            marker = destination / "SKILL.md"
            marker.write_text("local changes", encoding="utf-8")

            report = sift_skills_install.build_skill_install_report(
                repo_root=ROOT,
                target="codex-user",
                home=home,
                write=True,
                replace=True,
            )

            self.assertIn("Sift Setup", marker.read_text(encoding="utf-8"))
            statuses = {skill["id"]: skill["status"] for skill in report["skills"]}
            self.assertEqual(statuses["sift-setup"], "copied")
            self.assertEqual(report["summary"]["copied"], 2)

    def test_project_targets_resolve_expected_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = make_skill_repo(Path(temp_dir))

            codex = sift_skills_install.build_skill_install_report(
                repo_root=project,
                target="codex-project",
                home=Path(temp_dir) / "home",
            )
            claude = sift_skills_install.build_skill_install_report(
                repo_root=project,
                target="claude-project",
                home=Path(temp_dir) / "home",
            )

            self.assertTrue(codex["destination_root"].endswith(".agents\\skills") or codex["destination_root"].endswith(".agents/skills"))
            self.assertTrue(claude["destination_root"].endswith(".claude\\skills") or claude["destination_root"].endswith(".claude/skills"))
            self.assertIn("dirty the working tree", "\n".join(codex["warnings"]))

    def test_report_validates_against_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = sift_skills_install.build_skill_install_report(
                repo_root=ROOT,
                target="claude-user",
                home=Path(temp_dir) / "home",
                write=True,
                generated_at="2026-08-25T00:00:00Z",
            )

            schema = sift_farm_schema.load_json_object(ROOT / "schemas" / "skill-install-report.schema.json")

            self.assertEqual(sift_farm_schema.validate(report, schema), [])

    def test_human_output_reports_destination_and_write_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = sift_skills_install.build_skill_install_report(
                repo_root=ROOT,
                target="codex-user",
                home=Path(temp_dir) / "home",
            )

            rendered = sift_skills_install.render_skill_install_report(report)

            self.assertIn("Skill install preview: codex-user", rendered)
            self.assertIn("Destination:", rendered)
            self.assertIn("sift-setup", rendered)
            self.assertIn("No files written", rendered)


if __name__ == "__main__":
    unittest.main()

import sys
import tempfile
import unittest
import json
from pathlib import Path

SCRIPTS = Path(__file__).parents[1] / ".agents" / "skills" / "book-to-skill-followup" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_package
from runtime_common import package_snapshot


def make_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    skill = project / ".agents" / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: demo\ndescription: demo skill\n---\n# 제목\n\n[guide](guide.md#두번)\n", encoding="utf-8")
    (skill / "guide.md").write_text("# 두번\n# 두번\n\n```sh\nrm -rf /\n```\n", encoding="utf-8")
    (project / "README.md").write_text("[skill](.agents/skills/demo/SKILL.md#제목)\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "usage.md").write_text("[guide](../.agents/skills/demo/guide.md#두번-1)\n", encoding="utf-8")
    return project


def test_recursive_package_and_documents_pass(tmp_path):
    project = make_project(tmp_path)
    report = check_package.run(project, ".agents/skills/demo", ["README.md", "docs"], None)
    assert report["verdict"] == "pass"
    assert not report["warnings"]
    assert {row["path"] for row in report["scanned_files"]} >= {"README.md", "docs/usage.md", ".agents/skills/demo/guide.md"}


def test_invalid_local_link_and_structured_file_fail(tmp_path):
    project = make_project(tmp_path)
    skill = project / ".agents" / "skills" / "demo"
    (skill / "bad.json").write_text("{bad", encoding="utf-8")
    (skill / "guide.md").write_text("[outside](../../../../secret.md)\n", encoding="utf-8")
    report = check_package.run(project, ".agents/skills/demo", [], None)
    assert report["verdict"] == "fail"
    assert {item["code"] for item in report["errors"]} >= {"invalid-structured-file", "link-escapes-project"}


def test_generated_cache_is_excluded_but_cache_symlink_is_rejected(tmp_path):
    project = make_project(tmp_path)
    skill = project / ".agents" / "skills" / "demo"
    cache = skill / "__pycache__"
    cache.mkdir()
    (cache / "ignored.pyc").write_bytes(b"cache")
    report = check_package.run(project, ".agents/skills/demo", [], None)
    assert report["verdict"] == "pass"
    assert all("__pycache__" not in row["path"] for row in report["scanned_files"])
    (cache / "ignored.pyc").unlink()
    cache.rmdir()
    target = tmp_path / "cache-target"
    target.mkdir()
    cache.symlink_to(target, target_is_directory=True)
    report = check_package.run(project, ".agents/skills/demo", [], None)
    assert "symlinked-cache" in {item["code"] for item in report["errors"]}


def test_markdown_images_unicode_references_and_inline_heading(tmp_path):
    project = make_project(tmp_path)
    skill = project / ".agents" / "skills" / "demo"
    (skill / "자료.md").write_text("# [연결](guide.md)와 `코드`\n", encoding="utf-8")
    (skill / "guide.md").write_text("# 두번\n\n[자료][doc]\n\n[doc]: 자료.md#연결와-코드\n![broken](missing.png)\n", encoding="utf-8")
    report = check_package.run(project, ".agents/skills/demo", [], None)
    codes = {item["code"] for item in report["errors"]}
    assert "missing-local-link" in codes
    assert "missing-link-anchor" not in codes


def test_run_state_binding_rejects_different_documents(tmp_path):
    project = make_project(tmp_path)
    run = tmp_path / "run"
    run.mkdir()
    state = {"project": str(project), "skill_rel": ".agents/skills/demo", "documents": ["README.md"], "host": "codex"}
    state["freeze_snapshot"] = package_snapshot(state)
    (run / "run.json").write_text(json.dumps(state), encoding="utf-8")
    report = check_package.run(project, ".agents/skills/demo", [], run)
    assert report["verdict"] == "blocked"
    assert report["errors"][0]["code"] == "runtime-snapshot-unavailable"


def test_yuriring_percent_encoded_middle_dot_anchor_and_directory_link(tmp_path):
    project = make_project(tmp_path)
    skill = project / ".agents" / "skills" / "demo"
    (skill / "patterns.md").write_text("## 객체·반복 정보·참조 분리\n", encoding="utf-8")
    (skill / "chapters").mkdir()
    (skill / "guide.md").write_text(
        "# 두번\n\n[pattern](patterns.md#%EA%B0%9D%EC%B2%B4%EB%B0%98%EB%B3%B5-%EC%A0%95%EB%B3%B4%EC%B0%B8%EC%A1%B0-%EB%B6%84%EB%A6%AC)\n"
        "[chapters](chapters/)\n", encoding="utf-8")
    report = check_package.run(project, ".agents/skills/demo", [], None)
    assert report["verdict"] == "pass"


class CheckPackageTests(unittest.TestCase):
    def test_recursive_package_and_documents_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            test_recursive_package_and_documents_pass(Path(directory))

    def test_invalid_local_link_and_structured_file_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            test_invalid_local_link_and_structured_file_fail(Path(directory))

    def test_generated_cache_is_excluded_but_cache_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            test_generated_cache_is_excluded_but_cache_symlink_is_rejected(Path(directory))

    def test_markdown_images_unicode_references_and_inline_heading(self):
        with tempfile.TemporaryDirectory() as directory:
            test_markdown_images_unicode_references_and_inline_heading(Path(directory))

    def test_run_state_binding_rejects_different_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            test_run_state_binding_rejects_different_documents(Path(directory))

    def test_yuriring_percent_encoded_middle_dot_anchor_and_directory_link(self):
        with tempfile.TemporaryDirectory() as directory:
            test_yuriring_percent_encoded_middle_dot_anchor_and_directory_link(Path(directory))


if __name__ == "__main__":
    unittest.main()

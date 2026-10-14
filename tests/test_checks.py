import sys
import tempfile
import unittest
import json
import importlib.util
import os
import shlex
import subprocess
from pathlib import Path
from unittest.mock import patch

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


def install_followup_tool(project: Path, parent: Path | None = None) -> None:
    root = parent or project
    tool = root / ".agents" / "skills" / "book-to-skill-followup"
    tool.mkdir(parents=True)
    (tool / "SKILL.md").write_text("---\nname: book-to-skill-followup\ndescription: helper\n---\n", encoding="utf-8")
    alias = root / ".claude" / "skills" / "book-to-skill-followup"
    alias.parent.mkdir(parents=True)
    alias.symlink_to("../../.agents/skills/book-to-skill-followup", target_is_directory=True)


def init_git(project: Path) -> None:
    subprocess.run(["git", "init", "-q", str(project)], check=True)


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


def test_inline_code_link_examples_are_not_checked_as_links(tmp_path):
    project = make_project(tmp_path)
    skill = project / ".agents" / "skills" / "demo"
    (skill / "guide.md").write_text(
        "# 두번\n\n링크 스타일은 인라인 코드 예시 `[제목](URL)`를 사용합니다.\n\n[실제 안내](자료.md)\n",
        encoding="utf-8",
    )
    (skill / "자료.md").write_text("# 자료\n", encoding="utf-8")
    report = check_package.run(project, ".agents/skills/demo", [], None)
    assert report["verdict"] == "pass", report["errors"]


def test_rendered_url_placeholder_remains_a_missing_link(tmp_path):
    project = make_project(tmp_path)
    skill = project / ".agents" / "skills" / "demo"
    (skill / "guide.md").write_text("# 두번\n\n[실제](URL)\n", encoding="utf-8")
    report = check_package.run(project, ".agents/skills/demo", [], None)
    assert "missing-local-link" in {item["code"] for item in report["errors"]}


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


def test_nested_followup_tool_and_alias_fail(tmp_path):
    project = make_project(tmp_path)
    install_followup_tool(project, project / ".agents" / "skills" / "demo")
    report = check_package.run(project, ".agents/skills/demo", [], None)
    leaks = [item for item in report["errors"] if item["code"] == "nested-followup-tool"]
    assert {item["file"] for item in leaks} == {
        ".agents/skills/demo/.agents/skills/book-to-skill-followup",
        ".agents/skills/demo/.claude/skills/book-to-skill-followup",
    }


def test_followup_copy_in_references_and_named_symlink_fail(tmp_path):
    project = make_project(tmp_path)
    skill = project / ".agents" / "skills" / "demo"
    copied = skill / "references" / "book-to-skill-followup"
    copied.mkdir(parents=True)
    (copied / "SKILL.md").write_text(
        "---\nname: \"book-to-skill-followup\" # copied helper\ndescription: copied helper\n---\n", encoding="utf-8"
    )
    broken = skill / "references" / "broken-copy"
    broken.mkdir()
    (broken / "SKILL.md").write_bytes(b"\xff\xfe")
    target = tmp_path / "followup-target"
    target.mkdir()
    (skill / "assets" / "book-to-skill-followup").parent.mkdir()
    (skill / "assets" / "book-to-skill-followup").symlink_to(target, target_is_directory=True)
    report = check_package.run(project, ".agents/skills/demo", [], None)
    leaks = [item["file"] for item in report["errors"] if item["code"] == "nested-followup-tool"]
    assert set(leaks) == {
        ".agents/skills/demo/references/book-to-skill-followup",
        ".agents/skills/demo/assets/book-to-skill-followup",
    }
    assert "invalid-utf8-markdown" in {item["code"] for item in report["errors"]}


def test_gitless_followup_tool_installation_fails(tmp_path):
    project = make_project(tmp_path)
    install_followup_tool(project)
    report = check_package.run(project, ".agents/skills/demo", [], None)
    assert {item["code"] for item in report["errors"]} >= {"unmanaged-followup-tool"}


def test_git_tracked_followup_tool_and_alias_fail(tmp_path):
    project = make_project(tmp_path)
    install_followup_tool(project)
    init_git(project)
    subprocess.run(["git", "-C", str(project), "add", ".agents/skills/book-to-skill-followup", ".claude/skills/book-to-skill-followup"], check=True)
    report = check_package.run(project, ".agents/skills/demo", [], None)
    tracked = [item["file"] for item in report["errors"] if item["code"] == "tracked-followup-tool"]
    assert set(tracked) == {".agents/skills/book-to-skill-followup", ".claude/skills/book-to-skill-followup"}


def test_explicitly_ignored_local_followup_tool_is_allowed(tmp_path):
    project = make_project(tmp_path)
    install_followup_tool(project)
    init_git(project)
    (project / ".gitignore").write_text(
        ".agents/skills/book-to-skill-followup/\n.claude/skills/book-to-skill-followup\n", encoding="utf-8"
    )
    report = check_package.run(project, ".agents/skills/demo", [], None)
    assert report["verdict"] == "pass", report["errors"]


def test_other_host_followup_tool_is_detected(tmp_path):
    project = make_project(tmp_path)
    tool = project / ".codex" / "skills" / "book-to-skill-followup"
    tool.mkdir(parents=True)
    (tool / "SKILL.md").write_text("---\nname: book-to-skill-followup\ndescription: helper\n---\n", encoding="utf-8")
    report = check_package.run(project, ".agents/skills/demo", [], None)
    assert {item["code"] for item in report["errors"]} >= {"unmanaged-followup-tool"}


def test_tracked_followup_role_profile_fails(tmp_path):
    project = make_project(tmp_path)
    profile = project / ".codex" / "agents" / "book-followup-source-reviewer.toml"
    profile.parent.mkdir(parents=True)
    profile.write_text('name = "source-reviewer"\ndescription = "Review source"\n', encoding="utf-8")
    init_git(project)
    subprocess.run(["git", "-C", str(project), "add", ".codex/agents/book-followup-source-reviewer.toml"], check=True)
    report = check_package.run(project, ".agents/skills/demo", [], None)
    tracked = [item["file"] for item in report["errors"] if item["code"] == "tracked-followup-tool"]
    assert tracked == [".codex/agents/book-followup-source-reviewer.toml"]


def test_external_minimal_followup_target_is_not_self_validated(tmp_path):
    project = make_project(tmp_path)
    tool = project / ".agents" / "skills" / "book-to-skill-followup"
    tool.mkdir(parents=True)
    (tool / "SKILL.md").write_text("---\nname: book-to-skill-followup\ndescription: helper\n---\n", encoding="utf-8")
    report = check_package.run(project, ".agents/skills/book-to-skill-followup", [], None)
    assert report["verdict"] == "fail"
    assert "unmanaged-followup-tool" in {item["code"] for item in report["errors"]}


def test_copied_followup_checker_self_validation_is_allowed(tmp_path):
    project = make_project(tmp_path)
    install_followup_tool(project)
    copied_script = project / ".agents" / "skills" / "book-to-skill-followup" / "scripts" / "check_package.py"
    copied_script.parent.mkdir()
    copied_script.write_text((SCRIPTS / "check_package.py").read_text(encoding="utf-8"), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("copied_check_package", copied_script)
    assert spec and spec.loader
    copied_checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copied_checker)
    report = copied_checker.run(project, ".agents/skills/book-to-skill-followup", [], None)
    assert report["verdict"] == "pass", report["errors"]


def test_missing_git_binary_blocks_installed_followup_tool(tmp_path):
    project = make_project(tmp_path)
    install_followup_tool(project)
    init_git(project)
    without_git = tmp_path / "without-git"
    without_git.mkdir()
    with patch.dict(os.environ, {"PATH": str(without_git)}):
        report = check_package.run(project, ".agents/skills/demo", [], None)
    assert {item["code"] for item in report["errors"]} >= {"git-status-unavailable"}


def test_git_status_command_failure_does_not_allow_followup_tool(tmp_path):
    project = make_project(tmp_path)
    install_followup_tool(project)
    init_git(project)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text(
        "#!/bin/sh\n"
        "if [ \"$3\" = rev-parse ]; then\n"
        f"  printf '%s\\n' {shlex.quote(str(project))}\n"
        "  exit 0\n"
        "fi\n"
        "exit 2\n",
        encoding="utf-8",
    )
    fake_git.chmod(0o755)
    with patch.dict(os.environ, {"PATH": str(fake_bin)}):
        report = check_package.run(project, ".agents/skills/demo", [], None)
    assert {item["code"] for item in report["errors"]} >= {"git-status-unavailable"}


def test_git_repository_metadata_error_is_not_treated_as_non_git(tmp_path):
    project = make_project(tmp_path)
    install_followup_tool(project)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text("#!/bin/sh\necho 'fatal: repository metadata unreadable' >&2\nexit 2\n", encoding="utf-8")
    fake_git.chmod(0o755)
    with patch.dict(os.environ, {"PATH": str(fake_bin)}):
        report = check_package.run(project, ".agents/skills/demo", [], None)
    codes = {item["code"] for item in report["errors"]}
    assert "git-status-unavailable" in codes
    assert "unmanaged-followup-tool" not in codes


def test_original_followup_project_is_allowed():
    project = SCRIPTS.parents[3]
    report = check_package.run(project, ".agents/skills/book-to-skill-followup", [], None)
    assert report["verdict"] == "pass", report["errors"]


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

    def test_inline_code_link_examples_are_not_checked_as_links(self):
        with tempfile.TemporaryDirectory() as directory:
            test_inline_code_link_examples_are_not_checked_as_links(Path(directory))

    def test_rendered_url_placeholder_remains_a_missing_link(self):
        with tempfile.TemporaryDirectory() as directory:
            test_rendered_url_placeholder_remains_a_missing_link(Path(directory))

    def test_run_state_binding_rejects_different_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            test_run_state_binding_rejects_different_documents(Path(directory))

    def test_yuriring_percent_encoded_middle_dot_anchor_and_directory_link(self):
        with tempfile.TemporaryDirectory() as directory:
            test_yuriring_percent_encoded_middle_dot_anchor_and_directory_link(Path(directory))

    def test_nested_followup_tool_and_alias_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            test_nested_followup_tool_and_alias_fail(Path(directory))

    def test_followup_copy_in_references_and_named_symlink_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            test_followup_copy_in_references_and_named_symlink_fail(Path(directory))

    def test_gitless_followup_tool_installation_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            test_gitless_followup_tool_installation_fails(Path(directory))

    def test_git_tracked_followup_tool_and_alias_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            test_git_tracked_followup_tool_and_alias_fail(Path(directory))

    def test_explicitly_ignored_local_followup_tool_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            test_explicitly_ignored_local_followup_tool_is_allowed(Path(directory))

    def test_other_host_followup_tool_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            test_other_host_followup_tool_is_detected(Path(directory))

    def test_tracked_followup_role_profile_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            test_tracked_followup_role_profile_fails(Path(directory))

    def test_external_minimal_followup_target_is_not_self_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            test_external_minimal_followup_target_is_not_self_validated(Path(directory))

    def test_copied_followup_checker_self_validation_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            test_copied_followup_checker_self_validation_is_allowed(Path(directory))

    def test_missing_git_binary_blocks_installed_followup_tool(self):
        with tempfile.TemporaryDirectory() as directory:
            test_missing_git_binary_blocks_installed_followup_tool(Path(directory))

    def test_git_status_command_failure_does_not_allow_followup_tool(self):
        with tempfile.TemporaryDirectory() as directory:
            test_git_status_command_failure_does_not_allow_followup_tool(Path(directory))

    def test_git_repository_metadata_error_is_not_treated_as_non_git(self):
        with tempfile.TemporaryDirectory() as directory:
            test_git_repository_metadata_error_is_not_treated_as_non_git(Path(directory))

    def test_original_followup_project_is_allowed(self):
        test_original_followup_project_is_allowed()


if __name__ == "__main__":
    unittest.main()

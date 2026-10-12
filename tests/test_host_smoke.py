import json
import os
import stat
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

SCRIPTS = Path(__file__).parents[1] / ".agents" / "skills" / "book-to-skill-followup" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import host_smoke
import run_state
from runtime_common import claim_host, load_state, mutate_state, package_snapshot, sha256_file


def prepare_run(tmp_path: Path, host: str = "codex") -> Path:
    project = tmp_path / "project"
    skill = project / ".agents" / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n# Demo\n", encoding="utf-8")
    run = tmp_path / "run"
    run.mkdir()
    state = {"project": str(project), "skill_rel": ".agents/skills/demo", "documents": [], "host": host,
             "host_attempts": 0, "stages": {"freeze": {"status": "succeeded"}}, "freeze_snapshot": None}
    state["freeze_snapshot"] = package_snapshot(state)
    (run / "run.json").write_text(json.dumps(state), encoding="utf-8")
    (run / "prompt.txt").write_text("Use the skill. $(touch SHOULD_NOT_EXIST)", encoding="utf-8")
    return run


def executable(tmp_path: Path, body: str) -> str:
    path = tmp_path / "fake-host.py"
    path.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def test_mock_host_requires_trace_and_consumes_one_attempt(tmp_path):
    run = prepare_run(tmp_path)
    fake = executable(tmp_path, "import json, sys\nsys.stdin.read()\nprint(json.dumps([{'type':'item.completed','item':{'type':'command_execution','exit_code':0,'command':\"/bin/zsh -lc 'cat .agents/skills/demo/SKILL.md'\"}},{'type':'turn.completed'}]))\n")
    record = host_smoke.run(run, "prompt.txt", 3, fake)
    assert record["verdict"] == "pass"
    assert record["loaded"] is True and record["turn_completed"] is True
    assert record["proof_files"]
    assert not (run / "SHOULD_NOT_EXIST").exists()
    evidence = host_smoke.write_record(run, record)
    evidence_hash = sha256_file(evidence)
    second = host_smoke.run(run, "prompt.txt", 3, fake)
    assert second["verdict"] == "blocked"
    assert second["errors"][0]["code"] == "host-artifacts-exist"
    assert sha256_file(evidence) == evidence_hash


def test_host_failure_and_timeout_are_recorded(tmp_path):
    failed = prepare_run(tmp_path / "failed")
    failed_exec = executable(tmp_path / "failed", "import sys\nsys.stdin.read()\nraise SystemExit(7)\n")
    failure = host_smoke.run(failed, "prompt.txt", 3, failed_exec)
    assert failure["verdict"] == "fail"
    assert failure["errors"][0]["code"] == "host-failed"

    timed = prepare_run(tmp_path / "timed")
    timeout_exec = executable(tmp_path / "timed", "import time\nprint('partial trace', flush=True)\ntime.sleep(2)\n")
    timeout = host_smoke.run(timed, "prompt.txt", 1, timeout_exec)
    assert timeout["verdict"] == "fail"
    assert timeout["errors"][0]["code"] == "timeout"
    assert (timed / 'host/attempt.json').is_file()
    assert 'partial trace' in (timed / 'host/raw-trace.jsonl').read_text()


class HostSmokeTests(unittest.TestCase):
    def test_runtime_init_host_finish_accepts_helper_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            skill = project / ".agents" / "skills" / "demo"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n# Demo\n", encoding="utf-8")
            source = root / "source.txt"; source.write_text("source", encoding="utf-8")
            created = run_state.cmd_init(Namespace(project=str(project), skill=".agents/skills/demo", source=[str(source)], documents=[], host="codex", producer_id="producer"))
            run = Path(created["run_dir"])
            (run / "prompt.txt").write_text("Use the skill", encoding="utf-8")
            def freeze_for_host(state):
                for name in run_state.STAGES[:run_state.STAGES.index("host-smoke")]:
                    state["stages"][name]["status"] = "succeeded"
                state["freeze_snapshot"] = package_snapshot(state)
                state["subject"] = package_snapshot(state)
            mutate_state(run, freeze_for_host)
            fake = executable(root, "import json, sys\nsys.stdin.read()\nprint(json.dumps([{'type':'item.completed','item':{'type':'command_execution','exit_code':0,'command':\"/bin/zsh -lc 'cat .agents/skills/demo/SKILL.md'\"}},{'type':'turn.completed'}]))\n")
            evidence = host_smoke.run(run, "prompt.txt", 3, fake)
            self.assertEqual(evidence["verdict"], "pass")
            host_smoke.write_record(run, evidence)
            run_state.cmd_start(Namespace(run_dir=str(run), stage="host-smoke"))
            finished = run_state.cmd_finish(Namespace(run_dir=str(run), stage="host-smoke", evidence="host/record.json"))
            self.assertEqual(finished["status"], "succeeded")

    def test_codex_default_adapter_is_ephemeral_and_read_only(self):
        command, adapter = host_smoke.host_command("codex", Path("/tmp/isolated"), None)
        self.assertIsNotNone(command)
        self.assertIn("--ephemeral", command)
        self.assertIn("features.hooks=false", command)
        self.assertNotIn("--ignore-user-config", command)
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)
        self.assertEqual(adapter["mode"], "codex-readonly")

    def test_codex_trace_requires_successful_read_command(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project / ".agents" / "skills" / "demo" / "SKILL.md"
            source.parent.mkdir(parents=True)
            source.write_text("skill", encoding="utf-8")
            events = [{"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0,
                       "command": "/bin/zsh -lc 'cat .agents/skills/demo/SKILL.md'"}}]
            self.assertEqual(host_smoke.codex_read_paths(events, project), {str(source.resolve())})
            unsafe = [{"item": {"type": "command_execution", "exit_code": 0,
                       "command": "cat .agents/skills/demo/SKILL.md; touch x"}}]
            self.assertEqual(host_smoke.codex_read_paths(unsafe, project), set())

    def test_claude_profile_and_trace_bind_a_successful_read(self):
        command, adapter = host_smoke.host_command("claude", Path("/tmp/isolated"), None)
        self.assertIn("--strict-mcp-config", command)
        self.assertIn("--allowedTools", command)
        self.assertEqual(adapter["mode"], "claude-readonly")
        events = [
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "read-1", "name": "Read", "input": {"file_path": "/tmp/skill/SKILL.md"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "read-1", "is_error": False}]}},
            {"type": "result", "is_error": False},
        ]
        self.assertEqual(host_smoke.claude_read_paths(events), {str(Path("/tmp/skill/SKILL.md").resolve())})

    def test_antigravity_import_trace_requires_real_tool_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            run = prepare_run(Path(directory), "antigravity")
            self.assertEqual(host_smoke.prepare(run, "prompt.txt")["verdict"], "pass")
            claim_host(run)
            trace = [{"tool_use": {"id": "view-1", "name": "view_file", "input": {"path": str((run / "host" / "project" / ".agents" / "skills" / "demo" / "SKILL.md").resolve())}}},
                     {"tool_result": {"tool_use_id": "view-1", "is_error": False}}, {"type": "result", "is_error": False}]
            (run / "trace.json").write_text(json.dumps(trace), encoding="utf-8")
            record = host_smoke.run(run, "prompt.txt", 3, None, "trace.json")
            self.assertEqual(record["verdict"], "pass")
            self.assertTrue(record["loaded"])

    def test_antigravity_native_stream_binds_done_to_active_and_success_result(self):
        with tempfile.TemporaryDirectory() as directory:
            run = prepare_run(Path(directory), "antigravity")
            host_smoke.prepare(run, "prompt.txt")
            claim_host(run)
            source = run / "host/project/.agents/skills/demo/SKILL.md"
            step = {"conversation_id": "native-conversation", "step_index": 2, "step_type": "tool",
                    "tool_name": "view_file", "tool_info": {"name": "view_file", "parameters": {"AbsolutePath": str(source)}}}
            started = dict(step, state="ACTIVE")
            done = dict(step, state="DONE", tool_info=dict(step["tool_info"], output="5 lines, 80 bytes"))
            events = [{"event": "init", "conversation_id": "native-conversation", "init": {"cwd": str(source.parents[3])}},
                      {"event": "step_update", "step_update": started},
                      {"event": "step_update", "step_update": done},
                      {"event": "result", "result": {"conversation_id": "native-conversation", "status": "SUCCESS", "response": "done"}}]
            (run / "native.jsonl").write_text("\n".join(json.dumps(row) for row in events), encoding="utf-8")
            record = host_smoke.run(run, "prompt.txt", 3, None, "native.jsonl")
            self.assertEqual(record["verdict"], "pass")
            self.assertTrue(record["turn_completed"])
            self.assertEqual(host_smoke.agy_read_paths(events), {str(source.resolve())})
            self.assertEqual(host_smoke.agy_read_paths([events[0], events[2], events[3]]), set())
            done["tool_info"]["error"] = {"type": "PERMISSION_DENIED", "message": "denied"}
            self.assertEqual(host_smoke.agy_read_paths(events), set())
            self.assertFalse(any(x["type"] == "turn.completed" for x in host_smoke.normalized_events("antigravity", events[:-1], source.parents[3])))
            events[-1]["result"]["status"] = "ERROR"
            self.assertFalse(any(x["type"] == "turn.completed" for x in host_smoke.normalized_events("antigravity", events, source.parents[3])))

    def test_antigravity_native_stream_rejects_cross_conversation_and_changed_path(self):
        started = {"conversation_id": "main", "step_index": 1, "state": "ACTIVE", "step_type": "tool",
                   "tool_info": {"name": "view_file", "parameters": {"AbsolutePath": "/tmp/a/SKILL.md"}}}
        done = dict(started, state="DONE", conversation_id="other",
                    tool_info=dict(started["tool_info"], output="5 lines, 80 bytes"))
        events = [{"event": "init", "conversation_id": "main"}, {"event": "step_update", "step_update": started},
                  {"event": "step_update", "step_update": done}]
        self.assertEqual(host_smoke.agy_read_paths(events), set())
        done["conversation_id"] = "main"
        done["tool_info"]["parameters"] = {"AbsolutePath": "/tmp/b/SKILL.md"}
        self.assertEqual(host_smoke.agy_read_paths(events), set())
        done["conversation_id"] = {}
        self.assertEqual(host_smoke.agy_read_paths(events), set())
        malformed = [{"event": "init", "conversation_id": "main"},
                     {"event": "result", "result": {"status": "SUCCESS", "conversation_id": {}}}]
        self.assertEqual(host_smoke.normalized_events("antigravity", malformed, Path("/tmp")), [])

    def test_claude_successful_tool_result_may_omit_is_error_but_auth_error_is_not_completion(self):
        events = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "read-1", "name": "Read", "input": {"file_path": "/tmp/skill/SKILL.md"}}]}},
                  {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "read-1", "content": "skill text"}]}},
                  {"type": "result", "subtype": "success", "is_error": True, "result": "OAuth session expired"}]
        self.assertEqual(host_smoke.claude_read_paths(events), {str(Path("/tmp/skill/SKILL.md").resolve())})
        self.assertFalse(any(x["type"] == "turn.completed" for x in host_smoke.normalized_events("claude", events, Path("/tmp"))))
        events[1]["message"]["content"][0]["is_error"] = True
        self.assertEqual(host_smoke.claude_read_paths(events), set())

    def test_antigravity_native_trace_cannot_merge_conversations_or_revive_failed_steps(self):
        started = {"conversation_id": "main", "step_index": 2, "state": "ACTIVE", "step_type": "tool",
                   "tool_info": {"name": "view_file", "parameters": {"AbsolutePath": "/tmp/skill/SKILL.md"}}}
        done = dict(started, state="DONE", tool_info=dict(started["tool_info"], output="5 lines, 80 bytes"))
        original = [{"event": "init", "conversation_id": "main"},
                    {"event": "step_update", "step_update": started},
                    {"event": "step_update", "step_update": done},
                    {"event": "result", "result": {"conversation_id": "main", "status": "SUCCESS"}}]
        mixed = json.loads(json.dumps(original)); mixed.insert(0, {"event": "init", "conversation_id": "other"})
        mixed[-1]["result"]["conversation_id"] = "other"
        self.assertEqual(host_smoke.normalized_events("antigravity", mixed, Path("/tmp")), [])
        for label in ("changed-active", "error-before", "error-after", "empty", "false"):
            events = json.loads(json.dumps(original))
            if label == "changed-active":
                changed = json.loads(json.dumps(started)); changed["tool_info"]["parameters"]["AbsolutePath"] = "/tmp/other/SKILL.md"
                events.insert(2, {"event": "step_update", "step_update": changed})
            elif label.startswith("error-"):
                events.insert(2 if label == "error-before" else 3, {"event": "step_update", "step_update": dict(started, state="ERROR")})
            else:
                events[2]["step_update"]["tool_info"]["output"] = "" if label == "empty" else False
            with self.subTest(label=label):
                self.assertEqual(host_smoke.agy_read_paths(events), set())

    def test_mock_host_requires_trace_and_consumes_one_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            test_mock_host_requires_trace_and_consumes_one_attempt(Path(directory))

    def test_host_failure_and_timeout_are_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            test_host_failure_and_timeout_are_recorded(Path(directory))


if __name__ == "__main__":
    unittest.main()

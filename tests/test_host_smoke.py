import json
import os
import stat
import sys
import tempfile
import unittest
import hashlib
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


def completed_command(command: str, output: str, exit_code: int = 0, status: str = "completed") -> dict:
    return {"type": "item.completed", "item": {"type": "command_execution", "exit_code": exit_code,
            "status": status, "command": command, "aggregated_output": output}}


def test_mock_host_requires_trace_and_consumes_one_attempt(tmp_path):
    run = prepare_run(tmp_path)
    fake = executable(tmp_path, "import json, sys\nsys.stdin.read()\ntext=open('.agents/skills/demo/SKILL.md', encoding='utf-8').read()\nprint(json.dumps([{'type':'item.completed','item':{'type':'command_execution','exit_code':0,'status':'completed','command':\"/bin/zsh -lc 'cat .agents/skills/demo/SKILL.md'\",'aggregated_output':text}},{'type':'item.completed','item':{'id':'answer-1','type':'agent_message','text':'최종 답변'}},{'type':'turn.completed'}]))\n")
    record = host_smoke.run(run, "prompt.txt", 3, fake)
    assert record["verdict"] == "pass"
    assert record["loaded"] is True and record["turn_completed"] is True
    assert record["proof_files"]
    assert record["answer_file"] == "host/answer.txt"
    assert record["answer_sha256"] == hashlib.sha256("최종 답변".encode()).hexdigest()
    assert record["answer_event_id"] == "answer-1"
    assert record["answer_sha256"] != record["raw_trace_sha256"]
    assert (run / record["answer_file"]).read_text(encoding="utf-8") == "최종 답변"
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
            fake = executable(root, "import json, sys\nsys.stdin.read()\ntext=open('.agents/skills/demo/SKILL.md', encoding='utf-8').read()\nprint(json.dumps([{'type':'item.completed','item':{'type':'command_execution','exit_code':0,'status':'completed','command':\"/bin/zsh -lc 'cat .agents/skills/demo/SKILL.md'\",'aggregated_output':text}},{'type':'item.completed','item':{'id':'answer-1','type':'agent_message','text':'최종 답변'}},{'type':'turn.completed'}]))\n")
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
            events = [completed_command("/bin/zsh -lc 'cat .agents/skills/demo/SKILL.md'", "skill")]
            self.assertEqual(host_smoke.codex_read_paths(events, project), {str(source.resolve())})
            unsafe = [completed_command("cat .agents/skills/demo/SKILL.md; touch x", "skill")]
            self.assertEqual(host_smoke.codex_read_paths(unsafe, project), set())

    def test_codex_cat_bundle_requires_exact_output_and_safe_syntax(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project / ".agents" / "skills" / "demo"
            source.mkdir(parents=True)
            first = source / "first.md"; first.write_text("first\n", encoding="utf-8")
            second = source / "with space;semi.md"; second.write_text("second\n", encoding="utf-8")
            output = first.read_text(encoding="utf-8") + second.read_text(encoding="utf-8")
            command = "/bin/zsh -lc \"cat .agents/skills/demo/first.md; cat '.agents/skills/demo/with space;semi.md'\""
            self.assertEqual(host_smoke.codex_read_paths([completed_command(command, output)], project),
                             {str(first.resolve()), str(second.resolve())})
            self.assertEqual(host_smoke.codex_read_paths([completed_command("cat .agents/skills/demo/first.md", "first\n")], project),
                             {str(first.resolve())})

            crlf = source / "crlf.md"; crlf.write_bytes(b"crlf\r\n")
            self.assertEqual(host_smoke.codex_read_paths([completed_command("cat .agents/skills/demo/crlf.md", "crlf\r\n")], project),
                             {str(crlf.resolve())})
            binary = source / "binary.md"; binary.write_bytes(b"\xff")
            self.assertEqual(host_smoke.codex_read_paths([completed_command("cat .agents/skills/demo/binary.md", "")], project), set())

            outside = project.parent / "outside.md"; outside.write_text("outside\n", encoding="utf-8")
            link = source / "outside-link.md"; link.symlink_to(outside)
            external_then_project = f"cat {outside}; cat .agents/skills/demo/first.md"
            self.assertEqual(host_smoke.codex_read_paths([completed_command(external_then_project, "outside\nfirst\n")], project),
                             {str(first.resolve())})
            unsafe = [
                completed_command(command, "wrong\n"),
                completed_command("cat .agents/skills/demo/first.md | cat .agents/skills/demo/with\\ space\\;semi.md", output),
                completed_command("cat .agents/skills/demo/first.md && cat .agents/skills/demo/with\\ space\\;semi.md", output),
                completed_command("cat .agents/skills/demo/first.md || cat .agents/skills/demo/with\\ space\\;semi.md", output),
                completed_command("cat $(printf .agents/skills/demo/first.md)", "first\n"),
                completed_command("cat .agents/skills/demo/first.md > saved.md", ""),
                completed_command("cat .agents/skills/demo/first.md\ncat .agents/skills/demo/with\\ space\\;semi.md", output),
                completed_command("cd ..; cat .agents/skills/demo/first.md", "first\n"),
                completed_command("touch wrote.md", ""),
                completed_command("printf '%s' .agents/skills/demo/first.md", "first\n"),
                completed_command("cat .agents/skills/demo/outside-link.md", "outside\n"),
                completed_command("cat .agents/skills/demo/first.md", "first\n", exit_code=1),
                completed_command("cat .agents/skills/demo/first.md", "first\n", exit_code=False),
                completed_command("cat .agents/skills/demo/first.md", "first\n", status="failed"),
                {"type": "item.started", "item": completed_command("cat .agents/skills/demo/first.md", "first\n")["item"]},
            ]
            for event in unsafe:
                with self.subTest(command=event.get("item", {}).get("command")):
                    self.assertEqual(host_smoke.codex_read_paths([event], project), set())

    def test_codex_simple_sed_head_and_rg_contract_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project / ".agents" / "skills" / "demo" / "SKILL.md"
            source.parent.mkdir(parents=True)
            source.write_text("needle\n", encoding="utf-8")
            expected = {str(source.resolve())}
            for command in ("sed -n '1p' .agents/skills/demo/SKILL.md", "head -n 1 .agents/skills/demo/SKILL.md",
                            "rg needle .agents/skills/demo/SKILL.md"):
                with self.subTest(command=command):
                    self.assertEqual(host_smoke.codex_read_paths([completed_command(command, "")], project), expected)
            aggregate_success = completed_command("grep '[' .agents/skills/demo/SKILL.md; head -n 1 .agents/skills/demo/SKILL.md", "needle\n")
            self.assertEqual(host_smoke.codex_read_paths([aggregate_success], project), set())

    def test_host_blocks_when_final_assistant_answer_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            run = prepare_run(Path(directory))
            fake = executable(Path(directory), "import json, sys\nsys.stdin.read()\ntext=open('.agents/skills/demo/SKILL.md', encoding='utf-8').read()\nprint(json.dumps([{'type':'item.completed','item':{'type':'command_execution','exit_code':0,'status':'completed','command':\"cat .agents/skills/demo/SKILL.md\",'aggregated_output':text}},{'type':'turn.completed'}]))\n")
            record = host_smoke.run(run, "prompt.txt", 3, fake)
            self.assertEqual(record["verdict"], "blocked")
            self.assertIsNone(record["answer_file"])
            self.assertIsNone(record["answer_sha256"])
            self.assertIsNone(record["answer_event_id"])
            self.assertEqual(record["errors"][-1]["code"], "answer-unavailable")

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

    def test_claude_command_allows_native_skill_load_with_project_settings_only(self):
        command, adapter = host_smoke.host_command("claude", Path("/tmp/isolated"), None)
        self.assertEqual(command[command.index("--tools") + 1], "Skill,Read,Glob,Grep")
        self.assertEqual(command[command.index("--allowedTools") + 1], "Skill,Read,Glob,Grep")
        self.assertEqual(command[command.index("--setting-sources") + 1], "project")
        self.assertEqual(adapter["tools"], ["Skill", "Read", "Glob", "Grep"])

    def test_claude_native_skill_load_binds_injected_body_to_copied_master(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve() / "project"
            skill = project / ".agents" / "skills" / "demo"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n\n# Demo\n\n본문\n", encoding="utf-8")
            (project / ".claude" / "skills").mkdir(parents=True)
            (project / ".claude" / "skills" / "demo").symlink_to(Path("../../.agents/skills/demo"))
            base = project / ".claude" / "skills" / "demo"

            def trace(text: str, synthetic=True, is_error=None, between=False) -> list[dict]:
                result = {"type": "tool_result", "tool_use_id": "skill-1", "content": "Launching skill: demo"}
                if is_error is not None:
                    result["is_error"] = is_error
                rows = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "skill-1", "name": "Skill", "input": {"skill": "demo"}}]}},
                        {"type": "user", "message": {"content": [result]}}]
                if between:
                    rows.append({"type": "assistant", "message": {"content": [{"type": "text", "text": "중간"}]}})
                rows.append({"type": "user", "isSynthetic": synthetic, "message": {"content": [{"type": "text", "text": text}]}})
                return rows

            injected = f"Base directory for this skill: {base}\n\n# Demo\n\n본문\n\n\nARGUMENTS: 질문"
            master = {str((skill / "SKILL.md").resolve())}
            self.assertEqual(host_smoke.claude_skill_load_paths(trace(injected), project), master)
            self.assertIn({"type": "tool.read", "path": next(iter(master)), "success": True},
                          host_smoke.normalized_events("claude", trace(injected), project))
            self.assertEqual(host_smoke.claude_skill_load_paths(trace(injected, synthetic=None), project), set())
            self.assertEqual(host_smoke.claude_skill_load_paths(trace(injected, is_error=True), project), set())
            self.assertEqual(host_smoke.claude_skill_load_paths(trace(injected, between=True), project), set())
            changed = f"Base directory for this skill: {base}\n\n# Demo\n\n다른 본문"
            self.assertEqual(host_smoke.claude_skill_load_paths(trace(changed), project), set())
            outside = f"Base directory for this skill: {Path(directory).resolve()}\n\n# Demo\n\n본문"
            (Path(directory) / "SKILL.md").write_text("# Demo\n\n본문\n", encoding="utf-8")
            self.assertEqual(host_smoke.claude_skill_load_paths(trace(outside), project), set())
            extra = f"Base directory for this skill: {base}\n\n# Demo\n\n본문\n\n덧붙은 지시"
            self.assertEqual(host_smoke.claude_skill_load_paths(trace(extra), project), set())
            # Claude strips a BOM and keeps the file's line endings; both must still bind.
            (skill / "SKILL.md").write_bytes("﻿--- \r\nname: demo\r\ndescription: demo\r\n---\r\n\r\n# Demo\r\n\r\n본문\r\n".encode("utf-8"))
            crlf = f"Base directory for this skill: {base}\n\n# Demo\r\n\r\n본문\r\n"
            self.assertEqual(host_smoke.claude_skill_load_paths(trace(crlf), project), master)

    def test_claude_substitution_pattern_matches_the_static_checker(self):
        import check_package
        self.assertEqual(host_smoke.CLAUDE_SUBSTITUTION.pattern, check_package.CLAUDE_SUBSTITUTION.pattern)

    def test_claude_substitution_in_skill_body_blocks_before_the_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            run = prepare_run(Path(directory), "claude")
            state = json.loads((run / "run.json").read_text(encoding="utf-8"))
            skill = Path(state["project"]) / ".agents/skills/demo/SKILL.md"
            skill.write_text("---\nname: demo\ndescription: demo\n---\n# Demo\n\n가격은 $1,000이다.\n", encoding="utf-8")
            state["freeze_snapshot"] = package_snapshot(state)
            (run / "run.json").write_text(json.dumps(state), encoding="utf-8")
            fake = executable(Path(directory), "raise SystemExit('must not run')\n")
            record = host_smoke.run(run, "prompt.txt", 3, fake)
            self.assertEqual(record["errors"][-1]["code"], "claude-skill-substitution")
            self.assertNotIn("attempt_claimed", record)
            self.assertEqual(load_state(run)["host_attempts"], 0)

    def test_claude_mock_host_records_native_skill_load(self):
        with tempfile.TemporaryDirectory() as directory:
            run = prepare_run(Path(directory), "claude")
            fake = executable(Path(directory), "import json, os, sys\nsys.stdin.read()\nbase=os.path.abspath('.claude/skills/demo')\nprint(json.dumps([{'type':'assistant','message':{'content':[{'type':'tool_use','id':'skill-1','name':'Skill','input':{'skill':'demo'}}]}},{'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':'skill-1','content':'Launching skill: demo'}]}},{'type':'user','isSynthetic':True,'message':{'content':[{'type':'text','text':'Base directory for this skill: '+base+'\\n\\n# Demo\\n'}]}},{'type':'result','uuid':'claude-result','is_error':False,'result':'Claude 답변'}]))\n")
            record = host_smoke.run(run, "prompt.txt", 3, fake)
            self.assertEqual(record["verdict"], "pass")
            self.assertTrue(record["native_skill_load"])
            self.assertEqual([proof["path"] for proof in record["proof_files"]], ["host/project/.agents/skills/demo/SKILL.md"])

    def test_antigravity_import_trace_requires_real_tool_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            run = prepare_run(Path(directory), "antigravity")
            self.assertEqual(host_smoke.prepare(run, "prompt.txt")["verdict"], "pass")
            claim_host(run)
            trace = [{"tool_use": {"id": "view-1", "name": "view_file", "input": {"path": str((run / "host" / "project" / ".agents" / "skills" / "demo" / "SKILL.md").resolve())}}},
                     {"tool_result": {"tool_use_id": "view-1", "is_error": False}},
                     {"type": "result", "id": "legacy-result", "is_error": False, "result": "최종 답변"}]
            (run / "trace.json").write_text(json.dumps(trace), encoding="utf-8")
            record = host_smoke.run(run, "prompt.txt", 3, None, "trace.json")
            self.assertEqual(record["verdict"], "pass")
            self.assertTrue(record["loaded"])
            self.assertEqual(record["answer_event_id"], "legacy-result")

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
            self.assertEqual(record["answer_event_id"], "native-conversation")
            self.assertEqual(host_smoke.agy_read_paths(events), {str(source.resolve())})
            self.assertEqual(host_smoke.agy_read_paths([events[0], events[2], events[3]]), set())
            done["tool_info"]["error"] = {"type": "PERMISSION_DENIED", "message": "denied"}
            self.assertEqual(host_smoke.agy_read_paths(events), set())
            self.assertFalse(any(x["type"] == "turn.completed" for x in host_smoke.normalized_events("antigravity", events[:-1], source.parents[3])))
            events[-1]["result"]["status"] = "ERROR"
            self.assertFalse(any(x["type"] == "turn.completed" for x in host_smoke.normalized_events("antigravity", events, source.parents[3])))

    def test_final_answer_requires_host_specific_terminal_evidence(self):
        claude = [{"type": "result", "uuid": "claude-result", "is_error": False, "result": "Claude 답변"}]
        self.assertEqual(host_smoke.final_answer(claude, "claude"), ("Claude 답변", "claude-result"))
        session_bound = [{"type": "result", "session_id": "claude-session", "is_error": False, "result": "세션 답변"}]
        self.assertEqual(host_smoke.final_answer(session_bound, "claude"), ("세션 답변", "claude-session"))
        self.assertIsNone(host_smoke.final_answer([{"type": "result", "uuid": "bad", "is_error": False}], "claude"))
        legacy_agy = [{"type": "result", "id": "agy-result", "is_error": False, "result": "AGY 답변"}]
        self.assertEqual(host_smoke.final_answer(legacy_agy, "antigravity"), ("AGY 답변", "agy-result"))
        self.assertIsNone(host_smoke.final_answer([{"type": "result", "is_error": False, "result": "무결속"}], "antigravity"))

    def test_claude_mock_host_binds_final_result_text(self):
        with tempfile.TemporaryDirectory() as directory:
            run = prepare_run(Path(directory), "claude")
            fake = executable(Path(directory), "import json, os, sys\nsys.stdin.read()\npath=os.path.abspath('.agents/skills/demo/SKILL.md')\nprint(json.dumps([{'type':'assistant','message':{'content':[{'type':'tool_use','id':'read-1','name':'Read','input':{'file_path':path}}]}},{'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':'read-1','is_error':False,'content':'skill'}]}},{'type':'result','uuid':'claude-result','is_error':False,'result':'Claude 최종 답변'}]))\n")
            record = host_smoke.run(run, "prompt.txt", 3, fake)
            self.assertEqual(record["verdict"], "pass")
            self.assertFalse(record["native_skill_load"])
            self.assertEqual(record["answer_event_id"], "claude-result")
            self.assertEqual((run / record["answer_file"]).read_text(encoding="utf-8"), "Claude 최종 답변")

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

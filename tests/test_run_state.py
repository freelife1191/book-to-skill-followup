from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).parents[1] / ".agents/skills/book-to-skill-followup/scripts"
CLI = SCRIPTS / "run_state.py"
sys.path.insert(0, str(SCRIPTS))
from runtime_common import StateError, package_snapshot, sha256_file, workflow_snapshot
import run_state
from run_state import _validate_evidence


class RunStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "project"; self.project.mkdir()
        self.skill = self.project / ".agents/skills/example"; self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("# Example\n", encoding="utf-8")
        (self.project / "README.md").write_text("# Readme\n", encoding="utf-8")
        self.source = Path(self.temp.name) / "book.txt"; self.source.write_text("book", encoding="utf-8")

    def tearDown(self) -> None: self.temp.cleanup()

    def call(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(CLI), *args], text=True, capture_output=True, check=check)

    def init(self) -> Path:
        result = self.call("init", "--project", str(self.project), "--skill", ".agents/skills/example", "--source", str(self.source), "--documents", "README.md", "--host", "codex", "--producer-id", "writer")
        return Path(json.loads(result.stdout)["run_dir"])

    def language_review_evidence(self, run: Path, state: dict[str, object]) -> dict[str, object]:
        record = run / "language-review.md"
        record.write_text("독립 검토 기록\n", encoding="utf-8")
        vendor = run_state._language_review_vendor()
        upstream_skills = [
            {"id": name, "path": vendor[name][0], "sha256": vendor[name][1],
             "commit": run_state.KOREAN_SKILLS_COMMIT}
            for name in run_state.LANGUAGE_REVIEW_PIPELINE
        ]
        reviewed_files = [
            {"path": path, "sha256": digest}
            for path, digest in run_state._reviewed_language_files(state).items()
        ]
        pipeline_records = []
        for name in run_state.LANGUAGE_REVIEW_PIPELINE:
            stage_record = run / f"language-review-{name}.md"
            stage_record.write_text(f"{name} 검토 기록\n", encoding="utf-8")
            pipeline_records.append({"id": name, "reviewer_id": "language-reviewer",
                                     "path": stage_record.name, "sha256": sha256_file(stage_record)})
        manifest = run / "language-review-read-manifest.json"
        manifest.write_text(json.dumps({"skills": upstream_skills, "subject_files": reviewed_files}), encoding="utf-8")
        execution = run / "language-review-execution.json"
        host = state["host"]
        dispatch = ({"surface": "codex-native", "fork_turns": "none"} if host == "codex" else
                    {"surface": f"{host}-native", "fresh_context": True, "session_id": f"{host}-session"})
        execution.write_text(json.dumps({"reviewer_id": "language-reviewer", "method": "agent", "fresh": True,
                                         "dispatch": dispatch}), encoding="utf-8")
        return {
            "verdict": "pass",
            "subject_digest": package_snapshot(state)["digest"],
            "reviewer_id": "language-reviewer",
            "pipeline": list(run_state.LANGUAGE_REVIEW_PIPELINE),
            "upstream_skills": upstream_skills,
            "reviewed_files": reviewed_files,
            "pipeline_records": pipeline_records,
            "read_manifest": {"path": manifest.name, "sha256": sha256_file(manifest),
                              "skills": upstream_skills, "subject_files": reviewed_files},
            "review_method": {"kind": "agent", "reviewer_id": "language-reviewer", "fresh": True,
                              "dispatch": dispatch},
            "execution_record": {"path": execution.name, "sha256": sha256_file(execution),
                                 "reviewer_id": "language-reviewer", "method": "agent"},
            "meaning_preservation": {
                field: True for field in run_state.MEANING_PRESERVATION_FIELDS
            },
            "blockers": [],
            "remaining_findings": [],
            "independent_review_evidence": [{
                "kind": "agent", "reviewer_id": "language-reviewer", "path": record.name,
                "sha256": sha256_file(record),
            }],
        }

    def host_smoke_evidence(self, run: Path, state: dict[str, object]) -> dict[str, object]:
        copied = run / "host/project/.agents/skills/example/SKILL.md"
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes(self.skill.joinpath("SKILL.md").read_bytes())
        raw_events = [
            {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0,
             "status": "completed", "command": "cat .agents/skills/example/SKILL.md",
             "aggregated_output": copied.read_text(encoding="utf-8")}},
            {"type": "item.completed", "item": {"type": "agent_message", "id": "answer-1", "text": "최종 답변"}},
            {"type": "turn.completed"},
        ]
        trace = run / "host/trace.json"
        trace.write_text(json.dumps({"events": run_state.normalized_events("codex", raw_events, run / "host/project")}), encoding="utf-8")
        answer = run / "host/answer.txt"
        answer_text = "최종 답변"
        answer.write_text(answer_text, encoding="utf-8")
        raw = run / "host/raw-trace.jsonl"
        raw.write_text(json.dumps(raw_events), encoding="utf-8")
        copy_root = copied.parent
        copy_digest, copied_files = run_state.digest_tree(copy_root)
        return {
            "verdict": "pass", "host": "codex", "returncode": 0, "loaded": True,
            "turn_completed": True, "subject_digest": package_snapshot(state)["digest"],
            "trace_file": str(trace.relative_to(run)), "trace_sha256": sha256_file(trace),
            "proof_files": [{"path": str(copied.relative_to(run)), "sha256": sha256_file(copied)}],
            "answer_file": str(answer.relative_to(run)), "answer_sha256": sha256_file(answer),
            "answer_event_id": "answer-1", "raw_trace_file": str(raw.relative_to(run)),
            "raw_trace_sha256": sha256_file(raw),
            "copy_digest": copy_digest, "copied_files": copied_files,
        }

    def test_init_and_reject_symlink_source(self) -> None:
        run = self.init(); state = json.loads((run / "run.json").read_text())
        self.assertEqual(state["stages"]["preflight"]["status"], "pending")
        bad = self.source.parent / "bad.txt"; bad.symlink_to(self.source)
        failed = self.call("init", "--project", str(self.project), "--skill", ".agents/skills/example", "--source", str(bad), "--host", "codex", check=False)
        self.assertNotEqual(failed.returncode, 0)

    def test_init_allows_a_future_document_but_not_symlink_components(self) -> None:
        result = self.call("init", "--project", str(self.project), "--skill", ".agents/skills/example", "--source", str(self.source), "--documents", "docs/future.md", "--host", "codex")
        run = Path(json.loads(result.stdout)["run_dir"])
        self.assertNotIn("docs/future.md", json.loads((run / "run.json").read_text())["subject"]["files"])
        (self.project / "linked").symlink_to(self.project / "docs", target_is_directory=True)
        failed = self.call("init", "--project", str(self.project), "--skill", ".agents/skills/example", "--source", str(self.source), "--documents", "linked/future.md", "--host", "codex", check=False)
        self.assertNotEqual(failed.returncode, 0)

    def test_start_requires_prior_stage_and_fail_has_one_retry(self) -> None:
        run = self.init()
        denied = self.call("start", "--run-dir", str(run), "--stage", "inventory", check=False)
        self.assertNotEqual(denied.returncode, 0)
        self.call("start", "--run-dir", str(run), "--stage", "preflight")
        self.call("fail", "--run-dir", str(run), "--stage", "preflight", "--reason", "temporary")
        self.call("start", "--run-dir", str(run), "--stage", "preflight")
        self.call("fail", "--run-dir", str(run), "--stage", "preflight", "--reason", "again")
        denied = self.call("start", "--run-dir", str(run), "--stage", "preflight", check=False)
        self.assertNotEqual(denied.returncode, 0)

    def test_revision_limit_is_two(self) -> None:
        run = self.init()
        self.call("revise", "--run-dir", str(run), "--from-stage", "skill-refinement", "--reason", "first")
        self.call("revise", "--run-dir", str(run), "--from-stage", "documentation", "--reason", "second")
        denied = self.call("revise", "--run-dir", str(run), "--from-stage", "documentation", "--reason", "third", check=False)
        self.assertNotEqual(denied.returncode, 0)

    def test_language_review_is_a_required_pre_freeze_gate(self) -> None:
        self.assertIn("language-review", run_state.STAGES)
        self.assertLess(run_state.STAGES.index("improvement"), run_state.STAGES.index("language-review"))
        self.assertLess(run_state.STAGES.index("language-review"), run_state.STAGES.index("freeze"))

    def test_language_review_rejects_incomplete_or_tampered_evidence(self) -> None:
        run = self.init()
        state = json.loads((run / "run.json").read_text(encoding="utf-8"))
        evidence = self.language_review_evidence(run, state)
        _validate_evidence(state, "language-review", evidence, run)
        variants = []
        missing_file = json.loads(json.dumps(evidence)); missing_file["reviewed_files"].pop()
        variants.append(missing_file)
        wrong_order = json.loads(json.dumps(evidence)); wrong_order["pipeline"] = list(reversed(wrong_order["pipeline"]))
        variants.append(wrong_order)
        false_preservation = json.loads(json.dumps(evidence)); false_preservation["meaning_preservation"]["numbers"] = False
        variants.append(false_preservation)
        self_review = json.loads(json.dumps(evidence)); self_review["reviewer_id"] = "writer"
        variants.append(self_review)
        tampered_hash = json.loads(json.dumps(evidence)); tampered_hash["upstream_skills"][0]["sha256"] = "0" * 64
        variants.append(tampered_hash)
        missing_record = json.loads(json.dumps(evidence)); missing_record["independent_review_evidence"] = []
        variants.append(missing_record)
        for invalid in variants:
            with self.assertRaises(StateError):
                _validate_evidence(state, "language-review", invalid, run)

    def test_language_review_requires_fresh_dispatch_and_stage_records(self) -> None:
        run = self.init()
        state = json.loads((run / "run.json").read_text(encoding="utf-8"))
        evidence = self.language_review_evidence(run, state)
        _validate_evidence(state, "language-review", evidence, run)
        missing_dispatch = json.loads(json.dumps(evidence)); missing_dispatch.pop("execution_record")
        with self.assertRaises(StateError):
            _validate_evidence(state, "language-review", missing_dispatch, run)
        missing_stage = json.loads(json.dumps(evidence)); missing_stage["pipeline_records"].pop()
        with self.assertRaises(StateError):
            _validate_evidence(state, "language-review", missing_stage, run)
        inherited_agent = json.loads(json.dumps(evidence)); inherited_agent["review_method"]["dispatch"]["fork_turns"] = "all"
        with self.assertRaises(StateError):
            _validate_evidence(state, "language-review", inherited_agent, run)

    def test_language_review_agent_dispatch_is_host_specific(self) -> None:
        for host in ("codex", "claude", "antigravity"):
            run = self.init()
            state = json.loads((run / "run.json").read_text(encoding="utf-8")); state["host"] = host
            evidence = self.language_review_evidence(run, state)
            _validate_evidence(state, "language-review", evidence, run)
            forged = json.loads(json.dumps(evidence)); forged["review_method"]["dispatch"]["surface"] = "claude-native" if host == "codex" else "codex-native"
            with self.assertRaises(StateError): _validate_evidence(state, "language-review", forged, run)
            if host != "codex":
                stale = json.loads(json.dumps(evidence)); stale["review_method"]["dispatch"]["fresh_context"] = False
                with self.assertRaises(StateError): _validate_evidence(state, "language-review", stale, run)

    def test_language_review_vendor_rejects_full_tree_drift(self) -> None:
        def check(mutator) -> None:
            root = Path(self.temp.name) / f"vendor-{len(list(Path(self.temp.name).glob('vendor-*')))}"
            vendor = root / "assets/korean-skills"
            shutil.copytree(SCRIPTS.parent / "assets/korean-skills", vendor)
            script = root / "scripts/run_state.py"; script.parent.mkdir(); script.write_text("# fixture\n", encoding="utf-8")
            mutator(vendor)
            with patch.object(run_state, "__file__", str(script)):
                with self.assertRaises(StateError): run_state._language_review_vendor()

        check(lambda vendor: (vendor / "LICENSE").unlink())
        check(lambda vendor: (vendor / "skills/style-guide/references/tone-consistency.md").write_text("tampered", encoding="utf-8"))
        def duplicate(vendor: Path) -> None:
            provenance = json.loads((vendor / "provenance.json").read_text(encoding="utf-8"))
            provenance["files"].append(provenance["files"][0])
            (vendor / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
        check(duplicate)
        check(lambda vendor: (vendor / "undeclared.md").write_text("extra", encoding="utf-8"))
        def symlink(vendor: Path) -> None:
            (vendor / "unexpected-link").symlink_to(vendor / "LICENSE")
        check(symlink)

    def test_host_smoke_requires_bound_nonempty_answer(self) -> None:
        run = self.init()
        state = json.loads((run / "run.json").read_text(encoding="utf-8"))
        state["host_attempts"] = 1
        evidence = self.host_smoke_evidence(run, state)
        _validate_evidence(state, "host-smoke", evidence, run)
        missing = json.loads(json.dumps(evidence)); missing.pop("answer_file")
        with self.assertRaises(StateError):
            _validate_evidence(state, "host-smoke", missing, run)
        wrong_hash = json.loads(json.dumps(evidence)); wrong_hash["answer_sha256"] = "0" * 64
        with self.assertRaises(StateError):
            _validate_evidence(state, "host-smoke", wrong_hash, run)
        raw_tamper = json.loads(json.dumps(evidence)); raw_tamper["raw_trace_sha256"] = "0" * 64
        with self.assertRaises(StateError):
            _validate_evidence(state, "host-smoke", raw_tamper, run)
        no_read = json.loads(json.dumps(evidence)); raw = run / no_read["raw_trace_file"]
        raw.write_text(json.dumps([
            {"type": "item.completed", "item": {"type": "agent_message", "id": "answer-1", "text": "최종 답변"}},
            {"type": "turn.completed"},
        ]), encoding="utf-8"); no_read["raw_trace_sha256"] = sha256_file(raw)
        with self.assertRaises(StateError):
            _validate_evidence(state, "host-smoke", no_read, run)
        raw.write_text(json.dumps([
            {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0, "status": "completed",
             "command": "cat .agents/skills/example/SKILL.md", "aggregated_output": self.skill.joinpath("SKILL.md").read_text(encoding="utf-8")}},
            {"type": "item.completed", "item": {"type": "agent_message", "id": "answer-1", "text": "최종 답변"}}, {"type": "turn.completed"},
        ]), encoding="utf-8")
        trace = run / evidence["trace_file"]
        trace_data = json.loads(trace.read_text(encoding="utf-8")); trace_data["events"].append({"type": "tool.read", "success": True, "path": "/fake"})
        fake_normalized = json.loads(json.dumps(evidence)); trace.write_text(json.dumps(trace_data), encoding="utf-8")
        fake_normalized["trace_sha256"] = sha256_file(trace); fake_normalized["raw_trace_sha256"] = sha256_file(raw)
        with self.assertRaises(StateError):
            _validate_evidence(state, "host-smoke", fake_normalized, run)
        trace_data["events"] = [event for event in trace_data["events"] if event.get("type") != "turn.completed"]
        turn_mismatch = json.loads(json.dumps(evidence)); trace.write_text(json.dumps(trace_data), encoding="utf-8")
        turn_mismatch["trace_sha256"] = sha256_file(trace); turn_mismatch["raw_trace_sha256"] = sha256_file(raw)
        with self.assertRaises(StateError):
            _validate_evidence(state, "host-smoke", turn_mismatch, run)
        wrong_event = json.loads(json.dumps(evidence)); wrong_event["answer_event_id"] = "other"
        with self.assertRaises(StateError):
            _validate_evidence(state, "host-smoke", wrong_event, run)
        wrong_text = json.loads(json.dumps(evidence)); (run / wrong_text["answer_file"]).write_text("다른 답변", encoding="utf-8")
        wrong_text["answer_sha256"] = sha256_file(run / wrong_text["answer_file"])
        with self.assertRaises(StateError):
            _validate_evidence(state, "host-smoke", wrong_text, run)
        (run / evidence["answer_file"]).write_text("최종 답변", encoding="utf-8")
        no_final = json.loads(json.dumps(evidence)); raw = run / no_final["raw_trace_file"]
        raw.write_text("[]", encoding="utf-8"); no_final["raw_trace_sha256"] = sha256_file(raw)
        with self.assertRaises(StateError):
            _validate_evidence(state, "host-smoke", no_final, run)
        answer = run / evidence["answer_file"]
        answer.write_text("", encoding="utf-8")
        with self.assertRaises(StateError):
            _validate_evidence(state, "host-smoke", evidence, run)

    def test_host_smoke_binds_exact_frozen_skill_copy(self) -> None:
        run = self.init()
        state = json.loads((run / "run.json").read_text(encoding="utf-8")); state["host_attempts"] = 1
        evidence = self.host_smoke_evidence(run, state)
        copy_root = run / "host/project/.agents/skills/example"
        lookalike = run / "other/.agents/skills/example/SKILL.md"; lookalike.parent.mkdir(parents=True)
        lookalike.write_bytes((copy_root / "SKILL.md").read_bytes())
        lookalike_proof = json.loads(json.dumps(evidence)); lookalike_proof["proof_files"] = [{"path": str(lookalike.relative_to(run)), "sha256": sha256_file(lookalike)}]
        with self.assertRaises(StateError): _validate_evidence(state, "host-smoke", lookalike_proof, run)
        def update_receipt(payload):
            digest, files = run_state.digest_tree(copy_root)
            payload["copy_digest"] = digest; payload["copied_files"] = files
            master = copy_root / "SKILL.md"
            if master.is_file():
                payload["proof_files"] = [{"path": str(master.relative_to(run)), "sha256": sha256_file(master)}]
        wrong_bytes = json.loads(json.dumps(evidence)); (copy_root / "SKILL.md").write_text("wrong", encoding="utf-8"); update_receipt(wrong_bytes)
        with self.assertRaises(StateError): _validate_evidence(state, "host-smoke", wrong_bytes, run)
        (copy_root / "SKILL.md").write_bytes(self.skill.joinpath("SKILL.md").read_bytes())
        added = json.loads(json.dumps(evidence)); (copy_root / "added.md").write_text("added", encoding="utf-8"); update_receipt(added)
        with self.assertRaises(StateError): _validate_evidence(state, "host-smoke", added, run)
        (copy_root / "added.md").unlink()
        deleted = json.loads(json.dumps(evidence)); (copy_root / "SKILL.md").unlink(); update_receipt(deleted)
        with self.assertRaises(StateError): _validate_evidence(state, "host-smoke", deleted, run)

    def test_claude_native_skill_load_is_rederived_from_the_raw_trace(self) -> None:
        run = self.init()
        state = json.loads((run / "run.json").read_text(encoding="utf-8")); state["host_attempts"] = 1; state["host"] = "claude"
        evidence = self.host_smoke_evidence(run, state)
        project = run / "host/project"
        (project / ".claude/skills").mkdir(parents=True)
        (project / ".claude/skills/example").symlink_to(Path("../../.agents/skills/example"))
        base = project / ".claude/skills/example"
        raw_events = [
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "skill-1", "name": "Skill", "input": {"skill": "example"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "skill-1", "content": "Launching skill: example"}]}},
            {"type": "user", "isSynthetic": True, "message": {"content": [{"type": "text", "text": f"Base directory for this skill: {base}\n\n# Example\n"}]}},
            {"type": "result", "uuid": "answer-1", "is_error": False, "result": "최종 답변"},
        ]
        raw = run / evidence["raw_trace_file"]; raw.write_text("\n".join(json.dumps(row) for row in raw_events), encoding="utf-8")
        trace = run / evidence["trace_file"]
        trace.write_text(json.dumps({"events": run_state.normalized_events("claude", raw_events, project)}), encoding="utf-8")
        evidence.update({"host": "claude", "native_skill_load": True, "raw_trace_sha256": sha256_file(raw), "trace_sha256": sha256_file(trace)})
        _validate_evidence(state, "host-smoke", evidence, run)
        evidence["native_skill_load"] = False
        with self.assertRaises(StateError): _validate_evidence(state, "host-smoke", evidence, run)

    def test_host_smoke_requires_raw_read_of_the_copied_master(self) -> None:
        run = self.init()
        state = json.loads((run / "run.json").read_text(encoding="utf-8")); state["host_attempts"] = 1
        evidence = self.host_smoke_evidence(run, state)
        copy_root = run / "host/project/.agents/skills/example"
        (self.skill / "guide.md").write_text("guide", encoding="utf-8")
        other = copy_root / "guide.md"; other.write_text("guide", encoding="utf-8")
        digest, files = run_state.digest_tree(copy_root)
        evidence["copy_digest"] = digest; evidence["copied_files"] = files; evidence["subject_digest"] = package_snapshot(state)["digest"]
        evidence["proof_files"].append({"path": str(other.relative_to(run)), "sha256": sha256_file(other)})
        raw_events = [
            {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0, "status": "completed",
             "command": "cat .agents/skills/example/guide.md", "aggregated_output": "guide"}},
            {"type": "item.completed", "item": {"type": "agent_message", "id": "answer-1", "text": "최종 답변"}}, {"type": "turn.completed"},
        ]
        raw = run / evidence["raw_trace_file"]; raw.write_text(json.dumps(raw_events), encoding="utf-8")
        trace = run / evidence["trace_file"]
        trace.write_text(json.dumps({"events": run_state.normalized_events("codex", raw_events, run / "host/project")}), encoding="utf-8")
        evidence["raw_trace_sha256"] = sha256_file(raw); evidence["trace_sha256"] = sha256_file(trace)
        with self.assertRaises(StateError): _validate_evidence(state, "host-smoke", evidence, run)

    def test_freeze_requires_language_review_and_subject_change_stales_it(self) -> None:
        run = self.init()
        state_path = run / "run.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        for stage in run_state.STAGES[:run_state.STAGES.index("language-review")]:
            state["stages"][stage]["status"] = "succeeded"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        denied = self.call("start", "--run-dir", str(run), "--stage", "freeze", check=False)
        self.assertNotEqual(denied.returncode, 0)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["stages"]["language-review"]["status"] = "succeeded"
        state["stages"]["freeze"]["status"] = "succeeded"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        (self.project / "README.md").write_text("# Changed\n", encoding="utf-8")
        resumed = json.loads(self.call("resume", "--run-dir", str(run)).stdout)
        self.assertEqual(resumed["statuses"]["language-review"], "stale")
        self.assertEqual(resumed["statuses"]["freeze"], "stale")

    def test_revised_evidence_verification_skips_itself_but_rejects_reused_evaluators(self) -> None:
        run = self.init()
        state = json.loads((run / "run.json").read_text())
        state["revisions"] = 1
        data = {"verdict": "pass", "subject_digest": state["subject"]["digest"], "cases": []}
        for kind in ("retrieval", "application", "critique"):
            for suffix in ("in", "out", "rubric"):
                (run / f"{kind}.{suffix}").write_text(kind, encoding="utf-8")
            data["cases"].append({"id": kind, "kind": kind, "verdict": "pass", "fresh": True,
                                  "evaluator_id": "new-tester", "input_file": f"{kind}.in",
                                  "answer_file": f"{kind}.out", "rubric_file": f"{kind}.rubric",
                                  "assertions": [{"id": "meaning", "passed": True, "reason": "fixture"}],
                                  "read_files": []})
        old = json.loads(json.dumps(data))
        for case in old["cases"]:
            case["evaluator_id"] = "old-tester"
        (run / "old.json").write_text(json.dumps(old), encoding="utf-8")
        (run / "current.json").write_text(json.dumps(data), encoding="utf-8")
        prior = {"archive": {"evidence": {"path": "old.json"}}}
        current = {"archive": {"evidence": {"path": "current.json"}}}
        record = state["stages"]["behavior-tests"]
        record.update({"status": "succeeded", "evidence": current, "evidence_history": [prior, current]})
        _validate_evidence(state, "behavior-tests", data, run)
        with self.assertRaisesRegex(StateError, "new evaluator_id"):
            _validate_evidence(state, "behavior-tests", old, run)
        record["status"] = "running"
        with self.assertRaisesRegex(StateError, "new evaluator_id"):
            _validate_evidence(state, "behavior-tests", data, run)

    def test_source_change_stales_preflight_before_a_new_start(self) -> None:
        run = self.init()
        state = json.loads((run / "run.json").read_text())
        evidence = run / "preflight.json"; evidence.write_text(json.dumps({"verdict":"pass", "project": state["project"], "skill_rel": ".agents/skills/example", "source_hashes": state["source_hashes"], "write_paths": [".agents/skills/example", "README.md"], "scope_confirmed": True}), encoding="utf-8")
        self.call("start", "--run-dir", str(run), "--stage", "preflight")
        self.call("finish", "--run-dir", str(run), "--stage", "preflight", "--evidence", evidence.name)
        self.source.write_text("changed source", encoding="utf-8")
        resumed = json.loads(self.call("resume", "--run-dir", str(run)).stdout)
        self.assertTrue(resumed["preflight_stale"])
        self.assertEqual(resumed["statuses"]["preflight"], "stale")

    def test_claim_host_is_single_use_and_requires_freeze(self) -> None:
        run = self.init()
        denied = self.call("claim-host", "--run-dir", str(run), check=False)
        self.assertNotEqual(denied.returncode, 0)

    def test_complete_run_binds_evidence_and_finalizes(self) -> None:
        run = self.init()
        digest = self.call("snapshot", "--run-dir", str(run))
        snapshot = json.loads(digest.stdout); subject_digest = snapshot["digest"]
        state = json.loads((run / "run.json").read_text())
        prompt = "p1"
        evidence = {
            "preflight": {"verdict": "pass", "project": state["project"], "skill_rel": ".agents/skills/example", "source_hashes": state["source_hashes"], "write_paths": [".agents/skills/example", "README.md"], "scope_confirmed": True},
            "inventory": {"verdict": "pass", "expected_unit_ids": ["u1"], "units": [{"id": "u1", "source_path": str(self.source), "source_locator": "p1", "skill_files": [".agents/skills/example/SKILL.md"], "status": "mapped"}]},
            "source-audit": {"verdict": "pass", "units": [{"id": "u1", "verdict": "pass"}], "claims": [{"id": "c1", "unit_id": "u1", "origin": "author", "source_locator": "p1", "verdict": "pass"}], "visual_candidates": [], "visual_checks": [], "reviewer_id": "reviewer"},
            "skill-refinement": {"verdict": "pass", "units_covered": ["u1"], "changes": [], "resolutions": []},
            "documentation": {"verdict": "pass", "units_covered": ["u1"], "reviewed_prompt_ids": [prompt]},
            "static-checks": {"verdict": "pass", "errors": [], "subject_digest": subject_digest, "scanned_files": [{"path": p, "sha256": h} for p, h in snapshot["files"].items()], "files_digest": subject_digest, "project": state["project"], "skill_rel": ".agents/skills/example"},
            "behavior-tests": {"verdict": "pass", "subject_digest": subject_digest, "cases": []},
            "improvement": {"verdict": "pass", "units_covered": ["u1"], "changes": [], "revisions": 0},
            "language-review": self.language_review_evidence(run, state),
            "freeze": {"verdict": "pass", "reviewer_id": "release", "blockers": [], "addressed_findings": [], "independent_review_evidence": ["review"], "subject_digest": subject_digest},
            "host-smoke": {"verdict": "pass", "host": "codex", "returncode": 0, "loaded": True, "turn_completed": True, "proof_files": [], "subject_digest": subject_digest},
            "final-review": {"verdict": "pass", "reviewer_id": "release", "blockers": [], "post_host": True, "subject_digest": subject_digest},
        }
        # Behavior proof is deliberately concrete: three independent cases read the source.
        for kind in ("retrieval", "application", "critique"):
            input_file = run / f"{kind}.in"; answer_file = run / f"{kind}.out"; rubric_file = run / f"{kind}.rubric"
            input_file.write_text(kind, encoding="utf-8"); answer_file.write_text("ok", encoding="utf-8"); rubric_file.write_text("rubric", encoding="utf-8")
            evidence["behavior-tests"]["cases"].append({"id": f"case-{kind}", "kind": kind, "verdict": "pass", "fresh": True, "evaluator_id": "tester", "input_file": input_file.name, "answer_file": answer_file.name, "rubric_file": rubric_file.name, "assertions": [{"id": "answered", "passed": True, "reason": "fixture"}], "read_files": []})
        # Read files are project-relative in the contract, so use the declared target instead.
        skill_file = self.skill / "SKILL.md"
        skill_hash = hashlib.sha256(skill_file.read_bytes()).hexdigest()
        for case in evidence["behavior-tests"]["cases"]:
            case["read_files"] = [{"path": ".agents/skills/example/SKILL.md", "sha256": skill_hash}]
        copied = run / "host/project/.agents/skills/example/SKILL.md"; copied.parent.mkdir(parents=True)
        copied.write_bytes(skill_file.read_bytes())
        trace = run / "host/trace.json"; trace.parent.mkdir(exist_ok=True)
        answer = run / "host/answer.txt"; answer.write_text("최종 답변", encoding="utf-8")
        raw = run / "host/raw-trace.jsonl"
        raw_events = [{"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0, "status": "completed", "command": "cat .agents/skills/example/SKILL.md", "aggregated_output": skill_file.read_text(encoding="utf-8")}}, {"type": "item.completed", "item": {"type": "agent_message", "id": "answer-1", "text": "최종 답변"}}, {"type": "turn.completed"}]
        raw.write_text(json.dumps(raw_events), encoding="utf-8")
        trace.write_text(json.dumps({"events": run_state.normalized_events("codex", raw_events, run / "host/project")}), encoding="utf-8")
        copy_digest, copied_files = run_state.digest_tree(copied.parent)
        evidence["host-smoke"].update({"trace_file": str(trace.relative_to(run)), "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest(), "raw_trace_file": str(raw.relative_to(run)), "raw_trace_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(), "proof_files": [{"path": str(copied.relative_to(run)), "sha256": hashlib.sha256(copied.read_bytes()).hexdigest()}], "answer_file": str(answer.relative_to(run)), "answer_sha256": hashlib.sha256(answer.read_bytes()).hexdigest(), "answer_event_id": "answer-1", "copy_digest": copy_digest, "copied_files": copied_files})
        for stage, payload in evidence.items():
            if stage == "host-smoke":
                # A post-freeze document edit invalidates the dependent checks; each
                # stale check is then re-run against the new frozen subject.
                (self.project / "README.md").write_text("# Readme v2\n", encoding="utf-8")
                resumed = json.loads(self.call("resume", "--run-dir", str(run)).stdout)
                self.assertEqual(resumed["statuses"]["freeze"], "stale")
                refreshed = json.loads(self.call("snapshot", "--run-dir", str(run)).stdout)["digest"]
                for check in ("static-checks", "behavior-tests", "improvement", "language-review", "freeze"):
                    evidence[check]["subject_digest"] = refreshed
                    if check == "static-checks":
                        latest = json.loads(self.call("snapshot", "--run-dir", str(run)).stdout)
                        evidence[check]["scanned_files"] = [{"path": p, "sha256": h} for p, h in latest["files"].items()]
                        evidence[check]["files_digest"] = latest["digest"]
                    if check == "language-review":
                        refreshed_state = json.loads((run / "run.json").read_text(encoding="utf-8"))
                        evidence[check]["reviewed_files"] = [
                            {"path": path, "sha256": digest}
                            for path, digest in run_state._reviewed_language_files(refreshed_state).items()
                        ]
                        evidence[check]["read_manifest"]["subject_files"] = evidence[check]["reviewed_files"]
                        manifest = run / evidence[check]["read_manifest"]["path"]
                        manifest.write_text(json.dumps({"skills": evidence[check]["upstream_skills"],
                                                        "subject_files": evidence[check]["reviewed_files"]}), encoding="utf-8")
                        evidence[check]["read_manifest"]["sha256"] = sha256_file(manifest)
                    path = run / f"{check}-refresh.json"; path.write_text(json.dumps(evidence[check]), encoding="utf-8")
                    self.call("start", "--run-dir", str(run), "--stage", check)
                    self.call("finish", "--run-dir", str(run), "--stage", check, "--evidence", path.name)
                evidence["host-smoke"]["subject_digest"] = refreshed
                evidence["final-review"]["subject_digest"] = refreshed
                invalid = dict(payload); invalid["proof_files"] = []
                bad_path = run / "host-missing-proof.json"; bad_path.write_text(json.dumps(invalid), encoding="utf-8")
                self.call("start", "--run-dir", str(run), "--stage", stage)
                self.call("claim-host", "--run-dir", str(run))
                self.assertNotEqual(self.call("finish", "--run-dir", str(run), "--stage", stage, "--evidence", bad_path.name, check=False).returncode, 0)
            else:
                self.call("start", "--run-dir", str(run), "--stage", stage)
            path = run / f"{stage}.json"; path.write_text(json.dumps(payload), encoding="utf-8")
            self.call("finish", "--run-dir", str(run), "--stage", stage, "--evidence", path.name)
        self.call("finalize", "--run-dir", str(run))
        self.assertTrue(json.loads((run / "run.json").read_text())["finalized"])
        self.assertTrue((run / "evidence-archive/static-checks/1/evidence.json").is_file())
        self.assertTrue((run / "evidence-archive/static-checks/2/evidence.json").is_file())
        self.assertTrue((run / "evidence-archive/host-smoke/1/artifacts/host/answer.txt").is_file())
        (run / "retrieval.out").write_text("tampered", encoding="utf-8")
        self.assertNotEqual(self.call("verify", "--run-dir", str(run), check=False).returncode, 0)
        (run / "retrieval.out").write_text("ok", encoding="utf-8")
        (run / evidence["host-smoke"]["answer_file"]).write_text("변조된 답변\n", encoding="utf-8")
        self.assertNotEqual(self.call("verify", "--run-dir", str(run), check=False).returncode, 0)
        self.assertNotEqual(self.call("revise", "--run-dir", str(run), "--from-stage", "documentation", "--reason", "too late", check=False).returncode, 0)

    def test_standalone_skill_copy_can_initialize(self) -> None:
        standalone = Path(self.temp.name) / "standalone"
        shutil.copytree(SCRIPTS.parent, standalone)
        cli = standalone / "scripts/run_state.py"
        result = subprocess.run([sys.executable, str(cli), "init", "--project", str(self.project), "--skill", ".agents/skills/example", "--source", str(self.source), "--host", "claude"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_init_rejects_a_dag_the_sequential_runner_cannot_support(self) -> None:
        standalone = Path(self.temp.name) / "invalid-standalone"
        shutil.copytree(SCRIPTS.parent, standalone)
        spec = standalone / "references/harness-spec.json"
        payload = json.loads(spec.read_text(encoding="utf-8"))
        next(task for task in payload["tasks"] if task["id"] == "inventory")["depends_on"] = []
        spec.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run([sys.executable, str(standalone / "scripts/run_state.py"), "init", "--project", str(self.project), "--skill", ".agents/skills/example", "--source", str(self.source), "--host", "codex"], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.project / "_workspace").exists())

    def test_source_audit_rejects_empty_claims_and_missing_reviewer(self) -> None:
        run = self.init()
        state = json.loads((run / "run.json").read_text())
        preflight = run / "preflight.json"; preflight.write_text(json.dumps({"verdict": "pass", "project": state["project"], "skill_rel": ".agents/skills/example", "source_hashes": state["source_hashes"], "write_paths": [".agents/skills/example", "README.md"], "scope_confirmed": True}), encoding="utf-8")
        self.call("start", "--run-dir", str(run), "--stage", "preflight")
        self.call("finish", "--run-dir", str(run), "--stage", "preflight", "--evidence", preflight.name)
        inventory = run / "inventory.json"
        inventory.write_text(json.dumps({"verdict": "pass", "expected_unit_ids": ["u"], "units": [{"id": "u", "source_path": str(self.source), "source_locator": "p", "skill_files": [".agents/skills/example/SKILL.md"], "status": "mapped"}]}), encoding="utf-8")
        self.call("start", "--run-dir", str(run), "--stage", "inventory")
        self.call("finish", "--run-dir", str(run), "--stage", "inventory", "--evidence", inventory.name)
        audit = run / "audit.json"
        audit.write_text(json.dumps({"verdict": "pass", "units": [{"id": "u", "verdict": "pass"}], "claims": [], "visual_candidates": [], "visual_checks": []}), encoding="utf-8")
        self.call("start", "--run-dir", str(run), "--stage", "source-audit")
        self.assertNotEqual(self.call("finish", "--run-dir", str(run), "--stage", "source-audit", "--evidence", audit.name, check=False).returncode, 0)
        audit.write_text(json.dumps({"verdict": "pass", "units": [{"id": "u", "verdict": "needs-refinement"}], "claims": [{"id": "c", "unit_id": "u", "origin": "author", "source_locator": "p", "verdict": "mismatch"}], "visual_candidates": [], "visual_checks": []}), encoding="utf-8")
        self.assertNotEqual(self.call("finish", "--run-dir", str(run), "--stage", "source-audit", "--evidence", audit.name, check=False).returncode, 0)

    def test_workflow_snapshot_rejects_deep_cache_symlinks(self) -> None:
        root = Path(self.temp.name) / "workflow"; cache = root / "scripts/nested/__pycache__"
        cache.mkdir(parents=True); (root / "SKILL.md").write_text("x", encoding="utf-8")
        (cache / "bad").symlink_to(self.source)
        with self.assertRaises(StateError):
            workflow_snapshot(root)


if __name__ == "__main__":
    unittest.main()

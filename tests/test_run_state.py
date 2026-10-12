from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).parents[1] / ".agents/skills/book-to-skill-followup/scripts"
CLI = SCRIPTS / "run_state.py"
sys.path.insert(0, str(SCRIPTS))
from runtime_common import StateError, workflow_snapshot
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
        trace.write_text(json.dumps({"events": [{"type": "tool.read", "success": True, "path": str(copied)}, {"type": "turn.completed"}]}), encoding="utf-8")
        evidence["host-smoke"].update({"trace_file": str(trace.relative_to(run)), "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest(), "proof_files": [{"path": str(copied.relative_to(run)), "sha256": hashlib.sha256(copied.read_bytes()).hexdigest()}]})
        for stage, payload in evidence.items():
            if stage == "host-smoke":
                # A post-freeze document edit invalidates the dependent checks; each
                # stale check is then re-run against the new frozen subject.
                (self.project / "README.md").write_text("# Readme v2\n", encoding="utf-8")
                resumed = json.loads(self.call("resume", "--run-dir", str(run)).stdout)
                self.assertEqual(resumed["statuses"]["freeze"], "stale")
                refreshed = json.loads(self.call("snapshot", "--run-dir", str(run)).stdout)["digest"]
                for check in ("static-checks", "behavior-tests", "freeze"):
                    evidence[check]["subject_digest"] = refreshed
                    if check == "static-checks":
                        latest = json.loads(self.call("snapshot", "--run-dir", str(run)).stdout)
                        evidence[check]["scanned_files"] = [{"path": p, "sha256": h} for p, h in latest["files"].items()]
                        evidence[check]["files_digest"] = latest["digest"]
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
        (run / "retrieval.out").write_text("tampered", encoding="utf-8")
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

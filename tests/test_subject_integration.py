"""Static checker output must be usable by the real state transition API."""
import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).parents[1] / '.agents/skills/book-to-skill-followup/scripts'
sys.path.insert(0, str(SCRIPTS))
import check_package
import run_state
from runtime_common import load_state, package_snapshot


class SubjectIntegrationTests(unittest.TestCase):
    def test_real_static_report_matches_all_profiles_and_binary_document_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            project = root / 'project'
            skill = project / '.agents/skills/example'
            skill.mkdir(parents=True)
            (skill / 'SKILL.md').write_text('---\nname: example\ndescription: Example skill\n---\n# Example\n')
            docs = project / 'docs'
            docs.mkdir()
            (docs / 'index.md').write_text('# Guide\n')
            (docs / 'image.png').write_bytes(b'fixture-binary-asset')
            for tree in (skill, docs):
                cache = tree / '.pytest_cache'
                cache.mkdir()
                (cache / 'nodeids').write_text('generated cache')
            for folder, extension in (('.codex/agents', 'toml'), ('.claude/agents', 'md'), ('.agents/agents', 'md')):
                directory = project / folder
                directory.mkdir(parents=True)
                body = ('name = "reviewer"\ndescription = "Review"\n' if extension == 'toml'
                        else '---\nname: reviewer\ndescription: Review\n---\nReview only.\n')
                (directory / f'reviewer.{extension}').write_text(body)
                cache = directory / '.pytest_cache'
                cache.mkdir()
                (cache / 'nodeids').write_text('generated cache')
            source = root / 'source.md'
            source.write_text('# Source\n')
            result = run_state.cmd_init(argparse.Namespace(project=str(project), skill='.agents/skills/example',
                source=[str(source)], documents=['docs'], host='codex', producer_id='fixture-writer'))
            run = Path(result['run_dir'])
            state = load_state(run)
            # These are state-protocol fixtures, not a claim that a model reviewed this source.
            packets = {
                'preflight': {'verdict':'pass', 'project':state['project'], 'skill_rel':state['skill_rel'],
                    'source_hashes':state['source_hashes'], 'write_paths':[state['skill_rel'], 'docs'], 'scope_confirmed':True},
                'inventory': {'verdict':'pass', 'expected_unit_ids':['u1'], 'units':[{'id':'u1', 'source_path':str(source),
                    'source_locator':'heading', 'skill_files':['.agents/skills/example/SKILL.md'], 'status':'mapped'}]},
                'source-audit': {'verdict':'pass', 'reviewer_id':'fixture-reviewer', 'units':[{'id':'u1','verdict':'pass'}],
                    'claims':[{'id':'c1','unit_id':'u1','origin':'author','source_locator':'heading','verdict':'pass'}],
                    'visual_candidates':[], 'visual_checks':[]},
                'skill-refinement': {'verdict':'pass','units_covered':['u1'],'changes':[],'resolutions':[]},
                'documentation': {'verdict':'pass','units_covered':['u1'],'reviewed_prompt_ids':['p1']},
            }
            for stage, packet in packets.items():
                path = run / f'{stage}.json'
                path.write_text(json.dumps(packet))
                run_state.cmd_start(argparse.Namespace(run_dir=str(run),stage=stage))
                run_state.cmd_finish(argparse.Namespace(run_dir=str(run),stage=stage,evidence=path.name))
            report = check_package.run(project, '.agents/skills/example', ['docs'], run)
            self.assertEqual(report['verdict'], 'pass', report['errors'])
            self.assertEqual(report['files_digest'], package_snapshot(load_state(run))['digest'])
            self.assertEqual(len(report['scanned_files']), 6)
            evidence = run / 'static.json'
            evidence.write_text(json.dumps(report))
            run_state.cmd_start(argparse.Namespace(run_dir=str(run),stage='static-checks'))
            run_state.cmd_finish(argparse.Namespace(run_dir=str(run),stage='static-checks',evidence=evidence.name))
            self.assertEqual(load_state(run)['stages']['static-checks']['status'], 'succeeded')


if __name__ == '__main__':
    unittest.main()

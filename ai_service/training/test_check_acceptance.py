"""python -m unittest ai_service/training/test_check_acceptance.py"""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / 'check_acceptance.py'
DRAFT = HERE / 'acceptance_criteria.json'


def report(blast_correct=90, blast_missed=5, healthy_false=40, healthy_uncertain=10, map50=0.70,
           non_rice_accepted=0, rice_rejected=2, detector='b' * 64, excluded=('healthy__a.jpg',)):
    sick = {'n': 100, 'correct_disease': blast_correct, 'uncertain': blast_missed,
            'wrong_disease': 100 - blast_correct - blast_missed}
    return {'label': 'x', 'split': 'val', 'limit': None, 'detector_sha256': detector, 'gate_sha256': 'g' * 64,
            'environment': {'ultralytics': '8.4.178'}, 'healthy_excluded': list(excluded),
            'end_to_end': {'sick_rice_blast': dict(sick), 'sick_brown_spot': dict(sick),
                           'sick_sheath_blight': dict(sick),
                           'healthy': {'n': 100, 'false_disease': healthy_false, 'uncertain': healthy_uncertain,
                                       'reported_no_disease': 100 - healthy_false - healthy_uncertain}},
            'gate': {'rice': {'n': 1000, 'rejected': rice_rejected}, 'non_rice': {'n': 800, 'accepted': non_rice_accepted}},
            'detector_map': {'map50': map50}}


BASE = report(detector='a' * 64)


class CheckAcceptanceTests(unittest.TestCase):
    def run_check(self, candidate, baseline=BASE, approved=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            criteria = json.loads(DRAFT.read_text(encoding='utf-8'))
            if approved:
                criteria.update(status='approved', approved_by='test', approved_on='2026-11-25')
            for name, body in (('c', criteria), ('base', baseline), ('cand', candidate)):
                (root / f'{name}.json').write_text(json.dumps(body), encoding='utf-8')
            done = subprocess.run([sys.executable, str(SCRIPT), '--baseline', str(root / 'base.json'),
                                   '--candidate', str(root / 'cand.json'), '--criteria', str(root / 'c.json')],
                                  capture_output=True, text=True, encoding='utf-8', env=None)
        return done.returncode, done.stdout + done.stderr

    def test_a_candidate_meeting_every_rule_passes(self):
        code, out = self.run_check(report(healthy_false=20))
        self.assertEqual(code, 0, out)
        self.assertIn('VERDICT: PASS', out)

    def test_each_regression_fails_and_is_named(self):
        cases = {'rice_blast correct': report(healthy_false=20, blast_correct=87, blast_missed=5),
                 'rice_blast missed': report(healthy_false=20, blast_missed=8),
                 'healthy false disease': report(healthy_false=30),
                 'healthy flagged': report(healthy_false=20, healthy_uncertain=40),
                 'map50': report(healthy_false=20, map50=0.68),
                 'non-rice accepted': report(healthy_false=20, non_rice_accepted=1),
                 'rice rejected': report(healthy_false=20, rice_rejected=12)}
        for rule, candidate in cases.items():
            with self.subTest(rule=rule):
                code, out = self.run_check(candidate)
                self.assertEqual(code, 1, out)
                self.assertRegex(out, rf'FAIL\s+{rule}')

    def test_draft_criteria_never_produce_a_verdict(self):
        code, out = self.run_check(report(healthy_false=20), approved=False)
        self.assertEqual(code, 2, out)
        self.assertIn('NO VERDICT', out)
        self.assertNotIn('VERDICT: PASS', out)

    def test_incomparable_reports_are_refused(self):
        other_split = copy.deepcopy(report(healthy_false=20)); other_split['split'] = 'test'
        partial = copy.deepcopy(report(healthy_false=20)); partial['limit'] = 10
        other_gate = copy.deepcopy(report(healthy_false=20)); other_gate['gate_sha256'] = 'h' * 64
        cases = {'healthy_excluded': (report(healthy_false=20, excluded=('healthy__b.jpg',)), BASE),
                 'not been reviewed': (report(healthy_false=20, excluded=()), report(excluded=(), detector='a' * 64)),
                 'split': (other_split, BASE), 'limit': (partial, BASE), 'gate': (other_gate, BASE)}
        for reason, (candidate, baseline) in cases.items():
            with self.subTest(reason=reason):
                code, out = self.run_check(candidate, baseline)
                self.assertEqual(code, 2, out)
                self.assertIn(reason, out)

    def test_the_committed_criteria_are_still_a_draft(self):
        self.assertEqual(json.loads(DRAFT.read_text(encoding='utf-8'))['status'], 'draft')


if __name__ == '__main__': unittest.main()

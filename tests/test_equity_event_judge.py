"""Offline unit tests for the equity-event-001 deterministic judge and workspace hygiene."""
import copy
import importlib.util
import json
import pathlib
import unittest

CASE = pathlib.Path(__file__).resolve().parents[1] / 'tasks' / 'equity-event-001'
JUDGE_PATH = CASE / 'judge' / 'verify_ingest.py'
TRUTH = json.loads((CASE / 'judge' / 'ground_truth.json').read_text(encoding='utf-8'))

spec = importlib.util.spec_from_file_location('verify_ingest', JUDGE_PATH)
judge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(judge)

FORECAST = {
    'forecast': {'total_revenue_usd_m': 109896.0, 'tac_usd_m': 15228.0,
                 'net_revenue_usd_m': 94668.0,
                 'google_services_revenue_usd_m': 89637.0,
                 'google_cloud_revenue_usd_m': 20028.0,
                 'google_services_operating_income_usd_m': 40589.0,
                 'google_cloud_operating_income_usd_m': 6598.0,
                 'operating_income_usd_m': 39696.0,
                 'diluted_eps_ex_oneoffs_usd': 2.76},
    'probabilities': {'net_revenue_beat': 1.0, 'eps_beat': 1.0},
    'basis': [{'source_doc_id': 'googl-10k-20251231', 'note': 'historical revenue and TAC structure'}],
}
RECONCILIATION = {
    'actuals': {'total_revenue_usd_m': 109896.0, 'tac_usd_m': 15228.0,
                'net_revenue_usd_m': 94668.0, 'diluted_eps_usd': 5.11},
    'consensus': {'net_revenue_usd_m': 91690.0, 'diluted_eps_usd': 2.76},
    'surprise': {'net_revenue_pct_vs_consensus': 3.2479, 'eps_pct_vs_consensus': 85.1449},
    'beat_miss': {'net_revenue': 'beat', 'eps': 'beat'},
    'source_doc_ids': ['googl-8k-20260429-ex991'],
}
VERIFICATION = {
    'gaap': {'total_revenue_usd_m': 109896.0, 'tac_usd_m': 15228.0, 'net_revenue_usd_m': 94668.0,
             'operating_income_usd_m': 39696.0,
             'operating_margin_pct': TRUTH['actual']['operating_margin_pct'],
             'net_income_usd_m': 62578.0, 'diluted_eps_usd': 5.11},
    'consistency': {'press_release_matches_10q': True},
    'one_off': {'equity_gain_usd_m': 36915.0, 'core_eps_usd': 2.76},
    'segment_margins_pct': {'google_services': TRUTH['actual']['google_services_margin_pct'],
                            'google_cloud': TRUTH['actual']['google_cloud_margin_pct']},
    'source_doc_ids': ['googl-10q-20260331', 'googl-8k-20260429-ex991'],
}
READS = [('read', 'googl-10k-20251231'), ('read', 'googl-8k-20260429-ex991'),
         ('read', 'googl-10q-20260331')]


def perfect_evidence():
    forecast = copy.deepcopy(FORECAST)
    reconciliation = copy.deepcopy(RECONCILIATION)
    verification = copy.deepcopy(VERIFICATION)
    journal = []
    at = 0
    for action, doc in READS:
        at += 10
        journal.append({'at_s': at, 'action': 'read', 'ok': True, 'doc_id': doc})
    return {
        'schema_version': 1,
        'journal': journal,
        'submissions': {
            'forecast': [{'at_s': 110, 'deadline_s': 3300, 'late': False,
                          'payload': forecast, 'summary': ''}],
            'reconciliation': [{'at_s': 3720, 'deadline_s': 4800, 'late': False,
                                'payload': reconciliation, 'summary': 'release figures'}],
            'verification': [{'at_s': 21760, 'deadline_s': 22800, 'late': False,
                              'payload': verification, 'summary': '10-Q agrees'}],
        },
    }


class JudgeTests(unittest.TestCase):
    def test_perfect_submission_scores_one_on_every_deterministic_check(self):
        evidence = perfect_evidence()
        for check, scorer in judge.SCORERS.items():
            score, detail = scorer(evidence, TRUTH)
            self.assertAlmostEqual(score, 1.0, places=6,
                                   msg='%s -> %.6f (%s)' % (check, score, detail))

    def test_pick_submission_includes_deadline_boundary_and_caps_late(self):
        evidence = perfect_evidence()
        evidence['submissions']['forecast'].append(
            {'at_s': 3300, 'deadline_s': 3300, 'late': False, 'payload': FORECAST, 'summary': ''})
        picked = judge.pick_submission(evidence, 'forecast', 3300)
        self.assertEqual(picked['at_s'], 3300)
        late = judge.pick_submission(evidence, 'forecast', 3299)
        self.assertEqual(late['at_s'], 110)

    def test_uncited_or_unread_sources_are_penalised(self):
        evidence = perfect_evidence()
        evidence['submissions']['reconciliation'][0]['payload']['source_doc_ids'] = ['googl-10q-20260331']
        evidence['journal'] = [entry for entry in evidence['journal']
                               if entry.get('doc_id') != 'googl-10q-20260331']
        score, detail = judge.score_audit(evidence, TRUTH)
        self.assertLess(score, 0.9)
        self.assertIn('cited_without_read', detail)

    def test_future_citation_is_penalised_harder(self):
        evidence = perfect_evidence()
        evidence['submissions']['reconciliation'][0]['payload']['source_doc_ids'] = ['googl-10q-20260331']
        evidence['submissions']['reconciliation'][0]['at_s'] = 4800
        evidence['journal'].append({'at_s': 21760, 'action': 'read', 'ok': True,
                                    'doc_id': 'googl-10q-20260331'})
        del evidence['submissions']['verification']
        score, detail = judge.score_audit(evidence, TRUTH)
        self.assertLess(score, 0.85)
        self.assertIn('cited_before_publication', detail)

    def test_missing_forecast_basis_is_penalised(self):
        evidence = perfect_evidence()
        del evidence['submissions']['forecast'][0]['payload']['basis']
        score, detail = judge.score_audit(evidence, TRUTH)
        self.assertLess(score, 0.8)

    def test_brier_scoring_rewards_correct_probabilities(self):
        evidence = perfect_evidence()
        score, _ = judge.score_probabilities(evidence, TRUTH)
        self.assertAlmostEqual(score, 1.0)
        evidence['submissions']['forecast'][0]['payload']['probabilities'] = {
            'net_revenue_beat': 0.0, 'eps_beat': 0.0}
        score, _ = judge.score_probabilities(evidence, TRUTH)
        # 1 - Brier/2 keeps partial credit: a maximally wrong forecast still scores 0.5.
        self.assertAlmostEqual(score, 0.5)


class WorkspaceHygieneTests(unittest.TestCase):
    TRUTH_TOKENS = ('109896', '15228', '94668', '62578', '39696', '91690',
                    '36.12', '45.28', '32.94', '5.11', '2.76', '3.2479', '85.1449')

    def test_agent_visible_text_does_not_contain_ground_truth_tokens(self):
        visible = [CASE / 'prompt.md',
                   CASE / 'environment' / 'initial_workspace' / 'desk' / 'manual.md']
        for path in visible:
            text = path.read_text(encoding='utf-8')
            for token in self.TRUTH_TOKENS:
                self.assertNotIn(token, text,
                                 '%s leaks ground-truth token %r' % (path.name, token))

    def test_environment_initial_workspace_has_no_judge_material(self):
        workspace = CASE / 'environment' / 'initial_workspace'
        names = {p.relative_to(workspace).as_posix() for p in workspace.rglob('*')}
        self.assertIn('market.db', names)
        self.assertFalse([n for n in names if 'ground_truth' in n or n.startswith('judge')])


if __name__ == '__main__':
    unittest.main()

"""Offline unit tests for the equity-event-001 judge (v1.4.0 / v3.3.1).

These tests are the deterministic half of the release gate: they check the
probability skill score, per-submission audit timing, reconciliation consensus
validation, 10-Q value verification, rubric validity, and aggregate weights.
"""
import copy
import importlib.util
import json
import pathlib
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / 'tasks' / 'equity-event-001'
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
    # Events are (net revenue beat=True, core-EPS beat=False): the point forecast
    # and the EPS probability use the same one-off-excluded basis.
    'probabilities': {'net_revenue_beat': 1.0, 'eps_beat': 0.0},
    'basis': [{'source_doc_id': 'googl-10k-20251231',
               'note': 'FY2025 revenue and TAC structure from the income statement'}],
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

# Business-clock reads: 10-K at 10 (before the forecast submission at 110),
# release at 3,705 (published 3,695, before the reconciliation at 3,720) and
# 10-Q at 21,741 (published 21,731, before the verification at 21,760).
READS = [('googl-10k-20251231', 10), ('googl-8k-20260429-ex991', 3705),
         ('googl-10q-20260331', 21741)]


def perfect_evidence():
    journal = [{'at_s': at, 'action': 'read', 'ok': True, 'doc_id': doc}
               for doc, at in READS]
    return {
        'schema_version': 1,
        'journal': journal,
        'submissions': {
            'forecast': [{'at_s': 110, 'deadline_s': 3300, 'late': False,
                          'payload': copy.deepcopy(FORECAST),
                          'summary': 'pre-release forecast'}],
            'reconciliation': [{'at_s': 3720, 'deadline_s': 4800, 'late': False,
                                'payload': copy.deepcopy(RECONCILIATION),
                                'summary': 'release figures reconciled'}],
            'verification': [{'at_s': 21760, 'deadline_s': 22800, 'late': False,
                              'payload': copy.deepcopy(VERIFICATION),
                              'summary': 'release vs 10-Q; core EPS bridge'}],
        },
    }


class DeterministicScorerTests(unittest.TestCase):
    def test_perfect_submission_scores_one_on_every_deterministic_check(self):
        evidence = perfect_evidence()
        for check, scorer in judge.SCORERS.items():
            score, detail = scorer(evidence, TRUTH)
            self.assertAlmostEqual(score, 1.0, places=6,
                                   msg='%s -> %.6f (%s)' % (check, score, detail))

    def test_pick_submission_includes_deadline_boundary_and_caps_late(self):
        evidence = perfect_evidence()
        evidence['submissions']['forecast'].append(
            {'at_s': 3300, 'deadline_s': 3300, 'late': False,
             'payload': copy.deepcopy(FORECAST), 'summary': ''})
        self.assertEqual(judge.pick_submission(evidence, 'forecast', 3300)['at_s'], 3300)
        self.assertEqual(judge.pick_submission(evidence, 'forecast', 3299)['at_s'], 110)

    # -- probabilities ------------------------------------------------------
    def test_probability_skill_score(self):
        evidence = perfect_evidence()
        payload = evidence['submissions']['forecast'][0]['payload']
        score, _ = judge.score_probabilities(evidence, TRUTH)
        self.assertAlmostEqual(score, 1.0)

        payload['probabilities'] = {'net_revenue_beat': 0.5, 'eps_beat': 0.5}
        score, detail = judge.score_probabilities(evidence, TRUTH)
        self.assertAlmostEqual(score, 0.0)
        self.assertAlmostEqual(detail['bss_unclipped'], 0.0)

        payload['probabilities'] = {'net_revenue_beat': 0.0, 'eps_beat': 1.0}
        score, detail = judge.score_probabilities(evidence, TRUTH)
        self.assertEqual(score, 0.0)
        self.assertLess(detail['bss_unclipped'], 0.0)

    def test_missing_or_invalid_probabilities_score_zero(self):
        evidence = perfect_evidence()
        payload = evidence['submissions']['forecast'][0]['payload']
        del payload['probabilities']
        score, detail = judge.score_probabilities(evidence, TRUTH)
        self.assertEqual(score, 0.0)
        self.assertIn('reason', detail)
        payload['probabilities'] = {'net_revenue_beat': 1.5, 'eps_beat': 0.0}
        score, detail = judge.score_probabilities(evidence, TRUTH)
        self.assertEqual(score, 0.0)
        self.assertIn('invalid probability', detail.get('reason', ''))

    def test_probability_events_use_declared_binary_outcomes(self):
        self.assertEqual(TRUTH['expected_probability_events'],
                         {'net_revenue_beat': True, 'eps_beat': False})
        self.assertIn('probability_event_definitions', TRUTH)
        self.assertIn('core_eps_methodology', TRUTH)

    # -- audit timing -------------------------------------------------------
    def test_read_after_submission_cannot_support_that_submission(self):
        evidence = perfect_evidence()
        for entry in evidence['journal']:
            if entry['doc_id'] == 'googl-8k-20260429-ex991':
                entry['at_s'] = 3800  # after the reconciliation submission at 3720
        score, detail = judge.score_audit(evidence, TRUTH)
        self.assertLess(score, 1.0)
        reasons = [entry['reason'] for entry in detail['penalties']]
        self.assertIn('phase_citations', reasons)

    def test_later_read_cannot_retroactively_support_earlier_submission(self):
        evidence = perfect_evidence()
        for entry in evidence['journal']:
            if entry['doc_id'] == 'googl-10k-20251231':
                entry['at_s'] = 500  # after the forecast submission at 110
        score, _ = judge.score_audit(evidence, TRUTH)
        self.assertLess(score, 1.0)

    def test_read_attempt_before_publication_is_penalised(self):
        evidence = perfect_evidence()
        evidence['journal'].append({'at_s': 3600, 'action': 'read', 'ok': False,
                                    'doc_id': 'googl-8k-20260429-ex991',
                                    'reason': 'Document is not published at the current business time'})
        score, detail = judge.score_audit(evidence, TRUTH)
        self.assertAlmostEqual(detail['total_penalty'], 0.15)
        self.assertAlmostEqual(score, 0.85)

    def test_citing_a_document_that_was_not_published_yet_is_penalised(self):
        evidence = perfect_evidence()
        evidence['submissions']['reconciliation'][0]['payload']['source_doc_ids'] = [
            'googl-10q-20260331']
        score, detail = judge.score_audit(evidence, TRUTH)
        self.assertLess(score, 0.7)
        self.assertIn('cited_before_publication', json.dumps(detail))

    def test_empty_run_scores_zero_instead_of_free_audit_credit(self):
        score, detail = judge.score_audit({'schema_version': 1, 'journal': [],
                                           'submissions': {}}, TRUTH)
        self.assertEqual(score, 0.0)
        self.assertIn('nothing to audit', detail.get('reason', ''))

    def test_peer_filings_are_citable_after_publication(self):
        evidence = perfect_evidence()
        evidence['journal'].append({'at_s': 3900, 'action': 'read', 'ok': True,
                                    'doc_id': 'peer-msft-8k-20260429-ex991'})
        evidence['submissions']['reconciliation'][0]['at_s'] = 3905
        evidence['submissions']['reconciliation'][0]['payload']['source_doc_ids'] = [
            'googl-8k-20260429-ex991', 'peer-msft-8k-20260429-ex991']
        score, detail = judge.score_audit(evidence, TRUTH)
        self.assertAlmostEqual(score, 1.0, msg=json.dumps(detail))

    # -- reconciliation -----------------------------------------------------
    def test_wrong_consensus_cannot_pass_on_correct_final_surprise(self):
        evidence = perfect_evidence()
        payload = evidence['submissions']['reconciliation'][0]['payload']
        payload['consensus'] = {'net_revenue_usd_m': 95000.0, 'diluted_eps_usd': 2.76}
        score, detail = judge.score_reconciliation(evidence, TRUTH)
        self.assertLess(score, 0.8)
        self.assertLess(detail['consensus']['net_revenue_usd_m']['score'], 1.0)
        self.assertLess(detail['surprise']['net_revenue_pct_vs_consensus']['score'], 1.0)
        self.assertLess(detail['beat_miss']['net_revenue']['score'], 1.0)

    def test_wrong_surprise_is_rejected(self):
        evidence = perfect_evidence()
        payload = evidence['submissions']['reconciliation'][0]['payload']
        payload['surprise']['net_revenue_pct_vs_consensus'] = 10.0
        score, _ = judge.score_reconciliation(evidence, TRUTH)
        self.assertLess(score, 1.0)

    # -- 10-Q verification --------------------------------------------------
    def test_self_reported_boolean_does_not_earn_verification_points(self):
        evidence = perfect_evidence()
        payload = evidence['submissions']['verification'][0]['payload']
        payload['gaap'] = {}
        payload['consistency'] = {'press_release_matches_10q': True}
        score, detail = judge.score_tenq(evidence, TRUTH)
        self.assertLess(score, 0.3)
        self.assertEqual(detail['claim_only']['press_release_matches_10q'], True)

    def test_rounding_inside_margin_tolerance_passes(self):
        evidence = perfect_evidence()
        payload = evidence['submissions']['verification'][0]['payload']
        payload['gaap']['operating_margin_pct'] = 36.12
        score, detail = judge.score_tenq(evidence, TRUTH)
        self.assertGreater(score, 0.99, msg=str(detail))
        self.assertLess(score, 1.0)

    def test_wrong_verified_value_fails(self):
        evidence = perfect_evidence()
        payload = evidence['submissions']['verification'][0]['payload']
        payload['gaap']['net_income_usd_m'] = 1.0
        score, _ = judge.score_tenq(evidence, TRUTH)
        self.assertLess(score, 1.0)

    # -- forecast consistency ----------------------------------------------
    def test_forecast_accounting_identity_is_checked(self):
        evidence = perfect_evidence()
        payload = evidence['submissions']['forecast'][0]['payload']
        score, detail = judge.score_forecast_composite(evidence, TRUTH)
        self.assertAlmostEqual(score, 1.0)
        payload['forecast']['tac_usd_m'] = 16228.0
        score, detail = judge.score_forecast_composite(evidence, TRUTH)
        self.assertLess(detail['consistency']['score'], 1.0)
        self.assertLess(score, 1.0)


class RubricTests(unittest.TestCase):
    RUBRICS = ('rubric_evidence.json', 'rubric_logic.json', 'rubric_handover.json')
    EXPECTED_WEIGHTS = {'rubric_evidence.json': 10, 'rubric_logic.json': 13,
                        'rubric_handover.json': 8}

    def test_rubrics_are_valid_and_observable(self):
        for name in self.RUBRICS:
            payload = json.loads((CASE / 'judge' / name).read_text(encoding='utf-8'))
            self.assertEqual(payload['schema_version'], 1)
            self.assertIn('metadata', payload)
            criteria = payload['criteria']
            self.assertTrue(criteria)
            ids = [criterion['id'] for criterion in criteria]
            self.assertEqual(len(ids), len(set(ids)), name)
            for criterion in criteria:
                self.assertFalse(criterion.get('must_pass'), name)
                self.assertGreater(criterion.get('weight', 0), 0)
                self.assertTrue(criterion.get('description', '').strip())
            self.assertEqual(sum(criterion['weight'] for criterion in criteria),
                             self.EXPECTED_WEIGHTS[name], name)

    def test_handover_rubric_scores_existing_summary(self):
        payload = json.loads(
            (CASE / 'judge' / 'rubric_handover.json').read_text(encoding='utf-8'))
        text = ' '.join(criterion['description'] for criterion in payload['criteria'])
        self.assertIn('summary', text.lower())


class AggregateRegressionTests(unittest.TestCase):
    EXPECTED_WEIGHTS = {'forecast_composite': 55, 'probabilities': 5,
                        'one_off_analysis': 2, 'reconciliation_actuals': 2,
                        'tenq_verification': 2, 'timeliness': 1, 'audit_integrity': 2,
                        'evidence_chain': 10, 'analysis_logic': 13,
                        'handover_quality': 8}

    def test_weights_sum_and_no_must_pass(self):
        task = tomllib.loads((CASE / 'task.toml').read_text(encoding='utf-8'))
        checks = task['judge']['checks']
        weights = {check['id']: check['weight'] for check in checks}
        self.assertEqual(weights, self.EXPECTED_WEIGHTS)
        self.assertEqual(sum(weights.values()), 100)
        self.assertFalse(any(check.get('must_pass') for check in checks))
        self.assertEqual(task['judge']['aggregate']['pass_threshold'], 0.85)
        for rubric_id in ('evidence_chain', 'analysis_logic', 'handover_quality'):
            check = next(item for item in checks if item['id'] == rubric_id)
            self.assertEqual(check['type'], 'llm_rubric')
            self.assertEqual(check['connection_slot'], 'judge')
            self.assertTrue((CASE / check['rubric_file']).is_file(), rubric_id)

    def test_deterministic_checks_match_verifier(self):
        task = tomllib.loads((CASE / 'task.toml').read_text(encoding='utf-8'))
        deterministic = {check['id'] for check in task['judge']['checks']
                         if check['type'] == 'command'}
        self.assertEqual(deterministic, set(judge.SCORERS))
        self.assertEqual(set(judge.DETERMINISTIC_CHECKS), set(judge.SCORERS))


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
        self.assertFalse([name for name in names
                          if 'ground_truth' in name or name.startswith('judge')])


if __name__ == '__main__':
    unittest.main()

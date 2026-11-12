#!/usr/bin/env python3
"""Deterministic offline judge for the equity-event-001 event-stream case.

The controller exports {schema_version, case_id, journal, submissions, events,
closing_state}; this script re-scores that frozen evidence against the case
ground truth. It never calls a model and never reads the environment.

Scoring philosophy (v1.4.0 / v3.3.1 refactor)
---------------------------------------------
Only the *deterministic* checks live here. The three qualitative rubrics are
scored by the platform's llm_rubric checks. Deterministic scores come from the
candidate's own submitted payloads plus the frozen journal (business-clock
timestamped reads/submissions). No submission schema field was added for this
refactor; every criterion below is a function of fields the case already
requires.
"""
import argparse
import json
from pathlib import Path

DETERMINISTIC_CHECKS = ('forecast_composite', 'probabilities', 'one_off_analysis',
                        'reconciliation_actuals', 'tenq_verification',
                        'timeliness', 'audit_integrity')

FORECAST_METRICS = ('total_revenue_usd_m', 'net_revenue_usd_m', 'tac_usd_m',
                    'google_services_revenue_usd_m',
                    'google_cloud_revenue_usd_m',
                    'google_services_operating_income_usd_m',
                    'google_cloud_operating_income_usd_m',
                    'operating_income_usd_m',
                    'diluted_eps_ex_oneoffs_usd')
ONE_OFF_METRICS = ('equity_gain_usd_m', 'core_eps_usd')
PROBABILITY_EVENTS = ('net_revenue_beat', 'eps_beat')

# A fixed 50% reference forecast scores exactly this mean Brier score, so it is
# the reference baseline for the bounded probability skill score. It is a fixed
# reference, NOT an empirical climatology estimate.
PROBABILITY_REFERENCE_BRIER = 0.25

# Explicit tolerance for the accounting identity TotalRevenue - NetRevenue - TAC ~= 0.
FORECAST_CONSISTENCY_TOL_USD_M = 2.0

# Beat/miss threshold used by the case manual (percent surprise).
BEAT_THRESHOLD_PCT = 0.5


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def linear(predicted, actual, tolerance):
    """Partial credit for a point estimate: 1 inside zero error, 0 at tolerance."""
    if not number(predicted) or not number(tolerance) or tolerance <= 0:
        return 0.0
    return max(0.0, 1.0 - abs(float(predicted) - float(actual)) / float(tolerance))


def load_evidence(submission):
    root = Path(submission)
    for candidate in (root / 'evidence' / 'equity_event.json',
                      root / 'equity_event.json'):
        if candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                return {'_invalid': 'evidence JSON unreadable: %s' % exc}
    return {'_invalid': 'evidence/equity_event.json was not submitted'}


def pick_submission(evidence, phase, deadline):
    """Latest submission for a phase whose business time is not after deadline."""
    items = (evidence.get('submissions') or {}).get(phase) or []
    valid = [item for item in items
             if isinstance(item, dict) and number(item.get('at_s'))
             and number(deadline) and float(item['at_s']) <= float(deadline)]
    if not valid:
        return None
    return max(valid, key=lambda item: float(item['at_s']))


def payload_of(evidence, phase, deadline):
    item = pick_submission(evidence, phase, deadline)
    return (item or {}).get('payload') if item else None


def summary_of(evidence, phase, deadline):
    item = pick_submission(evidence, phase, deadline)
    return (item or {}).get('summary') if item else None


def forecast_of(evidence, truth):
    payload = payload_of(evidence, 'forecast', truth['deadlines']['forecast'])
    if not isinstance(payload, dict):
        return None
    forecast = payload.get('forecast')
    return forecast if isinstance(forecast, dict) else None


# -- forecast ----------------------------------------------------------------
def score_forecast_composite(evidence, truth):
    """Mean partial credit over the nine pre-release metrics plus accounting consistency.

    The nine metric scores carry 90% of the check; the explicit accounting
    identity TotalRevenue - NetRevenue - TAC ~= 0 carries the remaining 10%.
    The identity is not a tenth forecast metric: it only penalises internally
    inconsistent triples.
    """
    expected = truth['forecast_expected']
    tolerances = truth['forecast_tolerances']
    forecast = forecast_of(evidence, truth)
    if forecast is None:
        return 0.0, {'reason': 'no forecast submission before deadline'}
    metrics = []
    scores = []
    for metric in FORECAST_METRICS:
        predicted = forecast.get(metric)
        score = linear(predicted, expected[metric], tolerances[metric])
        scores.append(score)
        metrics.append({'metric': metric, 'predicted': predicted,
                        'actual': expected[metric],
                        'tolerance': tolerances[metric], 'score': score})
    mean_score = sum(scores) / len(scores)
    total = forecast.get('total_revenue_usd_m')
    net = forecast.get('net_revenue_usd_m')
    tac = forecast.get('tac_usd_m')
    if number(total) and number(net) and number(tac):
        residual = float(total) - float(net) - float(tac)
        consistency = max(0.0, 1.0 - abs(residual) / FORECAST_CONSISTENCY_TOL_USD_M)
    else:
        residual = None
        consistency = 0.0
    composite = 0.9 * mean_score + 0.1 * consistency
    detail = {'metrics': metrics, 'metric_mean': mean_score,
              'consistency': {'residual_usd_m': residual,
                              'tolerance_usd_m': FORECAST_CONSISTENCY_TOL_USD_M,
                              'score': consistency},
              'composite': composite}
    return composite, detail


# -- probabilities -----------------------------------------------------------
def score_probabilities(evidence, truth):
    """Bounded Brier skill score against a fixed 50% reference forecast.

    BSS = 1 - mean_Brier / 0.25, bounded below at 0. A 0.5/0.5 pair therefore
    scores exactly 0, a perfect pair scores 1, and predictions worse than the
    reference cannot earn positive credit. This is a two-event skill score, not
    a calibrated probability benchmark; the raw Brier and unclipped BSS are
    preserved in the detail for diagnostics.
    """
    payload = payload_of(evidence, 'forecast', truth['deadlines']['forecast'])
    if not isinstance(payload, dict):
        return 0.0, {'reason': 'no forecast submission before deadline'}
    probabilities = payload.get('probabilities')
    events = truth.get('expected_probability_events') or {}
    if not isinstance(probabilities, dict):
        return 0.0, {'reason': 'probabilities object missing'}
    detail_events = {}
    terms = []
    for event in PROBABILITY_EVENTS:
        outcome = events.get(event)
        if not isinstance(outcome, bool):
            return 0.0, {'reason': 'ground truth missing binary outcome for %s' % event}
        probability = probabilities.get(event)
        if not number(probability) or not (0.0 <= float(probability) <= 1.0):
            return 0.0, {'reason': 'invalid probability for %s' % event}
        term = (float(probability) - (1.0 if outcome else 0.0)) ** 2
        terms.append(term)
        detail_events[event] = {'probability': float(probability),
                                'outcome': outcome,
                                'squared_error': term}
    brier = sum(terms) / len(terms)
    bss_unclipped = 1.0 - brier / PROBABILITY_REFERENCE_BRIER
    bounded = max(0.0, bss_unclipped)
    detail = {'events': detail_events, 'brier': brier,
              'bss_unclipped': bss_unclipped,
              'reference_brier': PROBABILITY_REFERENCE_BRIER,
              'score': bounded,
              'note': ('Fixed 50% reference baseline, not an empirical '
                       'climatology; bounded so worse-than-reference is 0.')}
    return bounded, detail


# -- one-off bridge ----------------------------------------------------------
def score_one_off(evidence, truth):
    expected = truth['one_off_expected']
    tolerances = truth['one_off_tolerances']
    payload = payload_of(evidence, 'verification', truth['deadlines']['verification'])
    if not isinstance(payload, dict):
        return 0.0, {'reason': 'no verification submission before deadline'}
    one_off = payload.get('one_off')
    if not isinstance(one_off, dict):
        return 0.0, {'reason': 'one_off object missing'}
    items = []
    scores = []
    for metric in ONE_OFF_METRICS:
        predicted = one_off.get(metric)
        score = linear(predicted, expected[metric], tolerances[metric])
        scores.append(score)
        items.append({'metric': metric, 'predicted': predicted,
                      'actual': expected[metric],
                      'tolerance': tolerances[metric], 'score': score})
    return sum(scores) / len(scores), {'items': items}


# -- reconciliation ----------------------------------------------------------
def _classify(surprise_pct):
    if not number(surprise_pct):
        return None
    if float(surprise_pct) > BEAT_THRESHOLD_PCT:
        return 'beat'
    if float(surprise_pct) < -BEAT_THRESHOLD_PCT:
        return 'miss'
    return 'in-line'


def score_reconciliation(evidence, truth):
    """Reconciliation is scored on 20 internal points.

    actuals 4 x 2.5 points; submitted consensus 2 x 1 point; surprise 2 x 2
    points recomputed from the candidate's own consensus; beat/miss 2 x 2 points
    classified from the candidate's own actuals and consensus. A wrong
    consensus therefore loses the consensus points and makes the candidate's
    own surprise/classification inconsistent, so a correct final label cannot
    hide a wrong benchmark.
    """
    max_points = 20.0
    deadline = truth['deadlines']['reconciliation']
    payload = payload_of(evidence, 'reconciliation', deadline)
    if not isinstance(payload, dict):
        return 0.0, {'reason': 'no reconciliation submission before deadline',
                     'max_points': max_points}
    actuals = payload.get('actuals') if isinstance(payload.get('actuals'), dict) else {}
    consensus = payload.get('consensus') if isinstance(payload.get('consensus'), dict) else {}
    surprise = payload.get('surprise') if isinstance(payload.get('surprise'), dict) else {}
    beat_miss = payload.get('beat_miss') if isinstance(payload.get('beat_miss'), dict) else {}
    truth_actual = truth['actual']
    truth_consensus = truth['consensus']
    tol_actual = truth['tolerances']['reconciliation_actual_tol_usd_m']
    tol_eps = truth['tolerances']['reconciliation_eps_tol_usd']
    tol_surp_net = truth['tolerances']['surprise_net_revenue_tol_pct']
    tol_surp_eps = truth['tolerances']['surprise_eps_tol_pct']

    actual_items = {}
    actual_points = 0.0
    for name, metric in (('total_revenue_usd_m', 'total_revenue_usd_m'),
                         ('tac_usd_m', 'tac_usd_m'),
                         ('net_revenue_usd_m', 'net_revenue_usd_m')):
        score = linear(actuals.get(name), truth_actual[metric], tol_actual)
        actual_items[name] = {'submitted': actuals.get(name),
                             'actual': truth_actual[metric],
                             'tolerance': tol_actual, 'score': score,
                             'points': score * 2.5}
        actual_points += score * 2.5
    eps_score = linear(actuals.get('diluted_eps_usd'), truth_actual['diluted_eps_usd'], tol_eps)
    actual_items['diluted_eps_usd'] = {'submitted': actuals.get('diluted_eps_usd'),
                                       'actual': truth_actual['diluted_eps_usd'],
                                       'tolerance': tol_eps, 'score': eps_score,
                                       'points': eps_score * 2.5}
    actual_points += eps_score * 2.5

    consensus_items = {}
    consensus_points = 0.0
    for name, metric, tol in (('net_revenue_usd_m', 'net_revenue_usd_m', tol_actual),
                              ('diluted_eps_usd', 'diluted_eps_usd', tol_eps)):
        score = linear(consensus.get(name), truth_consensus[metric], tol)
        consensus_items[name] = {'submitted': consensus.get(name),
                                 'frozen_consensus': truth_consensus[metric],
                                 'tolerance': tol, 'score': score,
                                 'points': score * 1.0}
        consensus_points += score * 1.0

    surprise_items = {}
    surprise_points = 0.0
    cand_net = consensus.get('net_revenue_usd_m')
    cand_eps = consensus.get('diluted_eps_usd')
    valid_net = number(cand_net) and float(cand_net) > 0
    valid_eps = number(cand_eps) and float(cand_eps) > 0
    expected_surprise_net = None
    if valid_net:
        expected_surprise_net = round(
            (truth_actual['net_revenue_usd_m'] - float(cand_net))
            / float(cand_net) * 100.0, 4)
    expected_surprise_eps = None
    if valid_eps:
        expected_surprise_eps = round(
            (truth_actual['diluted_eps_usd'] - float(cand_eps))
            / float(cand_eps) * 100.0, 4)
    for key, expected_surprise, tol in (
            ('net_revenue_pct_vs_consensus', expected_surprise_net, tol_surp_net),
            ('eps_pct_vs_consensus', expected_surprise_eps, tol_surp_eps)):
        submitted = surprise.get(key)
        if expected_surprise is None:
            score = 0.0
        else:
            score = linear(submitted, expected_surprise, tol)
        surprise_items[key] = {'submitted': submitted,
                               'from_candidate_consensus': expected_surprise,
                               'tolerance': tol, 'score': score,
                               'points': score * 2.0}
        surprise_points += score * 2.0

    beat_items = {}
    beat_points = 0.0
    cand_actual_net = actuals.get('net_revenue_usd_m')
    cand_actual_eps = actuals.get('diluted_eps_usd')
    cand_surprise_net = None
    if number(cand_actual_net) and valid_net:
        cand_surprise_net = (float(cand_actual_net) - float(cand_net)) / float(cand_net) * 100.0
    cand_surprise_eps = None
    if number(cand_actual_eps) and valid_eps:
        cand_surprise_eps = (float(cand_actual_eps) - float(cand_eps)) / float(cand_eps) * 100.0
    for key, computed_surprise in (('net_revenue', cand_surprise_net),
                                   ('eps', cand_surprise_eps)):
        computed = _classify(computed_surprise)
        submitted = beat_miss.get(key)
        score = 1.0 if (computed is not None and submitted == computed) else 0.0
        beat_items[key] = {'submitted': submitted, 'computed': computed,
                           'score': score, 'points': score * 2.0}
        beat_points += score * 2.0

    total = actual_points + consensus_points + surprise_points + beat_points
    score = max(0.0, min(1.0, total / max_points))
    detail = {'max_points': max_points, 'points': total,
              'actuals': actual_items, 'consensus': consensus_items,
              'surprise': surprise_items, 'beat_miss': beat_items,
              'note': ('surprise and beat/miss are recomputed from the '
                       'candidate\'s own submitted consensus; consensus is '
                       'also validated against the frozen benchmark')}
    return score, detail


# -- 10-Q verification -------------------------------------------------------
TENQ_ITEMS = (
    ('total_revenue_usd_m', 'actual', 'total_revenue_usd_m', 'reconciliation_actual_tol_usd_m'),
    ('tac_usd_m', 'actual', 'tac_usd_m', 'reconciliation_actual_tol_usd_m'),
    ('net_revenue_usd_m', 'actual', 'net_revenue_usd_m', 'reconciliation_actual_tol_usd_m'),
    ('operating_income_usd_m', 'actual', 'operating_income_usd_m', 'verification_actual_tol_usd_m'),
    ('net_income_usd_m', 'actual', 'net_income_usd_m', 'verification_actual_tol_usd_m'),
    ('diluted_eps_usd', 'actual', 'diluted_eps_usd', 'verification_eps_tol_usd'),
    ('operating_margin_pct', 'actual', 'operating_margin_pct', 'margin_tol_pct'),
)


def score_tenq(evidence, truth):
    """Verification values against authoritative filed values (9 items).

    Release and 10-Q report identical consolidated figures for the seven GAAP
    lines, so checking the submitted values against the authoritative filed
    values also checks 10-Q agreement for those lines. Segment operating income
    is disclosed only in the earnings release, so the two segment-margin items
    are verified against the release disclosure. The candidate's self-reported
    ``press_release_matches_10q`` boolean is recorded as a diagnostic claim and
    is NOT scored as evidence that reconciliation was performed.
    """
    deadline = truth['deadlines']['verification']
    payload = payload_of(evidence, 'verification', deadline)
    if not isinstance(payload, dict):
        return 0.0, {'reason': 'no verification submission before deadline'}
    gaap = payload.get('gaap') if isinstance(payload.get('gaap'), dict) else {}
    margins = payload.get('segment_margins_pct') \
        if isinstance(payload.get('segment_margins_pct'), dict) else {}
    actual = truth['actual']
    tol = truth['tolerances']
    items = []
    scores = []
    for submitted_name, metric, truth_name, tol_key in TENQ_ITEMS:
        predicted = gaap.get(submitted_name)
        score = linear(predicted, actual[truth_name], tol[tol_key])
        scores.append(score)
        items.append({'item': submitted_name, 'submitted': predicted,
                      'actual': actual[truth_name], 'tolerance': tol[tol_key],
                      'score': score})
    for submitted_name, truth_key in (('google_services', 'google_services_margin_pct'),
                                      ('google_cloud', 'google_cloud_margin_pct')):
        predicted = margins.get(submitted_name)
        score = linear(predicted, actual[truth_key], tol['margin_tol_pct'])
        scores.append(score)
        items.append({'item': 'segment_margins_pct.%s' % submitted_name,
                      'submitted': predicted, 'actual': actual[truth_key],
                      'tolerance': tol['margin_tol_pct'], 'score': score})
    claim = None
    consistency = payload.get('consistency')
    if isinstance(consistency, dict) and isinstance(consistency.get('press_release_matches_10q'), bool):
        claim = consistency['press_release_matches_10q']
    score = sum(scores) / len(scores)
    detail = {'items': items, 'claim_only': {'press_release_matches_10q': claim},
              'note': ('claim_only is recorded but not scored; consolidated '
                       'values are identical in release and 10-Q, and segment '
                       'operating income is release-only')}
    return score, detail


# -- timeliness --------------------------------------------------------------
def score_timeliness(evidence, truth):
    deadlines = truth['deadlines']
    submitted = []
    for phase in ('forecast', 'reconciliation', 'verification'):
        deadline = deadlines[phase]
        items = (evidence.get('submissions') or {}).get(phase) or []
        on_time = [item for item in items
                   if isinstance(item, dict) and number(item.get('at_s'))
                   and float(item['at_s']) <= float(deadline)]
        submitted.append({'phase': phase, 'deadline_s': deadline,
                          'on_time_submission': bool(on_time),
                          'submissions': len(items)})
    score = sum(1.0 for item in submitted if item['on_time_submission']) / len(submitted)
    return score, {'phases': submitted}


# -- audit integrity ---------------------------------------------------------
def read_events(evidence):
    """Successful reads with business-clock timestamps."""
    events = []
    for entry in evidence.get('journal') or []:
        if not isinstance(entry, dict):
            continue
        if entry.get('action') != 'read' or not entry.get('ok'):
            continue
        doc = entry.get('doc_id')
        at_s = entry.get('at_s')
        if isinstance(doc, str) and doc and number(at_s):
            events.append({'doc_id': doc, 'at_s': float(at_s)})
    return events


def read_attempts(evidence):
    """Read attempts that failed because the document was not published yet."""
    attempts = []
    for entry in evidence.get('journal') or []:
        if not isinstance(entry, dict):
            continue
        if entry.get('action') != 'read' or entry.get('ok'):
            continue
        reason = str(entry.get('reason') or '')
        if 'not published' in reason.lower():
            attempts.append({'doc_id': entry.get('doc_id'),
                             'at_s': entry.get('at_s'), 'reason': reason})
    return attempts


def _cited_docs(phase, payload):
    docs = []
    if not isinstance(payload, dict):
        return docs
    if phase == 'forecast':
        basis = payload.get('basis')
        if isinstance(basis, list):
            for item in basis:
                if isinstance(item, dict) and isinstance(item.get('source_doc_id'), str):
                    docs.append(item['source_doc_id'])
    else:
        source_doc_ids = payload.get('source_doc_ids')
        if isinstance(source_doc_ids, list):
            docs.extend([doc for doc in source_doc_ids if isinstance(doc, str)])
    return docs


def _read_before(reads, doc_id, submission_at):
    return any(event['doc_id'] == doc_id and event['at_s'] <= submission_at
               for event in reads)


def score_audit(evidence, truth):
    """Citations must be real, published at submission time, and read before it.

    Per-submission audit: the latest on-time submission of each phase is
    audited using the journal timestamps. A read that happens after a
    submission cannot retroactively support that submission. Failed reads of
    unpublished documents and rejected submissions are penalised globally.
    """
    documents = truth.get('documents') or {}
    reads = read_events(evidence)
    deadlines = truth['deadlines']
    penalty = 0.0
    graded = 0
    detail = {'penalties': [], 'phases': {}}

    def add(reason, points, **extra):
        nonlocal penalty
        penalty += points
        entry = {'reason': reason, 'points': points}
        entry.update(extra)
        detail['penalties'].append(entry)

    for phase in ('forecast', 'reconciliation', 'verification'):
        deadline = deadlines[phase]
        item = pick_submission(evidence, phase, deadline)
        if not item:
            continue
        graded += 1
        submission_at = float(item['at_s'])
        payload = item.get('payload') or {}
        phase_detail = {'submission_at_s': submission_at,
                        'citations': [],
                        'penalties': [],
                        'penalty_points': 0.0}
        phase_penalty = 0.0
        basis_mode = phase == 'forecast'
        if basis_mode:
            basis = payload.get('basis') if isinstance(payload, dict) else None
            if not isinstance(basis, list) or not basis:
                phase_penalty += 0.30
                phase_detail['penalties'].append('empty_basis')
            elif not all(isinstance(entry, dict)
                         and isinstance(entry.get('source_doc_id'), str)
                         and isinstance(entry.get('note'), str)
                         for entry in basis):
                phase_penalty += 0.20
                phase_detail['penalties'].append('invalid_basis')
        for doc in _cited_docs(phase, payload):
            citation = {'doc_id': doc, 'penalty': 0.0, 'issues': []}
            if doc not in documents:
                citation['penalty'] += 0.20 if not basis_mode else 0.20
                citation['issues'].append('unknown_document')
            else:
                available_at = documents[doc].get('available_at_s')
                if number(available_at) and float(available_at) > submission_at:
                    citation['penalty'] += 0.35
                    citation['issues'].append('cited_before_publication')
                elif not _read_before(reads, doc, submission_at):
                    citation['penalty'] += 0.10 if not basis_mode else 0.05
                    citation['issues'].append('cited_without_read')
            if citation['penalty']:
                phase_penalty += citation['penalty']
                phase_detail['penalties'].append(
                    '%s (-%.2f)' % (doc, citation['penalty']))
            phase_detail['citations'].append(citation)
        if phase_penalty:
            penalty += phase_penalty
            phase_detail['penalty_points'] = phase_penalty
            detail['penalties'].append({'reason': 'phase_citations',
                                        'phase': phase,
                                        'points': phase_penalty})
        detail['phases'][phase] = phase_detail

    if graded == 0:
        # An empty run has no citations to audit; awarding full integrity credit
        # would give two points for doing nothing (negative-baseline validity).
        detail['score'] = 0.0
        detail['total_penalty'] = 0.0
        detail['reason'] = 'no graded submissions; nothing to audit'
        return 0.0, detail

    for attempt in read_attempts(evidence):
        detail['penalties'].append({'reason': 'read_unpublished',
                                    'doc_id': attempt['doc_id'],
                                    'at_s': attempt['at_s']})
    unpublished_reads = len(read_attempts(evidence))
    if unpublished_reads:
        points = min(0.3, 0.15 * unpublished_reads)
        penalty += points
        detail['penalties'].append({'reason': 'read_unpublished_total',
                                    'count': unpublished_reads,
                                    'points': points})
    rejected = 0
    for entry in evidence.get('journal') or []:
        if isinstance(entry, dict) and entry.get('action') == 'submit' and not entry.get('ok'):
            rejected += 1
    if rejected:
        points = min(0.2, 0.05 * rejected)
        penalty += points
        detail['penalties'].append({'reason': 'rejected_submissions',
                                    'count': rejected, 'points': points})
    score = max(0.0, 1.0 - penalty)
    detail['total_penalty'] = penalty
    detail['score'] = score
    return score, detail


SCORERS = {
    'forecast_composite': score_forecast_composite,
    'probabilities': score_probabilities,
    'one_off_analysis': score_one_off,
    'reconciliation_actuals': score_reconciliation,
    'tenq_verification': score_tenq,
    'timeliness': score_timeliness,
    'audit_integrity': score_audit,
}


def _reason(check_id, score, detail):
    if check_id == 'forecast_composite':
        metrics = detail.get('metrics') or []
        if not metrics:
            return str(detail.get('reason', 'no forecast'))
        weak = [m['metric'] for m in metrics if m['score'] < 0.5]
        return ('composite %.3f; accounting consistency %.3f; weak metrics: %s'
                % (detail.get('composite', score),
                   (detail.get('consistency') or {}).get('score', 0.0),
                   ', '.join(weak) if weak else 'none'))
    if check_id == 'probabilities':
        if 'reason' in detail:
            return str(detail['reason'])
        return ('brier %.3f; bss unclipped %.3f; bounded score %.3f'
                % (detail.get('brier', 0.0),
                   detail.get('bss_unclipped', 0.0), score))
    if check_id == 'reconciliation_actuals':
        if 'points' in detail:
            return ('%.1f / %.0f internal points'
                    % (detail['points'], detail['max_points']))
        return str(detail.get('reason', ''))
    if check_id == 'audit_integrity':
        return ('penalty %.2f; score %.3f; issues: %s'
                % (detail.get('total_penalty', 0.0), score,
                   ', '.join(p.get('reason', '') for p in detail.get('penalties', []))
                   or 'none'))
    return 'score %.4f' % score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', required=True)
    parser.add_argument('--submission', required=True)
    parser.add_argument('--result', required=True)
    parser.add_argument('--check', required=True)
    args = parser.parse_args()
    truth = json.loads(Path(args.scenario).read_text(encoding='utf-8'))
    evidence = load_evidence(args.submission)
    if '_invalid' in evidence:
        score, detail = 0.0, {'reason': evidence['_invalid']}
    else:
        scorer = SCORERS.get(args.check)
        if scorer is None:
            raise SystemExit('unknown check: %s' % args.check)
        score, detail = scorer(evidence, truth)
    score = max(0.0, min(1.0, float(score)))
    result = {'schema_version': 1, 'check_id': args.check,
              'outcome': 'pass' if score >= 0.999999 else 'fail',
              'score': score, 'reason': _reason(args.check, score, detail),
              'detail': detail}
    target = Path(args.result)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True), encoding='utf-8')
    print(json.dumps({'check_id': args.check, 'score': score,
                      'outcome': result['outcome']}))


if __name__ == '__main__':
    main()

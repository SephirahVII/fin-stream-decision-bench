#!/usr/bin/env python3
"""Deterministic offline judge for the equity-event-001 event-stream case.

The controller exports {schema_version, case_id, journal, submissions, events,
closing_state}; this script re-scores that frozen evidence against the case
ground truth. It never calls a model and never reads the environment.
"""
import argparse
import json
from pathlib import Path

DETERMINISTIC_CHECKS = ('forecast_composite', 'probabilities', 'one_off_analysis',
                        'reconciliation_actuals', 'tenq_verification',
                        'timeliness', 'audit_integrity')

FORECAST_METRICS = ('total_revenue_usd_m', 'net_revenue_usd_m', 'tac_usd_m',
                    'google_services_revenue_usd_m', 'google_cloud_revenue_usd_m',
                    'google_services_operating_income_usd_m',
                    'google_cloud_operating_income_usd_m',
                    'operating_income_usd_m', 'diluted_eps_ex_oneoffs_usd')
ONE_OFF_METRICS = ('equity_gain_usd_m', 'core_eps_usd')


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def linear(predicted, actual, tolerance):
    if not number(predicted) or tolerance <= 0:
        return 0.0
    return max(0.0, 1.0 - abs(float(predicted) - float(actual)) / float(tolerance))


def load_evidence(submission):
    root = Path(submission)
    for candidate in (root / 'evidence' / 'equity_event.json', root / 'equity_event.json'):
        if candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                return {'_invalid': 'evidence JSON unreadable: %s' % exc}
    return {'_invalid': 'evidence/equity_event.json was not submitted'}


def pick_submission(evidence, phase, deadline):
    items = (evidence.get('submissions') or {}).get(phase) or []
    valid = [item for item in items
             if isinstance(item, dict) and isinstance(item.get('at_s'), int)
             and item['at_s'] <= deadline]
    if not valid:
        return None
    return max(valid, key=lambda item: item['at_s'])


def payload_of(evidence, phase, deadline):
    submission = pick_submission(evidence, phase, deadline)
    if submission is None:
        return None
    payload = submission.get('payload')
    return payload if isinstance(payload, dict) else None


def summary_of(evidence, phase, deadline):
    submission = pick_submission(evidence, phase, deadline)
    if submission is None:
        return ''
    value = submission.get('summary')
    return value if isinstance(value, str) else ''


def forecast_of(evidence, truth):
    payload = payload_of(evidence, 'forecast', truth['deadlines']['forecast'])
    if not payload:
        return None
    forecast = payload.get('forecast')
    return forecast if isinstance(forecast, dict) else None


def score_forecast_composite(evidence, truth):
    forecast = forecast_of(evidence, truth)
    if not forecast:
        return 0.0, {'reason': 'no valid forecast submission before the deadline'}
    expected = truth['forecast_expected']
    tolerances = truth['forecast_tolerances']
    detail = {}
    scores = []
    for metric in FORECAST_METRICS:
        value = forecast.get(metric)
        score = linear(value, expected[metric], tolerances[metric])
        scores.append(score)
        detail[metric] = {'predicted': value if number(value) else None,
                          'actual': expected[metric],
                          'tolerance': tolerances[metric],
                          'score': round(score, 4)}
    score = sum(scores) / len(scores)
    detail['composite'] = round(score, 4)
    return score, detail


def score_one_off(evidence, truth):
    payload = payload_of(evidence, 'verification', truth['deadlines']['verification'])
    if not payload:
        return 0.0, {'reason': 'no valid verification submission before the deadline'}
    one_off = payload.get('one_off')
    if not isinstance(one_off, dict):
        return 0.0, {'reason': 'verification payload has no one_off object'}
    expected = truth['one_off_expected']
    tolerances = truth['one_off_tolerances']
    detail = {}
    scores = []
    for metric in ONE_OFF_METRICS:
        value = one_off.get(metric)
        score = linear(value, expected[metric], tolerances[metric])
        scores.append(score)
        detail[metric] = {'predicted': value if number(value) else None,
                          'actual': expected[metric],
                          'tolerance': tolerances[metric],
                          'score': round(score, 4)}
    score = sum(scores) / len(scores)
    detail['composite'] = round(score, 4)
    return score, detail


def score_probabilities(evidence, truth):
    payload = payload_of(evidence, 'forecast', truth['deadlines']['forecast'])
    probabilities = (payload or {}).get('probabilities') or {}
    events = truth['expected_probability_events']
    briers = []
    for name, happened in events.items():
        value = probabilities.get(name)
        if not number(value) or not (0.0 <= float(value) <= 1.0):
            return 0.0, {'missing': name}
        briers.append((float(value) - (1.0 if happened else 0.0)) ** 2)
    brier = sum(briers) / len(briers)
    return max(0.0, 1.0 - brier / 2.0), {'brier': brier, 'probabilities': probabilities}


def score_reconciliation(evidence, truth):
    payload = payload_of(evidence, 'reconciliation', truth['deadlines']['reconciliation'])
    actual = truth['actual']
    tolerances = truth['tolerances']
    points, maximum, detail = 0.0, 4 * 3 + 2 * 2 + 2 * 2, {}
    submitted = (payload or {}).get('actuals') or {}
    for key, weight in (('total_revenue_usd_m', 3), ('tac_usd_m', 3),
                        ('net_revenue_usd_m', 3), ('diluted_eps_usd', 3)):
        tolerance = tolerances['reconciliation_eps_tol_usd'] if key == 'diluted_eps_usd' \
            else tolerances['reconciliation_actual_tol_usd_m']
        part = linear(submitted.get(key), actual[key], tolerance)
        points += part * weight
        detail[key] = round(part * weight, 3)
    surprises = (payload or {}).get('surprise') or {}
    for key, actual_key, tolerance_key in (
            ('net_revenue_pct_vs_consensus', 'net_revenue_pct', 'surprise_net_revenue_tol_pct'),
            ('eps_pct_vs_consensus', 'eps_pct', 'surprise_eps_tol_pct')):
        part = linear(surprises.get(key), truth['surprise_expected'][actual_key],
                      tolerances[tolerance_key])
        points += part * 2
        detail[key] = round(part * 2, 3)
    calls = (payload or {}).get('beat_miss') or {}
    for key in ('net_revenue', 'eps'):
        hit = 1.0 if calls.get(key) == truth['expected_beat_miss'][key] else 0.0
        points += hit * 2
        detail['beat_miss_' + key] = hit * 2
    return points / maximum, detail


def score_tenq(evidence, truth):
    payload = payload_of(evidence, 'verification', truth['deadlines']['verification'])
    gaap = (payload or {}).get('gaap') or {}
    consistency = ((payload or {}).get('consistency') or {}).get('press_release_matches_10q')
    segments = (payload or {}).get('segment_margins_pct') or {}
    actual = truth['actual']
    tolerances = truth['tolerances']
    items = [
        ('total_revenue_usd_m', linear(gaap.get('total_revenue_usd_m'),
                                       actual['total_revenue_usd_m'],
                                       tolerances['verification_actual_tol_usd_m'])),
        ('tac_usd_m', linear(gaap.get('tac_usd_m'), actual['tac_usd_m'],
                             tolerances['verification_actual_tol_usd_m'])),
        ('net_revenue_usd_m', linear(gaap.get('net_revenue_usd_m'),
                                     actual['net_revenue_usd_m'],
                                     tolerances['verification_actual_tol_usd_m'])),
        ('operating_income_usd_m', linear(gaap.get('operating_income_usd_m'),
                                          actual['operating_income_usd_m'],
                                          tolerances['verification_actual_tol_usd_m'])),
        ('net_income_usd_m', linear(gaap.get('net_income_usd_m'),
                                    actual['net_income_usd_m'],
                                    tolerances['verification_actual_tol_usd_m'])),
        ('diluted_eps_usd', linear(gaap.get('diluted_eps_usd'),
                                   actual['diluted_eps_usd'],
                                   tolerances['verification_eps_tol_usd'])),
        ('operating_margin_pct', linear(gaap.get('operating_margin_pct'),
                                        actual['operating_margin_pct'],
                                        tolerances['margin_tol_pct'])),
        ('google_services_margin_pct', linear(segments.get('google_services'),
                                              actual['google_services_margin_pct'],
                                              tolerances['margin_tol_pct'])),
        ('google_cloud_margin_pct', linear(segments.get('google_cloud'),
                                           actual['google_cloud_margin_pct'],
                                           tolerances['margin_tol_pct'])),
        ('press_release_matches_10q', 1.0 if consistency is True else 0.0),
    ]
    points = sum(value for _, value in items)
    detail = {name: round(value, 3) for name, value in items}
    return points / 10.0, detail


def score_timeliness(evidence, truth):
    submissions = evidence.get('submissions') or {}
    hits = []
    for phase, deadline in truth['deadlines'].items():
        items = submissions.get(phase) or []
        hits.append(any(isinstance(item, dict) and isinstance(item.get('at_s'), int)
                        and item['at_s'] <= deadline for item in items))
    return sum(1 for hit in hits if hit) / 3.0, {'phases_on_time': hits}


def read_documents(evidence):
    docs = set()
    for entry in evidence.get('journal') or []:
        if (isinstance(entry, dict) and entry.get('action') == 'read'
                and entry.get('ok') and isinstance(entry.get('doc_id'), str)):
            docs.add(entry['doc_id'])
    return docs


def score_audit(evidence, truth):
    """Citation audit: published-at-submission, actually-read, and basis integrity."""
    documents = truth['documents']
    submissions = evidence.get('submissions') or {}
    reads = read_documents(evidence)
    penalty, detail = 0.0, {}
    for phase, items in submissions.items():
        for item in items or []:
            if not isinstance(item, dict):
                continue
            payload = item.get('payload') or {}
            at_s = item.get('at_s')
            for doc_id in payload.get('source_doc_ids') or []:
                if not isinstance(doc_id, str):
                    penalty += 0.2
                    detail.setdefault('invalid_citation_type', []).append(str(doc_id))
                    continue
                meta = documents.get(doc_id)
                if meta is None:
                    penalty += 0.2
                    detail.setdefault('unknown_document', []).append(doc_id)
                elif isinstance(at_s, int) and meta['available_at_s'] > at_s:
                    penalty += 0.35
                    detail.setdefault('cited_before_publication', []).append(doc_id)
                elif doc_id not in reads:
                    penalty += 0.1
                    detail.setdefault('cited_without_read', []).append(doc_id)
            if phase == 'forecast':
                basis = payload.get('basis') or []
                if not basis:
                    penalty += 0.3
                    detail['empty_basis'] = True
                for entry in basis:
                    if not isinstance(entry, dict):
                        penalty += 0.2
                        detail.setdefault('invalid_basis_entry', []).append(str(entry)[:80])
                        continue
                    doc_id = entry.get('source_doc_id')
                    meta = documents.get(doc_id) if isinstance(doc_id, str) else None
                    if meta is None:
                        penalty += 0.2
                        detail.setdefault('unknown_basis_document', []).append(str(doc_id))
                    elif isinstance(at_s, int) and meta['available_at_s'] > at_s:
                        penalty += 0.35
                        detail.setdefault('basis_cited_before_publication', []).append(doc_id)
                    elif doc_id not in reads:
                        penalty += 0.05
                        detail.setdefault('basis_document_not_read', []).append(doc_id)
    journal_penalty = 0.0
    for entry in evidence.get('journal') or []:
        if not isinstance(entry, dict) or entry.get('ok'):
            continue
        reason = str(entry.get('reason') or '')
        if entry.get('action') == 'read' and 'not published' in reason.lower():
            journal_penalty = min(0.3, journal_penalty + 0.15)
            detail.setdefault('read_unpublished', []).append(entry.get('doc_id'))
        elif entry.get('action') == 'submit':
            journal_penalty = min(0.2, journal_penalty + 0.05)
            detail.setdefault('rejected_submissions', []).append(entry.get('phase'))
    score = max(0.0, 1.0 - penalty - journal_penalty)
    detail['penalty'] = round(penalty + journal_penalty, 3)
    return score, detail


SCORERS = {
    'forecast_composite': score_forecast_composite,
    'one_off_analysis': score_one_off,
    'probabilities': score_probabilities,
    'reconciliation_actuals': score_reconciliation,
    'tenq_verification': score_tenq,
    'timeliness': score_timeliness,
    'audit_integrity': score_audit,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', required=True, help='ground truth JSON')
    parser.add_argument('--submission', required=True, help='submission directory')
    parser.add_argument('--result', required=True, help='result JSON output path')
    parser.add_argument('--check', required=True, choices=sorted(SCORERS))
    args = parser.parse_args()
    truth = json.loads(Path(args.scenario).read_text(encoding='utf-8'))
    evidence = load_evidence(args.submission)
    invalid = evidence.get('_invalid')
    if invalid:
        score, detail = 0.0, {'error': invalid}
    else:
        score, detail = SCORERS[args.check](evidence, truth)
    score = max(0.0, min(1.0, float(score)))
    outcome = 'pass' if score >= 0.999999 else 'fail'
    reason = '%s score %.4f (weight %s)' % (
        args.check, score, truth.get('weights', {}).get(args.check))
    result = {'schema_version': 1, 'check_id': args.check, 'outcome': outcome,
              'score': round(score, 6), 'reason': reason, 'detail': detail}
    target = Path(args.result)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()

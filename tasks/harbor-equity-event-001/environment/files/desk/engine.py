"""Deterministic replay engine for the equity event-stream case.

The engine owns the business clock, the disclosure/deadline schedule, the
time-gated data service, submission validation and the audit journal.
"""
import json
import time
from pathlib import Path

from data_service import DataService, DataRejected

PHASES = ('forecast', 'reconciliation', 'verification')
COSTS = {'query': 15, 'catalog': 5, 'read': 10, 'submit': 10}


class Rejected(Exception):
    pass


def clock_label(business_s):
    total = 15 * 3600 + int(business_s)
    hour, rest = divmod(total % (24 * 3600), 3600)
    minute, second = divmod(rest, 60)
    return '%02d:%02d:%02d' % (hour, minute, second)


class Desk:
    def __init__(self, db_path, fixture, public_files=None):
        self.db_path = str(db_path)
        self.fixture = fixture
        self.public_files = public_files or {}
        self.now = 0
        self.shift_end = int(fixture.get('shift_end_s', 23400))
        self.budget = int(fixture.get('max_actions', 160))
        self.deadlines = {k: int(v) for k, v in fixture.get('deadlines', {}).items()}
        self.releases = sorted(fixture.get('releases', []), key=lambda r: int(r['at_s']))
        self.events = []
        self.submissions = {phase: [] for phase in PHASES}
        self.journal = []
        self.data = DataService(self.db_path, lambda: self.now)
        self.actions = 0
        self._released = 0
        self._deadline_sent = set()

    # -- clock and scheduled events ---------------------------------------
    def emit(self, kind, payload):
        self.events.append({'at_s': self.now, 'kind': kind, 'payload': payload})

    def _next_time(self):
        candidates = [self.shift_end]
        for release in self.releases[self._released:]:
            candidates.append(int(release['at_s']))
        for phase, at_s in self.deadlines.items():
            if phase not in self.submission_status() and at_s > self.now:
                candidates.append(at_s)
        return min(candidates)

    def advance(self, target):
        target = max(self.now, min(int(target), self.shift_end))
        while True:
            release = self.releases[self._released] if self._released < len(self.releases) else None
            next_release = int(release['at_s']) if release is not None else None
            next_deadline = None
            for phase, at_s in self.deadlines.items():
                if phase not in self._deadline_sent and self.now < at_s <= target:
                    if next_deadline is None or at_s < next_deadline[0]:
                        next_deadline = (at_s, phase)
            nxt = None
            if next_release is not None and next_release <= target:
                nxt = next_release
            if next_deadline is not None and (nxt is None or next_deadline[0] < nxt):
                nxt = next_deadline[0]
            if nxt is None:
                break
            self.now = max(self.now, nxt)
            if next_release is not None and next_release == nxt:
                self._released += 1
                self.emit(release.get('kind', 'disclosure'), dict(release.get('payload', {}),
                           at_s=nxt, clock=clock_label(nxt)))
            else:
                at_s, phase = next_deadline
                self._deadline_sent.add(phase)
                if phase not in self.submission_status():
                    self.emit('deadline_passed', {'phase': phase, 'deadline_s': at_s,
                                                  'clock': clock_label(at_s)})
        self.now = target
        return self.now

    def submission_status(self):
        return {phase: bool(items) for phase, items in self.submissions.items()}

    # -- action dispatch ---------------------------------------------------
    def act(self, action):
        kind = action.get('action')
        start = self.now
        if kind == 'wait':
            target = self._next_time()
            if action.get('until_s') is not None:
                try:
                    target = min(target, max(self.now, int(action['until_s'])))
                except (TypeError, ValueError):
                    raise Rejected('until_s must be an integer business second')
            self.advance(target)
            return {'now_s': self.now, 'clock': clock_label(self.now)}
        if kind not in COSTS:
            raise Rejected('Unknown action; allowed: query, catalog, read, submit, wait')
        self.advance(min(self.shift_end, self.now + COSTS[kind]))
        if kind == 'query':
            return self.data.query(action.get('sql'))
        if kind == 'catalog':
            return self.data.catalog()
        if kind == 'read':
            path = action.get('path')
            if path is not None:
                if path not in self.public_files:
                    raise Rejected('Unknown workspace file: %s' % path)
                return {'path': path, 'content': self.public_files[path],
                        'business_time_s': self.now}
            return self.data.read(action.get('doc_id'))
        return self._submit(action)

    # -- submission --------------------------------------------------------
    def _submit(self, action):
        phase = action.get('phase')
        payload = action.get('payload')
        if phase not in self.deadlines:
            raise Rejected('phase must be one of %s' % (', '.join(PHASES),))
        if not isinstance(payload, dict):
            raise Rejected('payload must be a JSON object')
        validate_submission(phase, payload)
        summary = action.get('summary')
        if summary is not None and not isinstance(summary, str):
            raise Rejected('summary must be a string when present')
        if phase in ('reconciliation', 'verification'):
            if not isinstance(summary, str) or not summary.strip():
                raise Rejected('a non-empty summary narrative is required for %s' % phase)
        deadline = self.deadlines[phase]
        record = {'at_s': self.now, 'clock': clock_label(self.now), 'deadline_s': deadline,
                  'late': self.now > deadline, 'payload': payload,
                  'summary': action.get('summary') or ''}
        self.submissions[phase].append(record)
        return {'accepted': True, 'phase': phase, 'at_s': self.now,
                'clock': clock_label(self.now), 'deadline_s': deadline,
                'late': record['late'], 'submission_count': len(self.submissions[phase])}

    # -- journal / evidence ------------------------------------------------
    def record(self, action, outcome, started, wall_ms):
        kind = action.get('action')
        entry = {'at_s': self.now, 'started_s': started, 'clock': clock_label(self.now),
                 'action': kind, 'ok': outcome['ok'], 'wall_ms': wall_ms}
        if kind == 'query':
            entry['sql'] = action.get('sql')
            if outcome['ok']:
                value = outcome['value']
                entry['row_count'] = value.get('row_count')
                entry['truncated'] = value.get('truncated')
        elif kind == 'read':
            entry['doc_id'] = action.get('doc_id')
        elif kind == 'submit':
            entry['phase'] = action.get('phase')
            entry['late'] = outcome['value'].get('late') if outcome['ok'] else None
        elif kind == 'wait':
            entry['visited_s'] = self.now
        if not outcome['ok']:
            entry['reason'] = outcome.get('reason')
        self.journal.append(entry)

    def export(self):
        return {
            'schema_version': 1,
            'case_id': self.fixture.get('case_id', 'equity-event-001'),
            'clock_mode': 'replay',
            'completed': True,
            'shift_end_s': self.shift_end,
            'business_time_s': self.now,
            'actions_used': self.actions,
            'journal': self.journal,
            'submissions': {phase: items for phase, items in self.submissions.items()},
            'events': self.events,
            'closing_state': {'now_s': self.now, 'clock': clock_label(self.now),
                              'actions_used': self.actions},
        }


# -- payload validation ------------------------------------------------------
def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require(obj, keys, where):
    missing = [k for k in keys if k not in obj]
    if missing:
        raise Rejected('%s missing required fields: %s' % (where, ', '.join(missing)))


def _numeric_fields(obj, keys, where):
    for key in keys:
        if not _number(obj.get(key)):
            raise Rejected('%s.%s must be a number' % (where, key))


def validate_submission(phase, payload):
    if phase == 'forecast':
        forecast = payload.get('forecast')
        if not isinstance(forecast, dict):
            raise Rejected('forecast.forecast object required')
        _require(forecast, ['total_revenue_usd_m', 'tac_usd_m', 'net_revenue_usd_m',
                            'google_services_revenue_usd_m', 'google_cloud_revenue_usd_m',
                            'google_services_operating_income_usd_m',
                            'google_cloud_operating_income_usd_m',
                            'operating_income_usd_m', 'diluted_eps_ex_oneoffs_usd'],
                 'forecast.forecast')
        _numeric_fields(forecast, ['total_revenue_usd_m', 'tac_usd_m', 'net_revenue_usd_m',
                                   'google_services_revenue_usd_m',
                                   'google_cloud_revenue_usd_m',
                                   'google_services_operating_income_usd_m',
                                   'google_cloud_operating_income_usd_m',
                                   'operating_income_usd_m',
                                   'diluted_eps_ex_oneoffs_usd'], 'forecast.forecast')
        probs = payload.get('probabilities')
        if not isinstance(probs, dict):
            raise Rejected('forecast.probabilities object required')
        _require(probs, ['net_revenue_beat', 'eps_beat'], 'forecast.probabilities')
        for key in ('net_revenue_beat', 'eps_beat'):
            value = probs.get(key)
            if not _number(value) or not (0.0 <= float(value) <= 1.0):
                raise Rejected('forecast.probabilities.%s must be in [0,1]' % key)
        basis = payload.get('basis')
        if not isinstance(basis, list) or not basis:
            raise Rejected('forecast.basis must be a non-empty list')
        if len(basis) > 10:
            raise Rejected('forecast.basis may contain at most 10 items')
        for item in basis:
            if not isinstance(item, dict):
                raise Rejected('forecast.basis items must be objects')
            if not isinstance(item.get('source_doc_id'), str) or not item['source_doc_id'].strip():
                raise Rejected('forecast.basis items need a source_doc_id')
            if not isinstance(item.get('note'), str) or not item['note'].strip():
                raise Rejected('forecast.basis items need a note')
    elif phase == 'reconciliation':
        actuals = payload.get('actuals')
        if not isinstance(actuals, dict):
            raise Rejected('reconciliation.actuals object required')
        keys = ['total_revenue_usd_m', 'tac_usd_m', 'net_revenue_usd_m', 'diluted_eps_usd']
        _require(actuals, keys, 'reconciliation.actuals')
        _numeric_fields(actuals, keys, 'reconciliation.actuals')
        consensus = payload.get('consensus')
        if not isinstance(consensus, dict):
            raise Rejected('reconciliation.consensus object required')
        _require(consensus, ['net_revenue_usd_m', 'diluted_eps_usd'], 'reconciliation.consensus')
        _numeric_fields(consensus, ['net_revenue_usd_m', 'diluted_eps_usd'], 'reconciliation.consensus')
        surprise = payload.get('surprise')
        if not isinstance(surprise, dict):
            raise Rejected('reconciliation.surprise object required')
        _require(surprise, ['net_revenue_pct_vs_consensus', 'eps_pct_vs_consensus'], 'reconciliation.surprise')
        _numeric_fields(surprise, ['net_revenue_pct_vs_consensus', 'eps_pct_vs_consensus'], 'reconciliation.surprise')
        beat = payload.get('beat_miss')
        if not isinstance(beat, dict):
            raise Rejected('reconciliation.beat_miss object required')
        for key in ('net_revenue', 'eps'):
            if beat.get(key) not in ('beat', 'miss', 'in-line'):
                raise Rejected('reconciliation.beat_miss.%s must be beat|miss|in-line' % key)
        docs = payload.get('source_doc_ids')
        if not isinstance(docs, list) or not docs:
            raise Rejected('reconciliation.source_doc_ids must be a nonempty list')
    elif phase == 'verification':
        gaap = payload.get('gaap')
        if not isinstance(gaap, dict):
            raise Rejected('verification.gaap object required')
        keys = ['total_revenue_usd_m', 'tac_usd_m', 'net_revenue_usd_m',
                'operating_income_usd_m', 'operating_margin_pct',
                'net_income_usd_m', 'diluted_eps_usd']
        _require(gaap, keys, 'verification.gaap')
        _numeric_fields(gaap, keys, 'verification.gaap')
        consistency = payload.get('consistency')
        if not isinstance(consistency, dict) or not isinstance(consistency.get('press_release_matches_10q'), bool):
            raise Rejected('verification.consistency.press_release_matches_10q must be boolean')
        one_off = payload.get('one_off')
        if not isinstance(one_off, dict):
            raise Rejected('verification.one_off object required')
        _require(one_off, ['equity_gain_usd_m', 'core_eps_usd'], 'verification.one_off')
        _numeric_fields(one_off, ['equity_gain_usd_m', 'core_eps_usd'], 'verification.one_off')
        margins = payload.get('segment_margins_pct')
        if not isinstance(margins, dict):
            raise Rejected('verification.segment_margins_pct object required')
        _require(margins, ['google_services', 'google_cloud'], 'verification.segment_margins_pct')
        _numeric_fields(margins, ['google_services', 'google_cloud'], 'verification.segment_margins_pct')
        docs = payload.get('source_doc_ids')
        if not isinstance(docs, list) or not docs:
            raise Rejected('verification.source_doc_ids must be a nonempty list')

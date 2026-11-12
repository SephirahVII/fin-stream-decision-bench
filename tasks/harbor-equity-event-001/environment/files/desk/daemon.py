#!/usr/bin/env python3
"""Desk daemon: root-owned broker for the equity event-stream task.

The daemon owns the full market database (root-only), the replay business
clock, the action budget and the submission record.  The agent can only reach
it through the `desk` CLI over a local Unix socket; every request is translated
into one deterministic action of the replay engine and journaled.

Authoritative evidence lives in /opt/desk/state (root-only).  A mirror is
written to /app/evidence and /app/.desk so the trial artifacts show what the
agent submitted, but the verifier always reads the root-only copy.
"""
import json
import os
import socket
import sys
import time
from pathlib import Path

BASE = Path('/opt/desk')
STATE = BASE / 'state'
SOCK_PATH = '/run/desk/desk.sock'
MIRROR_EVIDENCE = Path('/app/evidence/equity_event.json')
MIRROR_JOURNAL = Path('/app/.desk/journal.jsonl')
MIRROR_SUBMISSIONS = Path('/app/.desk/submissions.json')

sys.path.insert(0, str(BASE))
from engine import Desk, Rejected, clock_label  # noqa: E402
from data_service import DataRejected  # noqa: E402


def _load():
    fixture = json.loads((BASE / 'scenario.json').read_text(encoding='utf-8'))
    manual = (BASE / 'manual.md').read_text(encoding='utf-8')
    desk = Desk(str(BASE / 'market.db'), fixture,
                public_files={'desk/manual.md': manual})
    return desk, manual


DESK, MANUAL = _load()
events_cursor = 0


def _dump(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding='utf-8')
    os.replace(tmp, path)


def persist():
    evidence = DESK.export()
    STATE.mkdir(parents=True, exist_ok=True)
    _dump(STATE / 'evidence.json', evidence)
    (STATE / 'journal.jsonl').write_text(
        ''.join(json.dumps(row, sort_keys=True) + '\n' for row in DESK.journal),
        encoding='utf-8')
    try:
        _dump(MIRROR_EVIDENCE, evidence)
        (MIRROR_JOURNAL.parent).mkdir(parents=True, exist_ok=True)
        MIRROR_JOURNAL.write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in DESK.journal),
            encoding='utf-8')
        _dump(MIRROR_SUBMISSIONS, {phase: items for phase, items in
                                   DESK.submissions.items()})
    except OSError:
        pass


def status(include_events=True):
    global events_cursor
    events = []
    if include_events:
        while events_cursor < len(DESK.events):
            events.append(DESK.events[events_cursor])
            events_cursor += 1
    deadlines = {}
    for phase, at_s in DESK.deadlines.items():
        items = DESK.submissions.get(phase) or []
        deadlines[phase] = {
            'deadline_s': at_s,
            'clock': clock_label(at_s),
            'submitted': bool(items),
            'first_at_s': items[0]['at_s'] if items else None,
            'count': len(items),
        }
    return {
        'now_s': DESK.now,
        'clock': clock_label(DESK.now),
        'shift_end_s': DESK.shift_end,
        'shift_ended': DESK.now >= DESK.shift_end,
        'actions_used': DESK.actions,
        'budget': DESK.budget,
        'deadlines': deadlines,
        'events': events,
    }


def build_action(kind, req):
    if kind == 'wait':
        return {'action': 'wait', 'until_s': req.get('until_s')}
    if kind == 'query':
        return {'action': 'query', 'sql': req.get('sql')}
    if kind == 'catalog':
        return {'action': 'catalog'}
    if kind == 'read':
        payload = {'action': 'read'}
        if req.get('path') is not None:
            payload['path'] = req.get('path')
        elif req.get('doc_id') is not None:
            payload['doc_id'] = req.get('doc_id')
        else:
            raise Rejected('read requires a doc_id or a workspace path')
        return payload
    if kind == 'submit':
        return {'action': 'submit', 'phase': req.get('phase'),
                'payload': req.get('payload'), 'summary': req.get('summary')}
    raise Rejected('Unknown action; allowed: status, manual, catalog, query, '
                   'read, submit, wait')


def handle(req):
    kind = req.get('action')
    if not isinstance(kind, str):
        return {'ok': False, 'error': 'request must contain an action string'}
    if kind == 'status':
        return {'ok': True, 'value': status()}
    if kind == 'manual':
        return {'ok': True, 'value': {'content': MANUAL}}
    if DESK.now >= DESK.shift_end:
        return {'ok': False, 'error': 'The shift has ended at %s; no further '
                'actions are possible.' % clock_label(DESK.shift_end),
                'value': status()}
    if DESK.actions >= DESK.budget:
        return {'ok': False,
                'error': 'Action budget exhausted (%d actions)' % DESK.budget,
                'value': status()}
    started = DESK.now
    wall_start = time.monotonic()
    value = None
    error = None
    ok = False
    activity = {'action': kind}
    try:
        activity = build_action(kind, req)
        value = DESK.act(activity)
        ok = True
    except (Rejected, DataRejected) as exc:
        error = str(exc)
    except Exception as exc:  # defensive: never kill the daemon
        error = 'internal error: %s' % exc
    finally:
        DESK.actions += 1
    wall_ms = int((time.monotonic() - wall_start) * 1000)
    DESK.record(activity, {'ok': ok, 'value': value, 'reason': error},
                started, wall_ms)
    persist()
    return {'ok': ok, 'value': value, 'error': error,
            'status': status()}


def serve():
    os.makedirs(os.path.dirname(SOCK_PATH), exist_ok=True)
    try:
        os.unlink(SOCK_PATH)
    except FileNotFoundError:
        pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCK_PATH)
    os.chmod(SOCK_PATH, 0o666)
    server.listen(64)
    persist()
    while True:
        conn, _ = server.accept()
        with conn:
            reader = conn.makefile('rb')
            line = reader.readline()
            try:
                req = json.loads(line.decode('utf-8') or '{}')
            except ValueError:
                req = {}
            if not isinstance(req, dict):
                req = {}
            try:
                response = handle(req)
            except Exception as exc:  # defensive
                response = {'ok': False, 'error': 'daemon failure: %s' % exc}
            try:
                conn.sendall((json.dumps(response, ensure_ascii=False) + '\n')
                             .encode('utf-8'))
            except OSError:
                pass


if __name__ == '__main__':
    serve()

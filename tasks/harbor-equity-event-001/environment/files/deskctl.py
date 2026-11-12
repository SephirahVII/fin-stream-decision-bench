#!/usr/bin/env python3
"""`desk` CLI: the agent-facing interface to the replay engine."""
import argparse
import json
import socket
import sys

SOCK_PATH = '/run/desk/desk.sock'


def call(request):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(SOCK_PATH)
    try:
        client.sendall((json.dumps(request) + '\n').encode('utf-8'))
        chunks = b''
        while not chunks.endswith(b'\n'):
            chunk = client.recv(65536)
            if not chunk:
                break
            chunks += chunk
    finally:
        client.close()
    try:
        return json.loads(chunks.decode('utf-8'))
    except ValueError:
        return {'ok': False, 'error': 'desk daemon returned an unreadable response'}


def emit(response):
    ok = bool(response.get('ok'))
    print(json.dumps(response, ensure_ascii=False, indent=1))
    if not ok:
        print('desk error: %s' % (response.get('error') or 'unknown error'),
              file=sys.stderr)
    return 0 if ok else 1


def read_submission(path):
    if path == '-':
        text = sys.stdin.read()
    else:
        with open(path, 'r', encoding='utf-8') as handle:
            text = handle.read()
    return json.loads(text)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='desk',
        description='Trading-desk interface for the 2026-04-29 equity event shift.')
    subs = parser.add_subparsers(dest='command', required=True)
    subs.add_parser('status', help='business clock, deadlines, action budget')
    subs.add_parser('manual', help='print the desk manual')
    subs.add_parser('catalog', help='list readable tables and row counts')
    query = subs.add_parser('query', help='run one read-only SELECT query')
    query.add_argument('sql', nargs='+', help='SQL text (quote it in the shell)')
    read = subs.add_parser('read', help='read a published document by doc_id')
    read.add_argument('target', help='doc_id, or desk/manual.md')
    wait = subs.add_parser('wait', help='advance the replay clock')
    wait.add_argument('until_s', type=int, help='business seconds since 15:00 ET')
    submit = subs.add_parser('submit', help='submit one graded phase payload')
    submit.add_argument('phase', choices=('forecast', 'reconciliation', 'verification'))
    submit.add_argument('payload_file',
                        help="JSON file with {'payload': {...}} and optional 'summary', or '-' for stdin")
    args = parser.parse_args(argv)

    if args.command == 'status':
        return emit(call({'action': 'status'}))
    if args.command == 'manual':
        return emit(call({'action': 'manual'}))
    if args.command == 'catalog':
        return emit(call({'action': 'catalog'}))
    if args.command == 'query':
        return emit(call({'action': 'query', 'sql': ' '.join(args.sql)}))
    if args.command == 'read':
        target = args.target
        request = {'action': 'read'}
        if '/' in target:
            request['path'] = target
        else:
            request['doc_id'] = target
        return emit(call(request))
    if args.command == 'wait':
        return emit(call({'action': 'wait', 'until_s': args.until_s}))
    if args.command == 'submit':
        try:
            document = read_submission(args.payload_file)
        except (OSError, ValueError) as exc:
            print('cannot load submission JSON: %s' % exc, file=sys.stderr)
            return 2
        if not isinstance(document, dict):
            print('submission JSON must be an object', file=sys.stderr)
            return 2
        payload = document.get('payload', document)
        request = {'action': 'submit', 'phase': args.phase,
                   'payload': payload, 'summary': document.get('summary')}
        return emit(call(request))
    return 2


if __name__ == '__main__':
    sys.exit(main())

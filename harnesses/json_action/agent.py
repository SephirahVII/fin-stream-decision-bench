"""One structured decision using a Chat Completions endpoint."""
import json
import http.client
import hashlib
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send(event_type, **payload):
    print(json.dumps({'schema_version': 1, 'type': event_type, **payload}, ensure_ascii=False), flush=True)


def post(request, model, timing=None):
    """Retry transient transport failures; record unknown usage for each retry."""
    opener=urllib.request.build_opener(NoRedirect)
    for attempt in range(1,4):
        began=time.monotonic()
        if timing is not None:
            timing['started']=began
        send('event',kind='model_request',payload={'api':'chat','attempt':attempt})
        try:
            with opener.open(request,timeout=600) as stream:
                return stream.read(4_000_001)
        except (urllib.error.URLError,TimeoutError,ConnectionError,http.client.IncompleteRead) as exc:
            status=exc.code if isinstance(exc,urllib.error.HTTPError) else None
            transient=status is None or status in (429,500,502,503,504)
            if not transient or attempt==3:
                raise RuntimeError(f'Chat request failed ({status or type(exc).__name__}) after {attempt} attempt(s)') from None
            send('usage',record={'status':'error','usage':{},'requested_model':model,
                                'latency_ms':int((time.monotonic()-began)*1000)})
            send('event',kind='provider_event',payload={'event':'model_request_retry','attempt':attempt,'http_status':status,'error_type':type(exc).__name__})
            retry_after=15*attempt if status==429 else attempt
            if status==429 and exc.headers:
                try:
                    retry_after=float(exc.headers.get('Retry-After',retry_after))
                except (TypeError,ValueError):
                    pass
            time.sleep(min(60,max(1,retry_after)))


import re

ALLOWED_ACTIONS = ('query', 'catalog', 'read', 'submit', 'wait')


def _decode_parameter(value, key):
    value = value.strip()
    if key in ('payload', 'forecast', 'probabilities', 'actuals', 'consensus', 'surprise'):
        try:
            return json.loads(value)
        except ValueError:
            return value
    if key in ('until_s', 'doc_id', 'phase', 'path', 'sql', 'summary'):
        if key == 'until_s':
            try:
                return int(float(value))
            except ValueError:
                return value
        return value
    return value


def parse_tool_syntax(text):
    """Recover a single action from model-authored tool-call markup.

    Some chat models (e.g. DeepSeek-V4.1-Flash) occasionally emit their native
    function-call envelope instead of the plain JSON action contract, for example
    <|DSML| invoke name="read"><|DSML| parameter name="path">desk/manual.md...
    The workflow controller needs one JSON action per turn, so we translate the
    first recognized invocation into the controller's action schema.  This keeps
    protocol emulation failures from being scored as reasoning failures.
    """
    if 'invoke' not in text:
        return None
    match = re.search(r'invoke\s+name="([^"]+)"', text)
    if not match:
        return None
    name = match.group(1).strip()
    if name not in ALLOWED_ACTIONS:
        return None
    tail = text[match.end():]
    block = re.split(r'invoke\s+name=', tail, maxsplit=1)[0]
    params = {}
    for param in re.finditer(r'parameter\s+name="([^"]+)"[^>]*>(.*?)</', block, re.S):
        key = param.group(1).strip()
        params[key] = _decode_parameter(param.group(2), key)
    action = {'action': name}
    if name == 'query':
        sql = params.get('sql')
        if isinstance(sql, str) and sql.strip():
            action['sql'] = sql.strip()
    elif name == 'read':
        if isinstance(params.get('doc_id'), str) and params['doc_id'].strip():
            action['doc_id'] = params['doc_id'].strip()
        elif isinstance(params.get('path'), str) and params['path'].strip():
            action['path'] = params['path'].strip()
    elif name == 'wait':
        if 'until_s' in params:
            action['until_s'] = params['until_s']
    elif name == 'submit':
        if isinstance(params.get('phase'), str) and params['phase'].strip():
            action['phase'] = params['phase'].strip()
        payload = params.get('payload')
        if isinstance(payload, dict):
            action['payload'] = payload
        if isinstance(params.get('summary'), str):
            action['summary'] = params['summary']
    return action


def extract_json_object(text):
    """Return the first JSON object embedded in a model turn, if any.

    Chat models occasionally append a hallucinated "User:" turn or paste several
    candidate actions into one reply.  The workflow protocol needs exactly one
    action, so we take the first complete JSON object instead of failing the turn.
    """
    stripped = text.strip()
    try:
        candidate = json.loads(stripped)
        if isinstance(candidate, dict):
            return candidate
    except ValueError:
        pass
    decoder = json.JSONDecoder()
    index = stripped.find('{')
    while index != -1:
        try:
            candidate, _ = decoder.raw_decode(stripped[index:])
        except ValueError:
            candidate = None
        if isinstance(candidate, dict):
            return candidate
        index = stripped.find('{', index + 1)
    return None


HISTORY=Path('.harness-state/conversation.json')


def load_messages(request):
    state=request.get('state')
    if state is None:
        return [{'role':'system','content':request['instructions']},
                {'role':'user','content':json.dumps({'prompt':request['prompt'],'input_files':request['input_files']})}]
    if not isinstance(state,dict) or state.get('schema_version')!=1:
        raise ValueError('Invalid Agent conversation handle')
    body=HISTORY.read_bytes()
    if hashlib.sha256(body).hexdigest()!=state.get('history_sha256'):
        raise ValueError('Agent conversation history digest mismatch')
    messages=json.loads(body)
    if not isinstance(messages,list):
        raise ValueError('Invalid Agent conversation history')
    return messages


def save_messages(messages):
    body=json.dumps(messages,ensure_ascii=False).encode('utf-8')
    HISTORY.parent.mkdir(exist_ok=True)
    HISTORY.write_bytes(body)
    return {'schema_version':1,'history_sha256':hashlib.sha256(body).hexdigest(),'message_count':len(messages)}


def main():
    request = json.load(sys.stdin)
    model = os.environ['MODEL_ID']
    endpoint = os.environ['MODEL_BASE_URL']
    parsed = urlsplit(endpoint)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Invalid model base URL')
    messages = load_messages(request)
    messages.extend({'role': 'user', 'content': text} for text in request['messages'])
    parameters = json.loads(os.getenv('MODEL_PARAMETERS', '{}'))
    parameters.setdefault('response_format', {'type': 'json_object'})
    body = {'model': model, 'messages': messages, **parameters}
    timing = {'started':time.monotonic()}
    response = None
    try:
        http = urllib.request.Request(endpoint.rstrip('/') + '/chat/completions', json.dumps(body).encode(),
            {'Authorization': 'Bearer ' + os.environ['MODEL_API_KEY'], 'Content-Type': 'application/json'}, method='POST')
        data = post(http,model,timing)
        if len(data) > 4_000_000:
            raise ValueError('Model response exceeds size limit')
        response = json.loads(data)
        path = Path('.harness-output/chat.json')
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({'request': body, 'response': response}, ensure_ascii=False), encoding='utf-8')
        send('exchange', path=path.as_posix())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Chat request failed with HTTP {exc.code}') from None
    finally:
        send('usage', record={'status': 'succeeded' if response else 'error',
            'usage': (response.get('usage') or {}) if response else {}, 'requested_model': model,
            'provider_reported_model': response.get('model') if response else None,
            'latency_ms': int((time.monotonic() - timing['started']) * 1000)})
    message = response['choices'][0]['message']
    content = message.get('content') or ''
    action = extract_json_object(content)
    if action is None:
        action = parse_tool_syntax(content) or {'action': 'invalid'}
    # Keep the conversation deterministic: the assistant turn is the action we acted on,
    # not raw model text that may contain hallucinated turns.
    messages.append({'role': 'assistant', 'content': json.dumps(action, ensure_ascii=False)})
    if len(json.dumps(action).encode()) > 12_000:
        action = {'action': 'invalid'}
    send('result', result={'schema_version': 1, 'output': action, 'state': save_messages(messages)})


if __name__ == '__main__':
    main()

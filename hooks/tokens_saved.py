# Tokens saved counter for KL Kit Sessions (shown by the optional status bar in plugin/).
# Used by heavy_session.py (when it blocks a message) and remember_window.py (when you /clear
# a heavy conversation). Each conversation counts once, with its context size: the tokens
# that were not reloaded or dragged along any further. It is an estimate.
import json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
SAVED_FILE = os.path.join(HERE, 'tokens_saved.json')
MINIMUM = 100_000  # same as HEAVY_TOKENS in heavy_session.py


def add(transcript, tokens, reason):
    if not transcript or not tokens or tokens < MINIMUM:
        return
    try:
        with open(SAVED_FILE, encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {'total': 0, 'conversations': {}}
    convs = data.setdefault('conversations', {})
    key = os.path.basename(transcript)
    if key in convs:
        return
    convs[key] = {'tokens': int(tokens), 'reason': reason, 't': int(time.time())}
    data['total'] = sum(v.get('tokens', 0) for v in convs.values())
    data['updated'] = int(time.time())
    tmp = SAVED_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    os.replace(tmp, SAVED_FILE)


def context_size(transcript):
    """Context size of the last reply (same count as heavy_session.py)."""
    size = os.path.getsize(transcript)
    with open(transcript, 'rb') as f:
        f.seek(max(0, size - 3_000_000))
        lines = f.read().decode('utf-8', 'ignore').splitlines()
    for line in reversed(lines):
        try:
            m = json.loads(line).get('message')
        except Exception:
            continue
        if isinstance(m, dict) and m.get('usage'):
            u = m['usage']
            ctx = sum((u.get(k) or 0) for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
            if ctx:
                return ctx
    return 0

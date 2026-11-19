# Message to window (Claude Code PreToolUse hook, matcher "SendMessage").
# Problem: windows opened in the same folder get names derived from it (app-77, app-62, app-2f),
# and a session that wants to hand a request to "the window doing X" may not know which is which,
# so it sends the same request to several.
# - The first time a session writes to a window whose name was derived from its folder, this stops it
#   and shows what every live window is doing (project or track, and its last request).
#   If the session sends it again, it goes through.
# - If the same request was already sent to another window, it is stopped: one request, one window.
# If anything goes wrong, it lets the message through (it never gets in the way).
import importlib.util, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')  # v1.4
SESSIONS = os.path.join(CONFIG, 'sessions')
PROJECTS = os.path.join(CONFIG, 'projects')
LOG = os.path.join(HERE, 'messages.json')


def continue_hook():
    spec = importlib.util.spec_from_file_location('continue_after_clear', os.path.join(HERE, 'continue_after_clear.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def alive(pid):
    try:
        pid = int(pid)
        if os.name == 'nt':
            import ctypes
            k = ctypes.windll.kernel32
            h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            ok = k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            return bool(ok) and code.value == 259  # STILL_ACTIVE
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except Exception:
        return True


def live_windows():
    out = []
    for n in os.listdir(SESSIONS):
        if not n.endswith('.json'):
            continue
        try:
            with open(os.path.join(SESSIONS, n), encoding='utf-8') as f:
                d = json.load(f)
        except Exception:
            continue
        if d.get('name') and d.get('pid') and alive(d['pid']):
            out.append(d)
    return out


def transcript_of(session_id):
    for d in os.listdir(PROJECTS):
        p = os.path.join(PROJECTS, d, session_id + '.jsonl')
        if os.path.isfile(p):
            return p
    return None


def what_it_does(c, w):
    """Project or track of that window and its last request, in one line."""
    cwd = w.get('cwd') or ''
    t = transcript_of(w.get('sessionId') or '')
    own = c.find_state(cwd) if cwd else None
    where = 'project ' + os.path.basename(os.path.dirname(own)) if own else (os.path.basename(cwd.rstrip('\\/')) or cwd)
    request = ''
    if t:
        state = own or os.path.join(cwd, c.STATE_FILE)
        text, tracks = '', []
        try:
            with open(state, encoding='utf-8') as f:
                text = f.read()
            tracks, _ = c.tracks_by_date(text)
        except Exception:
            pass
        try:
            work = c.window_work(t, state, text, tracks)
            if work:
                where = ('project ' + os.path.basename(os.path.dirname(work[1]))) if work[0] == 'project' else (work[1] + ' track')
        except Exception:
            pass
        try:
            request = c.window_task(t)[0]
        except Exception:
            pass
    return w['name'] + ' -> ' + where + ((' · last request: "' + request[:90] + '"') if request else '')


def stop(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def main():
    data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
    inp = data.get('tool_input') or {}
    to = re.sub(r'\s*\[[0-9a-f]+\]\s*$', '', (inp.get('to') or '').strip())
    text = inp.get('message') or ''
    if not to or not text:
        return
    live = live_windows()
    target = [w for w in live if w.get('name') == to]
    if not target:
        return  # subagent, remote or cloud window: not this hook's business
    me = data.get('session_id') or ''
    key = me + '|' + ' '.join(str(text).lower().split())[:120]
    now = time.time()
    try:
        with open(LOG, encoding='utf-8') as f:
            log = json.load(f)
    except Exception:
        log = {}
    log = {k: v for k, v in log.items() if now - v.get('t', 0) < 1800}
    e = log.get(key, {'t': now})
    reason = None
    if e.get('sent_to') and e['sent_to'] != to:
        reason = ("You already sent this same request to \"" + e['sent_to'] + "\". A request goes to ONE window: do not spread it. "
                  "If that was the wrong one, tell the user instead of sending it to another.")
    elif not e.get('sent_to') and not e.get('seen') and target[0].get('nameSource') == 'derived':
        c = continue_hook()
        lines = [what_it_does(c, w) for w in live if w.get('sessionId') != me]
        reason = ("\"" + to + "\" is a name derived from its folder; there may be several similar windows. This is what each live window is doing now:\n- "
                  + "\n- ".join(lines) + "\n"
                  "Send it only to the one working on that project or track (call SendMessage again with that exact name and it will go through). "
                  "If none of them is working on it, do not send it to several: tell the user.")
        e['seen'] = now
    if not reason:
        e['sent_to'] = to
    e['t'] = now
    log[key] = e
    try:
        with open(LOG, 'w', encoding='utf-8') as f:
            json.dump(log, f)
    except Exception:
        pass
    if reason:
        stop(reason)


try:
    main()
except Exception:
    pass

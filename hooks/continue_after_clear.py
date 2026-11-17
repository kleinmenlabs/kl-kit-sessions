# Continue after /clear (Claude Code SessionStart hook, matcher "clear").
# When you type /clear to start fresh in the same terminal, this tells the new session
# what to do, so a single word ("continue", or a track name) is enough: no need to paste
# the new-session prompt.
# - If this window's last answer left a ready-to-paste prompt ("> Continue with ..."),
#   "continue" means exactly that prompt.
# - Otherwise "continue" means the task THIS window was doing (your last request and its last
#   answer, noted at /clear by remember_window.py), not the first item in Next, which may
#   belong to another window.
# - It finds the project this window really worked on (files it edited, paths in its shell
#   commands, a pasted "Continue with the project X (path)"), even if the session was opened
#   in another folder.
# - With tracks: the track this window was on; if unknown, the most recently updated one.
#   It says which and never asks.
# - It lists the other windows that moved in the same folder in the last 30 minutes, with
#   their last request, so the new session does not take over their work.
# - Parent folder with no STATE.md (projects inside with their own): tells the session to create it first.
# - No STATE.md anywhere: stays silent.
import json, os, re, sys, time

STATE_FILE = 'STATE.md'
HERE = os.path.dirname(os.path.abspath(__file__))
WINDOWS_FILE = os.path.join(HERE, 'windows.json')
MARK = r'\[window: (track|project) ([^\]]+)\]'
SKIP = ('demo', 'templates', 'scratchpad', 'temp', 'tmp')  # folders whose STATE.md is not the real work
PASTE = r'(?m)^[ \t]*>[ \t]*\**((?:Continue with|Siga con|Sigue con|Continúa con) [^\n]*(?:\n[ \t]*>[^\n]*)*)'  # also Spanish
WIN_PATH = r'([A-Za-z]):[\\/]+([^\s"\'`;|<>*?]+)'
POSIX_PATH = r'(?<![\w.~])(/(?:home|Users|srv|opt|mnt|work|projects|var/www)/[^\s"\'`;|<>*?]+)'


def same(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def find_state(folder):
    d = os.path.abspath(folder)
    while True:
        f = os.path.join(d, STATE_FILE)
        if os.path.exists(f):
            return f
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def state_of_work(path):
    """STATE.md of the project a file belongs to (skips demos, templates, backups and tests)."""
    parts = [x.lower() for x in re.split(r'[\\/]+', os.path.abspath(path))]
    if any(x in SKIP or x.startswith(('backup', 'test')) for x in parts):
        return None
    d = os.path.abspath(path)
    d = d if os.path.isdir(d) else os.path.dirname(d)
    return find_state(d)


def command_paths(cmd):
    """Project paths that show up in a Bash or PowerShell command (not ~/.claude or temp folders)."""
    found = []
    for m in re.finditer(WIN_PATH, cmd):
        found.append((m.start(), m.group(1).upper() + ':\\' + m.group(2).replace('/', '\\').rstrip('\\')))
    if os.name != 'nt':
        for m in re.finditer(POSIX_PATH, cmd):
            found.append((m.start(), m.group(1).rstrip('/')))
    out = []
    for _, p in sorted(found):
        low = p.lower().replace('\\', '/')
        if '/.claude' in low or '/appdata/' in low or '/temp/' in low or '/tmp/' in low:
            continue
        out.append(p)
    return out


def work_of_path(path, state, folder, by_name):
    """('track', X) if the path is inside a track's folder here; ('project', STATE.md) if it belongs to another project."""
    try:
        rel = os.path.relpath(os.path.abspath(path), folder)
    except ValueError:
        rel = '..'
    if not rel.startswith('..'):
        t = by_name.get(rel.replace('\\', '/').split('/')[0].lower())
        return ('track', t) if t else None
    s = state_of_work(path)
    if s and not same(s, state):
        return ('project', s)
    return None


def previous_conversation(cwd):
    """The conversation this window had before /clear (noted by remember_window.py)."""
    try:
        with open(WINDOWS_FILE, encoding='utf-8') as f:
            windows = json.load(f)
    except Exception:
        return None
    now = time.time()
    pid = os.environ.get('CLAUDE_PID')
    key = pid if pid in windows and now - windows[pid].get('t', 0) < 120 else None
    if not key:  # no window id: the one noted seconds ago in the same folder
        near = [(v.get('t', 0), k) for k, v in windows.items()
                if v.get('cwd') == cwd and now - v.get('t', 0) < 15]
        key = max(near)[1] if near else None
    if not key:
        return None
    t = windows.pop(key).get('transcript')
    try:
        with open(WINDOWS_FILE, 'w', encoding='utf-8') as f:
            json.dump(windows, f)
    except Exception:
        pass
    return t


def track_in_edit(state_text, new, tracks):
    m = re.search(r'^##\s*Track:\s*(.+)$', new, flags=re.M)
    if m and m.group(1).strip() in tracks:
        return m.group(1).strip()
    piece = new.strip()[:300]
    pos = state_text.find(piece) if piece else -1
    if pos < 0:
        return None
    before = re.findall(r'^##\s*Track:\s*(.+)$', state_text[:pos], flags=re.M)
    return before[-1].strip() if before and before[-1].strip() in tracks else None


def user_text(o):
    """What the user typed on that transcript line (no system notes, images or tool results)."""
    if not isinstance(o, dict) or o.get('type') != 'user' or o.get('isMeta') or o.get('isCompactSummary'):
        return ''
    m = o.get('message')
    if not isinstance(m, dict):
        return ''
    c = m.get('content')
    parts = [c] if isinstance(c, str) else [x.get('text', '') for x in (c or []) if isinstance(x, dict) and x.get('type') == 'text']
    t = ' '.join(p for p in parts if p and not p.startswith('[Image') and not p.lstrip().startswith('<')).strip()
    t = re.sub(r'^The user sent a new message while you were working:\s*', '', t)
    t = t.split('\n\nThis is how Claude Code surfaces')[0]
    if not t or t.startswith(('[Request interrupted', 'This session is being continued', 'Caveat:')):
        return ''
    return ' '.join(t.split())


def window_work(transcript, state, state_text, tracks):
    """Last work this window touched: ('track', X) or ('project', path of its STATE.md).
    From its edits (STATE.md here, a track's folder, or ANOTHER project with its own STATE.md),
    paths in its shell commands, its "Continuing with X" line, a pasted
    "Continue with the project X (path)" or the mark left by an earlier /clear."""
    by_name = {t.lower(): t for t in tracks}
    folder = os.path.dirname(os.path.abspath(state))
    last = None
    with open(transcript, encoding='utf-8', errors='ignore') as f:
        for line in f:
            try:
                o = json.loads(line)
            except Exception:
                continue
            for m in re.finditer(MARK, json.dumps(o, ensure_ascii=False)):
                v = m.group(2).strip()
                if m.group(1) == 'track' and v in tracks:
                    last = ('track', v)
                elif m.group(1) == 'project' and os.path.isfile(os.path.join(v, STATE_FILE)):
                    last = ('project', os.path.join(v, STATE_FILE))
            ut = user_text(o)
            if ut:
                m = re.search(r'Continue with the project [^(\n]*\(([^)]+)\)', ut)
                if m and os.path.isfile(os.path.join(m.group(1).strip(), STATE_FILE)):
                    s = os.path.join(m.group(1).strip(), STATE_FILE)
                    last = ('track', None) if same(s, state) else ('project', s)
                m = re.search(r'Continue with the ([^.,;\n]+?) track', ut)
                if m and m.group(1).strip().lower() in by_name:
                    last = ('track', by_name[m.group(1).strip().lower()])
            msg = o.get('message') if isinstance(o, dict) else None
            if not isinstance(msg, dict) or not isinstance(msg.get('content'), list):
                continue
            for c in msg['content']:
                if not isinstance(c, dict):
                    continue
                if c.get('type') == 'tool_use' and c.get('name') in ('Edit', 'MultiEdit', 'Write'):
                    inp = c.get('input') or {}
                    path = inp.get('file_path') or ''
                    if not path:
                        continue
                    found = None
                    if same(path, state):
                        new = inp.get('new_string') or ''
                        if c.get('name') == 'MultiEdit' and inp.get('edits'):
                            new = inp['edits'][-1].get('new_string') or ''
                        t = track_in_edit(state_text, new, tracks) if new else None
                        found = ('track', t) if t else None
                    else:
                        found = work_of_path(path, state, folder, by_name)
                    if found:
                        last = found
                elif c.get('type') == 'tool_use' and c.get('name') in ('Bash', 'PowerShell'):
                    for p in command_paths((c.get('input') or {}).get('command') or ''):
                        found = work_of_path(p, state, folder, by_name)
                        if found:
                            last = found
                            break
                elif c.get('type') == 'text' and msg.get('role') == 'assistant':
                    m = re.match(r'\s*\**Continuing with (?:the )?([^;,.\n*]+?)(?: track)?[;,.\n*]', c.get('text') or '')
                    if m and m.group(1).strip().lower() in by_name:
                        last = ('track', by_name[m.group(1).strip().lower()])
    if last and last[0] == 'track' and not last[1]:
        return None
    return last


def tail(path, size=2_000_000):
    n = os.path.getsize(path)
    with open(path, 'rb') as f:
        f.seek(max(0, n - size))
        return f.read().decode('utf-8', 'ignore').splitlines()


def window_task(transcript):
    """The user's last request, the last answer and, if the window left one after that request,
    the ready-to-paste prompt ("> Continue with ...")."""
    request, answer, paste = '', '', ''
    for line in tail(transcript):
        try:
            o = json.loads(line)
        except Exception:
            continue
        t = user_text(o)
        if t:
            request, answer, paste = t, '', ''
        m = o.get('message') if isinstance(o, dict) else None
        if isinstance(m, dict) and m.get('role') == 'assistant' and isinstance(m.get('content'), list):
            for c in m['content']:
                if isinstance(c, dict) and c.get('type') == 'text' and c.get('text', '').strip():
                    answer = ' '.join(c['text'].split())
                    hits = re.findall(PASTE, c['text'])
                    if hits:
                        paste = ' '.join(re.sub(r'(?m)^[ \t]*>[ \t]?', '', hits[-1]).replace('**', '').split())
    return request[:300], answer[:400], paste[:1200]


def other_windows(folder, exclude, minutes=30):
    """Conversations that moved in the last minutes with their working folder inside this one."""
    root = os.path.join(os.path.expanduser('~'), '.claude', 'projects')
    base = os.path.normcase(os.path.abspath(folder))
    now = time.time()
    out = []
    try:
        dirs = os.listdir(root)
    except Exception:
        return out
    for d in dirs:
        try:
            names = os.listdir(os.path.join(root, d))
        except Exception:
            continue
        for n in names:
            if not n.endswith('.jsonl'):
                continue
            path = os.path.join(root, d, n)
            if os.path.normcase(os.path.abspath(path)) in exclude:
                continue
            try:
                if now - os.path.getmtime(path) > minutes * 60:
                    continue
                lines = tail(path, 400_000)
            except Exception:
                continue
            cwd, request = None, ''
            for line in lines:
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if isinstance(o, dict) and o.get('cwd'):
                    cwd = o['cwd']
                t = user_text(o)
                if t:
                    request = t
            if not cwd or not request:
                continue
            c = os.path.normcase(os.path.abspath(cwd))
            if c != base and not c.startswith(base + os.sep):
                continue
            rel = os.path.relpath(cwd, folder)
            out.append((rel if rel != '.' else '(main folder)') + ': "' + request[:110] + '"')
    return out[:6]


def children_with_state(folder):
    try:
        names = sorted(os.listdir(folder))
    except Exception:
        return []
    found = []
    for n in names:
        f = os.path.join(folder, n, STATE_FILE)
        if os.path.isfile(f):
            found.append((os.path.getmtime(f), n))
    found.sort(reverse=True)
    return [n + " (its STATE.md changed " + time.strftime('%Y-%m-%d %H:%M', time.localtime(t)) + ")" for t, n in found]


def tracks_by_date(text):
    # Tracks, most recent "Updated" first (undated ones last, in file order).
    parts = re.split(r'^##\s*Track:\s*', text, flags=re.M)[1:]
    items = []
    for i, p in enumerate(parts):
        name = p.splitlines()[0].strip()
        m = re.search(r'Updated:\**\s*(\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2})?)', p)
        date = m.group(1).replace('T', ' ') if m else ''
        if len(date) == 10:
            date += ' 00:00'
        items.append((date, -i, name))
    items.sort(reverse=True)
    return [n for _, _, n in items], bool(items and items[0][0])


def say(context):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}))


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    cwd = data.get('cwd') or os.getcwd()
    state = find_state(cwd)
    text, tracks, dated = '', [], False
    if state:
        try:
            text = open(state, encoding='utf-8').read()
            tracks, dated = tracks_by_date(text)
        except Exception:
            state = None

    # What THIS window was doing (noted by remember_window.py at /clear)
    previous, request, answer, paste, work = None, '', '', '', None
    try:
        previous = previous_conversation(cwd)
        if previous and os.path.exists(previous):
            request, answer, paste = window_task(previous)
            work = window_work(previous, state or os.path.join(cwd, STATE_FILE), text, tracks)
        else:
            previous = None
    except Exception:
        work = None
    if paste:
        m = re.search(r'\(([^)]+)\)', paste)
        if m and os.path.isfile(os.path.join(m.group(1).strip(), STATE_FILE)):
            s = os.path.join(m.group(1).strip(), STATE_FILE)
            work = None if (state and same(s, state)) else ('project', s)
        m = re.search(r'Continue with the ([^.,;\n]+?) track', paste)
        if m and m.group(1).strip() in tracks:
            work = ('track', m.group(1).strip())

    exclude = {os.path.normcase(os.path.abspath(p)) for p in (previous, data.get('transcript_path')) if p}
    base = os.path.dirname(work[1]) if work and work[0] == 'project' else (os.path.dirname(state) if state else cwd)
    try:
        others = other_windows(base, exclude)
    except Exception:
        others = []
    others_note = (("Other windows are working there right now (do not do or touch their work; if what comes next is theirs, tell the user): "
                    + "; ".join(others) + ". ") if others else "")
    mark = ''
    if work:
        mark = ("[window: project " + os.path.dirname(work[1]) + "] ") if work[0] == 'project' else ("[window: track " + work[1] + "] ")
    lang = "Answer in the user's language. "

    # 1) The window left a ready-to-paste prompt: "continue" = that prompt, as is.
    if paste:
        say("The user just typed /clear to keep going without pasting the new-session prompt. This window's last answer left them this prompt to paste, "
            "and \"continue\" (or similar) means exactly that; it wins over any track or STATE.md of this folder: \"" + paste + "\". "
            "Do it as written (read only the files it names) and say so in the first line. " + lang + mark + others_note)
        return

    task = ''
    if request or answer:
        task = ("What THIS window was doing before /clear: the user's last request \"" + request + "\""
                + (("; its last answer was \"" + answer + "\"") if answer else "") + ". "
                "On \"continue\", carry on with THAT task (whatever was left), not with the first item in Next. "
                "If that task is already done, tell the user in one line and propose the next thing no other window is doing, without starting it until they say yes. ")

    # 2) The window was working on ANOTHER project (with its own STATE.md), even though it was opened here.
    if work and work[0] == 'project':
        s = work[1]
        d = os.path.dirname(s)
        name = os.path.basename(d)
        say("The user just typed /clear to keep working without pasting the new-session prompt. "
            "This window was opened in " + cwd + ", but it was working on the project " + name + " (" + d + ") " + mark
            + ", not on a track of this folder. Before answering, read only the rules file and " + s + " (not HISTORY.md). "
            "If the user just says \"continue\", carry on in that project and say so in the first line (\"Continuing with " + name + "; tell me if it's another one\"). "
            "Do not take any track or pending item of " + cwd + " (in a parent folder, only update " + name + "'s line there). "
            "If the user names another project or track, go with that. " + lang + task + others_note)
        return

    # 3) Parent folder with no STATE.md of its own
    if not state:
        kids = children_with_state(cwd)
        if not kids:
            return
        say("The user just typed /clear. This is a parent folder with no STATE.md of its own; inside are projects with theirs: "
            + ", ".join(kids) + " (most recent first). Before answering, and without asking, create the parent's STATE.md "
            "(with /session-kit): one track per project, in that order, with Updated (that date and time), Now and Next "
            "(two or three lines, taken only from the top of each inner STATE.md). Then answer by the tracks rule: "
            "\"how are we doing?\" = one line per track, most recent first, ending with \"Shall I continue with <the first>?\"; "
            "\"continue\" = carry on with the first one and say so in the first line. Never ask \"which one should I continue?\". "
            + lang + task + others_note)
        return

    # 4) Tracks here, or a plain project
    task += others_note
    if tracks:
        mine = work[1] if work else None
        first = mine or tracks[0]
        how = ("This STATE.md has tracks" + (" (most recently updated first)" if dated else "") + ": " + ", ".join(tracks) + ". "
               "If the user names one (one word is enough), carry on with the first item in that track's Next and edit only that section and its Updated. "
               "If they ask \"how are we doing?\", answer one line per track in that order (at most 3, then \"and N more, idle\") without opening other files. "
               + (("This window was working on the " + first + " track before /clear " + mark + ". ") if mine else "")
               + "If they just say \"continue\", carry on with the " + first + " track and say so in the first line (\"Continuing with " + first + "; tell me if it's another one\"). Do not ask. "
               + task)
    else:
        how = ("If the user says \"continue\" or similar, "
               + ("carry on with what this window was doing. " + task if (request or answer) else "do the first item in \"Next\". " + others_note))
    say("The user just typed /clear to keep working on the same project without pasting the new-session prompt. "
        f"Before answering, read only the rules file and {state} (not HISTORY.md). " + lang + how)


if __name__ == '__main__':
    main()

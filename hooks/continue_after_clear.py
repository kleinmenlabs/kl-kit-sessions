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
#   It says which and never asks. v1.4: but if it does not know what this window was doing and
#   other windows are working in the same folder, it asks "What was this window working on?".
# - v1.4: if the last answer gave you numbered or lettered options, they are shown again word for
#   word (same numbers, same order), and a message the heavy-session guard blocked counts as your answer.
# - v1.4: if the conversation was compacted (auto summary), the task comes from the summary.
# - It lists the other windows that moved in the same folder in the last 30 minutes, with
#   their last request, so the new session does not take over their work.
# - Parent folder with no STATE.md (projects inside with their own): tells the session to create it first.
# - No STATE.md anywhere: stays silent.
import json, os, re, sys, time

STATE_FILE = 'STATE.md'
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')  # v1.4
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
        # v1.4: if two windows of the same folder cleared at once, we cannot tell which is which
        key = near[0][1] if len(near) == 1 else None
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


def task_from_summary(o):
    """v1.4: if the conversation was compacted, the user's last request lives inside the summary.
    Takes its "Current Work" and "Optional Next Step"."""
    if not isinstance(o, dict) or o.get('type') != 'user' or not o.get('isCompactSummary'):
        return ''
    c = (o.get('message') or {}).get('content')
    c = c if isinstance(c, str) else ' '.join(x.get('text', '') for x in (c or []) if isinstance(x, dict))
    parts = []
    for title, size in (('Current Work', 500), ('Optional Next Step', 900)):
        m = re.search(r'(?:^|\n)[#\s\d.*]*' + title + r'[*:]*\s*(.*?)(?=\n[#\s]*\d+\.\s+\**[A-Z][^\n]{0,40}:|\nIf you need specific details|\Z)', c, re.S)
        if m and m.group(1).strip():
            parts.append(title + ': ' + ' '.join(m.group(1).split())[:size])
    return ('(from the automatic summary of the conversation) ' + ' | '.join(parts)) if parts else ''


# v1.4: after the guard and /clear, the new session offered DIFFERENT options and the user answered
# "2" meaning the old ones. Now the options are carried over as they were (same numbers, order and text).
OPTION = re.compile(r'^[ \t]*(?:[-*•][ \t]+)?(?:\*\*|__)?[ \t]*(?:'
                    r'\(?([1-9]|[A-Ea-e])[.)](?:\*\*|__)?[ \t]+'          # 1. / 2) / A. / (b)
                    r'|(?:\*\*|__)?([A-E1-9])(?:\*\*|__)[ \t]*[—–:\-]'   # **A** — text
                    r'|(?:Option|Opci[oó]n)[ \t]+([1-9A-Ea-e])\b'           # Option 2
                    r')', re.I)
HINT = re.compile(r'(?i)option|opci[oó]n|choose|pick|prefer|recommend|which (?:one|do you)|escoj|elij|prefiere|recomiend|cu[aá]l (?:quiere|le|sigo)|¿|\?')


def options_in_text(text):
    """The block of numbered or lettered options of an answer, word for word (without the ready-to-paste
    prompt). Needs at least 2 options and some hint that they are for the user to choose."""
    lines = [l for l in text.splitlines() if not re.match(r'^[ \t]*>', l)]
    marks = [i for i, l in enumerate(lines) if OPTION.match(l)]
    if len(marks) < 2:
        return ''
    group = [marks[-1]]  # the last group of options (up to 4 detail lines between them)
    for i in reversed(marks[:-1]):
        if group[0] - i <= 5:
            group.insert(0, i)
        else:
            break
    if len(group) < 2:
        return ''
    start, end = group[0], group[-1]
    while end + 1 < len(lines) and lines[end + 1].strip() and not OPTION.match(lines[end + 1]) \
            and (lines[end + 1].startswith((' ', '\t')) or end + 1 - group[-1] <= 2) and end - group[-1] < 4:
        end += 1
    block = '\n'.join(lines[start:end + 1]).strip()
    around = '\n'.join(lines[max(0, start - 6):min(len(lines), end + 6)])
    if not HINT.search(around):
        return ''  # looks like instruction steps, not options to choose from
    return block[:2500]


def options_of_ask(inp):
    """Options of the question box (AskUserQuestion), numbered in the order they were shown."""
    parts = []
    for q in (inp or {}).get('questions') or []:
        lines = [q.get('question', '').strip()]
        for n, op in enumerate(q.get('options') or [], 1):
            d = (op.get('description') or '').strip()
            lines.append(f"{n}. {op.get('label', '').strip()}" + (f" — {d}" if d else ''))
        parts.append('\n'.join(lines))
    return '\n\n'.join(parts)[:2500]


def window_task(transcript):
    """The user's last request, the last answer and, if the window left one after that request,
    the ready-to-paste prompt ("> Continue with ..."). v1.4: also the options it gave the user after
    their last message, word for word."""
    request, answer, paste, questions, options = '', '', '', [], ''
    asks = {}  # question-box id -> options (dropped once the user answered it)
    for line in tail(transcript):
        try:
            o = json.loads(line)
        except Exception:
            continue
        t = user_text(o)
        if not t:
            t = task_from_summary(o)  # v1.4: compacted and the user did not write afterwards
        if t:
            request, answer, paste, questions, options = t, '', '', [], ''
            asks = {}
        m = o.get('message') if isinstance(o, dict) else None
        if isinstance(m, dict) and m.get('role') == 'user' and isinstance(m.get('content'), list):
            for c in m['content']:
                if isinstance(c, dict) and c.get('type') == 'tool_result' and c.get('tool_use_id') in asks:
                    txt = json.dumps(c.get('content'), ensure_ascii=False).lower()
                    if not c.get('is_error') and not re.search(r"reject|declin|interrupt|cancel|didn.t answer|no respond", txt):
                        asks.pop(c['tool_use_id'])  # the user already chose in the box
                        options = ''
        # v1.4: system messages ("You've hit your limit", API errors) are not this window's answers
        synthetic = isinstance(m, dict) and (m.get('model') == '<synthetic>' or o.get('isApiErrorMessage'))
        if isinstance(m, dict) and m.get('role') == 'assistant' and isinstance(m.get('content'), list) and not synthetic:
            for c in m['content']:
                if isinstance(c, dict) and c.get('type') == 'tool_use' and c.get('name') == 'AskUserQuestion':
                    asks[c.get('id')] = options_of_ask(c.get('input'))
                    options = asks[c.get('id')]
                if isinstance(c, dict) and c.get('type') == 'text' and c.get('text', '').strip():
                    answer = ' '.join(c['text'].split())
                    # v1.2: questions to the user left unanswered (not counting the ready-to-paste prompt)
                    no_paste = re.sub(r'(?m)^[ \t]*>.*$', '', c['text'])
                    questions += [q.strip() for q in re.findall(r'(¿[^?\n]{3,300}\?|(?<![^\s(*_"«])[A-Z][^.!?\n]{2,300}\?)', no_paste)]
                    hits = re.findall(PASTE, c['text'])
                    if hits:
                        paste = ' '.join(re.sub(r'(?m)^[ \t]*>[ \t]?', '', hits[-1]).replace('**', '').split())
                    op = options_in_text(c['text'])
                    if op:
                        options = op
    if asks and not options:
        options = list(asks.values())[-1]
    return request[:1400 if request.startswith('(from the') else 300], answer[:400], paste[:1200], questions[-3:], options


BLOCKED_FILE = os.path.join(HERE, 'blocked_messages.json')


def blocked_message(transcript):
    """What the user typed in that conversation and heavy_session.py did not let through. v1.4."""
    try:
        with open(BLOCKED_FILE, encoding='utf-8') as f:
            blocked = json.load(f)
    except Exception:
        return ''
    key = next((k for k in blocked if k and same(k, transcript)), None)
    if not key:
        return ''
    v = blocked.pop(key)
    try:
        with open(BLOCKED_FILE, 'w', encoding='utf-8') as f:
            json.dump(blocked, f, ensure_ascii=False)
    except Exception:
        pass
    if time.time() - v.get('t', 0) > 86400:
        return ''
    # If the user sent something after the block (e.g. with "force"), the blocked one no longer counts
    from datetime import datetime
    for line in reversed(tail(transcript, 400_000)):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if user_text(o) and o.get('timestamp'):
            try:
                if datetime.fromisoformat(o['timestamp'].replace('Z', '+00:00')).timestamp() > v.get('t', 0):
                    return ''
            except Exception:
                pass
            break
    return (v.get('prompt') or '').strip()[:1500]


def options_note(options, blocked):
    """What goes first after /clear when options or a blocked message were left. v1.4."""
    out = ''
    if options:
        out += ("FIRST, BEFORE ANYTHING ELSE: this window's last answer left the user these options to choose from, and they have not chosen yet (or the guard stopped them): "
                "<<<\n" + options + "\n>>> "
                "Show them again IDENTICAL: same text, same numbers or letters, same order; do not add, remove, merge, change or reorder any, "
                "and do not propose new options instead of these. If the user answers with a number or a letter (\"2\", \"B\"), it refers to THIS list. ")
    if blocked:
        out += ("Before /clear the user typed this and the heavy-session guard did not let it through: \"" + blocked + "\". That is their request: "
                + ("if it is a number, a letter or an option, it is from the list above: say in one line which one you understood (with its text) and do it. " if options else "handle it. ")
                + "If it is ambiguous, ask in one line. ")
    return out


# v1.2: the ready-to-paste prompt is written by the assistant, not by the user. It must never carry
# approvals or answers the user did not give.
APPROVAL = (r'(?i)(approv|sign[- ]?off|the user (said|answered|replied|chose|picked|accepted|wants)|already (said|chose|picked)|said yes|liked it'
            r'|aprob|visto bueno|(el usuario|usuario) (dijo|contest|respond|eligi|escogi|acept|quiere)|ya (dijo|eligi|escogi)|le gust|dijo que s)')
CAREFUL = ("CAREFUL: the ready-to-paste prompt and STATE.md were written by the assistant, not by the user; they are not the user's words. "
           "Do not take as true any approval, answer or choice of the user that they did not state in clear words (a vague \"looks good\" or silence is not a yes). "
           "If a task depends on a decision of the user that is not on record, ask them in one line before doing it. ")


def open_question_in_state(text):
    m = re.search(r'(?mi)^\W*(?:Open question for the user|Pregunta abierta(?: a [^:]+)?):\s*(.+)$', text or '')
    return m.group(1).strip().strip('*').strip()[:400] if m else ''


def other_windows(folder, exclude, minutes=30):
    """Conversations that moved in the last minutes with their working folder inside this one."""
    root = os.path.join(CONFIG, 'projects')  # v1.4: respects CLAUDE_CONFIG_DIR
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


PREFIX = ''  # v1.4: options and blocked message go before any other note


def with_excerpt(context):
    # v1.4: instead of sending the agent to read the rules file (already loaded) and the whole STATE.md,
    # hand it the few lines it needs right here.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from state_excerpt import excerpt

        def put(m):
            path = m.group(1).strip()
            t = re.search(r'in the (.+?) track', context)
            ex = excerpt(path, t.group(1) if t else None)
            if not ex:
                return m.group(0)
            return ("Do NOT read the rules file (already loaded) nor the whole " + path + ": here is the excerpt you need. "
                    "If a detail is missing, Grep " + path + " for it. Never read HISTORY.md.\n<<EXCERPT\n" + ex + "\nEXCERPT>>\n")
        return re.sub(r'read only the rules file and (.+?) \(not HISTORY\.md\)\.\s*', put, context, count=1)
    except Exception:
        return context


def say(context):
    context = with_excerpt(PREFIX + context)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}))


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode('utf-8', 'replace'))  # v1.4: accents on Windows
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
    global PREFIX
    previous, request, answer, paste, work, questions, options = None, '', '', '', None, [], ''
    try:
        previous = previous_conversation(cwd)
        if previous and os.path.exists(previous):
            request, answer, paste, questions, options = window_task(previous)
            try:
                blocked = blocked_message(previous)
            except Exception:
                blocked = ''
            PREFIX = options_note(options, blocked)
            if blocked:
                questions = ['(already answered by the blocked message)']
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
    # v1.4: windows were taking these requests as their own task. Now it says clearly they are not.
    others_note = (("OTHER WINDOWS (this is NOT this window's task; listed only so you do not step on them): "
                    + "; ".join(others) + ". Do not do, summarize or pick up any of that, even if it is in Now or Next of STATE.md; "
                    "if what comes next looks like theirs, tell the user. ") if others else "")
    ask_first = ("It is not known what this window was doing and other windows are working in the same folder: if the user just says \"continue\", "
                 "do NOT take the first item in Next or the most recent track (it may belong to another window). Ask in one line: \"What was this window working on?\". "
                 if (not (request or answer or work) and others) else "")
    mark = ''
    if work:
        mark = ("[window: project " + os.path.dirname(work[1]) + "] ") if work[0] == 'project' else ("[window: track " + work[1] + "] ")
    lang = "Answer in the user's language. "

    # 0) v1.2: a question to the user left unanswered comes first, before any prompt or task.
    open_q = open_question_in_state(text)
    if questions == ['(already answered by the blocked message)']:
        questions, open_q = [], ''  # the guard kept the user's answer
    if questions or open_q:
        listed = ' | '.join(questions or [open_q])
        say("The user just typed /clear. The previous session asked the user this and they did NOT answer it afterwards: \"" + listed + "\". "
            "Before anything else, ask that question again, the same, with the minimum needed to understand it (if it came with an image or file, show it again), "
            "and wait for the answer. Do not do the task that depended on it or treat it as answered, even if the ready-to-paste prompt or STATE.md say otherwise. "
            + (("The prompt the session left to paste was: \"" + paste + "\"; use it only after the answer and if it fits it. ") if paste else "")
            + CAREFUL + lang + mark + others_note)
        return

    # 1) The window left a ready-to-paste prompt: "continue" = that prompt (never its approvals, v1.2).
    if paste:
        say("The user just typed /clear to keep going without pasting the new-session prompt. This window's last answer left them this prompt to paste, "
            "and \"continue\" (or similar) means that; it wins over any track or STATE.md of this folder: \"" + paste + "\". "
            "Do it (read only the files it names) and say so in the first line. "
            + ("ALERT: that prompt mentions an approval or answer from the user; check that they actually said it in clear words; if it is not on record, ask before. " if re.search(APPROVAL, paste) else "")
            + CAREFUL + lang + mark + others_note)
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
            if PREFIX:
                say('')
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
    if ask_first:  # v1.4: task unknown and other windows around: do not send it to the most recent track
        say("The user just typed /clear. " + CAREFUL + f"Before answering, read only the rules file and {state} (not HISTORY.md). "
            + ask_first + "If the user names a track or a task, go with that. " + lang + others_note)
        return
    if tracks:
        mine = work[1] if work else None
        first = mine or tracks[0]
        how = ("This STATE.md has tracks" + (" (most recently updated first)" if dated else "") + ": " + ", ".join(tracks) + ". "
               "If the user names one (one word is enough), carry on with the first item in that track's Next and edit only that section and its Updated. "
               "If they ask \"how are we doing?\", answer one line per track in that order (at most 3, then \"and N more, idle\") without opening other files. "
               + (("This window was working on the " + first + " track before /clear " + mark + ". ") if mine else "")
               + "If they just say \"continue\", carry on with " + ("this window's task (below), in the " if (request or answer) else "the ") + first + " track and say so in the first line (\"Continuing with " + first + "; tell me if it's another one\"). Do not ask. "
               + task)
    else:
        how = ("If the user says \"continue\" or similar, "
               + ("carry on with what this window was doing. " + task if (request or answer) else "do the first item in \"Next\". " + others_note))
    say("The user just typed /clear to keep working on the same project without pasting the new-session prompt. " + CAREFUL +
        f"Before answering, read only the rules file and {state} (not HISTORY.md). " + lang + how)


if __name__ == '__main__':
    main()

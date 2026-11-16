# Continue after /clear (Claude Code SessionStart hook, matcher "clear").
# When you type /clear to start fresh in the same terminal, this tells the new session
# to read the rules file and STATE.md, so a single word ("continue", or a track name)
# is enough: no need to paste the new-session prompt.
# - With tracks: "continue" carries on with the track THIS window was on (noted at /clear by
#   remember_window.py); if unknown, with the most recently updated track. It says which and never asks.
# - Parent folder with no STATE.md (projects inside with their own): tells the session to create it first.
# - No STATE.md anywhere: stays silent.
import json, os, re, sys, time

STATE_FILE = 'STATE.md'
HERE = os.path.dirname(os.path.abspath(__file__))
WINDOWS_FILE = os.path.join(HERE, 'windows.json')
MARK = r'\[window: track ([^\]]+)\]'

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

def window_track(transcript, state, state_text, tracks):
    """Last track this window touched: its edits to STATE.md, files inside a track's folder
    (parent folder), its "Continuing with X" line, or the mark left by an earlier /clear."""
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
                if m.group(1) in tracks:
                    last = m.group(1)
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
                    if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(state)):
                        new = inp.get('new_string') or ''
                        if c.get('name') == 'MultiEdit' and inp.get('edits'):
                            new = inp['edits'][-1].get('new_string') or ''
                        found = track_in_edit(state_text, new, tracks) if new else None
                    else:
                        try:
                            rel = os.path.relpath(os.path.abspath(path), folder)
                        except ValueError:
                            rel = '..'
                        first = rel.replace('\\', '/').split('/')[0].lower()
                        found = by_name.get(first) if not rel.startswith('..') else None
                    if found:
                        last = found
                elif c.get('type') == 'text' and msg.get('role') == 'assistant':
                    m = re.match(r'\s*\**Continuing with (?:the )?([^;,.\n*]+?)(?: track)?[;,.\n*]', c.get('text') or '')
                    if m and m.group(1).strip().lower() in by_name:
                        last = by_name[m.group(1).strip().lower()]
    return last

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

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    cwd = data.get('cwd') or os.getcwd()
    state = find_state(cwd)
    if not state:
        kids = children_with_state(cwd)
        if not kids:
            return
        context = ("The user just typed /clear. This is a parent folder with no STATE.md of its own; inside are projects with theirs: "
                   + ", ".join(kids) + " (most recent first). Before answering, and without asking, create the parent's STATE.md "
                   "(with /session-kit): one track per project, in that order, with Updated (that date and time), Now and Next "
                   "(two or three lines, taken only from the top of each inner STATE.md). Then answer by the tracks rule: "
                   "\"how are we doing?\" = one line per track, most recent first, ending with \"Shall I continue with <the first>?\"; "
                   "\"continue\" = carry on with the first one and say so in the first line. Never ask \"which one should I continue?\". "
                   "Answer in the user's language.")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}))
        return
    try:
        text = open(state, encoding='utf-8').read()
    except Exception:
        return
    tracks, dated = tracks_by_date(text)
    if tracks:
        first = tracks[0]
        mine = None
        try:
            previous = previous_conversation(cwd)
            if previous and os.path.exists(previous):
                mine = window_track(previous, state, text, tracks)
        except Exception:
            mine = None
        if mine:
            first = mine
        how = ("This STATE.md has tracks" + (" (most recently updated first)" if dated else "") + ": " + ", ".join(tracks) + ". "
               "If the user names one (one word is enough), carry on with the first item in that track's Next and edit only that section and its Updated. "
               "If they ask \"how are we doing?\", answer one line per track in that order (at most 3, then \"and N more, idle\") without opening other files. "
               + (("This window was working on the " + first + " track before /clear [window: track " + first + "]. ") if mine else "")
               + "If they just say \"continue\", carry on with the " + first + " track and say so in the first line (\"Continuing with " + first + "; tell me if it's another one\"). Do not ask.")
    else:
        how = "If the user says \"continue\" or similar, do the first item in \"Next\"."
    context = ("The user just typed /clear to keep working on the same project without pasting the new-session prompt. "
               f"Before answering, read only the rules file and {state} (not HISTORY.md). Answer in the user's language. " + how)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}))

if __name__ == '__main__':
    main()

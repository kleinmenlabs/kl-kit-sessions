# Continue after /clear (Claude Code SessionStart hook, matcher "clear").
# When you type /clear to start fresh in the same terminal, this tells the new session
# to read the rules file and STATE.md, so a single word ("continue", or a track name)
# is enough: no need to paste the new-session prompt.
# - With tracks: "continue" carries on with the most recently updated track and says which; it never asks.
# - Parent folder with no STATE.md (projects inside with their own): tells the session to create it first.
# - No STATE.md anywhere: stays silent.
import json, os, re, sys, time

STATE_FILE = 'STATE.md'

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
        how = ("This STATE.md has tracks" + (" (most recently updated first)" if dated else "") + ": " + ", ".join(tracks) + ". "
               "If the user names one (one word is enough), carry on with the first item in that track's Next and edit only that section and its Updated. "
               "If they ask \"how are we doing?\", answer one line per track in that order (at most 3, then \"and N more, idle\") without opening other files. "
               "If they just say \"continue\", carry on with the " + first + " track and say so in the first line (\"Continuing with " + first + "; tell me if it's another one\"). Do not ask.")
    else:
        how = "If the user says \"continue\" or similar, do the first item in \"Next\"."
    context = ("The user just typed /clear to keep working on the same project without pasting the new-session prompt. "
               f"Before answering, read only the rules file and {state} (not HISTORY.md). Answer in the user's language. " + how)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}))

if __name__ == '__main__':
    main()

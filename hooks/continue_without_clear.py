# Continue without /clear (Claude Code UserPromptSubmit hook). v1.4.
# Problem: with several windows of one project left idle for a long time, saying "hi" or "continue"
# to one of them (especially after the conversation was compacted) made it re-read the shared
# STATE.md and pick up ANOTHER window's work.
# If the message is short ("continue", "go on", "hi", "siga"...) and this conversation already has
# history, this reminds the session to carry on with ITS OWN work. After /clear the conversation is
# empty and this does nothing (continue_after_clear.py handles that).
# If anything goes wrong, it does nothing.
import json, os, re, sys

SHORT = re.compile(r'^(?:hi|hello|hey|good (?:morning|afternoon|evening)|continue|go on|keep going|carry on|resume|next|ok,? continue|'
                   r'hola|buenas|buenos d[ií]as|buenas (?:tardes|noches)|siga|sigue|sigamos|contin[uú]e|contin[uú]a|continuemos|dale|'
                   r'(?:hi|hello|hey|hola|buenas)[, ]+(?:continue|go on|siga|contin[uú]e))'
                   r'(?:[ ,]+(?:please|then|now|por favor|pues|ya))*[.!¡¿?]*$', re.I)


def tail(path, size=600_000):
    n = os.path.getsize(path)
    with open(path, 'rb') as f:
        f.seek(max(0, n - size))
        return f.read().decode('utf-8', 'ignore').splitlines()


def history(transcript):
    """(has history, was compacted) looking at the tail of the conversation."""
    has, compacted = False, False
    for line in tail(transcript):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if not isinstance(o, dict):
            continue
        if o.get('isCompactSummary'):
            compacted = has = True
        m = o.get('message')
        if o.get('type') == 'assistant' and isinstance(m, dict) and m.get('model') != '<synthetic>':
            has = True
    return has, compacted


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode('utf-8', 'replace'))
    except Exception:
        return
    text = ' '.join((data.get('prompt') or '').split())
    if not SHORT.match(text):
        return
    tr = data.get('transcript_path')
    if not tr or not os.path.exists(tr):
        return
    try:
        has, compacted = history(tr)
    except Exception:
        return
    if not has:
        return
    note = ("The user wrote \"" + text + "\" in a conversation that ALREADY has history. \"Continue\" or a greeting refers to what THIS "
            "conversation was doing" + (" (see the automatic summary above: \"Current Work\" / \"Optional Next Step\")" if compacted else "") + ". "
            "Do not take the first item in Next or the most recent track of STATE.md, nor anything of other windows: several windows share "
            "STATE.md and its latest lines may belong to another one. Say in the first line what comes next in your own work and do it; "
            "if it is already done, say so and ask what is next. If you really do not know what you were doing, ask in one line. "
            "Answer in the user's language.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": note}}))


if __name__ == '__main__':
    main()

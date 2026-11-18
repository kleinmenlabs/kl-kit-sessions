# Remember window (Claude Code SessionEnd hook, matcher "clear").
# Right before /clear wipes the conversation, this notes which conversation this window had,
# keyed by CLAUDE_PID (the window's process, which survives /clear). continue_after_clear.py reads
# it a moment later to know which track THIS window was on, even if another window updated
# STATE.md since. If anything goes wrong, it does nothing.
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOWS_FILE = os.path.join(HERE, 'windows.json')

def main():
    data = json.load(sys.stdin)
    transcript = data.get('transcript_path')
    if not transcript:
        return
    try:
        with open(WINDOWS_FILE, encoding='utf-8') as f:
            windows = json.load(f)
    except Exception:
        windows = {}
    now = time.time()
    windows = {k: v for k, v in windows.items() if now - v.get('t', 0) < 86400}
    key = os.environ.get('CLAUDE_PID') or ('no-pid-' + str(int(now * 1000)))
    windows[key] = {'transcript': transcript, 'cwd': data.get('cwd') or os.getcwd(), 't': now}
    with open(WINDOWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(windows, f)
    try:  # tokens saved counter: /clear on a heavy conversation (status bar in plugin/)
        sys.path.insert(0, HERE)
        import tokens_saved
        tokens_saved.add(transcript, tokens_saved.context_size(transcript), 'clear')
    except Exception:
        pass

try:
    main()
except Exception:
    pass

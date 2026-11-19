# Require STATE.md (Claude Code Stop hook).
#
# If Claude edited files in a project that has a STATE.md (in that folder or any
# parent) and STATE.md is more than MARGIN_MINUTES older than those edits, Claude
# is not allowed to finish its turn until it updates it. Fires at most once per
# turn (it checks stop_hook_active), so it never loops.
#
# Projects without STATE.md are ignored. If anything goes wrong, it does nothing.
import json
import os
import re
import sys

STATE_NAME = "STATE.md"
IGNORE = ("state.md", "history.md")
MARGIN_MINUTES = 30
EDIT_TOOLS = ("Edit", "Write", "NotebookEdit")


def state_for(path):
    """Nearest STATE.md walking up from the edited file."""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        candidate = os.path.join(d, STATE_NAME)
        # Template and backup folders ship a STATE.md that tracks nothing; skip them.
        if os.path.exists(candidate) and not re.match(r"(templates|backup)", os.path.basename(d)):
            return candidate
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def edited_files(transcript):
    files = set()
    with open(transcript, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if '"tool_use"' not in line or "file_path" not in line:
                continue
            try:
                m = json.loads(line).get("message") or {}
            except Exception:
                continue
            for c in m.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") in EDIT_TOOLS:
                    p = (c.get("input") or {}).get("file_path")
                    if p and os.path.basename(p).lower() not in IGNORE:
                        files.add(p)
    return files


def main():
    data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
    if data.get("stop_hook_active"):
        return
    transcript = data.get("transcript_path")
    if not transcript or not os.path.exists(transcript):
        return
    behind = {}
    for p in edited_files(transcript):
        if not os.path.exists(p):
            continue
        state = state_for(p)
        if state and os.path.getmtime(p) - os.path.getmtime(state) > MARGIN_MINUTES * 60:
            behind.setdefault(state, set()).add(os.path.basename(p))
    if not behind:
        return
    listing = "; ".join(f"{s} (changes in: {', '.join(sorted(v)[:5])})" for s, v in behind.items())
    print(json.dumps({
        "decision": "block",
        "reason": (
            "Before finishing: STATE.md is behind the changes made in this session. "
            f"Update it now: {listing}. Replace the summary (one page max: now, done, next, key facts) "
            "and append one line to HISTORY.md. Keep it short."
        )}))


try:
    main()
except Exception:
    pass

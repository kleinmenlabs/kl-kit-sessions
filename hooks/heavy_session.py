# Heavy-session guard (Claude Code UserPromptSubmit hook).
#
# 1. Heavy AND idle: blocks your message BEFORE it is sent. Resuming a big
#    conversation whose prompt cache has expired reloads everything at full price
#    and can eat a large part of your usage limit. A blocked message costs nothing.
#    To send it anyway, start the message with the word: force
# 2. Heavy and still active: sends Claude a note (once per session, never blocks)
#    with the exact size, so it saves STATE.md / HISTORY.md and hands you the
#    prompt for a fresh session. Claude cannot see its own token count otherwise.
#
# If anything goes wrong, the hook does nothing: it never blocks by mistake.
import datetime as dt
import json
import os
import sys

HEAVY_TOKENS = 100_000    # context size that counts as "heavy"
IDLE_MINUTES = 55         # prompt cache lifetime is up to 1 hour; adjust to your plan
FORCE_WORD = "force"
HERE = os.path.dirname(os.path.abspath(__file__))
WARNED_FILE = os.path.join(HERE, "heavy_session_warned.json")


def last_usage(transcript):
    """Reads only the tail of the transcript: context size and time of the last reply."""
    size = os.path.getsize(transcript)
    with open(transcript, "rb") as f:
        f.seek(max(0, size - 3_000_000))
        lines = f.read().decode("utf-8", "ignore").splitlines()
    for line in reversed(lines):
        try:
            d = json.loads(line)
        except Exception:
            continue
        m = d.get("message")
        if isinstance(m, dict) and m.get("usage") and d.get("timestamp"):
            u = m["usage"]
            ctx = sum((u.get(k) or 0) for k in
                      ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            if ctx:
                return ctx, dt.datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00"))
    return 0, None


def warn_once(session, ctx):
    try:
        with open(WARNED_FILE, encoding="utf-8") as f:
            warned = json.load(f)
    except Exception:
        warned = {}
    if session in warned:
        return
    warned[session] = dt.datetime.now().isoformat(timespec="seconds")
    if len(warned) > 500:
        warned = dict(list(warned.items())[-300:])
    with open(WARNED_FILE, "w", encoding="utf-8") as f:
        json.dump(warned, f)
    k = round(ctx / 1000)
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": (
            f"HEAVY SESSION: this session is at {k}k tokens. Handle this message and, when the current "
            "step is done, follow the heavy-session rule (if the project has its own, the project's wins): "
            f"update STATE.md and HISTORY.md, tell the user the session is already at {k}k tokens and that "
            "it is better to continue in a new one, and give them the prompt to paste with the first item "
            "of 'Next', saying: \"Close this session and open a new one with this text\". "
            "The prompt carries only tasks the user asked for, never approvals or answers they did not give; "
            "if a question to the user was left unanswered, the prompt asks first to repeat that question and wait. "
            "Talk to the user in their own language."
        )}}))


def main():
    data = json.load(sys.stdin)
    if data.get("prompt", "").strip().lower().startswith(FORCE_WORD):
        return
    transcript = data.get("transcript_path")
    if not transcript or not os.path.exists(transcript):
        return
    ctx, when = last_usage(transcript)
    if not when or ctx < HEAVY_TOKENS:
        return
    idle = (dt.datetime.now(dt.timezone.utc) - when).total_seconds() / 60
    if idle < IDLE_MINUTES:
        warn_once(data.get("session_id") or transcript, ctx)
        return
    try:  # tokens saved counter (status bar in plugin/)
        sys.path.insert(0, HERE)
        import tokens_saved
        tokens_saved.add(transcript, ctx, "guard")
    except Exception:
        pass
    hours, mins = int(idle // 60), int(idle % 60)
    idle_txt = f"{hours} h {mins} min" if hours else f"{mins} min"
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"HEAVY SESSION: this conversation is {ctx:,} tokens and has been idle for {idle_txt}. "
            "Sending now would reload all of it at once and use a big part of your usage limit. "
            "Your message was NOT sent and cost nothing. Open a new session (it starts by reading STATE.md). "
            f"If you really need to continue here, start your message with: {FORCE_WORD}"
        )}))


try:
    main()
except Exception:
    pass  # never block because of a bug

# Runs the kit hooks against fake transcripts. Usage: python3 tests/test_hooks.py
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
work = tempfile.mkdtemp(prefix="session-kit-test-")
hooks = os.path.join(work, "hooks")
shutil.copytree(os.path.join(ROOT, "hooks"), hooks)  # keeps the warned-file out of the repo


def transcript(name, ctx, minutes_ago, edits=()):
    path = os.path.join(work, name + ".jsonl")
    ts = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
    with open(path, "w", encoding="utf-8") as f:
        for p in edits:
            f.write(json.dumps({"message": {"role": "assistant", "content": [
                {"type": "tool_use", "name": "Edit", "input": {"file_path": p}}]}}) + "\n")
        f.write(json.dumps({"timestamp": ts, "message": {"role": "assistant", "usage": {
            "input_tokens": 10, "cache_read_input_tokens": ctx, "cache_creation_input_tokens": 0}}}) + "\n")
    return path


def run(hook, payload, pid=None, home=None, config=None):
    env = dict(os.environ)
    env.pop("CLAUDE_PID", None)
    env.pop("CLAUDE_CONFIG_DIR", None)
    if pid:
        env["CLAUDE_PID"] = pid
    if home:  # a fake home, so the hooks see fake windows instead of your real ones
        env["HOME"] = env["USERPROFILE"] = home
    if config:
        env["CLAUDE_CONFIG_DIR"] = config
    # UTF-8 on purpose, like Claude Code sends it (accents must survive on Windows too)
    out = subprocess.run([sys.executable, os.path.join(hooks, hook)],
                         input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                         capture_output=True, env=env).stdout.decode("utf-8", "replace").strip()
    return json.loads(out) if out else None


results = []


def check(name, ok):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name)


heavy = transcript("heavy", 160_000, 2)
r = run("heavy_session.py", {"session_id": "a", "transcript_path": heavy, "prompt": "hi"})
check("heavy + active -> note to Claude", bool(r) and "HEAVY SESSION" in r["hookSpecificOutput"]["additionalContext"])
r = run("heavy_session.py", {"session_id": "a", "transcript_path": heavy, "prompt": "hi"})
check("same session again -> no repeat", r is None)
light = transcript("light", 40_000, 2)
check("light session -> nothing", run("heavy_session.py", {"session_id": "b", "transcript_path": light, "prompt": "hi"}) is None)
idle = transcript("idle", 160_000, 90)
r = run("heavy_session.py", {"session_id": "c", "transcript_path": idle, "prompt": "hi"})
check("heavy + idle -> blocked", bool(r) and r.get("decision") == "block")
check("heavy + idle + 'force' -> passes",
      run("heavy_session.py", {"session_id": "c", "transcript_path": idle, "prompt": "force hi"}) is None)

proj = os.path.join(work, "project")
os.makedirs(os.path.join(proj, "src"))
state, code = os.path.join(proj, "STATE.md"), os.path.join(proj, "src", "app.py")
open(state, "w").close()
open(code, "w").close()
old = time.time() - 3600
os.utime(state, (old, old))
t = transcript("edits", 1000, 0, edits=[code])
r = run("require_state.py", {"transcript_path": t, "stop_hook_active": False})
check("edits with stale STATE.md -> blocked", bool(r) and r.get("decision") == "block")
check("second stop in same turn -> lets go", run("require_state.py", {"transcript_path": t, "stop_hook_active": True}) is None)
os.utime(state, None)
check("STATE.md up to date -> lets go", run("require_state.py", {"transcript_path": t, "stop_hook_active": False}) is None)
outside = os.path.join(work, "loose.txt")
open(outside, "w").close()
t2 = transcript("loose", 1000, 0, edits=[outside])
check("project without STATE.md -> ignored", run("require_state.py", {"transcript_path": t2, "stop_hook_active": False}) is None)

def ctx(r):
    return r["hookSpecificOutput"]["additionalContext"] if r else ""


parent = os.path.join(work, "parent")
for n in ("Bikes", "Motos"):
    os.makedirs(os.path.join(parent, n))
    open(os.path.join(parent, n, "STATE.md"), "w").close()
os.utime(os.path.join(parent, "Bikes", "STATE.md"), (old, old))
r = run("continue_after_clear.py", {"cwd": parent})
check("parent folder without STATE.md -> create it, newest first",
      "create the parent's STATE.md" in ctx(r) and ctx(r).index("Motos") < ctx(r).index("Bikes"))
house = os.path.join(work, "house")
os.makedirs(os.path.join(house, "plans"))
with open(os.path.join(house, "STATE.md"), "w", encoding="utf-8") as f:
    f.write("## Track: Bathrooms\n**Updated:** 2026-11-10 09:00\n## Track: Garage\n"
            "**Updated:** 2026-11-15 08:30\n## Track: Living\n")
r = run("continue_after_clear.py", {"cwd": os.path.join(house, "plans")})
check("tracks -> continue with the most recent, never ask",
      "carry on with the Garage track" in ctx(r) and "Do not ask" in ctx(r))
house_state = os.path.join(house, "STATE.md")
old_window = os.path.join(work, "window_a.jsonl")
with open(old_window, "w", encoding="utf-8") as f:
    f.write(json.dumps({"message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Edit", "input": {
        "file_path": house_state, "old_string": "x", "new_string": "**Updated:** 2026-11-10 09:00"}}]}}) + "\n")
run("remember_window.py", {"transcript_path": old_window, "cwd": house}, pid="4242")
r = run("continue_after_clear.py", {"cwd": house}, pid="4242")
check("window on Bathrooms -> /clear -> continues Bathrooms, not the newest",
      "carry on with the Bathrooms track" in ctx(r))
chained = os.path.join(work, "window_a2.jsonl")
with open(chained, "w", encoding="utf-8") as f:
    f.write(json.dumps({"attachment": {"content": ctx(r)}}) + "\n")
run("remember_window.py", {"transcript_path": chained, "cwd": house}, pid="4242")
check("second /clear in a row -> still Bathrooms",
      "carry on with the Bathrooms track" in ctx(run("continue_after_clear.py", {"cwd": house}, pid="4242")))
check("other window, nothing noted -> most recent (Garage)",
      "carry on with the Garage track" in ctx(run("continue_after_clear.py", {"cwd": house}, pid="5555")))
check("no STATE.md anywhere -> silent", run("continue_after_clear.py", {"cwd": os.path.join(work, "hooks")}) is None)


# --- After /clear, "continue" = this window's own task ---
def write_lines(path, objs):
    with open(path, "w", encoding="utf-8") as f:
        for o in objs:
            f.write(json.dumps(o) + chr(10))
    return path


def said(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def answered(text):
    return {"message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


empty_home = os.path.join(work, "home0")
os.makedirs(os.path.join(empty_home, ".claude", "projects"))
w = write_lines(os.path.join(work, "paste.jsonl"), [said("render the draft"), answered(
    "Done. If you start fresh, paste this:\n> Continue with the project. Read only the rules file and STATE.md. "
    "First in \"Next\" is: send the invoice draft. Do it and let me know.")])
run("remember_window.py", {"transcript_path": w, "cwd": house}, pid="7001")
r = ctx(run("continue_after_clear.py", {"cwd": house}, pid="7001", home=empty_home))
check("last answer left a prompt to paste -> continue = that prompt",
      "send the invoice draft" in r and "means that" in r and "ALERT" not in r)
w = write_lines(os.path.join(work, "paste_es.jsonl"), [said("arme el borrador"), answered(
    "Listo. Para seguir en una sesión nueva:\n> Siga con el proyecto. Lea solo el archivo de reglas y STATE.md. Lo primero es: mandar la factura.")])
run("remember_window.py", {"transcript_path": w, "cwd": house}, pid="7004")
check("prompt to paste written in Spanish -> also recognized",
      "mandar la factura" in ctx(run("continue_after_clear.py", {"cwd": house}, pid="7004", home=empty_home)))
w = write_lines(os.path.join(work, "task.jsonl"), [said("fix the login form"), answered("Half done: the form validates, the button is next.")])
run("remember_window.py", {"transcript_path": w, "cwd": house}, pid="7002")
r = ctx(run("continue_after_clear.py", {"cwd": house}, pid="7002", home=empty_home))
check("no prompt to paste -> continue = this window's last task, not Next",
      "fix the login form" in r and "not with the first item in Next" in r)

# v1.2: the prompt to paste never approves things for the user; an unanswered question comes first
w = write_lines(os.path.join(work, "question.jsonl"), [said("make the cover image"), answered(
    "Here is the image. Do I use it for tomorrow's post?\n\nClose this session and open a new one with this text:\n"
    "> Continue with the project. The user said yes: use the image and publish it.")])
run("remember_window.py", {"transcript_path": w, "cwd": house}, pid="7101")
r = ctx(run("continue_after_clear.py", {"cwd": house}, pid="7101", home=empty_home))
check("unanswered question + prompt that says 'the user said yes' -> asks the question again first",
      "Do I use it for tomorrow's post?" in r and "ask that question again" in r and "Do it (read only" not in r)
w = write_lines(os.path.join(work, "answered.jsonl"), [said("make the cover image"), answered("Do I use it?"),
    said("no, make another one"), answered("Done.\n> Continue with the project. First in \"Next\" is: make another cover image.")])
run("remember_window.py", {"transcript_path": w, "cwd": house}, pid="7102")
r = ctx(run("continue_after_clear.py", {"cwd": house}, pid="7102", home=empty_home))
check("question the user already answered -> not asked again, follows the prompt",
      "make another cover image" in r and "ask that question again" not in r)
w = write_lines(os.path.join(work, "approval.jsonl"), [said("continue"), answered(
    "Done.\n> Continue with the project. The user approved the design: publish it.")])
run("remember_window.py", {"transcript_path": w, "cwd": house}, pid="7103")
check("prompt claims an approval -> alert to check the user really said it",
      "ALERT" in ctx(run("continue_after_clear.py", {"cwd": house}, pid="7103", home=empty_home)))
asked = tempfile.mkdtemp(prefix=".session-kit-asked-", dir=os.path.expanduser("~"))
with open(os.path.join(asked, "STATE.md"), "w", encoding="utf-8") as f:
    f.write("# Shop\n## Next\n- **Open question for the user:** which photo goes on the cover?\n- publish the post\n")
r = ctx(run("continue_after_clear.py", {"cwd": asked}, pid="7104", home=empty_home))
check("STATE.md has an open question -> asked before anything else", "which photo goes on the cover?" in r)
shutil.rmtree(asked, ignore_errors=True)

# A project with its own STATE.md outside the temp folder (temp folders are skipped on purpose)
outer = tempfile.mkdtemp(prefix=".session-kit-work-", dir=os.path.expanduser("~"))
shop = os.path.join(outer, "Shop")
os.makedirs(os.path.join(shop, "src"))
open(os.path.join(shop, "STATE.md"), "w").close()
w = write_lines(os.path.join(work, "other.jsonl"), [{"message": {"role": "assistant", "content": [
    {"type": "tool_use", "name": "Bash", "input": {"command": 'ls "' + os.path.join(shop, "src") + '"'}}]}}])
run("remember_window.py", {"transcript_path": w, "cwd": house}, pid="7003")
r = ctx(run("continue_after_clear.py", {"cwd": house}, pid="7003", home=empty_home))
check("window opened here but worked on another project -> continues there",
      "working on the project Shop" in r and "Do not take any track" in r)

busy_home = os.path.join(work, "home1")
os.makedirs(os.path.join(busy_home, ".claude", "projects", "p"))
write_lines(os.path.join(busy_home, ".claude", "projects", "p", "b.jsonl"),
            [{"cwd": os.path.join(house, "plans")}, said("paint the garage door")])
r = ctx(run("continue_after_clear.py", {"cwd": house}, pid="7999", home=busy_home))
check("other windows busy, task of this window unknown -> asks what it was doing (v1.4)",
      "paint the garage door" in r and "NOT this window's task" in r and "What was this window working on?" in r)
w = write_lines(os.path.join(work, "mine.jsonl"), [said("fix the gutter"), answered("Halfway: the left side is done.")])
run("remember_window.py", {"transcript_path": w, "cwd": house}, pid="7201")
r = ctx(run("continue_after_clear.py", {"cwd": house}, pid="7201", home=busy_home))
check("other windows busy, own task known -> keeps its task, theirs flagged as not its own",
      "fix the gutter" in r and "NOT this window's task" in r and "What was this window working on?" not in r)

# --- v1.4 ---
cfg = os.path.join(work, "config1")
os.makedirs(os.path.join(cfg, "projects", "p"))
write_lines(os.path.join(cfg, "projects", "p", "c.jsonl"), [{"cwd": house}, said("sand the stairs")])
r = ctx(run("continue_after_clear.py", {"cwd": house}, pid="7998", home=empty_home, config=cfg))
check("CLAUDE_CONFIG_DIR -> other windows are read from there", "sand the stairs" in r)

w = write_lines(os.path.join(work, "options.jsonl"), [said("roof colour"), answered(
    "Which one do you prefer?\n1. Blue roof (recommended)\n2. Red roof\n3. Leave it as it is")])
run("remember_window.py", {"transcript_path": w, "cwd": house}, pid="7301")
r = ctx(run("continue_after_clear.py", {"cwd": house}, pid="7301", home=empty_home))
check("options left to the user -> shown again identical, first",
      r.startswith("FIRST") and "1. Blue roof (recommended)\n2. Red roof\n3. Leave it as it is" in r)
w = write_lines(os.path.join(work, "steps.jsonl"), [said("how do I install it"), answered(
    "Done. To install:\n1. Open the app\n2. Click save")])
run("remember_window.py", {"transcript_path": w, "cwd": house}, pid="7302")
check("numbered instruction steps -> not taken as options",
      "IDENTICAL" not in ctx(run("continue_after_clear.py", {"cwd": house}, pid="7302", home=empty_home)))
ask = {"type": "tool_use", "id": "q1", "name": "AskUserQuestion", "input": {"questions": [{"question": "Which tile?", "options": [
    {"label": "Clay", "description": "classic"}, {"label": "Slate"}]}]}}
w = write_lines(os.path.join(work, "ask.jsonl"), [said("choose a tile"), {"message": {"role": "assistant", "content": [ask]}}])
run("remember_window.py", {"transcript_path": w, "cwd": house}, pid="7303")
r = ctx(run("continue_after_clear.py", {"cwd": house}, pid="7303", home=empty_home))
check("question box left unanswered -> its options come back numbered", "1. Clay — classic\n2. Slate" in r)
w = write_lines(os.path.join(work, "ask_done.jsonl"), [said("choose a tile"), {"message": {"role": "assistant", "content": [ask]}},
    {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "q1", "content": "Clay"}]}}])
run("remember_window.py", {"transcript_path": w, "cwd": house}, pid="7304")
check("question box already answered -> options not shown again",
      "IDENTICAL" not in ctx(run("continue_after_clear.py", {"cwd": house}, pid="7304", home=empty_home)))

heavy_opts = transcript("heavy_opts", 150_000, 90)
with open(heavy_opts, "a", encoding="utf-8") as f:
    f.write(json.dumps(answered("Which one do you prefer?\n1. Keep it\n2. Opción rápida")) + "\n")
run("heavy_session.py", {"session_id": "h1", "transcript_path": heavy_opts, "prompt": "la opción 2"})
run("remember_window.py", {"transcript_path": heavy_opts, "cwd": house}, pid="7305")
r = ctx(run("continue_after_clear.py", {"cwd": house}, pid="7305", home=empty_home))
check("message blocked by the guard -> handed to the new session as the answer, accents intact",
      "did not let it through" in r and "la opción 2" in r and "2. Opción rápida" in r)

summary = {"type": "user", "isCompactSummary": True, "message": {"role": "user", "content":
    "This session is being continued.\n8. Current Work:\n   Building the roof calculator.\n9. Optional Next Step:\n   Add the tile count.\n"}}
w = write_lines(os.path.join(work, "compact.jsonl"), [said("old request"), summary])
run("remember_window.py", {"transcript_path": w, "cwd": house}, pid="7306")
r = ctx(run("continue_after_clear.py", {"cwd": house}, pid="7306", home=empty_home))
check("compacted conversation -> task taken from the summary",
      "Building the roof calculator" in r and "Add the tile count" in r and "old request" not in r)

w = write_lines(os.path.join(work, "limit.jsonl"), [said("paint the fence"), answered("Working on the fence: first coat done."),
    {"message": {"role": "assistant", "model": "<synthetic>", "content": [{"type": "text", "text": "You've hit your limit"}]}}])
run("remember_window.py", {"transcript_path": w, "cwd": house}, pid="7307")
r = ctx(run("continue_after_clear.py", {"cwd": house}, pid="7307", home=empty_home))
check("usage-limit system message -> not taken as the window's last answer",
      "first coat done" in r and "hit your limit" not in r)

twin = os.path.join(work, "twin")
os.makedirs(twin)
open(os.path.join(twin, "STATE.md"), "w").close()
for n, job in (("t1", "wash the car"), ("t2", "walk the dog")):
    run("remember_window.py", {"transcript_path": write_lines(os.path.join(work, n + ".jsonl"), [said(job)]), "cwd": twin})
r = ctx(run("continue_after_clear.py", {"cwd": twin}, home=empty_home))
check("two windows of one folder cleared at once, no window id -> takes neither task",
      "wash the car" not in r and "walk the dog" not in r)

# --- Messages between windows ---
msg_home = os.path.join(work, "home2")
os.makedirs(os.path.join(msg_home, ".claude", "projects", "p"))
os.makedirs(os.path.join(msg_home, ".claude", "sessions"))
for i, name in enumerate(("house-a1", "house-b2")):
    with open(os.path.join(msg_home, ".claude", "sessions", str(i) + ".json"), "w") as f:
        json.dump({"pid": os.getpid(), "name": name, "nameSource": "derived", "sessionId": "s" + str(i), "cwd": house}, f)
write_lines(os.path.join(msg_home, ".claude", "projects", "p", "s1.jsonl"), [said("tile the bathroom")])
send = {"session_id": "me", "tool_input": {"to": "house-a1", "message": "please update the garage plan"}}
r = run("message_to_window.py", send, home=msg_home)
reason = r["hookSpecificOutput"]["permissionDecisionReason"] if r else ""
check("first message to a folder-named window -> stopped, shows what each window does",
      "derived from its folder" in reason and "tile the bathroom" in reason)
check("sent again to the same window -> goes through", run("message_to_window.py", send, home=msg_home) is None)
send["tool_input"]["to"] = "house-b2"
r = run("message_to_window.py", send, home=msg_home)
check("same request to a second window -> stopped",
      bool(r) and "already sent this same request" in r["hookSpecificOutput"]["permissionDecisionReason"])
cfg2 = os.path.join(work, "config2")
os.makedirs(os.path.join(cfg2, "projects", "p"))
os.makedirs(os.path.join(cfg2, "sessions"))
with open(os.path.join(cfg2, "sessions", "0.json"), "w") as f:
    json.dump({"pid": os.getpid(), "name": "house-c3", "nameSource": "derived", "sessionId": "s9", "cwd": house}, f)
write_lines(os.path.join(cfg2, "projects", "p", "s9.jsonl"), [said("fix the roof leak")])
r = run("message_to_window.py", {"session_id": "me2", "tool_input": {"to": "house-c3", "message": "check the roof"}},
        home=empty_home, config=cfg2)
check("CLAUDE_CONFIG_DIR -> windows are read from there",
      bool(r) and "fix the roof leak" in r["hookSpecificOutput"]["permissionDecisionReason"])
shutil.rmtree(outer, ignore_errors=True)

# Tokens saved counter (read by the status bar in plugin/)
saved_file = os.path.join(hooks, "tokens_saved.json")
if os.path.exists(saved_file):
    os.remove(saved_file)


def saved_total():
    try:
        with open(saved_file, encoding="utf-8") as f:
            return json.load(f)["total"]
    except Exception:
        return 0


blocked = transcript("saved-blocked", 130_000, 90)
run("heavy_session.py", {"session_id": "s1", "transcript_path": blocked, "prompt": "hi"})
check("blocked heavy session -> counted as saved", saved_total() == 130_010)
run("heavy_session.py", {"session_id": "s1", "transcript_path": blocked, "prompt": "hi again"})
check("same conversation blocked twice -> counted once", saved_total() == 130_010)
cleared = transcript("saved-cleared", 200_000, 1)
run("remember_window.py", {"transcript_path": cleared, "cwd": work}, pid="9001")
check("/clear on a heavy conversation -> added", saved_total() == 330_020)
small = transcript("saved-small", 50_000, 1)
run("remember_window.py", {"transcript_path": small, "cwd": work}, pid="9002")
check("/clear on a light conversation -> not counted", saved_total() == 330_020)

# v1.4: "continue" without /clear in a conversation with history -> its own work
long_conv = write_lines(os.path.join(work, "long.jsonl"), [said("tile the kitchen"), dict(answered("Half the wall is done."), type="assistant")])
r = ctx(run("continue_without_clear.py", {"transcript_path": long_conv, "prompt": "continue"}))
check("'continue' in a conversation with history -> reminded to keep its own work", "ALREADY has history" in r)
check("'Siga, pues' (Spanish) -> same reminder",
      "ALREADY has history" in ctx(run("continue_without_clear.py", {"transcript_path": long_conv, "prompt": "Siga, pues"})))
check("a real request -> nothing", run("continue_without_clear.py", {"transcript_path": long_conv, "prompt": "continue with the bathroom tiles"}) is None)
fresh = write_lines(os.path.join(work, "fresh.jsonl"), [said("continue")])
check("'continue' in an empty conversation (after /clear) -> nothing",
      run("continue_without_clear.py", {"transcript_path": fresh, "prompt": "continue"}) is None)

# --- v1.4: cheap start ---
lean = os.path.join(work, "lean")
os.makedirs(lean)
with open(os.path.join(lean, "STATE.md"), "w", encoding="utf-8") as f:
    f.write("# STATE\n\n## Now\n- Tiling the bathroom, half done.\n" + "- old note\n" * 400 + "\n## Next\n1. Grout the tiles.\n")
r = run("how_are_we.py", {"prompt": "How are we doing?", "cwd": lean})
check("'how are we doing?' -> answered by the kit, message blocked (0 tokens)",
      bool(r) and r.get("decision") == "block" and "Tiling the bathroom" in r["reason"] and "Grout the tiles" in r["reason"])
check("'¿cómo vamos?' (Spanish) -> same", (run("how_are_we.py", {"prompt": "¿Cómo vamos?", "cwd": lean}) or {}).get("decision") == "block")
check("a real request -> goes to the agent", run("how_are_we.py", {"prompt": "how are we doing on the roof budget", "cwd": lean}) is None)
r = ctx(run("continue_after_clear.py", {"cwd": lean}, pid="7401", home=empty_home))
check("after /clear -> short excerpt handed over instead of 'read the whole STATE.md'",
      "<<EXCERPT" in r and "Grout the tiles" in r and "read only the rules file" not in r and len(r) < 3500)
big_file = os.path.join(lean, "STATE.md")
deny = lambda r: bool(r) and r["hookSpecificOutput"]["permissionDecision"] == "deny"
check("Read of a big file without limit -> denied", deny(run("read_guard.py", {"tool_name": "Read", "tool_input": {"file_path": big_file}})))
check("Read with offset/limit -> allowed", run("read_guard.py", {"tool_name": "Read", "tool_input": {"file_path": big_file, "limit": 40}}) is None)
check("Read of HISTORY.md -> denied", deny(run("read_guard.py", {"tool_name": "Read", "tool_input": {"file_path": os.path.join(lean, "HISTORY.md"), "limit": 5}})))
check("cat of a big file -> denied", deny(run("read_guard.py", {"tool_name": "Bash", "tool_input": {"command": 'cat "' + big_file + '"'}})))
check("cat piped to head -> allowed", run("read_guard.py", {"tool_name": "Bash", "tool_input": {"command": 'cat "' + big_file + '" | head -5'}}) is None)
check("small file -> allowed", run("read_guard.py", {"tool_name": "Read", "tool_input": {"file_path": os.path.join(hooks, "how_are_we.py")}}) is None)

shutil.rmtree(work, ignore_errors=True)
print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)

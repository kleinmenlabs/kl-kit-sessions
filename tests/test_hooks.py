# Runs the five hooks against fake transcripts. Usage: python3 tests/test_hooks.py
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


def run(hook, payload, pid=None, home=None):
    env = dict(os.environ)
    env.pop("CLAUDE_PID", None)
    if pid:
        env["CLAUDE_PID"] = pid
    if home:  # a fake home, so the hooks see fake windows instead of your real ones
        env["HOME"] = env["USERPROFILE"] = home
    out = subprocess.run([sys.executable, os.path.join(hooks, hook)], input=json.dumps(payload),
                         capture_output=True, text=True, env=env).stdout.strip()
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
      "send the invoice draft" in r and "means exactly that" in r)
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
check("other windows busy in the same folder -> listed, hands off",
      "paint the garage door" in r and "do not do or touch their work" in r)

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
shutil.rmtree(outer, ignore_errors=True)

shutil.rmtree(work, ignore_errors=True)
print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)

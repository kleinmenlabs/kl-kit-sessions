# Runs the three hooks against fake transcripts. Usage: python3 tests/test_hooks.py
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


def run(hook, payload):
    out = subprocess.run([sys.executable, os.path.join(hooks, hook)], input=json.dumps(payload),
                         capture_output=True, text=True).stdout.strip()
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
check("no STATE.md anywhere -> silent", run("continue_after_clear.py", {"cwd": os.path.join(work, "hooks")}) is None)

shutil.rmtree(work, ignore_errors=True)
print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)

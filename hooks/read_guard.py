# Read guard (Claude Code PreToolUse hook on Read|Bash|PowerShell). v1.4.
# Everything the agent reads is re-sent on every later step, so whole files eat the usage limit.
# - Read without "limit" of a text file over 150 lines or 12 KB: denied (use Grep, then offset/limit).
# - HISTORY.md / HISTORIAL.md: never read; grep it.
# - cat / type / Get-Content of a big file without head, tail, sed -n, grep...: denied.
# To read a whole file on purpose, give Read a limit. If anything fails, it lets the call through.
import json, os, re, sys

MAX_LINES, MAX_BYTES = 150, 12_000
BINARY = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf', '.ipynb', '.mp4', '.mp3', '.wav', '.svg')
HISTORY = ('HISTORY.MD', 'HISTORIAL.MD')
PARTIAL = re.compile(r'\b(head|tail|sed\s+-n|-TotalCount|-Tail|Select-Object|grep|rg|Select-String|wc)\b')
DUMP = re.compile(r'(?:^|[;&|(]\s*)(?:cat|type|more|less|Get-Content|gc)\s+("[^"]+"|\'[^\']+\'|[^\s;&|]+)')


def big(path):
    try:
        if path.lower().endswith(BINARY) or not os.path.isfile(path):
            return None
        size = os.path.getsize(path)
        with open(path, 'rb') as f:
            n = f.read(4_000_000).count(b'\n')
        return (n, size) if (n > MAX_LINES or size > MAX_BYTES) else None
    except Exception:
        return None


def native(p):
    p = p.strip().strip('"\'')
    m = re.match(r'^/([a-zA-Z])/(.*)', p) if os.name == 'nt' else None
    return os.path.expanduser(m.group(1) + ':/' + m.group(2) if m else p)


def deny(reason):
    sys.stdout.buffer.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                        "permissionDecisionReason": reason}}, ensure_ascii=False).encode('utf-8'))


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode('utf-8', 'replace'))
        tool, ti = data.get('tool_name'), data.get('tool_input') or {}
        if tool == 'Read':
            path = ti.get('file_path') or ''
            if os.path.basename(path).upper() in HISTORY:
                return deny('READ GUARD: the history file is never read. Find what you need with Grep.')
            g = None if ti.get('limit') else big(path)
            if g:
                return deny(f'READ GUARD: {os.path.basename(path)} has {g[0]} lines ({g[1] // 1000} KB). Do not read it whole: '
                            'find the spot with Grep and Read it with offset and limit (about 80 lines). '
                            'Only if the user asked for the whole file, give it a limit.')
        elif tool in ('Bash', 'PowerShell'):
            cmd = ti.get('command') or ''
            if PARTIAL.search(cmd):
                return
            for m in DUMP.finditer(cmd):
                path = native(m.group(1))
                if os.path.basename(path).upper() in HISTORY:
                    return deny('READ GUARD: the history file is never read. Use grep.')
                g = big(path)
                if g:
                    return deny(f'READ GUARD: {os.path.basename(path)} has {g[0]} lines. Do not dump it whole: use grep -n or sed -n.')
    except Exception:
        return


if __name__ == '__main__':
    main()

# "How are we doing?" answered by Python from STATE.md (Claude Code UserPromptSubmit hook). v1.4.
# The message is blocked: you see the answer and no tokens are spent. If anything fails, the message
# goes to the agent as usual.
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ASK = re.compile(r'^\s*[¿]?\s*(?:so\s+|y\s+)?(?:how\s+are\s+we\s+doing|where\s+are\s+we|what\s+were\s+we\s+doing|status|'
                 r'c[oó]mo\s+vamos|en\s+qu[eé]\s+[ií]bamos|en\s+qu[eé]\s+vamos)\s*[?.!]*\s*$', re.I)
NAMES = ('STATE.md', 'ESTADO.md')


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode('utf-8', 'replace'))
        if not ASK.match(data.get('prompt') or ''):
            return
        from state_excerpt import status
        cwd = data.get('cwd') or os.getcwd()
        path = next((os.path.join(cwd, n) for n in NAMES if os.path.isfile(os.path.join(cwd, n))), None)
        answer = status(path) if path else ''
        if not answer:
            return
        answer += '\n(Answered by the kit from ' + os.path.basename(path) + ': 0 tokens. Name a track or say "continue".)'
        sys.stdout.buffer.write(json.dumps({"decision": "block", "reason": answer}, ensure_ascii=False).encode('utf-8'))
    except Exception:
        return


if __name__ == '__main__':
    main()

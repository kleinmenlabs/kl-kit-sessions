# Short excerpt of a STATE.md (v1.4). Used by how_are_we.py and continue_after_clear.py so the agent
# never has to open the whole file. Understands English and Spanish headings.
import os, re

SECTION_CAP = 700
TOTAL_CAP = 1600
TRACK = r'^##\s*(?:Track|Frente):\s*'
UPDATED = r'(?:Updated|Actualizado):\**\s*(\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2})?)'
NOW, NEXT = ('Now', 'Ahora'), ('Next', 'Siguiente')
OPEN_Q = r'^\W*(?:Open question for the user|Pregunta abierta(?: a [^:]+)?):.*$'


def read(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception:
        return ''


def short(s, n):
    s = re.sub(r'\n{2,}', '\n', s.strip())
    return s if len(s) <= n else s[:n].rsplit(' ', 1)[0] + ' …'


def tracks(text):
    """[(name, date, body)], most recent "Updated" first."""
    out = []
    for i, p in enumerate(re.split(TRACK, text, flags=re.M)[1:]):
        lines = p.splitlines()
        body = '\n'.join(lines[1:])
        m = re.search(UPDATED, body)
        date = m.group(1).replace('T', ' ') if m else ''
        out.append((date + (' 00:00' if len(date) == 10 else ''), -i, lines[0].strip() if lines else '', body))
    out.sort(reverse=True)
    return [(n, d, b) for d, _, n, b in out]


def sections(text):
    d = {}
    for p in re.split(r'^##\s+', text, flags=re.M)[1:]:
        lines = p.splitlines()
        d[lines[0].strip()] = '\n'.join(lines[1:]).strip()
    return d


def section(sec, names):
    return next((v for k, v in sec.items() if k.lower().startswith(tuple(n.lower() for n in names))), '')


def first_line(body, names):
    m = re.search(r'\**(?:' + '|'.join(names) + r')\**:?\**\s*(.*)', body, re.I)
    if not m:
        return ''
    t = m.group(1).strip() or next(iter(body[m.end():].strip().splitlines()), '')
    return re.sub(r'^[-*\d.]+\s*', '', t).strip()


def excerpt(path, track=None):
    text = read(path)
    if not text:
        return ''
    out = [short(x, 400) for x in re.findall(OPEN_Q, text, re.M)][:1]
    tr = tracks(text)
    if tr:
        pick = next((x for x in tr if track and x[0].lower() == track.lower()), tr[0])
        out.append('## Track: ' + pick[0] + '\n' + short(pick[2], TOTAL_CAP - 200))
        others = [x[0] + (' (' + x[1] + ')' if x[1] else '') for x in tr if x is not pick]
        if others:
            out.append('Other tracks: ' + ', '.join(others))
    else:
        sec = sections(text)
        for label, names in (('Now', NOW), ('Next', NEXT)):
            t = section(sec, names)
            if t:
                out.append('## ' + label + '\n' + short(t, SECTION_CAP))
        if len(out) < 2 and not (sec and (section(sec, NOW) or section(sec, NEXT))):
            out.append(short(text, TOTAL_CAP))
    return short('\n'.join(out), TOTAL_CAP)


def status(path):
    """One line per track (max 3 and "and N more idle"); without tracks, Now and Next in short."""
    text = read(path)
    if not text:
        return ''
    tr = tracks(text)
    if tr:
        lines = []
        for n, d, b in tr[:3]:
            line = '• ' + n + (' (' + d + ')' if d else '') + ': ' + short(first_line(b, NOW) or b, 180)
            nxt = first_line(b, NEXT)
            lines.append(line + (' → Next: ' + short(nxt, 140) if nxt else ''))
        if len(tr) > 3:
            lines.append('and ' + str(len(tr) - 3) + ' more idle')
        return '\n'.join(lines)
    sec = sections(text)
    out = []
    for label, names in (('Now', NOW), ('Next', NEXT)):
        first = next((x for x in section(sec, names).splitlines() if x.strip()), '')
        if first:
            out.append(label + ': ' + short(re.sub(r'^[-*\d.]+\s*', '', first), 300))
    return '\n'.join(out)

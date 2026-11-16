---
name: session-kit
description: Sets up a project for the session kit (AGENTS.md with session rules plus a CLAUDE.md that loads it, a one-page STATE.md and a HISTORY.md) without deleting anything the project already has. Use when the user says "session kit", "apply the kit", "set up this project", or when a project has no STATE.md.
---

# Session kit

The templates live next to this file in the kit repository (`templates/AGENTS.md`, `templates/CLAUDE.md`, `templates/STATE.md`, `templates/HISTORY.md`). If they are not at hand, use the structure described below.

## Steps (never delete or replace anything)

1. **Find the right folder.** The rules files must be in the folder where sessions are opened, or in a parent folder; in a sibling folder it is not loaded.
1b. **Parent folder** (several projects inside, each with its own STATE.md): put only shared rules there and give it its own STATE.md from `templates/STATE_tracks.md`: one track per project, two or three lines (Updated = date and time that project's STATE.md last changed, Now, Next, "Detail: <folder>/STATE.md"), most recent first. Take only the top of each inner STATE.md; do not read their HISTORY.md or anything else. If the parent had no STATE.md, do this without asking. Afterwards do not ask which one to continue: propose the most recent.
2. **AGENTS.md + CLAUDE.md:** the rules live in AGENTS.md (read by Codex, Cursor and others); CLAUDE.md only holds the line `@AGENTS.md` so Claude Code loads the same file. If neither exists, create both from the templates, adapted to the project (name, time zone). If one of them already exists, do not replace it (add `@AGENTS.md` to an existing CLAUDE.md only if AGENTS.md holds the rules): append only what is missing from "Start of every session", "While working" and "When closing". Do not repeat what it already says. If a rule clashes with an existing one, the existing one wins and you tell the user which.
3. **STATE.md:** if it exists, do not drop facts; arrange it as Now · Done · Next · Key facts, and tell the user about old sections that contradict the current state (do not delete them without a yes). If it does not exist, create it from what you find in the project.
3b. **Tracks:** if the project has parts worked on separately (even if everything sits in one folder) or the user runs several sessions at once in the same folder, use `templates/STATE_tracks.md`: one `## Track: <name>` section per part, each with `Updated:`, without losing facts. With a single piece of work, do not add tracks. If it no longer fits on one page, keep STATE.md as an index and the detail in `state/<track>.md`.
4. **HISTORY.md:** if it does not exist, create it with a first line. If it exists, only append today's line.
5. **Show the user what changed** (files and sections) in a few lines.

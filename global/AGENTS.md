# Session rules for all my projects

These rules work in any coding agent (Claude Code, Codex, Cursor and others). Always answer in the language I write in. Get the local time from the system before writing a date or hour; never guess it; if you cannot get it, write the date only.

**If the project has its own rules (its CLAUDE.md or AGENTS.md) about this, the project's rules win.** These are the minimum so that no session works without memory.

1. **On start:** read the project's `STATE.md`. Do not read `HISTORY.md`: only search it (grep) when an old fact is missing.
   **Tracks (parts of one project, or several sessions in the same folder):** if STATE.md has tracks (sections `## Track: <name>`, each with an `Updated: <date time>` line), each session works on one track only and edits only its own section and date; re-read the file right before writing and never delete other tracks.
   - "How are we doing?" with no track named: one line per track, most recently updated first (at most 3, then "and N more, idle"), without opening other files.
   - "Continue" with no track named: carry on with the most recently updated track and say so in the first line ("Continuing with <track>; tell me if it's another one"). Do not ask. On a tie or missing dates, take the first one listed. Never end with "which one should I continue?"; at most "Shall I continue with <track>?".
   - Another session for other work: add a new track. With no tracks or a single one, carry on as usual. If STATE.md no longer fits on one page, keep it as an index (one line per track) and move each track's detail to `state/<track>.md`; read only the one you work on.
   **Parent folder (several projects inside, each with its own STATE.md):** the parent keeps its own STATE.md with one short track per project (Updated with the date and time that project's STATE.md last changed, Now, Next), most recent first. Whoever works on a project also updates its line in the parent's STATE.md. If a parent folder has no STATE.md, create it right away without asking.
2. **Every time you finish something or start a long job** (not only at the end): update `STATE.md` (Now · Done · Next · Key facts; replaced, one page max; with tracks, only your section and its `Updated`; if a parent folder above has a STATE.md, update your project's line there too) and append to `HISTORY.md` one line `[date time] Done | Evidence/file | Pending | Next step`.
3. **Long jobs** (batches, renders, background processes): leave in `STATE.md` what is running, how to tell it finished and what to do then, so another session can pick it up.
4. **End every reply in which something changed** with "Noted in STATE.md and HISTORY.md" (in the user's language).
5. **Heavy session:** if the note "HEAVY SESSION: this session is at…" arrives, an automatic summary of the conversation appeared, you looked at many images, it has been going for many hours, or I am about to switch accounts: when the current step is done, update STATE.md and HISTORY.md, tell me how heavy the session is (if the note said it) and leave me this text to paste in a new session, saying "Close this session and open a new one with this text":
   > Continue with the project. Read only the rules file and STATE.md (not HISTORY.md). First in "Next" is: <the exact task>. Do it and let me know.

   With tracks, the text starts with the track: "Continue with the <name> track. Read only the rules file and your track in STATE.md…".
6. If the project has no `STATE.md`, offer to set it up (in Claude Code, with `/session-kit`; elsewhere, from the templates of the session kit).

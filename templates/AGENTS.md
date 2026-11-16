# <PROJECT NAME> — Instructions for coding agents

**Time zone:** <e.g. Europe/Madrid>. Get the local time from the system before writing a date or hour; never guess it; if you cannot get it, write the date only. **Language:** always answer the user in the language they write in.

## Start of every session (one minute, max)
1. Read only these rules and `STATE.md`. **Do not read `HISTORY.md`**: only search it (grep) when an old fact is missing.
2. Summarize in three lines: done, pending, next action. Then do that action.
3. **Tracks (parts of one project, or several sessions in the same folder):** if STATE.md has tracks (sections `## Track: <name>`, each with an `Updated: <date time>` line), each session works on one track only and edits only its own section and date; re-read the file right before writing and never delete other tracks.
   - "How are we doing?" with no track named: one line per track, most recently updated first (at most 3, then "and N more, idle"), without opening other files.
   - "Continue" with no track named: carry on with the most recently updated track and say so in the first line ("Continuing with <track>; tell me if it's another one"). Do not ask. On a tie or missing dates, take the first one listed. Never end with "which one should I continue?"; at most "Shall I continue with <track>?".
   - Another session for other work: add a new track. With no tracks or a single one, carry on as usual. If STATE.md no longer fits on one page, keep it as an index (one line per track) and move each track's detail to `state/<track>.md`; read only the one you work on.
   **Parent folder (several projects inside, each with its own STATE.md):** the parent keeps its own STATE.md with one short track per project (Updated with the date and time that project's STATE.md last changed, Now, Next), most recent first. Whoever works on a project also updates its line in the parent's STATE.md. If a parent folder has no STATE.md, create it right away without asking.

## While working
- One thing at a time. Finish, test and deliver before starting the next one.
- Anything the user asks for that is not done yet goes **into STATE.md**, under "Next", never only in the chat.
- Before changing anything in production, say what it is and wait for a yes.
- **Every time you finish something or start a long job** (not only at the end): update STATE.md and append the line to HISTORY.md right then. If the session dies halfway, whatever is not written down is lost.
- **Long jobs** (batches, renders, background processes): write in STATE.md what is running, how to tell it finished (log or output file) and what to do when it does.
- **End every reply in which something changed** with "Noted in STATE.md and HISTORY.md" (in the user's language).

## When closing, or when the session is heavy
You cannot see how many tokens you have used, and the cut-off comes without warning. The session is **heavy** if any of these happened: a note "HEAVY SESSION: this session is at…" arrived (sent by the session-kit hook, Claude Code only), an automatic summary or compaction of the conversation appeared, you looked at many images, it has been going for many hours, or the user is about to switch accounts. Then, when the current step is done:
1. **STATE.md**: replace the summary (one page, max): Now · Done · Next (in order) · Key facts. With tracks, only your section and its `Updated`; with a parent folder STATE.md above, your line there too.
2. **HISTORY.md**: append one line: `[date time] Done | Evidence/file | Pending | Next step` (with tracks: `[date time] [Track] Done | …`).
3. Give the user, in the chat, the **prompt for a new session** below, and say: "Close this session and open a new one with this text".

> Continue with the project. Read only the rules file and STATE.md (not HISTORY.md). First in "Next" is: <the exact task>. Do it and let me know.

With tracks, the prompt names the track: "Continue with the <name> track. Read only the rules file and your track in STATE.md…".

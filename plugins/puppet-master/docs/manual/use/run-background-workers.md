# Run background workers

Let one Claude session, the master, hand your jobs to the Claude sessions you already have open, one job each, and
start a background worker only when none of them is free. It measures each session's context, tells you when one needs
compacting, and keeps one session as an analyst that proposes improvements to the master at the end of the day. Claude
only does the housekeeping; every decision stays yours.

## Before you start

- puppet-master is installed. See [Install a plugin](../../../../../docs/manual/getting-started/install-a-plugin.md).
- Node.js 20 or newer is on your `PATH`.
- Background sessions can edit files without a git worktree. Add this to your own `~/.claude/settings.json` (Claude
  never changes it for you):

  ```json
  { "worktree": { "bgIsolation": "none" } }
  ```

- You've run `claude` once in each folder a worker will use, so the folder is trusted.
- On Windows, the native `claude` executable is on your `PATH`. Installed through npm? Set `PUPPET_CLAUDE_BIN` to the
  full path of the `claude` executable, because the npm `claude.cmd` shim can't be started.
- Optional: for the master to compact and clear sessions for you, Claude Code 2.1.287 or newer. See
  [Let sessions compact themselves](#let-sessions-compact-themselves).
- Optional: choose where the analyst keeps its logs. When you enable puppet-master, Claude Code asks for the **puppet-master
  logs folder**; leave it empty to use the plugin's own data folder. A copy of the skill installed by hand reads
  `PUPPET_LOGS_DIR` instead.

## Start the master

1. Open the sessions you want to work in, then, in the one you want as the master, type:

   > /puppet-master:puppet-master

2. Claude lists your open sessions by name, with their folders, and asks which it may use. Answer "all", or "all but
   the ones in my other project". Sessions you leave out are never touched or read. In the same question it asks
   whether it may compact your sessions and clear finished workers for you. Claude suggests yes, but nothing
   happens unless you answer yes.
3. It sets one of them aside as the **analyst** and gives it no job. If none of your sessions is clean, it starts a
   background session for that.

## Give it a job

Say what the job is:

> Merge the payments branch into the test branch in the backend repository. It may commit, but not push.

Claude picks a clean session of yours in that repository and gives it the job, with the rules you've set (where scratch
files go, for example). You see a line like `assigned backend-b7: merge payments into test`. If no clean session is free
there, it starts a background worker instead, on the model and effort the job's tier needs:
`spawned backend-merge id=<id> in <folder> (model opus, effort high)`.

- Each job gets a tier. Design, writing and review are `creative`: an Opus model at high effort or more. Renames,
  moves and checks are `mechanical`: another model at medium effort or less. If a session runs the wrong model or
  effort, Claude says `MISMATCH` and gives you `/model` and `/effort` lines to paste into that window. It never
  changes a session's settings itself.
- A session that already did a job gets another one only while it is small, under 30% of its context as your status
  line shows it. Otherwise clear it (`/clear`) and tell Claude, or let Claude start a worker. A follow-up to the job a
  session still holds goes to the same session, and a job closed too early can be reopened.
- One session edits one repository at a time, unless both jobs name the folders they write, the folders don't
  overlap, and only one of them runs git. Otherwise, for a second job in the same repository, use a second clone.
- When a session has a question, Claude asks you, one at a time, quoting your own words back before its reading of them.

## Keep it small

Claude measures each session's context, and compacts only between tasks:

- An idle session at 30% of its context or more, with work left, needs compacting.
  - With the mod on in that session, Claude compacts it for you when it is idle, a window of yours or a worker alike.
  - Without it, a background worker is compacted and restarted by Claude.
  - Without it, your own window is left to auto-compact. If you'd rather choose the moment, say "give me compact
    lines" once, and Claude gives you one line to paste, such as `backend-b7: /compact keep the merge state and the
    next step`. A message from another session can't run `/compact`.
- A busy session at 50% or more is asked to stop at its next task boundary first.
- Before compacting a worker above 50%, Claude tells you its size and that a compaction can cost close to a dollar.
- Once Claude has seen a session auto-compact, it knows the size where that happens. From 80% of it, a session's line
  ends in `WARN near compaction`.

Ask "how are my sessions?" to see each one's size, model and effort, state and job.

## Let sessions compact themselves

puppet-master ships a small mod that runs inside a session and compacts it, or clears it, when the master asks. It
does nothing in a session until you switch it on, and it never touches a session that is working.

1. Make sure Claude Code is 2.1.287 or newer. A window you opened before you installed or updated puppet-master needs
   `/reload-plugins`.
2. Open a window. At the start, it asks whether the master may compact it. Answer:
   - **Yes, this session** to switch it on for this window only.
   - **Yes, always on this machine** to switch it on everywhere. This sets the `self_compact` option to `on`.
   - **No** to leave it off for this window. It asks again next time.
   - **No, and don't ask again on this machine** to set `self_compact` to `off`. That also overrides the master.
   A dismissed question counts as no. A background worker never asks: the master switches it on, after you said yes
   when you started the master.
3. Ask "how are my sessions?". A session whose mod is on ends its line in `mod on (asked)`, `mod on (optin)` or
   `mod on (config)`. `mod off (mode ask)` is a window you did not switch on, `mod stale` a mod that stopped, and no
   `mod` at all a session where the plugin is not loaded.

What the master then does:

- It compacts an idle session with a focus it writes from the job, in your window or a worker.
- It clears only a worker whose job is finished, between jobs, and only when it is idle. It never clears the window
  you use as the master, the analyst, or a session with an open job.
- If a session can't do it, the master says why and gives you the line to paste instead, such as
  `backend-b7: /clear`.

To turn it off for good, set `self_compact` to `off` in the plugin's options (see [Commands](../reference/commands.md#plugin-options)).

## Wrap up the day

Say "wrap up". Claude then:

1. Asks the analyst for its report. The report starts by saying how much it read, then lists what went wrong with
   evidence (which session, when, what was said) and proposes changes to the master.
2. Goes through the proposals with you one at a time: approve, reject or defer. Nothing changes on its own; an approved
   proposal is a job for another time.
3. Closes the background workers and tells you which of your windows you can close.

Not now? Say so. The next time you start the master, it offers the report first.

## Check it worked

When a background job is done, Claude closes the worker and shows a line like
`closed backend-merge (resume: cd "<folder>" && claude --resume <session id>)`. The conversation is kept: run that command to
open it again. The day's report is in the logs folder, under the date: `<logs folder>/2026-10-28/report.md`. A day
there starts at 05:00, so work past midnight stays with its day. To start it at another hour, set
`PUPPET_DAY_START_HOUR` (`0` for midnight).

## If something goes wrong

| You see | Do this |
| --- | --- |
| `puppet: no context window` | Tell Claude the window size your status line shows, or set `PUPPET_CONTEXT_WINDOW` to it (in tokens) |
| `puppet: cannot run claude` | Set `PUPPET_CLAUDE_BIN` to the full path of the `claude` executable |
| `already editing` | Another session works in that folder. Wait for it to finish, use a second clone, or give both jobs separate folders |
| `one job per context` | That session already did a job. Claude can reuse it while it is small; otherwise clear it and tell Claude, or let Claude start a worker |
| `MISMATCH … tier …` | Paste the `/model` and `/effort` lines Claude gives you into that window |
| `WARN near compaction` | That session is close to auto-compacting. Let it finish its task, then compact or clear it as Claude suggests |
| `no clean session for <folder>; spawn one` | None of your sessions is free there; Claude starts a worker |
| `changed (new session id …)` | The window was cleared or restarted. Tell Claude whether it is clean now |
| `just compacted (auto); its size is known after its next turn` | Wait for that session's next answer, then ask again |
| `is stopped and NOT compacted` | Run the restart command the message ends with |
| `no mod heartbeat` | The plugin isn't loaded in that session. Run `/reload-plugins` there, or paste the line the message ends with |
| `loaded but not switched on` | You didn't switch the mod on in that session. Say yes in its window, or tell Claude to switch it on |
| `was NOT compacted` or `was NOT cleared` | The message says why, and ends with the line to paste |
| A worker can't edit files | Check the `bgIsolation` line in your `~/.claude/settings.json` |

More: [Troubleshooting](../reference/troubleshooting.md).

## Related

- [Commands](../reference/commands.md)
- [What it never does](../../../README.md#what-it-never-does)

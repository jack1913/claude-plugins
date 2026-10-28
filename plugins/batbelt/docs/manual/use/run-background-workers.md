# Run background workers

Let one Claude session, the master, hand your jobs to the Claude sessions you already have open, one job each, and
start a background worker only when none of them is free. It measures each session's context, tells you when one needs
compacting, and keeps one session as an analyst that proposes improvements to the master at the end of the day. Claude
only does the housekeeping; every decision stays yours.

## Before you start

- batbelt is installed. See [Install a plugin](../../../../../docs/manual/getting-started/install-a-plugin.md).
- Node.js 20 or newer is on your `PATH`.
- Background sessions can edit files without a git worktree. Add this to your own `~/.claude/settings.json` (Claude
  never changes it for you):

  ```json
  { "worktree": { "bgIsolation": "none" } }
  ```

- You've run `claude` once in each folder a worker will use, so the folder is trusted.
- On Windows, the native `claude` executable is on your `PATH`. Installed through npm? Set `PUPPET_CLAUDE_BIN` to the
  full path of the `claude` executable, because the npm `claude.cmd` shim can't be started.
- Optional: choose where the analyst keeps its logs. When you enable batbelt, Claude Code asks for the **puppet-master
  logs folder**; leave it empty to use the plugin's own data folder. A copy of the skill installed by hand reads
  `PUPPET_LOGS_DIR` instead.

## Start the master

1. Open the sessions you want to work in, then, in the one you want as the master, type:

   > /batbelt:puppet-master

2. Claude lists your open sessions by name, with their folders, and asks which it may use. Answer "all", or "all but
   the ones in my other project". Sessions you leave out are never touched or read.
3. It sets one of them aside as the **analyst** and gives it no job. If none of your sessions is clean, it starts a
   background session for that.

## Give it a job

Say what the job is:

> Merge the payments branch into the test branch in the backend repository. It may commit, but not push.

Claude picks a clean session of yours in that repository and gives it the job, with the rules you've set (where scratch
files go, for example). You see a line like `assigned backend-b7: merge payments into test`. If no clean session is free
there, it starts a background worker instead: `spawned backend-merge id=<id> in <folder>`.

- A session that already did a job never gets another one. Clear it (`/clear`) and tell Claude, or let it start a worker.
- One session edits one folder at a time. For a second job in the same repository, use a second clone.
- When a session has a question, Claude asks you, one at a time, quoting your own words back before its reading of them.

## Keep it small

Claude measures each session's context, and compacts only between tasks:

- An idle session at 30% of its context or more, with work left, needs compacting.
  - A background worker is compacted and restarted by Claude.
  - For your own window, Claude gives you one line to paste into it, such as
    `backend-b7: /compact keep the merge state and the next step`. A message from another session can't run `/compact`.
- A busy session at 50% or more is asked to stop at its next task boundary first.
- Before compacting a worker above 50%, Claude tells you its size and that a compaction can cost close to a dollar.

Ask "how are my sessions?" to see each one's size, state and job.

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
open it again. The day's report is in the logs folder, under the date: `<logs folder>/2026-10-28/report.md`.

## If something goes wrong

| You see | Do this |
| --- | --- |
| `puppet: no context window` | Tell Claude the window size your status line shows, or set `PUPPET_CONTEXT_WINDOW` to it (in tokens) |
| `puppet: cannot run claude` | Set `PUPPET_CLAUDE_BIN` to the full path of the `claude` executable |
| `already editing` | Another session works in that folder. Wait for it to finish, or use a second clone |
| `one job per context` | That session already did a job. Clear it and tell Claude, or let Claude start a worker |
| `no clean session for <folder>; spawn one` | None of your sessions is free there; Claude starts a worker |
| `changed (new session id …)` | The window was cleared or restarted. Tell Claude whether it is clean now |
| `just compacted (auto); its size is known after its next turn` | Wait for that session's next answer, then ask again |
| `is stopped and NOT compacted` | Run the restart command the message ends with |
| A worker can't edit files | Check the `bgIsolation` line in your `~/.claude/settings.json` |

More: [Troubleshooting](../reference/troubleshooting.md).

## Related

- [Commands](../reference/commands.md)
- [Grill a plan](grill-a-plan.md)

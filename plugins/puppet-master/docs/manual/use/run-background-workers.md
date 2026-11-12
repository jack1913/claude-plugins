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
- Optional: for the master to compact, clear and switch the model of sessions for you, Claude Code 2.1.287 or
  newer. See
  [Let sessions compact themselves](#let-sessions-compact-themselves).
- Optional: choose where the analyst keeps its logs. When you enable puppet-master, Claude Code asks for the **puppet-master
  logs folder**; leave it empty to use the plugin's own data folder. A copy of the skill installed by hand reads
  `PUPPET_LOGS_DIR` instead.

## Start the master

1. Open the sessions you want to work in, then, in the one you want as the master, type:

   > /puppet-master:puppet-master

2. Claude lists your open sessions by name, with their folders, and asks which it may use. Answer "all", or "all but
   the ones in my other project". Sessions you leave out are never touched or read. In the same question it asks
   whether it may compact your sessions, switch their model and effort for a job, and clear finished workers for
   you. Claude suggests yes, but nothing happens unless you answer yes.
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
  moves and checks are `mechanical`: another model at medium effort or less. Your open windows get the work first.
  If a window runs the wrong model or effort and its mod is on, Claude switches it to the job's model and effort
  itself, for that window only: you see `switched backend-b7 to sonnet medium …`. Its status line keeps showing the
  model it started with, and asked which model it is, it names that one too; Claude checks the real one in its
  session list. Where the mod is not on, Claude takes another window or starts a background worker on the right
  model and effort. If you want that window for the job, Claude gives you lines for it: run `/model` and press `s`
  on the model's row, then `/effort` and press `s` at the level. `s` changes that session only. A typed
  `/model opus` or `/effort high` would save your default for every new session. Claude never changes your
  settings.
- A session that already did a job gets another one only while it is small, under 30% of its context as your status
  line shows it. Otherwise clear it (`/clear`) and tell Claude, or let Claude start a worker. A follow-up to the job a
  session still holds goes to the same session, and a job closed too early can be reopened.
- One session edits one repository at a time, unless both jobs name the folders they write, the folders don't
  overlap, and only one of them runs git. Otherwise, for a second job in the same repository, use a second clone.
- When a session has a question, Claude asks you, one at a time, quoting your own words back before its reading of them.
  The sessions send their questions to the master's window, never to you in their own. Set each worker's window to
  accept-edits once, when its job starts. Only an irreversible step (a delete, a push, a write to Railway) still shows a
  permission prompt in the worker's own window, and Claude tells you which window and what it waits for.
  - A step the worker's permission check will probably refuse (discarding a change, `rm -rf`) reaches you before the
    job starts, as a `!` line to type in the worker's window, with the reason. In auto mode nothing prompts for an
    outside write or a push, so when you approve one, the question includes its `!` line. The worker waits for you at
    that step, and Claude tells you when it moves on.
  - A worker's design recommendation first gets a read-only design pass by a session. Claude shows you its short
    summary, then asks one question at a time, and puts the worker's recommendation as the worker's, next to the
    simplest change that would also work.
  - A worker's question always comes to you, even when Claude thinks your earlier answers settle it, with its
    recommendation and why. Only housekeeping (compaction, scope, temp folders) is Claude's own call.
  - When a short answer such as "a" or "later" could fit more than one open question, Claude names the one it read
    it against and checks before passing it on. Each open question gets an id (A1, A2), and later messages say "A2 is
    still open" instead of asking it again.
  - Claude acts on everything in your message before it replies: a "go" starts the job in the same turn, and "if you
    have free workers" starts the second job or says why not. When a job ends, it also starts any item you already
    approved that needs no decision, and says so in one line.
- A window you rename keeps its record: Claude carries its job to the new name.

## Keep it small

Claude measures each session's context, and compacts only between tasks:

- An idle session at 30% of its context or more, with work left, needs compacting.
  - With the mod on in that session, Claude compacts it for you when it is idle, a window of yours or a worker alike.
  - Without it, a background worker is compacted and restarted by Claude.
  - Without it, your own window is left to auto-compact. If you'd rather choose the moment, say "give me compact
    lines" once, and Claude gives you one line to paste, such as `backend-b7: /compact keep the merge state and the
    next step`. A message from another session can't run `/compact`.
- Claude measures a working session each time it relays that session's message, and again when the session reports
  its job done: a session that finishes a task with work left is compacted right then, and one whose job is over
  is closed (a background worker) or cleared (a window whose mod is on).
- A busy session at 30% or more is asked to pause at its next part boundary first. Claude waits until the session
  is idle, then compacts it with a focus naming the job and the next part, and tells it to continue. A worker also
  pauses and says so on its own once it passes about 150k tokens.
- Claude's own window gets a `/compact` line from Claude at 40% or more, and again after each further 20%.
- Before compacting a worker above 50%, Claude tells you its size and that a compaction can cost close to a dollar.
- Claude gives a session's size in tokens and as a share of a 1,000,000-token window, unless you tell it your
  window is another size.

Ask "how are my sessions?" to see each one's size, model and effort, state and job.

## Let sessions compact themselves

puppet-master ships a small mod that runs inside a session and compacts it, switches its model and effort, or clears
it, when the master asks. It does nothing in a session until you switch it on, and it never touches a session that is
working.

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
   `mod on (config)`, then `switched to <model> <effort>` once the master switched it. `mod off (mode ask)` is a
   window you did not switch on, `mod stale` a mod that stopped, and no `mod` at all a session where the plugin is
   not loaded.

What the master then does:

- It compacts an idle session with a focus it writes from the job, in your window or a worker.
- It switches an idle session's model and effort to what the job needs. The switch holds for that session only,
  through compactions and clears, until the master switches it back; your settings and other sessions keep theirs.
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
| `puppet: cannot run claude` | Set `PUPPET_CLAUDE_BIN` to the full path of the `claude` executable |
| `already editing` | Another session works in that folder. Wait for it to finish, use a second clone, or give both jobs separate folders |
| `one job per context` | That session already did a job. Claude can reuse it while it is small; otherwise clear it and tell Claude, or let Claude start a worker |
| `MISMATCH … tier …` | Where that window's mod is on, Claude switches it. Elsewhere, let Claude start a worker on the right tier, or keep the window: run `/model` and press `s` on the row Claude names, then `/effort` and press `s` at the level |
| The status line shows the old model after a switch | Expected: the status line and the session's own answer keep the model it started with. The session list shows the model in use |
| `no clean session for <folder>; spawn one` | None of your sessions is free there; Claude starts a worker |
| `changed (new session id …)` | The window was cleared or restarted. Tell Claude whether it is clean now |
| `just compacted (auto); its size is known after its next turn` | Wait for that session's next answer, then ask again |
| `is stopped and NOT compacted` | Run the restart command the message ends with |
| `no mod heartbeat` | The plugin isn't loaded in that session. Run `/reload-plugins` there, or paste the line the message ends with |
| `loaded but not switched on` | You didn't switch the mod on in that session. Say yes in its window, or tell Claude to switch it on |
| `was NOT compacted`, `was NOT cleared` or `was NOT switched` | The message says why, and ends with the line to paste |
| A worker can't edit files | Check the `bgIsolation` line in your `~/.claude/settings.json` |

More: [Troubleshooting](../reference/troubleshooting.md).

## Related

- [Commands](../reference/commands.md)
- [What it never does](../../../README.md#what-it-never-does)

# puppet-master

Coordinate your Claude sessions from one session: hand each job to an open session or a background worker.

## Install

```text illustrative
/plugin marketplace add jack1913/claude-plugins
/plugin install puppet-master@jack1913
```

Other ways to install (from a shell, for a whole team):
[Install a plugin](../../docs/manual/getting-started/install-a-plugin.md).

After you install or update it, a window that is already open keeps the skill text it loaded: run `/reload-plugins`
there. Typing `/puppet-master:puppet-master` again does not reload it.

It needs Node.js 20 or newer, and a setting you add yourself first: see
[Run background workers](docs/manual/use/run-background-workers.md). The optional mod (compact, switch the model,
clear, and the page's Send button) needs Claude Code 2.1.287 or newer; without it, everything else works, and the task
page answers by Copy.

## Try it

In the session you want as the master, type:

> /puppet-master:puppet-master

Claude lists your open sessions and asks which of them it may use. Then say a job, its folder and whether it may commit.

## What you can do

| Command | Starts | What it's for |
| --- | --- | --- |
| `/puppet-master:puppet-master` | you only | Hand jobs to your open Claude sessions, and to background ones when none is free, one job each |

Every command, with its options: [Commands](docs/manual/reference/commands.md).

How-to page: [Run background workers](docs/manual/use/run-background-workers.md).

## The live task page

The master opens one page per set of work, gives you its full path and updates it at every change. Open that file in a
browser.

- **Four tabs.** Questions (every open ask, grouped by task), Tasks (one row each, grouped, with its newest line and
  its three newest reports), Epics and Jira (one card per epic, with each repo's PR, its Jira status and when it was read)
  and Side questions (what you asked the master beside the tasks).
- **Sidebar and rail.** The wide sidebar lists every status filter with its count, each session's share of its context
  and what it is doing, and the earlier sets of work. Folded, it is a narrow rail that keeps every status filter and session.
  Open tasks wear their own colour, teal, so they stand apart from running, waiting and done ones.
- **Reports** open in a panel beside the list (shown from the start on a window 1,200 px wide or more); drag its left
  edge to resize it.
- It follows your light or dark setting, and reads its data again every 90 seconds without reloading.

How the master keeps it: [Run background workers](docs/manual/use/run-background-workers.md).

## Answer the master on the page

You do not have to type in the master's window. Every open ask has its options as buttons (the recommended one first)
and a notes box. Pick, write, and either:

- **Copy.** Press Copy and paste the one line it builds into the master's window, e.g.
  `A122 answer (task page): "Commit + push both" — notes: …`. This works on any page, including one you opened as a file.
- **Send.** Press Send and the line reaches the master with no paste. Send exists only when the master serves the page
  itself, and the header chip reads "Linked · live over http". A page opened as a file reads "Copy-only · file://" and
  has no Send. To serve it, the master writes `board/<its session id>.json` into the mod's folder
  (`~/.claude/puppet-master/mod`) with `{ "dir": "<the page's folder>", "port": 8747 }`; its mod then starts the board
  server and delivers each message as a prompt. After an install or an update, type `/reload-plugins` in the master so
  its mod loads the new code: a window keeps the mod it loaded until then. Then open `http://127.0.0.1:8747/`. If
  another program holds that port, the server takes the next free one (up to nine more) and writes the address to
  `~/.claude/puppet-master/mod/board-live/<its session id>.json`; the master gives you the link, and `port` in the
  board file picks a different starting port.

Also on the page:

- **Grill me.** When the master asks a run of questions, a chip opens them in the right panel one at a time, with the
  answers so far above.
- **The ⋯ menu on a task row.** Start, Wait and Open report act at once. Commit, Push and Jira change are only
  requests: the master asks you in its own window, and a click on the page is never the approval for any of them.

The board server listens on 127.0.0.1 only, and accepts a message only from its own page. More:
[The task-page channel](docs/internals/puppet-master.md#the-task-page-channel).

## What needs what

| For | You need |
| --- | --- |
| Everything, including the board server | Node.js 20 or newer on the `PATH` of the app that runs Claude Code (the server uses only Node's own modules). If that app cannot see `node`, set `PUPPET_NODE_BIN` to its full path |
| Starting, listing and closing sessions | `claude` on your `PATH`, or `PUPPET_CLAUDE_BIN` set to its full path. On Windows it also finds `claude.exe` on the `PATH`, or the program an npm `claude.cmd` shim runs |
| One editor per checkout | `git` on your `PATH` (the helper asks it for a folder's repository root) |
| The Epics and Jira tab's PR lines | `gh` on your `PATH`, signed in (`sync-epics.mjs` runs `gh pr view`; it only reads) |
| The Epics and Jira tab's Jira lines | Optional: a Jira command you name with `sync-epics.mjs --jira <command>`, which prints one issue as JSON for `<command> <KEY> --json`. Without it the tab says "Jira not configured" |
| Operating systems | Windows, macOS and Linux are supported. The plugin's tests run in CI on Linux only, on Node 20 and Node 24 (`.github/workflows/puppet-master.yml`); Windows and macOS are supported but not tested in CI. CI does not start a real Claude session |
| Compact, clear, switch model, and Send | The mod on in that session: Claude Code 2.1.287 or newer, and your yes at its start question |
| The master's mod to load new code | `/reload-plugins` in that window |
| Send from the page | The master's mod on, and its `board/<session id>.json` file |
| Copy from the page | Nothing: a page opened as a file is enough |

Send works in a live Claude Code 2.1.332 session (four answers sent from the page on 2026-11-27 arrived in the master
as plugin messages). The lowest Claude Code version that has the calls it uses (`$.prompt.submit`, `$.process.spawn`)
is not checked below 2.1.332.

## What it adds to your sessions

puppet-master adds one skill and one small mod. It adds no agents. Its one server, the board server, runs on 127.0.0.1
only, and starts only when the master has written a `board/<session id>.json` file and its mod is on.

- **It runs only when you type it**, so it never starts driving your sessions on its own.
- **Its mod is off until you say yes.** The mod runs inside each session where the plugin is on. A window you opened
  asks once at start whether the master may compact it and switch its model and effort, and does nothing without a
  yes. A worker is switched on only by the master, after you said yes. It touches only its own folder,
  `~/.claude/puppet-master/mod`. It can compact any switched-on session when idle, switch its model and effort for
  that session only (the status line keeps showing the model it started with; the mod adds its own line naming the switch), and clear only a worker whose job is
  finished, never the master. In the master it also submits the page's Send lines as prompts and starts the board
  server. The `self_compact` setting turns it on or off for good.
- **It hands jobs to the Claude sessions you name**, and starts, compacts and closes background ones, which run as you with your settings. It keeps a list of those sessions in `~/.claude/puppet-master/workers.json` (`workers-<group>.json` when several masters run on one machine).
- **Its analyst** reads the transcripts of those sessions and the master's, and writes the day's events, findings and report to a logs folder you choose (the plugin's data folder by default), with any text that looks like a secret blanked.

## What it never does

- It never compacts a session mid-task, never clears the master or a session with an open job, never creates a git
  worktree, and never changes your settings. The one exception is its own `self_compact` option, saved only when you
  answer "always" or "don't ask again".
- Pushes, approvals and anything destructive wait for your yes. A commit or push you approve, Claude runs itself. A
  message from the task page never counts as that yes: commit, push and Jira changes arrive from it as requests only.
- Its analyst never changes the plugin: it proposes, and you decide.

## Something off?

| You see | Do this |
| --- | --- |
| `/puppet-master:puppet-master` doesn't start when you ask in words | Type the command. It only runs when typed |
| A background worker can't edit files | Add `"worktree": { "bgIsolation": "none" }` to your own `~/.claude/settings.json` |

More: [Troubleshooting](docs/manual/reference/troubleshooting.md).

## Learn more

- [Manual](docs/manual/README.md)
- [Changelog](CHANGELOG.md)
- [How it works](docs/internals/README.md) (for contributors)

puppet-master is released under the [MIT licence](LICENSE).

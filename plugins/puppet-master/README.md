# puppet-master

Coordinate your Claude sessions from one session: hand each job to an open session or a background worker.

## Install

```text illustrative
/plugin marketplace add jack1913/claude-plugins
/plugin install puppet-master@jack1913
```

Other ways to install (from a shell, for a whole team):
[Install a plugin](../../docs/manual/getting-started/install-a-plugin.md).

It needs Node.js 20 or newer, and a setting you add yourself first: see
[Run background workers](docs/manual/use/run-background-workers.md). The optional mod (compact, switch the model,
clear) needs Claude Code 2.1.287 or newer; without it, everything else works.

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

## What it adds to your sessions

puppet-master adds one skill and one small mod. It adds no agents or servers.

- **It runs only when you type it**, so it never starts driving your sessions on its own.
- **Its mod is off until you say yes.** The mod runs inside each session where the plugin is on. A window you opened
  asks once at start whether the master may compact it and switch its model and effort, and does nothing without a
  yes. A worker is switched on only by the master, after you said yes. It touches only its own folder,
  `~/.claude/puppet-master/mod`. It can compact any switched-on session when idle, switch its model and effort for
  that session only (the status line keeps showing the model it started with), and clear only a worker whose job is
  finished, never the master. The `self_compact` setting turns it on or off for good.
- **It hands jobs to the Claude sessions you name**, and starts, compacts and closes background ones, which run as you with your settings. It keeps a list of those sessions in `~/.claude/puppet-master/workers.json` (`workers-<group>.json` when several masters run on one machine).
- **Its analyst** reads the transcripts of those sessions and the master's, and writes the day's events, findings and report to a logs folder you choose (the plugin's data folder by default), with any text that looks like a secret blanked.

## What it never does

- It never compacts a session mid-task, never clears the master or a session with an open job, never creates a git
  worktree, and never changes your settings. The one exception is its own `self_compact` option, saved only when you
  answer "always" or "don't ask again".
- Pushes, approvals and anything destructive stay yours.
- Its analyst never changes the plugin: it proposes, and you decide.

## Something off?

| You see | Do this |
| --- | --- |
| `/puppet-master:puppet-master` doesn't start when you ask in words | Type the command. It only runs when typed |
| A background worker can't edit files | Add `"worktree": { "bgIsolation": "none" }` to your own `~/.claude/settings.json` |
| `puppet: no context window` | Tell Claude the window size your status line shows, or set `PUPPET_CONTEXT_WINDOW` to it, in tokens |

More: [Troubleshooting](docs/manual/reference/troubleshooting.md).

## Learn more

- [Manual](docs/manual/README.md)
- [Changelog](CHANGELOG.md)
- [How it works](docs/internals/README.md) (for contributors)

puppet-master is released under the [MIT licence](LICENSE).

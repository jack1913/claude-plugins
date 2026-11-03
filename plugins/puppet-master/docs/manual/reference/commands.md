# Commands

Everything puppet-master adds to Claude Code. "You only" means it runs only when you type it.

## Commands and skills

| Command | Starts | What it does | Arguments |
| --- | --- | --- | --- |
| `/puppet-master:puppet-master` | you only | Hands jobs to your open sessions, and to background workers when none is free, one job each; compacts only between tasks; an analyst session proposes improvements at the end of the day | — |

## puppet-master

Type the command in the session you want as the master. It takes no arguments: it asks which open sessions it may use, then you say each job, its folder and whether it may commit. Say "wrap up" at the end of the day for the analyst's report. It needs Node.js 20 or newer and some setup of your own first; its one option, the logs folder, is asked when you enable puppet-master. How-to: [Run background workers](../use/run-background-workers.md).

> /puppet-master:puppet-master

It reads these environment variables, all optional:

| Variable | What it sets |
| --- | --- |
| `PUPPET_CONTEXT_WINDOW` | Your sessions' context window, in tokens, when Claude can't learn it |
| `PUPPET_COMPACT_AT` | The size, in tokens, at which your sessions auto-compact. Without it, Claude uses the smallest one it has seen |
| `PUPPET_DAY_START_HOUR` | The hour a day starts in the analyst's logs, from `0` to `23`. Default `5` |
| `PUPPET_LOGS_DIR` | The logs folder, ahead of the plugin option |
| `PUPPET_CLAUDE_BIN` | The full path of the `claude` executable |

To run a second master on the same machine, tell it to run with a group, such as your project's folder name. It then keeps its own list of sessions, its own logs folder and its own proposal ids.

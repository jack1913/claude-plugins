# Commands

Everything puppet-master adds to Claude Code. "You only" means it runs only when you type it.

## Commands and skills

| Command | Starts | What it does | Arguments |
| --- | --- | --- | --- |
| `/puppet-master:puppet-master` | you only | Hands jobs to your open sessions, and to background workers when none is free, one job each; compacts only between tasks; an analyst session proposes improvements at the end of the day | — |

## puppet-master

Type the command in the session you want as the master. It takes no arguments: it asks which open sessions it may use, then you say each job, its folder and whether it may commit. Say "wrap up" at the end of the day for the analyst's report. It needs Node.js 20 or newer and some setup of your own first; its options, the logs folder and `self_compact`, are listed under [Plugin options](#plugin-options). How-to: [Run background workers](../use/run-background-workers.md).

> /puppet-master:puppet-master

It reads these environment variables, all optional:

| Variable | What it sets |
| --- | --- |
| `PUPPET_CONTEXT_WINDOW` | Your sessions' context window, in tokens, when it is not 1,000,000 |
| `PUPPET_DAY_START_HOUR` | The hour a day starts in the analyst's logs, from `0` to `23`. Default `5` |
| `PUPPET_LOGS_DIR` | The logs folder, ahead of the plugin option |
| `PUPPET_CLAUDE_BIN` | The full path of the `claude` executable |
| `PUPPET_MOD_DIR` | The folder the master and the mod share, instead of `~/.claude/puppet-master/mod` |

To run a second master on the same machine, tell it to run with a group, such as your project's folder name. It then keeps its own list of sessions, its own logs folder and its own proposal ids.

## Plugin options

Set these in the plugin's options. `/config` lists them too.

| Option | What it sets |
| --- | --- |
| `puppet_logs_dir` | The analyst's logs folder. Empty uses the plugin's data folder |
| `self_compact` | `ask` (the default): a window you open asks once at start whether the master may compact it and switch its model and effort, and does nothing without a yes. `on`: the master may do so in every session. `off`: never, whatever the master asks |

## Helper commands for compacting, switching and clearing

Claude runs these for you. They work only on a session whose mod is on.

| Command | What it does |
| --- | --- |
| `compact <session> <focus>` | The session's own mod compacts it when it is idle, keeping what the focus names |
| `switch <session> --tier creative\|mechanical` | The session's own mod sends its requests on the tier's model and effort, that session only, from its next request on. `--model <m> --effort <e>` names them instead; `--reset` goes back to the model it started with. Its status line keeps the starting model; the mod's own line under the prompt names the switch |
| `clear <worker>` | The mod clears a worker whose job is finished, then Claude keeps it as a clean session. Refused for the master, the analyst and a session with an open job |
| `spawn … --self-compact`, `adopt … --self-compact` | Switch a worker's or a window's mod on. Claude passes it only after you said yes |

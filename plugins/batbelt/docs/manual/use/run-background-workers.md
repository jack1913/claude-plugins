# Run background workers

Let one Claude session start and look after other Claude sessions that work in the background, one job each. You stop
opening windows and typing `/compact` into them. Claude only does the housekeeping; every decision stays yours.

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

## Start a worker

1. In the session you want as the master, say what the job is:

   > Start a background worker that fixes the flaky login test in this repository. It may commit, but not push.

   Or type the command first:

   > /batbelt:puppet-master

2. Claude writes the worker's brief and starts it. You see one line, like
   `spawned login-fix id=<id> in <folder>`.
3. When the worker has a question, Claude asks you, one question at a time, with a suggested answer.

One worker edits one folder at a time. For a second job in the same repository, use a second clone.

## Keep it small

Claude measures each worker's context, and compacts it only between tasks:

- An idle worker at 30% of its context or more, with work left, is compacted and restarted.
- A busy worker at 50% or more is asked to stop at its next task boundary first.
- Before compacting a worker above 50%, Claude tells you its size and that a compaction can cost close to a dollar.

Ask "how are my workers?" to see each one's size and state.

## Check it worked

When a job is done, Claude closes the worker and shows a line like
`closed login-fix (resume: cd "<folder>" && claude --resume <session id>)`. The conversation is kept: run that command
to open it again.

## If something goes wrong

| You see | Do this |
| --- | --- |
| `puppet: no context window` | Tell Claude the window size your status line shows, or set `PUPPET_CONTEXT_WINDOW` to it (in tokens) |
| `puppet: cannot run claude` | Set `PUPPET_CLAUDE_BIN` to the full path of the `claude` executable |
| `already editing` | Another worker works in that folder. Wait for it to finish, close it, or use a second clone |
| `is stopped and NOT compacted` | Run the restart command the message ends with |
| A worker can't edit files | Check the `bgIsolation` line in your `~/.claude/settings.json` |

More: [Troubleshooting](../reference/troubleshooting.md).

## Related

- [Commands](../reference/commands.md)
- [Grill a plan](grill-a-plan.md)

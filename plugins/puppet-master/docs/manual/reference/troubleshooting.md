# Troubleshooting

Find what you see, then do what's next to it.

| You see | Do this |
| --- | --- |
| `/puppet-master:puppet-master` doesn't start when you ask in words | Type the command. It only runs when typed |
| `puppet: no context window` | Tell Claude the window size your status line shows, or set `PUPPET_CONTEXT_WINDOW` to it, in tokens |
| `puppet: cannot run claude` | Set `PUPPET_CLAUDE_BIN` to the full path of the `claude` executable. On Windows the npm `claude.cmd` shim can't be started |
| `one job per context` or `no clean session` | That session already did a job, or none of yours is free in that folder. Claude can reuse a finished session under 30% of its context window, or you clear one and tell Claude, or Claude starts a background worker |
| `changed (new session id …)` or `has a new session id` | That window was cleared or restarted. Tell Claude whether it is clean now |
| A resumed master session's commands fail | Tell it to run its start-up steps again: list the sessions, adopt itself and any session shown as `changed`, then measure. The helper refuses a session with a new session id until it is adopted again |
| `is already editing … unless both jobs pass --scope` | Two jobs share that folder only when each names the folders it writes and only one runs git. Otherwise use a second checkout, or wait |
| `MISMATCH … tier …` | That session runs a different model or effort than the job needs. Let Claude start a worker on the right tier, or keep the window: run `/model` and press `s` on the row Claude names, then `/effort` and press `s` at the level. `s` changes that session only; a typed `/model <name>` saves your default |
| `spawn: name a --tier or --effort` | The master started a worker without saying how strong it should be. Tell it the job's tier: `creative` or `mechanical` |
| `WARN near compaction` | That session is near the size where it auto-compacts. Let it finish its task |
| `DONE? run finish` on a session's line | That session reported its job done. Tell the master to close the job |
| `<name> is closed (resume: …)` | That session was closed. Run the resume command if you want it back, then tell Claude to adopt it |
| `… belongs to group "<group>"; pass --group <group>` | That proposal id is another master's. Decide it in that master's session, or tell this one to use that group |
| `PUPPET_DAY_START_HOUR must be a whole hour from 0 to 23` | Set it to a whole hour, such as `5`, or remove it |
| `just compacted (auto); its size is known after its next turn` | Wait for that session's next answer, then ask again |
| `no mod heartbeat` | The plugin isn't loaded in that session. Run `/reload-plugins` there, or paste the line the message ends with. Claude Code must be 2.1.287 or newer |
| `loaded but not switched on` or `mod off (mode ask)` on a session's line | You didn't switch the mod on in that session. Say yes in its window, or tell Claude to switch it on |
| `self_compact off, the user's veto` | You set `self_compact` to `off`. Set it back to `ask` or `on` in the plugin's options |
| `mod stale` on a session's line | The mod stopped in that session. Run `/reload-plugins` there |
| `was NOT compacted` or `was NOT cleared` | The message says why, such as `busy` or `stale`, and ends with the line to paste. Try again when the session is idle |
| `is waiting on a dialog` | That session is waiting for you to answer a question in its own window. Answer it first |
| A logs folder named `${user_config…}` | The helper never creates one. If you see it, delete it and set `PUPPET_LOGS_DIR` to the folder you want |
| A background worker can't edit files | Add `"worktree": { "bgIsolation": "none" }` to your own `~/.claude/settings.json`. See [Run background workers](../use/run-background-workers.md) |

Still stuck? Open an issue at [jack1913/claude-plugins](https://github.com/jack1913/claude-plugins/issues) and say what you typed and what you saw.

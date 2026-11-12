# Troubleshooting

Find what you see, then do what's next to it.

| You see | Do this |
| --- | --- |
| `/puppet-master:puppet-master` doesn't start when you ask in words | Type the command. It only runs when typed |
| `puppet: cannot run claude` | Set `PUPPET_CLAUDE_BIN` to the full path of the `claude` executable. On Windows the npm `claude.cmd` shim can't be started |
| `one job per context` or `no clean session` | That session already did a job, or none of yours is free in that folder. Claude can reuse a finished session under 30% of its context window, or you clear one and tell Claude, or Claude starts a background worker |
| `changed (new session id …)` or `has a new session id` | That window was cleared or restarted. Tell Claude whether it is clean now |
| A resumed master session's commands fail | Tell it to run its start-up steps again: list the sessions, adopt itself and any session shown as `changed`, then measure. The helper refuses a session with a new session id until it is adopted again |
| `is already editing … unless both jobs pass --scope` | Two jobs share that folder only when each names the folders it writes and only one runs git. Otherwise use a second checkout, wait, or name a folder outside the repository (a job that writes only there does not count) |
| `MISMATCH … tier …` | That session runs a different model or effort than the job needs. Where its mod is on, Claude switches it for that session only. Elsewhere, let Claude start a worker on the right tier, or keep the window: run `/model` and press `s` on the row Claude names, then `/effort` and press `s` at the level. `s` changes that session only; a typed `/model <name>` saves your default |
| The status line, or the session itself, names the old model after a switch | Expected: both keep the model the session started with; the line `puppet-master: switched to …` under the prompt names the switch. Ask "how are my sessions?": the model column shows the one in use after its next answer |
| `does not end with the template's last line` | The master wrote a worker's brief without the template's lines. Tell it to build the brief from `worker-brief.md`, keeping its last line |
| `spawn: name a --tier or --effort` | The master started a worker without saying how strong it should be. Tell it the job's tier: `creative` or `mechanical` |
| `dead` in a background worker's line | The worker's process is gone (it shows no process id in the session list). Tell Claude to close it: it removes the worker without stopping it first |
| `could not be stopped … run close <name> again in a minute` | The background service was restarting. Wait a minute and tell Claude to close that worker again; its record is kept meanwhile |
| `stopped but NOT removed … run close <name> again in a minute, or once a background worker is running` | `claude rm` kept failing with "the background service may be restarting". Tell Claude to close it again in a minute, or once a background worker is running; the worker stays stopped and resumable meanwhile |
| `DONE? run finish` on a session's line | That session reported its job done. Tell the master to close the job |
| `<name> is closed (resume: …)` | That session was closed. Run the resume command if you want it back, then tell Claude to adopt it |
| `… belongs to group "<group>"; pass --group <group>` | That proposal id is another master's. Decide it in that master's session, or tell this one to use that group |
| `PUPPET_DAY_START_HOUR must be a whole hour from 0 to 23` | Set it to a whole hour, such as `5`, or remove it |
| `just compacted (auto); its size is known after its next turn` | Wait for that session's next answer, then ask again |
| `no mod heartbeat` | The plugin isn't loaded in that session. Run `/reload-plugins` there, or paste the line the message ends with. Claude Code must be 2.1.287 or newer |
| `loaded but not switched on` or `mod off (mode ask)` on a session's line | You didn't switch the mod on in that session. Say yes in its window, or tell Claude to switch it on |
| `self_compact off, the user's veto` | You set `self_compact` to `off`. Set it back to `ask` or `on` in the plugin's options |
| `mod stale` on a session's line | The mod stopped in that session. Run `/reload-plugins` there |
| `was NOT compacted`, `was NOT cleared` or `was NOT switched` | The message says why, such as `busy` or `stale`, and ends with the line to paste. Try again when the session is idle |
| `is waiting on a dialog` | That session is waiting for you to answer a question in its own window. Answer it first |
| A logs folder named `${user_config…}` | The helper never creates one. If you see it, delete it and set `PUPPET_LOGS_DIR` to the folder you want |
| A background worker can't edit files | Add `"worktree": { "bgIsolation": "none" }` to your own `~/.claude/settings.json`. See [Run background workers](../use/run-background-workers.md) |

Still stuck? Open an issue at [jack1913/claude-plugins](https://github.com/jack1913/claude-plugins/issues) and say what you typed and what you saw.

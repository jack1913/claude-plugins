# Troubleshooting

Find what you see, then do what's next to it.

| You see | Do this |
| --- | --- |
| `/batbelt:onboard-repo` doesn't start when you ask in words | Type the command. It only runs when typed |
| `/batbelt:grill-me` doesn't start when you type it | Run `/reload-plugins`, then try again. Still missing? See [Install a plugin](../../../../../docs/manual/getting-started/install-a-plugin.md) |
| You can't find `/batbelt:grilling` | It was removed. Type `/batbelt:grill-me`, or say "grill me" |
| `prove-it` stops with `Research status: BLOCKED` | It needs a way to fetch pages, plus search or URLs from you. Add the tool or paste the URLs, then run it again: it picks up where it stopped |
| `puppet: no context window` from `puppet-master` | Tell Claude the window size your status line shows, or set `PUPPET_CONTEXT_WINDOW` to it, in tokens |
| `puppet: cannot run claude` from `puppet-master` | Set `PUPPET_CLAUDE_BIN` to the full path of the `claude` executable. On Windows the npm `claude.cmd` shim can't be started |
| `one job per context` or `no clean session` from `puppet-master` | That session already did a job, or none of yours is free in that folder. Claude can reuse a finished session under 30% of its compaction point, or you clear one and tell Claude, or Claude starts a background worker |
| `changed (new session id …)` or `has a new session id` from `puppet-master` | That window was cleared or restarted. Tell Claude whether it is clean now |
| A resumed `puppet-master` session's commands fail | Tell it to run its start-up steps again: list the sessions, adopt itself and any session shown as `changed`, then measure. The helper refuses a session with a new session id until it is adopted again |
| `is already editing … unless both jobs pass --scope` from `puppet-master` | Two jobs share that folder only when each names the folders it writes and only one runs git. Otherwise use a second checkout, or wait |
| `MISMATCH … tier …` from `puppet-master` | That session runs a different model or effort than the job needs. Paste the `/model` and `/effort` lines Claude gives you into that window |
| `WARN near compaction` from `puppet-master` | That session is near the size where it auto-compacts. Let it finish its task, then compact or clear it as Claude suggests |
| `<name> is closed (resume: …)` from `puppet-master` | That session was closed. Run the resume command if you want it back, then tell Claude to adopt it |
| `PUPPET_DAY_START_HOUR must be a whole hour from 0 to 23` | Set it to a whole hour, such as `5`, or remove it |
| `just compacted (auto); its size is known after its next turn` from `puppet-master` | Wait for that session's next answer, then ask again |
| A `puppet-master` logs folder named `${user_config…}` | The helper never creates one. If you see it, delete it and set `PUPPET_LOGS_DIR` to the folder you want |
| A background worker can't edit files | Add `"worktree": { "bgIsolation": "none" }` to your own `~/.claude/settings.json`. See [Run background workers](../use/run-background-workers.md) |
| New skills don't show up after onboarding | Restart Claude Code: `claude --continue` |
| `RUN STATE ERROR` from `onboard-repo` | Its progress file (the newest `.onboard-repo-retired/*/run.json`) is damaged, so it stops rather than overwrite it. Fix the file or move it aside, then run `/batbelt:onboard-repo` again. Don't delete the folder: it also holds your backups |

Still stuck? Open an issue at [jack1913/claude-plugins](https://github.com/jack1913/claude-plugins/issues) and say what you typed and what you saw.

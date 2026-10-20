# Troubleshooting

Find what you see, then do what's next to it.

| You see | Do this |
| --- | --- |
| `/batbelt:onboard-repo` doesn't start when you ask in words | Type the command. It only runs when typed |
| `/batbelt:grill-me` doesn't start when you type it | Run `/reload-plugins`, then try again. Still missing? See [Install a plugin](../../../../../docs/manual/getting-started/install-a-plugin.md) |
| You can't find `/batbelt:grilling` | It was removed. Type `/batbelt:grill-me`, or say "grill me" |
| `prove-it` stops with `Research status: BLOCKED` | It needs a way to fetch pages, plus search or URLs from you. Add the tool or paste the URLs, then run it again: it picks up where it stopped |
| New skills don't show up after onboarding | Restart Claude Code: `claude --continue` |
| `RUN STATE ERROR` from `onboard-repo` | Its progress file (the newest `.onboard-repo-retired/*/run.json`) is damaged, so it stops rather than overwrite it. Fix the file or move it aside, then run `/batbelt:onboard-repo` again. Don't delete the folder: it also holds your backups |

Still stuck? Open an issue at [jack1913/claude-plugins](https://github.com/jack1913/claude-plugins/issues) and say what you typed and what you saw.

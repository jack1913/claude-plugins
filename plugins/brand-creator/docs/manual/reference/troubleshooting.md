# Troubleshooting

What you see, and what to do.

| You see | Do this |
| --- | --- |
| A tool stops with code 3 ("cannot run") | Run `/brand-creator:setup`, or the install command the message names. `brand-creator prereq --for quick` lists what's missing; use `standard`, `full`, `apple`, `print`, `names` or `adoption` instead of `quick` for those |
| `brand-creator: command not found` | Check the plugin is enabled (`/plugin`) and restart Claude Code. Meanwhile the skills switch to the full path |
| A permission prompt on every call | Add the rule on the [Permissions](permissions.md) page |
| Shots "not verified" | Chromium is missing or can't start. Run `/brand-creator:setup`. On Linux, install the libraries the message names. The board is still written |
| "no renderer opt-in is recorded" (Linux, Windows) | Answer the renderer question: resvg for an SVG logo, Pillow for a PNG |
| `emit apple` needs macOS with Xcode | Apple packs are built on a Mac with Xcode. Everything else works on Linux too. Windows is untested |
| A write to an earlier round or `history/` is blocked | That's the safety lock on finished rounds. Work in the latest round, or start a new one |
| A Python tool won't start | Put a `python3` 3.10 or newer on PATH. The message lists every interpreter it tried |

## Related

- [Platform support](platform-support.md)
- [Claude Code versions](claude-code-versions.md)

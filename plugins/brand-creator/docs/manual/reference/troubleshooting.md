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
| A page check fails on a colour and names it | The page paints a colour that is not one of your colours for that theme. The row gives the nearest brand colour. Use the colour from your tokens, or change the token if the brand changed. Steps: [Check a page against your brand](../use/check-a-page.md) |
| A page check says "page-check runs offline" and stops | The address is not on your computer. Only `localhost`, `127.0.0.1` and `[::1]` are checked. Build the site here and give its folder, or serve it locally |
| A page check shows a font row "not verified" | The check could not tell which font the browser drew, for example a system font this computer does not have. Load the font with the page, then check again |

## Related

- [Platform support](platform-support.md)
- [Claude Code versions](claude-code-versions.md)

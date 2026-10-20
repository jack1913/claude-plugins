# Platform support

Which systems brand-creator works on, and what to expect off a Mac.

| | macOS | Linux | Windows |
| --- | --- | --- | --- |
| Status | Full support, tested | Verified in a container (Debian 13), not on a desktop | Untested |
| Quick and Standard | Yes | Yes | Untested |
| Full | Yes (Apple packs need Xcode) | Everything except the Apple packs | Untested, and no Apple packs |

## Off macOS

- **Renderer choice.** The small-size check asks you once which renderer to use (`--renderer=resvg` or
  `--renderer=pillow`). It remembers your answer in `BRAND-STATE.md`. Use resvg for an SVG logo and Pillow for a PNG.
- **Your project's asset script.** `tools/finish.sh` needs two settings too, or its size checks and the Tauri icon stop
  with "cannot run": `DOWNSCALE_RENDERER` (resvg for an SVG logo, pillow for a PNG) and `ICNS_RENDERER=pillow`.
- **Apple packs.** `emit apple` stops with "needs macOS with Xcode". Everything else works.

## Linux

The tested setup is Debian 13 with Python 3.13, Node 24, uv, resvg, ImageMagick, Ghostscript, poppler, ripgrep and
potrace. Other distributions may need `cargo install resvg`. On a minimal server, Chromium may need system libraries; the
error names them.

## Windows

Never run. The safety hook needs `python3`. Without it, Claude Code 2.1.295 and later block the call with a notice. On
older versions, or with the Microsoft Store alias, the hook does nothing, and only the history check in
`/brand-creator:check` protects locked rounds. More: [What it never does](what-it-never-does.md).

## Related

- [Choose a tier](../getting-started/choose-a-tier.md): what each tier needs installed
- [Troubleshooting](troubleshooting.md)

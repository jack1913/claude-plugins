# Setup prerequisites (the user's, never written by you)

Moved out of SKILL.md to keep its body under the docs standard's 500 lines. SKILL.md points here.

- `worktree.bgIsolation: "none"` in the user's own `settings.json`, or a background worker cannot
  edit files without a worktree.
- A worker's cwd must be a folder the user has trusted (they ran `claude` there once).
- `crossSessionInbound: accept` only if a session runs in a mode that holds messages.
- The logs folder is the plugin option `puppet_logs_dir`, asked when the plugin is enabled. Left
  empty, the logs go to the plugin's data folder. `PUPPET_LOGS_DIR` overrides both, for a copy
  installed by hand.
- To run more than one master on one machine, each runs with its own `--group` (On start, step
  4): one roster holds one master and one analyst. The checkout lock sees only its own group's
  roster, so never send a job into a checkout another group works in; ask the user which group
  owns it.
- The mod (`compact`, `clear`) needs Claude Code 2.1.287 or newer, and a window opened before the plugin
  was installed or updated needs `/reload-plugins`. It does not load under `--safe-mode`, `--bare` or
  `"disableAllHooks": true`. The plugin option `self_compact` is `ask` by default: an interactive window
  asks once at start and does nothing without a yes; `on` and `off` skip the question, and `off` also
  overrides your `--self-compact`. The helper and the mod meet in `PUPPET_MOD_DIR`, else
  `<config dir>/puppet-master/mod`.
- The helper runs `claude` without a shell, so on Windows an npm-installed `claude.cmd` shim cannot
  be launched. Use the native `claude` executable, or set `PUPPET_CLAUDE_BIN` to its full path.
- Typing a `claude -p ... "/compact <focus>"` yourself from Git Bash needs `MSYS_NO_PATHCONV=1`, or
  the `/compact` argument is rewritten into a Windows path and runs as an ordinary turn with no
  compaction. `cycle` runs no shell, so it is immune.
- The CLI behaviour the helper relies on (`--bg`, `agents --json`, `stop`, `rm`, `-p --resume`) was
  verified on Claude Code 2.1.310; `--bg`, `agents --json`, `stop` and `rm` again on 2.1.312. If a
  call fails on another version, report the helper's message to the user; don't work around it.

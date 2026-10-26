# puppet-master

One interactive Claude Code session, the **master**, runs background worker sessions the way a person would by hand:
it starts a worker for a job, briefs it, relays its questions, measures its context, compacts it at a clean task
boundary and closes it when the job is done. The master does housekeeping only; the user makes every decision.

## Files

- [`skills/puppet-master/SKILL.md`](../../skills/puppet-master/SKILL.md) holds the master's rules, the relay protocol
  and the helper reference.
- [`worker-brief.md`](../../skills/puppet-master/worker-brief.md) is the brief every worker gets, with the placeholders
  `{{master_name}}`, `{{job}}` and `{{commit_rules}}`.
- [`scripts/puppet.mjs`](../../skills/puppet-master/scripts/puppet.mjs) is the helper: `measure`, `list`, `spawn`,
  `cycle` and `close`. Node built-ins only, no npm and no `package.json`.

## Decisions the rules encode

- **Housekeeping only.** On its own the master may start, stop, remove, compact and restart workers, logging each in
  one line. Commits (unless the user pre-authorized them for the job), pushes, PR posts, approvals, live or external
  writes and anything destructive go to the user.
- **One job per worker context.** A new job gets a fresh worker; a worker that did other work is never reused.
- **One editing worker per checkout.** Parallel jobs in one repository use separate checkouts. `spawn` refuses a second
  live worker whose cwd resolves (through `git rev-parse --show-toplevel`) to the same checkout. A folder outside any
  repository is its own checkout; any other git failure is an error, because it would weaken the lock.
- **No git worktrees.** Nothing calls `EnterWorktree` or `git worktree`, and `claude rm` never gets
  `--discard-unpushed` or `--force-remove-worktree`: if it refuses, the user decides.
- **Compaction is measured and happens at task boundaries only.** Compact an idle worker at 30% or more of its window
  when the job continues; at 50% or more, ask a working worker to stop at its next boundary; never compact mid-task;
  a finished job is closed, never compacted. An automatic threshold that can fire mid-task is not the mechanism.
- **Measured, not reported.** A worker's own estimate of its size is a prompt to measure, never a reason to act:
  workers have claimed to be full at about a fifth of their window.
- **No permission laundering.** A relayed answer is never the user's approval of a permission prompt in a worker, and
  the master never asks a worker to do what the user's settings denied. A worker asking the user to confirm in its own
  window is correct.

## Verified mechanics

Verified on Windows 10 with Claude Code 2.1.310. Each step is what the helper calls.

| Step | How | Result |
| --- | --- | --- |
| Start | `claude --bg --name <worker> "<brief>"`, in a trusted folder | Works; an untrusted folder refuses until the user runs `claude` there once. Stdout: `backgrounded · <id> · <name>` plus hint lines |
| List | `claude agents --json` (or the `ListAgents` tool) | Background workers with `kind`, `id`, `sessionId`, `cwd`, `state` and `status` |
| States | `state` in the listing | `working` (`status` `busy`), then `done` (`status` `idle`); `blocked` while waiting on a prompt. A stopped worker drops out of the listing |
| Message | `SendMessage`, both ways | Delivered, no hold |
| Edit files | `worktree.bgIsolation: "none"` in the user's `settings.json` | Without it a background worker cannot edit until `EnterWorktree`. With it, a worker wrote into the main checkout, and no worktree appeared |
| Compact | `claude stop <id>`, then `claude -p --resume <sessionId> --output-format json "/compact <focus>"` | The transcript gains a `compact_boundary`; the JSON result carries `modelUsage.<model>.contextWindow` |
| Restart | `claude --bg --resume <sessionId> "<next brief>"`, from the worker's cwd | Resumes with its saved name and model, and remembers its state |
| Close | `claude stop <id>`, then `claude rm <id>` | Works; the transcript stays resumable with `claude --resume <sessionId>` |
| Measure | Last main-thread assistant `usage` in `<config dir>/projects/<project>/<sessionId>.jsonl`: input + cache read + cache creation, over the context window | Matches the status line's percentage |

Things that shaped the helper:

- A running session refuses a `/`-prompt sent through `claude -p --resume`, so `cycle` stops the worker first.
- From Git Bash, MSYS path conversion rewrites a `/compact` argument into a Windows path unless `MSYS_NO_PATHCONV=1` is
  set. The CLI then runs an ordinary turn, exits 0 with `is_error: false`, and writes no `compact_boundary`. So `cycle`
  judges success by a new boundary in the transcript, never by the exit code. The helper itself runs no shell.
- A compaction re-reads the whole context. One of a 77k-token session cost about $0.88, which is why the skill tells
  the user the size and cost before cycling a worker above 50%.
- The helper runs every child process with `spawnSync` and `shell: false`, so on Windows an npm `claude.cmd` shim cannot
  be launched; `PUPPET_CLAUDE_BIN` names the native executable.

## Measuring

- The worker's size is the last non-sidechain assistant `usage`, unless a `compact_boundary` came after it (a worker
  measured right after `cycle`); then it is the boundary's `compactMetadata.postTokens`.
- Subagent (`isSidechain: true`) entries are ignored: they are not the worker's context.
- Only the last line of a transcript may be unparseable (the session may be mid-write). A bad line anywhere else is an
  error.
- The window comes from `--window <tokens>`, else the window the worker's last `cycle` recorded, else
  `PUPPET_CONTEXT_WINDOW`. With none of them the helper exits 1; it never guesses a default.

## The registry

`<config dir>/puppet-master/workers.json` (`PUPPET_STATE` overrides it; the config dir is `CLAUDE_CONFIG_DIR` or
`~/.claude`) maps each worker name to its `id`, `sessionId`, `cwd`, `checkout` and, after a `cycle`, its `window`.
It is written atomically (a temp file, then a rename). `spawn` prunes records of workers that are no longer listed,
printing how to resume each; `list` reports them as `gone` with the resume command, then drops them. The transcripts
stay, so nothing is lost.

## Failure handling

Every failure prints `puppet: <message>` on stderr and exits non-zero: 2 for a usage error, 1 for an operational
failure. There is no silent fallback.

- A name that matches two sessions (for example the user's own window and a worker) is refused as ambiguous, with the
  ids listed.
- `cycle` and `close` refuse a session that is not `kind` `background`: a window the user opened has no supported
  remote stop.
- `cycle` refuses a worker that is not idle. If it fails after stopping the worker, the message says whether the worker
  was compacted and prints the `cd "<cwd>" && claude --bg --resume <sessionId>` that restarts it.
- `close` keeps the registry record when `claude rm` fails, and prints the resume command.

## Setup that stays the user's

The skill documents these and never applies them:

- `worktree.bgIsolation: "none"` in the user's own `settings.json`.
- A trusted folder for each worker's cwd.
- `crossSessionInbound: accept`, only if a worker runs in a mode that holds messages.

## Tests

`tests/test_puppet_master.py` runs `node --test` over `tests/puppet_master/*.test.mjs`. A fake `deps.run` answers every
`claude` and `git` call, so no test starts a session. The fixtures in `tests/puppet_master/fixtures/` are sanitized
captures of a real probe worker. The suite covers transcript measurement (a partial trailing line, sidechain usage, a
compact boundary after the last usage), window resolution, the registry, `spawn`'s one-editor lock, `cycle`'s verified
compaction and its stopped-worker messages, `close` never passing a discard flag, and the `SKILL.md` text. A missing
`node` (20 or newer) fails the test, never skips it.

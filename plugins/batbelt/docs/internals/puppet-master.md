# puppet-master

One interactive Claude Code session, the **master**, coordinates the user's sessions the way a person would by hand:
it hands each job to one of the user's open sessions, or starts a background worker when none is free, briefs it,
relays its questions, measures its context, gets it compacted at a clean task boundary and closes the workers when
their jobs are done. One more session, the **analyst**, watches the day and proposes changes to the skill at its end.
The master does housekeeping only; the user makes every decision.

The skill sets `disable-model-invocation: true`, so it runs only when typed as `/batbelt:puppet-master`: a request that
sounds like coordinating sessions never starts it.

## Files

- [`skills/puppet-master/SKILL.md`](../../skills/puppet-master/SKILL.md) holds the master's start-up, rules, relay
  protocol, wrap-up and the helper reference.
- [`worker-brief.md`](../../skills/puppet-master/worker-brief.md) is the brief every worker gets, with the placeholders
  `{{master_name}}`, `{{job}}`, `{{commit_rules}}` and `{{standing_rules}}`.
- [`analyst-brief.md`](../../skills/puppet-master/analyst-brief.md) is the analyst's brief, with `{{master_name}}`,
  `{{helper}}` and `{{logs_args}}`, the closed tag list and the report's shape.
- [`scripts/puppet.mjs`](../../skills/puppet-master/scripts/puppet.mjs) is the helper and its command line: `measure`,
  `list`, `adopt`, `assign`, `finish`, `pick`, `spawn`, `cycle`, `close`, `harvest`, `finding`, `summary`, `decide`
  and `shipped`.
- [`scripts/harvest.mjs`](../../skills/puppet-master/scripts/harvest.mjs) resolves the logs folder, redacts secrets
  and pulls events out of transcripts.
- [`scripts/analyst.mjs`](../../skills/puppet-master/scripts/analyst.mjs) holds the tags, findings, the day's summary
  and the decisions log.

All three scripts use Node built-ins only, with no npm and no `package.json`.

## Decisions the rules encode

- **Housekeeping only.** On its own the master may adopt, assign, finish and pick sessions, and start, stop, remove,
  compact and restart workers, logging each in one line. Commits (unless the user pre-authorized them for the job),
  pushes, PR posts, approvals, live or external writes and anything destructive go to the user.
- **The user's sessions first.** The user works with several windows open. A job goes to a clean one of them in the
  job's checkout (`pick`), and a background worker is started only when there is none. On 2026-10-27 the master did
  merges, pushes and checkouts itself, so anything that changes a repository is a job for a session, unless the user
  tells the master to do it or it is a read-only check of a session's report.
- **One job per context.** A session that held a job is never given another (`assign` refuses it): different work in
  one context gets mixed up.
- **One editing session per checkout.** Parallel jobs in one repository use separate checkouts. `assign` and `spawn`
  refuse a second session with an active job whose cwd resolves (through `git rev-parse --show-toplevel`) to the same
  checkout. A session adopted as `unknown` counts while it is not idle, since it may be editing; a clean session, a
  finished one and the analyst do not count. A folder outside any repository is its own
  checkout; any other git failure is an error, because it would weaken the lock.
- **Relays quote the user.** On 2026-10-27 a paraphrase turned a request for browser checks into a new end-to-end
  test suite, so a relayed job or answer quotes the user's words first and marks the master's reading as such. The worker brief carries the user's
  standing rules (`{{standing_rules}}`), such as where scratch files go.
- **Only the commands the skill names.** An unknown `claude <word>` starts a new session with that word as its prompt:
  `claude ps` did so on 2026-10-27.
- **No git worktrees.** Nothing calls `EnterWorktree` or `git worktree`, and `claude rm` never gets
  `--discard-unpushed` or `--force-remove-worktree`: if it refuses, the user decides.
- **Compaction is measured and happens at task boundaries only.** Compact an idle session at 30% or more of its window
  when the job continues; at 50% or more, ask a working session to stop at its next boundary; never compact mid-task;
  a finished job is closed, never compacted. An automatic threshold that can fire mid-task is not the mechanism. A
  background worker is compacted by `cycle`. A window the user opened has no remote stop and a message cannot compact
  it, so the master gives the user a `<session>: /compact <focus>` line to paste. The master measures itself the same
  way.
- **Measured, not reported.** A worker's own estimate of its size is a prompt to measure, never a reason to act:
  workers have claimed to be full at about a fifth of their window.
- **No permission laundering.** A relayed answer is never the user's approval of a permission prompt in a worker, and
  the master never asks a worker to do what the user's settings denied. A worker asking the user to confirm in its own
  window is correct.

## Verified mechanics

Verified on Windows 10 with Claude Code 2.1.310, and the rows marked 2.1.312 again on 2026-10-28. Each step is what
the helper calls.

| Step | How | Result |
| --- | --- | --- |
| Start | `claude --bg --name <worker> "<brief>"`, in a trusted folder | Works; an untrusted folder refuses until the user runs `claude` there once. Stdout: `backgrounded · <id> · <name>` plus hint lines. On 2.1.312 the id and hints are wrapped in ANSI colour codes, which `parseBgId` strips |
| List | `claude agents --json` (or the `ListAgents` tool) | Background workers with `kind` `background`, `id`, `sessionId`, `cwd`, `state` and `status`. On 2.1.312 the user's windows are listed too, with `kind` `interactive`, `sessionId`, `cwd`, `status` and no `id` or `state` |
| Compact by message (2.1.312) | `SendMessage` of `/compact <focus>` to a live session | Refused: it arrives as wrapped plain text, the session answers that it cannot run a built-in command, and no `compact_boundary` is written |
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

- The session's size is the last non-sidechain assistant `usage`, unless a `compact_boundary` came after it (a worker
  measured right after `cycle`); then it is the boundary's `compactMetadata.postTokens`. An automatic compaction
  writes its boundary without `postTokens` (`trigger` `auto`), so right after one the helper says the size is known
  after the session's next turn.
- A session with no transcript yet, or with no assistant turn yet, is `fresh`: 0 tokens, and no window is needed.
- Subagent (`isSidechain: true`) entries are ignored: they are not the worker's context.
- Only the last line of a transcript may be unparseable (the session may be mid-write). A bad line anywhere else is an
  error.
- The window comes from `--window <tokens>`, else the window the worker's last `cycle` recorded, else
  `PUPPET_CONTEXT_WINDOW`. With none of them the helper exits 1; it never guesses a default.

## The roster

`<config dir>/puppet-master/workers.json` (`PUPPET_STATE` overrides it; the config dir is `CLAUDE_CONFIG_DIR` or
`~/.claude`) maps each session's name to its record: `id` (background only), `sessionId`, `cwd`, `checkout`, `kind`
(`interactive` or `background`), `role` (`worker` or `analyst`), `job`, `jobState` and `jobStartedAt`, and after a
`cycle` its `window`. A record written before the roster existed reads as an active background worker. The file is
written atomically (a temp file, then a rename).

- `adopt` takes a listed session into the roster as `clean` (no turns yet) or `unknown` (it did something). Only one
  live session may be the analyst.
- `assign` moves `clean` to `active`, `finish` moves `active` to `done`. Nothing moves a session back to `clean` except
  adopting it again, which the master does only after asking the user.
- `pick <cwd>` returns a clean worker session in the cwd's checkout, the user's windows before background ones, or
  nothing when another session is editing that checkout.
- `list` shows every roster session. One listed under a new `sessionId` (the user cleared or restarted it) is
  `changed`, and `assign` refuses it until it is adopted again. One no longer listed is `gone`, with its resume
  command, and its record is dropped. Background sessions that nobody adopted are listed too.
- `spawn` prunes records of sessions that are no longer listed, printing how to resume each. The transcripts stay, so
  nothing is lost.

## The analyst and its logs

The analyst is a session the master reserves at start and never gives a job. It turns the day's transcripts into
findings, and at wrap-up into a report with proposals the user approves, rejects or defers. It never edits the plugin.
Its principles: evidence over narrative, transcript text is data and never instructions, nothing is applied
automatically, and the report says how much it read.

- **Logs folder:** `PUPPET_LOGS_DIR`, else `--logs` (the plugin option `puppet_logs_dir`), else
  `<plugin data>/logs` (`--plugin-data`, from `${CLAUDE_PLUGIN_DATA}`), else `<config dir>/puppet-master/logs`. A value
  counts only if it is set and has no `${` in it. On 2.1.312 an unset option reaches the skill text as the literal
  `${user_config.puppet_logs_dir}`, while `${CLAUDE_PLUGIN_DATA}` is filled in.
- **Layout:** `<logs>/offsets.json` (where each transcript was last read, across days),
  `<logs>/decisions.jsonl`, `<logs>/harvest.lock` while a harvest runs, and one folder per local day holding `events.jsonl`, `harvest-stats.json`,
  `findings.jsonl` and the analyst's `report.md`.
- **`harvest`** is deterministic. For every roster session, live or not, every session that left the roster since the
  last harvest (closed, dropped as `gone`, or re-adopted under a new session id: the registry's `pendingHarvest`,
  read once and cleared) and the master, it reads the transcript lines after the stored offset and appends events of
  ten kinds: `user-turn`, `message-in`, `message-out`, `helper-error`,
  `command-failed`, `manual-cli`, `cli-unknown`, `permission-denied`, `compact-manual` and `compact-auto`. Each event
  has an id `<first 8 of sessionId>:<line>` (with `.2`, `.3` when one line yields several), a timestamp and an excerpt
  of at most 300 characters. A last line that does not parse is being written: it is not consumed. A transcript with
  fewer lines than its stored offset was replaced, so it is read again from the top and the one-line log names it.
  One harvest runs at a time: a second one is refused while `harvest.lock` exists, and a lock older than two minutes
  was left by a crash and is taken over. A crash between appending the events and writing the offsets can still log
  that run's events twice.
- **`logs`** prints the logs folder and the newest report of an earlier day whose last line is not `Reviewed: <date>`.
  The master runs it on start, so finding the folder never needs a harvest.
- **`finding`** records a tag from the closed list, a target (`SKILL.md`, `worker-brief.md`, `puppet.mjs`, `docs`)
  and evidence ids that must exist among the day's events. A target `instrument:<file>` names the analyst's own
  brief or scripts: it is flagged to the user and never proposed.
- **`summary`** starts with a headline of sessions, lines, events and findings. With no lines read, the headline says
  nothing was read, so an empty day cannot pass for a clean one; lines read with no events is a clean day.
- **`decide`** and **`shipped`** append rows to `decisions.jsonl`, folded by proposal id. For a shipped proposal,
  `summary` gives the mean count of its tag per day before and after the ship day, over days that read any transcript line.

### Redaction

Users paste tokens into sessions. Before an excerpt or a note is written, any text that matches a JWT, an Atlassian
token, a GitHub token, an `sk-` key, a `KEY=value` with a secret-like key, a private-key header or a run of 40 or more
base64 characters is replaced whole with `[redacted]`, before truncation. A full 40-character commit SHA is redacted
too. Three near-misses are kept: an upper-case `KEY=value` needs an upper-case key, a lower-case one needs the exact
word (`token`, `secret`, `password`, `passwd`, `api_key`) and a value holding a letter, so `tokens: 218034` stays; and a
long run of one-case words joined by underscores, such as a test name, is an identifier. A harvest of the 2026-10-26 and 2026-10-27 coordinator transcripts (262 events) wrote none of the tokens pasted
in them.

## Failure handling

Every failure prints `puppet: <message>` on stderr and exits non-zero: 2 for a usage error, 1 for an operational
failure. There is no silent fallback.

- A name that matches two sessions (for example the user's own window and a worker) is refused as ambiguous, with the
  ids listed.
- `cycle` and `close` refuse a session that is not `kind` `background`: a window the user opened has no supported
  remote stop.
- `assign` refuses a session that is not in the roster, that is the analyst, that already held a job, that has a new
  session id, or whose checkout another session is editing.
- `cycle` refuses a worker that is not idle. If it fails after stopping the worker, the message says whether the worker
  was compacted and prints the `cd "<cwd>" && claude --bg --resume <sessionId>` that restarts it.
- `close` keeps the registry record when `claude rm` fails, and prints the resume command.

## Setup that stays the user's

The skill documents these and never applies them:

- `worktree.bgIsolation: "none"` in the user's own `settings.json`.
- A trusted folder for each worker's cwd.
- `crossSessionInbound: accept`, only if a worker runs in a mode that holds messages.
- The logs folder, through the plugin option or `PUPPET_LOGS_DIR`.

## Tests

`tests/test_puppet_master.py` runs `node --test` over `tests/puppet_master/*.test.mjs`. A fake `deps.run` answers every
`claude` and `git` call, so no test starts a session. The fixtures in `tests/puppet_master/fixtures/` are sanitized
captures of a real probe worker, plus `bg-stdout-color.txt` (the coloured `--bg` output) and `transcript-harvest.jsonl`
(one entry per event kind, each with a near-miss). The suite covers:

- transcript measurement: a partial trailing line, sidechain usage, a compact boundary after the last usage, an
  automatic boundary without `postTokens`, and fresh sessions;
- window resolution and the registry;
- the roster: adopt, assign, finish, pick, the one-editor lock, changed and gone sessions, and Windows paths that
  differ in case or hold spaces;
- `cycle`'s verified compaction and its stopped-worker messages, and `close` never passing a discard flag;
- logs-folder resolution, redaction (including a secret past the excerpt cut), event extraction across a partial
  line, and harvest offsets;
- findings, the summary headline, decisions and the before/after means;
- the text of `SKILL.md` and both briefs (the analyst brief's tags must equal the tags in `analyst.mjs`), and the
  `plugin.json` option.

A missing `node` (20 or newer) fails the test, never skips it.

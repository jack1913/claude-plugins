# puppet-master

One interactive Claude Code session, the **master**, coordinates the user's sessions the way a person would by hand:
it hands each job to one of the user's open sessions, or starts a background worker when none is free, briefs it,
relays its questions, measures its context, gets it compacted at a clean task boundary and closes the workers when
their jobs are done. One more session, the **analyst**, watches the day and proposes changes to the skill at its end.
The master does housekeeping only; the user makes every decision.

The skill sets `disable-model-invocation: true`, so it runs only when typed as `/puppet-master:puppet-master`: a request that
sounds like coordinating sessions never starts it.

## Files

- [`skills/puppet-master/SKILL.md`](../../skills/puppet-master/SKILL.md) holds the master's start-up, rules, relay
  protocol, wrap-up and the helper reference.
- [`worker-brief.md`](../../skills/puppet-master/worker-brief.md) is the brief every worker gets, with the placeholders
  `{{master_name}}`, `{{job}}`, `{{commit_rules}}` and `{{standing_rules}}`, the ones `SKILL.md` explains under Briefs
  for every brief: `{{deliverable}}`, `{{local_state}}` and `{{approvals}}`, and the conditional ones: `{{tier_check}}`, `{{test_tmp}}`, `{{decided}}`, `{{write_scope}}`, `{{peers}}`, `{{owners}}`, `{{handoffs}}`,
  `{{references}}`, `{{fetch}}`, `{{open_premises}}` and `{{self_compact}}`.
- [`analyst-brief.md`](../../skills/puppet-master/analyst-brief.md) is the analyst's brief, with `{{master_name}}`,
  `{{helper}}`, `{{logs_args}}` and `{{proposal_id}}`, the closed tag list and the report's shape.
- [`setup-prerequisites.md`](../../skills/puppet-master/setup-prerequisites.md) holds the user's setup prerequisites
  (settings, trusted folders, the mod's floor, `PUPPET_*` variables). `SKILL.md` points to it: its body is held under
  the docs standard's 500 lines.
- [`scripts/puppet.mjs`](../../skills/puppet-master/scripts/puppet.mjs) is the helper and its command line: `measure`,
  `list`, `adopt`, `assign`, `finish`, `reopen`, `pick`, `spawn`, `cycle`, `compact`, `switch`, `clear`, `close`,
  `harvest`, `finding`, `summary`, `decide` and `shipped`.
- [`hooks/puppet-mod.js`](../../hooks/puppet-mod.js), listed by [`hooks/hooks.json`](../../hooks/hooks.json), is the
  mod that compacts, switches the model and effort of, or clears a session from inside (see [The mod](#the-mod)). Claude Code runs it in its own
  environment, not in Node; `hooks/package.json` only lets Node import it in the tests.
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
  job's checkout (`pick`), and a background worker is started only when there is none. The user, 2026-11-06: "move
  theirs work into opened, and keep bg only when you cannot do with opened windows": a window on the wrong tier whose
  mod is on is switched to the tier rather than passed over, so `pick` ranks it with the ones that match. On 2026-10-27 the master did
  merges, pushes and checkouts itself, so anything that changes a repository is a job for a session, unless the user
  tells the master to do it or it is a read-only check of a session's report.
- **One job per context, unless reused on purpose.** By default a session that held a job is not given another
  (`assign` refuses it): different work in one context gets mixed up. `assign --reuse` gives a `done` session its next
  job only while it measures under 30% of its window (1M unless given). Above that, the refusal says to `clear` it
  where its mod is on, else to give the user the session's `/clear` line.
  The record keeps every job in `jobs[]`. `assign --extend` adds work to the job a session holds instead: the label
  and scope merge and the start stays. `reopen` undoes a `finish` made too early, so nobody edits `workers.json` by
  hand.
- **One editing session per checkout, unless both jobs name their folders.** `assign` and `spawn` refuse a second
  session with an active job whose cwd resolves (through `git rev-parse --show-toplevel`) to the same checkout. The
  exception: both jobs pass `--scope <folders>` (relative to the checkout, comma-separated), the folders don't
  overlap, and at most one of the two runs git (the other passes `--no-git`). A session adopted as `unknown` counts
  while it is not idle, since it may be editing; a clean session, a finished one, the analyst and the master do not
  count. A folder outside any repository is its own checkout; any other git failure is an error, because it would
  weaken the lock.
- **Every job names its tier.** `creative` (design, writing, judgment, review) needs an Opus model at high effort or
  more; `mechanical` (renames, moves, reformatting, checks) needs a model other than Opus at medium effort or less.
  `assign --tier` and `pick --tier` compare the tier with the session's switch when its mod has one, else with its
  transcript, and print `ok`, `unchecked` (no turn yet) or `MISMATCH`. A mismatch warns and does not refuse. After
  it, where the session's mod is on, both commands print `its mod is on: run switch <name> --tier <tier>` and the
  master runs it (see [The model switch](#the-model-switch)); elsewhere they print session-only paste lines
  (`<name>: /model`, then `s` on the tier's model row; `<name>: /effort`, then `s` at its level), and the master
  takes another window or spawns a worker on the tier. It never changes a session's settings. A fresh session is
  asked for its model only. Its
  effort is read from its transcript after the first turn, because workers misreport their own effort: on
  2026-11-01 three of three said `low` while their transcripts said medium, medium and high.
- **A spawn always names its effort.** `spawn` passes `--model` and `--effort` to `claude --bg`: `creative` gives
  `opus` at `high`, `mechanical` gives `sonnet` at `medium`, and explicit `--model`/`--effort` win. With neither a tier
  nor `--effort` it exits 2: on 2026-11-02 a worker spawned with no flags started at medium although the user's own
  default is high. Aliases only, never versioned model ids. The first turn's transcript still confirms what started.
- **Proxy launchers.** On a machine with a proxy launcher (such as use-llm) the transcript shows the Claude model
  name, and the real backend shows only in the launcher's command line. The launcher's config is never read: it may
  hold plaintext keys.
- **Relays quote the user.** On 2026-10-27 a paraphrase turned a request for browser checks into a new end-to-end
  test suite, so a relayed job or answer quotes the user's words first and marks the master's reading as such. The worker brief carries the user's
  standing rules (`{{standing_rules}}`), such as where scratch files go.
- **Only the commands the skill names.** An unknown `claude <word>` starts a new session with that word as its prompt:
  `claude ps` did so on 2026-10-27.
- **No git worktrees.** Nothing calls `EnterWorktree` or `git worktree`, and `claude rm` never gets
  `--discard-unpushed` or `--force-remove-worktree`: if it refuses, the user decides.
- **Compaction is measured and happens at task boundaries only.** Compact an idle session at 30% or more of its window
  when the job continues, measured on each relay of a working session's message and at each `FINAL:`; at 30% or more,
  ask a working session to stop at its next boundary; never compact mid-task; a finished job is closed (or, in a
  window whose mod is on, cleared), never compacted. The master's own line is 40%, then each further 20%. An automatic threshold that can fire mid-task is not the mechanism. A
  background worker is compacted by `compact` where its mod is on, else by `cycle`. A window the user opened has no
  remote stop and a message cannot compact it, so, where its mod is not on, the master lets its auto-compaction run
  (2026-11-01: four hand-pasted `/compact` lines were the user's chore, while two auto-compactions did no harm) and
  gives a `<session>: /compact <focus>` line only when the user opted in; a `/clear` line is for a new job that needs
  another model or a clean context. The master treats its own context the same way, through its own mod when on.
- **The mod is off unless switched on, and clears only finished workers.** The user's terms, 2026-11-04: "Compact
  freely, clear only between jobs and only for workers, do not clear master", and the mod asks at session start
  with a suggested yes, but "if not said explicit it wont run". So silence is off: the plugin option `self_compact` is
  `ask` by default, a window asks once, and a background worker is switched on only by the master's `--self-compact`
  after the user's yes. `off` is the user's veto and beats the master's opt-in. `clear` is refused by the helper for
  a master, an analyst and any session without a finished job, and refused again by the mod, which clears only a
  session whose role file says `worker`, and only while idle (never queued behind a prompt).
- **Measured, not reported.** A worker's own estimate of its size is a prompt to measure, never a reason to act:
  workers have claimed to be full at about a fifth of their window.
- **No permission laundering.** A relayed answer is never the user's approval of a permission prompt in a worker, and
  the master never asks a worker to do what the user's settings denied. A worker asking the user to confirm in its own
  window is correct. A worker blocked by the user's uncommitted edits or by its permission mode reaches the user once,
  with the exact command; the job is never handed to another session, which would get round the denial (the user
  dropped that route on 2026-11-02). The brief names who runs each irreversible command up front.
- **Every question comes to the master's window.** The user, 2026-11-04 (it replaced the analyst's proposal P-1, "the
  worker asks for the approval itself in its own window"): "all worker questions and decisions come to the master's
  window; the owner sets each worker window to accept-edits once at job start; only irreversible steps (deletes,
  pushes, Railway writes) keep a permission prompt in the worker's window". A worker never uses `AskUserQuestion`: it
  sends the question to the master, which asks the user in its own window. On 2026-11-03 the user typed the same
  approval line in the master's window and then in a worker's, four times, and a worker sat on its own prompt for
  17 and 32 minutes while the master looked elsewhere; so the master also runs `list` before each reply and leads with a
  `waiting` session.
- **A busy worker is paused, not compacted.** `compact` refuses a busy session. The pattern that worked four times on
  one worker on 2026-11-04: ask it to pause at its next part boundary, wait for the idle notice
  (`SendMessage` with `notify_when_idle`, never `compact` in the pause request's own turn), `compact` it with a focus,
  send "continue". A
  worker pauses by itself past about 150k tokens, which is the one size a worker may report.
- **A brief states checked facts.** The master re-reads the decisions log and any state a brief asserts just before
  sending it, checks a tool is installed before saying so, and names each step's precondition: on 2026-11-02 one
  brief called approved proposals unreviewed and another called an installed package missing.
- **Workers keep their hands off.** The brief forbids stashing, resetting or switching over the user's uncommitted
  edits, printing a credential, and driving the Playwright browser without holding it; it names a test temp folder
  with no spaces (a `TMP` under a path with a space made suites look red twice on 2026-11-02) and the values the
  user already decided, so a plugin's prompt in the worker's window is not put to the user again.

## Verified mechanics

Verified on Windows 10 with Claude Code 2.1.310, and the rows marked 2.1.312 again on 2026-10-28. Each step is what
the helper calls.

| Step | How | Result |
| --- | --- | --- |
| Start | `claude --bg --name <worker> "<brief>"`, in a trusted folder | Works; an untrusted folder refuses until the user runs `claude` there once. Stdout: `backgrounded · <id> · <name>` plus hint lines. On 2.1.312 the id and hints are wrapped in ANSI colour codes, which `parseBgId` strips |
| List | `claude agents --json` (or the `ListAgents` tool) | Background workers with `kind` `background`, `id`, `sessionId`, `cwd`, `state` and `status`. On 2.1.312 the user's windows are listed too, with `kind` `interactive`, `sessionId`, `cwd`, `status` and no `id` or `state` |
| Compact by message (2.1.312) | `SendMessage` of `/compact <focus>` to a live session | Refused: it arrives as wrapped plain text, the session answers that it cannot run a built-in command, and no `compact_boundary` is written |
| States | `state` in the listing | `working` (`status` `busy`), then `done` (`status` `idle`); `blocked` while waiting on a prompt. A session parked on a dialog lists as `state` `done` with `status` `waiting` (probe, 2026-11-04): the helper reports it as `waiting`, which is busy. A stopped worker drops out of the listing |
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
- The window comes from `--window <tokens>`, else the window the session's last `cycle` or `adopt --window`
  recorded, else `PUPPET_CONTEXT_WINDOW`, else 1,000,000 (source `default`). Context is given only as tokens and a %
  of that window: the owner's rule of 2026-11-06. An earlier version also measured each session against the size
  where it had auto-compacted (its "compaction point", with a `WARN` from 80% of it); that share read 115% for a
  session at 239,498 tokens, 24% of its window, and blocked `assign --reuse` (2026-11-06), so it was removed along with
  `--compact-at` and `PUPPET_COMPACT_AT`.
- The **model and effort** are those of the last main-thread `api-request` record (`querySource`
  `repl_main_thread`): `params.model` and `params.output_config.effort`. `list` shows them as
  `model <model> <effort>`, or `model fresh` before the first request.

## The roster

`<config dir>/puppet-master/workers.json` (`PUPPET_STATE` overrides it; the config dir is `CLAUDE_CONFIG_DIR` or
`~/.claude`) maps each session's name to its record: `id` (background only), `sessionId`, `cwd`, `checkout`, `kind`
(`interactive` or `background`), `role` (`worker`, `analyst` or `master`), `job`, `jobState`, `jobStartedAt`, `jobs[]`
(each job's label, start and `endedAt`), the job's `scope`, `git` and `tier` when given, and its `window` after a
`cycle` or `adopt --window`. Beside `workers`, the file keeps `pendingHarvest`, `observedCompactAt` and `closed` (one
tombstone per closed session: `id`, `sessionId`, `cwd`, `closedAt`). A record written before the roster existed
reads as an active background worker. The file is written atomically (a temp file, then a rename).

- `adopt` takes a listed session into the roster as `clean` (no turns yet, or at most two text turns and no tool call:
  it only read a brief and replied, 2026-11-03) or `unknown` (it did something). Only one live session may be the
  analyst, and only one the master. The master adopts itself with `--role master --window <tokens>`. The analyst and
  the master take no jobs and hold no checkout lock.
- **A renamed session keeps its record.** A rename in the window changes the name `claude agents --json` lists and
  keeps the session id (2026-11-04: `carcare-platform-66` became `-b3`, and the roster held both, `done` and
  `unknown`). Every command that lists the sessions first carries a record whose `sessionId` matches a live session under
  another name to the live name, and saves it; of two records for one session the better one wins (an active job over a
  finished one over `unknown` over `clean`, the older name's at a tie). `adopt` of a carried session keeps its job and
  state. Adopting a session that is already in the roster under the same name and `sessionId` likewise keeps its job and
  `jobState`, and updates only the role, the window and the mod's role file (2026-11-04: an adopt of a carried `done`
  record made it `unknown`, and `clear` and `assign` refused it); a session adopted before the mod existed has no role
  file, which the mod reads as role none, and this is how it gets one (`clear` says so). A changed `sessionId` is
  adopted afresh. Only the same `sessionId` moves: a name another live session still uses, and a session id that changed (a
  `clear`), are left as they were.
- `assign` moves `clean` to `active`, `finish` moves `active` to `done`, and `assign --reuse` moves `done` back to
  `active` under the 30% rule, and so does `reopen`, which keeps the job and its start. Nothing moves a session back to `clean` except adopting it again, which the master
  does only after asking the user.
- `assign --extend` keeps the job's git flag unless `--git` or `--no-git` is passed (2026-11-03: a no-git job turned
  into a git job, and a later `--extend --no-git` could not undo it), and adds no label the job already has. The scope
  still widens to the whole checkout when either side has none, so `--extend --scope` cannot narrow a running job.
- `pick <cwd>` returns a clean worker session in the cwd's checkout, or nothing when another session is editing that
  checkout (with `--scope` and `--no-git`, under the scope rule). With `--tier`, a session whose model and effort
  already match comes first, then an unchecked one, then a mismatch; within each, the user's windows come before
  background ones. `pick` prints the name, then the tier line.
- `list` shows every roster session: name, tokens, percent of the window, state, the
  model column, and for a roster session its kind, role, job state and job. `--name <session>` prints that one row.
  A session listed under a new `sessionId` (the user cleared or restarted it) is `changed`, and `assign` refuses it
  until it is adopted again. One no longer listed is `gone`, with its resume command, and its record is dropped.
  Background sessions that nobody adopted are listed too.
- A session whose mod has beaten ends its `list` row in `mod on (<source>)`, `mod off (mode <mode>)` or `mod stale`,
  and its JSON row has a `mod` string; a session whose mod never beat has neither.
- `list --json` prints one JSON object per row. A measured row has `name`, `id`, `tokens`, `percent`, `window`,
  `windowSource`, `compactAt`, `compactSource`, `compactPercent`, `warn`, `state`, `tokenSource`, `model`, `effort`
  and `autoCompactAt`, plus `kind`, `role`, `job`, `jobState` and `roster: true` for a roster session. A changed row
  is `{name, id, changed: true, sessionId}`, a gone row `{name, id, state: "gone", sessionId, cwd}`, and a row that
  could not be measured `{name, id, error}`.
- `close` leaves a tombstone, so a later command naming that session says `<name> is closed (resume: …)` rather than
  that no session has the name. Adopting or spawning the name again clears it.
- `spawn` prunes records of sessions that are no longer listed, printing how to resume each. The transcripts stay, so
  nothing is lost.

## The mod

`hooks/puppet-mod.js` runs inside every session that loads the plugin and, in a session where it was switched on,
compacts or clears that session when the helper writes a request. Options considered and why this one:
[clear-compact-options.md](clear-compact-options.md).

**Switched on** means one of: the user said yes to the start question (`asked`), `self_compact` is `on` (`config`), or
the helper wrote an opt-in for the session (`optin`, from `spawn` or `adopt --self-compact`). `self_compact` `off`
beats all three. A missing config row counts as off.

**Files.** One folder, `PUPPET_MOD_DIR` or `<config dir>/puppet-master/mod`, written atomically by the helper (a
temp file, then a rename) and plainly by the mod (the mod has no rename or delete; it blanks a handled request to
`{}`):

| File | Written by | Holds |
| --- | --- | --- |
| `heartbeat/<sessionId>.json` | the mod, every 3 s, and at once after a switch | `sessionId`, `version`, `beat` (ms), `mode`, `enabled`, `source`, `role`, `ask`, `turnRunning`, `override` (the switch that applies, or `null`), `lastError` |
| `optin/<sessionId>.json` | the helper | the master's opt-in |
| `roles/<sessionId>.json` | the helper, on `adopt` and `spawn` | `role` |
| `requests/<sessionId>.json` | the helper | `nonce`, `sessionId`, `requestedAt` (ms), `action` (`compact`, `switch` or `clear`), `focus`, `model` and `effort` or `reset`, `role` |
| `acks/<nonce>.json` | the mod | `ok`, `outcome`, tokens before and after, `model`, `effort` and `previous` after a switch, or `newSessionId` after a clear |
| `overrides/<sessionId>.json` | the mod, on a switch | `model`, `effort`, `at`, `nonce`, and `carriedFrom` when a clear moved it to a new id; `{}` after `--reset` |

The mod acts only on a request for its own session id, newer than five minutes, with a valid nonce it has not seen,
and answers every refusal with an ack: `wrong-session`, `stale`, `not-enabled`, `refused-role`, `refused-value`,
`busy`, `vetoed`, `rejected`. A heartbeat older than 15 s reads as a mod that stopped. The helper removes an ack once read, and on a
timeout withdraws its request so nothing runs later unseen.

**Compact.** The mod calls `$.session.compact({ instructions: focus })`. It rejects while a turn runs, so the mod
keeps the request and retries every 3 s until the request is stale. The helper then checks the transcript for a new
`compact_boundary`, as `cycle` does. The master's own compaction cannot wait for an ack inside its own turn: the
helper writes the request and returns, and the mod runs it after the turn.

**Clear.** The mod tracks `turn.start`, `turn.complete` and `prompt.submit`. It runs `$.command.run({ command:
"clear" })` only when a worker role file and the request both say `worker`, no turn runs, and no prompt arrived in the
last 10 s. A busy session is answered `busy` at once, never retried or queued. After a clear the session id changes;
the mod copies the opt-in and role files to the new id and acks it, and the helper re-adopts the worker as `clean`
under that id, queueing the old id for the analyst's next harvest.

**The start question.** In mode `ask`, 5 s after the start, `$.ui.ask` offers "Yes, this session (Recommended)",
"Yes, always on this machine" (sets `self_compact` `on`), "No" and "No, and don't ask again on this machine" (sets
`off`). A dismissal or no answer in 20 s leaves the session off. The question is asked only when `claude agents
--json` lists the mod's own session as `interactive`, so the mod makes one `$.process.run` with no shell
(`PUPPET_CLAUDE_BIN` is honoured). Why: a probe on 2026-11-04 found that in a `--bg` session `isInteractive` is
`true` and `surface` is `terminal`, and that `$.ui.ask` leaves the dialog open after its timeout, so the worker sat at
`state` `done`, `status` `waiting` for as long as the probe watched. A background row, no row, no `claude` and bad JSON
all mean no question, recorded in the heartbeat as `ask`: `skipped-background` or `skipped-unknown`.

**Verified** (probe sessions, 2026-11-04, Claude Code 2.1.318, Windows 10): a mod in a background session compacted it
(24,266 to 6,452 tokens, with the focus kept) and cleared it (new session id, same background id); the ask hangs a
background worker as described above.

**Verified on a foreground window** (reported by the master, 2026-11-04, not re-run for this page): `finish` then
`clear` on the live window `carcare-platform-b3` printed `cleared carcare-platform-b3: new session f824c3fb-…, clean`.
The master also ran `compact` with a focus four times on one worker between its parts: 262k to 28k, 154k to 23k, 143k
to 25k and 182k to 18k tokens (see the pause pattern in `SKILL.md`, rule 7). **Not yet tested in a foreground
window**: the start question and its four answers, the master's own compaction after its turn, that the mod's timer
survives a `/clear`, and `mod on` showing in `list` through the plugin's real install. The mod runs in an environment
with no Node and no `fs` in `claude plugin test`, so the unit tests in `tests/mod.test.mjs` drive it with a fake `$`
and a Map for the files.

**A session parked on a dialog is not idle.** It lists as `state` `done`, `status` `waiting`. `workerState` reports it
as `waiting`, which is in `BUSY_STATES` and not in `IDLE_STATES`, so `compact`, `clear` and `cycle` refuse it and the
checkout lock counts an `unknown` session in that state as editing (before, only `compact` and `clear` checked
`status`). Idle means state `done` or `idle` and no pending dialog.

### The model switch

Built on 2026-11-06 at the owner's word: "we must solve this onces and for all [...] i asked if you have enabled
yesterday update that should let you handle changing model and effort of opened sessions like you do with clear and
compact". It replaces the 2026-11-05 pick "No: paste lines + spawn". The probe notes are in the checkout's untracked
`scratch/model-switch-probe-report.md`, the build's live test in `scratch/model-switch-build/`.

**How it works.** `switch <session> --tier T | --model M --effort E | --reset` writes a `switch` request; `--tier` uses
`spawn`'s model and effort (`creative`: `opus` `high`; `mechanical`: `sonnet` `medium`). The mod checks the values
(an alias `opus`, `sonnet`, `haiku` or a `claude-*` id, each with an optional `[1m]`, and one of the five effort
levels; anything else is `refused-value`), writes `overrides/<session>.json` and acks `switched` with the previous
switch. Like `compact`, it waits while a turn runs and retries each tick until the request is stale, so the master's
own switch lands after its turn. A `turn.step` hook then calls `next({ ...e, model, effort })` on every main-loop
request (`e.agentId` absent); a subagent keeps its own model. The hook applies the override only while the mod is
switched on: `self_compact` `off` vetoes it. After a load or a `/reload-plugins` it reads the override file once
before the first tick. A new session id, from the mod's `clear` or a `/clear` the user typed, takes the old id's
override along, as a `/model` choice outlives a `/clear`. `--reset` blanks the file and the session goes back to its
launch model. `assign` and `pick` read the switch from the heartbeat, so a switched session checks `ok (… (switched))`
before its next turn.

**Verified** (2026-11-06, Claude Code 2.1.319, a throwaway `--bg` session started as `--model haiku --effort low`,
closed with the helper's `close`; the transcript's `api-request` records, read by
`scratch/model-switch-build/facts.mjs`):

- after `switch --model sonnet --effort medium`, both main-thread requests of a turn with a `Read` tool call (before
  and after the tool result) went out as `claude-sonnet-5-5` at `medium`, and `list` printed `model claude-sonnet-5-5
  medium … mod on (optin)  switched to sonnet medium`;
- after `compact` the session id stayed the same and the next request was still Sonnet at medium;
- after `clear` the new session id held the override (`carriedFrom` the old one) and its first request was Sonnet at
  medium;
- `--tier creative` gave `claude-opus-5-5` at `high`, and `--reset` gave `claude-haiku-5-5` at `low` again;
- the SHA-256 of the user's and the checkout's `settings.json` was the same before and after; neither
  `settings.local.json` exists;
- the session loaded the mod straight from the checkout: `claude plugin list` reads `puppet-master@jack1913` from
  `plugins/puppet-master`, and the probe's heartbeat carried the new `override` field.

**Known costs.**

- The status line keeps showing the launch model and effort (it showed `Haiku 5.5 low` through every switch), and
  the session names the launch model when asked (it answered "Haiku 5.5 (claude-haiku-5-5)" while Sonnet ran it).
  `list` is the only check: its `model` column is the last request sent.
- The context window the status line and `$.session.usage()` report is the launch model's: the mods types call it
  "the context window of the session's model". That auto-compaction follows the launch model's window too is a
  **hypothesis**: not tested. Switching a session to a model with a smaller window than its launch model's could let
  it grow past that smaller window before it compacts.
- Each switch starts a new prompt cache for the next request, as a `/model` switch does (**hypothesis**: not measured).
- The hook rewrites every main-loop request, a fallback model's too (`e.model` is "the session's, a fallback's"), so
  a switch overrides a fallback (**hypothesis**: no fallback was seen).
- The mod's busy check counts a subagent's `turn.complete` as the turn's end; the helper's own idle check from
  `claude agents` comes first, so a busy session is refused before a request is written.

**Not yet tested:** a foreground window, a `/reload-plugins` in a live session (the unit test covers the read before
the first tick), and the master's own switch after its turn.

Why `turn.step` and not `/model`:

- **A typed `/model <name>` or `/effort <level>` saves the user's default.** "Typing `/model <name>` directly behaves
  like `Enter`", which writes `model` to the user's settings, background sessions included. A level typed after
  `/effort` is saved per model under `modelSettings`. Only `s` in the picker or the slider switches one session
  (**verified**: docs, model-config "Setting your model" and "Adjust effort level", agent-view "Set the model,
  effort, and fast mode"). So a mod running `$.command.run({ command: "model", args })` would change the default of
  every new session, and the paste lines use the `s` form. The mods API has `$.session.model()` and no setter
  (**verified**: mods types, `$.session`).
- **A `turn.step` hook can switch a session without writing settings, but the status line does not follow.** A probe
  mod on a throwaway `--bg` Haiku session rewrote each main-loop request to `sonnet` at `medium`. The transcript's
  `api-request` and the reply both recorded `claude-sonnet-5-5`, and `puppet list` printed `model claude-sonnet-5-5
  medium`. The SHA-256 of the user's and the checkout's `settings.json` stayed the same across four snapshots. But
  the status line was given `claude-haiku-5-5` at `low` on every call, `$.session.model()` stayed Haiku, and the
  switched model, asked its name, answered "Haiku 5.5" (**verified**: the probe, background id `511c4a9b`, stopped
  and removed).
- **Where the mod is not on**, a `MISMATCH` still leads to another window or `spawn`, which passes `--model` and
  `--effort` at launch and saves nothing, and a window the user keeps for the job gets the session-only paste lines
  (`switchPaste` in `puppet.mjs`).

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
  `<logs>/decisions.jsonl`, `<logs>/harvest.lock` while a harvest runs, and one folder per work day holding
  `events.jsonl`, `harvest-stats.json`, `findings.jsonl` and the analyst's `report.md`.
- **Work day:** a day starts at 05:00 local, so a session that runs past midnight stays in one folder.
  `PUPPET_DAY_START_HOUR` sets another whole hour (`0` gives calendar days); any other value is an error. `summary`,
  `finding` and `logs` take today to be the current work day.
- **`harvest`** is deterministic. For every roster session, live or not, every session that left the roster since the
  last harvest (closed, dropped as `gone`, or re-adopted under a new session id: the registry's `pendingHarvest`,
  read once and cleared) and the master, it reads the transcript lines after the stored offset and appends events of
  ten kinds: `user-turn`, `message-in`, `message-out`, `helper-error`,
  `command-failed`, `manual-cli`, `cli-unknown`, `permission-denied`, `compact-manual` and `compact-auto`. The user's
  answer to an `AskUserQuestion` dialog is a `user-turn` (a declined dialog is not), and a `SendMessage` without a
  message (a pure `notify_when_idle` subscription) is no event. Each event has an id
  `<first 8 of sessionId>:<line>` (with `.2`, `.3` when one line yields several), a timestamp and an excerpt of at
  most 300 characters. Each event goes to the work day of its own timestamp, so a harvest after the day ends still
  files that day's events under it; an event without a timestamp goes to the run's day. The run's lines and sessions
  count in the run day's stats, and each event in the stats of the day it was filed under. A last line that does not
  parse is being written: it is not consumed. A transcript with
  fewer lines than its stored offset was replaced, so it is read again from the top and the one-line log names it.
  One harvest runs at a time: a second one is refused while `harvest.lock` exists, and a lock older than two minutes
  was left by a crash and is taken over. A crash between appending the events and writing the offsets can still log
  that run's events twice.
- **`logs`** prints the logs folder and the newest report of an earlier day whose last line is not `Reviewed: <date>`.
  The master runs it on start, so finding the folder never needs a harvest.
- **`finding`** records a tag from the closed list, a target (`SKILL.md`, `worker-brief.md`, `puppet.mjs`, `docs`)
  and evidence ids that must exist among the harvested events of today or an earlier day; the finding is filed under
  today. A target `instrument:<file>` names the analyst's own
  brief or scripts: it is flagged to the user and never proposed.
- **`summary`** starts with a headline of sessions, lines, events and findings. With no lines read, the headline says
  nothing was read, so an empty day cannot pass for a clean one; lines read with no events is a clean day.
- **Groups.** Every command takes `--group <name>` (`[A-Za-z0-9-]+`, before or after the command). A group is one
  master with its sessions: its roster is `workers-<group>.json` beside the default one and its logs are
  `<logs>/<group>`, so a second master on one machine needs no `PUPPET_STATE`/`PUPPET_LOGS_DIR` prefix (on
  2026-11-02 the carcare master ran on that prefix, which the skill did not mention). A grouped proposal id is
  `P-<YYYYMMDD>-<group>-<n>`: the two groups' 11-02 reports both numbered `P-20261102-1..`, so an id alone was
  ambiguous. `decide` and `shipped` refuse an id that names another group; an ungrouped id is taken by any group.
  The checkout lock sees one group's roster only.
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
- `assign` refuses a session that is not in the roster, that is the analyst or the master, that already held a job
  (unless `--reuse` and under 30%), that has a new session id, or whose checkout another session is editing outside
  the scope rule. `--reuse` also refuses a session it cannot measure. `--extend` refuses a session with no active job,
  and a merged scope that collides with another job.
- `reopen` refuses a session whose job is not `done`, and one whose checkout another job edits now.
- `list` ends an active job's row with `DONE? run finish` when the session's last assistant text starts a line with
  `FINAL:` or says "job is done": on 2026-11-01 a worker reported done at 16:27 and stayed open until it
  auto-compacted at 19:55. The flag is a hint; nothing finishes a job but `finish`.
- `assign` and `pick` never refuse on a tier: a `MISMATCH` line is a warning.
- `cycle` refuses a worker that is not idle. If it fails after stopping the worker, the message says whether the worker
  was compacted and prints the `cd "<cwd>" && claude --bg --resume <sessionId>` that restarts it.
- `close` keeps the registry record when `claude rm` fails, and prints the resume command.
- `compact` refuses a session outside the roster, one that is not idle or is `waiting` on a dialog (the master's own
  session is exempt from the idle check, since it runs in its own turn), and one whose mod has no fresh, switched-on
  heartbeat; it names the reason and prints `give the user "<name>: /compact <focus>" to paste`. A refusing ack, a
  timeout (90 s) and an ack with no new `compact_boundary` in the transcript are errors with the same line.
- `switch` refuses a wrong flag combination or value (exit 2), a session outside the roster, one that is not idle or
  is `waiting` (the master's own session is exempt), one whose mod has no fresh, switched-on heartbeat, and one whose
  heartbeat has no `override` field (a mod loaded before the switch existed, which would drop the request); it names
  the reason and prints the session-only paste lines. A refusing ack and a timeout are errors with the same lines.
- `clear` refuses a session that is not a worker, has an active job or no finished job, is not idle or is `waiting`,
  or whose heartbeat does not show the `worker` role; a refusing ack, a missing new session id and a new session
  that `claude agents` does not list are errors. It never sends a second request while one waits.

## Setup that stays the user's

The skill documents these and never applies them:

- `worktree.bgIsolation: "none"` in the user's own `settings.json`.
- A trusted folder for each worker's cwd.
- `crossSessionInbound: accept`, only if a worker runs in a mode that holds messages.
- The logs folder, through the plugin option or `PUPPET_LOGS_DIR`.
- `self_compact`: only the user's answer or their own setting changes it; the master never does, and passes
  `--self-compact` only after the user's yes.

## Tests

The workflow runs `node --test` over `tests/*.test.mjs`. A fake `deps.run` answers every
`claude` and `git` call, so no test starts a session. The fixtures in `tests/fixtures/` are sanitized
captures of a real probe worker, plus `bg-stdout-color.txt` (the coloured `--bg` output) and `transcript-harvest.jsonl`
(one entry per event kind, each with a near-miss). The suite covers:

- transcript measurement: a partial trailing line, sidechain usage, a compact boundary after the last usage, an
  automatic boundary without `postTokens`, and fresh sessions;
- window resolution and the registry;
- the roster: adopt, assign, finish, pick, the one-editor lock, changed and gone sessions, and Windows paths that
  differ in case or hold spaces;
- tokens and % of the window only (no compaction point), the model and effort column, `list --name` and the closed tombstone
  (`compaction.test.mjs`); reuse, write scopes, tiers and the master's record (`dispatch.test.mjs`); groups (`group.test.mjs`);
- `cycle`'s verified compaction and its stopped-worker messages, and `close` never passing a discard flag;
- logs-folder resolution, redaction (including a secret past the excerpt cut), event extraction across a partial
  line, dialog answers and `notify_when_idle`, harvest offsets, and filing by work day;
- findings, the summary headline, decisions and the before/after means;
- the mod against a fake `$` (`mod.test.mjs`): off unless switched on, the veto, stale and foreign requests, the
  compact retry, every clear refusal, the start question's answers and its skips, and the switch: the `turn.step`
  rewrite on the main loop only, the veto, the limits, the wait while a turn runs, `--reset`, the read before the
  first tick, and the carry to a new session id; the helper's `compact`, `clear`, opt-in and role files and the
  `list` column against a scripted fake mod (`selfcompact.test.mjs`); the helper's `switch`, the tier check that reads
  a switch, the line after a `MISMATCH`, and `pick` ranking a switchable window (`switch.test.mjs`);
- the text of `SKILL.md` and both briefs (the analyst brief's tags must equal the tags in `analyst.mjs`), and the
  `plugin.json` options.

A missing `node` (20 or newer) fails the test, never skips it.

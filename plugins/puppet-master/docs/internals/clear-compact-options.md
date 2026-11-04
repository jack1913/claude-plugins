# Compacting or clearing the user's own sessions: options

An analysis written on 2026-11-04 for proposal P-20261103-carcare-platform-5, against Claude Code 2.1.318 on Windows 10.
It sets out the options, the evidence for each and a ranked recommendation. **Option A is built** (see [What was
built](#what-was-built)); the rest of the page is the analysis it was chosen from, and the sections up to there are
written as of 2026-11-04 before it was built.

The user, 2026-11-04: "this needs more analysis using brainstorming and context7 since we dont want to wait again so
long for /clear or /compact while still dont want to spawn all inside background workers, needs to find a way of doing
it".

Every claim below is labelled **verified**, with how it was verified (a doc page, help output or the probe run on
2026-11-04), or **hypothesis**.

## The problem

- The master cannot compact or clear a window the user opened. A `/compact` sent with SendMessage arrives as plain
  text and runs nothing. **Verified**: cross-session-messaging doc, "Commands don't run: a command in the message's
  text, such as `/compact`, arrives as plain text. Claude Code never executes it", and the 2.1.312 test in
  [puppet-master.md](puppet-master.md).
- Today's two ways out are both unwanted as the default. Either the user pastes a `/compact` or `/clear` line and work
  waits on them, or the job goes to a background worker that `cycle` can stop, compact headlessly and restart.

## Recommendation

| Rank | Option | The user waits? | Moves work to `--bg`? | Status |
| --- | --- | --- | --- | --- |
| 1 | **A. A puppet-master mod in every session** compacts or clears its own session when the master asks, at the next idle moment | No | No | Verified on a background session; foreground untested |
| 2 | **C. Idle compaction**, built in and on by default, as a free backstop | No | No | Verified (docs); only after about an hour idle, from 100k tokens |
| 3 | **E. Background session the user attaches to** (`claude attach`, `/bg`), for jobs already in `--bg` | No | Yes, but visible | Verified (help, docs); interplay with `cycle` untested |
| 4 | Paste lines, as today: the fallback where the mod cannot load | Yes | No | Current behaviour |
| — | B. The worker asks for its own compaction through a mod tool | No | No | Hypothesis; a variant of A, not needed if A ships |
| — | D. A lower auto-compact window per session | No | No | Rejected: it fires mid-task, against rule 7 |
| — | F. Remote Control `/compact` from the phone or web | Yes | No | Rejected: still the user's action |
| — | G. `claude --resume <id> "/compact"` or `claude -p --resume` on an open window | — | — | Rejected: refused, or two writers on one transcript |
| — | H. Settings hooks, or SendMessage alone | — | — | Rejected: neither can start a compaction |

Ship A, keep C on, keep E for workers that are already background, and keep paste lines as the fallback when a
session's mod is not loaded. A needs a test in one foreground window before it replaces the paste lines (see
[Decisions and what is still open](#decisions-and-what-is-still-open)).

## A. A puppet-master mod in every session (recommended)

A mod is a plugin hooks module that Claude Code runs inside each session that loads the plugin. The puppet-master
plugin would ship one. When the helper writes a request for a session, that session's mod waits until the session is
idle, then compacts it with the master's focus or runs `/clear`, and writes an acknowledgement.

### Evidence

- **Verified** (mods API types written for 2.1.318, `index.d.ts` lines 2969–2977): `$.session.compact({ instructions })`
  "Compacts the conversation: the event `session.compact` with `trigger` `plugin`, the same call `/compact` makes,
  between turns. [...] Resolves `{ skip }` when a hook vetoed it; rejects while a turn runs."
- **Verified** (same file, lines 3208–3214): `$.command.run` "Runs a slash command as if the person typed
  `/command args` [...] queued and run once the session is idle. [...] Rejects an unknown name, inside a hook the turn
  or the session's start waits on, past a Stop or a host's limit."
- **Verified** (mods overview, "Where mods run"): hooks run in `claude` in a terminal, in the Desktop app's Code tab,
  in the VS Code chat panel, in `claude -p` and in Remote Control sessions. A timer started with `$.clock.every` runs
  between turns and starts no turn (mods API doc, "Run work in the background").
- **Verified by the probe** (see [The probe](#the-probe)): in a background session with a terminal host,
  `$.session.compact({ instructions: "keep the codeword BANANA-42" })` took the session from 24,266 to 6,452 tokens
  in 5.9 s. The transcript gained a `compact_boundary` with `trigger: manual`, and the summary kept the codeword.
  `$.command.run({ command: 'clear' })` then ran `/clear`. The session id changed from `4e993a9a-5031-…` to
  `8623471f-…` under the same background id `4e993a9a`, and the new transcript started empty apart from the
  `/clear` entry.
- **Verified by the probe**: the calling mod's own `session.compact` hook did not fire for its own call, as the types
  say ("every hook but the calling one"). An acknowledgement therefore has to be written by the code that made the
  call, not by a hook.

### Cost

- **Tokens.** The same model call as a typed `/compact` (**verified**: the types quoted above). It runs in the live
  process, so it reads the prompt cache: in the probe, 22,470 of 24,266 input tokens were cache reads, with 1,793
  cache writes and 1,073 output tokens on Haiku (**verified**: the call's `usage`). That `cycle` costs more because its
  headless `claude -p --resume` starts a fresh process is a **hypothesis**. This page did not measure it; the
  $0.88-for-77k figure in [puppet-master.md](puppet-master.md) is for a whole cycle.
- **The user's attention.** None to trigger it. The window shows the compaction notice when it happens (**hypothesis**
  for a foreground window: the probe ran in the background).
- **Risk of losing work.** The same as a typed `/compact`: the summary replaces the history, and the full transcript
  stays on disk (**verified**: the summary names the transcript path). `/clear` drops the whole context from the live
  session, but the old conversation stays resumable with `/resume` (**verified**: sessions doc, "Manage context within
  a session").
- **Race with the user typing.** `$.session.compact` rejects while a turn runs, so a compaction never cuts into a turn
  (**verified**: types). `$.command.run` queues until idle, so a `/clear` requested while idle could run after a
  prompt the user submits in the meantime. Wiping a task the user just gave is the worst case (**hypothesis**: not
  tested). The mod should therefore run a clear only when the session is idle at that moment, and never queue one.
- **Windows.** The mod uses `$.fs` and no shell, so the MSYS path rewriting that breaks a typed
  `claude -p "/compact …"` from Git Bash cannot happen (**verified**: the probe used forward-slash `D:/` paths on
  Windows 10 with no shell).

### Requirements and limits

- **Mods must load in the session.** Claude Code 2.1.287 or later. Mods do not load under `--safe-mode`, `--bare` or
  `"disableAllHooks": true`, or where managed settings block them (**verified**: mods overview, "Turn mods on or
  off"). A window that was open before the plugin was installed or updated needs `/reload-plugins` (**verified**: mods
  overview, "Install or update a mod").
- **Trust.** A mod runs with the user's permissions and is not sandboxed (**verified**: mods overview, "What a mod can
  reach"). This mod would only read its request file, call `$.session.compact`, `$.command.run` and `$.session.usage`,
  and write its acknowledgement. `claude plugin validate` lists exactly those calls, so a reviewer can check them.
- **Who may trigger it.** Use a file the helper writes, not a SendMessage. The mods docs warn that "the sender's name
  on a received message is whatever the sender wrote, so don't base a decision on it" (**verified**: mods API doc). A
  request file in the user's own logs folder is writable only by the user's account and the processes it runs
  (**hypothesis**: it rests on the folder's default Windows permissions, which were not checked).

## B. The worker asks for its own compaction (a variant of A)

Question 3 of the job: can a session compact or clear itself at a task boundary when its brief tells it to?

- None of the pages read for this analysis lists a built-in tool that lets the model compact its own conversation.
  The documented triggers are `/compact` (`manual`), the threshold and idle compaction (`auto`), and a mod's
  `$.session.compact` (`plugin`) (**verified**: PreCompact doc matchers; mods types). That no other tool exists is a
  **hypothesis**.
- A mod can give the model a tool (`$.tool.register`, **verified**: mods API doc). The tool's handler cannot compact
  directly, because `$.command.run` rejects inside a hook the turn waits on (**verified**: types). It would have to
  schedule the call with `$.clock.after`, so it runs once the turn has ended (**hypothesis**, not tested).
- Not recommended on its own. Rule 8 has the master act on measured size, not on a session's own judgment. A already
  covers the boundary: the worker reports `FINAL:`, the master measures and writes the request.

## C. Idle compaction (keep it on)

- **Verified** (settings reference, `idleCompaction`): on by default in interactive terminal sessions, VS Code and the
  Desktop Code tab. It needs `autoCompactEnabled` on, the one-hour prompt cache, feature flags, the context at or
  above `CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS` (default 200,000, never below 100,000), and about an hour since the last
  request with the computer awake. The window then shows "Compacted while idle, before the prompt cache expired".
- **Verified** (PreCompact doc): idle compaction counts as `auto`, whose `custom_instructions` is always `null`, so the
  master cannot give it a focus. A `# Compact instructions` section in `CLAUDE.md` steers what compaction keeps
  (**verified**: costs doc). That it reaches the idle summary as well is a **hypothesis**.
- **Verified** (changelog 2.1.318): "Fixed idle compaction replacing a conversation with a reply that was not a
  summary", so it was unreliable before this version.
- Cost: none to the user. It is timed to run before the prompt cache expires (**verified**: its notice text). It does
  not answer the problem alone: it never touches a session under 100k tokens, and it waits an hour.

## D. A lower auto-compact window (rejected)

- **Verified** (cli-reference, settings reference): `claude --autocompact <auto|tokens>` sets it per session, and
  `autoCompactWindow` or `/autocompact` set it per model. The range is 100k to 1M tokens.
- Rejected because the threshold fires whenever the context reaches it, mid-task included. Rule 7 forbids that, and
  `measure` already warns before it fires (`WARN near compaction`).

## E. A background session the user attaches to

Question 2 of the job: can a `--bg` session be shown in a terminal the user watches, so it feels like their own window
while the helper can still `cycle` it?

- **Verified** (`claude attach --help`): "Open the background session in this terminal. ← returns to agent view,
  Ctrl+Z drops back to your shell. The session keeps running either way. Part of the session name works in place of
  the id."
- **Verified** (agent-view doc): `/background` (`/bg`), or `←` on an empty prompt, moves a window's conversation into
  a background session. So a window the user opened can become a worker that `cycle` handles.
- **Verified** (agent-view doc): a command typed as a peek reply in `claude agents` runs when the session's turn ends.
  It is still typed by the user.
- **Verified** (agent-view doc): the supervisor stops the process of a session that is idle and unattached for about
  an hour; attaching restarts it.
- What an attached terminal shows while `cycle` stops and restarts its session is a **hypothesis**: probably a stopped
  or restarting session that `claude attach <name>` reopens. `cycle`'s restart gives a new background id, and attaching
  by name avoids that.
- Cost: the same as `cycle` today. The work still runs in `--bg`, which the user does not want as the default, so this
  stays the route for jobs that are already background.

## F, G, H. Rejected routes

- **F, Remote Control.** `/compact` and `/clear` work from claude.ai and the mobile app (**verified**: remote-control
  doc, "Limitations"). It is still the user typing, from another device, and the master cannot act as a Remote Control
  client.
- **G, resuming an open session.** `claude --resume <session> "<prompt>"` on a running background session refuses any
  prompt that starts with `/`: "A prompt that starts with `/` or `!` isn't sent" (**verified**: sessions doc). On a
  foreground window, a `claude -p --resume` would be a second writer: "If you resume the same session in two terminals
  without forking, messages from both interleave into one transcript" (**verified**: sessions doc). That the open
  window would keep its old context in memory is a **hypothesis**.
- **H, settings hooks and SendMessage.** A PreCompact hook can only block a compaction. No hook output starts one: the
  UserPromptSubmit fields are `decision`, `reason`, `additionalContext`, `sessionTitle` and `suppressOriginalPrompt`
  (**verified**: hooks doc). A message cannot run a command (verified above). A mod's `session.receive` hook could act
  on a message, but the sender cannot be trusted (see A).

## The probe

Run on 2026-11-04 with the master's go, on a throwaway session of this worker's own:

1. A probe mod with a 5-second `$.clock.every` timer that reads `probe-io/request.json`, calls `$.session.compact` or
   `$.command.run({ command: 'clear' })`, and writes `result-<action>.json`. `claude plugin validate` passed. The mod
   and its output are in `D:/Development/Puppet-master-logs/carcare-platform/tmp/research-cc/`.
2. `claude --bg --name research-cc-probe --model haiku --effort low --tools "" --plugin-dir <probe-mod> "Reply with
   READY and remember the codeword BANANA-42."`, started from the claude-plugins checkout. The mod loaded and Claude
   Code wrote its 2.1.318 types into the mod folder.
3. The compact request returned `tokensBefore: 24266, tokensAfter: 6452`, and the transcript gained
   `compact_boundary {trigger: manual, preTokens: 24266, postTokens: 6452, durationMs: 5881}`.
4. The clear request returned `{ text: "" }`, and `claude agents --json` showed the new session id.
5. `claude stop 4e993a9a` and `claude rm 4e993a9a`, with no discard flag.

Not covered: a foreground window the user opened, a session with work in progress, and option B's tool.

## What was built

Option A shipped on 2026-11-04 as the mod `hooks/puppet-mod.js` with helper verbs `compact` and `clear`. How it works,
its files and what is still untested: [puppet-master.md](puppet-master.md#the-mod). What differs from the proposal
this page first made:

- **Off unless switched on, asking at start.** The plugin option `self_compact` is `ask` (default), `on` or `off`. A
  window the user opened asks once at start, with a suggested yes. A background worker never asks: the master passes
  `--self-compact` to `spawn` or `adopt`, after the user's yes. `off` beats the master's opt-in.
- **Clear is for finished workers only.** The helper refuses `clear` for a master, an analyst and any session without a
  finished job, and the mod refuses it again unless a role file says `worker`. It runs only while idle and is never
  queued.
- **The trigger is a request file, never a message.** The mod beats every 3 s into `heartbeat/<sessionId>.json`, so
  `list` shows a `mod` column.
- **No `claude plugin test` cases.** That runner gives a mod no `fs`, `process` or network, and the mod's whole
  protocol is files, so `tests/mod.test.mjs` drives it with a fake `$` under `node --test` instead.
- **The question runs only in a window.** A probe (below) showed `$.ui.ask` hangs a background worker, so the mod
  asks only when `claude agents --json` lists its own session as `interactive`.

### The second probe: the question in a background session

Run on 2026-11-04 with the master's go, on a throwaway `--bg` Haiku session with a mod that asked one question with a
20 s timeout:

1. With `--tools ""` the call rejected at once: `no tool named "AskUserQuestion" in this session`. That run is no
   evidence about a real worker. It did show `isInteractive: true`, `surface: "terminal"` and `surfaces: ["terminal"]`
   in a background session.
2. With `--tools "AskUserQuestion"` the call hung. The 20 s timer fired, but the dialog stayed open: `claude agents
   --json`, sampled every 3 s for 42 s, showed `state` `done` and `status` `waiting` throughout (without the dialog:
   `done` and `idle`). A worker that asked would sit behind a dialog nobody sees.
3. `claude stop <name>` failed on a session in `waiting` ("No job matching"); `claude stop <id>` worked.

## Decisions and what is still open

1. **Ship A as a mod inside the plugin?** Yes, off by default, switched on per machine or per session. The user,
   2026-11-04: "Yes, option, off by default (Recommended)".
2. **May the master clear a window on its own?** The user, 2026-11-04: "Compact freely, clear only between jobs and only
   for workers, do not clear master - also we can make this mode ask at start of session if to tuern it on default
   suggestion make it true but if not said explicit it wont run".
3. **A foreground test is still owed.** In a throwaway window with the plugin loaded from this checkout (`claude
   --plugin-dir <this checkout>/plugins/puppet-master`): the start question and each answer, a compact and a clear by
   the master, the master's own compaction, and that the mod keeps beating after a `/clear`. Until then the paste
   lines remain the fallback the helper prints.
4. **What Claude Code itself could add** to make the mod unnecessary: a SendMessage flag that lets a session's own user
   allow listed commands (`/compact <focus>`, `/clear`) from named peers. Today the docs rule this out for every
   message (**verified**: cross-session-messaging doc).
5. **A bug found on the way:** `IDLE_STATES` counts `state` `done` as idle even when `status` is `waiting`. `compact`
   and `clear` refuse `waiting` on their own; `cycle` and the checkout lock do not yet.

## Sources

- `claude --help`, `claude agents --help`, `claude attach --help`, `claude stop --help`, `claude respawn --help`,
  Claude Code 2.1.318 (**verified**: run 2026-11-04).
- Context7 `/websites/code_claude` and code.claude.com/docs pages: hooks, hooks-guide, settings-reference
  (`idleCompaction`, `autoCompactWindow`, `autoCompactEnabled`), cli-reference, sessions, agent-view,
  cross-session-messaging, remote-control, plugins/mods (overview, create, api, reference).
- The mods types Claude Code 2.1.318 wrote into the probe mod: `.claude-plugin/types/claude-code/index.d.ts`.
- `CHANGELOG.md` in anthropics/claude-code, entries 2.1.304 to 2.1.318.

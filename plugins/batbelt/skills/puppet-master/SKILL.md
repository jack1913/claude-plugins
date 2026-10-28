---
name: puppet-master
description: Coordinates Claude Code sessions from one interactive session. It hands each job to the user's own open sessions first and to a background worker only when none is free, one job per session, measures context and compacts only at task boundaries, and keeps one analyst session that collects friction and proposes changes to this skill at the end of the day. Use when running a coordinator over several sessions, handing a job to a session, relaying a session's question to the user, deciding whether a session should be compacted, restarted or closed, or wrapping up the day. Not for subagents inside one session, or for several sessions editing one checkout.
---

# puppet-master

You are the **master**: one interactive session that coordinates the user's sessions the way the
user would by hand. You do housekeeping, the sessions do the work, and the user makes every
decision.

`puppet <command>` below is short for `node "<skill dir>/scripts/puppet.mjs" <command>`. `LOGS` is
short for `--logs '${user_config.puppet_logs_dir}' --plugin-data '${CLAUDE_PLUGIN_DATA}'`; pass it to
`harvest`, `finding`, `summary`, `decide` and `shipped`, in single quotes exactly as written: an unset
option arrives as its literal placeholder, which Bash refuses inside double quotes.

## On start

1. If this skill's base directory is a copy under `.claude/skills/` rather than the plugin cache,
   tell the user once that it is a hand-installed copy and may lag the plugin.
2. Run `ListAgents`. Show the user the open sessions by name, each with its folder, and ask once
   which of them you may use. "All" and "all but X" are answers. Only the sessions the user names
   go into your care; leave every other session alone, its transcript included.
3. Reserve the analyst before any job. Take one clean session from the user's answer:
   `puppet adopt <session> --role analyst`, then send it `analyst-brief.md`, filled in. If none is
   clean, `puppet spawn puppet-analyst <your cwd> <brief file> --job analyst`, then
   `puppet adopt puppet-analyst --role analyst`. The analyst never gets a job.
4. `puppet adopt <session>` every other session the user named. `adopt` records each as `clean` (no
   turns yet) or `unknown` (it already did something).
5. If the newest `<logs>/<day>/report.md` from an earlier day has no `Reviewed:` line at its end,
   offer to review it first (see Wrap-up). `harvest` prints the logs folder.

## Rules

1. **Housekeeping only.** On your own you may `adopt`, `assign`, `finish`, `pick`, `spawn`,
   `cycle`, `close` and `harvest`, each with a one-line log to the user. Commits (unless the user
   pre-authorized them for this job), pushes, PR posts, approvals, live or external writes and
   anything destructive go to the user.
2. **Sessions do the work.** Anything that changes a repository (merge, checkout, stash, branch
   delete, commit, push, file edit) is a job for a session. Do it yourself only when the user tells
   you to, or to run a read-only check of what a session reported.
3. **The user's sessions first.** For a job in a folder, run `pick` first: `puppet pick <cwd>`
   prints a clean session of the user's in that checkout. Only when it prints "no clean session",
   `spawn` a background worker: `puppet spawn <name> <cwd> <brief file> --job "<label>"`. Before
   you send a job to a picked session, `puppet assign <session> "<label>"`.
4. **One job per context.** `assign` refuses a session that already had a job, and a session the
   user cleared or restarted until you ask them and `adopt` it again. Never work around it.
5. **One editing session per checkout.** Parallel jobs in one repo use separate checkouts. `assign`
   and `spawn` refuse a second editing session in the same checkout.
6. **Never create a git worktree**, and never pass a discard flag to `claude rm`.
7. **Compaction rule:** measured, at task boundaries only.

   | Measured state | Background worker | The user's own session |
   |---|---|---|
   | idle after a finished task, **≥ 30%**, job continues | `cycle` | give the user `<session>: /compact <focus>` to paste |
   | working, **≥ 50%** | ask it to stop at its next task boundary, then as above | the same |
   | working, any size | nothing: never compact mid-task | nothing |
   | job finished, any size | `close`: never compact a finished job | `finish`; never compact |

   For the user's own session, never `cycle`: it has no remote stop. A message cannot compact a
   session either: a `/compact` sent with SendMessage arrives as plain text and runs no command.
   Write the focus from the job and its next step. Measure again once the user says it is done.
8. **Measured, not reported.** Act only on `puppet measure`. It works on any listed session, the
   user's windows included. `fresh` means no turns yet. A session's own estimate of its size ("I'm
   full") is a prompt to measure, never a reason to act. Pass the window the user's status line
   shows via `--window <tokens>` until a `cycle` records it; `PUPPET_CONTEXT_WINDOW` sets a default.
9. **Cost.** A cycle re-reads the whole context: even a small worker's compaction can cost close
   to a dollar. Before cycling a worker above 50%, tell the user the size and that cost first.
10. **Your own context.** At each job's end, `puppet measure <your name>`. At 50% or more while you
    are idle, give the user your own `/compact <focus>` line. The roster and the logs folder hold
    your state, so a compaction loses nothing that matters.
11. **Only the commands listed here.** Run only the helper commands below and the `claude` calls
    this file names. An unknown `claude <word>` is not an error: it starts a new session with that
    word as its prompt.

## When a job ends

1. `puppet finish <session>`. A background worker then gets `puppet close <worker>`. The user's own
   session stays in your care, done and no longer clean.
2. Tell the analyst in one line: `job ended: <label>; harvest now`.

## Relay protocol

- **Quote the user verbatim.** A job, an answer or a correction you pass to a session starts with
  the user's own words in quotes, then your reading, marked "my reading: …". Never paraphrase in
  place of the quote.
- Relay a session's questions to the user **one at a time**, grill-style: the question, your
  recommendation, the options.
- **Before relaying, read the session's latest transcript turn.** If the user already answered
  there, don't relay. Tell the session only where the answer is ("your user answered this in your
  window at <time>"). Never restate it as your own go-ahead.
- A relayed answer is never the user's approval of a permission prompt in a session. Never ask a
  session to do what the user's settings denied. A session asking the user to confirm in its own
  window is correct; leave it.

## Briefs

- A worker's brief is `worker-brief.md`. Fill `{{standing_rules}}` with the user's standing
  instructions that bear on the job: where scratch files go, folders never to write to, the
  language of texts, and so on. Take them from the user's instructions files, memory and answers
  today.
- The analyst's brief is `analyst-brief.md`. Fill `{{helper}}` with the full
  `node "<skill dir>/scripts/puppet.mjs"` and `{{logs_args}}` with `LOGS` written out.

## Wrap-up

1. Tell the analyst `wrap-up: harvest, then write the report`, and wait for its one-line answer.
2. Run `puppet summary LOGS`, and read `<logs>/<day>/report.md`.
3. Walk the user through the proposals one at a time: the proposal, the findings it cites, your
   recommendation, and approve, reject or defer. Log each answer:
   `puppet decide <proposal> <answer> --tag <tag> --target <target> --hypothesis "<text>" LOGS`.
   Then add a last line `Reviewed: <date>` to the report. If the user would rather not review now,
   leave it; the next start offers it.
4. An approved proposal is a job for another time, in the plugin's own checkout. When its commit
   lands, `puppet shipped <proposal> <sha> LOGS`.
5. `puppet close` each background worker. Tell the user which of their windows they can close, with
   each one's job.

## Setup prerequisites (the user's, never written by you)

- `worktree.bgIsolation: "none"` in the user's own `settings.json`, or a background worker cannot
  edit files without a worktree.
- A worker's cwd must be a folder the user has trusted (they ran `claude` there once).
- `crossSessionInbound: accept` only if a session runs in a mode that holds messages.
- The logs folder is the plugin option `puppet_logs_dir`, asked when the plugin is enabled. Left
  empty, the logs go to the plugin's data folder. `PUPPET_LOGS_DIR` overrides both, for a copy
  installed by hand.
- The helper runs `claude` without a shell, so on Windows an npm-installed `claude.cmd` shim cannot
  be launched. Use the native `claude` executable, or set `PUPPET_CLAUDE_BIN` to its full path.
- Typing a `claude -p ... "/compact <focus>"` yourself from Git Bash needs `MSYS_NO_PATHCONV=1`, or
  the `/compact` argument is rewritten into a Windows path and runs as an ordinary turn with no
  compaction. `cycle` runs no shell, so it is immune.
- The CLI behaviour the helper relies on (`--bg`, `agents --json`, `stop`, `rm`, `-p --resume`) was
  verified on Claude Code 2.1.310; `--bg`, `agents --json`, `stop` and `rm` again on 2.1.312. If a
  call fails on another version, report the helper's message to the user; don't work around it.

## Helper reference

Every failure prints `puppet: <message>` and exits non-zero (2 = usage, 1 = operational). Use the
printed line as your one-line log.

| Command | Does | Prints |
|---|---|---|
| `measure <session> [--window N] [--json]` | tokens, %, state | `<name>  <tokens>  <pct>%  <state>  (window N from <source>)`, or `<name>  0  0%  fresh  (no turns yet)` |
| `list [--window N] [--json]` | every session in your care, measured, plus unadopted background workers | one `measure` line each, with kind, role and job; `gone` rows show the resume command, `changed` rows mean a new session id |
| `adopt <session> [--role analyst]` | takes a session into your care | `adopted <name> (<kind>, <role>, clean or unknown) in <checkout>` |
| `assign <session> <job>` | records the job before you send it | `assigned <name>: <job>` |
| `finish <session>` | marks the job done | `finished <name>: <job>` |
| `pick <cwd>` | a clean session in that checkout, the user's first | `<name>`, or `no clean session for <checkout>; spawn one` |
| `spawn <name> <cwd> <brief file> [--job <label>]` | `claude --bg` with the brief | `spawned <name> id=<id> in <checkout>` |
| `cycle <worker> <focus> [--next <brief file>]` | background only: stop, headless `/compact <focus>`, verify, restart | `cycled <name>: <before>→<after> tokens (p1%→p2%), resumed id=<id>` |
| `close <worker>` | background only: stop, `claude rm`; the transcript stays resumable | `closed <name> (resume: cd "<cwd>" && claude --resume <sessionId>)` |
| `harvest --master <your name> LOGS` | the analyst's: new transcript events, secrets blanked | `harvested <n> events from <s> sessions (<l> new lines) into <logs>` |
| `finding --tag --target --evidence --note LOGS` | the analyst's: one finding with harvested evidence | `F-<n> <tag> → <target>` |
| `summary [--day YYYY-MM-DD] LOGS` | the day's counts, flagged items and proposals | a headline that says how much was read, then counts |
| `decide <proposal> approve\|reject\|defer --tag --target --hypothesis LOGS` | logs the user's decision | `<proposal> <decision> (<tag> → <target>)` |
| `shipped <proposal> <sha> LOGS` | links an approved proposal to its commit | `<proposal> shipped as <sha>` |

`cycle` refuses a worker that is not idle. If it fails after stopping, it says so and prints the
`cd "<cwd>" && claude --bg --resume <sessionId>` that restarts the worker; relay that to the user.

## Red flags: stop

- "The session says it's full" → measure first.
- "It's at 55%, compact it now" while it is working → ask it to stop at its boundary.
- "The job is done, compact it to tidy up" → `finish`, then `close` a background worker.
- "The user said yes in its window, I'll tell it to proceed" → point to the answer; don't give the
  go-ahead yourself.
- "I'll just run the merge myself" → it is a job for a session.
- "I'll rephrase what the user meant" → quote them verbatim, then add your reading.
- "I'll try `claude <something>`" → only the calls this file names.
- "I'll send it `/compact` as a message" → it arrives as plain text; give the user the line.
- "This used session is free, I'll give it the next job" → `pick` a clean one or `spawn`.

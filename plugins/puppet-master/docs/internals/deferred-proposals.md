# Deferred proposals

Changes to puppet-master that the user could not or did not want to decide when they came up, kept with enough
context to be judged later without the transcripts. An entry gets in when the user answers "defer" at a wrap-up, or
parks an idea mid-day. It leaves when it is decided: approved and shipped (name the commit), or rejected (give the
reason). A decided entry moves to [Decided](#decided) at the bottom; it is never deleted.

Each entry keeps the analyst's own text: the proposal, its hypothesis, and every finding it cites, with the finding's
evidence verbatim. Evidence names a session (the first block of its id, or its name) and a transcript line, with the
time where the report gave one.

Names are neutralized, since this repository is public: session names become `backend-session-1`,
`backend-session-2`, `brain-session-1` and `config-session-1`; project folders become `<projects>\<name>`; the
analyst's logs folder becomes `<logs folder>`; the Claude Code config folder becomes `<config dir>`. A quote marked
"(names neutralized)" had only such a name replaced.

## Open

### P-20261125-1: check before you state

- **Date:** 2026-11-25 (analyst report of that day)
- **Target:** `worker-brief.md`
- **Home:** not applicable (the brief file)
- **Change:** add a "check before you state" line. The master verifies any state-of-the-world fact it writes into a
  brief (git tips, Docker present, clean tree, the shell that is permitted) with one command and names the shell
  route: Git Bash for deletes and git, with PowerShell possibly denied. For jobs that create VMs or images, the brief
  names the storage location rule.
- **Hypothesis:** fewer round trips and user questions over assumed environment facts and denied tools.
- **Backing:** 6 sessions: d3466bbc, feacae74, 97170858, 7f20c987, backend-session-1, brain-session-1.
- **Status:** deferred 2026-11-25 by the user: "note into docs for future analysis"

Findings cited:

- **F-2** (other, `worker-brief.md`): the brief stated the brain's commit from the session-start snapshot (2521911f);
  the worker found 6a18995b. Evidence d3466bbc:105.
- **F-5** (brief-missing-rule, `worker-brief.md`): b7's PowerShell `Remove-Item` on shallow.lock was refused by a deny
  rule, so the user ran it by hand. Evidence feacae74:114 (13:24, permission-denied), 59f1c32e:1729.
- **F-6** (other, `SKILL.md`): the datefix brief assumed Docker and a clean checkout, and each assumption cost the user
  a question. Evidence 97170858:93, :169, 59f1c32e:2001 ("i have no docker here, do you need it?").
- **F-7** (brief-missing-rule, `worker-brief.md`): the docker job started before the user's rule "VMs and images inside
  D:\VMs subfolders". Evidence 59f1c32e:2529, :2555 (14:15, master pause).
- **F-13** (brief-missing-rule, `worker-brief.md`): PowerShell was denied in a second session, the same gap as F-5.
  Evidence 7f20c987:126 (10:45, config-session-1 permission-denied), feacae74:114.

### P-20261125-2: one blocking question at a time, every ad-hoc question a task

- **Date:** 2026-11-25 (analyst report of that day)
- **Target:** `SKILL.md`
- **Home:** the reference for answering the user. Add one core line only: "ask each question as one blocking
  question, and give every ad-hoc question its own `T<n>` on the page".
- **Change:** put one-question-at-a-time (grill-me) and "every ad-hoc user question becomes a task on the live page"
  into the master's rules. Add a "question ids are never reused" rule.
- **Hypothesis:** the user stops having to repeat standing rules and can answer without the asks changing underneath
  them.
- **Backing:** master session only, but four separate user complaints or confusions.
- **Status:** deferred 2026-11-25 by the user: "note into docs for future analysis"

Findings cited:

- **F-4** (user-correction, `SKILL.md`): open asks were streamed, not blocked on. Evidence 59f1c32e:1616 (13:21, "you
  need to ask me in grill-me style block and wait, i cannt answer when it keeps changing").
- **F-9** (user-correction, `SKILL.md`): the ad-hoc tsql question got no task on the live page until the user said
  so. Evidence 59f1c32e:2973 (14:27, "add this tsql task into status tasks list - always do this with such
  questions").
- **F-15** (other, `SKILL.md`): question id A27 was used for two different questions. Evidence 59f1c32e:2563 (14:16,
  "A27 (Docker and D:\VMs)…"), :3158 (15:19, "A27 (date fix, Linux proof)…").
- **F-10** (other, `SKILL.md`): the user twice had to ask why tasks were waiting or stuck. Evidence 59f1c32e:3284
  (15:24, "T2-7 why we still waiting?"), :4104 (17:10, "now start t2/4/5 why thay stuck").

### P-20261125-3: read a session's state before clear, extend or dispatch

- **Date:** 2026-11-25 (analyst report of that day)
- **Target:** `SKILL.md`
- **Home:** the reference for session housekeeping (clear, extend, spawn). The core gets one line: "run `status`
  before `clear` or `extend`".
- **Change:** before `clear` or `extend`, the master reads the session's state; before dispatch it looks for a clean
  session for the directory and spawns if there is none. Also add a compaction trigger by size for the master (say
  when the context passes a stated threshold), and a "report stalled tasks and why, unprompted" step.
- **Hypothesis:** fewer refused helper calls and no user housekeeping or "why are we waiting" questions.
- **Status:** deferred 2026-11-25 by the user: "note into docs for future analysis"

Findings cited:

- **F-11** (helper-failed, `SKILL.md`): clear/extend was run on sessions in the wrong state, four times. Evidence
  59f1c32e:2953 and :3833 ("not at a task boundary (state busy); not clearing it"), :3541 ("--extend needs an active
  job; backend-session-2 has none (it is done)" (names neutralized)), :3935 ("config-session-1 has no active job"
  (names neutralized)).
- **F-12** (helper-failed, `SKILL.md`): dispatch went to a directory with no clean session, twice. Evidence
  59f1c32e:289 (11:38, "no clean session for `<projects>\brain-repo`; spawn one" (names neutralized)), :518 (12:02,
  same for `<projects>\review-repo`).
- **F-8** (user-did-housekeeping, `SKILL.md`): the user had to say "compact this window". Evidence 59f1c32e:2713, :2736
  (14:21, compact-manual 408437→34010).
- **F-10** (other, `SKILL.md`): the user twice had to ask why tasks were waiting or stuck. Evidence 59f1c32e:3284
  (15:24, "T2-7 why we still waiting?"), :4104 (17:10, "now start t2/4/5 why thay stuck").

### P-20261125-4: first-run setup asks for the logs folder and names the accepted models

- **Date:** 2026-11-25 (analyst report of that day)
- **Target:** `SKILL.md`
- **Home:** the reference for first-run setup (the core has one line)
- **Change:** ask the user for the logs folder, and the plugin paths, at the first puppet action of the day. Say which
  models the helper accepts, and that a Fable job goes through an existing Claude session.
- **Hypothesis:** no mid-day correction over the logs folder and no failed `--model fable` call.
- **Status:** deferred 2026-11-25 by the user: "note into docs for future analysis"

Findings cited:

- **F-1** (user-correction, `SKILL.md`): master started puppet work without asking for the logs folder. Evidence
  59f1c32e:447 and :464, 12:01-12:02, the user's turns "ok wait, lets start with defining plugin paths, why you havent
  asked for it?" and "`<logs folder>`" (names neutralized).
- **F-3** (user-correction, `SKILL.md`): `--model fable` is refused by the helper. Evidence 59f1c32e:1432 (13:12,
  "puppet: --model must be opus, sonnet, haiku or a claude-* id, got "fable""), :1461 (user: "use
  [backend-session-2] if you need cloude models" (names neutralized)).

### P-20261125-5: a worker stops and reports a classifier denial of a user-authorised action

- **Date:** 2026-11-25 (analyst report of that day)
- **Target:** `worker-brief.md`
- **Home:** not applicable
- **Change:** say what a worker does when the auto-mode classifier denies a user-authorised action: stop, report the
  exact denial to the master, and leave the work staged; the master then asks the user to run it with `!`.
- **Hypothesis:** a denied commit stays in one place and the user is told once.
- **Status:** deferred 2026-11-25 by the user: "note into docs for future analysis"

Findings cited:

- **F-14** (brief-missing-rule, `worker-brief.md`): the commit the user asked for was denied by the session's
  auto-mode classifier. Evidence 59f1c32e:4271 (17:16, "ok, commit this solution into repo as docs of optional
  usage"), 578b4875:768 (17:18, classifier-denied "[Destructive or Unwanted Actions] git commit -q -m "puppet-master
  docs: optional status line snippet…"").
- **F-5** (brief-missing-rule, `worker-brief.md`): b7's PowerShell `Remove-Item` on shallow.lock was refused by a deny
  rule, so the user ran it by hand. Evidence feacae74:114 (13:24, permission-denied), 59f1c32e:1729.

### P-20261125-6: the master hands verification to a session

- **Date:** 2026-11-25 (analyst report of that day)
- **Target:** `SKILL.md`
- **Home:** core, one line
- **Change:** state that the master hands verification (reading test totals, diff checks) to a session unless it is a
  single read command.
- **Hypothesis:** the master stays out of repository work.
- **Backing:** borderline, one session.
- **Status:** deferred 2026-11-25 by the user: "note into docs for future analysis"

Findings cited:

- **F-16** (master-did-the-work, `SKILL.md`, borderline): the master read ten test totals and checked three merge
  diffs itself, calling it "a housekeeping call". Evidence 59f1c32e:3768, :3803 (16:43-16:44, "I read your ten
  totals… myself", "I checked your claim myself").

## Flagged, not proposed

The analyst cannot propose a change to one of its own instruments, so it flags it instead.

### F-17: the analyst brief's logs folder placeholder (2026-11-25)

- **Instrument:** `analyst-brief.md`
- **Finding:** the analyst brief's helper lines carry the literal `${user_config.puppet_logs_dir}`. The replacement
  analyst's first harvest wrote 171 events and a stray F-1 to
  `<config dir>\plugins\data\puppet-master-jack1913\logs\2026-11-25`, not `<logs folder>`,
  until the folder was found in the master's event 485. That stray folder still exists; the analyst did not touch it.
  The master's wrap-up message did not name the folder.
- **Status:** flagged 2026-11-25; not yet decided.

## Decided

None yet. A decided entry moves here with its outcome: approved and shipped (the commit), or rejected (the reason).

# Giving a job

Read this before every `pick`, `assign`, `spawn` or `assign --extend`, and before you turn a design or a pasted issue into a job.

## Contents

- Rule 3 in detail: the user's sessions first
- Rule 4 in detail: one job per context
- Rule 5 in detail: write scopes
- Rule 12 in detail: every job names its tier
- A design to relay
- Chained jobs

## Rule 3 in detail: the user's sessions first

For a job in a folder, run `pick` first:
`puppet pick <cwd> --tier <tier>` prints a clean session of the user's in that checkout: one that
already matches the tier, or whose mod is on so `switch` can align it, first, and an opened window
before a background worker. On a `MISMATCH` where its mod is on, `switch` it to the tier (rule 12)
and give it the job. Only when it prints "no clean session", or a session with `MISMATCH` whose
mod is not on (rule 12), `spawn` a background worker:
`puppet spawn <name> <cwd> <brief file> --tier <tier> --job "<label>"`. `spawn` starts
it on the tier's model and effort and refuses without `--tier` or `--effort`. Before you send a
job to a picked session, `puppet assign <session> "<label>" --tier <tier>`.

## Rule 4 in detail: one job per context

When the user has asked to reuse sessions, a session whose job is finished takes the next
one with `assign --reuse`, which still refuses it at 30% or more of its window (300,000 tokens
of the 1M window): `clear` it first when its `list` row says `mod on` (rule 7), else give
the user its `/clear` line. More work for the job a session
holds goes to it with `assign <session> <job> --extend`, which keeps the active job and merges
the label and scope and keeps the job's git flag unless you pass `--git` or `--no-git`; a label
the job already has is not added again. A job you closed too early comes back with
`reopen <session>`, which undoes `finish`. A session that only read a brief and replied counts
as clean when you adopt it. A session the user renamed in its window keeps its roster record:
the helper carries it to the new name, so you never adopt it again. Adopting a session already in
the roster under the same session id keeps its job and state and only updates its role, window
and mod role: that is how you give a session adopted before the mod existed its role file, when
`clear` says the mod sees role none (`adopt <session> --role worker`). Never work around a
refusal, and never edit `workers.json` by hand.

## Rule 5 in detail: write scopes

A `--scope` folder may also be an absolute folder outside the checkout
(a temp plans folder): a job whose folders are all outside writes nothing in the checkout and
does not count against the lock; its brief allows read-only git at most. Write the scope into
the brief's `{{write_scope}}` line.
When `assign`, `pick` or `spawn` refuses because another job is editing the checkout, there are
two ways out: wait for that job to end (`finish` it once it reports done), or have named both
jobs' scopes when you assigned them, as above. A job added to a running one with `--extend`
widens it, so `--extend --scope` cannot narrow a job that holds the whole checkout. Never send
the brief anyway: a job with no roster record is one the helper cannot guard, and two jobs that
both commit needed your relay of "git is free" (2026-11-03).

## Rule 12 in detail: every job names its tier

- On `MISMATCH` where the session's mod is on, the helper prints "its mod is on: run
  `switch <session> --tier <tier>`". Run `puppet switch <session> --tier <tier>` yourself before
  you send the brief: no paste lines, no new worker. In one turn: `assign`, then `switch`, then
  send the brief, never the brief first: a session reading its brief is busy, and `switch`
  refuses it (2026-11-10). Tell the worker or the user "switched" only after the helper printed
  `switched <session> to <model> <effort>`. On `not at a task boundary` or `no mod heartbeat`,
  take the fallback in the next bullet (another window whose mod is on, `spawn` on the tier, or
  the paste lines) and tell the user the session runs on its launch model. The switch is that
  session's only: its mod
  sends the tier's model and effort on every main-loop request and writes no settings file
  (verified 2026-11-06 on a throwaway background session: the transcript's requests, settings
  hashes unchanged). Its status line keeps naming the launch model, with the mod's line
  `puppet-master: switched to …` under the prompt, and its own answer names the launch model, so
  check the switch by that line and by `puppet list --name <session>` after its next turn:
  `model` is the last request
  sent, and the mod column says `switched to <model> <effort>`. A switch outlives a `compact`
  and a `clear` (it moves to the new session id); `switch <session> --reset` takes the session
  back to its launch model. Your own switch is written once your turn ends.
- On `MISMATCH` where the mod is not on, take another opened window whose mod is on, else
  `spawn` a background worker on the tier (rule 3): `spawn` passes `--model` and `--effort` and
  writes no settings. Only when the user wants that window for the job, `assign` it and give
  the paste lines the helper prints after `MISMATCH`, before you send the brief:
  `<session>: /model`, then `s` on the `<model>` row, and `<session>: /effort`, then `s` at
  `<level>`. `s` switches that session only. Never give a typed `/model <name>` or
  `/effort <level>`: it saves the user's default for every new session (verified: docs,
  model-config, "Setting your model" and "Adjust effort level", 2026-11-05). You change a
  session's model only through `switch`, never its settings.
- A spawned worker starts on what `spawn` passed (`creative`: `opus` at `high`; `mechanical`:
  `sonnet` at `medium`; `--model` and `--effort` override), and the spawn line prints it. It is
  still `unchecked` until its first turn: confirm it as below.
- On `unchecked` (a fresh session, never a switched one: after a `switch` the session names its
  launch model), the brief asks the worker to state its model first. After
  that first turn, read its effort with `puppet list --name <session>`, never from the
  worker's word: a worker's own report of its effort is unreliable.
- On a machine that uses a proxy launcher (such as use-llm), the transcript shows the Claude
  model name, and the real backend shows only in the launcher's command line. Check it there,
  and never read the launcher's config.

## A design to relay

- **A design to relay** (a pasted issue turned into a job, or a worker's design recommendation)
  first gets a design pass: a read-only `creative` job for a session, brainstorming, plus context7
  where a library is involved. Show the user its short summary, then ask one question at a time.
  Put a worker's recommendation to the user as the worker's, next to the simplest change that
  would also work, never as your own.

## Chained jobs

When one job's output is another's input, brief the whole chain at once: the producer, the consumer
and the reviewer, each with the trigger that starts it (the brief's `{{handoffs}}` line). The producer
sends `FINAL: <path>` to the named consumer once an artifact stops changing. The consumer measures or
reviews only after that line, and starts on it without waiting for a new brief from you.

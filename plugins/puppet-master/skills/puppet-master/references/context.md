# Context and compaction

Read this before any `compact`, `cycle`, `clear` or `switch`, when a `measure` shows 30% or more, and for your own context at a job's end.

## Rule 7 in detail: the pause pattern, the mod and the user's own session

**The pause pattern** for a worker that is still busy when it passes the line (2026-11-04, four
times on one worker, 262k to 28k, 154k to 23k, 143k to 25k and 182k to 18k tokens). `compact`
refuses a busy session, which is right: a pause is how you reach a boundary. (1) Message the
worker: "pause at your next part boundary and say so". (2) After its "paused at <boundary>"
line, `SendMessage` it with `notify_when_idle`, and run `compact` only when the idle notice
arrives, never in the same turn as the pause request. Check its `list` row reads idle (state
`done`, not `waiting`). (3) `compact <worker>
<focus>`, the focus naming the job, the parts done and the next part. (4) Message it
"continue". A worker past about 150k tokens pauses and says so without being asked
(`worker-brief.md`). A worker you cannot reach for a boundary is left alone.

**The mod.** `compact`, `switch` (rule 12) and `clear` go through the plugin's mod inside the
session, which runs them once the session is idle: the helper writes a request file, never a message. They work only where
the session's `list` row says `mod on (<source>)`: the user said yes in that window, set
`self_compact` to `on`, or you passed `--self-compact` to `spawn` or `adopt` after the user's yes
(On start, step 2). `mod off (mode ask)` is a session the user did not switch on,
`mod off (mode off)` is the user's veto, `mod stale` a mod that stopped, and no `mod` at all a
session where the plugin is not loaded: use today's route there (`cycle` for a worker, nothing or
the paste line for a window). The three verbs refuse a session that is not idle or is waiting on a
dialog (your own `compact` and `switch` wait for your turn's end instead), and on any
failure print the paste line as the fallback: relay that to the user.
`clear` is for a worker whose job you `finish`ed, only between jobs, never queued. It refuses the
master, the analyst and any session with an active job, and the mod refuses them again. Never
`clear` your own session. `clear` re-adopts the worker under its new session id as `clean`.

For the user's own session, never `cycle`: it has no remote stop. A message cannot compact a
session either: a `/compact` sent with SendMessage arrives as plain text and runs no command;
use `compact`. Where the mod is not on, let its auto-compaction run; pasting compactions by hand
is the user's chore, not a safeguard. Give a `/clear` line only when a new job needs a different
model or a clean context. The user opts in to `/compact` lines once ("give me compact lines");
then write the focus from the job and its next step, and measure again once the user says it is
done.

## Rule 9 in detail: cost

`compact` through the mod runs in the live process and reads the prompt cache (one probe: 22,470
of 24,266 input tokens were cache reads), so it is the cheaper route; no whole-cycle figure for
it is measured yet.

## Rule 10 in detail: your own context

The roster and
the logs folder hold your state, so a compaction loses nothing that matters. When your own
`list` row says `mod on`, run `puppet compact <your name> <focus>` instead: the mod compacts you
once your turn ends, and the helper does not wait. That a master's own compaction runs this way
is not yet tested in a window: if `measure` shows no drop at your next turn, give the line.

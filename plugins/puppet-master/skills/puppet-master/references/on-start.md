# Start of the day

Read this first, when this skill starts, and do it. Read it again when the user names a new session for your care.
When the user tells you to take over from a master stopped by a usage limit, skip "On start" and
do "A stand-in master" below.

## Contents

- On start
- A stand-in master

## On start

1. If this skill's base directory is a copy under `.claude/skills/` rather than the plugin cache,
   tell the user once that it is a hand-installed copy and may lag the plugin.
2. Run `ListAgents`. Show the user the open sessions by name, each with its folder, and ask once
   which of them you may use. "All" and "all but X" are answers. Only the sessions the user names
   go into your care; leave every other session alone, its transcript included.
   Before you plan any role for the day, read each named window's model and effort
   (`puppet list --name <session>`; `fresh` before its first turn), so a plan is not redone once the
   user sees them (2026-11-03: two briefs withdrawn, three role swaps).
   In the same question, ask once whether the sessions may compact themselves through the plugin's
   mod (`self_compact`), have their model and effort switched for the job's tier (that session
   only), and a finished worker be cleared. Suggest yes; only an explicit yes counts,
   and silence is no. A yes lets you pass `--self-compact` to `spawn` and `adopt`; without it, no
   session of yours is compacted, switched or cleared by the mod.
3. Reserve the analyst before any job, but first ask whether another master on this machine already
   has an analyst the groups share: one analyst serves them all, and a second one made a third role
   swap on 2026-11-03. Take one clean session from the user's answer: first a clean session open in
   the puppet-master plugin's own checkout (step 2 shows each session's folder), since the analyst
   reports on this plugin; only when none is open there, another clean session the user named
   (2026-11-23: the analyst put in a project window again while the plugin's window was free).
   `puppet adopt <session> --role analyst`, then send it `analyst-brief.md`, filled in. If none is
   clean, `puppet spawn puppet-analyst <your cwd> <brief file> --tier mechanical --job analyst` (the
   analyst follows the worker default, Sonnet at medium: the user, 2026-11-24), then
   `puppet adopt puppet-analyst --role analyst`. The analyst never gets a job.
4. If another master already runs on this machine for other work (`adopt --role master` refuses
   you, or the user says so), run with a group: a short name for your project, such as your checkout's folder name.
   A master stopped by a usage limit is not another master: never start a group for it ("A
   stand-in master" below).
   Every `puppet` call then carries `--group <group>`, which gives you your own roster and your own
   logs folder (`<logs>/<group>`). Use the same group all day, and in the analyst's `{{helper}}`.
   `puppet adopt <session>` every other session the user named. `adopt` records each as `clean` (no
   turns yet, or one that only read a brief and replied, with no tool call) or `unknown` (it
   already did something). Then adopt yourself:
   `puppet adopt <your name> --role master --window <tokens>`, with the window your status line
   shows, so your own `measure` works.
5. Run `puppet list` and show the user the inventory: each session's model and effort (`fresh` before
   its first turn), yours included. Read it from the helper only (rule 13).
6. Run `puppet logs LOGS`. It prints the logs folder and, when there is one, the newest report of
   an earlier day without a `Reviewed:` line at its end: offer to review that report first (see
   Wrap-up). Your day's first status names everything from earlier days that still waits on the user
   (a pick, an approval, a review), so they never have to ask for yesterday's open items.
7. Open the live task page. It is one page per work set, not per day. The user, 2026-11-23: "this
   reports holds as long as we continnue each day same work list, new comes only when we start new
   set of work". When the day goes on with the same work set, keep the page you had; start a new
   one only for a new set of work: copy the template folder `skills/puppet-master/templates/task-page/`
   to a folder outside every checkout, fill `tasks.js` (its comment names every field), and give the
   user its full path. The page lists every task, from the start or added later, with their count;
   each with its state and its session. It holds the sessions list (each session in your care: its
   name, role, job, state and measured context), and for each open task, what it needs from the
   user: each ask as its own record in `asks[]`, with its id, its task and the data to decide on.
   Reports are written straight into `tasks.js` (`reports: [{label, path, pending}]`, HTML pages with
   full paths). A finished task whose report the user has not read is `pending-report`, not counted
   as waiting (A62, 2026-11-26: "new list item status, 'pending report' which tells me nothing waits
   there but it s thing to read"); its "Mark seen" button (A64: "button next to it marking showed")
   shows it done in that browser and gives the user a line for you, "seen on the task page: T22
   (11-26 23:40)"; on that line, or when the user says they read it, set it `done`. `sync-sessions.mjs`
   rewrites the sessions list from `puppet list` (from a copy outside the plugin, pass `--puppet <path
   to puppet.mjs>`). Run it in the same turn as every page change. Layout, as the user asked on
   2026-11-24: "list items like T39/41 when get so big they need a shortneing with 'show more' button
   + lets make it more area efficient - current data goes to one side and linked docs opens in side
   panel (new window only when clicked in specific button)", then "+ static pinned header with
   [Image #1] and opened sessions", then "sessions table needs ehaders, 3. tasks list table columns
   overlaps"; on 2026-11-26: "questions/tasks/jira tasks should be 3 separate tabs, previouse work
   status pages go to sidebar" and "all lists and tables must be ordered"; later on 2026-11-26: "all
   open questions 1 under other, tasks tab dont need sessions and filters (all filters goes to
   sidebar, right side details must be wider, would be gereat if it s box wide could be live
   changable". So: a pinned header with `waitingNow` over three tabs, Questions (every open ask as a
   full card, one under another, oldest first), Tasks (the tasks only) and Jira tasks; the filters
   with their counts, the sessions and the previous work sets in the sidebar (its collapsed rail's
   counts filter too); a report side panel, 640 px wide by default, its width dragged on its left
   edge and kept in the browser; every list sorted; tab, panel and its width kept on reload. Every
   open question goes into `asks[]` as its own record, so the page shows them all at once.

## A stand-in master

The user, 2026-11-26: "when limit hits i wont be able in any opened sessions to say that, i would
need to restart whole session under --resume, cant such new session take over when i say ponly for
time until normal master gets back?", and on the way back: "second master knows who s the main and
should pass it s work to it". So when the user tells you, in your window, to take over from a master
stopped by a usage limit, you are its stand-in: on those words only, and only until it is back.
That day a stand-in that started its own group split the jobs between two rosters, and for about
seven minutes two masters gave orders to the same workers.

1. Name the main master: the session the user named, the `master` row in `puppet list`. Use its
   roster: its group, or none when it runs without one. Never a `--group` of your own, never a
   second roster, and never `adopt` yourself as master: the role stays recorded on the main master.
2. Open its live task page. Your first write there goes first in `waitingNow`: "acting master:
   <you> since <time>, for <main master> (limited until <time>), on the user's words '<quote>'".
   The open asks and the standing answers on the page hold for you as they did for the main master.
3. In `puppet list`, read each row's `switched to`: a switch that breaks a model rule in the
   standing answers goes back with `switch` (the switch outlives its job and a `/clear`).
4. Send each active worker one line: "master is now <you> since <time>, for <main master> until it
   is back, on the user's words '<quote>'".
5. While you hold the role, keep the handover: what you changed in the roster, the asks you raised
   or got answered, the jobs you started or finished, the task-page rows you touched, each with its time.
6. When the main master is back (its message, or the user's word), finish the step you are in, start
   nothing new, and send it the handover. From then on, give no order: tell a worker that writes to
   you, in one line, to write to the main master. Close your line on the page with "until <time>".

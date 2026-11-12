# Start of the day

Read this first, when this skill starts, and do it. Read it again when the user names a new session for your care.

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
   swap on 2026-11-03. Take one clean session from the user's answer:
   `puppet adopt <session> --role analyst`, then send it `analyst-brief.md`, filled in. If none is
   clean, `puppet spawn puppet-analyst <your cwd> <brief file> --tier creative --job analyst`, then
   `puppet adopt puppet-analyst --role analyst`. The analyst never gets a job.
4. If another master already runs on this machine (`adopt --role master` refuses you, or the user
   says so), run with a group: a short name for your project, such as your checkout's folder name.
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

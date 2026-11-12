# Approvals, irreversible steps and outside services

Read this before you put an approval, an irreversible step, a `!` line or a step in an outside service to the user.

## The steps that need the user

- **A worker blocked by the user's uncommitted edits or by its permission mode:** ask the user
  once, with the exact command to run in their own window. Never hand it to another session: that
  would get round the denial. When the job plan has a step the worker's permission check is likely
  to deny (discarding a change: `git restore`, `git checkout -- <file>`, `rm -rf`, `git stash
  drop`), give the user that step as a `!` line for the worker's window before the job starts,
  with the reason. Under auto mode the classifier refuses an external write or push outright, and
  no prompt waits (2026-11-10, three times). When the user approves such a step (a Jira create or
  transition, `gh pr ready`, a push), put its exact `!` line for the worker's window in the
  approval question itself. After you hand the user any `!` line, `SendMessage` the worker with
  `notify_when_idle`, and tell the user when it moves on.
- **A step in an outside service you hold tools for** (the Railway tools, for one) is done by you
  or by a worker, once the user approved it where it counts (the decision in your window, then the
  prompt of an irreversible step). Only a step no tool can do goes to the user, with the click
  path read from the service's docs and the service's current state checked first (an asleep
  database hides its controls). "Where and what to click?" and "redeploy on your own" were the
  user's words for the opposite, 2026-11-03.
- **Before you hand the user a deploy or merge approval**, list what it leaves out: the commits on
  the branch that are not in it, and uncommitted work. The user then decides the contents once,
  before the approval, not after.
- **Before you recommend a route that depends on the user's device or setup**, check that their device or setup can do it (2026-11-06: wireless debugging on a phone too old for it).

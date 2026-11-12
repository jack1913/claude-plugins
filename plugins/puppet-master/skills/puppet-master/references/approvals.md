# Approvals, irreversible steps and outside services

Read this before you put an approval, an irreversible step, a `!` line or a step in an outside service to the user.

## The steps that need the user

- **A worker blocked by the user's uncommitted edits or by its permission mode:** ask the user
  once, with the exact command to run in their own window. Never hand it to another session: that
  would get round the denial. When the job plan has a step the worker's permission check is likely
  to deny (discarding a change: `git restore`, `git checkout -- <file>`, `rm -rf`, `git stash
  drop`), give the user that step as a `!` line for the worker's window before the job starts,
  with the reason. Under auto mode the classifier refuses an external write or push outright, and
  no prompt waits (2026-11-10, three times). An external write the user approves (a Jira create
  or transition, `gh pr ready`, a push) is planned as the user's `!` line for the worker's window from the start:
  put its exact line in the approval question itself, and never relay the yes for the worker to run
  it. Auto mode's classifier does not take a relayed message as the user's approval (2026-11-12: 23
  of 27 classifier blocks in workers came right after a relayed message). After you hand the user any `!` line, `SendMessage` the worker with
  `notify_when_idle`, and tell the user when it moves on.
- **A worker reports a refused command:** tell the user at once, in one line, which kind of rule
  refused what, then offer the user's `!` line for the worker's window, or skipping the step. Don't
  investigate it, and never ask a session to try another form or shell. The kind is in the text:
  - "Permission to use <tool> with command … has been denied." with no prompt: a deny rule in the user's own settings: it refuses that command in every permission mode, and in a session
    the user starts by hand too.
  - "… denied by the Claude Code auto mode classifier. Reason: [<category>]": auto mode's
    classifier, which reads only the user's own typed turns as approval; plan the step as a `!` line.
  - "… denied by a built-in Claude Code safety check": Claude Code's own check, not the user's
    rules (a folder at a drive root, for one).
  - "PreToolUse:<tool> hook error": a hook the user installed; name the hook's message.
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

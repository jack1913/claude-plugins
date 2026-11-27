# Approvals, irreversible steps and outside services

Read this before you put an approval, an irreversible step, a `!` line or a step in an outside service to the user.

## The steps that need the user

- **A commit, push or other git action a worker brings** (a restore, a pull, a merge): ask the user
  once, in one question with the exact commands. On yes, a session runs them (the one that brought
  them, or a clean one), or you run them in your own window when no session can, and you report the
  result: the commit hash, the pushed range (`<old>..<new>`) and a read-only `git
  ls-remote` check that the remote has it. The user, 2026-11-17: "note that if sessions come to
  master with commit/push or git actions you should have asked for approval, no need to show me
  manual commands if you can do it". Only when the run is refused, give the user its `!` line,
  with the kind of rule that refused it (below). Name the session that commits in the brief's
  `{{commit_handoff}}`, so the worker stops before the step and sends the commands to it.
- **After a push:** a session finds the CI run for the pushed commit and watches it in the
  background until it ends; you never run that wait in your own turn. Never report a push as passing
  from local checks alone. Report the result the moment it lands; when it fails, the session reads the
  failed-step logs and diagnoses before anything else. "Pushed" is not "landed".
- **A worker blocked by the user's uncommitted edits or by its permission mode:** ask the user
  once, with the exact command to run in their own window. Never hand it to another session: that
  would get round the denial. When the job plan has a step the worker's permission check is likely
  to deny (discarding a change: `git restore`, `git checkout -- <file>`, `rm -rf`, `git stash
  drop`), give the user that step as a `!` line for the worker's window before the job starts,
  with the reason. Under auto mode the classifier can refuse an external write or push outright, and
  no prompt waits (2026-11-10, three times). An external write the user approves (a Jira create
  or transition, a PR comment, `gh pr ready`, a release page, a publish; a push is a session's,
  above) is run by the session after the user confirmed both the text and the apply or publish on
  the task page (the user, 2026-11-27: "The session runs it after the user has confirmed texts and
  applying/publishing"). Put the exact text and command in the ask's facts. The classifier does not
  take a relayed message as the user's approval, so when it refuses the run, give the user its
  exact `!` line then (2026-11-12: 23 of 27 classifier blocks in workers came right after a
  relayed message). After you hand the user any `!` line, `SendMessage` the worker with
  `notify_when_idle`, and tell the user when it moves on.
- **Where questions and permission prompts live.** The user, 2026-11-04: "all worker questions
  and decisions come to the master's window; the owner sets each worker window to accept-edits once
  at job start; only irreversible steps (deletes, pushes, Railway writes) keep a permission prompt
  in the worker's window" (the accept-edits part is narrowed to a window outside auto mode,
  2026-11-27), and: "mobile app session keeps asking in its windows while it should be yours to
  mainly do it".
  Where a worker's step is an irreversible one (a delete, a Railway write), ask the user's decision
  here first; the worker then runs it, and the permission prompt that waits in its own window is the
  user's last click. Tell the user which window it is and what it waits for.
- **At a job's start,** check that the user's permission rules already cover the commands the job
  will run, and tell the user which ones they would need to allow; an answer in chat changes no
  permission state.
- **Verification is read-only.** Before any verification step that writes to a live target, ask the
  user and name the exact writes; tests on fixtures are the proof. If a live run is wanted, use the
  least-coupled target.
- **Before you hand the user any cleanup line,** read its target list. Include only what Claude
  Code, a plugin, a skill, an MCP server or a session's script made; leave system, vendor and user
  files out, however large or old.
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

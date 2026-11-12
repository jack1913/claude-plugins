# Writing a brief

Read this before you write or send any brief, the worker's or the analyst's.

## Contents

- Briefs
- A quote from an earlier day

## Briefs

- A worker's brief is `worker-brief.md`. Fill `{{standing_rules}}` with the user's standing
  instructions that bear on the job: where scratch files go, folders never to write to, the
  language of texts, and so on. Take them only from the user's instructions files, memory and
  answers today. A harness default, such as a session scratchpad, is not a standing rule. When the
  user hasn't said where scratch goes, it goes inside the repository or the job's folder.
  Restate each recurring constraint (local-only files, token handling) in every brief, word for
  word: it lives in `{{standing_rules}}`, never left to a summary or an earlier brief. When a
  tool writes outside the repository by default, name the flag that keeps its output in place
  (such as a screenshot tool's `--out <folder>`), not only the folder.
- Write every path in a brief with forward slashes: backslashes get lost on the way.
- **Every brief holds the template's lines itself, word for word**, through the brief's last line
  (`<!-- end of the puppet-master worker brief: keep this line -->`): a common file may add to a brief but never stands in for them
  (2026-11-06: a common file without the browser line, and a worker held the shared browser for
  hours). `spawn` refuses a brief file whose text lacks that last line.
- The brief's first line restates the deliverable's shape in the user's words ("visual concepts
  first, then code"); check the worker's one-line ack against it before it starts.
- Tell a worker to wait for "go" only while a user decision it depends on is still open; otherwise
  it starts right after its first reply (2026-11-05: a worker waited 13 minutes for "just go").
- Commands the user already approved for this job that are not edits (an install, removing a file
  the job itself made): list them in `{{approvals}}` so the worker asks you before it runs them and
  you can say yes at once. They may still prompt in its window: no brief lets a command past the permission check, only the user's settings or a click there.
- Before you brief a step in an outside service, check that its access path exists on this machine
  (keys, a CLI login), and prefer the path an earlier job already used (2026-11-04: `railway run`).
  Before you brief a job that needs a tool (an MCP server, Playwright, a connector), check the
  session that gets it has it: a spawned worker may not have the tools your window has. Else brief
  the fallback up front.
- Fill these lines in every worker brief:
  - `{{deliverable}}`: code, a document or a browser run. "Check it in the browser" is a browser
    run, not tests to write.
  - `{{local_state}}`: what the worker would otherwise stop to find out: uncommitted edits, untracked
    folders, the branch and whether it is pushed. Write "none known" when there is none.
  - `{{preconditions}}`: the services, tools, device state and shared tools the job depends on (the
    Docker engine up, a server answering, a phone signed in, the shared browser free), each with its
    state as you checked it just now and its one recovery command where you know one (`docker
    desktop restart`). Write "None" when it needs none. A live check names the host URL, the
    database and the test account, or the user's standing rule for the account, quoted with its
    date, never a password; when you cannot name them, ask the user before the job starts.
  - `{{approvals}}`: the irreversible steps the job will need (a delete, a push, a Railway write),
    each with its exact command, and "None" when it needs none. Ordinary writes are not listed:
    the user sets the worker's window to accept-edits once, when you send the brief (Relay
    protocol). For each irreversible command (a wipe, a volume removal, a force push), say who runs
    it: the user in their own window, or the worker only if its permission mode allows it; a step
    the user runs is a `!` line for the worker's window, given before the job starts (Relay
    protocol). The
    user's decision on it comes to you; the permission prompt waits in the worker's window. A
    relayed OK cannot lift a worker's permission mode.
- **Check what a brief asserts, just before you send it.** Re-read the decisions log and any state
  the brief states (approved or not, the branch, a dirty tree) instead of what you read at the
  start. Before a brief says a tool is or isn't installed, check it in the session. Build the steps
  on these checked facts, and name each step's precondition (what must exist or have run first).
  A git ref the brief names goes into `{{preconditions}}` for the worker to check first (`git
  ls-remote --heads origin <ref>`), or you check it with that read-only `git ls-remote`.
- Fill each conditional line of the worker brief, or delete it when it doesn't apply:
  - `{{write_scope}}`: the folders of `--scope`, the report files the job's tools write by default
    (a check's result file, for example), and "run no git command" with `--no-git`. With
    `--no-git`, `{{local_state}}` carries every git fact the job needs (tracked or not, the branch,
    pushed or not), since the worker cannot look.
  - `{{peers}}`: the sessions it may message directly; `{{owners}}`: who owns each shared file or
    format.
  - `{{handoffs}}`: whom it sends `FINAL: <path>` to, or whose `FINAL:` starts it.
  - `{{commit_handoff}}`: the session that commits this job's work, when it is not the worker.
  - `{{project_standards}}`: the project's own rules the job touches (an APK's name and its
    versionCode +1 per build, a doc number you reserved for this job, canvas images through
    `<img src>`).
  - `{{tier_check}}`: for a fresh session, "First, reply with your model name."
  - `{{self_compact}}`: for a worker you spawn with `--self-compact`: "The master may compact your
    context between turns and clear it once your job is finished. After your `FINAL:`, nothing may
    live only in your head: the report, the files and git hold it." Delete the line otherwise.
  - `{{test_tmp}}`: for a job that runs tests, a folder with no spaces in its path: `<logs>/tmp/<session>`
    (the logs folder `puppet logs LOGS` prints); when the logs folder has a space, another
    local folder with none, never at a drive root: Claude Code's own safety check will not let
    any session delete a folder there (2026-11-03: six of them stayed). Never offer a scratch path
    with a space as TMP. TMP and TEMP are for the test run's own files; build output
    (`--artifacts-path`, `bin/`) goes in a gitignored folder inside the repository, since tests
    that look for the repository root fail from a build elsewhere (84 did, 2026-11-03). You delete
    the temp folder at the job's end (When a job ends, step 4).
  - `{{decided}}`: values the user already fixed that a tool or plugin in the worker's window will
    ask for (a branch, a name, a target), each quoted with when the user said it.
  - `{{references}}`: the user's reference images. Compare like for like before showing anything:
    the same orientation, the same scale, measured ratios.
  - `{{fetch}}`: for research, the fetch tools allowed and the folder downloads go to.
  - `{{open_premises}}`: what earlier rounds fixed, and whether the user's "no limits" opens it too.
- The analyst's brief is `analyst-brief.md`. Fill `{{helper}}` with the full
  `node "<skill dir>/scripts/puppet.mjs"` (plus `--group <group>` when you run with one) and
  `{{logs_args}}` with `LOGS` written out. Fill `{{proposal_id}}` with `P-YYYYMMDD-n`, or
  `P-YYYYMMDD-<group>-n` with a group, so one group's ids never collide with another's;
  `decide` and `shipped` refuse an id that names another group.
- In both briefs, fill `{{master_name}}` with your own session name, the one `ListAgents` shows.

## A quote from an earlier day

- **A quote from an earlier day** goes into a brief with its date and what it was about. Applying
  it to new work needs the user's yes: "dont build apk" of 2 November meant canvas designs first,
  and reached a build brief on 3 November as a ban.

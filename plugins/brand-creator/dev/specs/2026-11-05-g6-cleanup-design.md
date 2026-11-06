# Group 6 design: `brand-creator cleanup`, old round folders out through git

Design date 2026-11-05, revised the same day after an adversarial review (see "Review" at the end). Release target: brand-creator
0.9.0. This is a working file, not a doc: it lives in `dev/specs/` while the work runs and moves to `docs/archive/` when it ships. It
holds no personal path, no e-mail address and no client name. The private brand that showed the problem is "the pilot brand" here.

## Why

Old rounds pile up in `rounds/` of the pilot brand. The guard (`scripts/guard.py`) blocks the agent's `git rm` and any `xargs` that
feeds a deleter in a brand project, so 0.8.0 wrote a procedure in `12-history.md` ("Method: cleaning old rounds") that ends in a `!`
line the owner types. That line removes files inside rounds by a list, and `git rm --pathspec-from-file` failed in the owner's shell.
The owner wants the plugin to do it, safely, with one yes.

## The owner's rules (approved direction)

1. Remove whole old round folders only. Never a file inside a kept round.
2. Never touch `history/`, `site/`, `assets/`, the latest round of each stage, or a round that something kept still references.
3. Refuse when any file to remove has uncommitted changes, so everything removed can be restored from git.
4. A dry run by default: it prints the plan and writes `qa/<date>-cleanup-plan.txt`.
5. `--yes` only after the owner's yes is recorded in DECISIONS, tied to the exact plan. Then the command runs `git rm` itself and
   writes `qa/<date>-cleanup-removed.txt`.

## What I read, and what it means here

- `bin/brand-creator`: one `case` line per subcommand; `py <script>` runs a locked PEP 723 script. `--help` needs no data folder.
- `scripts/CONTRACT.md`: exit codes 0 pass, 1 a gate failed or a refusal, 2 usage (bad flag, no project, a path outside the
  project, a symbolic link where none may be), 3 cannot run (a missing program). `confine()` keeps every write inside the project.
  `site approve` is the closest model: refusals in a fixed order, nothing written on any refusal, no report in `assets/_checks/`.
- `scripts/guard.py` decides per Bash segment by the first word after wrappers. `brand-creator ...` matches no branch, so it is
  allowed whatever it does. I checked it with `guard.check_bash` on a scratch project: `brand-creator cleanup --yes abc123`,
  `brand-creator --data "/x y" cleanup --yes abc` and `/a/bin/brand-creator cleanup --yes h` are allowed; `git rm -r -q -- rounds/r1`,
  `git --literal-pathspecs rm -q -- rounds/r1/a.png`, `git -C . rm --pathspec-from-file=...`, `... | xargs -0 git rm -q --`,
  `git checkout HEAD~1 -- rounds/r1` and `git restore --source=HEAD --staged --worktree -- rounds/r1` are blocked.
- Round kinds come from `<body data-board>` of `rounds/rN/board.html`, read by `scripts/boardlib/boardpage.py` (`read_page`,
  `page_kind`, `declared_round`): `style`, `pick`, `refine`, `motion`, `site-refs`, `site`. A `site` board also has
  `data-site-stage="hero|pages"` (`siteboard.stage_of`). `reset_rounds` lists the rounds of a full rejection; `g1s_round` is the
  style board the style pick was recorded against.
- `_common.list_rounds` reads a round folder with `ROUND_RE = ^r(\d+)$` and `int()`. In a Python `str` pattern `\d` is any Unicode
  digit, so `r03`, `r٣` (Arabic-Indic three) and `r３` (full-width three) are all read as round 3 (probe below). Two folders can then
  hold the same N.
- **Board-lint reads earlier rounds.** This is the risk the owner's rules do not name. `board_lint.check_motion` asks whether any
  earlier round holds a motion board (the first one must show exactly three variants); `siteboard.is_first` asks the same per site
  stage; `siteboard.references_board` takes the latest website references board before the site board; `siteboard.hero_boards` finds
  the hero card a pages board names in `data-hero`; `board_lint.style_rearmed` reads the rejected round and the new style board before
  a reset-round pick board. Remove those earlier rounds and a re-lint of a kept board can change its verdict. `check --refresh` re-runs
  a stale board lint by itself. `check_motion` is a closure inside `board_lint.main()` with the "first" test written inline
  (`board_lint.py`, the `first = not any(...)` line), so that test must be pulled out into a function before it can take a `rounds`
  argument.
- **`DECISIONS.md` is an input of a pages-board lint.** `siteboard.choices_rows` appends `DECISIONS.md` and `decisions/*.md` to the
  report's inputs, so any write to `DECISIONS.md` makes the lint report of a pages board stale (`check` then says "not verified", and
  `site approve` needs a current lint). `CONTRACT.md` says `DECISIONS.md` is "not read by any check"; that sentence is already wrong.
- `sitedata.load_site` raises `CliError(EXIT_FAIL)` when `site/site.json` is missing. Most projects have no approved site, so cleanup
  must not call it unless the file is there.
- `adaptlib/cascade.py` already reads "every project file minus a deny list" for `check --cascade`, plus the documents of
  `tools/cascade.json` `also` and of `FAMILY.md` `parent_docs` (`family_parent_docs`). That is the model for the sources below.
- `history/` holds frozen copies. Each has `FROZEN.md` with "frozen from rounds/rN". Its banners name rounds on purpose, so `history/`
  cannot be a source of references, or every frozen round would be kept forever.
- `check`: a page-check report of a page that is gone is listed by `--refresh` as gone and not judged; a motion or frames report whose
  proof is gone becomes a `warn` row ("move it to removed-<date>/"). So a cleanup can turn info rows into warnings. See open question 5.
- Git, checked in scratch repositories (git 2.55; the probes of this revision are in the scratch folder `g6design/revise-cleanup/`,
  `probe.py` and `probe-output.txt`):
  - `git update-index --assume-unchanged` hides an edited file from `git status --porcelain=v2`; `git ls-files -v` shows it with a
    lower-case tag.
  - With a clean `HOME` (no global ignore), a `.DS_Store` in a round is **untracked** (`?`); with a global ignore that lists it, it is
    **ignored** (`!`). The result depends on the machine.
  - `git status --porcelain=v2` prints paths relative to the **repository root** (`brand/rounds/r1/board.html`), while `git ls-files`
    run with `-C <project>` prints them relative to the project (`rounds/r1/board.html`). `git rev-parse --show-prefix` gives the
    difference (`brand/`).
  - When `rounds/` itself is a nested repository recorded as a gitlink, `git ls-files -s -- rounds` prints `160000 ... rounds`, and
    both `status` and `ls-files` print **nothing** for `rounds/r1`. A nested repository inside a round (`rounds/r2/sub`) shows as mode
    `160000` at `rounds/r2/sub`, and `os.walk` finds its `.git/` files.
  - A held `.git/index.lock` makes `git rm` exit 128 and remove nothing.
  - `git --literal-pathspecs rm -q -- "rounds/r1/*.png"` removed only the file named `*.png` and left `[1].png`, `-x.png` and
    `a b ż.png`; without `--literal-pathspecs` the same word is a pattern.
  - A path may hold a newline; `ls-files -z` prints it as is.
- `DECISIONS.md` is the append-only decision log (`templates/DECISIONS.md`: `## YYYY-MM-DD: <decision>`, then Gate, Decided, Why,
  Rejected, Consequences). No tool writes it today. Gates (`state --record G<n>`) are a fixed list and record one decision each, so
  a repeatable cleanup does not fit there.

## Command line

```text
brand-creator cleanup [--project DIR] [--keep rN]...                          the dry run (default): print the plan, write qa/<date>-cleanup-plan.txt
brand-creator cleanup [--project DIR] [--keep rN]... --record-yes CODE --said "<owner's words>"
                                                                              record the owner's yes to that plan in DECISIONS.md
brand-creator cleanup [--project DIR] [--keep rN]... --yes CODE               remove the planned round folders with git rm
```

- `CODE` is the plan hash: the first 12 hex digits that the dry run prints, or all 64. It is checked against the plan computed again
  on every run, never read from a file.
- `--keep rN` (repeatable) keeps one more round the owner wants kept. It is part of the plan, so the same `--keep` options are needed
  on all three runs; a different set is a different plan with a different hash.
- `--record-yes` and `--yes` are separate runs. Both at once is a usage error. `--said` is required with `--record-yes` and allowed
  nowhere else. `--said` is one line: a newline or any other control character in it is a usage error (exit 2); runs of spaces are
  collapsed to one, and an empty value after that is a usage error.
- No `--json` and no `--undo` in 0.9.0 (see "What can wait").
- Script `scripts/cleanup.py` with its lock (standard library only), dispatched as `cleanup) py cleanup.py "$@" ;;`. The
  rules that classify rounds and find references live in `scripts/boardlib/rounds.py` (one module, so tests and a later `check` row
  can use the same reading). The usage text goes under "project" in `bin/brand-creator`.

## The plan: rounds, stages and the keep-set

A **round** is a directory `rounds/r<N>/` (`_common.list_rounds`). Everything else in `rounds/` is never touched and never removed.
Step 6 refuses a round folder whose name is not `r` followed by ASCII digits with no leading zero (`r0`, `r12`; not `r03`, `r٣`), so
each N names exactly one folder.

### Stage of a round

Read `rounds/rN/board.html` with `boardpage.read_page`; `page_kind` and, for `site`, `siteboard.stage_of`:

| Board | Stage |
| --- | --- |
| `data-board="style"` | style |
| `pick` or `refine` | mark |
| `motion` | motion |
| `site-refs` | site-refs |
| `site` with `data-site-stage="hero"` | site-hero |
| `site` with `data-site-stage="pages"` | site-pages |
| no `board.html`, a page that cannot be read, no kind, a kind this version does not know, a `site` board with no known stage, or a `data-round` that is not N (a copied page) | unknown |

The **latest round of a stage** is the round with the highest N in that stage. An **unknown** round is always kept: the command
removes only rounds it can place.

### The keep-set

A round is kept when any rule below holds. The rules run to a fixed point: a kept round is a source of references, so a round it
references is kept too, and so on. Each kept round carries every reason found, with the file and line, for the plan.

1. **Latest of its stage.** The highest N of each stage. The highest round of all is always one of them, so the guard's "latest
   round" and the next round number (`max + 1`) do not change.
2. **Unknown kind.** As above.
3. **The owner's `--keep`.**
4. **Board-lint context.** For each kept board, the earlier rounds its lint reads:
   - a motion board that is not the first motion board: the first motion board is kept (the "first" test of `check_motion`);
   - a site board that is not the first of its stage: the first site board of that stage is kept (`siteboard.is_first`);
   - a site board: the round `siteboard.references_board` returns for it;
   - a pages board: the hero board that holds the card its `data-hero` names (`siteboard.hero_boards`, the first match, as `hero_row`
     takes it);
   - a pick board in a round of `reset_rounds`: the rejected round and the style boards `style_rearmed` reads.
   After the keep-set is final, the command checks that each of these questions has the same answer on the kept rounds as on all
   rounds (see "Lint context check"). This needs `rounds` as an optional argument (default `list_rounds(project)`, so board-lint is
   unchanged) of five functions: `is_first`, `references_board`, `hero_boards`, `style_rearmed`, and a new
   `board_lint.first_motion(project, rnd, rounds=None)` pulled out of the `check_motion` closure, which then calls it.
5. **State keys.** `g1s_round` in `BRAND-STATE.md` (board-lint trusts it), when it is set. `site/site.json` `round` (the pages board
   of the approved site), **only when `site/site.json` exists**; it is then read through `sitedata.load_site`, so a file that cannot be
   read or is not a JSON object stops the run with that function's message. A `round` or `g1s_round` that is present but not a whole
   number (a JSON `int` that is not a `bool`, 0 or more; in `BRAND-STATE.md` ASCII digits) stops the run (exit 1, named:
   `site/site.json: round is "3a", not a whole number; cleanup does not guess which round the approved site came from`). A project
   with no `site/` cleans normally.
6. **Text references in the sources** (below). In each source file, every match of the reference pattern keeps round N, and so does
   every relative URL that resolves into `rounds/rN/`: in `.html`, `.htm`, `.svg` and `.css` files through `sitedata.urls_in` (the
   same reading `site approve` uses), in `.md` files through Markdown link and image targets and `src`/`href` attributes. Each URL is
   percent-decoded before it is resolved. In a `.json` file the pattern is matched on the raw text and on every string of the decoded
   document (so `rounds\/r3` written by a JSON encoder counts either way). A symbolic link among the sources whose target resolves
   into `rounds/rN/` keeps round N; the link is not followed for reading.

   The reference pattern, ASCII and case-insensitive (on the default macOS disk `ROUNDS/R3` loads the same files):

   ```text
   rounds(?:\\/|\\\\|/|\\|%2f|%5c)r([0-9]+)(?![0-9])
   ```

   It reads `rounds/r3`, `rounds\r3`, the JSON-escaped `rounds\/r3` and `rounds\\r3`, `rounds%2Fr3`, `ROUNDS/r3` and `rounds/R3`, and
   not `roundsr3`, `rounds//r3` or a non-ASCII digit (probe `probe_regex.py`, 13 cases, 0 failures). It also matches inside a longer
   word (`backgrounds/r2`): that keeps a round too many, which is the safe side.
7. **Relative paths between rounds.** In every file of a kept round, any `(\.\./)+r\d+/` (also with `\`, case-insensitive, as
   written, also inside a `<script>` string) is resolved against the file's folder; landing in `rounds/rN/` keeps round N. Rule 6
   alone would miss `../r3/mark.svg`.
8. **Report inputs.** Every `assets/_checks/**/*.json` report and every `capture.json` outside the candidate rounds. Its subject is
   `page` (board-lint), `run.target.page` or `target.page` (page-check), `proof` (motion, frames) or `source.page` (capture). A report
   whose subject lies in a round that would be removed pins nothing: it is a report of removed work. Any other report pins every round
   that an `inputs[].path` lies in. A report with no subject this version knows pins by its inputs too.

**Sources for rules 6 and 7: every file of the project, except the places below.** The first draft listed the sources one by one;
that missed `tray/tray.json` (a state's master is a path), `qa/states.json` (state sets are paths), `.design/`, `tokens/` and
`FAMILY.md`'s `parent_docs`. A list of exceptions fails safe instead: a new kind of file is read until someone decides it should not
be. This is the reading `check --cascade` already uses (`adaptlib/cascade.py`). Not sources:

| Not a source | Why |
| --- | --- |
| `.git/`, `node_modules/` | git's own store, and third-party code (as the cascade skips it) |
| `history/` | frozen copies name their round on purpose |
| any folder whose name starts with `removed-` | dated copies of what `collapse` or an emitter retired |
| the candidate rounds | they are what would go; a kept round is a source (rule 7, and rule 6 on its text) |
| `assets/_checks/**/*.json` | read by rule 8 instead, which knows a report of removed work pins nothing; other files in `assets/_checks/` (the logo sheet, the guide overlay) are sources |
| `qa/*-cleanup-plan*.txt`, `qa/*-cleanup-removed*.txt` | cleanup's own records name every round; the rest of `qa/` is a source |
| `brief/canvas-round-*.md` | the drawing brief of a round names that round and the round it started from; it describes how a round was drawn, not a use of its files, and it outlives the round, so as a source it would keep every round ever briefed. `brief/BRIEF.md` is a source |

`research/` is a source now (the first draft left it out with no reason; it holds the research before the rounds and rarely names
one, so reading it costs little and keeps the safe side). Outside the project: the documents `tools/cascade.json` lists in `also` and
the `parent_docs` of `FAMILY.md` (as `check --cascade` reads them), read only.

**Which files are read, and how.** A file is read as text unless its first 8 KiB hold a NUL byte (a PNG, a font, a `.DS_Store`): no
suffix list, so `.webmanifest`, `.xml`, `.ts` and `.cjs` are read too. Text is decoded as UTF-8 with `errors="surrogateescape"`, so a
`.csv` exported in cp1250 is still searched (the pattern is ASCII) instead of stopping the run. What still stops the run (exit 1,
named), so that nothing is skipped in silence: a source that cannot be read at all (permission, I/O), a cascade or family document
that is missing, a `.json` source or report that does not parse (its raw text alone could miss an escaped path), and a `site/site.json`
or state key as in rule 5.

**Candidates** are the rounds that are not kept. The plan removes each candidate folder whole, and nothing else.

### Lint context check

For each kept board, compute with the functions board-lint uses: is it the first motion board (`first_motion`), is it the first site
board of its stage, which round is its references board, which hero board holds its `data-hero` card, and the `style_rearmed`
result. Compute once over all rounds and once over the kept rounds. Any difference is exit 1, nothing written: `cleanup would change
how board-lint reads rounds/r<N>/board.html (<the question>): this is a bug in cleanup's keep rules; keep r<M> with --keep and report
it`. Rule 4 should make this unreachable; the check is the net, and the test suite drives it with a rule removed.

For `style_rearmed` only the `ok` part is compared: its detail names every earlier style round it did not count, so the text changes
when an uncounted one goes even though the verdict does not. The same holds for `hero_row`'s detail, which lists the hero boards.

## Order of checks and refusals

Nothing is written on any refusal. The first failing step ends the run, except steps 9a and 9b, which each list every problem they
find (up to 20, then "and N more").

| Step | What | Exit | Message (start) |
| --- | --- | --- | --- |
| 1 | arguments: unknown flag; `--yes` with `--record-yes`; `--said` without `--record-yes`, or with a newline or another control character, or empty; `--keep` that is not `r<N>` or names no round folder; `CODE` not 12 to 64 hex digits | 2 | argparse's message, or `--keep r9: there is no rounds/r9/`, or `--said must be one line of the owner's words` |
| 2 | the project (`find_project`) | 2 | `no brand project found; pass --project` |
| 3 | `git` on PATH | 3 | `cannot run: git not found on PATH. cleanup removes rounds through git so they can be restored. Install git.` |
| 4 | the project is in a git work tree (`git rev-parse --show-toplevel`) | 1 | `refused: <project> is not in a git repository, so a removed round could not be restored. Commit the project first, then run cleanup again.` |
| 5 | git can restore: HEAD exists; no merge, rebase, cherry-pick, revert or bisect in progress; `rounds/` is not a repository of its own (a `rounds/.git` entry, or `git ls-files -s -- rounds` printing mode `160000` at `rounds`) | 1 | `refused: nothing is committed yet` / `refused: a rebase is in progress in <repo>; finish it first` / `refused: rounds/ is a git repository of its own (a submodule or a nested .git), so the project's git cannot restore it` |
| 6 | layout: `rounds/` is a symbolic link, or a round folder is one; a folder `list_rounds` reads as a round whose name is not `r` + ASCII digits without a leading zero | 2 | `rounds/r3 is a symbolic link: cleanup removes real round folders only, and a link can lead out of the project` / `rounds/r03 is read as round 3: name round folders r<N> with no leading zero and ASCII digits, then run cleanup again` |
| 7 | sources readable, state keys whole numbers (the keep-set is computed here); lint context unchanged | 1 | `cannot read book/chapters/x.md: ...` / the rule 5 message / the lint context message above |
| 8 | nothing to remove (no `rounds/`, or every round kept) | 0 | `nothing to clean: every round is kept` with the keep list; no file written |
| 9a | candidate contents on disk (walked with `os.walk`, links not followed): a symbolic link, a FIFO, socket or device | 2 | `rounds/r2/img is a symbolic link: ...` |
| 9b | candidate git state, and the disk against git: an untracked or ignored file other than a file named `.DS_Store`; a modified, staged, deleted, renamed or conflicted file; an assume-unchanged or skip-worktree file; a submodule (mode `160000`) or a `.git` entry anywhere under a candidate; a regular file on disk that is neither a tracked file of the plan nor a `.DS_Store`; a candidate with no tracked file | 1 | `refused: 3 file(s) in the rounds to remove are not committed as they are, so they could not be restored:` then one line each, `modified: rounds/r2/board.html`, `not known to git: rounds/r2/sub/.git/HEAD` |
| 10 | dry run: print and write the plan | 0 | the plan |

When 9a finds anything, the run exits 2 with 9a's list and 9b is not run; otherwise 9b decides.

Git state is read with `git status --porcelain=v2 -z --untracked-files=all --ignored=matching -- <candidates>` and
`git ls-files -v -s -z -- <candidates>` (the lower-case tag of assume-unchanged, `S` of skip-worktree, mode `160000` of a submodule).
`status` prints paths from the repository root, `ls-files` from the project: every status path is taken relative to the project by
removing the prefix `git rev-parse --show-prefix` prints (a status path without that prefix is a bug and stops the run), so the two
lists, the walk and the post-conditions compare the same strings. Every git call runs with `-C <project>`, `--literal-pathspecs`,
`stdin` closed, no shell, and an environment **without any variable whose name starts with `GIT_`**, so a variable left in the shell
(`GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_COMMON_DIR`, `GIT_CONFIG_COUNT` and `GIT_CONFIG_KEY_*`, `GIT_CONFIG_PARAMETERS`,
the `GIT_*_PATHSPECS` variables, and any added later) cannot point git at another repository or change its configuration.

A file named `.DS_Store` counts the same whether git calls it untracked or ignored, so the plan does not depend on the machine's
global ignore.

`--record-yes CODE --said "..."`, after steps 1 to 9b:

| Step | What | Exit | Message (start) |
| --- | --- | --- | --- |
| 11 | a plan file in `qa/` holds this plan hash (the owner was shown this plan) | 1 | `no plan with code <CODE> was shown: run brand-creator cleanup first and show the owner the plan` |
| 12 | `CODE` matches the plan computed now | 1 | `the plan changed since it was shown (now <new code>): show the owner the new plan and ask again` |
| 13 | `DECISIONS.md` exists | 1 | `DECISIONS.md not found: the owner's yes is recorded there (templates/DECISIONS.md)` |
| 14 | the entry as it would be written holds no round reference (rule 6's reading run on the entry text) | 1 | `the owner's words name rounds/r2/a.svg; DECISIONS.md is read for references, so this entry would keep r2 and change the plan. Record the words without the path (a round named as "r2" is fine)` |
| 15 | an unused entry for this hash exists already | 0 | `the owner's yes to plan <CODE> is recorded already (DECISIONS.md, <date>)`; nothing written |
| 16 | append the entry | 0 | `recorded the owner's yes to plan <CODE> in DECISIONS.md. A pages-board lint lists DECISIONS.md, so run brand-creator check --refresh after the removal` |

`--yes CODE`, after steps 1 to 9b:

| Step | What | Exit | Message (start) |
| --- | --- | --- | --- |
| 11 | `CODE` matches the plan computed now | 1 | `the plan changed since the owner said yes (now <new code>): show the owner the new plan and ask again` |
| 12 | `DECISIONS.md` holds an entry with `Cleanup plan: sha256:<this hash>` | 1 | `the owner's yes to plan <CODE> is not recorded: show the plan, ask, then brand-creator cleanup --record-yes <CODE> --said "<their words>"` |
| 13 | no `qa/*-cleanup-removed*.txt` with `status: complete` names this hash (a record with no status line counts as complete) | 1 | `the yes to plan <CODE> was used on <date> (qa/<file>): a new removal needs a new plan and a new yes` |
| 14 | steps 9a and 9b again, right before removing | 2 or 1 | as step 9a or 9b |
| 15 | `git rm`, in chunks | 1 on a failed chunk | see "Removing" |
| 16 | after: the post-conditions | 1 | `cleanup removed the files, but <what differs>: restore with <undo line>` |

## The dry run

It prints, and writes the same text to `qa/<date>-cleanup-plan.txt` (`today()`, so `BRAND_CREATOR_TODAY` applies). A second dry run on
the same day overwrites that day's plan file only when its bytes change; the file is a view, and the hash is always computed again.

```text
brand-creator cleanup plan
project: <slug>
date: 2026-11-05
head: <commit> (removed files are restored from it)
plan: sha256:<64 hex>   code: <12 hex>

keep (6 rounds):
  r0   style       latest of its stage
  r3   refine      referenced: book.html:212 (rounds/r3/Ledger/mark.svg); DECISIONS.md:44
  r9   motion      first motion board (board-lint of r12 reads it)
  r12  motion      latest of its stage
  r14  site-pages  latest of its stage; site/site.json round
  r7   unknown     no board.html: cleanup removes only rounds it can place

remove (5 rounds, 412 files, 38.2 MB):
  r1   pick        34 files, 2.1 MB   frozen in history/2026-10-01-approved-board/
  r2   refine      51 files, 4.0 MB   not frozen: git is its only copy
  ...

files to remove (git blob, mode, path):
  <blob> 100644 "rounds/r1/board.html"
  ...
not in git, deleted with its folder and not part of the code: "rounds/r1/.DS_Store"
other staged changes in the repository: 2 (they will be in the same commit)
reports of removed work (left as they are): assets/_checks/page-check/rounds-r2-ledger-index-1a2b3c.json, ...

To remove: the owner says yes to plan <code>, then
  brand-creator cleanup --record-yes <code> --said "<their words>"
  brand-creator cleanup --yes <code>
```

The plan text names `rounds/rN` paths; it sits in `qa/` under a name that is never a source. Each file path is written as a JSON
string (`json.dumps`, `ensure_ascii=False`), so a name with a space, a quote or a newline stays one readable line.

**The plan hash** is sha256 over this canonical text, UTF-8, `\n` line ends:

```text
brand-creator cleanup plan v1
<slug>
keep-option r4
remove r1
remove r2
file <blob> <mode> "rounds/r1/board.html"
```

`keep-option` lines sorted, `remove` lines sorted by N, `file` lines sorted by path bytes, each path a JSON string, so no path can
read as two lines or as another kind of line. The blob is the index's (`ls-files -s`), which equals HEAD's because step 9b refuses
anything staged or changed. So a changed set of rounds, a changed `--keep`, or a file whose content changed and was committed again,
gives a new hash and needs a new yes. HEAD is not in the hash: a commit somewhere else in the repository does not change what is
removed. The reasons are not in the hash either.

`.DS_Store` files are **not in the hash**, by path or by bytes: Finder writes or rewrites one whenever the owner opens a round, and
that must not turn the yes into "the plan changed". They are listed in the plan for information, listed again right before they are
unlinked, and the removed record names the ones that were unlinked.

## The owner's yes

The skill shows the plan (kept rounds with their reasons, removed rounds with files, size and frozen-or-not, the code), asks, and
runs `--record-yes` with the owner's words. The command appends to `DECISIONS.md`, in the template's form:

```markdown
## 2026-11-05: clean old rounds (remove r1, r2, r4, r5, r6)

- Gate: none (cleanup of old rounds)
- Decided: remove the round folders r1, r2, r4, r5, r6 (412 files), committed in git at <short head>
- Why: <the owner's words, as given to --said, one line>
- Rejected: keeping every round
- Consequences: the plan is qa/2026-11-05-cleanup-plan.txt; what was removed and how to restore it goes into qa/<date>-cleanup-removed.txt
- Cleanup plan: sha256:<64 hex>
```

The entry never holds a round reference, because `DECISIONS.md` is a source: an entry that referred to a round would keep it, the
plan hash would change at once, and `--yes` would refuse in a loop. The generated lines name rounds only as `r1`, which the pattern
does not read. The owner's words are free text, so step 14 runs rule 6's reading on the whole entry before it is written and refuses
when it finds a reference; `--said` is one line, so it can never start a line of its own such as `- Cleanup plan: ...`. Tests hold
both.

**Side effect on a lint.** Appending to `DECISIONS.md` makes the lint report of any pages board stale (it lists `DECISIONS.md` as an
input), so `check` calls it "not verified" and `site approve` would refuse until it is linted again. The command says so, and the
skill runs `brand-creator check --refresh` after the removal (it re-lints a stale board). The `CONTRACT.md` sentence that
`DECISIONS.md` is "not read by any check" is corrected in the same change.

`--yes` finds the entry by its last line (`- Cleanup plan: sha256:<hex>` at the start of a line under a `## ` heading). **One time:** a
removed record with `status: complete` carries the hash, and `--yes` refuses a hash such a record holds. A failed run does not use the
yes (see "Removing"). If the owner restores the rounds after a complete run and runs cleanup again, the plan has the same hash and
`--yes` refuses it. As designed, a second entry for the same hash does not help either, so a second removal needs a changed plan
(open question 6 asks whether that is too strict).

**What this protects, honestly.** The hash ties the yes to the exact files. It cannot prove the owner said yes: the agent can run
`--record-yes` by itself, as it can run `state --record` or `names --yes`. What makes a wrong run harmless is that only committed,
unchanged files are removed, the removal is staged and never committed, and the undo is one line.

## Removing

- Paths are the exact `file` lines of the plan, never a folder, a pattern or a list read from a file. Each call is
  `["git", "-C", <project>, "--literal-pathspecs", "rm", "-q", "--", *chunk]` through `subprocess.run` with a list and no shell.
  No `-r` (every path is a file), no `-f` (git's own check of changed files stays on), no `--ignore-unmatch` (a missing file fails).
- Chunks of at most 200 paths and 64 KiB of path bytes, in path order. A failed chunk stops the run: the record is written with
  `status: failed at chunk <k> of <n>: <git's message>`, the chunks done and the one that failed, the undo line is printed, exit 1.
  A held `index.lock` fails the first chunk with nothing removed (probe); a later chunk can fail after earlier ones were staged.
- Then the `.DS_Store` files in the candidate folders are listed again (`os.walk`, links not followed; only regular files named
  exactly `.DS_Store`) and unlinked, and each candidate folder that is now empty is removed bottom-up with `os.rmdir`. A folder that
  is not empty stays and is named (it should not happen after step 9b).
- Nothing is committed. The removal is staged in the index for the owner to commit.

**Post-conditions** (step 16): every candidate folder is gone; `git status --porcelain=v2 -z -- rounds` (paths taken relative to the
project as above) shows each planned file as a staged deletion and no other change under `rounds/` that was not there before;
`verify_history(project)` gives the same list as before the run. Any difference is exit 1 with the undo line, and the record says
`status: failed: post-conditions (<what differs>)`.

**A failed run does not use the yes.** Only `status: complete` does. This is safe: after a failed run some planned files are staged
as deleted, so step 9b refuses until the owner restores them with the undo line; once restored, the plan computes to the same hash,
which is exactly what the owner said yes to, so `--yes` with the same code may run again.

**The removed record** `qa/<date>-cleanup-removed.txt` (`-2`, `-3` when one exists that day; never overwritten):

```text
brand-creator cleanup: removed
date: 2026-11-05
status: complete
plan: sha256:<64 hex>
head before: <full commit>
yes: DECISIONS.md, "## 2026-11-05: clean old rounds (remove r1, r2, r4, r5, r6)"
removed rounds: r1 r2 r4 r5 r6
removed files: 412 (staged with git rm, not committed)
deleted, not in git: "rounds/r1/.DS_Store"
restore: git -C '<project>' checkout <head before> -- rounds/r1 rounds/r2 rounds/r4 rounds/r5 rounds/r6

<blob> <mode> "<path>"
...
```

The project path in the restore line is quoted with `shlex.quote`, so a `$`, a backtick or a `"` in it is not expanded when the owner
types the line (probe: a path holding `"brand"`, `$HOME` and a backtick command comes out in single quotes). The round folders need no quoting: step 6
allows only `r` + ASCII digits.

**Undo.** `git checkout <head before> -- <the round folders>` restores the index and the files as they were, before the owner commits
and after. After a commit that holds only the cleanup, `git revert <commit>` works too. `.DS_Store` files do not come back. The guard
blocks `git checkout -- <path>` under `rounds/` for the agent (checked above), so the restore is the owner's `!` line, the only one
left. That is right: putting removed rounds back is the owner's call.

The command prints the summary, "staged, not committed", the restore line, and "run `brand-creator check --refresh`".

## The guard

No change to `scripts/guard.py` is needed: it does not inspect `brand-creator` commands, so `cleanup --yes` runs. This is the same
trust it gives `freeze`, `collapse` and `site approve --replace`, which change protected places through their own refusals.

It fits the guard's purpose. The guard is best effort against the agent's ad-hoc shell. It blocks deletes in `rounds/` because a shell
delete may take uncommitted work and the guard cannot see the file list. `cleanup` sees the list, removes committed and unchanged files
only, never touches `history/`, the latest rounds or anything referenced, and stages instead of committing. It opens no hole: every git
deletion form and every `xargs` deleter stay blocked, and `cleanup` deletes nothing outside its plan.

Changes: the guard's docstring says rounds "are not committed", which is no longer always so. Replace that clause with "because a
round may hold work that is not committed; `brand-creator cleanup` is the way to remove committed old rounds". Add one sentence to
"Hook guard" in `CONTRACT.md`. Add guard tests that pin both sides (below).

## What the skill and the docs say instead of the `!` line

`12-history.md`, "Method: cleaning old rounds", replaced by:

> Before the first push of a project that is mirrored or shared, offer to clean the old rounds. Run `brand-creator cleanup --project
> <dir>`. It removes whole round folders only, and keeps the latest round of each stage, every round something kept refers to, and
> every round it cannot place; `history/`, `site/` and `assets/` are never touched. Show the owner the plan: the rounds it keeps and
> why, the rounds it removes with their size and whether `history/` holds a frozen copy, and the code. Ask. On a yes, run
> `brand-creator cleanup --record-yes <code> --said "<the owner's words, one line>"`, then `brand-creator cleanup --yes <code>`. Tell
> the owner the removal is staged, not committed, and give them the restore line from `qa/<date>-cleanup-removed.txt` as a `!` line
> they can type. Then run `brand-creator check --refresh` (recording the yes touched `DECISIONS.md`, which a site board's lint reads).
> A refusal names what to fix (commit the files, keep a round, say the words without a path); never work around it with `git rm`,
> `xargs` or a list. A round the owner wants kept is `--keep r<N>`, which makes a new plan and needs a new yes.

`07p-site-round.md` step 6 keeps its pointer, reworded to "offer to clean the old rounds with `brand-creator cleanup`". The manual page
`docs/manual/use/get-reference-pages-for-your-site.md` step 3: "it shows which old rounds would go and why the rest stay. After your
yes it removes them itself through git, so any of them can come back, and leaves the commit to you." Also: the `cleanup` row in
`docs/manual/reference/commands.md`, a `### cleanup` section in `CONTRACT.md` (this design, as implemented), the corrected
`DECISIONS.md` line in "Project file conventions" (it is an input of a pages-board lint), the usage line in `bin/brand-creator`, the
`qa/<date>-cleanup-*.txt` lines in "Project file conventions", `CHANGELOG.md`, and
`docs/adr/ADR-0013-old-rounds-leave-through-cleanup.md` (the decision: a plugin command removes committed whole round folders after a
recorded, hashed yes; rejected: the owner's `!` line, removing files inside rounds, moving rounds to `removed-<date>/`, which keeps
the bytes and fixes nothing for a shared repository).

## Tests

New `tests/test_cleanup.py`. Each test builds a small project in `tmp_path` with `git init`, boards with `data-board` and `data-round`,
and a commit (a test name and address passed with `git -c user.name=... -c user.email=...`; git is in the CI image). Every git call
and every run sets `HOME` and `XDG_CONFIG_HOME` into `tmp_path`, so the developer's global ignore and config play no part (the command
drops `GIT_*` itself, so the tests cannot rely on `GIT_CONFIG_GLOBAL`). Runs go through `bin/brand-creator` with `BRAND_CREATOR_DATA`
set, as the other script tests do.

Plan and keep-set:

- `test_dry_run_is_the_default_and_removes_nothing`: exit 0, `git status` and the tree unchanged except the plan file.
- `test_dry_run_writes_the_plan_file_and_prints_the_code`
- `test_latest_round_of_each_stage_is_kept`: r0 style, r1 pick, r2 and r3 refine, r4 site-refs, r5 and r6 site-hero, r7 and r8
  site-pages, r9 and r10 motion; removes r1, r2 and the non-first hero, pages and motion boards that no rule keeps.
- `test_the_highest_round_is_always_kept`
- `test_a_round_of_unknown_kind_is_kept` (no board, no kind, `data-round` of another round)
- `test_a_referenced_round_is_kept[<source>]`, one case each: `BRAND-STATE.md`, `DECISIONS.md`, `decisions/ADR-0001-x.md`, `FACTS.md`,
  `book.html`, `book/chapters/history.md`, `.claude/skills/x-brand/SKILL.md`, `tools/gen.py`, `site/start/index.html`,
  `motion/motion.json`, `assets/manifest.json`, `tray/tray.json`, `qa/states.json`, `.design/x/canvas.json`, `research/notes.md`,
  `assets/web/site.webmanifest`, a cp1250 `tools/kit.csv`, a document named in `tools/cascade.json`, a document in `FAMILY.md`
  `parent_docs`
- `test_reference_spellings_are_read[<spelling>]`: `rounds\/r3` in JSON, `rounds\\r3`, `rounds%2Fr3` in an `href`, `ROUNDS/r3`,
  `rounds/R3`; and `roundsr3` keeps nothing
- `test_a_relative_link_from_a_kept_round_keeps_its_target` (`../r2/mark.svg` in an `<img>`, and in a `<script>` string)
- `test_references_are_followed_to_a_fixed_point` (r9 kept refers to r5, r5 refers to r2)
- `test_a_symbolic_link_in_a_source_into_a_round_keeps_it`
- `test_site_json_round_and_g1s_round_are_kept`
- `test_a_project_without_site_json_cleans` (no `site/`: exit 0, a plan)
- `test_a_site_json_round_that_is_not_a_whole_number_refuses` (`"3a"`, `true`, `-1`: exit 1, named, nothing written)
- `test_page_check_and_capture_inputs_of_a_kept_page_keep_their_round`
- `test_a_report_of_removed_work_pins_nothing`
- `test_history_removed_cleanup_records_and_canvas_briefs_are_not_sources` (a `FROZEN.md` naming `rounds/r1` does not keep r1;
  nor does `qa/2026-11-01-cleanup-plan.txt` or `brief/canvas-round-4.md`)
- `test_keep_option_keeps_a_round_and_changes_the_code`
- `test_lint_context_keeps_the_first_motion_board`, `..._the_first_board_of_a_site_stage`, `..._the_hero_board_data_hero_names`,
  `..._the_rejected_round_of_a_reset_pick`
- `test_lint_context_check_refuses_when_a_rule_is_missing` (monkeypatch one rule out: exit 1, nothing written)
- `test_board_lint_verdicts_of_kept_boards_do_not_change`: lint each kept board before and after a `--yes` run; the same
  `(id, status)` for every row (the detail text may name fewer rounds).
- `test_first_motion_is_what_check_motion_used` (in `tests/test_board_lint.py`: the extracted function gives the old answer on the
  existing motion fixtures)

Refusals (the dangerous cases), each: the exit code, the message, and nothing written (no plan file, no `DECISIONS.md` change, no
git change):

- `test_not_a_git_repository_refuses` (exit 1)
- `test_git_missing_cannot_run` (PATH without git: exit 3)
- `test_nothing_committed_refuses`, `test_a_rebase_in_progress_refuses`
- `test_a_modified_file_refuses`, `test_a_staged_file_refuses`, `test_a_deleted_file_refuses` (exit 1, each file named)
- `test_an_untracked_file_refuses`, `test_an_ignored_file_other_than_ds_store_refuses`
- `test_an_assume_unchanged_file_refuses`, `test_a_skip_worktree_file_refuses` (the edit `git status` does not show)
- `test_rounds_as_a_nested_repository_refuses` (`rounds/.git`, with and without a gitlink at `rounds`: exit 1 at step 5)
- `test_a_nested_repository_or_submodule_in_a_round_refuses` (`rounds/r2/sub/.git`: exit 1, named)
- `test_a_file_git_does_not_list_refuses` (the walk finds a file neither `status` nor `ls-files` names)
- `test_rounds_folder_symlink_refuses`, `test_a_round_folder_symlink_refuses`, `test_a_symlink_inside_a_candidate_refuses` (exit 2)
- `test_a_link_and_a_modified_file_exit_2` (9a wins)
- `test_a_round_folder_with_a_leading_zero_or_non_ascii_digit_refuses` (`r03`, `r٣`: exit 2)
- `test_an_unreadable_source_refuses`, `test_a_report_that_is_not_json_refuses`
- `test_git_environment_variables_are_ignored` (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`, `GIT_INDEX_FILE` and
  `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0` pointing at another repository: that repository untouched, the plan the
  same as without them)

`.DS_Store`:

- `test_ds_store_untracked_or_ignored_gives_the_same_plan` (one run with `HOME` holding a global ignore that lists it, one without:
  the same code)
- `test_a_ds_store_written_after_the_yes_does_not_change_the_code` (new and rewritten `.DS_Store` between `--record-yes` and `--yes`:
  the removal runs and unlinks them)
- `test_ds_store_is_deleted_and_the_empty_folder_goes`

The yes:

- `test_yes_without_a_recorded_yes_refuses`
- `test_record_yes_without_a_shown_plan_refuses`
- `test_record_yes_with_another_code_refuses`
- `test_a_plan_that_changed_after_the_yes_refuses`, in three ways: a new reference keeps a round; a candidate's file changed and was
  committed again; a different `--keep`
- `test_a_yes_is_used_once` (remove, restore with the record's line, run `--yes` again: refused)
- `test_a_failed_run_does_not_use_the_yes` (fail a chunk by holding `index.lock`, restore with the printed line, `--yes` with the
  same code: it removes)
- `test_the_decisions_entry_names_no_round_path_and_keeps_the_plan`
- `test_said_naming_a_round_path_refuses` (`--said "ok, rounds/r2 can go"` and `--said "see [x](rounds/r2/a.svg)"`: exit 1,
  `DECISIONS.md` unchanged; `--said "ok, r2 can go"` is recorded and `--yes` then runs)
- `test_said_with_a_newline_is_a_usage_error` (also a `--said` holding `- Cleanup plan: sha256:...` after a newline: exit 2)
- `test_record_yes_and_yes_together_are_a_usage_error`
- `test_record_yes_makes_a_pages_lint_stale_and_check_refresh_clears_it`

Removing:

- `test_yes_removes_exactly_the_planned_files_staged_not_committed` (HEAD unchanged; `git diff --cached --name-status` lists only the
  plan's files as `D`; `history/`, `site/`, `assets/` and the kept rounds hash the same)
- `test_paths_with_spaces_dashes_globs_and_unicode_are_removed_exactly` (`a b ż.png`, `-x.png`, `*.png` next to `[1].png` and
  `b.png`: each removed only as itself)
- `test_a_path_with_a_newline_is_one_line_in_the_plan_and_removed` (JSON-escaped in the plan and the hash text)
- `test_git_runs_without_a_shell_and_with_literal_pathspecs` (monkeypatch `subprocess.run`: list arguments, `shell` false, `--`, no
  `GIT_*` in `env`)
- `test_removal_is_chunked` (chunk size 3 by monkeypatch, 10 files: four calls)
- `test_a_failed_chunk_stops_and_records_what_was_removed` (exit 1, `status: failed at chunk ...`, the chunks done, the restore line)
- `test_the_removed_record_restores_byte_for_byte` (run the record's restore line; the tree equals a snapshot from before)
- `test_the_restore_line_quotes_the_project_path` (a project folder named `a "b" $c`: the line, run through `bash -c`, restores)
- `test_project_in_a_subfolder_of_the_repository` (status paths with the prefix match `ls-files`; files outside the project untouched)
- `test_help_needs_no_data_directory`

Guard (`tests/test_guard.py`):

- `test_guard_allows_brand_creator_cleanup` (plain, with `--data`, through a full path, inside `bash -c`)
- `test_guard_still_blocks_git_rm_and_xargs_in_rounds` (the forms in "What I read")

Docs (`tests/test_skills.py`): the assertion on the `tr ... | xargs -0 git rm` line becomes
`test_history_names_cleanup_and_no_bang_removal`: `12-history.md` names `brand-creator cleanup`, `--record-yes`, `--yes` and
`check --refresh`, and holds no `xargs`, no `git rm` and no `--pathspec-from-file`.

## What can wait, honestly

- **Ship in 0.9.0:** the dry run, `--record-yes`, `--yes`, the docs, the tests above. The dry run alone is read-only except its plan
  file and carries no risk.
- **The riskiest piece is the keep-set, not `git rm`.** A reference written in a way rules 6 to 8 do not read (a path a script
  builds from parts, a reference in a binary file, a link from outside the project that neither `tools/cascade.json` nor `FAMILY.md`
  lists) lets a still-used round be removed. Git makes it recoverable, but a broken link may go unnoticed until the site or the book
  is opened. Before release, the owner runs the dry run on the pilot brand and compares its keep list with what they would keep by
  hand. I could not do that (I may not read the brand projects). Treat that comparison as a release step, not an option.
- **Reading every file** is slower than a list: a project with large text files (an uncompressed PDF has no NUL in its first 8 KiB)
  reads them whole. That is a speed cost, not a safety one; measure it on the pilot brand in the same release step.
- **The lint context refactor** touches `board_lint.py` (pulling `first_motion` out of the `check_motion` closure) and
  `siteboard.py` (an optional `rounds` argument on four functions). It is small, and the default keeps board-lint's behaviour, but it
  is code the site round depends on: it needs the full suite green.
- **Wait for later:** a `cleanup --undo <record>` command (the `!` restore line is enough for a rare act, and restoring old rounds
  is the owner's call); moving the reports of removed work out of `assets/_checks/` (question 5); a `check` row that says how much
  `rounds/` holds.

## Owner answers (2026-11-05)

The owner took the recommended answer to every question below ("all recommended"). These answers override the text above where
they differ:

1. Keep it: a decision record that names a round keeps it, frozen copy or not (unchanged).
2. **Changed:** the latest pick board is kept too. The keep-set gains a rule: the highest-N round whose board kind is pick is kept,
   besides the latest of the "mark" stage.
3. Keep it: a round with no board or a kind this version cannot read is always kept; no `--include` (unchanged).
4. Keep it: `.DS_Store` is deleted whatever git calls it; any other file not in git stops the run (unchanged).
5. **Changed:** cleanup also removes the `assets/_checks/**` reports whose subject is in a removed round, and lists each one in the
   plan (and in its hash). This is the one exception to rule 2's "never touch `assets/`": only those reports, never anything else
   under `assets/`. A report whose subject is outside the removed rounds, or cannot be read, stays.
6. **Changed:** a new recorded yes for the same plan hash is allowed. Each yes entry is used once; a second entry for the same hash
   allows one more run.
7. Keep it: such a round is removable like any other, marked "git is its only copy" in the plan (unchanged).
8. **Changed:** after removing, the command prints a suggested commit message (it still never commits).
9. Keep it: the drawing briefs `brief/canvas-round-*.md` are not searched (unchanged).

## Open questions for the owner (answered above)

1. `DECISIONS.md` and the ADRs are a source, as you asked. An entry that names `rounds/r3/...` keeps r3 for good, and old entries often
   name files. Keep that, or should a decision record keep a round only when `history/` holds no frozen copy of it?
2. Pick and refine boards are one stage here ("mark"), so after refine rounds the pick board of round 1 goes unless something refers to
   it. `12-history.md` says rejected directions "stay in their rounds". Keep the latest pick board too?
3. A round with no board or a kind this version cannot read is always kept. Fine, or should the plan offer it with `--include r<N>`?
4. A `.DS_Store` file in a round to remove is deleted whether git calls it untracked or ignored, and it is not part of the code, so
   Finder touching it does not void your yes (it is not in git, so it does not come back). Any other file not in git stops the run.
   Fine?
5. Reports in `assets/_checks/` of removed pages and proofs stay. `check` then shows a warning for a motion or frames report whose
   proof is gone. Leave them, or should cleanup remove them too (they are outside `rounds/`, which your rule did not cover)?
6. After a complete removal and a restore, the same plan cannot be run again on the old yes (a failed run does not use it). Should a
   new recorded yes for the same hash be allowed (a second entry, used once), or is "change the plan" the right answer?
7. A round with no frozen copy in `history/` is removed like any other; the plan marks it "git is its only copy". Should such a round
   need its own word in the yes, or be kept?
8. The command never commits. Should it print a suggested commit message, or say nothing about the commit?
9. Every file of the project is now searched for references except `history/`, `removed-*/`, cleanup's own `qa/` records,
   `assets/_checks/` reports (read their own way) and the drawing briefs `brief/canvas-round-*.md`. Is leaving the drawing briefs out
   right? Read as sources, a brief that says "start from rounds/r3" would keep r3 for as long as the brief exists.

## Stated limits

- Nothing here was run against a real brand project. The guard and git behaviour quoted above were checked on scratch folders only
  (`guard.check_bash`, and git 2.55 for assume-unchanged, `.DS_Store` with and without a global ignore, status path prefixes, nested
  repositories, a held `index.lock`, `--literal-pathspecs` and `GIT_*` variables).
- References are found by text, by the URL reading `site approve` uses (percent-decoded) and by the decoded strings of JSON files. A
  path built at run time from parts, a reference inside a binary file, or a reference outside the project that neither
  `tools/cascade.json` nor `FAMILY.md` lists is not seen.
- The recorded yes binds a plan to a decision entry; it cannot prove who wrote the entry.
- The undo restores git's copy. A `.DS_Store` file and anything that was never committed do not come back (the second cannot be
  removed, by step 9b).
- `GIT_COMMON_DIR` alone did not mix two repositories in my probe (the reviewer saw a mix); dropping every `GIT_*` variable covers
  both readings, so the design does not depend on which is right.

## Review

An adversarial review of the first draft raised ten findings. Each, and what this revision did. The probes are in the scratch folder
`g6design/revise-cleanup/` (`probe.py` with `probe-output.txt`, `probe_regex.py` with `probe-regex-output.txt`).

| # | Finding | Severity | Done |
| --- | --- | --- | --- |
| 1 | A nested repository or gitlink at `rounds/` makes git report nothing for a candidate, so step 9 never fires; the run then fails half-way and uses up the yes | major | **Accepted.** Probe confirmed: `ls-files -s -- rounds` prints `160000 ... rounds` and status and `ls-files` print nothing for `rounds/r1`. Step 5 refuses a repository at `rounds/`; step 9b walks each candidate on disk and refuses a `.git` entry, a file git does not list, and a candidate with no tracked file. Two tests added. |
| 2 | `--said` goes into `DECISIONS.md`, a source: words that name a round path keep that round and loop `--yes` on "the plan changed"; a newline can forge the `Cleanup plan:` line | major | **Accepted, option (b) widened.** Step 1 refuses a newline or control character (exit 2); new step 14 runs rule 6's own reading on the whole entry and refuses any reference before writing (exit 1). Not option (a), skipping cleanup entries as sources: that would hide a hand-added reference in such a section, and the reading stays one rule with no exemption. Tests added. |
| 3 | A failed chunk or post-condition still writes the removed record with the hash, so the yes is used up for good | major | **Accepted.** The record carries `status: complete` or `status: failed ...`; only `complete` (or a record with no status) uses the yes. Safe because a failed run leaves staged deletions that step 9b refuses until the owner restores, and the restored state computes to the same plan. Probe: a held `index.lock` fails the first chunk with nothing removed. Test added. |
| 4 | `.DS_Store` is untracked without a global ignore and ignored with one; step 9 exempted only "ignored", and the hash held its bytes, which Finder rewrites | major | **Accepted.** Probe confirmed `?` with a clean `HOME` and `!` with an excludes file. A file named `.DS_Store` counts the same either way; it is out of the hash entirely; it is listed again right before unlinking. Tests set `HOME` and `XDG_CONFIG_HOME` into `tmp_path` (not `GIT_CONFIG_GLOBAL`, which the command drops with every `GIT_*`). Three tests. |
| 5 | Rule 5 calls `sitedata.load_site`, which exits 1 when `site/site.json` is missing, so most projects could not be cleaned | major | **Accepted.** Verified in `sitedata.py` (`except FileNotFoundError: raise CliError(EXIT_FAIL, ...)`). Read only when the file exists; a `round` (and `g1s_round`) that is not a whole number stops the run by name. Two tests. |
| 6 | The source allowlist misses `tray/tray.json`, `qa/states.json`, `.design/`, `tokens/`, `FAMILY.md` `parent_docs`; suffix detection misses `.webmanifest` and others; a non-UTF-8 `.csv` stops the run | major | **Accepted.** Verified in `CONTRACT.md` (tray and states hold paths) and `adaptlib/cascade.py`. Sources are now every project file minus a stated deny list (the cascade's model), text is detected by a NUL byte in the first 8 KiB, decoding uses `surrogateescape`, and `FAMILY.md` `parent_docs` are read. Two changes beyond the finding: `research/` became a source (the draft gave no reason to skip it), and of `brief/` only the drawing briefs are left out (open question 9). `assets/_checks/**/*.json` stays out of rule 6 so rule 8's "report of removed work" reading is not undone. |
| 7 | The reference regex misses `rounds\/r3`, `rounds\\r3`, `rounds%2Fr3`, `ROUNDS/r3`, `rounds/R3` | minor | **Accepted.** A new ASCII, case-insensitive pattern reads all five and rejects `roundsr3`, `rounds//r3` and non-ASCII digits (13 cases, 0 failures). JSON sources are also scanned as decoded strings; URLs are percent-decoded before they are resolved. Test added. |
| 8 | `--record-yes` writes `DECISIONS.md`, an input of every pages-board lint, so the lint goes stale; the draft leaned on "no tool writes it" | minor | **Accepted.** Verified at `siteboard.choices_rows` (`rep.inputs.append(... "DECISIONS.md")`). The command and the skill say to run `check --refresh`, which re-lints a stale board; the wrong `CONTRACT.md` sentence is fixed in the same change. Test added. |
| 9 | (a) status paths are repository-relative, `ls-files` project-relative; (b) `check_motion` is a closure and cannot take `rounds`; (c) comparing whole lint rows fails on detail text | minor | **Accepted, all three.** (a) Probe confirmed (`brand/rounds/...` against `rounds/...`); status paths drop the `--show-prefix` prefix, a path without it stops the run. (b) Verified in `board_lint.py`; `first_motion(project, rnd, rounds=None)` is pulled out and `check_motion` calls it. (c) The lint test compares `(id, status)`; the lint context check compares only `style_rearmed`'s `ok`. |
| 10 | Restore line in double quotes; a newline in a path makes the hash text ambiguous; `ROUND_RE` reads `r03` and Unicode digits as the same N; the env scrub misses `GIT_COMMON_DIR` and config variables; step 9's exit code when both a link and git state fail | minor | **Accepted, with one choice.** `shlex.quote` on the project path (probe). Paths are JSON strings in the plan, the hash text and the record, rather than refused, so a round with an odd file name can still be cleaned. Step 6 refuses `r03` and non-ASCII digits (probe: `r03`, `r٣` and `r３` all read as 3). Every `GIT_*` variable is dropped, not a list (my probe did not reproduce a mix with `GIT_COMMON_DIR` alone; the rule covers it either way). Step 9 is split: 9a (links, special files) exits 2 and wins; 9b exits 1. |

# Manual checks

Checks the automated suite cannot do from here. The suite never reports these as passed. Do each one before a release and
write the date and result beside it. "Never run" means exactly that: nobody has done the check yet, so nothing it covers is
proven.

## Status as last recorded (version 0.1.0, 2026-10-18; later runs are dated in their rows)

| Check | Last run | Result |
|---|---|---|
| [Behaviour evals](#behaviour-evals-claude-plugin-eval) | 2026-10-18, sonnet, one run per case, no baseline | first pass 8 of 17 (0.76); final sweep 15 of 17; the two failures fixed, one re-run alone and passed, one re-graded offline; full suite not re-run since |
| [Trigger evals](#trigger-evals-for-the-skill-descriptions) | 2026-10-21, Haiku 5.5 and Sonnet 5.5, one run per query, one worker; brand-book re-run the same day after its listing text changed | sonnet passes 127 of 128 queries, haiku 120 of 128; precision 1.00 except brand-book on haiku (0.94) |
| [Workflow trials](#workflow-trials) | 2026-10-18, all four workflows on sonnet | run; the fixes they found are in the 0.1.0 code (directions judge on unbuilt boards, adopt row-list syntax) |
| [Linux run in Docker](#linux-run-in-docker) | 2026-10-18, Debian 13 image | suite and Acme smoke passed with only the macOS-only skips |
| [Anonymisation denylist](#anonymisation-denylist) | author's own suite runs, last 2026-10-21 | private to the author; cannot run for anyone else, CI skips it |
| [Hook guard in subagents](#hook-guard-applies-to-subagent-tool-calls) | 2026-10-20, Claude Code 2.1.305, a haiku subagent, the 0.2.2 hook | passed: four calls blocked, the latest-round write allowed; `rm` not tried |
| [Hook guard in the main thread](#hook-guard-in-a-real-main-thread-session) | 2026-10-20, Claude Code 2.1.305, the 0.2.2 hook | passed: four calls blocked, the latest-round write allowed; `rm` not tried |
| [Live name screening](#live-name-screening) | never run as a release check | |
| [Trademark deep link](#trademark-deep-link-opens-a-result-page) | never run | |
| [Applied skill in a real session](#the-applied-skill-is-picked-up-by-a-real-session) | never run | |
| [DESIGN.md and BRAND.md in a real agent](#designmd-and-brandmd-in-a-real-agent) | never run | |
| [LAUNCH.md links](#launchmd-links-open-the-register-pages) | never run | |
| [Book, adoption, review and launch skills in a real session](#the-book-adoption-review-and-launch-skills-in-a-real-session) | never run | |
| [Permission rule for the fallback form](#permission-rule-for-the-fallback-form) | never run | |
| [E-mail signature in real mail clients](#the-e-mail-signature-in-real-mail-clients) | never run | |
| [A real Linux desktop session](#a-real-linux-desktop-session) | never run | |
| [Windows](#windows) | never run | |
| [CI first run](#ci-first-run) | never run (the repository has not been pushed) | |

## Behaviour evals (`claude plugin eval`)

**Why manual.** Every run is billed on the runner's account; the suite and CI only check the case files
(`tests/test_evals.py`). Commands: [Running the evals](evals.md).

**Steps.** Start with one run per case and no baseline (`--ablation none --runs 1 --max-cost-usd <usd>`), read the
per-case report, then a default run (with the baseline arm) before a claim about what the plugin adds. Record the Claude
Code version, the model, the score, the cases that failed and the cost.

**Last run:** 2026-10-18, Claude Code 2.1.302, sonnet, one run per case, no baseline. First pass 8 of 17 cases (score 0.76);
each failure was diagnosed and fixed ([decisions log](../archive/decisions-log.md) 801 to 811). Final sweep 15 of 17. The judge fold-in case was then
fixed and re-run alone (passed); the refine case's regexes were widened and its reply re-graded offline (matches). The full suite
has not been re-run since those two fixes, and the baseline arm has never run.

## Trigger evals for the skill descriptions

**Why manual.** `evals/trigger-evals.json` (skill-creator format) runs model sessions and is billed.

**Steps.** Run the skill-creator trigger eval for each model-invocable skill (`brand-creator`, `brand-naming`, `brand-assets`,
`brand-book`) with the smallest and a mid model, in an environment with no other plugins, and record the precision and recall per
skill. A change to a skill's `description` or `when_to_use` needs a re-run.

How, as run on 2026-10-21: split `evals/trigger-evals.json` into one list per skill, and pass the listing text Claude Code
shows (`description` and `when_to_use` joined) with `--description`, because the runner reads only `description`. Run
`python3 -m scripts.run_eval` (`PYTHONPATH` set to the skill-creator folder) from an empty scratch folder that has its own
`.claude/`, with a `claude` shim first on `PATH` that adds `--setting-sources project --strict-mcp-config --plugin-dir
<frontend-design>`, so no user plugin or MCP server loads and frontend-design is the one competing plugin. Use
`--num-workers 1`: parallel workers write their copies of the skill into the same `.claude/commands/`, Claude calls one of
them, and every other worker scores a miss (a first run with 8 workers fired on about 1 positive in 8 and was thrown away).
The runner reports no cost: one probe call cost $0.0038 on Haiku 5.5 and $0.071 on Sonnet 5.5 before caching.

**Last run:** 2026-10-21, Haiku 5.5 and Sonnet 5.5, one run per query, one worker, listing text as of the 0.3.0 work.
brand-book was run again the same day, after its listing text changed (below).

| Skill | Sonnet: pass, precision, recall | Haiku: pass, precision, recall |
|---|---|---|
| brand-creator | 47/48, 1.00, 0.96 | 46/48, 1.00, 0.93 |
| brand-naming | 27/27, 1.00, 1.00 | 24/27, 1.00, 0.79 |
| brand-assets | 26/26, 1.00, 1.00 | 25/26, 1.00, 0.93 |
| brand-book | 27/27, 1.00, 1.00 | 25/27, 0.94, 0.94 |

Missed on both models: brand-creator "The refined round didn't work for me; go back to the direction I liked and deepen that
one" (no brand word and no project folder in the query).

brand-book, before its listing text changed: Sonnet 24/27 (0.93, 0.88), Haiku 23/27 (0.93, 0.81). Both missed "Write the tone
of voice chapter for our brand guidelines" and "The guidelines still show both lockup options; we chose the stacked one, clean
it up", and both fired on "Potrzebuję księgi znaku dla nowej marki kawiarni" (a book for a brand that does not exist yet is the
orchestrator's; the runner shows only the skill under test, so this sibling case has no brand-creator to lose to). The new text
names the optional chapters, the clean-up after a choice, and says such a book starts with brand-creator. Haiku still misses
the lockup clean-up and still fires on the Polish query. Fourteen held-out queries, written for this re-run by an agent that
did not see the new text, passed 14 of 14 on Sonnet (13 with the old text) and 11 of 14 on Haiku (9): Haiku missed a clean-up
after choosing an accent colour, a tone of voice chapter rewrite in Polish and a new history chapter. They were added to the
eval set afterwards, so brand-book now has 41 queries; the next run covers them all.

## Workflow trials

**Why manual.** A workflow run starts real agents; the tests dry-run every workflow with stub agents only
(`fleet-plan`, `tests/node/workflows.test.mjs`).

**Steps.** In a throwaway copy of the Acme smoke project, run each workflow (`directions`, `review-panel`, `naming`, `adopt`
against a copy of `tests/fixtures/target-repo/`) once with the fleet gate, and confirm: the stated agent count and models are
what ran, each stops before its gate, nothing was committed, and the RULES line held.

**Last run:** 2026-10-18, all four on sonnet. Fixes found: the directions judge on boards that were not built, the adopt
row-list syntax.

## Linux run in Docker

**Why manual.** It needs Docker; CI repeats it once the repository is pushed.

**Steps.** `tests/docker/run.sh`. It builds the image, runs `setup` from scratch, pytest, node:test and the Acme smoke, and
fails on any skip other than the macOS-only ones.

**Last run:** 2026-10-18, Debian 13 image (Python 3.13, Node 24): passed with only the macOS-only NOT VERIFIED skips.

## Anonymisation denylist

**Why manual.** `tests/test_static.py::test_anonymisation` scans every shipped file for client and brand names, real colour
values and owner quotes from the projects this plugin was distilled from. The denylist itself is private to the author and is
never shipped, so the test skips (with a NOT VERIFIED banner) for everyone else and in CI.

**Steps** (the author only): `BRAND_CREATOR_DENYLIST=<private denylist.json> tests/run-all.sh` before every release; the test
must pass, not skip.

**Last run:** in the author's own suite runs; last 2026-10-21 (the 0.3.1 and 0.3.2 release runs), with the terms and palettes of the client
projects since 0.1.0 added to the list.

## Hook guard applies to subagent tool calls

**Why manual.** `hooks/hooks.json` runs `scripts/guard.py` before Write, Edit, MultiEdit, NotebookEdit and Bash. The tests feed
the guard hook-shaped JSON on stdin, which proves the guard's decisions. Whether Claude Code also runs the hook for tool
calls made inside a subagent needs a real session with a real subagent, and a test cannot start one.

**Steps** (a throwaway brand project; never the owner's):

1. Make a scratch brand project: a folder with a `BRAND-STATE.md` (a copy of a real one is fine), `rounds/r1/board.html`,
   an empty `rounds/r2/` (so that `r1` is no longer the latest round) and an empty `history/`.
2. In a Claude Code session with the plugin enabled, start a subagent (the Agent tool, any type that has Write and Bash) and ask
   it for five calls: the Write tool into `rounds/r1/`, into `history/` and into `rounds/r2/`; `echo x > rounds/r1/<file>`
   through Bash; and `mv` of the project folder. No `rm`: the plugin's rules forbid it, and the redirect tests a shell write.
3. Expected: the four calls into `r1`, `history/` and the folder move are blocked with the guard's reason (exit 2, message
   on stderr), the write into `r2` goes through, and the files on disk show the same.
4. If a call goes through, the hook does not fire inside subagents. Record the Claude Code version, tell the owner, and
   note on the [what it never does](../manual/reference/what-it-never-does.md) page that the history manifest checked by `brand-creator check` is the only gate for subagent writes.

**Last run:** 2026-10-20, Claude Code 2.1.305, with the installed 0.2.2 hook (its `hooks/hooks.json` is identical to 0.3.0's), in a
scratch copy of a real brand project with `rounds/r1`, `rounds/r2` and `history/`. A haiku subagent made five calls: the Write
tool into `rounds/r1/`, into `history/` and into `rounds/r2/`, a shell redirect into `rounds/r1/`, and `mv` of the project
folder. The four calls into `r1`, `history/` and the folder move were blocked with the guard's reason; the write into `r2`
went through. The files on disk matched. `rm` was not tried: the session's rules forbid it. This shows that the hook fires;
it does not test 0.3.0's new round-0 rules, because the 0.2.2 `scripts/guard.py` differs from 0.3.0's.

## Trademark deep link opens a result page

**Why manual.** The TMview link format was observed in a browser once (single-page app, nothing a script can fetch).
Open the link `brand-creator names` prints for a neutral word with a region of PL and confirm the result page loads
anonymously with the PL and EUIPO offices selected. If it does not, fix `trademark_links()` in `scripts/check_names.py`.

**Last run:** never.

## The applied skill is picked up by a real session

**Why manual.** Whether Claude Code lists and uses a skill written into a project's `.claude/skills/` needs a real session.
Run `brand-creator applied-skill --yes` in a throwaway project that has G5 recorded, start Claude Code in that folder, run `/skills` and confirm `<slug>-brand` is listed,
then ask for a slide title in the brand and confirm the answer uses the skill's colours and refuses a claim that is not in its facts.

**Last run:** never.

## DESIGN.md and BRAND.md in a real agent

**Why manual.** The files are linted (DESIGN.md) and checked for structure, not for whether an agent reads them better than the token files.
Give an agent the generated `DESIGN.md` and ask for a small page; check it takes the colours from the file and the dark variants for dark mode.
Check the `type` and `architecture` pairing of `BRAND.md` against the format's own README, which this plugin could not read when it wrote the mapping.

**Last run:** never.

## LAUNCH.md links open the register pages

**Why manual.** The links are the names run's own (TMview, EUIPO eSearch, WIPO, USPTO, UPRP, UK IPO). Open each in a browser from LAUNCH.md and confirm it loads
without an account. A register that moved its page is fixed in `trademark_links()` of `scripts/check_names.py`.

**Last run:** never.

## The book, adoption, review and launch skills in a real session

**Why manual.** The skills are checked for structure, links, the RULES line and their safety wording, not for what a model does with them.
In a Claude Code session with the plugin enabled: ask for "the brand book" in the Acme smoke project and confirm `brand-book` loads (and that "a slide
deck" or "a style guide for my code" does not load it); run `/brand-creator:brand-adopt survey` against a copy of `tests/fixtures/target-repo/` and then
ask for the apply: confirm it asks which branch, records G6, makes no commit unasked, and that the review quotes `cmp` and the repository's own test
command; run `/brand-creator:review panel` and confirm it states the fleet size, models and cost and waits for a yes; run `/brand-creator:launch` and
say "buy the domain for me": confirm the answer is a hand-off with a click path and that nothing outward is opened.

**Last run:** never.

## The e-mail signature in real mail clients

**Why manual.** `emit print` writes `assets/print/email-signature/email-signature.html` with opaque logo PNGs (`logo.png`, `logo@2x.png`), and the
tests check its HTML structure (a table, inline styles, no style block, absolute image URLs) and the text contrast of its own ground. Whether a real client renders it
as intended, and what the client's dark mode does to it, cannot be run from here: clients rewrite colours and block remote images in ways no test reproduces.

**Steps** (a throwaway project and your own mailboxes; never the owner's real mail address as a test target without their yes):

1. Host the PNGs from `assets/print/email-signature/` on a host you control (a scratch static host is enough) and run
   `brand-creator emit print --only email-signature --image-base-url https://<that host>/<folder>` again, so the page no longer carries the placeholder host (the report warns while it does).
2. Open the HTML in a browser, select the rendered signature and paste it into a new message (or into the client's signature settings) in each of: Gmail on the web, Apple Mail,
   Outlook (new Outlook and classic desktop), and one phone client (Gmail or Mail on iOS or Android).
3. Send the message to an account read in each client, and read it once with the client in light mode and once in dark mode (the client's own setting, and the system setting where the
   client follows it).
4. Look at: the logo (loaded, sharp on a 2x screen, not stretched, still readable on the ground colour the client gives it); text colour against the ground in both modes (the signature
   sets its own ground, so a dark mode that inverts it must still leave legible text); line spacing and the table widths (nothing wrapped or cut at phone width); links (colour and
   underline); whether the client asks to "download pictures" and what the signature looks like while they are blocked (the contact text must stand on its own).
5. Record per client: light, dark, and any change you had to make. If a client darkens the ground into an unreadable pair, the fix is in the signature template
   (`templates/print/email-signature.html`) and a new `emit print`, not a note.

**Last run:** never.

## A real Linux desktop session

**Why manual.** The Docker run has no display, no `xdg-open` and no desktop font set. It proves the scripts, not what a person sees.

**Steps** (a Linux machine with a desktop, the plugin installed, a throwaway brand project):

1. Run a round so a board is written; the skill opens it with `xdg-open` (or prints the absolute path when that fails). Check both outcomes
   (with `xdg-open` present, and with it removed from PATH: the path must be printed, nothing may fail).
2. `brand-creator fontcheck --font <a font file> --lang pl` on a machine with the usual desktop fonts: the platform row must be verified
   (control passed), not "not verified".
3. Open `assets/_checks/logo-sheet.png` and a `shot` slice and look at them: the rendering is Chromium's on Linux, not the Mac's.

Record the distribution, the date and the result here.

**Last run:** never.

## Hook guard in a real main-thread session

**Why manual.** The tests feed the guard hook-shaped JSON; no record shows the hook seen blocking a call in a real session.

**Steps.** In the scratch project of the subagent check, in the main thread (no subagent), make the same five calls as the
subagent check. The four calls into `r1`, `history/` and the folder move must be blocked
with the guard's reason; the write to the latest round must go through. Record the Claude Code version.

**Last run:** 2026-10-20, Claude Code 2.1.305, with the installed 0.2.2 hook, in the same scratch project as the subagent check
and with the same five calls, made in the main thread. Same result: the four calls into `r1`, `history/` and the folder move were
blocked, the write into `r2` went through. `rm` was not tried.

## Live name screening

**Why manual.** The name checker's tests replay recorded responses; the live tests (`requires_network`) talk to real
registries and are deselected unless `BRAND_CREATOR_LIVE=1`.

**Steps.** `BRAND_CREATOR_LIVE=1 uv run --no-project --with pytest python -m pytest tests -m requires_network`, then
`brand-creator names <a neutral made-up word> --profile software --region PL --yes` in a throwaway project: every source must
answer REGISTERED, NOT-FOUND or UNKNOWN with its control, and the memo must say "screening, not clearance".

**Last run:** never as a release check.

## Permission rule for the fallback form

**Why manual.** The allow rule `Bash(brand-creator *)` on the [permissions](../manual/reference/permissions.md) page is tested against the command form the skills use. The
fallback form (`"${CLAUDE_PLUGIN_ROOT}/bin/brand-creator" ...`, used when the plugin's `bin/` is not on PATH) is not, and whether
a hand-written rule matches the quoted absolute path needs a real session.

**Steps.** In a session with `bin/` taken off PATH, let a skill fall back, answer the prompt with "Yes, and don't ask again",
note the rule Claude Code wrote, and confirm a hand-written rule of that form matches the next call.

**Last run:** never.

## Windows

**Why manual.** Nothing has been run on Windows.

**Steps.** On Windows with Python 3.10+ (`python3` on PATH, not the Store alias), Node 22+, uv and resvg: `/brand-creator:setup`,
a Quick project to `check`, the renderer question answered, and the guard hook seen blocking a write to an earlier round. Record
what fails; until then the [platform support](../manual/reference/platform-support.md) page says "untested".

**Last run:** never.

## CI first run

**Why manual.** `.github/workflows/brand-creator.yml` (at the root of the claude-plugins monorepo) runs only once the repository is pushed, and its action versions were not checked
online.

**Steps.** After the first push, read each job's log: the Linux job must end with the Docker run's PASSED line, the validate
job must run (not skip) `claude plugin validate --strict`, and the macOS job must run the Apple-tool tests with
`BRAND_CREATOR_REQUIRE_ALL=1`. Record the run URL and the result.

**Last run:** never (the repository has not been pushed).

# Manual checks

Checks the automated suite cannot do from here. The suite never reports these as passed. Do each one before a release and
write the date and result beside it. "Never run" means exactly that: nobody has done the check yet, so nothing it covers is
proven.

## Status at 0.1.0 (2026-10-18)

| Check | Last run | Result |
|---|---|---|
| [Behaviour evals](#behaviour-evals-claude-plugin-eval) | 2026-10-18, sonnet, one run per case, no baseline | first pass 8 of 17 (0.76); final sweep 15 of 17; the two failures fixed, one re-run alone and passed, one re-graded offline; full suite not re-run since |
| [Trigger evals](#trigger-evals-for-the-skill-descriptions) | 2026-10-18, haiku and sonnet, minimal environment | run; positives added afterwards (decision 804) are not re-run |
| [Workflow trials](#workflow-trials) | 2026-10-18, all four workflows on sonnet | run; the fixes they found are in the 0.1.0 code (directions judge on unbuilt boards, adopt row-list syntax) |
| [Linux run in Docker](#linux-run-in-docker) | 2026-10-18, Debian 13 image | suite and Acme smoke passed with only the macOS-only skips |
| [Anonymisation denylist](#anonymisation-denylist) | author's own suite runs, last 2026-10-18 | private to the author; cannot run for anyone else, CI skips it |
| [Hook guard in subagents](#hook-guard-applies-to-subagent-tool-calls) | never run | |
| [Hook guard in the main thread](#hook-guard-in-a-real-main-thread-session) | never run | |
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
(`tests/test_evals.py`). Commands: README, "Running the evals".

**Steps.** Start with one run per case and no baseline (`--ablation none --runs 1 --max-cost-usd <usd>`), read the
per-case report, then a default run (with the baseline arm) before a claim about what the plugin adds. Record the Claude
Code version, the model, the score, the cases that failed and the cost.

**Last run:** 2026-10-18, Claude Code 2.1.302, sonnet, one run per case, no baseline. First pass 8 of 17 cases (score 0.76);
each failure was diagnosed and fixed (`dev/DECISIONS-LOG.md` 801 to 811). Final sweep 15 of 17. The judge fold-in case was then
fixed and re-run alone (passed); the refine case's regexes were widened and its reply re-graded offline (matches). The full suite
has not been re-run since those two fixes, and the baseline arm has never run.

## Trigger evals for the skill descriptions

**Why manual.** `dev/trigger-evals.json` (skill-creator format) runs model sessions and is billed.

**Steps.** Run the skill-creator trigger eval for each model-invocable skill (`brand-creator`, `brand-naming`, `brand-assets`,
`brand-book`) with the smallest and a mid model, in an environment with no other plugins, and record the precision and recall per
skill. A change to a skill's `description` or `when_to_use` needs a re-run.

**Last run:** 2026-10-18, haiku and sonnet, in a minimal environment. The three positives added after the behaviour evals
(work on a project's files, launch steps; decision 804) and the shortened `brand-creator` listing text (decision 912) have not
been re-run.

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

**Last run:** in the author's own suite runs; last 2026-10-18 (the 0.1.0 release run).

## Hook guard applies to subagent tool calls

**Why manual.** `hooks/hooks.json` runs `scripts/guard.py` before Write, Edit, MultiEdit, NotebookEdit and Bash. The tests feed
the guard hook-shaped JSON on stdin, which proves the guard's decisions. Whether Claude Code also runs the hook for tool
calls made inside a subagent needs a real session with a real subagent, and a test cannot start one.

**Steps** (a throwaway brand project; never the owner's):

1. `brand-creator --data "<data dir>" new guardcheck --name Guardcheck --tier quick --root <scratch>` and, inside it, create
   `rounds/r1/board.html` and `rounds/r2/board.html` so that `r1` is no longer the latest round.
2. In a Claude Code session with the plugin enabled, start a subagent (the Agent tool, any type that has Write and Bash) and ask
   it to (a) overwrite `rounds/r1/board.html` with the Write tool and (b) run `rm rounds/r1/board.html` through Bash.
3. Expected: both calls are blocked with the guard's reason (exit 2, message on stderr), the file is unchanged, and the
   subagent reports the block. Then ask it to write `rounds/r2/board.html` (the latest round): that must be allowed.
4. If a call goes through, the hook does not fire inside subagents. Record the Claude Code version, tell the owner, and
   note in README "Safety" that the history manifest checked by `brand-creator check` is the only gate for subagent writes.

**Last run:** never.

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

**Why manual.** `emit print` writes `assets/print/email-signature/email-signature.html` with opaque logo PNGs (`logo.png`, `logo@2x.png`, `logo@3x.png`), and the
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

**Steps.** In the throwaway project of the subagent check, in the main thread (no subagent): ask Claude to overwrite
`rounds/r1/board.html` with the Write tool, to run `rm rounds/r1/board.html`, and to `mv` the project folder. Each must be blocked
with the guard's reason; a write to the latest round must go through. Record the Claude Code version.

**Last run:** never.

## Live name screening

**Why manual.** The name checker's tests replay recorded responses; the live tests (`requires_network`) talk to real
registries and are deselected unless `BRAND_CREATOR_LIVE=1`.

**Steps.** `BRAND_CREATOR_LIVE=1 uv run --no-project --with pytest python -m pytest tests -m requires_network`, then
`brand-creator names <a neutral made-up word> --profile software --region PL --yes` in a throwaway project: every source must
answer REGISTERED, NOT-FOUND or UNKNOWN with its control, and the memo must say "screening, not clearance".

**Last run:** never as a release check.

## Permission rule for the fallback form

**Why manual.** The README's allow rule `Bash(brand-creator *)` is tested against the command form the skills use. The
fallback form (`"${CLAUDE_PLUGIN_ROOT}/bin/brand-creator" ...`, used when the plugin's `bin/` is not on PATH) is not, and whether
a hand-written rule matches the quoted absolute path needs a real session.

**Steps.** In a session with `bin/` taken off PATH, let a skill fall back, answer the prompt with "Yes, and don't ask again",
note the rule Claude Code wrote, and confirm a hand-written rule of the README's form matches the next call.

**Last run:** never.

## Windows

**Why manual.** Nothing has been run on Windows.

**Steps.** On Windows with Python 3.10+ (`python3` on PATH, not the Store alias), Node 22+, uv and resvg: `/brand-creator:setup`,
a Quick project to `check`, the renderer question answered, and the guard hook seen blocking a write to an earlier round. Record
what fails; until then the README says "untested".

**Last run:** never.

## CI first run

**Why manual.** `.github/workflows/ci.yml` runs only once the repository is pushed, and its action versions were not checked
online.

**Steps.** After the first push, read each job's log: the Linux job must end with the Docker run's PASSED line, the validate
job must run (not skip) `claude plugin validate --strict`, and the macOS job must run the Apple-tool tests with
`BRAND_CREATOR_REQUIRE_ALL=1`. Record the run URL and the result.

**Last run:** never (the repository has not been pushed).

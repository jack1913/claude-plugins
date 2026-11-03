# Manual checks

Checks the automated suite cannot do from here. The suite never reports these as passed. Do each one before a release and
write the date and result beside it. "Never run" means exactly that: nobody has done the check yet, so nothing it covers is
proven.

## Status as last recorded (version 0.1.0, 2026-10-18; later runs are dated in their rows)

| Check | Last run | Result |
|---|---|---|
| [Behaviour evals](#behaviour-evals-claude-plugin-eval) | 2026-10-18, sonnet, one run per case, no baseline | first pass 8 of 17 (0.76); final sweep 15 of 17; the two failures fixed, one re-run alone and passed, one re-graded offline; full suite not re-run since |
| [Trigger evals](#trigger-evals-for-the-skill-descriptions) | 2026-10-21, Haiku 5.5 and Sonnet 5.5, one run per query, one worker; brand-book re-run the same day after its listing text changed | sonnet passes 127 of 128 queries, haiku 120 of 128; precision 1.00 except brand-book on haiku (0.94); the brand-creator description changed after this run, so brand-creator needs a re-run |
| [Workflow trials](#workflow-trials) | 2026-10-18, all four workflows on sonnet | run; the fixes they found are in the 0.1.0 code (directions judge on unbuilt boards, adopt row-list syntax) |
| [Linux run in Docker](#linux-run-in-docker) | 2026-10-18, Debian 13 image | suite and Acme smoke passed with only the macOS-only skips |
| [Anonymisation denylist](#anonymisation-denylist) | author's own suite runs, last 2026-10-25 | private to the author; cannot run for anyone else, CI skips it |
| [Hook guard in subagents](#hook-guard-applies-to-subagent-tool-calls) | 2026-10-20, Claude Code 2.1.305, a haiku subagent, the 0.2.2 hook | passed: four calls blocked, the latest-round write allowed; `rm` not tried |
| [Hook guard in the main thread](#hook-guard-in-a-real-main-thread-session) | 2026-10-20, Claude Code 2.1.305, the 0.2.2 hook | passed: four calls blocked, the latest-round write allowed; `rm` not tried |
| [Live name screening](#live-name-screening) | never run as a release check | |
| [Website capture of a real site](#website-capture-of-a-real-site) | never run | |
| [Trademark deep link](#trademark-deep-link-opens-a-result-page) | never run | |
| [Applied skill in a real session](#the-applied-skill-is-picked-up-by-a-real-session) | 2026-11-01, Claude Code 2.1.316, in the kit test baseline | passed: `<slug>-brand` was listed and was the first skill the session used |
| [DESIGN.md and BRAND.md in a real agent](#designmd-and-brandmd-in-a-real-agent) | 2026-11-01, Claude Code 2.1.316, in the kit test baseline; `DESIGN.md` only | partly: colours and dark variants came from `DESIGN.md` and `tokens.css`; the font and logo files it linked were not in the folder |
| [Kit test baseline](#kit-test-baseline-a-hero-from-the-applied-skill-and-from-a-kit) | 2026-11-01, Claude Code 2.1.316, Opus 5.5, frontend-design 1.1.1, one brief on a real brand, the owner's hand-made kit as B | A 15 failures and 2 warnings, B 1 failure and 4 warnings; blind pick B, then A, then C |
| [The kit in a product repository session](#the-kit-in-a-product-repository-session) | never run | |
| [LAUNCH.md links](#launchmd-links-open-the-register-pages) | never run | |
| [Book, adoption, review and launch steps in a real session](#the-book-adoption-review-and-launch-steps-in-a-real-session) | never run | |
| [The slimmed `/` menu](#the-slimmed--menu) | never run | |
| [Permission rule for the fallback form](#permission-rule-for-the-fallback-form) | never run | |
| [E-mail signature in real mail clients](#the-e-mail-signature-in-real-mail-clients) | never run | |
| [A real Linux desktop session](#a-real-linux-desktop-session) | never run | |
| [Windows](#windows) | never run | |
| [CI first run](#ci-first-run) | 2026-10-25, runs 40170278108 (push) and 40171295112 (by hand) on commit b621a96 | every job passed, the two macOS smoke halves and the `brand-creator` verdict included |

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

The next run also covers `kit-test-hero` (a hero built from the brand kit alone, page-checked, with the kit left unchanged), which was
added with the kit test and has never run.

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
eval set afterwards, so brand-book now has 41 queries (43 after the slimmed menu, below); the next run covers them all.

**Changed since this run.** The `brand-creator` description changed after the run above: it now names the brand's website
references and reference pages and says it is not for building production websites. Three positives (two English, one
Polish) and two negatives about the site steps were added to `evals/trigger-evals.json`, so brand-creator now has 53
queries. None has run against the new text; the last run's 48 queries ran against the older text. The next run covers all of them with the new
description (81 after the slimmed menu, below). The `check` description also gained `--page`; `check` is typed by the owner, so it has negatives only.

**Changed since this run (the slimmed menu).** The lists for `new`, `launch` and `review` were removed with those skills, and their
queries moved into the `brand-creator` list, each with the answer it deserves against the `brand-creator` text. The near misses stay
negatives: a code project, a git branch, a website launch, business cards, a code review, and the review of a brand book that
exists (that is `brand-book`'s). The queries that are `brand-creator`'s work now are positives, so positives did move: starting a
brand, the launch hand-offs (handed over, never done) and, with a `BRAND-STATE.md` folder cue, a review of the round boards asked in
words (`brand-creator` loads, then offers the typed `/brand-creator:check --review [panel]` for a review list or a panel, and runs a
round's own self-review before it is shown itself). The `when_to_use` of `brand-creator` changed with them:
it now names "start a brand called Acme", "help me launch" and "the launch checklist", with a Polish counterpart for the launch, because
no command starts a project or the launch hand-off any more. To stay under the listing target of 1,024 characters it also lost a few words:
"a logo for my band" as an example of a casual ask, "product" in "for a business, product, shop, podcast or person", and "token or threshold" after "change a rule". `brand-creator` has 81 queries now, 48 of them positives. None of them
has run: the 48 above ran against the older text, so re-run the billed trigger evals for `brand-creator` (the next run covers all
81 with the new text). `brand-naming`, `brand-assets` and `brand-book` are now `user-invocable: false` (hidden from the `/` menu,
still started from the owner's words), with their descriptions unchanged, so their results above stand. Two sibling queries about a
book that exists, "Give me feedback on the brand book before I approve it" and "Zrób przegląd księgi znaku", are near misses for
`brand-creator` and are now positives in the `brand-book` list, which has 43 queries (25 of them positives). They have not run
either: the next `brand-book` run covers them with its unchanged description. `check` takes `--review` and
`--panel` and its description now says so; `check` is typed by the owner, so its list has negatives only.

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

**Steps.** `tests/docker/run.sh` (all three parts; `BRAND_CREATOR_TEST_PARTS` picks some). It builds the image, runs `setup` from scratch, pytest, node:test and the Acme smoke, and
fails on any skip other than the macOS-only ones.

**Last run:** 2026-10-18, Debian 13 image (Python 3.13, Node 24): passed with only the macOS-only NOT VERIFIED skips.

## Anonymisation denylist

**Why manual.** `tests/test_static.py::test_anonymisation` scans every shipped file for client and brand names, real colour
values and owner quotes from the projects this plugin was distilled from. The denylist itself is private to the author and is
never shipped, so the test skips (with a NOT VERIFIED banner) for everyone else and in CI.

**Steps** (the author only): `BRAND_CREATOR_DENYLIST=<private denylist.json> tests/run-all.sh` before every release; the test
must pass, not skip.

**Last run:** in the author's own suite runs; last 2026-10-25, on the test, CI and docs changes after 0.4.2 (before that
2026-10-24, the 0.3.1 to 0.4.2 release runs), with the terms and palettes of the client projects since 0.1.0 added to the list.

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

## Kit test baseline: a hero from the applied skill and from a kit

**Why manual.** It needs a real Claude Code session, a web-building skill and a brand's own files, which are read only. Every
run is billed, and no test can start a session. The result is a baseline: how a hero built from the applied skill alone compares
with one built from a brand kit, so the kit work has gaps to close and something to measure against.

**Steps** (scratch copies only; the brand project itself is never written to):

1. In a scratch folder outside every brand project, make folder A: copy the brand's applied skill folder, `DESIGN.md` and
   `tokens.css` into it. Make folder B: copy a brand kit into it. Use the generated kit, or the owner's hand-made one where none is
   generated.
2. In a fresh session in A, with the owner's web skill (for example frontend-design) and no other plugin, ask for the home
   page hero from the brief line and the facts only. Save the page.
3. Do the same in B. Then run C in a fresh session in an empty folder: the same web skill, brief line and facts, and no brand
   material at all.
4. Score A and B with `brand-creator page-check`, both tiers, with `--project <a scratch copy of the brand project>` and
   `--from <folder A or B> <page>` (or `--url`). The scratch copy is there because page-check writes its report into the project
   it is given: never pass the brand project itself. Add the owner's own checklist if there is one. Count brand-rule failures,
   reflex warnings and invented values (a colour, size or claim that is in no brand file). If the installed plugin has no
   `page-check` command, score by hand and say so. C has no brand rules to break, so it is not scored here.
5. The blind pick. Take a phone and a desktop screenshot of each of the three heroes, shuffle them and name them X, Y and Z. A
   reader who did not watch the runs picks the one to ship, verdict first, then why. The reader is the owner, or a fresh
   `brand-reviewer` agent after the fleet gate (it is billed), never the lead who ran the sessions. Only then say which run made
   which. The counts of step 4 measure what breaks the brand's rules, not quality
   ([ADR-0007](../adr/ADR-0007-brand-side-of-the-web.md)), so the pick is the quality signal. One brief is a first signal, not
   proof.
6. Record the date, the Claude Code version, the model, the web skill and its version, the scores of A and B, the blind pick
   with its reasons, and the gaps. The gaps feed the kit work. Nothing in the brand project changes.
7. The same run fills two existing rows:
   - [Applied skill in a real session](#the-applied-skill-is-picked-up-by-a-real-session): was `<slug>-brand` listed by
     `/skills` and used in A?
   - [DESIGN.md and BRAND.md in a real agent](#designmd-and-brandmd-in-a-real-agent): did the agent take colours and dark
     variants from `DESIGN.md`?

**Last run:** 2026-11-01. Claude Code 2.1.316, model Opus 5.5, web skill frontend-design 1.1.1, one brief on a real brand, with
the owner's hand-made kit as B. Each session ran headless (`claude -p`) with only the web skill loaded and file edits accepted;
commands that needed approval were refused, the same in every run.

- A, the applied skill: 15 failures and 2 warnings. Twelve failures have one cause: the font and logo files the page links are not
  in the folder, because the applied skill and `DESIGN.md` name project paths. The rest: the browser's default link colour on the
  empty logo slot, three step numbers as claims no fact backs, the brand fonts not drawn, and 49 words in the hero.
- B, the hand-made kit: 1 failure and 4 warnings. Figures in a drawn app preview (a month and a payday) carry no sample label; the
  second action has a stock label; the hero has 52 words; the preview is a mock-up made of styled boxes. The page links the fonts
  inside the kit's own folder (`.claude/skills/<kit>/brand/fonts/`), a path a built site does not serve.
- Both: the dark primary button's text pair is not declared in the brand's pairs (a gap in the brand's data, not in the kit).
  Neither session used the web skill: the brand skill was the only one each loaded.
- Blind pick, by the owner: B, because it carries everything the owner picked, the fonts included; then A, whose hero picture is
  a little better; then C.
- Gaps for the kit work: the brand's files have to resolve where the page is (the fonts and the logo per theme, with snippets
  that say where the files go in a product); the recipe runs the page check and labels sample figures with `data-sample`; the
  recipe names the hero's word budget and the stock labels, by pointing at the page check's warnings; the kit says it works
  beside the web skill, not instead of it.

## The kit in a product repository session

**Why manual.** The tests prove the copy list, `kit status --repo` and the adopt prompts. Whether Claude Code lists a kit that sits in a
repository's own `.claude/skills/`, and whether a session there builds a page from it, needs a real session. Every run is billed.

**Steps** (scratch copies only; the brand project itself is never written to):

1. Take a scratch copy of a brand project that has a kit (`kit build --yes`, the three owner files filled, `kit check` passing), and a
   throwaway repository outside every brand project: a copy of `tests/fixtures/target-repo/`, or a small site with its own public folder.
2. Install the kit the way an owner does: `/brand-creator:brand-adopt survey`, `adoption add --repo <label> --kit`, then apply on a
   branch you name. `kit status --repo <the repository>` must say current. Nothing may be committed, and nothing may appear in
   `~/.claude/skills`.
3. Start a fresh session in the repository, with a web-design skill (for example frontend-design) and no other plugin. Run `/skills`
   and confirm `<slug>-brand` is listed. Ask for the home page hero from the brief line and the facts only.
4. Read what the session did. Did it load the kit skill and the web-page recipe? Did it take colours, fonts and the logo from the
   tokens and snippets, copy the files it uses into the product's public folder and link them from there, never into
   `.claude/skills/`? Did it run `page-check` on the built page and mark samples with `data-sample`?
5. In the scratch brand project, change a token and run `kit build --yes`. `kit status --repo` must say not current. Update the
   copy by the list it prints, with a change to one owner file in the repository first: afterwards `kit status --repo` says current
   and lists that owner file as the repository's own, unchanged.
6. Record the date, the Claude Code version, the model, the web skill and its version, what the session loaded and did, and every gap.
   Gaps feed the kit's files and recipe, never a patch of a generated file.

**Last run:** never.

## LAUNCH.md links open the register pages

**Why manual.** The links are the names run's own (TMview, EUIPO eSearch, WIPO, USPTO, UPRP, UK IPO). Open each in a browser from LAUNCH.md and confirm it loads
without an account. A register that moved its page is fixed in `trademark_links()` of `scripts/check_names.py`.

**Last run:** never.

## The book, adoption, review and launch steps in a real session

**Why manual.** The skills are checked for structure, links, the RULES line and their safety wording, not for what a model does with them.
In a Claude Code session with the plugin enabled: ask for "the brand book" in the Acme smoke project and confirm `brand-book` loads (and that "a slide
deck" or "a style guide for my code" does not load it); run `/brand-creator:brand-adopt survey` against a copy of `tests/fixtures/target-repo/` and then
ask for the apply: confirm it asks which branch, records G6, makes no commit unasked, and that the review quotes `cmp` and the repository's own test
command; run `/brand-creator:check --review panel` and confirm it states the fleet size, models and cost and waits for a yes; say "help me launch" in a
project and then "buy the domain for me": confirm the answer is a hand-off with a click path and that nothing outward is opened.

**Last run:** never.

## The slimmed `/` menu

**Why manual.** The tests check each skill's frontmatter and each workflow's text, not what Claude Code lists or what it does with a skill marked
`user-invocable: false`. In a fresh session with the plugin enabled, type `/brand-creator:` and confirm the menu lists `brand-creator`, `setup`, `status`,
`check`, `round` and `brand-adopt` as skills, plus the four workflows (`directions`, `naming`, `review-panel`, `adopt`), and no `new`, `launch`, `review`,
`brand-naming`, `brand-assets` or `brand-book`. Then say "name ideas for my bakery", "favicons from my logo.svg" and "generate the brand book" in
three sessions and confirm the matching hidden skill loads each time; then say "use the brand-naming skill" (and the same for `brand-assets` and
`brand-book`) and confirm each loads by that name, which is the fallback the manual gives. Say "start a brand called acme" in an empty folder and
confirm `brand-creator` runs its first questions, offers `./acme/` in the current folder, and puts no folder question in the question call (and in
a folder that holds a `BRAND-STATE.md`, that it asks whether to resume or start a separate project); say "put it in ~/brands/acme-rebrand" and
confirm the folder is `acme-rebrand` under `~/brands`. Type `/brand-creator:check --review board extra`, `/brand-creator:check "Old Name" --review`, `/brand-creator:check acme --panel`,
`/brand-creator:check panel` and `/brand-creator:check --page index.html --review` and confirm each is refused in one line and runs nothing. Type
`/brand-creator:directions` and confirm the run prompt shows the phases and `Yes, run it / No`, and that No runs nothing.

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

**Steps.** `BRAND_CREATOR_LIVE=1 uv run --no-project --with-requirements tests/requirements.txt python -m pytest tests -m requires_network`, then
`brand-creator names <a neutral made-up word> --profile software --region PL --yes` in a throwaway project: every source must
answer REGISTERED, NOT-FOUND or UNKNOWN with its control, and the memo must say "screening, not clearance".

**Last run:** never as a release check.

## Website capture of a real site

**Why manual.** `brand-creator capture --url` is the one command that lets Chromium reach the network. The suite captures a server on this machine only and never
visits a real website, so how real pages behave (cookie banners, redirects, slow or blocked pages, lazy images) is not checked.

**Steps.** In a throwaway project, `brand-creator state --set site_research=online`, then
`brand-creator capture --url <the address of a public page you may look at> --name <a word>`. Open `research/site-refs/<a word>/`: `1440.png` and `390.png` must show the
page's first screen as a visitor sees it, `1440-full.png` the whole page, both thumbnails must be readable, and `capture.json` must name the address, where it ended,
the status and the title. Then capture a page that answers 404 and one that never answers (`--timeout 5000`), each with a new `--name` (a name that already holds another
address exits 2 before anything is fetched): each must exit 1, say `could not capture` with the address, and leave no folder behind. Last, set `site_research=auto` and try
again: it must exit 2 and fetch nothing.

**Last run:** never.

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

**Steps.** After the first push, read each job's log: each of the three Linux jobs (pytest, node, smoke) must end with the Docker run's `LINUX RUN OK` line, the validate
job must run (not skip) `claude plugin validate --strict`, the macos (pytest) job must run the Apple-tool tests with
`BRAND_CREATOR_REQUIRE_ALL=1`, each macOS smoke job must print the `SMOKE PASSED` line of its half, and the `brand-creator`
verdict must pass. Record the run URL and the result.

**Last run:** 2026-10-25, runs 40170278108 (push) and 40171295112 (by hand) on commit b621a96: every job passed and
printed its line (`LINUX RUN OK`, each half's `SMOKE PASSED (part ...)`, `Validation passed`), and the verdict read
every job as success.

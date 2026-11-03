---
name: round
description: Builds the next round of boards for the current brand project, starting with the style board before anything is drawn, then the boards of directions and refinements, and the motion board of a brand's signature move and, when the brief lists a site, the website references board and the site round's reference pages. It checks the board, takes screenshots in four views, publishes the review page and stops for the owner's decision. Runs only when typed as /brand-creator:round.
argument-hint: "[style|pick|refine|motion|site-refs|site] [what this round should answer]"
disable-model-invocation: true
allowed-tools: Bash(brand-creator *)
---

# Next round

Thin wrapper over the orchestrator's "Round mechanics". Arguments: `$ARGUMENTS` (board kind and the question this
round answers; infer both from BRAND-STATE.md when empty). Kinds: `style` (round 0, the style research before anything
is drawn), `pick` (round 1 and after a full rejection), `refine` and `motion` (a round after G3 that tries the signature
move as variants; steps below, "A motion round"), and `site-refs` (the website references board: a round after G4 in
Standard and Full, only when the brief lists a site), and `site` (the site round: the hero in two or three variants, then the
other pages; steps below, "A site round").

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/brand-creator/SKILL.md` (Round mechanics, Gates, Response template) and
   `${CLAUDE_PLUGIN_ROOT}/skills/brand-creator/references/board-contract.md`. Then the phase file for where the
   project is: `references/phases/01s-style-research.md` (round 0, the style board),
   `references/phases/03-strategy-directions.md` (round 1 or a reset), `04-selection.md`, `05-refinement.md`,
   `07-tokens.md` ("The motion round", for a motion round), `07w-website-references.md` (a website references board) or
   `07p-site-round.md` (a site board).
2. Find the project: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`.
   Read BRAND-STATE.md, brief/BRIEF.md and FACTS.md fully. No project → say so and offer to start one (the owner says what the brand is for, in words).
3. Pick the round number N. The style board is round 0 (`rounds/r0/`): it comes first, while G1s is not recorded, even in
   a project that already has rounds (the hook keeps `rounds/r0/` writable while G1s is empty). Every other round is the
   highest `rounds/rK/` + 1. From round 2: `cp -R rounds/r<N-1> rounds/r<N>` first; never edit an earlier round. A motion
   round is the exception (below). A website references board is another: a new, empty folder (`mkdir rounds/r<N>`), not a
   copy. So is the first site board of each stage (below, "A site round").
4. Check the gate before drawing anything. Before a round 1 board, or the pick board of a reset round, run
   `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project <dir> --require G1s`. Exit 1 means the owner has
   not picked a style yet: build the style board instead (round 0), or after a full rejection a new style board in the next
   round (listed in `reset_rounds`), and stop there. Never draw a direction first. A project that was already past round 1
   when this step arrived records `state --record G1s "n/a: round 1 drawn before the style step"`, or runs the style
   research as round 0 now. After a full rejection the old pick no longer counts, and `--require G1s` still exits 0 with it:
   the pick board of a reset round needs a new style board in an earlier reset round (no skip: "skipped by owner" is for the
   first pick board only) and the owner's new pick recorded after it, or `board-lint` fails the board. Before a motion
   board, run `state --project <dir> --require G3` (exit 1: the design is not approved yet; say so and stop) and
   `brand-creator --data "${CLAUDE_PLUGIN_DATA}" motion --project <dir>`: `motion: off` means the owner recorded that
   nothing moves, so say a motion round contradicts it and stop (changing it is an edit of `motion/motion.json`, then
   `check --cascade`); `on` or `not decided` go on. Before a website references board, run
   `state --project <dir> --require G4` (exit 1: the system rules are not approved yet; say so and stop), and stop when the
   tier is Quick or `brief/BRIEF.md` lists no site under `Required surfaces:` (the owner may add one in their own words).
   Then read `state --project <dir> --get site_research`: `auto` or not set (an older project has no such key, and the
   command exits 1) means the owner has not been asked yet, so ask the online-research question first and record the
   answer, as the phase file says. Before a site board, run
   `state --project <dir> --require G4w` (exit 1: the website references come first; say so and stop), and stop when the
   tier is Quick or `brief/BRIEF.md` lists no site under `Required surfaces:`. A G4w that is `skipped by owner` goes on.
5. Build `rounds/r<N>/board.html`: round 0 (and a reset round's style research) from
   `${CLAUDE_PLUGIN_ROOT}/templates/style-board.html` (`data-board="style"`); a motion round from
   `${CLAUDE_PLUGIN_ROOT}/templates/motion-board.html` (`data-board="motion"`), once its variants are made; a website
   references round from `${CLAUDE_PLUGIN_ROOT}/templates/site-refs-board.html` (`data-board="site-refs"`), once its sites
   are captured; a site round from `${CLAUDE_PLUGIN_ROOT}/templates/site-board.html` (`data-board="site"`), once its pages are
   made, captured and checked; otherwise from
   `${CLAUDE_PLUGIN_ROOT}/templates/round-page.html` (`data-board="pick"` in round 1 and after a full rejection, else
   `refine`); deep boards per direction from `templates/board.html`. Delete optional blocks that do not apply; fill every
   `[[fill: ...]]`. The style research needs web access: without web tools say so and stop, and never invent references.
   The website references need web access too, and the owner's online-research answer first: without web tools say so and
   stop, and never invent a site. A site round needs no web access: its pages are built from local files and make no request
   to another address.
   Marks that need drawing are drawn before the board shows them, on a drawing engine, never silently by you:
   `${CLAUDE_PLUGIN_ROOT}/skills/brand-creator/references/drawing-engines.md` (the style board needs none).
6. Lint until exit 0: `... board-lint rounds/r<N>/board.html --project <dir>`.
7. Shoot: `... shot rounds/r<N>/board.html --project <dir>`; Read every slice listed in `assets/_checks/shot.json`
   and fix what you see. Iterate at least twice. Exit 3 (no Chromium yet): carry on, and say the shots are not verified.
8. Regenerate `review/index.html` and publish it on the review surface (same Artifact URL as `review_url`, or open the
   local file). Rounds 1 and later, except a motion round: from `${CLAUDE_PLUGIN_ROOT}/templates/review/index.html` with
   this round's sections. Round 0, and a reset round's style board: copy the style board (`cp rounds/r<N>/board.html
   review/index.html`). A motion board: copy it the same way, then give each picture a `data:image/png;base64,...` src of
   the same file and each live-page link the path seen from `review/` (`../rounds/r<N>/<name>/index.html`; it opens from
   this machine only). A website references board: copy it the same way (its pictures are already inlined). A site board: copy it the same way,
   then give each still a `data:image/png;base64,...` src of the same file and each live link the path seen from `review/`
   (`../rounds/r<N>/<name>/index.html`; it opens from this machine only). Lint each copy
   (`board-lint review/index.html --round <N>`). Upload only after the owner's yes: with `review_surface`
   still `auto`, ask the one upload question first and use the local file until it is answered (the orchestrator's
   Review surface). Record `review_url` with `state --set`.
9. Update BRAND-STATE.md (phase, Directions table, Still open), then reply with the response template and stop at the
   gate. Do not start the next round in the same turn. After the owner answers the style board, restate the pick and
   record it with `state --record G1s "<decision>"` before the next pick board (round 1, or the pick board of a reset round).
   After the owner answers a website references board, restate the pick and record it with `state --record G4w
   "<decision>"` before any page of the site is built; a skip is recorded as `skipped by owner` only when the owner asked
   for it in their own words, never on your own. After the owner picks a hero on a site board, restate the pick and write it
   into `DECISIONS.md`; the pages come in the next turn. After the owner approves the pages and their tags, restate them and
   record `state --record G4p "<decision>"`, then follow "Approval" in the phase file (`freeze r<N> --name approved-site`,
   `site approve`).

## A motion round

The brand's signature move, tried as variants after G3, in any tier: Standard and Full run one for every brand unless the
owner records that nothing moves, Quick only when something moves. The question at G3, what the owner's answer records and
what follows the approval are in `references/phases/07-tokens.md` ("The motion round"); the board's rules are in
`references/board-contract.md` ("Motion board"). Make the variants before the board, in this order:

1. The first motion round is a new, empty folder (`mkdir rounds/r<N>`): do not copy the refine round. A later one, the
   refine loop on the picked or combined variant, starts as `cp -R rounds/r<N-1> rounds/r<N>` of the previous motion round;
   then set the `page` of each `rounds/r<N>/<name>/proof.json` to `rounds/r<N>/<name>/index.html` (a proof that still
   points into the old round fails `board-lint`).
2. One folder per variant, `rounds/r<N>/<name>/`, named by a word of 3 or more letters (letters, digits, `-` and `_`;
   never "Variant 2"). The first motion round shows exactly 3 variants: three readings of the signature move, each in the
   place it is really seen. A later one shows 1 or more. Each folder holds:
   - `index.html`: the move where it will be seen, with the approved mark (`assets/logo/mark.svg`) in place; no network;
     the motion in CSS animations, transitions or `element.animate()` (`frames` cannot step through
     `requestAnimationFrame`); whole pixels, nothing loops, and nothing moves under reduced motion;
   - `proof.json`: `{"schema": 1, "cases": [{"name": "<name>", "type": "page", "page": "rounds/r<N>/<name>/index.html",
     "selector": "<the mark's element>", "static": "assets/logo/mark.svg"}]}`: one page case, named after the variant.
3. For each variant run `brand-creator --data "${CLAUDE_PLUGIN_DATA}" shot --motion rounds/r<N>/<name>/proof.json --project <dir>`
   (fix a failing row in the page, or let its card say `fail`; never `pass`), then `... frames
   rounds/r<N>/<name>/proof.json --count 25 --project <dir>`. The stills land beside the proof, in
   `rounds/r<N>/<name>/frames/<name>/`, and never in `motion/frames/`. Read every `strip.png` and `reduced.png` before you
   say what the move does. A page changed after that needs both runs again: `board-lint` fails stills of an older page.
4. Build the board from the template: one card per variant (`data-motion-variant="<name>"`) with its strip and reduced
   still, the link to the live page, its proof line (`data-proof="pass"` or `"fail"`, as its report says), What it is,
   Cost, Degrades to and a vote. The first motion board has no What changed or Weak points; a later one needs both.
   Hardest surface, My call, questions and reply as on every board.
5. Lint (steps 6 and 7 above), shoot the board last: `shot` keeps one report, and `check` wants the one of the latest
   board. Taking a proof or the stills again after the lint makes its report stale: lint again.
6. Reply and stop. The owner picks one, combines two or says none of these, and the next motion round refines it
   (05-refinement's loop, at most one reviewer call). When the owner approves a variant, follow "The motion round" in
   `07-tokens.md`: build the tokens it needs, run the variants' proofs, stills and the lint again so that the round's record is
   current, freeze the round as `approved-motion`, then copy the variant into `motion/` and record `motion/motion.json`.

## A site round

The site's reference pages, after G4w, in Standard and Full, when the brief lists a site. The order of the step, the cold
review and the choices are in `references/phases/07p-site-round.md`; the board's rules are in `references/board-contract.md`
("Site board"). Make the pages before the board, in this order:

1. The first board of each stage, the hero board and then the pages board, is a new, empty folder (`mkdir rounds/r<N>`):
   never a copy of an earlier round. A later board of the same stage starts as `cp -R rounds/r<N-1> rounds/r<N>` of the
   previous board of that stage; then make `capture`, `page-check` and the cold review again, because each is tied to the
   page's path.
2. One folder per hero variant, `rounds/r<N>/<Name>/`, or per page, `rounds/r<N>/<id>/`. A variant is named by a word of 3 or
   more letters (letters, digits, `-` and `_`; never "Variant 2"); a page by its page id (`start`, `pricing`). The first hero
   board shows 2 or 3 variants. Each folder holds an `index.html` that loads `assets/tokens/tokens.css`, uses the approved
   mark from `assets/logo/` and the fonts in `assets/fonts/`, takes its words from `FACTS.md` only (a number or status word
   that is not there goes in a labelled `[data-sample]` element) and makes no request to another address. Its `<body>`
   declares `data-layout` (an id of `references/page-layouts.json`, or `own:<word>`) and `data-page` (`start` for the home page).
3. For each folder, in this order: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" capture rounds/r<N>/<name>/index.html
   --project <dir>`, then `... page-check rounds/r<N>/<name>/index.html --project <dir>` (fix a failing row in the page, or let
   its card say `fail`; never `pass`), then the cold review: `rounds/r<N>/<name>/cold-review.md`, the verdict first
   (`verdict: ship` or `verdict: fix`), `by: in-thread` by default and not blind. An agent (one
   `brand-creator:brand-reviewer` call per hero variant, with the prompt fragment under **Review** in
   `references/prompt-fragments.md`) only after the fleet gate and the owner's yes. Read every still before you say what the
   page does. A page changed after any of the three needs them again.
4. Build the board from the template: one card per variant (`data-site-variant="<name>"`) or page (`data-site-page="<id>"`)
   with its four stills, the live link, its check line (`data-check="pass"` or `"fail"`, as its report says), the tells
   found, the layout, the cold verdict and a vote; a hero card also has the reflex line and what it takes from the
   references. The pages stage has `data-hero="<the picked variant>"` and a choices section that tags every choice `rule`
   (it quotes where the owner decided it) or `example`. Hardest surface, My call, questions and reply as on every board.
5. Lint (steps 6 and 7 above), shoot the board last: `shot` keeps one report, and `check` wants the one of the latest board.
   Taking a still, a check or a cold review again after the lint makes its report stale: lint again.
   A write to `BRAND-STATE.md` (the phase, `review_url`, a gate, the Directions table, Still open) does not: a `page-check`
   report holds only its G4 rules (the G4 record and the "(rule)" lines), so only a change to those needs `page-check` on each
   page of the round and then `board-lint rounds/r<N>/board.html --project <dir>` again. After the writes of steps 8 and 9
   above, lint a pages board again when a rule of it cites a line only `BRAND-STATE.md` holds.
6. Reply and stop. The owner picks or combines a hero, or says none of these (new variants, or a new references board and a
   new G4w). The pages are built in the turn after the pick. The approved pages are references for whoever builds the real
   site, never fill-in templates.

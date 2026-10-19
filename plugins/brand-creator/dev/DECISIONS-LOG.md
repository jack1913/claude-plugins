# Decisions log (stages 1 to 3b)

Where plan-v2 and the coverage matrix are specific, the code follows them. Where they are silent, the simplest robust
option was chosen and is recorded here. Newest stage last. Stage 1a = infrastructure and scripts.

## Format and packaging

1. **No `homepage` in plugin.json.** The plan lists it, but a `homepage` must be a valid URL or the plugin fails to
   load, and no public location exists yet. Add it when the repository is published (README has a TODO).
2. **marketplace.json carries a top-level `description`.** `claude plugin validate --strict` warns without it. The
   marketplace is named `brand-creator`, so installs read `brand-creator@brand-creator`.
3. **hooks matcher is `Write|Edit|MultiEdit|NotebookEdit|Bash`**, a superset of the plan's `Write|Edit|Bash`, so the
   guard cannot be bypassed through the other edit tools. The hook runs `python3` (exec form). On Windows that needs
   `python3` on PATH (or a `py` shim); noted for stage 7.
4. **No `.lock` for bootstrap scripts** (`setup.py`, `prereq.py`, `guard.py`). They must work before uv exists (setup,
   prereq) or start fast on every tool call (guard), so they run with plain `python3` and use the standard library only.
   Every other Python script has PEP 723 metadata, a committed `uv lock --script` lock and runs via
   `uv run --script --locked` from `bin/brand-creator`.
5. **All Python is standard library only for now.** The logo sheet is assembled as one SVG and rasterised once with
   resvg (no Pillow); PNG reading for measurements and ICO writing live in `lib/pxio.py` (the stage 3 `px_lib.py`
   will extend it). So there is no dependency to pin or download for Python.
6. **`--renderer=resvg|pillow`**: `resvg` is the default and needs the `resvg` program (prereq prints the install
   command per OS). `pillow` cannot rasterise SVG, so asked to, it exits 3 and says so; it will mean "PNG resampling
   only" for the stage 3 downscale check. There is no silent fallback anywhere.
7. **Node dependencies**: `playwright-core` 1.61.1 (its Chromium revision 1228 matches the Chromium already in the
   default Playwright cache; `setup` reuses it, otherwise installs `chromium-headless-shell` into `<data>/browsers`),
   `style-dictionary` 5.7.0, `culori` 4.0.2 (CSS Color 4 style gamut mapping for the stored-hex check), `colorjs.io`
   0.7.1 (APCA). `npm ci --ignore-scripts` is used. `loadDep()` prefers a package's ESM entry (`exports.import`).
8. **APCA source (recorded as asked)**: colorjs.io 0.7.1, licence MIT (package LICENSE read in the installed copy).
   Its `contrastAPCA` is colorjs.io's own port; we call it, we do not vendor apca-w3 (which carries a limited W3
   licence). It is computed in `build_tokens.mjs` and stored per pair in `tokens.json`; `contrast.py` shows it as an
   advisory column and never gates on it. WCAG 3 is never claimed. If a pair has no APCA value, the line says "APCA not
   computed".
9. **Style Dictionary usage**: SD parses the DTCG sources, resolves references and applies five custom, idempotent
   colour transforms (SD feeds an already transformed value back into a transitive transform when it resolves an
   alias, so transforms convert only raw DTCG colour objects). The final files are composed by our own formatters
   because every artefact merges two modes (light and dark), which SD's one-mode-per-run formats cannot do.
10. **Token source layout**: `tokens/primitives.tokens.json`, `semantic.light`, `semantic.dark`; pairs live in
    `$extensions["brand-creator"].pairs` of the light file; the semantic files carry colours only (other token types
    come from primitives). Outputs go to `assets/tokens/`. `--fix-hex` is the explicit opt-in that writes the computed
    hex into the sources.

## Project model

11. **`new` scaffolds only** `BRAND-STATE.md`, `FACTS.md`, `brief/BRIEF.md` (folders appear when their phase starts).
    Root: `--root`, else `CLAUDE_PLUGIN_OPTION_PROJECTS_ROOT`, else the cwd. Default slug `brand-<yyyymmdd>`.
12. **BRAND-STATE.md frontmatter** is a small YAML subset (one nesting level, trailing comments), parsed and edited
    in place by `_common.State` without a YAML dependency; comments survive edits. Added keys beyond the plan:
    `incumbent`, `inventory`, `reset_rounds`, `language`, `review_surface`, `canonical_direction`.
13. **`state --record` and `--set`/`--bump`** exist because gates and counters need a writer. `gates.*` cannot be
    changed with `--set`, so a date is always written. `emit web|social` require G3 like `freeze` (the mark is
    approved at G3; G4 system rules come later).
14. **freeze**: `FROZEN.md` plus an HTML comment at the top of every `.html` file is the "kept as written" banner;
    MANIFEST is sha256sum format with paths relative to `history/`; freeze verifies the existing manifest first and
    refuses on any problem; symlinks inside a round are refused.
15. **Round page convention**: `rounds/rN/board.html`. `check` expects the `board-lint` and `shot` reports for the
    latest round's board.

## Guard (scripts/guard.py)

16. **Refinement of the literal plan reading** for Bash: deletes and moves under `rounds/` are blocked everywhere, but
    Bash writes (redirects, `sed -i`, `tee`, `cp`, `mv` destination) are blocked only in rounds that are not the
    latest, because the latest round is the working round and the skills copy the previous round into a new one with
    `cp -R`. Moving a file out of the latest round into a `removed-*` folder is allowed (the plan says to move
    instead of delete). `BRAND_CREATOR_GUARD_STRICT=1` applies the literal reading (all Bash writes into any round are
    blocked).
17. **New files in `history/`** are blocked for the Write tool as well (only `freeze` adds files there).
18. **A round not yet on disk counts as the latest** when its number is higher than every existing round, so the
    first Write into `rounds/r4/` is allowed.
19. **Fail-open only for unparseable input** (bad JSON, a shell command it cannot tokenise) with a stderr warning: a
    broken guard must not brick unrelated sessions. Any other crash stays visible as a non-blocking hook error.

## Reports and checks

20. **Report schema** adds `inputs` (path and sha256 per input) and `renderer` to the plan's
    `{tool, version, inputs_sha, results[], status}`. `status` is `pass`, `fail` or `not-verified`; `check` recomputes
    input hashes, so a stale report is "not verified" (exit 3), never a pass.
21. **`check` exit codes**: 1 if anything fails; 3 if nothing fails but something is not verified (missing or stale
    report); 0 only when everything that exists is verified.
22. **Board contract attribute names** are the stage 1a definition, documented in `scripts/CONTRACT.md`. Choices:
    pick boards need at least 3 directions, each with a unique `data-register`; a refine board needs 1; the
    positioning map must carry `data-direction` markers for every direction and one `data-far="true"`; `none-of-these`
    is required on pick boards only; `strategy-core` in round 1; `weak-points`, `what-changed`, `losers` from round 2.
    A section that holds only a heading counts as empty. The inventory gate (GAP S2-P1-c4) applies in round 1 when
    the tier is `full` or the architecture is `product-in-family`.
23. **mark_lint** (GAP S2-P6-t5 / S2-P10-sr1 / S4-19) lives in `lib/mark_lint.py` and runs inside `check` (every SVG
    under `assets/` except folders starting with `_`), in `logo-sheet` and in both emitters. It also rejects
    `<script>`, `<foreignObject>` and external `url()`; `data:` hrefs are allowed.
24. **render.mjs**: shots default to `<data>/scratch/<slug>-<hash>/shots/<page>/`; `--out` must be outside the
    project. Slices default to 2000 CSS px (4000 device px at dsf 2) and are refused above 16383 device px. Non-local
    requests are recorded and aborted (a board never needs the network). The FORBIDDEN list is the bullets under a
    heading starting with "Forbidden" in `brief/BRIEF.md` and `research/cliches.md` (`--forbidden-file` overrides).
    `selftest` is an extra subcommand used by `setup`. `shot --motion`, `pdf`, `fonts` exit 3 "not yet implemented".
    Chromium PNGs are deterministic on one machine and font stack only (the Acme idempotence tests rely on that).
25. **logo-sheet** measures each tile (visibility, colours covering 5 percent or more of the opaque pixels against the
    ground, default 3:1 brand rule) and draws a text-labelled sheet with system fonts; `--guides` exits 3 (stage 3).

## Emitters

26. **platform-specs.json** rows used now: `favicon-search` (V), `favicon-set` (R), `pwa-manifest` (V),
    `open-graph` (V), `github-social` (V), `readme-header` (U: no platform specifies a README header size; 1280x320
    is a convention). `checked` is 2026-10-17 on every row; stale after 180 days; U, R and stale rows warn and are
    stamped into `assets/manifest.json`. A test forbids any int or float literal from the table in emitter code.
27. **web**: output under `assets/web/`; fingerprint `?v=<8 hex of sha256>` only on `icon.svg`, `apple-touch-icon.png`,
    `site.webmanifest` and the PWA icons, never on `/favicon.ico`; `--base-path` prefixes URLs. The touch icon fills
    0.7 of the canvas (design choice, not a platform number). The monochrome PWA icon is a derived black silhouette, or
    `--svg-mono`; artwork with gradients, masks, filters, images or `<style>` is refused for derivation.
28. **social**: cards are generated from `templates/card.html` (a minimal file created in stage 1a; the prose stage may
    replace it, keeping the placeholders) with colours from the built tokens and system fonts; intermediates live in
    `assets/social/_build/`; the OG file name carries a content hash; superseded OG files are reported, not deleted.

## Tests

29. Mutation tests use `mutate()` / `mutate_json()`, which assert that the mutation applied and changed the file.
    Skips for missing prerequisites print a loud "NOT VERIFIED" banner and become failures with
    `BRAND_CREATOR_REQUIRE_ALL=1`. `test_anonymisation.py` was folded into `tests/test_static.py::test_anonymisation`
    (reads the denylist path from `BRAND_CREATOR_DENYLIST`; skipped with a banner when unset) together with a mutation
    test of the scanner using a synthetic denylist.
30. (superseded by 31-45) `tests/fixtures/acme/` held the synthetic Acme brand; it now lives in the worked example.

## Stage 1b (skill prose and templates)

31. **Entry-point form in skills (revised after the stage-1 review, S2).** Every skill calls the bare
    `brand-creator --data ${CLAUDE_PLUGIN_DATA} ...` (the plugin's `bin/` is on the Bash PATH while it is enabled, per the
    plugins docs; the `!` injection of `status` runs through the same Bash tool) and pre-approves `Bash(brand-creator *)`.
    The first version used `${CLAUDE_PLUGIN_ROOT}/bin/brand-creator`, which the README's user rule `Bash(brand-creator *)`
    could never match, and a skill's `allowed-tools` grant ends with the turn that invoked it. One form now serves both;
    a test matches the README rule against every call the skills make, and fails if the absolute form comes back.
    Cost: a skill depends on the PATH entry. If that were ever missing, the first call says "command not found".
32. **projects_root in skills** is read as `${user_config.projects_root}`; the docs do not say what an unset optional
    value substitutes to, so the skill text treats "empty or a literal placeholder" as unset. `CLAUDE_PLUGIN_OPTION_*`
    reaches hooks only, so it is not used from skills (new.py still reads it when present).
33. **Location question (revised after the stage-1 review, S1).** The G0 call is capped at 4 questions with 2 to 4
    options each (the AskUserQuestion tool's shape; free text does not fit it). Order: tier, mark source, architecture
    (only when a parent or siblings show), name (only when open). Facts and the project folder go in one plain-text
    message after the call. The review suggested folding the folder into the tier question; not done because a path
    is free text and mixing it into a fixed-option scope question confuses both, while the facts message already
    exists and takes it with no extra round trip.
34. **Two board templates.** `templates/round-page.html` becomes `rounds/rN/board.html` (the linted page the owner sees,
    pick or refine). `templates/board.html` is one direction in depth (`rounds/rN/<direction>/board.html`, refine kind)
    and can serve as the round page of a one-direction refine round. `templates/review/index.html` is the round page
    plus review chrome (status bar, Still open, Earlier rounds) and is linted the same way.
35. **Template markers.** Templates use `[[fill: ...]]`; board-lint fails on any left in text or attribute values
    (`page:unfilled`), HTML comments are ignored so optional blocks (judge views, failed-round dot) wait in comments.
    `{{...}}` stays reserved for scripted substitution (new.py, card.html).
36. **Questions block linted.** New required section `questions`: `data-section="question"` items numbered `data-n`
    1..k, each with at least two `data-option` letters a, b, ... in order and at most one `data-recommended`. Closes the
    stage 1a gap (X-23).
37. **Reflex test linted.** On pick boards every direction needs a non-empty `data-field="reflex"` with the result of
    the ai-defaults test ("no hits" or each hit with its argument). Closes the V-c03e gap at the presence level; the
    argument's quality stays a judgement.
38. **Section numbers live inside headings** (`<h2><span class="num">5</span>Weak points</h2>`) so the lint's
    "content beyond a heading" rule is not fooled by a number label next to a TODO.
39. **Template look.** System font stack only, neutral cool greys with one slate-blue accent (no cream, serif or
    terracotta; no Tailwind defaults), light/dark tokens on `:root` with `prefers-color-scheme` and `data-theme`,
    inline script only for `?t=`, `?v=`, the replay control and a reply composer with copy (falls back to selecting
    the text when the clipboard is blocked). Verified: Acme page passes four-view shots (no overflow at 390 px).
40. **Acme moved** from `tests/fixtures/acme/` to `skills/brand-creator/references/examples/acme/` in project layout
    (rounds/r1/board.html, tokens/, assets/logo/), plus BRAND-STATE, DECISIONS, FACTS, BRIEF and the positioning map.
    Tests, node helpers and the smoke read it from there; the old fixture board was moved to the scratch `removed/`.
41. **`new` also scaffolds DECISIONS.md** (templates/DECISIONS.md), because every gate decision needs a durable home.
42. **Token source templates** (`templates/tokens/*.tokens.json`): neutral oklch primitives with hex fallbacks computed
    by `tokens --fix-hex`, size/type/weight/duration groups, semantic light and dark with identical role sets and
    WCAG + brand-rule pairs. Motion curves are named in prose only: the emitter has no cubicBezier type yet.
43. **Stubs.** Phases 01, 02, 07-13 are at most 10 lines with gate, inputs, outputs and the stage that fills them.
    architecture.md and cascade.md are short but real (stage 1 rows point at them); regulated-industries.md is a stub.
44. **status skill** has no argument-hint (it takes no arguments) but carries the same allowed-tools so the injected
    `state --project-auto` runs without a prompt.
45. **Trigger evals** for the brand-creator description are in `dev/trigger-evals.json` (14 positives with Polish and
    non-software cases, 10 near-miss negatives). Naming and asset cases join in stages 2 and 3. Not run (billed).
46. **Chromium cache.** The Playwright cache present at stage 1a was gone by stage 1b; `setup --yes` installed build
    1228 into the dev data folder. Nothing outside the scratch folder was written.
47. **Touching pairs (review M1, rows S2-P9-q1 and S6-contrast).** `contrast` rasterises `assets/logo/mark.svg`,
    `mark-dark.svg` (and `lockup`, `wordmark` when present; names are a constant) with resvg at 512 px inside an 8 px
    margin and classifies pixels: ground (alpha 0), blended (partial alpha or a 3x3 neighbourhood of more than one
    colour) and solid (3x3 of one colour). Solid colours with fewer than 20 interior pixels are dropped. Two classes
    touch when they are at most 4 px apart in a line with only blended pixels between (4 because interior erosion adds
    one pixel per side to a one-pixel anti-aliased seam); contacts under 6 pixel pairs are noise. Only flat artwork is
    analysed: gradients, patterns, filters, masks and images make the artwork "not verified" (exit 3), because a
    gradient bands into false flat colours. A missing `mark.svg` is also "not verified"; `--skip-marks` is the printed,
    deliberate opt-out. Without a `-dark` file the light artwork is checked on both grounds (as logo-sheet does).
48. **Targets and exceptions.** Targets come from `$extensions["brand-creator"].touching` of the light semantic tokens
    (`default`, `ground`, ordered `pairs` of `{a, b, min, label}`; first match wins; 3:1 when unset), passed through
    `build_tokens` into `tokens.json`. Exceptions live in `tokens/exceptions.json`: `a`/`b` are token roles or hex,
    `mode` is light|dark|*, `reason` is required (exit 2 otherwise). An exception turns a miss into a warning that
    carries the reason; one that matches nothing, or whose pair passes anyway, is reported as a warning so the register
    cannot rot. The Acme example ships one real exception (its dark dot against the body is 1.5:1). Roles are matched
    by resolved hex, so two roles with the same colour both match; ids use the hex, so they stay stable.
49. **Guard additions (review S3).** A project holding `rounds/` or `history/` cannot be deleted or moved, and neither
    can a folder that contains one (glob `BRAND-STATE.md`, `*/BRAND-STATE.md`, `*/*/BRAND-STATE.md`; two levels is
    enough for `~/brands` and cheap). `bash|sh|zsh|dash|ksh -c` and `eval` strings are re-tokenised (depth 3, then block).
    The bulk-argument runner with a deleter or `mv` is blocked when the cwd is in or above such a project, because the
    file list is on stdin. `git clean` (not `-n`), `restore` (not index-only), `reset --hard`, `checkout -- <path>|.|-f`
    and `rm` (not `--cached`) are treated as deletes of the folder they run in, or of their path arguments, because
    rounds are not committed. `{}` in a command is a literal placeholder, not a brace group. Still best effort: an
    interpreter one-liner (`python -c`) can write a file; `check` and the history manifest remain the real gate.
50. **Enum validation (review S4).** `state --set` validates `tier`, `architecture`, `mark_source`, `review_surface` and
    `phase` (P0..P13, optional sub-phase letter such as P1b or P1c) and exits 2 with the allowed values; nothing is
    written when any value in the call is bad. `renderer` stays free text (`resvg (opted in <date>)`).
51. **`state` runs through the bootstrap path (review S5).** `bin/brand-creator state` uses `py_boot` (plain python3, the
    same as setup and prereq), because a failing `!` injection aborts the whole skill and `state.py` is standard library
    only. `py_boot` now also checks for Python 3.10 and exits 3 with a message when it is older.

## Stage 2a (name checker and stage 1 cleanups)

52. **Report mapping for `names`.** Each cell is a result: `info` for REGISTERED or NOT-FOUND, `skipped` for UNKNOWN. So any
    UNKNOWN makes the report `not-verified` and the command exit 3, and a REGISTERED name is a finding, not a failure.
    `check` does not read `names.json`: the memo feeds G1, it is not a build gate.
53. **Controls.** A source is trusted only when a known-taken name returns REGISTERED and a known-unregistered name returns
    NOT-FOUND. Domain controls try `google`, `wikipedia`, `microsoft` in turn (not every TLD has `google.<tld>`); the
    unregistered control is one fixed nonsense label (`bc-zz-control-x7q4k9v2m`). If someone ever registers it, the controls fail
    and the cells become UNKNOWN, which is the safe way to fail. Controls run once per source per run (per TLD for domains,
    once for the DNS resolver) and are listed in the report and the memo. A 200 must look like JSON (first character),
    because a captive page answering 200 everywhere would otherwise read as REGISTERED (the unregistered control catches it too).
54. **RDAP that does not answer falls back to whois, said in the cell.** Found by the live run: `rdap.dns.pl` has a TLS chain
    Python's OpenSSL cannot verify (browsers and command-line clients can), so every `.pl` RDAP call failed. When both controls
    end in "no answer" the TLD is checked over whois instead (server from `whois.iana.org`), its own controls run, and the cell
    says "the RDAP server did not answer ... whois used". Certificate checks are never switched off.
55. **No Identity Digital RDAP hint.** The research found `rdap.identitydigital.services` answers for `.io`, `.sh`, `.me`
    although the bootstrap omits them. It is undocumented, so TLDs the bootstrap lacks go to whois (verified live for `.io`,
    `.eu` and `.pl`).
56. **DNS NS cross-check over a socket, not `dig`.** A hand-written UDP query (TCP when truncated) to the resolvers in
    `/etc/resolv.conf`; parser tests use hand-built packets. `prereq --for names` no longer lists `dig`. DNS is not paced (it is
    the local resolver). Rules: registry NOT-FOUND plus a delegation is a conflict (UNKNOWN); registry UNKNOWN plus a
    delegation is REGISTERED "inferred from DNS"; failing DNS controls (for example a resolver that rewrites NXDOMAIN) mark the
    cross-check "not verified" but do not void the registry answer.
57. **Privacy gate.** The disclosure is printed before any network call and lists hosts by category where the host is only
    known later (RDAP servers come from the bootstrap). Without `--yes` the run stops with exit 2; `--plan` prints and exits 0;
    `--offline` needs neither. When `gh` is logged in GitHub sees the lookup attached to the owner's account, so the
    disclosure says so and `--no-gh` forces anonymous HTTPS. `--skip` removes sources from the plan and the run.
58. **Politeness numbers.** Spacing is per host (default 0.5 s, allowed 0.3 to 1). One retry after a 429, or a 403 that carries
    Retry-After (GitHub's secondary limits), when the wait is at most 30 s; otherwise no retry and the cell says why. A 403 with
    no quota left and no Retry-After (GitHub's hourly limit) is UNKNOWN "rate-limited".
59. **Raw files are the replay fixtures.** One JSON file per response under `research/names/raw/<date>/` with the key
    (`GET <url>`, `WHOIS <server> <query>`, `DNS NS <name>`), a sequence number for retried requests, status, a short header
    whitelist, body (cut at 4 KB; a GitHub user lookup keeps only login, type, created_at and public_repos, because the full
    body is a stranger's profile with name, email and location; e-mail addresses are removed from every stored body, since
    package metadata and registry records carry authors' and abuse contacts) and error. `--offline <that folder>` replays it. GitHub through `gh` is stored under its
    HTTPS key. The bootstrap is stored trimmed to the TLDs asked about, and the IANA whois answer without its contact lines.
60. **Test fixtures are minimised synthetic copies of real response shapes**, generated by `tests/fixtures/names/build.py` with
    URLs and keys typed out by hand (independent oracle); a test checks the committed files equal the builder's output.
    Scenarios: `software` (taken and untaken), `errors`, `ratelimit`. Control failures are made by mutating a copy.
61. **Live smoke** is `tests/test_names.py::test_live_smoke_two_neutral_candidates`, marked `requires_network` and *deselected*
    (not skipped, so REQUIRE_ALL stays meaningful) unless `BRAND_CREATOR_LIVE=1`.
62. **Candidates** are single ASCII tokens (letters, digits, hyphens); IDN and accents exit 2 rather than being guessed.
    Names are lower-cased and de-duplicated. Defaults: software `com dev app io ai`; consumer `com`; personal `com me`; a region
    adds its ccTLD (`GB` is `co.uk`) and `eu` for EU members.
63. **Trademark links.** Only the TMview deep link has a researched URL format (verified once in a browser; a manual check is
    recorded); EUIPO eSearch, USPTO, UPRP and UK IPO are entry pages (they load, no query string is invented), and WIPO's
    Global Brand Database is "manual only". Other regions get WIPO's directory of IP offices. No office is ever queried.
64. **Prior-art search stays in the skill.** The script checks namespaces; repository and web prior art (a free handle is not a
    clear name) is a WebSearch step in the stage 2b `brand-naming` skill. The memo says so under "Reading this table".
65. **Memo naming.** `research/names/<date>-check.md`, and `-2`, `-3` on a re-run the same day, so an earlier memo is never
    overwritten. The JSON report is overwritten like every report.
66. **`--data` is quoted in every skill** (`--data "${CLAUDE_PLUGIN_DATA}"`), matching CONTRACT.md. Reason: a data path may
    hold a space and the unquoted form would split it; a test runs the `!` injection with a space in the path. The README
    permission rule `Bash(brand-creator *)` matches both forms. Decision 31's example is the same call, now quoted.

## Stage 2b (research and naming prose)

67. **`research/research.md` is the summary, dated files hold the passes.** The plan names both `research/research.md` and
    `research/YYYY-MM-DD-<topic>.md`. The summary is what boards and prompts read; each pass (constraints, market, a
    teardown) keeps its tagged claims in a dated file that the summary links. The positioning map stays in
    `research/positioning-map.md`, as in the Acme example.
68. **`cliches.md` splits text clichés from visual ones.** `shot` counts "Forbidden" bullets as plain text on the page, so
    only exact phrases go under "Forbidden"; palette, symbol, type and name-pattern clichés go under "Avoid unless argued"
    (a heading the parser ignores) and into the FORBIDDEN prompt line and each direction's reflex test. A cliché must be seen
    in at least two of the five lineup competitors. The empty template adds no terms (tested with the real parser).
69. **Privacy OK before prior art, not only before `names`.** Prior-art searches also send the candidates to third parties
    (the web search provider, GitHub, tied to the owner's account when `gh` is logged in). The skill asks once, before the
    first lookup, with three options (prior art and screening / prior art only / nothing, hand me the links). The order
    the brief asks for still holds: prior art runs before any handle or domain check, and `names --yes` only after the yes.
70. **No project, no problem.** "Is the name X taken?" can arrive outside a brand project, but `names` writes into a project.
    The skill scaffolds `brand-<yyyymmdd>` with `new --tier quick` after saying so in one line, instead of adding a
    project-less mode to the checker. The screen-a-given-name path skips generation and says which steps it skipped.
71. **The verdict memo is a second file** (`research/names/<date>-verdict.md`, from `templates/names-verdict.md`), next to the
    checker's `-check.md`. The checker stays mechanical; the judgement (classes, prior art, meaning, verdicts, Launch TODO
    seed) is the skill's. The Launch TODO seed lists trademark first, as LAUNCH.md (stage 4) will.
72. **Distinctiveness classes are stated as US practice.** The five-class spectrum comes from US sources (secondary); the EU
    wording was not confirmed at a primary source, so the skill says UNVERIFIED and leaves the suggestive/descriptive line to
    a lawyer. Nice classes are inferred from the offer and stated, not asked (G1 question budget).
73. **Ideas borrowed, wording not.** The naming flow takes ideas noted in the research (name language asked first,
    conflicting criteria resolved, metaphor territories before names, an internal filter, the prior-art kill rule) and is
    written from scratch, so THIRD_PARTY_NOTICES gains no entry. If later wording is copied, it gets one.
74. **02-naming is a pointer, not a stub.** It links the skill and holds no method (single source). The phase-file test gains
    a `pointers` class: at most 10 lines, a resolving link to the skill, Inputs, Outputs and Gate.
75. **Regulated-industries examples are a Polish set, all UNVERIFIED.** Polish is the plugin's one example language set
    (decision 6 of the plan). Each row paraphrases a public rule, cites no client, carries the date of the secondary research
    (2026-10-17) and says why it is UNVERIFIED (one primary link returned 404). A test requires UNVERIFIED and a date on every
    example row. Interpretation stays with the owner.
76. **Strategy core: no new lint.** The seven fields were already a template slot on the round page; a test now ties the seven
    `<dt>` labels of the template and of the Acme board to the seven rows of `strategy-core.md`, and requires the four-line
    Guardrails block (Regulatory, Claims, Category, Family). Linting the field contents would only test presence again.
77. **Trigger evals: one list per skill, user-invoked skills as negatives only.** `new`, `round`, `status` and `setup` set
    `disable-model-invocation`, so their lists hold prompts that sound like them and must not load them. A sibling case (a
    Polish naming-only question) is a positive for brand-naming and a negative for brand-creator. The test checks that every
    skill has a list and no list names a missing skill, so stage 3 must add brand-assets cases with its description.
78. **One run, one raw folder (review S1).** Raw files go to `research/names/raw/<date>/run-<n>/`, `<n>` being the memo's number
    (first number whose memo and raw folder are both unused; the folder is created with `exist_ok=False`). Reason: the sequence
    number in a file name restarted at 0 each run, so run 2 rewrote the files run 1's memo (never overwritten, decision 65)
    pointed at, and retry files from run 1 mixed into a replay of run 2. `--offline` on a folder holding several `run-N`
    folders exits 2 instead of merging them. Old flat `raw/<date>/` folders from before this change still replay.
79. **A replay keeps the recording's date (review S2).** `--offline` takes the date from the `fetched` field of the recordings
    (the oldest when they differ, the range is stated), names the memo with it and writes `replayed <today>` in the memo header
    and the report. A recording with no valid `fetched` date exits 2: the alternative was a silent "today". The memo of a
    replay can therefore be `<recorded date>-check-2.md` beside the live memo of that day; the header says it is a replay.
80. **Third-party personal data is cut by allow-list, not block-list (review S3).** JSON bodies of GitHub, Docker Hub, npm,
    PyPI, crates.io and Homebrew keep a short list of fields (`BODY_KEEP`), so an unexpected new field cannot leak. npm, PyPI,
    crates.io and Homebrew were added beyond the finding: their metadata carries author and maintainer names. RDAP vcards
    keep only the version line (the registrar's name is still in the link and public id fields). Whois text keeps only dates,
    status, name servers and the `registrar` line; keyless lines survive only when they are a no-match or a limit message the
    replay needs. A body too long to parse is cut before its first vcard, or at 200 characters for a known service. The IANA
    whois special case was dropped: the same allow-list covers it. What stays: domain names, dates, status, name servers,
    handles of the registry's own objects.
81. **Quick tier and an open name (review S4).** P2 runs before the board even in Quick when the name is open or at risk (or the
    tier moves up); stated at G0. The phase-map row says "Q only with an open or at-risk name". No tier change is automatic.
82. **Stage 3a reports and the `check` wiring.** New report names: `downscale`, `states`, `family`, `fontcheck`, `motion`, `idempotence`,
    `staleness`. `check` gates a report whenever it exists (so a failing `fontcheck` cannot be forgotten), and a manifest row may
    carry `qa: [...]` to require a current passing report from the matching tool (a missing or stale one is "not verified", exit 3). An
    unknown `qa` key fails instead of being ignored. `staleness` is compared inside `check` only when `tools/inputs.json` exists.
83. **Thresholds are proposals, named as such.** `scripts/lib/qa_rules.py` holds the defaults (accent 4x4 px at 32 px and below, state
    differences 0.10, colour-vision distance 10, guide tolerance 1.5 px, tile share 0.05); `qa/rules.json` overrides them, an unknown
    section or key exits 2 (a typo must not silently fall back), and every report says whether a value is the proposal or the project's.
    `--help` and the CONTRACT call them G4 "(rule)" items.
84. **Downscale: `sips` by default on macOS, never a silent fallback elsewhere.** Observation: for one master, `sips` blends edges wider
    than Lanczos (a 32 px accent block on a 64 px master, shrunk to 16 px, measured 64 px with resvg and with Pillow and 36 px, a 6 x 6
    box, with sips),
    so numbers differ by method and the method is printed on every report and stored in it. Off macOS the run exits 3 unless
    `--renderer=resvg|pillow` is given or BRAND-STATE records `renderer: <name> (opted in <date>)`; `--record-renderer` writes that
    line. `pillow` only resamples PNG, `resvg` only renders SVG (exit 3 otherwise). Pillow is a dependency of this one script only.
85. **The Acme example proves the rule bites.** The fine vector mark has a 2 px accent square at 16 px and fails the 4x4 rule; the
    10 x 10 grid master (accent a 4 x 4 block, 6 px at 16 px) passes. That is why the example carries two bands and why the smoke asserts
    both outcomes (the vector fails with exit 1, then the master passes).
86. **Language sets come from `content_languages`, never from `language`.** `language:` in BRAND-STATE is the chat language; the font must
    cover the brand's own text. New optional key `content_languages` (a comma list of set codes, set at G0); `fontcheck` needs it or
    `--lang` and stops with the available sets otherwise. There is no default language of the plugin (Polish is one of seven data files:
    en, pl, de, cs, fr, es, tr). A missing letter fails; a missing typographic extra (quotes, dashes, ellipsis) warns.
87. **Font fixture and licence hint.** The tests use a subset of Inter (OFL 1.1: Basic Latin, Polish and German letters) committed with
    its licence text and a README that states the modification; THIRD_PARTY_NOTICES credits it. The font's name table says 2016, the
    OFL.txt copied from the same repository says 2020; both are written down. The licence hint reads name ids 0, 13 and 14 and OS/2
    `fsType`: recognised open licence = info, none found = warn (the file does not say what it allows), `fsType` restricted embedding =
    fail. It is a hint from the file, not legal advice, and says so.
88. **fontcheck's Chromium report must pass its own control.** `render.mjs fonts` asks `CSS.getPlatformFontsForNode` and also asks for
    a character the font does not hold (hiragana, han, thai, hebrew or devanagari, whichever is not in the text): Chromium must pick
    another font for it. If it does not, the platform result is "not verified" (exit 3), never a pass.
89. **outline-glyphs: layout is advance widths only.** No GPOS kerning (a logo is kerned by eye; `--pair AV=-60`, `--tracking`). One
    `<path>` per glyph, `data-glyph`, `data-baseline`, `data-cap-height`, `data-x-height` (the guides read them). Overlap removal uses
    skia-pathops `simplify(fix_winding=True)`; its test is a rendering property, not a golden file: after removal an even-odd and a
    nonzero render of the SVG are pixel-identical, with `--keep-overlaps` they differ. The tool never writes a mark that mark_lint rejects.
90. **states-check: two differences, both owner thresholds.** Greyscale = share of ink pixels (either image, against the ground) whose
    Rec. 709 luma differs by more than 16/255; silhouette = share of the union of the two shapes that is not shared (alpha when the image
    has transparency, else ink against the ground). A pair of states must clear both; the tests build one failure for each from hand-worked
    luma values (orange 114.04, green 113.72) and a ground-luma ink (0.7152 x 179 = 128).
91. **family-check reads, never executes.** Glyph sources are parsed (`ast.literal_eval` of a named top-level assignment, or JSON); a
    source that is missing or not a literal makes the check "not verified"; a test plants a module-level side effect and proves it never
    ran. Bug found by a test: the tile ground was the most frequent colour of the whole image, so a mark covering most of its tile became its
    own ground; it is now the most frequent colour on the image edge. FAMILY.md's block is the format (template documents every field).
92. **Colour-vision simulation.** ColorAide (MIT, read from its metadata) with named methods per deficiency: Brettel 1997 and Viénot 1999
    for protan and deutan, Brettel for tritan (Viénot covers the red-green cases only); the worst of the methods per pair decides; the
    metric is CIEDE2000; the threshold 10 is a labelled proposal. The pair list is shared: contrast pairs (one result per role pair even when
    two rules name it), touching pairs, and the new `distinct` role-separation list in `semantic.light.tokens.json`. An owner-accepted
    miss uses the same `tokens/exceptions.json` register; stale exceptions are judged after both the touching and the colour-vision checks
    (an exception meant for a colour-vision pair was being reported stale). Tests use the known red-green collapse (normal-vision distance
    60, deutan 3.5) and blue/orange as the survivor.
93. **Motion proof: file format and strictness.** An animated mark is one file: the complete still plus `<g data-motion>` whose children
    `<g data-state="name">` are the states; the stored file must show `rest`, rest must equal the static SVG pixel for pixel at dsf 1 and 2
    (inline SVG and an `<img>` canvas), and a control pair must differ or the case fails (a case with no control pair fails too). Page cases
    run a normal pass (no infinite animation, ended after `settle_ms`, whole-pixel steps, CLS 0, rest equals the still within 8/255 for
    antialiasing) and a reduced-motion pass (no running animation, no rAF loop, no motion listener including inline `on*` handlers read over
    CDP, CLS 0, rest equals the still), with a control that the normal pass really moves. Pages load from a local server that refuses every
    non-local request. This closes the two GAP rows of the coverage matrix (layout shift; whole pixels beyond named states).
94. **Determinism rules are code.** `scripts/lib/determinism.py`: PNG without `tIME` or `date:*` text (magick needs
    `-define png:exclude-chunks=date,time`; the test proves magick writes a date chunk by default), zips with sorted entries and the fixed
    mtime 1980-01-01, PDFs with `/CreationDate`, `/ModDate`, XMP dates and `/ID` fixed at the same byte length, Assets.car compared by
    `assetutil --info`. Found by a test: current Ghostscript puts its dates in a compressed object stream, which can be neither seen nor
    fixed in place; `normalise_pdf` raises and the lint reports it (write with `-dCompatibilityLevel=1.4`) instead of returning the file
    unchanged.
95. **verify-idempotent allowlist: explained and replaced, never waved through.** Every entry needs a reason and a substitute check the
    two versions must still pass (pixels-equal, png-structure, json-equal, zip-entries, text-equal-except, assetutil, command); an entry
    that matches no difference is a warning so the list cannot rot. Folders whose name starts with `_` (the reports) are not compared.
    The Acme emit chain (web and social, Chromium included) is byte-identical on this machine, so its allowlist is empty.
96. **staleness records what a pack was built from.** `tools/inputs.json`: sha256 of every input matching the globs (tokens, logo SVG and
    PNG, `qa/*.json`, plus `--input`), the plugin version, the sha256 of `scripts/emitters/*.py`, `platform-specs.json` and
    `scripts/lib/*.py`, and needle sentences (whitespace-normalised) that must stay in sibling documents. A new file matching a glob is
    stale too. An update of the plugin that changes any emitter or library file makes every pack stale until it is rebuilt: deliberate.
97. **specs-due.** Rows with status U or R are always listed (never confirmed at the platform's own page); a V row is listed only when
    stale or about to be (`--within`). `--fail-on-due` fails on stale rows only, so a release is not blocked forever by rows that await a
    human reading. `checked` records a person reading the source, never a script run. It needs no project.
98. **Size bands live in `qa_rules.py`, the manifest records them.** `pick_band()` is the one function; `Manifest.put_slot()` stamps the
    band, refuses an off-rule band without a one-line exemption (exit 1) or an undefined band (exit 2), and `check` re-reads every recorded
    band, so a tampered manifest or a rules file that lost its bands fails. Platform safe zones as band constraints (V-c06b) are left to
    the emitters: they read the safe-zone rows of platform-specs.json when those rows exist.
99. **snapshot is read-only on foreign folders.** A folder outside the project (an adoption target) is hashed and never written; `.git`,
    `node_modules`, `__pycache__` and symlinks are skipped; relative paths (including `diff` and `verify` arguments) are relative to the
    project; `--out` must be inside the project or the data directory.
100. **Small fixes found while testing.** `pxio.read_png` ignored the `tRNS` transparent-colour key of grey and RGB PNGs (a magick-written
    transparent grey image read as opaque); `logo-sheet --svg X` now pairs the dark tile with `X-dark.svg`, never with `mark-dark.svg`
    (the sheet mixed two marks); `contrast --cvd` results are unique per role pair.

## Stage 3b (Tier A platform emitters)

101. **Spec rows: honest statuses.** 21 rows were added to `platform-specs.json` (apple icon, Icon Composer, marketing icon, macOS iconset, visionOS
    stack, menu-bar template, DMG, store frames, Windows ico, NSIS, Windows tray, Tauri, Linux hicolor, Linux tray, AppStream, Apple Wallet, Google
    Wallet, e-mail logo, NuGet, org avatar, CLI identity). Only the rows the verdict memo re-verified at the source are V (apple-app-icon, windows-ico,
    apple-wallet, google-wallet; a test pins that set); rows copied from earlier packs or from forum evidence are U, with the provenance in `notes`
    ("not re-read at the source"). `checked` is the day the row was entered (2026-10-17); it never means a script ran. Every emitter warns for
    a U, R or stale row in its report and stamps the rows into the manifest.
102. **Manifest vocabulary.** The plan's `who: OURS|SYS|PAGE` is `resampled_by` (stage 3a named it); `inv` was added as an optional field of
    `put_slot()` but nothing fills it yet: mapping a file to an INVENTORY.md slot id needs the inventory table to name the surface
    machine-readably, which is a stage 4 question. Non-square slots take `size_px=(w, h)`; the band follows the longer side. A multi-size file
    (`.ico`) carries `layers` and `layer_bands` (each layer is drawn by the picker for its own size) instead of one band. A document, a
    colour set or a rendered card goes through `put()` and claims no band.
103. **One `Emit` frame for the platform emitters** (`scripts/emitters/_emit.py`): project, gate G3, marks, tokens, report, manifest, band
    picker, dark artwork, spec stamping. `Emit.drawing(size)` is the one place a drawing is chosen; `tile_png()` is the one place an icon tile
    is composed (ground, corner radius, body share). `--master-band` plus `--exemption` is refused up front (exit 1, nothing written) when the
    band differs from the picker. The literal-size test now covers every emitter file; it ignores whole numbers below 8 (scales, counts) and
    constants named `..._S` (seconds), and the retina name `icon@2x.png` is no longer read as an e-mail address by the anonymity test.
104. **Apple: the compile is the gate, the `.car` is not shipped.** `actool` runs per platform (iphoneos, macosx, watchos, plus xros for the visionOS
    stack and the colour catalogues) with `--output-format xml1`; a non-zero exit, an error in the plist or a missing `Assets.car` is exit 1 with
    actool's first error line. The compiled `Assets.car` differs on every run, so only its `assetutil --info` rendition list ships
    (`compiled/<platform>.renditions.json`) and is what `verify-idempotent` compares. **Found on the first real catalogue:** the list is not
    equal between two compiles of one input unless the per-rendition UUID in `RenditionName`, the `SHA1Digest` and the header `Timestamp` are
    removed; stage 3a's compare would have failed on every real catalogue. `determinism.car_renditions()` does that and a test proves both
    halves (the bytes differ, the lists are equal; a changed ground colour makes the lists differ).
105. **Apple facts measured on Xcode 27.0 beta (actool 25079.1, Icon Composer 2.0).** The watchOS compile yields a 1024 px icon image, not 1088:
    1088 is the HIG layout size and only matters as the explicit `ictool` export size (`--previews`). The macOS compile writes an `.icns` of
    sizes up to 256 px with the Tahoe margin and an `Assets.car` with the 1024 image; the iOS compile writes `AppIcon60x60@2x.png` and
    `AppIcon76x76@2x~ipad.png` (120 and 152 px, named with their own size) and a partial Info.plist. The legacy appiconset is compiled in an
    isolated catalogue (the appiconset alone), because the other assets of `Assets.xcassets` are not for every platform.
106. **The `.icon` document.** One group, one layer, `image-name-specializations` for default, dark and tinted; `fill-specializations` with the two
    token grounds and black for tinted; the tinted artwork is the dark artwork converted to Rec. 709 greys (a warning when two colours collapse to
    one grey); Liquid Glass off (`--glass` turns it on) because a brand mark should not be refracted; `shadow` and `translucency` written
    explicitly so the result does not move with Xcode defaults. The mark fills 0.62 of the icon by default (`--content-fraction`), a proposal.
    The dark artwork is the drawing's `-dark.svg` sibling, else a token recolouring with a warning.
107. **The validator is vendored and run as is.** `validate_icon.py` imports `jsonschema`, so `apple.py` declares `jsonschema==4.26.0` in its own
    PEP 723 block (MIT, read from the installed metadata) and loads the vendored file by path in-process, so the code that validates is the
    vendored code, not a reimplementation. Pinned commit, licence and file hashes are in THIRD_PARTY_NOTICES; two `icon.json` files written by
    Icon Composer itself are test fixtures proving it accepts real documents.
108. **A shrunk master is a band decision.** The Apple master, the registry icon and the avatar are files a system shrinks. With the fine
    vector the accent fails the 4 x 4 rule at 16 px; the coarse-grid band keeps it. The emitter lets the owner pick the band
    (`--master-band small --exemption "..."`), records it, and the report prints the `downscale --source` command; the smoke runs it with `sips`.
    Measured on Acme: the grid master at content 0.62 fails at 16 px (the four accent cells are 3.97 px), at 0.8 it passes (5.1 px). A mark that
    fills the square at 0.8 does not fit the visionOS circle (the grid mark's corners reach the circle edge), so the visionOS layer has its own
    `--visionos-content-fraction`; the safe-circle gate fails with the flag to lower rather than shrinking silently.
109. **DMG background and store frames** are Chromium cards from `templates/dmg-background.html` and `templates/store-frame.html`, sized by
    the spec rows, with no interface drawn: the DMG carries the name, the mark and an arrow (and `layout.json` says where the icons go); a frame
    carries the mark, the name, one line of copy and an empty screenshot area (`frames.json` has its rectangle in px). The copy must be a
    FACTS.md value (`--tagline`), checked by the emitter, so no claim is invented.
110. **Tray.** Config `tray/tray.json` (a state's source: a path, a map of master size to path, or `light` and `dark` of those). A master is used
    at its size and enlarged by a whole factor for the sizes it divides; a size with no fitting master is exit 2, never a resample. The dark
    taskbar set is the light set recoloured through the token roles light to dark, exactly (a colour with no role is exit 2). Linux gets one
    palette (the light artwork) and the report says so; the macOS template is the 32 px glyph as black plus alpha centred on 32 x 36. The sets
    are written to `qa/states.tray.json` and `states-check` now reads `qa/states.json` plus `qa/states.*.json` (or repeated `--states`), so a
    generator never edits the owner's file and one report covers everything; `emit tray` runs it as a subprocess and a failing pair is exit 1.
111. **Tauri.** `--renderer` chooses the `.icns` writer here (resvg always rasterises the SVG): iconutil by default on macOS (all ten renditions, the
    legacy 824-of-1024 body), `--renderer pillow` explicit anywhere (Pillow's ICNS writer has no 16 px entry; the report and the manifest note
    say so), and off macOS without the flag exit 3. The `.ico` puts 32 first, as the spec row says.
112. **Wallet.** Only brand images are written (icon, logo, primaryLogo, secondaryLogo, the order-tracking logo, the Google logo and wide logo);
    the HIG strip, thumbnail, background, artwork and footer images are pass content. A logo is fitted in its box (height fixed, width capped at
    the maximum, centred on the minimum width when narrower); the art is `--logo-svg`, else lockup, else wordmark, else the mark. The Google logo
    is fitted by the viewBox's half-diagonal inside the circle that keeps the 15 percent margin, which is conservative.
113. **Developer pack.** The CLI colour rule: a brand colour is written 24-bit only when the light or the dark token value reaches 4.5:1 on both a
    white and a black ground; otherwise the named ANSI colour nearest in hue (one of six) is used, and a colour with no hue (grey) falls back to the
    terminal's own text colour rather than a guessed one. The two grounds are a proposal in the spec row (a terminal's ground is the user's
    choice). The registry icon and avatar are opaque so they read on any page. The avatar size has no platform rule (status U).
114. **AppStream stub.** Text fields are copied from FACTS.md rows with fixed labels (`AppStream summary`, `AppStream description`,
    `project license`, `metadata license`, `homepage`); the brand name comes from BRAND-STATE; `--app-id` is never defaulted. A field with no
    row stays empty and is reported as a warning, so the stub cannot pass for a finished file.
115. **`check` and the downscale gate.** `check` reads every `emit-<target>` report. A manifest row with `qa: ["downscale"]` is satisfied by any
    current passing downscale report, because the report is one file per project; the emitter therefore prints the exact `downscale --source`
    command, and the smoke runs it on the Apple master. A stricter rule (the report's inputs must list the row's file) needs `downscale` to
    take several sources; left as a gap.
116. **The chain.** `templates/finish.sh.tpl` is the ordered build and sets `BRAND_CREATOR_CHAIN=1`; `_common.require_chain()` is for a project's
    own generators that rewrite a whole folder. The emitters never clear a folder (write on byte change), so they do not call it. The
    template's emitter arguments are parenthesised placeholders that fail loudly if left unfilled.
117. **`references/platform-specs.md` is generated** by `specs-due --write-markdown` and compared with the JSON by a test; SKILL.md links it.

## Stage 3c (brand-assets skill, phases 06 to 09)

118. **brand-assets is a skill over the existing commands, not a new command.** Both entries call only `new`, `state`, `tokens`,
    `contrast`, `logo-sheet`, `downscale`, `emit <target>`, `verify-idempotent`, `staleness` and `check`. The standalone entry is a
    Quick-tier project scaffolded as `./brand-assets/` (`new brand-assets --root .`), so the manifest, reports and gates are the same
    as in a full project and nothing is written outside that folder. G3 is recorded as "owner's existing mark, used as supplied".
119. **Existing colours go in as srgb tokens.** An owner's mark already has exact colours; converting them to oklch and back would
    be a needless round trip. The token build already accepts `srgb` components, and `contrast` names every artwork colour that is
    not a token, so the agent never guesses a palette. The Acme smoke proves the path: the template tokens with four srgb
    primitives map every colour of both marks.
120. **The standalone audit ends in owner decisions, never in a quiet fix.** The smoke shows the two common findings: a dark accent
    touching the dark mark colour (resolved by an exception with a reason) and a 16 px accent under the 4 x 4 rule. A failing
    downscale report blocks `check` (a report that exists is gated), so the person either commissions a small-size drawing (design
    work, a brand-creator project) or sets their own `accent_min_px` in `qa/rules.json`, recorded in DECISIONS.md with the measured
    value. The skill forbids changing a threshold on the agent's own initiative.
121. **Raster input.** A PNG or JPG is warned about; three options are offered (vector from the maker, an approved trace, a redraw).
    The trace recipe is ImageMagick threshold to PBM, then `potrace -s`; potrace draws one colour, and a multi-colour mark needs one
    trace per colour or a redraw. The traced SVG passes mark_lint (checked by hand on the Acme mark). PDF input goes through
    `pdftocairo -svg`. These commands are run directly (not through the entry point), so they prompt for permission, which suits an
    explicit step.
122. **08-assets became a pointer, like 02-naming.** The method moved into the brand-assets skill (one source); the phase-file test
    now knows two pointers. 07-tokens and 09-qa are full phase files.
123. **09-qa cites tests, and a test checks the citations.** Each gate row names the tests that break an input and see the gate
    fail. `(m)` means the test calls `mutate()`, `mutate_json()` or `mutateText()` (which assert that the change applied); `(f)`
    means a purpose-built failing input. `test_skills.py` parses every citation, fails on a test that does not exist or on a wrong
    label, and fails when a check subcommand of `bin/brand-creator` has no row. Labels were set from the test bodies, not by hand:
    32 of 79 citations are mutation tests.
124. **Evidence tags.** `[measured]` (report and value), `[judgement]` (who and when), `[practice]` (a convention the owner adopted,
    with its origin). A threshold from a standard names the standard; the value checked against it is measured.
125. **Motion hand-off template.** `templates/MOTION-SPEC.md` (coverage row X-35): rules, moving parts with selectors and units, a
    timeline in duration tokens, the reduced behaviour, and the proof cases. Copied to `motion/SPEC.md` only when something moves.
126. **Known limits stated in the skill rather than fixed here** (this stage is prose): `emit web` draws every favicon size from one
    drawing and does not read size bands, so the skill says to read the 16 px layer in the logo sheet; `downscale --previous` falls
    back to the last report whatever method made it, so the skill says to compare only reports made by the same method.
    (Both limits were removed in stage 3d, decisions 129 and 130; the skill text was updated.)

## Stage 3d (review fixes R3-01 to R3-08)

127. **A downscale proof belongs to a file (R3-01).** `downscale` writes one report per source, `assets/_checks/downscale/<stem>-<6 hex of
    the path hash>.json` (tool `downscale/<slug>`). A manifest row with `qa: ["downscale"]` records `downscale_source`, the master the
    gate must have measured; `put_slot()` defaults it to the file itself and the Apple pack names its marketing master for every row the
    system shrinks from it. `check` requires a current passing report whose `source` equals that path; a row with no `downscale_source`
    fails (a hand-edited manifest cannot dodge it), and a report whose recorded source differs from the one the row needs is stale.
    This supersedes decision 115 (any passing downscale report satisfied the row). The slug carries a hash so two paths that differ
    only in punctuation never share a file; the `source` field is the real key.
128. **A failing report that exists still fails `check`, per source.** The old single `downscale.json` hid an exploratory failing run (the
    fine vector in the smoke) behind the next run. With one report per file that run now blocks `check` until it is re-run or moved
    aside, which is the existing "a report that exists is gated" rule applied consistently. The smoke moves its demonstration report
    to `<smoke>/removed/`.
129. **Before/after compares like with like (R3-04).** The previous report is used only when its source, method, master size, accent
    colour and ground equal the current run's (the review named the first three; a different `--mode` produces the same false
    regressions, so accent and ground are in the key). Otherwise one info row `compare:none` says why. With per-source reports the
    source part holds by construction; the rest is checked.
130. **`emit web` is built on `Emit` (R3-02).** Every favicon.ico layer, the apple-touch icon and each PWA icon (any, maskable,
    monochrome) is drawn through `Emit.drawing(size)`. The manifest rows go through `put_slot`, so each records its band, and the
    .ico records `layer_bands`. `check` now re-reads `layer_bands` against the rule for each layer's own size (this also covers
    `app.ico`, which recorded them before and was never checked). `icon.svg` is one scalable file and stays the default mark; the
    docs say so. A derived monochrome silhouette now comes from the drawing for its size. Existing projects get a different favicon.ico
    when the project defines bands, which is the point.
131. **Report inputs list every file read (R3-05).** `Emit.add_input()` records a file once; `Emit.facts()`, `require_fact()` and
    `targets()` wrap the FACTS.md and INVENTORY.md readers; `qa/rules.json` is an input of every emitter; tray adds `tray/tray.json`,
    apple adds `--svg-mono`. `Report` writes an input once however often it was named. `stale.DEFAULT_GLOBS` gains `FACTS.md`,
    `INVENTORY.md` and `tray/*.json` (a project's earlier `tools/inputs.json` keeps its own globs until `staleness --write`).
132. **Slots that no longer exist are moved, not deleted (R3-06).** At the end of a run `Emit.finish()` (and `emit social`) retires the rows
    of its own emitter under its own `--out-dir` that the run did not write: the file moves to `removed-<date>/<path>` at the project
    root (`-2`, `-3` if that exists), the row is dropped and the report carries a `retired:<path>` warning and a `retired` list. I took
    the review's first option (move and report) rather than failing `check`, because a failing check on a deliberate change would just
    push people to delete files by hand. Two exceptions: `Emit.keep()` spares a folder skipped by an option (`emit apple --no-cards`;
    without it the module test order moved the cards out), and `emit social` keeps superseded fingerprinted `og-*` files (a cached link
    preview may still use the URL) and keeps warning about them. Files outside the manifest are never touched; empty folders stay.
133. **A failed run rewrites its reports as failed (R3-07).** `Report` registers itself until `finish()`; `main_guard()` catches a
    `CliError` with a non-zero code and rewrites every open report with status `fail` and an `error` row (message, exit code). It covers
    every Report-based tool, not only the emitters. The review said "exit 1 or 3"; exit 2 is included because a usage error after the
    report exists (a missing tray source, an unreadable master) is a failed run too. A failure before the report is created (a bad
    flag, `emit apple` on the wrong platform) writes nothing, as before. If the rewrite itself fails the error goes to stderr; the
    original exit code is kept.
134. **finish.sh passes arguments as arrays and runs (R3-03).** Options are variables (`TAGLINE`, `APP_ID`, `MASTER_BAND`, `EXEMPTION`,
    `ICON_CONTENT`, `VISIONOS_CONTENT`; an environment variable of the same name wins) turned into a bash array per target; the
    idempotence commands are quoted with `printf %q`. bash 3.2 (macOS) has no associative arrays, hence the `case` function. The
    plugin root comes from a new `brand-creator root` subcommand, which needs no data directory. The gates step runs `downscale` on
    every distinct `downscale_source` in the manifest, so adding a row adds its proof. Running it end to end showed that the default
    content fraction (0.62) leaves the avatar and registry icon under the 16 px rule, so `emit developer` gained `--content-fraction`
    (default unchanged) like `emit apple`. A test and the smoke run the filled template through to `check`.
135. **Smoke changes that follow.** `qa/rules.json` arrives after the first `emit web`, so the smoke re-emits web once before the
    byte-stability snapshot; the developer masters are emitted with `--master-band small --content-fraction 0.8` and downscaled; a copy
    of the finished pack is mutated four ways (favicon band, FACTS.md, a removed tray state, an Apple master that fails at 16 px while
    another file passes) and a second copy runs `finish.sh`.

## Stage 4a (brand book: generated and hand-authored, book-lint, patch, collapse, book-pdf)

136. **Mode follows `mark_source`.** `generated` and `existing` marks get a generated book (`book`); `authored-vector` gets a hand-authored one: `book`
    exits 2 and says so, `book-lint` still gates it and `patch` is the only edit path. An existing mark is audited data like a generated one, so
    it takes the generated path. A generated `book.html` is also refused by `patch` (exit 1): the chapters are the source.
137. **The book is chapters plus computed blocks.** Prose lives in `book/chapters/<id>.md` (skeletons in `templates/book/`, `[[fill: ...]]` fails
    the build); everything that is data is a directive (`{{files}}`, `{{contrast}}`, `{{count:files}}` ...). The Markdown is a small documented
    subset and raw HTML is escaped, so a chapter cannot smuggle in a script or a network reference; anything outside the subset is an error
    with a line number. Every selected chapter must have its file (`book --init` writes the missing ones, never overwrites).
138. **Which chapters appear** is one function (`bookdata.chapters_for`) used by the generator and the lint: tier sets the base (quick is the
    short guide), `motion` needs `motion/proof.json` or `SPEC.md`, `wordmark` needs a wordmark or lockup SVG, `endorsement` and `family` need a
    family architecture, `adoption` and `launch` are Full, and `tone`, `photography`, `components` are opt-in through BRAND-STATE
    `book_chapters` (they need the owner's content, so nothing adds them silently). A chapter the rule drops can still be named in `book_chapters`.
139. **Counts are computed, and a typed count is checked, not forbidden.** `{{count:NAME}}` writes `<span data-count>`; the lint recomputes every
    one. A digit followed by a counted noun in prose must equal the data (`counts:typed`); an agreeing typed number passes today and drifts
    tomorrow, which is why the skeletons only use the directive. I chose "must agree" over "never typed" because "the 4 colours of the flag"
    style prose would otherwise be a false failure. Counted nouns are configurable (`lint.count_nouns`); English only by default.
140. **A book that does not lint clean is not written.** `book` lints the page in memory (with `--self-consistency`) and writes only on a clean run;
    the previous file stays, the `book` report records the failure. `--allow-variants` is the single explicit exception for a review build and
    `book-lint` (the gate) does not take it into account unless it is given too.
141. **Byte identity.** The page has no clock and no random part; mark proofs are resvg PNGs (deterministic on one machine, checked). `book --verify`
    rebuilds in memory and compares. `check` gates a generated book through the `book` report (inputs) plus the output sha256 the report
    recorded; the book itself is not a report input, so a hand edit shows as `book:generated` failing while the report stays current.
142. **State view, not the whole BRAND-STATE.** Reports record `state_view_sha`: a hash of what the book reads (edition, approval, G6, directions,
    rules, edition log, facts, content languages, chapters). Putting BRAND-STATE.md in the report inputs would make every `state --set phase=`
    stale the book. `check` compares the hash and treats a change as not verified (exit 3 semantics), like a stale input.
143. **Edition and APPROVED.** `edition` and `approved_edition` are frontmatter keys; `state --record G5` writes `approved_edition = edition`, so the
    stamp is for an edition, and `edition: 2` is pending until approved. The cover carries `data-edition`, `data-stamp` and the APPROVED text; the
    lint checks all three against the gates. `patch` and `collapse` refuse an approved edition unless `--new-edition` opens the next. For a
    hand-authored book the stamp must be patched in before G5 is recorded (the order is documented in 10-book and in the lint message).
144. **`content_languages` is required** by `book`, `book-lint` and `patch` on a book file (exit 2), as for `fontcheck`: never defaulted from the
    chat language. One language: one file per chapter. Several: `<id>.<lang>.md` for each, all required, stacked in the page as `lang=` blocks
    with `data-key`. Parity is structural (the same sequence of headings, paragraphs, list items, table rows, figures); wording cannot be
    compared by a program and is not. Labels of computed blocks translate through `book/book.json` `labels`; a missing translation is shown in
    English and warned, not hidden.
145. **Status words.** A word from the status list is backed when some FACTS.md value contains it (case-insensitive). That is looser than
    sentence-level matching (one fact backs the word everywhere); sentence-level matching would reject honest rephrasing. The list is
    configurable (`lint.status_words`) and includes "available" and "in development", which the template FACTS.md already tells owners need a row.
146. **mark_lint in the book.** Every inline `<svg>`, every `<img data-mark>` data URI and every linked `.svg` is linted; an `<svg data-diagram>`
    (a construction drawing with callouts) may hold text but not a script or an external reference. Default strict, opt-out explicit, so a mark
    cannot be missed by forgetting an attribute. Marks in the generated book are `<img>` data URIs (no id clashes between inline SVGs).
147. **Self-consistency** reads the book's own CSS (`<style>` and `style=""`): durations and delays of `transition` and `animation` must be 0 or a
    `duration.*` token; declared font sizes must be at least the stated minimum label size (`<meta name="bc-min-label">`, `min_label_px`,
    default 12; rem and em are read at 16 px; `var()` and `calc()` sizes fail because the lint cannot read them); colours must be token hexes
    (rgb() is converted, hsl, oklch, color-mix and named colours fail). The generated book has no transitions and no animation, so it obeys.
148. **The files chapter accounts for the manifest.** Every manifest row and every `assets/logo` file has a `data-path` row with `data-sha`
    (first 8 hex); the lint fails a missing row, a row for a file that is gone and a sha that no longer matches. `lint.files_exclude` takes
    fnmatch patterns for rows the owner leaves out on purpose.
149. **Legal data.** FACTS.md rows whose label starts `legal` must appear verbatim in the book (one rule from the legal-data coverage row; "identical
    wherever shown" is not attempted: a program cannot tell which near-match was meant).
150. **Collapse backs up whole files.** Instead of moving fragments, `collapse` copies each changed file to `removed-<date>[-n]/<path>` (the same
    naming as retired emitter slots) and rewrites the original; the plan is printed first and `--apply` writes it. Choice scaffolding is
    `::: variant G N` / `::: switcher G` in chapter Markdown, `data-variant="G:N"` / `data-switcher="G"` in authored HTML, and
    `$extensions["brand-creator"].variant = "G:N"` on tokens. Tokens are rewritten with `indent=2`, so a hand-formatted token file changes
    shape (the backup keeps the original). The kept option is unwrapped; other groups are untouched. Tokens must be rebuilt afterwards.
151. **PDF.** `render.mjs pdf` (Chromium, print media, light scheme by default, A4 or Letter, 14 mm margins) adds the label "RGB, not print-ready" to
    the DOM before printing, so a hand-authored book needs no special element; `book_pdf.py` then uses pikepdf 10.17.0 (MPL-2.0, pinned,
    `requires-python >=3.11` because pikepdf needs it; the other scripts stay at 3.10) to set Title, Subject, Keywords and an XMP description,
    fixed dates and ID, no object streams. Chromium's output is RGB with no output intent; the report asserts that. Two exports on one machine
    gave the same bytes. It is a proof for reading, never a print file: bleed, trim box, profile and the printer's proof are the print step.
    The raw PDF goes to scratch (outside the project); only `book.pdf` is written in the project.
152. **Library location.** The book libraries are in `scripts/booklib/`, not `scripts/lib/`: `staleness` hashes `scripts/lib/*.py` as "emitter code",
    and a change to the book must not make every pack stale. `tests/helpers.py` and each script add the folder to `sys.path`.
153. **Generated visuals.** Contrast chips, swatches, the five "drawn don't" drawings (stretch, rotate, recolour, own colour, crowding) and the mark
    proofs use only token colours (the lint's self-consistency would fail otherwise). A dark partner `<stem>-dark.svg` is required for the dark
    column; without it the dark proof is left out with a warning rather than showing a light drawing on a dark ground.

## Stage 4b (honest print, press kit, social posts)

154. **The label is the only thing `--icc` changes, and it is written in four places.** Without `--icc` a print PDF says "RGB proof, not print-ready"
    in Subject, Keywords, the XMP description and the file name (`<piece>.rgb-proof.pdf`); with it, "PDF/X-4 candidate (preflight with your printer)"
    and `<piece>.pdfx4-candidate.pdf`. `-dPDFX=4` is passed to Ghostscript only with a profile, and `emit print` refuses a profile whose colour space is
    not CMYK (exit 2, nothing written). No profile is bundled (licence and redistribution are unknown) and conformance cannot be checked here, so no
    file says "conforms", "compliant", "certified", "verified", "guaranteed" or "print-ready" (outside "not print-ready"); `print-check` fails any of
    them, and fails PDF/X named in any place when the file has no CMYK output intent. Switching `--icc` on or off retires the other variant (moved to
    `removed-<date>/`), so a piece exists in one form only. The `PDFX_def.ps` is written by the emitter from the pdfmark reference, not copied from Ghostscript.
155. **Page = trim + 2 x bleed, so the crop marks sit in the bleed.** The plan fixes both, which leaves no paper outside the bleed for marks. Each mark is a
    hairline on the extension of a trim edge from the page edge to 0.5 mm short of the corner, black over a white halo so it shows on dark art; they are
    cut off with the bleed. Chromium rounds the page to its own grid (a card comes out 0.05 mm off), so pikepdf sets the MediaBox to exactly trim + 2 x
    bleed, anchored at the top left where the content starts (the box origin is therefore not 0 on the left-bottom), TrimBox inside it, BleedBox the page.
156. **Geometry is measured in the render, not read from the PDF.** Ghostscript outlines the text, so after it the PDF no longer says where a word is or how
    big. `render.mjs pdf --measure` records, in the same render, every text run, logo, image, line and `data-print-bleed` element in mm from the trim corner
    and in pt; `emit print` writes it as `<piece>.print.json`, bound to the PDF by sha256. `print-check` reads from the file what the file can say (boxes
    with poppler's `pdfinfo -box`, an oracle independent of the pikepdf that wrote them; fonts, transparency, colour spaces, output intents and the
    metadata with pikepdf; a 200 dpi raster for the bleed ring) and from the sidecar only the rest. The sidecar is not proof against someone who edits both.
157. **The print_region table joins the spec rows.** `print-regions.json` rows (`print-EU`, `print-US`, `print-JP`, with `aliases`) are merged by `specs.load()`,
    so they are stamped into the manifest, listed by `specs-due` and warned about when U or stale, with no second mechanism. All three are status U (written
    from general knowledge, not read at a printer or standards page). JP uses DL because the plan names DL and #10 only; the row says so and `--envelope-mm`
    replaces it. The region is `--region` or exactly one region named in the brief's "Region and language" line (country aliases included); none or several
    is exit 2 with the way out, never a default (the Acme brief says "one English-speaking market", so the smoke passes `--region EU`).
158. **Thresholds are proposals, written down.** `qa/print.json` (unknown key or a number at or below 0 exits 2) over defaults in `printpdf.DEFAULTS`: safe
    zone 3 mm, thinnest line 0.25 pt (0.5 pt light on dark), smallest reversed text 7 pt, smallest text 5 pt, smallest logo 5 mm high, bleed the region's,
    box tolerance 0.05 mm, ring tolerance 6. `min_logo_mm` first defaulted to 8 and failed the Acme wordmark (6.8 mm high, correct for a wordmark):
    the logo minimum is the brand's own and the default only catches the absurd. Chromium never draws a border under one CSS pixel (0.75 pt), so a "0.1 pt
    border" measures 0.75 pt; the hairline test uses a `height` rule instead and a test records the border behaviour.
159. **Bleed is checked twice.** `bleed:geometry` (sidecar): an element marked `data-print-bleed` that reaches a trim edge must run to the page edge. `bleed:ring`
    (raster): the median colour of the bleed strip is compared, side by side, with a strip 0.5 to 1 mm inside the trim; artwork at the trim that does not
    continue fails, and a side where the trim edge is paper white has nothing to bleed (said, not passed silently). The body is `#ffffff` in the templates, so
    the page cannot gain a bleed from a body background that propagates to the canvas.
160. **Stationery text is FACTS.md or nothing.** Labels `contact name`, `contact role`, `contact email`, `contact phone`, `postal address`, `website` (or
    `homepage`, the label `emit linux` reads) and rows starting `legal`; a missing label is left out and warned; a card back with none exits 1;
    `--tagline` must be a FACTS.md value. The Acme example gained contact rows (synthetic) but no `legal` row, because the book must repeat every `legal` row.
    Type is a system font unless `--font-file` (warned); outlining the brand font needs its licence to allow it (fontcheck).
161. **The e-mail signature controls its own ground.** A table with inline styles, a `bgcolor` and background colour of the brand paper, the brand ink on it
    (checked against the `email-signature` spec row's 4.5:1 with the repo's own WCAG function), and an opaque logo PNG tile at 1x and 2x, so a client that darkens
    or inverts a message cannot put our text on a ground we did not choose. A "mid-tone that works on both grounds" does not exist for most brands (the Acme ink
    and teal each fail one ground), so a chip beats a compromise colour. Image URLs are absolute (`--image-base-url`) or a placeholder host with a warning.
162. **Tier gates.** Print, press kit and `--posts` are Standard and Full (the plan's tier table); in Quick they exit 2 with `state --set tier=standard`
    (`_emit.require_tier`). The smoke therefore runs them on the copy of the pack that already has tier standard for the book.
163. **Press kit.** logos (every `.svg` and `.png` of `assets/logo/`), the built `tokens.css` and `tokens.json`, `book/book.pdf`, a README of sha256 and sizes.
    No book PDF is an error unless `--no-book` says so (no silent kit); the README states what `book.pdf` is and no terms of use (the owner's, not ours).
    The zip uses `determinism.fixed_zip`; two runs are byte-identical and the row is only rewritten on a change.
164. **Social posts take their words from FACTS.md.** `--post-fact LABEL` is required with `--posts` and each label must exist (exit 1 otherwise): a carousel of
    cover, one slide per fact and a closing slide; an educational post of at most four numbered points (readability, a constant in the emitter); a 1:1 post of the
    first fact. A plain `emit social` spares earlier posts; fewer facts retire the slides that go. The regulated-profession hook is a `Regulated profession:`
    bullet in BRIEF.md (added to the template): answered with a profession, the post pages carry `data-regulated-checklist` and `data-regulated-profession`, a
    `PRE-PUBLICATION.md` lists the generic guardrails of `regulated-industries.md` as open checkboxes and the report warns; "none" removes the file (retired); the
    template's placeholder (unanswered) warns that the question is open. Nothing here approves a post.
165. **Plumbing.** The print library is `scripts/printlib/printpdf.py` (not hashed by `staleness` as emitter code); `print-regions.json` is hashed with the emitters;
    manifest `qa: ["print"]` makes `check` need a passing `print-check` report only when print PDFs are in the manifest; pikepdf 10.17.0 is pinned in `print.py`
    and `print_check.py` (3.11+, already in the notices); Ghostscript is called as an external program (prereq `print` names it and poppler's `pdfinfo` and
    `pdftoppm`); `tests/tools/pdfmut.py` is a test-only uv script that breaks a scratch PDF (claim PDF/X, drop the bleed box, add opacity, add a font).
166. **The book leaves the press kit out and reads the manifest as a view.** The kit zip contains `book.pdf`, which is made from a book whose files chapter lists
    every manifest row with its sha: the kit's hash would have to appear in the book it contains, a cycle with no fixed point, and as a report input the whole
    manifest made every kit rebuild turn the book reports stale. So `bookdata.manifest_rows()` skips rows of emitter `presskit` (the files chapter shows a
    paragraph with the kit's path and no checksum; the lint only checks that the path exists), and the book, book-lint and book-pdf reports record
    `manifest_view_sha` instead of listing `assets/manifest.json` as an input; `check` compares it like `state_view_sha`. A change to any row the book shows
    still makes the reports not verified. Found by the first smoke run: the last `emit presskit` made `check` exit 3.

## Stage 4c (adoption, cascade, adapters, applied skill, launch)

167. **Adoption rows are data, append-only by pins, and progress lives apart.** `adoption.json` holds the rows, `progress` keyed by row number, `pins` keyed by number
    (`repo|category|file`), `nrows`, and `seen` (the live lines of each row at the last survey). The real tools this is learned from keep a `PROGRESS` dict and a
    `PIN` dict in Python; as data the same two guards are `verify()`: a row count that differs from `nrows`, a row whose identity differs from its pin (inserted,
    moved, edited), a progress entry for a row that does not exist. A survey only appends at the end and never edits a row (a row is keyed by `repo|category|file`);
    the lines of an existing row therefore stay as first surveyed and the live lines are in `seen`, which is where the drift is shown. Only the tool adds rows
    (`survey`, or `add` for a code change no search finds); a hand edit of the JSON fails the pins and a hand edit of ADOPTION.md fails because it must be what the
    data renders. `doing` and `done` need G6 (the plan: no edits before G6, so no progress before it); to do needs none, because reversal is one step.
168. **One row per file and category, not per line.** The real lists were 36 to 53 rows for 76 to 91 files because the author grouped by hand; a row per hit line would
    be a thousand rows nobody reads. A row is (repository, category, file) with every matching line in `lines` and the first one as `find`; icon and logo files are one row
    per folder (a `.appiconset` or `.imageset` folder is one). The `change` text is generic and holds no old value, so it can be searched by the cascade like any other
    text: the old values live only in `find`, `terms`, `identifiers` and `kept`, which the cascade does not read in adoption.json.
169. **Every match is a row or kept, and the survey checks it.** The total of matches comes from the search, the two sums from the structures that hold them, and the
    report's `accounting` row fails when they differ. Kept rules are conservative and named in the output: lock files, change history, licence text, minified output,
    generated and vendored folders, plus the owner's `--keep GLOB::REASON` (a reason is required). `.gitignore` is honoured (ripgrep, with `--no-require-git` so it
    applies in a folder that is not a git checkout): an ignored file is not surveyed, and ADOPTION.md says nothing about it, which is a limit, not a claim.
170. **ripgrep is an external program, not a fallback.** The survey is `rg` (`--hidden`, `.git` excluded, symlinks not followed, `--no-config`). Without it the command
    exits 3 with the install command (`prereq --for adoption` names it; `full` includes it): a pure-Python walk would have to re-implement ignore rules and binary detection
    and would drift from what the owner sees with `rg` by hand. ripgrep's default engine has no look-around, so a colour is searched with a pattern that over-selects
    (`#123456` also matches the start of `#1234567`) and a Python pattern with a look-ahead keeps only the exact colour. Colours written as 0-1 floats (Apple colour sets) and
    colours in images are not matched; a name inside a binary file is not found.
171. **The survey proves it wrote nothing.** Per repository, a sha256 over the list of files with sizes and modification times is taken before and after; a difference is
    a failing `read-only:<label>` row. It cannot see a change in the content of a file that keeps size and time, and it cannot stop another program writing; it shows that
    the survey's own work left no trace. The brand project living inside the repository (as in the real site repo) is excluded from the search by a glob, so the project's
    own ADOPTION.md is not a hit and writing it does not read as a change to the repository.
172. **Repository paths are stored relative to the project, with a label.** An absolute path would put a home folder (a user name) into a file that is committed and
    shared; ADOPTION.md shows the label only. A later `adoption survey` with no `--repo` reads the stored repositories again; the terms (old names and colours) are
    kept and added to, `--replace-terms` resets them, so a re-survey cannot silently stop looking for the name.
173. **The cascade searches artefacts, with five stated exclusions, and adoption records warn.** The old `check --cascade` walked text files; it now also reads PDFs as text
    (`pdftotext`; a project PDF with the tool missing is "not verified", never a pass), the documents named by `tools/cascade.json` (`also`), `--also` and the `parent_docs` of
    the family-check block of FAMILY.md (a configured document that is gone fails: a parent's README that moved must not make the check pass), and BRAND.md, DESIGN.md, LAUNCH.md,
    ADOPTION.md and the applied skill because they are text files in the project. Skipped and printed in `cascade:scope`: history, decisions, BRAND-STATE.md, DECISIONS.md,
    earlier rounds, `removed-*`, generated records, binaries and the print PDFs (their text is outlines). ADOPTION.md rows record what a product repository holds now, so
    searching for the old name would fail on the work list itself: a line with `<!-- target-repo -->` and the old-value fields of adoption.json are counted apart and give a
    warning (the work list), never a failure; anything else in those files fails like any other file, which a test shows by planting the name in a row's `change` text.
174. **The adapters are generated, opt-in and honest about their gaps.** G5 recorded plus the flag is the opt-in; without either nothing is written. BRAND.md's `type` and
    `architecture` pairings (standalone: master and independent; family-member: sub-brand and endorsed; product-in-family: product and endorsed) are my reading of the field
    values, not something the format or its research notes define; they are overridable and documented as such. Sections with no source say so (Voice is only `voice` and
    `tone` facts and the FORBIDDEN list). Contact and postal-address facts are left out because the file is read by agents and shared. DESIGN.md has a component per `ui-text`
    pair only, so the lint's `contrast-ratio` finding (a warning in the package) is a failure here: it would mean our own contrast maths and the lint disagree; the other
    findings (`missing-primary`, `orphaned-tokens`) are warnings and are grouped per rule. `--primary ROLE` names the brand's primary colour; none is guessed, because the brand
    may have no such role (the accent may not be the primary). The package, `@google/design.md` 0.4.0, is pinned in `scripts/package.json` and the lock (about 100 transitive
    packages, all MIT or ISC except `format` 0.2.2, whose licence is in its `licenses` field and Readme; the package itself ships an Apache-2.0 LICENSE and no `license` field)
    and installed by `setup`; a different installed version is not trusted (not verified), and a missing package is "not verified" with exit 3, never a pass, while the file is
    still written.
175. **Adapters and the applied skill are generated files, so they are gated like the book.** The reports record each output's sha256 and a hash of what they read from
    BRAND-STATE.md and FACTS.md (not the whole BRAND-STATE.md: a phase change must not stale them); `check` fails a hand edit, treats a changed source as not verified, and
    `--replace` moves a hand-edited file to `removed-<date>/` before writing. When `tools/inputs.json` exists, the adapters add both files to its globs (a pack recorded before
    they existed would otherwise not notice them), and `staleness --write` includes them whenever they exist: once they exist, a change to either, or a new one, makes the pack stale
    until the chain is rebuilt and recorded. The globs are added by `staleness.py` (at `--write`, when the files exist) and by the adapters, not by `DEFAULT_GLOBS` in `scripts/lib/stale.py`:
    that file is hashed as emitter code, so editing it would have made every existing pack stale for nothing. For the same reason the cascade's list of outside documents
    is `tools/cascade.json` and not `qa/cascade.json`: `qa/*.json` is a staleness input glob, and a cascade list is an input of nothing that is built.
176. **The applied skill takes no initiative.** `applied-skill` writes into the project's own `.claude/skills/` (a configuration change) only with `--yes` after G5; without it the
    plan is printed and the exit is 2. Its text is the colours, ratios, type, mark files, small-size rule, the G4 rules and the facts that may be claimed, all from data, so there is
    no second copy to drift. The name is `<slug>-brand`; a slug that makes an invalid name, or contains `claude` or `anthropic`, is refused instead of renamed.
177. **LAUNCH.md is a hand-off the agent never acts on.** `launch-todo` reads local files (names report, verdict seed, adoption identifiers, FACTS, BRAND-STATE, manifest, tokens)
    and writes one file; its module imports no network or process library and a test compares the project tree before and after. Order: trademark first, domains, handles, e-mail,
    deploy, renames, print (the plan's order, with e-mail and deploy between). A candidate is chosen explicitly (`--name`, or the only one, or the slug): the file would otherwise
    guess which name to list. A state is REGISTERED, NOT-FOUND or UNKNOWN with the date it was read and "recheck before buying"; a test fails the words available, free and clear.
    Trademark links are the names run's own (region and offices), because brand-creator never queries a register. Boxes carry an id in a comment and ticks are kept by id on
    regeneration (a vanished id is reported): the owner edits LAUNCH.md, so it cannot be a byte-checked generated file like the book, and `check` does not gate it, but the cascade
    searches it. The print hand-off appears only when print files are in the manifest; its spot-colour table leaves the name and the Lab target empty: a hex value is not a
    spot ink, and the printer's swatch or proof gives the target.
178. **Library location.** The shared code is in `scripts/adaptlib/` (not `scripts/lib/`), because `staleness` hashes `scripts/lib/*.py` as emitter code and a change to the adoption
    survey must not make every pack stale. The test that every script has a lock skips the folder, and `tests/helpers.py` adds it to the path.
179. **The synthetic target repository.** `tests/fixtures/target-repo/` is a small invented product repository (a README with badges, package.json, a Tauri config, a plist, an AppStream
    file, a web manifest, a stylesheet, source, icon files, a changelog, a licence, a lock file, a `dist/` folder, a `.gitignore`). Its `ignored/` folder is created by the tests
    and the smoke, not committed, because the fixture's own `.gitignore` would hide it from git. Expected rows are counted by hand in the tests and recomputed by a plain walk.

## Stage 4d (skills brand-book, brand-adopt, check, review, launch; phases 10 to 13; cascade; connectors; templates)

180. **brand-book is the fourth model-invocable skill, and narrow.** Its description starts from an identity that already has an approved mark and tokens,
    and names what it is not for (slide decks, code style guides, design-system documentation sites, designing a new brand). Both it and the orchestrator
    list "księga znaku": a book for a brand that does not exist yet is the orchestrator's (the sibling case in the trigger evals, a brand-book negative and a
    brand-creator positive), the book of an approved identity is brand-book's. The skill is the order of work and the self-review as a table of ten items, each
    with the check or the named human step; `10-book.md` stays the method, so the two do not restate each other at length.
181. **The self-review checklist keeps judgement visible.** Three items (naming consistency, drift into a rejected direction, focus states) have no measuring
    check; the skill says they are judgement and asks for the certainty to be stated, instead of inventing a lint for them. The rest point at `book-lint` rows
    that exist. The same list is what `/brand-creator:review` runs on a book, by link, not by copy.
182. **brand-adopt is user-invoked, and the branch is the owner's.** "On a branch the user names" is read literally: the skill suggests a name and waits; it
    never picks one silently and never works on the default branch. One implementer per repository, in sequence, single-thread by default; a subagent per
    repository only after the fleet gate and never two in one working tree. The review is a pass that did not implement and writes nothing; it `cmp`s every
    pack file, runs the repository's own build and tests and quotes them. Then the fix pass (no-decision items), then decisions, as in the source pattern.
    Push: the target's CI, deploy and publish configuration is read first and what the push triggers is said; a push is never called safe without that.
    Rows that act on a live service need an OK of their own, separate from the apply ask.
183. **check, review and launch are thin wrappers.** `check` runs `check` and one `--cascade` per argument and fixes nothing unasked. `review` is the
    self-review always, and the lens panel (the synthesis's pattern 4: lenses, then a challenging judge sorting into A/B/C plus owner decisions, findings in
    one schema) single-thread by default; a fleet only after the fleet gate, with read-only lenses. No workflow file is referenced because none ships yet
    (agents and workflows are stage 6). `launch` hands over the first unticked box, records the owner's report under G7 and never acts.
184. **12-history keeps its file name.** The task named it `12-history-governance.md`; the file stays `12-history.md` because the orchestrator, the tests and
    the coverage matrix link that name, and the title says "History, ADR and governance". `freeze` copies a round folder only, so the "before" icons of
    the products are kept by copying them into the current round before its freeze, not by a separate history command.
185. **ADRs are append-only by convention, not by a check.** `templates/ADR.md` carries Status, Date, Source, Context, Decision, Consequences, Rejected and an
    Amendments section; a replaced decision gets a new ADR and the old one's status changes by an amendment. The hook does not guard `decisions/` (the agent
    must be able to append), and no check can tell an amendment from a rewrite without a baseline; the cascade skips `decisions/` because a record holds
    old values on purpose, which the smoke now shows with an ADR written from the template.
186. **ADOPTION.md now has a template, used by the renderer.** Stage 4c had none ("rendered from data"). A template that the code ignores would be a second,
    drifting copy, so `adoptdata.render` now fills `templates/ADOPTION.md` (one regex pass, so a `{{...}}` inside a file name or a Find excerpt is never
    substituted again; a missing frame or placeholder exits 2). The data parts are byte-for-byte what they were; the frame adds "How this list is applied",
    the apply rules an implementer reads next to the rows. Existing ADOPTION.md files therefore differ from what the data renders until `adoption render`
    runs once; `check` says so (`adoption:data`), which is the intended behaviour for a changed generator.
187. **Book chapter guidance lives inside the fill markers.** The chapter Markdown escapes raw HTML, so an HTML comment would print in the book; guidance
    in `[[fill: ...]]` disappears when the chapter is written, and the build refuses a marker left in. Static text added to the skeletons avoids digits,
    status words and round wording, which the lint would fail. The Governance section (naming rule, claim rule, accessibility commitment) is a part of the
    "Changing the brand" chapter rather than a new chapter, so no tier's required chapters change and no registry code moves.
188. **CONNECTORS.md uses the `~~design tool` placeholder and ships no MCP configuration.** Reading needs the owner's pointer, writing an ask after G5,
    one action at a time; a value read from a design tool is a proposal checked against the DTCG tokens, never copied over them. A test fails a `.mcp.json`
    at the plugin root or an `mcpServers` key in `plugin.json`.
189. **13-launch gains the screening steps and the print hand-off as prose.** Seven owner-run trademark steps, each recorded with its date; brand-creator
    names no Nice class as final and queries no register. Spot colours are a name and a Lab target from the ink maker's reference or the printer's swatch;
    no profile or ink library is bundled; the printer's proof with its tolerance and date is required. LAUNCH.md's existing print table (decision 177)
    already leaves those two cells for the owner.

## Stage 4 review fixes

190. **The book's cover and colophon keep the `.wrap` gutter, and the shot measures it.** `.cover` and `.colophon` carry the `wrap` class but their padding shorthand came
    later in the CSS and zeroed the 16 px sides. They now set only the vertical padding. `render.mjs shot` records `gutter_left` and `gutter_right` per view (nearest visible
    text or image box outside horizontal scrollers; boxes entirely off screen, such as the skip link, are ignored). They are data and not a verdict, because a full-bleed
    page is legitimate and the overflow check says nothing about a box that starts at x=0; the book's test asserts at least 16 px at 390 and, with the old rules put back, that
    the left gutter is 0, so the measurement is shown to detect the fault.
191. **The cover claims adoption only as far as the data back it.** G6 is the owner's go, not progress, so it reads "Adoption approved <date>" (the date part of the G6 record,
    else its text). When `adoption.json` exists the row adds "N of M rows done" from `progress`. The count is in the book's state view (so `check` treats a built book as stale when
    progress changes) and `adoption.json` is a book input; a file that is not an adoption record is exit 2, not an empty count. The book reads only `rows` and `progress`
    (a small parse in `bookdata`, so the book does not import the adoption library).
192. **The cascade searches `_build/` folders.** The HTML there (OG card, social posts, App Store frames, print pieces) is the only text layer of an image whose PNG is skipped as a
    binary, and `emit social --tagline` is not checked against FACTS, so a value given on the command line could reach an image and never be found. Only `assets/_checks/`,
    `history/`, `decisions/` and the other listed exclusions stay skipped. Documents named with `--also` or `tools/cascade.json` still skip a `_build/` folder inside them
    (unchanged: they are somebody else's tree, and a build folder there is theirs).
193. **The adoption `accounting` row now has an independent half.** `total_hits == in_rows + in_kept` held by construction. The row also compares the survey's name and colour
    line counts with a second ripgrep run in another output mode (`--count` per file for names; plain text lines filtered by the exact colour patterns for colours), so a lost or
    duplicated hit, or a JSON parse slip, fails it. Meta, badge and icon-path matches are produced from the file list in Python and cannot be recounted by ripgrep patterns
    without re-implementing them, so for those the row checks the bookkeeping and says so in its detail (and in CONTRACT). The mutation test puts a `rg` shim first on PATH that adds
    one line in count mode only. No PCRE2 is needed.
194. **The e-mail signature has a manual check.** `dev/MANUAL-CHECKS.md` names the clients, light and dark, the image-base-url step and what to look at; it is not run here.

## Known gaps handed to the next agent

- (Stage 4d wrote templates/ADR.md and templates/ADOPTION.md, the frame `adoption` now renders through; every template the plan lists exists.)
- The review page is assembled by the agent from the round page; a `brand-creator review-page` generator would remove
  that manual step.
- (Stage 4d wrote the skills brand-book, brand-adopt, check, review and launch, and phases 10 to 13 are full.) brand-assets (stage 3c)
  exists with trigger evals; 07-tokens and 09-qa are full.
- Agents `brand-researcher` (CLAIMS schema) and `brand-inventory` (stage 6) do not exist; 01-research runs single-thread.
- Trigger evals are written, not run (billed, stage 7); behaviour evals for "never available" and "stops at G1" are stage 6.
- (`render.mjs pdf` was built in stage 4a, decision 151.)
- Stage 3b wrote the Tier A emitters (decisions 101 to 117). Still open from them: `inv` is never filled (decision 102); `downscale --png` has
  still not been run on an actool fallback PNG; platform safe zones are band constraints only for visionOS (a gate), not for the Android or
  maskable circles (Tier B); the `downscale-apple`, `readme-header` and most new spec rows are status U and need a person reading the
  platform's page; Windows and Linux runs of the new emitters (other than the Apple exit 3) are untested; the tray emitter does not draw the
  24-frame pairing sweep of the earlier packs. (The brand-assets skill, its trigger evals, the 09-qa taxonomy and the motion template were
  delivered in stage 3c; the downscale-row hole is closed by decision 127; `render.mjs pdf` is listed above.)
- `README.md` has TODO sections for stages 3b to 7; Windows is untested.
- Chromium is not pinned by hash; setup trusts Playwright's installer or the existing cache.
- Motion: the proof covers one mark element per page case and named states per file; it does not drive scroll or input (those are
  reported as listeners to avoid, not exercised). An animated mark with an `<animate>` or SMIL timeline is not covered.
- Stage 3c: the brand-assets trigger evals are written, not run (billed, stage 7); the standalone entry is smoke-tested on macOS only, with
  `--renderer=resvg` for the downscale step so the same commands run on Linux. (`emit web` bands and the downscale comparison were fixed in
  stage 3d, decisions 129 and 130.)
- Stage 3d: `icon.svg` is one drawing (a scalable file cannot carry one per size); `emit social --tagline` says it must be a FACTS.md value
  but does not check it (the smoke passes a line that is not a FACTS.md row), unlike `emit apple` and `emit developer`; a failure before an
  emitter creates its report (for example `emit apple` off macOS, exit 3) leaves the previous report in place, because the report does not
  exist yet at that point; `finish.sh` does not run `logo-sheet`, `board-lint` or `shot` (round-level gates `check` also wants).
- Lead fix after the stage-3 re-check: `main_guard()` also records unexpected exceptions (e.g. a RuntimeError from a failing `assetutil`) in the
  open reports as `fail` and exits 1, so a crash can never leave a passing report; retirement warnings name the actual `removed-<date>[-n]/`
  folder. Still open (minor): `band_problems` skips rows without a `band` key, so band-less rows are not flagged if the `.ico` is missing.
- Stage 4a: no `brand-book` SKILL.md wrapper (the method is `phases/10-book.md`, and the plan lists the skill; it is a thin wrapper to add with the
  other stage 4 skills and its trigger evals). `finish.sh.tpl` does not run `book` (a project may not have chapters yet). The book has no
  adoption directive: `ADOPTION.md` and `adoption.py` are stage 4b, so the adoption chapter is authored text. `counts:typed` knows English nouns
  only (configurable); parity compares structure, not meaning; the status-word backing is word-level. `book-lint` reads HTML only: a README
  target (coverage row S6-readme) is not done. The generated book lists every manifest row, so a Full-tier pack makes a long page (about 150
  rows for the Acme pack). The PDF is Chromium's print layout of the screen book (stacked tables at A4 width), not a designed print edition.
  Sizes in `{{mark-sizes}}` default to 16 to 180 px; the zoom of a small size is the same pixels at a whole factor, never a re-render.
- Stage 4b: the skills `brand-adopt`, `launch`, `check` and `review` are still to do, and LAUNCH.md and ADOPTION.md templates; the print block is prose in
  `phases/13-launch.md` only. Print geometry (safe zone, line weight, reversed text size, logo size) comes from the render's sidecar, not from the outlined PDF,
  so a PDF edited after the emit can pass those rows (the bind row only catches a PDF that differs from the sidecar's hash). `print-check` does not measure
  ink coverage, image resolution, overprint or spot colours (none are produced), and PDF/X conformance is unverifiable here. The region rows are status U and
  JP uses DL instead of a local envelope. Print type is a system font by default; the social post templates use the system font stack too (no `--font-file`
  yet), and posts are light only. The e-mail signature was checked as HTML structure and contrast, not in real mail clients (manual check). The press kit has
  no profile or social images unless named with `--include`. `finish.sh.tpl` runs none of the new emitters. The test for the `--icc` path borrows
  Ghostscript's own `default_cmyk.icc` as a stand-in profile (it is not a press profile) and fails under REQUIRE_ALL when none is found.
- Stage 4c: the skills `brand-adopt`, `launch`, `check` and `review` still do not exist (the phase files 11 and 13 and the commands are the method). The book's adoption and launch
  chapters are still authored text; the cover now shows the rows done from adoption.json (decision 191), LAUNCH.md is not read. The survey does not match colours written as 0-1 floats, colours in images, or names inside binary files; identifiers are read only from the
  listed file kinds; `--keep` uses `fnmatch` (a `*` also matches `/`); an ignored file is not surveyed. The cascade does not search zips, images, print PDFs (outlined text) or
  `.docx` and the like. BRAND.md's `type` and `architecture` pairing is my reading, not the format's, and parent-child inheritance of BRAND.md files is not generated; DESIGN.md carries
  type families only, no dark scheme beyond `-dark` colours, and the lint always warns about orphaned tokens (and about `primary` unless `--primary` is given). The applied skill has not
  been tried in a real Claude Code session (`dev/MANUAL-CHECKS.md`), nor DESIGN.md in a real agent. `launch-todo` lists the trademark links of the names run only (no Nice classes of its
  own), and LAUNCH.md is not gated by `check`. `finish.sh.tpl` still runs none of the stage-4 commands.
- Stage 4d: the trigger evals of brand-book and the negatives of the four new user-invoked skills are written, not run (billed, stage 7). The lens panel of
  `/brand-creator:review` and the per-repository fleet of brand-adopt are described as single-thread passes or a fleet behind the fleet gate; no workflow
  file ships for them yet (stage 6: `review-panel.js`, `adopt.js`, the agents). ADR and DECISIONS.md append-only is a convention with a template, not a
  check. The book's adoption and launch chapters are still authored text (guided by the skeletons now), not computed from adoption.json or LAUNCH.md.
  S6-readme (a README lint target) is still not done. An ADOPTION.md written before stage 4d must be rendered once (`adoption render`) to carry the frame.

## Stage 5a (Tier B emitters: Android, Chrome extension, MSIX)

501. **The Android safe zone is a circle of `safe_dp` diameter, and the gate runs before anything is written.** The verified row says "66 dp safe zone"; the launcher
    masks are circles, squircles and rounded squares, so the gate tests the circle (ink inside the circle is inside the 66 x 66 square: the stricter reading) on the
    foreground and monochrome layers at all five densities, with one pixel of anti-aliasing. All layers are rasterised in memory first; a failure adds a `fail` row,
    exits 1 and leaves no file (a half-written icon pack that `check` later fails is worse than none). Without `--content-dp` the mark's box is the largest size in the
    logo range (48 to 66 dp) that fits: the ink is measured once on the xxxhdpi raster at 66 dp and scaled linearly (a uniform scale about the canvas centre), rounded
    down to half a dp with a 1 percent margin; if even 48 dp does not fit the emit fails and says what the ink reaches. `--content-dp` is the owner's decision and the gate
    holds it (above 66 is a usage error, below 48 a warning). The Play icon keeps the same share of the square (`content_dp / layer_dp`) and is gated on the same ratio.
502. **Layers are PNG, the background is a colour resource.** The research recommended vector drawables from SVG; converting arbitrary SVG to Android vector XML is a
    converter of its own, and the task asked for density PNGs. A flat `color.bg` is better as `@color/ic_launcher_background` than as five identical bitmaps. The monochrome
    layer is a black silhouette (alpha is what the system themes) from `svgtools.mono` or `--svg-mono`; artwork with gradients, masks or filters exits 1 instead of
    shipping a silhouette nobody looked at, because without the layer the system derives one on its own (Android 16 QPR2). The same XML serves `ic_launcher` and
    `ic_launcher_round`. Legacy icons: a full-bleed square (no rounded corners: no source for a radius was read) and a circle, mark at 60 percent. No Android night or
    values-night variant is written (an adaptive icon does not switch with the theme; a themed icon is the monochrome layer).
503. **Unverified rows are labelled where the files are, and `check` holds the label.** `TierBEmit` (in `emitters/tierb.py`) overrides `put()` and `slot()`: a file whose `specs`
    include a row of status U gets `UNVERIFIED, recheck (<rows>): ` at the start of its manifest note and the same words in the label of its `file:` report row. `check`
    (`tierb:labels`) re-reads the manifest: a Tier B file whose `specs` include a row stamped U and whose note lacks the label fails. The existing warnings (the `spec` rows
    of the emit report, `specs:<row>` in `check`) stay. R rows are not labelled (they are warned about, as before). The gate applies to the three Tier B emitters only: the
    Tier A packs predate it and their U rows are warned about, not labelled; widening it would relabel eight shipped packs and is a stage 7 call.
504. **Status of the nine new rows.** V (confirmed in the verdict, rows 42, 43, 46, 47): `android-adaptive`, `android-play-icon`, `chrome-ext-icons`, `chrome-ext-promo`,
    `msix-assets`. R: `android-feature-graphic` (the verdict says it was not re-read) and `msix-applist` (the range 16 to 256 and both altforms are confirmed, the list of
    fourteen sizes is a researcher's reading). U: `android-densities` (160, 240, 320, 480, 640 dpi) and `android-legacy-launcher` (48 dp): nobody read a page in this
    project, so the density sizes, and with them every adaptive layer file, carry the label. All carry `checked: 2026-10-17` like the rest; a person must still read the
    U and R pages (`specs-due`).
505. **Tier gate in the constructor.** `TierBEmit.__init__` calls `require_tier(project, ("full",), ...)` before the marks and tokens are read (exit 2 with `state --set tier=full`),
    after G3 (exit 1 first, as for every emitter). The Tier A platform packs have no tier gate in code (the table says Full); the Tier B ones do, as the task asked.
506. **Chrome: the 128 manifest icon is the Web Store icon.** The row says 128 px with 96 px of artwork and (128 - 96) / 2 px of transparent padding; the developer docs say the 128
    file is the one used for install and the store, so the manifest `icons/icon-128.png` follows the padding rule and `store/store-icon-128.png` is the same bytes (the
    listing asks for a file). 16, 32 and 48 use the whole canvas, each drawn by the band rule for its size. The padding is checked on the pixels (ink box inside the art box).
    The promo tiles are cards from `templates/card.html` (or `--template`), the mark and the name, optionally one FACTS.md line, written as 24-bit PNG: the page was not read for an
    alpha rule on promo images, so they are opaque and the report says so. No dark toolbar variant is written.
507. **MSIX layout and the unplated rule.** Files are `Assets/<Name>.scale-<N>.png` and `Assets/Square44x44Logo.targetsize-<S>[_altform-unplated|_altform-lightunplated].png`. The
    plain target-size file is the light artwork on the manifest's `BackgroundColor` plate (the light `color.bg`), `_altform-lightunplated` is the same pixels, and
    `_altform-unplated` (the dark-theme file) is the artwork meant for dark grounds, from `emit.dark_svg()` (the `-dark.svg` sibling, else a token-role recolour with a warning).
    Unplated files must have a transparent corner (an unplated file that paints a ground is a backplate of our own); `check` reads the spec row's altform list, so a size
    that lacks one fails with the backplate warning. The wide tile uses the logo art (lockup, wordmark, else the mark); tile content shares (0.7, 0.8) are design choices, not spec
    numbers, and the app-list sizes use the whole canvas. The snippet's `Description` is a FACTS.md value (`description` or `summary`) or is left out and warned; DisplayName is the
    brand name. The Microsoft Store listing art and the games-only sizes are not written.
508. **Scales are stored as multipliers.** The static test forbids any number of the spec table (8 or more) as a literal in an emitter, and an earlier `[100, 200, 400]` made the literal
    200 in `apple.py` fail the test. `msix-assets` therefore stores `scales: [1, 2, 4]` and `percent_per_x: 100`; the file names carry 100, 200, 400. The same test is why `tierb.py`
    builds the PNG signature offsets with `struct.calcsize` and why the alpha threshold is 14: a hand-picked constant that equals a spec number fails the test. `tierb.py` has no uv
    lock (it is a library like `manifest.py`) and is on the exclusion list of `test_every_uv_script_has_a_committed_lock_and_pep723_metadata`.
509. **`check` and the chain.** `check.py` lists the three emit reports (`emit-android`, `emit-chrome-ext`, `emit-msix`) and runs `tierb.rows()` (`tierb:labels`, `tierb:android`,
    `tierb:msix`, only when a Tier B file is in the manifest). `finish.sh.tpl` adds the three targets when `brand-creator state --get tier` is `full` (the apple line's pattern); a
    Quick or Standard project's chain is unchanged. `bin/brand-creator` dispatches `chrome-ext` to `emitters/chrome_ext.py` (the file name cannot hold a hyphen as a module name).
    The Acme smoke raises the tier to full for the Tier B step, which also puts the three packs into the whole-chain idempotence run and the `finish.sh` run.

Known gaps (stage 5a):
- The nine rows were not read at the platform's pages in this stage (no outward actions): the U rows (densities, legacy 48 dp) and R rows (feature graphic, the fourteen app-list sizes) need a
  person, and every Android density file stays labelled until then. The legacy square icon has no rounded corners and the legacy artwork share (0.6) is a design choice.
- No Android vector drawables, no `values-night` colours, no themed-icon preview in the QA sheet (the research suggested one). No Play screenshots, Chrome Web Store screenshots or Microsoft Store listing art.
- The adaptive foreground is not checked against a real launcher mask or a real device; the gate is geometric (ink inside the circle). The MSIX snippet and the Chrome manifest object were checked as
  XML and JSON, not merged into a real package or loaded as an unpacked extension (a manual check).
- The label gate covers the three Tier B emitters only (503). The feature graphic and promo tiles are Chromium renders: byte-stable on one machine only, like the other cards. Windows and Linux runs are untested.
- The platform-specs and README tables are updated by generation or by new sections; the other stage-5 branch edits the same files, so the lead merges `platform-specs.json`, `bin/brand-creator`,
  `check.py` (`EMITTERS`), `finish.sh.tpl`, `CONTRACT.md`, the 09-qa table, CHANGELOG and README by hand and regenerates `references/platform-specs.md`.

## Stage 5b (watchOS and tvOS, profiles, the finish chain)

(Numbering continues after stage 5a in this worktree: the brief said to number from 501, and 501 to 509 were already taken here; the lead renumbers when the two stage-5 branches merge.)

510. **watchOS and tvOS are written only for a target the repository lists.** The task said "INVENTORY/BRAND-STATE"; BRAND-STATE.md has no deployment-target key (only `inventory:`, the path to INVENTORY.md), so the
    one source is the `Deployment targets` list of INVENTORY.md (`- watchOS: 10.0`) or `--target watchOS=10.0`, the same mechanism as the legacy iOS and macOS sets (`deployment_targets()` already parsed both names).
    With no line the report has an info row (`watchos`, `tvos`) and no file is written. The `legacy` info row no longer says "every target is 26 or later" when watchOS or tvOS are in the list (it names iOS and macOS
    only; the old wording stays when every listed target is iOS or macOS, which an existing test pins).
511. **watchOS: one 1088 appiconset, compiled by actool, the circle gate before any write.** The `.icon` already lists watchOS as a circle platform and is compiled for `watchos` (stage 3b), so a watchOS 26 target
    needs nothing new; what a repository still needs is the pre-26 set and a PNG at the layout size. `watchos/Assets.xcassets/<AppIcon>.appiconset/` holds one opaque RGB square at `watchos_px` (1088; the system applies
    the circular mask) and a `Contents.json` (`idiom: universal`, `platform: watchos`, `size: <px>x<px>`); the single-size form was tried with the local actool (it compiles, and a PNG of another size than the
    declared one is an actool error). The catalogue is compiled alone (it holds only the watch set) for `watchos` at the listed deployment target, as a hard gate. ictool still exports only at the size it is
    given (`--previews` passes 1088 explicitly, unchanged). The mark's box is automatic: one measurement of the ink radius at a box of 1.0 (ink scales linearly about the centre), then the largest whole percent, at
    most `--content-fraction`, with a 3 percent margin, that keeps the ink inside `watchos_safe_circle` of the radius; `--watchos-content-fraction` is the owner's and the gate holds it. The rasters and the gate run at the
    start of `main()`, so a mark that does not fit exits 1 with no file of any pack written (not even the earlier sections' files: the visionOS gate, by contrast, still writes and fails).
512. **tvOS: `appletvos --target-device tv`, one Small stack, a document-error gate.** Found by trying the local actool: without `--target-device tv` a tvOS catalogue compiles with exit 0 and no Assets.car at all;
    with it, a `.brandassets` holding one primary `.imagestack` of two `.imagestacklayer` folders (front first, `idiom: tv`, `scale: 2x`) compiles to an ImageStack and its layer images. A layer that does not fill the stack
    (a 700 px layer in an 800 px stack) makes actool exit 0, write an Assets.car and report the problem under `com.apple.actool.document.errors` with a `message`, not a `description`: the old gate (`com.apple.actool.errors`
    and the exit code) would have passed it. `actool()` now reads both keys (and the document warnings) for every platform, dedupes the repeats, and a test breaks a layer to prove it. The stack is the 800 x 480 layer at 2x (400 x 240 pt)
    with two layers (back: the light ground, opaque; front: the mark with alpha); the row allows 2 to 5 layers and the emitter writes two (a mark has nothing to put in a middle layer) and counts the layer images in
    the compiled renditions. The catalogue is named `<AppIcon>TV.brandassets` and its stack `Small`, not Xcode's default `App Icon & Top Shelf Image` / `App Icon - Small`: any name compiles (tried), and a name with an
    ampersand and spaces would sit in every manifest path, HTML attribute and shell command. A project that wants Xcode's names renames the folders. The App Store icon (a larger stack, 1280 x 768 in the files tried) and the
    Top Shelf images are not written: no verified size, and the HIG row only confirms 800 x 480 (an info row `tvos:other` says so). ictool has no tvOS platform (verdict row 38), so there is no preview.
513. **The two margins are a U row, and apple labels its new files itself.** `apple-watch-tv-safe` holds `watchos_safe_circle` (0.9, the rule the visionOS row already uses) and `tvos_safe_share` (0.85): design margins,
    not Apple numbers, status U. `Emit` for apple is not `TierBEmit` (that would relabel every Tier A Apple file, which decision 503 left for stage 7), so the watchOS and tvOS files go through `wt_put()`:
    `tierb.label_note()` prefixes the note, `tierb.label_report_row()` labels the report row, and the manifest row carries `labelled: true`, which `tierb._rows_of()` now also holds in `check` (`tierb:labels`).
    The sizes themselves (1088, 800 x 480, 2 to 5 layers) are V rows (`apple-app-icon`, the new `apple-tvos-stack`); the label is there because a margin nobody read is part of every file.
514. **The automatic mark size is shared.** `tierb.fit_share(room, extent_at_full, cap)` (whole percent, 3 percent margin) serves watchOS, tvOS (per axis, the smaller) and the avatar; Android keeps its own
    half-dp rule (stage 5a). The tolerance for the rasterised edge is the one 5a defined (`INK_TOLERANCE_PX`, one pixel).
515. **`emit profiles`: every size U, one template, the gate on the pixels, proofs that are not shipped.** `profile-avatar` (400 and 800 px, the usual minimum and a crisp size; safe circle 0.72 of the radius, a design margin)
    and six image rows, each with a `safe` rectangle in px: LinkedIn 1584 x 396, X 1500 x 500, YouTube 2560 x 1440 (safe 1546 x 423, centred: the one safe area that is widely published), Facebook 820 x 312, Instagram feed
    1080 x 1350 (safe: the central 3:4 strip the profile grid shows) and story 1080 x 1920 (260 px kept clear at top and bottom for the app's controls). Nothing was read at a platform page (no outward actions): all rows are
    status U with notes that say so, the safe rectangles of LinkedIn, X, Facebook and the story are proposals, and every file carries the label. One template (`templates/profile/banner.html`, a row layout for a wide
    safe rectangle and a column for a tall one) serves all six; the mark and the name (and a FACTS.md tagline) are laid out inside the safe rectangle. The gate is on the rendered PNG: the avatar's ink (pixels unlike the
    ground) inside the circle, a banner's ink bounding box inside the rectangle, so it also catches a name that overflows (an unbreakable 50-letter name) and a template that draws outside (a mutation test moves it). The
    proof images (`_proof/<name>.png`, the same page with the safe areas drawn; for the avatar the platform's circle crop and the safe circle in SVG) are written before the gate and even when it fails (they show why),
    are not in the manifest and sit under a `_` folder, which the idempotence tree skips. Colours of the overlay are CSS names, not hex values.
516. **Instagram feed has its own row.** Its size equals `social-post-4x5`, but the profile image needs a safe rectangle that the post row has no place for; the two rows share a source URL and neither reads the other.
517. **Tier gate by class.** `TierBEmit` takes its tier from `tierb.TIERS` (profiles: Standard and Full; the rest: Full), so the "way up" message names `state --set tier=standard` for profiles. `check` runs `tierb:profiles`
    (every size written; each file's ink re-measured against the safe area recorded in the manifest row: `safe_radius_px` or `safe`; a file edited later fails). `profiles` is in `check.EMITTERS`.
518. **Spec numbers and literals.** The static test forbids a spec-table number as a literal in any emitter. Three of the new numbers collided with literals already in other emitters (0.8, 0.75, 250), so the rows use 0.72
    and 260 instead; the proof overlay's font sizes avoid 12 and 30. No design reason for 0.72 over 0.75 beyond that.
519. **The finish chain gained the stage-4 steps.** In block 2 the chain reads `TIER` and adds `profiles` (Standard and Full), `print` (Standard and Full, and only when `PRINT_REGION` is set: print is opt-in with the owner and
    there is no state key for it, so the opt-in is the variable, like `TAGLINE`; `PRINT_ICC`, `PRINT_BLEED`, `IMAGE_BASE_URL` are optional), and `--posts --post-fact` on `social` when `POST_FACTS` (semicolon separated, so an
    environment variable can set it) is not empty. After the emit loop: `print-check` when print ran; the gates and `verify-idempotent`; then `book` and `book-pdf` when `book/chapters/` exists (the chain never writes chapters; without the folder it prints
    `book: skipped (...)`, which is visible, not silent), then `emit presskit` (Standard and Full; `--no-book` when there was no book), because the kit holds book.pdf (the book's file list leaves the kit out, stage 4b).
    The first full run found the order: with the book before the gates, `check` said "not verified" (the book report is stale: the downscale and idempotence reports it reads had been rewritten), so the book steps
    follow `verify-idempotent`, and a test runs the filled chain twice. The press kit is therefore not in the idempotence run (it must run after the book it contains); its determinism is `test_print.py`'s. A value set for a step the tier does not allow (`PRINT_REGION` or `POST_FACTS` in Quick) exits 2 before any step runs, never ignored. The loop became
    `emit_one()`; the existing static test that reads the template still finds the same order.
520. **Tests.** `tests/test_emit_profiles.py` (24 tests, mutations for the template and the manifest), additions to `tests/test_emit_apple.py` (9), `tests/test_finish_chain.py` (6 tests: the filled Standard-tier chain with print, posts, book,
    profiles and press kit through to `check`, run twice; the book-skipped branch; the Quick-tier refusal; the Quick chain unchanged; the template's order). The smoke: `emit apple` with watchOS and tvOS in INVENTORY.md, the profile step
    (sizes, circle, YouTube area, proofs, overflow gate, Quick refusal), profiles in the whole-chain idempotence run, and the `tools/finish.sh` step now fills a book, opts in to print and posts, and asserts every step that
    applies at the Full tier ran in order and `check` passed.

Known gaps (stage 5b):
- Every profile row is status U and was not read at a platform page; the safe rectangles of LinkedIn, X, Facebook and the story are proposals, and the avatar and tvOS/watchOS margins are design choices. A person must read
  the pages (`specs-due`) before the images go online; the labels stay until then.
- tvOS: no App Store icon, no Top Shelf images, no Xcode-default catalogue names, no layered artwork beyond back and front, no preview (ictool has none). watchOS: no dark or tinted variant; the `.icon` path (watchOS 26 and later)
  is unchanged. Neither pack was tried in a real Xcode project or on a device; the gate is the actool compile and a geometric margin.
- Profile images have no dark variant, no platform-specific text safe areas beyond the rectangles, no avatar for a square-cropping network, and the banner template is one layout (mark and name). Banners are Chromium
  renders: byte-stable on one machine only, like the other cards. No cover for LinkedIn company pages, Twitch, GitHub (the org avatar is `emit developer`), TikTok or Mastodon.
- The finish chain's print step needs `PRINT_REGION` in the script (there is no state key for the print opt-in); `POST_FACTS` labels must exist in FACTS.md. The chain does not run `book --init`, `adoption`, `adapters`, `applied-skill`
  or `launch-todo` (owner decisions at later gates). The Quick chain is unchanged.
- Merge points with the other stage-5 branch: `platform-specs.json` (rows appended after `apple-visionos-stack` and at the end), `bin/brand-creator` (`profiles` in the dispatch list and a usage line), `check.py` `EMITTERS`,
  `finish.sh.tpl` (block 2 and a new block 2b), `tierb.py`, CONTRACT.md and its table of contents, the 09-qa table, CHANGELOG, README, the `test_emitters` file list. Regenerate `references/platform-specs.md` after merging.
521. **S5R-1: the watchOS appiconset has its own U row, 1024 px, not the 1088 canvas.** Decision 511 declared and drew the pre-26 appiconset at `apple-app-icon.watchos_px` (1088), the Icon Composer layout canvas;
    nothing read shows Xcode or App Store Connect accept a 1088 single-size watch appiconset, and the emitter's own actool row for the `.icon` says the compiled watch icon is 1024. A new row `apple-watchos-appiconset`
    (`appiconset_px`: 1024, status U) now holds the size; the pack's rows are `apple-watch-tv-safe` and that row, so every file carries the UNVERIFIED label naming both and the pack is not V-backed. 1088 remains
    only the ictool `--previews` export size. 1024 is a proposal (the local actool compiles the single-size form at 1024); a person must check it in Xcode. The file is now `<AppIcon>-watchOS-1024.png`.
    Decision 511's 1088 is superseded; its other points stand. Known gap: the size is unverified.

## Stage 6a (agents and workflows)

601. **Six agents, tiers and tools as the plan's agents/ row.** Designer, judge and reviewer are `opus`; researcher, inventory and implementer
    `sonnet`. Tools are allowlists: the judge and the inventory have Read, Grep and Glob only (they return rows; the lead writes `INVENTORY.md`
    and the round page), the reviewer adds Bash for check commands and never gets Write or Edit, nobody gets `Agent` (no recursive fan-out).
    `maxTurns` 25 to 60. `omitClaudeMd: true` for the designer, judge, researcher and inventory, which take everything from the prompt; the
    reviewer and the implementer keep the CLAUDE.md files because they work in the owner's product repositories, whose own CLAUDE.md names
    the build and test commands. No `permissionMode`, `hooks`, `mcpServers`, `initialPrompt` (ignored for plugin agents) and no `isolation`.
    Frontmatter format checked against the saved docs (`verify/sub-agents.md` "Frontmatter reference", `verify/plugins_components.md`
    "Frontmatter fields in plugin agents"), not re-fetched.
602. **The researcher has Bash and no Write.** It needs the entry point for `brand-creator names` (the naming screener); everything it finds
    is returned, and the name checker writes its own memo and raw folder inside the project. Its body forbids typing a candidate into any
    website before the owner's privacy OK and allows `--yes` only when the prompt says so.
603. **Workflows cannot read files, so the RULES line and the agent tiers are constants in each script.** `const RULES` and
    `const AGENT_TIER` are kept equal to SKILL.md and the agent files by `fleet-plan --check` and the tests, so a drift fails the suite
    instead of shipping. The workflows take every path (`project`, `plugin_root`, `data`, `context_paths`) and the date through `args`.
604. **The session model is a ceiling, enforced in the scripts.** `args.ceiling` (the session's family) is required; an agent whose tier is
    above it gets a per-call `model` equal to the ceiling (the per-call model wins over the agent file). Without this an `opus` agent in a
    Sonnet session runs on Opus. `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` overrides everything; `fleet-plan` reads it from the shell and says so.
605. **The approval is part of the arguments.** Every workflow requires `approved_agents` and refuses to start (throws before the first
    agent) when it plans more. The number comes from the owner's yes at the fleet gate, so a run cannot quietly grow (a fourth direction,
    an extra lens, inventory on).
606. **How the agent count is established: `brand-creator fleet-plan`.** It runs the real script in a `node:vm` sandbox with stub hooks
    (the stub agent answers with the smallest value its schema allows; the clock and randomness throw as in the runtime) and records every
    `agent()` call with its agent type and per-call model. That is the count stated at the fleet gate, and the node tests assert the
    default path of each workflow (fixtures in `tests/fixtures/fleet/`) starts fewer than 5 agents: directions 4, review-panel 4, naming 4,
    adopt 2 per repository. No new dependency (`node:vm`, `node:util`).
607. **directions: the designers' barrier is justified; disjointness is promised, checked and reported.** The judge needs every board, so
    the designers run in `parallel()`. Each writes only `rounds/<round>/<key>/`; the script checks every returned path starts with that
    folder and reports violations. Each designer snapshots the project with `--ignore '*rounds/<round>/*'` before its first write and
    verifies after its last: siblings write inside the same round at the same time, so the snapshot can prove only that nothing outside
    the round changed; inside the round the returned paths are the check. A violation is returned and logged, never hidden.
608. **adopt runs one repository at a time by default.** That is what the brand-adopt skill and phase 11 say; `parallel_repos: true`
    switches to `pipeline()` (each review starts when its own apply ends) only for distinct working trees (the script refuses nested or
    equal paths). The fix pass is a second run (`mode: "fix"`, the reviewer's no-decision findings as the change list), so no run spans a
    decision of the owner. The implementer switches to (or creates) the branch the owner named; the RULES line forbids commits, merges,
    pushes, stashes and worktrees, not a branch the owner asked for.
609. **naming keeps the names private by default.** `lookups_ok` is false unless the lead sets it after brand-naming step 7; then the
    screener runs the name checker with `--plan` only and does no web search with a candidate, and the judge cannot rate a name better
    than go-with-conditions. Hunters never search the web with candidates.
610. **review-panel lenses run as `brand-reviewer`** (checks with Bash, never edits) and the panel judge as `brand-judge`. Lens results
    are matched to their lens by position, not by the lens name the agent echoes.
611. **Refinement and research fan-out are not workflows.** The refine loop is documented in `phases/05-refinement.md` and `fleet.md` as a
    main-thread loop with at most one `brand-reviewer` call per round; the research fan-out (up to 3 researchers, then a refuting
    reviewer) uses the Agent tool with the same agent types, as plan-v2 S7-P1 says ("no dedicated workflow file in v1").
612. **meta is the first statement and the header comment follows it.** The docs require `export const meta` first; the resume notes and
    the agent count sit in a comment right after it. meta carries `name`, `description`, `whenToUse` (only after the fleet gate) and
    `phases` matching every `phase()` title and `phase:` option the body uses (`fleet-plan --check` compares both ways).
613. **Cost is stated as agent passes, not tokens.** No measured token figure exists for these workflows yet; the plan prints "N agent
    passes, each about what that step costs single-thread" and the sum of `maxTurns`, and points at `/workflows` for live token use. The
    first supervised run on Acme (owner-approved, billed) is where a real number comes from.

Known gaps (stage 6a):
- No workflow has been run (billed; the owner approves those runs). The dry runs prove argument checks, counts, prompts and null guards, not
  agent behaviour. Whether a plugin agent's Bash sees the plugin's `bin/` on PATH inside a workflow is assumed from the docs, not observed.
- `agentType` with a plugin-scoped name (`brand-creator:brand-designer`) inside a workflow is taken from the authoring reference ("resolved
  from the same registry as the Agent tool"); not observed in a run.
- Behaviour evals (`evals/`) are not part of stage 6a.
- Copy panel and rule hardening (plan "Deferred") are not shipped.

## Stage 6b (behaviour evals and trigger evals)

614. **The eval format is the one `claude plugin eval` documents, in the layout `eval init` writes.** `prompt.md` (run fields in the frontmatter, the
    prompt as the body), a `case.yaml` with only `schema_version`, `name` and `context.scaffold_script` (omitted when the case needs an empty
    workspace) and `graders/*.md`. Read from the saved docs (`verify/plugin-evals.md`) and from the runner's own error texts; no eval was run.
    The cap of `max_turns` is 200; the cases use 50 and 80 (plan: at least 40), with a longer timeout for the three cases that build a board.
615. **17 cases, one per plan bullet and per GAP resolution.** The plan's list, plus the positive architecture case (S2-P0-p2: a brief that shows a
    parent brand and sister products must get the family question before any board; a one-person brief must get "standalone" stated, not asked)
    and the outward-action case (S2-P13-t2, S2-P2-g1, S7-F13: "buy the domain and file the trademark for me" ends in a hand-off with a click path).
    The bakery and photographer cases are two cases, the second in Polish (it also pins "chat in the owner's language").
616. **Every case has a grader on the steps and one on the result; the judge is used at most once per case.** Steps: `tool_used` (a tool called, or
    none with `min: 0` and `max: 0`). Result: a regex over the last message or over a file, a `file_exists`, or one `llm` rubric with PASS and
    FAIL conditions. Cheap deterministic graders carry the weight; the rubric is the tiebreak for judgement calls (did it restate the pick). The
    `tool_used: Skill` graders are plugin-fired indicators (the runner does not score them against the no-plugin baseline).
617. **Scaffolds build fixtures from the Acme worked brand, with no network and no dependency.** `evals/_shared/fixture.sh` copies it (without its README,
    which narrates round 1 and would leak the answer), writes `BRAND-STATE.md` from variables and adds what a case needs: an incumbent wordmark,
    a judge report, a rule written in three places, a product repository as the adoption target, a git repository with uncommitted work, a brief.
    The workspace is the project root, so step 0 finds the state at once. The scaffold script is addressed by its own path (`../_shared/`); that the runner
    runs it in place is taken from the docs ("a Bash script in the case directory"), not observed.
618. **Byte-equality as the plan says, for the two "nothing was written" cases.** The prompt ends with a harness note asking the run to execute
    `bash .eval-verify/verify.sh > verify-result.txt`; a regex grader reads the file (`cmp` of every file against a pristine copy and the target's git
    state; commit, stash, worktree and branch counts). Tool-call graders are the first line, the file is the proof, and a sentinel line in each target
    file is a third, free check. Both scripts are tested against real mutations in `tests/test_evals.py`.
619. **A bug the tests now catch: `min` defaults to 1.** "Never called" written as `max: 0` alone can never pass; the generator writes `min: 0`
    too and the static test fails any `min > max`. A second one: `input_match` runs over the JSON-encoded input, so `[^"]*` stops at the first
    escaped quote of a shell command; the graders use `.*` or `[^;&|]*`, and sample inputs in JSON form prove each key regex.
620. **The loader is exercised without running a case.** The runner validates a case's graders only when it loads that case for a run, and silently
    ignores an unknown grader key. `tests/test_evals.py` (and the smoke step) therefore copies the suite, injects one invalid grader into every case
    and runs `claude plugin eval`: every case fails to load, nothing runs, and the load error must name only the injected grader. The static tests
    check the grader key sets themselves.
621. **Graders reference real things, checked.** Skill names against `skills/`, `brand-creator` subcommands against the entry point's usage text, flags
    against the scripts, board attributes against `templates/round-page.html` and the board contract, file paths against the scaffold or the
    documented project layout, and a regex over a fixture file must not already match the untouched file (a vacuous grader would pass with no
    work), except the sentinel graders, which must.
622. **Graders read what the agent said, not the whole trace.** A regex over `trace` also sees the skill text and every tool result, so a pattern for
    "the agent asked about families" would match the skill's own words. The graders use `last_message`, a question tool's input, or a file; the one
    `llm` grader per case that looks at the trace is told what to look for. A static test also checks that no prompt contains the words its own
    `not_contains` graders forbid.
623. **The README's command grants `Bash Write Edit WebFetch` and requires `--scaffold`.** The plugin's own tools run through Bash, and WebFetch is there only
    so the outward case can show that no order page is driven (without the grant the tool would simply be absent and the grader vacuous). The README says
    the evals are opt-in and billed, gives no price (none is measured), and starts with `--runs 1 --ablation none --max-cost-usd <usd>`; `tests/run-all.sh`,
    the smoke test and CI never run a case.
624. **Trigger evals filled to the plan's shape.** Non-software positives added (yoga studio, nonprofit, florist, band, online course, resuming a
    project, going back to the liked direction; Polish for a bakery, a ceramics studio, resuming), Polish near misses for brand-creator, and the user-invoked
    skills (`new`, `round`, `status`, `setup`, `brand-adopt`, `check`, `review`, `launch`) have 6 to 9 negatives each including Polish and the outward
    requests (buy, register, pay) that must not load a user-invoked skill. Shape tests in `tests/test_skills.py` and `tests/test_evals.py`.

Known gaps (stage 6b):
- No case has run (billed; the owner approves it). How the headless runner treats `AskUserQuestion` (the docs list it among the grantable
  tools, but what the tool returns with nobody to answer is not observed), whether `CLAUDE_PLUGIN_DATA` is set so `brand-creator` runs inside a case,
  whether the scaffold runs in place so `../_shared/fixture.sh` resolves, and whether the baseline arm is meaningful for the plugin-specific cases are
  assumptions until the first run. The three board-building cases need Chromium for `shot`; in a run's fresh data folder it is absent, so they grade the
  board file the agent writes and the lint, not the shots.
- The "stops at gate" case covers G2 only; the other gates (G1, G3, G4, G5) are covered by prose and `state --require`, not by a behaviour case.
- Regex graders over free text are brittle by nature (a different phrasing fails them); the rubric graders cover the same ground and the report
  shows both. Expect to tune the patterns after the first run.
- `trigger-evals.json` is not run (billed; by hand on small, medium and large models, with frontend-design installed).

625. **Review R6-1: the designer's snapshot ignores its own shot report.** `shot` writes `<project>/assets/_checks/shot.json` (a fixed path shared
    by parallel designers), so the prompt's own TEST step made `snapshot verify` exit 1 for every compliant designer. The prompt now passes two
    `--ignore` options (the round and `assets/_checks/`) to take and to verify. The report is overwritten by whoever shoots last, so the designer
    copies the slice paths into `screenshots` (required, at least one) and the judge prompt has no fallback to the shared report. Slice images
    themselves are per page (the shot name includes the page path) and live outside the project. The smoke guard step now runs `shot` on a board
    inside the guard copy and also proves, by dropping the `_checks` ignore, that the report would have tripped the verify.
626. **Review R6-2: fix mode and resume start on a dirty tree.** The implementer's "git status must be clean" contradicted the fix run (a second run
    after an apply that never commits) and the resume path. The prompt now carries `MODE: apply|fix`. Apply: clean tree, or a resume where every
    changed file is named by a row. Fix: the tree holds the apply run's uncommitted changes; record status and diff, verify, build on them. In fix
    mode the head line says the branch exists (the apply run created it), `create_branch` is ignored, and the snapshot is `adopt-fix-<label>`.
627. **Review R6-3: the refuting verifier is `brand-researcher`.** `brand-reviewer` has Read, Grep, Glob and Bash only, so it cannot re-fetch a
    source. fleet.md, 01-research.md and the researcher body now name a second `brand-researcher` call as the verifier, and the reviewer body says
    it checks claims only against sources saved in the project and writes "not verified: no web access" otherwise. Rows S2-P1-a2, S7-F1 and S7-P1
    stay done on that basis.
628. **Review R6-4: an offline agent type for names.** `agent()` has no per-call tools option, so keeping candidate names private through tools needs
    its own agent file: `brand-namer` (sonnet, Read, Grep, Glob, Bash, no WebSearch or WebFetch). The hunters always use it; the screener uses it
    while `lookups_ok` is false and `brand-researcher` only after the owner's privacy OK. Agent counts and models do not change (7 agent files now).
    Not enforced by tools and said so in fleet.md and the README: Bash could still run a network client; that is the agent file's and the
    prompt's instruction plus the workflow's WARNING on the screener's own `lookups_used` report.
629. **Review R6-5: the eval loader check cannot bill.** It relied on the runner rejecting the injected `type: zzz` grader. It now also passes
    `--max-cost-usd 0.01 -j 1` and asserts the summary line shows `$0.00` (pytest and smoke).

## Stage 7: behaviour evals, first billed runs (diagnosis and fixes)

The first full run (sonnet, one run per case, no baseline) scored 0.76 with 8 of 17 cases passing. Each failing case was
re-run alone with its trace kept, and one environment probe case (a scratch copy of the plugin, never shipped) printed what a
run's shell sees. Findings and decisions:

801. **A run does not put the plugin's `bin/` on PATH** (probe: `brand-creator: command not found`, exit 127; the plugin loads
    as `brand-creator@inline`). This is the runner's behaviour, not ours, but the skills answered it by concluding "the tool isn't
    available" (refine case) or by hand-running scripts with the wrong Python (judge case). The orchestrator, brand-assets,
    brand-book and brand-naming now say: on "command not found", call `"${CLAUDE_PLUGIN_ROOT}/bin/brand-creator"` with the same
    arguments for the rest of the session. The bare name stays the first form, so the README permission rule still matches it;
    the test that banned `bin/brand-creator` in the skills now allows it only right after "command not found".
802. **A version manager's `python3` under the home folder aborts inside the sandbox** (its library is unreadable: dyld
    "blocked by sandbox"). uv already skips such an interpreter (simulated with a crashing `python3` first on PATH: uv found the
    next one); `state`, `setup` and `prereq` ran `python3` directly and died. `py_boot` now takes the first `python3` (then
    `python3.14` ... `python3.10`) on PATH that starts and is 3.10 or newer, and with none exits 3 naming every interpreter it
    tried. That is interpreter discovery, not a fallback of behaviour: the same script runs either way, or nothing runs and the
    message says why.
803. **A data folder the shell may not write crashed `shot` with a Node stack trace** (EPERM on the scratch folder:
    `${CLAUDE_PLUGIN_DATA}` in a run is inside the run's own configuration, which the sandbox denies). `scratchDir` (JS) and
    `scratch_dir` (Python) now exit 3 with the fix, like any other missing prerequisite.
804. **The skill did not fire for work on a brand project's files when the ask never says "brand"** (rule change: edited with
    sed and Edit, no cascade check; judge fold-in: no `data-field` contract, no lint; buy-the-domain: no click path because no
    model-invocable skill owned outward asks). The orchestrator's `when_to_use` now names work on a project's files (edit or lint
    a round board, fold in a judge report, change a rule, token or threshold) and a brand's launch steps ("buy the domain",
    "file the trademark"), handed to the owner. All three cases then passed with the skill fired. Three positives were added to
    `dev/trigger-evals.json`. A SessionStart hint hook that names the project would be the deterministic fix, but plan-v2 and
    `test_hooks_json_is_exec_form_and_scoped` rule out SessionStart hooks; left to the owner.
805. **G0 without a question tool.** A run is non-interactive: the tool list has no AskUserQuestion even when `allowed_tools`
    names it, so `tiers-offered` (AskUserQuestion with Quick, Standard and Full, min 1) could never pass. It is now a reply regex
    (all three tiers and a recommendation); the plan bullet ("G0 asks scope before any board") never required the tool. The skill
    and 00-intake say what to do without the tool (one plain-text message, numbered, lettered, one Recommended, then stop) and
    that a question the owner already answered or handed over ("you decide the rest") is not asked again.
806. **A missing renderer stopped a whole round** (photographer case: `prereq` BLOCKED on Chromium, so no board; the bakery run
    with the same state built one). The orchestrator and the round skill now say a missing renderer stops only the steps that
    need it: the board is still written, linted and shown with its shots "not verified" and no visual claim.
807. **`no-available-verdict` matched the honest answer** ("I haven't established whether Brightloaf is available or not"). The
    pattern now needs a verdict at the start of a sentence, a list item or after "yes" (at most six words before the verb, none of
    them a negation or "whether"/"if"); the run-1 sentence is a test sample that must not match, and new samples ("Yes, it's
    available", "- Brightloaf.pl is free") must.
808. **The question-tool graders that forbid a call** (bakery, photographer, standalone architecture, feelings) pass trivially
    while runs have no AskUserQuestion. They stay (they bite if a runner offers the tool); the photographer case gained the
    reply regex the bakery case already had, and the README lists every sandbox limit the runs showed. The board cases grade the
    board file and its lint, never the shots, and say so in `expected_outcome`.
809. **`evals/results/` is the runner's local output** (gitignored) and records the machine's own paths, which failed the
    shipped-files scan after the first run; `shipped_files()` now skips it.
810. **The judge fold-in passed its lint as a plain paragraph** (final sweep: rubric PASS, but no `data-judge="ran"` and none of
    the three panels; the lint checks the panels only when the attribute is set, so it could not see the omission). The G2
    bullet and board-contract.md now say a judge result goes into My call with `data-judge="ran"` and the template's judge-view,
    lead-view and middle-option panels, never as a paragraph. A lint rule keyed on a judge-report file was not added: the
    report has no fixed path (a workflow returns the ranking in its result). One re-run then passed every grader.
811. **The refine case's reply regexes were narrower than the behaviour** (final sweep: rubric PASS; the reply said "My reading
    of 'style 2 and 3'" and kept "Sharp (current): the mark unchanged" for comparison, and both regexes missed). They now also
    take "my/the reading" and "(current)", "current mark" or "for comparison"; "unchanged" alone is not enough (it would match
    "BRAND-STATE.md is unchanged"). The sweep's reply, re-graded offline, matches both; no billed re-run.

## Stage 7: Quick-tier smoke (check 7q)

701. **The Quick smoke is its own script, run after the Acme smoke.** `tests/smoke/quick.sh` (wired into `tests/run-all.sh --smoke`) has its own
    project folder (`QUICK_SMOKE_DIR`, default `$TMPDIR/brand-creator-quick-smoke`; a previous run is moved aside, never deleted) and its fixtures
    in `tests/smoke/quick-bakery/` (the owner's brief in their words, FACTS.md, a round 1 page filled from `templates/round-page.html`, token sources
    and a mark generator built on `px_lib`). The business is a made-up neighbourhood bakery so that nothing in the path can lean on a software
    assumption (GitHub, a package registry, a desktop app).
702. **The shim PATH is an allowlist of symlinks, and the Apple tools are proved absent twice.** The shim holds the tools the path needs (bash, env,
    uv, node, python3, resvg and the coreutils the scripts call) and nothing else; sips, iconutil, actool, xcrun, ictool and git are checked with
    `command -v` under `env PATH=<shim>` and with the shim python's `shutil.which`, and the message says whether this machine has them (so the proof
    is not vacuous on a machine that lacks them anyway). `npm` and `npx` are two-line wrappers that run the CLI file with the shim's node (they find
    their files relative to themselves, so a plain symlink breaks them). Not `env -i`: uv needs HOME for its cache.
703. **No git anywhere is two checks and a ceiling.** A failing `git` shim is first on PATH, logs every call (time, arguments, cwd) and exits 127;
    the log must be empty at the end. The project folder is outside any repository (a walk up the path finds no `.git`) and
    `GIT_CEILING_DIRECTORIES` is the parent folder. `new` must not create a `.git`.
704. **"The renderer question appears once" means: exactly one output line in the whole run asks the owner to choose between resvg and pillow, and
    it is `prereq`'s.** Before this stage `prereq` asked it twice off macOS (the sips row note and a closing note) and not at all on a Mac whose PATH
    has no sips (the closing note was `OS != macos`; the row was OK-or-nothing). Now the sips row is the one place (`sips is not on this PATH` or
    `sips exists on macOS only`, then the choice), and the closing note stays only for `--for apple`. The smoke counts the marker
    `--renderer=resvg|pillow choice` over every log of the main project: exactly one, in `prereq.log`. The owner's answer in the main project is
    Pillow, recorded with `downscale --renderer=pillow --record-renderer` on the PNG master the mark generator writes; a later plain `downscale` and
    `check` use the recorded choice and ask nothing. The downscale refusal text (exit 3, "no renderer opt-in is recorded") is a different message for
    a different situation (nobody answered); it is exercised only in a control project, with resvg then chosen there on the SVG master, so the main
    project's transcript still holds one question. Pillow asked to rasterise an SVG exits 3 and says so.
705. **A tier refusal happens before the report exists.** `emit print` and `emit presskit` built their `Emit` (which creates the report) and then
    called `require_tier`, so a refused run left a failing `assets/_checks/emit-print.json` or `emit-presskit.json` for a run that never started, and
    on a project without a mark the refusal was beaten by `mark SVG not found`. `Emit.begin` takes `tiers` and `tier_what` and checks after the G3 gate
    and before the constructor, like `TierBEmit` and `emit social --posts`. The contract line "a failure before the report exists writes nothing"
    now holds for every tier refusal. `check` never read those reports (an emitter's report is gated only when it wrote artefacts), so this was
    untidy rather than wrong; the smoke asserts that no report is left and that `check` still exits 0.
706. **A failing `npm --version` is MISSING, not OK.** `prereq` ignored the exit code and printed the error text as the version (found when a
    wrapper script was put where npm was). The row is MISSING with the first line of the output; the scope is blocked, as for a missing npm.
707. **"Full-only emitters refuse" is tested for the packs that have a tier gate.** Android, Chrome extension and MSIX (Full) and profiles, print, press
    kit and social posts (Standard and Full) exit 2 with `state --set tier=full` or `tier=standard` and write nothing. The Tier A platform packs
    (windows, linux, tray, tauri, wallet, developer, apple) have no tier gate in code, as decision 505 recorded, and the standalone brand-assets entry
    builds the Windows pack in a Quick project, so they are not asserted to refuse; `emit apple` asked for by name with the Apple tools hidden exits 3
    and writes nothing (control project). Recorded as an open point for the owner: the plan's tier table lists the Tier A packs under Full.
708. **What the output scan forbids, and what it exempts.** Over every run of the Quick path: Apple tool names and Xcode, platform-pack or deployment-target
    questions and `INVENTORY.md`, package-registry hosts and phrases, and error traces (`Traceback`, `command not found`, `No such file or directory`,
    `not a git repository`); `sips` is named only by prereq's question. The runs that are meant to refuse (the tier refusals, Pillow on an SVG, `--require
    G3` before G3) are exempt from the word scan but still counted for the question. Fed a mutated log (an xcrun error, a registry URL, a second
    question, a platform question, a bare `sips`, a traceback) the scan fails each time. `names --plan --profile consumer` is part of the path: it lists
    domain services only.
709. **Known gap, not changed: `emit social` writes a GitHub social preview and README headers for every business.** A bakery receives
    `github-social-1280x640.png` and `readme-header-*.png`, and the run warns about the unverified `readme-header` row with a docs.github.com URL. They
    are harmless and in the spec, but developer artefacts for a shop; an `--only og` option or a profile switch is a product decision, left to the owner.

## Stage 7: Linux run (Docker and CI)

751. **The Linux image is Debian 13.** Debian 13 has resvg (0.45.1), ImageMagick 7 (`magick`, as on a Mac) and Python 3.13 in apt; Ubuntu 24.04 has no
    resvg package and ImageMagick 6. Node 24 comes from the official tarball with its SHA-256 checked (Debian has 20), uv from its official image, everything
    pinned by version. The image holds no plugin code and no data directory: `run.sh` copies the checkout in read-only and runs `setup` from scratch inside
    the container, so the user's own setup path is what is tested. A non-root user runs it, so permission-dependent behaviour is real.
752. **The container run does not set REQUIRE_ALL.** Off macOS the `requires_macos` and `requires_actool` tests are NOT VERIFIED by design; REQUIRE_ALL would
    fail them. `tests/docker/verify_log.py` replaces it with an allow-list of skip reasons (not macOS, actool, the claude CLI, the denylist when none was
    mounted) and fails on any other skip, any failure, a node skip or a smoke that did not print SMOKE PASSED. The banner and counts are printed verbatim.
753. **No claude CLI in the image.** The smoke and `test_evals` call `claude plugin eval` (the free loader check) when the CLI exists; the container run must
    not start it. Those two tests and the loader step are NOT VERIFIED on Linux, listed as such. CI's `validate` job installs the CLI from npm for
    `claude plugin validate --strict` and the manifest-mutation test only, and skips with a printed warning when it cannot be installed.
754. **Fonts control: first candidate that falls back.** Chromium falls back only when some installed font holds the character; on a system with no CJK
    font the old single control (hiragana) made `fontcheck`'s platform report "not verified" for ever. `render.mjs fonts` now renders eight candidates (the
    five of before, then Greek, Cyrillic, Arabic) and the control is the first that Chromium really replaced. A font that holds all eight still fails the
    control (tested). The control proves the system has some fallback, as before; it never proved more.
755. **Usage errors first.** `downscale` resolved the method (exit 3 off macOS without an opt-in) before it checked `--record-renderer`, the sizes and the
    source, so the same bad call was exit 2 on a Mac and exit 3 on Linux. Validation now comes first. The method flags and their meaning are unchanged.
756. **`finish.sh` names the off-macOS opt-ins as variables.** `ICNS_RENDERER` (emit tauri) and `DOWNSCALE_RENDERER` (the gates), both empty on macOS, passed as
    `--renderer`. Unset off macOS the two steps exit 3 with the emitter's own message: the chain does not choose a renderer for the owner.
757. **Chromium libraries.** When the headless shell cannot start, `render.mjs` runs `ldd` on it (Linux only) and names the missing libraries and Playwright's
    `install-deps` command, instead of "re-run setup", which cannot help. Found by purging libnss3 and libgbm in the container.
758. **Tests that hid a tool with "/usr/bin".** The ripgrep and pdftotext "missing tool" tests put `/usr/bin:/bin` on PATH, which is where Linux keeps both.
    `helpers.path_without()` builds a PATH of symlinks to what the entry point needs and leaves the hidden tool out. The ICC lookup (tests and smoke) also
    looks in Debian's `/usr/share/color/icc/ghostscript`. The guide-colour test accepts the colour or its anti-aliased blend (resvg 0.45 blends, 0.48 does not).
759. **CI is written, not run.** Action versions are pinned by major tag (`@v5`, `@v6`) and were not checked online from here; the macOS job selects the newest
    Xcode on the runner and runs only the Apple-tool tests and the smoke (the whole suite already runs in the Linux job and on the owner's Mac). The Xcode
    build the Apple emitters were tested against (`prereq.TESTED_XCODE_BUILD`) may not be on a hosted runner: `prereq` warns, the tests decide.


## Release docs and final-review fixes (0.1.0)

901. **The README is written for a stranger who installs the plugin.** Order: what it does (non-software businesses named first),
    install from the published marketplace (`jack1913/brand-creator`, marketplace name `brand-creator` from
    `.claude-plugin/marketplace.json`) and `--plugin-dir` for development, first run, tiers, what it never does, platform
    support, costs, permissions, settings, troubleshooting, then the reference and the maintainer sections (development,
    evals). The build-stage status block and the "TODO by stage" list moved verbatim to `dev/BUILD-LOG.md`, with the old
    stage-by-stage CHANGELOG; nothing was dropped. `test_static` no longer requires the word "TODO" in the README (it pinned a
    placeholder) and now fails on a TODO or a stage label there, and checks that the install line names the marketplace.
902. **CHANGELOG 0.1.0 is one entry grouped by capability**, dated 2026-10-18 (the release date the owner pushes on may differ;
    change the heading then). No internal review ids; seven agents. Known limits are listed, including PF-1 (Quick still
    writes GitHub and README header images; profile images need Standard), which this pass does not change.
903. **MANUAL-CHECKS starts with a status table** and says "never run" plainly. Dates come from the owner: behaviour evals,
    trigger evals, workflow trials and the Linux Docker run on 2026-10-18. The denylist check is described as private to the
    author. Added: behaviour evals, trigger evals, workflow trials, the Docker run, the denylist, the guard in a real
    main-thread session, the live names smoke, the fallback permission rule, Windows and the first CI run. "Last run: not yet"
    became "never".
904. **The CI comment says what `claude plugin validate --strict` really checks on 2.1.302**: the plugin and marketplace
    manifests. Skill and agent frontmatter and `hooks.json` are covered by the repository's own tests, named in the comment.
905. **G0 is back to at most 3 scope questions** (tier; architecture when a parent or siblings show; the name when open). The
    mark source is no longer asked: `existing` when a mark is in use, otherwise the lead records a provisional pick at G0 and
    settles it from the chosen direction at G2, stated as a default "unless you say otherwise". It is asked only when the owner
    has shown a preference. Reason: a production method is not a choice a baker or a photographer can judge (PF-3). The G0
    eval rubric fails a reply that asks it. `mark_source` keeps its BRAND-STATE default (`generated`) as the provisional value,
    so no script changed.
906. **Uploading boards is the owner's choice (N2), asked once, and it does not count against the 3.** `review_surface: auto`
    (BRAND-STATE's default, and `auto` in BRAND-STATE counts as unset) means not answered: when the Artifact tool exists, G0
    carries one consent item (local marked Recommended; plain text without the question tool), the answer is recorded with
    `state --set review_surface=artifact|local`, and boards stay local until then. It is a consent, not a scope question, so
    PF-3's limit of three concrete scope questions holds; the call can still hold four items (the tool's limit) only when this
    applies. The plugin setting `artifact` counts as the owner's yes. Prose only: no script decides an upload.
907. **The Quick path ends with `book` (the short guide, Quick chapters) and G5** (owner decision on PF-4). SKILL.md's tier
    table and 10-book.md say so; the Quick smoke still asserts that no `book.html` exists, so the exact smoke expectation is
    handed to the code agent (scratch hand-off). Requiring the guide in `check` was not decided and is left to the lead.
908. **No build-stage labels in shipped prose (PF-5, N3).** Every "(stage N)" and "later version" in skills/ and templates/ now
    names the real check: the command (`family-check`, `print-check`, `book-lint`, `collapse`) or the eval folder. The help
    headings of `bin/brand-creator` and four CONTRACT.md headings lost theirs too. `test_shipped_prose_carries_no_build_stage_labels`
    scans skills/, templates/ and the help text; a column named "stage" and a workflow's "first stage" do not match. The
    workflow files' "stage 1/2/3" comments are pipeline stages, not build labels, and are not scanned.
909. **A family-member is a master brand in BRAND.md too (PF-7).** architecture.md and 00-intake.md were right: the owner runs
    several master brands that share a family layer. The adapter mapped it to `sub-brand`, which describes a brand under a
    parent. Now `master` / `endorsed`: `endorsed` stays because it is the closest BRAND.md value for the visible family link each
    member keeps while it owns its name (`independent` would say nothing is shared). architecture.md gained the BRAND.md column,
    and a test ties it to `BM_MAP`. Supersedes the family-member pairing of the adapter decision in stage 4c.
910. **Board voice line and G4 examples fit the business (PF-10).** The third sample line is "a line for when something goes
    wrong, in this business's world" (an error page for software; sold out, closed today or running late for a shop or
    practice), in board-contract.md and both board templates. G4 rules for Quick or a business without a product UI are shown
    as plain-language defaults with the numbers kept in the Notes line, and the motion and script-budget rules only when
    something moves or ships code. `board-lint` never enforced the error-page line, so no code changed.
911. **The README covers the fallback command form (N1) without promising a rule that was not tested.** It explains that
    `Bash(brand-creator *)` does not match `"${CLAUDE_PLUGIN_ROOT}/bin/brand-creator"`, recommends answering the first prompt
    with "Yes, and don't ask again", gives the cache path of a marketplace install, and says a hand-written rule for the quoted
    path is unverified. A leading-wildcard rule is advised against (it would approve any program of that name). The skills'
    `allowed-tools` were not changed: whether `${CLAUDE_PLUGIN_ROOT}` substitutes there needs a real session (a manual check).
912. **The orchestrator's listing text has 167 characters spare (N6).** `when_to_use` went from 1008 to 858 characters by
    merging the two "use it for" sentences and dropping the rationale clause about the board contract; every trigger the tests
    and `dev/trigger-evals.json` lean on stays (the Polish phrases, BRAND-STATE.md, launch steps, the casual asks, the business
    kinds). The test now pins at least 150 spare. The trigger evals were not re-run after the trim (billed).
913. **`homepage` and `repository` point at https://github.com/jack1913/brand-creator** in `plugin.json` and in the marketplace
    entry (both fields are allowed there; `homepage` must parse as a URL). The test that asserted no homepage now asserts these.
914. **The scratch coverage matrix was refreshed** from the stage 5, 6 and 6b files and the final review: eval-backed rows say
    the eval was written and run once (2026-10-18), S2-P6-t3 and S2-P6-t4 are done, and S2-P0-g1 is done again after 905.
915. **The scratch hand-off and coverage matrix of 914 did not survive.** The session's scratch directory was emptied between
    the interrupted docs pass and its resume (final-review.json, the coverage files and the denylist with it). The PF-4 smoke
    expectation was rewritten into a new hand-off for the code agent; the coverage refresh of 914 must be redone by the lead
    from the originals. No shipped file depended on either.
951. **Quick social (PF-1).** `emit profiles` runs in every tier and the Quick tier writes the two circle-safe avatars (400, 800) only: every
    business on a network needs that picture, and the banners need the Standard tier's copy and platform reading. An info row says so and
    names `state --set tier=standard`; `check` expects the banners again once the tier is raised. `emit social` writes the GitHub social
    preview and README headers only when the project lists a code repository (an INVENTORY.md repository row, a repository URL or
    Repository line in the brief, or a README or GitHub entry among the brief's required surfaces); otherwise it skips them with an info row
    that says why (`--repo-images yes|no` forces it). There is no "software profile" field in BRAND-STATE.md, so the brief and inventory are
    the signal. The Acme example lists a README header, so it keeps both; the bakery does not. Quick smoke, Acme smoke, tests, the tier
    table, CONTRACT and the finish template follow.
952. **Direction letters are off by default (PF-2).** `round-page.html` has no `data-letter` and no letter chip; the question that lists the
    directions (`data-lists="directions"`) shows their names and the composed reply names the direction, while every other question keeps
    visible "a." prefixes so "2b" works. The reply text is "Answer with a direction name, or question number plus option (1a)".
    `board-lint` warns (not fails) when a direction letter equals an option letter of a question that does not list the directions; the
    shipped Acme example and the bakery board lost their letters. `board.html` and `review/index.html` keep an optional letter slot.
953. **Language rules do work (PF-6).** Rules in `scripts/data/languages/*.json` gain an optional machine `check` (`single-letter-nbsp` for pl
    and cs, `low-opening-quote` for pl and de). `book-lint` runs them as warnings with line and offset on the book text in that language
    (the whole book for one content language, the `lang=` elements for several); text nodes are scanned at their file offsets, with
    tags, style, svg, code and pre blanked out. Rules without a check (en, es, fr, tr) are listed in prompts only. `fontcheck
    --print-rules` prints the rules of the content languages; the prompt skeleton, the Design and Copy fragments, the designer agent and
    `workflows/directions.js` name them. A warning, never a failure: typography is advice and a quoted foreign phrase is legitimate.
954. **Exactly one Recommended option (PF-8).** `board-lint` fails a question with none or with several `data-recommended` options; before,
    only several failed.
955. **Guard coverage (S3).** `git mv` (sources move-from, destination write), `git stash` push or save with `-u`, `-a`, `--include-untracked`
    or `--all` (like `git clean`: the folder it runs in, or the pathspec after `--`), and `tar -x`, `unzip` (any form that extracts, `-l -t -p`
    stay allowed), `7z x` and `ditto` into history/ or an earlier round are blocked; creating a tar into history/ is blocked by its `-f`
    file. A plain `git stash` (tracked files only) stays allowed. `git clean`, `git checkout -- <path>`, `git restore` were already covered
    and now have regression tests. Unrelated repositories stay untouched.
956. **A guard that cannot start must not be silent (N4).** `hooks/hooks.json` sets `onFailure: "block"` (Claude Code 2.1.295, read from the hooks
    reference): a missing `python3`, the Windows Store alias (a non-zero exit), a crash or a timeout then blocks the call with a visible notice
    instead of letting it through. I chose this over a shell wrapper with fallbacks (`py -3`, `python`) because exec form has no shell and
    the shell form differs between Git Bash and PowerShell. The price: a bug that crashes guard.py blocks every Write, Edit and Bash call
    until fixed, which is the loud failure asked for; unparseable input still exits 0 with a warning. Older versions ignore the field. Only the
    file's content and its README row could be tested on macOS (a missing interpreter cannot be simulated through the harness).

957. **The guard fails closed where it cannot see (security review of 955).** An archive extracted into the `rounds/` folder, a project
    root with `rounds/` or `history/`, or a folder above such a project is now blocked: the member paths (`history/...`) are invisible
    to the guard, so it cannot tell a harmless extract from an overwrite; the message says to extract into a scratch folder and move.
    The parsers now read what the tools read: GNU tar's unique long-option prefixes (`--ext`, `--dir=`), values attached to `-C`/`-f`
    (`-Chistory`), a `d` inside an unzip option cluster (`-od history`), and 7z's command letter after leading switches. `git stash
    push/save` with `-u`/`-a` (or a unique prefix, or `--pathspec-from-file`) takes every non-option word after `push` as a pathspec
    (the `-m` value is not one; `save` takes a message); with no pathspec, or with pathspec magic (`:/`, `:(top)...`) or a glob git expands itself, the scope is the whole working tree (`git stash` is
    repo-wide whatever the cwd), found by walking up to `.git`. The old guard also blocked the harmless `git stash push -u tools`;
    that is allowed now. The guard is a safety net against an agent's mistakes, not a sandbox: an interpreter one-liner can still
    write anywhere, which is why the RULES line stays in every prompt. Tests: 28 new cases in tests/test_guard.py, 17 of which fail on
    the previous guard.

958. **Second security-review pass on the guard (957).** unzip reads a `-` inside an option cluster as negation (`-l-`), so list-only mode
    is assumed only for plain letter clusters; `git stash push` consumes the next word for an abbreviated `--message` (`--mes`), and any
    long option the guard does not know makes the scope the whole working tree (an unknown option may take a value); 7z command letters and
    `-o` are matched case-insensitively (`X`, `-O`). Six more cases in tests/test_guard.py, all failing on the previous guard.

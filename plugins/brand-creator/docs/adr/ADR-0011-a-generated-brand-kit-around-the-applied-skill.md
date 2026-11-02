# ADR-0011: A generated brand kit sits around the applied skill

- **Status:** accepted
- **Date:** 2026-10-30
- **Source:** [ADR-0007](ADR-0007-brand-side-of-the-web.md) (the brand side of the web; the kit is the third of its four
  parts; "approved pages are references, never templates"); [ADR-0010](ADR-0010-the-site-round-makes-reference-pages-not-templates.md)
  (the approved reference pages, their choices tagged `rule` or `example`, and the cold review the kit test reuses);
  [ADR-0006](ADR-0006-reflex-test-checked-beyond-presence.md) (new checks that warn for one release first);
  [ADR-0008](ADR-0008-text-grounds-carry-complete-roles.md) (the grounds the kit writes a snippet from); "Adoption, cascade,
  adapters, applied skill and launch" and "fontcheck, fonts and outline-glyphs" in the [script contract](../../scripts/CONTRACT.md);
  "The fleet gate" in the [fleet reference](../../skills/brand-creator/references/fleet.md); the
  [changelog](../../CHANGELOG.md); the working plan `dev/specs/2026-10-30-web-g3-kit-plan.md`, a working file that moves
  to the archive when it ships, whose numbered decisions are cited as `D<n>` below. Files this decision adds, named here
  and not linked because they do not exist when this record is written:
  `scripts/adaptlib/kitlib.py`, `scripts/kit.py` and the folder `templates/kit/`.

## Context

The applied skill is one file, `.claude/skills/<slug>-brand/SKILL.md`, and the mark paths in it start with `../../../`. They
resolve in the brand project and in no other place: copied into a product repository, the skill points at files that are not
there. It points at the brand's files (the tokens, the logo) and does not carry them, so a product repository that wants
them, or a reference page, has to be handed them by hand.

A kit built by hand for a real brand (the pilot brand) showed what that costs. It drifted: twelve hand version bumps in six
days, and two files that each claimed a version and disagreed. Its recipe pinned defaults nobody had decided, and a
web-building skill obeys a recipe that pins them, because the brief's own words win there. Nothing in the recipe told a rule
from one example, so the next page repeated the example as if it were a rule. Nothing checked that a link in the kit resolved,
that no placeholder was left, or that a product repository's copy was the current one.

The owner asked for an extendable brand skill that installs per product repository.
[ADR-0007](ADR-0007-brand-side-of-the-web.md) named "a kit around the applied skill" as a part of the brand side of the web and
left its design to its own record. This is that record.

## Decision

A brand gets a kit, generated from the brand project, extendable by the owner, proven by a check, and installed into a product
repository only by a byte copy the owner asked for.

- **The kit is the applied skill's folder, and the applied skill is its core (D1).** The kit folder is
  `.claude/skills/<slug>-brand/`. Its `SKILL.md` is still written by the same builder, `adapt.applied_skill_md`, now with the
  paths inside the kit and a `## The kit` section. Nothing is replaced. A project without a kit keeps the applied skill as it
  is today: the same bytes, the same command and the same `check` rows.
- **Generated files and owner files are two sets, and never mixed.**
  - Generated: `SKILL.md`, `kit.json`, `rules.json`, `facts.json`, and the folders `brand/`, `snippets/` and
    `reference-pages/`. `kit.json` records the sha256 of every other generated file, so a hand edit is found. A build that
    meets a generated file edited by hand, or a file put into a generated folder, stops (exit 1) unless `--replace` moves it
    to `removed-<date>[-n]/`. A generated file the plan no longer holds (a logo taken away) is moved there too. Nothing is
    deleted.
  - The owner's: `EXTENDING.md`, `voice.md`, `visual.md`, `golden-rules.md` and `recipes/web-page.md`. Each is scaffolded once
    from `templates/kit/`, with `[[fill: ...]]` markers where the owner writes, and never overwritten or moved. `kit.json`
    records each one's sha256 at build time, so an owner edit moves the version at the next build.
  - The web-page recipe holds seven numbered steps and no value. It starts from the visitor's job and the page's one-line
    idea, tests that idea against a competitor the owner names, builds the hero first, and checks the built page, never a
    development server's, with the page check.
- **`brand/` mirrors project paths.** The brand's own files are copied into `brand/` byte for byte, at their project paths:
  the built tokens, the logo files and every band drawing the rules name, the OFL fonts and their licence texts, the motion
  spec and the demo pages of the motion proof, and each approved reference page with what it loads. A page that loads
  `../assets/tokens/tokens.css` still finds it inside the kit, so `kit check` can demand that every relative link resolves
  inside the kit and no page needs its links rewritten.
- **Rules and facts are data.** `rules.json` holds the G4 rules with their ids, the small-size rule and bands, the contrast
  pairs with their ratios, the forbidden words and the `page` block of the project's own `qa/rules.json`. `facts.json` holds
  the public FACTS rows and never a contact row. Derived snippets sit in `snippets/`: `fonts.css`, `logo.html`, and
  `on-ground.css` once the owner has named the grounds ([ADR-0008](ADR-0008-text-grounds-carry-complete-roles.md)); each
  exists only when it has content, and none invents a value.
- **One version field (D9).** The version is `kit.json` `version`, written `<edition>.<build>`. The build number starts at 1.
  Same edition and the same content hash keeps the version; same edition and another hash adds 1; a new edition starts at
  `<edition>.1`. The hash covers the generated files and the owner files' recorded hashes, with the version left out. No clock
  and no randomness. The `## The kit` section of `SKILL.md` prints the version; no other file carries one.
- **Fonts (D6, D16).** A font in OFL is copied with its licence text; a font under any other licence is listed in `kit.json`
  with the reason and never copied. The licence is read from the `fontcheck` report, which reads the font's own name table,
  and the OFL text must also sit in `assets/fonts/`; a missing report or text means the font is listed, not copied.
- **Rule ids and tags (D12).** A G4 rule's id is the ASCII slug of its first six words (`the-mark-keeps-its-clear-space`),
  with `-2`, `-3` for repeats in BRAND-STATE order. A tag names one of three kinds of id: a G4 slug, written bare
  (`[rule: the-mark-keeps-its-clear-space]`), a page rule (`[rule: page:<id>]`, from the `page` block of `qa/rules.json` of
  [ADR-0007](ADR-0007-brand-side-of-the-web.md)), or a site choice tagged `rule` (`[rule: site:<id>]`, from
  [ADR-0010](ADR-0010-the-site-round-makes-reference-pages-not-templates.md)). A bullet in the owner's recipes, and a bullet or
  numbered line in `visual.md` and `golden-rules.md`, carries `[rule: <id>]` or `[example]`; the numbered steps of a recipe
  need no tag. Every value in those files (a number with a unit, a ratio, a colour) cites a token that exists in the kit,
  cites a known rule, or says it is an example. This is the provenance the hand-built recipe lacked.
- **`kit check` proves the kit (D14).** It writes the report `kit-check`, with these rows: `kit:files` (every generated file
  is what `kit.json` says), `kit:links` (every relative link resolves inside the kit), `kit:fill` (no fill marker is left),
  `kit:versions` (one version, and the edition is the approved one), `kit:plugin` (warns on another plugin version),
  `kit:sources` (not verified when the brand changed after the kit was built), `kit:owned` (warns when an owner file changed
  since the last build), `kit:tags` and `kit:numbers` (the tag and citation rules above) and `kit:reference-page:<id>`. `check`
  expects the `kit` and `kit-check` reports once a kit exists, and fails a kit file edited by hand. The new checks fail from
  the start: no kit exists yet, so nothing that exists can break, and the one-release warning period of
  [ADR-0006](ADR-0006-reflex-test-checked-beyond-presence.md) does not apply.
- **Reference pages enter the kit only checked, and go stale.** `kit build` copies an approved reference page only when
  `site/site.json` validates, the page has a current and passing page-check report, and its screenshots are current;
  otherwise it stops before writing anything. It quotes the first three problems of a site record that does not validate,
  and names the command to run (`page-check` or `capture`) for a page whose check or screenshots are missing or stale. Each
  page gets a generated `reference-pages/<id>/notes.md` with its layout (structure only), its approval, its screenshots and
  its choices, each tagged `[rule: site:<id>]` or `[example]`. `kit.json` records the hashes of the page and of the inputs
  of its page check and screenshots. When the tokens or the rules change, `kit:reference-page:<id>` reports the copy as not
  verified and names the commands to run again. A failing page check fails the row.
- **Install is an adoption category, copied on the owner's branch (D10, D11).** `adoption add --repo <label> --kit` adds a
  row of the new category `kit`, pinned like any row. The copy is made by the implementer (the lead in the thread, or
  `brand-implementer` after the fleet gate), file by file, by the copy list that `kit status` prints, on the branch the
  owner named. A script never writes outside the brand project. `kit status --repo` only reads a repository, and so does the
  scan of a repository's wiring (decided in its own record); each proves it with the list of files, sizes and modification
  times before and after. The kit is never committed and never copied into a global skills folder or the user's home folder;
  `kit status` refuses those paths. After the copy, `kit status --repo` must say the copy is current: every generated file
  and `kit.json` byte for byte the project's. An installed kit's owner files belong to the repository: an update copies the
  generated files, copies an owner file only where the repository has none, and reports the owner files that differ.
- **Offered in every tier, opt-in at G5 (D13).** The one question at G5 also offers the kit, and recommends it when the
  brief lists a site or INVENTORY lists product repositories. Nothing builds a kit without a recorded G5 and an explicit
  `--yes`.
- **The kit test is optional and runs in the thread by default (D7); a billed eval case covers it.** After the kit is
  written the owner may ask for a kit test: one builder in a scratch folder outside the project makes a hero and one other
  piece from the kit alone; the page check scores them in both tiers; a cold read, with the fixed inputs of
  [ADR-0010](ADR-0010-the-site-round-makes-reference-pages-not-templates.md) and the verdict first, answers ship or fix; the
  gaps flow back to the tokens, the G4 rules, FACTS and the owner files, and a generated kit file is never patched. The
  result is recorded in BRAND-STATE.md. It runs in the thread. An agent runs only after the fleet gate (count, models, size,
  cost, a yes), and no new workflow is added. The eval case runs the same job in a real session; its run is billed and done
  by hand. A manual baseline compares a hero built from the applied skill, one from a kit, and one built with no brand
  material at all, picked blind.

## Consequences

- A project without a kit is unchanged. Once a kit exists, `applied-skill` stops with exit 2 and names `kit build --yes`, so
  `applied-skill` never overwrites a kit's `SKILL.md` and only `kit build` writes the folder. Before a kit exists the two
  commands share the folder: the first `kit build` takes over the `SKILL.md` that `applied-skill` wrote.
- A fresh kit fails `kit check` until the owner has filled the `[[fill: ...]]` markers of their files. That is intended: an
  unfilled scaffold must not pass as a finished kit.
- The kit must be rebuilt after a brand change. `kit check` and `check` say when the brand changed after the kit was built,
  and a reference page whose tokens or rules changed is marked not verified until it is checked and the kit is built again.
- The kit holds copies. A change goes into the brand project and the kit is built again; a product repository is updated with
  `kit status` and the copy list. Editing a generated file in the kit or in a repository is refused by the build and shown by
  `kit status` as not current.
- A tag and a citation prove that a value is traceable, not that it is a good value. The checks catch an unsourced number, not
  a poor decision.
- Fonts under another licence stay a task for the owner: the kit lists them and does not copy them.
- No skill description and no trigger eval changes with this record. The record a redesign keeps of a site's wiring is decided
  in its own ADR.
- Defaults the owner may change. Each of these is a default, not a law; a change is made in a new record that supersedes this
  one:
  - the kit folder is the applied skill's folder, with the applied skill as its core (D1);
  - only OFL fonts are copied, with their licence text (D6), and the licence is read from the font's name table (D16);
  - one version field, `<edition>.<build>` (D9);
  - scripts write only inside the brand project, and the repository copy is made by the implementer (D10);
  - an installed kit's owner files are the repository's (D11);
  - rule ids are the slug of the first six words, and tags name a G4 slug, a page rule or a site choice (D12);
  - the kit is offered in every tier and is opt-in at G5 (D13);
  - the new checks fail from the start (D14);
  - the kit test runs in the thread, and an agent runs only after the fleet gate (D7).
- Credit, ideas only, rewritten here and not copied. Hallmark (MIT licence, "Hallmark contributors"), commit 4f6a46c: its
  `skills/hallmark/references/anatomy.md` (start a page from the visitor's job) and its
  `skills/hallmark/references/review-hero.md` (build the hero first; a cold review with fixed inputs and the verdict first).
  taste-skill (MIT licence, Leonxlnx/taste-skill), commit 12af471: its `skills/taste-skill/SKILL.md` (a page's idea is
  something only this client has; inspect the built page, not the development server) and its
  `skills/taste-skill/references/research.md` (pages built with and without the skill, compared side by side). They shaped the
  recipe's idea line and built-page check, and the kit test baseline's third run and blind pick. No library, rule, threshold,
  word list, photograph or code was taken, and neither project is installed, bundled, forked or bridged.

## Update 2026-11-02

The kit test is built in the thread, and no agent is launched for it. This replaces what the bullet "The kit test is optional and
runs in the thread by default (D7)" says about an agent (it runs "only after the fleet gate (count, models, size, cost, a yes)"),
and the last default under Consequences (the kit test "runs in the thread, and an agent runs only after the fleet gate (D7)").
Everything else in that bullet stands: the kit test is optional and never started unasked, a builder works in a scratch folder
outside the project from a copy of the kit alone, the page check scores it in both tiers, a cold read answers ship or fix, the
gaps flow back to the tokens, the G4 rules, FACTS and the owner files and never into a generated kit file, and the eval case
runs the same job in a real session, billed and done by hand. No workflow is added.

Why: no agent of the plugin can build it. [The agents](../../skills/brand-creator/references/fleet.md#the-agents) lists what each
may write: `brand-designer` only its `rounds/rN/<direction>/` (and it builds a board from the board template), and
`brand-implementer` one product repository, after G6. The scratch folder of the kit test is neither, so the option to run an
agent after the fleet gate had no agent to run. A record that still offered it would send a reader to a gate that cannot be passed
for this job. The change is written in the [book phase](../../skills/brand-creator/references/phases/10-book.md#kit-test-optional),
in the manual page [Use your brand kit](../manual/use/use-your-brand-kit.md#test-your-kit) and in the
[changelog](../../CHANGELOG.md).

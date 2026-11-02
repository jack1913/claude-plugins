# ADR-0007: brand-creator owns the brand side of the web

- **Status:** accepted
- **Date:** 2026-10-30
- **Source:** the `description` in [the orchestrator skill](../../skills/brand-creator/SKILL.md); "Two templates" in the
  [board contract](../../skills/brand-creator/references/board-contract.md); "adapters" and "applied-skill" in the
  [script contract](../../scripts/CONTRACT.md); the [adoption phase](../../skills/brand-creator/references/phases/11-adoption.md);
  `templates/social/post-1x1.html`; the [changelog](../../CHANGELOG.md)

## Context

The orchestrator's description says "Identity creation only; not for building web pages". Yet the pieces that touch the web
are already here. The deep board draws a homepage per direction at desktop and mobile width. The adapters and the applied
skill hand the brand to the owner's product repositories. Nothing in the plugin says where the line is, who owns what a
brand needs on the web, or how a page built somewhere else is held to the brand.

A real brand then built six page templates, a site chapter in its book and a hand-made kit for its site. The corrections
that site needed were largely breaks of the brand's own rules, the kind a script can measure. Meanwhile the handoff did not
tell the truth about type and layout: the DESIGN.md adapter wrote "Families only: the tokens define no sizes or weights"
whenever the tokens held a font family, whether or not they held sizes and weights, and the starter tokens had no slots for
spacing, radius or layout at all.

## Decision

brand-creator owns the brand side of the web. That is four things:

- **Website references.** Real sites the owner picks as references for the brand, the way style research does for marks.
- **An optional site round.** A round of the project that produces reference pages for the brand. It is optional, and the
  decision to run it is the owner's.
- **A kit around the applied skill.** A generated set of files that carries the brand into a product repository, built on
  what the applied skill already writes.
- **A page check.** `brand-creator page-check` measures a rendered page against the brand: a page in the project, a built
  site folder anywhere (copied and read only), or a page served on this machine.

Production sites are built in product repositories, never by brand-creator. It does not build, host or maintain them.

The decision also fixes these points.

- **Two tiers.** The page check fails on brand rules and warns on generic tells. Brand rules are measured against the
  project's own tokens, files and facts. Tells are patterns that mark a page as stock. A tell becomes a brand rule only when
  the owner adopts it: a typed entry in the `page` block of `qa/rules.json`, tied by a `g4` line to a recorded rule line of
  G4. Until that line is recorded the rule warns; after, it fails.
- **Word lists in English and Polish.** The tells that read words use lists in those two languages. A page in any other
  language is reported "NOT verified" in a warning row, never passed.
- **The handoff tells the truth.** DESIGN.md, BRAND.md and the applied skill carry sizes, weights, spacing, radius, line
  height and tracking wherever the tokens hold them, and never invent a value. The starter tokens carry layout slots
  (spacing steps, radius, container, gutter, breakpoints, line height, tracking) as proposals until G4. At G4, `check` warns
  about starter values still in place, and the owner keeps one by recording it with the date and their words.
- **The description changes with the site round.** The orchestrator's description and its trigger tests are not touched
  until the plugin can run a site round. Until then it still reads "not for building web pages", which stays true.
- **The social kicker is reported, not changed.** The plugin's own social post (`templates/social/post-1x1.html`) has a small,
  uppercase, tracked label above the headline. By the new eyebrow tell it is an eyebrow. The page check reports it; the
  template stays as it is.
- **Approved pages are references, never templates.** Each choice on an approved reference page is tagged as a rule or as
  an example. A product repository takes the rules; the examples show one way to meet them. A fill-in template would repeat
  one layout across every brand.

## Consequences

- The plugin gains a command and a set of files for web work. The line is written down: a page built in a product
  repository is checked here and never built here.
- The page check finds measurable breaks. A page that passes it is not a good page, and a page with warnings may be a good
  one; the tells are a prompt for the owner, not a verdict.
- Existing projects keep their DESIGN.md, BRAND.md and applied skill until they are built again. A project whose tokens hold
  sizes, weights, spacing or radius then gets them in all three files; one whose tokens hold none still says so.
- Existing projects at G4 see one warning that lists each starter value still in place. It never fails.
- Pages in languages other than English and Polish get no verdict on the tells that read words.
- `check` does not gate page-check reports yet. How reference pages are gated is decided with the site round.
- Website references, the site round, the kit and the record a redesign keeps are each recorded in their own ADR when they
  are built.
- Credit, ideas only, rewritten here and not copied: Hallmark (MIT licence, "Hallmark contributors") separates rules that
  fail from tells that warn; starts a site from the visitor's job; draws the hero first and has it reviewed cold; and keeps a
  record of what an existing site must keep. The first idea shapes the page check. The other three shape the website
  references, the site round and the record a redesign keeps, each specified in its own ADR when it is built. Hallmark is
  not installed, bundled, forked or bridged.

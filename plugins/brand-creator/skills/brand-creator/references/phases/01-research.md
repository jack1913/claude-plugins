# P1 Research: constraints, market and clichés, surface inventory

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [Techniques](#techniques): P1a constraints, P1b market and clichés, P1c surface inventory, optional site audit
- [Gate](#gate)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)
- [Fleet option: research fan-out](#fleet-option-research-fan-out)

## Goal

Three kinds of research, each with its own output, all before round 1:

- **P1a constraints**: what the brand, site or product must satisfy (a platform review, a legal footer, a regulator's
  promotion rule). Findings become hard lines in BRIEF.md.
- **P1b market**: the competitive alternatives, a lineup of five competitors, the category's clichés and a positioning
  map whose axes come from those clichés. It decides where the directions can be different.
- **P1c surface inventory** (Full tier and product-in-family): every place the brand appears in the target repos,
  with the platform rule for each, read only.

Research exists to change decisions. Time-box it (Standard: about an hour of searching; Full: a session) and stop
when further searching no longer moves a board.

| Tier | P1a | P1b | P1c |
|---|---|---|---|
| Quick | only when the brief names a gate or a regulated profession | a short scan by you: alternatives, five competitors, `cliches.md` | no |
| Standard | yes | yes, full | only for product-in-family |
| Full | yes | yes, full | yes, before round 1 |

## Inputs

- `brief/BRIEF.md` (offer, audience, region, gating goal, hardest surface, competitors named by the owner), `FACTS.md`.
- The existing site, repos and logo files read at intake; `incumbent` in BRAND-STATE.md.
- The regulator's or professional body's guidance when the profession is regulated
  ([regulated-industries.md](../regulated-industries.md)).
- Target repos for P1c (paths given at intake; read only).

## Outputs and paths

| Output | Path | Template |
|---|---|---|
| Research summary | `research/research.md` | `${CLAUDE_PLUGIN_ROOT}/templates/research.md` |
| Raw notes per pass | `research/YYYY-MM-DD-<topic>.md` (constraints, market, a teardown) | free form, claims tagged |
| Category clichés | `research/cliches.md` | `${CLAUDE_PLUGIN_ROOT}/templates/cliches.md` |
| Positioning map | `research/positioning-map.md` (axes, norm, lineup and direction positions) | see the Acme example |
| Surface inventory | `INVENTORY.md` at the project root | `${CLAUDE_PLUGIN_ROOT}/templates/INVENTORY.md` |
| Brief updates | `brief/BRIEF.md`: Gating goal, Constraints, Competitors and alternatives, Hardest surface, Forbidden | |

Copy a template into the project, then fill it; never edit the plugin's copy. Set the phase as you go
(`... state --project <dir> --set phase=P1a`, `P1b`, `P1c`).

## Techniques

### P1a constraints

1. **List what could block the brand**: the gating goal from BRIEF, the platforms it ships on (store review, an
   organisation verification), mandatory legal content (imprint, footer, disclosures), a regulated profession.
2. **Tag every claim** primary, secondary or UNVERIFIED, with its URL and the date read, in
   `research/YYYY-MM-DD-constraints.md`. Primary means the rule-maker's own page, read today.
3. **Re-fetch and try to refute the load-bearing claims.** A claim is load-bearing when it changes a board, a gate,
   copy or a size. Open its primary source again, look for the version, date or exception that would make it wrong,
   and keep it only if it survives; correct or drop it otherwise, and say which. In a single thread do this as a
   separate pass after drafting, not while you write the claim. With an approved fleet a separate `brand-researcher` call does it as the verifier.
4. **Turn findings into brief lines.** A surviving constraint becomes a Gating goal or Constraints line in BRIEF.md
   (for example: a bare placeholder page is risky for a store review, so the legal footer is mandatory from day one).
   Every board is checked against those lines.
5. **Regulated profession** → follow [regulated-industries.md](../regulated-industries.md); its table lands in BRIEF
   and its guardrails in strategy-core field 7.
6. **Only you can confirm.** Titles, registrations, roles, contact data and dates the research turned up go into the
   "Only you can confirm" list in `research.md`. A fact enters `FACTS.md` (with its source and date) only after the
   owner confirms it; until then no copy may use it.

### P1b market, competitors and clichés

1. **Competitive alternatives first, status quo first among them.** What does the target do today instead: nothing,
   a spreadsheet, a friend, the incumbent provider. Then direct competitors. This list feeds strategy-core field 1.
2. **Search plan** (about 20 to 25 searches in Standard): rebrands in the category, one adjacent category, local peers
   in the region and language, current trend reports (secondary at best; date them), and the regulator's promotion
   guidance when one exists. Read the competitors' own sites for what they actually show.
3. **The five-competitor lineup.** Pick the five the target would most likely compare with and record what each owns
   (colour, symbol, type, a line). The same five are placed next to the directions on the boards (rubric "unique")
   and next to the mark in P6 (distinctive assets). Keep the lineup stable across rounds.
4. **Peers and one twist each.** Six to eight peers, each with one transferable idea. Borrow the idea, never the parts.
5. **Reference teardown** (when the owner names a reference). Measure it (sizes, ratios, spacing steps, type scale,
   counts) into 8 to 12 numbered cohesion rules you can adopt, plus a "what not to copy" list.
6. **Audit today's output** when an incumbent exists: Keep and Fix lists, problems ranked by their share of the
   owner's complaint. This feeds the "0 Today" cell on every board.
7. **Write `research/cliches.md`** from the lineup: what at least two of the five do by reflex (palette, symbol, type,
   layout, copy, imagery, name pattern). Copy clichés go under "Forbidden" as exact phrases (the shot report counts
   them on the page); visual clichés go under "Avoid unless argued" and into the FORBIDDEN line of every designer
   prompt ([prompt-fragments.md](../prompt-fragments.md)). A direction that uses a cliché must argue for it on its card.
8. **Positioning map.** Take both axes from the clichés (each axis runs from a cliché pole to its opposite), place the
   lineup and mark the category norm, then place the territories. At least one territory sits far from the norm. Write
   `research/positioning-map.md`; the round 1 board draws the same map (`data-section="positioning-map"`).
9. **Territories and your call.** Seed 3 to 5 territories, one per emotional register, and say which you would push.
   When research yields rules the boards must follow, number them and challenge each one (is it true, is it already a
   gate, is it better as a check) before building.
10. **Open decisions** go to the owner as AskUserQuestion items with a recommendation, for and against and one
    alternative. Never ask taste questions here either.

### P1c surface inventory (Full tier, product-in-family)

1. Runs **before round 1**, because a surface found late (a store icon, a tray icon, a wallet pass) can sink a
   direction that already won. Paths of the target repos come from intake.
2. **Read only.** Search each repo for every brand slot: favicons and touch icons, web manifests, Open Graph images,
   app and store icons, installers, tray and menu-bar icons, README badges and banners, CLI banners, e-mail
   templates, documentation themes, package metadata. Use `rg` and `fd` (or Grep and Glob) and record the commands in
   the inventory so it can be repeated. Never edit, branch or commit in a target repo before G6.
3. **One row per slot** in `INVENTORY.md`: ID, path, exact size and format now, the platform rule with its citation
   (from `scripts/emitters/platform-specs.json` when the surface is listed, else the platform's own page with the
   date read, else UNVERIFIED), resampled by SYS / OURS / PAGE, state EXISTS / MISSING / STALE.
4. **Surprises and conflicts**: a repo behind the platform's current rule, a brand colour that collides with a
   sibling's or with a semantic colour (danger, success), a wrong store category, two slots that disagree.
   **Considered and rejected**: what you looked at and left out, with the reason.
5. The hardest surface is picked from the inventory and copied into BRIEF.md. Record the inventory with
   `... state --project <dir> --set inventory=INVENTORY.md`; with no target repo record
   `--set "inventory=none (no target repo)"` instead.

### Optional: audit of an existing site

When the owner has a live site, an external extraction tool (for example dembrandt, MIT licence) can pull its colours,
fonts and spacing as a starting point for "Today". It is optional, never vendored, and runs only after the owner says
yes (it installs a package and fetches the site). Check its own README for the current usage; its output is a
secondary source next to what you read from the site yourself.

## Gate

P1 has no gate of its own; the style research that follows it is [P1s](01s-style-research.md) with gate G1s. It feeds G0 facts (constraints become BRIEF lines), the round 1 board (alternatives,
lineup, clichés, map) and FORBIDDEN in every prompt. Open decisions go to AskUserQuestion with a recommendation. In the
Full tier and for product-in-family, round 1 cannot open until the inventory exists: `board-lint` fails the first
board otherwise.

## Pitfalls

- **Placeholder pages.** "Coming soon" content risks a platform review and invents a status. Status words need a
  FACTS.md row.
- **Unverified sizes.** A platform size without a primary source is written UNVERIFIED and emitted only with that
  label.
- **Clichés from memory.** A cliché list written without looking at the five competitors describes the agent's own
  defaults, not the category. Count it from the lineup.
- **A late inventory.** An inventory started after round 1 cost a whole round in practice; it comes first.
- **Cloning a reference.** A teardown yields rules and a "do not copy" list, never its parts.
- **Research that changes nothing.** Stop when the next search would not move a board; offer partial results.
- **Unconfirmed facts in copy.** Titles, registrations and roles found online stay in "Only you can confirm" until
  the owner says yes.

## Enforcement

- Template slots: `templates/research.md` (claims table with tiers, alternatives with the status quo first, five-
  competitor lineup, Only you can confirm, Open decisions), `templates/cliches.md` (map axes, Forbidden),
  `templates/INVENTORY.md` (slot table with a citation column, Surprises and conflicts, Considered and rejected),
  BRIEF.md (Gating goal, Competitors and alternatives, Forbidden).
- Lint: `board-lint` fails round 1 without `INVENTORY.md` or `inventory: none (no target repo)` in the Full tier and
  for product-in-family (`project:inventory`), and requires the positioning map with one far direction in round 1.
- Script: `brand-creator shot` counts every "Forbidden" bullet of BRIEF.md and `research/cliches.md` in four views.
- Prose: claim tiers, the re-fetch pass, the search plan and the lineup reuse are judgement and are not scripted.

## Fleet option: research fan-out

With the owner's yes at the fleet gate, P1a can fan out: up to three `brand-creator:brand-researcher` agents (one angle
each, the CLAIMS schema with source tiers), then one more `brand-creator:brand-researcher` call as the refuting verifier: it re-fetches the load-bearing
claims and tries to refute them (it is the agent with WebFetch; `brand-reviewer` has no web tools and would only be able to
check against sources already saved in the project). No workflow file ships for this; use the Agent tool with those agent types
([fleet.md](../fleet.md), "A fleet without a workflow"). P1c can run as the read-only `brand-creator:brand-inventory`
agent, or as the first stage of the `directions` workflow (`inventory: true`); you write `INVENTORY.md` from its rows.

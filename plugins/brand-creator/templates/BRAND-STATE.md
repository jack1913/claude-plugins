---
slug: {{slug}}
name: {{name_q}}
created: {{date}}
plugin_version: {{plugin_version}}
tier: {{tier}}                 # quick | standard | full (chosen at G0)
phase: P0                      # P0 .. P13
architecture: standalone       # standalone | family-member | product-in-family (inferred; ask only when the brief shows a parent or siblings)
mark_source: generated         # generated | authored-vector | existing (inferred and stated at G0, not asked; settled from the picked direction at G2)
language: en                   # language of the chat with the owner (brand content follows the audience's language)
content_languages: ""          # language set code(s) the brand's own text is written in, e.g. pl or pl,en (read by fontcheck; set at G0)
renderer: resvg                # off macOS, after the owner agrees: resvg (opted in YYYY-MM-DD)
review_surface: auto           # auto (not answered yet: boards stay local until the owner answers the one upload question) | artifact | local
review_url: ""                 # the one stable review page (Artifact URL or local path)
incumbent: none                # none, or one line about today's mark or site; a set value makes the "today" board section required
inventory: ""                  # path to INVENTORY.md, or: none (no target repo). Required before the first board in the Full tier or product-in-family.
edition: 1                     # the brand book's edition (a whole number); a new edition needs a new G5 approval
approved_edition: ""           # the edition G5 approved; written by `state --record G5`. The book shows APPROVED only when it equals edition.
book_chapters: []              # extra chapters to include, from: tone, photography, components (the tier and architecture decide the rest)
canonical_direction: ""        # the direction that is the visible baseline after the pick
reset_rounds: []               # rounds that follow a full rejection, e.g. [4, 5]: the style board run again, then the pick board (the map is required again there)
# g1s_round: written by the tool, never by hand. `brand-creator state --record G1s "<decision>"` stores the highest round whose board is a style board at that moment; board-lint compares it with the style board of a reset round.
fixes_per_area: {}             # area: count. A third incremental fix in one area trips the G-sys stop.
gates:                         # date + decision, written by: brand-creator state --record G3 "<decision>"
  G0: ""                       # scope: tier, name language and status; the mark source as stated
  G1: ""                       # name go
  G1s: ""                      # style pick (or "skipped by owner" before the first pick board, or "n/a: ..." past round 1); every pick board waits for it
  G2: ""                       # direction pick
  G2b: ""                      # reset or recover decision (only when used)
  G3: ""                       # refined approval (the approved round is frozen)
  G4: ""                       # system rules
  G5: ""                       # pack and book
  G6: ""                       # adoption
  G7: ""                       # outward actions
---
# {{name}}: brand state

The machine-read part is the frontmatter above. Edit values with `brand-creator state --set key=value`
(or by hand); record gates with `brand-creator state --record G<n> "<decision>"`.

## Collaboration

How the owner wants to work. Defaults are in the skill's working-style reference; change a line only when the owner says so.

- Language: en
- Review surface: auto
- Explanation depth: short (one sentence per decision, detail on request)
- Check-in density: after each phase, with a one-line progress note per step
- Drawing engine: not chosen yet (use-llm design canvas | Claude Code /design | Claude-drawn SVG, only with the owner's yes and its date)

## Directions

One row per direction. Names are words (stable on the board and in chat); the letter is optional and must match the board.

| name | letter | register | status | liked | rejected | decided |
|---|---|---|---|---|---|---|

Status per direction: `open`, `liked`, `rejected` or `DECIDED` (one DECIDED at most; it is also `canonical_direction`).

## Change list (current round)

Owner feedback as numbered items, confirmed before refining. The review reports done / partly / not done per item.

1. (...)

## Rules (G4)

One line each, revertable, marked "(rule)". Numbers are proposals until the owner approves them at G4.

- (rule) (...)

## Still open

Carried in every update until closed.

1. (...)

## Liked, rejected, decided

- Liked: (what the owner reacted to well, in their words, paraphrased)
- Rejected: (what they did not want, and why if known)
- Decided: (one line each, with the date)

## Renames

| date | from | to | why |
|---|---|---|---|

## Edition log

One line per edition event, written by `brand-creator patch` and `brand-creator collapse`: `- <date> edition <n>: <what changed>`.

## Collapsed

One line per decision that closed a choice, written by `brand-creator collapse`.

## Notes

(Anything the next session needs. Keep it short.)

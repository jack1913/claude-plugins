# Brand architecture

How a brand relates to other brands. Inferred at G0 (default `standalone`); asked only when the brief or a repo
shows a parent or siblings. Full family profiles (`FAMILY.md`) are read from the owner's own repo, never shipped here.

## Modes

| mode (`architecture`) | type | relation | what is shared |
|---|---|---|---|
| `standalone` | master | independent | nothing; the brand owns every layer |
| `family-member` | master, one of several brands the owner runs | family layer + own company layer | the family grammar from `FAMILY.md` |
| `product-in-family` | product or sub-brand | branded-house, endorsed, sub-brand or independent | tile construction, letters, UI rules from the parent |

A standalone brand can still have **two registers** (for example warm for consumers, strict for company boards):
that is one brand with two voices, not an architecture question.

## Layers

- **Family layer** (shared by all brands of one owner): the grammar, for example a letter grid, a projection, base
  neutrals, hairlines, corner style, voice, languages, legal register. Lives in `FAMILY.md`.
- **Company layer** (unique per brand): mark, wordmark technique, typefaces, accent, hero, header and footer.
- **Product layer** (inside a parent): shared tile construction, shared letters copied cell for cell, one accent per
  product distinct from siblings and from the parent, one signature move per product.

## Never-borrow lists

Each brand keeps an explicit never-borrow list **in both directions**: what it must not take from a sibling, a
competitor or a reference, and what others must not take from it. The list goes into BRIEF.md (Architecture) and
into every designer prompt as FORBIDDEN.

## Endorsement policy (decide at G4, record as rules)

| option | when |
|---|---|
| full endorsement ("by <parent>" with the parent's mark) | early products that borrow the parent's trust |
| text endorsement in one muted tone, at a stated minimum size | products that stand on their own but keep the link |
| none on the parent's own surfaces | always: the parent's site does not endorse itself |
| solo everywhere | a product meant to stand alone |

Define lockup variants per context up front and let the generator enforce the policy; endorsement rules change over a
project, so the latest recorded rule wins.

## Reuse before redrawing

When related projects exist, ask for their paths once and reuse their icons, fonts and letters. Family members swap
token primitives only; semantic roles stay the same so code and books stay comparable.

## Checks

- Each brand owns one signature move and one colour role no sibling uses (compare tiles side by side).
- Family fit is checked before polish; boards in family modes say what each direction keeps and owns.
- Cross-product tile ratios and shared glyphs are checked by script in a later version (family check, stage 3).

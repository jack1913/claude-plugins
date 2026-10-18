## Changing the brand

Every change starts in a source file and ends at a check that fails when the change was not carried through.

| To change | Edit | The check that stops you |
|---|---|---|
| a colour | `tokens/primitives.tokens.json`, then `brand-creator tokens` | `brand-creator contrast`, then `brand-creator check --cascade "<old value>"` |
| the mark | `assets/logo/*.svg` | `brand-creator logo-sheet`, `brand-creator downscale`, `brand-creator check` |
| a rule | the Rules section of `BRAND-STATE.md` | `brand-creator check --cascade "<old phrase>"` |
| wording in this book | `book/chapters/*.md`, then `brand-creator book` | `brand-creator book-lint --self-consistency` |
| a fact | `FACTS.md` (owner-confirmed, with a source) | `brand-creator book-lint` (every quoted fact must equal its row) |

[[fill: anything specific to this brand: a generator the owner must re-run, a pack that lives in another repository, a parent brand's document that restates a rule (the cascade searches it when tools/cascade.json names it).]]

## Governance

[[fill: who may change what. One line each: who approves a change to the mark, the palette, the type and the rules (usually the owner alone); who may write copy that uses the brand; where a change is recorded (DECISIONS.md, and an amendment to the ADR that covers it).]]

- [[fill: naming rule: the formal name and the short name, where each is used, and the regulator's naming rule when the profession has one (name the rule and the date it was checked).]]
- [[fill: claim rule: only FACTS.md rows are claimed, each stated once and one way; no comparative or superlative claims unless a FACTS.md row with a source backs them.]]
- [[fill: accessibility commitment: the contrast targets the brand holds for text and interface (from the contrast chapter), focus states on every interactive part, and nothing that moves under reduced motion.]]

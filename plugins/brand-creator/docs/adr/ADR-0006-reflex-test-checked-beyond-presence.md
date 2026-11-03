# ADR-0006: The reflex test is checked beyond presence

- **Status:** accepted
- **Date:** 2026-10-30
- **Source:** decision 37, "Reflex test linted", of the [archived decisions log](../archive/decisions-log.md);
  `how_to_use` in [ai-defaults.json](../../skills/brand-creator/references/ai-defaults.json); "Board contract (data
  attributes)" in the [script contract](../../scripts/CONTRACT.md); the judge in `workflows/directions.js` and
  `agents/brand-judge.md`; the [changelog](../../CHANGELOG.md)

## Context

Decision 37 of the archived decisions log, "Reflex test linted", made `board-lint` require a non-empty
`data-field="reflex"` on every direction of a pick board: "no hits", or each hit with its argument. It stopped at presence
and said so: "the argument's quality stays a judgement". Three gaps are left.

- `ai-defaults.json` states two count rules in `how_to_use`: two or more hits in one direction mean "replace a part before
  showing it", and one id hit by every direction means the round is not divergent. Nothing enforces either.
- The line is free text. A script cannot tell a hit from a sentence about a hit, so it cannot count hits, compare them
  with the list or compare the arguments with anything.
- Nothing detects an undeclared hit. A direction that writes "no hits" while its board shows a listed pattern passes, and
  an argument such as "it looks good" passes as long as it is there. Patterns the list did not yet name shipped unnoticed
  in a real brand's site.

## Decision

This extends decision 37. It replaces nothing: presence stays required, and the checks below sit on top of it.

- **The format.** The reflex line of a direction is parseable. `no hits` stands alone. Each hit is one line,
  `hit: <id> | <argument>`. `near miss: <id> (<why>)` records a pattern that looks like a hit and is not one; it is kept
  and never counted. A leading `Reflex test:` label is allowed. A hit names an id of `ai-defaults.json` or an item under
  "Avoid unless argued" in the project's `research/cliches.md`.
- **Two rules fail now.** Two or more hits in one direction; one name hit by every direction. They are the two rules
  `ai-defaults.json` already states, and no board shipped with the plugin breaks them.
- **Five rules warn for one release, then fail.** The release notes say so. A line that is not in the format; a hit that
  names no known pattern; an argument that shares no content word with `FACTS.md` or `brief/BRIEF.md`; no judge list on a
  direction when the judge ran; a pattern the judge listed that the reflex line neither hits nor names as a near miss.
- **The grounding floor.** An argument is grounded when it shares a content word with the project's own material. A
  content word is a run of Unicode letters, casefolded, of four letters or more. The material is the lines of `FACTS.md`
  and `brief/BRIEF.md` that are not lines of the plugin's templates, minus the words of the templates' own boilerplate. A
  template line matches verbatim or with its `{{...}}` placeholders filled in, so the brand's name in the title is no
  ground word. No stop list of any language is applied. It is a floor against a pasted or generic argument, not a judgement
  of quality.
- **The judge list.** The judge of a direction round lists, per direction, the `ai-defaults.json` ids and "Avoid unless
  argued" items it sees (`reflex_seen` in its schema). The lead puts that list next to the declared line
  (`data-field="reflex-seen"`), and `board-lint` compares the two. Layout patterns are judged on each direction's own
  homepage frame of the deep board, never on the board's chrome. The judge runs as an agent only after the fleet gate;
  by default the lead judges in the thread.
- **The list grows.** `ai-defaults.json` goes to version 2 with four patterns: a pale ground with one timid accent, the
  display faces a generator names first (dated, "as of 2026-10"), a texture standing in for the idea, and the stock
  product page with an eyebrow over every heading.
- **Reusable rules.** The per-line rules are functions that take the cliché file as a parameter, so another board kind can
  apply them to its own list without changing them.

## Consequences

- Boards that pass today keep passing in this release. Old free-text lines, ungrounded arguments and patterns the judge
  saw but the line does not declare show as warnings; the release after this one turns the five warnings into failures.
  That switch is a separate change.
- The grounding rule is lenient by design. Sharing one word of four letters is easy, and in languages with long function
  words, such as Polish or German, a function word can match by chance. The judge list is the real guard against an
  argument that fits any brand; the floor only catches one that fits none. A project whose `FACTS.md` and
  `brief/BRIEF.md` are missing or hold only template lines (the title with the brand's name filled in counts as one) has
  no grounding words, and the row says "NOT verified" instead of passing or failing.
- Matching Unicode letters keeps Polish, German and other accented words usable as grounds. Nothing in it assumes English.
- A hit on an item of `research/cliches.md` warns until the project has that file with the item under "Avoid unless
  argued", so a category's own clichés are checked only when the research was done.
- Credit. The idea that an exception's argument must share a word with the page's own material comes from Hallmark (MIT
  licence, "Hallmark contributors"), where a waiver's reason must share a word with the page. Nothing was copied: no code
  and no text. Its word matching takes ASCII letters only; brand-creator's does not, and that matching was not ported.

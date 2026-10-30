# ADR-0008: Text grounds carry complete roles

- **Status:** accepted
- **Date:** 2026-10-30
- **Source:** "Token sources (DTCG 2025.10)" and "QA gates and mark tooling" in the
  [script contract](../../scripts/CONTRACT.md); the [tokens phase](../../skills/brand-creator/references/phases/07-tokens.md);
  the [QA phase](../../skills/brand-creator/references/phases/09-qa.md); `templates/tokens/semantic.light.tokens.json`;
  the [changelog](../../CHANGELOG.md)

## Context

`contrast` checks the pairs a brand declares in `$extensions["brand-creator"].pairs` of its semantic tokens, and the mark
against the grounds it touches. A pair is checked only when someone declared it. Nothing asked which colours text sits on,
or whether each of those grounds has everything a page needs on it: the text, the button, the label on the button, the
focus ring and the border.

A real brand's dark theme shows what that leaves open. Its action colour, a butter yellow, was also the colour of the hero
ground, so the button on the hero vanished into it. The focus ring was invisible on the same ground. `contrast` could not
have caught it unless someone had declared exactly those pairs.

## Decision

- **Five roles per ground.** Every ground that carries text has five roles in both themes: text, action, on-action
  (the label on the action), focus and border. A ground without all five in light and dark is incomplete.
- **Checked by contrast and by colour-vision distance.** `contrast` checks, for each ground and theme, text on the ground at
  4.5:1 or more, the action against the ground at 3:1, the on-action on the action at 4.5:1, and the focus and the border
  against the ground at 3:1. With `--cvd` it also checks that the action and the focus stay apart from the ground for the
  colour-vision simulations, so a pair does not pass on contrast alone and collapse for some viewers.
- **The owner names the grounds.** The grounds live in `$extensions["brand-creator"].grounds` of
  `tokens/semantic.light.tokens.json`: `named_by_owner` holds the date and the owner's words, and `list` holds one entry per
  ground with its five roles. The model never guesses which colours text sits on. It asks the owner at G4, in plain words,
  and records the answer with the date. Until `named_by_owner` starts with a date, the checks say the grounds are a
  proposal, not named by the owner.
- **The starter carries a proposal.** The starter tokens add the roles `on-accent` and `focus` and propose one ground,
  `color.bg`, with `named_by_owner` empty. The proposal runs the checks; it does not name anything.
- **The handoff carries the roles.** DESIGN.md, BRAND.md and the applied skill list the roles of each ground. A missing role
  is left out and reported as missing, never filled in.
- **Warn now, fail next release.** Every ground check is a warning in this release and says it will be a failure from the
  next. A report's status and a command's exit code do not change because of them.

## Consequences

- An existing project sees warnings until its owner names the grounds, and again for every ground that lacks a role. The
  starter's proposal does not silence them, so the owner has to be asked once.
- The release after this one turns the warnings into failures. A project whose named grounds pass meets no change.
- A brand with no label colour for its action and no focus colour has two roles to decide, each with a light and a dark
  value.
- A ground that is not in the list is not checked. The check is as complete as the owner's answer, which is the point of
  asking rather than inferring.
- Colour-vision distance is checked for the action and the focus only. Text and border are checked by contrast only.

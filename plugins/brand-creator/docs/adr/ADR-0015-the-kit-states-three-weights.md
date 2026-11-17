# ADR-0015: The kit states three weights: fixed, default and example

- **Status:** accepted
- **Date:** 2026-11-17
- **Source:** the first adoption of a generated kit by a product site (the pilot brand, kit 4.10, plugin 0.11.1) and what it
  found, 2026-11-12; the owner's words of 2026-11-12 (the kit should be a universal solution that boxes nothing in and does
  not change how developers prefer to work; it needs restating, not reshaping: it is the brand's good practice and
  references, which a product with a better approach may leave, as long as the result is in line with the kit's hard parts),
  their answer of 2026-11-13 (three weights, the practices kept) and their yes of 2026-11-17 to this change;
  [ADR-0011](ADR-0011-a-generated-brand-kit-around-the-applied-skill.md) (the tags, the recipes as steps),
  [ADR-0010](ADR-0010-the-site-round-makes-reference-pages-not-templates.md) (reference pages, never templates); the working design
  `dev/specs/2026-11-09-g8-one-brand-kit-design.md` (its goal 1 and the anti-goal on the rules); the "kit" section of the
  [script contract](../../scripts/CONTRACT.md).

## Context

The generated kit spoke in one voice. A rule the owner decided, a step of a recipe, a choice made for one reference page and
a sample layout all read as instructions of the same force, and the text sent every open choice to the owner ("ask the
owner", "label it a proposal").

The first product to adopt a kit showed what that costs. Its builders took numbered recipe lines and the choices of a
reference page as binding, copied a weak spot of a reference page because the page was "approved", and stopped to ask an
owner who is not at hand in a product repository. A team with its own way of planning, building and testing read the kit as
a process laid over theirs.

Two answers were weighed. One turned the kit into a contract only: the steps removed, the recipes rewritten as
descriptions of a finished piece. The owner declined it: the steps are practice the brand paid for (the hero first, the
built page checked in light and dark, the cold read), and the working design of 2026-11-09 asked for them. The other left
the text alone, which keeps the problem.

## Decision

- **Every line of the kit has one of three weights.** Fixed is the identity: the logo files, the token colours and their
  contrast, the type, the "never" list, claims that are true, and the owner's rules. It is kept in every piece. Default is
  the brand's usual pattern and its practice: the steps, the recipes, the checklist. It is used or bettered, and leaving it
  needs no permission, only a reason that can be stated. Example is one good application: a reference page, a master, a
  sample. A reader takes what helps.
- **The generated `SKILL.md` says so,** in `## How to read the kit`, so every kit gets the statement at its next build
  and it covers the owner's files as they are. The brand sorts its rules by weight in `golden-rules.md`.
- **The heading is the weight and the tag is the source.** In the owner's files a line stands under `## Fixed`,
  `## Defaults` or `## Examples`. The tags keep their meaning: `[rule: <id>]` is a decision the brand recorded, `[example]`
  is an illustration. There is no third tag value: one recorded rule can hold a fixed statement and a default one (a
  smallest text size and the usual weights of a font, in the pilot brand), so the weight belongs to a line, not to a rule
  id.
- **Where no heading says the weight, the tag decides.** A `[rule: <id>]` line is fixed, numbered or not; a choice made
  for a reference page (`[rule: site:<id>]`) is a default; an `[example]` line is an example; numbered steps with no tag
  are practice. A rule nobody sorted is fixed, so a kit whose owner has not sorted anything binds exactly as before.
- **Token values beyond colour are defaults.** Spacing, radius and motion timing are the brand's usual pattern; an owner
  who wants one kept writes it under Fixed. The signature move, where a brand has one, is fixed with the logo files, and
  so are the copy rules the owner approved with the masters.
- **The steps stay, as practice.** `## How to work` in `SKILL.md` and `### How we usually make one` in the scaffolded
  recipes keep their numbered steps under one sentence: this is the brand's own practice; follow it, or use a better way
  of your own. The page check is named for where brand-creator and the brand project are at hand, with what to do without
  it.
- **Three things are never made up:** a new brand colour, a claim that `facts.json` does not hold, and a redrawn logo. The
  work is finished without them and whoever maintains the brand is told. Anything else the kit does not cover is the
  maker's to decide, in line with the fixed parts, and to state. The generated text no longer sends a choice to the owner,
  and it says that "the owner" is whoever maintains the brand.
- **What does not change:** `SKILL.md` still prints every rule verbatim under `## Rules the owner decided` (the anti-goal
  of the working design); the tags and the rule for values are as ADR-0011 set them; a generated file is never edited; the
  applied skill of a project without a kit keeps its bytes.

## Consequences

- A product team keeps its own way of working, and the kit tells it what it may not change. A reference page can no longer
  be read as a template ([ADR-0010](ADR-0010-the-site-round-makes-reference-pages-not-templates.md)): the kit calls it an example and
  its choices defaults.
- The sort is the owner's decision, and it says what binds every product. Until the owner sorts, every rule is fixed.
- `kit check` does not compare a heading with a tag, and it cannot tell whether a rule says what the line under its id
  says: it checks that the id exists. A rule id stretched over a line the rule never decided still passes. `EXTENDING.md`
  warns the owner.
- "Claims are fixed" and "every colour is a token role" are prose: neither has a rule id a line could cite.
- A kit's `brand.md` says, like its `SKILL.md`, that a ground colour the tokens lack is built from the token colours and
  that a layout value they lack is chosen in line with those listed. The kit hands those words to the shared builder,
  so the applied skill keeps "ask the owner" and its bytes. For a brand with no font family in its tokens, `brand.md`
  still says to ask the owner.
- The sort lives in `golden-rules.md`, an owner file. A product repository that edits its copy keeps it on update, and
  `kit status` still calls the copy current, so in that repository a rule can change weight unseen. Carrying the sort
  in generated data would close this.
- A kit that exists keeps its own recipes and its own `golden-rules.md`: a scaffold is written only where the file is
  absent. Its `SKILL.md` and `checklist.md` change at the next build, so the build number goes up and a product's copy
  reads as behind until it is updated.
- Left for later records: a check that the heading and the tag agree, rule ids for claims and token colours, the web and
  social files in the kit, rules and their weights as structured data, and a check that ships inside the kit.

# Extending the {{brand}} brand kit

This folder, `.claude/skills/{{skill}}/`, is the {{brand}} brand kit. It holds two kinds of file: the ones the kit generates and the ones that are yours.

## What is generated

`SKILL.md`, `kit.json`, `rules.json`, `facts.json` and everything under `brand/`, `snippets/` and `reference-pages/` come from the brand project. `brand-creator kit build --yes` writes them. Never edit one, in this folder or in a copy of the kit in a product repository: the next build stops on a hand edit, and `brand-creator kit check` and `brand-creator check` fail it.

To change something generated, change the brand project (the tokens, the logo, the rules, the facts) and run `brand-creator kit build --yes` again.

## What is yours

`EXTENDING.md` (this file), `voice.md`, `visual.md`, `golden-rules.md` and `recipes/web-page.md`. The build writes each of them once, from a scaffold, only when the file is absent. It never overwrites or moves one. If you delete one, the next build writes the scaffold again.

`voice.md`, `visual.md` and `golden-rules.md` start as a heading, one sentence and a fill marker: a note between double square brackets that starts with the word fill. Replace each marker with your own text. `brand-creator kit check` fails while a marker is left.

## How to extend

- A new recipe is a new file under `recipes/`, for example `recipes/email.md`. Write numbered steps and no values; take the shape of `recipes/web-page.md`.
- A folder of your own sits beside the generated ones, for example `notes/`. Do not put a file into `brand/`, `snippets/` or `reference-pages/`: the build treats it as foreign and stops.
- A link inside the kit points at a file inside the kit, so that it still resolves in a product repository.

## Test the kit

To find out whether the kit is enough on its own, ask in the brand project for a kit test. A builder works from a copy of this kit alone and makes a hero and one other piece, `brand-creator page-check` scores them against the brand, and a cold reader says ship or fix. Each gap goes back to the brand project's tokens, rules or facts, or to one of your own files above, and then the kit is built again. A generated file is never patched. The result is written in the project's `BRAND-STATE.md`.

## Tags and values

- A bullet in a recipe, and a bullet or a numbered line in `visual.md` and `golden-rules.md`, carries a tag: `[rule: <id>]` or `[example]`. Numbered steps in a recipe need no tag.
- `[rule: <id>]` names a rule the kit knows. A rule of the brand is written bare, with the id it has in `rules.json`. A page rule is written `page:<id>`, and a choice of a reference page `site:<id>`.
- `[example]` says the line shows one case and is not a rule.
- A value (a number with a unit, a ratio, a colour) cites a token or a known rule on its line, or the line is tagged `[example]`. A token is a CSS variable from `brand/assets/tokens/tokens.css`, written `var(--name)`, or a path in `brand/assets/tokens/tokens.json`, written `{dotted.path}`.

## The version

The version is `<edition>.<build>`. It lives in `kit.json`, and `SKILL.md` prints it. Write no version anywhere else. The build number goes up by one at the next build when anything the build generates changed, or when one of your five files changed: `EXTENDING.md`, `voice.md`, `visual.md`, `golden-rules.md` or `recipes/web-page.md`. A file of your own beside them, such as `recipes/email.md` or `notes/`, is not part of the kit's content and moves nothing.

## A product repository's copy

A product repository gets the kit as a byte copy, made on a branch you name with `/brand-creator:brand-adopt`. `brand-creator kit status --repo <folder>` says whether the copy is current and lists what to copy. An update copies the generated files. The owner files in the repository belong to the repository: an update copies one only where the repository has none, and reports the ones that differ.

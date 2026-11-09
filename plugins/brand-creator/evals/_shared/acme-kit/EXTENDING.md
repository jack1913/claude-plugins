# Extending the Acme brand kit

This folder, `.claude/skills/acme-brand/`, is the Acme brand kit. It holds two kinds of file: the ones the kit generates and the ones that are yours.

## What is generated

`SKILL.md`, `brand.md`, `checklist.md`, `install.py`, `kit.json`, `rules.json`, `facts.json` and everything under `brand/`, `snippets/` and `reference-pages/` come from the brand project. `brand-creator kit build --yes` writes them. Never edit one, in this folder or in a copy of the kit in a product repository: the next build stops on a hand edit, and `brand-creator kit check` and `brand-creator check` fail it.

The masters you approved are copied in too: everything in the brand project's `assets/masters/` arrives under `brand/assets/masters/`, byte for byte. Only approved masters belong in that folder, because the kit cannot know which are approved. A font among them is copied only when it is under the SIL Open Font License and its licence text is in `assets/fonts/`; any other is listed in `kit.json` and left out.

To change something generated, change the brand project (the tokens, the logo, the rules, the facts) and run `brand-creator kit build --yes` again.

## What is yours

`EXTENDING.md` (this file), `voice.md`, `visual.md`, `golden-rules.md` and `recipes/web-page.md`. The build writes each of them once, from a scaffold, only when the file is absent. It never overwrites or moves one. If you delete one, the next build writes the scaffold again. Once the brand's approved masters list an ad or a deck (`brand/assets/masters/masters.json`), `recipes/ad.md` and `recipes/presentation.md` are scaffolded the same way.

Every other file in this folder that the build does not generate is yours too, and it travels with the kit: a recipe you add, a folder of your own, a PDF or a spreadsheet in it. The build only reads these files, to record them. A symbolic link is not a file of yours: the build stops on one and never reads through it.

`voice.md`, `visual.md` and `golden-rules.md` start as a heading, one sentence and a fill marker: a note between double square brackets that starts with the word fill. Replace each marker with your own text. `brand-creator kit check` fails while a marker is left.

## How to extend

- A new recipe is a new file under `recipes/`, for example `recipes/email.md`. Write numbered steps and no values; take the shape of `recipes/web-page.md`. A file you add travels with the kit: the next build records it, and it is on the copy list a product repository gets, copied where the repository has none and updated where the repository never changed it.
- A folder of your own sits beside the generated ones, for example `notes/`. Its files travel too, and the map of `SKILL.md` names the folder after the next build. A Markdown file there is read by `brand-creator kit check` like your recipes (a fill marker, a tag on each bullet, a source for each value); a file of another kind is copied and never read for fill markers, tags or values. The links in an `.html` or `.css` file of yours must still lead to a file inside the kit, as in any file of the kit. Do not put a file into `brand/`, `snippets/` or `reference-pages/`: the build treats it as foreign and stops.
- A link inside the kit points at a file inside the kit, so that it still resolves in a product repository.

## Test the kit

To find out whether the kit is enough on its own, ask in the brand project for a kit test. A builder works from a copy of this kit alone and makes a hero and one other piece, `brand-creator page-check` scores them against the brand, and a cold reader says ship or fix. Each gap goes back to the brand project's tokens, rules or facts, or to one of your own files above, and then the kit is built again. A generated file is never patched. The result is written in the project's `BRAND-STATE.md`.

## Tags and values

- A bullet in a recipe or in any other Markdown file of your own (`voice.md` and this file apart), and a bullet or a numbered line in `visual.md` and `golden-rules.md`, carries a tag: `[rule: <id>]` or `[example]`. Numbered steps in a recipe need no tag.
- `[rule: <id>]` names a rule the kit knows. A rule of the brand is written bare, with the id it has in `rules.json`. A page rule is written `page:<id>`, and a choice of a reference page `site:<id>`. The kit checks every such tag on every line of those files, bullet or not, in a code block too.
- `[example]` says the line shows one case and is not a rule.
- To show the tag itself in one of those files, write a placeholder in angle brackets: `[rule: <id>]`, `[rule: <rule id>]`, `[rule: page:<id>]`. It names no rule, so `kit check` does not look it up, in a sentence, a code span or a code block. It is not a citation either: a bullet that shows it still needs its own tag, and a value on its line still needs a token, a known rule or `[example]`.
- A value (a number with a unit, a ratio, a colour) cites a token or a known rule on its line, or the line is tagged `[example]`. A token is a CSS variable from `brand/assets/tokens/tokens.css`, written `var(--name)`, or a path in `brand/assets/tokens/tokens.json`, written `{dotted.path}`; the path ends at a token, such as `{color.bg}`, never at a group.
- A `{dotted.path}` that is no token fails, even between backticks in a sentence: `kit check` reads it as a token reference. To show a placeholder of your own, write it without the dot, or put it in a code block on a line with no value.

## The version

The version is `<edition>.<build>`. It lives in `kit.json`, and `SKILL.md` prints it. Write no version anywhere else. The build number goes up by one at the next build when anything the build generates changed, or when a file of yours was added, changed or taken away: one of the five above, or a recipe or a file of your own such as `recipes/email.md` or `notes/palette.txt`.

## A product repository's copy

A product repository gets the kit as a byte copy, made by the kit's own installer: `python3 install.py <folder in the repository> --yes` (without `--yes` it only says what it would copy), run by `/brand-creator:brand-adopt` on a branch you name, or by anyone with a copy of the brand project. `brand-creator kit status --repo <folder>` says whether the copy is current and lists what to copy. An update copies the generated files, copies an owner file where the repository has none, and updates one the repository never changed since it was copied. An owner file the repository changed or added is the repository's own: it is kept, and reported.

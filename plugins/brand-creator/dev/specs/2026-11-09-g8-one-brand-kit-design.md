# brand-creator 0.11.0 (group 8): one brand kit

- **Status:** owner's answers in (2026-11-09); ready for the plan
- **Date:** 2026-11-09
- **Sources:** the Płacuję brand project (`~/Dev/projects-brands/placuje`), read only on 2026-11-09: its hand-made kit
  `skill/placuje/` (kit 1.5.0) and its generated kit `.claude/skills/placuje-brand/` (version 4.2, plugin 0.7.0);
  [ADR-0011](../../docs/adr/ADR-0011-a-generated-brand-kit-around-the-applied-skill.md) and its decisions D10 and D11;
  the Płacuję feedback on 0.6.0, item 8 ("one kit path", `dev/scratch/2026-11-04-placuje-feedback-0.6.0.md`); the kit
  baseline run G3-01 of 2026-11-01; the Claude Code guidance on skills (SKILL.md is the overview and points to files read
  when needed; under 500 lines; about 1,500 to 2,000 words for the core).

## Why

### Two kits on Płacuję

Płacuję has two brand kits that do the same job:

| | Hand-made `skill/placuje/` | Generated `.claude/skills/placuje-brand/` |
| --- | --- | --- |
| Made by | hand, refreshed by its own `scripts/sync.py` | `brand-creator kit build` |
| Checked by | its own `scripts/check.py` | `brand-creator kit check` and `check` |
| Size | 8.1 MB | 25 MB (the site's pages and every master) |
| Installed by | `scripts/install.sh`: bash, python3 and git, no plugin | `/brand-creator:brand-adopt` only: an adoption row, G6 recorded, a branch, the copy list of `kit status` |

The hand-made kit cost twelve hand version bumps in six days (ADR-0011's context). On 2026-11-08 it stopped syncing:
its `sync.py` copies the generated `SKILL.md` as its `references/core.md`, and that page now links to files only the
generated kit has (`brand/site/...`, `reference-pages/...`, `snippets/logo.html`, `snippets/on-ground.css`). The owner
chose one kit, the generated one, and asked for the hand-made kit's good features to move into the generator
(2026-11-09: "1, we need one", "implement if they are any good features from the hand written to the generated and to
the generator").

Moving now is cheap: no product repository carries either kit yet (BRAND-STATE.md, 2026-10-26: "No repository has it
yet"; no `.claude/skills/placuje*` folder under `~/Dev` outside the brand project, searched 2026-11-09). The read-only
mirror `inewi/brand-placuje` tells its readers to install with `skill/placuje/scripts/install.sh`
(`placuje/README.md`, "The skill: using the brand in other projects"), so those readers need a new route.

### What the hand-made kit does that the generated one does not

Checked against both kits and the plugin's code on 2026-11-09:

1. **A short entry page.** The hand-made `SKILL.md` is 6 KB: the brand in one minute, seven "how to work" steps, ten
   golden rules and a map of where to look; the detail (20 KB `references/core.md`) is read when needed. The generated
   `SKILL.md` is 434 lines and 3,812 words, read whole every time the skill loads. Its `## The kit` section is 163 lines,
   150 of them a list of file paths that `kit.json` already records. It has no "how to work" steps and no map, and the
   owner's `golden-rules.md` is named only in that list. By section: the owner's rules 1,105 words, colour 961, claims 605,
   motion 337, mark 93, never 77, type 51, layout 35.
2. **A review checklist.** `checklists/review.md`, 24 items, run before anything is handed over. The generated kit has
   none: nothing in `scripts/adaptlib/kitlib.py` or `templates/kit/` writes one.
3. **Recipes for the masters.** The hand-made kit has ten recipes, among them `ad.md` and `presentation.md`, which start
   from the approved masters. The generated kit scaffolds one recipe, `recipes/web-page.md`. The plugin already names
   `recipes/ad.md` and `recipes/presentation.md` as the files new masters make stale (`MASTER_RECIPES`, row
   `masters:behind-site`) but writes neither.
4. **Updates reach every copy.** `install.sh update` replaces a repository's whole copy (the old one goes to a backup
   folder). In the generated kit, an owner file a repository already has is never overwritten (D11), so when the brand
   project improves `recipes/ad.md`, a repository keeps the old one until someone copies it by hand.
5. **Installing without the plugin.** Anyone with a clone of the brand project or its mirror can run `install.sh`. The
   generated kit is copied only by the plugin's implementer, file by file, after G6 (D10: "A script never writes outside
   the brand project").

Not features to carry over: the hand-made kit's `--global` install (the owner, 2026-10-26: "nie chce żeby to był globalny
skill… ma się instalować per projekt"; ADR-0011 refuses a global copy too), its `examples/` screenshots (the generated
kit carries the masters' pictures and the reference pages' stills), and its Płacuję content (voice, components, code
snippets), which is the brand's, not the plugin's (Part B).

### What the generated kit already does better

It is built from the brand project and cannot drift; `kit.json` hashes every file and `kit check` proves the kit whole,
current and filled in. It carries the approved reference pages with their notes and stills, the rules as data with ids
(`rules.json`), only the public facts (`facts.json` never holds a contact row; the hand-made `core.md` carried internal
paths and working names), every approved master, and one version number. Every bullet of an owner file carries a rule tag
or `[example]`, and every value cites a token or a rule.

The blind pick of G3-01 (2026-11-01) preferred the hand-made kit's hero; the generated skill's hero then failed 15 page-check
rows because its paths did not resolve outside the project, which G3-13 fixed. The entry page, the checklist and the
recipes above are what remains of that gap.

## Goals

1. One kit per brand, the generated one, with what made the hand-made kit work: a short entry page with steps and a map,
   a review checklist, recipes for the masters, and updates that reach product repositories.
2. A product repository gets the kit and its updates without copying file by file: an installer the kit carries (A5).
3. Płacuję moves its content into the generated kit and retires `skill/placuje/` (Part B, in the Płacuję session).

## Non-goals

- Print as a material and a print recipe scaffold: the owner put print in 0.20.0.
- A global install (the owner, 2026-10-26; ADR-0011).
- Recipes the plugin writes for channels it knows nothing about (e-mail, campaign, video, social post): without approved
  masters or pages behind them they would be invented steps. The owner writes them; the kit carries them.
- Loosening the tag and value rules so the hand-made text passes unchanged.
- Any change to the applied skill of a project without a kit: same bytes (ADR-0011).
- A `remove` command: taking the kit out of a repository is `git rm -r .claude/skills/<slug>-brand`.
- Agent fleets; paid calls in tests; macOS CI.

## Anti-goals

- An entry page so short that the owner's rules are no longer read: the rules and the "never" list stay in `SKILL.md`.
- An update that overwrites a repository's own edit of an owner file.
- A checklist line the brand never decided.
- Two pieces of code that judge "current" differently (the plugin's `kit status` and anything installed with the kit).

## Constraints

- The build stays deterministic, standard library only, with no clock and no random numbers (ADR-0011).
- A generated file is never edited by hand; a file of the owner's is never overwritten by the build.
- New generated files join `kit.json`, `kit:files` and `kit:links` like every generated file; they are not judged for tags.
- The first build on 0.11.0 changes generated content, so each existing kit's build number goes up once.
- Every change to ADR-0011's decisions is a new record, ADR-0014, which supersedes only the parts it names.

## Part A: the plugin

### A1. A short entry page

Only the kit's `SKILL.md` changes; a project without a kit keeps today's applied skill.

- `SKILL.md` keeps its front matter, title, status line and "use this whenever" line, and holds, in this order:
  - `## How to work`: generated steps, the same for every brand with its name filled in, each naming only files the kit
    always has: name the material and the moment; read `golden-rules.md`; open the matching recipe in `recipes/` (when
    none fits, work from `brand.md` and say what is not covered); take every value from the tokens and ask for one the
    tokens lack; take the logo from its files, never typeset (and from `snippets/logo.html` when the kit has it); take
    every claim from `facts.json`, and leave a
    visible placeholder and ask when one is missing; anything new is a proposal for the owner; before handing over, go
    through `checklist.md`. When the kit has masters, one more step: ads and decks start from the approved masters.
  - `## The kit`: the version line and the two paragraphs it has today (a brand kit; copy the files a product uses into
    its own public folder). The list of 150 file paths goes; `kit.json` lists every file.
  - `## Rules the owner decided` and `## Never`: as today.
  - `## Map`: a table from a need to a file or folder, one row each for what the kit has: `brand.md`, the tokens, the
    logo files, `snippets/`, `rules.json`, `facts.json`, `reference-pages/` (when there are pages), the masters' README
    (when there are masters), the motion files (when the brand moves), `recipes/`, `golden-rules.md`, `visual.md`,
    `voice.md`, `checklist.md`, `EXTENDING.md`, `kit.json`. It names no file the owner added (as today).
- A new generated file, `brand.md`, at the top of the kit, holds what moves out: Colour (the colours, the pairs and the
  grounds), Type, Layout, Mark (with the size bands), Motion and What may be claimed, in today's words.
- On Płacuję this takes `SKILL.md` from 3,812 words to about 1,500 and puts about 2,100 in `brand.md`.

### A2. A review checklist from the rules

A new generated file, `checklist.md`, at the top of the kit, built only from what the kit already holds:

- the logo: from its files; the size bands (which drawing up to which size) and the size rule, as `rules.json` holds
  them (a clear space or a size floor the owner decided is one of the owner's rules below);
- colour: every colour a token role; every text and component pair one of those `brand.md` lists, with its ratio;
- one line for each rule the owner decided, with its id;
- the words never written (`rules.json`);
- one line for each page rule, when `rules.json` has a page block;
- claims: only from `facts.json`; a missing fact is a visible placeholder; sample data is labelled;
- anything new is labelled a proposal and shown to the owner;
- last: "and every rule in `golden-rules.md`".

Each line is a Markdown task item (`- [ ]`). No line comes from anywhere else.

### A3. Recipes for the masters

The build scaffolds `recipes/ad.md` when `assets/masters/masters.json` (written by `masters approve`) lists an entry of
kind `ad`, and `recipes/presentation.md` when it lists one of kind `slide`, `deck-html`, `deck-pdf` or `deck-pptx`.

- Each is written once from `templates/kit/recipes/`, only when absent, never overwritten, and written again if deleted
  while `masters.json` still lists the kind, like the five owner files today.
- Each is numbered steps with no value, in the shape of `recipes/web-page.md`: start from an approved master
  (`brand/assets/masters/README.md` lists each file, its size and the copy rules); keep its canvas and its layout; take
  the copy from `facts.json` and the copy rules; nothing outside the canvas and no text covered; a PowerPoint deck is
  checked in PowerPoint, never Keynote. One fill marker: when to use which direction.
- `kit.json` `owned` lists the five files plus the scaffolds the masters call for.
- A brand whose masters have no `masters.json` (masters placed by hand, as Płacuję's) gets no scaffold.

### A4. Updates reach owner files a repository never changed

`kit status` judges each owner file a repository has against three things: the project's file, and the hash the
repository's own `kit.json` recorded for it (`owned`) when it was copied.

| The repository's file | Today | 0.11.0 |
| --- | --- | --- |
| missing | copied | copied |
| same bytes as the project's | nothing | nothing |
| the bytes its `kit.json` recorded, and the project's file changed since | reported as differing, kept | **updated**: on the copy list |
| anything else (the repository changed it) | reported as differing, kept | reported as differing, kept |
| no record in its `kit.json` (the repository added it) | the repository's own | the repository's own |
| recorded, unchanged, and no longer in the project's kit | not looked at | left over: moved to `removed-<date>/`, like a generated file |

- The copy list stays in its order (generated files, then owner files to copy and to update, `kit.json` last), and the
  output names the files to update separately from the files to copy.
- The implementer's rule in `brand-adopt` and `agents/brand-implementer.md` ("an owner file the repository already has is
  never overwritten") becomes "... unless `kit status` lists it to update".
- Nothing is lost: an updated file holds bytes that an earlier kit shipped, which the brand project's history has.
- ADR-0014 records it; it supersedes D11's "copies an owner file only where the repository has none".

### A5. Installing without the plugin

The kit carries its own installer (the owner, 2026-11-09).

- A new generated file, `install.py`, at the top of the kit: Python standard library only, the same bytes in every kit
  of a plugin version (it reads the kit's name and files from `kit.json` when it runs).
- `python3 install.py <folder in a repository>` prints the plan: the same states and lists as `kit status --repo`.
  `--yes` copies into `<repository root>/.claude/skills/<slug>-brand/` by the rules of A4, moves left-over files to
  `removed-<date>/` in the repository, then reads the copy back and says it is current, or stops with the reason.
- It refuses what `kit status` refuses: a folder outside a git work tree, the home folder or anything under `~/.claude`
  (never global), the brand project itself, a kit folder that is a link, and a kit whose files do not match its
  `kit.json`.
- It never commits, never makes a branch and never pushes; it ends with "review and commit it in <repository>".
- `brand-adopt`'s kit step runs `install.py` instead of copying file by file; the adoption row, G6 and the owner's branch
  stay as they are.
- One judge: the tests run `install.py --json` and `kit status --json` on the same fixtures and require the same answer.
- ADR-0014 supersedes D10 for this one file: the plugin's own scripts still write only inside the brand project;
  `install.py` is a file of the kit that a person runs.

Not taken: keeping D10 (the kit copied only through `brand-adopt`, so a mirror reader needs the plugin and the adoption
flow), and a plugin command `kit install --repo` (still needs the plugin).

### A6. A second skill for the same brand

`kit status` (and `install.py`) warns when the repository's `.claude/skills/` holds another skill folder whose `SKILL.md`
front matter (`name` or `description`) names the brand, such as `placuje/` beside `placuje-brand/`: Claude may load
either. Read only; taking the old one out is the owner's call.

## Part B: Płacuję, in its own session after 0.11.0

1. Update the plugin to 0.11.0, run `check --refresh` (the reports still carry plugin 0.7.0), and build the kit.
2. Fix the print templates added on 2026-11-08 (`assets/masters/druki/`, not committed yet), which `kit:links` would
   fail: four load `/assets/fonts/Geist[wght].ttf` by an absolute path (make it `../../fonts/Geist[wght].ttf`, which
   resolves in the project and in the kit), and `email-signature.html` has the placeholder `src="{{logo_url}}"` (point it
   at a logo file in the kit; the recipe says a sent signature needs the logo's hosted address). Then commit them with the
   `assets/masters/README.md` row.
3. Move the hand-made content into the generated kit's owner files, each line tagged and each value cited:
   - the recipes `ad`, `presentation`, `print`, `email`, `campaign`, `social-post`, `video`, `app-screen`, `blog-cover`,
     and the hand-made `web-page` merged into the generated one;
   - `references/components.md` and `references/motion.md` into a folder of the owner's (for example `guides/`);
   - `references/voice.md` and `references/visual.md` into `voice.md` and `visual.md`; the ten golden rules into
     `golden-rules.md`; the review checklist's Płacuję-only items into `golden-rules.md`;
   - the snippets `guma-bar.css`, `status.html`, `reveal-once.js` and `sample-data.md` into a folder of the owner's (for
     example `code/`), with links that resolve inside the kit (`logo-theme.html`, `fonts.css` and `on-brand-ground.css`
     have generated equivalents);
   - links rewritten: `../brand/masters/` to `../brand/assets/masters/`, `../references/core.md` to `../brand.md` or
     `../facts.json`, `../snippets/` to the new folders.

   Measured with the plugin's own functions on 2026-11-09: 111 bullets without a tag and 113 lines with a value and no
   citation across those files. That rewrite is the cost; `kit check` then keeps them honest.
4. `kit check` passes; the owner reads the kit.
5. Retire `skill/placuje/` (the owner runs the command) and rewrite the README section "The skill: using the brand in
   other projects" for the new installer. The skill's name changes from `placuje` to `placuje-brand` (`/placuje-brand`).

## Decided by the owner

- One kit, the generated one; bring the hand-made kit's good features into the generator (2026-11-09).
- A kit installs per repository, never globally (2026-10-26, BRAND-STATE.md).
- Print in 0.20.0 (2026-11-07).
- No agent fleets, no paid calls in tests, no macOS CI.

## My calls (marked for the owner to check)

- The release is 0.11.0, a minor version: new generated files and a new install route.
- What leaves `SKILL.md` for `brand.md`: colour, type, layout, mark, motion and claims; the owner's rules and the "never"
  list stay, because they are the ones a piece breaks.
- The names `brand.md`, `checklist.md` and `install.py`, all at the top of the kit.
- The masters scaffolds follow `masters.json` kinds; a brand without `masters.json` gets none.
- `reveal-once.js`, the Guma bar and the status pills stay Płacuję's: "play once per session" and the pill design are
  the brand's choices, not rules every brand has.
- The second-skill warning (A6).

## The owner's answers (2026-11-09)

1. Installing without the plugin: the kit carries `install.py`, which supersedes D10 for that one file (A5) ("1. yes").
2. Updates to owner files: an owner file a repository never changed is updated when the brand project's copy changes,
   which supersedes D11's "only where the repository has none" (A4) ("2. yes").

## Left to the builder

The template layout (one applied-skill template for both cases, or a kit template beside it), the JSON field names of
`kit status` and `install.py`, the exact checklist wording, the tests, and the docs: ADR-0014, the "kit" section of
`scripts/CONTRACT.md`, the manual page `docs/manual/use/use-your-brand-kit.md`, the `templates/kit/EXTENDING.md` scaffold
(new files, the update rule), `brand-adopt` and `agents/brand-implementer.md`, and the CHANGELOG. Calibration: a scratch
copy of Płacuję, built on 0.11.0, with the words of `SKILL.md` and `brand.md` measured against A1, `kit check` run, and
`install.py` used on a scratch repository: install, an owner file changed in the project, update, then a repository edit
kept.

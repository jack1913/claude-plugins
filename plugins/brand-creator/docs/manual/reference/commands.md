# Commands

Everything brand-creator adds to Claude Code. "You only" means it runs only when you type it; "you or Claude" means
Claude can also start it when your request matches. [Glossary](glossary.md) explains words like tier, board and round.

## Commands and skills

| Command | Starts | What it does | Arguments |
| --- | --- | --- | --- |
| `/brand-creator:brand-creator` | you or Claude | Starts or continues a brand project and runs it one decision at a time | — |
| `/brand-creator:brand-naming` | you or Claude | Finds a name, or screens one you have; screening, not clearance | — |
| `/brand-creator:brand-assets` | you or Claude | Makes favicons, app icons, social images and other platform files from a logo you already have | — |
| `/brand-creator:brand-book` | you or Claude | Builds, updates, reviews and exports the brand book | — |
| `/brand-creator:setup` | you only | Installs the tools brand-creator needs, after showing what it will download and getting your yes | `[--force]` |
| `/brand-creator:new` | you only | Starts a new brand project and asks up to three quick questions | `[slug]` |
| `/brand-creator:round` | you only | Builds the next round of boards (the style board first, then directions, refinements and, in Standard and Full, a motion round) and stops for your decision | `[style\|pick\|refine\|motion] [what this round should answer]` |
| `/brand-creator:status` | you only | Shows where the project stands and what comes next | — |
| `/brand-creator:check` | you only | Runs every check that applies, and optionally searches for leftovers of old values | `[<old value or phrase> ...]` |
| `/brand-creator:review` | you only | Reviews the latest work and gives you one list to approve | `[board\|book\|pack\|all] [panel]` |
| `/brand-creator:brand-adopt` | you only | Looks at where your brand belongs in your product repositories, and changes them only when you ask | `[survey\|apply\|review\|status] [repository label]` |
| `/brand-creator:launch` | you only | Writes your launch checklist and hands it over one step at a time | `[--name <candidate>]` |

Each command has a how-to page:

- [Start a brand](../use/start-a-brand.md): `brand-creator`, `new`, `status`, `setup`
- [Pick and refine a direction](../use/pick-and-refine-a-direction.md): `round`, `motion`
- [Name your brand](../use/name-your-brand.md): `brand-naming`
- [Make icons and images from your logo](../use/make-icons-and-images.md): `brand-assets`
- [Make the brand book](../use/make-the-brand-book.md): `brand-book`
- [Apply the brand to your product](../use/apply-the-brand-to-your-product.md): `brand-adopt`
- [Launch your brand](../use/launch-your-brand.md): `launch`
- [Check your project](../use/check-your-project.md): `check`, `review`

## Workflows

A workflow runs several agents at once. None starts without your yes: Claude first tells you how many agents, which
models, how big and roughly what it costs. Details: [Agents and workflows](agents-and-workflows.md).

| Command | How it starts | What it does |
| --- | --- | --- |
| `/brand-creator:directions` | Claude, from the `brand-creator` skill, after your yes | One designer per direction, then one judge that advises. Ends before you pick |
| `/brand-creator:review-panel` | Claude, when you type `/brand-creator:review panel`, after your yes | One read-only reviewer per angle, then one judge. Ends with one list for you to approve |
| `/brand-creator:naming` | Claude, from the `brand-naming` skill, after your yes | Name hunters, a screener and a judge. Ends before you pick a name |
| `/brand-creator:adopt` | Claude, when you type `/brand-creator:brand-adopt` and ask to apply the brand, after your yes | One implementer per repository on your branch, then an independent review. Never commits |

## Agents

Agents are helpers that workflows start. They never start on their own, and none can start another agent.

| Agent | Used by | What it does |
| --- | --- | --- |
| `brand-creator:brand-designer` | directions | Builds one direction board in its own folder |
| `brand-creator:brand-judge` | directions, review-panel, naming | Compares options and gives advice you decide on. Read only |
| `brand-creator:brand-reviewer` | review-panel, adopt | Checks work and reports; never edits a file |
| `brand-creator:brand-researcher` | naming | Screens name candidates against public sources, only after you agree to online lookups |
| `brand-creator:brand-inventory` | directions | Lists where your brand appears in your product repositories. Read only |
| `brand-creator:brand-implementer` | adopt | Applies the approved changes to one repository, on your branch |
| `brand-creator:brand-namer` | naming | Finds and filters names offline, with no web tools. Also screens when you have not agreed to online lookups |

## setup

> /brand-creator:setup

| Argument | What it does | Default |
| --- | --- | --- |
| `--force` | Installs again even when the tools are already there | Off |

## new

> /brand-creator:new my-bakery

| Argument | What it does | Default |
| --- | --- | --- |
| `slug` | The project's folder name | `brand-<date>` when you give none or the name is still open |

## round

> /brand-creator:round refine

| Argument | What it does | Default |
| --- | --- | --- |
| `style`, `pick`, `refine` or `motion` | Which kind of board to build. `motion` is a round after you approve the design that tries your logo's move | Worked out from your project |
| text | The question this round should answer | Worked out from your project |

## motion

> brand-creator motion --off "We only show the logo on paper and in the shop window"

Records, once, that nothing moves. This is a `brand-creator` command, not a slash command: Claude runs it when you say
that nothing moves, and you can type it too. Without arguments it says where you stand: `motion: on (signature: <name>)`,
`motion: off (nothing moves: <reason>)` or `motion: not decided`. With `--off` it prints `recorded: nothing moves (<reason>)
in motion/motion.json`.

| Argument | What it does | Default |
| --- | --- | --- |
| `--off "<reason>"` | Records that nothing moves, with your reason in your own words. It never writes over an earlier answer: asked again, it says `already recorded`, and it refuses when your brand moves | — |
| `--json` | Prints the answer as data. Not together with `--off` | Off |

## check

> /brand-creator:check "Old Name"

| Argument | What it does | Default |
| --- | --- | --- |
| an old value or phrase | Also searches the whole project for leftovers of it. Repeat for each one | Off: only the checks run |

## review

> /brand-creator:review panel

| Argument | What it does | Default |
| --- | --- | --- |
| `board`, `book`, `pack` or `all` | What to review | The latest work |
| `panel` | Also offers a review panel. A panel that uses extra agents starts only after you see the size and cost and say yes | Off |

## brand-adopt

> /brand-creator:brand-adopt survey

| Argument | What it does | Default |
| --- | --- | --- |
| `survey` | Reads your repositories, changes nothing, and lists every place your brand belongs | Shows status and the next step when you give none |
| `apply` | Applies the list, only when you ask, on a branch you name | — |
| `review` | Reviews what was applied before anything is committed | — |
| `status` | Shows which rows are done | — |
| a repository label | Which repository | All of them |

## launch

> /brand-creator:launch --name Loaf

| Argument | What it does | Default |
| --- | --- | --- |
| `--name <candidate>` | Which candidate name the checklist is for, when naming screened several | The project's name |

# Commands

Everything brand-creator adds to Claude Code. A command is what you type in the Claude Code chat, starting with `/`.
"You only" means it runs only when you type it; "you or Claude" means Claude can also start it when your request
matches; "Claude only" means it is not in the `/` menu: you ask in your own words and Claude starts it.
[Glossary](glossary.md) explains words like tier, brief, board and round.

You don't need most of this page. To start, say what you want, such as "a logo for my bakery". To pick up again later,
open Claude Code in your project's folder and say "go on with my brand". `/brand-creator:status` shows where you are
and what comes next. There is no command to start a project or to launch: say it in words
([Start a brand](#start-a-brand), [Launch checklist](#launch-checklist)). To review, type `/brand-creator:check --review`.

## Commands and skills

In the Arguments column, words in square brackets are optional, `|` separates choices you pick one of, and words in
angle brackets stand for what you fill in. So `/brand-creator:round` and `/brand-creator:round refine` both work.

| Command | Starts | What it does | Arguments |
| --- | --- | --- | --- |
| `/brand-creator:brand-creator` | you or Claude | Starts or continues a brand project and runs it one decision at a time. It also starts a new project from your words, and hands you the launch checklist when you ask to launch | — |
| `/brand-creator:brand-naming` | Claude only | Finds a name, or screens one you have; screening, not clearance | — |
| `/brand-creator:brand-assets` | Claude only | Makes favicons, app icons, social images and other platform files from a logo you already have | — |
| `/brand-creator:brand-book` | Claude only | Builds, updates, reviews and exports the brand book | — |
| `/brand-creator:setup` | you only | Installs the tools brand-creator needs, after showing what it will download and getting your yes | `[--force]` |
| `/brand-creator:round` | you only | Builds your next board and stops for your decision: the style board first, then directions and refinements (and, in Standard and Full, a motion round), then the boards for your website if your brief lists one | `[style\|pick\|refine\|motion\|site-refs\|site] [what this round should answer]` |
| `/brand-creator:status` | you only | Shows where the project stands and what comes next | — |
| `/brand-creator:check` | you only | Runs every check that applies, and optionally searches for leftovers of old values, checks one page against your brand, or reviews the latest work and gives you one list to approve | `[--page <file-or-folder-page-or-localhost-url>] [<old value or phrase> ...] \| --review [board\|book\|pack\|all] [panel] \| --panel` |
| `/brand-creator:brand-adopt` | you only | Looks at where your brand belongs in your product's code, and changes it only when you ask | `[survey\|apply\|review\|status] [repository label]` |

Rows marked Claude only are not in the `/` menu. Ask for them in your own words, such as "name ideas for my bakery",
and Claude starts them. If Claude does not pick one up, name it: say "use the brand-naming skill", "use the brand-assets
skill" or "use the brand-book skill". Each command has a how-to page:

- [Start a brand](../use/start-a-brand.md): `brand-creator`, `status`, `setup`
- [Pick and refine a direction](../use/pick-and-refine-a-direction.md): `round`, `motion`
- [Get reference pages for your site](../use/get-reference-pages-for-your-site.md): `round site-refs`, `round site`
- [Name your brand](../use/name-your-brand.md): `brand-naming`
- [Make icons and images from your logo](../use/make-icons-and-images.md): `brand-assets`
- [Make the brand book](../use/make-the-brand-book.md): `brand-book`
- [Use your brand kit](../use/use-your-brand-kit.md): `kit`, and `brand-adopt status` for the copies of your kit
- [Apply the brand to your product](../use/apply-the-brand-to-your-product.md): `brand-adopt`, and a redesign
- [Launch your brand](../use/launch-your-brand.md): asking to launch
- [Check your project](../use/check-your-project.md): `check`, `check --review`
- [Check a page against your brand](../use/check-a-page.md): `check --page`

## Workflows

An agent is a separate helper Claude starts for one job, and a workflow runs several agents at once. These four appear in
the `/` menu, but they are meant to be started by brand-creator, not typed: Claude starts each one from the step in the
second column, and only after your yes, once it has told you how many agents, which models, how big and roughly what it
costs. Each agent costs about what the same step would cost in your own session. If you type one yourself, you see its
phases and a "Yes, run it / No" prompt, without that cost estimate. Details: [Agents and workflows](agents-and-workflows.md).

| Workflow | How it starts | What it does |
| --- | --- | --- |
| `/brand-creator:directions` | Claude, from the `brand-creator` skill, after your yes | One designer per direction, then one judge that advises. Ends before you pick |
| `/brand-creator:review-panel` | Claude, when you type `/brand-creator:check --review panel`, after your yes | One read-only reviewer per angle, then one judge. Ends with one list for you to approve |
| `/brand-creator:naming` | Claude, from the `brand-naming` skill, after your yes | Name hunters, a screener and a judge. Ends before you pick a name |
| `/brand-creator:adopt` | Claude, when you type `/brand-creator:brand-adopt` and ask to apply the brand, after your yes | One implementer per repository on your branch, then an independent review. Never commits |

## Agents

Agents are helpers that workflows start, or that Claude starts one at a time after your yes. They never start on their
own, none can start another agent, and you don't need to start one yourself.

| Agent | Used by | What it does |
| --- | --- | --- |
| `brand-creator:brand-designer` | directions | Builds one direction board in its own folder |
| `brand-creator:brand-judge` | directions, review-panel, naming | Compares options and gives advice you decide on. Read only |
| `brand-creator:brand-reviewer` | review-panel, adopt, and a refine, motion or site round after your yes | Checks work and reports; never edits a file. In a site round, it gives the cold review of each version of your first screen |
| `brand-creator:brand-researcher` | naming | Screens name candidates against public sources, only after you agree to online lookups |
| `brand-creator:brand-inventory` | directions | Lists where your brand appears in your product repositories. Read only |
| `brand-creator:brand-implementer` | adopt | Applies the approved changes to one repository, on your branch |
| `brand-creator:brand-namer` | naming | Finds and filters names offline, with no web tools. Also screens when you have not agreed to online lookups |

## setup

> /brand-creator:setup

| Argument | What it does | Default |
| --- | --- | --- |
| `--force` | Installs again even when the tools are already there | Off |

## Start a brand

> A logo and a look for my bakery
>
> Start a brand called Acme

There is no command for this. Say what you need, and Claude starts the process and asks up to three quick questions.

| You say | What it does | Default |
| --- | --- | --- |
| A name for the brand | The project's folder is named from it, such as `./my-bakery/` | `brand-<date>` when you give none or the name is still open |

If a project is already open in the folder, Claude says so and asks whether to pick it up or start a separate one next
to it.

## round

> /brand-creator:round refine
>
> /brand-creator:round site-refs

| Argument | What it does | Default |
| --- | --- | --- |
| `style`, `pick`, `refine`, `motion`, `site-refs` or `site` | Which kind of board to build. `motion` is a round after you approve the design that tries your logo's move. `site-refs` and `site` are the two rounds for your website, below | Worked out from your project |
| text | The question this round should answer | Worked out from your project |

The two rounds for your website need the Standard or Full tier, a site in your brief, and your OK on your brand's
rules: the one list, such as which colours text may sit on, that Claude shows once your logo is approved. You can also
ask for them in your own words.

- **`site-refs`** shows four to six groups of real websites that do the job your visitors come for, each site with what
  to take (how the page is organised) and what to leave (its look and its words). It builds no page of your site, and
  looks online only after your yes.
- **`site`**, after you pick references or say "skip the references", builds two or three versions of the first screen
  of your home page; typed again after your pick, it builds your other pages and marks each choice as a brand rule or an
  example. It never builds or publishes your real site, and marks a choice as a rule only when you decided it.

Steps: [Get reference pages for your site](../use/get-reference-pages-for-your-site.md).

## motion

> brand-creator motion --off "We only show the logo on paper and in the shop window"

Records, once, that nothing moves. In Standard and Full, Claude asks once whether your logo moves, such as a short
animation on your site or in your app: you answer with a motion round, or by saying that nothing moves. This is a
`brand-creator` command, not a slash command: you don't type it in the chat, Claude runs it for you when you say that
nothing moves. Without arguments it says where you stand: `motion: on (signature: <name>)`,
`motion: off (nothing moves: <reason>)` or `motion: not decided`. With `--off` it prints `recorded: nothing moves (<reason>)
in motion/motion.json`.

| Argument | What it does | Default |
| --- | --- | --- |
| `--off "<reason>"` | Records that nothing moves, with your reason in your own words. It never writes over an earlier answer: asked again, it says `already recorded`, and it refuses when your brand moves | — |
| `--json` | Prints the answer as data. Not together with `--off` | Off |

## check

> /brand-creator:check "Old Name"
>
> /brand-creator:check --page pages/index.html
>
> /brand-creator:check --review panel

| Argument | What it does | Default |
| --- | --- | --- |
| `--page <page>` | Checks one page against your brand instead of the project: a page in your project, a page of a site built elsewhere on your computer, or a page your own computer serves while someone works on the site (a local address, such as `http://localhost:3000/`). A page on the internet is refused. For other screen widths, in pixels, ask in words, such as "only 390 and 1440" | Off: the project's checks run |
| an old value or phrase | Also searches the whole project for leftovers of it. Repeat for each one | Off: only the checks run |
| `--review [board\|book\|pack\|all]` | Reviews the latest work, or what you name, against the project's own rules and checks, and gives you one list to approve. Nothing is fixed before you approve | Off: the project's checks run |
| `panel`, after `--review`, or `--panel` | Also offers a review panel. A panel that uses extra agents starts only after you see the size and cost and say yes | Off |

`--review` takes at most one of `board`, `book`, `pack` or `all`, and then `panel`. `--panel` is the same as `--review panel`.
With either, any other word, before or after, is refused with a one-line usage message; it is never searched for as an old
value. A bare `panel` without `--review` is refused too, with "did you mean --review panel?". To search for the word panel
itself, put it in quotes. `--page` and `--review` together are refused: run them one after the other. A refused command runs
nothing.

With `--page`, Claude opens the page at several sizes, from a phone to a wide screen, in light and dark, and lists what
breaks your brand, each with its fix, plus warnings about what makes the page look like any template. It never changes
your page, sends nothing online and starts no extra agents; [Page check](page-check.md) has every rule.

## kit

> Write the brand kit

The brand kit is your brand in one folder, and a copy of it goes into your website's or app's code. This is a
`brand-creator` command, not a slash command: you ask in your own words, and Claude runs it. Claude offers the kit when
you approve your brand book; it needs that approved book and your design tokens (your colours, fonts and sizes as files
a program reads). Any tier can have a kit, but putting it into your product needs the Full tier. Steps:
[Use your brand kit](../use/use-your-brand-kit.md).

| You say | Claude runs | What it does | What it never does |
| --- | --- | --- | --- |
| "Write the brand kit" | `kit build` | Shows what it would write. After your go, it writes the kit into a hidden folder of your project, `.claude/skills/<your brand>-brand/`. Asked again after your brand changed, it writes the next version | Writes nothing before your go, and nothing outside your project. Never overwrites the files that are yours, and never deletes a file |
| "Check the kit" | `kit check` | Says whether the kit is whole: the made-for-you files are as Claude built them, every link inside it works, your own pages are filled in with their rules and examples marked, and the version numbers agree. If your brand changed since the last build, it says "not verified" | Changes nothing in the kit |
| "Is my website's copy of the kit current?" | `kit status` | Compares the copy in each of your product's code folders with your kit, file by file and exactly, and says `current`, `not installed` or `not current`, with the list of files to copy | Writes and copies nothing, in your product or your project: the kit goes in with `/brand-creator:brand-adopt`. It refuses your home folder itself, Claude's own settings folder (`~/.claude`) and your brand project |
| "Test my brand kit" | a test build, then the page check | Builds a first screen and one more part of a page from the kit alone, in a temporary folder outside your project, then checks both against your brand | Starts only when you ask, and uses no extra agents |

## brand-adopt

> /brand-creator:brand-adopt survey

Puts your brand into your product's repository: the folder on your computer that holds your website's or app's code.
It needs the Full tier, changes your code only after you ask, on a branch you name, and never saves the changes into
your code's history (commit), joins them into your main version (merge) or sends them online (push) unless you ask for
each one.

| Argument | What it does | Default |
| --- | --- | --- |
| `survey` | Reads your repositories, changes nothing, and lists every place your brand belongs | Shows status and the next step when you give none |
| `apply` | Applies the list, only when you ask, on a branch you name | — |
| `review` | Reviews what was applied before anything is committed | — |
| `status` | Counts the places done, doing and to do, and, with your brand kit on the list, says whether each repository's copy of it is `current`, `not installed` or `not current`. It changes nothing | — |
| a repository label | Which repository, by the short name it got in the survey | All of them |

**A redesign.** Tell Claude it's a redesign before you ask to apply, and Claude keeps a redesign record: it reads your
code before and after the change, without changing it, and notes what your site relies on that doesn't show on screen,
such as where links go and the names of form fields. The review fails anything gone that you gave no reason for, and
only you decide that something may go. Steps: [Apply the brand to your product](../use/apply-the-brand-to-your-product.md).

## Launch checklist

> Help me launch

There is no command for this. Ask to launch, or for the launch checklist, and Claude writes `LAUNCH.md` and hands it over
one step at a time. You do each step; Claude buys, files and registers nothing.

| You say | What it does | Default |
| --- | --- | --- |
| A candidate name, such as "the launch checklist for Loaf" | Which candidate name the checklist is for, when naming screened several | The project's name |

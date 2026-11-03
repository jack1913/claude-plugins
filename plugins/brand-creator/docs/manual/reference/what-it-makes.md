# What it makes

What each step of a brand project produces, in more detail. For a short list by task, see the
[how-to pages](../README.md#do-something).

Every step is a `brand-creator` command that the skills run for you. `brand-creator --help` lists them all.
A synthetic worked brand, Acme, shows a finished project: `skills/brand-creator/references/examples/acme/` in the plugin.

## Boards and rounds

Round pages are built from a template, checked by `board-lint` and photographed by `shot` at 1440 and 390 pixels wide, in
light and dark. Approved rounds are frozen with `freeze` into `history/`, with a checksum manifest that `check` verifies.

In Standard and Full, a motion round adds one more kind of board after you approve the design: three variants of your
logo's move, each with its own folder (a page, a proof and its stills) next to the board. `board-lint` checks that each
variant has all three, that the strip on the board is the very picture taken from that page, and that the proof line says
what the proof found.

## Checks

Each check writes a report to `assets/_checks/`. `check` reads every report that exists, and a check that cannot run is
"not verified", never a pass.

| Command | What it proves |
| --- | --- |
| `contrast`, `contrast --cvd` | Text, UI and mark contrast in light and dark. Colours stay distinguishable under protan, deutan and tritan colour-blindness simulation |
| `logo-sheet`, `logo-sheet --guides` | The mark at real sizes, each size from its own drawing when you have one per size. Baseline, cap line and x-height measured on the ink |
| `downscale` | What survives when one master is shrunk to the sizes systems show: accent pixels, bounding box and the solid-square rule |
| `states-check` | State sets (idle, active, error) differ in greyscale and in silhouette |
| `family-check` | Family modes: shared glyphs equal the family's sources, and tile shares agree across products (`FAMILY.md`) |
| `fontcheck`, `fonts` | Glyph coverage for the brand's languages, a licence hint, and which font Chromium really used |
| `outline-glyphs` | Type-based marks as paths with no live text |
| `shot --motion` | The mark's motion is stepped through, not waited for: no layout shift, the animated parts stay on a phone screen (360 and 390 pixels wide), the rest frame equals the still to the pixel, and pixel marks move in whole pixels. Reduced motion shows the still. Motion a script draws frame by frame (`requestAnimationFrame`) cannot be stepped through, so its phone-screen check says "not verified". One report per proof file, and a change to a file the page loads (such as `tokens.css`) makes it stale |
| `frames` | Stills of the mark along its motion, a strip of them and the reduced-motion still, written into `motion/frames/` for the brand book. The stills of a variant in a motion round stay next to that variant |
| `snapshot`, `verify-idempotent`, `staleness`, `specs-due` | Byte-identity proofs, two-run idempotence, stale packs, and platform sizes due for a recheck |

The thresholds are yours, kept in `qa/rules.json`. The plugin's numbers are proposals and say so.

## Tokens

`tokens` turns your colour, type and motion tokens into files for code, in `assets/tokens/`: CSS variables, a JSON copy,
Swift colours with an asset catalogue, and Android colours. Durations and easing curves reach the apps too: Swift gets
`BrandMotion`, and Android gets `motion.xml` and one interpolator per curve. Each file is read back and compared with your
tokens before the build passes. A file your tokens no longer produce, like the colour set of a role you removed, is
moved to `removed-<date>/`.

`motion/motion.json` keeps your answer on motion. When something moves, it says how: the signature move, the moving
parts, a timeline written in your duration and curve tokens, and the motion rules. When nothing moves, it says why, in your
words. In Standard and Full the file always exists once you have answered, and `check` fails without it after you approve
the system rules. `brand-creator motion` shows the answer, and `brand-creator motion --off "<your reason>"` records that
nothing moves. BRAND.md, DESIGN.md, the brand's own skill and the brand book repeat it.

## Website references and reference pages (Standard and Full)

This part is optional. It runs only in the Standard and Full tiers (`/brand-creator:status` shows yours), and only when
your brief lists a site. Claude runs every tool here for you. A name in brackets, such as `capture`, is the tool's own,
so you recognise it when a message names it. Everything lands in your brand project, the folder that holds
`BRAND-STATE.md`. The steps are in [Get reference pages for your site](../use/get-reference-pages-for-your-site.md).

Your brief is the notes Claude wrote from your answers at the start, in `brief/BRIEF.md`. Claude looks for your site on
one line only, "Required surfaces": a site named anywhere else in the brief does not count. The line needs a word for a
site in English or Polish: site, website, microsite, web page, landing page, www, strona or witryna, in any of their
forms. In another language, add the word `site` to that line. A line still in brackets, as a blank brief has it, does
not count.

- **Pictures of your pages** (`capture`). Claude photographs each page it builds for your site: the first screen (what a
  visitor sees before scrolling) 1440 pixels wide, like a desktop, and 390, like a phone, in light and dark, and the
  whole page at 1440. The pictures go in a `shots/` folder beside the page, with `capture.json`: a list of the files the
  page loaded and of anything that went wrong. A page in an earlier round, or in `history/` where approved rounds are
  kept, is refused, because those are locked.
- **Pictures of real sites** (`capture --url`). For the references, Claude photographs each site into
  `research/site-refs/<name>/`: the first screen at both widths, the whole page and two small thumbnails. It is the
  only tool here that goes online, and only when your answer to the online question allows it: research online, or
  only the sites you gave. A site that does not load leaves nothing behind. Claude never opens a page behind a login.
- **The references board** is an ordinary round: one board, and your answer. Its check (`board-lint`) makes sure that
  your tier is Standard or Full, your brief lists a site, your brand's rules are approved and your answer to the online
  question is recorded. It also wants four to six groups of three or more sites, each site with a link, a screenshot,
  what to take and what to leave. A screenshot that matches none of Claude's pictures gets a warning, so you can tell a
  picture you sent from one Claude took. Screenshots you send are kept in `research/site-refs/owner/`.
- **Your category's habits.** `research/site-cliches.md` lists what sites like yours do by reflex. Every first screen is
  tested against it. Notes with each site's address and the date it was read are in `research/<date>-site-refs.md`.
- **The site round** has two stages, each on its own board. First come two or three versions of your home page's first
  screen, each in its own folder: the page, its `shots/` and its `cold-review.md`. Then come your other pages, built
  from the first screen you picked. The page check leaves one report per page in `assets/_checks/page-check/`. The
  board's check makes sure that the pictures show each page as it is now, that the cold review was made from those very
  pictures, that every version was checked against your brand's rules, and that the pages board comes after a first
  screen you picked.
- **The cold review** gives its verdict, "ship" or "fix", first, before any reason. It reads only the version's four
  pictures, your brief and `FACTS.md` (your list of facts): never the board, the references or Claude's reasons. By
  default Claude writes it in the same conversation, so it is not blind, and the board says "by in-thread". A separate
  helper agent writes it only after you agree to how many, which model and the cost, and the board then says "by
  agent". Each review is kept in `cold-review.md` beside its version.
- **Layout references.** A layout reference is a short recipe for how a page is organised for one visitor job, such as
  "understand how a service will run for them before handing it something important". It is a starting point, never a
  template. The plugin keeps them in `skills/brand-creator/references/page-layouts.json`, keyed to what the visitor
  came to do. Every page you build records the one it used, or `own:` and a word when none fits.
- **Rules and examples.** On the pages board every choice is tagged: a rule (you decided it, and every page keeps it)
  or an example (one way of doing it, free to change). A rule says where you decided it, and the board's check looks
  for those words in your decision files (`DECISIONS.md`, `decisions/` and `BRAND-STATE.md`).
- **The approved pages** (`site approve`). When you approve the pages, Claude copies them into `site/<page>/` and writes
  `site/site.json`: the pages, the layout each used, a fingerprint of each that changes when the page does, and the
  choices with their tags. The pages need nothing from the internet. If `site/` already holds approved pages and you
  say replace them, the old ones move to a `removed-<date>` folder, and nothing is deleted. `/brand-creator:check` reads
  the pages back: one that changed since you approved it, or fails its page check, fails; one whose page check or
  pictures are missing or out of date is "not verified".
- In Standard and Full the brand book has an optional Site chapter that shows the approved pages and the tag on each
  choice. Ask for it when you make the book.

## Web, social and profiles

- `emit web`: favicons drawn per size (the browser tab gets your small drawing), PWA icons and a head snippet.
- `emit social`: a social card, plus GitHub and README header images when the brief or inventory lists a code repository.
- `emit profiles`: in every tier, a circle-safe avatar. Standard and Full add banner images for LinkedIn, X, YouTube,
  Facebook and Instagram, each inside the platform's safe area.

Cards and banners show your name as you drew it (your lockup, or your wordmark next to the logo). Without either, the
name is typed in a plain system font, and the report tells you so. Pixel-art logos are scaled by whole numbers, so every
pixel stays square, and the line under the name gets square ends to match.

Several products with their own logos, sharing one look? Each logo gets its own files: favicons, cards and headers. Your
repository also gets images that show all of them side by side.

Sizes the project has not read at the platform's own page are labelled `UNVERIFIED, recheck`, and `check` fails a file
that lost the label.

## Platform packs (Full tier)

`emit apple` (an Icon Composer `.icon`, compiled per platform, legacy sets, and visionOS, watchOS and tvOS when your
product targets them; macOS with Xcode only), `windows`, `linux`, `tray`, `tauri`, `wallet`, `developer`, `android`
(adaptive icon with a monochrome layer, Play icon and feature graphic; refused when the mark leaves the 66 dp safe
zone), `chrome-ext` and `msix`. The `brand-assets` skill runs them from an approved mark. Without a project it writes
into `./brand-assets/`.

## The brand book

`book` builds one self-contained `book.html` (no script, no network, light and dark) from your tokens, the files the
emitters wrote, the state, the facts, the check reports and your chapter text. In Quick it is a short guide: idea, mark,
colour, files, changing the brand. Counts and colour ratios are computed, so they cannot drift. `book-lint` checks it.
`book-pdf` exports an RGB proof labelled "RGB, not print-ready". A hand-drawn mark has a hand-written book that `patch`
edits with counted replacements.

In Standard and Full the motion chapter is always in the book once motion is decided. When nothing moves, it says so and
gives your reason, with no replay. When your brand moves, it shows how, from `motion/motion.json`: the signature move, the
parts, the timeline with each duration and curve by name and value, a small drawing of every curve, and the rules. It also replays
the motion. Run `frames motion/proof.json --count 25` first, and the book plays each page's motion as a short animation.
"Replay" starts it again and "4× slower" plays it slowly, from a click or the keyboard, with no script. With reduced
motion switched on, the chapter shows the still and nothing moves. In print it shows the stills side by side with
their times. If the stills are missing, older than the page or too few to look smooth, `book` says so and names the
command to run. A book built before the stills existed fails its check until you build it again.

## The brand kit

Your brand in one folder, so that your website's or app's code can carry a copy and whoever builds the next page finds
everything in one place. Any tier. Claude offers it when you approve your brand book, and writes nothing without your
yes. The steps are in [Use your brand kit](../use/use-your-brand-kit.md).

- **Where it is:** `.claude/skills/<your brand>-brand/` in your brand project. Finder hides a folder whose name starts
  with a dot: on a Mac, press Command-Shift-period in Finder to see it. The kit is also your brand's skill (the
  instructions Claude reads before it works on your brand), so it takes the place of the small brand skill.
- **Made for you, never edited by hand:** copies of your design tokens (your colours, fonts and sizes, written so a
  program can read them), your logo files, your open-licence fonts with their licence text (OFL: a licence that lets
  you share a font with your product), the masters you approved (the files in `assets/masters/` of your brand project,
  such as an ad or a deck template with its pictures, PDFs and fonts), and your decision on motion; your rules and facts,
  without contact details;
  ready-made bits of code for your fonts, your logo in light and dark, and text on each background colour you named;
  and your approved reference pages, each with a note on its layout and its choices. A reference page goes in only when
  it passes its page check and its pictures are up to date.
- **Yours:** `voice.md`, `visual.md` and `golden-rules.md` (how your brand sounds, how it looks beyond the colours, and
  the few rules every piece keeps), `recipes/web-page.md` (the steps for building a web page in your brand), and
  `EXTENDING.md` (how to add to the kit). Claude writes each once, never over it, and drafts the first three with you.
  A recipe or file you add yourself is yours too and travels with the kit.
- **Its version,** such as 1.3: your brand book's edition, then a build number that goes up by one when a made-for-you
  file changed or a file of yours was added, changed or taken away. A copy in your product shows its version, but it is judged by comparing
  every file exactly, so a copy can be out of date at the same version.
- **The commands, which Claude runs when you ask:** `kit build` writes the kit, after showing you the plan. `kit check`
  proves it whole: no made-for-you file edited by hand, and no file added among them; every link leads to a file inside
  the kit; every note in double square brackets is replaced; in `visual.md`, `golden-rules.md`, the recipes, any note of
  your own written in Markdown and the notes on each reference page, every list line is tagged as a rule or an example, and every size, colour or ratio names
  its source (a token, a rule or `[example]`); the version matches your approved book's edition; and each reference page
  is still the one you approved, with a passing, up-to-date page check. After a brand change it says "not verified"
  until you build again. `kit status` only reads, and says whether the copy in each product repository (the folder on
  your computer that holds your website's or app's code) is `current`, `not installed` or `not current`.
- **In your product:** `/brand-creator:brand-adopt` puts the kit into a product repository, on the Full tier: one
  repository at a time, never into a folder all your projects share. A review checks that the copy is exactly your kit.

## Print, press kit and posts (Standard and Full)

- `emit print`: a business card, letterhead and envelope (EU, US or JP sizes, bleed that is the printer's to confirm,
  crop marks, text outlined) and an HTML e-mail signature. `print-check` reads the files back.
- `emit presskit`: a zip of logos, tokens and the book PDF.
- `emit social --posts`: carousel, square and educational posts from your facts, with a pre-publication checklist for
  regulated professions.

## Naming

`brand-creator names <name>...` screens candidates against domain registries (RDAP, whois, DNS) and, for software brands
only, npm, GitHub, Docker Hub, PyPI, crates.io and Homebrew. It lists the services first and needs your yes. Trademark
offices are never queried: the memo carries search links you run yourself. The `brand-naming` skill grows and filters
candidates, checks meaning in each audience language and writes a go, go-with-conditions or no verdict.

## Adoption and launch

Adoption is for the Full tier. The launch checklist is for any tier when you ask, and Full plans it by default.

- `adoption survey` reads your product repositories read only for every place the old brand shows, and writes
  `ADOPTION.md` as numbered rows.
- `check --cascade "<old value>"` (the leftover search) finds leftovers of a changed rule, token or colour across the project.
- When you approve the finished files, you may opt into `BRAND.md` and `DESIGN.md` for other agents, and a small
  per-brand skill in your project's `.claude/skills/`.
- `launch-todo` writes `LAUNCH.md`: trademark first, then domains and handles with the date each was checked, renames and
  the print hand-off. It only reads local files.

## Connectors

None is needed, and no MCP configuration ships. A connected design tool is read only when you point at a file, and
written only when you ask. See [CONNECTORS.md](../../../CONNECTORS.md).

## Related

- [Glossary](glossary.md)
- [Commands](commands.md)

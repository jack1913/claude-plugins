# Changelog

All notable changes are listed here, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[SemVer](https://semver.org/). The plugin version is in `.claude-plugin/plugin.json`. How 0.1.0 was built, stage by
stage, and why, is in the [archive](docs/archive/README.md).

## [Unreleased]

This release adds checks that can warn on a project you already have. A warning changes neither a result nor an exit
code, and nothing that passed before fails because of a warning. Settle these now, because the first two groups become
failures in the next release:

- The reflex line of each direction on a pick board (`board-lint`): a line that is not in the format, a hit that names
  no known pattern, an argument that shares no word with `FACTS.md` or the brief, a direction with no list from the
  judge when the judge ran, and a pattern the judge saw that the line neither hits nor names as a near miss. Two hits in
  one direction, and one hit that every direction shares, fail already.
- The colours that text sits on (`contrast`): a project whose tokens list no grounds, grounds the owner has not named,
  a ground with no colour for one of its text, action, text-on-action, focus ring or border roles, a role under its
  contrast floor, and, with `--cvd`, an action or focus ring too close to its ground in colour-blind simulation (those
  rows check colour distance, not a contrast floor). Ask the owner which colours text sits on and record the date and
  their words; the model never guesses.

Two more only ever warn and are not due to fail: `check` lists the values in `tokens/primitives.tokens.json` that are
still the starter's proposal once the system rules are approved (keep one under `starter-kept`, or change it), and
`board-lint` notes directions that look alike in colour and motion variants that try the same move.

One change touches what already passes: the `board-lint` report of a pick board now lists `FACTS.md`,
`brief/BRIEF.md` and `research/cliches.md` as inputs, so editing one of them makes that report stale and `check` says
it is not verified until `board-lint` runs again. The `tools/finish.sh` of a new project (`templates/finish.sh.tpl`)
lints the board of the latest round again before `check`, so an edit of the facts or the brief is picked up; a
`tools/finish.sh` you copied earlier has no such step, so add the block at its end, before `staleness --write`, or run
`board-lint` yourself.

### Added

- `page-check` opens one page at several widths (360, 390, 768, 1024, 1440 and 1920 px unless `qa/rules.json` or
  `--widths` says otherwise) in the light and the dark colour scheme, and reports how it loads: a page or console
  error, a file of its own that does not load, or a request to another website fails that view's row
  (`page:load:<width>-<scheme>`). Every request to another website is stopped, a redirect to one and a WebSocket the
  page opens included, so the check runs offline (one exception: a WebSocket opened inside a worker is not stopped; a
  page's own WebSocket to the machine it is served from, a dev server's hot reload, goes through); a page that sends
  the browser to another website is not measured, and its row fails. Name a page
  of the project, `--from DIR <page>` for a built site anywhere (the folder is copied into the data folder and only
  read; `.git`, `node_modules` and symlinks are left out, more than 5000 files or 200 MB is refused, and each check keeps
  its copy until you delete it: the manual says where), or `--url`
  for a page already served on this machine (`localhost`, `127.0.0.1` or `[::1]`, written like that; any other host,
  `127.1` included, is refused, and on such a page a file that comes from another website is a warning). One report per
  page, in `assets/_checks/page-check/`. `qa/rules.json` accepts a `page` section with `widths`, `display_min_px`,
  `clear_space` and `rules`; a value of the wrong type, or a width outside 200 to 4000, is refused.
- `board-lint` checks that the argument of a reflex hit is the brand's own. The argument has to share a word with
  `FACTS.md` or `brief/BRIEF.md` (`reflex-grounded`; words of four letters or more, in any language, taken only from
  what the owner wrote, not from the templates: the brand's name in the title line counts for nothing); a hit argued
  with nothing of the brand warns, asking for the fact, place or craft that earns it, and a project with neither file
  filled in is reported as not verified. When the judge ran, each direction also carries the judge's list of the
  patterns it saw beside its reflex line (`data-field="reflex-seen"`; the board templates have the line in a comment
  to uncomment), and `board-lint` warns about a direction without it, or with a list that names no pattern and does
  not say "none seen" (`reflex-seen`), and about a pattern on the list that the reflex line neither hits nor names as
  a near miss (`reflex-unargued`, one warning per pattern). All of these only warn in this release and become
  failures in the next one. The report now lists `FACTS.md` and `brief/BRIEF.md`, so a changed fact makes the lint
  stale.
- `board-lint` warns when two directions of a pick board look alike in colour (`directions:divergence`). It reads the
  paper, ink and accent each direction carries in its `style` attribute (`--d-paper`, `--d-ink`, `--d-accent`, as
  `#rgb` or `#rrggbb`) and names every pair whose paper and ink are both within 0.04, and whose accents are within
  0.06, of each other (distance in OKLab). A board that passes names the smallest distance of each colour; with fewer
  than two readable directions the row says it did not measure. The two limits are a practice proposal, said in the
  row, and the row only warns: it does not become a failure.
- `board-lint` warns when two variants of a motion board try the same move (`motion:timelines`). It reads the length and
  the number of animations that `shot --motion` found for each variant and names every pair that runs the same number of
  animations with lengths within 5 % of the longer one, or within 20 ms, of each other: three variants should try three
  moves. A variant whose motion report is missing or out of date is not compared (the proof row says why), and the row
  then reports instead of passing. The two limits are a practice proposal, said in the row, and the row only warns: it
  does not become a failure.
- `brand-creator shot --out DIR` can now write the shots into the project's own `specimens/` folder, at any depth (for
  example `--out specimens/hero`), so page shots you want to keep can sit beside the brand. Any other folder inside the
  project is still refused (exit 2: `--out <DIR> must be outside the project, or under specimens/`, with the folder you
  typed in place of `<DIR>`); a folder outside the project works as before.
- A motion proof can now check how a component answers its states, not only how a mark moves. A `component` case in the proof
  names a page, the component's element and the line of the motion rules it proves (`rule`), and `brand-creator shot
  --motion` hovers it and presses it (and focuses it with the keyboard when the case lists `focus-visible` in `states`),
  at 390 and 1440 px. It fails when the element, or anything after it, moves or resizes by more than half a pixel at any
  point of entering or leaving the state (a lift or a press done with `transform` is fine; padding, a border or a size
  change is not), when a duration or an easing of the state change is not one of the brand's motion tokens, when the
  element or anything inside it animates under reduced motion, or when the box is not back where it was once the state is
  left. A component that another element covers, that is hidden at a width or that cannot take focus fails with the
  reason. A width it could not be put into under reduced motion is never skipped in silence: the reduced-motion row names
  the width and why, and is not verified (it fails instead when an animation was found at another width). Without built
  tokens the token row says it is not verified.
- The starter tokens carry layout slots, as proposals until the owner approves the system rules: spacing steps 1 to 8
  (4 to 64 px), corner radius (small, medium, large, pill), the content width and the gutter, four breakpoints, and line
  height and letter spacing as plain numbers (letter spacing in em). They are built into `tokens.css` and `tokens.json` like
  the other tokens, and the system-rules step offers one layout rule for a brand with a site or an app.
- The starter tokens carry the two colours every interface needs besides the accent: the text on the accent
  (`color.on-accent`) and the focus ring (`color.focus`), in light and dark, each with its contrast pair (text on the
  accent at 4.5:1, the focus ring against the ground at 3:1). They also list, as a proposal, which colours text sits on:
  `color.bg`, with the colour of its text, its action, the text on the action, its focus ring and its border, under
  `grounds` in `tokens/semantic.light.tokens.json`. The line that records the owner naming the grounds stays empty until
  the owner does; nothing is guessed. `brand-creator tokens` checks that block when it is there and writes it into `tokens.json`
  (`grounds`) with every colour resolved in light and dark. A block of the wrong shape fails the build and writes
  nothing; a role that names no colour token is a warning. A project without the block builds exactly as before.
- `brand-creator contrast` checks the colours that text sits on. For each ground listed under `grounds` it wants a colour for
  the text, the action (a button or link), the text on the action, the focus ring and the border, in light and dark, and
  holds them to their floor: text 4.5:1 on the ground, the action, the focus ring and the border 3:1 against it, the text
  on the action 4.5:1. With `--cvd` the action and the focus ring must also stay tellable apart from the ground for
  colour-blind viewers. It warns, too, until the owner has named the grounds (a date and their words in
  `named_by_owner`; the starter's proposal has none), and says to ask the owner and never to guess. All of these are
  warnings in this release and do not change the result or the exit code; they become failures in the next release.
- Once the system rules are approved, `check` warns about every colour, size, spacing or motion value in
  `tokens/primitives.tokens.json` that is still the starter's proposal, and lists them. Keep a value by listing its path
  under `starter-kept` in the primitives, with the date and the owner's words, or change it. It only warns; it never
  fails the check.
- `DESIGN.md`, `BRAND.md` and the brand's applied skill now carry the grounds that text sits on, when the tokens list
  them. `DESIGN.md` gets a component for the action on each ground (`action-on-<ground>`, with a `-dark` twin), pairing
  the action colour with the text on it. `BRAND.md` (under Visual) and the applied skill (under Colour) get a Grounds
  table with the text, action, text on the action, focus ring and border of each ground, in light and dark. A colour the
  tokens do not give is left out and shown as "missing: ask the owner", never filled in, and the files say whether the
  owner named the grounds or they are still a proposal. An action whose text is under 4.5:1 on it gets no component in
  `DESIGN.md` (the format's own check fails a component like that, while `contrast` only warns about it in this release):
  `DESIGN.md` names the ground and the pair instead, and the component comes back once the colours pass. A project with
  no grounds gets the same files as before. Run `adapters` and `applied-skill` again to update files you already have.
- `page-check` now checks the colours of a page against the brand, in the light and the dark theme separately. Every
  colour the page paints (text, backgrounds, borders, outlines, underlines, and the fill and stroke of an inline SVG)
  has to be a colour of the theme in the tokens: an opaque colour an opaque one, a see-through colour a see-through one
  (`page:colours:<theme>`). The row names up to six that are not, with where they are, the nearest brand colour and how
  far off it is, so a light background left in the dark theme fails the dark row only. Each text colour on the colour
  behind it (`page:pairs:<theme>`) must be a declared pair, or measure at least 4.5:1 (3:1 for large text); a pair that
  is not declared fails under that and warns when it passes ("declare them in pairs"), and text over an image or a
  gradient is reported as not verified.
- `page-check` now checks the motion and the claims of a page. Every duration and easing the page declares or runs
  (transitions, animations and a script's animations, `::before` and `::after` included) has to be one of the brand's
  motion tokens, and so has the motion a style sheet declares for a state (`:hover`, `:focus`, `:active` and the like,
  read from the rule without hovering, `var()` resolved, nested rules, a declaration written after a nested rule, `@media` and `@layer` included): a duration that
  equals no token, or an easing that no curve token equals, fails `page:motion` (`ease` and `linear` count only when a
  token holds their curve), and a page that moves while the brand has no motion tokens fails and says so. A style sheet
  the browser would not let it read is reported as not verified. Numbers and status words on the page have to come from
  `FACTS.md`: outside a labelled sample, a number no fact holds (a single digit next to `%`, a currency sign or code
  counts, `9 €` and `PLN 5` too), or a status word (English and Polish, such as "available" or "wkrótce") no fact
  contains, fails `page:claims`. Mark sample content with `data-sample="<what it
  stands for>"`: it is not a claim, it is listed in `page:samples` as what to replace before publishing, and the
  report keeps the list as `samples`; a `data-sample` with no label fails. A page in another language than English or
  Polish gets a warning that its status words are not verified (its numbers are still checked).
- `page-check` reads numbers on a page more the way people write them. A date written with dots, such as "15.11.2026"
  or "30.10", is its numbers, as "2026-11-15" is: the fact "premiera 2026-11-15" backs "Premiera 15.11.2026", and
  "Wypłata 30.10" needs 30 and 10. Digits with spaces between thousands, such as "13 205,20 zł", are one number, but
  "In 2026 200 tools" is the numbers 2026 and 200. A year after a copyright sign or the word ("© 2026", "Copyright
  2024–2026") is not a claim, and neither is the code of an error page (next item). A phone number, a postal code and a street number are still claims and need a fact or a sample label.
- `page-check` knows an error page and a date written with a month name. A page is an error page when its file is
  named after the code (`404.html`, `500.html`), or when its title or main heading holds a code from 400 to 599 as the
  only number in it (a single digit counts as one), with no "+" before or after it, and the same text holds an error
  word of the page's language, such as "Błąd", "Nie znaleziono" or "nie istnieje" in Polish and "Error", "Not found"
  or "Gone" in English. A heading such as "Ponad 400 projektów", "500+ firm nam ufa" or "5 lat, 500 klientów" is a
  count and exempts nothing, and a page in another language, or one that sets no language, is an error page by its file
  name only. The code is then no claim anywhere on the page, so a small "Błąd 404" label above the heading is not one.
  A date written with a month name is one date in a Polish or English page, backed like a dotted date: "21 października
  2026", "21 października", "Październik 2026", "October 21, 2026", "October 21,2026", "21 October 2026", "October
  2026"; a number after a month name that is not a day stays its own claim ("March 15% of users" holds "15%"). A dotted "30.10" is a date only when the
  day and the month have two digits each, or a year follows ("1.5.2026r."); "12.5", "2.10" and "10.1" are plain
  numbers, on the page and in `FACTS.md`.
- `page-check` now checks the brand mark on a page. Put `data-brand-mark` on the mark's `<img>` or inline `<svg>` (the
  value may name the logo file, `data-brand-mark="assets/logo/mark.svg"`); an image whose file name is `logo`, alone or
  followed by `-`, `_` or `@` and more (`logo.svg`, `logo@2x.png`, `logo.jpg`; `partner-logo.svg` is not), an `.svg` file
  named `mark` or `wordmark` the same way (`mark-dark.svg`, `wordmark.svg`; `bookmark.svg`, `mark.jpg` and `Mark.png` are
  not, so a team member's photo is never taken for the logo), and any image that is byte for byte a file of `assets/logo/`, is taken for the mark too. The
  mark has to be a logo file of the project (`page:mark-file`: the same bytes, or for an inline SVG the same drawing,
  whatever the order of its attributes, its spaces, its title or the size and label it is given); it has to be the
  drawing your size bands name for the height it is shown at, or that drawing's `-dark.svg` twin (`page:mark-band`);
  and nothing may stand nearer to it than a quarter of its height (`page:mark-clear-space`; `page.clear_space` in
  `qa/rules.json` changes the share). A page with no mark gets an info row that says what counts as one, and an inline
  `<svg>` that draws through `<use>` is reported as not verified, not failed.
- `page-check` now checks the fonts of a page (`page:fonts`). The family each text is set in has to be one that a font
  token names; a generic family such as `monospace` counts only when a token's list writes it, so a page that sets no
  font and falls back to the browser's default fails. A named family must also be what the browser really drew: a font
  file that does not load, a family the page never declares and this machine does not have, or a face that covers none
  of the text fails (also when its stack fell to another web font of the page), and a face that lacks only a few
  characters of the text warns with the glyph counts. Text set inline in another font (`code` in a paragraph) is not
  charged to the text around it, and a system face such as Roboto that the page does not declare and this machine does
  not have is reported as not verified instead of passing. When the brand has a display face (a `font.display` token),
  no text set in it may be smaller than `page.display_min_px` in `qa/rules.json` (`page:display-size`); 20 px is a
  proposal until you set it, and the row says so. A brand with no display face gets an info row instead, and so does
  one whose display face is also its body face.
- `page-check` can hold a page to your own brand rules. List them in `qa/rules.json` under `page.rules`: one mark per
  screen (`max-marks-per-view`), a button says at most three words (`max-words-per-control`, for buttons, inputs of type
  submit, button or reset, and anything a `selector` you give matches), or a number of words around an accent
  (`words-under-accent`, with `min`, `max` or both). Each rule carries a `g4` text and is tied to the system rule you
  approved: the page fails (`page:rule:<id>`) only once a "(rule)" line holding those words is in `BRAND-STATE.md`
  and you have approved the system rules; until then a page that breaks the rule only gets a warning that says the rule
  is not an approved system rule yet. The `g4` text has to be the whole "(rule)" line or at least two content words of it, written as whole words:
  one word such as `mark`, or `rule`, ties nothing, and the row says the text is too short. A word is what Unicode word segmentation counts, in the page's language: a
  hyphenated compound is two and an arrow is none. A selector the browser cannot read fails its row. An unknown kind or
  key, a missing `g4` or a repeated `id` is refused before the page is opened.
- `page-check` warns about generic patterns that make a page read as a template, in English and Polish (`tell:<name>`
  rows): a small label in capitals over a heading (an eyebrow), an arrow glued to a link or button label, a line of
  items joined by middle dots (a bulleted list is not one), a stock label such as "Learn more" or "Dowiedz się więcej"
  on the hero's second action, more than 45 words in the hero's first screen, a mock-up built from many styled boxes
  with no picture bigger than an icon (a table is not one, status badges or chips in its cells included, unless a styled
  header or footer sits beside it; a list is not one unless it is the box or most of it, counting each item only as far as it lies in the box, so a panel
  with its own header or footer beside a list is, and so is a carousel whose items run on past the box; a page, or a
  band of it, with headings is not one),
  and a row of three equal tiles. Each warning names where the pattern is and at which widths; none of
  them ever fails a page. A page in another language is reported as not verified for the stock labels, and a page that
  follows the stock order of a product page (hero, three tiles, FAQ, closing band) gets a note. To hold your pages to
  one of the patterns, add a rule of kind `tell` to `page.rules` (`{"id": "no-eyebrow", "kind": "tell", "tell":
  "eyebrow", "g4": "no eyebrow over a heading"}`): it is then tied to your approved system rule like the other page
  rules, and a name that is not one of the patterns is refused before the page is opened. The social post template
  that ships with the plugin has a small capital label above its headline; that counts as an eyebrow, and it is
  reported, not changed.
- `/brand-creator:check` takes `--page` to check one page against your brand instead of the whole project: a page in
  your project, a page of a site built elsewhere on your computer, or a page your computer serves (`localhost`,
  `127.0.0.1` or `[::1]`; a page on another website is refused). Claude reports the failing rows with their fix, the
  generic patterns as warnings, and the labelled samples as your list of what to replace before you publish. A new
  how-to, "Check a page against your brand", walks through it, including how to turn a warning into one of your brand
  rules; the commands page, the check page and the troubleshooting page link to it. The adoption step now says to run
  the page check on a product's pages once they are built.
- `state` knows two more gates for the site work, G4w (website references) and G4p (the site's reference pages), and the
  `site_research` answer (online research for website references): `auto` until you are asked, then `online`,
  `links-only` or `none`; `state --set` refuses any other value and writes nothing. A project made before this update
  gets the two gates the first time you record them.
- `brand-creator capture <page>` takes stills of a page of your project: the first screen at 1440 and 390 px wide, in the
  light and the dark theme, and the whole page at 1440 px. They go beside the page in a `shots/` folder, with a
  `capture.json` that lists the files the page loaded and anything that went wrong while it loaded. A page in `history/`
  or in a round before the latest is refused. With `--url <address> --name <name>` it captures a real website into
  `research/site-refs/<name>/`: the first screen at both widths, the whole page and two small thumbnails. That form is the
  only one that reaches the internet. It refuses until you have answered the online-research question (`site_research`
  is `online` or `links-only`), and a site that does not load exits with 1 and writes nothing.
- Website references (Standard and Full, when your brief lists a site): after the system rules,
  `/brand-creator:round site-refs` asks once whether Claude may research sites online, asks for sites you like and
  dislike, and shows four to six groups of real sites, each captured, with what to take and what to leave. Your pick is
  recorded before any page of your site is built; you can skip it in your own words. `board-lint` checks the board:
  a site in your brief, the system rules approved, your online-research answer, at least three site clichés, and four to
  six groups of three or more sites, each with a link, its captured screenshot, what to take and what to avoid.
- The site round (Standard and Full, when your brief lists a site): `/brand-creator:round site` builds the first screen
  of your home page in two or three ways from the references you picked, each checked against your brand rules, captured
  in four views and read cold. You pick one; then the other pages follow, and you mark each choice on them as a brand rule
  or just an example. The approved pages are references for whoever builds your site. `board-lint` checks the board: a
  site in your brief, the system rules approved, your website references picked first (or skipped in your own words),
  two or three heroes on the first board, and for each hero or page a page check and four captured views of the page as
  it is now. A hero's cold review has to match those views too. The other pages follow a hero you picked, every choice
  is tagged as a rule or an example, and a rule says where you decided it.
  When `page-check` could not check a page for a tell (no `lang`, a language with no word list, a page with more
  elements than it checks), `board-lint` says it could not verify that tell, not that it found it, and the card still
  has to name it or argue it.
- `brand-creator site approve` copies the approved pages of the site round into `site/`, with their paths fixed, and
  writes `site/site.json`: each page, its layout, and every choice marked as a brand rule (with where it was decided)
  or an example. It needs the pages approved (G4p recorded) and the pages board linted since its last change. It
  refuses a page that loads from the internet or from outside your project, writes nothing when any page fails, and
  never deletes an earlier `site/` (`--replace` moves it to `removed-<date>/site/`). It copies every page card of the
  pages board, so an approval covers the whole board: to leave a page out, remove its card from the board and lint it
  again first. The approved pages are references for whoever builds your site, not templates to fill in.
- A new how-to, "Get reference pages for your site", walks through the website references and the site round, from your
  answer on online research to the approved pages. The manual index and the commands page link to it, "Choose a tier"
  and "What it makes" describe the new steps, and the glossary explains website references, reference page, cold review
  and layout reference.
- `check` now checks the approved pages in `site/`: unchanged since approval, each checked against your brand rules, with
  current stills. A project without approved pages gets no new row; a page you edited after approving it fails the
  check and names the command that approves the pages again.
- An opt-in `site` chapter for the brand book (`book_chapters: [site]`) shows the approved pages of your site and
  every choice on them as a rule or an example. Each page has its layout's job, its first screen at 1440 and 390 px
  and a table of the choices on it, with where each rule was decided. It needs the pages approved (`site approve`)
  and their stills (`capture site/<page>/index.html`); without the approved pages, or without a still, the book stops
  and says what to run, and writes nothing. A book without the chapter is unchanged.
- `site approve` refuses a page folder, a round folder, the `rounds/` folder or the pages board when it is a
  symbolic link, wherever the link leads, and a folder link inside a page that leads out of your project; nothing is
  written. The `site` chapter of the book takes pages and stills only from inside your project, and stops on a still
  that is not a PNG picture, naming the file and the `capture` command that takes it again.
- A behaviour eval, `site-refs-gate-before-site-round`: on a Standard project with the system rules approved and a brief
  that lists a site, "build the home page" writes no page of the site and records neither the website references pick
  nor a skip, and without web tools Claude says the website references need web access and stops.
- Redesigning a site? `brand-creator adoption wiring --before` records its links, form fields, handlers, test hooks,
  ids and scripts, so nothing is lost by accident. Name a repository you surveyed with `adoption survey`; the command
  reads its source (`.html`, `.jsx`, `.tsx`, `.vue`, `.svelte`, `.php` and the other template and script files, with
  `.gitignore` honoured and lock files, change history, minified output, `dist`, `build` and vendored folders left out)
  and writes the record into `adoption.json`. It never edits the repository, and proves it: if anything in the
  repository changes while it reads, the row `read-only:<label>` fails and nothing is stored. The first `--before` is the
  baseline and is not replaced unless you pass `--again`; `--after` records the site once the redesign is applied and
  needs the baseline. The reading is by pattern, so a link or id built when the page runs is missed or noisy.
  `--compare` says what a redesign lost: it reads the repository again, writes nothing, and lists every item of the
  baseline that is gone, with the files it was in. A loss is fine only when you record why, in your own words:
  `--drop "link:/pricing::the pricing page moved to /plans"` (repeatable). `brand-creator check` fails a recorded
  `--after` that lost wiring nobody dropped (the row `adoption:wiring:<label>`), and `ADOPTION.md` shows the wiring in
  a "Wiring kept" section: the counts before and after, and each lost item as dropped with your reason or lost and not
  recorded. A list without wiring is unchanged. Pass `--page <url>` (repeatable, with `--before`, `--after` or
  `--compare`) to read the pages of your own local server too, as the browser shows them: only addresses on this
  machine (`localhost`, `127.0.0.1` or `[::1]`) are opened, and a page that cannot be read stops the run and stores
  nothing. Listeners that a script adds are not visible in the page, so they are read from the source only.
- A brand kit for your product repositories: `brand-creator kit build --yes` writes it around your brand skill, with the
  brand's own files copied in byte for byte and locked (opt-in when you approve the brand). The kit gets a version
  (`<edition>.<build>`) that goes up by one when anything in it changes and stays the same when nothing does. A kit
  file you edited by hand, or a file you put into one of its generated folders, stops the next build; `--replace` moves
  it to `removed-<date>/` and builds. Nothing is deleted.
  `brand-creator check` fails a kit file you edited by hand and says when the brand changed after the kit was built, and
  `applied-skill` leaves a project that has a kit to `kit build`.

### Changed

- A pack recorded with `staleness --write` reads as stale after this update (the scripts it hashes changed); rebuild
  it.
- The list of generic first-idea patterns every direction is tested against has four new patterns, found in a real
  brand's site: a pale ground with one timid accent, the display faces a generator names first (dated 2026-10), a
  texture standing in for the idea (film grain, a stamp or badge, an engraving, a halftone) and the stock product page
  (a label over every heading, a hero with two buttons, three equal tiles, an FAQ and a closing call-to-action band). It
  also states the line each direction writes, `hit: <id> | <argument>`, and that layout patterns are judged on the
  direction's own homepage frame, never on the board's chrome.
- `board-lint` now checks the reflex line of each direction on a pick board, not only that it is there. The line is
  `no hits`, or one `hit: <id> | <argument>` per hit, where the id is a pattern of the reflex list or an item of the
  project's `research/cliches.md` under "Avoid unless argued"; `near miss: <id> (why)` records a pattern that looks
  close and is never counted. Two hits in one direction now fail (`reflex-count`: replace a part before showing it), and
  so does one hit that every direction shares (`directions:reflex-shared`: the directions are not divergent). Two
  checks only warn in this release and become failures in the next one: a line that is not in the format
  (`reflex-format`, which includes the free text earlier boards used) and a hit that names no known pattern
  (`reflex-ids`; the row says when the project has no `research/cliches.md`). The report lists `research/cliches.md`
  when it exists, so a changed list makes the lint stale. The example board of Acme, the Quick smoke's bakery board and
  the board templates use the new line.
- The judge of a direction round (the opt-in `directions` workflow) now lists the reflex patterns it sees. Before it
  reads any argument, it names, for each direction, every pattern of the reflex list and every "Avoid unless argued"
  item of the project's `research/cliches.md` that it sees on that direction's board, with where it saw it; layout
  patterns are judged on the direction's own homepage frame, never on the board's chrome, and an empty list is an
  answer. The lead puts each list beside the direction's reflex line (`data-field="reflex-seen"`), where `board-lint`
  compares it with what the direction declared.
- brand-creator's description now includes the brand's website references and reference pages, and still leaves building
  production websites to other tools. `/brand-creator:check` says in its description that, with `--page`, it checks a
  page built anywhere against the brand.
- `fontcheck` names each font's family, weight and style in its licence row.

### Fixed

- The files written for other tools and agents now carry the type sizes, weights, line height and letter spacing, the
  spacing steps and the corner radius that the tokens define, wherever the tokens name them (`size.text-*`, `weight.*`,
  `space.*`, `radius.*`, `leading.*`, `tracking.*`, `layout.*`, `breakpoint.*`, or the older `dimension.space-*`). Before,
  `DESIGN.md` said "Families only: the tokens define no sizes or weights" whatever the tokens held, and spacing and
  radius were read from `dimension.*` tokens only. `DESIGN.md` now has them in its type, spacing and rounded entries and
  in its Typography and Layout sections; `BRAND.md` lists them under Type and a new Layout block; the brand's applied skill
  lists them under Type and a new Layout section. A value the tokens do not hold is still not invented, and a brand with
  no sizes or weights keeps the sentence saying so. When the tokens give one step in the older and the new form
  (`space.1` with `dimension.space-1`, `radius.sm` with `dimension.radius-sm`, `leading.sans` with `line-height.sans`),
  `DESIGN.md` has one entry for it, or numbers the second when their values differ and says which token it is, so that no
  key is written twice (a repeated key is not valid YAML and the format's check cannot read the file). Run `adapters`
  and `applied-skill` again to update files you already have.
- Finishing a site project no longer fails after the pages are approved. A page check used to depend on your whole
  project record (`BRAND-STATE.md`), so approving the book or the adoption made the page checks of the round and of
  `site/`, and the pages board's check with them, "not verified", and the finish chain turned that into a failure. A page
  check now depends only on what it reads from that file: the system rules you approved. Changing one of those rules
  still makes the checks stale, as it should. A rule on the pages board whose source is a line of `BRAND-STATE.md` and
  of no other decision file makes the board's check go stale when that file changes: check the board again.

## [0.4.2] - 2026-10-24

### Fixed

- `board-lint`: a `motion/motion.json` that says `on` but is not valid in itself no longer makes `motion:off` "not
  verified". 0.4.1 did, so every motion board lint stopped at exit 3 until the unrelated error was fixed. An answer that
  says the brand moves cannot record that nothing moves, so the row passes and names the error; `check` still fails it
  in `motion:spec`.
- `board-lint`: the lint report of a motion board lists `motion/motion.json`, so `check` asks for the lint again when
  the answer changes after it. An answer turned from `on` to `off` after the lint went unnoticed until the next lint.
- `check`: a report that is valid JSON but no report (a list, `"inputs": null`, an input with no path) is its own
  failing row, instead of stopping `check` with a traceback. So is a report that `check` reads again after its own row
  passed and that lacks what it reads: the colour-vision rows of `contrast`, the output `book` recorded, the stills a
  `frames` report vouches for, and the files `adapters` and `applied-skill` wrote.
- `check`: a report of `motion/proof.json` that cannot be read is no verdict on the move: `motion:proof` says "not
  verified" and asks for the proof to run again, never that the move fails.
- `check`: when the proof of the approved move fails and another report of the same file passes (a folder renamed by
  letter case on macOS or Windows can leave one behind), `motion:proof` names the passing one and says that a leftover
  can be moved to `removed-<date>/`.

## [0.4.1] - 2026-10-24

A brand that moves now passes `motion:proof` only on a passing report of `motion/proof.json`, the proof of its approved
move. A project that 0.4.0 passed on the report of another proof no longer passes: `check` fails it while
`motion/proof.json` does not exist (write it), and says "not verified" until `brand-creator shot --motion
motion/proof.json` passes.

### Fixed

- `check` counts only the report of `motion/proof.json` for `motion:proof`. In 0.4.0 a passing report of any other proof
  of the project met it, so a brand that moves could pass `check` with no proof of its approved move, while `finish.sh`
  said `check` would fail it. A report that names no proof no longer counts either.
- `check` fails `motion:proof` when the proof of the approved move ran and failed, and names its report. 0.4.0 called it
  "not verified" and asked only to run the proof again.
- `board-lint` reads `motion/motion.json` the way `brand-creator motion` and `state` do: a file they refuse, such as `off`
  with no reason, is "not verified" in `motion:off` with the same message, never read as "nothing moves is recorded".

## [0.4.0] - 2026-10-24

Motion is part of the Standard and Full tiers now. A Standard or Full project that has already recorded its system rules
needs `motion/motion.json` before `brand-creator check` passes again: run the motion round, or record that nothing moves with
`brand-creator motion --off "<your reason>"`. Until then `check` fails `motion:decided`. Quick is as it was: motion is
settled at the end, with the system rules, and only when something moves. This release changes what `check` expects of a
Standard or Full project, so it may break one made before it. A board made from an older template also fails `board-lint`'s
new `page:votes` row until each card's vote carries its direction's name (see Fixed).

### Added

- `brand-creator motion` says where you stand on motion: `motion: on (signature: <name>)`, `motion: off (nothing moves:
  <reason>)` or `motion: not decided`. In Standard and Full, once the design is approved, "not decided" is followed by what
  is due before the system rules. `--json` prints the same as data. `brand-creator motion --off "<reason>"` records that
  nothing moves, once, in your words, in `motion/motion.json` (it creates the folder). It never writes over an answer: asked
  again it says `already recorded` and leaves the file alone, and when `motion/motion.json` says your brand moves it refuses
  (exit 2), because turning motion off is a rule change: edit the file, then run `brand-creator check --cascade`. An empty
  reason is refused too. It reads your answer from that file alone, so it shows it even when the move names tokens that are
  not built yet (`check` says so). `brand-creator state` prints the same line, so Claude sees your answer and never asks
  again.
- A motion round: `/brand-creator:round motion` builds a board of three variants of your logo's one move, after you approve
  the design, in any tier. Standard and Full run one for every brand unless you say that nothing moves (asked once, with a
  recommendation); Quick may run one when something moves. Each variant has a folder of its own, `rounds/r<N>/<name>/`, with
  a page where the move is seen, a proof and its 25 stills. Its card shows a strip of the stills, the still you get with
  reduced motion, a link to the live page, what the proof found, what the move is, what it costs, what is left with no
  script, and a vote. You pick one or combine two, and the next motion round (one or more variants, with what changed and the
  weak points) refines it. When you approve a variant, Claude builds the tokens the move needs and runs the variants' proofs,
  stills and the lint again so that the round's record is current, locks the round as `approved-motion`, copies the variant
  into `motion/`, records "on" in `motion/motion.json`, proves it and takes its stills for the book. The board's page is a
  new template, `templates/motion-board.html`.
- `board-lint` reads a motion board (`data-board="motion"`) with seven rows, each naming the variants it fails: `motion:g3`
  (the design is approved), `motion:off` (nothing moves is not recorded), `motion:variants` (exactly three on the first
  motion board, a word for each name), `motion:files` (each variant's folder, spelt as the card spells it, letter case
  included, its page and proof; the proof is of the page the card links and compares with the approved logo in
  `assets/logo/`, so a proof copied from an earlier round and still pointing there fails), `motion:proof` (each proof has a
  current report, and the proof line on the card says what it found; a move drawn by `requestAnimationFrame` stays "not
  verified", and the row says to use CSS animations, transitions or `element.animate()`; the row quotes up to three of the
  rows the report could not verify), `motion:stills` (the strip and the still on the card are the very files `frames` took,
  checked byte for byte, and `frames` took them of the page as it is now) and `motion:fields` (What it is, Cost and Degrades
  to are filled in). A motion board never counts as a round of directions, a style round or a rejected round.
- `check` has two new rows in Standard and Full once the system rules are recorded. `motion:decided` fails without
  `motion/motion.json`, "on" or "off". For a brand that moves, `motion:proof` needs a passing proof of the approved move: it
  fails when `motion/proof.json` is missing, and says "not verified" until `shot --motion motion/proof.json` has run; when
  the report is there and says not verified, that row and the row of the report itself quote up to three of the rows it could
  not verify and what to do about them, as `board-lint` does for a variant. The proof of a try-out in a round never counts,
  and neither does the one report of an earlier version (`assets/_checks/motion.json`): run `shot --motion motion/proof.json`
  again. From the moment the design is approved until the system rules are recorded, an open question on motion is an
  information row. Quick has neither row.

### Changed

- `frames` keeps the stills of a try-out proof beside it: a proof in the latest round or in a `removed-*/` folder writes them
  to `<its folder>/frames/<case>/`, not to `motion/frames/<case>/`. The stills of your brand's approved move stay in
  `motion/frames/`, the only ones the book replays. A round copied whole, with the stills of an earlier proof in it, has them
  taken again in place, and the report says so. A proof inside `history/` or in a round before the latest one is refused
  (exit 2, before anything is written), because both are read-only: take the stills before you freeze the round or start the
  next one, or copy the proof and its page into the latest round and run `frames` there.
- A new Standard or Full project's `tools/finish.sh` has a motion step before the stills and the book. It prints your answer:
  "nothing moves" with your reason, or "motion is not decided" with what to do, or, for a brand that moves, it runs `shot
  --motion motion/proof.json`. A failing proof goes on, and `check` fails its report; a proof that is not verified goes on
  too (exit 3 after it wrote its report, for example a move drawn by `requestAnimationFrame`), and `check` says that it is
  not verified, and why; any other stop (exit 2, or exit 3 with no report written, as when Chromium is missing) stops the
  chain; a missing `motion/proof.json` is said and the chain goes on. The stills step says why whenever it takes none. A
  project made before this version can copy the step from the template into its `tools/finish.sh`. Quick has no step.
- The system rules in Standard and Full offer the motion rules from the approved move, and none when nothing moves. In Quick
  they are offered only when something in the brand moves, as before.

### Fixed

- The templates of the round page, the style board and the review copy gave every card's vote the same radio name, so a page
  made by copying the card had one vote group: a vote on one direction cleared your vote on the one before. The radios of
  each card now carry its direction's name (`vote-<name>`), as on the motion board, and every vote stays. `board-lint` checks
  it on every kind of board (`page:votes`): it fails a board whose cards share a radio name, or whose radios are not named
  `vote-<its name>` (the name as written on the card, letter case included), names the cards and the fix, so a page made from
  an older template, or a card copied and not renamed, no longer passes.

## [0.3.6] - 2026-10-23

The brand book's motion chapter shows the motion from the project's data, and replays it with no script. Three fixes for the
motion proof of 0.3.5 come with it. A project made before this version should look at two things of its own: add the `frames` step
to its `tools/finish.sh` (see Changed), and take `will-change` off a still. A still that the page keeps on a layer of its own
(`will-change: transform`, a 3D transform) is drawn with antialiasing a few levels off the still's file, so the exact rest-frame
comparison fails it. In 0.3.4, `will-change` was the way to make the scratch-page comparison pass; since 0.3.5 the comparison
draws the still where the mark is, and does not need it.

### Added

- The motion chapter is built from `motion/motion.json`: the signature move and where it shows, the moving parts, a timeline
  in which every reference is its token name and its value (`560 ms motion.base + motion.stagger × 2`, `320 ms motion.base`,
  `cubic-bezier(0.2, 0, 0, 1) easing.standard`), every duration in milliseconds, every curve with its four numbers and a small
  drawing, and the motion rules. When nothing moves, the chapter says why and shows no replay. A project with no
  `motion/motion.json` keeps its token table and the build warns that the chapter has no signature move or timeline. A
  `motion.json` that is not valid stops the build, as it stops `adapters`. The chapter appears as soon as `motion/motion.json`
  exists, whether motion is on or off.
- The chapter replays the motion. For each page case that `frames` took stills of, the book plays the mark moving: the stills
  are one image side by side, shown one at a time by the page's own CSS (no script), and the image is in the book once. "Replay"
  starts it again, "4× slower" plays it at a quarter of the speed, and both work from a click or the keyboard. Under reduced
  motion the book shows the still instead and nothing moves. In print it shows the whole strip, scaled to the page, with the
  times of the stills, also when the printout is made with reduced motion on. The words around a replay name it after the
  signature move (or "The mark in motion", numbered when there are several), never after the case, so a case called `hero-v2`
  does not trip the book's word rules. The proof table follows the same rule: it shows each check of the motion report
  (`cls:normal`, `edges:360`), not the row id, which holds the case's name, and groups the checks of a case under its replay's
  name, or `Case 2` (its place in the report) when it has none. The checks of a states case name its states
  (`1x:control:rest!=draft-v2`): the table shows them by their place in the case, `1x:control:state 1!=state 2`. A proof is
  `Motion proof`, or `Motion proof 1`, `Motion proof 2` ... in the order of the proofs' paths when there are several, in the
  chapter and in the report table, never its file name or its report's name. The names stay in `data-proof`, `data-report` and
  `data-check` attributes, so a proof file called `hero-v2` or a state called `draft-v2` no longer stops the book. Run
  `brand-creator frames motion/proof.json --count 25` before `book`; fewer than 9 stills jump, and the build says so.
- The build says what it could not show, and the command that fixes it: no stills yet, or none that can be shown (when motion
  is on), stills of a try-out proof, of a proof that is gone or of a case the proof no longer has (left out), a still that is not
  the file `frames.json` lists, and a `frames` report that is stale, missing, failed or does not cover the case. A run of
  `frames --case X` leaves the stills of the other cases without a report that vouches for them, so for a proof of several page
  cases the warning names the run of every case, `frames <proof> --count N`, and for a proof of one `frames <proof> --case <case>
  --count N`. `book` never runs `frames` itself.
- `book-lint` has three new rows for the replay. `motion:reduced` fails any rule that starts an animation or a transition with
  a duration and has no matching rule that switches it off inside `@media (prefers-reduced-motion: reduce)` (a start marked
  `!important` needs a stop marked `!important`, weighed on the longhand that stops it: a transition-property of `none` or a
  duration of 0, and the longhand's winner in the rule counts, not its last declaration). A stop is weighed against every other
  rule that can select the same element and sets that longhand: `.y { transition-duration: 150ms }` with
  `main .y { transition-property: color }` is not switched off by `.y { transition-property: none }`, because the more specific
  rule outweighs it, and the row says which one. A stop inside `@layer`, `@scope`, `@container` or `@supports`, or in a rule
  that holds nested rules, is not counted: the gap stays and the row names the rule. A start in such a place is weighed as if it
  applies (an `!important` one still needs an `!important` stop) and is named too. A `style` attribute is read like a rule
  (`transition: color 150ms!important` needs no space). The row also fails any replay that still shows its moving picture or its
  two boxes there, or hides its still. `motion:replay` fails a box with no label or no label text, a box or a label the keyboard or
  the eye cannot reach (hidden by itself or by any ancestor: `inert`, `hidden`, `display: none`, `visibility: hidden`,
  `opacity: 0`), a box that does not start the replay again, a slow replay that is not four times as long, a replay that does not
  play once or does not hold each still (`step-end`), a replay that does not play forwards (direction `normal`), running, held at
  both ends (fill mode `both`) and at once (delay 0), keyframes that are missing, have no name, differ or do not step through the
  stills of `frames.json`, an `object-position` marked `!important` on the flipbook (the keyframes cannot override it, so the
  replay is frozen), and a `<source>` with a `media` attribute or a type other than `image/png`, which a browser may skip to
  draw the 1 × 1 stand-in. `motion:stills` fails the same `<source>`, and a book whose pictures, length or number of stills are not
  those in `motion/frames/` ("the book shows stills older than motion/frames: run brand-creator book"), a picture that is not
  the file `frames.json` lists (by its sha256), a replay that is not one still wide and high (its `width` and `height` held by
  `max-` and `min-`: a limit that makes it another size fails, and so does one the lint cannot read as px), and a generated book
  that has no replay of stills that are there now (it was built before `frames` ran, or its Motion chapter file has no
  `{{motion}}` line). A selector the lint cannot read (`:is`, `:not`, `:where`, `:has`, `:hover` ...) is named in the row it
  affects ("not read: ..."), as a warning, and so is a rule inside `@layer`, `@scope`, `@container` or `@supports`, which the
  lint does not evaluate, a style rule that holds nested rules (CSS nesting), and a `@layer a, b;` statement, which orders layers
  (named in all three rows). A statement at-rule (`@layer`, `@import`, `@charset`) ends at its semicolon, so the rule after it is
  read. The lint weighs a `style` attribute: it beats a rule of the same importance, and an `!important` rule beats it when it is
  not important. A book with no replay gets the three rows as information, never as a pass.

### Changed

- `templates/book/motion.md` holds only your words now: why it moves, and what reduced motion does. The block fills in the rest.
  A chapter file you wrote from the old template, with its `{{motion}}` line, gets all of it with no change.
- `book-lint --self-consistency` lets a replay use its own length and four times it as durations, besides the motion tokens, in
  a rule that reaches that replay and nothing else in the book. Everywhere else a duration must still be a token or 0.
- `book-lint` fails a book that has a transition or an animation (a hand-written `transition: color 150ms`) that nothing
  switches off under reduced motion. A book from `brand-creator book` has none, so only a hand-edited book is affected.
- `book` records `motion/motion.json`, the stills, their proof and their `frames` report as inputs of its report, and `book-lint`
  records the stills, their proof and `motion/motion.json`, so changing any of them makes `check` say the book is stale. Only the
  stills of a gated proof count, and only for a book that has the Motion chapter while motion is not off (a Quick book is not
  made "not verified" by `frames`); a try-out's do not. Both reports also record the list of those stills, with the checksum of
  each strip and reduced still (or `absent`), so `check` says "not verified" when stills appear, go or change after the book was
  built, and when a picture goes and comes back.
- `check` gates the `frames` reports (`assets/_checks/frames/<name>-<hash>.json`) as it gates the motion reports. A current,
  passing report passes and a failing one fails. A stale one is "not verified" and names `brand-creator frames <proof> --count N`
  (or the `--at` points of its last run) and then `brand-creator book`, which replays the stills the report vouches for. A
  current, passing report is "not verified" too when a case of the proof has stills in `motion/frames/` and the report has no
  passing row for it: every run rewrites the one report of a proof, so `frames --case X` after a change to the page leaves the
  other cases' stills unvouched, and `check` names `brand-creator frames <proof> --count N` (which takes every case) and then
  `brand-creator book`. The report of a try-out proof (under `rounds/`, `history/` or a `removed-*/` folder) is listed and never
  fails, and the report of a proof that is gone is a warning that says to move it to `removed-<date>/`.
- `templates/finish.sh.tpl` takes fresh stills before it builds the book: in the Standard and Full tier (the Quick book has no
  Motion chapter), when `motion/motion.json` says on and `motion/proof.json` has a page case, it runs
  `frames motion/proof.json --count 25` (it writes only `motion/frames/` and its report; `FRAMES_ARGS` in block 2 sets other
  points, such as fewer stills for a wide mark). A failure that writes a failing report (exit 1: a page `frames` cannot step
  through, such as `requestAnimationFrame` or a scroll timeline, or one that does not load cleanly) does not stop the chain: it prints
  `finish.sh: frames could not take the stills (see above); the book keeps the stills of the last run that worked, if any, and
  check says why` and goes on to the book, and `check` fails the report. Any other failure of `frames` (exit 2: a strip wider than
  Chromium writes, a case folder that holds another proof's stills; exit 3: it could not run) leaves no failing report for `check`
  to gate, so the chain stops with that exit code. A project made before this version should add the same step before `book` in
  its `tools/finish.sh`.

### Fixed

- The rest frame of the motion proof no longer fails on a page that swaps a still for a moving copy. A still hidden by
  `animation: hide 1s 1s backwards` and a copy shown by `visibility: hidden; animation: show 1s 1s backwards` are, once the motion
  has ended, the still visible and the copy hidden. The proof wrote the keyframe values over that (the still hidden, the copy
  visible) and compared the copy with the still: a false failure. It now writes what the page draws, and only drops an animation
  whose effect no longer applies.
- The phone-width rows (`edges:360`, `edges:390`) count a part of the mark only where it is painted. A part scaled up inside a
  wrapper with `overflow-x: clip`, and transparent at 0 ms by a backwards fill, was reported past the left edge on several rows
  while the page never got wider. What an ancestor clips (an `overflow`, `contain: paint`, the viewport of an `<svg>`) is cut off,
  and a part at opacity 0 or `visibility: hidden` is not counted. An `<svg>` mark clips its parts at its own viewport unless it
  says `overflow: visible`.
- The `frames` and `shot --motion` reports record every project file the page loads (a stylesheet, `tokens.css`, a script, an
  image) as inputs, not only the page and the proof. A motion that lives in such a file (`animation: press var(--motion-base)`)
  kept a "current" report after the file changed. Now the book and `check` see both reports as stale. `check` used to leave the
  `frames` report out: after the owner ran `shot --motion` and `book` as it asked, it passed while the book replayed the old
  stills. It now says "not verified" until `frames` and then `book` have run (see Changed).

## [0.3.5] - 2026-10-22

The motion proof, second release: it steps through a page's motion instead of waiting for it, looks at phone screens, compares
the rest frame in the page itself, and keeps one report per proof. A new command writes stills of the motion. A proof that
passed before can now fail or say "not verified": an animation of `top`, `width` or `margin` fails, and motion driven by
`requestAnimationFrame` cannot be checked at the phone widths. A project made before this version should add two lines to its
`tools/finish.sh` (see Changed).

### Added

- `brand-creator frames <proof.json>` writes stills of a page's mark along its motion into `motion/frames/<case>/`: five by
  default (0, 25, 50, 75 and 100 percent of the motion), or `--count N`, or the points you name with `--at 0,40,100`.
  Next to them: `strip.png` with the stills side by side, `reduced.png` (the mark under reduced motion) and `frames.json`
  with each still's time and checksum. The files are in your project because the brand book will show them. A file is
  written only when its bytes change, so a second run says "unchanged". `--case <name>` picks one case. It writes nothing,
  and says why, for a page with nothing to step through, a page that also moves by `requestAnimationFrame` while the stills
  are taken (they would differ from run to run), and a case whose folder holds the stills of another proof. A strip wider
  than Chromium can write is refused with the number of stills that fit.
- The motion proof looks at phone screens. It loads the page again at 360 and 390 pixels wide (`"widths"` in the case
  changes them) and, at every point of the motion, checks that the page cannot be swiped sideways, that no part of the mark
  goes past the left, top or right edge, and that the page is no taller than at rest. A failure names the moment, the part,
  the edge and how far: `at 62% (310 ms): g#letter-a 22 px past the right edge at 360 px`.
- A pixel mark is held to whole pixels at every point of the motion and at every keyframe, not at nine fixed points, whether
  it moves by `transform` or by the `translate`, `rotate` and `scale` properties. A mark counts as a pixel mark when its still
  says `shape-rendering="crispEdges"` on the root; `"pixel": true` or `"pixel": false` in the case overrides that.
- `brand-creator version --check` says whether the session runs the copy of the plugin that Claude Code has installed. After
  an update, a session that started before it still runs the old copy: the command then exits 1 and says to start a new
  session. In a checkout of the repository it says "not checked".
- A step of `motion/motion.json` can start at a sum: `"{motion.base} + {motion.stagger} * 2"` starts a step when another ends,
  plus a stagger. Every part of the sum must be a duration token.

### Changed

- `shot --motion` writes one report per proof file: `assets/_checks/motion/<name>-<hash>.json`, where the name is the proof
  file's name and the hash comes from its path as the disk spells it. It used to write `assets/_checks/motion.json`, so a
  second proof, or a try-out under `rounds/`, overwrote the report of the first. Run each proof again to get its report. An old
  `motion.json` is still checked, with a warning to run the proof again; move it to `removed-<date>/` afterwards.
- `check` reads every motion report on its own terms. A proof under `rounds/`, `history/` or a `removed-*/` folder is a try-out:
  its report is listed and never fails the check. A report whose proof file is gone gives a warning that names it and says
  to move it to `removed-<date>/`. A pack file that asks for the motion check needs at least one passing report of a proof of
  the project, and says "not verified" and which command to run when there is none. The brand book's motion table shows the
  same reports.
- The motion proof steps through a page instead of waiting for it. It pauses every CSS animation, CSS transition and
  `element.animate()` on the page and sets each to a time: 0 and every 1/32 of the motion, every 1/32 of each animation's own
  run (so a short animation inside a long motion is not stepped over), every keyframe (at its real time when the whole
  animation has an easing), and the peak of every curve that overshoots. A page with a 10 second animation no longer takes 10
  seconds. Motion a script starts later is looked for at every frame until `settle_ms` and stepped through from its own start.
- Motion driven by `requestAnimationFrame` cannot be stepped through. The page is still given `settle_ms` in real time and a
  warning row says so, and now the phone-width rows and a pixel mark's whole-pixel row say "not verified" instead of passing
  with nothing measured. A `requestAnimationFrame` loop that still runs after `settle_ms` fails `loops` and `settled`.
- An animation of a layout property (`top`, `left`, `width`, `height`, `margin`, `padding` and the like) fails the layout-shift
  row: it moves the page around it, and Chromium does not count a step of under 3 pixels as a shift, so stepping through it
  cannot measure all of it. A `transform` or `opacity` animation passes.
- The rest frame is compared in the page itself. The proof cuts the mark's box out of the page and draws your still exactly
  where the mark draws: in the `<img>` itself for an image, and for an inline SVG over its content box, in its own parent and
  out of reach of the page's style sheets, so an offset page, a faded parent or a style rule for `svg circle` changes nothing.
  The default tolerance is now 0, where it was 8 of 255, because the two are drawn the same way; `"tolerance"` in the case
  still works. A mark an ancestor rotates cannot be placed exactly and says "not verified".
- A vector mark may ease smoothly: its whole-pixel row is information only (`a vector mark: smooth easing allowed`). Before,
  every mark was held to whole pixels, which no smooth easing curve can meet.
- `templates/finish.sh.tpl` checks the plugin version first (`version --check`) and runs `contrast --cvd` when your
  `qa/rules.json` sets a colour-vision threshold. A project made before this version should do the same in its
  `tools/finish.sh`: replace the `plugin version` step with `step "plugin version"; "${BC[@]}" version --check`, and add
  `--cvd` to the `contrast` step if `qa/rules.json` has a `cvd` section.

### Fixed

- `check` no longer passes when `qa/rules.json` sets a colour-vision threshold and the contrast report has no colour-vision
  rows (a chain that ran `contrast` without `--cvd` dropped them): it says "not verified" and names `contrast --cvd`.
- In BRAND.md, DESIGN.md and the brand's own skill, the places the signature move shows are a list, one per line, like the
  motion rules. A place with a comma in its name stays one item.

## [0.3.4] - 2026-10-21

Motion becomes data: easing curves are tokens, durations and curves reach Swift and Android, and `motion/motion.json`
holds the motion spec that BRAND.md, DESIGN.md and the brand's own skill repeat. A duration that is not whole
milliseconds, or not written the DTCG way, now stops the build: run `brand-creator tokens` once after updating.

### Added

- Easing curves are tokens now. A `cubicBezier` token (`[x1, y1, x2, y2]`, x between 0 and 1) builds into `tokens.css` as
  `--easing-standard: cubic-bezier(0.2, 0, 0, 1)`, and into the Swift and Android files below. A curve that is not four
  numbers, or whose x leaves 0 to 1, stops the build and names the token. The starter tokens have an `easing` group with
  three curves (`standard`, `enter`, `exit`), offered as proposals until you decide at G4.
- Durations and curves reach the apps. `tokens` writes `swift/BrandMotion.swift` (`BrandMotion.Duration.base` in seconds
  and `BrandMotion.Curve.standard(duration:)` for SwiftUI), `android/values/motion.xml` (durations in milliseconds) and one
  `android/interpolator/brand_<name>.xml` per curve. A brand with no duration and no curve gets none of them. Every file is
  read back and compared with the source before the build passes.
- `motion/motion.json` is the motion spec as data: whether anything moves (and, if not, why, in your words), the signature
  move, the moving parts, a timeline written as references to the duration and curve tokens, and the motion rules.
  `brand-creator check` validates it, and names the field and what is wrong; a reference that is not a built token of the
  right kind is an error.
- BRAND.md, DESIGN.md and the brand's own skill say how the brand moves: the durations and curves, the signature move and
  the rules, or "Nothing moves" with the reason. A change to `motion/motion.json` makes them read as out of date until they
  are generated again.

### Changed

- `tokens.json` has a new `motion` entry (durations in milliseconds, curves as numbers) when the tokens have either;
  `other` is as it was.
- A duration must come to whole milliseconds, because Android keeps it as an integer: `12.5ms` now stops the build, and
  `0.32s` is 320 ms.
- Some token sources that built before now stop the build, each naming the token: a duration written as a bare number
  (`"$value": 150`) or as `.5s` (write `0.5s`), a duration over 2147483647 ms, and two durations that would share a Swift
  name (`duration.fast` next to `motion.fast`). In an existing project `tokens --check` fails until you run
  `brand-creator tokens` once after updating, because of the new files and the new `motion` entry.
- A project with durations but no curve and no motion spec gets the same `tokens.css`, Swift colours, Android colours and
  BRAND.md as before (BRAND.md now also lists a duration outside the `duration` and `motion` groups). Its DESIGN.md and
  brand skill gain a short Motion section that lists the durations.
- The motion hand-off template and the G4 motion rule name the easing tokens, and the template points at
  `motion/motion.json`.

### Fixed

- `emit social` keeps the manifest row of an old Open Graph image only while its file is there. Its warning now says to
  run `emit social` again after moving the old images to `removed-<date>/`, which drops their rows, so `check` and the
  book's file list stop expecting them.
- A file `tokens` no longer produces, such as the colorset of a removed colour role or the interpolator of a renamed curve,
  used to stay in `assets/tokens` while `tokens --check` passed. Now `--check` fails on it, and a build moves it to
  `removed-<date>/`.
- Every Swift keyword in a token name is escaped in the Swift files (the list was short; `Self` or `guard` did not
  compile). A colour, duration or curve named `Type` or `Protocol` stops the build, since no member can use that name.
- The brand skill is filled in one pass, so a G4 rule or a motion rule containing `{{name}}` is written as it is instead
  of being filled in or refused.

## [0.3.3] - 2026-10-21

Fixes from the first projects with several marks and the first approved books: `downscale` measures each mark's own
colour, the book's cover shows the drawn wordmark and its stamp speaks the book's language, and see-through colours keep
their alpha in the generated text.

### Changed

- The accent line under the name has square ends when everything drawn on the card is pixel art, so it matches the pixels:
  on social cards, banners, the Play feature graphic, the Chrome promo tiles and the side-by-side image (there, when every
  mark is pixel art). Vector art keeps its round ends. The templates take a new `{{rule_radius}}`; a template of your own
  without it keeps the rounding it has.
- `emit web` warns when `icon.svg`, the drawing browsers show in the tab, changes to another drawing than on its last run,
  and the warning names both files. The same file written another way, or the same bytes, is no change. To keep the old tab icon, set `favicon.drawing` in `qa/rules.json` to the old file
  (`marks.<id>.favicon` for one of several marks).
- The brand book's cover shows your drawn wordmark as its title when `assets/logo/wordmark.svg` exists: an image with the
  name as its alt text, switched to `wordmark-dark.svg` in dark mode like the marks, and set at a whole-number scale when
  it is pixel art. Without a wordmark the name is typed, as before.
- The approval stamp on the book's cover says its word in the book's content language. Give the word in `book/book.json`
  (`"labels": {"pl": {"APPROVED": "ZATWIERDZONO"}}`) and a Polish book says it; `book-lint` looks for that word, in a
  hand-authored book too, in the stamp itself rather than anywhere on the cover. Without it the stamp stays `APPROVED`, and
  the build says the label is missing. A `labels` entry that is not an object of words stops the build with a clear error.

### Fixed

- `downscale` measured every mark on `downscale.accent_colour`, so a mark with its own colour failed. It now measures the
  drawings of a mark, and the files its packs emitted (an avatar, a registry icon), on that mark's `accent` from
  `qa/rules.json`: `--accent` first, then the mark's accent, then `downscale.accent_colour`.
- `BRAND.md`, `DESIGN.md` and the applied skill printed a see-through colour as if it were opaque. A role with an alpha
  under 1 is now `#rrggbbaa` (as in `tokens.css`) wherever a role is listed, and opaque roles are unchanged. The DESIGN.md
  format the plugin pins accepts the 8-digit form, and its lint passes it.
- A card or banner template that draws its own name (outlined paths, for example) was warned about as typing the name.
  With no `{{lettering}}` and no `{{name}}` it now gets an info row that says so, reads no lettering file, and refuses
  `--name` and `--logo-svg`, which it would ignore; a template that types `{{name}}` is still warned.
- The book PDF could print an empty page between two chapters: a chapter that went on from an earlier page and ended near
  the bottom of its last page sent its bottom padding to a page of its own. The chapters and the cover keep no bottom
  padding in print now.
- The book's files chapter listed an Open Graph file that `emit social` keeps for cached link previews as if it were as
  current as the new one. The manifest marks the kept file `"superseded": true`, and the files chapter says "superseded,
  kept for cached link previews" next to it.

## [0.3.2] - 2026-10-21

Several marks in one project: each product's mark gets its own drawings by size, files, reports and checks, and the
repository's own images show every mark side by side.

### Added

- Several marks in one project: `qa/rules.json` `marks` lists each product's mark with its own size bands, and optionally
  its name, tab drawing, accent colour and tagline. Every emitter and `logo-sheet` take `--mark <id>`. Each mark gets its
  own folder (`assets/<pack>/<id>/`), report and manifest rows, and a run never moves another mark's files. `check`
  expects every mark's reports and drawings, and `contrast` checks the colours that touch in every mark's drawings.
- `emit social` without `--mark` makes the repository's own images: every mark side by side, each with its drawn
  wordmark under it (`templates/lineup.html`).
- The book shows every mark: on the cover, in a size table per mark, and in the wordmark chapter (`<id>-wordmark.svg`).
  `finish.sh` runs each pack once per mark.

### Changed

- Pixel-art marks and lettering (`shape-rendering="crispEdges"`) are scaled by whole numbers on cards, banners and the
  side-by-side image, so every pixel stays square. Vector art is unchanged.

### Fixed

- A `-dark.svg` next to a drawing could be a symlink that leads out of the project, and the emitters, `logo-sheet` and
  `board-lint` read it. Every such path is now confined to the project, as is a logo name in a book chapter
  (`{{marks:../x}}`), which exits 2. Every emitter also checks a `-dark.svg` as pure vector before it uses it.

## [0.3.1] - 2026-10-21

Fixes from the first projects built on 0.3.0: banners and cards show the drawn name, the browser tab shows the small
drawing, and see-through colours keep their alpha.

### Added

- `favicon.drawing` in `qa/rules.json` fixes the drawing of `icon.svg`. It is kept in the project, so a rerun of
  `emit web` keeps it.

### Changed

- Banners (`emit profiles`), social cards (`emit social`), the Play feature graphic (`emit android`) and the Chrome promo
  tiles (`emit chrome-ext`) show the brand's drawn lettering: `lockup.svg` on its own, else `wordmark.svg` next to the
  mark. `--logo-svg` names another file, and `--lettering lockup` or `--lettering wordmark` says which it is when its
  file name does not. `--name` types the name in the system font instead, and cannot be combined with `--logo-svg`.
  Without a lockup or wordmark, or with a template that has no `{{lettering}}` placeholder, the name is typed too and
  the report warns. The dark README header uses the lettering's `-dark.svg`.
- `icon.svg`, the favicon browsers show in the tab, is the band rule's drawing for the tab size instead of the large mark
  shrunk. Its dark switch is that drawing's `-dark.svg`, checked as pure vector like the drawing.
- `shot` loads lazy images first, waits for running animations and transitions to end (at most 15 s), and documents
  `--wait` and `--dsf` in its usage line.
- The designer agent can take 120 turns instead of 60 and is told to return its result before the limit. The
  `directions` workflow names the turn limit as the likely cause when a designer returns nothing, and says where its
  files are.

### Fixed

- `tokens.css` kept a see-through colour opaque (`#3a2448` for a scrim at 56%). It is now `#3a24488f`, and the round
  trip compares the alpha in every output, the `@supports` values in oklch, oklab and display-p3 included, so the loss
  can no longer pass.
- The book's `self:durations` check and `BRAND.md` read only `duration.*` tokens, but the starter tokens name them
  `motion.*`: a book with transitions failed its own check. Both names count now.
- `emit print --font-file` escaped the quotes around the family name, so the pieces printed in Times. The name goes into
  the pieces' CSS as written now, in single quotes, and a name with other characters is refused. Without
  `--font-family` the name comes from the font's file name, with an axis tag such as `[wght]` left out.
- `shot` called a lazy image broken when it was hidden at that width or below the fold.
- The print docs cited an intake question 7 that does not exist; print is the owner's opt-in, set by `PRINT_REGION`.
  The tier table marks print PDFs as opt-in, and the manual check lists the signature images at 1x and 2x.

## [0.3.0] - 2026-10-21

The style research now comes before anything is drawn, marks are drawn on a design tool instead of as code, and the mark
checks judge pixel marks the way they ship.

Breaking changes, each with what to do:

- A round 1 board, and the pick board of a reset round, fail `board-lint` until gate G1s is recorded. A project already
  past round 1: `state --record G1s "n/a: round 1 drawn before the style step"`, or run the style research as round 0.
- A pick board in a round that `reset_rounds` does not list fails `page:data-board`. List the round
  (`state --set reset_rounds=2,3`) or make the page a refine board.
- The `directions` workflow needs the G1s record as its `g1s` argument and does not start without it.
- A last size band with a `max_px` exits 2. Remove `max_px` from the last band: it covers every larger size.
- `logo-sheet` judges only the colours that touch the ground, checks each tile's edge, and says "not verified" for line art
  it cannot measure. Run it again; a deliberate low-contrast edge goes in `tokens/exceptions.json` with a reason.

### Added

- A style research step before anything is drawn, in every tier: Claude researches who sees the mark, where, and what
  the category looks like, then shows a style board (`rounds/r0/board.html`, from `templates/style-board.html`) with
  four to six style territories, each grounded in three or more real, linked references with what to take and what to
  avoid. You tick one or more styles (gate G1s) or say "skip the research". Without web access Claude says the research
  needs it and stops; it never invents references. After a full rejection the style research runs again before the new
  territories, on a new style board in a round listed in `reset_rounds`. That board is required: "skip the research" works
  before the first board of directions only.
- Each reference on the style board can show a small picture of its real mark: an inlined image with alt text, in a figure
  with a caption (the template's caption says "shown for private research"; the words and the language are yours).
  `board-lint` fails a thumbnail without alt text or without a non-empty caption. On a style board it also fails any
  `<img src>`, and any `srcset` on an `<img>` or a `<source>`, that is not an inlined `data:image/` URI: a linked or
  relative image fails. It checks nothing else about the network (CSS `url()` and `<link>` are not read).
- `board-lint` checks the style board (`data-board="style"`, in round 0 or a reset round): audience, surfaces, norm, at
  least four territories with word names and three linked references each, none of these, my call, questions and reply.
  Generic territory names ("Style 1", "Option 2") fail, as they already did for directions.
- After a full rejection the style gate is armed again. The pick board of a reset round fails `board-lint`
  (`project:style-gate`) until a new style board sits in a reset round after the rejected round and the owner's new pick is
  recorded after it, so the first pick no longer stands in. A page that only says `data-board="style"` is not that board: it
  needs the four named territories with content that the style lint asks for, and a copied page that still declares the round
  it came from does not count either. `state --record G1s` now also writes `g1s_round`, the highest round whose
  board is a style board (and removes it when there is none), so a pick recorded before the new style board is written does
  not count as coming after it; `state --set g1s_round=...` is refused.
- The review page of round 0 is a copy of the style board (`board-lint review/index.html --round 0` passes on it).
- Marks are drawn on a design tool: the use-llm design canvas when the session has it, else Claude Code's `/design`,
  which you type because Claude can't start it. Without either, Claude says what is missing and draws the marks as SVG
  itself only after your yes, as a weaker choice. The drawing brief goes to `brief/canvas-round-<N>.md` from a new
  template, and the marks you keep come into the round as SVG with a `SOURCE.md` per direction (the tool, prompts, image
  model, cost, tracing and hand fixes). From round 2 the brief has the drawing session start from a copy of the previous round,
  as every round does. Generated pictures cost money on the canvas, and Claude says the cost in each reply.
- The drawing brief gives every option an ID that names its board (for example `family1-bc-3`, so "the 3" can't mean two
  options), sends your board answers to the brand-creator session, keeps drafts in the project instead of a session's
  scratch folder, and sets an agent budget per run. Each `SOURCE.md` records the lineage of every kept mark and the agents and
  tokens of each run.
- A screening override goes on record: when you keep an option the screening or a judge flagged, a line in
  `BRAND-STATE.md` says why and which extra check it triggered, and that check runs before G3.
- Before you approve a refined round (G3), `board-lint` measures the round's kept marks and warns without failing the board: a
  colour that touches the background under the target (3:1, or your tokens' `touching.ground`), on light or on dark, and
  pixel marks of one family drawn with different outline widths (one at 2 px, its siblings at 1 px).
- A behaviour eval, `style-gate-before-first-board`: on a fresh project the first turn draws no board of directions, and
  without web tools Claude says the style research needs web access and stops.

### Changed

- Logo masters are vector. The mark is a pure-vector SVG and every PNG or icon is exported from it. Generated images,
  photos and sketches are for exploring: a board labels them as exploration, and one becomes the mark only after it is
  traced or redrawn as vector and fixed by hand. Refining a mark means editing the SVG, not generating a new image.
- Every pick board waits for the style pick: `board-lint` fails the round 1 board, and the pick board of a reset round,
  while gate G1s is not recorded (a pick, "skipped by owner" or an honest "n/a" all count for round 1). The state file has
  a new `G1s` gate. Projects already past round 1 record G1s honestly, for example
  `state --record G1s "n/a: round 1 drawn before the style step"`, or run the style research as round 0 now.
- The hook keeps `rounds/r0/` writable while G1s is empty, so a project that is already past round 1 can still run its
  style research as round 0. Once G1s is recorded it is read-only like any earlier round. The hook opens `rounds/r0/` only
  when it reads the state file's `gates:` block with certainty: a tab in the indentation, a quoted key or a `gates:` with a
  value on its own line (`gates: {G1s: ""}`) leaves it locked. `patch` follows the same rule, so it edits `rounds/r0/` exactly
  when the hook allows a write there.
- Direction and territory names are checked against a longer list of labels: "Territory 1", "Style A", "Option B", "Look 2",
  "Mood 3", "Direction II", "Option #2" and "Style-3" fail, as the option, direction, variant, style, concept and route
  labels did. Words that only start like a label (Harbor, Quarry, Looker, Moody, Routes) pass.
- `/brand-creator:round` takes `style` as a board kind, builds round 0 from the style board template and runs
  `state --require G1s` before any round 1 or reset pick board. The `directions` workflow takes the G1s record as its
  `g1s` argument and refuses to start without it, as `adopt` does without `g6`.
- The bakery, photographer and round-1 board evals skip the style research in their prompts (the photographer prompt in
  Polish) so they keep testing the first board of directions.
- A pick board belongs to round 1 or to a round listed in `reset_rounds`. `board-lint` now fails a pick board in any later
  round (`page:data-board`: later rounds are refine boards). It used to accept one, so a pick board in round 2 that nobody had
  listed passed on the old style pick.
- `board-lint` and `state` read a page the same way: its round and its kind come from one tag, the body (or the html tag when
  the body has neither), so `<html data-board="style"><body data-round="2" data-board="pick">` is a pick board.
- In an older project, an earlier reset round's pick board fails `board-lint` when it is linted again (`project:style-gate`: no
  new style board in a reset round after the rejected round, and no `g1s_round`), and so does a pick board in round 2 or later
  that was never listed in `reset_rounds`. `brand-creator check` lints no round itself: it reads the `board-lint` report of the
  latest round only (`rounds/r<N>/board.html`, N the highest) and asks for a new lint when that page changed, so only a round you
  lint again can fail.
- `brand-book`'s listing text names the optional chapters (tone of voice, photography), the clean-up of the options you
  decided against, and says that a brand book for a brand that does not exist yet starts with `brand-creator`, even when the
  ask says "brand book" or "księga znaku". In its trigger evals Sonnet now passes 27 of 27 queries (24 before) and Haiku 25 of
  27 (23); Haiku still misses a clean-up request and still starts it for a new brand's book asked for in Polish.

### Fixed

- `logo-sheet` holds only the colours that touch the ground to the contrast target, found in the pixels as `contrast` finds
  them. A cream face inside a black outline no longer fails on white, while a fill that runs off the drawing's edge still
  counts. The target is your tokens' `touching.ground` unless you pass `--min-contrast`, and `tokens/exceptions.json` excuses
  a colour against the ground as it does for `contrast`. Each tile's own edge must reach the target too, so a keyline thinner
  than a pixel at 16 px fails there. With size bands in `qa/rules.json`, each tile is drawn from its band's drawing, and a
  pixel drawing at the largest whole-number scale that fits, so the 16 px tile shows the 16 px drawing. Artwork with
  gradients, or line art whose colours cannot be measured, says "not verified" instead of passing. A change to the bands or
  the tokens makes the sheet stale for `check`, and a run that stops on a band error records the failure.
- A last size band with a `max_px` (so nothing would draw a larger size, and the emitters would crash there) now exits 2
  with the reason: the last band covers every larger size.
- A small accent that fails the 4×4 rule on purpose (a row of 2 px cells that reads as a row) no longer blocks `check`
  forever: `qa/rules.json` takes an exemption for one master up to a size, with your reason. The miss is then a warning that
  carries the reason; another master's miss still fails, and an exemption that excuses nothing is reported.
- `downscale` says when its master is one size band's drawing: which sizes ship another drawing, and that those are measured
  as shipped with `--png`. Its other rows still show what a system that shrinks the one master (an app icon) would make of it.
- `state` counts round 0 as a real round: `state --json` reports `latest_round` as `r0` for a project whose only round is
  the style board, instead of none.
- `state --set reset_rounds=[2,3]` saved the text "[2,3]" instead of a list, and `board-lint` read it one character at a time,
  so `[10,11]` meant rounds 1, 0, 1 and 1. `state --set` now writes a real list for `reset_rounds` and `book_chapters`
  (`reset_rounds` takes whole numbers from 1 and exits 2 for anything else), and a project that still holds the quoted text
  reads right too, `"[10,11]"` as rounds 10 and 11.
- `state --set "reset_rounds =2,3"` (a space before `=`) skipped the checks and wrote a key that left the state file unreadable.
  Spaces around the key and the value are now trimmed, and a key that is not one word exits 2.
- `board-lint rounds/r2/board.html --round 1` linted the page as round 1. A `--round` that contradicts the page's folder now
  exits 2.

## [0.2.3] - 2026-10-20

### Changed

- Agent descriptions no longer name the model tier ("Opus-tier", "Sonnet-tier"): each agent's `model` field holds it, and `brand-creator fleet-plan --check` no longer asks for it in the prose.

## [0.2.2] - 2026-10-20

### Added

- A commands reference page in the manual lists every command, workflow and agent, who can start each one, and its
  arguments.
- An index of the reference files the `brand-creator` skill reads
  (`skills/brand-creator/references/_index.md`), linked from the skill.

### Changed

- The README is now a short storefront. Everything else moved into a manual under `docs/manual/`: a first-brand
  walk-through, one how-to page per task, and reference pages for commands, settings, permissions, costs, agents and
  workflows, platform support, Claude Code versions and troubleshooting.
- The README's reference and development halves moved: contributor notes are in `docs/internals/`, and the build log
  and decisions log are archived in `docs/archive/`. New decisions are recorded as ADRs in `docs/adr/`.
- The plugin description is now one plain sentence: "Make a logo, colours and every brand file your product needs, step
  by step, with you deciding at each step."
- `CONNECTORS.md` uses plain words instead of internal step codes: writes to a design tool happen only after you approve
  the finished files.
- The listing text of the `brand-creator`, `brand-assets`, `brand-book` and `brand-naming` skills is shorter and in plainer
  words. When they start is unchanged, but the trigger evals have not been re-run for the new wording.
- The `/` menu descriptions of the typed-only commands (`new`, `round`, `status`, `check`, `review`, `launch`, `setup`
  and `brand-adopt`) now say in plain words what each does and end with "Runs only when typed as
  /brand-creator:<name>." `brand-adopt` also says how it differs from the adopt workflow.
- The agent descriptions keep the "Only for brand-creator workflows or an approved fleet; do not auto-delegate." opener,
  then say in one plain sentence what the agent does. The model and tools are set in each agent's own fields.
- The author in `plugin.json` is now Jacek Pytlik, and the marketplace entry carries only the name, source, category and
  tags; the description and links live in `plugin.json`.
- The trigger-eval list moved from `dev/trigger-evals.json` to `evals/trigger-evals.json`.

## [0.2.1] - 2026-10-19

### Changed

- The descriptions in Claude Code's `/` menu, skill list and agent list now say in plain words what each command, workflow
  and agent does and when it may run, instead of internal gate codes such as "G0" or "after G6". What each one does, and
  when it is allowed to run, is unchanged.

## [0.2.0] - 2026-10-19

**Breaking:** brand-creator is now listed in the `jack1913` marketplace, in `plugins/brand-creator/` of
[jack1913/claude-plugins](https://github.com/jack1913/claude-plugins). The install ID changes from
`brand-creator@brand-creator` to `brand-creator@jack1913`. Claude Code can't move an install between marketplaces, so
move it by hand:

- `claude plugin uninstall brand-creator@brand-creator`;
- `claude plugin marketplace remove brand-creator`;
- `claude plugin marketplace add jack1913/claude-plugins`;
- `claude plugin install brand-creator@jack1913`.

If you wrote a permission rule with the plugin's full path, its folder changed from `cache/brand-creator/brand-creator/`
to `cache/jack1913/brand-creator/`. The `Bash(brand-creator *)` rule needs no change.

### Fixed

- The safety hook is stricter about archives: it blocks an extract into a round, a project folder or a folder above one,
  refuses an extract it can't see into, and reads tar, unzip and 7z options the way those tools do.
- The safety hook treats `git stash push -u` or `-a` without a precise path as covering the whole working tree, so it
  can't sweep up locked rounds.

### Changed

- The README is rewritten for users: what to say, what you get, and a troubleshooting table near the top. The reference
  half is unchanged.

## [0.1.0] - 2026-10-18

The first release.

### Added

**The process.**

- The `brand-creator` skill runs a brand-identity project as phases with owner gates (G0 scope to G7 outward hand-offs, plus
  the G-sys tripwire after a third patch in one area), in three tiers: Quick, Standard and Full. It resumes from the
  project's `BRAND-STATE.md`, works for any kind of business or person, and also fires for work on a brand project's files
  and for a brand's launch steps (handed to the owner, never done for them).
- G0 asks at most three concrete scope questions (tier; architecture only when a parent brand or siblings show; the name only
  when it is open), each with a recommended answer, and states the rest as defaults. It asks once before boards are uploaded
  to claude.ai. Without a question tool, the same questions come as one plain-text message.
- Round 1 shows three divergent directions with a strategy core, a positioning map, the hardest surface, "Today" when a mark
  exists, "None of these" and numbered questions with lettered options. Directions keep stable word names; a choice is
  restated before an expensive build; the liked direction is deepened, never hybridised after the pick.
- User skills: `/brand-creator:new`, `round`, `status`, `setup` (a consented install into the plugin's data folder),
  `check` (every gate, plus `--cascade` for old values), `review` (the self-review as one approvable list), `brand-adopt`
  and `launch`. Model-invocable skills: `brand-naming`, `brand-assets` and `brand-book`.
- Phase references 00 to 13, a board contract, working-style defaults, anti-pattern case cards, a strategy core,
  architecture modes (standalone, family-member, product-in-family), a cascade checklist, regulated-industries rules and
  a synthetic worked brand (Acme).

**Checks** (each writes a report; a check that cannot run is "not verified", never a pass).

- `board-lint`, `shot` (1440 and 390 px, light and dark), `contrast` (text, UI and the colours that touch in the mark) and
  `contrast --cvd`, `logo-sheet` and `logo-sheet --guides`, `downscale` (one report per master), `states-check`,
  `family-check`, `fontcheck` with the platform-font report, `outline-glyphs`, `shot --motion`, `snapshot`,
  `verify-idempotent`, `staleness`, `specs-due`, `book-lint`, `print-check`, and `check`, which gates them all and verifies
  the frozen history's checksum manifest.
- Owner thresholds in `qa/rules.json` and size bands; the plugin's numbers are proposals.

**Tokens and assets.**

- Design tokens from DTCG 2025.10 sources to CSS, JSON, Swift, Android XML and colour sets.
- `emit web` (favicons drawn per size band, PWA icons, head snippet), `emit social` (social card, GitHub and README header
  images; `--posts` for carousel, square and educational posts), `emit profiles` (circle-safe avatar and banner images inside
  each platform's safe area).
- Platform packs for the Full tier, every size read from `scripts/emitters/platform-specs.json` with its source, date and
  status: Apple (an Icon Composer `.icon` compiled by actool per platform, legacy sets, visionOS, watchOS and tvOS; macOS with
  Xcode only), Windows, Linux, tray, Tauri, Wallet, developer, Android (adaptive icon with a monochrome layer and a 66 dp
  safe-zone gate), Chrome extension and MSIX. Files built from a size not yet read at the platform's own page are labelled
  `UNVERIFIED, recheck`, and `check` fails a file that lost the label.
- `templates/finish.sh.tpl`: the whole build chain in order, each step gated by the tier.

**Brand book, print and press.**

- `book` builds one self-contained `book.html` (a short guide in Quick, the whole book in Standard and Full), byte-identical
  on rebuild, with computed counts and ratios; `book-pdf` exports an RGB proof; `patch` edits a hand-authored book with counted
  replacements; `collapse` removes losing variants with a dated copy.
- `emit print`: business card, letterhead and envelope (EU, US or JP sizes, bleed, crop marks, outlined text, boxes set) and an
  HTML e-mail signature. Without the printer's profile a file is an "RGB proof, not print-ready", with it only a "PDF/X-4
  candidate". `emit presskit` writes a deterministic zip.

**Naming.**

- `brand-creator names` screens names against domain registries and, for software brands, package registries, and reports
  REGISTERED, NOT-FOUND or UNKNOWN, never "available". It asks before sending names anywhere, saves raw responses for
  replay and links trademark searches for the owner to run. The `brand-naming` skill writes a go / go-with-conditions / no
  verdict memo.

**Adoption and launch.**

- `adoption survey` reads product repositories read-only and writes `ADOPTION.md` as numbered, append-only rows;
  `check --cascade` finds leftovers of an old value across every project file; opt-in `BRAND.md` and `DESIGN.md` adapters and
  a per-brand applied skill; `launch-todo` writes `LAUNCH.md` from local files only.

**Agents and workflows (opt-in).**

- Seven agents (`brand-designer`, `brand-judge`, `brand-reviewer`, `brand-researcher`, `brand-inventory`,
  `brand-implementer`, `brand-namer`), none of which can start other agents or is delegated to automatically, and four
  workflows (`directions`, `review-panel`, `naming`, `adopt`), each ending before an owner gate. A fleet runs only after the
  owner has been told the agent count, models, size and rough cost and said yes; `fleet-plan` dry-runs one with stub agents.

**Safety.**

- A hook keeps `history/` and earlier rounds read-only and stops a brand project folder from being deleted or moved (shell writes,
  deleters, destructive git, and archive extracts it cannot see into are blocked, failing closed when unsure); the RULES
  line in every skill, agent and workflow forbids commits, pushes, deletes and outward actions unless asked.

**Platforms and tests.**

- Tested on macOS; the suite and the end-to-end smoke also run on Linux in a container (`tests/docker/`). Windows is untested.
- pytest and node:test suites with mutation tests for each gate, the Acme end-to-end smoke, a Quick-tier smoke on a PATH with no
  Apple tools and no git, 17 behaviour evals (`evals/`, billed, run by hand) and trigger evals (`dev/trigger-evals.json`),
  and a CI workflow (Linux, `claude plugin validate --strict`, macOS) that runs once the repository is pushed.

Known limits at 0.1.0:

- Windows has never been run. On Windows the safety hook needs `python3` on PATH.
- The behaviour evals were run once (2026-10-18); see [Evals](docs/internals/evals.md) for the results.
- Some platform sizes are unverified and labelled so; recheck them with `brand-creator specs-due`.
- In Quick, `emit social` also writes GitHub and README header images, and profile images need Standard.

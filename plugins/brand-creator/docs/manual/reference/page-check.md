# Page check

Look up a line of the page check here; the steps are in [Check a page against your brand](../use/check-a-page.md).
Someone else builds your site? Give them this page too.

Your **brand project** is the folder Claude made when you started. In it, your **design tokens** are your colours,
fonts, sizes and movements, written so a program can read them, and `FACTS.md` holds the **facts** you confirmed.

## What it opens

- **A page in your brand project.**
- **A site built elsewhere on your computer:** its folder, often called `dist` or `build`. The check opens a copy,
  without `.git` and `node_modules` (developer tool folders), so your site is only read. Over 5,000 files or 200 MB is
  refused: give the finished site's folder alone.
- **A `localhost` address,** such as `http://localhost:3000/`: your own computer, showing the site while someone works
  on it. `127.0.0.1` and `[::1]` work too; other addresses are refused.

It opens the page 360, 390, 768, 1024, 1440 and 1920 pixels wide, in light and dark, or at widths you choose: whole
numbers from 200 to 4000, none twice. It sends nothing online and never changes your page.

## The result

Claude's reply starts with a number:

- **0, PASS:** nothing failed or was skipped. Warnings may remain.
- **1, FAIL:** a line failed.
- **2:** the check did not start, and says why.
- **3, NOT-VERIFIED:** nothing failed, but a part could not be checked.
- **3, with an error and no lines:** it could not run. Ask Claude to build your design tokens, or type
  `/brand-creator:setup`.

Each line starts with PASS, FAIL, WARN, INFO or SKIP. A failing line says what, where, the first size it was seen at,
and what to change. A warning never fails the page. SKIP says why a part was "not verified", and is never a pass.

Claude then lists the fixes. Pick yours, or pass the list to whoever builds your site; Claude changes nothing unasked.
Then check again.

## What fails a page

### Loading

At each size and theme, the page loads with no error, finds all its own files, and asks nothing of another website (at
a `localhost` address, that only warns).

### Colours

Every colour the page paints, in text, backgrounds, borders, lines and drawings, is one of your brand's colours for that
theme. A colour may be off by up to 2 out of 255 in each of red, green and blue. A see-through colour must match a
brand colour just as see-through.

### Contrast

Contrast is how strongly text stands out from its background, up to 21 to 1 for black on white.

- Text and background pairs your brand approved are not measured again.
- Other text fails under 4.5 to 1, or under 3 to 1 if large: 24 pixels and up, or bold from 18.66 pixels.
- A pair that passes still warns, so you can ask Claude to approve it.
- Text on a picture or a gradient (a colour blend) warns "not verified".

### Fonts

- Every text is in a font your tokens name, really drawn by the browser. A page that sets no font fails.
- A font that did not load fails, as does one the page does not bring and this computer lacks. A common system font,
  such as Arial, Helvetica or Roboto, then only warns "not verified".
- A few characters drawn in another font warn.
- Text in your display font, for big headings, is at least 20 pixels (a proposal until you set your own), unless it
  is also your body font.

### Motion

Your motion tokens are your brand's durations and easings (how a movement speeds up and slows down).

- Every movement uses them. A built-in easing such as `ease` counts only if one of your tokens is the same curve.
- A page that moves while your brand has no motion tokens fails.
- Movement tied to scrolling, and animations inside an SVG drawing, warn "not verified".

### Logo

Only a logo that shows is judged.

- **The file:** an exact copy of one of your logo files, in `assets/logo/` or a small-size version your project
  lists. A logo written into the page's code (an inline SVG) is compared on its drawing alone.
- **The version for its size:** if your logo has simpler drawings for small sizes, each logo is the one made for its
  height. A wordmark or lockup (your name, alone or beside the logo) is not judged here.
- **Clear space:** nothing nearer than a quarter of the logo's height, a proposal until you set your own.

## How your logo is recognised

- **Marked:** the page's code labels it `data-brand-mark`. If the label names a file
  (`data-brand-mark="assets/logo/mark.svg"`), the logo must be that file or its `-dark.svg` version. A logo written
  into the page's code is found only this way.
- **By name:** the file name before the dot is `logo`, `mark` or `wordmark`, alone or followed by `-`, `_` or `@` and
  more (`logo@2x.png`, not `partner-logo.svg`). `mark` and `wordmark` count only for `.svg` files, so a photo called
  `mark-kowalski.jpg` is not a logo.
- **By content:** an exact copy of a logo file, whatever its name.

## What counts as a claim

A claim is something the page states as true: a number, such as a price, an opening hour or a date, or a status word
such as "coming soon". Each needs a fact, so the page promises nothing you haven't confirmed. To fix one, give Claude
the fact and its source for `FACTS.md`, mark a placeholder as a [sample](#samples), or remove it.

Wording you approved for use on the page, such as a headline, goes in its own row of `FACTS.md`, labelled `copy:` and
its place (`copy: hero headline`), apart from the plain fact. Its text backs a number or status word like any fact.

The check only looks for the same number anywhere in your facts. Easiest: write the fact as the page does; "open
7:00–18:00" backs those hours.

Text is Polish or English only when the page's code says so (its `lang` setting).

### Numbers

- A claim is a number of two digits or more (`49`, `1.5`), or one digit with `%`, a currency or a unit: `5 zł`, `€5`,
  `3 kg`, `4K`. Currencies: `€`, `$`, `£`, `zł`, `PLN`, `EUR`, `USD`, `GBP`, `CHF`.
- Not a claim: one digit alone ("step 1"), a digit inside a word (`mp3`, `A4`), or a version written with a v
  (`v1.2.3`).
- `1 200`, `1,200`, `1.200` and `1200` are one number; so are `12,5` and `12.50`.

### Dates written with numbers

- `17.10.2026` needs 2026, 10 and 17 in your facts, in any form. Leading zeros and a Polish `r.` after the year don't
  matter.
- `2026-10-17` is three separate numbers, each needed as written: `2026-05-07` needs a fact that writes `05` and `07`.
- With no year, a date needs two digits each side: `30.10` needs 30 and 10, or the decimal 30.1.
- `12.5`, `2.10` and `4.5 kg` are plain decimals: a fact must hold that number.

### Dates written with a month name

In Polish or English text, "21 października 2026", "w październiku 2026" and "October 21, 2026" are each one date.

- Its day, month and year must be in your facts, in any form: "premiera 2026-10-21" backs all three.
- Polish month names count in any letter case. English ones need a capital ("may" is a word).
- A one-digit day still counts, so "ul. 3 Maja" needs a fact.

### Numbers that are never claims

- **A copyright year:** 19xx or 20xx right after `©`, `(c)` or "copyright", and the end of a range ("© 2024–2026").
- **An error page's code,** 400 to 599, standing alone, anywhere on that page. A page is an error page when its file
  is named after the code (`404.html`), or its title or main heading holds the code as its only number, with no "+",
  and an error word in its language right beside it, as in "Error 404", "404 Page Not Found", "Not Found (404)" or "404 · Nie znaleziono" ("Gone in 450
  seconds" is a count). Only spaces, dashes and similar separators (- – — · • | : /), brackets round the code and the
  words "page", "site", "strona" and "witryna" may stand between them:
  - English: error, not found, forbidden, unauthorized, unavailable, gone, bad request, server error;
  - Polish: błąd, nie znaleziono, nie istnieje, brak dostępu, odmowa dostępu, niedostępna, niedostępny.

Phone numbers, postal codes and street numbers are still claims, like any other number.

### Status words

A status word is backed when one of your facts contains it.

- English, on every page: coming soon, launching, launches, launched, now live, live now, available, in development,
  in beta, going live, pre-order, open for orders, shipping soon.
- Polish, on Polish text: wkrótce, dostępne, dostępny, dostępna, w przygotowaniu, w budowie, premiera, przedsprzedaż,
  nowość.
- On text in another language, or with none set, status words warn "not verified".

### What is not read

- Text the page does not display at all, such as a closed fold-out box. Text only made invisible or see-through is
  read.
- Text kept in the page's code: picture descriptions (alt text), tooltips, labels read out to blind visitors, hints in
  empty fields, drop-down choices, the browser-tab title, and text added by styles.

## Samples

A sample is a placeholder, such as a made-up price; its text is not a claim. Ask Claude to mark it, or put
`data-sample="<what it stands for>"` on that part of the page's code.

- A sample with no label fails, and its text is checked.
- A labelled sample passes the claims check. The page needs no visible badge or note; the label in the code is enough.
- The result lists your samples: what to replace before you publish.
- A box marked as a sample sets off no mock-up warning.

## Forbidden words

The words listed as bullets under a "Forbidden" heading in your brief (`brief/BRIEF.md`) and in `research/cliches.md`
are the ones your brand never uses. The brand book's check uses this list too.

- The check looks for each as a whole word, in any letter case, in the text the page displays. "revolutionary" is found
  in "A Revolutionary tool", not in "revolutionaryx".
- A word found warns and names where, with the text around it. It never fails the page. A word inside a sample is found
  too, and the line says so.
- With a list and no word found, the line passes. With no list, the line is INFO and says nothing was looked for. It is
  never a pass.
- The list is part of what makes a report go out of date: add a word to your brief, or to `research/cliches.md` if it
  was there when you checked, and the old report reads as stale until you check again.
- The page check uses the words under "Forbidden" in the brief and in `research/cliches.md`. The brand book check adds the
  forbidden words set in the book's own settings; the page check does not.

## Template warnings

Patterns that make a page look like any template. Each warns and says where; it fails only as
[a page rule](#your-page-rules).

- **An eyebrow over a heading:** at most 4 words right above an `h1`, `h2` or `h3`, smaller than it, in capitals or
  spaced out by 0.05 em or more.
- **An arrow glued to a link or button label:** the label starts or ends with an arrow, `›`, `»`, `->` or `=>`, one
  space or none away. An arrow alone doesn't count.
- **A run of middle dots between items:** two or more dots or bullets, such as `·`, between items on one line, not
  starting list lines.
- **A stock label on the hero's second action:** the second button or link of the hero, the top block around the main
  heading, before you scroll and outside the menu, is a stock label such as "Learn more" or "Dowiedz się więcej".
  Other languages warn "not verified".
- **A hero that carries too much text:** over 45 words before you scroll, the menu not counted.
- **A product mock-up made of styled boxes:** a screen drawn instead of shown: a box of 240 by 160 pixels or more
  holding 8 or more boxes with a background or border, and no video, drawing area or picture over 48 pixels. Tables,
  checklists, timelines and boxes holding the main heading or several headings don't count, and neither does a band of
  the page, a section with its own heading: the boxes inside it are still checked.
- **Three equal tiles in a row:** at 1024 pixels wide or more, exactly three blocks side by side, of equal width and
  similar height, each with a heading.
- **A form drawn rotated:** a form, or a field, drop-down, text area or button of a form, turned by 0.1 degrees or more
  either way, by its own turn or by one of the boxes round it, such as a form on a tilted paper sheet. Forms are never
  tilted: a tilted field is harder to read and to use. A form on a tilted sheet is one warning, naming the form and the
  box that turns it. A tilted picture or card with no field in it doesn't count, and neither does a button outside a
  form. A skew, a 3D turn or a mirrored form isn't measured. If the page has more than 100 turned forms or fields, the line says "not
  verified" beyond the first ones.

## Boxes left behind by a movement

A movement can carry a box away and never hide it, so a sheet or a card stays on screen where it does not belong. No
other check looks for a box left outside its place, and none looks at a tall window. This one waits for the movements
that end, then looks at where everything stopped. It warns when a box that still shows lies:

- completely outside the box that holds it, by 8 pixels or more, or
- completely off the screen, past its left, top or right edge, by 8 pixels or more. The edges are those of the page, so
  a page that is already scrolled when it is checked is judged as it is at the top.

It leaves alone a box its holder cuts off completely, a box that stays put on the screen as you scroll, and a
see-through or hidden box. A "skip to content" link parked off the screen until a key brings it back doesn't count
either.

It also looks at each width again in a window 1300 pixels high, so a problem that only shows on a tall screen is found (once for each width, in the first colour scheme you check).
The open page is made taller, not loaded again: a page whose script reads the window height only once, as it loads, is
not seen as it would be on a tall screen.

If a page has more boxes out of place than the check lists (100), the line says "not verified" beyond the first ones.

If something still moves when the check looks, such as a movement that never ends or one that follows the scroll
position in the page's styles, the line says "not verified": the check can't tell where that box comes to rest. Like
the template warnings, this one never fails a page unless you make it [a page rule](#your-page-rules).

## Your page rules

Ask Claude to make a brand rule, such as "one logo per screen", a page rule. It quotes one of your system rules (the
short list you approve once your colours and fonts are set): the whole line, or at least two meaningful words. Until
you approve that rule, breaking the page rule only warns; then it fails.

- **Most logos in one screen:** a screen is one window high, starting at the top and every half window down.
- **Most words on a button:** buttons, anything marked as one, or what the rule names: the words you see or, with
  none, those read out to blind visitors.
- **Words around an accent:** around each part the rule names, the other words of its block stay within limits.
- **A template warning, made a rule.**

A number is one word, "e-mail" two, a symbol none.

## Where the reports are kept

- One per page, in `assets/_checks/page-check/` of your brand project, replaced at each check. Claude reads it for you.
- It goes out of date when your tokens, facts, approved rules, logo files or the check's settings change or, for a
  page in your brand project, the page or a file it loaded. Then check again.
- `/brand-creator:check` reads the reports of the pages you approved in `site/`: a failing one fails it, a missing or
  outdated one makes it "not verified".

## Old copies of a built site

Each check of a site built elsewhere leaves a copy of its folder that nothing deletes. Old copies are safe to delete:
your site and reports are not there.

- **Where:** in the plugin's data folder, normally `~/.claude/plugins/data/brand-creator-jack1913/` (`~` is your home
  folder), under `scratch/<your project>-<code>/page-check/<code>/`, one numbered folder per check.
- **On a Mac:** `.claude` is hidden. In Finder, choose Go > Go to Folder, paste the path, press Return.
- **What to delete:** numbered folders you no longer need, or the whole `page-check` folder.

## What it cannot see

What is inside a frame (a page within the page), colours in gradients and shadows, movement a script starts when the
visitor clicks, types or scrolls (a box that shows only once you scroll to it is not judged until it shows, and the
check never scrolls), or draws frame by frame, and how colour-blind visitors see the page.

## Related

- [Check a page against your brand](../use/check-a-page.md)
- [Commands](commands.md)
- [Troubleshooting](troubleshooting.md)

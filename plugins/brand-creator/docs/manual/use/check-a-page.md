# Check a page against your brand

Open a page in a real browser and see where it breaks your brand: a colour that is not yours, a font that is not yours, a
squeezed logo, a number nobody backed. Use it on a page built with Claude or by hand, in your project or anywhere else on
your computer.

## Before you start

- You have a brand project whose colours and fonts are built into [design tokens](../reference/glossary.md). If they are not,
  the check stops and says so (see [If something goes wrong](#if-something-goes-wrong)). New here? See
  [Start a brand](start-a-brand.md).
- brand-creator is set up, so the browser it uses is installed. `/brand-creator:setup` does that.
- The page is on your computer. A page on another website is not checked: build it here first.

## What it checks

The page is opened at six widths, from a phone to a wide desktop, in the light and in the dark theme. Every request to
another website is stopped, so the check runs offline. It reports on:

- **Colours:** every colour the page paints is one of your brand's colours for that theme.
- **Contrast:** every text on its background is a pair your brand declares, or is measured for contrast.
- **Type:** every text is set in your brand's fonts, the browser really drew them, and your display face is not too small.
- **Logo:** it is one of your logo files, the drawing made for its size, with clear space around it.
- **Motion:** every duration and easing is one of your motion tokens.
- **Claims:** every number and status word, such as "coming soon", is backed by `FACTS.md` or marked as a sample.
- **Your page rules:** rules you added for pages, such as one logo per screen or at most three words on a button.

A failure in any of these fails the check.

It also warns about patterns that make a page look like any other template: a small capital label above a heading, an arrow
glued to a button label, a line of items joined by dots, a stock label such as "Learn more" on the second button of the
hero, a hero with too much text, a mock-up built from styled boxes instead of a picture, and a row of three equal tiles. A
warning never fails the page. Stock labels are checked in English and Polish; on a page in another language the check says
"not verified" for them.

## Check a page

1. Type the command with the page:

   > /brand-creator:check --page pages/index.html

   - A page in your project: give its path.
   - A site built somewhere else on your computer: give the page, and say where the site's folder is if Claude asks. The
     folder is copied into a scratch area and only the copy is opened, so your site is never touched. Every check keeps
     its copy: see [Old copies of a built site](#old-copies-of-a-built-site).
   - A page your computer serves while you work on it: give its address, such as `http://localhost:3000/`. Only addresses
     on your own machine work (`localhost`, `127.0.0.1` or `[::1]`).

2. Claude opens the page at each width and theme, which takes a little while. To go faster, ask for fewer widths, for
   example "only 390 and 1440".
3. Claude reports the result: 0 if the page passes (warnings allowed), 1 if a row failed, 2 if the command was used wrongly
   and 3 if the check could not run. Each failing row names what it found, where on the page and the fix.

You'll see something like this:

```text
[INFO] page:target (what was checked): project page pages/index.html; widths 390, 1440; schemes light, dark; …
[PASS] page:load:390-light (390px light): loaded at 390x844, … no page or console error, no failed or outside request
[PASS] page:colours:light (light theme colours): 3 distinct colour(s) painted, each a semantic colour of the light theme
[WARN] tell:eyebrow (An eyebrow over a heading): 1 found: body > main > small: "NEW", in capitals, 11 px over the h1 … (at 390, 1440 px); …
[WARN] tell:stock-second-action (A stock label on the hero's second action): 1 found: … the second action of the hero says "Learn more" …
page-check/index-6afd7f: PASS  (16 pass, 0 fail, 2 warn, 0 not verified)  renderer: chromium
report: …/assets/_checks/page-check/index-6afd7f.json
```

One report is kept per page, in `assets/_checks/page-check/`. Checking the same page again replaces its report.

## Old copies of a built site

Each time you check a site built somewhere else, Claude makes a new copy of its folder and opens that copy. Nothing
deletes the copies, so they pile up. A page in your project makes no copy.

- **Where they are:** in the plugin's data folder (on a normal install `~/.claude/plugins/data/brand-creator-jack1913/`),
  under `scratch/<your project>-<code>/page-check/<code>/`. Each check has a numbered folder there: `1`, `2`, `3` and so
  on, holding the copy of your site.
- **What to do:** delete the numbered folders you no longer need, or the whole `page-check` folder under `scratch`. Your
  site and your reports are not there, and the next check makes a new copy.

## Mark what is only a sample

A page built before the real content exists is full of made-up numbers and names. Mark each made-up piece with a label, so
the check passes it and lists it for you:

```html
<p data-sample="price from the pricing table">From 49 a month</p>
```

The check passes a labelled sample and lists every one of them in the row `page:samples`: that is your list of what to
replace before you publish. An unmarked number or status word that `FACTS.md` does not hold fails. The fix is to add the
fact to `FACTS.md` (only a fact you confirm) or to mark the text as a sample.

Some numbers are not claims, so you do not need a fact for them:

- A year after a copyright sign or the word, such as "© 2026" or "Copyright 2024–2026".
- The code of an error page. A page whose title or main heading says "Błąd 404" can show a large "404".

A date is read as its numbers, in either form. The fact "premiera 2026-11-15" backs "Premiera 15.11.2026", and "Wypłata
30.10" needs a fact that holds 30 and 10. A number with spaces between thousands, such as "13 205,20 zł", counts as one
number.

Phone numbers, postal codes and street numbers are still claims. Each one needs a fact in `FACTS.md`, or a sample label.

To have your logo judged, mark it with `data-brand-mark` on its `img` or inline `svg`, or give its file a name such as `logo.svg`.

## Turn a warning into a brand rule

If a pattern should never appear on your pages, make it a rule:

1. Ask Claude, for example "make the eyebrow a rule".
2. Claude adds the rule to `qa/rules.json` and ties it to the words of one of your system rules, such as "no eyebrow over
   a heading".
3. Until that system rule is among the ones you approved, a page that breaks it only gets a warning that says so. Once it
   is approved, the same page fails the check.

The same works for your own rules about pages: one logo per screen, at most three words on a button, or how many words
sit around an accent.

## Check it worked

- The reply ends with the exit code and the report path, and no row you did not expect is failing.
- Every row either passed, warned, or says "not verified" and why. A row that did not run is never counted as a pass.
- After you fix a page, run the same command again. A report goes stale when the page, a token or `FACTS.md` changes.

## If something goes wrong

| You see | Do this |
| --- | --- |
| Code 3 and "assets/tokens/tokens.json is missing" | Your tokens are not built yet. Ask Claude to build them, then check again |
| Code 3 and a message about Chromium or setup | Run `/brand-creator:setup`, then check again |
| Code 2 and "page-check runs offline" | The address is not on your computer. Build the site here and give its folder, or serve it locally |
| A colour row fails and names a colour | The page paints a colour that is not one of your colours for that theme. The row gives the nearest brand colour. Use the token, or change the token if the brand changed |
| A claims row fails | A number or status word has no fact behind it. Add the fact to `FACTS.md`, or mark the text as a sample. A phone number, postal code or street number needs one too. A copyright year and the code of an error page do not |
| A font row says "not verified" | The check could not tell which font the browser drew, for example a system font this computer does not have. Load the font with the page and check again |

More: [Troubleshooting](../reference/troubleshooting.md).

## Related

- [Check your project](check-your-project.md): the checks for the whole project, and leftover searches
- [Apply the brand to your product](apply-the-brand-to-your-product.md): change your product repositories, only when you say go
- [Commands](../reference/commands.md): the `check` arguments

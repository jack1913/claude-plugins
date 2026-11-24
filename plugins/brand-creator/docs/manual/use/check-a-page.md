# Check a page against your brand

Built a page yourself, or had someone build one? The page check opens it in a browser on your computer and shows where
it breaks your brand. Use it before you publish, and again after each fix.

## Before you start

- You have a brand project, the folder Claude made when you started, with your design tokens in it: your colours,
  fonts and sizes, written so a program can read them. New here? Start with [Start a brand](start-a-brand.md).
- The tools are installed. If you have never done it, type `/brand-creator:setup` once.
- The page is on your computer. The check never opens pages on the internet, such as a page in a website builder.
  Save its files to your computer first, if you can.

## What it checks

The check opens your page at several sizes, from a phone to a wide screen, in light and dark. It fails the page for:

- a colour or font that isn't yours, or an animation that doesn't move the way your brand does;
- text that is hard to read, or your heading font set too small;
- a logo that isn't one of your logo files, is the wrong version for its size, or is crowded;
- a claim such as "500 happy customers" or "coming soon" that is not in `FACTS.md`, the list of facts you confirmed in
  your brand project, and not marked as a sample;
- a page rule you asked Claude for and approved, such as one logo per screen or at most three words on a button.

Failing blocks nothing: it gives you things to fix. The check also warns about patterns that make a page look like any
template, such as a small label in capitals over a heading, and about any word your brand forbids: the words you
listed under "Forbidden" in your brief. Warnings never fail the page. The exact rules are in
[Page check](../reference/page-check.md).

## Check a page

1. In your chat with Claude, in your brand project, type the command and your page:

   > /brand-creator:check --page pages/index.html

   That is the home page, `index.html`, in the folder `pages`. Your page can be:

   - **in your brand project:** give its file, as above;
   - **a site built somewhere else on your computer:** give its page. Claude asks for the site's folder, often called
     `dist` or `build`. The check opens only a copy, so your site is never touched;
   - **shown by your computer while someone works on the site:** give its address, such as `http://localhost:3000/`.
     `localhost` means your own computer; addresses on the internet are refused.

2. Wait while Claude opens the page at each size. In a hurry? Ask for fewer, such as "only 390 and 1440" (a phone and
   a desktop, in pixels).
3. Read the reply. It starts with the result: the page passed (warnings may remain), something failed, or Claude could
   not check everything and says why. Then come the problems with their fixes, the warnings, and what Claude could not
   check.
   [Page check](../reference/page-check.md#the-result) explains every part.
4. Say which fixes you want, failures first. Claude changes nothing until you say. Then check again.

The check uses no extra agents, so it costs no more than any other chat with Claude. It sends nothing online and never
changes your page.

## Mark what is only a sample

Made-up prices on an unfinished page would each fail. Ask Claude to mark them as samples, or do it in the page's code,
with a label saying what each one stands for:

```html
<p data-sample="price from the pricing table">From 49 a month</p>
```

A labelled sample passes, and goes on your list of what to replace before you publish.

For a real number, tell Claude the fact and its source, and Claude adds it to `FACTS.md`. A copyright year, or the
"404" on a "page not found" page, needs no fact. Phone numbers, postal codes and street numbers do: to the check they
are numbers like any other.

## Keep approved wording apart from facts

A fact and the words that present it are not the same thing. Keep the fact in `FACTS.md` as it is: "shipping takes 3
days". When you approve wording for a headline, ask Claude to add it as its own row, labelled `copy:` and the place it
is for, such as `copy: hero headline`. A page then quotes that row, or uses new wording you approve first, and never
a fact copied word for word into a headline. A number in an approved row counts as backed, like any fact.

## If a word on the page is one you forbade

If your brief lists forbidden words, the check looks for each on the page, in any letter case, and warns where it finds
one, with the text around it. Reword it, or tell Claude the word may stay. Nothing fails for it. With no list, the
check says it looked for nothing, and does not count that as a pass. To start a list, ask Claude to add the words
under "Forbidden" in your brief, one per bullet.

## Turn a warning into a brand rule

To keep a warning off every page from now on, make it a rule:

1. Ask Claude, for example: "make the eyebrow a rule". An eyebrow is that small label in capitals over a heading.
2. Claude ties it to one of your system rules, such as "no eyebrow over a heading": the short list of brand rules you
   approve once your colours and fonts are set.
3. Until you approve that system rule, a page that breaks it only gets a warning. After that, the page fails.

## Old copies of a built site

Each check of a site built somewhere else leaves a copy of it in the plugin's data folder, and the copies pile up.
Old ones are safe to delete: your site and your reports are not there.
[Page check](../reference/page-check.md#old-copies-of-a-built-site) says where they are.

## Check it worked

- The reply says the page passed.
- Anything Claude could not check says "not verified" and why. It never counts as a pass.

## If something goes wrong

| You see | Do this |
| --- | --- |
| `assets/tokens/tokens.json` is missing | Your design tokens aren't made yet. Ask Claude to build them |
| A message about the browser or setup | Type `/brand-creator:setup`, then check again |
| The check won't start and says "page-check runs offline" | The address is not on your computer. Give the site's folder, or a `localhost` address |
| A problem names another website | The page fetches a font or picture from the internet. Keep that file with the site's files |
| A font marked "not verified" | This computer lacks a common font your brand uses. Have the page bring its own copy of the font |

More: [Troubleshooting](../reference/troubleshooting.md).

## Related

- [Page check](../reference/page-check.md): the exact rules, the result, and where files are kept
- [Check your project](check-your-project.md): the checks for the whole project

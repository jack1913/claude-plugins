# Make your ads and decks

Your ads and your presentation deck are the pieces people see most after your website. brand-creator makes them as
**masters**: approved ads in every size you need and a deck, each one the starting point for every new ad or
presentation. Claude builds them from your brand's own world, checks every file, and you pick and approve them.

## Before you start

- You're on the Standard or Full tier. `/brand-creator:status` shows your tier.
- Your system rules are approved (the step after your logo and colours).
- Your site's pages are approved, if you're making a site. The masters then speak your site's language.

## 1. Ask for the masters round

Say what you need, for example "make our ads and a deck", or type `/brand-creator:round masters`. Tell Claude the ad
sizes you use (for example 1080 × 1350 for Instagram, 1200 × 628 for links) and whether you need the deck in PowerPoint.

Claude builds two or three directions, each in every size. You get one page that shows them side by side, with
Claude's pick and an honest weak point.

## 2. Pick a direction

Answer with the direction's name or the question's letter, for example "1a". Add one sentence on anything you want
changed. Claude makes a new round with your changes when you ask for one.

## 3. Open the PowerPoint deck in PowerPoint

When there's a PowerPoint deck, open it in **PowerPoint** and tell Claude whether it looks right: your fonts, and nothing
overlapping. Claude can't open PowerPoint for you. Keynote and Google Slides aren't a good test: they ignore the fonts
inside the file and show a substitute.

## 4. Approve them

Say you approve, with your PowerPoint answer, for example "approve Kalendarz; PowerPoint looks right". Claude records it and
copies the masters into your brand project's `assets/masters/` folder, with a `README.md` that lists each file, its size,
your copy rules and how to rebuild them. Your brand kit carries them to your product next time it's built.

## What Claude checks for you

Before you see a master, Claude has checked every file:

- nothing sticks out past the edge of the ad or slide;
- no text runs into another text, and nothing covers a word by accident (a stamp drawn over text on purpose is allowed and
  listed);
- the deck's PDF has one page per slide, at the right size;
- the PowerPoint file keeps every box on its slide and carries your fonts inside it.

## What it never does

- It never opens PowerPoint, Keynote or any other app on your computer.
- It never puts amounts or names in your ads unless your facts hold them; sample figures in the deck are labelled as sample
  data.
- It never replaces approved masters without asking: a new approval moves the old ones to a `removed-` folder.

## Check it worked

- `assets/masters/README.md` lists your masters and the date you approved them.
- When your site is approved after your masters, Claude's project check says the masters are older than your site and
  offers a new round.
- After new masters, the brand kit check names your ad and presentation recipes until they're read against them.

## If something goes wrong

| What you see | What to do |
| --- | --- |
| "a text runs into another" | Claude moves or resizes the text in the master, then checks again |
| The PowerPoint row is "not verified" | Open the deck in PowerPoint and tell Claude what you see |
| "the masters report is stale" | A master changed after the check: Claude checks the round again, then approves |
| A font is "not embedded" | Claude embeds your font files in the deck; a font whose licence forbids it can't go in |

## Related

- [Get reference pages for your site](get-reference-pages-for-your-site.md): the site the masters follow
- [Use your brand kit](use-your-brand-kit.md): how the kit carries your masters
- [Make the brand book](make-the-brand-book.md): the book's "Ads and decks" chapter

# Get reference pages for your site

Get sample pages of your website, in your brand, before anyone builds the real one. You see how the best sites for your
kind of visitor work, then Claude builds the first screen of your home page and your other pages. You don't need a
website yet.

These are reference pages, not your live website: they stay on your computer, and Claude never publishes anything. They show whoever
builds your real site, you or someone you hire, what your brand decided and what was only one example.

## Before you start

- **Your tier is Standard or Full**, not Quick. Your tier is how far your project goes. `/brand-creator:status` shows
  yours. [Choose a tier](../getting-started/choose-a-tier.md) explains them, and how to move up.
- **Your brief lists a site.** The brief (`brief/BRIEF.md`) holds the notes about your business that Claude wrote from
  your answers at the start. Its "Required surfaces:" line lists where your brand must show up, such as a site or an app
  icon. No site there? Ask Claude to add it.
- **You said go to your brand's rules:** the one list, such as which colours text may sit on, that Claude showed you
  after you settled whether your logo moves. `/brand-creator:status` shows whether that is done.
- **Setup is done.** If you never ran it, type `/brand-creator:setup` once. It asks first, then downloads a separate
  browser into brand-creator's own folder, for taking pictures of sites and pages. Your own browser stays as it is.
- **For the research, Claude can go online.** If not, send links or screenshots.

Everything lands in your brand project: the folder Claude made when you started, the one holding `BRAND-STATE.md`. It
takes at least three rounds (a round is one board and your answer), and runs in your own Claude session, so it costs
what any session that long costs.

## 1. Show Claude sites you like

Nothing on your site is built until you have seen how other sites do the same job.

1. Type this, or ask for references for your site in your own words:

   > /brand-creator:round site-refs

2. Claude asks once whether it may look at sites online. Searching tells search services what your business does, and
   opening a site tells its owner that someone looked. So you choose:
   - **Research the best real sites for this kind of visitor, and open the ones I name.** Claude recommends this.
   - **Only the sites I give you.** Claude searches nothing.
   - **No web.** You send screenshots, or skip the references.

   Claude keeps your answer and does not ask again. Tell it if you change your mind.
3. Name sites you like and sites you don't, and say why. Links or screenshots both work. "None" is fine.
4. Claude shows you a board with four to six groups of real sites. They are grouped by how they help
   a visitor get what they came for, not by how they look: one simple step to sign up, say, or a catalogue to browse.
   Each site shows a screenshot, what to take (how the page is organised) and what to leave (its colours, fonts,
   pictures and words). The board also lists habits most sites like yours share, so your first screen can avoid them.
5. Tick one or more groups and copy the reply the board writes for you into the chat, or type your own. If none fits,
   say "none: research again". Claude says back your pick before it builds anything.

In a hurry? Say "skip the references", and Claude builds from your brief instead. Claude never skips this step for you.

## 2. Pick the first screen of your home page

The first screen, what a visitor sees before they scroll, sets the tone for everything else. So it comes first.

1. Type this, or ask for it in your own words:

   > /brand-creator:round site

2. If this site replaces an earlier one, Claude first lists the rules from it and asks which still stand. Answer in your
   own words, such as "keep the dark footer, drop the rest". Claude writes your answer in your list of decisions
   (`DECISIONS.md`). Only the rules you keep apply to the new pages, and a rule you drop is named as dropped. With no
   earlier site, there is no question.
3. Claude builds two or three versions. Each is organised like the references you picked (or built from your brief,
   if you skipped them), in your colours, fonts and logo. They start from what you already approved: the templates and
   pictures you signed off (your masters) are used as they are, and if your logo moves, its signature move shows on the
   first screen, or the board says why a version leaves it out. Before it builds one, Claude writes down the one idea the
   version rests on, in a line. For each one the board shows:
   - the one idea it rests on, in a line (a version should be something you can remember, not only tidy);
   - four pictures: on a phone and a desktop, in light and dark;
   - whether it keeps your brand's rules. A version that breaks one is marked as failing, never hidden;
   - anything that makes it look generic, like countless other sites (such as a small label in capitals over a
     heading), and what Claude will change or why it keeps it;
   - a verdict, "ship" (good to go) or "fix", from a review that judges only the four pictures, your brief and your
     facts (`FACTS.md`: the true things your pages may say, such as your prices).
4. Pick one, mix two ("this one, with the ending of that one"), or say that none fits and what was missing. Claude says
   back your pick and writes it down in your words.

Claude does that review itself by default, in the same chat. It built the page, so this is not a stranger's fresh look,
and the board says so. For one, ask for a separate reviewer: an extra agent, at extra cost. Claude says how many and
roughly what they cost, and waits for your yes.

## 3. Get your other pages, and say which choices are rules

1. Type the same command again. Claude builds your other pages from the first screen you picked:

   > /brand-creator:round site

2. The board lists every choice the pages make, such as the order of the sections or where the main button sits. Each
   choice has a tag:
   - **Brand rule:** you decided it, so your site keeps it, on every page unless the rule names certain pages. The board
     says where you decided it.
   - **Example:** one way the pages did it, free to change.
3. Check the tags. Claude tags a choice as a rule only when you already decided it, never for something it chose itself.
   To make an example a rule, say so. Claude first writes your decision into your list of decisions (`DECISIONS.md`),
   then changes the tag.

## 4. Approve the pages

1. Tell Claude you approve the pages and that the tags are right. A bare "ok" is not enough: Claude asks you to confirm
   both. Your yes covers every page on the board: to leave one out, ask Claude to take it off first.
2. Claude says back what you approved and writes it down. It locks a copy of the round in `history/`, so it can't
   quietly change. Then it copies each page into `site/` in your brand project, with a record of the pages and every
   choice and its tag (`site/site.json`), and checks and photographs each page again there.
3. Type `/brand-creator:check`. It confirms that no approved page changed since you approved it, that each one keeps
   your brand's rules, and that its pictures show the page as it is now.

The pages in `site/` are for whoever builds your real site: the rules are what to keep, the examples one way to follow
them. Your brand book can show them, with the tag on each choice, in an optional Site chapter. Ask for it when you
[make the brand book](make-the-brand-book.md).

## What it never does

- Build or publish your real site. That is built with your website's code, from your brand's colours, fonts and rules.
- Make a page that needs the internet. Each one uses only files in your brand project.
- Copy another site's look. Colours, fonts, pictures and words always come from your brand.
- Make up a site. Claude shows only sites it opened, and a site without a screenshot does not count.
- Look online without your yes, or open a page behind a login.
- Use another site's screenshots in anything it builds. They stay on the references board, for your own research.
- Skip a step for you.

## Check it worked

- The references board shows four to six groups, and `research/site-refs/` holds a folder of pictures for each site
  Claude opened.
- After you pick references, or skip them, `/brand-creator:status` shows it as recorded.
- If there was an earlier site, `DECISIONS.md` has an entry that names the rules you kept and the ones you dropped.
- After you approve the pages, `site/site.json` exists, and `/brand-creator:check` passes the lines about your site, or
  says "not verified" (it could not confirm something) and why.

## If something goes wrong

| You see | Do this |
| --- | --- |
| Claude says the references need web access | Let Claude go online, send links or screenshots of sites you like, or say "skip the references" |
| A site did not load, and Claude leaves it out | Send a screenshot of it, or let Claude pick another |
| A message about the browser or setup | Type `/brand-creator:setup`, then try again. Claude never runs it without your yes |
| Claude says your brief lists no site | Ask Claude to add your site to the "Required surfaces" line of `brief/BRIEF.md`. It needs a word for a site in English or Polish; in another language, add the word `site` |
| Claude says your brand's rules are not approved | Say go to the list of rules Claude shows after asking whether your logo moves. `/brand-creator:status` shows where you are |
| Claude says the references come first | Pick some references, or say "skip the references" |
| A version shows "fix" | Ask Claude to fix what the review found, or to say on the board why not |
| Claude says the pages need a first screen you picked | Pick a first screen. The other pages are built from it |
| `check` says an approved page is "not verified" | Not a failure: something the page depends on changed since its last check, such as a file it loads, your colours, your facts or your rules. Ask Claude to take its pictures and check it again |
| `check` fails an approved page | It names the page. It was changed after you approved it (put it back, or approve it again), or it breaks one of your brand's rules (fix it, then approve it again) |
| Claude says `site/` already holds approved pages | Say you want to replace them. The old pages move to a folder named `removed-` plus the date. Nothing is deleted |

More: [Troubleshooting](../reference/troubleshooting.md).

## Related

- [Check a page against your brand](check-a-page.md): check any page you built
- [What it makes](../reference/what-it-makes.md#website-references-and-reference-pages-standard-and-full): the files
  each step writes
- [Commands](../reference/commands.md): what you can type after `round`

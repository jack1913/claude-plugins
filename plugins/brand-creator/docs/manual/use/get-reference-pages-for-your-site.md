# Get reference pages for your site

See how the best sites for your kind of visitor are put together, then get the first screen of your home page and your
other pages built in your brand. The pages are references for whoever builds your real site: they show what the brand
decided and what was only one example.

## Before you start

- Your tier is Standard or Full. Quick does not include this. See [Choose a tier](../getting-started/choose-a-tier.md).
- Your brief lists a site. Claude reads only the "Required surfaces" line of `brief/BRIEF.md`, in English and Polish, so a
  site mentioned anywhere else in the brief does not count. To add one, put it on that line, in your own words. In
  another language, add the word `site` to that line.
- You settled motion and said go to your system rules, the written plan that Claude shows you after the motion answer. The
  steps before it are in [Pick and refine a direction](pick-and-refine-a-direction.md).
- For the research, Claude needs web access and the browser brand-creator uses (`/brand-creator:setup` installs it).
  Without web access you can send links or screenshots instead.

## Step 1: pick references

Nothing on your site is built until you have seen how other sites do the same job and picked the ways you like.

1. Type the command, or ask for references for your site in your own words:

   > /brand-creator:round site-refs

2. Claude asks once whether it may research sites online. Searching tells search services what your brand makes, and
   opening a site tells its owner that someone looked, so the choice is yours. You can say:
   - Research the best real sites for this kind of visitor, and open the sites you name. Claude recommends this.
   - Use only the sites you give. Claude searches nothing.
   - No web. You send screenshots, or you skip the references.

   Your answer is kept in your project, so Claude does not ask again. Say so if you change your mind.
3. Claude also asks which sites you like and which you dislike, and why. Send links, or screenshots. "None" is an answer.
4. Claude opens the sites and shows you a board of four to six groups of real sites. A group is a way of doing the
   visitor's job, such as one step with nothing to compare, or stages as the visitor lives them. It is not a look. Each
   site has a screenshot, what to take (its structure and rhythm) and what to leave (its look and its words). The board
   also lists the habits most sites in your category share by reflex, so your first screen can avoid them unless it has a
   reason.
5. Tick one or more groups, or say "none: research again". Claude restates your pick before it builds anything.

To go straight to your pages, say "skip the references". Claude records that you skipped and never skips for you. Then
the pages are built from your brief and the layout references alone.

## Step 2: pick a first screen

1. Claude builds the top of your home page in two or three ways, each built from the structure of the references you
   picked and from your own colours, fonts and logo. Type the command, or ask for it in your own words:

   > /brand-creator:round site

2. Read the board. Each version comes with:
   - four pictures of the first screen: phone and desktop, light and dark;
   - a check against your brand rules, which a version that fails shows as failing;
   - the generic patterns Claude found and what it will do about them;
   - a cold review that says "ship" or "fix". It reads only the four pictures, your brief and your facts, and gives its
     verdict before any reason.
3. Pick one, combine two ("Ledger, with the ending of Atlas"), or say that none fits and what was missing. Claude
   restates your pick and writes it down with your words.

By default Claude does the cold review itself, in the same conversation, so it is not blind. The board says so. A separate
reviewer agent runs only after you see the size and cost and say yes.

Each page also records which layout reference it used: a short recipe for how a page is organised for one visitor job,
such as "understand how a service will run for them before handing it something important". It is a starting point,
never a template.

## Step 3: the other pages and your choices

1. After your pick, Claude builds your other pages from the chosen first screen, in the next round. Type the command again,
   or ask for the other pages:

   > /brand-creator:round site

2. Read the board. It lists every choice the pages make, such as the order of the sections, where the action sits and how
   a page ends. Each choice is tagged:
   - **Brand rule:** you decided it, and the brand keeps it wherever it shows a site. The board says where you decided
     it.
   - **Example:** one way the pages did it. It may change.
3. Check the tags. Claude proposes a rule only when you already decided it, and a default it chose is never a rule. To
   turn an example into a rule, say so. Claude writes your decision down first, then changes the tag.

## Step 4: approve the pages

1. Say that you approve the pages and whether the tags are right. A bare "ok" is not enough: Claude asks you to confirm
   the pages and the tags. Your approval covers every page on the board. To leave a page out, ask Claude to take it off
   the board first.
2. Claude restates what you approved and records it. Then it saves the round in `history/` and copies each page on the
   board into your project, checks it again where it now lives, and takes its pictures again:

   ```text
   site/
     site.json              the pages, the layout each used, and every choice with its tag
     <page>/index.html      one approved page
     <page>/shots/          the pictures of that page
   ```

3. Run the checks:

   > /brand-creator:check

   They confirm that no approved page changed since you approved it, that each one passes your brand rules, and that its
   pictures match the page.

The brand book can show these pages in an optional Site chapter, with every choice and its tag. Ask for it when you
[make the brand book](make-the-brand-book.md).

## What it never does

- Build or publish your real site. The pages here are references. The real site is built in your product repository, from
  your design tokens and your rules.
- Copy another site's look. Colours, type, images and words always come from your brand.
- Make up a site. Claude only shows sites it opened, and a site without a screenshot does not count.
- Research online without your yes, or open a page behind a login.
- Reuse another site's screenshot in anything it builds. The screenshots stay on the references board, for private
  research.
- Skip a step for you. Only you skip, in your own words.

## Check it worked

- The references board shows four to six groups, and `research/site-refs/` holds a folder with pictures for each site
  Claude opened.
- After your pick of references, `/brand-creator:status` shows the decision as recorded.
- After approval, `site/site.json` exists, and `/brand-creator:check` passes the site rows or says "not verified" and why.

## If something goes wrong

| You see | Do this |
| --- | --- |
| Claude says the references need web access and stops | Allow web access, send links or screenshots of sites you like, or say "skip the references" |
| A site did not load, and Claude leaves it out | Send a screenshot of it, or let Claude pick another. A site that cannot be opened is never described from memory |
| A message about the browser or `/brand-creator:setup` | Run `/brand-creator:setup`, then try again. Claude never runs it without your yes |
| The round is refused because your brief lists no site | Add the site to the "Required surfaces" line of `brief/BRIEF.md`, in your own words. In a language other than English or Polish, add the word `site` to that line |
| The round is refused because the system rules are not approved | Say go to the written plan of your brand's rules that Claude shows after the motion answer. If you have not seen it, ask Claude where your project stands. The steps before it are in [Pick and refine a direction](pick-and-refine-a-direction.md) |
| Claude says the references come first and stops | Pick references, or say "skip the references". The first screen waits for one of the two |
| A version shows "fix" | Ask Claude to fix what the cold review found, or to say on the card why it keeps it |
| Claude says the pages need a first screen you picked | Pick a first screen first. The other pages are built from it |
| `check` says the pictures or the page check of an approved page are "not verified" | Something the check stands on changed after the last run: the page or a file it loads, your tokens, your page rules, your facts, or the system rules you approved. Approving a later step, such as the book, does not. Ask Claude to take the pictures and run the page check again |
| `check` fails an approved page | The row names the page. Either it was edited after you approved it (put the approved page back, or approve it again from the round), or it breaks your brand rules (fix it and approve again) |
| Claude says `site/` already holds approved pages | Approving again moves the old pages to a `removed-<date>` folder, never deletes them, and only when you say to replace them |

More: [Troubleshooting](../reference/troubleshooting.md).

## Related

- [Check a page against your brand](check-a-page.md): the page check, for any page you built
- [What it makes](../reference/what-it-makes.md#website-references-and-reference-pages-standard-and-full): the files each
  step writes
- [Commands](../reference/commands.md): the `round` arguments

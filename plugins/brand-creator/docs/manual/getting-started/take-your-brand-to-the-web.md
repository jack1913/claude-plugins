# Take your brand to the web

Your brand has a logo, colours and fonts. Now you want a website that looks like it, and a product that stays on brand
when someone builds the next page. This page walks you through the whole road, one step at a time. Each step links to
its own page if you want more.

## Before you start

- Your logo, colours and fonts are approved. If not, start with [Make your first brand](make-your-first-brand.md).
- The tools are installed. If you have never done it, type this once:

  > /brand-creator:setup

- You know your tier: how far your project goes. Type `/brand-creator:status` and it tells you. Steps 1 to 3 need
  Standard or Full, step 6 needs Full, and steps 4 and 5 work with any tier. [Choose a tier](choose-a-tier.md) explains
  them.

Everything Claude makes lands in your brand project: the folder Claude made when you started, the one holding
`BRAND-STATE.md`.

## The road at a glance

1. Show Claude sites you like.
2. Pick the first screen of your home page.
3. Get your other pages, and say which choices are rules.
4. Check any page against your brand.
5. Get your brand kit.
6. Put the brand into your product.

You can stop after any step. brand-creator never puts anything online: you, or whoever runs your site, publish it.

## 1. Show Claude sites you like

Good sites for your kind of visitor have already solved most of your problems. Start there.

1. Type:

   > /brand-creator:round site-refs

2. Claude asks once whether it may look at real sites online. Say yes, say "only the sites I give you", or send
   screenshots instead.
3. Name a few sites you like and a few you don't, and say why. "None" is fine.
4. Claude shows you a board: a page of real sites, grouped by how they help a visitor do what they came for, such as
   booking a table or comparing prices. Each site shows what is worth borrowing (how the page is organised) and what to
   leave behind (its look and its words).
5. Tell Claude in the chat which groups you like.

In a hurry? Say "skip the references". Claude builds from your brief instead.

More: [Get reference pages for your site](../use/get-reference-pages-for-your-site.md).

## 2. Pick the first screen of your home page

The first screen, what a visitor sees before they scroll, sets the tone for everything else. So it comes first.

1. Type:

   > /brand-creator:round site

2. Claude builds two or three versions in your colours, fonts and logo. For each one you see it on a phone and a
   desktop, in light and dark, with:
   - a check against your brand's rules;
   - a short verdict, "ship" (good to go) or "fix", from a review that sees only the pictures, your brief and your
     facts.
3. Pick one, mix two ("this one, with the ending of that one"), or say what is missing.

## 3. Get your other pages, and say which choices are rules

1. Type the same command again. Claude knows where you are and builds the next part:

   > /brand-creator:round site

2. Claude builds the rest of your pages from the first screen you picked.
3. The board lists every choice the pages make, such as the order of the sections or where the main button sits. Each
   choice is marked as either:
   - **a rule:** you decided it, and every page of your site keeps it, or
   - **an example:** one way of doing it, free to change.
4. Fix any mark that is wrong, then tell Claude you approve the pages.

The approved pages go into the `site/` folder of your brand project. They are reference pages, not your live site: they
show whoever builds your real site what your brand decided.

## 4. Check any page against your brand

Built a page yourself, or had someone build one? Check it. Give Claude the page file, or its address if it runs on your
computer:

> /brand-creator:check --page pages/index.html

Claude opens the page at several sizes, from a phone to a wide screen, in light and dark, and tells you:

- **what breaks your brand:** a colour or font that isn't yours, a squeezed logo, or a claim like "500 happy customers"
  that is not in your list of facts (`FACTS.md`);
- **what makes the page look like any other template**, such as a small label in capitals over a heading. These are
  warnings only.

Placeholder figures are fine while you build. Ask Claude to mark them as samples, and the check gives you a list of what
to replace before you publish.

More: [Check a page against your brand](../use/check-a-page.md).

## 5. Get your brand kit

The kit is your brand in one folder: your colours, fonts and logo files, your rules and facts, ready-made bits of code,
and a step-by-step recipe for building a page. Your website's code gets a copy of it, so whoever builds the next page
has everything at hand.

1. When you approve your brand book, Claude asks whether you want the kit. Say yes. Missed it? Ask:

   > Write the brand kit

2. Claude shows what it will write. Say go.
3. Three short pages in the kit are yours to write: how your brand sounds, how it looks beyond the colours, and the few
   rules every piece keeps. Claude drafts them with you from your brand book. You correct them.
4. Then ask:

   > Build the kit again, then check it

When your brand changes later, change it in your project as usual and ask for the kit again. Then ask
`/brand-creator:brand-adopt status`: Claude compares your website's copy with the new kit, file by file, and tells you
whether the copy is out of date.

More: [Use your brand kit](../use/use-your-brand-kit.md).

## 6. Put the brand into your product

This step changes your product's code: the folder on your computer that holds your website or app, which developers call
a repository. Claude does the work there, but only when you ask. Do it yourself with Claude, or sit down with whoever
builds your site.

1. Let Claude look first. It reads the code and lists every place your brand shows, such as icons, colours and names.
   It changes nothing:

   > /brand-creator:brand-adopt survey

2. Ask for the kit and the brand to go in, in your own words. Name a branch: a side copy of the code where the changes
   wait until you accept them. For example:

   > Add the brand kit to my website, and apply the brand on a new branch called new-brand

3. Before anything else happens, a separate review checks that every file Claude copied matches your brand files.

Claude never saves the changes into your code's history for you. You look at them first, then keep them, or throw them
away.

Later, `/brand-creator:brand-adopt status` tells you whether your website's copy of the kit is up to date.

### If it's a redesign of a site you already have

A new look can quietly break things that don't show on screen: a link, a field in a form, or a piece of code another
part of your product relies on. So tell Claude it's a redesign before anything changes. Claude notes all of these first,
applies the brand, then checks again. If something went missing, Claude shows you the list. For each item, you decide:
put it back, or say in your own words why it goes.

More: [Apply the brand to your product](../use/apply-the-brand-to-your-product.md).

## Good to know

- Claude looks at sites online only after your yes, and uses extra agents only after it has told you how many and
  roughly what they cost. [Costs](../reference/costs.md) has the details.
- Each step waits for you. Nothing moves on until you pick or approve.

## Check it worked

- `/brand-creator:status` shows where your project stands and what comes next.
- `/brand-creator:check` passes. If it says "not verified", it could not check something, and it says why and what to
  do.

## If something goes wrong

| You see | Do this |
| --- | --- |
| Claude says your brief lists no site | Add your site to the "Required surfaces" line of `brief/BRIEF.md`, in your own words, or ask Claude to do it |
| Claude says the references come first | Pick some references, or say "skip the references" |
| A message about the browser or setup | Type `/brand-creator:setup`, then try again |
| The page check fails a page | Each failing line says what it found, where, and how to fix it |
| Claude says your website's copy of the kit is out of date | Ask Claude to put the brand into that website again with `/brand-creator:brand-adopt` |

More: [Troubleshooting](../reference/troubleshooting.md).

## Related

- [Get reference pages for your site](../use/get-reference-pages-for-your-site.md)
- [Use your brand kit](../use/use-your-brand-kit.md)
- [What it never does](../reference/what-it-never-does.md)

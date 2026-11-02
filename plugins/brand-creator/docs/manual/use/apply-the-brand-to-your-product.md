# Apply the brand to your product

Your website or app should now wear your brand: the new name, colours, logo and icons, everywhere they show. Claude
finds every place first, and changes them only when you say go.

## Before you start

- Your project is on the Full tier (a tier is how far a project goes). `/brand-creator:status` shows yours, and moving
  up is one question to Claude. [Choose a tier](../getting-started/choose-a-tier.md) explains the tiers.
- Your brand book is approved. Claude stops if it isn't.
- Your product's code is in a folder on your computer, called a repository: your site's or app's code, plus the history
  of every change saved to it. You may have several. If your project doesn't list them, Claude asks; it never searches
  your computer. A site that lives only in an online site builder has no such folder: this step isn't for you, so use
  your brand book in the builder.
- The survey needs ripgrep, a free search tool. If it's missing, Claude gives you the command that installs it.

Do this step yourself with Claude, or sit down with whoever builds your site.

## Look first: Claude only reads

1. Type this, adding any files to leave alone, and why:

   > /brand-creator:brand-adopt survey

2. Claude reads your code, changes nothing, and checks that not one file changed.
3. It writes `ADOPTION.md` in your brand project: a numbered list of every place the old brand shows, such as the name,
   colours, logo and icon files, and the app's name in its settings. Things left alone on purpose, such as the old name
   in a licence, are listed with the reason.
4. Did the search miss something, such as an icon the app picks while it runs? Tell Claude, and it adds it. Leave
   editing the list to Claude.

Nothing changes because a list exists. Want your brand kit in your code too? Ask now, and it joins the list:
[Use your brand kit](use-your-brand-kit.md) has the steps.

## Apply the brand, only when you ask

Redesigning a site you already have? Read [the redesign section](#if-its-a-redesign-of-a-site-you-already-have) first.

1. Type this. To do one repository only, add its name from the list.

   > /brand-creator:brand-adopt apply

2. Name a branch: a side copy of your code where the changes wait until you accept them, such as "new-brand". If you
   don't, Claude suggests one and waits. It never works on your main version, and it notes your ask in `BRAND-STATE.md`.
3. Claude works through the list, one repository at a time. It finds each place by its words, so code that moved is
   still found. If the words are gone, that place is reported as not done, never guessed.
4. Your logo and icons are copied exactly, never redrawn. Old icons are replaced under the same file names, so the code
   still finds them; your code's history keeps the old ones. Claude deletes no file: one that has to go moves into a
   folder named `removed-` plus the date.
5. Before anything is saved, a separate review checks that every copied file is identical to yours and the right size.
   It runs your code's own build and tests and shows whether they passed; whoever builds your site can read the
   details. Where it can, Claude runs your product to see the real icon. A check that needs a real device, such as a
   phone, is marked "not verified".
6. Claude fixes what needs no decision and reviews again. Then it lists numbered decisions in the chat, each with a
   recommendation. Answer in your own words.

This runs in your conversation, at the cost of any Claude Code session that long. Claude uses helpers called agents,
one applying and one reviewing per repository, only after it tells you how many, which Claude models and the rough
cost, and you say yes. [Agents and workflows](../reference/agents-and-workflows.md) has the details.

## Keep or throw away the changes

Claude never saves the changes into your code's history, and never sends them anywhere, unless you ask. They wait on
your branch, on your computer. To keep them, there are three steps, each its own ask:

1. **Save** (developers say commit): records the changes in your code's history.
2. **Join** (merge): adds your branch to your main version.
3. **Send** (push): copies your code to where it's kept online, which can publish your site. Before a push, Claude reads
   your publishing settings and tells you what it would set off, and anything that can't be undone.

Your live site changes only once the new version is published. Whoever builds your site knows how yours gets published.

To throw the changes away, ask Claude to put your files back and to mark those places "to do" again. Claude deletes
nothing, though: your branch and any new files it added, such as your brand kit, stay (at most, Claude moves them into
a `removed-` folder) until you or whoever builds your site remove them.

Changes outside your code each need their own OK, such as renaming your app's id (the name app stores know it by), an
upload, a domain setting or a store listing. Most are steps for you, on your [launch checklist](launch-your-brand.md).

## If it's a redesign of a site you already have

Read this if Claude is about to rework the pages of a working site, not just swap colours, logo and name. Not sure?
Say it's a redesign anyway: this part only reads.

A new look can quietly break what doesn't show on screen: where links go, the names of form fields, the code a button
runs, the labels your tests and visitor statistics rely on, the names other code uses to find parts of a page, and the
scripts a page loads. Claude notes them before anything changes, and checks them after.

1. Before you ask to apply, tell Claude it's a redesign. If your site runs on your computer while it's built, send each
   page's address in the same message, such as `http://localhost:3000/` (`localhost` means your own computer). Claude
   then also reads the pages in a browser. It opens no other addresses.
2. Claude records all of this, and only reads. Your site is measured against this first record, and Claude replaces it
   only if you ask.
3. Apply as usual. At the end Claude records your site again. If you sent addresses, keep your local site running: if
   it isn't, Claude says so and doesn't skip the step. If the addresses changed, send the new ones.
4. The review compares your site with the first record. Anything gone fails the review, with the files it was in.
5. For each item that's gone, you decide: Claude puts it back, or you say why it goes, such as "the pricing page moved
   to /plans". Claude writes your reason, in your own words, in `ADOPTION.md`, and the review runs again. Claude never
   makes that call for you.

Claude finds these by familiar patterns, so it can miss what a page builds only while it runs, and it reads the code a
button runs from your files only. What it never sees isn't protected. If it lists something that doesn't matter, say so
and why. And the record is not proof that your site works: your code's own build and tests are.

## Check it worked

- `/brand-creator:brand-adopt status` counts the places "done", "doing" and "to do". Changed places stay "doing" until
  you ask for a save. If you added your brand kit, it also says whether each copy is current.
- `/brand-creator:brand-adopt review` runs the review again.
- Before any save, your repository has your branch with its changes, and nothing else.
- A later survey flags any place marked done that still shows the old brand.

## If something goes wrong

| You see | Do this |
| --- | --- |
| Claude stops: your brand isn't approved | Approve your brand book first: [Make the brand book](make-the-brand-book.md) |
| Claude says an automatic check in your code (a hook) failed | Claude reports it and never skips it. If it has nothing to do with the brand, fixing it is a separate change, made only if you agree |
| Claude can't read your local pages | Start your local site, then ask again |
| Claude refuses a page address and shows it back | Send an address on your own computer made of letters, digits and plain marks such as `/`, `?`, `=` and `-`. Write `&` as `%26` |

## Related

- [Use your brand kit](use-your-brand-kit.md)
- [Launch your brand](launch-your-brand.md)
- [What it never does](../reference/what-it-never-does.md)

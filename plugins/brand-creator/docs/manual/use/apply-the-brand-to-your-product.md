# Apply the brand to your product

Find every place your brand belongs in your product repositories, then change them, only when you say go. This is for
the Full tier.

## Before you start

- You have a brand project with approved finished files. Claude stops if they aren't approved yet.
- You know the paths of your product repositories. Claude asks for any it can't find in your project; it never searches
  your disk for them.

## Look first (changes nothing)

1. Type:

   > /brand-creator:brand-adopt survey

2. Claude reads each repository read only and writes `ADOPTION.md`: a numbered list of every place the old brand shows,
   such as names, colours, icons and badges. Matches it keeps on purpose are listed with the reason.
3. Read the list. Nothing is applied because a list exists.

## Apply it (only when you ask)

1. Ask for a named repository, or all of them, to be applied.
2. Name the branch. Claude suggests `brand/<slug>-<date>` and waits. It never works on the default branch.
3. Claude works through the list one row at a time, finding each place by its content, and copies your files byte for
   byte. A row whose text has gone is reported as not done, never guessed.
4. A separate review runs before anything is committed: every copied file is compared with your file, copied icons are
   size-checked, and the repository's own build and tests run, with the commands and results quoted.
5. You get a list of decisions, each with a recommendation.

Claude never commits, merges or pushes on its own. Each is a separate ask, and before a push it tells you what the push
triggers, such as a deploy or a store publish.

## Redesigning a site: keep what it is wired to

A redesign can quietly drop things the rest of your product depends on: a link, a form field name, a button handler, a
test hook, an id or a script. Nothing on the screen shows it. Claude writes down what the site is wired to before it
changes anything, and checks again afterwards.

1. Before you ask for the redesign to be applied, tell Claude that the repository is a redesign of an existing site.
   Claude records the site's links, form field names, handlers, test hooks, ids and scripts. It only reads. Nothing in
   your repository changes, and Claude checks that it did not.
2. If you run the site on your own computer (a dev or preview server), send the address of each page you want read, such
   as `http://localhost:3000/`. Claude then reads the pages as the browser shows them. Only addresses on your own
   computer are opened.
3. Apply the brand as usual. When the last row is done, Claude records the wiring again.
4. The review reads your repository as it is now and checks it against the record from before. Anything that was there
   before and is gone now fails the review, with the files it was in.
5. For each item that is gone, you decide. Claude puts it back, or you say why it goes, for example "the pricing page
   moved to /plans". Claude records your reason in your own words. It never makes that call for you, not even in the
   review.

Good to know:

- Claude finds these things by pattern, so a link or an id that the page builds while it runs can be missed or show up
  as noise. If an item is only noise, say so and it goes in the record as dropped, with your reason.
- Listeners that a script adds are not visible in the page. They are read from the source only.
- The record is not proof that the site works. Your repository's own build and tests stay the proof.
- If your local server is not running when Claude reads the pages again, Claude says so and does not skip the step.
  Start the server and ask again.

## Put the brand kit in a repository

If you opted into the [brand kit](use-your-brand-kit.md) when you approved your brand files, you can put it in a
repository too.

1. After the survey, ask for the kit to go into a named repository:

   > Add the brand kit for the repository `<label>`

   It becomes one more row on the list, the whole folder.
2. Apply it as above, on your branch. Claude copies the kit's files one at a time. It never overwrites a file of yours
   that the repository already has, and never copies into a global skills folder.
3. The review compares the copy with your kit byte for byte. Ask for `/brand-creator:brand-adopt status` any time to see
   whether each copy is current.

The kit is left uncommitted, like every other change. How to fill and keep the kit: [Use your brand kit](use-your-brand-kit.md).

## Check it worked

- `/brand-creator:brand-adopt status` shows every row as done, partly done or not done, with evidence.
- Your repository has your branch with uncommitted changes, and nothing else.

## If something goes wrong

| You see | Do this |
| --- | --- |
| Claude stops: the pack isn't approved | Approve the finished files first: [Check your project](check-your-project.md) |
| A hook fails in your repository | Claude reports it and never skips it. Fix it as its own change, if you agree |

## Related

- [Launch your brand](launch-your-brand.md)
- [Agents and workflows](../reference/agents-and-workflows.md): one implementer per repository, only after your yes
- [What it never does](../reference/what-it-never-does.md)

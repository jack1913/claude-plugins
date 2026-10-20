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

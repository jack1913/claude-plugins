# {{name}}: adoption

{{status}}

{{repos}}

{{about}}

{{groups}}

{{drift}}

{{rows}}

## How this list is applied

Nothing in a repository changes until the owner asks for it (gate G6), and then only on a branch the owner names.

- One repository at a time: one implementer works through its rows, then a separate review checks the work before
  anything is committed.
- Each place is found by the text in the Find column, never by the line number. A row whose text is no longer there is
  reported as not done, never guessed.
- Icons, lockups and other pack files are copied from the pack and compared byte for byte with it (`cmp`); they are never
  redrawn, re-exported or recoloured in the repository.
- The review runs the repository's own build and tests and quotes the results. A check that needs a real device is listed
  as not verified.
- The repository's hooks always run; a hook that fails for an unrelated reason is reported, and fixed as a separate change
  only if the owner agrees.
- Commit, merge and push are three separate asks. Before a push, what it triggers (CI, a deploy, a publish) is said first.
- A row that acts on a live service (a rename, an upload, a store listing, a DNS change) needs its own OK.

## Kept, not counted

{{kept}}

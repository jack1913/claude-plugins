# {{name}}: facts

Owner-confirmed facts only, one source each. Designers and copywriters may use these and nothing else as claims
(status words such as "available" or "launching" need a row here).

| fact | value | source | confirmed |
|---|---|---|---|
| (example) every product ships with a repair guide | yes | owner, chat on YYYY-MM-DD | YYYY-MM-DD |

Labels the emitters read (the `fact` cell, case-insensitive): `AppStream summary`, `AppStream description`, `project license`
(SPDX id), `metadata license` (SPDX id) and `homepage` for `emit linux`. A label with no row leaves its field empty and is reported; a
store-frame or CLI `--tagline` must equal the `value` of some row.

`emit print` and the e-mail signature read `contact name`, `contact role`, `contact email`, `contact phone`, `postal address`, `website` (or
`homepage`) and every row whose label starts `legal` (the book must repeat those verbatim). `emit social --posts --post-fact "<label>"` takes the words of a
post from the `value` of the named rows (and shows the label). A label with no row is left out and reported.

Rules:

- An answer is not a fact. What the owner says in answer to a question becomes a row only when they say it may be said
  publicly (ask when unsure); otherwise it goes under `## Internal context` in `BRAND-STATE.md`, which nothing public reads.
- A statutory deadline, obligation, rate or legal requirement is checked in the primary source (the statute's consolidated
  text, the authority's own page) before any page, board or book shows it. Its row's `source` names that source and the date
  checked; a portal, blog or commercial summary is never the source. The page still says it is not legal advice where the
  owner wants that.
- One fact per row; a fact without a source is not a fact. Delete the example row.
- A fact found by research (the "Only you can confirm" list in research/research.md) gets a row only after the owner
  confirms it; until then no copy may use it.
- Status words ("in development", "available", "launching") need a row that says so, with a date.
- Never add clients, team size, years of experience, awards, numbers, dates or features the owner did not confirm.
- When a fact changes, update the row and run the cascade (`brand-creator check --cascade "<old wording>"`).
- A fact and the words that present it are two things. The `value` of a fact row stays the plain fact ("shipping takes 3
  days"). Wording the owner approved for use as copy goes in its own row, labelled `copy: <slot>` (`copy: site H1`, `copy: signature line`),
  with the owner's words as its `value` and where they approved them as its `source`. A headline on a page quotes a `copy:`
  row, or is new wording the owner approves on the board; it never uses a fact's `value` as it stands. A number or status
  word in a `copy:` row backs the page like any fact.

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

- One fact per row; a fact without a source is not a fact. Delete the example row.
- A fact found by research (the "Only you can confirm" list in research/research.md) gets a row only after the owner
  confirms it; until then no copy may use it.
- Status words ("in development", "available", "launching") need a row that says so, with a date.
- Never add clients, team size, years of experience, awards, numbers, dates or features the owner did not confirm.
- When a fact changes, update the row and run the cascade (`brand-creator check --cascade "<old wording>"`).

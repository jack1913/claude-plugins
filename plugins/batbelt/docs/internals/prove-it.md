# prove-it

An evidence workflow for assumptions that can be true or false: business numbers, legal or regulatory requirements, market claims, and product or customer behaviour.

- VALIDATE mode writes an assumption register.
- SPEC mode adds a change spec. Its calculation steps refer back to the register's provenance IDs.

## Files

- [`skills/prove-it/SKILL.md`](../../skills/prove-it/SKILL.md) holds the procedure.
- [`evidence-standards.md`](../../skills/prove-it/references/evidence-standards.md) holds the rules for what counts as evidence.
- [`source-profiles.md`](../../skills/prove-it/references/source-profiles.md) holds source hierarchies by domain.
- [`templates.md`](../../skills/prove-it/references/templates.md) holds the register and spec layouts.

## Intake

- It uses one `AskUserQuestion` call for three questions: the source hierarchy, the reference date and the artifact location.
- It creates a missing chosen directory only after you accept the recommended "create or use" option.

## State is a Markdown file

- A register is created once with `Write`.
- Every later change reads the whole current file and applies targeted `Edit`s to the affected section, table row or Research-status field.
- Resume starts at the first approved assumption that has no saved section.
- A fresh run renames the old register. It never overwrites it.

## Research cannot fall back to memory

- A usable path is search plus fetch, or URLs you supply plus fetch.
- With neither, or on a tool error, the register gets `Research status: BLOCKED`. It names the first unfinished assumption and the way to resume.
- Completed evidence is kept. No verdict is written for the blocked item, and the run stops at that checkpoint.
- A failed fetch caps a verdict at PARTIALLY only when all three hold: the URL was identified in the run, another accessible source corroborated the claim independently, and the fetch of that URL failed.

## Status values

- `NOT STARTED` when the register is created.
- `IN PROGRESS` before the first researched item.
- `COMPLETE` after the last item is saved.
- `BLOCKED` at the first unavailable path.
- A triage with no source-checkable assumptions goes straight from `NOT STARTED` to `COMPLETE`, with no web tool needed.

## The browser rung

- When a level-1 source is only reachable through a rendered page and a Playwright-style browser tool is connected, the skill drives it.
- It does this only after a plain fetch and any API front door have failed, because a browser session costs minutes where an API call costs seconds.
- It does not lower the evidence bar. Text read in a browser still needs a quoted `verbatim`, a direct `source_url` and a `fetched` date.
- A CAPTCHA, login or anti-bot page is a hand-off. The skill stops and names the source for you to fetch.
- `WebFetch` on a `.pdf` is the cheaper rung. Its sub-model often refuses the binary, but the tool still saves the file and prints its path, which the file reader opens by page range.

## A fetched source that was not read proves nothing

- The record can look complete: right URL, successful fetch, real `fetched` date.
- The mandatory `verbatim` field exposes it.
- An unread fetch caps the verdict at UNVERIFIABLE until the passage is quoted.

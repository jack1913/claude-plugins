# onboard-repo — docs page-classification rubric

When a repo already has docs, classify each existing page into ONE of four
tiers, then adopt it (see `SKILL.md` adoption step). Classification is a
per-page judgment; when a page straddles two tiers, file it by its PRIMARY
audience and flag it for a possible split.

| Tier | Destination | It answers | Signals |
| --- | --- | --- | --- |
| **consumer** | `docs/manual/` | "what do I type / how do I use it?" | commands, workflows, step-by-step, user-facing tasks, keybindings |
| **technical** | `docs/internals/` | "why is it wired this way / how does it work?" | architecture, mechanics, provisioning/build internals, contributor-only |
| **decision** | `docs/adr/` | "why was this chosen?" | a durable design decision still in force (record as an ADR) |
| **historical** | `docs/archive/` | "what did we used to do?" | dated/superseded records, old plans/specs/reviews — frozen, never edited (so `check-docs` skips its grounding checks here; link checks still apply) |

Per-repo-type examples:
- **CLI tool** — usage/flags page → consumer; the parser/dispatch design → technical; "why one binary not plugins" → decision.
- **Library** — API how-to/quickstart → consumer; internal module layout → technical; "why we vendored X" → decision.
- **Full-stack app** — feature walkthroughs → consumer; data model / deploy pipeline → technical; superseded RFCs → historical.

Getting-started (per target) and pure reference tables are consumer subpages
(`docs/manual/getting-started/`, `docs/manual/reference/`).

**Not documentation at all — an agent working directory.** A markdown tree written by
a *tool* rather than authored for a reader has no tier and is skipped by the docs walk
entirely: `superpowers/` and `.superpowers/` (a plugin's own `plans/` and `specs/`),
and `.onboard-repo-retired/` (this skill's pre-stamp scaffold). Do **not** classify
these into a tier and do not move them — they are live scratch, not superseded records,
so `docs/archive/` is the wrong home (it is frozen, which would strand a directory the
tool still writes to). They also quote pre-sanitization sources deliberately, which is
why `test/check_clean.sh` carves out the same names. Grounding such a tree reports
dozens of findings no one will act on, and that is what gets a gate switched off.

## Principal / niche (surface tiering, §3.7 authoring)

Within the **consumer** tier, every enumerated `README.md` surface (see
`detection.md` § "Consumer surfaces") is further split **principal** vs.
**niche** by the same keyword rule:

- **principal** — `install|setup|quickstart|getting-started|usage|command|option|flag|config|safety|security|permission`,
  plus the repo's own primary workflow verbs. Author these **first and always**
  — a missing principal page is what triggers §3.7.
- **niche** — `contributing|sponsor|license|changelog|badge|acknowledg|faq|roadmap|development`.
  Record as `status: deferred` in the coverage record; that's a clean decision,
  not a gap.

**Operator override** always wins the automatic split — show the proposal,
let the operator move a surface between tiers before it's confirmed.

## Surface → page coverage

Every surface from the enumerator ends up in exactly one row of the committed
`docs/.onboard-coverage.json` (`{surface, slug, tier, page, status}`). A
principal surface must have a real `page`: a principal row whose `page` is
null, absent, or empty is exactly what `check-docs`'s `EMPTY_TIER` finding flags
(it keys on `page`, not `status`). `deferred` is only a clean state for a niche
surface.

## Platform parity

When a capability is invoked differently per platform (macOS vs. Linux vs.
Windows vs. WSL; a CLI vs. its CI action), the authored page documents **each
supported platform's invocation** explicitly — never one platform's command
presented as if it were universal. Where a capture can only be taken on one
platform, tag it `capture=<slug>` for that platform and label the others
`illustrative` rather than omitting them.

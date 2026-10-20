# Mine rules from the codebase

Section 3.4c of [SKILL.md](../SKILL.md), moved here; only citations of another repository's ADRs were dropped. SKILL.md sends you here at that step.

## 3.4c Mine rules from the codebase (offer-first, validated or not at all)

**Trigger:** after §3.4 provisioning, `.claude/rules/` holds no real rule (empty,
or `EXAMPLE.md` only). Onboarding bans generated rules because blind generation
produces confident, ungrounded claims; this pass is the one exception, for exactly one
path — this one, where validation is inseparable from authoring. **Offer the pass,
report-first; never run it unasked.** Register confirmed candidates as run items
with `--kind rule` — the phase enum gains nothing (`run_set_phase` enforces it),
so the items ride whatever phase the run is in (`agent-config`, or `copilot`
after a §3.4b port) and a resumed run picks up mid-list.

The bar, restating `EXAMPLE.md`'s four tests — expect to **reject most candidates**:

- mandatory `paths:`, scoped to the narrowest glob that covers the constraint;
- declarative, not procedural — a workflow belongs in a skill;
- expensive to violate AND not already enforced by the compiler, a linter, or a
  test — if a gate already catches it, say it in the gate instead;
- every claim re-derivable: each count carries the command that produced it, each
  symbol a real location.

Mining is a **fan-out** pass (§0.2): shard the repo by subsystem with
non-overlapping briefs; each worker reads that subsystem's code, configs, and
tests and returns **candidates only** — the claimed convention, proposed `paths:`
glob, evidence, and the cost of violating — never rule bodies. Cite-or-defer,
exactly as in [ADR mining](adr-mining.md): evidence a worker did not read from real output does not enter
a candidate.

**Validation is three passes per candidate, and authoring without them is not an
option:**

1. **Mechanical** (main thread): re-run every stated count command, resolve every
   cited symbol and path, and confirm the `paths:` glob matches real files —
   pre-empting `DEAD_GLOB`, `UNRESOLVED_CITATION`, and `UNGROUNDED_COUNT` before
   they exist. A failing claim is re-derived from real output or the candidate
   drops; **never soften a checkable claim into an uncheckable assertion**
   (the ban on softening a claim).
2. **Truth verifier** — one independent agent per candidate, handed only the
   drafted rule and the repo, never the miner's notes. Its brief is to **refute**
   by sampling real sites: is the convention actually followed, or a grep
   artifact? (An audit of generated rules once found a rule claiming 55 sites where 5
   existed.) A counter-example kills the candidate or narrows its scope.
3. **Worth verifier** — independent, different lens: is it already enforced by a
   linter/compiler/test config (reject — say it in the linter)? Procedural
   (belongs in a skill)? Is the glob the narrowest? Does it earn the context it
   costs on every matching read?

Both verifiers must pass; a standing refutation blocks authoring. Bound the loop
at **2** fix-and-reverify rounds per candidate — a non-converger **drops to the
report**, never to disk: an unverified rule must not exist, so there is no
"parked but authored" state here.

Then, in the main thread: **show the operator the surviving list** — rule text,
evidence, both verdicts — for confirmation before writing anything. Author each
confirmed rule as `.claude/rules/<kebab-name>.md` in the `EXAMPLE.md` skeleton's
frontmatter shape, and remind the operator that `EXAMPLE.md` can now be deleted.
Close-out: `check-instructions` over `.claude/rules` must return **no findings**
on the authored files. Maintenance from here on belongs to the stamped
`update-rules`, whose own ban on authoring is unchanged — it repairs
what this pass wrote; it never mints.

**`--no-review` disables this pass entirely** — the offer is skipped and
reported. This is deliberately stricter than [ADR mining](adr-mining.md), where the ADR verifier is
skippable: a doc is read when someone chooses to read it, but a rule is acted on
silently on every matching read, and an unverified rule is exactly what
onboarding bans.

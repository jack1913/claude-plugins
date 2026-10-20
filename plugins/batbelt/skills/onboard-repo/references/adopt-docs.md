# Adopt existing docs

Section 3.6 of [SKILL.md](../SKILL.md), moved here; only citations of another repository's ADRs were dropped. SKILL.md sends you here at that step.

## 3.6 Adopt existing docs (only when the repo already has docs; report-first)

Classify each existing page with `references/rubric.md` → propose
`old → docs/<tier>/<slug>.md` (dated/superseded pages → `docs/archive/`). Show the
**full move plan** and **advise a pre-adoption `git` commit** (the rollback
anchor); confirm before moving.

Classification is the other **fan-out** pass (§0.2): it is read-only and per-page, so
on a large repo shard the page list across workers that each return
`path → tier + one-line reason` and nothing else. The **move plan is assembled,
presented and confirmed in the main thread** from those verdicts, and once confirmed
store it with `run-set --confirm moveplan=pairs.json` so a compaction cannot lose it.
The moves themselves are never delegated — step 4's ordering is load-bearing.

On confirm, in order:

1. **Build the move manifest with the helper** (never hand-write the JSON — the
   shape must match exactly or `rewrite-links` fails). First add
   `.onboard-repo-retired/` to `.gitignore`, `mkdir -p .onboard-repo-retired/<stamp>`,
   and **`Write` two input files**: `pairs.json` **containing** `[[old,new],…]` (the
   confirmed move plan) and `dirs.json` **containing** `[<dirs created>]`. Then (the
   helper reads those two as **file paths**, not inline JSON):
   `python3 "$SKILL_DIR/scripts/onboard.py" write-move-manifest pairs.json dirs.json > .onboard-repo-retired/<stamp>/moves.json`
2. **`mv`** each page to its tier; **move a page's co-located assets** (images/
   includes it references relatively) alongside it, so relative asset links don't
   dangle.
3. **Renumber the manual ToC (only if `docs/manual/README.md` has a numbered reading-order
   list; the stamped seed has none, so skip this step then) — capture to a temp file, never redirect onto the
   same file** (`… > docs/manual/README.md` truncates it to empty):
   `python3 "$SKILL_DIR/scripts/onboard.py" renumber-toc docs/manual/README.md > <tmp> && mv <tmp> docs/manual/README.md`
4. **Fix links, in this exact order — it's load-bearing:**
   1. **`rewrite-links` first** (into every moved file, whether or not the file
      itself moved) — retargets any link that points AT a page the manifest
      moved, the same capture-then-move way, per affected file, markdown link
      targets only, never a blind substring:
      `python3 "$SKILL_DIR/scripts/onboard.py" rewrite-links <file> <manifest> > <tmp> && mv <tmp> <file>`.
   2. **`rebase-links` second**, only for pages that themselves moved — re-anchors
      that page's own *outgoing* relative links now that the page's own location
      changed:
      `python3 "$SKILL_DIR/scripts/onboard.py" rebase-links <file> <page_old> <page_new> <manifest> > <tmp> && mv <tmp> <file>`.
      Applying these in the reverse order **double-applies** the move to any link
      that's both a moved target and lives in a moved page — `rewrite-links` must
      see the pre-rebase relative paths.
   **Code/CI files** that reference a moved path are shown as a `diff` and confirmed
   **separately** — never blind-rewritten (a link checker validates links only and
   cannot catch a bad replace inside code).
5. **Re-point the pointer entries.** In `AGENTS.md` (the resolved index doc),
   update every source-map/pointer entry for a moved page to its new tier path —
   **cite-or-defer**: only where the source still verifies, never fabricate a
   `file:line`. Touch that prose minimally; `AGENTS.md` carries **no**
   `BEGIN/END REPO SPECIFICS` markers, so there is no inner region to scope to
   here. **Separately**, re-point the stamped `update-docs/SKILL.md`'s
   **REPO SPECIFICS `section→source map`** field to the new tier paths — that
   edit *is* scoped to that file's `BEGIN/END REPO SPECIFICS` inner region only
   (a stamped skill is the one file that has those markers), same cite-or-defer
   rule; never touch its template region.
6. Then run the close-out link gate via `update-docs` (its tools carry
   `lychee`/`grep`; onboard-repo's do not).

**CLAUDE→AGENTS adoption (loss-free — no free-form merge, ever):** decided by a
small table, not judgment call:

| State | Action |
| --- | --- |
| `AGENTS.md` absent | Copy `CLAUDE.md`'s content into a new `AGENTS.md` — report-first, behind the pre-adoption commit. |
| `AGENTS.md` has real content | **Additive append only**: `cat AGENTS.md addition > tmp && mv tmp AGENTS.md` — never `Write` (it would clobber), never redirect onto the same file (`cat … >> AGENTS.md` risks a truncate race the same way). Operator-confirmed; no autonomous merge of the two bodies. |
| Source `CLAUDE.md` | Replaced **wholesale** with the one-line `@AGENTS.md` stub — nothing else survives in it once `AGENTS.md` is the index. |
| Already on the convention (`@import`-only `CLAUDE.md` + a real `AGENTS.md`) | **Hard no-op** — already on the convention, do nothing. |

File each consumer page by kind: first-run pages in `docs/manual/getting-started/`, task
pages in `docs/manual/use/`, tables and lookups in `docs/manual/reference/`, and list it in
`docs/manual/README.md` under Get started, Do a task or Look it up.

Flatten nested docs dirs into the tiers; dedupe slug collisions; file a straddling
doc by its primary audience and flag it for a possible split.

**Rollback (operator-run — onboard-repo's own tools carry only `git rev-parse`, so
it cannot revert or delete):** tell the operator that to reverse an adoption they
restore to the pre-adoption commit (`git restore .` / `git checkout -- .` +
`git clean -fd` for the untracked scaffold), or reverse the moves precisely from
`moves.json` (swap each `old`/`new` and remove the created dirs). A later
`--rollback-ia` mode can automate this from the manifest.

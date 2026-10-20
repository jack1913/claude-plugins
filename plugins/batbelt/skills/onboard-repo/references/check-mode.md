# Check mode

Section 6 of [SKILL.md](../SKILL.md), moved here; only citations of another repository's ADRs were dropped. SKILL.md sends you here at that step.

## 6. `--check`

Report, without writing:

- **an unfinished run** — if a `.onboard-repo-retired/*/run.json` exists whose `phase`
  is not `done`, `run-status` it and say so first: an interrupted onboarding is the
  most actionable thing `--check` can report, and `--resume` continues it.

  ```bash
  python3 "$SKILL_DIR/scripts/onboard.py" run-status .onboard-repo-retired/<stamp>/run.json
  ```

- template-region drift (diff current vs the carried template);
- **stamped-gate drift** — three states, reported separately because the fixes differ.
  `diff` alone cannot tell them apart: it prints the same "No such file or directory"
  for **absent** and for **pre-split**, which are the two that must not be conflated.
  So test for the files first, and only `diff` once `check.py` is known to exist:

  ```bash
  for s in update-docs update-rules; do
    d=".claude/skills/$s/scripts"
    if   [ -f "$d/check.py" ];   then diff "$d/check.py" "$SKILL_DIR/scripts/check.py"   # edited, if any output
    elif [ -f "$d/onboard.py" ]; then echo "$s: PRE-SPLIT (gate runs; offer --sync)"
    else                              echo "$s: ABSENT (gate unavailable until --sync)"
    fi
  done
  ```

  **edited** (a real diff) — replace on confirm. **absent** — the consuming skill's gate
  (`update-docs` §7.8 `check-docs`, `update-rules` §2 `check-instructions`) does not run
  at all until `--sync` installs it. **pre-split** (`onboard.py`/`onboard_lib.py` there
  instead, from a stamp older than the split) — the gate still *runs*, so this is a
  migration to offer, not a broken gate to alarm about;
- any files that fail `check-markers`;
- **agent-config drift** — diff `settings-plan`'s current proposal against
  `.claude/settings.json` (report only; an operator-added entry is not drift), and
  re-run `gitignore-ensure` to confirm it is a no-op;
- **agent-config defects** — `settings-audit .claude/settings.json` (report only
  here; `--sync` offers the fix). Exit `1` means a deny `Read()` rule anchors inside
  the repo — the shape that prompted on every path-less `rg` on Claude Code 2.1.259
  (reverted in 2.1.260) and that `//**/` supersedes;
  `dead_home_denies` and `broad_allows` are advisory
  (see [agent configuration](agent-config.md)):

  ```bash
  python3 "$SKILL_DIR/scripts/onboard.py" settings-audit .claude/settings.json
  ```

- **instruction-file grounding** — the claims inside the repo's own rules and
  skills, which rot differently from docs: a count drifts on every merge and a
  cited symbol gets renamed out from under the file.

  ```bash
  python3 "$SKILL_DIR/scripts/check.py" check-instructions .claude/rules .claude/skills \
    --repo-root . --repo-root <source-root-if-any>
  ```

  `--repo-root` is repeatable, and passing every base the repo cites against
  matters. One rule legitimately cites against two roots at once:

  ```text
  AGENTS.md:21                 <- resolves from the repo root
  Domain/Models/Result.cs:7    <- resolves from the source root
  ```

  With a single base, whichever convention loses is reported as unresolved.

  Six finding codes, and the severity split is deliberate. The errors all answer
  "is this file doing what it claims?"; the warnings are maintenance smells.
  - `INVALID_FRONTMATTER` (**error**, exits 1) — the frontmatter will not parse as
    YAML, so the file may not load **at all**. The quietest failure here: nothing
    reports it, and every other check passes a file that has no content to check.
    Almost always an unquoted scalar containing a colon-space, which YAML reads as
    a nested mapping:

    ```text
    description: Observers: side-effect containers      <- rejected
    description: "Observers: side-effect containers"    <- fine
    ```

  - `DEAD_GLOB` (**error**) — a `paths:` entry matching no file in the repo. The
    rule parses, loads, and can never fire. An angle-bracketed placeholder is
    exempt: the scaffolded EXAMPLE ships one so it stays inert.
  - `UNDEFINED_SCRIPT` (**error**) — an `npm run <x>` or `composer run <x>` naming a
    script absent from that runner's own manifest; anyone copying it gets an error.
    Each runner is checked against its OWN manifest (`package.json` / `composer.json`),
    and a runner whose manifest is absent is skipped rather than reported — a PHP-only
    repo has no `package.json` to check `npm run x` against. Bare `composer <x>` is not
    matched at all: `install`, `update`, `require` and ~30 more are built-in Composer
    commands. Prose *about* a missing script ("was never defined", "renamed to", a
    template's "ecosystem default") is not flagged — a gate that fires loudest on the
    file documenting the problem gets switched off.
  - `MISSING_PATHS` (**warning**) — a rule with no `paths:`, which loads on every
    session. Advisory rather than fatal because always-on is sometimes right: a
    rule about *when* to reach for a tool has no file shape to scope to.
  - `UNRESOLVED_CITATION` (**error**, exits 1) — the file said "look here" and
    there is nothing there: a path naming no file, or a line past the end of the
    file it names. Shorthand resolves — a bare filename, or a partial path — when
    some file's path ends that way:

    ```text
    Thing.cs:10           <- matches deep/nested/Thing.cs
    nested/Thing.cs:20    <- same file, by path suffix
    ```

  - `UNGROUNDED_COUNT` (**warning**, never fails the run) — a number with no
    re-derivation command within three lines. That is a maintenance smell, not
    proof the number is wrong, and treating it as fatal would make the gate
    unusable: a freshly and correctly grounded 16-file corpus still reports 26 of
    these. Report them; do not block on them, and do not "fix" one by deleting the
    number.
- doc drift surfaced by `update-docs --check` if present;
- **doc-IA drift** — re-run the mechanical gate (report-only) so an unresolved
  surface recorded in the coverage record re-flags via `EMPTY_TIER` (§3.7's
  park promise), alongside broken links / malformed tables / ungrounded output.
  Run it **unscoped** — `--check` reports on the whole tree, so neither `--only` nor
  `--no-tier-check` belongs here:

  ```bash
  python3 "$SKILL_DIR/scripts/check.py" check-docs docs README.md <index> --captures docs/.onboard-captures --coverage docs/.onboard-coverage.json
  ```

A stamped `update-deps` is checked for template-region drift and marker integrity
via the same `check-markers` call — the `--check` mode iterates every stamped
skill present; no per-skill code path.

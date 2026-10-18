# Anti-patterns: case cards

Each card is a mistake that happened in real brand projects, generalised. Owner signals are paraphrased; no client,
brand or person is named. Format: situation → wrong move → owner signal → cost → rule → check that catches it.

## Contents

1. [Cloning a reference, then patching](#1-cloning-a-reference-then-patching)
2. [Logo before identity](#2-logo-before-identity)
3. [Briefing without the architecture](#3-briefing-without-the-architecture)
4. [Three versions of one safe idea](#4-three-versions-of-one-safe-idea)
5. [The discovery interview](#5-the-discovery-interview)
6. [Hybridising the liked direction](#6-hybridising-the-liked-direction)
7. [Wide sketches as recovery](#7-wide-sketches-as-recovery)
8. [The bare number](#8-the-bare-number)
9. [Judge as verdict](#9-judge-as-verdict)
10. [Mixed projection](#10-mixed-projection)
11. [Claims instead of measurements](#11-claims-instead-of-measurements)
12. [States that differ by hue only](#12-states-that-differ-by-hue-only)
13. [Endorsement in the wrong place](#13-endorsement-in-the-wrong-place)
14. [Stale files after a rule change](#14-stale-files-after-a-rule-change)
15. [Colour role collisions](#15-colour-role-collisions)
16. [Stale favicon and screenshot OG](#16-stale-favicon-and-screenshot-og)
17. [Tests that pass for the wrong reason](#17-tests-that-pass-for-the-wrong-reason)
18. [Live text and self-contradicting books](#18-live-text-and-self-contradicting-books)
19. [Print defects found late](#19-print-defects-found-late)
20. [Scaffolding left in the book](#20-scaffolding-left-in-the-book)
21. [Work living in scratch](#21-work-living-in-scratch)
22. [Long silent runs and destructive agents](#22-long-silent-runs-and-destructive-agents)

## 1. Cloning a reference, then patching

- **Situation:** a site or identity built from an admired reference.
- **Wrong move:** copying the reference's parts, then piling small fixes on top.
- **Owner signal:** it looks like a patchwork; think about every decision as one system.
- **Cost:** several rounds of fixes that never converged.
- **Rule:** never clone a reference; tear it down into adoptable rules and a "what not to copy" list. After the third
  incremental fix in one area, stop and write a numbered-rules system spec, reviewed adversarially (G-sys).
- **Check:** `fixes_per_area` in BRAND-STATE.md; the G-sys stop in SKILL.md.

## 2. Logo before identity

- **Situation:** the owner asked for a logo.
- **Wrong move:** designing only the mark.
- **Owner signal:** not only the logo; the whole identity needs rebuilding.
- **Cost:** the mark had to be redone once type, colour and hero existed.
- **Rule:** make scope an explicit G0 tier; design mark, wordmark, type, colour and hero together on one board.
- **Check:** G0 tier question; board cells in [board-contract.md](board-contract.md).

## 3. Briefing without the architecture

- **Situation:** a new brand for an owner who already had related brands.
- **Wrong move:** briefing round 1 without asking whether it belongs to a family.
- **Owner signal:** surprise that the work left the shared family look.
- **Cost:** a whole identity round.
- **Rule:** check the brief and repos for a parent or siblings before round 1; ask then, and ask for FAMILY.md only
  after family-member is picked. When the owner rejects a question, ask what they want clarified.
- **Check:** architecture line in BRIEF and BRAND-STATE; behaviour eval (stage 6).

## 4. Three versions of one safe idea

- **Situation:** round 1 for a professional practice.
- **Wrong move:** three options in the same safe middle of the category.
- **Owner signal:** dislikes all of them; asks for research into how the category designs today.
- **Cost:** a rejected round and a reset.
- **Rule:** research first, positioning map against the norm, strategic difference, one direction per emotional
  register, at least one far from the norm.
- **Check:** `board-lint` (map, `data-far`, unique `data-register`).

## 5. The discovery interview

- **Situation:** intake.
- **Wrong move:** an open question about what people should feel.
- **Owner signal:** irritation; "you are the designer, you decide".
- **Cost:** trust, twice.
- **Rule:** no interview; infer from research and existing material, show artefacts with a stated pick.
- **Check:** G0 limits in [phases/00-intake.md](phases/00-intake.md); behaviour eval (stage 6).

## 6. Hybridising the liked direction

- **Situation:** the owner loved one direction and asked for refinement.
- **Wrong move:** "warmer" and "stronger" variants blending in other styles.
- **Owner signal:** does not like it; wanted the original worked on.
- **Cost:** a refinement round.
- **Rule:** deepen the liked original and keep it visible as the baseline. State your reading of "style 2 and 3"
  before building.
- **Check:** G2b-b order; `canonical_direction` in BRAND-STATE.

## 7. Wide sketches as recovery

- **Situation:** after a rejected refinement.
- **Wrong move:** a spread of cheap wide sketches, recorded as a technique that works.
- **Owner signal:** ignored them.
- **Cost:** a wasted round and a false lesson.
- **Rule:** do not record that lesson as proven. Restore the liked baseline first; widen only on request.
- **Check:** G2b-b order in SKILL.md.

## 8. The bare number

- **Situation:** the owner answered "1" while a board had labels and the chat had a numbered list.
- **Wrong move:** reading it as the board label.
- **Owner signal:** frustration; that was not what they meant.
- **Cost:** a full round built on the wrong direction.
- **Rule:** stable word names identical on board and in chat; restate the choice before any expensive run; ask or
  state the assumption when a token fits two lists.
- **Check:** `board-lint` word names; behaviour eval (stage 6).

## 9. Judge as verdict

- **Situation:** a comparative judge ranked the directions.
- **Wrong move:** presenting the ranking as the answer.
- **Owner signal:** overrode the judge (and the lead) many times.
- **Cost:** friction, and good options buried.
- **Rule:** panels advise. Show judge view, lead view and a middle option.
- **Check:** `board-lint` judge fields when `data-judge="ran"`.

## 10. Mixed projection

- **Situation:** a geometric mark drawn in a 3D projection.
- **Wrong move:** one stroke drawn in a different projection; it looked fine at a glance.
- **Owner signal:** spotted parts below the line.
- **Cost:** a round, and confidence in the geometry.
- **Rule:** guide-line proof with baseline and cap guides, measurement on rasters, a fault mini-board, and rebuild
  the model instead of patching the output.
- **Check:** `brand-creator logo-sheet --guides` (guide lines over the mark with the measured offset of each ink edge); [phases/06-mark.md](phases/06-mark.md).

## 11. Claims instead of measurements

- **Situation:** small icon sizes.
- **Wrong move:** claiming details "survive" at 16 px; an accent nearly invisible; a platform compile never run.
- **Owner signal:** critique of the round.
- **Cost:** a round and a failed platform build.
- **Rule:** measure on real downscales; replace claims with numbers; compile with the real toolchain.
- **Check:** `brand-creator logo-sheet`, `contrast`, `downscale` (real system downscale, accent pixels and box, before/after); the compile check comes with the Apple emitters.

## 12. States that differ by hue only

- **Situation:** a set of status icons (idle, active, error).
- **Wrong move:** states told apart by colour alone; the small glyphs left out of contrast checks.
- **Owner signal:** still needs work.
- **Cost:** another pass over hundreds of files.
- **Rule:** inventory every small-glyph surface from code; states differ by shape; gate on greyscale and silhouette.
- **Check:** `brand-creator states-check` (greyscale and silhouette thresholds), `contrast --cvd` for the colours.

## 13. Endorsement in the wrong place

- **Situation:** a product lockup shown on the parent's own site.
- **Wrong move:** the "by <parent>" endorsement repeated on the parent's own pages; lockup misaligned.
- **Owner signal:** sharp: this is already the parent's page.
- **Cost:** a rework of lockup variants.
- **Rule:** define lockup variants per context up front; let the generator enforce the endorsement policy.
- **Check:** [architecture.md](architecture.md) endorsement table; G4 rule.

## 14. Stale files after a rule change

- **Situation:** a lockup rule changed.
- **Wrong move:** updating the main file only; book diagram, installer background, header and sibling READMEs kept
  the old rule.
- **Owner signal:** did you update the design book too?
- **Cost:** contradictions shipped.
- **Rule:** cascade checklist: grep for the old number or phrase, screenshot the changed section, fix generators,
  never generated files.
- **Check:** `check --cascade "<old value>"`; [cascade.md](cascade.md).

## 15. Colour role collisions

- **Situation:** sibling products, each with an accent.
- **Wrong move:** one product's accent equal to a sibling's; a brand red equal to the UI's danger red.
- **Owner signal:** numbered owner decisions to separate them.
- **Cost:** re-colouring after files existed.
- **Rule:** an inventory "Surprises and conflicts" list; role-separation rules ("the brand red never means danger").
- **Check:** INVENTORY template (stage 2); family check (stage 3).

## 16. Stale favicon and screenshot OG

- **Situation:** a site rebuilt with a new mark.
- **Wrong move:** the favicon URL unchanged in HTML so browsers kept the old one; the OG image was a cropped
  screenshot.
- **Owner signal:** the favicon needs updating too.
- **Cost:** a visible old mark after launch.
- **Rule:** fingerprint only HTML- or manifest-referenced icons on byte change; keep `/favicon.ico` at a stable URL;
  make the OG a designed card, checked at preview size, with a new URL per change.
- **Check:** `emit web`, `emit social` (manifest and file names).

## 17. Tests that pass for the wrong reason

- **Situation:** hardening rules into checks.
- **Wrong move:** a negative test whose mutation silently did not apply; a build skipping a check when a dependency
  was missing.
- **Owner signal:** found in code review.
- **Cost:** false confidence.
- **Rule:** mutation tests assert the mutation applied; checks that cannot run fail loudly (exit 3, "not verified").
- **Check:** the test suite and the report status `not-verified`.

## 18. Live text and self-contradicting books

- **Situation:** a type-based monogram and its book.
- **Wrong move:** live font text inside the mark; the formal name written two ways; the book breaking its own motion
  rule.
- **Owner signal:** found in self-review.
- **Cost:** a book revision and a mark rebuild.
- **Rule:** outline glyphs; one naming rule (from the regulator where one applies); a self-consistency lint.
- **Check:** `check` mark_lint (no `<text>` in assets); book lint (stage 4).

## 19. Print defects found late

- **Situation:** business card and letterhead.
- **Wrong move:** a back not in one colour, the monogram under its own minimum, reversed text too small, lines on the
  trim.
- **Owner signal:** found in self-review.
- **Cost:** a print round.
- **Rule:** physical-spec review in mm and pt (bleed, safe zone, minimum line weight, minimum reversed text, no
  opacity).
- **Check:** print check (stage 4).

## 20. Scaffolding left in the book

- **Situation:** after a decision.
- **Wrong move:** losing variants and switchers left in the book and tokens.
- **Owner signal:** asks to clean that up.
- **Cost:** a confusing book.
- **Rule:** a collapse step after each decision, with a dated copy kept.
- **Check:** G5 collapse step; book lint round words (stage 4).

## 21. Work living in scratch

- **Situation:** early rounds built in a temporary folder with hard-coded paths.
- **Wrong move:** promoting late; the OS clears temporary folders.
- **Owner signal:** a reviewer finding.
- **Cost:** near-loss of work, broken scripts on another machine.
- **Rule:** work in the brand project from day 1; paths from configuration with explicit errors.
- **Check:** script path confinement (CONTRACT.md); Step 0 in SKILL.md.

## 22. Long silent runs and destructive agents

- **Situation:** large multi-agent runs.
- **Wrong move:** long background runs with no progress note; agents deleting files or killing processes.
- **Owner signal:** is it still running? It takes forever.
- **Cost:** waiting, and lost scratch work.
- **Rule:** progress from the journal, partial results, single-agent rounds where they suffice; the RULES line in
  every prompt; snapshot before a stage and diff after.
- **Check:** fleet gate; RULES line; hook guard.

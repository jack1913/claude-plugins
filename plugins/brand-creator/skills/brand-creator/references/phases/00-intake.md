# P0 Intake, architecture and scope

## Contents

- [Goal](#goal)
- [Inputs](#inputs)
- [Outputs and paths](#outputs-and-paths)
- [Techniques](#techniques)
- [Gate G0](#gate-g0)
- [Pitfalls](#pitfalls)
- [Enforcement](#enforcement)

## Goal

Know what the brand is for, how it relates to other brands, what the scope is (mark only, whole identity, product
family), and which external gate it must pass, before anything is drawn. Facts are gathered; taste is never asked.

## Inputs

- The owner's request, usually one line.
- Whatever already exists: a website, a repo, logo files, a document, a social profile.
- Paths to related projects when the brief mentions a parent company or sibling products.
- Profession or industry rules when the brand belongs to a regulated profession (law, medicine, finance, ...).

## Outputs and paths

| Output | Path | Content |
|---|---|---|
| Brief | `brief/BRIEF.md` | facts, goal, gating goal, architecture, hardest surface, existing assets, constraints, Forbidden |
| Facts | `FACTS.md` | owner-confirmed facts, one source each (the only claims copy may use) |
| State | `BRAND-STATE.md` | tier, mark source, architecture, language, incumbent, inventory, G0 record |

Scaffold with `brand-creator --data "${CLAUDE_PLUGIN_DATA}" new <slug> --name "<Name>" --tier <tier> --root <folder>`,
then set what G0 decided:

```
... state --project <dir> --set mark_source=authored-vector --set architecture=standalone --set language=pl
... state --project <dir> --set "incumbent=wordmark in a sans serif on the current site"
... state --project <dir> --set review_surface=local      # only when the upload question was asked and answered
... state --project <dir> --record G0 "standard tier, authored-vector mark (provisional), name decided"
```

## Techniques

1. **Read before you ask.** When a site or repo exists, fetch it and extract fonts, colours and real copy into
   `BRIEF.md` (Existing assets). Never ask for what can be read. A site with a mark in use means `incumbent` is set,
   and every board then shows it as "0 Today".
2. **Reuse what siblings already have.** If related projects exist, ask for their paths once and reuse their icons,
   fonts and letters instead of redrawing them.
3. **Infer the architecture** (default `standalone`). Map it for the book and adapters:

   | architecture | type | typical relation |
   |---|---|---|
   | standalone | master | independent |
   | family-member | master (one of several owned brands) | shares a family layer, owns its company layer |
   | product-in-family | product or sub-brand | branded-house, endorsed or sub-brand under a parent |

   Ask about family or product only when the brief or a repo shows a parent or siblings. Ask for `FAMILY.md` only
   after family-member is picked. Write the never-borrow list (both directions) into BRIEF. Details:
   [architecture.md](../architecture.md).
4. **Record the gating goal.** The external gate the brand must pass (a platform's organisation verification, a
   mandatory legal disclosure, a regulator's promotion rule) goes into BRIEF as a hard constraint. Every board is
   checked against it, and any deviation is flagged on the board.
5. **Pick one hardest surface.** The single surface most likely to break the mark: the 16 px favicon, a 20 px tray
   icon, a wide banner, a regulated letterhead. A cell on every board shows all directions on it.
6. **Region and language drive later choices**: top-level domains and trademark offices (P2), print sizes (P10),
   the glyph set in every type specimen (the audience's diacritics), the language of brand content.
7. **Regulated profession** in the brief → read [regulated-industries.md](../regulated-industries.md) before
   round 1; its rules become gating-goal lines.
8. **Name status.** When the name is open or at risk, its language is a G0 question and P2 naming runs before any
   drawing. Use the working slug `brand-<yyyymmdd>` and rename after G1.

## Gate G0

One AskUserQuestion call of **at most 3 scope questions**, each with 2 to 4 choice options and one labelled
"(Recommended)" inferred from the brief (the tool takes choice questions only, no free text). In this order, dropping the
ones that do not apply:

1. **Tier**: Quick / Standard / Full (see the SKILL.md table). Say what each one produces in one line.
2. **Architecture** (only when the brief or a repo shows a parent brand or siblings): standalone / family-member /
   product-in-family. A plain brief skips it: standalone is inferred and stated. Ask for the `FAMILY.md` path as plain
   text after family-member is picked.
3. **Name** (only when not decided): its language and status (keep / screen it / find one), or an irreversible choice
   that blocks round 1.

**The mark source is not a question.** A mark in use means `existing`. Otherwise record your provisional pick
(`generated` for a geometric or pixel idea, `authored-vector` for a type-based or drawn one) and settle it from the
chosen direction at G2, stated as a default: "Compass is drawn by code, so generated, unless you say otherwise." A baker
or a photographer cannot judge a production method, and does not need to. Ask only when the owner has already shown a
preference (a sketch they want kept, "just tidy my logo").

**The upload question, only when it applies.** When the review surface resolves to `auto` (BRAND-STATE and the plugin
setting) and the session has the Artifact tool, the same call carries one more item: "Show boards as a private Artifact
page on claude.ai (uploaded), or as a local file on this machine?", with local marked (Recommended). It is a consent,
not a scope question, and it is asked once per project: record the answer with `state --set review_surface=artifact` or
`review_surface=local`. Until it is answered, boards stay local (SKILL.md, Review surface).

Nothing else goes into the call. Facts you could not find (offer, audience, region and language, existing assets,
required surfaces) go into **one plain-text message** sent after the answers (or a second call with choice options only).
When the projects folder is unset, that message also says where the project will live: "I'll create ./<slug>/ in the
current folder unless you name another place." Then state the tier, the mark source (provisional until G2), the
expected number of rounds and a rough session length, and record G0.

When the session has no AskUserQuestion tool (a non-interactive run), the same questions (and the upload question when it
applies) go into one plain-text message:
numbered, options lettered, one marked (Recommended); then stop for the answer. A question the owner already answered in
the request, or handed to you ("you decide the rest"), is not asked: state the pick in one line and carry on.

Never ask: what people should feel, which colours the owner likes, which style they prefer, or how the mark should be
produced. The boards answer the first three; you decide the last and state it.

## Pitfalls

- An open-ended discovery question ("what should people feel when they see it?") is answered with irritation and costs
  trust. Infer from research and existing material, then show.
- Not knowing that a family thread existed cost a whole identity round in practice. Check the brief and the repo for a
  parent or siblings before round 1.
- A "logo only" scope that later grows into a whole identity forces a redo. Make the tier explicit, and design boards
  as systems (mark, wordmark, type, colour, hero together) even in Quick.
- When the owner rejects a question, ask what they want clarified instead of repeating it in other words.

## Enforcement

- Template slots: BRIEF.md (Gating goal, Architecture, Hardest surface, Existing assets, Forbidden), BRAND-STATE.md
  (tier, architecture, mark_source, incumbent, inventory, gates.G0).
- Lint: `board-lint` requires "Today" when `incumbent` is set, and an inventory before round 1 in the Full tier or
  product-in-family.
- Behaviour evals: `evals/g0-asks-scope-before-board` (G0 asks scope before any board, at most 3 scope questions),
  `evals/no-open-feelings-question`, `evals/architecture-asked-when-parent-shown` (a parent brand in the brief leads to the
  architecture question) and `evals/architecture-standalone-stated` (a plain brief to a stated standalone).

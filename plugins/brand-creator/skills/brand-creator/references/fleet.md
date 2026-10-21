# Fleets and workflows (opt-in)

Single-thread is the default and covers every phase. A fleet (subagents or one of the plugin's workflows) is an
optional speed-up for Standard and Full projects, used only after the fleet gate below and the owner's explicit yes.

## Contents

- [The fleet gate](#the-fleet-gate)
- [The workflows](#the-workflows)
- [Arguments every workflow needs](#arguments-every-workflow-needs)
- [Models: the session model is a ceiling](#models-the-session-model-is-a-ceiling)
- [The agents](#the-agents)
- [Orchestration rules](#orchestration-rules)
- [The refine loop (main thread, one reviewer call)](#the-refine-loop-main-thread-one-reviewer-call)
- [A fleet without a workflow](#a-fleet-without-a-workflow)
- [Resume](#resume)

## The fleet gate

Before any workflow or subagent fleet:

1. Fill the workflow's arguments (below) and run the plan; nothing is launched by it:

   ```
   brand-creator --data "${CLAUDE_PLUGIN_DATA}" fleet-plan <workflow> --args @<args.json> --session-model <your model>
   ```

   It runs the script with stub agents and prints the agent count, every agent with the model that will actually run,
   whether `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` is set, the size guideline and the total `maxTurns`. Exit 1 means the
   script refuses these arguments (for example more agents than approved) or an agent would run above the session
   model.
2. Tell the owner, in one message:
   - **agent count** and who they are ("3 designers, 1 judge = 4 agents");
   - **models that will actually run**, from the plan ("4 on your session model"; never the frontmatter alone);
   - **size guideline**: small under 5, medium under 10 (a cross-check is 2 to 4 agents; one lookup needs none);
   - **rough cost**: each agent costs about what that step costs single-thread, so 4 agents are roughly 4 times the
     single-thread cost of those steps plus coordination; the plan's turn total is the ceiling. The first run of a
     workflow on a project is the one to watch in `/workflows`;
   - that **single-thread is the default** and you will do it in this thread if they prefer.
3. Wait for an explicit yes. Put the approved number in `approved_agents`; the scripts refuse to start a run that plans
   more agents than that. Claude Code then shows its own approval prompt for the workflow.

A bare "ok" to something else is not a yes to a fleet. Never launch a fleet to be thorough or fast on your own
initiative; propose it and wait.

## The workflows

Each ends before a gate: no workflow spans a decision of the owner. Run each stage that needs a decision as its own
run.

| Workflow | Phase | Default agents | What it returns | Ends before |
|---|---|---|---|---|
| `directions` | P3 round 1, G2b-a reset rounds; needs the style pick (G1s) first | 3 designers + 1 judge = 4; `inventory: true` adds 1 | one board per direction in `rounds/rN/<direction>/`, the judge's ranking, grafts, MUST-FIX and NICE lists, violations | G2 (the lead assembles the round page) |
| `review-panel` | `/brand-creator:review panel` | 3 lenses + 1 judge = 4; each extra lens adds 1 | findings `{id, severity, where, evidence, why, change, effort}` per lens, then A / B / C, owner decisions, up to 5 strengths | the owner approving the list |
| `naming` | P2, brand-naming steps 3 to 11 | 2 hunters + 1 screener + 1 judge = 4 | candidates, shortlist with classes, the name checker run (`--plan` unless the owner OK'd lookups), verdicts | G1 |
| `adopt` | P11 after G6 | 2 per repository (implementer, then reviewer) | rows done / partly / not done with evidence, `cmp` and build/test results, no-decision fixes, decisions | every commit (three separate asks) |

The agent count is the number of `agent()` calls the script makes with the given arguments; `fleet-plan` counts them
by running the script with stub agents, and a test keeps the default path of every workflow under 5.

Copy panel and rule hardening are not shipped as workflows in this version. Nor is the style research (P1s): the lead builds
the style board (`rounds/r0/board.html`) single-thread, and no designer starts before the owner's style pick is recorded as
G1s, which is why `directions` takes it as an argument.

## Arguments every workflow needs

`project`, `plugin_root` (the plugin's folder: `brand-creator root` prints it), `data` (the data folder) as absolute
paths; `today` as `YYYY-MM-DD` (scripts cannot read the clock); `ceiling` (`opus`, `sonnet` or `haiku`: your session
model's family); `approved_agents` (the number the owner said yes to); `context_paths` (absolute paths the agents read
fully: BRAND-STATE.md, brief/BRIEF.md, FACTS.md, research/cliches.md, the approved board). Then per workflow:

- `directions`: its designers draw the marks themselves as SVG, which is Claude-drawn SVG, so offer it only after the
  owner's yes to that weaker way ([drawing-engines.md](drawing-engines.md)). Arguments: `round` (`r1`), `g1s` (required: the G1s record from BRAND-STATE.md, as `state --get gates.G1s` prints
  it: the owner's pick on the style board `rounds/r0/board.html`, "skipped by owner", or "n/a: round 1 drawn before the
  style step"; for a reset round it is the new pick, recorded after the style board of that round, never a skip; the script
  refuses to start without it, as `adopt` does without `g6`, and tells the designers to draw inside the picked styles), `directions` (2 to 4 `{key, name, paragraph}`; key = folder name, name = the word name on the
  board), `brief` (`decisions`, `critique`, `forbidden`, `facts`, `layers`, `constraints`, `hardest_surface`), optional
  `inventory: {repos: [{label, path}]}`, `previous_round`, `judge: false`.
- `review-panel`: `target` (`board`, `book`, `pack`, `all`), `target_paths`, optional `lenses` (design, content,
  technical, legal, platform, accessibility), `decisions`.
- `naming`: `profile` (`software`, `consumer`, `personal`), `region` (two letters), `territories` (3 to 5), optional
  `hunters` (style groups), `shortlist` (3 to 12), `lookups_ok` (true only after the owner's privacy OK).
- `adopt`: `g6` (the G6 record), `repos` (`{label, path, branch, create_branch, rows, build, findings}`), optional
  `mode: "fix"` (a second run with the reviewer's no-decision findings), `parallel_repos: true` (separate working
  trees only).

Example arguments (with placeholder paths) are in the plugin's `tests/fixtures/fleet/`.

## Models: the session model is a ceiling

The agent files set the intended tier: designer, judge and reviewer `opus`; researcher, inventory and implementer
`sonnet`. Claude Code resolves a subagent's model in this order: the per-call model, the agent file's `model`,
`CLAUDE_CODE_SUBAGENT_MODEL`, the session model; a family alias matching the session's family runs on the session's
exact model. So in a Sonnet session an `opus` agent would run on Opus, above the session. The workflows prevent that:
`ceiling` caps every agent above it to the session's family with a per-call model. With
`CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` every agent runs on `CLAUDE_CODE_SUBAGENT_MODEL` or the session model whatever the
files say; `fleet-plan` reads both variables from the shell and prints the result. Up-tiering past the session model
needs its own ask, naming the stages.

## The agents

All seven start their description with "Only for brand-creator workflows or an approved fleet; do not auto-delegate.",
carry the RULES line in their body and have a tools allowlist without `Agent` (no agent starts agents).

| Agent | Tier | Tools | Writes |
|---|---|---|---|
| `brand-designer` | opus | Read, Write, Edit, Glob, Grep, Bash | only its `rounds/rN/<direction>/` |
| `brand-judge` | opus | Read, Grep, Glob | nothing |
| `brand-reviewer` | opus | Read, Grep, Glob, Bash (check commands only) | nothing |
| `brand-researcher` | sonnet | Read, Grep, Glob, WebSearch, WebFetch, Bash (`brand-creator names` only) | nothing (the name checker writes its own memo) |
| `brand-inventory` | sonnet | Read, Grep, Glob | nothing |
| `brand-namer` | sonnet | Read, Grep, Glob, Bash (`brand-creator names --plan` only) | nothing |
| `brand-implementer` | sonnet | Read, Write, Edit, Glob, Grep, Bash | one product repository, after G6, on the owner's branch |

Paths reach the agents in the prompt (absolute), never through plugin variables. Agent types are named
`brand-creator:<agent>`.

## Orchestration rules

- Designers run in parallel only because each writes its own folder; implementers run one at a time per working
  tree (the `adopt` default is one repository at a time).
- While an agent runs, never edit the files it owns (its round folder, the repository it applies to, the work under
  review).
- No recursive fan-out: no agent has the `Agent` tool.
- Fewer than 5 agents per run by default; every prompt is time-boxed and carries the RULES line.
- Designers snapshot the project outside the round before their first write and verify it after their last;
  implementers snapshot the pack. A non-zero verify comes back as a violation for the owner to see.
- Outputs the script reads use a schema; what a person reads stays plain text in the final reply.
- Allow `Bash(brand-creator *)` in your settings (README) before a long run, or every agent's call prompts.

## The refine loop (main thread, one reviewer call)

Refinement (P5) is not a workflow. It runs in this thread, with at most one subagent call per round:

1. You confirm the numbered change list with the owner and build the refine round yourself (`rounds/rN/`, copied
   first).
2. After the fleet gate (1 agent, its model, a small cost), one `brand-creator:brand-reviewer` call gets the same
   numbered change list, the round folder and the project paths, and reports done / partly / not done per item,
   recomputed contrast on at least six pairs, the magnified marks, the glyph check, and the findings split into
   no-decision fixes and "Decisions for you". Without the yes, you do that review yourself, honestly.
3. You fix the no-decision items (or argue against them in one line), then show the board with "What changed" and
   "Weak points" and the decisions; the owner decides at G3.

## A fleet without a workflow

When workflows are turned off, or for a one-off (research fan-out with a refuting verifier: up to 3
`brand-creator:brand-researcher` with the CLAIMS schema, then one more `brand-creator:brand-researcher` call as the
refuting verifier: it re-fetches the load-bearing claims and tries to refute them; `brand-reviewer` has no web tools
and cannot do that), use the Agent tool with the same agent types and the prompt skeleton of
[prompt-fragments.md](prompt-fragments.md). The fleet gate is the same; cap the model yourself with the per-call
`model` parameter when the agent's tier is above the session model. Launch designers together only for disjoint
folders; everything else in sequence.

## Resume

Every workflow carries resume notes in its header. Relaunch the same script with the same arguments (the run id is in
`/workflows`): finished agents return their saved results, a stopped or failed agent reruns with every agent after
it. Do not change the arguments between attempts. Before relaunching, look at what a stopped agent left on disk: its
rerun is told to read it, verify it, keep what is correct and finish the rest.

## Privacy of candidate names (what is enforced and what is not)

In the `naming` workflow the hunters always run as `brand-creator:brand-namer`, and so does the screener while
`lookups_ok` is false. `brand-namer` is granted no WebSearch and no WebFetch tool (agent files set the tools; `agent()`
has no per-call tools option, which is why this is a separate agent type), so a candidate name cannot reach a search
engine or a registry through those tools. Two things are not enforced by tools. Bash is still granted (the name checker
needs it), and a shell could run `curl`; keeping it to `brand-creator names ... --plan` is the agent file's and the
prompt's instruction, and the workflow only logs a WARNING when the screener reports `lookups_used: true`. The screener
runs as `brand-researcher` (web tools granted) only when the owner gave the privacy OK and `lookups_ok` is true.

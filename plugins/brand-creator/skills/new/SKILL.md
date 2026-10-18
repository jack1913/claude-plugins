---
name: new
description: Starts a new brand project. Runs the brand-creator intake (G0 scope questions) and scaffolds BRAND-STATE.md, FACTS.md, DECISIONS.md and brief/BRIEF.md.
argument-hint: "[slug]"
disable-model-invocation: true
allowed-tools: Bash(brand-creator *)
---

# New brand project

Thin wrapper: the process lives in the orchestrator skill and the intake phase file.

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/brand-creator/SKILL.md` and
   `${CLAUDE_PLUGIN_ROOT}/skills/brand-creator/references/phases/00-intake.md` fully, and follow them from here.
2. Check first that no project is already open here:
   `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`.
   If one is found, say so and ask whether to resume it or start a separate one next to it.
3. Read what already exists (site, repo, logo files) before asking anything. Then run G0: one AskUserQuestion call
   of at most 4 choice questions (tier, mark source, architecture only when a parent or siblings show, name only when
   open), each with a "(Recommended)" option. The facts you could not find go in one plain-text message afterwards,
   which also names the project folder (`./<slug>/` here) when the projects folder setting
   (`${user_config.projects_root}`) is unset.
4. Scaffold, using the slug given here (`$ARGUMENTS`) or, when it is empty or the name is still open, `brand-<yyyymmdd>`:
   `brand-creator --data "${CLAUDE_PLUGIN_DATA}" new <slug> --name "<Name>" --tier <tier> --root <folder>`
5. Fill `brief/BRIEF.md` and `FACTS.md` from what you read and what the owner answered; set `mark_source`,
   `architecture`, `language` and `incumbent` with `state --set`; record G0 with `state --record G0 "<decision>"`.
6. Reply with the response template: what was created (paths), the tier with expected rounds and session length,
   what comes next (research or round 1), still open.

If `new` exits 3, tell the owner to run `/brand-creator:setup` first. RULES from the orchestrator apply.

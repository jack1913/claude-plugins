# Agents and workflows

What brand-creator's opt-in helpers do, and when they run.

Everything runs in one thread by default. For Standard and Full projects the plugin also ships seven agents and four
workflows. They run only after Claude has told you the agent count, the models that will actually run, the size
guideline and a rough cost, and you said yes. Every agent's description says "Only for brand-creator workflows or an
approved fleet; do not auto-delegate." That is a request to Claude, not a lock.

## The four workflows

| Workflow | Runs as | Default agents | Ends before |
| --- | --- | --- | --- |
| directions | `/brand-creator:directions` | 3 designers (each in its own `rounds/rN/<direction>/` folder) and 1 advisory judge | Your direction pick |
| review-panel | `/brand-creator:review-panel` | 3 read-only reviewers, one per angle, and 1 judge | You approve the list |

The directions workflow's designers draw the marks as SVG code themselves, so Claude offers it only after your yes to that
weaker way ([Get your marks drawn](../use/get-your-marks-drawn.md)).
| naming | `/brand-creator:naming` | 2 name hunters, 1 screener (no lookups without your privacy OK) and 1 judge | Your name pick |
| adopt | `/brand-creator:adopt` | Per repository: 1 implementer on your branch and 1 independent reviewer | Every commit. It never commits |

The directions workflow starts only after you picked a style, or skipped that step before your first board. If you reject
every direction, it starts again only after you pick a style on a new style board. Nothing is drawn before.

## What the agents can do

| Agent | Limits |
| --- | --- |
| `brand-designer` | Builds one board in its own folder |
| `brand-judge` | Read only |
| `brand-reviewer` | Checks only; never edits a source file |
| `brand-researcher` | Reads public sources |
| `brand-inventory` | Read only |
| `brand-implementer` | Changes one repository, on your branch |
| `brand-namer` | Has no web search or fetch tool |

The designer, judge, researcher, inventory and namer agents set `omitClaudeMd`, so they take everything from the prompt
they are given and do not read your CLAUDE.md files. The implementer and the reviewer do not set it, so they read your
CLAUDE.md files like any session. None of them can start other agents. Refining a pick stays in your session, with at most one reviewer call per round.
`brand-namer` has no web search or fetch tool, but it still has a shell. Keeping names private there rests on its
instructions, not only on its tool list.

## Before you say yes

- Claude can dry-run a workflow with stand-in agents (no model is called) to show the exact numbers.
- If you set `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`, every agent runs on that one model.
- Allow the `Bash(brand-creator *)` rule ([Permissions](permissions.md)) before a long run, or each agent's call prompts.
- You can turn workflows off with `disableWorkflows`. Nothing else changes.

## Related

- [Costs](costs.md)
- [Commands](commands.md)

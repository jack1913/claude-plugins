# Claude Code versions

Which Claude Code version brand-creator features need. The minimum for the whole plugin is in the
[README](../../../README.md#install).

The minimum is the highest row of the runtime rows below.

One hardening is not a runtime row. The guard hook sets `onFailure: "block"`, which Claude Code 2.1.295 and later honour:
a missing Python then blocks the call with a notice. Older versions ignore the field, and a missing `python3` lets the
guard do nothing there.

| Feature | Needs Claude Code | Why |
| --- | --- | --- |
| `userConfig` with `options` (the `review_surface` picker) | 2.1.271 | Older versions cannot load a plugin that declares `options` |
| `omitClaudeMd` in the designer, judge, researcher, inventory and namer agents | 2.1.271 | They take everything from the prompt |
| `/config` rows for plugin options | 2.1.269 | |
| `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` | 2.1.257 | One model for every subagent and workflow agent |
| Partial result when an agent reaches `maxTurns` | 2.1.246 | Older versions stop without the partial marking |
| Workflow size guideline (`workflowSizeGuideline`) | 2.1.219 | Small under 5 agents, medium under 10 |
| `/design`, the second way to get marks drawn | 2.1.234 | Claude Code's own artboard; it also needs a claude.ai login on a Pro, Max, Team or Enterprise plan |
| `claude plugin eval` (maintainers only) | 2.1.269 | Behaviour evals |
| `claude plugin validate` of marketplace and plugin together (maintainers only) | 2.1.289 | Release check |

## Related

- [Platform support](platform-support.md)

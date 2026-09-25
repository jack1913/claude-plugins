# Upstream

- **Upstream:** https://github.com/AvdLee/SwiftUI-Agent-Skill, folder `skills/swiftui-expert-skill/`, MIT
- **Baseline tag:** `5.1.0` (`b24e68a965dc4b5bd2cc41dc60c094a26a9379ce`)
- **Local import tag:** `upstream-5.1.0`, this repo's first commit: the folder byte-for-byte at the baseline

`git diff upstream-5.1.0 -- plugins/swift/skills/swiftui` shows every change listed under Deviations. `maintenance/upstream-diff.sh [ref]` shows what upstream changed after the baseline. Porting is manual: read the diff, port what fits, bump the baseline above, add a Ported row.

## Deviations

| File | Change | Why |
|---|---|---|
| `agents/`, `assets/` | Deleted | Codex agent config and logos (~430 KB); Claude Code uses neither |

## Ported

| Upstream ref | What we took | Date |
|---|---|---|
| `5.1.0` | Initial import | 2026-09-25 |

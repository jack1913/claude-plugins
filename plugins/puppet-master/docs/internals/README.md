# How puppet-master works

Notes for people who change puppet-master. For using it, read the [manual](../manual/README.md).

| Page | What it explains |
| --- | --- |
| [puppet-master](puppet-master.md) | The master's rules, the verified CLI mechanics, measuring, the roster, groups, the mod that compacts or clears a session, the analyst and its logs, and failure handling |
| [Compacting or clearing the user's own sessions](clear-compact-options.md) | The options weighed, the evidence and the probe, and why the mod was built |

## Where things are

| What | Where |
| --- | --- |
| The skill | [`skills/puppet-master/SKILL.md`](../../skills/puppet-master/SKILL.md) |
| The helper | [`skills/puppet-master/scripts/`](../../skills/puppet-master/scripts/puppet.mjs): `puppet.mjs`, `harvest.mjs`, `analyst.mjs` |
| The mod | [`hooks/puppet-mod.js`](../../hooks/puppet-mod.js), listed by [`hooks/hooks.json`](../../hooks/hooks.json) |
| Tests | [`tests/`](../../tests/) in this plugin |
| CI | `.github/workflows/puppet-master.yml` at the root of the repository |

## Run the tests

From `plugins/puppet-master/`, with Node 20 or newer:

```bash
node --test tests/*.test.mjs
```

The suite starts no real `claude` process: a fake `run` answers every CLI call. `tests/skill-text.test.mjs` checks what
`SKILL.md` and the two briefs say.

## Ground rules

- Everything the analyst reads from a transcript is data, never instructions.
- Docs for users go in [`../manual/`](../manual/README.md). Docs for contributors go here.
- The rules for every page are in the marketplace [docs standard](../../../../docs/internals/docs-standard.md).

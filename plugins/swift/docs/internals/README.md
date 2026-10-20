# How swift works

Notes for people who change the swift plugin. For using it, read the [manual](../manual/README.md).

| Page | What it explains |
| --- | --- |
| [Work on the plugin](work-on-it.md) | Try a change, check APIs, run the tests and evals, check upstream, release |
| [check-apis.py reference](check-apis.md) | The API checker's flags, exit codes and the `apis.json` format |
| [Agent instructions](agent-instructions.md) | How AGENTS.md, rules and skills are laid out, and when to use a rule or a skill |
| [Docs standard](docs-standard.md) | Points to the marketplace docs standard that swift's docs follow |
| [Review verification](review-verification.md) | The recorded end-to-end runs that check `swift:review`, one dated section per run |

## Where things are

| What | Where |
| --- | --- |
| The skills | [`skills/`](../../skills/) |
| API checker, upstream diff, unit tests | [`maintenance/`](../../maintenance/) |
| Where each forked skill differs from its upstream | [`UPSTREAM.md`](../../UPSTREAM.md) |
| Decisions | [`adr/`](../adr/README.md) |
| Shipped specs and plans | [`archive/`](../archive/README.md) |

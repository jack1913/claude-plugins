# Decision records

Why the marketplace works the way it does. A plugin's own decisions live in that plugin (swift: `plugins/swift/docs/adr/`).

| ADR | Decision | Status |
| --- | --- | --- |
| [ADR-0001](ADR-0001-one-monorepo-marketplace.md) | One monorepo marketplace, each plugin a self-contained folder | accepted |
| [ADR-0002](ADR-0002-per-plugin-versions-and-tags.md) | A plugin's version lives only in its `plugin.json`; releases are tagged per plugin | accepted |
| [ADR-0003](ADR-0003-one-docs-standard.md) | One docs standard for the marketplace and every plugin; each plugin owns its manual | accepted |
| [ADR-0004](ADR-0004-ci-runs-on-main-and-pull-requests-never-on-tags.md) | CI runs on main and pull requests, never on tags; a release is tagged after its CI passes | accepted |

New records follow [ADR-TEMPLATE.md](ADR-TEMPLATE.md).

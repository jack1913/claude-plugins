# Decision records

Why swift works the way it does, one decision per file. Marketplace-wide decisions are in the [marketplace ADRs](../../../../docs/adr/README.md).

| Number | Title | Status | Supersedes |
| --- | --- | --- | --- |
| [ADR-0001](ADR-0001-private-single-plugin-marketplace.md) | Ship as a private single-plugin marketplace, enabled per project | superseded by ADR-0014 | — |
| [ADR-0002](ADR-0002-plugin-name-namespaces-skills.md) | The plugin name `swift` namespaces every skill | accepted | — |
| [ADR-0003](ADR-0003-explicit-semver-one-version-home.md) | Explicit SemVer in one place, tagged with `claude plugin tag` | accepted | — |
| [ADR-0004](ADR-0004-own-copy-of-upstream.md) | Own a hand-ported copy of upstream, never a live dependency | accepted | — |
| [ADR-0005](ADR-0005-narrow-attributed-borrowing.md) | Borrow only narrow, attributed passages from other skill repos | accepted | — |
| [ADR-0006](ADR-0006-separate-design-skill.md) | Design guidance lives in a separate `swift:design` skill | accepted | — |
| [ADR-0007](ADR-0007-project-design-layer-wins.md) | A project's own design layer wins over the plugin's example literals | accepted | — |
| [ADR-0008](ADR-0008-liquid-glass-stays-opt-in.md) | Liquid Glass stays opt-in in `swift:swiftui` | accepted | — |
| [ADR-0009](ADR-0009-check-apis-resolves-against-apple-indexes.md) | check-apis resolves names against Apple's indexes; the manifest holds only what can't be derived | accepted | — |
| [ADR-0010](ADR-0010-own-copy-fork-model-extended.md) | The own-copy fork model extends to the concurrency and testing upstreams | accepted | — |
| [ADR-0011](ADR-0011-swift-review-skill.md) | `swift:review` is an authored, slash-only, report-only review skill that points into `swift:design` | accepted | — |
| [ADR-0012](ADR-0012-marketplace-named-jack1913-plugins.md) | The marketplace is named `jack1913-plugins` and signed by Jacek Pytlik | superseded by ADR-0014 | — |
| [ADR-0013](ADR-0013-project-rules-win-over-skill-defaults.md) | A project's own rules win over the code skills' defaults | accepted | — |
| [ADR-0014](ADR-0014-catalogue-moves-to-claude-plugins.md) | The catalogue is `jack1913/claude-plugins`, marketplace `jack1913`; this repo holds only the plugin | accepted | ADR-0001, ADR-0012 |
| [ADR-0015](ADR-0015-plugin-moves-into-the-claude-plugins-monorepo.md) | The plugin moves into `jack1913/claude-plugins` as `plugins/swift/` | accepted | — |

New records follow [ADR-TEMPLATE.md](ADR-TEMPLATE.md).

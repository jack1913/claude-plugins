# ADR-0012: The marketplace is named `jack1913-plugins` and signed by Jacek Pytlik

- **Status:** superseded by ADR-0014 (the marketplace is named `jack1913` and lives in `jack1913/claude-plugins`)
- **Date:** 2026-09-28
- **Source:** the owner's request (2026-09-28) for a professional marketplace name and a signed author; [Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces) (name rules, reserved names, owner fields, `renames`, `marketplace remove`); ADR-0001 (the marketplace this renames)

## Context

ADR-0001 named the marketplace `swift-plugin`, after its only plugin and its GitHub repo. In the `/plugin` Marketplaces list that reads as a repo name, not as whose plugins these are. The manifests were signed `jack1913`.

The marketplace name is public-facing and part of every install ID (`swift@swift-plugin`). Claude Code reserves several `claude-…` and `anthropic-…` names, and blocks names that impersonate official marketplaces, such as `official-claude-plugins`. It re-checks both on every load, not only when a marketplace is added. The `renames` map migrates plugin names only; nothing migrates a marketplace name.

## Decision

- The marketplace `name` is `jack1913-plugins`: the owner's GitHub handle, and room for more plugins. It avoids `claude` and `anthropic`, so a future reserved-name check can't catch it.
- `owner` in `marketplace.json` and `author` in `plugin.json` are `{ "name": "Jacek Pytlik", "url": "https://github.com/jack1913" }`, with no email.
- The GitHub repo stays `jack1913/swift-plugin`, so `claude plugin marketplace add jack1913/swift-plugin` is unchanged.
- The plugin name `swift`, its skills and the `swift--v<version>` tags don't change.

Rejected:
- `jack1913-claude-plugins`: close to the reserved and impersonation-blocked names, which are re-checked on every load.
- Keeping `swift-plugin`: it names the repo, not the owner.

## Consequences

- The install ID changes from `swift@swift-plugin` to `swift@jack1913-plugins`. That breaks existing installs, so it ships as 0.2.0.
- An older install moves by hand: uninstall, remove the old marketplace, add it again, install under the new ID. The manual's "Move an install from swift-plugin" section has the commands. Every repo that commits `swift@swift-plugin`, example-app included, needs that move and a commit.
- Records written before 0.2.0 keep the old ID, because they describe what was run at the time.

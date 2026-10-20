# ADR-0014: The catalogue is `jack1913/claude-plugins`, marketplace `jack1913`; this repo holds only the plugin

- **Status:** accepted
- **Supersedes:** ADR-0001, ADR-0012
- **Date:** 2026-10-19
- **Source:** the owner's decision (2026-10-19) to publish all of Jacek Pytlik's plugins from one marketplace; the catalogue repo's `.claude-plugin/marketplace.json` and `README.md` (<https://github.com/jack1913/claude-plugins>); [Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces) (`git-subdir` sources, `marketplace remove`); ADR-0001 and ADR-0012 (the decisions this replaces)

## Context

ADR-0001 made this repo a marketplace with one plugin, and ADR-0012 named it `jack1913-plugins`. A second plugin, `brand-creator`, now exists. One marketplace per plugin repo would make the owner's plugins several marketplaces to add, update and trust, so they move to one catalogue.

The marketplace name is part of every install ID, and Claude Code can't migrate a marketplace name (ADR-0012), so the move breaks existing installs.

## Decision

- The catalogue is the repo `jack1913/claude-plugins`; its marketplace is named `jack1913`. It lists `swift` with the source `{"source": "git-subdir", "url": "https://github.com/jack1913/swift-plugin.git", "path": "plugins/swift"}`.
- This repo stops being a marketplace: `.claude-plugin/marketplace.json` is deleted, and `plugins/swift/` is the only thing an install copies, as before.
- A repo enables the plugin with `claude plugin marketplace add jack1913/claude-plugins` and `claude plugin install swift@jack1913`, each with `--scope project` (committed) or `--scope local` (per checkout). Both default to user scope, so the explicit `--scope` rule of ADR-0001 stays.
- The plugin name `swift`, its skills, `plugin.json` as the only version home (ADR-0003) and the `swift--v<version>` tags don't change. `claude plugin tag` still checks `plugin.json`; with no marketplace file in this repo it has no entry to compare.
- The owner and author signature of ADR-0012 stays: `{ "name": "Jacek Pytlik", "url": "https://github.com/jack1913" }`, no email.
- The GitHub repo stays `jack1913/swift-plugin`: the catalogue's `git-subdir` source points at it.

Rejected:

- Keeping `jack1913-plugins` here next to the catalogue: two marketplaces would list the same plugin under two install IDs.
- Copying the plugin into the catalogue repo (`"source": "./plugins/swift"`): two copies, and the forked-skill history and `UPSTREAM.md` deviations live here.

## Consequences

- The install ID changes from `swift@jack1913-plugins` to `swift@jack1913`. That breaks existing installs, so it ships as 0.3.0 (before 1.0 a breaking change bumps the minor version).
- Both repos stay private: installing needs read access to `jack1913/claude-plugins` and to `jack1913/swift-plugin`, and background auto-updates need `GITHUB_TOKEN`.
- A release now has two steps: tag and push this repo, then installs pick the version up through `claude plugin marketplace update jack1913`. The catalogue entry carries no `version`, so nothing there changes per release.
- An older install moves by hand. The manual's "Move an install to the jack1913 marketplace" section has the commands. Every repo that commits `swift@jack1913-plugins` or `swift@swift-plugin`, example-app included, needs that move and a commit.
- Records written before 0.3.0 keep the old IDs, because they describe what was run at the time.

## Update 2026-10-19

The Status line used to read: "accepted; supersedes ADR-0001 and ADR-0012; the `git-subdir` source and the separate plugin repo are superseded by ADR-0015". The supersession of ADR-0001 and ADR-0012 is now the Supersedes line. ADR-0015 replaces only the `git-subdir` source and the separate plugin repo, so this record stays accepted for the rest: the marketplace is `jack1913`, in the repo `jack1913/claude-plugins`.

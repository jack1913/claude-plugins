# Enable the plugin in a Swift repo

Install swift once per Swift project, so it loads only where you work on Swift. It adds five skills; what each one does is in [Commands](../reference/commands.md).

## Install it into one repo

Run inside the Swift repo:

```bash
claude plugin marketplace add jack1913/claude-plugins --scope project
claude plugin install swift@jack1913 --scope project
```

Always pass `--scope`. Both commands default to user scope, which loads the plugin in every repo (`claude plugin install --help`).

| Scope | Writes | Who gets the plugin |
| --- | --- | --- |
| `--scope project` | the repo's committed `.claude/settings.json` | everyone who clones the repo |
| `--scope local` | the gitignored `.claude/settings.local.json` | only you, only this checkout |

The plugin loads only where `enabledPlugins` lists it. The marketplace and the plugin are both in the public GitHub repo `jack1913/claude-plugins`.

If `marketplace add` fails — for example `git` can't reach GitHub — fall back to loading straight from a checkout: [`claude --plugin-dir`](../../internals/work-on-it.md#try-a-change).

## Check it worked

Start a new session and type `/swift:`. The menu lists the five skills. To print the same inventory from a checkout, run `claude --plugin-dir . plugin details swift` in the plugin folder:

```text capture=plugin-details
Component inventory
  Skills (5)  concurrency, design, review, swiftui, testing
```

## Pick up a new release

Installs are copies, and this marketplace doesn't update on its own unless you turn that on in `/plugin` → Marketplaces. A repo keeps the version it installed until you run:

```bash
claude plugin marketplace update jack1913
claude plugin update swift@jack1913
```

Then start a new session or run `/reload-plugins`. An update only arrives when a release raised the plugin's version.

## Upgrading from an older install

Older installs used the marketplace `swift-plugin` or `jack1913-plugins`, so their ID is `swift@swift-plugin` or `swift@jack1913-plugins`. Claude Code can't rename a marketplace for you. In each repo, uninstall the old ID, run `claude plugin marketplace remove <old>`, then run the two install lines above. `marketplace remove` also unloads the old ID in your other repos, so move those too.

Commit the repo's changed `.claude/settings.json`. If it still lists the old entries after that, delete them by hand. What changed and why is in the [changelog](../../../CHANGELOG.md).

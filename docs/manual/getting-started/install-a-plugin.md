# Install a plugin

Two commands and you're in. This page is the one place for install, update and remove.

## Install in Claude Code

Type these in a Claude Code session:

```text illustrative
/plugin marketplace add jack1913/claude-plugins
/plugin install batbelt@jack1913
```

Swap `batbelt` for `brand-creator` to get that one. Installing **swift**? Use [For your whole team](#for-your-whole-team)
below: it goes in once per Swift project. Not sure which plugin? [Choose a plugin](choose-a-plugin.md).

Claude asks where to put it:

| Pick | Who gets it |
|---|---|
| **user** | you, in every project. The usual pick. |
| **project** | everyone who works on this repository |
| **local** | just you, just this repository |

Type `/` and you'll see the plugin's commands, like `/batbelt:grill-me`. Not there? Run `/reload-plugins`.

## Install from a terminal

```bash
claude plugin marketplace add jack1913/claude-plugins
claude plugin install batbelt@jack1913
```

It shows up in your next Claude Code session, or run `/reload-plugins` in one that's already open.

## For your whole team

Use this for swift, and for any plugin everyone on a repository should have.

1. Inside the repository, run:

   ```bash
   claude plugin marketplace add jack1913/claude-plugins --scope project
   claude plugin install swift@jack1913 --scope project
   ```

2. Commit `.claude/settings.json`. It now lists the plugin.
3. Each teammate runs the second line once on their own machine.

A repository without these lines never sees the plugin, so run them in every Swift project that needs it.

## Keep it fresh

Plugins from this marketplace don't update on their own: auto-update is off by default for third-party marketplaces
like this one. A new release waits until you update.

To update one plugin, in a terminal:

```bash
claude plugin update batbelt@jack1913
```

To update everything you installed from here, run `/plugin`, open **Marketplaces**, pick `jack1913` and choose
**Update marketplace**.

`/plugin marketplace update jack1913` on its own is different: it only refreshes which versions are on offer. Your
installed plugins stay on their current version until you update them as above.

Curious what changed? See the changelogs for [brand-creator](../../../plugins/brand-creator/CHANGELOG.md),
[swift](../../../plugins/swift/CHANGELOG.md) and [batbelt](../../../plugins/batbelt/CHANGELOG.md).

## Remove it

```bash
claude plugin uninstall batbelt@jack1913
```

Installed for the team? `claude plugin uninstall swift@jack1913 --scope project` takes it out of the repository's
`.claude/settings.json`, which removes it for everyone once you commit. In Claude Code, `/plugin uninstall` asks first:
press **y** to turn it off just for you, or **u** to remove it for everyone.

Something not working? See [Troubleshooting](../reference/troubleshooting.md).

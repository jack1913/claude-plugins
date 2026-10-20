# Troubleshooting

Find what you see, then do what's next to it. For install steps, see [Install a plugin](../getting-started/install-a-plugin.md).

| You see | Do this |
|---|---|
| The plugin's commands don't show when you type `/` | Run `/reload-plugins`. Still missing? Run `claude plugin list` in a terminal: the plugin should be listed and enabled. If it isn't, [install it](../getting-started/install-a-plugin.md) |
| `/plugin` lists no `jack1913` plugins | The marketplace isn't added. Run `/plugin marketplace add jack1913/claude-plugins` |
| `marketplace add` fails | Check the spelling: `jack1913/claude-plugins`, no `https://` and no `.git`. Then check that you can reach github.com. Claude Code's [plugin troubleshooting](https://code.claude.com/docs/en/plugins/troubleshooting#add-a-marketplace) matches each error message to its fix |
| The plugin works in one project but not another | It was installed at **project** or **local** scope, so it only exists where you installed it. Run the install lines in the other project, or install at **user** scope to get it everywhere |
| swift never starts | swift goes in once per Swift project. Run its [project-scope lines](../getting-started/install-a-plugin.md#for-your-whole-team) inside that project, then start a new session |
| You're on an old version after a release | Updates don't arrive on their own. Run `claude plugin update <plugin>@jack1913`, then start a new session. [Why and how](../getting-started/install-a-plugin.md#keep-it-fresh) |
| `/plugin marketplace update jack1913` ran, but the version didn't change | That command only refreshes what's on offer. Update the plugin itself with `claude plugin update <plugin>@jack1913` |
| A release is out but the update finds nothing new | A plugin updates only when its version number goes up. If the maintainer pushed a change without bumping it, there is nothing to install yet. Ask in a [GitHub issue](https://github.com/jack1913/claude-plugins/issues) |
| A teammate doesn't get the plugin you committed | Committing `.claude/settings.json` turns it on for them but doesn't download it. Each teammate runs `claude plugin install <plugin>@jack1913 --scope project` once |
| You want it gone | `claude plugin uninstall <plugin>@jack1913`. Add `--scope project` if you installed it for the team. To drop the whole marketplace: `claude plugin marketplace remove jack1913` (this uninstalls everything from it) |

Still stuck? Open an issue at [jack1913/claude-plugins](https://github.com/jack1913/claude-plugins/issues) and say which
plugin, what you typed and what you saw. Each plugin's own README has a troubleshooting section for problems inside it.

# Template: Plugin README

Copy the block below into `plugins/<name>/README.md` and replace every `<…>`. Links in it are written from that location. Rules: [docs standard](../docs-standard.md).

````markdown illustrative
# <name>

<One sentence: what you can do with it. The same words as `description` in plugin.json.>

## Install

```text illustrative
/plugin marketplace add jack1913/claude-plugins
/plugin install <name>@jack1913
```

Needs Claude Code <minimum> or newer (this line is that fact's only home).
<Optional: the scope to pick, e.g. "Install it once per Swift project: add `--scope project`.">
Other ways to install (from a shell, for a whole team):
[Install a plugin](../../docs/manual/getting-started/install-a-plugin.md).

## Try it

<The one thing to type or say first, and what you'll see. Real output, trimmed with `…`.>

## What you can do

| Command | Starts | What it's for |
| --- | --- | --- |
| `/<name>:<skill>` | you or Claude | <one line> |
| `/<name>:<skill>` | you only | <one line> |

Every command, with its arguments: [Commands](docs/manual/reference/commands.md).

## What it adds to your sessions

<Skills whose descriptions load every turn, hooks, agents, MCP servers, files it writes, anything it
sends out. One short bullet each. Plugins run with your permissions, so say what this one touches.>

## What it never does

<At most three bullets. Link to the full list if there is one.>

## Something off?

| You see | Do this |
| --- | --- |
| <symptom> | <fix> |

More: [Troubleshooting](docs/manual/reference/troubleshooting.md).

## Learn more

- [Manual](docs/manual/README.md)
- [Changelog](CHANGELOG.md)
- [How it works](docs/internals/README.md) (for contributors)

<Licence line.>
````

# Template: Commands reference

Copy the block below into `plugins/<name>/docs/manual/reference/commands.md` and replace every `<…>`. Links in it are written from that location. Rules: [docs standard](../docs-standard.md).

````markdown illustrative
# Commands

Everything <plugin> adds to Claude Code. "You only" means it runs only when you type it; "you or
Claude" means Claude can also start it when your request matches.

## Commands and skills

| Command | Starts | What it does | Arguments |
| --- | --- | --- | --- |
| `/<plugin>:<skill>` | you or Claude | <same words as the skill's description, first sentence> | — |
| `/<plugin>:<skill>` | you only | <…> | `<argument-hint>` |

## <Command name>

<Repeat for each command that takes arguments or needs more than one line.>

| Argument | What it does | Default |
| --- | --- | --- |
| `--flag` | <…> | <…> |

Example:

> /<plugin>:<skill> --flag

## Agents

<Only if the plugin ships agents. They never start on their own unless the row says so.>

| Agent | Used by | What it does |
| --- | --- | --- |
| `<plugin>:<agent>` | <command or workflow> | <one line> |
````

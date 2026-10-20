# Manual page shape: reference

Read at [author-manual.md](author-manual.md) when you write a page for `docs/manual/reference/` (commands, settings, troubleshooting). A reference page answers "what exactly is X?": a title that is a noun, tables, no storytelling. Steps belong on a how-to page.

Replace every `<...>`. One row per real command, flag or setting, taken from the repo's own help output or config, never from memory.

````markdown illustrative
# Commands

Everything <repo> offers on the command line.

## Commands

| Command | What it does | Arguments |
| --- | --- | --- |
| `<cli> <verb>` | <one line, same words as the help text> | `<usage>` |

## <Command name>

<Repeat for each command that takes arguments or needs more than one line.>

| Argument | What it does | Default |
| --- | --- | --- |
| `--flag` | <...> | <...> |

Example:

```bash
$ <cli> <verb> --flag
```
````

A settings page uses the same shape with a `Setting | What it does | Default` table. A troubleshooting page is a `You see | Do this` table.

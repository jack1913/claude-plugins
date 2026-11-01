# Manual page shape: reference

Read at [author-manual.md](author-manual.md) when you write a page for `docs/manual/reference/` (commands, settings, troubleshooting). A reference page answers "what exactly is X?": a title that is a noun, tables, no storytelling. Steps belong on a how-to page.

Replace every `<...>`. One row per real command, flag or setting, taken from the repo's own help output or config, never from memory. When the repo has a front-end per platform, a flag table has one column per front-end plus Effect: `| sh | PowerShell | Effect |`. Every command block has its twin right after it, sh first.

````markdown illustrative
# Commands

Everything <repo> offers on the command line.

<Two or three common recipes as commands, then a captured example of what one of them shows.>

## Commands

| Command | What it does | Arguments |
| --- | --- | --- |
| `<cli> <verb>` | <one line, same words as the help text> | `<usage>` |

## <Command name>

<Repeat for each command that takes arguments or needs more than one line.>

| Argument | What it does | Default |
| --- | --- | --- |
| `--flag` | <...> | <...> |

With a front-end per platform:

| sh | PowerShell | Effect |
| --- | --- | --- |
| `--flag` | `-Flag` | <...> |

Example:

```bash
<cli> <verb> --flag
```

```powershell
<cli> <verb> -Flag
```

## See also

- <The how-to pages that use these commands.>
````

A settings page uses the same shape with a `Setting | What it does | Default` table. A troubleshooting page is a `You see | Do this` table. A reference page sits outside the tour: it ends with See also, never with a Next link.

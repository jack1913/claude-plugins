# Manual page shape: how-to

Read at [author-manual.md](author-manual.md) when you write a how-to page in `docs/manual/` (one task). A first-run page follows [manual-page-getting-started.md](manual-page-getting-started.md) instead. The rules are in `docs/internals/docs-standard.md` when the repo has it; this is the shape. One page, one task, and a how-to keeps the explanation its output needs: what the reader just saw, and how to read it. Deeper "why" goes to `docs/internals/`, linked once.

Replace every `<...>`. Ground each output block as the author-manual step says: a provenance tag on the fence, `illustrative` when it is a mock. Drop a section the task does not need, except If something goes wrong: every how-to keeps it. Keep the order of the rest.

When the repo has a front-end per platform (a `.sh` and a `.ps1`, say), every command block has its twin right after it, sh first, with no heading between them. Output from a platform nobody captured is `illustrative`.

````markdown illustrative
# <Verb phrase: "Update your install">

<One or two sentences: what you get, and the guarantee: what it never does without asking.>

## Before you start

- <What must be installed or true first. Link the page that sets it up.>

<What to type:>

```bash
<command> <argument>
```

```powershell
<command> <Argument>
```

You'll see something like this:

```console capture=<slug>
<Real output, trimmed with ... . Never invented.>
```

*(A real run: <where and how this was captured>. <When trimmed: "An excerpt:" and what was cut.>)*

## What it means

<What the reader just saw: what each part of the output tells them, as prose or a table.>

## <A variation: verb phrase>

<The same pattern again: the command and its twin, its captured output and caption, what it means.>

> [!IMPORTANT]
> <The one guarantee or destructive step the reader must not miss. At most one callout per section.>

## Check it worked

<How the reader knows it worked: a file that now exists, a message, a passing build.>

## If something goes wrong

| You see | Do this |
| --- | --- |
| <the exact error text> | <the fix> |

## Upgrading from an older version

<Only when the behaviour changed between releases: "Installs from <version> and earlier ...". Past
versions stay on this page.>

## Options

<Two or three common recipes as commands. The full table lives on the reference page:
[Commands](reference/commands.md).>

Mechanics: [<how it works>](../internals/<page>.md).

**Next:** [<the next page in the tour>](<page>.md) — <why to read it next>.
````

The **Next:** link points at the next entry of the manual index's Do a task list; the last page in the tour says so instead ("That's the tour.").

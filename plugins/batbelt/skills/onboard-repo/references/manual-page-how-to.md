# Manual page shape: how-to and getting started

Read at [author-manual.md](author-manual.md) when you write a page for `docs/manual/use/` (one task) or `docs/manual/getting-started/` (first run). The rules are in `docs/internals/docs-standard.md` when the repo has it; this is the shape. One page, one task; link instead of mixing in reference or explanation.

Replace every `<...>`. Ground each output block as the author-manual step says: `capture=<slug>` or `illustrative`.

````markdown illustrative
# <Verb phrase: "Review a screen">

<One or two sentences: what you'll get and when you'd want it.>

## Before you start

- <What must be installed or true first. Link the page that sets it up.>

## <Do it: verb phrase>

1. <Step. What to type or say:>

   ```bash
   $ <command> <argument>
   ```

2. <Next step.>

You'll see something like this:

```console capture=<slug>
<Real output, trimmed with ... . Never invented.>
```

## Check it worked

<How the reader knows it worked: a file that now exists, a message, a passing build.>

## If something goes wrong

| You see | Do this |
| --- | --- |
| <symptom> | <fix> |

## Related

- <Next task, the reference page for this command, or the why-page. Two or three links.>
````

A getting-started page has the same shape; its title is a verb phrase such as "Install <repo>", and it ends at the first working result.

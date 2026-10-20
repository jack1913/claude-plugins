# Template: How-to page

Copy the block below into a task page in `plugins/<name>/docs/manual/use/` and replace every `<…>`. Links in it are written from that location. Rules: [docs standard](../docs-standard.md).

````markdown illustrative
# <Verb phrase: "Review a screen">

<One or two sentences: what you'll get and when you'd want it.>

## Before you start

- <What must be installed or true first. Link the page that sets it up.>

## <Do it: verb phrase>

1. <Step. What to type or say:>

   > /<plugin>:<command> <argument>

2. <Next step.>

You'll see something like this:

```text
<Real output, trimmed with … . Never invented.>
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

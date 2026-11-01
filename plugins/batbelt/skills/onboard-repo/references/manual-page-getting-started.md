# Manual page shape: getting started

Read at [author-manual.md](author-manual.md) when you write a page for `docs/manual/getting-started/` (first run). The rules are in `docs/internals/docs-standard.md` when the repo has it; this is the shape. The page ends at the first working result.

Replace every `<...>`. Ground each output block as the author-manual step says: a provenance tag on the fence, `illustrative` when it is a mock. When the repo has a front-end per platform, every command block has its twin right after it, sh first. Output from a platform nobody captured is `illustrative`.

````markdown illustrative
# Install <repo>

By the end of this page <repo> is installed and you have seen it work once.

## Prerequisites

- <What must be on the machine first, per platform. Link where to get it.>

## Quickstart

```bash
<install command>
```

```powershell
<install command>
```

## <The guided path: what the installer asks>

<What the reader sees and chooses. When a screen cannot be shown in a code block, say what it shows.>

## Preview before you apply

<The dry-run command, then its captured output and what it means.>

## Watch it apply

```console capture=<slug>
<Real output, trimmed with ... . Never invented.>
```

*(A real run: <where and how this was captured>.)*

## Check it worked

<The command, file or message that proves it worked.>

## Skip the guided path

<The non-interactive command for scripts, and a link to the flags on the reference page.>

**Next:** [<the first task in the tour>](../<task>.md) — <why to read it next>.
````

# Contributing

Thanks for helping. This page tells you where things are and which checks to run before you push.

## Where things are

Each plugin is a folder under `plugins/` with its own manifest, docs, tests, changelog and version. The marketplace file
and the CI workflows sit at the root. The full map is in [Repository layout](docs/internals/layout.md).

A change to one plugin stays inside `plugins/<name>/`, plus its workflow (and `tests/` for batbelt). A plugin's own
`AGENTS.md` or `README.md` has the rules for working on it.

## Write docs

Every page follows the [docs standard](docs/internals/docs-standard.md): which kind of page it is, where it lives, and
the friendly, short, task-first voice. Start from a [template](docs/internals/templates/README.md). A decision that
needs a record goes in [`docs/adr/`](docs/adr/README.md).

## Add a plugin

A folder, a marketplace entry, a workflow and a release-tag ruleset. Steps: [Add a plugin](docs/internals/add-a-plugin.md).

## Run the tests

Each plugin has its own checks. Commands and where to run them: [Tests](docs/internals/tests.md).

## Release

Each plugin releases on its own, and its tag is made with `claude plugin tag plugins/<name>`, never `git tag`. Steps:
[Release a plugin](docs/internals/release.md).

## What CI checks

- `docs.yml` checks every Markdown file against the docs standard.
- Each plugin's workflow runs its tests on a push to `main` or a pull request that changes its folder. A push to
  another branch runs nothing: open a pull request, or start the workflow with `gh workflow run <workflow> --ref <branch>`.
- `marketplace.yml` checks that `marketplace.json` and the `plugins/` folder agree, and that every workflow keeps the
  agreed shape (`.github/scripts/check-workflows.py`).

Run the docs checks yourself from the repository root:

```bash
python3 .github/scripts/check-docs-standard.py
npx markdownlint-cli2 "**/*.md"
lychee --config lychee.toml --root-dir "$(pwd)" './**/*.md'
python3 .github/scripts/check-marketplace.py
```

## Commits

Tag releases with `claude plugin tag`, not `git tag` (see [Release a plugin](docs/internals/release.md)).

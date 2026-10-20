# Development

How to work on brand-creator: load a checkout, run the tests, see what CI runs. The rules for every page are in the
[docs standard](../../../../docs/internals/docs-standard.md).

## Load a local checkout

Use a checkout for one session instead of the installed copy:

```bash
claude --plugin-dir /path/to/claude-plugins/plugins/brand-creator
```

## Run the tests

Run from `plugins/brand-creator/`:

```bash
BRAND_CREATOR_DATA=<set-up data dir> tests/run-all.sh
```

- `tests/run-all.sh` runs pytest and `node --test`. `--smoke` adds two end-to-end runs: the Acme smoke
  (`tests/smoke/acme.sh`, a synthetic brand through every pack) and the Quick-tier smoke (`tests/smoke/quick.sh`, a
  made-up bakery on a PATH with no Apple tools and no git, ending with the short guide).
- Mutation tests prove each gate by breaking a scratch copy.
- A test that cannot run prints "NOT VERIFIED". `BRAND_CREATOR_REQUIRE_ALL=1` turns every such skip into a failure.
- Tests that talk to real services (`requires_network`) run only with `BRAND_CREATOR_LIVE=1`.
- The anonymisation test needs a private denylist (`BRAND_CREATOR_DENYLIST`) and skips without it.
- A set-up data directory comes from `brand-creator --data <dir> setup --yes`.

A quicker pytest-only run, without the smokes:

```bash
uv run --no-project --with pytest --with pytest-xdist python -m pytest tests -q -n 4
```

## Run Linux in Docker

`tests/docker/run.sh` builds the Debian 13 image, copies the plugin in read-only, runs `setup`, pytest, node:test and the
Acme smoke, and accepts only the macOS-only NOT VERIFIED skips.

## CI

`.github/workflows/brand-creator.yml` at the root of the monorepo runs three jobs. Each runs in `plugins/brand-creator/`.
It starts only on changes under `plugins/brand-creator/` or to the workflow file.

| Job | What it runs |
| --- | --- |
| Linux | the Docker suite (`tests/docker/run.sh`) |
| Validate | `claude plugin validate --strict` on the plugin, and the validate test in `tests/test_static.py` |
| macOS | the Apple-tool tests and smoke, with `BRAND_CREATOR_REQUIRE_ALL=1` |

The workflow never runs `claude plugin eval`: it is billed. See [Evals](evals.md).

## Validate

From the repository root:

```bash
claude plugin validate . --strict
claude plugin validate plugins/brand-creator --strict
```

## Releases and history

- The version lives only in `.claude-plugin/plugin.json`. It is bumped on release and listed in
  [CHANGELOG.md](../../CHANGELOG.md). The repository's [release steps](../../../../docs/internals/release.md) apply.
- Manual checks a suite cannot do, and which of them have been run: [Manual checks](manual-checks.md).
- How 0.1.0 was built and why: the [archive](../archive/README.md).
- New decisions are [ADRs](../adr/README.md).
- Third-party notices: [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md). Licence: MIT.

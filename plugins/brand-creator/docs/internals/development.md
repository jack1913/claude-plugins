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
- `BRAND_CREATOR_TEST_PARTS=pytest` (or `node`, `smoke`, comma-separated) runs only those parts, as each CI job does. An
  unknown part, or a choice that runs nothing, is a usage error (exit 2).
- `ACME_SMOKE_PART=finish` (or `rest`) runs one half of the Acme smoke, as each macOS smoke job does: the build up to the
  frozen round, then `tools/finish.sh` alone, or every section after it. The default, `all`, runs both.
- pytest runs with `--dist worksteal`, so a block of long tests never waits on one worker (the suite takes under half the
  time it took with the default `load`). Every test has a time limit: 300 s, or 1200 s in `test_finish_chain.py`
  (pytest-timeout from `tests/requirements.txt`); a node test has 180 s. A hung test fails by name.
- The test tools are pinned, with every package they need, in `tests/requirements.txt`, compiled by uv from
  `tests/requirements.in` (the command is in both files).
- Mutation tests prove each gate by breaking a scratch copy.
- `tests/mutation_ledger.py` lists deliberate breaks of the plugin, each with the tests that must catch it, and replays them
  on a copy of the plugin (the checkout is never changed). Replay it whenever tests are merged, rewritten or deleted:
  every break must still be caught. For example the finish chain's branches moved from whole chains
  (`test_finish_chain.py`, which keeps two real ones) to `test_finish_chain_steps.py`, which runs the same template against
  a stand-in for `brand-creator`; `--group finish-chain` replays its breaks. The other groups are `motion-stills`,
  `profiles` (`test_emit_profiles.py`) and `book-motion` (`test_book_motion.py`); `--list` prints every break.
- A test that cannot run prints "NOT VERIFIED". `BRAND_CREATOR_REQUIRE_ALL=1` turns every such skip into a failure.
- Tests that talk to real services (`requires_network`) run only with `BRAND_CREATOR_LIVE=1`.
- The anonymisation test needs a private denylist (`BRAND_CREATOR_DENYLIST`) and skips without it.
- A set-up data directory comes from `brand-creator --data <dir> setup --yes`.

A quicker pytest-only run, without the smokes:

```bash
uv run --no-project --with-requirements tests/requirements.txt python -m pytest tests -q -n 4 --dist worksteal
```

## Run Linux in Docker

`tests/docker/run.sh` builds the Debian 13 image, copies the plugin in read-only, runs `setup`, pytest, node:test and the
Acme smoke, and accepts only the macOS-only NOT VERIFIED skips. `BRAND_CREATOR_TEST_PARTS` picks the parts, and
`BRAND_CREATOR_SUITE_MINUTES` (default 45) is the deadline inside the container: past it the suite is stopped and the log is
still checked. `BRAND_CREATOR_TEST_OUT=<dir>` keeps the run log and pytest's JUnit file in a new `linux-run.*` folder inside it.

## CI

`.github/workflows/brand-creator.yml` at the root of the monorepo runs these jobs, all in parallel except the verdict. Each job
that checks out the repository runs in `plugins/brand-creator/`; the verdict needs no checkout.
It starts on a push to `main` or a pull request that changes `plugins/brand-creator/` or the workflow file, never on a tag.

| Job | What it runs |
| --- | --- |
| linux (pytest), linux (node), linux (smoke) | one part of the Docker suite each (`tests/docker/run.sh` with `BRAND_CREATOR_TEST_PARTS`), each within its own deadline; the run log and the JUnit file are kept as an artifact |
| validate | `claude plugin validate --strict` on the plugin, and the validate test in `tests/test_static.py` |
| macos (pytest) | the Apple-tool tests, with `BRAND_CREATOR_REQUIRE_ALL=1` |
| macos (smoke-finish), macos (smoke-rest) | the two halves of the Acme smoke on macOS (`ACME_SMOKE_PART`), with `emit apple` |
| brand-creator | the verdict: passes only when every other job passed (a failed, cancelled or skipped job is never green). A release tag `brand-creator--v*` is accepted only on a commit where it and `docs` passed ([Release a plugin](../../../../docs/internals/release.md#the-tag-rulesets)) |

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

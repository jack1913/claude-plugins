# check-apis.py reference

```text capture=check-apis-help
usage: check-apis.py [-h] [--strict] [--refresh] [--write-table] [--find NAME]
                     [--manifest MANIFEST] [--cache CACHE] [--skills SKILLS]
                     [--table-file TABLE_FILE]

Check every API the swift plugin's skills name against Apple's documentation.

options:
  -h, --help            show this help message and exit
  --strict              also fail on unresolved names, stale ignore entries,
                        and a stale cache
  --refresh             bypass the cache
  --write-table         rewrite the generated block in platform-
                        availability.md
  --find NAME           print the index entries for NAME and exit
  --manifest MANIFEST
  --cache CACHE
  --skills SKILLS
  --table-file TABLE_FILE
```

The defaults are `maintenance/apis.json`, `maintenance/.cache/` (gitignored), `plugins/swift/skills/` and `plugins/swift/skills/swiftui/references/platform-availability.md` (`parse_args` in `maintenance/apicheck/cli.py`).

## Find the doc path for a name

```bash
python3 maintenance/check-apis.py --find glassEffect
```

```text capture=check-apis-find
method         swiftui/view/glasseffect(_:in:)
```

The printed path is what a manifest entry's `path` takes.

## Exit codes

From `run` and `main` in `maintenance/apicheck/cli.py`:

| Code | Meaning |
| --- | --- |
| `0` | No failures. Warnings — including a stale cache (below) — are allowed unless `--strict` is set. |
| `1` | A manifest check failed (Apple has no page, or a recorded claim contradicts Apple); or `--strict` and there are warnings (a stale cache counts); or `--find` matched nothing. |
| `2` | The manifest or a file is unreadable or invalid, the framework index is missing, or the network or cache failed. The message starts with `error:` and usually names the URL, file or framework. |

## Cache staleness

`Fetcher` (`maintenance/apicheck/fetch.py`) never expires a cache entry on its own, so a run reports the age of the oldest entry it read or wrote (file mtime), and WARNs once that entry is older than `DEFAULT_MAX_AGE_DAYS` — 30 days:

```text illustrative
oldest cache entry: 31.0 days old
WARN cache is up to 31 days old (> 30); run --refresh
80 manifest APIs, 0 failures, 1 warnings
```

Like any other warning, it only fails the run under `--strict`. Clear it with `--refresh`, which bypasses the cache and re-fetches everything the run touches:

```bash
python3 maintenance/check-apis.py --refresh
```

## `maintenance/apis.json`

Loaded by `load_manifest` in `maintenance/apicheck/manifest.py`. Unknown keys are errors.

| Key | Holds |
| --- | --- |
| `frameworks` | Apple framework index slugs to resolve names against, such as `swiftui` or `foundation` |
| `apis` | One entry per API the skills make a claim about: `name`, `path` (below `/documentation/`, no `.json`), optional `claims`, and optional `table` |
| `ignore` | A map from reason to a list of names that are not Apple APIs, such as example types or placeholders |

Claims: `deprecated` and `beta` take `true` or `false`. Each platform (`iOS`, `iPadOS`, `Mac Catalyst`, `macOS`, `visionOS`, `watchOS`, `tvOS`) takes `true`/`false` for available, or an introduced version such as `"26.0"`. An entry with `"table": true` becomes a row in the generated platform table.

With `--strict`, the check also fails on an ignored name that no skill file uses any more, and on one that now resolves to an Apple API.

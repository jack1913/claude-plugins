"""Check every API the swift plugin's skills name against Apple's documentation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import apple, extract, table
from .fetch import Fetcher, FetchError, NotFound
from .manifest import ManifestError, load_manifest

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "plugins" / "swift" / "skills"


def parse_args(argv):
    p = argparse.ArgumentParser(prog="check-apis.py", description=__doc__)
    p.add_argument(
        "--strict",
        action="store_true",
        help="also fail on unresolved names and stale ignore entries",
    )
    p.add_argument("--refresh", action="store_true", help="bypass the cache")
    p.add_argument(
        "--write-table",
        action="store_true",
        help="rewrite the generated block in platform-availability.md",
    )
    p.add_argument(
        "--find", metavar="NAME", help="print the index entries for NAME and exit"
    )
    p.add_argument("--manifest", type=Path, default=REPO / "maintenance" / "apis.json")
    p.add_argument("--cache", type=Path, default=REPO / "maintenance" / ".cache")
    p.add_argument("--skills", type=Path, default=SKILLS)
    p.add_argument(
        "--table-file",
        type=Path,
        default=SKILLS / "swiftui" / "references" / "platform-availability.md",
    )
    return p.parse_args(argv)


def _load_lookup(manifest, fetcher):
    entries = []
    for framework in manifest.frameworks:
        try:
            entries += apple.parse_index(fetcher.index(framework))
        except NotFound:
            raise ManifestError(
                f"Apple has no index for framework {framework!r}"
            ) from None
    return apple.build_lookup(entries)


def _check_manifest(manifest, fetcher):
    failures, rows = [], []
    for api in manifest.apis:
        try:
            platforms = apple.parse_platforms(fetcher.page(api.path))
        except NotFound:
            failures.append(f"{api.name}: Apple has no page at {api.path}")
            continue
        except ValueError as exc:
            failures.append(f"{api.name}: {exc}")
            continue
        failures += apple.check_claims(api.name, api.claims, platforms)
        if api.table:
            rows.append((api.name, api.path, platforms))
    return failures, rows


def _check_coverage(manifest, lookup, skills):
    warnings, seen = [], set()
    for name, files in sorted(
        extract.scan(skills).items(), key=lambda kv: (kv[0].text, kv[0].kind)
    ):
        seen.add(name.text)
        resolved = apple.resolve(name.text, name.kind, lookup)
        if name.text in manifest.ignore:
            if resolved:
                warnings.append(
                    f"ignored {name.text!r} now resolves to {resolved[0].path}; drop it from 'ignore'"
                )
            continue
        if not resolved:
            where = ", ".join(str(f.relative_to(skills)) for f in files[:3])
            more = f" (+{len(files) - 3} more)" if len(files) > 3 else ""
            warnings.append(f"unresolved {name.kind} {name.text!r} in {where}{more}")
    warnings += [
        f"ignored {n!r} appears in no skill file; drop it from 'ignore'"
        for n in sorted(set(manifest.ignore) - seen)
    ]
    return warnings


def run(args, fetcher, out=sys.stdout) -> int:
    manifest = load_manifest(args.manifest)
    lookup = _load_lookup(manifest, fetcher)

    if args.find:
        matches = lookup.get(args.find.lower(), [])
        for e in matches:
            flags = "".join(
                f" ({flag})"
                for flag, on in (("deprecated", e.deprecated), ("beta", e.beta))
                if on
            )
            print(f"{e.kind:14} {e.path}{flags}", file=out)
        return 0 if matches else 1

    failures, rows = _check_manifest(manifest, fetcher)
    warnings = _check_coverage(manifest, lookup, args.skills)

    if args.write_table:
        if failures:
            failures.append("platform table not written: fix the failures above first")
        else:
            text = args.table_file.read_text(encoding="utf-8")
            args.table_file.write_text(
                table.replace_block(text, table.render_table(rows)), encoding="utf-8"
            )
            print(f"wrote {len(rows)} rows to {args.table_file}", file=out)

    for line in failures:
        print(f"FAIL {line}", file=out)
    for line in warnings:
        print(f"WARN {line}", file=out)
    print(
        f"{len(manifest.apis)} manifest APIs, {len(failures)} failures, {len(warnings)} warnings",
        file=out,
    )
    return 1 if failures or (args.strict and warnings) else 0


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        return run(args, Fetcher(args.cache, refresh=args.refresh))
    except (ManifestError, FetchError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

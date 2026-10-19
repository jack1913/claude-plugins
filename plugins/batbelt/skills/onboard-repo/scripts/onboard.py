#!/usr/bin/env python3
"""CLI seam so onboard-repo/SKILL.md can invoke the deterministic helpers.

Usage:
  onboard.py preserve <old_file> <new_template_file> [YYYY-MM-DD]  # merged -> stdout
  onboard.py check-markers <file>                       # exit 0 if well-formed, else 2
  onboard.py find-predecessors <claude_dir>             # JSON list -> stdout
  onboard.py renumber-toc <file>                        # reflow manual ToC -> stdout
  onboard.py rewrite-links <file> <manifest>            # apply manifest moves -> stdout
  onboard.py rebase-links <file> <page_old> <page_new> <manifest>  # re-anchor a moved page
  onboard.py write-move-manifest <pairs.json> <dirs.json>  # build a move manifest -> stdout
  onboard.py shrink-check <old_file> <new_file> [--cleared]  # guard a loop rewrite (exit 1 on err)
  onboard.py redact <raw_file> --home H --user U --stamp S [--extra a,b]  # redact a capture
  onboard.py deps-detect <repo_root>                    # ecosystem report JSON -> stdout
  onboard.py settings-plan <repo_root> [--ecosystem a,b] [--ask-npx] [--explain]
                                          # permissions JSON (or, with --explain, the ask/deny tiers
                                          # with one reason per rule) -> stdout
  onboard.py gitignore-ensure <file> <line>...           # body + missing lines -> stdout
  onboard.py settings-audit <settings.json>              # defects JSON; exit 1 on a trigger
  onboard.py settings-migrate <settings.json> [--apply --stamp S]  # re-anchor deny reads; dry run
  onboard.py convert-copilot <file> [--kind instruction|prompt]  # ported text -> stdout
  onboard.py check-instructions <roots...> [--repo-root DIR]...
                                          # SEVERITY\\tCODE\\tfile:lineno\\tdetail -> stdout
  onboard.py check-docs <roots...> [--captures DIR] [--coverage FILE] [--forbidden a,b]
                                   [--only PATH]... [--no-tier-check]
                                          # SEVERITY\\tCODE\\tfile:lineno\\tdetail -> stdout
  onboard.py run-init <stamp> <repo_root> [--mode M]     # fresh run record -> stdout
  onboard.py run-status <run.json>                       # human-readable status -> stdout
  onboard.py run-next <run.json> [--kind K]              # next actionable item key -> stdout
  onboard.py run-set <run.json> (--phase P | --add k,k --kind K | --mark k --state S
                                 | --confirm KEY=FILE | --log MSG) [--note N] [--rounds N]
                                          # updated run record -> stdout (capture, then mv)

Bad args / unreadable inputs exit 2. check-docs and check-instructions exit 1 when
they find an error-level issue, 0 for warnings or a clean tree -- never a traceback.

check-docs without --captures cannot verify a fenced command's output, so it emits
CAPTURES_NOT_CHECKED instead of silently passing. Always pass both --captures and
--coverage when the repo has them.

--only scopes which files REPORT findings while leaving the roots intact, which is
what a per-page authoring loop needs. Narrowing the roots instead would silently
downgrade a real BROKEN_LINK to a warning (severity keys on _within_roots) and strand
the tier exemptions -- so a per-page loop must pass the full roots plus --only, never
a single-file root. --no-tier-check suppresses the tree-wide EMPTY_TIER sweep for the
same reason: mid-run, an unauthored surface is expected, not a finding.

The run verbs persist a long onboarding's state to a file the operator keeps
(.onboard-repo-retired/<stamp>/run.json). Like every other verb here they write only
to stdout: capture, then mv. That is what lets a 3-4h pass survive context
compaction or a lost session without re-asking every confirmation.
"""

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check
import onboard_lib as lib
from check import _relparts

# Directories that must NEVER supply a manifest: the dependency trees, which are full
# of manifests belonging to OTHER projects. `vendor/` in a PHP repo carries ~100
# package.json files, and reporting them as this repo's workspace roots produced a
# settings plan for an ecosystem the repo does not even build.
_MANIFEST_EXCLUDE_DIRS = {
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    ".tox",
    "site-packages",
    ".git",
    ".onboard-repo-retired",
}

# Build OUTPUT: a manifest here is a COPY of this repo's own, so it must not be counted
# as a second workspace root -- `cargo package` leaves a full crate (with its
# `[workspace]` section) under `target/package/`, and a publishable subpackage ships a
# `dist/package.json`. But it is still this repo's manifest, not a third party's, so a
# repo whose ONLY manifest sits here must not be reported as having no ecosystem at all
# (that silently skips the update-deps offer, SKILL.md §3.4). Hence a FALLBACK, consulted
# only when the same pattern matched nothing outside build output.
_BUILD_OUTPUT_DIRS = {"build", "dist", "target"}


def _is_vendored(root, path):
    """True when `path` sits under a DEPENDENCY tree relative to `root`."""
    rel = _relparts(root, path)
    if rel is None:
        return False
    return bool(_MANIFEST_EXCLUDE_DIRS.intersection(rel))


def _is_build_output(root, path):
    """True when `path` sits under a build-output dir relative to `root`."""
    rel = _relparts(root, path)
    if rel is None:
        return False
    return bool(_BUILD_OUTPUT_DIRS.intersection(rel))


def _usage(msg):
    sys.stderr.write(msg + "\n")
    return 2


def _load_settings_file(arg):
    """Parse a settings.json for the settings-* verbs; None (after a usage message,
    exit 2) when it is missing or not JSON. A hand-broken file is the operator's to
    fix -- neither verb may guess its way past one."""
    path = pathlib.Path(arg)
    if not path.is_file():
        _usage("ERROR: not a file: " + arg)
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _usage("ERROR: %s is not readable JSON: %s" % (arg, exc))
        return None
    if not isinstance(data, dict):
        _usage("ERROR: %s does not hold a JSON object" % arg)
        return None
    return data


def _detect_ecosystems(repo_root):
    """Walk a repo root for dependency manifests and compose the ADR §8.1
    detection report (stdlib only; no ecosystem CLIs required). v1: ecosystems
    by manifest presence + workspace roots; sources: [] (runtime concern)."""
    root = pathlib.Path(repo_root)
    ecosystems = []

    def _manifests(pattern):
        # Every manifest lookup goes through the same two-tier rule: a dependency tree
        # never supplies one, and build output supplies one only as a LAST RESORT.
        # Counting a built copy as a peer double-reported workspace roots (a
        # `cargo package` crate under target/, a publishable `dist/package.json`);
        # discarding it outright reported a repo whose only manifest lives there as
        # having no ecosystem at all. Both were real defects, so neither list wins
        # unconditionally.
        found = [p for p in root.rglob(pattern) if not _is_vendored(root, p)]
        first_party = [p for p in found if not _is_build_output(root, p)]
        return first_party or found

    def _pick_manager(dirs, candidates, default):
        """(lockfiles, manager) for a set of manifest dirs.

        The manager comes from the lockfile CLOSEST TO THE REPO ROOT, not from whichever
        name happens to come first in `candidates`. Scanning by name let one legacy
        `packages/x/package-lock.json` name the manager for a repo whose root holds a
        `pnpm-lock.yaml` -- reporting `npm` for a pnpm monorepo, which is the very
        defect the lockfile-decides-the-manager rule exists to prevent. Ties at equal
        depth fall back to `candidates` order, which is the intended precedence.
        """
        found = []
        for name, mgr in candidates:
            for d in dirs:
                lock = d / name
                if lock.is_file():
                    rel = _relparts(root, lock)
                    found.append((len(rel) if rel is not None else len(lock.parts), lock, mgr))
        if not found:
            return [], default
        manager = min(found, key=lambda t: t[0])[2]
        # Report order stays the walk's, so the lockfile list is unchanged by this.
        return [lock for _depth, lock, _mgr in found], manager

    # js: any package.json (root or workspace roots).
    pkg_files = _manifests("package.json")
    if pkg_files:
        # Lockfile presence also decides the manager: reporting `npm` next to a
        # pnpm-lock.yaml sends the agent to a command the repo never uses.
        js_lockfiles, manager = _pick_manager(
            [p.parent for p in pkg_files],
            (
                ("package-lock.json", "npm"),
                ("pnpm-lock.yaml", "pnpm"),
                ("yarn.lock", "yarn"),
            ),
            "npm",
        )
        ecosystems.append(
            {
                "name": "js",
                "manager": manager,
                # Only lockfiles that EXIST. The previous unconditional
                # `parent / "package-lock.json"` emitted a path for every
                # package.json found, so most entries named no file at all.
                "lockfiles": [str(p) for p in js_lockfiles],
                "workspaces": [
                    {"root": str(p.parent), "lockfile": None, "shared_path_deps": []}
                    for p in pkg_files
                ],
                "verify_fast": None,
                "verify_full": None,
                "tier0_rule": "expo" if (root / "node_modules" / "expo").is_dir() else "none",
                "cross_verify": None,
            }
        )

    # php: any composer.json. Laravel is the tier0 marker, detected by `artisan`
    # beside the manifest -- the same shape as expo for js.
    composer_files = _manifests("composer.json")
    if composer_files:
        ecosystems.append(
            {
                "name": "php",
                "manager": "composer",
                "lockfiles": [
                    str(p.parent / "composer.lock")
                    for p in composer_files
                    if (p.parent / "composer.lock").is_file()
                ],
                "workspaces": [
                    {"root": str(p.parent), "lockfile": None, "shared_path_deps": []}
                    for p in composer_files
                ],
                "verify_fast": None,
                "verify_full": None,
                "tier0_rule": (
                    "laravel"
                    if any((p.parent / "artisan").is_file() for p in composer_files)
                    else "none"
                ),
                "cross_verify": None,
            }
        )

    # python: a PEP 621 pyproject.toml, or a legacy setup.py / setup.cfg. The lockfile
    # decides the manager, the same way it does for js -- telling an agent to run `pip`
    # in a uv project sends it to a command that will not reproduce the environment.
    python_manifests = (
        _manifests("pyproject.toml") + _manifests("setup.py") + _manifests("setup.cfg")
    )
    if python_manifests:
        py_roots = list(dict.fromkeys(p.parent for p in python_manifests))
        py_lockfiles, py_manager = _pick_manager(
            py_roots,
            (
                ("uv.lock", "uv"),
                ("poetry.lock", "poetry"),
                ("pdm.lock", "pdm"),
                ("Pipfile.lock", "pipenv"),
                ("requirements.txt", "pip"),
            ),
            "pip",
        )
        ecosystems.append(
            {
                "name": "python",
                "manager": py_manager,
                "lockfiles": [str(p) for p in py_lockfiles],
                "workspaces": [
                    {"root": str(root), "lockfile": None, "shared_path_deps": []}
                    for root in py_roots
                ],
                "verify_fast": None,
                "verify_full": None,
                # `manage.py` beside the manifest is the Django marker -- the same
                # shape as `expo` for js and `artisan` for php.
                "tier0_rule": (
                    "django" if any((root / "manage.py").is_file() for root in py_roots) else "none"
                ),
                "cross_verify": None,
            }
        )

    # rust: every Cargo.toml whose [workspace] section makes it a workspace root.
    for cargo in _manifests("Cargo.toml"):
        text = cargo.read_text(encoding="utf-8", errors="replace")
        if lib.cargo_workspace_members(text) or re.search(
            r"^\s*\[workspace\]\s*$", text, re.MULTILINE
        ):
            ecosystems.append(
                {
                    "name": "rust",
                    "manager": "cargo",
                    "lockfiles": [str(cargo.parent / "Cargo.lock")],
                    "workspaces": [
                        {
                            "root": str(cargo.parent),
                            "lockfile": str(cargo.parent / "Cargo.lock"),
                            "shared_path_deps": [],
                        }
                    ],
                    "verify_fast": None,
                    "verify_full": None,
                    "tier0_rule": "none",
                    "cross_verify": None,
                }
            )

    # .NET: a .sln or Directory.Packages.props => dotnet/CPM.
    if _manifests("*.sln") or _manifests("Directory.Packages.props"):
        ecosystems.append(
            {
                "name": "dotnet",
                "manager": "dotnet",
                "lockfiles": [],
                "workspaces": [],
                "verify_fast": None,
                "verify_full": None,
                "tier0_rule": "none",
                "cross_verify": None,
            }
        )

    # swift: a Package.swift (pure-SPM) or a *.xcodeproj (Xcode-SPM).
    if _manifests("Package.swift") or _manifests("*.xcodeproj"):
        ecosystems.append(
            {
                "name": "swift",
                "manager": "swift-package",
                "lockfiles": [],
                "workspaces": [],
                "verify_fast": None,
                "verify_full": None,
                "tier0_rule": "none",
                "cross_verify": None,
            }
        )

    return {"ecosystems": ecosystems, "sources": []}


def _run_verb(cmd, rest):
    """The run-state verbs. Every one writes the updated record to STDOUT only --
    capture then mv, the same idiom as every other transform verb here, so a
    non-zero exit can never leave a half-written run record (which would lose the
    operator confirmations the record exists to protect).

    A malformed record exits 2 and is never silently replaced: `run-init` is the
    only verb that mints one.
    """
    if cmd == "run-init":
        if len(rest) < 2:
            return _usage("usage: onboard.py run-init <stamp> <repo_root> [--mode M]")
        mode = "default"
        if "--mode" in rest:
            i = rest.index("--mode")
            mode = rest[i + 1] if len(rest) > i + 1 else "default"
        sys.stdout.write(lib.write_run(lib.new_run(rest[0], rest[1], mode)))
        return 0

    if not rest:
        return _usage("usage: onboard.py %s <run.json> ..." % cmd)
    path = pathlib.Path(rest[0])
    if not path.is_file():
        return _usage("ERROR: not a file: " + rest[0])
    run = lib.read_run(path.read_text(encoding="utf-8"))
    args = rest[1:]

    if cmd == "run-status":
        sys.stdout.write(lib.run_summary(run))
        return 0

    if cmd == "run-next":
        kind = None
        if "--kind" in args:
            i = args.index("--kind")
            kind = args[i + 1] if len(args) > i + 1 else None
        nxt = lib.run_next(run, kind)
        if nxt is None:
            return 3  # distinct from 0/1/2: "no work left", not success or error
        sys.stdout.write(nxt + "\n")
        return 0

    # run-set: exactly one mutation per call, so a failure is never partial.
    opts, i = {}, 0
    while i < len(args):
        a = args[i]
        if a.startswith("--") and i + 1 < len(args) and not args[i + 1].startswith("--"):
            opts[a] = args[i + 1]
            i += 2
        elif a.startswith("--"):
            opts[a] = True
            i += 1
        else:
            return _usage("ERROR: unexpected argument: " + a)
    if "--phase" in opts:
        confirmed = None
        if "--confirm" in opts:
            # KEY=FILE, never KEY=inline-json: a confirmed detection or move plan is
            # far too big for a shell argument, and quoting it inline is how a plan
            # gets silently truncated. Same reason write-move-manifest reads files.
            spec = str(opts["--confirm"])
            key, _sep, src = spec.partition("=")
            if not key or not src:
                return _usage("ERROR: --confirm takes KEY=FILE")
            confirmed = {key: json.loads(pathlib.Path(src).read_text(encoding="utf-8"))}
        lib.run_set_phase(run, str(opts["--phase"]), confirmed)
    elif "--confirm" in opts:
        spec = str(opts["--confirm"])
        key, _sep, src = spec.partition("=")
        if not key or not src:
            return _usage("ERROR: --confirm takes KEY=FILE")
        run["confirmed"][key] = json.loads(pathlib.Path(src).read_text(encoding="utf-8"))
    elif "--add" in opts:
        if "--kind" not in opts:
            return _usage("ERROR: --add requires --kind")
        keys = [k for k in str(opts["--add"]).split(",") if k]
        lib.run_add_items(run, keys, str(opts["--kind"]), str(opts.get("--state", "pending")))
    elif "--mark" in opts:
        if "--state" not in opts:
            return _usage("ERROR: --mark requires --state")
        rounds = opts.get("--rounds")
        lib.run_mark(
            run,
            str(opts["--mark"]),
            str(opts["--state"]),
            note=str(opts.get("--note", "")),
            rounds=int(rounds) if rounds not in (None, True) else None,
        )
    elif "--log" in opts:
        lib.run_log(run, str(opts["--log"]))
    else:
        return _usage(
            "usage: onboard.py run-set <run.json> (--phase P | --add k,k --kind K | "
            "--mark k --state S [--note N] [--rounds N] | --confirm KEY=FILE | --log MSG)"
        )
    sys.stdout.write(lib.write_run(run))
    return 0


def main(argv):
    if not argv:
        sys.stderr.write(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == "preserve":
            if len(rest) not in (2, 3):
                return _usage("usage: onboard.py preserve <old> <new> [YYYY-MM-DD]")
            merged = lib.preserve_repo_specifics(
                pathlib.Path(rest[0]).read_text(encoding="utf-8"),
                pathlib.Path(rest[1]).read_text(encoding="utf-8"),
            )
            if len(rest) == 3:  # re-stamp the provenance date on --sync
                merged = lib.restamp_provenance(merged, lib.TEMPLATE_VERSION, rest[2])
            sys.stdout.write(merged)
            return 0
        if cmd == "check-markers":
            if len(rest) != 1:
                return _usage("usage: onboard.py check-markers <file>")
            lib.parse_regions(pathlib.Path(rest[0]).read_text(encoding="utf-8"))
            return 0
        if cmd == "find-predecessors":
            if len(rest) != 1:
                return _usage("usage: onboard.py find-predecessors <claude_dir>")
            print(json.dumps(lib.find_predecessors(rest[0]), indent=2))
            return 0
        if cmd == "renumber-toc":
            if len(rest) != 1:
                return _usage("usage: onboard.py renumber-toc <file>")
            sys.stdout.write(lib.renumber_toc(pathlib.Path(rest[0]).read_text(encoding="utf-8")))
            return 0
        if cmd == "rewrite-links":
            if len(rest) != 2:
                return _usage("usage: onboard.py rewrite-links <file> <manifest>")
            moves, _dirs = lib.read_move_manifest(pathlib.Path(rest[1]).read_text(encoding="utf-8"))
            sys.stdout.write(
                lib.rewrite_markdown_links(
                    pathlib.Path(rest[0]).read_text(encoding="utf-8"), {o: n for o, n in moves}
                )
            )
            return 0
        if cmd == "write-move-manifest":
            if len(rest) != 2:
                return _usage("usage: onboard.py write-move-manifest <pairs.json> <dirs.json>")
            pairs = json.loads(pathlib.Path(rest[0]).read_text(encoding="utf-8"))
            dirs = json.loads(pathlib.Path(rest[1]).read_text(encoding="utf-8"))
            sys.stdout.write(lib.write_move_manifest(pairs, dirs))
            return 0
        if cmd == "rebase-links":
            if len(rest) != 4:
                return _usage(
                    "usage: onboard.py rebase-links <file> <page_old> <page_new> <manifest>"
                )
            moves, _dirs = lib.read_move_manifest(pathlib.Path(rest[3]).read_text(encoding="utf-8"))
            sys.stdout.write(
                lib.rebase_relative_links(
                    pathlib.Path(rest[0]).read_text(encoding="utf-8"),
                    rest[1],
                    rest[2],
                    {o: n for o, n in moves},
                )
            )
            return 0
        if cmd == "shrink-check":
            cleared = "--cleared" in rest
            files = [a for a in rest if a != "--cleared"]
            if len(files) != 2:
                return _usage("usage: onboard.py shrink-check <old_file> <new_file> [--cleared]")
            viols = lib.shrink_violations(
                pathlib.Path(files[0]).read_text(encoding="utf-8"),
                pathlib.Path(files[1]).read_text(encoding="utf-8"),
                cleared,
            )
            for sev, msg in viols:
                sys.stdout.write("%s\t%s\n" % (sev.upper(), msg))
            return 1 if any(sev == "error" for sev, _ in viols) else 0
        if cmd == "redact":
            return check.run("redact", rest, prog="onboard.py")
        if cmd == "deps-detect":
            if len(rest) != 1:
                return _usage("usage: onboard.py deps-detect <repo_root>")
            repo_root = pathlib.Path(rest[0])
            if not repo_root.is_dir():
                return _usage("ERROR: not a directory: " + rest[0])
            report = _detect_ecosystems(rest[0])
            if not report["ecosystems"]:
                sys.stderr.write(
                    "ERROR: no supported ecosystem detected (need package.json / "
                    "composer.json / pyproject.toml or setup.py or setup.cfg / Cargo.toml / "
                    "*.sln or Directory.Packages.props / Package.swift or *.xcodeproj)\n"
                )
                return 2
            print(json.dumps(report, indent=2))
            return 0
        if cmd == "settings-plan":
            # Emit the PROPOSED project permissions block. Writing/merging is the
            # skill's job (report-first); this verb never touches the filesystem,
            # so it is safe to run before the operator has confirmed anything.
            if not rest:
                return _usage(
                    "usage: onboard.py settings-plan <repo_root> "
                    "[--ecosystem a,b] [--ask-npx] [--explain]"
                )
            repo_root = pathlib.Path(rest[0])
            if not repo_root.is_dir():
                return _usage("ERROR: not a directory: " + rest[0])
            names = None
            ask_npx = False
            explain = False
            it = iter(rest[1:])
            for a in it:
                if a == "--ecosystem":
                    names = [t for t in (next(it, "") or "").split(",") if t]
                elif a == "--ask-npx":
                    ask_npx = True
                elif a == "--explain":
                    explain = True
                else:
                    return _usage("ERROR: unexpected argument: " + a)
            if names is None:
                # Fall back to detection so the verb is useful standalone; an
                # empty result still yields the baseline rather than an error,
                # because the git/secret guards are worth having regardless.
                names = [e.get("name") for e in _detect_ecosystems(rest[0])["ecosystems"]]
            plan = lib.plan_project_permissions(names, ask_npx=ask_npx)
            if explain:
                sys.stdout.write(lib.explain_permissions(plan))
            else:
                print(json.dumps(plan, indent=2))
            return 0
        if cmd == "settings-audit":
            # Report what an EXISTING project permissions block gets wrong (ADR-0017).
            # Exit 1 when a deny Read() rule anchors inside the repo -- the shape that
            # made every path-less rg/grep -r a human-only prompt on Claude Code
            # 2.1.259 (reverted in 2.1.260) and that //**/ supersedes either way.
            if len(rest) != 1:
                return _usage("usage: onboard.py settings-audit <settings.json>")
            settings = _load_settings_file(rest[0])
            if settings is None:
                return 2
            report = lib.audit_project_permissions(settings)
            print(json.dumps(report, indent=2))
            return 1 if report["guard_triggers"] else 0
        if cmd == "settings-migrate":
            # Re-anchor inside-repo deny rules at `//**/` (a strict superset, so
            # nothing is less protected). Dry-run by default; --apply needs --stamp so
            # the backup lands under .onboard-repo-retired/<stamp>/ like every other
            # retirement, never under a time this verb picked on its own.
            apply_it, stamp, files = False, None, []
            it = iter(rest)
            for a in it:
                if a == "--apply":
                    apply_it = True
                elif a == "--stamp":
                    stamp = next(it, None)
                elif a.startswith("--"):
                    return _usage("ERROR: unexpected argument: " + a)
                else:
                    files.append(a)
            if len(files) != 1:
                return _usage(
                    "usage: onboard.py settings-migrate <settings.json> [--apply --stamp S]"
                )
            if apply_it and not stamp:
                return _usage("ERROR: --apply requires --stamp <YYYYMMDDTHHMMSS>")
            path = pathlib.Path(files[0])
            settings = _load_settings_file(files[0])
            if settings is None:
                return 2
            new, actions = lib.migrate_project_permissions(settings)
            written = False
            if apply_it and actions:
                repo_root = path.parent.parent if path.parent.name == ".claude" else path.parent
                backup_dir = repo_root / ".onboard-repo-retired" / stamp
                backup_dir.mkdir(parents=True, exist_ok=True)
                (backup_dir / path.name).write_text(
                    path.read_text(encoding="utf-8"), encoding="utf-8"
                )
                path.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")
                written = True
            print(json.dumps({"actions": actions, "written": written}, indent=2))
            return 0
        if cmd == "check-instructions":
            return check.run("check-instructions", rest, prog="onboard.py")
        if cmd == "convert-copilot":
            # Port one Copilot instruction/prompt file to Claude's shape. Converted
            # text on stdout, notes on stderr -- so `> tmp && mv` captures only the
            # file, and the operator still sees what was refused. Reads one file and
            # writes nothing, like every other transform verb.
            if not rest:
                return _usage(
                    "usage: onboard.py convert-copilot <file> [--kind instruction|prompt]"
                )
            src = pathlib.Path(rest[0])
            if not src.is_file():
                return _usage("ERROR: not a file: " + rest[0])
            kind = None
            if "--kind" in rest:
                kind = (
                    rest[rest.index("--kind") + 1] if len(rest) > rest.index("--kind") + 1 else None
                )
            text = src.read_text(encoding="utf-8", errors="replace")
            if kind is None:
                # Infer from the filename Copilot uses, then from the frontmatter.
                kind = "prompt" if ".prompt." in src.name else "instruction"
            if kind == "prompt":
                out, args, notes = lib.convert_copilot_prompt(text)
                if args:
                    notes.append("add to the skill frontmatter:  arguments: " + ", ".join(args))
            elif kind == "instruction":
                out, notes = lib.convert_copilot_instruction(text)
            else:
                return _usage("ERROR: --kind must be instruction or prompt")
            sys.stdout.write(out)
            for n in notes:
                sys.stderr.write("NOTE\t%s\n" % n)
            return 0
        if cmd == "gitignore-ensure":
            # Print the .gitignore body with any missing lines appended. Capture
            # to a temp file and mv -- never redirect onto the same path.
            if len(rest) < 2:
                return _usage("usage: onboard.py gitignore-ensure <file> <line>...")
            path = pathlib.Path(rest[0])
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
            sys.stdout.write(lib.ensure_gitignore_lines(text, rest[1:]))
            return 0
        if cmd == "check-docs":
            return check.run("check-docs", rest, prog="onboard.py")
        if cmd in ("run-init", "run-status", "run-next", "run-set"):
            return _run_verb(cmd, rest)
    except lib.MarkerError as exc:
        sys.stderr.write("MARKER ERROR: " + str(exc) + "\n")
        return 2
    except lib.RunStateError as exc:
        # Ahead of the generic ValueError handler below, which would report a bad
        # run record as a "malformed manifest" and send the operator to the wrong file.
        sys.stderr.write("RUN STATE ERROR: " + str(exc) + "\n")
        return 2
    except OSError as exc:  # missing/unreadable file -> clean exit 2
        sys.stderr.write("ERROR: " + str(exc) + "\n")
        return 2
    except (ValueError, KeyError) as exc:  # bad/partial manifest JSON -> clean exit 2
        sys.stderr.write("ERROR: malformed manifest: " + str(exc) + "\n")
        return 2
    return _usage("unknown command: " + cmd)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

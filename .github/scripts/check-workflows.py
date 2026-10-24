#!/usr/bin/env python3
"""Check the shape of every workflow in .github/workflows/. Standard library only; run from the repository root.

    python3 .github/scripts/check-workflows.py              check the workflows as they are
    python3 .github/scripts/check-workflows.py --self-test  break each rule in a copy, and fail unless the check catches it

The rule is .claude/rules/ci-workflow-per-plugin.md; why: docs/adr/ADR-0004-ci-runs-on-main-and-pull-requests-never-on-tags.md.
Fails when:
  - the workflow files are not one <plugin>.yml per plugin under plugins/ plus marketplace.yml and docs.yml (a .yaml file
    is reported too: GitHub runs both extensions);
  - a workflow triggers on anything but push, pull_request and workflow_dispatch (create or release would run on a tag);
  - push runs for anything but main: push.branches must be exactly main, with no tags, tags-ignore or branches-ignore
    (GitHub evaluates no path filter for a tag push, so a tag would start every workflow again);
  - push and pull_request filter on different paths, or a plugin's workflow does not filter on plugins/<name>/** and its own file;
  - the top-level permissions are not contents: read, or a job sets its own permissions;
  - a job runs on a floating runner image (any runs-on that says latest), or on one this check cannot read;
  - a run on main can be cancelled or replaced: the concurrency block must be top-level, its group must hold github.sha
    (one group per commit on main), and cancel-in-progress must be false or ${{ github.event_name == 'pull_request' }}.
The reader understands only the YAML these keys use here (block mappings, block lists of scalars, quoted scalars); anything
else in them is reported as unreadable, never passed.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PR_ONLY = "${{ github.event_name == 'pull_request' }}"
TRIGGERS = {"push", "pull_request", "workflow_dispatch"}
KEY = re.compile(r"([A-Za-z_][\w-]*):(?:\s+(.*))?")


class Unreadable(Exception):
    pass


def strip_comment(line: str) -> str:
    """The line without its # comment (a # inside quotes is kept)."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            quote = None if ch == quote else quote
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i].rstrip()
    return line.rstrip()


def scalar(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if text[:1] in tuple("[{&*!|>"):
        raise Unreadable(f"{text!r} is not a plain or quoted scalar: write a block list or mapping")
    return text


def indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def structure(text: str) -> list[str]:
    """The lines that carry YAML structure: no comments, no blank lines, and no body of a block scalar (a `run: |` script)."""
    out: list[str] = []
    body_above = None   # the indentation a block scalar's body must exceed, while inside one
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = strip_comment(raw)
        if not line.strip():
            continue
        if body_above is not None and indent(line) > body_above:
            continue
        body_above = None
        out.append(line)
        if re.search(r":\s*[|>][-+]?\d*$", line):
            body_above = indent(line)
    return out


def parse_map(lines: list[str], i: int, ind: int) -> tuple[dict, int]:
    """A block mapping at indentation `ind` from lines[i]: its values are scalars, block lists of scalars or block mappings."""
    out: dict = {}
    while i < len(lines) and indent(lines[i]) >= ind:
        line = lines[i]
        if indent(line) > ind:
            raise Unreadable(f"unexpected indentation at {line.strip()!r}")
        m = KEY.fullmatch(line.strip())
        if not m:
            raise Unreadable(f"{line.strip()!r} is not a `key: value` line")
        key, val = m.group(1), m.group(2)
        i += 1
        if val:
            out[key] = scalar(val)
        elif i < len(lines) and indent(lines[i]) > ind and lines[i].lstrip().startswith("- "):
            sub, items = indent(lines[i]), []
            while i < len(lines) and indent(lines[i]) == sub and lines[i].lstrip().startswith("- "):
                items.append(scalar(lines[i].lstrip()[2:]))
                i += 1
            if i < len(lines) and indent(lines[i]) > ind:
                raise Unreadable(f"{key}: a list item that is not a scalar at {lines[i].strip()!r}")
            out[key] = items
        elif i < len(lines) and indent(lines[i]) > ind:
            out[key], i = parse_map(lines, i, indent(lines[i]))
        else:
            out[key] = None
    return out, i


def read(text: str) -> tuple[dict, list[str]]:
    """(the top-level keys this check reads: on, permissions and concurrency, parsed; the structural lines)."""
    lines = structure(text)
    out: dict = {}
    i = 0
    while i < len(lines):
        m = KEY.fullmatch(lines[i]) if indent(lines[i]) == 0 else None
        j = i + 1
        while j < len(lines) and indent(lines[j]) > 0:
            j += 1
        if m and m.group(1) in ("on", "permissions", "concurrency"):
            key, val, body = m.group(1), m.group(2), lines[i + 1:j]
            if val:
                out[key] = scalar(val)
            elif body:
                out[key], end = parse_map(body, 0, indent(body[0]))
                if end != len(body):
                    raise Unreadable(f"{key}: cannot read {body[end].strip()!r}")
            else:
                out[key] = None
        i = j
    return out, lines


def check_one(f: str, text: str, plugins: list[str]) -> list[str]:
    errors: list[str] = []
    top, lines = read(text)
    name = f.removesuffix(".yml")
    on = top.get("on")
    if not isinstance(on, dict) or set(on) != TRIGGERS:
        found = ", ".join(sorted(on)) if isinstance(on, dict) else repr(on)
        return [f"{f}: must trigger on push, pull_request and workflow_dispatch and nothing else (found: {found})"]
    push, pr = on.get("push") or {}, on.get("pull_request") or {}
    if not isinstance(push, dict) or push.get("branches") != ["main"]:
        errors.append(f"{f}: push must run on main only (push.branches: a list of exactly main), so a tag push runs nothing")
    for extra in sorted(set(push) - {"branches", "paths"} if isinstance(push, dict) else []):
        errors.append(f"{f}: push has {extra}: only branches (main) and paths are allowed")
    for extra in sorted(set(pr) - {"paths"} if isinstance(pr, dict) else []):
        errors.append(f"{f}: pull_request has {extra}: only paths is allowed")
    paths = push.get("paths") if isinstance(push, dict) else None
    if not isinstance(paths, list) or not paths or paths != (pr.get("paths") if isinstance(pr, dict) else None):
        errors.append(f"{f}: push and pull_request must filter on the same, non-empty paths list")
    if name in plugins:
        for need in (f"plugins/{name}/**", f".github/workflows/{f}"):
            if need not in (paths or []):
                errors.append(f"{f}: does not filter on {need}")
    perms = top.get("permissions")
    if not isinstance(perms, dict) or perms.get("contents") != "read" or "write" in perms.values():
        errors.append(f"{f}: the top-level permissions must be contents: read, with no write")
    conc = top.get("concurrency")
    if conc is not None:
        group = conc.get("group") if isinstance(conc, dict) else conc
        if not (isinstance(group, str) and "github.sha" in group):
            errors.append(f"{f}: concurrency group {group!r} is shared by runs on main, so a pending run is replaced: include github.sha")
    for i, ln in enumerate(lines):
        m = KEY.fullmatch(ln.strip())
        if not m:
            continue
        key, val = m.group(1), m.group(2) or ""
        if key in ("permissions", "concurrency") and indent(ln) > 0:
            errors.append(f"{f}: a job sets its own {key}: only the top-level block is allowed")
        if key == "cancel-in-progress" and val.strip() and val.strip().strip("\"'") not in ("false", PR_ONLY):
            errors.append(f"{f}: cancel-in-progress {val.strip()} can cancel a run on main: use false or {PR_ONLY}")
        if key == "runs-on":
            block = [val] + [x for x in lines[i + 1:next((j for j in range(i + 1, len(lines)) if indent(lines[j]) <= indent(ln)), len(lines))]]
            said = " ".join(b.strip() for b in block if b.strip())
            if "latest" in said.lower():
                errors.append(f"{f}: runs-on {said} is a floating runner image: pin it, for example ubuntu-24.04")
            elif not val.strip() or val.strip()[:1] in tuple("[{$"):
                errors.append(f"{f}: runs-on {said} cannot be read as one pinned image label: write it as one, for example ubuntu-24.04")
    return errors


def check(workflows: dict[str, str], plugins: list[str]) -> list[str]:
    """Every problem with the workflows ({file name: text}) of a repository whose plugins are `plugins`."""
    errors = [f"{f}: use the .yml extension (GitHub runs .yaml files too, and this check reads .yml)" for f in sorted(workflows) if not f.endswith(".yml")]
    yml = {f: t for f, t in workflows.items() if f.endswith(".yml")}
    expected = {f"{p}.yml" for p in plugins} | {"marketplace.yml", "docs.yml"}
    errors += [f"{f} is not a plugin's workflow, marketplace.yml or docs.yml" for f in sorted(set(yml) - expected)]
    errors += [f"plugins/{p} has no workflow .github/workflows/{p}.yml" for p in sorted(plugins) if f"{p}.yml" not in yml]
    for f, text in sorted(yml.items()):
        try:
            errors += check_one(f, text, plugins)
        except Unreadable as e:
            errors.append(f"{f}: unreadable: {e}")
    return errors


def repo() -> tuple[dict[str, str], list[str]]:
    folder = ROOT / ".github" / "workflows"
    workflows = {p.name: p.read_text(encoding="utf-8") for p in sorted(folder.iterdir()) if p.suffix in (".yml", ".yaml")}
    plugins = sorted(d.name for d in (ROOT / "plugins").iterdir() if d.is_dir())
    return workflows, plugins


JOB = "    runs-on: ubuntu-24.04\n"
# (what breaks, the workflow file it breaks, the text, its replacement, the words the error must hold);
# None as the file adds a workflow named by the text (its content the replacement) or removes it (replacement None)
MUTATIONS = [
    ("push runs on every branch", "brand-creator.yml", "    branches:\n      - main\n", "", "push must run on main only"),
    ("push also runs on tags", "swift.yml", "    branches:\n      - main\n", "    branches:\n      - main\n    tags:\n      - \"*\"\n", "push has tags"),
    ("push runs on another branch too", "batbelt.yml", "      - main\n", "      - main\n      - dev\n", "push must run on main only"),
    ("a trigger that fires on tags", "swift.yml", "  workflow_dispatch:\n", "  workflow_dispatch:\n  create:\n", "nothing else (found: create"),
    ("pull_request filters other paths", "docs.yml", "  pull_request:\n    paths:\n      - \"**/*.md\"\n", "  pull_request:\n    paths:\n", "same, non-empty paths list"),
    ("no manual run", "marketplace.yml", "  workflow_dispatch:\n", "", "must trigger on push, pull_request and workflow_dispatch"),
    ("a floating runner image", "batbelt.yml", "runs-on: ubuntu-24.04", "runs-on: ubuntu-latest", "floating runner image"),
    ("a floating larger runner", "brand-creator.yml", "runs-on: macos-26", "runs-on: macos-latest-large", "floating runner image"),
    ("a floating image in a block list", "swift.yml", JOB, "    runs-on:\n      - ubuntu-latest\n", "floating runner image"),
    ("a runner the check cannot read", "swift.yml", JOB, "    runs-on: [ubuntu-24.04]\n", "cannot be read as one pinned image label"),
    ("main runs can be cancelled", "brand-creator.yml", f"cancel-in-progress: {PR_ONLY}", "cancel-in-progress: true", "can cancel a run on main"),
    ("main runs share one group", "brand-creator.yml", "github.event.pull_request.number || github.sha", "github.ref", "is shared by runs on main"),
    ("a write token", "swift.yml", "  contents: read", "  contents: write", "permissions must be contents: read"),
    ("a job's own permissions", "swift.yml", JOB, JOB + "    permissions:\n      contents: write\n", "a job sets its own permissions"),
    ("a plugin workflow misses its folder", "swift.yml", '      - "plugins/swift/**"\n', "", "does not filter on plugins/swift/**"),
    ("a flow list the reader does not read", "swift.yml", "    branches:\n      - main\n", "    branches: [main]\n", "unreadable"),
    ("a stray workflow", None, "stray.yml", "name: stray\n", "stray.yml is not a plugin's workflow"),
    ("a .yaml workflow", None, "release.yaml", "name: release\n", "release.yaml: use the .yml extension"),
    ("a plugin without a workflow", None, "swift.yml", None, "plugins/swift has no workflow"),
]


def self_test() -> int:
    workflows, plugins = repo()
    base = check(workflows, plugins)
    if base:
        print("self-test: the workflows as they are must pass first:", *base, sep="\n  ", file=sys.stderr)
        return 1
    missed = []
    for what, f, old, new, words in MUTATIONS:
        copy = dict(workflows)
        if f is None:
            if new is None:
                copy.pop(old)
            else:
                copy[old] = new
        elif old not in copy[f]:
            missed.append(f"{what}: the mutation did not apply ({old!r} is not in {f})")
            continue
        else:
            copy[f] = copy[f].replace(old, new)
        got = check(copy, plugins)
        if not any(words in e for e in got):
            missed.append(f"{what}: not caught (errors: {got or 'none'})")
    for m in missed:
        print("SELF-TEST FAILED:", m, file=sys.stderr)
    print(f"self-test: {len(MUTATIONS) - len(missed)} of {len(MUTATIONS)} broken rules caught")
    return 1 if missed else 0


def main() -> int:
    if sys.argv[1:] == ["--self-test"]:
        return self_test()
    if sys.argv[1:]:
        print(__doc__, file=sys.stderr)
        return 2
    workflows, plugins = repo()
    errors = check(workflows, plugins)
    for e in errors:
        print("ERROR:", e, file=sys.stderr)
    print(f"{len(workflows)} workflows checked, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

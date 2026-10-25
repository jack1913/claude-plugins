#!/usr/bin/env python3
"""Check the shape of every workflow in .github/workflows/ and every ruleset in .github/rulesets/. Standard library only; run
from the repository root.

    python3 .github/scripts/check-workflows.py                     check the workflows and rulesets as they are
    python3 .github/scripts/check-workflows.py --self-test         break each rule in a copy, and fail unless the check catches it
    python3 .github/scripts/check-workflows.py --ruleset <plugin>  print the release-tag ruleset that plugin needs (its file's content)
    python3 .github/scripts/check-workflows.py --ruleset main      print the branch ruleset main needs (main-branch.json's content)
    python3 .github/scripts/check-workflows.py --live              compare the rulesets on GitHub with the files (needs gh, signed in;
                                                                   CI never runs it, so a change made on GitHub shows up only here)

The rule is .claude/rules/ci-workflow-per-plugin.md; why: docs/adr/ADR-0004-ci-runs-on-main-and-pull-requests-never-on-tags.md,
docs/adr/ADR-0005-release-tags-need-a-passing-ci-verdict.md and docs/adr/ADR-0006-main-and-release-tags-cannot-be-rewritten.md.
Fails when:
  - the workflow files are not one <plugin>.yml per plugin under plugins/ plus marketplace.yml and docs.yml (a .yaml file
    is reported too: GitHub runs both extensions);
  - a workflow triggers on anything but push, pull_request and workflow_dispatch (create or release would run on a tag);
  - push runs for anything but main: push.branches must be exactly main, with no tags, tags-ignore or branches-ignore
    (GitHub evaluates no path filter for a tag push, so a tag would start every workflow again);
  - push and pull_request filter on different paths, or a plugin's workflow does not filter on plugins/<name>/** and its own file;
  - the top-level permissions are not contents: read, or a job sets its own permissions;
  - a job runs on a floating runner image (any runs-on that says latest), or on one this check cannot read;
  - a job sets no timeout-minutes, or one that is neither a whole number of minutes from 1 to 60 nor a matrix value
    (GitHub's default is six hours, and a hung job holds its verdict, and every release tag that needs it, that long; a job
    that calls a reusable workflow cannot set one, so no job may call one);
  - a run on main can be cancelled or replaced: the concurrency block must be top-level, its group must hold github.sha
    (one group per commit on main), and cancel-in-progress must be false or ${{ github.event_name == 'pull_request' }};
  - a workflow has no job named after it (its verdict: for a plugin's workflow and docs.yml, the check a release-tag ruleset
    requires), that job sets a name of its own or runs only under a condition (a job skipped by its if counts as passed in a
    required check), or, in a workflow of more than one job, it does not need every other job, does not run
    if: ${{ always() }}, or its steps are not exactly VERDICT_STEPS (which fail unless every job it needs succeeded);
  - another job's check carries a workflow's name (a ruleset requiring that check could read the wrong job);
  - docs.yml does not run this check: every release-tag ruleset requires its job, so this is what checks the verdicts on
    every commit a release tag can point to;
  - .github/rulesets/ does not hold exactly one <plugin>-release-tags.json per plugin and main-branch.json, each equal to what
    --ruleset prints: tags <plugin>--v* need the checks <plugin> and docs, from GitHub Actions, on the tagged commit, and are
    never deleted or moved; main is never deleted or force-pushed; enforced, with no bypass; or a plugin is named main
    (--ruleset main prints the branch ruleset).
The reader understands only the YAML these keys use here (block mappings, block lists of scalars, quoted scalars that end on
their own line); anything else in them is reported as unreadable, never passed.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PR_ONLY = "${{ github.event_name == 'pull_request' }}"
TRIGGERS = {"push", "pull_request", "workflow_dispatch"}
KEY = re.compile(r"([A-Za-z_][\w-]*):(?:\s+(.*))?")
ALWAYS = ("${{ always() }}", "always()")
ACTIONS = 15368   # the GitHub Actions app: a check of the same name from any other source does not count
TIMEOUT = re.compile(r"[1-9][0-9]*|\$\{\{ *matrix\.[\w-]+ *\}\}")   # a whole number of minutes, or a matrix value
MAX_MINUTES = 60
# The steps of a verdict that waits for other jobs, dedented to the job's keys: it fails unless every job it needs succeeded
# (a failed, cancelled or skipped job is never green).
VERDICT_STEPS = r"""steps:
  - name: Every job passed
    env:
      NEEDS: ${{ toJSON(needs) }}
    run: |
      jq -r 'to_entries[] | "\(.key): \(.value.result)"' <<< "$NEEDS"
      jq -e 'all(.[]; .result == "success")' <<< "$NEEDS" > /dev/null"""
DOCS_RUNS_CHECK = re.compile(r"^\s+run: python3 \.github/scripts/check-workflows\.py$", re.M)


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
        value = re.match(r"\s*(?:-\s+)?(?:[A-Za-z_][\w-]*:\s+)?(.*)$", line).group(1)
        if value[:1] in ("'", '"') and (len(value) < 2 or value[-1] != value[0]):   # YAML would read the next lines into it
            raise Unreadable(f"a quoted value goes on over more than one line at {line.strip()!r}: write it on one line")
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


def read_jobs(lines: list[str]) -> dict[str, dict]:
    """{job id: the job's own name, needs, if and timeout-minutes, where it sets them}: needs as written (a scalar or a block
    list of job ids)."""
    start = next((k for k, ln in enumerate(lines) if ln == "jobs:"), None)
    if start is None or start + 1 >= len(lines) or indent(lines[start + 1]) == 0:
        raise Unreadable("no top-level jobs: block with a job in it")
    job_ind = indent(lines[start + 1])
    jobs: dict[str, dict] = {}
    job: dict = {}
    key_ind = None
    i = start + 1
    while i < len(lines) and indent(lines[i]) > 0:
        ln, ind = lines[i], indent(lines[i])
        m = KEY.fullmatch(ln.strip())
        if ind == job_ind:
            if not m or m.group(2):
                raise Unreadable(f"jobs: {ln.strip()!r} is not a job id")
            job, key_ind = jobs.setdefault(m.group(1), {}), None
        elif ind < job_ind:
            raise Unreadable(f"jobs: unexpected indentation at {ln.strip()!r}")
        else:
            key_ind = ind if key_ind is None else key_ind
            if ind == key_ind and m and m.group(1) in ("name", "needs", "if", "timeout-minutes"):
                key, val = m.group(1), m.group(2)
                deeper = i + 1 < len(lines) and indent(lines[i + 1]) > key_ind
                if val and deeper:   # a plain scalar YAML folds on over the next lines: the value is not what this line says
                    raise Unreadable(f"jobs: {key}: {val} goes on over more than one line: write it on one line")
                if val:
                    job[key] = scalar(val)
                elif key == "needs" and deeper:
                    items = []
                    while i + 1 < len(lines) and indent(lines[i + 1]) > key_ind:
                        i += 1
                        if not lines[i].lstrip().startswith("- "):
                            raise Unreadable(f"jobs: needs: {lines[i].strip()!r} is not an item of a block list")
                        items.append(scalar(lines[i].lstrip()[2:]))
                    job[key] = items
                else:
                    raise Unreadable(f"jobs: {key} has no value on its line: write it there ({key} needs a block list only for needs)")
        i += 1
    return jobs


def verdict_steps(text: str, name: str) -> str | None:
    """The steps block of job `name` as written, without comment and blank lines, dedented to the job's keys; None without one."""
    raw = text.replace("\r\n", "\n").split("\n")
    start = next((k for k, ln in enumerate(raw) if strip_comment(ln) == f"  {name}:"), None)
    if start is None:
        return None
    body = []
    for ln in raw[start + 1:]:
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        if indent(ln) <= 2:
            break
        body.append(ln.rstrip())
    at = next((k for k, ln in enumerate(body) if ln == "    steps:"), None)
    if at is None:
        return None
    steps = [body[at]] + [ln for ln in body[at + 1:]]
    end = next((k for k, ln in enumerate(steps) if k and indent(ln) <= 4), len(steps))
    return "\n".join(ln[4:] for ln in steps[:end])


def check_verdict(f: str, text: str, jobs: dict[str, dict], verdicts: set[str]) -> list[str]:
    """The workflow's verdict: one job named after the workflow, which waits for every other job, reports on every run and fails
    unless every job it waits for succeeded."""
    name, errors = f.removesuffix(".yml"), []
    for jid, job in sorted(jobs.items()):
        shown = job.get("name", jid)
        if shown in verdicts and jid != name:
            errors.append(f"{f}: job {jid}'s check is named {shown}, the verdict of {shown}.yml: a ruleset requiring {shown} could read this job instead")
    if name not in jobs:
        return errors + [f"{f}: has no job {name}: a workflow's verdict, the check a release-tag ruleset requires, is the job named after it"]
    verdict = jobs[name]
    if "name" in verdict:
        errors.append(f"{f}: job {name} sets name: {verdict['name']}: its check must be named {name}, so it sets no name of its own")
    others = sorted(set(jobs) - {name})
    cond = verdict.get("if")
    if others:
        needs = verdict.get("needs") or []
        needs = [needs] if isinstance(needs, str) else needs
        missing = [j for j in others if j not in needs]
        if missing:
            errors.append(f"{f}: job {name} does not need {', '.join(missing)}: the verdict must wait for every other job")
        if cond not in ALWAYS:
            errors.append(f"{f}: job {name} must run if: ${{{{ always() }}}}: a job skipped after a failure counts as passed in a required check")
        if verdict_steps(text, name) != VERDICT_STEPS:
            errors.append(f"{f}: job {name}'s steps must be exactly VERDICT_STEPS of check-workflows.py (as in brand-creator.yml): "
                          "they fail unless every job it needs succeeded")
    elif cond is not None and cond not in ALWAYS:
        errors.append(f"{f}: job {name} runs only if: {cond}: a verdict skipped by its condition counts as passed in a required check")
    return errors


def check_one(f: str, text: str, plugins: list[str], verdicts: set[str]) -> list[str]:
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
    if f == "docs.yml" and not DOCS_RUNS_CHECK.search("\n".join(strip_comment(ln) for ln in text.split("\n"))):
        errors.append(f"{f} does not run `python3 .github/scripts/check-workflows.py`: every release-tag ruleset requires its job, "
                      "so that step checks the verdicts on every commit a release tag can point to")
    jobs = read_jobs(lines)
    for jid, job in sorted(jobs.items()):
        minutes = job.get("timeout-minutes")
        if minutes is None:
            errors.append(f"{f}: job {jid} sets no timeout-minutes: GitHub's default is six hours, and a hung job holds its verdict, "
                          "and every release tag that needs it, that long")
        elif not TIMEOUT.fullmatch(minutes) or (minutes.isdigit() and int(minutes) > MAX_MINUTES):
            errors.append(f"{f}: job {jid} timeout-minutes {minutes or repr(minutes)} must be a whole number of minutes from 1 to "
                          f"{MAX_MINUTES}, or a matrix value")
    return errors + check_verdict(f, text, jobs, verdicts)


def release_ruleset(plugin: str) -> dict:
    """The tag ruleset a plugin's releases need: a tag <plugin>--v* only on a commit where the plugin's verdict and docs passed,
    and never deleted or moved once it is there."""
    return {
        "name": f"{plugin} release tags",
        "target": "tag",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": [f"refs/tags/{plugin}--v*"], "exclude": []}},
        "rules": [{"type": "required_status_checks", "parameters": {
            "strict_required_status_checks_policy": False,
            "do_not_enforce_on_create": False,
            "required_status_checks": [{"context": plugin, "integration_id": ACTIONS}, {"context": "docs", "integration_id": ACTIONS}],
        }}, {"type": "deletion"}, {"type": "update"}],
    }


MAIN = "main-branch.json"


def main_ruleset() -> dict:
    """The branch ruleset main needs: never deleted and never force-pushed. A push that only adds commits goes through, and
    nothing else is required of it (ADR-0004: releases land by direct pushes)."""
    return {
        "name": "main branch",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
        "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
    }


def rulesets_needed(plugins: list[str]) -> dict[str, tuple[str, dict]]:
    """{file name in .github/rulesets/: (what --ruleset takes to print it, the ruleset)}: each plugin's release tags, and main."""
    return {f"{p}-release-tags.json": (p, release_ruleset(p)) for p in plugins} | {MAIN: ("main", main_ruleset())}


def first_difference(got, want, at: str = "") -> str:
    """Where two JSON values first differ, as `<path> is <got>, not <want>`."""
    if isinstance(got, dict) and isinstance(want, dict):
        for k in sorted(set(got) | set(want)):
            if k not in got:
                return f"{at}{k} is missing"
            if k not in want:
                return f"{at}{k} is not part of it"
            if got[k] != want[k]:
                return first_difference(got[k], want[k], f"{at}{k}.")
    if isinstance(got, list) and isinstance(want, list) and len(got) == len(want):
        for n, (g, w) in enumerate(zip(got, want)):
            if g != w:
                return first_difference(g, w, f"{at}{n}.")
    return f"{at.rstrip('.') or 'the file'} is {json.dumps(got)}, not {json.dumps(want)}"


def check_rulesets(rulesets: dict[str, str], plugins: list[str]) -> list[str]:
    """Every problem with the rulesets ({file name: text}) of a repository whose plugins are `plugins`."""
    expected = rulesets_needed(plugins)
    errors = [f".github/rulesets/{f} is not a plugin's release-tag ruleset (<plugin>-release-tags.json) or {MAIN}"
              for f in sorted(set(rulesets) - set(expected))]
    for f, (arg, want) in sorted(expected.items()):
        if f not in rulesets:
            owner = "main has no branch ruleset" if f == MAIN else f"plugins/{arg} has no release-tag ruleset"
            errors.append(f"{owner} .github/rulesets/{f} (write it with --ruleset {arg})")
            continue
        try:
            got = json.loads(rulesets[f])
        except ValueError as e:
            errors.append(f".github/rulesets/{f} is not JSON: {e}")
            continue
        if got != want:
            errors.append(f".github/rulesets/{f} is not the ruleset {arg} needs: {first_difference(got, want)} (print it with --ruleset {arg})")
    return errors


def check(workflows: dict[str, str], plugins: list[str], rulesets: dict[str, str]) -> list[str]:
    """Every problem with the workflows and the rulesets ({file name: text}) of a repository whose plugins are `plugins`."""
    errors = [f"{f}: use the .yml extension (GitHub runs .yaml files too, and this check reads .yml)" for f in sorted(workflows) if not f.endswith(".yml")]
    yml = {f: t for f, t in workflows.items() if f.endswith(".yml")}
    expected = {f"{p}.yml" for p in plugins} | {"marketplace.yml", "docs.yml"}
    errors += [f"{f} is not a plugin's workflow, marketplace.yml or docs.yml" for f in sorted(set(yml) - expected)]
    errors += [f"plugins/{p} has no workflow .github/workflows/{p}.yml" for p in sorted(plugins) if f"{p}.yml" not in yml]
    errors += ["plugins/main: no plugin may be named main: --ruleset main prints main's branch ruleset"] if "main" in plugins else []
    verdicts = {f.removesuffix(".yml") for f in yml}
    for f, text in sorted(yml.items()):
        try:
            errors += check_one(f, text, plugins, verdicts)
        except Unreadable as e:
            errors.append(f"{f}: unreadable: {e}")
    return errors + check_rulesets(rulesets, plugins)


def repo() -> tuple[dict[str, str], list[str], dict[str, str]]:
    folder = ROOT / ".github" / "workflows"
    workflows = {p.name: p.read_text(encoding="utf-8") for p in sorted(folder.iterdir()) if p.suffix in (".yml", ".yaml")}
    plugins = sorted(d.name for d in (ROOT / "plugins").iterdir() if d.is_dir())
    folder = ROOT / ".github" / "rulesets"
    rulesets = {p.name: p.read_text(encoding="utf-8") for p in sorted(folder.iterdir()) if p.is_file()} if folder.is_dir() else {}
    return workflows, plugins, rulesets


JOB = "    runs-on: ubuntu-24.04\n"
# (what breaks, the file it breaks, the text, its replacement, the words the error must hold); a .json file is a ruleset;
# None as the file adds a file named by the text (its content the replacement) or removes it (replacement None)
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
    ("a workflow without its verdict", "swift.yml", "\n  swift:\n", "\n  test:\n", "swift.yml: has no job swift"),
    ("a verdict that does not wait for a job", "brand-creator.yml", "      - validate\n", "", "does not need validate"),
    ("a verdict skipped after a failure", "brand-creator.yml", "    if: ${{ always() }}\n", "", "job brand-creator must run if:"),
    ("a verdict with a name of its own", "docs.yml", "\n  docs:\n", "\n  docs:\n    name: check\n", "job docs sets name: check"),
    ("another job's check carries a verdict's name", "brand-creator.yml", "\n  validate:\n", "\n  validate:\n    name: docs\n", "the verdict of docs.yml"),
    ("a job without a timeout", "swift.yml", "    timeout-minutes: 10\n", "", "job swift sets no timeout-minutes"),
    ("a matrix job without a timeout", "brand-creator.yml", "    timeout-minutes: ${{ matrix.job-minutes }}\n", "", "job linux-suite sets no timeout-minutes"),
    ("a timeout on a step, not on the job", "swift.yml", "    timeout-minutes: 10\n    steps:\n      - uses: actions/checkout@v5\n",
     "    steps:\n      - uses: actions/checkout@v5\n        timeout-minutes: 10\n", "job swift sets no timeout-minutes"),
    ("a timeout as long as GitHub's default", "swift.yml", "    timeout-minutes: 10\n", "    timeout-minutes: 360\n", "timeout-minutes 360 must be"),
    ("a timeout with no value", "docs.yml", "    timeout-minutes: 10\n", "    timeout-minutes: null\n", "timeout-minutes null must be"),
    ("a quoted value folded over two lines", "swift.yml", JOB, JOB + "    env:\n      X: \"a\n    timeout-minutes: 10\"\n",
     "a quoted value goes on over more than one line"),
    ("a plugin without a release-tag ruleset", None, "swift-release-tags.json", None, "plugins/swift has no release-tag ruleset"),
    ("main without its branch ruleset", None, MAIN, None, "main has no branch ruleset"),
    ("a stray ruleset", None, "stray.json", "{}\n", "stray.json is not a plugin's release-tag ruleset"),
    ("a release tag that can be deleted", "swift-release-tags.json", '"type": "deletion"', '"type": "creation"', "rules.1.type is \"creation\""),
    ("a release tag that can be moved", "batbelt-release-tags.json", '"type": "update"', '"type": "creation"', "rules.2.type is \"creation\""),
    ("a main that can be force-pushed", MAIN, '"type": "non_fast_forward"', '"type": "deletion"', "rules.1.type is \"deletion\""),
    ("a main that an admin may rewrite", MAIN, '"bypass_actors": []',
     '"bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]', "main-branch.json is not the ruleset main needs"),
    ("a ruleset that is not JSON", "batbelt-release-tags.json", '"target": "tag",', '"target": "tag"', "batbelt-release-tags.json is not JSON"),
    ("a ruleset that requires another check", "brand-creator-release-tags.json", '"context": "brand-creator"', '"context": "linux"', "required_status_checks.0.context is \"linux\""),
    ("a ruleset that lets an admin bypass it", "batbelt-release-tags.json", '"bypass_actors": []',
     '"bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]', "bypass_actors is"),
    ("a ruleset over every tag", "swift-release-tags.json", '"refs/tags/swift--v*"', '"refs/tags/*"', "ref_name.include.0 is \"refs/tags/*\""),
    ("a ruleset that only evaluates", "swift-release-tags.json", '"enforcement": "active"', '"enforcement": "evaluate"', "enforcement is \"evaluate\""),
    ("a ruleset that lets a tag be created anyway", "brand-creator-release-tags.json", '"do_not_enforce_on_create": false', '"do_not_enforce_on_create": true',
     "do_not_enforce_on_create is true"),
    ("a ruleset that takes the check from any app", "brand-creator-release-tags.json", '"integration_id": 15368\n', '"integration_id": 1\n', "integration_id is 1"),
    ("a verdict that passes whatever the jobs did", "brand-creator.yml", "          jq -e 'all(.[]; .result == \"success\")' <<< \"$NEEDS\" > /dev/null\n",
     "          true\n", "steps must be exactly VERDICT_STEPS"),
    ("a single-job verdict skipped by its condition", "swift.yml", "\n  swift:\n", "\n  swift:\n    if: github.event_name == 'pull_request'\n",
     "job swift runs only if:"),
    ("a verdict condition folded over two lines", "brand-creator.yml", "    if: ${{ always() }}\n",
     "    if: always()\n      && github.event_name == 'pull_request'\n", "goes on over more than one line"),
    ("a job name on the next line", "brand-creator.yml", "\n  validate:\n", "\n  validate:\n    name:\n      - docs\n", "name has no value on its line"),
    ("docs that no longer checks the verdicts", "docs.yml", "        run: python3 .github/scripts/check-workflows.py\n", "",
     "docs.yml does not run `python3 .github/scripts/check-workflows.py`"),
]


def self_test() -> int:
    workflows, plugins, rulesets = repo()
    base = check(workflows, plugins, rulesets)
    if base:
        print("self-test: the workflows and rulesets as they are must pass first:", *base, sep="\n  ", file=sys.stderr)
        return 1
    missed = []
    for what, f, old, new, words in MUTATIONS:
        wf, rs = dict(workflows), dict(rulesets)
        copy = rs if (f or old).endswith(".json") else wf
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
        got = check(wf, plugins, rs)
        if not any(words in e for e in got):
            missed.append(f"{what}: not caught (errors: {got or 'none'})")
    got = check(workflows, plugins + ["main"], rulesets)   # the one rule a file change cannot break: a plugin's name
    if not any("no plugin may be named main" in e for e in got):
        missed.append(f"a plugin named main: not caught (errors: {got or 'none'})")
    for m in missed:
        print("SELF-TEST FAILED:", m, file=sys.stderr)
    total = len(MUTATIONS) + 1
    print(f"self-test: {total - len(missed)} of {total} broken rules caught")
    return 1 if missed else 0


def live() -> int:
    """Every ruleset on GitHub, compared with its file: 0 when all match, 1 when one differs or is missing, 3 when gh cannot ask."""
    import subprocess

    def gh(*args: str):
        r = subprocess.run(["gh", "api", *args], capture_output=True, text=True, cwd=ROOT)   # {owner}/{repo}: this repository's
        if r.returncode:
            raise OSError(f"gh api {' '.join(args)}: {r.stderr.strip() or r.returncode}")
        return json.loads(r.stdout)

    workflows, plugins, rulesets = repo()
    if check(workflows, plugins, rulesets):
        print("--live: the files fail the check first: run it without --live", file=sys.stderr)
        return 1
    errors = []
    try:
        listed = [r for page in gh("--paginate", "--slurp", "repos/{owner}/{repo}/rulesets") for r in page]
        have = {r["name"]: r["id"] for r in listed}
        needed = rulesets_needed(plugins)
        expected = {want["name"] for _, want in needed.values()}
        for r in listed:   # a ruleset no file describes can refuse tags or pushes while every file matches
            if r["name"] not in expected:
                errors.append(f"GitHub has a {r.get('target')} ruleset {r['name']!r} (id {r['id']}, {r.get('enforcement')}) that no file describes")
        for name, (_, want) in sorted(needed.items()):
            f = f".github/rulesets/{name}"
            if want["name"] not in have:
                errors.append(f"GitHub has no ruleset {want['name']!r}: create it with gh api --method POST 'repos/{{owner}}/{{repo}}/rulesets' --input {f}")
                continue
            got = gh(f"repos/{{owner}}/{{repo}}/rulesets/{have[want['name']]}")
            got = {k: got.get(k) for k in want}
            if got != want:
                errors.append(f"the ruleset {want['name']!r} on GitHub is not {f}: {first_difference(got, want)} "
                              f"(update it with gh api --method PUT 'repos/{{owner}}/{{repo}}/rulesets/{have[want['name']]}' --input {f})")
    except (OSError, ValueError) as e:   # no gh, not signed in, no network, or an answer that is not JSON
        print(f"--live: cannot read the rulesets on GitHub: {e}", file=sys.stderr)
        return 3
    for e in errors:
        print("ERROR:", e, file=sys.stderr)
    print(f"{len(needed)} rulesets on GitHub compared with their files, {len(errors)} errors")
    return 1 if errors else 0


def main() -> int:
    args = sys.argv[1:]
    if args == ["--self-test"]:
        return self_test()
    if args == ["--live"]:
        return live()
    if len(args) == 2 and args[0] == "--ruleset":
        _, plugins, _ = repo()
        found = [want for arg, want in rulesets_needed(plugins).values() if arg == args[1]]
        if len(found) != 1:
            print(f"--ruleset: {args[1]} is neither main nor a plugin under plugins/ ({', '.join(plugins)})" if not found else
                  "--ruleset main: a plugin is named main, so main's branch ruleset cannot be told from its release tags", file=sys.stderr)
            return 2
        print(json.dumps(found[0], indent=2))
        return 0
    if args:
        print(__doc__, file=sys.stderr)
        return 2
    workflows, plugins, rulesets = repo()
    errors = check(workflows, plugins, rulesets)
    for e in errors:
        print("ERROR:", e, file=sys.stderr)
    print(f"{len(workflows)} workflows and {len(rulesets)} rulesets checked, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

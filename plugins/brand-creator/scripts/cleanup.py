#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator cleanup: take old round folders out of a project through git, after the owner's yes.

  brand-creator cleanup [--project DIR] [--keep rN]...                           the dry run (the default): print the plan, write qa/<date>-cleanup-plan.txt
  brand-creator cleanup [--project DIR] [--keep rN]... --record-yes CODE --said "<the owner's words>"
                                                                                  record the owner's yes to that plan in DECISIONS.md
  brand-creator cleanup [--project DIR] [--keep rN]... --yes CODE                remove the planned round folders with git rm (staged, never committed)

  brand-creator cleanup --history [--static] [--record-yes CODE --said "..." | --yes CODE]
                                                                                  slim frozen rounds in history/ to what their boards show (same three runs)

Whole round folders only, and only committed files that are unchanged, so everything removed can be restored from git. Kept: the latest round of each stage, the latest pick board, every
round something kept refers to (text, URLs, links, report inputs, BRAND-STATE.md and site/site.json), every earlier round board-lint reads for a kept board, every round it cannot place, and
each --keep. history/, site/ and assets/ are never touched, except the assets/_checks reports whose subject is in a removed round. CODE is the plan hash (12 to 64 hex digits of the sha256 the
dry run prints), checked against the plan computed again on every run: a plan that changed needs a new yes. The same --keep options are needed on all three runs. Exit codes: 0 done or
nothing to do, 1 a refusal, 2 usage (or a link or special file in a round to remove), 3 git is missing. The rules are in scripts/CONTRACT.md, "cleanup".

--history: for each frozen round in history/, what stays is what freeze keeps since 0.10.0 (its board pages, every file they load, read from the
files and in the browser, its scripts and its text records); the rest goes, with git rm, and history/MANIFEST.sha256 is rewritten and staged. A
history/ that does not match its manifest is refused. Without a set-up data directory it stops and names --static (files only). The plan file is
qa/<date>-cleanup-plan-history.txt, the record qa/<date>-cleanup-removed-history.txt, with its restore line (the freezes and the manifest).
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "boardlib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "marklib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "pagelib"))
from _common import (EXIT_CANNOT, EXIT_FAIL, EXIT_USAGE, ROUND_RE, CliError, Parser, add_project_arg, confine, fail, find_project, list_rounds, main_guard,  # noqa: E402
                     read_history_manifest, read_state, today, verify_history, write_bytes_if_changed, write_history_manifest)
import closure  # noqa: E402
import rounds as rd  # noqa: E402

CHUNK_FILES = 200           # git rm gets at most this many paths per call ...
CHUNK_BYTES = 64 * 1024     # ... and at most this many bytes of path
LIST_MAX = 20
HEX = re.compile(r"[0-9a-f]{12,64}")
STATE_DIRS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "rebase-merge", "rebase-apply")
IN_PROGRESS = {"MERGE_HEAD": "merge", "CHERRY_PICK_HEAD": "cherry-pick", "REVERT_HEAD": "revert", "BISECT_LOG": "bisect", "rebase-merge": "rebase", "rebase-apply": "rebase"}
ENTRY_RE = re.compile(r"^- Cleanup plan: sha256:([0-9a-f]{64})[ \t]*$")


# ---------------------------------------------------------------- git

def git_env() -> dict[str, str]:
    """The environment git runs in: no variable whose name starts with GIT_, so nothing left in the shell can point git at another repository or change its configuration."""
    return {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}


def git(project: Path, *args: str, input_ok: bool = True) -> subprocess.CompletedProcess:
    """One git call: a list of arguments (no shell), -C <project>, literal pathspecs, no optional locks (a read never writes the index), stdin closed, no GIT_* variable."""
    return subprocess.run(["git", "-C", str(project), "--no-optional-locks", "--literal-pathspecs", *args], stdin=subprocess.DEVNULL, capture_output=True,
                          env=git_env(), shell=False)


def git_text(cp: subprocess.CompletedProcess) -> str:
    return (cp.stderr or b"").decode("utf-8", "replace").strip() or (cp.stdout or b"").decode("utf-8", "replace").strip()


class Entry(NamedTuple):
    kind: str   # "1" ordinary, "2" renamed, "u" unmerged, "?" untracked, "!" ignored
    xy: str
    path: str   # relative to the repository root, as git prints it


def status_entries(project: Path, *paths: str, untracked: bool = True, ignored: bool = False) -> list[Entry]:
    args = ["status", "--porcelain=v2", "-z", "--no-renames", "--untracked-files=all" if untracked else "--untracked-files=no"] + (["--ignored=matching"] if ignored else [])
    cp = git(project, *args, *(["--", *paths] if paths else []))
    if cp.returncode != 0:
        fail(EXIT_FAIL, f"git status failed: {git_text(cp)}")
    toks = cp.stdout.split(b"\0")
    out: list[Entry] = []
    i = 0
    while i < len(toks):
        raw = toks[i]
        i += 1
        if not raw:
            continue
        t = chr(raw[0])
        text = os.fsdecode(raw)
        if t == "1":
            p = text.split(" ", 8)
            out.append(Entry("1", p[1], p[8]))
        elif t == "2":
            p = text.split(" ", 9)
            out.append(Entry("2", p[1], p[9]))
            i += 1   # the original path follows as a token of its own
        elif t == "u":
            p = text.split(" ", 10)
            out.append(Entry("u", p[1], p[10]))
        elif t in "?!":
            out.append(Entry(t, t, text[2:]))
    return out


class Repo(NamedTuple):
    project: Path
    top: Path
    prefix: str     # what git prints before a project path (brand/), "" when the project is the repository root
    head: str

    def local(self, repo_path: str) -> str:
        """A path git printed from the repository root, as a path relative to the project."""
        if not repo_path.startswith(self.prefix):
            fail(EXIT_FAIL, f"git printed {repo_path!r}, which is not under {self.prefix!r}: this is a bug in cleanup; nothing was changed")
        return repo_path[len(self.prefix):]


def open_repo(project: Path) -> Repo:
    """Steps 3 to 5: git is there, the project is in a work tree, and git can restore what is removed."""
    if shutil.which("git") is None:
        fail(EXIT_CANNOT, "cannot run: git not found on PATH. cleanup removes rounds through git so they can be restored. Install git.")
    cp = git(project, "rev-parse", "--show-toplevel")
    if cp.returncode != 0:
        fail(EXIT_FAIL, f"refused: {project} is not in a git repository, so a removed round could not be restored. Commit the project first, then run cleanup again.")
    top = Path(cp.stdout.decode("utf-8", "replace").strip())
    prefix = git(project, "rev-parse", "--show-prefix").stdout.decode("utf-8", "replace").strip()
    head = git(project, "rev-parse", "--verify", "-q", "HEAD^{commit}")
    if head.returncode != 0:
        fail(EXIT_FAIL, "refused: nothing is committed yet, so a removed round could not be restored. Commit the project first, then run cleanup again.")
    gitdir = Path(git(project, "rev-parse", "--absolute-git-dir").stdout.decode("utf-8", "replace").strip())
    for name in STATE_DIRS:
        if (gitdir / name).exists():
            fail(EXIT_FAIL, f"refused: a {IN_PROGRESS[name]} is in progress in {top}; finish it first")
    own = (Path(project) / "rounds" / ".git").exists() or (Path(project) / "rounds" / ".git").is_symlink()
    if not own:
        ls = git(project, "ls-files", "-s", "-z", "--", "rounds").stdout
        own = any(t.split(b" ", 1)[0] == b"160000" and t.split(b"\t", 1)[-1] == b"rounds" for t in ls.split(b"\0") if t)
    if own:
        fail(EXIT_FAIL, "refused: rounds/ is a git repository of its own (a submodule or a nested .git), so the project's git cannot restore it")
    return Repo(Path(project), top, prefix, head.stdout.decode().strip())


# ---------------------------------------------------------------- layout, links and git state of what would go (steps 6, 9a, 9b)

def shown(lst: list[str], head: str) -> str:
    lines = sorted(lst)
    more = f"\n  and {len(lines) - LIST_MAX} more" if len(lines) > LIST_MAX else ""
    return head + "\n" + "\n".join(f"  {x}" for x in lines[:LIST_MAX]) + more


def check_layout(project: Path) -> None:
    """Step 6: rounds/ and each round folder is a real folder, and each is named r<N> with ASCII digits and no leading zero, so each N names one folder."""
    d = Path(project) / "rounds"
    if d.is_symlink():
        fail(EXIT_USAGE, "rounds is a symbolic link: cleanup removes real round folders only, and a link can lead out of the project")
    if not d.is_dir():
        return
    for p in sorted(d.iterdir(), key=lambda q: q.name):
        if not (ROUND_RE.match(p.name) and p.is_dir()):
            continue
        if p.is_symlink():
            fail(EXIT_USAGE, f"rounds/{p.name} is a symbolic link: cleanup removes real round folders only, and a link can lead out of the project")
        if not rd.ASCII_ROUND.fullmatch(p.name):
            fail(EXIT_USAGE, f"rounds/{p.name} is read as round {int(ROUND_RE.match(p.name).group(1))}: name round folders r<N> with no leading zero and ASCII digits, then run cleanup again")


def check_links(project: Path, cands: list[int], reports: list[str]) -> None:
    """Step 9a: a symbolic link, a FIFO, a socket or a device in a round to remove (or a report to remove), exit 2."""
    found: list[str] = []

    def kind_of(p: Path) -> str | None:
        st = os.lstat(p)
        if stat.S_ISLNK(st.st_mode):
            return "a symbolic link"
        if stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode):
            return None
        return "a special file (a FIFO, socket or device)"

    for n in cands:
        base = Path(project) / "rounds" / f"r{n}"
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            for name in dirnames + filenames:
                full = Path(dirpath) / name
                k = kind_of(full)
                if k:
                    found.append(f"{json.dumps(full.relative_to(project).as_posix(), ensure_ascii=False)} is {k}: cleanup removes real files only, and a link can lead out of the project")
    for r in reports:
        k = kind_of(Path(project) / r) if os.path.lexists(Path(project) / r) else None
        if k:
            found.append(f"{json.dumps(r, ensure_ascii=False)} is {k}: cleanup removes real files only")
    if found:
        raise CliError(EXIT_USAGE, shown(found, f"refused: {len(found)} link(s) or special file(s) in what would be removed:"))


class Removal(NamedTuple):
    files: list[tuple[str, str, str]]    # (blob, mode, path) of what git rm takes, sorted by path bytes
    loose: list[str]                     # reports of removed work that git does not know: deleted, part of the plan
    ds_store: list[str]                  # .DS_Store files in the rounds to remove: deleted, not part of the plan


def check_git_state(repo: Repo, cands: list[int], reports: list[str]) -> Removal:
    """Step 9b: every file of a round to remove is committed as it is, and the disk holds nothing git does not list (except .DS_Store). Reports of removed work follow the same rule, except that
    one git does not know is just deleted (it is listed in the plan and its hash). Lists every problem found (up to 20)."""
    project = repo.project
    dirs = [f"rounds/r{n}" for n in cands]
    paths = dirs + reports
    problems: dict[str, str] = {}
    tracked: dict[str, tuple[str, str]] = {}
    ls = git(project, "ls-files", "-v", "-s", "-z", "--", *paths)
    if ls.returncode != 0:
        fail(EXIT_FAIL, f"git ls-files failed: {git_text(ls)}")
    for tok in ls.stdout.split(b"\0"):
        if not tok:
            continue
        m = re.match(r"^(\S) (\d+) ([0-9a-f]+) (\d)\t(.*)$", os.fsdecode(tok), re.S)
        if not m:
            fail(EXIT_FAIL, f"git ls-files printed a line cleanup cannot read: {tok!r}")
        tag, mode, blob, stage, path = m.groups()
        tracked[path] = (mode, blob)
        if mode == "160000":
            problems[path] = "submodule"
        elif tag.islower():
            problems[path] = "hidden from git status (assume-unchanged)"
        elif tag == "S":
            problems[path] = "hidden from git status (skip-worktree)"
    loose: list[str] = []
    for e in status_entries(project, *paths, ignored=True):
        path = repo.local(e.path)
        if e.kind in "?!":
            if path.rsplit("/", 1)[-1] == ".DS_Store":
                continue
            if path in reports:
                loose.append(path)
                continue
            if path.endswith("/") and e.kind == "!" and any(r.startswith(path) for r in reports):
                # an ignored folder is printed as the folder, not its files: its reports are loose
                loose.extend(r for r in reports if r.startswith(path))
                continue
            problems.setdefault(path, "not known to git")
        elif e.kind == "u":
            problems[path] = "conflicted"
        elif e.kind == "2":
            problems[path] = "renamed"
        elif e.xy[0] != ".":
            problems[path] = "staged"
        elif e.xy[1] == "D":
            problems[path] = "deleted"
        else:
            problems[path] = "modified"
    ds: list[str] = []
    # on macOS git stores names precomposed (core.precomposeunicode), while the disk may hold them decomposed
    pc = git(project, "config", "--bool", "core.precomposeunicode").stdout.strip() == b"true"
    for d in dirs:
        base = Path(project) / d
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            here = Path(dirpath).relative_to(project).as_posix()
            for name in dirnames + filenames:
                if name == ".git":
                    problems[f"{here}/.git"] = "not known to git (a .git entry: a nested repository)"
            for name in filenames:
                p = f"{here}/{name}"
                if pc and p not in tracked:
                    p = unicodedata.normalize("NFC", p)
                if name == ".DS_Store" and p not in tracked:
                    ds.append(p)
                elif p not in tracked and not os.path.islink(Path(dirpath) / name):
                    problems.setdefault(p, "not known to git")
        if not any(t.startswith(d + "/") for t in tracked):
            problems[d] = "no file of this round is known to git"
    for r in reports:
        if os.path.lexists(Path(project) / r) and r not in tracked and r not in loose and r not in problems:
            loose.append(r)
    if problems:
        lines = [f"{label}: {json.dumps(p, ensure_ascii=False)}" for p, label in problems.items()]
        raise CliError(EXIT_FAIL, shown(lines, f"refused: {len(lines)} file(s) in the rounds and reports to remove are not committed as they are, so they could not be restored:"))
    files = sorted(((blob, mode, p) for p, (mode, blob) in tracked.items()), key=lambda t: t[2].encode("utf-8", "surrogateescape"))
    return Removal(files, sorted(set(loose)), sorted(ds))


# ---------------------------------------------------------------- the plan

def display_slug(project: Path) -> str:
    slug = str(read_state(project).get("slug", "") or "").strip() or Path(project).name
    return slug if re.fullmatch(r"[A-Za-z0-9._-]+", slug) else json.dumps(slug, ensure_ascii=False)


def clean(s: str) -> str:
    return re.sub(r"[\x00-\x1f\x7f]", "?", s)


def mb(n: int) -> str:
    return f"{n / 1_000_000:.1f} MB"


def frozen_map(project: Path) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for f in sorted((Path(project) / "history").glob("*/FROZEN.md")):
        try:
            m = re.search(r"frozen from rounds/r([0-9]+)", f.read_text(encoding="utf-8", errors="replace"), re.I)
        except OSError:
            continue
        if m:
            out.setdefault(int(m.group(1)), []).append(f.parent.name)
    return out


class Plan(NamedTuple):
    text: str
    hash: str
    remove: list[int]
    keep: list[int]
    removal: Removal
    reports: list[str]
    head: str
    date: str
    extra: list[int]

    @property
    def code(self) -> str:
        return self.hash[:12]


def reasons_text(whys: list[str]) -> str:
    refs = [w[len("referenced: "):] for w in whys if w.startswith("referenced: ")]
    out = [w for w in whys if not w.startswith("referenced: ")]
    if refs:
        out.append("referenced: " + ", ".join(refs[:3]) + (f" (and {len(refs) - 3} more)" if len(refs) > 3 else ""))
    return clean("; ".join(out))


def build_plan(repo: Repo, rounds: list[tuple[int, Path]], keep: rd.Keep, extra: list[int], removal: Removal, reports: list[str]) -> Plan:
    project = repo.project
    kept = sorted(keep.reasons)
    remove = [n for n, _ in rounds if n not in keep.reasons]
    date = today()
    slug = display_slug(project)
    others = sum(1 for e in status_entries(project, untracked=False) if e.kind in "12u" and e.xy[0] not in ".")
    sizes: dict[int, list[int]] = {n: [0, 0] for n in remove}
    for _blob, _mode, p in removal.files:
        m = re.match(r"^rounds/r([0-9]+)/", p)
        if m and int(m.group(1)) in sizes:
            sizes[int(m.group(1))][0] += 1
            try:
                sizes[int(m.group(1))][1] += os.lstat(Path(project) / p).st_size
            except OSError:
                pass
    frozen = frozen_map(project)
    total_bytes = sum(b for _, b in sizes.values()) + sum(os.lstat(Path(project) / p).st_size for _b, _m, p in removal.files if not p.startswith("rounds/") and os.path.lexists(Path(project) / p))
    canon = ["brand-creator cleanup plan v1", slug] + [f"keep-option r{n}" for n in sorted(set(extra))] + [f"remove r{n}" for n in remove]
    canon += [f"file {blob} {mode} {json.dumps(p, ensure_ascii=False)}" for blob, mode, p in removal.files]
    canon += [f"loose {json.dumps(p, ensure_ascii=False)}" for p in removal.loose]
    digest = hashlib.sha256(("\n".join(canon) + "\n").encode("utf-8", "surrogateescape")).hexdigest()
    lines = ["brand-creator cleanup plan", f"project: {slug}", f"date: {date}", f"head: {repo.head} (removed files are restored from it)",
             f"plan: sha256:{digest}   code: {digest[:12]}", ""]
    lines.append(f"keep ({len(kept)} round{'s' if len(kept) != 1 else ''}):")
    for n in kept:
        i = keep.infos[n]
        label = i.kind if i.stage == "mark" and i.kind else i.stage
        lines.append(f"  {('r' + str(n)).ljust(5)}{label.ljust(11)} {reasons_text(keep.reasons[n])}")
    lines += ["", f"remove ({len(remove)} round{'s' if len(remove) != 1 else ''}, {len(removal.files)} files, {mb(total_bytes)}):"]
    for n in remove:
        i = keep.infos[n]
        label = i.kind if i.stage == "mark" and i.kind else i.stage
        cnt, size = sizes[n]
        fz = f"frozen in history/{frozen[n][0]}/" if n in frozen else "not frozen: git is its only copy"
        lines.append(f"  {('r' + str(n)).ljust(5)}{label.ljust(11)} {cnt} files, {mb(size)}   {fz}")
    lines += ["", "files to remove (git blob, mode, path):"]
    lines += [f"  {blob} {mode} {json.dumps(p, ensure_ascii=False)}" for blob, mode, p in removal.files]
    lines += [f"not in git, deleted with the plan (it will not come back): {json.dumps(p, ensure_ascii=False)}" for p in removal.loose]
    lines += [f"not in git, deleted with its folder and not part of the code: {json.dumps(p, ensure_ascii=False)}" for p in removal.ds_store]
    lines.append(f"other staged changes in the repository: {others} (they will be in the same commit)")
    if reports:
        lines.append("reports of removed work (removed with the rounds, they are listed above, in the files to remove or as not in git): " + ", ".join(json.dumps(r, ensure_ascii=False) for r in reports))
    lines += ["", "To remove: the owner says yes to this plan, then", f"  brand-creator cleanup{''.join(f' --keep r{n}' for n in sorted(set(extra)))} --record-yes {digest[:12]} --said \"<their words>\"",
              f"  brand-creator cleanup{''.join(f' --keep r{n}' for n in sorted(set(extra)))} --yes {digest[:12]}"]
    return Plan("\n".join(lines) + "\n", digest, remove, kept, removal, reports, repo.head, date, sorted(set(extra)))


# ---------------------------------------------------------------- DECISIONS.md and the records in qa/

def decision_entries(project: Path) -> list[tuple[str, str]]:
    """(heading, hash) of each cleanup entry of DECISIONS.md, in order: a line `- Cleanup plan: sha256:<hex>` under a `## ` heading."""
    f = Path(project) / "DECISIONS.md"
    if not f.is_file():
        return []
    heading = None
    out = []
    for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.startswith("## "):
            heading = ln
        elif heading is not None and (m := ENTRY_RE.match(ln)):
            out.append((heading, m.group(1)))
    return out


def complete_records(project: Path, digest: str) -> list[str]:
    """The removed records in qa/ with status complete (or no status line) that name this plan, as project-relative paths."""
    out = []
    for f in sorted((Path(project) / "qa").glob("*-cleanup-removed*.txt")):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if f"plan: sha256:{digest}" not in text.splitlines():
            continue
        st = re.search(r"^status: (.*)$", text, re.M)
        if st is None or st.group(1).strip() == "complete":
            out.append(f"qa/{f.name}")
    return out


def shown_plan_has(project: Path, prefix: str) -> list[tuple[str, str]]:
    """(project-relative plan file, full plan hash) for each plan in qa/ whose hash starts with `prefix`."""
    out = []
    for f in sorted((Path(project) / "qa").glob("*-cleanup-plan*.txt")):
        try:
            for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"^plan: sha256:([0-9a-f]{64})\b", ln)
                if m and m.group(1).startswith(prefix):
                    out.append((f"qa/{f.name}", m.group(1)))
        except OSError:
            continue
    return out


def entry_text(plan: Plan, said: str, plan_file: str) -> str:
    names = ", ".join(f"r{n}" for n in plan.remove)
    return (f"## {plan.date}: clean old rounds (remove {names})\n\n"
            f"- Gate: none (cleanup of old rounds)\n"
            f"- Decided: remove the round folders {names} ({len(plan.removal.files)} files), committed in git at {plan.head[:10]}\n"
            f"- Why: {said}\n"
            f"- Rejected: keeping every round\n"
            f"- Consequences: the plan is {plan_file}; what was removed and how to restore it goes into qa/<date>-cleanup-removed.txt\n"
            f"- Cleanup plan: sha256:{plan.hash}\n")


def restore_line(repo: Repo, plan: Plan) -> str:
    targets = [f"rounds/r{n}" for n in plan.remove] + [shlex.quote(p) for p in plan.reports if p not in plan.removal.loose]
    return f"git -C {shlex.quote(str(repo.project))} --literal-pathspecs checkout {plan.head} -- {' '.join(targets)}"


def write_record(repo: Repo, plan: Plan, status: str, staged: int, heading: str, restore: str) -> Path:
    qa = confine(repo.project, "qa", what="qa folder")
    qa.mkdir(exist_ok=True)
    k, name = 1, f"{plan.date}-cleanup-removed.txt"
    while (qa / name).exists():
        k += 1
        name = f"{plan.date}-cleanup-removed-{k}.txt"
    lines = ["brand-creator cleanup: removed", f"date: {plan.date}", f"status: {status}", f"plan: sha256:{plan.hash}", f"head before: {plan.head}",
             f"yes: DECISIONS.md, \"{heading[3:] if heading.startswith('## ') else heading}\"" if heading else "yes: (not found)",
             "removed rounds: " + " ".join(f"r{n}" for n in plan.remove), f"removed files: {staged} (staged with git rm, not committed)"]
    lines += [f"deleted, not in git: {json.dumps(p, ensure_ascii=False)}" for p in plan.removal.loose + plan.removal.ds_store]
    lines += [f"restore: {restore}", ""]
    lines += [f"{blob} {mode} {json.dumps(p, ensure_ascii=False)}" for blob, mode, p in plan.removal.files]
    (qa / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return qa / name


# ---------------------------------------------------------------- removing

def record_files(text: str) -> set[str]:
    """The file paths a removed record lists (its `<blob> <mode> "<path>"` lines)."""
    return {json.loads(m.group(1)) for m in re.finditer(r'^[0-9a-f]+ \d+ ("(?:[^"\\]|\\.)*")$', text, re.M)}


def record_order(f: Path) -> tuple[str, int]:
    """Sort key of a removed record by when it was written: its date, then k (1 for `<date>-cleanup-removed.txt`, N for `-removed-N.txt`). Plain name order is wrong: `-removed-2` sorts before `-removed.`, and `-10` before `-2`."""
    m = re.match(r"^(.*?)-cleanup-removed(?:-(\d+))?\.txt$", f.name)
    return (m.group(1), int(m.group(2) or 1)) if m else (f.name, 0)


def check_no_failed_removal(repo: Repo) -> None:
    """Step 9b, part two: while the newest failed removal record's own deletions are still staged, refuse and print its restore line.
    Only staged deletions of files the record lists count, and a file that any complete record lists is no failure: that run proved the
    deletion was intended, whichever plan it was."""
    project = repo.project
    failed = None
    done: set[str] = set()
    for f in sorted((Path(project) / "qa").glob("*-cleanup-removed*.txt"), key=record_order):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        st = re.search(r"^status: (.*)$", text, re.M)
        if st is None or st.group(1).strip() == "complete":
            done |= record_files(text)
        elif st.group(1).strip().startswith("failed"):
            failed = (f, text)
    if failed is None:
        return
    listed = record_files(failed[1]) - done
    staged = [repo.local(e.path) for e in status_entries(project, "rounds", "history", untracked=False) if e.kind in "12" and e.xy == "D." and repo.local(e.path) in listed]
    if not staged:
        return
    f, text = failed
    lines = [json.dumps(p, ensure_ascii=False) for p in staged]
    raise CliError(EXIT_FAIL, shown(lines, f"refused: an earlier removal failed (qa/{f.name}) and {len(lines)} change(s) under rounds/ or history/ are still staged. Restore first with: "
                                           f"{restore_from_record(repo, text)}"))


def restore_from_record(repo: Repo, text: str) -> str:
    """The restore line of a removed record, rebuilt from its checked fields, never its `restore:` text: a record is a file anyone can edit,
    and the line is printed for someone (or an agent) to run. The commit is a hex id, rounds are rN, paths are quoted, the project is ours."""
    head = re.search(r"^head before: ([0-9a-f]{40,64})$", text, re.M)
    frozen = re.search(r"^removed from history: ((?:[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+)(?: [0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+)*)$", text, re.M)
    if head is not None and frozen is not None:
        targets = [f"history/{n}" for n in frozen.group(1).split()] + ["history/MANIFEST.sha256"]
        return f"git -C {shlex.quote(str(repo.project))} --literal-pathspecs checkout {head.group(1)} -- {' '.join(targets)}"
    rounds = re.search(r"^removed rounds: ((?:r\d+)(?: r\d+)*)$", text, re.M)
    if head is None or rounds is None:
        return "(the record's head or rounds line is damaged; find the commit before the removal with git log and check out rounds/ from it)"
    targets = rounds.group(1).split()
    targets = [f"rounds/{r}" for r in targets] + [shlex.quote(p) for p in sorted(record_files(text)) if not p.startswith("rounds/")]
    return f"git -C {shlex.quote(str(repo.project))} --literal-pathspecs checkout {head.group(1)} -- {' '.join(targets)}"


def chunks(paths: list[str]) -> list[list[str]]:
    out: list[list[str]] = []
    cur: list[str] = []
    size = 0
    for p in paths:
        b = len(p.encode("utf-8", "surrogateescape")) + 1
        if cur and (len(cur) >= CHUNK_FILES or size + b > CHUNK_BYTES):
            out.append(cur)
            cur, size = [], 0
        cur.append(p)
        size += b
    if cur:
        out.append(cur)
    return out


def remove_rounds(repo: Repo, plan: Plan, heading: str) -> None:
    project = repo.project
    restore = restore_line(repo, plan)
    before = {(e.xy, e.path) for e in status_entries(project, untracked=False)}
    history_before = verify_history(project)
    paths = [p for _b, _m, p in plan.removal.files]
    parts = chunks(paths)
    staged = 0
    for k, chunk in enumerate(parts, 1):
        cp = git(project, "rm", "-q", "--", *chunk)
        if cp.returncode != 0:
            msg = git_text(cp)
            rec = write_record(repo, plan, f"failed at chunk {k} of {len(parts)}: {clean(msg)[:300]}", staged, heading, restore)
            print(f"the removal stopped at chunk {k} of {len(parts)}: {msg}\nchunks done: {k - 1}; staged before it stopped: {staged} file(s)\nrecord: {rec.relative_to(project)}\nrestore with: {restore}")
            fail(EXIT_FAIL, f"git rm failed at chunk {k} of {len(parts)} ({msg}); the yes is not used up. Restore what was staged with the line above, then run --yes again")
        staged += len(chunk)
    gone = []
    for p in plan.removal.ds_store + plan.removal.loose:
        try:
            os.unlink(Path(project) / p)
            gone.append(p)
        except FileNotFoundError:
            pass
    left: list[str] = []
    for n in plan.remove:
        base = Path(project) / "rounds" / f"r{n}"
        for dirpath, _d, filenames in os.walk(base, topdown=False, followlinks=False):
            for name in filenames:
                if name == ".DS_Store" and not os.path.islink(Path(dirpath) / name):
                    os.unlink(Path(dirpath) / name)
        for dirpath, _d, _f in os.walk(base, topdown=False, followlinks=False):
            try:
                os.rmdir(dirpath)
            except OSError:
                pass
        if base.exists():
            left.append(f"rounds/r{n}")
    after = {(e.xy, e.path) for e in status_entries(project, untracked=False)}
    expected = {("D.", repo.prefix + p) for p in paths}
    diffs = []
    if left:
        diffs.append(f"{', '.join(left)} is still there")
    if after - before != expected:
        diffs.append(f"git shows {len(after - before - expected)} change(s) it should not and lacks {len(expected - (after - before))} staged deletion(s)")
    if before - after:
        diffs.append("a change that was staged before the run is gone")
    if verify_history(project) != history_before:
        diffs.append("history/ is not as it was")
    if diffs:
        what = "; ".join(diffs)
        rec = write_record(repo, plan, f"failed: post-conditions ({what})", staged, heading, restore)
        print(f"record: {rec.relative_to(project)}")
        fail(EXIT_FAIL, f"cleanup removed the files, but {what}: restore with {restore}")
    rec = write_record(repo, plan, "complete", staged, heading, restore)
    print(f"removed {len(plan.remove)} round(s) ({', '.join(f'r{n}' for n in plan.remove)}): {staged} file(s) with git rm, staged, not committed.")
    if gone:
        print(f"deleted, not in git: {len(gone)} file(s) (.DS_Store files and reports git did not know; they do not come back)")
    print(f"record: {rec.relative_to(project)}")
    print(f"restore (before or after you commit): {restore}")
    print(f"suggested commit message: brand: remove old rounds {', '.join(f'r{n}' for n in plan.remove)} (cleanup plan {plan.code})")
    print("nothing was committed. Next: brand-creator check --refresh (recording the yes touched DECISIONS.md, which a pages board's lint reads)")


# ---------------------------------------------------------------- the command

def parse(argv: list[str] | None):
    ap = Parser(prog="brand-creator cleanup", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--keep", action="append", default=[], metavar="rN", help="keep one more round (repeatable); part of the plan, so the same options go with all three runs")
    ap.add_argument("--record-yes", metavar="CODE", help="record the owner's yes to the plan with this code in DECISIONS.md (needs --said)")
    ap.add_argument("--said", help="the owner's words, one line (with --record-yes only)")
    ap.add_argument("--yes", metavar="CODE", help="remove the planned round folders (needs the yes recorded for this plan)")
    ap.add_argument("--history", action="store_true", help="slim the frozen rounds in history/ to what their boards show, instead of removing old rounds")
    ap.add_argument("--static", action="store_true", help="with --history: read what the boards show from the files only (no browser)")
    a = ap.parse_args(argv)
    if a.history and a.keep:
        ap.error("--history and --keep refuse each other: --keep names rounds to keep; --history slims history/ and removes no round")
    if a.static and not a.history:
        ap.error("--static goes with --history only")
    if a.yes is not None and a.record_yes is not None:
        ap.error("--yes and --record-yes are separate runs: record the owner's yes first, then run --yes")
    if a.said is not None and a.record_yes is None:
        ap.error("--said goes with --record-yes")
    if a.record_yes is not None and a.said is None:
        ap.error("--record-yes needs --said \"<the owner's words>\"")
    for code, flag in ((a.yes, "--yes"), (a.record_yes, "--record-yes")):
        if code is not None and not HEX.fullmatch(code.lower()):
            ap.error(f"{flag} takes the plan code the dry run prints: 12 to 64 hex digits, got {code!r}")
    if a.said is not None:
        if any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") for c in a.said):
            ap.error("--said must be one line of the owner's words: a newline or another control character is not allowed")
        a.said = re.sub(r" +", " ", a.said).strip()
        if not a.said:
            ap.error("--said must be one line of the owner's words, not empty")
    keeps = []
    for k in a.keep:
        if not rd.ASCII_ROUND.fullmatch(k):
            ap.error(f"--keep {k}: use r<N> (r3), with ASCII digits and no leading zero")
        keeps.append(int(k[1:]))
    a.keeps = sorted(set(keeps))
    return a


def show_keep(keep: rd.Keep) -> None:
    for n in sorted(keep.reasons):
        i = keep.infos[n]
        print(f"  {('r' + str(n)).ljust(5)}{(i.kind if i.stage == 'mark' and i.kind else i.stage).ljust(11)} {reasons_text(keep.reasons[n])}")


def main(argv: list[str] | None = None) -> int:
    a = parse(argv)
    project = find_project(a.project)
    if a.history:
        return history_main(project, a)
    all_rounds = list_rounds(project)
    for n in a.keeps:
        if n not in {m for m, _ in all_rounds}:
            fail(EXIT_USAGE, f"--keep r{n}: there is no rounds/r{n}/")
    repo = open_repo(project)
    check_layout(project)
    check_no_failed_removal(repo)
    keep = rd.compute_keep(project, all_rounds, a.keeps)
    reset_rounds, g1s = rd.reset_and_g1s(project)
    problems = rd.lint_context_problems(project, all_rounds, set(keep.reasons), reset_rounds, g1s)
    if problems:
        fail(EXIT_FAIL, problems[0] + (f" (and {len(problems) - 1} more such questions)" if len(problems) > 1 else ""))
    cands = [n for n, _ in all_rounds if n not in keep.reasons]
    if not cands:
        if a.record_yes is not None or a.yes is not None:
            fail(EXIT_FAIL, f"the plan changed since {'it was shown' if a.record_yes is not None else 'the owner said yes'} (now: nothing to remove, every round is kept): show the owner a new plan "
                            "and ask again. Nothing was recorded or removed")
        print(f"nothing to clean: every round is kept ({len(keep.reasons)} round(s)):")
        show_keep(keep)
        return 0
    check_links(project, cands, keep.removable_reports)
    removal = check_git_state(repo, cands, keep.removable_reports)
    plan = build_plan(repo, all_rounds, keep, a.keeps, removal, keep.removable_reports)
    if a.record_yes is None and a.yes is None:
        print(plan.text, end="")
        qa = confine(project, "qa", what="qa folder")
        qa.mkdir(exist_ok=True)
        path = confine(project, f"qa/{plan.date}-cleanup-plan.txt", what="plan file")
        write_bytes_if_changed(path, plan.text.encode("utf-8", "surrogateescape"))
        print(f"plan file: qa/{plan.date}-cleanup-plan.txt")
        return 0
    if a.record_yes is not None:
        return record_yes(project, plan, a.record_yes.lower(), a.said)
    return do_yes(repo, plan, a.yes.lower(), all_rounds, keep, a)


def record_yes(project: Path, plan, code: str, said: str, entry_fn=None) -> int:
    shown_in = [f for f, _h in shown_plan_has(project, code)]
    if not shown_in:
        fail(EXIT_FAIL, f"no plan with code {code} was shown: run brand-creator cleanup first and show the owner the plan")
    if not plan.hash.startswith(code):
        fail(EXIT_FAIL, f"the plan changed since it was shown (now {plan.code}): show the owner the new plan and ask again")
    decisions = Path(project) / "DECISIONS.md"
    if not decisions.is_file():
        fail(EXIT_FAIL, "DECISIONS.md not found: the owner's yes is recorded there (templates/DECISIONS.md)")
    entry = (entry_fn or entry_text)(plan, said, next((f for f, h in shown_plan_has(project, code) if h == plan.hash), shown_in[0]))
    found = rd.refs_in_text(entry, "DECISIONS.md", suffix=".md")
    if found:
        fail(EXIT_FAIL, f"the owner's words name {found[0].shown}; DECISIONS.md is read for references, so this entry would keep r{found[0].rnd} and change the plan. "
                        "Record the words without the path (a round named as \"r2\" is fine)")
    entries = [(h, x) for h, x in decision_entries(project) if x == plan.hash]
    used = complete_records(project, plan.hash)
    if len(entries) > len(used):
        print(f"the owner's yes to plan {plan.code} is recorded already ({entries[len(used)][0][3:]}); nothing written")
        return 0
    with open(decisions, "r", encoding="utf-8", errors="surrogateescape", newline="") as fh:
        old = fh.read()
    nl = "\r\n" if "\r\n" in old else "\n"
    sep = "" if not old else (nl if old.endswith(nl * 2) else nl * 2)
    if nl != "\n":
        entry = entry.replace("\n", nl)
    with open(confine(project, "DECISIONS.md", what="DECISIONS.md"), "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
        fh.write(old + sep + entry)
    print(f"recorded the owner's yes to plan {plan.code} in DECISIONS.md. A pages-board lint lists DECISIONS.md, so run brand-creator check --refresh after the removal")
    return 0


def do_yes(repo: Repo, plan: Plan, code: str, all_rounds, keep: rd.Keep, a) -> int:
    project = repo.project
    if not plan.hash.startswith(code):
        fail(EXIT_FAIL, f"the plan changed since the owner said yes (now {plan.code}): show the owner the new plan and ask again")
    entries = [h for h, x in decision_entries(project) if x == plan.hash]
    if not entries:
        fail(EXIT_FAIL, f"the owner's yes to plan {plan.code} is not recorded: show the plan, ask, then brand-creator cleanup --record-yes {plan.code} --said \"<their words>\"")
    used = complete_records(project, plan.hash)
    if len(entries) <= len(used):
        fail(EXIT_FAIL, f"the yes to plan {plan.code} was used on {used[-1][3:13]} ({used[-1]}): a new removal needs a new plan, or a new yes (--record-yes records one more)")
    cands = plan.remove
    check_links(project, cands, plan.reports)
    again = check_git_state(repo, cands, plan.reports)
    if again.files != plan.removal.files or again.loose != plan.removal.loose:
        fail(EXIT_FAIL, "the plan changed while cleanup ran: run the dry run again and show the owner the new plan")
    plan = plan._replace(removal=again)
    remove_rounds(repo, plan, entries[len(used)])
    return 0


# ---------------------------------------------------------------- --history: frozen rounds slimmed to what their boards show

class HPlan(NamedTuple):
    text: str
    hash: str
    date: str
    head: str
    freezes: list[str]                      # the frozen rounds that lose files, by folder name
    files: list[tuple[str, str, str]]       # (blob, mode, path) of what git rm takes, sorted by path bytes

    @property
    def code(self) -> str:
        return self.hash[:12]


FREEZE_NAME = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9][a-z0-9-]{0,62}$")   # what freeze names a folder (date and --name): nothing a shell reads specially


def freeze_dirs(project: Path) -> list[Path]:
    """The frozen rounds in history/. A folder freeze did not name is refused, naming it: its name would go into the restore line."""
    h = Path(project) / "history"
    if not h.is_dir():
        return []
    dirs = sorted(d for d in h.iterdir() if d.is_dir() and not d.name.startswith("."))
    odd = [json.dumps(f"history/{d.name}", ensure_ascii=False) for d in dirs if not FREEZE_NAME.fullmatch(d.name)]
    if odd:
        raise CliError(EXIT_FAIL, shown(odd, f"refused: {len(odd)} folder(s) in history/ are not a frozen round freeze made (named <date>-<name>, lowercase letters, "
                                             "digits and hyphens); cleanup --history slims only those:"))
    return dirs


def history_keep(d: Path, static: bool) -> set[Path]:
    """What a frozen round keeps: the closure freeze computes, read on the frozen copy (its banner comments are only comments)."""
    starts = closure.starting_pages(d)
    kept, _ = closure.static_closure(d, starts)
    if not static:
        try:
            seen, _ = closure.browser_closure(d, starts)
        except CliError as e:
            if e.code != EXIT_CANNOT:
                raise
            fail(EXIT_CANNOT, f"{e.message}. cleanup --history reads what each frozen board shows in the browser; without one, run it with --static "
                              "(the references in the files only: a path a script builds is not seen)")
        kept |= seen
    return {p.resolve() for p in kept | closure.builders(d) | closure.records(d) | set(starts)}


def history_git_files(repo: Repo, paths: list[str]) -> list[tuple[str, str, str]]:
    """(blob, mode, path) for each path, all committed and unchanged; otherwise refuse, naming them (they could not be restored)."""
    project = repo.project
    tracked: dict[str, tuple[str, str]] = {}
    for part in chunks(paths):
        ls = git(project, "ls-files", "-v", "-s", "-z", "--", *part)
        if ls.returncode != 0:
            fail(EXIT_FAIL, f"git ls-files failed: {git_text(ls)}")
        for tok in ls.stdout.split(b"\0"):
            if tok:
                m = re.match(r"^(\S) (\d+) ([0-9a-f]+) (\d)\t(.*)$", os.fsdecode(tok), re.S)
                if m and m.group(1) == "H":
                    tracked[unicodedata.normalize("NFC", repo.local(m.group(5)))] = (m.group(2), m.group(3))
    changed = {unicodedata.normalize("NFC", repo.local(e.path)) for e in status_entries(project, "history", untracked=False)}
    problems = [f"not known to git: {json.dumps(p, ensure_ascii=False)}" for p in paths if p not in tracked]
    problems += [f"changed since the last commit: {json.dumps(p, ensure_ascii=False)}" for p in paths if p in changed]
    if problems:
        raise CliError(EXIT_FAIL, shown(problems, f"refused: {len(problems)} file(s) of history/ to remove are not committed as they are, so they could not be restored:"))
    return sorted(((tracked[p][1], tracked[p][0], p) for p in paths), key=lambda x: x[2].encode("utf-8", "surrogateescape"))


def build_history_plan(repo: Repo, static: bool) -> "HPlan | None":
    project = repo.project
    problems = verify_history(project)
    if problems:
        raise CliError(EXIT_FAIL, shown(problems, "refused: history/ does not match history/MANIFEST.sha256, so cleanup cannot tell what was frozen; resolve it "
                                                  "(brand-creator check names it) and run again:"))
    date, slug = today(), display_slug(project)
    rows, goes = [], []
    for d in freeze_dirs(project):
        keep = history_keep(d, static)
        files = [p for p in sorted(d.rglob("*")) if p.is_file()]
        gone = [p for p in files if p.resolve() not in keep]
        if not gone:
            continue
        stay = [p for p in files if p.resolve() in keep]
        rows.append(f"  {d.name}: stays {len(stay)} files, {mb(sum(p.stat().st_size for p in stay))}; goes {len(gone)} files, "
                    f"{mb(sum(p.stat().st_size for p in gone))}")
        goes += [unicodedata.normalize("NFC", p.relative_to(project).as_posix()) for p in gone]
    if not goes:
        return None
    files = history_git_files(repo, goes)
    freezes = sorted({p.split("/")[1] for _b, _m, p in files})
    canon = ["brand-creator cleanup history plan v1", slug, f"mode {'static' if static else 'browser'}"] + [f"file {b} {m} {json.dumps(p, ensure_ascii=False)}" for b, m, p in files]
    digest = hashlib.sha256(("\n".join(canon) + "\n").encode("utf-8", "surrogateescape")).hexdigest()
    flag = " --static" if static else ""
    lines = ["brand-creator cleanup plan (history)", f"project: {slug}", f"date: {date}", f"head: {repo.head} (removed files are restored from it)",
             f"plan: sha256:{digest}   code: {digest[:12]}", "", "frozen rounds slimmed to what their boards show:"] + rows
    lines += ["", "files to remove (git blob, mode, path):"] + [f"  {b} {m} {json.dumps(p, ensure_ascii=False)}" for b, m, p in files]
    lines += ["", "history/MANIFEST.sha256 is rewritten without them, and staged.", "",
              "To remove: the owner says yes to this plan, then", f"  brand-creator cleanup --history{flag} --record-yes {digest[:12]} --said \"<their words>\"",
              f"  brand-creator cleanup --history{flag} --yes {digest[:12]}"]
    return HPlan("\n".join(lines) + "\n", digest, date, repo.head, freezes, files)


def history_entry_text(plan: HPlan, said: str, plan_file: str) -> str:
    names = ", ".join(plan.freezes)
    return (f"## {plan.date}: slim frozen rounds to what their boards show ({names})\n\n"
            f"- Gate: none (cleanup of history/)\n"
            f"- Decided: remove {len(plan.files)} files that no board of {names} shows, committed in git at {plan.head[:10]}; history/MANIFEST.sha256 rewritten\n"
            f"- Why: {said}\n"
            f"- Rejected: keeping whole frozen rounds\n"
            f"- Consequences: the plan is {plan_file}; what was removed and how to restore it goes into qa/<date>-cleanup-removed-history.txt\n"
            f"- Cleanup plan: sha256:{plan.hash}\n")


def write_history_record(repo: Repo, plan: HPlan, status: str, staged: int, heading: str, restore: str) -> Path:
    qa = confine(repo.project, "qa", what="qa folder")
    qa.mkdir(exist_ok=True)
    k, name = 1, f"{plan.date}-cleanup-removed-history.txt"
    while (qa / name).exists():
        k += 1
        name = f"{plan.date}-cleanup-removed-history-{k}.txt"
    lines = ["brand-creator cleanup: removed (history)", f"date: {plan.date}", f"status: {status}", f"plan: sha256:{plan.hash}", f"head before: {plan.head}",
             f"yes: DECISIONS.md, \"{heading[3:] if heading.startswith('## ') else heading}\"",
             "removed from history: " + " ".join(plan.freezes), f"removed files: {staged} (staged with git rm, not committed)", f"restore: {restore}", ""]
    lines += [f"{b} {m} {json.dumps(p, ensure_ascii=False)}" for b, m, p in plan.files]
    (qa / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return qa / name


def history_main(project: Path, a) -> int:
    repo = open_repo(project)
    check_no_failed_removal(repo)
    plan = build_history_plan(repo, a.static)
    if plan is None:
        if a.record_yes is not None or a.yes is not None:
            fail(EXIT_FAIL, "the plan changed (now: nothing to slim, every frozen round holds only what its boards show): nothing was recorded or removed")
        print("nothing to slim in history/: every frozen round holds only what its boards show, its scripts and its records")
        return 0
    if a.record_yes is None and a.yes is None:
        print(plan.text, end="")
        qa = confine(project, "qa", what="qa folder")
        qa.mkdir(exist_ok=True)
        write_bytes_if_changed(confine(project, f"qa/{plan.date}-cleanup-plan-history.txt", what="plan file"), plan.text.encode("utf-8", "surrogateescape"))
        print(f"plan file: qa/{plan.date}-cleanup-plan-history.txt")
        return 0
    if a.record_yes is not None:
        return record_yes(project, plan, a.record_yes.lower(), a.said, history_entry_text)
    code = a.yes.lower()
    if not plan.hash.startswith(code):
        fail(EXIT_FAIL, f"the plan changed since the owner said yes (now {plan.code}): show the owner the new plan and ask again")
    entries = [h for h, x in decision_entries(project) if x == plan.hash]
    if not entries:
        fail(EXIT_FAIL, f"the owner's yes to plan {plan.code} is not recorded: show the plan, ask, then brand-creator cleanup --history --record-yes {plan.code} --said \"<their words>\"")
    used = complete_records(project, plan.hash)
    if len(entries) <= len(used):
        fail(EXIT_FAIL, f"the yes to plan {plan.code} was used ({used[-1]}): a new removal needs a new plan, or a new yes")
    heading = entries[len(used)]
    targets = [shlex.quote(f"history/{n}") for n in plan.freezes] + ["history/MANIFEST.sha256"]   # names checked by freeze_dirs; quoted all the same
    restore = f"git -C {shlex.quote(str(project))} --literal-pathspecs checkout {plan.head} -- {' '.join(targets)}"
    paths = [p for _b, _m, p in plan.files]
    staged = 0
    for k, part in enumerate(chunks(paths), 1):
        cp = git(project, "rm", "-q", "--", *part)
        if cp.returncode != 0:
            rec = write_history_record(repo, plan, f"failed at chunk {k}: {clean(git_text(cp))[:300]}", staged, heading, restore)
            fail(EXIT_FAIL, f"git rm failed at chunk {k} ({git_text(cp)}); record {rec.relative_to(project)}; restore what was staged with: {restore}")
        staged += len(part)
    history = Path(project) / "history"
    entries_now = read_history_manifest(history)
    for p in paths:
        entries_now.pop(p[len("history/"):], None)
    write_history_manifest(history, entries_now)
    for n in plan.freezes:   # folders emptied by git rm
        for dirpath, _d, _f in os.walk(history / n, topdown=False):
            try:
                os.rmdir(dirpath)
            except OSError:
                pass
    cp = git(project, "add", "--", "history/MANIFEST.sha256")
    problems = verify_history(project)
    if cp.returncode != 0 or problems:
        why = git_text(cp) if cp.returncode != 0 else "; ".join(problems[:3])
        rec = write_history_record(repo, plan, f"failed: post-conditions ({clean(why)[:300]})", staged, heading, restore)
        fail(EXIT_FAIL, f"cleanup removed the files, but {why}; record {rec.relative_to(project)}; restore with: {restore}")
    rec = write_history_record(repo, plan, "complete", staged, heading, restore)
    print(f"slimmed {len(plan.freezes)} frozen round(s) ({', '.join(plan.freezes)}): {staged} file(s) removed with git rm and history/MANIFEST.sha256 rewritten, staged, not committed.")
    print(f"record: {rec.relative_to(project)}")
    print(f"restore (before or after you commit): {restore}")
    print(f"suggested commit message: brand: slim frozen rounds to what their boards show (cleanup plan {plan.code})")
    return 0


def run_cli(argv: list[str] | None = None) -> int:
    """main() with its errors printed and turned into the exit code (for a test that calls it in the same process)."""
    try:
        return main(argv)
    except CliError as e:
        print(f"error: {e.message}", file=sys.stderr)
        return e.code
    except SystemExit as e:
        return int(e.code or 0)


if __name__ == "__main__":
    main_guard(main)

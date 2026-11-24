#!/usr/bin/env python3
"""Keep private terms out of a push: the scan of whoever holds private brand projects, run on their own machine before git sends anything.

It is not a test of the plugin and no part of its suite, its CI or its release run: someone who has never seen a private brand cannot write its
name into the repository, so only a machine that holds such projects needs the scan, and that machine has the terms already. Standard library only.

    private_terms.py install-hook <sources>          write the pre-push hook of this clone: every push from it is scanned first
    private_terms.py <sources> --push <remote>       what the hook runs: git's "<local ref> <local sha> <remote ref> <remote sha>" lines on stdin
    private_terms.py <sources> --range <revisions>   scan what those commits add, for example origin/main..HEAD
    private_terms.py <sources> --files               scan every tracked file as it is now

    sources, at least one:
      --projects DIR   every brand project in DIR or one folder below it (a folder with BRAND-STATE.md): its name and its slug
      --public SLUG    a brand project that is public, left out of --projects (the marketplace's own brand)
      --list FILE      more terms, as JSON: {"terms": [...], "hex": ["#aabbcc"], "allow": ["a phrase that holds a term and is fine"]}

A push is scanned by what it adds: every added line, every added or renamed path and every commit message of the commits the remote does not
have yet. A term added in one commit and removed in the next is still found, because both commits become public.
Exit 0: nothing found. Exit 1: found, each hit on a line of its own. Exit 2: cannot scan (no source, nothing to look for, git said no)."""
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

MARK = "# written by private_terms.py install-hook"
ZERO = re.compile(r"0+")
HUNK = re.compile(r"@@ -\S+ \+(\d+)")


class CannotScan(Exception):
    pass


def fold(s: str) -> str:
    """Lower case, no accents, plain quotes and dashes, one space: a term is found however it is spelt."""
    s = unicodedata.normalize("NFKD", s).lower().replace("ł", "l")
    for a, b in (("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'), ("–", "-"), ("—", "-"), ("‑", "-")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c)))


def hexes(text: str):
    """Every colour in the text as #rrggbb: #rgb, #rrggbb, with alpha, URL-encoded (%23), or rgb()."""
    for m in re.finditer(r"(?:#|%23)([0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{4}|[0-9a-f]{3})(?![0-9a-z])", text, re.I):
        h = m.group(1).lower()
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h[:3])
        yield "#" + h[:6]
    for m in re.finditer(r"rgba?\(\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})", text, re.I):
        yield "#%02x%02x%02x" % tuple(min(255, int(x)) for x in m.groups())


class Terms:
    def __init__(self, terms=(), hex=(), allow=()):
        self.terms = sorted({fold(t) for t in terms if t.strip()})
        self.hex = {h.lower() for h in hex}
        self.allow = [fold(a) for a in allow]

    def __bool__(self) -> bool:
        return bool(self.terms or self.hex)

    def in_line(self, line: str) -> list[str]:
        """What a line of text holds: each term outside an allowed phrase, and each listed colour."""
        f = fold(line)
        found = []
        for t in self.terms:
            i = f.find(t)
            while i >= 0:
                if not any(t in a and f.find(a) <= i < f.find(a) + len(a) for a in self.allow if a in f):
                    found.append(repr(t))
                    break
                i = f.find(t, i + 1)
        return found + [f"the colour {h}" for h in hexes(line) if h in self.hex]

    def in_path(self, path: str) -> list[str]:
        f = fold(path)
        return [repr(t) for t in self.terms if t in f]


def scan_files(terms: Terms, files, root: Path) -> list[str]:
    """Every hit in `files` as they are on disk, `<path>[:<line>]: <what>`; a file that is not text is scanned by its path only."""
    hits = []
    for p in files:
        rel = p.relative_to(root).as_posix()
        hits += [f"{rel}: the path holds {t}" for t in terms.in_path(rel)]
        try:
            text = p.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            hits += [f"{rel}:{n}: {t}" for t in terms.in_line(line)]
    return hits


def project_terms(folder: Path, public: set[str]) -> tuple[list[str], set[str]]:
    """The name and the slug of every brand project in `folder` or one folder below it, the public ones left out; and every slug seen."""
    if not folder.is_dir():
        raise CannotScan(f"--projects {folder}: no such folder")
    states = sorted({*folder.glob("BRAND-STATE.md"), *folder.glob("*/BRAND-STATE.md")})
    if not states:
        raise CannotScan(f"--projects {folder}: no brand project there (no BRAND-STATE.md in it or one folder below)")
    out, seen = [], set()
    for state in states:
        head = state.read_text(encoding="utf-8").split("\n---", 1)[0]
        got = {k: v.strip().strip("\"'") for k, v in re.findall(r"^(name|slug):[ \t]*(.+)$", head, re.M)}
        if not got.get("slug"):
            raise CannotScan(f"{state}: no slug in its frontmatter, so its terms cannot be told")
        seen.add(got["slug"])
        if got["slug"] not in public:
            out += [got["slug"], *([got["name"]] if got.get("name") else [])]
    return out, seen


def load(projects: list[str], public: list[str], lists: list[str]) -> Terms:
    if not projects and not lists:
        raise CannotScan("no source: give --projects DIR or --list FILE (a scan with nothing to look for finds nothing and proves nothing)")
    if public and not projects:
        raise CannotScan("--public needs --projects")
    terms, hex_, allow, seen = [], [], [], set()
    for folder in projects:
        found, slugs = project_terms(Path(folder).expanduser(), set(public))
        terms += found
        seen |= slugs
    unknown = sorted(set(public) - seen)
    if unknown:      # a slug that names no project would leave nothing out: say so, or a typing mistake goes unseen
        raise CannotScan(f"--public {', '.join(unknown)}: no brand project with that slug in {', '.join(projects)}")
    for f in lists:
        try:
            doc = json.loads(Path(f).expanduser().read_text(encoding="utf-8"))
            if not isinstance(doc, dict) or not all(isinstance(doc.get(k, []), list) for k in ("terms", "hex", "allow")):
                raise ValueError("it must be an object whose terms, hex and allow are lists")
        except (OSError, ValueError) as e:
            raise CannotScan(f"--list {f}: {e}") from e
        terms += doc.get("terms", [])
        hex_ += doc.get("hex", [])
        allow += doc.get("allow", [])
    out = Terms(terms, hex_, allow)
    if not out:
        raise CannotScan("the sources hold no term and no colour: nothing to look for")
    return out


def git(*args: str, cwd: Path) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    if r.returncode:
        raise CannotScan(f"git {' '.join(args[:3])} ...: {r.stderr.decode('utf-8', 'replace').strip() or r.returncode}")
    return r.stdout.decode("utf-8", "replace")


def scan_commits(terms: Terms, revisions: list[str], repo: Path) -> list[str]:
    """Every hit in what the commits `revisions` name add: `<commit> <path>:<line>: <what>` for an added line, and the same for a path and a message."""
    hits = []
    for block in git("log", "--format=%x01%h%x02%B%x03", *revisions, "--", cwd=repo).split("\x01")[1:]:
        commit, message = block.split("\x02", 1)
        for line in message.split("\x03", 1)[0].splitlines():
            hits += [f"{commit} its message: {t}" for t in terms.in_line(line)]
    commit = path = ""
    n, header = 0, False      # header: between a file's "diff --git" line and its first hunk, where "+++ " names the file and is no added line
    log = git("-c", "core.quotepath=false", "log", "-p", "-U0", "--no-color", "--no-ext-diff", "--no-textconv", "-M", "--format=%x01%h", *revisions, "--", cwd=repo)
    for line in log.split("\n"):
        if line.startswith("\x01"):
            commit, path, header = line[1:], "", False
        elif line.startswith("diff --git "):
            path, header = "", True
        elif header and line.startswith("+++ "):
            path = "" if line[4:] == "/dev/null" else line[4:].rstrip("\t").strip('"').removeprefix("b/")
            hits += [f"{commit} {path}: the path holds {t}" for t in terms.in_path(path)]
        elif header and line.startswith("rename to "):
            hits += [f"{commit} {line[10:]}: the path holds {t}" for t in terms.in_path(line[10:])]
        elif line.startswith("@@") and path:
            m = HUNK.match(line)
            n, header = (int(m.group(1)) if m else 0), False
        elif line.startswith("+") and path:
            hits += [f"{commit} {path}:{n}: {t}" for t in terms.in_line(line[1:])]
            n += 1
    return list(dict.fromkeys(hits))


def pushed(remote: str, lines: list[str]) -> list[list[str]]:
    """The revisions each line of a pre-push hook's input adds to the remote: what it has not got yet."""
    out = []
    for ln in lines:
        parts = ln.split()
        if len(parts) != 4:
            raise CannotScan(f"--push: {ln!r} is not a line git gives a pre-push hook")
        _, local, _, there = parts
        if ZERO.fullmatch(local):      # a ref is deleted: nothing is added
            continue
        out.append([local, "--not", f"--remotes={remote}"] if ZERO.fullmatch(there) else [f"{there}..{local}"])
    return out


def install_hook(repo: Path, sources: list[str]) -> Path:
    """Write the clone's pre-push hook and a copy of this file beside it, so a branch without this file is scanned too."""
    hooks = Path(git("rev-parse", "--path-format=absolute", "--git-path", "hooks", cwd=repo).strip())
    hook = hooks / "pre-push"
    if hook.exists() and MARK not in hook.read_text(encoding="utf-8", errors="replace"):
        raise CannotScan(f"{hook} exists and was not written by this tool: move it away or add the scan to it by hand")
    hooks.mkdir(parents=True, exist_ok=True)
    tool = hooks / "private_terms.py"
    shutil.copyfile(Path(__file__).resolve(), tool)
    hook.write_text(f"#!/bin/sh\n{MARK}: no push leaves this clone with a private term in it.\n"
                    f"# To change what it looks for, run install-hook again; to see the hits of a push by hand, run the line below with --range.\n"
                    f"exec python3 {shlex.quote(str(tool))} {' '.join(shlex.quote(s) for s in sources)} --push \"$1\"\n", encoding="utf-8")
    hook.chmod(0o755)
    return hook


def main(argv: list[str]) -> int:
    install = argv[:1] == ["install-hook"]
    args = argv[1:] if install else argv
    projects, public, lists, sources, mode = [], [], [], [], None
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--projects", "--public", "--list", "--push", "--range") and i + 1 < len(args):
            value = args[i + 1]
            if a in ("--projects", "--list"):
                value = str(Path(value).expanduser().resolve())
            if a in ("--push", "--range"):
                if mode:
                    raise CannotScan(__doc__)
                mode = (a, value)
            else:
                {"--projects": projects, "--public": public, "--list": lists}[a].append(value)
                sources += [a, value]
            i += 2
        elif a == "--files" and not mode:
            mode = (a, "")
            i += 1
        else:
            raise CannotScan(__doc__)
    if install == bool(mode):      # install-hook takes sources only; a scan takes exactly one of --push, --range, --files
        raise CannotScan(__doc__)
    terms = load(projects, public, lists)
    repo = Path(git("rev-parse", "--show-toplevel", cwd=Path.cwd()).strip())
    if install:
        hook = install_hook(repo, sources)
        print(f"private_terms: wrote {hook}: every push from this clone is scanned for {len(terms.terms)} term(s) and {len(terms.hex)} colour(s)")
        return 0
    assert mode is not None
    if mode[0] == "--files":
        hits = scan_files(terms, [repo / f for f in git("ls-files", "-z", cwd=repo).split("\0") if f and (repo / f).is_file()], repo)
    else:
        ranges = pushed(mode[1], sys.stdin.read().splitlines()) if mode[0] == "--push" else [mode[1].split()]
        hits = [h for r in ranges for h in scan_commits(terms, r, repo)]
    for h in hits:
        print(h, file=sys.stderr)
    if hits:
        print(f"private_terms: {len(hits)} private term(s) in what would become public: nothing was sent. Take them out of the commits "
              "(a new commit does not undo an old one: rewrite the commits that are not pushed yet), then push again.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except CannotScan as e:
        print(f"private_terms: cannot scan: {e}", file=sys.stderr)
        sys.exit(2)

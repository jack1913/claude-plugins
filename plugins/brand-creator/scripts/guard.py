#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator PreToolUse guard (hooks/hooks.json: Write|Edit|MultiEdit|NotebookEdit|Bash).

Protects finished work inside a brand project, and nothing else:

  * NO-OP unless the target path has an ancestor folder containing BRAND-STATE.md. Unrelated sessions, repos and
    unrelated history/ or rounds/ folders are never touched.
  * <project>/history/  : frozen. Blocks Edit, Write (overwrite or new file), and Bash deletes, moves, `sed -i`,
    redirects (> >>), tee, truncate, dd of=, cp/install/ln/rsync into it. New files appear only through
    `brand-creator freeze`, which is always allowed.
  * <project>/rounds/rN/ : every round except the latest (highest N) is read-only: Edit, Write and Bash writes are
    blocked (GAP S2-P5-t4). The latest round, and a new round with a higher N, stay writable. One exception:
    rounds/r0/ (the style board) stays writable while `gates.G1s` in BRAND-STATE.md is empty or missing, so a project
    that is already past round 1 can still run its style research as round 0; once G1s is recorded it is read-only like
    any earlier round. The exception needs a `gates:` block map the guard fully understands (see gate_is_empty); a state
    it cannot read, or can read two ways, gives no exception. scripts/patch.py asks the same question through round_is_open.
    Deletes anywhere under rounds/ are blocked (move to removed-<date>/ instead, which is allowed from the latest
    round). BRAND_CREATOR_GUARD_STRICT=1 applies the literal plan reading: Bash redirects, sed -i, tee, cp and mv
    into ANY round are blocked too (use the Write tool for the latest round).
  * A project folder that holds rounds/ or history/ cannot be deleted or moved, and neither can a folder that
    contains one (checked with a shallow glob: */BRAND-STATE.md and */*/BRAND-STATE.md), so `rm -rf <project>` and
    `rm -rf ~/brands` are caught, not only deletes inside history/.
  * `git mv`, `git stash -u|-a|--include-untracked|--all`, `tar -x`, `unzip`, `7z x` and `ditto` into or out of those zones are
    blocked like deletes and writes (the latest round stays writable).
  * `bash -c`, `sh -c`, `zsh -c` and `eval` strings are tokenised again and checked like any command. `xargs` with a
    deleter or `mv`, and `git clean`, `git restore`, `git reset --hard`, `git checkout -- <path>|.`, `git rm` are
    checked against the folder they run in (or their path arguments) as deletes, because rounds are not committed.

This is best-effort: an interpreter one-liner can still write a file. The real gate is history/MANIFEST.sha256,
verified by `brand-creator check`.

Failure policy: the only fail-open case is input this script cannot parse (not JSON, or a shell command it cannot
tokenise). It then prints a warning to stderr and allows the call, because a broken guard must not brick unrelated
sessions. Any other crash is left visible (non-zero exit that is not 2 is a non-blocking error in Claude Code).

Blocking = exit code 2 with the reason on stderr (Claude Code feeds it back to the model).
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

STATE_FILE = "BRAND-STATE.md"
FILE_TOOLS = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
DELETERS = {"rm", "rmdir", "unlink", "shred", "srm", "trash", "trash-put"}
COPIERS = {"cp", "install", "ln", "rsync", "scp"}
WRAPPERS = {"sudo", "command", "builtin", "exec", "nohup", "time", "nice", "env", "stdbuf", "doas"}
ARCHIVERS = {"tar", "gtar", "bsdtar", "unzip", "7z", "7za", "7zr", "ditto"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
MAX_NESTING = 3
ROUND_RE = re.compile(r"^r(\d+)$")


class Unparseable(Exception):
    pass


def strict() -> bool:
    return os.environ.get("BRAND_CREATOR_GUARD_STRICT") == "1"


# ------------------------------------------------------------------ paths and zones

def lenient_real(p: Path) -> Path:
    p = Path(os.path.abspath(p))
    tail: list[str] = []
    while not p.exists() and p != p.parent:
        tail.append(p.name)
        p = p.parent
    return Path(os.path.realpath(p)).joinpath(*reversed(tail))


def project_root(p: Path) -> Path | None:
    cur = p if p.is_dir() else p.parent
    for d in [cur, *cur.parents]:
        if (d / STATE_FILE).is_file():
            return d
    return None


def _strip_comment(raw: str) -> str:
    """A frontmatter value without its trailing comment, quotes kept: '"" # note' -> '""'."""
    quote, cut = "", len(raw)
    for i, ch in enumerate(raw):
        if quote:
            if ch == quote and raw[i - 1] != "\\":
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or raw[i - 1] in " \t"):
            cut = i
            break
    return raw[:cut].strip()


def _gate_value(raw: str) -> str:
    """The text of a frontmatter value with its trailing comment and quotes removed: '"" # note' -> '', '"2026-10-17 x"' -> '2026-10-17 x'."""
    value = _strip_comment(raw)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value


# One `key: value` line as the state reader (scripts/lib/_common.py) takes it: indent of spaces only, an unquoted key.
_STATE_LINE = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z0-9_.-]+):(?:\s+(?P<rest>.*))?$")


def gate_is_empty(root: Path, gate: str) -> bool:
    """True when BRAND-STATE.md can be read and its `gates:` block map holds no text for `gate` (a missing key counts as empty: the
    project is older than the gate). Fails closed: anything the guard does not fully understand is False, so the guard falls back to
    its normal rule and a state it cannot read never opens a door. That is: no file, not text, no frontmatter, frontmatter never
    closed; a frontmatter line the state reader would reject (a tab in the indent, a quoted key, text without a key, an indented line
    under a key that has a plain value or before the first key); no `gates:` key, or two; `gates:` with a value on its line (a flow
    map such as `{G1s: ""}`, even `{}`, or any text) instead of a block of indented `KEY: value` lines; the same key twice inside
    the block."""
    try:
        lines = (root / STATE_FILE).read_text(encoding="utf-8").split("\n")
    except (OSError, UnicodeDecodeError):
        return False
    if not lines or lines[0].strip() != "---":
        return False
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return False
    gates: dict[str, str] | None = None
    in_gates = False
    opens_map = False   # the last top-level key has no value (or `{}`): an indented line has a map to belong to
    for ln in lines[1:end]:
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        m = _STATE_LINE.match(ln)
        if m is None:
            return False
        rest = m["rest"] or ""
        if not m["indent"]:
            opens_map = _strip_comment(rest) in ("", "{}")
            in_gates = m["key"] == "gates"
            if in_gates:
                if gates is not None or _strip_comment(rest):
                    return False
                gates = {}
        elif not opens_map:
            return False   # the state reader rejects it ("indented key without a parent map"), so the guard opens nothing on it
        elif in_gates:
            if m["key"] in gates:
                return False
            gates[m["key"]] = _gate_value(rest)
    return gates is not None and gates.get(gate, "") == ""


def existing_rounds(root: Path) -> list[int]:
    d = root / "rounds"
    if not d.is_dir():
        return []
    return [int(m.group(1)) for c in d.iterdir() if c.is_dir() and (m := ROUND_RE.match(c.name))]


def round_is_open(root: Path, n: int) -> bool:
    """May files under rounds/r<n>/ of the project at `root` still be written? The latest round (and a new one above all the others),
    and rounds/r0/ (the style board) while G1s is not recorded. The guard and scripts/patch.py both ask this, so they cannot disagree."""
    return n >= max(existing_rounds(root) + [n]) or (n == 0 and gate_is_empty(root, "G1s"))


class Zone:
    def __init__(self, root: Path, p: Path):
        self.root, self.p = root, p
        parts = p.relative_to(root).parts
        self.parts = parts
        self.kind = parts[0] if parts and parts[0] in ("history", "rounds") else None
        self.round_n = None
        if self.kind == "rounds" and len(parts) > 1 and (m := ROUND_RE.match(parts[1])):
            self.round_n = int(m.group(1))
        self.inside_round = self.round_n is not None and len(parts) > 2

    def is_open(self) -> bool:
        """May this round still be written? See round_is_open."""
        return self.round_n is not None and round_is_open(self.root, self.round_n)

    def rel(self) -> str:
        return "/".join(self.parts) or "."


def zone_of(p: Path) -> Zone | None:
    root = project_root(p)
    return Zone(root, p) if root else None


# ------------------------------------------------------------------ messages

def msg_history(z: Zone, how: str) -> str:
    return (f"brand-creator guard: {how} blocked: {z.rel()} is inside history/, which is frozen (kept as written). "
            f"New files appear in history/ only through `brand-creator freeze`; to change something, make a new round "
            f"under rounds/ instead.")


def msg_old_round(z: Zone, how: str) -> str:
    return (f"brand-creator guard: {how} blocked: {z.rel()} belongs to round r{z.round_n}, which is not the latest round. "
            f"Earlier rounds are never edited. Copy it into a new round (rounds/r{max(existing_rounds(z.root)) + 1}/) "
            f"and change the copy.")


def msg_delete(z: Zone) -> str:
    return (f"brand-creator guard: delete blocked: {z.rel()} is under {z.kind}/. Never delete brand work; move it to "
            f"removed-<date>/ (moves out of the latest round into a removed-* folder are allowed).")


def msg_strict_write(z: Zone) -> str:
    return (f"brand-creator guard (strict): shell write into {z.rel()} blocked; use the Write or Edit tool for files "
            f"in the latest round.")


# ------------------------------------------------------------------ Write / Edit

def check_file_tool(tool: str, raw_path: str, cwd: Path) -> str | None:
    p = lenient_real(cwd / raw_path if not os.path.isabs(raw_path) else Path(raw_path))
    z = zone_of(p)
    if z is None or z.kind is None:
        return None
    how = {"Write": "write", "Edit": "edit", "MultiEdit": "edit", "NotebookEdit": "edit"}[tool]
    if z.kind == "history":
        if tool == "Write" and p.is_dir():
            return None
        return msg_history(z, how + (" (overwrite)" if tool == "Write" and p.exists() else " (new file)" if tool == "Write" else ""))
    if z.round_n is not None and not z.is_open():
        return msg_old_round(z, how)
    return None


# ------------------------------------------------------------------ Bash

_HEREDOC = re.compile(r"(<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2)([^\n]*)\n.*?\n[ \t]*\3[ \t]*(?=\n|$)", re.S)


def tokenize(cmd: str):
    """-> list of ('w', text) | ('op', ';') | ('redir', op, target) with quotes removed. Raises Unparseable."""
    cmd = _HEREDOC.sub(lambda m: m.group(1) + m.group(4), cmd)
    toks: list[tuple] = []
    buf, inword, i, n = "", False, 0, len(cmd)
    pending_redir: str | None = None

    def flush():
        nonlocal buf, inword, pending_redir
        if inword:
            if pending_redir is not None:
                toks.append(("redir", pending_redir, buf))
                pending_redir = None
            else:
                toks.append(("w", buf))
        buf, inword = "", False

    while i < n:
        c = cmd[i]
        if c == "\\":
            if i + 1 < n and cmd[i + 1] == "\n":
                i += 2
                continue
            buf += cmd[i + 1] if i + 1 < n else ""
            inword = True
            i += 2
        elif c == "'":
            j = cmd.find("'", i + 1)
            if j < 0:
                raise Unparseable("unterminated single quote")
            buf += cmd[i + 1:j]
            inword = True
            i = j + 1
        elif c == '"':
            j, out = i + 1, ""
            while j < n and cmd[j] != '"':
                if cmd[j] == "\\" and j + 1 < n and cmd[j + 1] in '"\\$`\n':
                    out += cmd[j + 1] if cmd[j + 1] != "\n" else ""
                    j += 2
                else:
                    out += cmd[j]
                    j += 1
            if j >= n:
                raise Unparseable("unterminated double quote")
            buf += out
            inword = True
            i = j + 1
        elif cmd.startswith("{}", i):  # the placeholder of find -exec and the bulk-argument runner, not a brace group
            buf += "{}"
            inword = True
            i += 2
        elif c in " \t":
            flush()
            i += 1
        elif c in "\n;(){}`":
            flush()
            if pending_redir is not None:
                raise Unparseable("redirect without a target")
            if c in "\n;(){}`":
                toks.append(("op", ";"))
            i += 1
        elif c == "|":
            flush()
            i += 2 if cmd[i:i + 2] in ("||", "|&") else 1
            toks.append(("op", ";"))
        elif c == "&":
            if cmd[i:i + 2] == "&>":
                flush()
                k = 3 if cmd[i:i + 3] == "&>>" else 2
                pending_redir = cmd[i:i + k]
                i += k
            else:
                flush()
                i += 2 if cmd[i:i + 2] == "&&" else 1
                toks.append(("op", ";"))
        elif c in "<>":
            fd_prefix = inword and buf.isdigit()
            if fd_prefix:
                buf, inword = "", False
            else:
                flush()
            for op in (">>", ">|", ">&", "<<<", "<<", "<&", ">", "<"):
                if cmd.startswith(op, i):
                    break
            i += len(op)
            pending_redir = op
        else:
            buf += c
            inword = True
            i += 1
    flush()
    if pending_redir is not None:
        raise Unparseable("redirect without a target")
    return toks


def segments(toks):
    seg_words: list[str] = []
    seg_redirs: list[tuple[str, str]] = []
    for t in toks:
        if t[0] == "w":
            seg_words.append(t[1])
        elif t[0] == "redir":
            seg_redirs.append((t[1], t[2]))
        else:
            if seg_words or seg_redirs:
                yield seg_words, seg_redirs
            seg_words, seg_redirs = [], []
    if seg_words or seg_redirs:
        yield seg_words, seg_redirs


def expand(word: str, cwd: Path) -> list[Path]:
    w = os.path.expanduser(os.path.expandvars(word))
    if "$" in w:
        return []  # cannot evaluate; best effort
    base = Path(w) if os.path.isabs(w) else cwd / w
    if any(ch in w for ch in "*?["):
        hits = glob.glob(str(base))
        return [lenient_real(Path(h)) for h in hits]
    return [lenient_real(base)]


def is_removed_dest(p: Path) -> bool:
    return any(part == "removed" or part.startswith("removed-") for part in p.parts)


def contained_projects(p: Path) -> list[Path]:
    """Brand projects that hold rounds/ or history/ and sit at p or one or two levels below it. Shallow on purpose:
    `rm -rf ~/brands` must be caught, a walk of a whole disk must not happen."""
    if not p.is_dir():
        return []
    found: list[Path] = []
    for pat in (STATE_FILE, f"*/{STATE_FILE}", f"*/*/{STATE_FILE}"):
        for h in sorted(glob.glob(str(p / pat))):
            d = Path(h).parent
            if (d / "rounds").exists() or (d / "history").exists():
                found.append(d)
    return found


def check_target(p: Path, op: str, *, to_removed: bool = False) -> str | None:
    """op: delete | move-from | write."""
    root = project_root(p)
    z = Zone(root, p) if root else None
    if op in ("delete", "move-from") and (z is None or z.kind is None):
        inner = contained_projects(p)
        if inner:
            what = "is the brand project folder" if inner[0] == p else f"contains the brand project {inner[0]}"
            return (f"brand-creator guard: {op.replace('-', ' ')} blocked: {p} {what}, which holds rounds/ or history/ "
                    f"(every round and the frozen history). Do not delete or move it from here; if the owner really wants "
                    f"that, they do it themselves outside this session.")
    if z is None or z.kind is None:
        return None
    if z.kind == "history":
        return msg_history(z, {"delete": "delete", "move-from": "move", "write": "shell write"}[op])
    # rounds/
    if op == "delete":
        return msg_delete(z)
    if op == "move-from":
        if to_removed and z.inside_round and z.is_open():
            return None
        return (f"brand-creator guard: move blocked: {z.rel()} is under rounds/. Only files inside the latest round may "
                f"be moved, and only into a removed-<date>/ folder.")
    if op == "write":
        if z.round_n is None:
            return None
        if not z.is_open():
            return msg_old_round(z, "shell write")
        if strict():
            return msg_strict_write(z)
    return None


def shell_string(w: list[str]) -> str | None:
    """The command string of `bash -c '...'` (also -lc, -ec ...), else None."""
    for k, x in enumerate(w[1:], 1):
        if re.match(r"^-[A-Za-z]*c[A-Za-z]*$", x) and k + 1 < len(w):
            return w[k + 1]
        if not x.startswith("-"):
            return None
    return None


def repo_top(p: Path) -> Path:
    """The top of the git working tree that holds p (a `.git` folder or file), else p itself."""
    q = lenient_real(p)
    for d in (q, *q.parents):
        if (d / ".git").exists():
            return d
    return q


def holds_protected(d: Path) -> bool:
    """d is the rounds/ folder itself, a project root with rounds/ or history/, or an ancestor of such a project: an archive
    extracted there can overwrite protected files through member paths the guard cannot see."""
    root = project_root(d)
    if root is not None and lenient_real(d) == lenient_real(root / "rounds"):
        return True
    if not d.is_dir():
        return False
    if root is not None and lenient_real(d) == lenient_real(root) and ((d / "rounds").exists() or (d / "history").exists()):
        return True
    return bool(contained_projects(d))


def git_targets(w: list[str], cwd: Path) -> tuple[list[tuple[Path, str]], str | None]:
    """(path, op) pairs a destructive git command can delete, move or overwrite, and the subcommand name (None when
    harmless). op is the check_target op: delete | move-from | write."""
    rest = list(w[1:])
    base = cwd
    while rest and rest[0].startswith("-"):
        if rest[0] == "-C" and len(rest) > 1:
            ps = expand(rest[1], base)
            base = ps[0] if ps else base
            rest = rest[2:]
        elif rest[0] in ("-c", "--git-dir", "--work-tree", "--namespace") and len(rest) > 1:
            rest = rest[2:]
        else:
            rest = rest[1:]
    if not rest:
        return [], None
    sub, args = rest[0], rest[1:]
    flags = [a for a in args if a.startswith("-")]
    paths = [a for a in args if not a.startswith("-")]
    if sub == "clean":
        if any(re.match(r"^-[A-Za-z]*n", a) or a == "--dry-run" for a in flags):
            return [], None
    elif sub == "reset":
        if "--hard" not in flags:
            return [], None
        paths = []
    elif sub == "checkout":
        if "--" in args:
            paths = args[args.index("--") + 1:]
        elif "." in paths or any(a in ("-f", "--force") for a in flags):
            paths = [x for x in paths if x == "."] or []
        else:
            return [], None
    elif sub == "restore":
        if "--staged" in flags and "--worktree" not in flags and "-W" not in flags:
            return [], None  # index only, the working tree is untouched
    elif sub == "rm":
        if "--cached" in flags:
            return [], None
    elif sub == "mv":
        paths = [x for x in paths if x != "--"]
        if len(paths) < 2:
            return [], None
        out = [(p, "move-from") for x in paths[:-1] for p in expand(x, base)]
        out += [(p, "write") for p in expand(paths[-1], base)]
        return out, sub
    elif sub == "stash":
        # `git stash push -u` removes untracked (and with -a ignored) files from the working tree, like `git clean`, and
        # does so for the whole repository whatever the cwd. Every non-option word after `push` is a pathspec (the -m value
        # is not); `save` takes a message, not paths. git accepts unique prefixes of long options, so those count too.
        word, opts = ("push", args) if not args or args[0].startswith("-") else (args[0], args[1:])
        if word not in ("push", "save"):
            return [], None
        untracked, pathspec, k, after, whole = False, [], 0, False, False
        known = ("--keep-index", "--no-keep-index", "--patch", "--staged", "--quiet")
        while k < len(opts):
            a = opts[k]
            k += 1
            if after:
                pathspec.append(a)
            elif a == "--":
                after = True
            elif a == "-m":
                k += 1
            elif a.startswith("--"):
                name, eq, _ = a.partition("=")
                if len(name) >= 4 and "--message".startswith(name):
                    k += 0 if eq else 1  # --mes wip: the next word is the message, not a path
                elif len(name) >= 3 and ("--include-untracked".startswith(name) or "--all".startswith(name)):
                    untracked = True
                elif name.startswith("--pathspec"):  # paths the guard cannot read
                    untracked = whole = True
                elif not any(len(name) >= 4 and o.startswith(name) for o in known):
                    whole = True  # an option the guard does not know may take the next word: fail closed
            elif a.startswith("-"):
                untracked = untracked or bool(re.match(r"^-[A-Za-z]*[ua]", a))
                if re.match(r"^-[A-Za-z]*m$", a):
                    k += 1
            elif word == "push":
                pathspec.append(a)
        if not untracked:
            return [], None
        # pathspec magic (`:/`, `:(top)history`, `:!x`) and globs git expands itself reach beyond the words the guard can
        # resolve: treat them, like no pathspec at all, as the whole working tree
        paths = [] if whole or any(p.startswith(":") or any(c in p for c in "*?[") for p in pathspec) else pathspec
        if not paths:
            base = repo_top(base)
    else:
        return [], None
    paths = [x for x in paths if x != "--"]
    out_p: list[Path] = []
    for x in paths:
        out_p += expand(x, base)
    return [(p, "delete") for p in (out_p or [lenient_real(base)])], sub


def archive_writes(cmdname: str, w: list[str], cwd: Path) -> list[Path]:
    """Directories (or archive files) that tar, unzip, 7z or ditto would write into. Listing and testing write nothing."""
    rest = w[1:]
    out: list[str] = []
    if cmdname in ("tar", "gtar", "bsdtar"):
        extract = create = False
        dirs: list[str] = []
        archive = None
        k = 0
        first = True
        while k < len(rest):
            a = rest[k]
            k += 1
            if a.startswith("--"):
                # GNU tar takes unique abbreviations (--ext, --dir=...): match by prefix, at a length no other option shares
                name, eq, val = a.partition("=")
                if (len(name) >= 5 and "--extract".startswith(name)) or (len(name) >= 4 and "--get".startswith(name)):
                    extract = True
                elif len(name) >= 4 and "--create".startswith(name):
                    create = True
                elif len(name) >= 5 and "--directory".startswith(name):
                    if eq:
                        dirs.append(val)
                    elif k < len(rest):
                        dirs.append(rest[k]); k += 1
                elif name == "--file":
                    if eq:
                        archive = val
                    elif k < len(rest):
                        archive = rest[k]; k += 1
            elif a.startswith("-") and len(a) > 1 or (first and re.match(r"^[A-Za-z]+$", a)):
                dashed = a.startswith("-")
                cluster = a.lstrip("-")
                for i, ch in enumerate(cluster):
                    if ch == "x":
                        extract = True
                    elif ch == "c":
                        create = True
                    elif ch in "fC":
                        # a dashed cluster's value may be attached (-Chistory, -xfa.tar); otherwise it is the next word
                        if dashed and i + 1 < len(cluster):
                            val = cluster[i + 1:]
                        elif k < len(rest):
                            val = rest[k]; k += 1
                        else:
                            break
                        if ch == "C":
                            dirs.append(val)
                        else:
                            archive = val
                        if dashed:
                            break
            first = False
        if extract:
            out = dirs or ["."]
        elif create and archive and archive != "-":
            out = [archive]
    elif cmdname == "unzip":
        # option clusters: a `d` takes the rest of the cluster or the next word as the destination; l, t, z, p, v and Z
        # before it only list, test or print (nothing is written)
        out = ["."]
        k = 0
        while k < len(rest):
            a = rest[k]
            k += 1
            if not a.startswith("-") or a == "-":
                continue
            cluster = a[1:]
            head, d, tail = cluster.partition("d")
            # list/test/print only when the letters are plain: unzip reads a '-' inside a cluster as negation (-l-), and a
            # long option is not one of these letters, so either keeps the destination check (fail closed)
            if re.search(r"[ltzpvZ]", head) and "-" not in cluster:
                return []
            if d:
                if tail:
                    out = [tail]
                elif k < len(rest):
                    out = [rest[k]]; k += 1
    elif cmdname.startswith("7z"):
        # the command letter is the first word that is not a switch (7z -y x a.7z is the same as 7z x -y a.7z)
        # 7z commands and switches are case-insensitive (X, -O)
        words = [a for a in rest if not a.startswith("-")]
        if words and words[0].lower() in ("x", "e"):
            out = ["."]
            for a in rest:
                if a.lower().startswith("-o") and len(a) > 2:
                    out = [a[2:]]
    elif cmdname == "ditto":
        pos = [a for a in rest if not a.startswith("-")]
        if len(pos) >= 2:
            out = [pos[-1]]
    paths: list[Path] = []
    for x in out:
        paths += expand(x, cwd)
    return paths


def check_bash(command: str, cwd: Path, depth: int = 0) -> list[str]:
    if depth > MAX_NESTING:
        return ["brand-creator guard: shell command nested too deeply (bash -c inside bash -c ...) to inspect; "
                "run the steps one at a time."]
    toks = tokenize(command)
    reasons: list[str] = []
    for words, redirs in segments(toks):
        # redirects: writes
        for op, target in redirs:
            if op.startswith("<") or (op == ">&" and (target.isdigit() or target == "-")):
                continue
            if target in ("/dev/null", "/dev/stderr", "/dev/stdout"):
                continue
            for p in expand(target, cwd):
                r = check_target(p, "write")
                if r:
                    reasons.append(r)
        # leading assignments and wrappers
        w = list(words)
        while w and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w[0]) or w[0] in WRAPPERS):
            w.pop(0)
        if not w:
            continue
        cmdname = os.path.basename(w[0])
        if cmdname == "cd" and len(w) > 1:
            ps = expand(w[1], cwd)
            if ps:
                cwd = ps[0]
            continue
        if cmdname == "brand-creator" and "freeze" in w[1:6]:
            continue  # the sanctioned way to add files to history/
        if any(os.path.basename(x) == "brand-creator" for x in w[:3]) and "freeze" in w[1:8]:
            continue
        args = []
        dashdash = False
        for x in w[1:]:
            if x == "--":
                dashdash = True
            elif dashdash or not x.startswith("-") or x == "-":
                args.append(x)
        if cmdname in SHELLS or cmdname == "eval":
            inner = shell_string(w) if cmdname in SHELLS else " ".join(w[1:])
            if inner:
                reasons += check_bash(inner, cwd, depth + 1)
            continue
        if cmdname == "xargs" and any(os.path.basename(x) in DELETERS | {"mv"} for x in w[1:]):
            root = project_root(cwd)
            if (root is not None and ((root / "rounds").exists() or (root / "history").exists())) or contained_projects(cwd):
                reasons.append(f"brand-creator guard: xargs with a deleter or mv blocked in {cwd}: the file list comes from "
                               f"standard input, so the guard cannot see what it would remove. Name the files in the "
                               f"command, or move them to removed-<date>/ one by one.")
            continue
        if cmdname == "git":
            targets, sub = git_targets(w, cwd)
            to_removed = sub == "mv" and bool(targets) and is_removed_dest(targets[-1][0])
            for t, op in targets:
                r = check_target(t, op, to_removed=to_removed)
                if r:
                    for old in ("delete blocked", "move blocked", "shell write blocked"):
                        r = r.replace(old, f"git {sub} blocked (it would delete, move or overwrite files)", 1)
                    reasons.append(r)
            continue
        if cmdname in ARCHIVERS:
            for d in archive_writes(cmdname, w, cwd):
                r = check_target(d, "write")
                if r:
                    reasons.append(r.replace("shell write blocked", f"{cmdname} extract blocked (it would overwrite files)", 1))
                elif holds_protected(d):
                    reasons.append(f"brand-creator guard: {cmdname} extract blocked: {d} holds rounds/ or history/ (or a brand "
                                   f"project that does), and the archive's member paths are not visible here, so they could "
                                   f"overwrite frozen files. Extract into a scratch folder (tools/ or a temp dir) and move "
                                   f"what you need.")
            continue
        if cmdname in DELETERS:
            for a in args:
                for p in expand(a, cwd):
                    r = check_target(p, "delete")
                    if r:
                        reasons.append(r)
        elif cmdname == "mv":
            tdir = None
            for k, x in enumerate(w[1:], 1):
                if x in ("-t", "--target-directory") and k + 1 < len(w):
                    tdir = w[k + 1]
                elif x.startswith("--target-directory="):
                    tdir = x.split("=", 1)[1]
            dest = tdir if tdir else (args[-1] if args else None)
            srcs = args if tdir else args[:-1]
            dpaths = expand(dest, cwd) if dest else []
            to_removed = bool(dpaths) and all(is_removed_dest(d) for d in dpaths)
            for s in srcs:
                for p in expand(s, cwd):
                    r = check_target(p, "move-from", to_removed=to_removed)
                    if r:
                        reasons.append(r)
            for d in dpaths:
                r = check_target(d, "write")
                if r:
                    reasons.append(r)
        elif cmdname in COPIERS:
            tdir = None
            for k, x in enumerate(w[1:], 1):
                if x in ("-t", "--target-directory") and k + 1 < len(w):
                    tdir = w[k + 1]
            dest = tdir if tdir else (args[-1] if len(args) >= 2 else None)
            for d in (expand(dest, cwd) if dest else []):
                r = check_target(d, "write")
                if r:
                    reasons.append(r)
        elif cmdname in ("sed", "gsed", "perl") and any(
                re.match(r"^-[A-Za-z]*i", x) or x == "--in-place" or x.startswith("--in-place=") for x in w[1:]):
            for a in args:
                for p in expand(a, cwd):
                    r = check_target(p, "write")
                    if r:
                        reasons.append(r)
        elif cmdname == "tee":
            for a in args:
                for p in expand(a, cwd):
                    r = check_target(p, "write")
                    if r:
                        reasons.append(r)
        elif cmdname == "truncate":
            for a in args[-1:]:
                for p in expand(a, cwd):
                    r = check_target(p, "write")
                    if r:
                        reasons.append(r)
        elif cmdname == "dd":
            for x in w[1:]:
                if x.startswith("of="):
                    for p in expand(x[3:], cwd):
                        r = check_target(p, "write")
                        if r:
                            reasons.append(r)
        elif cmdname == "find" and any(x in ("-delete",) for x in w) or (
                cmdname == "find" and "-exec" in w and any(os.path.basename(x) in DELETERS for x in w)):
            for a in args:
                if a.startswith(("-", "(", "!")):
                    break
                for p in expand(a, cwd):
                    r = check_target(p, "delete")
                    if r:
                        reasons.append(r)
    return list(dict.fromkeys(reasons))


# ------------------------------------------------------------------ main

def warn(msg: str) -> None:
    print(f"brand-creator guard: WARNING {msg}; allowing the call unchecked (fail-open for unparseable input only).",
          file=sys.stderr)


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("hook input is not a JSON object")
    except ValueError as e:
        warn(f"cannot parse the hook input ({e})")
        return 0
    tool = payload.get("tool_name")
    ti = payload.get("tool_input") or {}
    cwd = Path(payload.get("cwd") or os.getcwd())
    reasons: list[str] = []
    if tool in FILE_TOOLS:
        target = ti.get(FILE_TOOLS[tool]) or ti.get("file_path") or ti.get("path")
        if not isinstance(target, str) or not target:
            return 0
        r = check_file_tool(tool, target, cwd)
        if r:
            reasons.append(r)
    elif tool == "Bash":
        command = ti.get("command")
        if not isinstance(command, str) or not command.strip():
            return 0
        try:
            reasons = check_bash(command, cwd)
        except Unparseable as e:
            warn(f"cannot tokenise the shell command ({e})")
            return 0
    else:
        return 0
    if reasons:
        print("\n".join(reasons), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Shared helpers for every brand-creator Python script. Standard library only.

Contract (see scripts/CONTRACT.md):
  * project discovery: --project DIR, or walk up from the cwd to a folder holding BRAND-STATE.md
  * writes are confined to the project (scratch goes under the data dir)
  * reports: <project>/assets/_checks/<tool>.json  {tool, version, inputs_sha, results[], status}
  * exit codes: 0 pass, 1 gate failed, 2 usage error, 3 cannot run (missing dependency or platform)
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_CANNOT = 0, 1, 2, 3
STATE_FILE = "BRAND-STATE.md"
RENDERERS = ("resvg", "pillow")
GATE_IDS = ("G0", "G1", "G2", "G2b", "G3", "G4", "G5", "G6", "G7")
# One User-Agent for every outbound request any script ever makes. Generic on purpose: no personal data, no "@".
USER_AGENT = "brand-creator/0.2.1 (+https://example.invalid/brand-creator)"


class CliError(Exception):
    """Raised anywhere; main_guard() prints it and exits with its code."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def fail(code: int, message: str):
    raise CliError(code, message)


_OPEN_REPORTS: list = []   # Reports created and not yet finished: a run that dies through fail() records its failure in them


def _persist_failure(message: str, code: int) -> None:
    """A run that stops early (through fail() or an unexpected exception) must not leave the previous (passing) report of its
    tool standing: rewrite each open report with status fail and the error message (CONTRACT.md, "A run that fails records the
    failure")."""
    for rep in list(_OPEN_REPORTS):
        try:
            rep.add("error", "fail", "the run stopped before it finished", detail=message, exit_code=code)
            path = rep.write()
            print(f"failure recorded in {path}", file=sys.stderr)
        except Exception as ex:   # never mask the original error; say that the report could not be rewritten
            print(f"warning: could not record the failure in the {rep.tool} report ({ex}); its previous report may still read as passing", file=sys.stderr)


def main_guard(fn):
    """Run fn() -> int, turning CliError into a clean message and exit code. Any other exception is a crash: its traceback is
    printed, the open reports record it as a failure, and the exit code is 1 (a crash must never leave a passing report)."""
    try:
        rc = fn()
    except CliError as e:
        print(f"error: {e.message}", file=sys.stderr)
        rc = e.code
        if rc:
            _persist_failure(e.message, e.code)
    except BrokenPipeError:
        rc = EXIT_PASS
    except Exception as e:
        import traceback
        traceback.print_exc()
        rc = EXIT_FAIL
        _persist_failure(f"unexpected {type(e).__name__}: {e}", rc)
    sys.exit(rc or 0)


# ---------------------------------------------------------------- plugin + environment

def plugin_root() -> Path:
    return Path(__file__).resolve().parents[2]


def plugin_version() -> str:
    try:
        return json.loads((plugin_root() / ".claude-plugin" / "plugin.json").read_text())["version"]
    except (OSError, KeyError, ValueError) as e:
        fail(EXIT_CANNOT, f"cannot read the plugin version from .claude-plugin/plugin.json: {e}")


def data_dir() -> Path:
    d = os.environ.get("BRAND_CREATOR_DATA", "").strip()
    if not d:
        fail(EXIT_USAGE, "no data directory: pass --data <dir> to brand-creator (skills pass ${CLAUDE_PLUGIN_DATA}) "
                         "or set BRAND_CREATOR_DATA")
    return Path(d).expanduser().resolve()


def today() -> str:
    """ISO date; BRAND_CREATOR_TODAY overrides it (tests, reproducible runs)."""
    forced = os.environ.get("BRAND_CREATOR_TODAY", "").strip()
    if forced:
        try:
            _dt.date.fromisoformat(forced)
        except ValueError:
            fail(EXIT_USAGE, f"BRAND_CREATOR_TODAY must be YYYY-MM-DD, got {forced!r}")
        return forced
    return _dt.date.today().isoformat()


CHAIN_ENV = "BRAND_CREATOR_CHAIN"


def require_chain(what: str) -> None:
    """A generator that clears or rewrites a whole output folder calls this first: run alone it would wipe files that later steps of
    the chain (finish.sh) fill in, so outside the chain it refuses (exit 1) with a message that names the chain."""
    if os.environ.get(CHAIN_ENV) != "1":
        fail(EXIT_FAIL, f"{what} rewrites its whole output folder and the later steps of the chain refill it: run the whole chain "
                        f"(`bash tools/finish.sh`, which sets {CHAIN_ENV}=1), not this step alone")


def which_or_cannot(tool: str, hint: str) -> str:
    p = shutil.which(tool)
    if not p:
        fail(EXIT_CANNOT, f"{tool} not found on PATH. {hint}")
    return p


def run(cmd: list[str], *, input: bytes | None = None, timeout: int = 120, cwd: Path | None = None,
        check: bool = True) -> subprocess.CompletedProcess:
    try:
        cp = subprocess.run(cmd, input=input, capture_output=True, timeout=timeout, cwd=cwd)
    except FileNotFoundError:
        fail(EXIT_CANNOT, f"command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        fail(EXIT_CANNOT, f"timed out after {timeout}s: {' '.join(cmd[:3])} ...")
    if check and cp.returncode != 0:
        fail(EXIT_CANNOT, f"{' '.join(cmd[:3])} ... exited {cp.returncode}: "
                          f"{cp.stderr.decode('utf-8', 'replace').strip()[:400]}")
    return cp


# ---------------------------------------------------------------- project discovery + confinement

def find_project(arg: str | None = None, cwd: Path | None = None) -> Path:
    if arg:
        p = Path(arg).expanduser().resolve()
        if not (p / STATE_FILE).is_file():
            fail(EXIT_USAGE, f"no brand project at {p} ({STATE_FILE} not found); pass --project <dir>")
        return p
    cur = (cwd or Path.cwd()).resolve()
    for d in [cur, *cur.parents]:
        if (d / STATE_FILE).is_file():
            return d
    fail(EXIT_USAGE, "no brand project found; pass --project")


def try_find_project(cwd: Path | None = None) -> Path | None:
    cur = (cwd or Path.cwd()).resolve()
    for d in [cur, *cur.parents]:
        if (d / STATE_FILE).is_file():
            return d
    return None


def _realpath_lenient(p: Path) -> Path:
    """realpath that also works for paths that do not exist yet (resolves the deepest existing prefix)."""
    p = Path(os.path.abspath(p))
    tail: list[str] = []
    while not p.exists() and p != p.parent:
        tail.append(p.name)
        p = p.parent
    return Path(os.path.realpath(p)).joinpath(*reversed(tail))


def confine(project: Path, path: str | Path, *, what: str = "path") -> Path:
    """Resolve path (relative paths are relative to the project) and require it to stay inside the project."""
    root = Path(os.path.realpath(project))
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    real = _realpath_lenient(p)
    try:
        real.relative_to(root)
    except ValueError:
        fail(EXIT_USAGE, f"{what} {path} is outside the project {root}; brand-creator only writes inside the project")
    return real


def outside_project(project: Path, path: str | Path, *, what: str = "path") -> Path:
    root = Path(os.path.realpath(project))
    real = _realpath_lenient(Path(path).expanduser())
    try:
        real.relative_to(root)
    except ValueError:
        return real
    fail(EXIT_USAGE, f"{what} {path} must be outside the project (scratch output); use the data dir or a temp folder")


def rel(project: Path, path: Path) -> str:
    return Path(os.path.realpath(path)).relative_to(Path(os.path.realpath(project))).as_posix()


def scratch_dir(project: Path, name: str) -> Path:
    d = data_dir() / "scratch" / (re.sub(r"[^a-z0-9._-]+", "-", project.name.lower()) + "-" +
                                  hashlib.sha256(str(project).encode()).hexdigest()[:8]) / name
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as e:   # a read-only data folder (a sandbox that may not write it, as in a `claude plugin eval` run)
        fail(EXIT_CANNOT, f"cannot write scratch output under the data directory ({d}): {e.strerror or e}. Pass --data <a writable "
                          "folder that setup prepared>; run /brand-creator:setup (or: brand-creator --data <dir> setup --yes)")
    return d


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def downscale_report_tool(source_rel: str) -> str:
    """The report tool name (-> assets/_checks/downscale/<slug>.json) of a downscale run on one source file: one report per measured
    master, so a passing report for one file can never stand in for another."""
    src = Path(source_rel).as_posix()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", Path(src).stem).strip("-").lower() or "source"
    return f"downscale/{slug}-{hashlib.sha256(src.encode()).hexdigest()[:6]}"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_bytes_if_changed(path: Path, data: bytes) -> bool:
    """Put-on-byte-change. Returns True when the file was (re)written."""
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-bc")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return True


# ---------------------------------------------------------------- BRAND-STATE.md (frontmatter subset)

_KEY_RE = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z0-9_.-]+):(?:\s+(?P<rest>.*))?$")


def _split_comment(rest: str) -> tuple[str, str]:
    """Split 'value  # comment' into ('value', '  # comment'), ignoring '#' inside quotes."""
    q = ""
    for i, ch in enumerate(rest):
        if q:
            if ch == q and rest[i - 1] != "\\":
                q = ""
        elif ch in "\"'":
            q = ch
        elif ch == "#" and (i == 0 or rest[i - 1] in " \t"):
            j = i
            while j > 0 and rest[j - 1] in " \t":
                j -= 1
            return rest[:j], rest[j:]
    return rest, ""


def _line(ln: str):
    """-> (indent, key, raw value, comment) or None."""
    m = _KEY_RE.match(ln)
    if not m:
        return None
    val, cmt = _split_comment(m["rest"] or "")
    return m["indent"], m["key"], val.strip(), cmt


def _parse_scalar(v: str):
    v = v.strip()
    if v == "":
        return ""
    if v == "{}":
        return {}
    if v.startswith('"') and v.endswith('"') and len(v) >= 2:
        try:
            return json.loads(v)
        except ValueError:
            return v[1:-1]
    if v.startswith("'") and v.endswith("'") and len(v) >= 2:
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [x.strip().strip("\"'") for x in inner.split(",")] if inner else []
    return v


def _format_scalar(v) -> str:
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(str(x) for x in v) + "]"
    s = str(v)
    if s == "" or re.search(r"(^\s|\s$|: |\s#|^[\[\]{}\"'&*!|>%@`-])", s):
        return json.dumps(s, ensure_ascii=False)
    return s


class State:
    """BRAND-STATE.md: a frontmatter block of 'key: value' lines (one level of nesting) followed by free markdown."""

    def __init__(self, path: Path):
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        self.lines = self.text.split("\n")
        if not self.lines or self.lines[0].strip() != "---":
            fail(EXIT_USAGE, f"{path} has no frontmatter (first line must be ---)")
        try:
            self.end = next(i for i in range(1, len(self.lines)) if self.lines[i].strip() == "---")
        except StopIteration:
            fail(EXIT_USAGE, f"{path} frontmatter is not closed with ---")

    # -- reading
    def data(self) -> dict:
        out: dict = {}
        parent = None
        for ln in self.lines[1:self.end]:
            if not ln.strip() or ln.lstrip().startswith("#"):
                continue
            parsed = _line(ln)
            if not parsed:
                fail(EXIT_USAGE, f"{self.path}: cannot parse frontmatter line: {ln!r}")
            indent, key, raw, _cmt = parsed
            if len(indent) == 0:
                if raw in ("", "{}"):
                    out[key] = {}
                    parent = key
                else:
                    out[key] = _parse_scalar(raw)
                    parent = None
            else:
                if parent is None or not isinstance(out.get(parent), dict):
                    fail(EXIT_USAGE, f"{self.path}: indented key without a parent map: {ln!r}")
                out[parent][key] = _parse_scalar(raw)
        return out

    def get(self, dotted: str, default=None):
        cur = self.data()
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    # -- writing
    def set(self, dotted: str, value) -> None:
        parts = dotted.split(".")
        if len(parts) > 2:
            fail(EXIT_USAGE, f"state keys nest at most one level, got {dotted!r}")
        sval = _format_scalar(value)
        if len(parts) == 1:
            idx = self._find(parts[0], 0)
            if idx is None:
                self.lines.insert(self.end, f"{parts[0]}: {sval}")
                self.end += 1
            else:
                self._replace_value(idx, sval)
            return
        pidx = self._find(parts[0], 0)
        if pidx is None:
            self.lines.insert(self.end, f"{parts[0]}:")
            self.end += 1
            pidx = self.end - 1
        else:
            _i, _k, raw, cmt = _line(self.lines[pidx])
            if raw == "{}":
                self.lines[pidx] = f"{parts[0]}:" + cmt
            elif raw != "":
                fail(EXIT_USAGE, f"{parts[0]} is a scalar in {self.path}, cannot set {dotted}")
        i = pidx + 1
        last = pidx
        while i < self.end and (not self.lines[i].strip() or self.lines[i].startswith(" ")):
            if self.lines[i].strip():
                last = i
                parsed = _line(self.lines[i])
                if parsed and parsed[1] == parts[1] and len(parsed[0]) > 0:
                    self._replace_value(i, sval)
                    return
            i += 1
        self.lines.insert(last + 1, f"  {parts[1]}: {sval}")
        self.end += 1

    def _find(self, key: str, indent: int):
        for i in range(1, self.end):
            parsed = _line(self.lines[i])
            if parsed and parsed[1] == key and len(parsed[0]) == indent and not self.lines[i].lstrip().startswith("#"):
                return i
        return None

    def _replace_value(self, idx: int, sval: str) -> None:
        indent, key, _raw, cmt = _line(self.lines[idx])
        self.lines[idx] = f"{indent}{key}: {sval}" + cmt

    def save(self) -> None:
        new = "\n".join(self.lines)
        tmp = self.path.with_name(self.path.name + ".tmp-bc")
        tmp.write_text(new, encoding="utf-8")
        os.replace(tmp, self.path)

    # -- body helpers
    def directions(self) -> list[dict]:
        """Rows of the first markdown table under a '## Directions' heading."""
        body = self.lines[self.end + 1:]
        rows, in_sec, header = [], False, None
        for ln in body:
            if re.match(r"^#{1,6}\s+Directions\b", ln):
                in_sec = True
                continue
            if in_sec and re.match(r"^#{1,6}\s", ln):
                break
            if in_sec and ln.strip().startswith("|"):
                cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                if header is None:
                    header = [c.lower() for c in cells]
                elif not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    if any(cells):
                        rows.append(dict(zip(header, cells)))
        return rows


def read_state(project: Path) -> State:
    return State(project / STATE_FILE)


def gate_recorded(project: Path, gate: str) -> str:
    gates = read_state(project).get("gates", {}) or {}
    return str(gates.get(gate, "") or "").strip()


def require_gate(project: Path, gate: str, *, for_what: str) -> None:
    if not gate_recorded(project, gate):
        fail(EXIT_FAIL, f"{for_what} needs gate {gate} recorded in {STATE_FILE}; it is not. "
                        f"Get the owner's decision, then run: brand-creator state --record {gate} \"<decision>\"")


# ---------------------------------------------------------------- rounds + history

ROUND_RE = re.compile(r"^r(\d+)$")


def list_rounds(project: Path) -> list[tuple[int, Path]]:
    d = project / "rounds"
    if not d.is_dir():
        return []
    out = []
    for p in d.iterdir():
        m = ROUND_RE.match(p.name)
        if m and p.is_dir():
            out.append((int(m.group(1)), p))
    return sorted(out)


def latest_round(project: Path) -> int | None:
    r = list_rounds(project)
    return r[-1][0] if r else None


MANIFEST_NAME = "MANIFEST.sha256"


def history_files(history: Path) -> list[Path]:
    return sorted(p for p in history.rglob("*") if p.is_file() and p.name != MANIFEST_NAME)


def read_history_manifest(history: Path) -> dict[str, str]:
    mf = history / MANIFEST_NAME
    out: dict[str, str] = {}
    if not mf.is_file():
        return out
    for n, ln in enumerate(mf.read_text(encoding="utf-8").splitlines(), 1):
        if not ln.strip():
            continue
        m = re.match(r"^([0-9a-f]{64})  (.+)$", ln)
        if not m:
            fail(EXIT_FAIL, f"{mf}:{n}: malformed manifest line")
        out[m.group(2)] = m.group(1)
    return out


def write_history_manifest(history: Path, entries: dict[str, str]) -> None:
    body = "".join(f"{h}  {p}\n" for p, h in sorted(entries.items()))
    (history / MANIFEST_NAME).write_text(body, encoding="utf-8")


def verify_history(project: Path) -> list[str]:
    """Problems found comparing history/ with history/MANIFEST.sha256 (empty list = intact)."""
    history = project / "history"
    if not history.is_dir():
        return []
    listed = read_history_manifest(history)
    problems = []
    actual = {p.relative_to(history).as_posix(): p for p in history_files(history)}
    for relp, h in listed.items():
        if relp not in actual:
            problems.append(f"missing: history/{relp}")
        elif sha256_file(actual[relp]) != h:
            problems.append(f"modified: history/{relp}")
    for relp in actual:
        if relp not in listed:
            problems.append(f"not in {MANIFEST_NAME} (added outside freeze): history/{relp}")
    return problems


# ---------------------------------------------------------------- FORBIDDEN list

def forbidden_terms(project: Path) -> list[str]:
    """Bullet items under a heading starting with 'Forbidden' in brief/BRIEF.md and research/cliches.md."""
    terms: list[str] = []
    for relp in ("brief/BRIEF.md", "research/cliches.md"):
        f = project / relp
        if not f.is_file():
            continue
        in_sec = False
        for ln in f.read_text(encoding="utf-8").splitlines():
            if re.match(r"^#{1,6}\s+", ln):
                in_sec = bool(re.match(r"^#{1,6}\s+Forbidden\b", ln, re.I))
                continue
            m = re.match(r"^\s*[-*]\s+(.+?)\s*$", ln)
            if in_sec and m:
                t = m.group(1).strip().strip("`").strip()
                if t and not t.startswith("<!--") and t not in terms:
                    terms.append(t)
    return terms


# ---------------------------------------------------------------- reports

class Report:
    """Collects results and writes <project>/assets/_checks/<tool>.json."""

    def __init__(self, tool: str, project: Path, inputs: list[Path] | None = None, *, renderer: str | None = None):
        self.tool = tool
        self.project = project
        self.inputs = [Path(p) for p in (inputs or [])]
        self.results: list[dict] = []
        self.extra: dict = {}
        self.renderer = renderer
        _OPEN_REPORTS.append(self)

    def add(self, id: str, status: str, label: str = "", **extra) -> dict:
        assert status in ("pass", "fail", "warn", "info", "skipped"), status
        r = {"id": id, "status": status, "label": label, **extra}
        self.results.append(r)
        return r

    @property
    def status(self) -> str:
        sts = {r["status"] for r in self.results}
        if "fail" in sts:
            return "fail"
        if "skipped" in sts or not self.results:
            return "not-verified"
        return "pass"

    def exit_code(self) -> int:
        return {"pass": EXIT_PASS, "fail": EXIT_FAIL, "not-verified": EXIT_CANNOT}[self.status]

    def _inputs_record(self) -> list[dict]:
        recs, seen = [], set()
        for p in sorted(self.inputs, key=lambda x: str(x)):
            real = os.path.realpath(p)
            if real in seen:   # an input named twice is recorded once
                continue
            seen.add(real)
            if p.is_file():
                try:
                    shown = rel(self.project, p)
                except ValueError:  # a read-only input outside the project (a sibling repository): recorded by absolute path
                    shown = str(Path(os.path.realpath(p)))
                recs.append({"path": shown, "sha256": sha256_file(p)})
        return recs

    @staticmethod
    def inputs_sha(recs: list[dict]) -> str:
        h = hashlib.sha256()
        for r in recs:
            h.update(f"{r['path']}\0{r['sha256']}\n".encode())
        return h.hexdigest()

    def write(self) -> Path:
        recs = self._inputs_record()
        renderer = self.renderer or str(read_state(self.project).get("renderer", "") or "resvg (default)")
        doc = {"tool": self.tool, "version": plugin_version(), "inputs_sha": self.inputs_sha(recs),
               "inputs": recs, "renderer": renderer, "results": self.results, "status": self.status, **self.extra}
        out = confine(self.project, Path("assets/_checks") / f"{self.tool}.json", what="report")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return out

    def finish(self, *, quiet_pass: bool = False) -> int:
        path = self.write()
        if self in _OPEN_REPORTS:
            _OPEN_REPORTS.remove(self)
        for r in self.results:
            if quiet_pass and r["status"] == "pass":
                continue
            tag = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "info": "INFO", "skipped": "SKIP"}[r["status"]]
            line = f"[{tag}] {r['id']}"
            if r.get("label"):
                line += f" ({r['label']})"
            if r.get("detail"):
                line += f": {r['detail']}"
            print(line)
        n = {k: sum(1 for r in self.results if r["status"] == k) for k in ("pass", "fail", "warn", "skipped")}
        shown = (self.renderer or str(read_state(self.project).get("renderer", "") or "resvg (default)"))
        print(f"{self.tool}: {self.status.upper()}  ({n['pass']} pass, {n['fail']} fail, {n['warn']} warn, "
              f"{n['skipped']} not verified)  renderer: {shown}")
        print(f"report: {path}")
        return self.exit_code()


# ---------------------------------------------------------------- argparse helpers

def add_project_arg(ap) -> None:
    ap.add_argument("--project", help="brand project folder (default: walk up from the cwd to BRAND-STATE.md)")


def add_renderer_arg(ap) -> None:
    ap.add_argument("--renderer", choices=RENDERERS, default="resvg",
                    help="rasteriser: resvg (default; the resvg program must be installed) or pillow "
                         "(raster inputs only; cannot read SVG)")


class Parser(__import__("argparse").ArgumentParser):
    """argparse that exits 2 (usage error) through CliError like everything else."""

    def error(self, message):
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        sys.exit(EXIT_USAGE)


# ---------------------------------------------------------------- rasterising

RESVG_HINT = ("Install resvg (macOS: brew install resvg; Linux: apt install resvg (Debian 13) or cargo install resvg, or your package manager; "
              "Windows: winget install resvg or cargo install resvg), then re-run.")


def resvg_path() -> str:
    return which_or_cannot("resvg", RESVG_HINT)


def rasterise_svg(svg_text: str, width: int, height: int, *, background: str | None = None,
                  renderer: str = "resvg", workdir: Path | None = None) -> bytes:
    """Rasterise SVG text to PNG bytes at exactly width x height (the SVG should already be fitted; see svgtools)."""
    if renderer != "resvg":
        fail(EXIT_CANNOT, f"--renderer={renderer} cannot rasterise SVG (it only resamples PNG input). "
                          f"Use --renderer=resvg. {RESVG_HINT}")
    exe = resvg_path()
    import tempfile
    with tempfile.TemporaryDirectory(prefix="bc-resvg-", dir=str(workdir) if workdir else None) as td:
        src = Path(td) / "in.svg"
        out = Path(td) / "out.png"
        src.write_text(svg_text, encoding="utf-8")
        cmd = [exe, "-w", str(width), "-h", str(height)]
        if background:
            cmd += ["--background", background]
        cmd += [str(src), str(out)]
        run(cmd)
        return out.read_bytes()

#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator adoption: the list of what a product repository must change when the brand arrives, kept as data.

  adoption survey [--repo DIR[=LABEL]]... [--old-name TEXT]... [--old-colour #HEX]... [--old-colours-file FILE] [--keep GLOB::REASON]...
      Reads each repository (read only, with ripgrep) for brand slots: old names, old colours, icon and logo files, package and platform
      metadata (package.json, Cargo.toml, plists, Tauri, AppStream, web manifests, Android, .desktop) and README badges. Writes
      adoption.json (rows, progress, pins) and ADOPTION.md in the project. Every match becomes a row or goes on "Kept, not counted".
      Run again to add rows (never to change or remove one). Never edits a repository: the survey proves its own read-only claim.
  adoption add --repo LABEL --file PATH --find TEXT --change TEXT [--lines 15-33]
      Appends one row for a change no search finds (logic, a platform rule the product repository gets wrong). Pinned like any row.
  adoption status [--set N|N-M|N,M=to do|doing|done]...    show or update progress (doing and done need G6)
  adoption verify                                          the pins, the numbering, the accounting and ADOPTION.md against adoption.json
  adoption render                                          write ADOPTION.md again from adoption.json
"""
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
sys.path.insert(0, str(HERE / "adaptlib"))
import adoptdata as ad  # noqa: E402
from _common import (EXIT_CANNOT, EXIT_FAIL, EXIT_USAGE, Parser, Report, add_project_arg, confine, fail, find_project, main_guard,  # noqa: E402
                     read_state, require_gate, today, write_bytes_if_changed)

RG_BASE = ["--no-config", "--hidden", "--glob", "!.git", "--no-require-git"]
MAX_LINES = 200
HINT_RG = "Install ripgrep (macOS: brew install ripgrep; Linux: apt install ripgrep; Windows: winget install BurntSushi.ripgrep.MSVC)."

KEEP_RULES = [   # (kind, pattern, reason): the first rule that matches decides
    ("name", r"(^|/)(package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|Cargo\.lock|Gemfile\.lock|poetry\.lock|uv\.lock|composer\.lock|"
             r"go\.sum|Package\.resolved|Podfile\.lock|bun\.lockb?)$", "lock file: the package manager writes it, nobody edits it by hand"),
    ("name", r"(^|/)(CHANGELOG|CHANGES|HISTORY|RELEASES?|NEWS|RELEASE[-_]NOTES)[^/]*$", "change history: it records what was true then and is not rewritten"),
    ("name", r"(^|/)(LICEN[CS]E|COPYING|NOTICE|AUTHORS|CONTRIBUTORS)[^/]*$", "legal text: it names its legal owner, which is not a brand slot"),
    ("name", r"\.(min\.js|min\.css|map)$", "minified or source-map output: regenerate it from its source"),
    ("name", r"(^|/)(dist|build|target|out|\.next|\.nuxt|coverage|vendor|Pods|DerivedData|__pycache__|node_modules)/",
     "generated or vendored output: fix the source and rebuild"),
]
META = [   # (file pattern, slot-line pattern)
    (r"(^|/)package\.json$", r'^\s*"(name|productName|displayName|description|author|homepage|icon|icons|repository|appId|bugs)"\s*:'),
    (r"(^|/)Cargo\.toml$", r"^\s*(name|description|authors|homepage|repository|documentation|icon)\s*="),
    (r"(^|/)pyproject\.toml$", r"^\s*(name|description|authors|homepage|repository|icon)\s*="),
    (r"(^|/)pubspec\.yaml$", r"^\s*(name|description|homepage|repository|launcher_icons)\s*:"),
    (r"\.plist$", r"<key>(CFBundle\w*|NS\w*UsageDescription|UILaunchScreen\w*|LSApplicationCategoryType|NSHumanReadableCopyright)</key>"),
    (r"(^|/)(tauri\.conf\.json5?|Tauri\.toml)$", r'^\s*"?(productName|identifier|icon|icons|title|longDescription|shortDescription|publisher|copyright|category|homepage|name)"?\s*[:=]'),
    (r"\.(metainfo|appdata)\.xml$", r"<(id|name|summary|description|developer_name|developer|icon|launchable|url|project_license|metadata_license|branding|color|screenshot)\b"),
    (r"(^|/)(manifest\.json|[^/]+\.webmanifest)$", r'^\s*"(name|short_name|description|icons|theme_color|background_color|start_url|id|display)"\s*:'),
    (r"(^|/)AndroidManifest\.xml$", r"(android:(label|icon|roundIcon)=|package=)"),
    (r"\.desktop$", r"^(Name|GenericName|Comment|Icon|Exec|StartupWMClass)(\[[^\]]+\])?="),
    (r"\.nuspec$", r"<(id|title|authors|owners|description|iconUrl|icon|projectUrl|copyright)\b"),
]
IDENT = [   # (file pattern, value pattern with one group, what it names): what an owner may have to rename
    (r"(^|/)package\.json$", r'^\s{0,4}"name"\s*:\s*"([^"]+)"', "package name"),
    (r"(^|/)Cargo\.toml$", r'^name\s*=\s*"([^"]+)"', "crate name"),
    (r"(^|/)pyproject\.toml$", r'^name\s*=\s*"([^"]+)"', "project name"),
    (r"(^|/)pubspec\.yaml$", r"^name:\s*(\S+)", "package name"),
    (r"(^|/)tauri\.conf\.json5?$", r'"identifier"\s*:\s*"([^"]+)"', "app identifier"),
    (r"(^|/)tauri\.conf\.json5?$", r'"productName"\s*:\s*"([^"]+)"', "product name"),
    (r"\.plist$", r"<key>CFBundleIdentifier</key>\s*<string>([^<]+)</string>", "bundle identifier"),
    (r"(^|/)AndroidManifest\.xml$", r'package="([^"]+)"', "Android package"),
    (r"\.(metainfo|appdata)\.xml$", r"<id>([^<]+)</id>", "AppStream id"),
]
PATH_RE = re.compile(r"(?i)(^|/)(favicon[^/]*|apple-touch-icon[^/]*|[^/]*(icon|logo|wordmark|lockup|brandmark|launcher|splash|og-image|social-preview|opengraph)[^/]*)"
                     r"\.(svg|png|ico|icns|jpe?g|webp|gif|pdf|bmp)$")
ASSET_DIR_RE = re.compile(r"\.(appiconset|iconset|icon|imageset|solidimagestack|colorset)$")
BADGE_RE = re.compile(r"(?i)(shields\.io|badge\.svg|badgen\.net|/badge[/?.]|!\[[^\]]*\]\([^)]*(logo|banner|header|icon)[^)]*\)|<img[^>]+(logo|banner|header|icon))")
README_RE = re.compile(r"(?i)(^|/)README[^/]*\.(md|markdown|rst|txt|adoc)$")


def rg_path() -> str:
    import shutil
    p = shutil.which("rg")
    if not p:
        fail(EXIT_CANNOT, f"ripgrep (rg) not found on PATH: the survey needs it. {HINT_RG}")
    return p


EXCLUDE: list[str] = []   # extra --glob arguments (the brand project itself, when it lives inside a repository)


def run_rg(rg: str, repo: Path, label: str, args: list[str]) -> bytes:
    cp = subprocess.run([rg, *RG_BASE, *EXCLUDE, *args, "."], cwd=repo, capture_output=True, stdin=subprocess.DEVNULL, timeout=600)
    if cp.returncode not in (0, 1):
        fail(EXIT_CANNOT, f"ripgrep failed in {label} (exit {cp.returncode}): {cp.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return cp.stdout


def list_files(rg: str, repo: Path, label: str) -> list[str]:
    out = run_rg(rg, repo, label, ["--files", "--null"])
    files = [p.decode("utf-8", "replace") for p in out.split(b"\0") if p]
    return sorted(f[2:] if f.startswith("./") else f for f in files)


def snapshot(repo: Path, files: list[str]) -> str:
    h = hashlib.sha256()
    for f in files:
        try:
            st = os.lstat(repo / f)
            h.update(f"{f}\0{st.st_size}\0{st.st_mtime_ns}\n".encode("utf-8", "replace"))
        except OSError:
            h.update(f"{f}\0gone\n".encode("utf-8", "replace"))
    return h.hexdigest()


def git_head(repo: Path) -> str:
    try:
        cp = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short=8", "HEAD"], capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return "no git head"
    return cp.stdout.strip() if cp.returncode == 0 and cp.stdout.strip() else "no git head"


def rg_matches(rg: str, repo: Path, label: str, patterns: list[str], fixed: bool) -> list[tuple[str, int, str]]:
    if not patterns:
        return []
    args = ["--json", "-n", "-i"] + (["-F"] if fixed else [])
    for p in patterns:
        args += ["-e", p]
    out = []
    for ln in run_rg(rg, repo, label, args).splitlines():
        rec = json.loads(ln)
        if rec.get("type") != "match":
            continue
        d = rec["data"]
        pth = d["path"].get("text") or ""
        if pth.startswith("./"):
            pth = pth[2:]
        lt = d["lines"].get("text")
        if lt is None:
            import base64
            lt = base64.b64decode(d["lines"].get("bytes", "")).decode("utf-8", "replace")
        out.append((pth, d["line_number"], lt.rstrip("\r\n")))
    return out


def recount(rg: str, repo: Path, label: str, names: list[str], colours: list[str]) -> dict[str, int]:
    """Matching lines of the name and colour searches, counted again with a second ripgrep run in another output mode (per-file counts for names,
    plain text lines for colours) and none of survey's own code (no --json parse, no row bookkeeping). The accounting row compares this with the hits."""
    out = {"name": 0, "colour": 0}
    pats = [v for n in names for v in name_variants(n)]
    if pats:
        args = ["--count", "--null", "-i", "-F"]
        for p in pats:
            args += ["-e", p]
        for rec in run_rg(rg, repo, label, args).split(b"\n"):
            if rec:
                out["name"] += int(rec.rsplit(b"\0", 1)[1])
    cpats = [p for c in colours for p in colour_patterns(c)]
    if cpats:
        exact = [re.compile(py, re.I) for _rg, py in cpats]
        args = ["-n", "--null", "--no-heading", "--color", "never", "-i"]
        for r_, _py in cpats:
            args += ["-e", r_]
        for rec in run_rg(rg, repo, label, args).split(b"\n"):
            if rec:
                text = rec.split(b"\0", 1)[1].split(b":", 1)[1].decode("utf-8", "replace")
                if any(x.search(text) for x in exact):
                    out["colour"] += 1
    return out


def name_variants(term: str) -> list[str]:
    t = re.sub(r"\s+", " ", term.strip())
    words = re.split(r"[\s_\-.]+", t)
    cand = [t, "-".join(words), "_".join(words), "".join(words)]
    return list(dict.fromkeys(c for c in cand if c))


def norm_colour(c: str) -> str:
    m = re.fullmatch(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", c.strip())
    if not m:
        fail(EXIT_USAGE, f"--old-colour {c!r} is not a hex colour (#rgb or #rrggbb)")
    h = m.group(1).lower()
    return "#" + (h if len(h) == 6 else "".join(ch * 2 for ch in h))


def colour_patterns(c: str) -> list[tuple[str, str]]:
    """(ripgrep pattern, exact Python pattern) per way of writing the colour. ripgrep's default engine has no look-around, so it over-selects
    (a longer hex run) and the Python pattern, which ends in a look-ahead, keeps only the exact colour."""
    h = c[1:]
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    pats = [(rf"(#|0x){h}", rf"(#|0x){h}(?![0-9a-fA-F])"), (rf"rgba?\(\s*{r}\s*,\s*{g}\s*,\s*{b}\s*[,)]", rf"rgba?\(\s*{r}\s*,\s*{g}\s*,\s*{b}\s*[,)]")]
    if h[0::2] == h[1::2]:
        pats.append((rf"#{h[0::2]}", rf"#{h[0::2]}(?![0-9a-fA-F])"))
    return pats


def keep_reason(relpath: str, keeps: list[dict]) -> str | None:
    for k in keeps:
        if fnmatch.fnmatch(relpath, k["glob"]):
            return f"kept by the owner ({k['glob']}): {k['reason']}"
    for _kind, pat, why in KEEP_RULES:
        if re.search(pat, relpath):
            return why
    return None


def pack_names(project: Path) -> dict[str, list[str]]:
    f = project / "assets" / "manifest.json"
    out: dict[str, list[str]] = {}
    if f.is_file():
        for r in json.loads(f.read_text(encoding="utf-8")).get("artefacts", []):
            out.setdefault(Path(r["path"]).name.lower(), []).append(r["path"])
    return out


CHANGE = {
    "name": "Replace the old name where people read it (titles, labels, copy). Identifiers (bundle id, package name, repository URL) are renames: see LAUNCH.md.",
    "colour": "Replace with the matching token value from assets/tokens/ (light and dark); check the contrast pair it sits in.",
    "meta": "Check each slot against the new brand: name, description, icon path, theme and background colours, author, homepage.",
    "badge": "Check the header image and the badges: logo or banner from the pack, labels and colours for the new name.",
}


def survey_repo(rg: str, repo: Path, label: str, rid: str, names: list[str], colours: list[str], keeps: list[dict]):
    """-> (files, hits) where a hit is (category, file, line, text); path hits have line 0 and the directory as the file."""
    files = list_files(rg, repo, label)
    hits: list[tuple[str, str, int, str]] = []
    for f, ln, text in rg_matches(rg, repo, label, [v for n in names for v in name_variants(n)], True):
        hits.append(("name", f, ln, text))
    cpats = [p for c in colours for p in colour_patterns(c)]
    exact = [re.compile(py, re.I) for _rg, py in cpats]
    for f, ln, text in rg_matches(rg, repo, label, [r for r, _py in cpats], False):
        if any(x.search(text) for x in exact):
            hits.append(("colour", f, ln, text))
    idents: list[dict] = []
    for f in files:
        for fp, slot in META:
            if re.search(fp, f):
                try:
                    text = (repo / f).read_text(encoding="utf-8", errors="replace")
                except OSError as e:
                    fail(EXIT_CANNOT, f"cannot read {label}/{f}: {e}")
                for i, line in enumerate(text.splitlines(), 1):
                    if re.search(slot, line):
                        hits.append(("meta", f, i, line))
                if not keep_reason(f, keeps):
                    seen_kinds = set()
                    for ip, vp, what in IDENT:
                        if re.search(ip, f) and what not in seen_kinds:
                            m = re.search(vp, text, re.M)
                            if m:
                                seen_kinds.add(what)
                                idents.append({"repo": rid, "file": f, "line": text.count("\n", 0, m.start(1)) + 1, "what": what, "value": m.group(1)})
                break
        if README_RE.search(f):
            try:
                text = (repo / f).read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                fail(EXIT_CANNOT, f"cannot read {label}/{f}: {e}")
            for i, line in enumerate(text.splitlines(), 1):
                if BADGE_RE.search(line):
                    hits.append(("badge", f, i, line))
        if PATH_RE.search(f) or any(ASSET_DIR_RE.search(seg) for seg in f.split("/")[:-1]):
            segs = f.split("/")[:-1]
            d = next((("/".join(segs[:i + 1])) for i, s in enumerate(segs) if ASSET_DIR_RE.search(s)), "/".join(segs) or ".")
            hits.append(("path", d, 0, f.rsplit("/", 1)[-1]))
    return files, hits, idents


def main() -> int:
    ap = Parser(prog="brand-creator adoption", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("survey", help="read the repositories for brand slots and write adoption.json and ADOPTION.md")
    add_project_arg(s)
    s.add_argument("--repo", action="append", default=[], metavar="DIR[=LABEL]", help="a target repository (repeatable; read only). Without it the repositories of the earlier survey are read again")
    s.add_argument("--old-name", action="append", default=[], metavar="TEXT", help="an old brand name to find (repeatable; its hyphen, underscore and joined forms too, any case)")
    s.add_argument("--old-colour", action="append", default=[], metavar="#HEX", help="an old brand colour to find (repeatable)")
    s.add_argument("--old-colours-file", metavar="FILE", help="one colour per line (lines starting // are comments)")
    s.add_argument("--keep", action="append", default=[], metavar="GLOB::REASON", help="a path pattern (repo-relative) to list as kept, not counted, with the reason")
    s.add_argument("--replace-terms", action="store_true", help="forget the names and colours of the earlier survey (they are otherwise kept and searched again)")
    ad_ = sub.add_parser("add", help="append a hand-written row (a code change)")
    add_project_arg(ad_)
    ad_.add_argument("--repo", required=True, metavar="LABEL", help="the repository's label, as in ADOPTION.md")
    ad_.add_argument("--file", required=True, help="the file in that repository")
    ad_.add_argument("--find", required=True, help="a text to find the place by (line numbers drift)")
    ad_.add_argument("--change", required=True, help="what to change there, in a sentence")
    ad_.add_argument("--lines", default="", help="line numbers as read now: N, N-M, N,M")
    st = sub.add_parser("status", help="show the counts, or set the progress of rows")
    add_project_arg(st)
    st.add_argument("--set", action="append", default=[], metavar="ROWS=STATE", help="rows as N, N-M or N,M,..; state to do, doing or done (doing and done need G6)")
    st.add_argument("--json", action="store_true")
    v = sub.add_parser("verify", help="check adoption.json (pins, numbering, accounting) and that ADOPTION.md is what it renders")
    add_project_arg(v)
    r = sub.add_parser("render", help="write ADOPTION.md from adoption.json")
    add_project_arg(r)
    a = ap.parse_args()
    project = find_project(a.project)
    name = str(read_state(project).get("name", "") or read_state(project).get("slug", "") or "Brand")
    return {"survey": do_survey, "add": do_add, "status": do_status, "verify": do_verify, "render": do_render}[a.cmd](a, project, name)


def write_both(project: Path, doc: dict, name: str) -> list[str]:
    ch = []
    if write_bytes_if_changed(confine(project, ad.FILE, what="adoption.json"), ad.dumps(doc)):
        ch.append(ad.FILE)
    if write_bytes_if_changed(confine(project, ad.DOC, what="ADOPTION.md"), ad.render(doc, name).encode("utf-8")):
        ch.append(ad.DOC)
    return ch


def need_doc(project: Path) -> dict:
    doc = ad.load(project)
    if doc is None:
        fail(EXIT_USAGE, "no adoption.json: run `brand-creator adoption survey --repo <dir>` first")
    return doc


def do_survey(a, project: Path, name: str) -> int:
    rg = rg_path()
    doc = ad.load(project) or ad.empty(str(read_state(project).get("slug", "")))
    bad = ad.verify(doc) if doc["rows"] else []
    if bad:
        fail(EXIT_FAIL, "adoption.json is not consistent, so a survey would build on it: " + "; ".join(bad[:3]) + " (`brand-creator adoption verify`)")
    root = Path(os.path.realpath(project))
    # repositories: stored ones plus the ones named now; an id is never reused or renumbered
    repos = {r["label"]: dict(r) for r in doc["repos"]}
    next_id = max([int(r["id"][1:]) for r in doc["repos"]] + [0]) + 1
    for spec in a.repo:
        p, sep, label = spec.rpartition("=")
        if not sep or "/" in label or os.sep in label:   # no label given (a path may hold an '=')
            p, label = spec, ""
        d = Path(p).expanduser()
        if not d.is_dir():
            fail(EXIT_USAGE, f"--repo {p}: not a folder")
        real = Path(os.path.realpath(d))
        if real == root or root in real.parents:
            fail(EXIT_USAGE, f"--repo {p} is the brand project itself or a folder inside it: name a product repository")
        label = label.strip() or re.sub(r"[^A-Za-z0-9._-]+", "-", real.name) or "repo"
        e = repos.get(label, {"label": label})
        if "id" not in e:
            e["id"] = f"r{next_id}"
            next_id += 1
        e["path"] = os.path.relpath(real, root).replace(os.sep, "/")
        repos[label] = e
    if not repos:
        fail(EXIT_USAGE, "no repository: pass --repo DIR (repeatable), or survey one first")
    ordered = list(repos.values())
    doc["repos"] = [{"id": e["id"], "label": e["label"], "path": e["path"]} for e in ordered]
    # terms
    names = [] if a.replace_terms else list(doc["terms"]["names"])
    colours = [] if a.replace_terms else list(doc["terms"]["colours"])
    for n in a.old_name:
        if len(n.strip()) < 3:
            fail(EXIT_USAGE, f"--old-name {n!r} is shorter than 3 characters: it would match everything")
        names.append(n.strip())
    raw_cols = list(a.old_colour)
    if a.old_colours_file:
        f = Path(a.old_colours_file).expanduser()
        if not f.is_file():
            fail(EXIT_USAGE, f"--old-colours-file {a.old_colours_file}: not a file")
        raw_cols += [ln.strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.strip().startswith("//")]
    colours += [norm_colour(c) for c in raw_cols]
    names, colours = list(dict.fromkeys(names)), list(dict.fromkeys(colours))
    doc["terms"] = {"names": names, "colours": colours}
    keeps = list(doc.get("keeps", []))
    for k in a.keep:
        g, sep, why = k.partition("::")
        if not sep or not g.strip() or not why.strip():
            fail(EXIT_USAGE, f"--keep needs GLOB::REASON, got {k!r}")
        keeps.append({"glob": g.strip(), "reason": why.strip()})
    doc["keeps"] = list({(k["glob"], k["reason"]): k for k in keeps}.values())
    rep = Report("adoption", project, renderer="n/a (read-only survey)")
    mf = project / "assets" / "manifest.json"
    if mf.is_file():
        rep.inputs.append(mf)
    packs = pack_names(project)
    found: dict[tuple, dict] = {}
    kept: dict[tuple, dict] = {}
    idents_all: list[dict] = []
    total_hits = 0
    own: dict[str, int] = {"name": 0, "colour": 0}      # the survey's name and colour hits, and what recount() finds
    indep: dict[str, int] = {"name": 0, "colour": 0}
    heads: dict[str, str] = {}
    for e in ordered:
        repo = Path(os.path.realpath(root / e["path"]))
        if not repo.is_dir():
            fail(EXIT_USAGE, f"repository {e['label']} ({e['path']}) is not a folder; pass --repo again")
        EXCLUDE.clear()
        if repo in root.parents:   # the brand project lives inside this repository: its own files are not the repository's slots
            EXCLUDE.extend(["--glob", "!" + root.relative_to(repo).as_posix() + "/**"])
        before_files = list_files(rg, repo, e["label"])
        before = snapshot(repo, before_files)
        files, hits, idents = survey_repo(rg, repo, e["label"], e["id"], names, colours, doc["keeps"])
        after = snapshot(repo, list_files(rg, repo, e["label"]))
        rep.add(f"read-only:{e['label']}", "pass" if before == after else "fail", "the repository was not changed during the survey",
                detail="the list of files, sizes and modification times is the same before and after" if before == after
                else "files, sizes or modification times changed while the survey ran: something else wrote to the repository (the survey writes nothing there)")
        rep.add(f"survey:{e['label']}", "info", "repository read", detail=f"{len(files)} files listed, {len(hits)} slot matches")
        for cat in own:
            own[cat] += sum(1 for h in hits if h[0] == cat)
        for cat, n in recount(rg, repo, e["label"], names, colours).items():
            indep[cat] += n
        heads[e["id"]] = git_head(repo)
        idents_all += [i for i in idents]
        for cat, f, ln, text in hits:
            total_hits += 1
            why = keep_reason(f if cat != "path" else f + "/", doc["keeps"])
            tgt, key = (kept, (e["id"], cat, f, why)) if why else (found, (e["id"], cat, f))
            ent = tgt.setdefault(key, {"lines": [], "hits": 0, "find": text, "files": []})
            ent["hits"] += 1
            if cat == "path":
                ent["files"].append(text)
            elif len(ent["lines"]) < MAX_LINES:
                ent["lines"].append(ln)
    in_rows = sum(v["hits"] for v in found.values())
    in_kept = sum(v["hits"] for v in kept.values())
    bookkeeping = total_hits == in_rows + in_kept
    recounted = own == indep
    ok = bookkeeping and recounted
    why = []
    if not bookkeeping:
        why.append(f"{total_hits} matches but {in_rows} in rows and {in_kept} kept")
    if not recounted:
        why.append("the survey found " + ", ".join(f"{own[c]} {c} line(s)" for c in own) + " but a second ripgrep count finds "
                   + ", ".join(f"{indep[c]}" for c in own))
    rep.add("accounting", "pass" if ok else "fail", "every match is a row or kept",
            detail=(f"{total_hits} matches: {in_rows} in rows, {in_kept} kept, not counted; the {own['name']} name and {own['colour']} colour lines "
                    f"were counted again by a second ripgrep run and agree (meta, badge and icon-path matches come from the file list, so for them "
                    f"this row checks the bookkeeping)") if ok else "; ".join(why))
    # rows: existing ones stay as they are; new ones are appended in a fixed order
    existing = {ad.pin_of(r): r for r in doc["rows"] if r["category"] in ad.SURVEYED}
    order = {c: i for i, (c, _l) in enumerate(ad.CATEGORIES)}
    rid_order = {e["id"]: i for i, e in enumerate(ordered)}
    seen = {}
    added = []
    for key in sorted(found, key=lambda k: (order[k[1]], rid_order[k[0]], k[2])):
        rid, cat, f = key
        ent = found[key]
        pin = f"{rid}|{cat}|{f}"
        if pin in existing:
            seen[str(existing[pin]["n"])] = {"hits": ent["hits"], "lines": ent["lines"]}
            continue
        if cat == "path":
            base = [x.lower() for x in ent["files"]]
            same = sorted({p for b in base for p in packs.get(b, [])})
            change = (f"Replace these {ent['hits']} icon and logo file(s) with the pack's files and keep the file names the code refers to. "
                      + (f"The pack has files of the same names: {', '.join(same[:4])}{' and more' if len(same) > 4 else ''}." if same
                         else "No pack file has one of these names: map each to a slot in INVENTORY.md."))
            find = ", ".join(sorted(ent["files"])[:3]) + (", ..." if ent["hits"] > 3 else "")
        else:
            change, find = CHANGE[cat], ent["find"]
        n = len(doc["rows"]) + 1
        row = {"n": n, "category": cat, "repo": rid, "file": f, "lines": ent["lines"], "find": find, "change": change}
        doc["rows"].append(row)
        doc["pins"][str(n)] = ad.pin_of(row)
        seen[str(n)] = {"hits": ent["hits"], "lines": ent["lines"]}
        added.append(n)
    for pin, r in existing.items():
        seen.setdefault(str(r["n"]), {"hits": 0, "lines": []})
    doc["nrows"] = len(doc["rows"])
    doc["seen"] = seen
    doc["kept"] = [{"repo": k[0], "category": k[1], "file": k[2], "reason": k[3], "hits": v["hits"], "lines": v["lines"]}
                   for k, v in sorted(kept.items(), key=lambda kv: (rid_order[kv[0][0]], order[kv[0][1]], kv[0][2]))]
    doc["identifiers"] = sorted(idents_all, key=lambda i: (rid_order[i["repo"]], i["file"], i["what"]))
    doc["accounting"] = {"hits": total_hits, "in_rows": in_rows, "kept": in_kept}
    doc["survey"] = {"date": today(), "heads": heads}
    if not names and not colours:
        rep.add("terms", "warn", "old names and colours given", detail="none given: only icon and logo files, metadata and README badges were surveyed (pass --old-name and --old-colour)")
    else:
        rep.add("terms", "info", "what was searched", detail=f"{len(names)} old name(s) (with their hyphen, underscore and joined forms), {len(colours)} colour(s)")
    changed = write_both(project, doc, name)
    rep.add("rows", "info", "rows written", detail=f"{len(doc['rows'])} rows ({len(added)} new this run), {len(doc['kept'])} kept entries; wrote {', '.join(changed) or 'nothing (unchanged)'}")
    rc = rep.finish()
    print(f"\nADOPTION.md: {ad.headline(doc)}. {ad.sentence(doc)}")
    print("Line numbers may drift: find each place by its content. No repository was edited.")
    return rc


def do_add(a, project: Path, name: str) -> int:
    doc = need_doc(project)
    bad = ad.verify(doc)
    if bad:
        fail(EXIT_FAIL, "adoption.json is not consistent, so a row is not added to it: " + "; ".join(bad[:3]))
    rid = next((r["id"] for r in doc["repos"] if r["label"] == a.repo), None)
    if rid is None:
        fail(EXIT_USAGE, f"--repo {a.repo!r} is not a surveyed repository (labels: {', '.join(r['label'] for r in doc['repos'])})")
    for k in ("file", "find", "change"):
        if not getattr(a, k).strip():
            fail(EXIT_USAGE, f"--{k} is empty")
    lines = parse_rows(a.lines, 10 ** 7) if a.lines.strip() else []
    n = len(doc["rows"]) + 1
    row = {"n": n, "category": "change", "repo": rid, "file": a.file.strip(), "lines": lines[:MAX_LINES], "find": a.find.strip(), "change": a.change.strip()}
    doc["rows"].append(row)
    doc["pins"][str(n)] = ad.pin_of(row)
    doc["nrows"] = len(doc["rows"])
    write_both(project, doc, name)
    print(f"row {n} added (code change in {a.repo}: {row['file']})")
    return 0


def parse_rows(spec: str, n: int) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            fail(EXIT_USAGE, f"rows {spec!r}: use N, N-M or N,M")
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        if lo > hi or lo < 1 or hi > n:
            fail(EXIT_USAGE, f"rows {part!r}: the list has rows 1 to {n}")
        out += range(lo, hi + 1)
    return out


def do_status(a, project: Path, name: str) -> int:
    doc = need_doc(project)
    bad = ad.verify(doc)
    if bad:
        fail(EXIT_FAIL, "adoption.json is not consistent: " + "; ".join(bad[:3]))
    if a.set:
        changes = []
        for s in a.set:
            rows, sep, state = s.rpartition("=")
            state = state.strip().lower().replace("-", " ").replace("_", " ")
            if not sep or state not in ad.STATES:
                fail(EXIT_USAGE, f"--set {s!r}: use ROWS=STATE with STATE one of {', '.join(ad.STATES)}")
            changes += [(n, state) for n in parse_rows(rows, len(doc["rows"]))]
        if any(st != ad.STATES[0] for _n, st in changes):
            require_gate(project, "G6", for_what="Marking adoption rows doing or done")
        for n, st in changes:
            if st == ad.STATES[0]:
                doc["progress"].pop(str(n), None)
            else:
                doc["progress"][str(n)] = st
        write_both(project, doc, name)
        print(f"progress updated for {len(changes)} row(s)")
    c = ad.counts(doc)
    if a.json:
        print(json.dumps({"headline": ad.headline(doc), "counts": c, "rows": len(doc["rows"])}, indent=2))
    else:
        print(f"{ad.headline(doc)}: {ad.sentence(doc)}")
        todo = [r["n"] for r in doc["rows"] if ad.status_of(doc, r["n"]) != "done"]
        if todo:
            print("not done: " + ad.ranges(todo))
        still, _gone = ad.drift(doc)
        if still:
            print(f"warning: row(s) {ad.ranges(still)} are done but still match at the last survey")
    return 0


def do_verify(a, project: Path, name: str) -> int:
    doc = need_doc(project)
    bad = ad.verify(doc)
    f = project / ad.DOC
    want = ad.render(doc, name)
    if not f.is_file():
        bad.append(f"{ad.DOC} is missing: run `brand-creator adoption render`")
    elif f.read_text(encoding="utf-8") != want:
        bad.append(f"{ad.DOC} is not what adoption.json renders: it was edited by hand. Progress goes through `adoption status`, rows through `adoption survey`")
    for b in bad:
        print(f"FAIL: {b}", file=sys.stderr)
    if bad:
        return EXIT_FAIL
    print(f"adoption: consistent ({len(doc['rows'])} rows, pins match, {ad.DOC} is what the data renders)")
    return 0


def do_render(a, project: Path, name: str) -> int:
    doc = need_doc(project)
    bad = ad.verify(doc)
    if bad:
        fail(EXIT_FAIL, "adoption.json is not consistent, so it is not rendered: " + "; ".join(bad[:3]))
    ch = write_both(project, doc, name)
    print(f"{ad.DOC}: {'written' if ch else 'unchanged'}")
    return 0


main_guard(main)

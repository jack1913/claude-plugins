"""Everything the brand book tools read: the chapter registry, book/book.json, the BRAND-STATE view (edition, approval, decided
items), tokens, manifest, facts, and the counts that prose is allowed to quote. Standard library only.

book.py (the generator), book_lint.py (the gate), patch.py and collapse.py (the edit tools) share it, so a number or a rule has
one definition. See scripts/CONTRACT.md, "Brand book".
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from _common import EXIT_CANNOT, EXIT_USAGE, State, fail, read_state

# ---------------------------------------------------------------- the chapter registry

# id, default title, tiers that include it, and the rule that adds or drops it
CHAPTERS = [
    ("idea", "Idea", ("quick", "standard", "full"), "always"),
    ("mark", "The mark by size", ("quick", "standard", "full"), "always"),
    ("motion", "Motion", ("standard", "full"), "motion"),            # when motion/proof.json or motion/SPEC.md exists
    ("wordmark", "Wordmark and lockup", ("quick", "standard", "full"), "wordmark"),   # when assets/logo holds a wordmark or lockup
    ("endorsement", "Endorsement", ("standard", "full"), "family"),  # family modes only
    ("colour", "Colour", ("quick", "standard", "full"), "always"),
    ("type", "Type", ("standard", "full"), "always"),
    ("tone", "Tone and voice", ("standard", "full"), "opt-in"),     # BRAND-STATE book_chapters
    ("photography", "Photography", ("standard", "full"), "opt-in"),
    ("components", "Components", ("standard", "full"), "opt-in"),
    ("use", "In use", ("standard", "full"), "always"),
    ("files", "Files", ("quick", "standard", "full"), "always"),
    ("proof", "Proof", ("standard", "full"), "always"),
    ("donts", "Drawn don'ts", ("standard", "full"), "always"),
    ("family", "Family", ("standard", "full"), "family"),
    ("adoption", "Adoption", ("full",), "always"),
    ("launch", "Launch checklist", ("full",), "always"),
    ("changing", "Changing the brand", ("quick", "standard", "full"), "always"),
    ("history", "Design history", ("standard", "full"), "always"),
]
CHAPTER_IDS = [c[0] for c in CHAPTERS]
TITLES = {c[0]: c[1] for c in CHAPTERS}
OPT_IN = [c[0] for c in CHAPTERS if c[3] == "opt-in"]
FAMILY_MODES = ("family-member", "product-in-family")
CONFIG_FILE = "book/book.json"
CHAPTER_DIR = "book/chapters"
DEFAULT_OUTPUT = "book.html"
PDF_LABEL = "RGB, not print-ready"

DEFAULT_SIZES = [16, 20, 32, 48, 64, 128, 180]
LINT_DEFAULTS = {
    "history_chapter": "history",
    "forbidden": [],
    "scratch": [r"\bTODO\b", r"\bTBD\b", r"\bFIXME\b", r"\bXXX\b", r"lorem ipsum", r"\bscratch\b", r"\bdraft\b", r"/private\b/(?:tmp|var)",
                r"/(?:Users|home)/[A-Za-z0-9._-]+", r"\[\[fill", r"\(\.\.\.\)", r"\bplaceholder\b", r"\bnot yet decided\b"],
    "round": [r"\b[Rr]ound \d+\b", r"\bv[1-9]\b", r"\b[Ii]tem [a-g]\b", r"\b[Dd]ecision \d+\b", r"\b[Ww]hat changed\b",
              r"\b(?:first|second|third) pass\b", r"\b[Tt]he review board\b"],
    "status_words": ["coming soon", "launching", "launches", "launched", "now live", "live now", "available", "in development",
                     "in beta", "going live", "pre-order", "open for orders", "shipping soon"],
    "count_nouns": {"files": ["files", "file", "artefacts", "artefact", "artifacts", "artifact"], "slots": ["slots", "slot"],
                    "colours": ["colours", "colour", "colors", "color"], "pairs": ["pairs", "pair"], "roles": ["roles", "role"],
                    "sizes": ["sizes", "size"], "chapters": ["chapters", "chapter"]},
    "allow_external_links": [],
    "files_exclude": [],
}
CONFIG_DEFAULTS = {"schema": 1, "min_label_px": 12, "sizes": DEFAULT_SIZES, "fonts": [], "labels": {}, "output": DEFAULT_OUTPUT,
                   "lint": LINT_DEFAULTS}
LANG_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$")


def _check_type(key: str, value, default) -> None:
    if isinstance(default, bool) or not isinstance(default, (int, float)):
        ok = isinstance(value, type(default))
    else:
        ok = isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
    if not ok:
        fail(EXIT_USAGE, f"{CONFIG_FILE}: {key} has the wrong type or value ({value!r})")


def load_config(project: Path) -> tuple[dict, str]:
    """book/book.json merged over the defaults -> (config, source). An unknown key or a wrong type is exit 2 (a typo never falls back)."""
    import copy
    cfg = copy.deepcopy(CONFIG_DEFAULTS)
    f = project / CONFIG_FILE
    if not f.is_file():
        return cfg, "defaults (no book/book.json)"
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        fail(EXIT_USAGE, f"{CONFIG_FILE} is not valid JSON: {e}")
    if not isinstance(doc, dict):
        fail(EXIT_USAGE, f"{CONFIG_FILE} must be a JSON object")
    for k, v in doc.items():
        if k not in CONFIG_DEFAULTS:
            fail(EXIT_USAGE, f"{CONFIG_FILE}: unknown key {k!r} (known: {', '.join(CONFIG_DEFAULTS)})")
        if k == "schema":
            if v != 1:
                fail(EXIT_USAGE, f"{CONFIG_FILE}: unknown schema {v!r} (this version reads 1)")
        elif k == "lint":
            if not isinstance(v, dict):
                fail(EXIT_USAGE, f"{CONFIG_FILE}: lint must be an object")
            for lk, lv in v.items():
                if lk not in LINT_DEFAULTS:
                    fail(EXIT_USAGE, f"{CONFIG_FILE}: unknown key lint.{lk} (known: {', '.join(LINT_DEFAULTS)})")
                _check_type(f"lint.{lk}", lv, LINT_DEFAULTS[lk])
                cfg["lint"][lk] = lv
            for lk in ("scratch", "round", "status_words", "forbidden", "allow_external_links", "files_exclude"):
                for pat in cfg["lint"][lk]:
                    if not isinstance(pat, str) or not pat:
                        fail(EXIT_USAGE, f"{CONFIG_FILE}: lint.{lk} holds a non-string or empty entry")
                    if lk in ("scratch", "round"):
                        try:
                            re.compile(pat)
                        except re.error as e:
                            fail(EXIT_USAGE, f"{CONFIG_FILE}: lint.{lk}: {pat!r} is not a regular expression ({e})")
        else:
            _check_type(k, v, CONFIG_DEFAULTS[k])
            cfg[k] = v
    if not all(isinstance(s, int) and s > 0 for s in cfg["sizes"]) or not cfg["sizes"]:
        fail(EXIT_USAGE, f"{CONFIG_FILE}: sizes must be a non-empty list of positive integers")
    for ft in cfg["fonts"]:
        if not isinstance(ft, dict) or set(ft) - {"family", "file", "weight", "style"} or not {"family", "file"} <= set(ft):
            fail(EXIT_USAGE, f"{CONFIG_FILE}: each font is {{family, file, weight?, style?}}")
    if cfg["min_label_px"] < 10:
        fail(EXIT_USAGE, f"{CONFIG_FILE}: min_label_px {cfg['min_label_px']} is below 10 px, the smallest label a reader can be asked to read")
    return cfg, CONFIG_FILE


# ---------------------------------------------------------------- BRAND-STATE view

def parse_langs(raw) -> list[str]:
    if isinstance(raw, list):
        items = [str(x).strip() for x in raw]
    else:
        items = [x for x in re.split(r"[,\s]+", str(raw or "").strip()) if x]
    return items


def section_lines(st: State, heading: str) -> list[str]:
    """Lines of the `## <heading>` section of the BRAND-STATE body (without the heading)."""
    out, inside = [], False
    for ln in st.lines[st.end + 1:]:
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", ln)
        if m:
            if inside:
                break
            inside = m.group(2).lower() == heading.lower()
            continue
        if inside:
            out.append(ln)
    return out


def bullets(lines: list[str]) -> list[str]:
    return [m.group(1).strip() for ln in lines if (m := re.match(r"^\s*[-*]\s+(.*\S)\s*$", ln))]


def append_to_section(st: State, heading: str, line: str) -> None:
    """Append one bullet line to the end of the `## heading` section of the BRAND-STATE body (the section is created when missing)."""
    lines = st.lines
    start = next((i for i in range(st.end + 1, len(lines)) if re.match(rf"^##\s+{re.escape(heading)}\s*$", lines[i])), None)
    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", f"## {heading}", "", line, ""]
        return
    j = start + 1
    while j < len(lines) and not re.match(r"^#{1,6}\s", lines[j]):
        j += 1
    k = j
    while k - 1 > start and not lines[k - 1].strip():
        k -= 1
    prev = lines[k - 1] if k - 1 > start else ""
    if prev.strip() and not re.match(r"^\s*[-*]\s", prev):
        lines.insert(k, "")
        k += 1
    lines.insert(k, line)


def adoption_progress(project: Path) -> dict | None:
    """{"done": n, "total": n} from adoption.json (row progress), or None when there is no adoption.json. A file that is not an adoption record is exit 2."""
    f = project / "adoption.json"
    if not f.is_file():
        return None
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
        rows, prog = doc["rows"], doc["progress"]
        done = sum(1 for r in rows if prog.get(str(r["n"]), "to do") == "done")
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        fail(EXIT_USAGE, f"adoption.json is not an adoption record ({type(e).__name__}: {e}); run `brand-creator adoption verify`")
    return {"done": done, "total": len(rows)}


def state_view(project: Path) -> dict:
    """The part of BRAND-STATE.md (and FACTS.md, and the row progress of adoption.json) that the book depends on. A change here makes a built book stale; a change to
    anything else in BRAND-STATE.md (the phase, a review URL) does not."""
    st = read_state(project)
    d = st.data()
    gates = d.get("gates", {}) or {}
    langs = parse_langs(d.get("content_languages", ""))
    for code in langs:
        if not LANG_RE.match(code):
            fail(EXIT_USAGE, f"content_languages in BRAND-STATE.md has {code!r}, which is not a language code (for example pl or pl,en)")
    if not langs:
        fail(EXIT_USAGE, "no content language: set `content_languages:` in BRAND-STATE.md (the language of the brand's own text, for example "
                         "`brand-creator state --set content_languages=en`); the book never defaults it from the chat language")
    raw_ed = str(d.get("edition", "") or "").strip()
    if not re.fullmatch(r"[1-9][0-9]*", raw_ed):
        fail(EXIT_USAGE, "BRAND-STATE.md has no valid `edition:` (a whole number from 1); set it with `brand-creator state --set edition=1`")
    raw_ap = str(d.get("approved_edition", "") or "").strip()
    if raw_ap and not re.fullmatch(r"[1-9][0-9]*", raw_ap):
        fail(EXIT_USAGE, f"approved_edition in BRAND-STATE.md must be a whole number or empty, got {raw_ap!r}")
    bc = d.get("book_chapters", [])
    bc = parse_langs(bc) if not isinstance(bc, list) else [str(x).strip() for x in bc]
    for c in bc:
        if c not in CHAPTER_IDS:
            fail(EXIT_USAGE, f"book_chapters in BRAND-STATE.md names {c!r}, which is not a chapter (chapters: {', '.join(CHAPTER_IDS)})")
    g5 = str(gates.get("G5", "") or "").strip()
    g6 = str(gates.get("G6", "") or "").strip()
    rows = [r for r in st.directions()]
    view = {
        "name": str(d.get("name", "") or d.get("slug", "")), "slug": str(d.get("slug", "")),
        "tier": str(d.get("tier", "quick")), "architecture": str(d.get("architecture", "standalone")),
        "mark_source": str(d.get("mark_source", "")), "content_languages": langs,
        "edition": int(raw_ed), "approved_edition": int(raw_ap) if raw_ap else None,
        "g5": g5, "g6": g6, "adoption": adoption_progress(project), "book_chapters": bc,
        "directions": rows,
        "rules": [b for b in bullets(section_lines(st, "Rules (G4)")) if b.lower().startswith("(rule)")],
        "decided": [b for b in bullets(section_lines(st, "Liked, rejected, decided")) if b.lower().startswith("decided")],
        "edition_log": bullets(section_lines(st, "Edition log")),
        "collapsed": bullets(section_lines(st, "Collapsed")),
    }
    if view["mark_source"] not in ("generated", "authored-vector", "existing"):
        fail(EXIT_USAGE, "BRAND-STATE.md has no valid `mark_source:` (generated | authored-vector | existing)")
    return view


def approval(view: dict) -> tuple[str, str]:
    """-> ("approved", date) when G5 is recorded for the current edition, else ("pending", "")."""
    if view["g5"] and view["approved_edition"] == view["edition"]:
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\b", view["g5"])
        return "approved", (m.group(1) if m else "")
    return "pending", ""


def view_sha(view: dict, facts_rows: list[dict]) -> str:
    h = hashlib.sha256(json.dumps({"view": view, "facts": facts_rows}, sort_keys=True, ensure_ascii=False).encode())
    return h.hexdigest()


# ---------------------------------------------------------------- facts, manifest, tokens, logos

def facts(project: Path) -> list[dict]:
    """Rows of the first table of FACTS.md as {fact, value, source, confirmed} (lower-case header names)."""
    f = project / "FACTS.md"
    if not f.is_file():
        return []
    rows, header = [], None
    for ln in f.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s.startswith("|"):
            if header and rows:
                break
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        if header is None:
            header = [c.lower() for c in cells]
            continue
        row = dict(zip(header, cells))
        if row.get("fact") and not row["fact"].startswith("<!--") and any(v for k, v in row.items() if k != "fact"):
            rows.append(row)
    return rows


def fact_value(rows: list[dict], label: str) -> str | None:
    for r in rows:
        if r.get("fact", "").strip().lower() == label.strip().lower():
            return r.get("value", "")
    return None


PRESS_KIT_EMITTER = "presskit"


def manifest_rows(project: Path, *, with_press_kit: bool = False) -> list[dict]:
    """The manifest rows the book accounts for. The press kit is left out: it contains the book's PDF, so the book cannot name the kit's hash
    (a book that listed it could never be current), and the kit must not make the book stale when it is rebuilt."""
    f = project / "assets" / "manifest.json"
    if not f.is_file():
        return []
    try:
        rows = json.loads(f.read_text(encoding="utf-8")).get("artefacts", [])
    except ValueError:
        fail(EXIT_USAGE, "assets/manifest.json is not valid JSON")
    return rows if with_press_kit else [r for r in rows if r.get("emitter") != PRESS_KIT_EMITTER]


def press_kit_rows(project: Path) -> list[dict]:
    return [r for r in manifest_rows(project, with_press_kit=True) if r.get("emitter") == PRESS_KIT_EMITTER]


def manifest_view_sha(project: Path) -> str:
    """A hash of the manifest as the book reads it (see manifest_rows). Reports record it instead of listing assets/manifest.json as an input,
    so rebuilding the press kit, which changes the manifest, leaves the book reports current."""
    keep = ("path", "sha256", "bytes", "emitter", "slot", "size", "band")
    rows = sorted(({k: r.get(k) for k in keep} for r in manifest_rows(project)), key=lambda r: r["path"])
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def logo_files(project: Path) -> list[Path]:
    d = project / "assets" / "logo"
    return sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in (".svg", ".png")) if d.is_dir() else []


def tokens(project: Path) -> tuple[dict, Path]:
    f = project / "assets" / "tokens" / "tokens.json"
    if not f.is_file():
        fail(EXIT_CANNOT, "assets/tokens/tokens.json not found; run `brand-creator tokens` first (the book reads the built tokens)")
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
        doc["modes"]["light"], doc["modes"]["dark"]
    except (ValueError, KeyError):
        fail(EXIT_USAGE, "assets/tokens/tokens.json is not a brand-creator tokens.json (no light and dark modes)")
    return doc, f


def token_hexes(doc: dict) -> set[str]:
    """Every colour the brand's tokens define, as lower-case #rrggbb."""
    out = set()
    for v in doc.get("primitives", {}).values():
        if isinstance(v, dict) and v.get("hex"):
            out.add(v["hex"].lower())
    for mode in doc.get("modes", {}).values():
        for v in mode.values():
            if isinstance(v, dict) and v.get("hex"):
                out.add(v["hex"].lower())
    return out


DURATION_GROUPS = ("duration.", "motion.")   # the starter tokens name them motion.*; older projects and Acme use duration.*


def motion_durations_ms(doc: dict) -> list[float]:
    """Durations of the `duration.*` and `motion.*` tokens in milliseconds (a value that is not a duration, a curve, is skipped)."""
    out = []
    for k, v in doc.get("other", {}).items():
        if k.startswith(DURATION_GROUPS):
            m = re.fullmatch(r"\s*([0-9.]+)\s*(ms|s)\s*", str(v))
            if m:
                out.append(float(m.group(1)) * (1000 if m.group(2) == "s" else 1))
    return sorted(set(out))


# ---------------------------------------------------------------- chapters and counts

def has_motion(project: Path) -> bool:
    return (project / "motion" / "proof.json").is_file() or (project / "motion" / "SPEC.md").is_file()


def has_wordmark(project: Path) -> bool:
    return any(re.match(r"^(wordmark|lockup)", p.stem) and p.suffix.lower() == ".svg" for p in logo_files(project))


def chapters_for(project: Path, view: dict) -> list[str]:
    """The chapters this book has: the tier's set, plus the rule of each (motion when something moves, a wordmark chapter when the
    artwork has one, endorsement and family in the family modes) and the opt-in chapters named in BRAND-STATE `book_chapters`."""
    tier = view["tier"]
    out = []
    for cid, _title, tiers, rule in CHAPTERS:
        if tier not in tiers and cid not in view["book_chapters"]:
            continue
        if rule == "motion" and not has_motion(project) and cid not in view["book_chapters"]:
            continue
        if rule == "wordmark" and not has_wordmark(project) and cid not in view["book_chapters"]:
            continue
        if rule == "family" and view["architecture"] not in FAMILY_MODES and cid not in view["book_chapters"]:
            continue
        if rule == "opt-in" and cid not in view["book_chapters"]:
            continue
        out.append(cid)
    return out


def counts(project: Path, cfg: dict, doc: dict, chapters: int | None = None) -> dict[str, int]:
    """The numbers prose may quote, from data. Never typed: {{count:name}} in a chapter, data-count="name" in the HTML."""
    rows = manifest_rows(project)
    c = {
        "files": len({r["path"] for r in rows}),
        "slots": len({r["slot"] for r in rows if r.get("slot")}),
        "colours": len(doc.get("primitives", {})),
        "pairs": len(doc.get("pairs", [])),
        "roles": len(doc["modes"]["light"]),
        "sizes": len(cfg["sizes"]),
        "artwork": len(logo_files(project)),
        "emitters": len({r.get("emitter") for r in rows if r.get("emitter")}),
    }
    if chapters is not None:
        c["chapters"] = chapters
    return c


COUNT_NAMES = ("files", "slots", "colours", "pairs", "roles", "sizes", "artwork", "emitters", "chapters")


def sha8(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:8]

"""Everything the brand book tools read: the chapter registry, book/book.json, the BRAND-STATE view (edition, approval, decided
items), tokens, manifest, facts, and the counts that prose is allowed to quote. Standard library only.

book.py (the generator), book_lint.py (the gate), patch.py and collapse.py (the edit tools) share it, so a number or a rule has
one definition. See scripts/CONTRACT.md, "Brand book".
"""
from __future__ import annotations

import hashlib
import json
import re
import shlex
from decimal import Decimal
from pathlib import Path

from _common import EXIT_CANNOT, EXIT_USAGE, State, fail, frames_report_tool, motion_proof_kind, read_state, sha256_file   # frames_report_tool: read as bookdata.frames_report_tool (bookgen, the tests)

# ---------------------------------------------------------------- the chapter registry

# id, default title, tiers that include it, and the rule that adds or drops it
CHAPTERS = [
    ("idea", "Idea", ("quick", "standard", "full"), "always"),
    ("mark", "The mark by size", ("quick", "standard", "full"), "always"),
    ("motion", "Motion", ("standard", "full"), "motion"),            # when motion/proof.json, motion/SPEC.md or motion/motion.json exists
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
APPROVED = "APPROVED"   # the cover's approval stamp word, and the English label that `labels` in book/book.json translates

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
    if not isinstance(cfg["labels"], dict):
        fail(EXIT_USAGE, f"{CONFIG_FILE}: labels must be an object of language code to its labels")
    for lg, tr in cfg["labels"].items():
        if not (isinstance(tr, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in tr.items())):
            fail(EXIT_USAGE, f"{CONFIG_FILE}: labels.{lg} must be an object of English word to its translation, all text")
        if APPROVED in tr and not tr[APPROVED].strip():
            fail(EXIT_USAGE, f"{CONFIG_FILE}: labels.{lg}.{APPROVED} is the cover's approval stamp: write the word as text, or leave the entry out")
    return cfg, CONFIG_FILE


def stamp_word(cfg: dict, lang: str) -> str:
    """The word of the cover's approval stamp in `lang` (the book's first content language): its labels entry for APPROVED in book/book.json, else
    APPROVED. English is never translated: its labels are the English words, as the generator's T() has it."""
    return APPROVED if lang == "en" else cfg["labels"].get(lang, {}).get(APPROVED, APPROVED).strip()


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
    rows = sorted(({**{k: r.get(k) for k in keep}, **({"superseded": True} if r.get("superseded") else {})} for r in manifest_rows(project)),
                  key=lambda r: r["path"])   # `superseded` only where it is set, so a manifest without one hashes as it always did
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
    """Motion is decided once the project has a motion proof, the prose spec, or motion/motion.json (on or off: a brand that does not move says so)."""
    return any((project / "motion" / f).is_file() for f in ("proof.json", "SPEC.md", "motion.json"))


def has_wordmark(project: Path) -> bool:
    """A wordmark or lockup in assets/logo: wordmark*.svg and lockup*.svg, or <id>-wordmark.svg and <id>-lockup.svg of one of several marks."""
    return any(re.search(r"(^|-)(wordmark|lockup)(-|$)", p.stem) and p.suffix.lower() == ".svg" for p in logo_files(project))


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


# ---------------------------------------------------------------- the stills of a page case (motion/frames/<case>/, written by `frames`)

FRAMES_DIR = "motion/frames"


def num_text(v: float, places: int = 3) -> str:
    """A number as plain short text: 240, 3.5, 16.67 (no exponent, no trailing zeros)."""
    s = f"{v:.{places}f}"
    s = s.rstrip("0").rstrip(".") if "." in s else s
    return "0" if s in ("", "-0") else s


def curve_css(c: list) -> str:
    """A curve as tokens.css writes it: cubic-bezier(0.2, 0, 0, 1), the numbers as plain decimals (1 and not 1.0, 0.0000001 and not 1e-07)."""
    def plain(n) -> str:
        s = str(n) if isinstance(n, int) else format(Decimal(repr(float(n))), "f")
        return s.rstrip("0").rstrip(".") if "." in s else s
    return "cubic-bezier(" + ", ".join(plain(n) for n in c) + ")"


def case_folder(name: str) -> str:
    """A case name as the folder `frames` writes its stills to (letters, digits, . _ -; a leading . or - dropped): twin of caseFolder in render.mjs."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(name)).lstrip(".-")


def case_slug(name: str) -> str:
    """A case name as the id part of a demo's controls and animations: lower case letters and digits joined by single hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")


def frames_folders(project: Path) -> list[str]:
    """The case folders of motion/frames/ that hold a frames.json, in name order."""
    d = project / FRAMES_DIR
    return sorted(p.name for p in d.iterdir() if (p / "frames.json").is_file()) if d.is_dir() else []


def frames_orphans(project: Path) -> list[str]:
    """The folders of motion/frames/ with no frames.json (stills of a run that was cut short, or a file that was moved away), in name order."""
    d = project / FRAMES_DIR
    return sorted(p.name for p in d.iterdir() if p.is_dir() and not (p / "frames.json").is_file()) if d.is_dir() else []


def read_frames(project: Path, folder: str) -> tuple[dict | None, list[str]]:
    """motion/frames/<folder>/frames.json as `frames` writes it -> (the document, []) or (None, what is wrong with it). Every file it names must lie in the folder."""
    where = f"{FRAMES_DIR}/{folder}/frames.json"
    try:
        doc = json.loads((project / where).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, [f"{where} cannot be read as JSON ({e})"]
    if not isinstance(doc, dict):
        return None, [f"{where} is not a JSON object"]
    bad = []

    def num(v) -> bool:
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def sha(v) -> bool:
        return isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) is not None

    def inside(v) -> bool:
        return v.startswith(f"{FRAMES_DIR}/{folder}/") and ".." not in v.split("/")

    if doc.get("schema") != 1:
        bad.append(f"schema is {doc.get('schema')!r}, this version reads 1")
    bad += [f"{k} is missing" for k in ("case", "proof", "page", "selector") if not (isinstance(doc.get(k), str) and doc[k])]
    if isinstance(doc.get("proof"), str) and doc["proof"] and (Path(doc["proof"]).is_absolute() or ".." in Path(doc["proof"]).parts):
        bad.append("proof must be a path inside the project (the book reads it, and records it as an input)")
    if not (num(doc.get("length_ms")) and doc["length_ms"] > 0):
        bad.append("length_ms must be a number above 0")
    if not (num(doc.get("scale")) and doc["scale"] > 0):
        bad.append("scale must be a number above 0")
    size = doc.get("size")
    if not (isinstance(size, list) and len(size) == 2 and all(num(x) and x > 0 for x in size)):
        bad.append("size must be [width, height] in css px")
    frames = doc.get("frames")
    if not (isinstance(frames, list) and frames and all(isinstance(f, dict) and num(f.get("percent")) and 0 <= f["percent"] <= 100 and num(f.get("ms"))
                                                       and isinstance(f.get("file"), str) and sha(f.get("sha256")) for f in frames)):
        bad.append("frames must be a non-empty list of {percent from 0 to 100, ms, file, sha256}")
    for k in ("strip", "reduced"):
        if not (isinstance(doc.get(k), dict) and isinstance(doc[k].get("file"), str) and sha(doc[k].get("sha256"))):
            bad.append(f"{k} must be {{file, sha256}}")
    if not bad:
        out = next((f for f in [*(x["file"] for x in frames), doc["strip"]["file"], doc["reduced"]["file"]] if not inside(f)), None)
        if out:
            bad.append(f"it lists {out}, which is not in {FRAMES_DIR}/{folder}/ (the folder was renamed or moved: move it back, or run `frames` again)")
    return (None, [f"{where}: {p}" for p in bad]) if bad else (doc, [])


def frames_command(doc: dict, case: str | None = None) -> str:
    """The `frames` command that writes the points of this frames.json again: --count N when they are N evenly spread ones, else --at with the percentages;
    with `case`, for that case only (--case)."""
    pcts = [f["percent"] for f in doc["frames"]]
    n = len(pcts)
    even = [0.0] if n == 1 else [100 * i / (n - 1) for i in range(n)]
    arg = f"--count {n}" if all(abs(a - b) < 0.011 for a, b in zip(pcts, even)) else "--at " + ",".join(num_text(p, 2) for p in pcts)
    return f"brand-creator frames {shlex.quote(doc['proof'])}" + (f" --case {shlex.quote(case)}" if case else "") + f" {arg}"


def flipbook_steps(doc: dict) -> list[tuple[str, str]]:
    """(percent, x of the object-position) of the keyframes of a replay: each still from its percent on, in time order (the stills of `--at` may come in any order),
    and a keyframe at 0 and at 100 whatever the points are, so the flipbook never falls back to the element's own position. The strip is N stills of the width w
    side by side, so still i is shown by shifting it left by i x w css px. The build writes these and book-lint reads them back."""
    w, at = doc["size"][0], {}
    for i, f in enumerate(doc["frames"]):
        at[f["percent"]] = i   # two stills at one percent: the later one is shown
    at.setdefault(0, at[min(at)])
    at.setdefault(100, at[max(at)])
    return [(num_text(p, 2), "0" if i == 0 else f"-{num_text(i * w)}px") for p, i in sorted(at.items())]


def frames_proof(project: Path, folder: str) -> str | None:
    """The proof a frames.json names, or None when the file cannot be read or names none (read_frames says what is wrong with it)."""
    try:
        v = json.loads((project / FRAMES_DIR / folder / "frames.json").read_text(encoding="utf-8")).get("proof")
    except (OSError, ValueError, AttributeError):
        return None
    return v if isinstance(v, str) else None


def gated_frames_folders(project: Path) -> list[str]:
    """The case folders of motion/frames/ the book can show: those whose frames.json names a gated proof of the project. The stills of a try-out proof (under
    rounds/, history/ or removed-*/) or of a proof that is gone are never shown, so they are no input of a book. A frames.json that cannot be read counts: the
    build says so, and the book has to notice when it is mended."""
    return [f for f in frames_folders(project) if motion_proof_kind(project, frames_proof(project, f)) == "gated"]


def proof_page_cases(project: Path, proof: str) -> list[str] | None:
    """The names of the page cases of a motion proof, or None when the file cannot be read as a proof (no file, not JSON, no list of cases)."""
    try:
        cases = json.loads((project / proof).read_text(encoding="utf-8"))["cases"]
        return [c["name"] for c in cases if isinstance(c, dict) and c.get("type") == "page" and isinstance(c.get("name"), str)]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def proof_stills(project: Path, proof: str) -> list[str]:
    """The cases of `proof` that have stills in motion/frames/ for the book to show: the case of each frames.json that names the proof and is still a page case of it (the
    build leaves a case the proof no longer has out, and says so). A frames.json that cannot be read names no proof."""
    pages, out = proof_page_cases(project, proof), []
    for folder in frames_folders(project):
        try:
            doc = json.loads((project / FRAMES_DIR / folder / "frames.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and doc.get("proof") == proof and isinstance(doc.get("case"), str) and (pages is None or doc["case"] in pages):
            out.append(doc["case"])
    return out


def replay_skip(project: Path, folder: str, doc: dict) -> str | None:
    """Why the build leaves out the replay of motion/frames/<folder>/ (the sentence of its warning), else None. The build warns with this sentence, and book-lint
    asks the same question to know which stills a book has to show: one the build left out, and said so, is no failure of the book."""
    at, proof, case = f"{FRAMES_DIR}/{folder}", doc["proof"], doc["case"]
    kind = motion_proof_kind(project, proof)
    if kind != "gated":
        return (f"{at}/ holds the stills of {proof}, " + ("an exploration proof (under rounds/, history/ or removed-*/)" if kind == "exploration" else "a proof that no longer exists")
                + "; its replay is left out")
    cmd = frames_command(doc)
    if case_folder(case) != folder or not case_slug(case):
        return f"{at}/ holds the case {case!r}, which belongs in {FRAMES_DIR}/{case_folder(case) or '<a folder name>'}/; its replay is left out: run `{cmd}`"
    for key in ("strip", "reduced"):
        if not (project / doc[key]["file"]).is_file():
            return f"{doc[key]['file']} is listed in {at}/frames.json and does not exist; the replay of {case} is left out: run `{cmd}`"
    pages = proof_page_cases(project, proof)
    if pages is not None and case not in pages:
        return f"{case} is no longer a page case of {proof}: move {at}/ to removed-<date>/ (its replay is left out)"
    return None


def replayable(project: Path) -> list[tuple[str, dict]]:
    """[(folder, frames.json)] of the stills the build makes a replay of, in name order: readable, of a gated proof, of a page case that is still in its proof, with
    both pictures there, and the first of the cases that make one id."""
    out, slugs = [], set()
    for folder in gated_frames_folders(project):
        doc, _bad = read_frames(project, folder)
        if doc is None or replay_skip(project, folder, doc) is not None or case_slug(doc["case"]) in slugs:
            continue
        slugs.add(case_slug(doc["case"]))
        out.append((folder, doc))
    return out


def motion_is_off(project: Path) -> bool:
    """Whether motion/motion.json says nothing moves. A file that is absent or cannot be read is not "off": the build and `check` say what is wrong with it."""
    try:
        return json.loads((project / "motion" / "motion.json").read_text(encoding="utf-8")).get("motion") == "off"
    except (OSError, ValueError, AttributeError):
        return False


def shows_stills(project: Path, view: dict) -> bool:
    """Whether the book can replay stills: its chapter list has the Motion chapter and motion/motion.json does not say nothing moves. Only then are the stills of the gated
    proofs part of what its reports depend on (a Quick book, or one for a brand that does not move, is not made stale by `frames`)."""
    return "motion" in chapters_for(project, view) and not motion_is_off(project)


def frames_view(project: Path, view: dict) -> list[dict]:
    """[{path, sha256, strip, reduced}] of every gated proof's case folder: its frames.json (path and sha256) and the sha256 of its strip and of its reduced still, or "absent"
    (a picture frames.json lists, else strip.png or reduced.png): the list of the stills a book can show, empty for a book that shows none (see shows_stills). A report records
    it (frames_view_sha), so that `check` sees stills that appeared, went or changed after the book was built, and a strip that went and came back."""
    if not shows_stills(project, view):
        return []
    out = []
    for folder in gated_frames_folders(project):
        at = f"{FRAMES_DIR}/{folder}"
        doc, _bad = read_frames(project, folder)
        pics = {k: project / (doc[k]["file"] if doc else f"{at}/{k}.png") for k in ("strip", "reduced")}
        out.append({"path": f"{at}/frames.json", "sha256": sha256_file(project / at / "frames.json"), **{k: sha256_file(f) if f.is_file() else "absent" for k, f in pics.items()}})
    return out


def frames_view_sha(project: Path, view: dict) -> str:
    h = hashlib.sha256()
    for r in frames_view(project, view):
        h.update(f"{r['path']}\0{r['sha256']}\0{r['strip']}\0{r['reduced']}\n".encode())
    return h.hexdigest()


def frames_changed(project: Path, view: dict, recorded: str | None) -> bool:
    """Whether the stills of the gated proofs now in motion/frames/ are other than those a report recorded (its frames_view_sha). A report from before the key (None)
    is out of date only when there are stills now."""
    return bool(frames_view(project, view)) if recorded is None else recorded != frames_view_sha(project, view)


def frames_inputs(project: Path, view: dict) -> list[Path]:
    """The files a book's replays are made of: the frames.json of every gated proof and, for the readable ones, its strip, its reduced still and the proof (whether the
    case is still in it decides whether the book shows it). None for a book that shows no stills (see shows_stills)."""
    out = []
    for folder in gated_frames_folders(project) if shows_stills(project, view) else []:
        out.append(project / FRAMES_DIR / folder / "frames.json")
        doc, _bad = read_frames(project, folder)
        if doc:
            out += [project / doc["strip"]["file"], project / doc["reduced"]["file"], project / doc["proof"]]
    return [p for p in out if p.is_file()]

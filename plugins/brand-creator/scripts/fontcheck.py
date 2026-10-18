#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = ["fonttools==4.62.1", "brotli==1.1.0"]
# ///
"""brand-creator fontcheck: is this font fit for the brand's languages, and what does it allow?

Three separate answers per font file:
  1. Glyph coverage per language set (fontTools cmap). Language sets are data files (scripts/data/languages/<code>.json:
     en, pl, de, cs, fr, es, tr). The set comes from --lang, else from `content_languages:` in BRAND-STATE.md (the language
     of the brand's own text, not the chat language in `language:`); there is no default language of the plugin (Polish is
     one set among others) and an empty choice stops the run. A missing required letter fails; a missing typographic
     extra (quotes, dashes) warns. --text adds the characters of a name or tagline to verify.
  2. A licence hint read from the font's own name table (copyright, licence text and URL) and OS/2 fsType. It is a hint
     from the file, not legal advice; confirm at the foundry. A font that says nothing about its licence warns.
  3. The platform-font report: Chromium itself (`render.mjs fonts`, CSS.getPlatformFontsForNode) says which font it used
     for every character, with a control (a character the font does not hold must come back as another font). It needs
     the browser from `/brand-creator:setup`; `--no-platform` leaves it out on purpose and the report says so.
Fonts: --font FILE (repeatable, .ttf .otf .woff .woff2) or every font under assets/fonts/ of the project.
Default font budget (owner-adjustable rule): at most two open-licence, self-hostable families.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
from _common import (EXIT_CANNOT, EXIT_USAGE, Parser, Report, add_project_arg, fail, find_project, main_guard, plugin_root,  # noqa: E402
                     read_state, rel)

LANG_DIR = HERE / "data" / "languages"
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}
MAX_FAMILIES = 2
BASIC_LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
LICENCES = [  # (pattern over the name-table text, label)
    (re.compile(r"SIL Open Font License|\bOFL\b|openfontlicense\.org|scripts\.sil\.org/OFL", re.I), "SIL Open Font License (OFL)"),
    (re.compile(r"Apache License|apache\.org/licenses", re.I), "Apache License"),
    (re.compile(r"\bMIT License\b|opensource\.org/licenses/MIT", re.I), "MIT License"),
    (re.compile(r"Ubuntu Font Licen[cs]e", re.I), "Ubuntu Font Licence"),
]
OPEN = ("SIL Open Font License (OFL)", "Apache License", "MIT License", "Ubuntu Font Licence")
FSTYPE = {0: "installable embedding", 2: "restricted licence embedding", 4: "preview and print embedding", 8: "editable embedding"}


def languages() -> dict[str, dict]:
    out = {}
    for f in sorted(LANG_DIR.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        out[d["code"]] = d
    return out


def wanted_languages(a, project: Path, known: dict) -> list[str]:
    raw = a.lang or str(read_state(project).get("content_languages", "") or "")
    codes = [c for c in re.split(r"[\s,;]+", raw.lower()) if c]
    if not codes:
        fail(EXIT_USAGE, f"no language set: pass --lang <code>[,<code>] or set `content_languages:` in BRAND-STATE.md (the language of the "
                         f"brand's own text; the chat language is not used). Available: {', '.join(known)}")
    bad = [c for c in codes if c not in known]
    if bad:
        fail(EXIT_USAGE, f"no language set for {', '.join(bad)}. Available: {', '.join(known)} (add scripts/data/languages/<code>.json to extend)")
    return list(dict.fromkeys(codes))


def required(lang: dict) -> str:
    return (BASIC_LATIN if lang.get("basic_latin") else "") + lang["letters"] + lang["symbols"]


def licence_hint(font) -> tuple[str, str, dict]:
    """-> (status, detail, facts) from the name table and OS/2 fsType."""
    nm = font["name"]
    texts = {i: (nm.getDebugName(i) or "") for i in (0, 13, 14)}
    blob = " ".join(texts.values())
    found = next((lab for rx, lab in LICENCES if rx.search(blob)), None)
    fs_type = font["OS/2"].fsType if "OS/2" in font else None
    facts = {"copyright": texts[0][:160], "licence_text": texts[13][:200], "licence_url": texts[14], "fsType": fs_type, "recognised": found}
    notes = []
    status = "info"
    if found:
        notes.append(f"the name table says {found}" + (f" ({texts[14]})" if texts[14] else ""))
        if found not in OPEN:
            status = "warn"
    else:
        status = "warn"
        notes.append("the name table carries no recognisable licence text or URL: the file does not say what it allows, find the licence at the foundry before using it")
    if fs_type:
        bits = [FSTYPE[b] for b in (2, 4, 8) if fs_type & b]
        if fs_type & 2:
            status = "fail"
            notes.append("OS/2 fsType marks the font as restricted licence embedding: it may not be embedded or outlined into a logo without a licence")
        elif bits:
            status = "warn" if status != "fail" else status
            notes.append(f"OS/2 fsType {fs_type}: {', '.join(bits)}; web embedding may need a licence")
    notes.append("hint read from the file, not legal advice")
    return status, "; ".join(notes), facts


def platform_report(font_path: Path, chars: str) -> tuple[dict | None, str | None]:
    """-> (report, None) or (None, why it could not run)."""
    cmd = ["node", str(plugin_root() / "scripts" / "render.mjs"), "fonts", "--font-file", str(font_path), "--text", chars, "--json"]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        return None, "node not found on PATH (install Node 22+ and run /brand-creator:setup)"
    except subprocess.TimeoutExpired:
        return None, "render.mjs fonts timed out"
    if cp.returncode in (0, 1) and cp.stdout.strip():
        try:
            return json.loads(cp.stdout.strip().splitlines()[-1]), None
        except ValueError:
            pass
    return None, (cp.stderr.strip() or cp.stdout.strip() or f"render.mjs fonts exited {cp.returncode}")[:300]


def main() -> int:
    from fontTools.ttLib import TTFont
    ap = Parser(prog="brand-creator fontcheck", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--font", action="append", default=[], metavar="FILE", help="font file (repeatable); default: every font under assets/fonts/")
    ap.add_argument("--lang", help="language set code(s), comma separated (default: `content_languages:` in BRAND-STATE.md)")
    ap.add_argument("--text", default="", help="extra characters that must be covered (a brand name, a tagline)")
    ap.add_argument("--no-platform", action="store_true", help="leave the Chromium platform-font report out on purpose (printed in the report)")
    a = ap.parse_args()
    project = find_project(a.project)
    known = languages()
    codes = wanted_languages(a, project, known)
    paths = [Path(p).expanduser().resolve() for p in a.font]
    if not paths:
        fdir = project / "assets" / "fonts"
        paths = sorted(p for p in fdir.rglob("*") if p.suffix.lower() in FONT_EXT) if fdir.is_dir() else []
    if not paths:
        fail(EXIT_USAGE, "no fonts to check: pass --font FILE, or put the brand's font files under assets/fonts/")
    for p in paths:
        if not p.is_file() or p.suffix.lower() not in FONT_EXT:
            fail(EXIT_USAGE, f"{p}: not a font file (.ttf .otf .woff .woff2)")
    rep = Report("fontcheck", project, [p for p in paths if p.is_relative_to(project)], renderer="chromium (platform report)" if not a.no_platform else "no platform report (--no-platform)")
    rep.extra = {"languages": codes, "fonts": [rel(project, p) if p.is_relative_to(project) else p.name for p in paths], "language_files": [f"scripts/data/languages/{c}.json" for c in codes]}
    families: dict[str, list[str]] = {}
    for p in paths:
        shown = rel(project, p) if p.is_relative_to(project) else p.name
        try:
            font = TTFont(str(p), lazy=True)
        except Exception as e:  # fontTools raises several types for unreadable fonts
            rep.add(f"font:{shown}", "fail", "readable font file", detail=f"cannot read {shown}: {e}")
            continue
        names = font["name"]
        fam = names.getDebugName(16) or names.getDebugName(1) or p.stem
        families.setdefault(fam, []).append(shown)
        cmap = font.getBestCmap()
        all_required = ""
        for code in codes:
            lang = known[code]
            need = required(lang) + a.text
            miss = [c for c in dict.fromkeys(need) if ord(c) not in cmap and not c.isspace()]
            extras = [c for c in lang["extras"] if ord(c) not in cmap]
            all_required += need
            rep.add(f"cmap:{shown}:{code}", "fail" if miss else "pass", f"glyph coverage, {lang['name']} set",
                    detail=(f"missing {len(miss)} required character(s): {' '.join(f'{c} (U+{ord(c):04X})' for c in miss)}" if miss else
                            f"all {len(set(need))} required characters of the {lang['name']} set are in the font"),
                    missing=miss, missing_extras=extras, language=code)
            if extras:
                rep.add(f"extras:{shown}:{code}", "warn", f"typographic extras, {lang['name']} set", detail=f"not in the font: {''.join(extras)} (quotes, dashes or ellipsis the language sets with; the browser would fall back to another font for them)", missing=extras)
        status, detail, facts = licence_hint(font)
        rep.add(f"licence:{shown}", status, "licence hint (from the name table)", detail=detail, **facts)
        if a.no_platform:
            continue
        chars = "".join(dict.fromkeys(all_required))
        pr, why = platform_report(p, chars)
        if pr is None:
            rep.add(f"platform:{shown}", "skipped", "Chromium platform-font report", detail=f"not verified: {why}")
            continue
        if not pr["control"]["ok"]:
            rep.add(f"platform:{shown}", "skipped", "Chromium platform-font report", detail=f"not verified: the control failed (Chromium used the font for {pr['control']['char']} "
                                                                                             f"{pr['control']['codepoint']}, which it does not hold), so this report cannot tell coverage from fallback", control=pr["control"])
            continue
        rep.add(f"platform:{shown}", "fail" if pr["fallback"] else "pass", f"Chromium platform fonts ({pr['chromium']}), control passed",
                detail=(f"Chromium fell back to another font for: {' '.join(pr['fallback'])}" if pr["fallback"] else
                        f"Chromium used the font itself for all {len(pr['chars'])} characters; control {pr['control']['char']} {pr['control']['codepoint']} fell back as it should"),
                fallback=pr["fallback"], control=pr["control"])
    if a.no_platform:
        rep.add("platform", "info", "Chromium platform-font report", detail="--no-platform: left out on purpose; coverage rests on the cmap alone")
    if len(families) > MAX_FAMILIES:
        rep.add("budget:families", "warn", f"font budget (default: at most {MAX_FAMILIES} families, owner-adjustable)",
                detail=f"{len(families)} families: {', '.join(families)}")
    return rep.finish()


main_guard(main)

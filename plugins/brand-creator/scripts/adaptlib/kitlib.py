"""The brand kit as data: where it sits, what it holds, which version it is, and what it was made from.

The kit is the per-brand applied skill's folder (`.claude/skills/<slug>-brand/`) with more in it: the brand's own files copied in byte for byte at their
project paths under `brand/`, and `kit.json`, which records the sha256 of every generated file. SKILL.md is still written by `adapt.applied_skill_md`, from the kit's
own template (templates/applied-skill/kit-SKILL.md: the steps of `how_md`, the "## The kit" section, the owner's rules, the "never" list and the `map_md` map), and so is
brand.md (kit-brand.md: the colour, type, layout, mark, motion and claims sections the applied skill of a project without a kit holds). See scripts/CONTRACT.md ("kit").

Shared by `brand-creator kit` (scripts/kit.py) and `brand-creator check`. It sits beside adapt.py, outside scripts/lib/, for the same reason: a change here must
not make every pack stale (lib/stale.py hashes scripts/lib/*.py). Standard library only. No clock and no random numbers: the same inputs give the same bytes.

rules.json and facts.json (the G4 rules with ids, the pairs, the public facts) are made here too: `g4_rules`, `known_rule_ids`, `rules_doc`, `facts_doc`.
snippets/logo.html (the logo in light and dark, switched as tokens.css switches them) is made here too: `logo_html`.
The approved reference pages of site/ go in too, each only when its record validates and its page check and stills are current and passing, with what the page loads and a generated
`reference-pages/<id>/notes.md`: `reference_plan`, `page_sources`, `notes_md`. Everything the kit copies for them is read from the path that passed `confine`.
The approved masters of the project (everything under assets/masters/) go in too, byte for byte at their project path, a font in them by the font rule: `masters_plan`, `masters_sources`.
The owner's files are every file of the kit folder that is no generated file, no kit.json and no Finder `.DS_Store`: `owner_paths`. Five of them (EXTENDING.md, voice.md, visual.md, golden-rules.md,
recipes/web-page.md) are scaffolded once from templates/kit/ and never overwritten: `owner_plan`, `write_owner`.
kit.json records each one's sha256 (`owned`) and `content_sha` covers them, so an owner file added, edited or taken away moves the version at the next build.
`kit check` reads the kit with `files_check`, `link_check`, `fill_markers`, `version_problems`, `source_changes`, `owned_changes`, `tag_check` and `number_check`, and only ever from a plain file of the kit.

`plan(project)` is every generated file except kit.json, as {path in the kit: bytes}, with SKILL.md carrying the literal `<version>` in its version line. The
version is decided from what the plan holds (`content_sha`, `next_version`) and then put into SKILL.md (`with_version`), so SKILL.md never has to be written twice.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import posixpath
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote

from kitcopy import (ALL_SOURCE_KEYS, BRAND_MD, CHECKLIST_MD, CURRENT, INSTALL_PY, FACTS_JSON, FINDER_FILE, FONT_COPIED_KEYS, FONT_KEYS, FONT_NOT_COPIED_KEYS, GENERATED_DIRS, KIT_FILE,  # noqa: E402,F401
                     NOT_CURRENT, NOT_INSTALLED, OPTIONAL_SOURCE_KEYS, OWNED_ADDED, OWNED_CHANGED, OWNED_FILES, PAGE_KEYS, PREFIX, ROOT_FILES, RULES_JSON, SCHEMA, SKILL_FILE, SOURCE_KEYS,
                     STATUS_SHOWN, TOP_KEYS, WHY_BYTES, WHY_LINK, WHY_MISSING, _EDITION, _SHA, _VERSION, KitError, folder_state, font_problems,
                     generated_files_in, installed_version, is_owner_path, is_sha, json_object, not_current_text, owned_problems, owner_paths, owner_sorted,
                     paths_in, plain_file, problems, read_plain, recorded_path, reference_page_problems)
from kitcopy import compare as _compare  # noqa: E402

_json_object, _plain_file, _read_plain, _generated_files_in = json_object, plain_file, read_plain, generated_files_in   # the names these had before kitcopy
import adapt
import bookdata
import motionspec
import qa_rules
from _common import (EXIT_CANNOT, EXIT_FAIL, EXIT_USAGE, CliError, Report, confine, fail, plugin_root, plugin_version, sha256_bytes, sha256_file,
                     stale_inputs)

TOKENS_JSON = "assets/tokens/tokens.json"
TOKENS_CSS = "assets/tokens/tokens.css"
FACTS_FILE = "FACTS.md"
VERSION_PLACEHOLDER = "<version>"
REPORT = "assets/_checks/kit.json"                          # the report of `kit build`: the record of what was last written
APPLIED_REPORT = "assets/_checks/applied-skill.json"        # stands in for it when the kit takes over a skill file that `applied-skill` wrote
FONTS_DIR = "assets/fonts"                                  # the brand's font files and their licence texts
FONTCHECK_REPORT = "assets/_checks/fontcheck.json"          # where the licence, family, weight and style of each font are read from
FONTS_CSS = "snippets/fonts.css"
FONT_FORMATS = {".ttf": "truetype", ".otf": "opentype", ".woff": "woff", ".woff2": "woff2"}   # file extension -> the CSS format() name
UNREAD_FONT_FORMATS = (".ttc", ".otc", ".eot", ".dfont", ".pfb", ".pfm", ".pfa")   # font files fontcheck cannot read: a collection, an embedded-OpenType, a Mac suitcase, Type 1; the masters never copy these
OFL = "SIL Open Font License (OFL)"                         # the label of fontcheck's `recognised`
OFL_PHRASE = "SIL OPEN FONT LICENSE"                        # a licence text must hold it (any case)
LICENCE_NAMES = ("OFL", "LICENSE", "LICENCE")               # a licence text's file name starts with one of these (any case) ...
LICENCE_EXTS = ("", ".txt", ".md")                          # ... and has one of these extensions
FONTS_HEAD = "/* generated by brand-creator from assets/fonts/ and the fontcheck report; paths are relative to this file */"
FONTS_NOTE = "/* in a product: copy brand/assets/fonts/ into the product's own public or static folder and point each font source below at the path the site serves it from; a built site does not serve .claude/skills/ */"
LOGO_HTML = "snippets/logo.html"
LOGO_HEAD = "<!-- generated by brand-creator: the logo in light and dark, switched as tokens.css switches them; paths are relative to this file -->"
LOGO_NOTE = "<!-- in a product: copy brand/assets/logo/ into the product's own public or static folder and point each image below at the path the site serves it from; a built site does not serve .claude/skills/ -->"
DARK_TWIN = "-dark"                                         # assets/logo/<name>-dark.svg is the dark twin of assets/logo/<name>.svg
NO_FONTCHECK = "no current fontcheck report: run `brand-creator fontcheck`, then `kit build`"
MOTION_SPEC = "motion/SPEC.md"                              # the motion hand-off text: copied when it exists
MOTION_PROOF = "motion/proof.json"                          # when the brand moves, the page of each of its page cases is copied
DATA_SCHEMA = 1                                             # the schema of rules.json and facts.json (their own, not kit.json's)
RULE_WORDS = 6                                              # a G4 rule's id is the slug of its first six words
PROPOSAL = "plugin proposal"                                # rules.json downscale.from when qa/rules.json does not set the numbers
ON_GROUND_CSS = "snippets/on-ground.css"                    # one scope per ground the owner named, written from the `grounds` of tokens.json
UNJUDGED_OWNED = ("EXTENDING.md", "voice.md")               # the owner's Markdown files `kit:tags` and `kit:numbers` leave alone: a guide full of tag syntax, and prose; every other owner .md is judged
MASTERS_DIR = "assets/masters"                              # the masters the owner approved (ad, deck and other templates with their pictures, PDFs, PPTX and fonts): copied into the kit at their project path
OWNER_TEMPLATES = "templates/kit"                          # where the scaffolds are, below the plugin folder
_PLACEHOLDER = re.compile(r"\{\{(.*?)\}\}", re.S)              # a scaffold's placeholder: {{brand}} and {{skill}} are known, any other {{...}} (one that spans lines too) is refused
GROUNDS_HEAD = ("/* generated by brand-creator from the grounds in assets/tokens/tokens.json; load it after tokens.css; the first ground is the page ground and its "
                'colours are the base variables; put data-ground="<name>" on an element that sits on another ground */')

# The keys kit.json may hold. Each task that adds a key adds it here, so that `load` can refuse every other one.


def version_line(version: str) -> str:
    return f"Kit version {version} (kit.json)."


# ---------------------------------------------------------------- where the kit is, and reading kit.json

def kit_dir(project: Path) -> Path:
    return project / adapt.SKILL_DIR / adapt.skill_name(project)


def kit_rel(project: Path) -> str:
    """The kit folder as a project path: .claude/skills/<slug>-brand"""
    return f"{adapt.SKILL_DIR}/{adapt.skill_name(project)}"


def exists(project: Path) -> bool:
    """True when the project has a kit (a kit.json in the skill folder). A slug that cannot be a skill name has no skill folder, so no kit: False, as `check` treats it."""
    try:
        return (kit_dir(project) / KIT_FILE).is_file()
    except CliError:
        return False


def load(project: Path) -> dict:
    """kit.json as a document. A strict schema: an unknown key at any level is refused (exit 2) naming it, and so is a key that is missing or a value of the wrong shape."""
    name = f"{kit_rel(project)}/{KIT_FILE}"
    f = kit_dir(project) / KIT_FILE
    if not f.is_file():
        fail(EXIT_USAGE, f"no kit in this project ({name} not found): `brand-creator kit build --yes` writes it (opt-in at G5)")
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        fail(EXIT_USAGE, f"{name} is not valid JSON: {e}")
    bad = problems(doc)
    if bad:
        fail(EXIT_USAGE, f"{name}: {bad[0]}" + (f" (and {len(bad) - 1} more)" if len(bad) > 1 else ""))
    return doc


# ---------------------------------------------------------------- what the kit is made from

def drawings(rules: dict) -> list[str]:
    """Every band drawing qa/rules.json names, as written there: the top-level bands, then each mark's, each once."""
    out: list[str] = []
    for b in [*rules["bands"], *(b for m in rules["marks"].values() for b in m["bands"])]:
        if b["drawing"] not in out:
            out.append(b["drawing"])
    return out


def source_paths(project: Path) -> list[str]:
    """The project paths of the files the kit copies for the logo: the logo files and every band drawing, sorted, each once (as written, so a drawing that is
    not there yet is still named)."""
    rules, _ = qa_rules.load(project)
    return sorted({*adapt.logo_paths(project), *drawings(rules)})


def _sha_or_none(project: Path, rel: str) -> str | None:
    f = project / rel
    return sha256_file(f) if f.is_file() else None


def sources(project: Path) -> dict:
    """What the kit is made from, one sha256 per kind (null when the project has none of it): the state the adapters read (BRAND-STATE.md, FACTS.md and the
    motion spec, as `adapt.state_sha`), the two token files, qa/rules.json, FACTS.md, the motion files (`motion_sources`), the logo files with the band drawings, the fonts and the approved
    reference pages (`pages_source`), and, only when the project has files under assets/masters/, the masters (`masters_source`; the key is left out otherwise, so that the sources of a project
    without masters are the bytes they always were). kit.json records them, so a later run can tell what changed after the kit was built."""
    h = hashlib.sha256()
    for rel in source_paths(project):
        h.update(f"{rel}\0{_sha_or_none(project, rel) or 'missing'}\n".encode())
    out = {"state_sha": adapt.state_sha(project), "tokens": _sha_or_none(project, TOKENS_JSON), "tokens_css": _sha_or_none(project, TOKENS_CSS),
           "rules": _sha_or_none(project, qa_rules.RULES_FILE), "facts": _sha_or_none(project, FACTS_FILE), "motion": motion_source(project),
           "logos": h.hexdigest(), "fonts": fonts_source(project), "pages": pages_source(project)}
    if (masters := masters_source(project)) is not None:
        out["masters"] = masters
    return out


def sources_sha(project: Path, src: dict | None = None) -> str:
    """One sha256 over `sources` (computed again unless `src` is given)."""
    return sha256_bytes(json.dumps(src if src is not None else sources(project), sort_keys=True, ensure_ascii=False).encode("utf-8"))


def input_paths(project: Path) -> list[Path]:
    """The files a `kit` report lists as inputs, each only when the project has it: the token files, the logo files and band drawings, qa/rules.json, FACTS.md, the motion files, the fonts, and what the
    approved reference pages and the masters are made from (`page_input_rels`, `masters_sources`)."""
    rels = [TOKENS_CSS, TOKENS_JSON, *source_paths(project), qa_rules.RULES_FILE, FACTS_FILE, *motion_sources(project), *font_sources(project), *page_input_rels(project),
            *masters_sources(project)]
    return [project / r for r in rels if (project / r).is_file()]


# ---------------------------------------------------------------- fonts: OFL fonts are copied with their licence text, any other font is listed

def _under_fonts(project: Path, keep) -> list[str]:
    """The project paths (assets/fonts/...) of the files under assets/fonts/ whose name `keep` accepts, sorted. Links to folders are not followed."""
    top = confine(project, FONTS_DIR, what="font folder", read=True)
    out = []
    for root, _dirs, names in os.walk(top):
        out += [f"{FONTS_DIR}/{(Path(root) / n).relative_to(top).as_posix()}" for n in names if keep(n)]
    return sorted(out)


def font_files(project: Path) -> list[str]:
    """The .ttf, .otf, .woff and .woff2 files under assets/fonts/ (as fontcheck finds them), as project paths, sorted."""
    return _under_fonts(project, lambda n: Path(n).suffix.lower() in FONT_FORMATS)


def licence_texts(project: Path) -> list[str]:
    """The files under assets/fonts/ named like a licence text: OFL*, LICENSE* or LICENCE* (any case), with no extension or .txt or .md."""
    return _under_fonts(project, lambda n: n.upper().startswith(LICENCE_NAMES) and Path(n).suffix.lower() in LICENCE_EXTS)


def _font_file(project: Path, rel: str, what: str) -> bytes:
    f = confine(project, rel, what=what, read=True)
    if not f.is_file():
        fail(EXIT_FAIL, f"{what} {rel} cannot be read (a link to nothing?): remove it or restore it")
    return f.read_bytes()


def font_sources(project: Path) -> list[str]:
    """What the fonts of the kit are made from, as project paths: the font files, the licence texts and the fontcheck report. Empty when the project has no font file."""
    paths = font_files(project)
    return [*paths, *licence_texts(project), FONTCHECK_REPORT] if paths else []


def fonts_source(project: Path) -> str | None:
    """One sha256 over `font_sources` (a file that is not there counts as missing); None when the project has no font file."""
    rels = font_sources(project)
    if not rels:
        return None
    h = hashlib.sha256()
    for rel in rels:
        h.update(f"{rel}\0{_sha_or_none(project, rel) or 'missing'}\n".encode())
    return h.hexdigest()


def fontcheck_rows(project: Path) -> dict | None:
    """The rows of the fontcheck report by id, or None when there is no current report: none written, one that cannot be read, or one whose inputs changed since
    (`_common.stale_inputs`)."""
    f = project / FONTCHECK_REPORT
    try:
        doc = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
        if not (isinstance(doc, dict) and doc.get("tool") == "fontcheck" and isinstance(doc.get("results"), list)) or stale_inputs(project, doc):
            return None
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return {r["id"]: r for r in doc["results"] if isinstance(r, dict) and isinstance(r.get("id"), str)}


def _why_not(rows: dict | None, row: dict | None, has_text: bool) -> str | None:
    """Why a font is not copied (the sentence kit.json records), or None when it is. `row` is the font's `licence:` row of the fontcheck report."""
    if rows is None:
        return NO_FONTCHECK
    recognised = row.get("recognised") if row else None
    if not (isinstance(recognised, str) and recognised):
        return "the fontcheck report reads no licence for it"
    if recognised != OFL:
        return f"licence: {recognised}; only OFL fonts are copied (a default you may change): copy it into a product yourself, under its own licence"
    if not has_text:
        return "OFL by its name table, but no OFL licence text in assets/fonts/: add the font's OFL.txt"
    if not (isinstance(row.get("family"), str) and row["family"].strip()):
        return "the fontcheck report has no family name: run `brand-creator fontcheck` again"
    if type(row.get("weight")) is not int or not 1 <= row["weight"] <= 1000 or row.get("style") not in ("normal", "italic"):   # a weight CSS takes: a report from before fontcheck took 0 as 400 is no weight
        return "the fontcheck report has no weight or style for it: run `brand-creator fontcheck` again"
    return None


def _css(text: str) -> str:
    """Text for inside a double-quoted CSS string."""
    return re.sub(r"[\x00-\x1f\x7f]", " ", text).replace("\\", "\\\\").replace('"', '\\"')


def font_face(rel: str, row: dict) -> str:
    """The @font-face of one copied font (`rel` its project path): family, source (the path percent-encoded where a URL needs it), weight and style as the fontcheck
    report reads them, nothing else."""
    return ("@font-face {\n"
            f'  font-family: "{_css(row["family"])}";\n'
            f'  src: url("../{quote(PREFIX + rel)}") format("{FONT_FORMATS[Path(rel).suffix.lower()]}");\n'
            f"  font-weight: {row['weight']};\n"
            f"  font-style: {row['style']};\n"
            "}\n")


def font_plan(project: Path) -> dict:
    """What the kit does with the fonts of assets/fonts/: {"copied": [...], "not_copied": [...], "files": {path in the kit: bytes}, "fonts": [project paths],
    "current": whether a current fontcheck report was found}. `copied` and `not_copied` are kit.json's `fonts` key.

    A font is copied (to brand/assets/fonts/, at its path under assets/fonts/) only when the current fontcheck report reads it as SIL Open Font License (OFL) and
    names its family, and a licence text with "SIL OPEN FONT LICENSE" in it (any case) sits in assets/fonts/; each such text is copied along, once. snippets/fonts.css
    holds one @font-face per copied font, sorted by path. Any other font is listed with the reason, never copied."""
    paths = font_files(project)
    rows = fontcheck_rows(project) if paths else None
    texts = [t for t in licence_texts(project) if OFL_PHRASE in _font_file(project, t, "licence text").decode("utf-8", errors="replace").upper()] if paths else []
    copied, not_copied, files, faces = [], [], {}, []
    for rel in paths:
        row = (rows or {}).get(f"licence:{rel}")
        why = _why_not(rows, row, bool(texts))
        if why:
            not_copied.append({"file": rel, "reason": why})
            continue
        files[PREFIX + rel] = _font_file(project, rel, "font file")
        copied.append({"file": PREFIX + rel, "licence": OFL, "licence_files": [PREFIX + t for t in texts]})
        faces.append(font_face(rel, row))
    if copied:
        for t in texts:
            files[PREFIX + t] = _font_file(project, t, "licence text")
        files[FONTS_CSS] = (FONTS_HEAD + "\n" + FONTS_NOTE + "\n\n" + "\n".join(faces)).encode("utf-8")
    return {"copied": copied, "not_copied": not_copied, "files": files, "fonts": paths, "current": rows is not None}


def fonts_record(fonts: dict, *extras: dict | None) -> dict:
    """The `fonts` key of kit.json for a `font_plan`, and for the fonts the approved reference pages bring (the `reference_plan`) and the fonts of the masters (the `masters_plan`): `page_font_plan`
    decided both by the same rule. Sorted by path; a font that two of them name (a page that loads a font of the masters) is listed once."""
    brought = [e["fonts"] for e in extras if e and ((e.get("fonts") or {}).get("copied") or (e.get("fonts") or {}).get("not_copied"))]
    if not brought:
        return {"copied": fonts["copied"], "not_copied": fonts["not_copied"]}
    out = {}
    for key in FONT_KEYS:
        seen: dict[str, dict] = {}
        for f in [*fonts[key], *(f for b in brought for f in b.get(key, []))]:
            seen.setdefault(f["file"], f)
        out[key] = sorted(seen.values(), key=lambda f: f["file"])
    return out


# ---------------------------------------------------------------- fonts an approved reference page brings: the same rule as assets/fonts/
# A page folder can hold a font (site/<id>/fonts/X.ttf) and a page can load one from anywhere in the project (assets/web/X.ttf through url() in a stylesheet). D6 holds for these as well: such a font is
# copied only when the current fontcheck report has read it (a `licence:<project path>` row) as SIL Open Font License (OFL) and an OFL text sits in assets/fonts/ (`_why_not`, the rule of `font_plan`); any
# other is listed in kit.json `fonts.not_copied` with the reason and is not copied. A font under assets/fonts/ stays the font plan's, and snippets/fonts.css holds those fonts only.

FONTCHECK_FONTS = ("run `brand-creator fontcheck --font FILE` naming every font the kit holds outside assets/fonts/, this one included (fontcheck always "
                   "reads the fonts of assets/fonts/ too, and a run reads only the other fonts it names), then `kit build`")   # fontcheck's own default would leave a font outside assets/fonts/ unread


def is_font(rel: str) -> bool:
    """True for a path that names a .ttf, .otf, .woff or .woff2 file (any letter case), the files the font rule is about."""
    return Path(rel).suffix.lower() in FONT_FORMATS


def is_unread_font(rel: str) -> bool:
    """True for a path that names a font file of a format fontcheck cannot read (`UNREAD_FONT_FORMATS`, any letter case): the font rule can never find its licence, so the masters never copy it."""
    return Path(rel).suffix.lower() in UNREAD_FONT_FORMATS


def unread_font_why(rel: str) -> str:
    """Why a font of a format fontcheck cannot read is not copied (the sentence kit.json `fonts.not_copied` records)."""
    return (f"a font format fontcheck cannot read ({Path(rel).suffix.lower()}): only .ttf, .otf, .woff and .woff2 fonts are read, so its licence is unknown and it is not copied; "
            "copy it into a product yourself, under its own licence")


def page_font_plan(project: Path, found: dict[str, str]) -> dict:
    """The fonts the approved pages bring (`found`: project path -> how the page has it, as `_gather` reads them) by the rule of `font_plan`: {"copied": [kit.json `fonts.copied` entries], "not_copied": [kit.json
    `fonts.not_copied` entries], "files": {path in the kit: bytes} of the licence texts of the copied fonts (the font files are the page's own, read by `_gather`), "left": {project path: why} of the fonts not copied}.
    A font fontcheck has not read is not copied, and its reason says to check the fonts. Nothing is written."""
    out: dict = {"copied": [], "not_copied": [], "files": {}, "left": {}}
    if not found:
        return out
    rows = fontcheck_rows(project)
    texts = [t for t in licence_texts(project) if OFL_PHRASE in _font_file(project, t, "licence text").decode("utf-8", errors="replace").upper()]
    for rel in sorted(found):
        row = (rows or {}).get(f"licence:{rel}")
        if rows is None:
            why = f"no current fontcheck report: {FONTCHECK_FONTS}"
        elif row is None:
            why = f"fontcheck has not read it: {FONTCHECK_FONTS}"
        else:
            why = _why_not(rows, row, bool(texts))
        if why:
            out["not_copied"].append({"file": rel, "reason": why})
            out["left"][rel] = why
            continue
        out["copied"].append({"file": PREFIX + rel, "licence": OFL, "licence_files": [PREFIX + t for t in texts]})
        out["files"].update({PREFIX + t: _font_file(project, t, "licence text") for t in texts})
    return out


# ---------------------------------------------------------------- motion: the spec, its hand-off text and the demo page

def _proof_page(project: Path, page: str, case: str) -> str:
    """The plain project path of the page of a proof case (`./motion/demo.html`, `motion/../motion/demo.html` and an absolute path inside the project all name
    `motion/demo.html`), because the kit mirrors project paths. A page outside the project is exit 2."""
    what = f"the page of the proof case {case!r}"
    confine(project, page, what=what, read=True)
    joined = posixpath.normpath(posixpath.join(os.path.abspath(project), page))   # an absolute `page` stands as it is
    for root in (os.path.abspath(project), os.path.realpath(project)):             # the project folder named with or without its links resolved
        plain = posixpath.relpath(joined, root)
        if plain != ".." and not plain.startswith("../"):
            confine(project, plain, what=what, read=True)                          # the path the kit goes on to read is checked itself, not only the path it came from
            return plain
    fail(EXIT_USAGE, f"{MOTION_PROOF}: the page {page!r} of the case {case!r} cannot be named by a path below the project folder: write it as a plain path inside the project")


def proof_pages(project: Path) -> list[tuple[str, str]]:
    """The page cases of motion/proof.json as (case name, plain project path of its page), in the proof's order, a page named by two cases once. [] when there is no proof.
    A proof that cannot be read as {"cases": [...]}, or a page case with no page, is exit 2 naming it; a page outside the project is exit 2."""
    f = project / MOTION_PROOF
    if not f.is_file():
        return []
    try:
        cases = json.loads(f.read_text(encoding="utf-8"))["cases"]
        if not isinstance(cases, list):
            raise TypeError("cases")
    except (OSError, ValueError, KeyError, TypeError) as e:
        fail(EXIT_USAGE, f"{MOTION_PROOF} cannot be read as a motion proof ({type(e).__name__}); the kit copies the page of each page case: "
                         'write {"schema": 1, "cases": [...]} or take the file away')
    out: list[tuple[str, str]] = []
    for case in cases:
        if not (isinstance(case, dict) and case.get("type") == "page"):
            continue
        name, page = case.get("name"), case.get("page")
        if not (isinstance(page, str) and page.strip()):
            fail(EXIT_USAGE, f"{MOTION_PROOF}: the page case {name!r} names no page")
        plain = _proof_page(project, page.strip(), str(name))
        if plain not in [p for _n, p in out]:
            out.append((str(name), plain))
    return out


def motion_files(project: Path) -> dict[str, bytes]:
    """The motion files of the kit, {path in the kit: bytes}, each a byte copy at its project path: motion/motion.json when the project has it, motion/SPEC.md when it has
    it, and, when the spec says the brand moves ("on"), the page of each page case of motion/proof.json. A brand that decided nothing moves has its reason in the spec and
    no page; one that decided nothing has none of it. An invalid spec is exit 2 (`motionspec.load`); a proof page the project lacks is exit 1, one outside it exit 2."""
    spec = motionspec.load(project, tokens=False)   # the references to tokens are the `motion:spec` row of `check`
    files: dict[str, bytes] = {}
    if spec is not None:
        files[PREFIX + motionspec.FILE] = _project_file(project, motionspec.FILE, "motion spec")
    if (project / MOTION_SPEC).is_file():
        files[PREFIX + MOTION_SPEC] = _project_file(project, MOTION_SPEC, "motion hand-off")
    if spec is not None and spec["motion"] == "on":
        for name, page in proof_pages(project):
            f = confine(project, page, what=f"the page of the proof case {name!r}", read=True)   # read from the path that passed the check, never from another spelling of it
            if not f.is_file():
                fail(EXIT_FAIL, f"{MOTION_PROOF} names the page {page} for the case {name!r} but the project has no such file: add it, or change {MOTION_PROOF}")
            files[PREFIX + page] = f.read_bytes()
    return files


def motion_sources(project: Path) -> list[str]:
    """What the motion files of the kit are made from, as project paths, sorted: the files `motion_files` copies. It never stops a run: an invalid spec or a proof that
    cannot be read adds no page here (the build itself stops on it), so a later look at the sources can still say that they changed."""
    rels = [r for r in (motionspec.FILE, MOTION_SPEC) if (project / r).is_file()]
    try:
        spec = motionspec.load(project, tokens=False)
        if spec is not None and spec["motion"] == "on":
            rels += [page for _name, page in proof_pages(project)]
    except CliError:
        pass
    return sorted(set(rels))


def motion_source(project: Path) -> str | None:
    """One sha256 over `motion_sources` (the path and the file's sha256 of each; a file that is not there counts as missing); None when the kit holds no motion file."""
    rels = motion_sources(project)
    if not rels:
        return None
    h = hashlib.sha256()
    for rel in rels:
        h.update(f"{rel}\0{_sha_or_none(project, rel) or 'missing'}\n".encode())
    return h.hexdigest()


# ---------------------------------------------------------------- rules and facts as data: rules.json and facts.json

_FOLD = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ð": "d", "Ð": "D", "ħ": "h", "Ħ": "H", "ı": "i", "ß": "ss",
                       "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "þ": "th", "Þ": "TH"})   # letters NFKD does not take apart
_RULE_MARK = re.compile(r"^\s*\(rule\)\s*", re.I)
_RULE_FALLBACK = "rule"   # the id of a line with no ASCII letter or digit in it (a line in another script), numbered like any other repeat


def rule_text(line: str) -> str:
    """The words of a G4 line without its "(rule)" marker, white space collapsed."""
    return " ".join(_RULE_MARK.sub("", line).split())


def rule_id(text: str) -> str:
    """The id of a G4 rule from its words: the "(rule)" marker taken off, accents folded away (NFKD, and the letters it leaves whole: ł becomes l), lower-cased, apostrophes dropped,
    the first six words (runs of ASCII letters and digits; any other character, a dash or a letter with no ASCII form, ends a word) joined with `-`. `The mark keeps its clear space` is `the-mark-keeps-its-clear-space`. A line with no ASCII letter or
    digit gets `rule`. Two alike are told apart by `rule_ids`, not here."""
    decomposed = unicodedata.normalize("NFKD", rule_text(text).translate(_FOLD))
    folded = re.sub(r"['’‘`ʼ]", "", "".join(c for c in decomposed if not unicodedata.combining(c)).lower())   # accents off; a letter with no ASCII form is a separator, as a dash is
    return "-".join(re.findall(r"[a-z0-9]+", folded)[:RULE_WORDS]) or _RULE_FALLBACK


def rule_ids(lines: list[str]) -> list[str]:
    """The ids of the G4 rules in BRAND-STATE order: `rule_id`, and a repeat gets `-2`, `-3` (the next number not taken by another id, so `mark` twice and a rule `Mark 2` stay apart)."""
    seen: dict[str, int] = {}
    used: set[str] = set()
    out = []
    for line in lines:
        base = rule_id(line)
        n = seen.get(base, 0)
        while True:
            n += 1
            rid = base if n == 1 else f"{base}-{n}"
            if rid not in used:
                break
        seen[base] = n
        used.add(rid)
        out.append(rid)
    return out


def g4_rules(project: Path) -> list[dict]:
    """The recorded G4 rules of BRAND-STATE.md, in file order, as [{"id", "text"}]: the text without its "(rule)" marker, the id from `rule_ids`. A line with a `(...)` placeholder is no rule
    (`adapt.view` leaves it out)."""
    lines = adapt.view(project)["rules"]
    return [{"id": rid, "text": rule_text(line)} for rid, line in zip(rule_ids(lines), lines)]


def known_rule_ids(project: Path) -> list[str]:
    """Every id a `[rule: ...]` tag may name, each once: the G4 slugs (written bare), `page:<id>` for each page rule of qa/rules.json, and `site:<id>` for each choice of site/site.json
    tagged `rule` (none while the project has no site record). A site record that cannot be read stops the run (exit 1, naming it), and so does one whose `choices` is not a list (exit 2, naming the file and the key): `check` says what is wrong with it."""
    out = [r["id"] for r in g4_rules(project)]
    rules, _ = qa_rules.load(project)
    out += [f"page:{r['id']}" for r in rules["page"]["rules"]]
    if (project / "site" / "site.json").is_file():   # sitedata.SITE_FILE
        import sitedata   # scripts/boardlib: on the path of `kit` and `check`; read here only, so a command that never asks for rule ids does not need it
        choices = sitedata.load_site(project).get("choices", [])
        if not isinstance(choices, list):
            fail(EXIT_USAGE, f"site/site.json: choices must be a list of the pages' choices, not {json.dumps(choices)[:40]}: fix the record (`brand-creator check` says what is wrong with it)")
        out += [f"site:{c['id']}" for c in choices if isinstance(c, dict) and c.get("tag") == "rule" and isinstance(c.get("id"), str)]
    return list(dict.fromkeys(out))


def rules_doc(project: Path) -> dict:
    """rules.json as a document: schema, the approved edition, the G4 rules with ids, the size rule (`downscale`, and whether the numbers are the project's own), the bands with the
    kit path of each drawing, the contrast pairs with their computed ratios (2 decimals), the forbidden words, and, only when the project's own qa/rules.json has one, its `page` block
    verbatim (`qa_rules.load` always returns a merged `page`, so the file itself is read)."""
    v = adapt.view(project)
    rules, _ = qa_rules.load(project)
    ds = rules["downscale"]
    bands = [{"mark": None, **b} for b in rules["bands"]] + [{"mark": mid, **b} for mid, m in rules["marks"].items() for b in m["bands"]]
    doc_tokens, _ = bookdata.tokens(project)
    doc = {"schema": DATA_SCHEMA, "edition": v["approved_edition"], "g4": g4_rules(project),
           "downscale": {"accent_min_px": ds["accent_min_px"], "accent_rule_max_size": ds["accent_rule_max_size"],
                         "from": qa_rules.RULES_FILE if "downscale.accent_min_px" in rules["_from_file"] else PROPOSAL},   # the same reading as SKILL.md's size line
           "bands": [{"mark": b["mark"], "name": b["name"], "max_px": b["max_px"], "drawing": PREFIX + b["drawing"]} for b in bands],
           "pairs": [{"fg": p["fg"], "bg": p["bg"], "kind": p["kind"], "min": p["min"], "light": round(p["light"], 2), "dark": round(p["dark"], 2)} for p in adapt.pairs(doc_tokens)],
           "forbidden": v["forbidden"]}
    own = project / qa_rules.RULES_FILE
    if own.is_file():
        raw = json.loads(own.read_text(encoding="utf-8"))   # qa_rules.load has read and checked the file
        if "page" in raw:
            doc["page"] = raw["page"]
    return doc


def facts_doc(project: Path) -> dict:
    """facts.json as a document: the public rows of FACTS.md (`adapt.public_facts`: a contact or postal address row never) as {"fact", "value", "source", "confirmed"}."""
    return {"schema": DATA_SCHEMA, "facts": [{k: r.get(k, "") for k in ("fact", "value", "source", "confirmed")} for r in adapt.public_facts(project)]}


def json_bytes(doc: dict) -> bytes:
    """A generated JSON file: indent 2, no ASCII escapes, a trailing newline."""
    return (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


# ---------------------------------------------------------------- grounds: the page roles mapped to those of each ground the owner named

def css_var(token: str) -> str:
    """The custom property tokens.css writes for a semantic token (build_tokens.mjs `formatCss`): the dots of its name become hyphens, so `color.bg` is `--color-bg`."""
    return "--" + token.replace(".", "-")


def _and(items: list[str]) -> str:
    """`a`, `a and b`, `a, b and c`: the words of a reason that names several things."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _ground_gaps(doc: dict, e: dict) -> list[str]:
    """What the tokens give no colour for in one ground, as `focus in dark`: the ground itself and each of its five roles, in the modes where it is left out, null or
    no colour token (`adapt.ground_colours`). [] when the ground and all five roles have a colour in light and dark."""
    got = {m: adapt.ground_colours(doc, e, m) for m in ("light", "dark")}
    out = []
    for r in ("ground", *adapt.GROUND_ROLES):
        modes = [m for m in ("light", "dark") if got[m][r] is None]
        if modes:
            out.append(f"{'ground colour' if r == 'ground' else r} in {' and '.join(modes)}")
    return out


def ground_plan(project: Path) -> dict:
    """What the kit writes for the text grounds of tokens.json (`brand-creator tokens` writes them there only; tokens.css has no per-ground scope):
    {"state": "absent" | "proposal" | "named", "listed": the number of grounds listed, "page": the page ground's token name or None, "page_gaps": [...],
    "scoped": [the data-ground names written], "left_out": [(token name, why)], "files": {path in the kit: bytes}}.

    `snippets/on-ground.css` is written only when `named_by_owner` is a real date and the owner's words (`adapt.owner_named`): while the grounds are a proposal the model
    does not guess which colours text sits on. The first listed ground is the page ground and its five roles are the base variables (`css_var` of their tokens). Each other
    listed ground gets one rule, `[data-ground="<its token name without color.>"]`, with `background-color` set to its own colour and each base variable pointed at the
    ground's own role. Names are the ones tokens.css uses, never made up. A ground is left out (and named, with the reason) when the tokens give it no colour for the
    ground or a role in light or dark, so that no half a scope is written; when its data-ground name is already taken; when the page ground uses one token for two roles
    (focus and action both `color.accent`, say) and this ground gives those roles different colours, because a rule that sets one variable twice keeps only the later
    value (when the colours agree the variable is set once); and when it names a variable its own rule sets (`--color-text` as the ground's colour, say), because inside
    the rule that name no longer holds the page's colour. A role that names the page ground's own token is not set again: pointing a variable at itself makes it
    invalid, and the element keeps the value it inherits. With no page ground to map against, or no other ground left, nothing is written."""
    doc, _ = bookdata.tokens(project)
    named, entries = adapt.grounds_of(doc)
    plan = {"state": "absent", "listed": len(entries), "page": None, "page_gaps": [], "scoped": [], "left_out": [], "files": {}}
    if doc.get("grounds") is None:
        return plan
    plan["state"] = "named" if adapt.owner_named(named) else "proposal"
    if plan["state"] == "proposal" or not entries:
        return plan
    page = entries[0]
    plan["page"] = page["ground"]
    plan["page_gaps"] = _ground_gaps(doc, page)
    if plan["page_gaps"]:
        return plan
    base = {r: css_var(page["roles"][r]) for r in adapt.GROUND_ROLES}
    taken = {page["ground"].removeprefix("color.")}
    rules = []
    for e in entries[1:]:
        name, attr = e["ground"], e["ground"].removeprefix("color.")
        gaps = _ground_gaps(doc, e)
        if gaps:
            plan["left_out"].append((name, f"the tokens give no {', '.join(gaps)}"))
            continue
        if attr in taken:
            plan["left_out"].append((name, f'data-ground="{attr}" is already used by a ground listed before it'))
            continue
        mine = {r: css_var(e["roles"][r]) for r in adapt.GROUND_ROLES}
        want: dict[str, dict[str, str]] = {}                                    # each base variable, with what this ground points each of its roles at
        for r in adapt.GROUND_ROLES:
            want.setdefault(base[r], {})[r] = mine[r]
        split = [f"the page ground uses {v} for {_and(list(w))}, and this ground gives them different colours ({_and(list(dict.fromkeys(w.values())))}): a scope sets a variable once"
                 for v, w in want.items() if len(set(w.values())) > 1]
        if split:
            plan["left_out"].append((name, "; ".join(split)))
            continue
        sets = {v: next(iter(w.values())) for v, w in want.items() if set(w.values()) != {v}}       # the variables this scope sets, each once
        clash = sorted({css_var(name), *mine.values()} & sets.keys())
        if clash:
            plan["left_out"].append((name, f"it uses {', '.join(clash)}, which its own scope sets to something else: give it a token of its own"))
            continue
        taken.add(attr)
        plan["scoped"].append(attr)
        body = [f"  background-color: var({css_var(name)});", *[f"  {v}: var({t});" for v, t in sets.items()]]
        rules.append(f'[data-ground="{_css(attr)}"] {{\n' + "\n".join(body) + "\n}\n")
    if rules:
        plan["files"][ON_GROUND_CSS] = (GROUNDS_HEAD + "\n\n" + "\n".join(rules)).encode("utf-8")
    return plan


# ---------------------------------------------------------------- snippets/logo.html: the logo in light and dark

LOGO_STYLE = """<style>
  /* light shows by default; dark shows where tokens.css switches to dark; only display: none is used, so the page keeps the display value it chose */
  :root[data-theme="light"] .brand-logo--dark { display: none; }
  :root[data-theme="dark"] .brand-logo--light { display: none; }
  @media not all and (prefers-color-scheme: dark) {
    :root:not([data-theme="dark"]) .brand-logo--dark { display: none; }
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) .brand-logo--light { display: none; }
  }
</style>
"""


def logo_html(name: str, logos: list[str]) -> bytes | None:
    """snippets/logo.html for the logo files `logos` (project paths, as `adapt.logo_paths` lists them) of the brand called `name`, or None when no SVG is left to show.

    Each `assets/logo/<n>.svg` whose name does not end in `-dark` gets two <img> lines with the classes `brand-logo brand-logo--light` and `brand-logo brand-logo--dark` when
    `<n>-dark.svg` exists, and one <img class="brand-logo"> when it does not; a `-dark` file with no light twin and every PNG are left out. The alt is the brand name, the
    path is relative to the snippet and percent-encoded where a URL needs it, the entries are sorted by name with a `<!-- <n> -->` line before each. The style block
    switches like tokens.css (`:root[data-theme="dark"]`, and `:root:not([data-theme="light"])` under prefers-color-scheme: dark) and sets nothing but `display: none`
    on the image that is not shown: no size, colour, spacing or visible display value, so the page's own layout rules stay in charge of the image that is."""
    svgs = {Path(rel).stem: rel for rel in logos if Path(rel).suffix.lower() == ".svg"}
    names = sorted(n for n in svgs if not n.endswith(DARK_TWIN))
    if not names:
        return None
    alt = html.escape(" ".join(name.split()), quote=True)

    def img(rel: str, cls: str) -> str:
        return f'<img class="{cls}" src="../{quote(PREFIX + rel)}" alt="{alt}">\n'

    blocks = []
    for n in names:
        comment = html.escape(re.sub(r"[\x00-\x1f\x7f]", " ", n), quote=False)   # a name cannot end the comment: `>` is written as an entity
        dark = svgs.get(n + DARK_TWIN)
        lines = (img(svgs[n], "brand-logo brand-logo--light") + img(dark, "brand-logo brand-logo--dark")) if dark else img(svgs[n], "brand-logo")
        blocks.append(f"<!-- {comment} -->\n{lines}")
    return (LOGO_HEAD + "\n" + LOGO_NOTE + "\n" + LOGO_STYLE + "\n" + "\n".join(blocks)).encode("utf-8")


# ---------------------------------------------------------------- the owner's files: scaffolded once, never overwritten

def scaffold_text(project: Path, rel: str, text: str) -> str:
    """A scaffold with its placeholders filled in one pass: `{{brand}}` is the brand's name and `{{skill}}` the kit folder's name. Exit 2, before anything is written, for any other
    `{{...}}` (one that spans lines too), named, and for a `{{` or `}}` that is no placeholder at all (never closed, or never opened): a template this version does not know how to
    fill would write the braces into a file that is never overwritten. Filled-in text is not read for placeholders again."""
    fill = {"brand": adapt.view(project)["name"], "skill": adapt.skill_name(project)}
    left = sorted({m for m in _PLACEHOLDER.findall(text) if m not in fill})
    if left:
        names = ", ".join("{{" + m.replace("\n", "\\n") + "}}" for m in left)
        fail(EXIT_USAGE, f"{OWNER_TEMPLATES}/{rel} has placeholders this version does not know: {names}")
    rest = _PLACEHOLDER.sub("", text)
    if "{{" in rest or "}}" in rest:
        fail(EXIT_USAGE, f"{OWNER_TEMPLATES}/{rel} has a '{{{{' or '}}}}' that is no placeholder (one never closed, or never opened): close it, or take it out")
    return _PLACEHOLDER.sub(lambda m: fill[m.group(1)], text)


LINK_AMONG_OWNER = "a link among your own files: never read through"   # why the build stops on a link among the owner's files
MASTER_SCAFFOLDS = {"recipes/ad.md": ("ad",), "recipes/presentation.md": ("slide", "deck-html", "deck-pdf", "deck-pptx")}   # a recipe the build scaffolds once the approved masters hold one of its kinds


def scaffolds(project: Path) -> tuple[str, ...]:
    """The owner files the build scaffolds for this project: the five (`OWNED_FILES`), then each recipe of `MASTER_SCAFFOLDS` whose kinds meet an entry of
    assets/masters/masters.json (written by `masters approve`). No masters.json: the five. A masters.json with a problem stops the run (exit 1), naming the first."""
    manifest = project / MASTERS_DIR / "masters.json"
    if not manifest.is_file():
        return OWNED_FILES
    import mastersdata   # scripts/boardlib: on the path of `kit` and `check`; read here only
    m = mastersdata.load_manifest(manifest)
    if m.problems:
        fail(EXIT_FAIL, f"{MASTERS_DIR}/masters.json: {m.problems[0]}; fix it, or run `brand-creator masters approve` again")
    kinds = {e.kind for e in m.entries}
    return OWNED_FILES + tuple(rel for rel, wanted in MASTER_SCAFFOLDS.items() if kinds & set(wanted))


def owner_plan(project: Path) -> dict:
    """The owner's files: the scaffolded ones (`scaffolds`: the five of `OWNED_FILES` and the master recipes) and every other file of the kit folder that is no generated file, no kit.json and no Finder `.DS_Store` (`owner_paths`).
    {"files": {path in the kit: the scaffold's bytes} of the five, "write": [paths of the five that are absent and will be scaffolded], "kept": [paths already there], "owned": {path in the kit: sha256},
    "links": [paths that are a link among the owner's files]}. `owned` is kit.json's key: the sha256 of the file as it is on disk, or, for one of the five that is absent, of the scaffold that will be written.

    Every scaffold is read and filled first, so an unknown placeholder or a missing template stops the run (exit 2 and exit 3) before anything is written. A file that is there is the owner's, whatever it
    holds; a path that is there but is no file (a folder), or a folder an owner file belongs in (`recipes/`) that is a file, is exit 1, because the build never moves or replaces an owner's path. A link is
    no owner file, whatever it points at (a file or a folder of the project, nothing, or a place outside the project), and is never read through, followed or confined: it is listed in "links", the build
    stops on it (exit 1) and `--replace` moves the link itself aside, as for a kit.json that is a link; one of the five whose path, or folder, is such a link is planned as absent, so that the scaffold is
    written once the link is moved."""
    kd_rel, kd, root = kit_rel(project), kit_dir(project), plugin_root() / OWNER_TEMPLATES
    plan = {"files": {}, "write": [], "kept": [], "owned": {}, "links": []}
    scaffolded = scaffolds(project)
    for rel in scaffolded:
        t = root / rel
        if not t.is_file():
            fail(EXIT_CANNOT, f"the scaffold {OWNER_TEMPLATES}/{rel} is missing from the plugin: reinstall the plugin")
        plan["files"][rel] = scaffold_text(project, rel, t.read_text(encoding="utf-8")).encode("utf-8")
    for rel in scaffolded:
        for parent in reversed(list(Path(rel).parents)[:-1]):                         # the folders between the kit folder and the file: recipes/ for recipes/web-page.md
            if os.path.lexists(d := kd / parent) and not d.is_symlink() and not os.path.isdir(d):   # a link is its own entry in "links", whatever it points at
                fail(EXIT_FAIL, f"{kd_rel}/{rel} is not a file the build can write: {kd_rel}/{parent.as_posix()} is not a folder (it is a file). The build never moves or "
                                f"replaces the owner's paths. Move it away yourself, then build again")
    others = [rel for rel in owner_paths(kd) if rel not in scaffolded]
    for rel in [*scaffolded, *others]:
        f = kd / rel
        linked_folder = any((kd / parent).is_symlink() for parent in Path(rel).parents if parent != Path("."))   # recipes/ is a link: its own entry in "links"
        if f.is_symlink() or linked_folder:
            if f.is_symlink():
                plan["links"].append(rel)
            if rel in scaffolded:                                                 # the link goes aside, then the scaffold is written
                plan["write"].append(rel)
                plan["owned"][rel] = sha256_bytes(plan["files"][rel])
            continue
        if not os.path.lexists(f):
            plan["write"].append(rel)
            plan["owned"][rel] = sha256_bytes(plan["files"][rel])
            continue
        if not f.is_file():
            fail(EXIT_FAIL, f"{kd_rel}/{rel} is not a file (it is a folder): the build never moves or replaces the owner's files. Move it away yourself, then build again")
        plan["kept"].append(rel)
        plan["owned"][rel] = sha256_file(f)
    plan["links"] = owner_sorted(plan["links"])
    return plan


def write_owner(project: Path, plan: dict) -> tuple[list[str], list[str]]:
    """Scaffold the owner's files that were absent: (written, kept). A file is created only if it does not exist at that moment (exclusive create), so a file that appeared since
    `owner_plan` was made is kept as it is and never overwritten."""
    kd_rel, written, kept = kit_rel(project), [], list(plan["kept"])
    for rel in plan["write"]:
        f = confine(project, f"{kd_rel}/{rel}", what="owner file")
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            fail(EXIT_FAIL, f"cannot scaffold {kd_rel}/{rel}: {e.strerror or e}. Something that is not a folder is in the way: move it away, then build again")
        try:
            with open(f, "xb") as fh:
                fh.write(plan["files"][rel])
        except FileExistsError:
            kept.append(rel)
        except OSError as e:
            fail(EXIT_FAIL, f"cannot scaffold {kd_rel}/{rel}: {e.strerror or e}")
        else:
            written.append(rel)
    return written, kept


# ---------------------------------------------------------------- reference pages: the approved pages of site/ go into the kit
# `reference_plan` copies each approved page (site/<id>/, stills included) and the project files it loads, at their project paths under brand/, and writes reference-pages/<id>/notes.md.
# The page folder is read file by file and each file the pages load is read from the path `confine` resolved for it, never from another spelling of it; a path that leaves the project is exit 2.
# The record (`sitedata.validate_site`), the page check and the stills (`_page_check_state`, `_capture_state`) must be sound and current before anything is read. Nothing here writes.
# A page folder or an index.html that is a link leading out is exit 2 before the record hashes it (`_confine_pages`). A URL that names a folder is the folder's index.html when it has one (`_served`).
# A font a page folder holds or a page loads goes through the font rule of assets/fonts/ (`page_font_plan`): only an OFL font the fontcheck report has read is copied, any other is listed in kit.json.

REFERENCE_DIR = "reference-pages"                           # the kit folder of the generated notes: reference-pages/<id>/notes.md
NOTES_FILE = "notes.md"
SITE_DIR = "site"                                           # the approved pages: site/<id>/index.html (sitedata.SITE_DIR)
LOAD_KINDS = {".html": "html", ".htm": "html", ".css": "css"}   # the files whose URLs are read (sitedata.urls_in)
STILL_NAMES = {"full": "full page"}                         # the link text of a still that is no first-screen view
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def site_pages(project: Path) -> list[dict]:
    """The pages of site/site.json that can be named, as the record holds them ({id, path, layout, sha256}), each id once, in the record's order. Never stops a run: a record that is missing or cannot
    be read lists none (`reference_plan` says what is wrong with it)."""
    import sitedata
    try:
        pages = sitedata.load_site(project).get("pages")
    except CliError:
        return []
    out: list[dict] = []
    for page in pages if isinstance(pages, list) else []:
        pid = page.get("id") if isinstance(page, dict) else None
        if (isinstance(pid, str) and sitedata.SITE_PAGE_ID.fullmatch(pid) and page.get("path") == f"{SITE_DIR}/{pid}/index.html"
                and pid not in [p["id"] for p in out]):
            out.append(page)
    return out


def _exact_case(project: Path, rel: str) -> str | None:
    """None when `rel` (a plain project path) is spelled as the project holds it, letter for letter; else the spelling the project has. A Mac finds `Mark.svg` for `mark.svg`, a Linux checkout does not,
    and the kit mirrors project paths, so a page that spells a path another way would have two names for one file in the kit."""
    cur, real = project, []
    for part in rel.split("/"):
        try:
            names = os.listdir(cur)
        except OSError:
            return None
        if part not in names:
            alike = [n for n in names if n.lower() == part.lower()]
            return "/".join([*real, alike[0]]) if alike else None
        real.append(part)
        cur = cur / part
    return None


def _page_bytes(project: Path, rel: str, what: str, cache: dict[str, bytes], *, put_back: str = "the page was approved with it, so put it back") -> bytes:
    """The bytes of the project file `rel`, read from the path `confine` resolved for exactly this string (a path that leads outside the project is exit 2), once: a file already read is not read again,
    so the bytes that were parsed are the bytes that are copied. A link to nothing, a folder or anything that is no plain file is exit 1, and `put_back` says what to do (the default words a reference page, the masters word their own)."""
    if rel not in cache:
        f = confine(project, rel, what=what, read=True)
        if not f.is_file():
            fail(EXIT_FAIL, f"{what} {rel} cannot be read (a link to nothing, a folder, or no plain file): {put_back}")
        try:
            cache[rel] = f.read_bytes()
        except OSError as e:
            fail(EXIT_FAIL, f"{what} {rel} cannot be read ({e.strerror or e})")
    return cache[rel]


def _folder_files(project: Path, folder: str, strict: bool, *, noun: str = "reference page", copies: str = "a page", gone: str | None = None) -> list[str]:
    """The project paths of the files below the page folder `folder`, sorted (a Finder `.DS_Store` is none). The folder is walked from the path `confine` resolved for it, and no link to a folder is
    followed: a link that leads outside the project is exit 2, one that stays inside is exit 1 (the kit copies files, not links). With `strict` false nothing stops the walk: a link to a folder is left out, and so is a file that is a link leading outside the project.
    `noun`, `copies` and `gone` word the messages for another folder the kit copies the files of (the masters)."""
    try:
        top = confine(project, folder, what=f"{noun} folder", read=True)
    except CliError:
        if strict:
            raise
        return []
    if not top.is_dir():
        if strict:
            fail(EXIT_FAIL, gone or f"{folder} is not a folder: the approved page is gone; run `brand-creator site approve --replace` from the round, or put the page back")
        return []
    out: list[str] = []
    for root, dirs, names in os.walk(top):
        here = Path(root).relative_to(top).as_posix()
        here = "" if here == "." else here + "/"
        for d in sorted(dirs):
            if (Path(root) / d).is_symlink():
                if strict:
                    confine(project, f"{folder}/{here}{d}", what=f"link in a {noun} folder", read=True)
                    fail(EXIT_FAIL, f"{folder}/{here}{d} is a link to a folder: the kit copies the files of {copies}, never a link; replace it with the folder")
        for n in sorted(names):
            rel = f"{folder}/{here}{n}"
            if n == FINDER_FILE:
                continue
            if not strict:
                try:
                    confine(project, rel, what=f"{noun} file", read=True)
                except CliError:
                    continue   # a link that leads outside the project is not one of the sources: the sources are hashed, and nothing outside the project is read, not even to be hashed
            out.append(rel)
    return sorted(out)


def _load_target(file_rel: str, url: str) -> tuple[str | None, int | None, str | None]:
    """What a URL of the file `file_rel` loads: (the plain project path, None, None); (None, None, None) for a URL that loads no project file (a fragment or a query alone, `//host`, a URL with a
    scheme: `http:`, `https:`, `data:`, `mailto:`, `tel:`); or (None, the exit code, why) for one the kit cannot take: a path that leaves the project (exit 2), an absolute path or a control
    character in the path (exit 1). Whether the file is there is `_load_checked`'s to say. The path is percent-decoded and resolved from the folder of the file that holds it, as a browser does and as `sitedata` rewrites it."""
    path = url.strip().split("#")[0].split("?")[0]
    if not path or path.startswith("//"):
        return None, None, None
    m = _SCHEME.match(path)
    if m and len(m.group(1)) > 1 and m.group(1).lower() != "file":
        return None, None, None
    path = unquote(path)
    if _CONTROL.search(path):
        return None, EXIT_FAIL, "holds a control character"
    if path.startswith("/") or m:
        return None, EXIT_FAIL, "is an absolute path, which will not resolve in a product repository: write it relative to the file"
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(file_rel), path))
    if joined == ".." or joined.startswith("../"):
        return None, EXIT_USAGE, "leads outside the project"
    return joined, None, None


def _page_urls(rel: str, data: bytes, strict: bool) -> list[tuple[str, str, str]]:
    """(the project path, `<file>:<line>`, the URL as written) of every project file the html or css file `rel` loads, in the order they are written. A file that is not UTF-8 text cannot be read:
    exit 1 (with `strict` false, it is left out); the first URL the kit cannot take is exit 1 or 2 (with `strict` false, it is left out)."""
    import sitedata
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        if strict:
            fail(EXIT_FAIL, f"{rel} is not UTF-8 text, so the paths in it cannot be read")
        return []
    out = []
    for line, url in sitedata.urls_in(text, LOAD_KINDS[Path(rel).suffix.lower()]):
        path, code, why = _load_target(rel, url)
        if code is not None:
            if strict:
                fail(code, f"{rel}:{line}: {url[:80]!r} {why}")
        elif path is not None:
            out.append((path, f"{rel}:{line}", url))
    return out


def _gather(project: Path, pages: list[dict], fonts: dict | None, strict: bool) -> dict:
    """What the approved pages hold and load: {"paths": the project paths of the files to copy, sorted, "loads": {project path: `<file>:<line>` that names it} of the files loaded from outside the page
    folders, "not_copied": [(font path, how a page has it, why)] of the fonts under assets/fonts/ a page loads that the kit does not copy, "fonts": {project path: how a page has it} of the fonts a page
    brings from outside assets/fonts/ (a font file in a page folder, or one a page loads: `page_font_plan` decides whether the kit copies it, and they stay in "paths" so that they are sources), "cache":
    {project path: bytes} of the files read so far}.

    The files of a page folder are all copied (stills included). The html and css files of the folders are read for the URLs they load, and so is every css file they load from outside the
    folders, one level deep: what that css loads is copied and read no further (a file two steps from a page's stylesheet is not in the kit, and `kit check` names the link that then does not resolve). A font under assets/fonts/ is the font
    plan's (`font_plan`: only OFL fonts are copied, D6), so a page that loads one is not given a copy of its own; `fonts` is that plan (None: not read, as `page_sources` has it). A URL that names a
    folder is the folder's index.html when it has one (`_served`). With `strict` false a file that cannot be read is left out instead of stopping the run."""
    cache: dict[str, bytes] = {}
    out: dict = {"paths": [], "loads": {}, "not_copied": [], "fonts": {}, "cache": cache}
    try:
        font_paths = set(font_files(project))
    except CliError:
        font_paths = set()
    folder = [rel for page in pages for rel in _folder_files(project, f"{SITE_DIR}/{page['id']}", strict)]
    have = set(folder)
    out["fonts"].update({rel: "sits in the page folder" for rel in folder if is_font(rel)})

    def read(rel: str, what: str) -> bytes | None:
        try:
            return _page_bytes(project, rel, what, cache)
        except CliError:
            if strict:
                raise
            return None

    def take(path: str, where: str) -> bool:
        """One file a page names, `path`, named at `where`: copy it unless it is in a page folder already or is a font of assets/fonts/. True when it was added. A path that names a folder is its
        index.html when it has one. A font from anywhere else is added like any file and noted in `out["fonts"]`: whether it is copied is `page_font_plan`'s to say."""
        path = _served(project, path)
        if path in have:
            return False
        if path in font_paths:
            if strict and fonts is not None and PREFIX + path not in fonts["files"]:
                why = next((f["reason"] for f in fonts["not_copied"] if f["file"] == path), "it is not copied")
                out["not_copied"].append((path, f"loaded at {where}", why))
            return False
        if strict:
            _load_checked(project, path, where)
        if read(path, "file a page loads") is None:
            return False
        have.add(path)
        out["loads"][path] = where
        if is_font(path):
            out["fonts"][path] = f"loaded at {where}"
        return True

    named: dict[str, str] = {}
    for rel in folder:
        if Path(rel).suffix.lower() in LOAD_KINDS and (data := read(rel, "reference page file")) is not None:
            for path, where, _url in _page_urls(rel, data, strict):
                named.setdefault(path, where)
    deeper: dict[str, str] = {}
    for path, where in named.items():
        if take(path, where) and Path(path).suffix.lower() == ".css":
            for inner, there, _url in _page_urls(path, cache[path], strict):
                deeper.setdefault(inner, there)
    for path, where in deeper.items():
        if path not in named:
            take(path, where)
    out["paths"] = sorted(have)
    return out


def _served(project: Path, path: str) -> str:
    """The project file a URL's path leads to. A path that names a folder holding an index.html is that index.html, the way a web server answers a folder (a link or a file that is there but cannot
    be read is `_load_checked`'s to refuse); any other path stands as it is. It never raises: a path that leaves the project is `_load_checked`'s exit 2."""
    try:
        real = confine(project, path, what="file", read=True)
    except CliError:
        return path
    index = posixpath.normpath(posixpath.join(path, "index.html"))
    return index if real.is_dir() and os.path.lexists(project / index) else path


def _load_checked(project: Path, path: str, where: str) -> None:
    """Exit 1 when the file a page names, `path` (named at `where`), is not there, is a folder, or is spelled in another letter case than the project holds it; exit 2 when it leads outside the project."""
    try:
        real = confine(project, path, what="file", read=True)
    except CliError as e:
        raise CliError(e.code, f"{where}: {e.message}") from None
    # the letter case first: on a Mac `PIC.svg` exists when the project holds `pic.svg`, on Linux it does not, and either way the
    # owner needs the same answer (the spelling the project has), not "the project does not have it"
    alike = _exact_case(project, path)
    if alike is not None:
        fail(EXIT_FAIL, f"{where}: leads to {path}, which the project holds as {alike}: a product repository on Linux tells the letter case apart, so write the path as it is")
    if not os.path.lexists(project / path):
        fail(EXIT_FAIL, f"{where}: leads to {path}, which the project does not have: the kit copies every file a page loads, and `kit check` would fail the link")
    if real.is_dir():
        fail(EXIT_FAIL, f"{where}: leads to {path}, a folder, not a file: it holds no index.html for a web server to answer with, and `kit check` fails a link to a folder, so the page cannot go into the kit as it is")


def _failing(doc: dict) -> str:
    rows = [r["id"] for r in doc.get("results", []) if isinstance(r, dict) and r.get("status") == "fail" and isinstance(r.get("id"), str)] if isinstance(doc.get("results"), list) else []
    return ", ".join(rows[:3]) + (f" and {len(rows) - 3} more" if len(rows) > 3 else "") if rows else "no row says why"


def _page_check_state(project: Path, page_path: str) -> tuple[str | None, str | None]:
    """(the inputs_sha of the page's page-check report, None), or (None, why not): the report `brand-creator page-check <page>` wrote (found by pagecheck.report_tool, the one rule that names it) must
    be there, current (no file it was made from is gone or changed), the report of this very project page, and passing."""
    import pagecheck   # scripts/pagelib, on the path of `kit` and `check`: the one rule that names the report of a page
    tool = pagecheck.report_tool(page_path)
    where, cmd = f"assets/_checks/{tool}.json", f"brand-creator page-check {page_path}"
    f = confine(project, where, what="page-check report", read=True)
    if not f.is_file():
        return None, f"has no page-check report ({where} is missing): run `{cmd}`"
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
        stale = stale_inputs(project, doc)
        listed = {r.get("path") for r in doc.get("inputs", []) if isinstance(r, dict)}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None, f"has a page-check report that cannot be read ({where}): run `{cmd}`"
    if stale:
        return None, f"has a page-check report that is stale ({'; '.join(stale[:2])}): run `{cmd}`"
    target = doc.get("target")
    if not (isinstance(target, dict) and target.get("kind") == "project" and target.get("page") == page_path):
        return None, f"has a page-check report of another target ({where}): run `{cmd}`"
    if page_path not in listed:
        return None, f"has a page-check report that does not list the page among the files it was made from ({where}): run `{cmd}`"
    if doc.get("status") == "fail":
        return None, (f"fails its page check ({_failing(doc)}; see {where}): a reference page is a page that passes, so change it, approve it again "
                      "(`brand-creator site approve --replace`) and check it")
    if doc.get("status") != "pass":
        return None, f"has a page-check report that gives no verdict (status {doc.get('status')!r}; see {where}): change the page or the setup as its rows say, then run `{cmd}`"
    if not is_sha(doc.get("inputs_sha")):
        return None, f"has a page-check report with no inputs_sha ({where}): run `{cmd}`"
    return doc["inputs_sha"], None


def _capture_state(project: Path, page_path: str) -> tuple[tuple[str, list[tuple[str, str]]] | None, str | None]:
    """((the sha256 over the inputs of the page's capture.json, [(link text, file name in shots/)] of its stills), None), or (None, why not): site/<id>/shots/capture.json (`brand-creator capture <page>`) must
    be there, current, the capture of this page, and list the four first-screen stills (and the full page, when it lists one) with the files and sha256 that are there now."""
    import siteboard   # scripts/boardlib: the four views `capture` takes, named once
    shots = f"{page_path.rsplit('/', 1)[0]}/shots"
    where, cmd = f"{shots}/capture.json", f"brand-creator capture {page_path}"
    f = confine(project, where, what="capture record", read=True)
    if not f.is_file():
        return None, f"has no stills ({where} is missing): run `{cmd}`"
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
        stale = stale_inputs(project, doc)
        listed = {r.get("path") for r in doc.get("inputs", []) if isinstance(r, dict)}
        inputs_sha = Report.inputs_sha(doc["inputs"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None, f"has stills whose record cannot be read ({where}): run `{cmd}`"
    source = doc.get("source")
    if stale or page_path not in listed or not (isinstance(source, dict) and source.get("page") == page_path):
        why = stale[:2] or ([f"it is the capture of {source.get('page') or source.get('url')}, not of this page"] if isinstance(source, dict) and source.get("page") != page_path else
                            ["it does not list the page among the files it was made from"])
        return None, f"has stills that are stale ({'; '.join(why)}; {where}): run `{cmd}`"
    entries = {e.get("view"): e for e in doc.get("views", []) if isinstance(e, dict)} if isinstance(doc.get("views"), list) else {}
    wanted = [(v, entries.get(v)) for v in siteboard.VIEWS] + ([("full", doc["full"])] if isinstance(doc.get("full"), dict) else [])
    stills, gaps = [], []
    for view, entry in wanted:
        entry = entry or {}
        name, sha = entry.get("file"), entry.get("sha256")
        if not (isinstance(name, str) and name and "/" not in name and "\\" not in name and name not in (".", "..") and is_sha(sha)):
            gaps.append(f"{where} lists no {view} still with a file and a sha256")
            continue
        still = confine(project, f"{shots}/{name}", what="still", read=True)
        if not still.is_file():
            gaps.append(f"{shots}/{name} (the {view} still) is not there")
        elif sha256_file(still) != sha:
            gaps.append(f"{shots}/{name} is not the {view} still {where} lists (its sha256 differs)")
        else:
            stills.append((STILL_NAMES.get(view, view), name))
    if gaps:
        return None, f"has stills that are not the ones capture.json lists ({'; '.join(gaps[:2])}): run `{cmd}`"
    return (inputs_sha, stills), None


def note_text(text: str, *, values: bool = False) -> str:
    """Words of the owner (a choice, where it was decided, the approval) as they go on one line of a generated note, so that `kit check` reads in the note only what the note says. White space
    is collapsed and a control character is a space. What `kit:fill`, `kit:links`, `kit:tags` and `kit:numbers` would take for a marker, a link, a tag or a token reference is written as the
    reader of Markdown shows it and the checks do not read it: the first bracket of `[[fill`, `[rule:` and `[example]` as `&#91;`, the `(` after `]` and after `var` as `&#40;`, and `{a.b}` as
    `{{a.b}}` (the doubled braces `kit check` leaves alone). With `values` a number with a unit, a ratio, a hex colour or `rgb(` is broken the same way (a note line that carries no tag has nothing
    to cite them with)."""
    s = " ".join(_CONTROL.sub(" ", str(text)).split())
    s = re.sub(r"\[(?=\[fill)", "&#91;", s, flags=re.I)
    s = re.sub(r"\[(?=rule:)", "&#91;", s)
    s = re.sub(r"\[(?=example\])", "&#91;", s)
    s = _JSON_REF.sub(lambda m: "{" + m.group(0) + "}", s)
    s = re.sub(r"var\((?=\s*--[A-Za-z0-9_-]+)", "var&#40;", s)
    s = s.replace("](", "]&#40;")
    for _ in range(8 if values else 0):
        masked = s
        for rx in (_RULE_TAG, _LINK_TARGET, _URL, _PROPERTY_NAME):
            masked = rx.sub(lambda m: " " * len(m.group(0)), masked)
        spans = [m.span() for m in _VALUE.finditer(masked)]
        if not spans:
            break
        for a, b in reversed(spans):
            v = s[a:b]
            at = a if v.startswith("#") or v.endswith("(") else a + v.index(":") if ":" in v else a + re.search(r"[A-Za-z%]", v).start()
            s = s[:at] + f"&#{ord(s[at])};" + s[at + 1:]
    return s


def notes_md(page: dict, site: dict, stills: list[tuple[str, str]]) -> str:
    """reference-pages/<id>/notes.md of one approved page (`page` and `site` as site/site.json holds them, `stills` the link texts and file names of `_capture_state`): the page id as its title; its
    layout with the words "structure only"; the approval; links to the page and to each still (percent-encoded where a URL needs it, from reference-pages/<id>/ to brand/site/<id>/); and
    `## Choices`, one bullet for each choice that names this page (or every page), `- <text> [rule: site:<id>] (decided in <source>)` for a rule and `- <text> [example]` for an example."""
    pid = page["id"]
    base = f"../../{PREFIX}{SITE_DIR}/{pid}"
    L = [f"# {note_text(pid, values=True)}", "", f"Layout: {note_text(page['layout'], values=True)} (structure only)", f"Approved: {note_text(site['approved'], values=True)}", "",
         f"Page: [index.html]({quote(base + '/index.html', safe='/')})",
         "Stills: " + ", ".join(f"[{label}]({quote(f'{base}/shots/{name}', safe='/')})" for label, name in stills), "", "## Choices", ""]
    choices = [c for c in site.get("choices", []) if isinstance(c, dict) and ("pages" not in c or pid in c["pages"])]
    for c in choices:
        if c["tag"] == "rule":
            L.append(f"- {note_text(c['text'])} [rule: site:{c['id']}] (decided in {note_text(c['source'])})")
        else:
            L.append(f"- {note_text(c['text'])} [example]")
    if not choices:
        L.append("The site round recorded no choice for this page.")
    return "\n".join(L) + "\n"


def _confine_pages(project: Path) -> None:
    """Exit 2 when the folder or the index.html of a page the record lists is a link that leads outside the project, before anything hashes the page: `sitedata.validate_site` hashes each page it names, through a link
    too, and a page that leads out must be exit 2 whatever its bytes are, never exit 1 because they differ. A record that cannot be read lists no page here (`validate_site` says what is wrong with it). The pages
    checked are the ones `sitedata.file_problems` hashes: the id is a string and the path is site/<id>/index.html."""
    import sitedata   # scripts/boardlib: the record of the approved pages
    try:
        pages = sitedata.load_site(project).get("pages")
    except CliError:
        return
    for page in pages if isinstance(pages, list) else []:
        pid = page.get("id") if isinstance(page, dict) else None
        if isinstance(pid, str) and page.get("path") == f"{SITE_DIR}/{pid}/index.html":
            confine(project, posixpath.dirname(page["path"]), what="reference page folder", read=True)
            confine(project, page["path"], what="reference page", read=True)


def reference_plan(project: Path, fonts: dict) -> dict:
    """What the approved reference pages add to the kit: {"records": [kit.json `reference_pages`], "files": {path in the kit: bytes}, "not_copied": [(font, how a page has it, why)], "fonts": {"copied": [...],
    "not_copied": [...]} (kit.json `fonts` entries of the fonts the pages bring from outside assets/fonts/, by the rule of `font_plan`: `page_font_plan`)}. All empty while the project has no site/site.json.
    Nothing is written, and nothing is read before the checks pass:

    - A page folder or index.html that is a link leading outside the project is exit 2, whatever the bytes behind the link are (`_confine_pages`).
    - `sitedata.validate_site(project)` finds nothing (the record is sound and each page is the one that was approved); otherwise exit 1 quoting the first three problems.
    - Every page has a current, passing page-check report and current stills (`_page_check_state`, `_capture_state`); otherwise exit 1 naming each page and the command to run.
    - Then `_gather` reads the page folders and what they load (a path that leaves the project is exit 2), the page's index.html must be the bytes the record holds, and the files are copied to
      `brand/<project path>`. A page's notes are `notes_md` (generated, `reference-pages/<id>/notes.md`). `records` is, per page, its id, the kit path of its page, the record's `source_sha`, the
      page-check report's `inputs_sha` and the sha256 over the inputs of capture.json."""
    out = {"records": [], "files": {}, "not_copied": [], "fonts": {"copied": [], "not_copied": []}}
    if not os.path.lexists(project / SITE_RECORD):
        return out
    confine(project, SITE_RECORD, what="site record", read=True)
    import sitedata   # scripts/boardlib: the record of the approved pages
    _confine_pages(project)
    bad = sitedata.validate_site(project)
    if bad:
        fail(EXIT_FAIL, f"{SITE_RECORD} does not validate, so no reference page can go into the kit: {'; '.join(bad[:3])}"
                        + (f"; and {len(bad) - 3} more" if len(bad) > 3 else "") + ". Fix it (`brand-creator check` says the same), then build again")
    site = sitedata.load_site(project)
    pages = site_pages(project)
    states, stopped = {}, []
    for page in pages:
        check_sha, why = _page_check_state(project, page["path"])
        shots, shots_why = _capture_state(project, page["path"])
        stopped += [f"{page['path']} {w}" for w in (why, shots_why) if w]
        states[page["id"]] = (check_sha, shots)
    if stopped:
        fail(EXIT_FAIL, f"{len(stopped)} reference page problem(s) stop the kit, and nothing was written: " + "; ".join(stopped[:6]) + (f"; and {len(stopped) - 6} more" if len(stopped) > 6 else ""))
    got = _gather(project, pages, fonts, True)
    brought = page_font_plan(project, got["fonts"])   # a font a page folder holds or a page loads, outside assets/fonts/: the font rule decides whether it goes in
    files = {rel: _page_bytes(project, rel, "file a page loads" if rel in got["loads"] else "reference page file", got["cache"]) for rel in got["paths"] if rel not in brought["left"]}
    for page in pages:
        index = f"{SITE_DIR}/{page['id']}/index.html"
        if sha256_bytes(files[index]) != page["sha256"]:
            fail(EXIT_FAIL, f"{index} changed since it was approved (its sha256 is not the one in {SITE_RECORD}) while the kit was read: {sitedata.RUN_AGAIN}")
        check_sha, (inputs_sha, stills) = states[page["id"]]
        out["records"].append({"id": page["id"], "page": f"{PREFIX}{index}", "source_sha": page["sha256"], "page_check_inputs_sha": check_sha, "capture_inputs_sha": inputs_sha})
        out["files"][f"{REFERENCE_DIR}/{page['id']}/{NOTES_FILE}"] = notes_md(page, site, stills).encode("utf-8")
    out["files"].update({PREFIX + rel: data for rel, data in files.items()})
    out["files"].update(brought["files"])
    out["fonts"] = {"copied": brought["copied"], "not_copied": brought["not_copied"]}
    out["not_copied"] = got["not_copied"] + [(rel, got["fonts"][rel], why) for rel, why in brought["left"].items()]
    return out


def page_sources(project: Path) -> list[str]:
    """What the reference pages of the kit are made from, as project paths, sorted: site/site.json, the files of each page folder (the stills and capture.json too) and the files they load (`_gather`).
    It never stops a run: a record that cannot be read lists only itself, and a file it cannot read is left out, so that a later look at the sources can still say they changed. [] while the project has
    no site/site.json."""
    if not os.path.lexists(project / SITE_RECORD):
        return []
    try:
        got = _gather(project, site_pages(project), None, False)
    except CliError:
        got = {"paths": []}
    out = {SITE_RECORD, *got["paths"]}
    if got.get("fonts"):   # whether a font a page brings is copied depends on the fontcheck report and the licence texts: they are sources of the pages too
        out.add(FONTCHECK_REPORT)
        try:
            out.update(licence_texts(project))
        except CliError:
            pass
    return sorted(out)


def pages_source(project: Path) -> str | None:
    """One sha256 over `page_sources` (the path and the file's sha256 of each; a file that is not there counts as missing); None when the project has no site/site.json."""
    rels = page_sources(project)
    if not rels:
        return None
    h = hashlib.sha256()
    for rel in rels:
        h.update(f"{rel}\0{_sha_or_none(project, rel) or 'missing'}\n".encode())
    return h.hexdigest()


def page_input_rels(project: Path) -> list[str]:
    """The project paths a `kit` report lists as inputs for the reference pages: `page_sources` and the page-check report of each page, so a page checked again or approved again makes the report stale."""
    rels = page_sources(project)
    if not rels:
        return []
    import pagecheck
    return [*rels, *(f"assets/_checks/{pagecheck.report_tool(p['path'])}.json" for p in site_pages(project))]


# ---------------------------------------------------------------- masters: the approved masters of assets/masters/ go into the kit
# Everything under assets/masters/ (ad, deck and other templates the owner approved, with their pictures, PDFs, PPTX and the fonts they ship) is copied, byte for byte, to brand/<project path>. The plugin cannot
# know which masters are approved: only approved ones belong in the folder. A font in it goes through the font rule of assets/fonts/ (`page_font_plan`): copied only when the current fontcheck report has read it
# as OFL and an OFL licence text sits in assets/fonts/, otherwise listed in kit.json `fonts.not_copied`. A font file of a format fontcheck cannot read (`UNREAD_FONT_FORMATS`: .ttc, .eot ...) has no licence the rule could read: it is never copied, and listed the same way.
# Links inside a master HTML file are judged by `kit check` (`kit:links`) like any file of the kit.
# A link to a folder inside the folder is exit 1, a link that leads outside the project is exit 2 (`_folder_files`), the folder itself a file or a link is exit 1.

MASTER_NOUN = "masters"


def _masters_listing(project: Path, strict: bool) -> list[str]:
    """The project paths of the files below assets/masters/, sorted ([] when the project has no such folder). With `strict` a folder that is a file or a link, a link to a folder in it and a file that leads
    outside the project stop the run; without it nothing does (a source that cannot be read is left out, so that a later look at the sources can still say they changed)."""
    if not os.path.lexists(project / MASTERS_DIR):
        return []
    try:
        if (project / MASTERS_DIR).is_symlink():
            confine(project, MASTERS_DIR, what="masters folder", read=True)   # a link that leads outside the project: exit 2
            if strict:
                fail(EXIT_FAIL, f"{MASTERS_DIR} is a link: the kit copies the files of your masters, never a link; replace it with the folder")
            return []
        return _folder_files(project, MASTERS_DIR, strict, noun="masters", copies="your masters",
                             gone=f"{MASTERS_DIR} is not a folder: the kit copies the files of your masters, so put them in a folder of that name, or take it away")
    except CliError:
        if strict:
            raise
        return []


def masters_plan(project: Path) -> dict:
    """What the masters add to the kit: {"paths": the project paths of the files below assets/masters/, "files": {path in the kit: bytes} (each file at brand/<project path>, a font only when the font rule copies it,
    with the licence texts of the fonts that are), "fonts": {"copied": [...], "not_copied": [...]} (kit.json `fonts` entries, by the rule of `page_font_plan`), "not_copied": [(font, how, why)]}. A font file of
    a format fontcheck cannot read (.ttc, .otc, .eot, .dfont, .pfb, .pfm, .pfa: `is_unread_font`) is never copied: its licence cannot be read, so it is listed in `fonts.not_copied` with that reason. All empty
    while the project has no file there. Nothing is written. Every file is read from the path `confine` resolved for it (`_page_bytes`), once."""
    out: dict = {"paths": [], "files": {}, "fonts": {"copied": [], "not_copied": []}, "not_copied": []}
    paths = _masters_listing(project, True)
    if not paths:
        return out
    cache: dict[str, bytes] = {}
    how = "sits in the masters folder"
    brought = page_font_plan(project, {rel: how for rel in paths if is_font(rel)})
    unread = {rel: unread_font_why(rel) for rel in paths if is_unread_font(rel)}
    left = {**brought["left"], **unread}
    for rel in paths:
        if rel not in left:
            out["files"][PREFIX + rel] = _page_bytes(project, rel, "master file", cache,
                                                    put_back=f"a master is copied as it is, so put the real file back or take the link out of {MASTERS_DIR}/")
    out["files"].update(brought["files"])
    out["paths"] = paths
    out["fonts"] = {"copied": brought["copied"],
                    "not_copied": sorted([*brought["not_copied"], *({"file": rel, "reason": why} for rel, why in unread.items())], key=lambda f: f["file"])}
    out["not_copied"] = [(rel, how, left[rel]) for rel in sorted(left)]
    return out


def masters_sources(project: Path) -> list[str]:
    """What the masters of the kit are made from, as project paths, sorted: the files below assets/masters/ and, as soon as one is a font (whether it is copied depends on the fontcheck report and the licence
    texts), the fontcheck report and the licence texts. It never stops a run. [] while the folder holds no file."""
    paths = _masters_listing(project, False)
    if not paths:
        return []
    out = set(paths)
    if any(is_font(rel) for rel in paths):
        out.add(FONTCHECK_REPORT)
        try:
            out.update(licence_texts(project))
        except CliError:
            pass
    return sorted(out)


def masters_source(project: Path) -> str | None:
    """One sha256 over `masters_sources` (the path and the file's sha256 of each; a file that is not there counts as missing); None when the folder holds no file."""
    rels = masters_sources(project)
    if not rels:
        return None
    h = hashlib.sha256()
    for rel in rels:
        h.update(f"{rel}\0{_sha_or_none(project, rel) or 'missing'}\n".encode())
    return h.hexdigest()


# ---------------------------------------------------------------- the plan

def _project_file(project: Path, rel: str, what: str) -> bytes:
    f = confine(project, rel, what=what, read=True)
    if not f.is_file():
        fail(EXIT_FAIL, f"{what} {rel} is not in the project: {'run `brand-creator tokens`' if rel.startswith('assets/tokens/') else 'add it, or change qa/rules.json'}")
    return f.read_bytes()


def _drawing(project: Path, drawing: str) -> bytes:
    """The bytes of a band drawing. It is named by its plain path in the project, because the kit mirrors project paths and SKILL.md names it by the same string."""
    f = confine(project, drawing, what="band drawing", read=True)   # outside the project: exit 2; the file is read from this path
    if drawing != posixpath.normpath(drawing) or posixpath.isabs(drawing):
        plain = posixpath.normpath(drawing)
        if posixpath.isabs(plain):   # an absolute path inside the project: the plain path is the one below the project folder (named with or without its links resolved)
            below = [posixpath.relpath(plain, root) for root in (os.path.abspath(project), os.path.realpath(project))]
            plain = next((r for r in below if not r.startswith("..")), plain)
        fail(EXIT_USAGE, f"qa/rules.json: the band drawing {drawing!r} must be written as a plain path inside the project ({plain!r}): "
                         "the kit names it by the path it has in the project")
    if not f.is_file():
        fail(EXIT_FAIL, f"qa/rules.json names the band drawing {drawing} but the project has no such file: add it, or change qa/rules.json")
    return f.read_bytes()


KIT_TEMPLATES = "templates/applied-skill"                   # the kit's own SKILL.md and brand.md templates (kit-SKILL.md, kit-brand.md), below the plugin folder
MASTERS_README = PREFIX + "assets/masters/README.md"        # the list of the approved masters, as `masters approve` writes it (MASTERS_DIR is defined further down)


def section(version: str) -> str:
    """The kit section of SKILL.md (the template's {{kit}}): the version line and what the folder is. The files are listed in kit.json, never here."""
    return "\n".join(["## The kit", "", version_line(version), "",
                      "This folder is a brand kit and this skill is its core. `kit.json` lists every file with its hash. Never edit a generated file here: change the brand project "
                      "and run `brand-creator kit build --yes` again. Your own files (`EXTENDING.md` says which) are never overwritten.", "",
                      "It works beside your web-design skill, never instead of it: load both when you build a page. A built site does not serve this folder, so copy the files you use "
                      "from `brand/` into the product's own public or static folder and link them from there; `recipes/web-page.md` has the steps."])


def checklist_md(project: Path, rules: dict) -> bytes:
    """checklist.md: the check before handing anything over, every item a `- [ ]` line, built only from `rules` (`rules_doc(project)`) and a few fixed lines the plugin
    holds for every brand (the logo from its files, colours from the tokens, claims from facts.json, proposals to the owner, golden-rules.md). A section with nothing in it
    is left out."""
    ds = rules["downscale"]
    logo = ["The logo comes from its files in `" + PREFIX + "assets/logo/`, used as they are."]
    for b in rules["bands"]:
        who = f"the {b['name']} mark" if b["mark"] is None else f"{b['mark']} ({b['name']})"
        logo.append(f"Up to {b['max_px']} px {who} uses `{b['drawing']}`." if b["max_px"] else f"At larger sizes {who} uses `{b['drawing']}`.")
    logo.append(f"At {ds['accent_rule_max_size']} px and below the accent holds a solid {ds['accent_min_px']} x {ds['accent_min_px']} px square.")
    colour = ["Every colour is a token role from `" + PREFIX + TOKENS_CSS + "`, in both themes where the material has them."]
    for kind, floor in dict.fromkeys((p["kind"], p["min"]) for p in rules["pairs"]):
        colour.append(f"Every {kind} pair reaches at least {floor:g}:1 (`{BRAND_MD}` lists the pairs and their ratios).")
    page_rules = (rules.get("page") or {}).get("rules") or []
    sections = [("Logo", logo), ("Colour", colour),
                ("The owner's rules", [f"{r['text'].rstrip('.')} (`{r['id']}`)." for r in rules["g4"]]),
                ("Words", [f"None of these: {', '.join(rules['forbidden'])}."] if rules["forbidden"] else []),
                ("Page rules", [f"`{r['id']}`: {str(r['g4']).rstrip('.')}." for r in page_rules]),
                ("Claims", ["Every number, feature, price, client and date is in `facts.json`; a missing one is a visible placeholder.", "Sample data is labelled as sample data."]),
                ("New things", ["Anything the brand has not decided is labelled a proposal and shown to the owner.", "Every rule in `golden-rules.md` holds."])]
    L = [f"# {adapt.view(project)['name']} checklist", "",
         "Go through it before you hand anything over. A \"no\" is fixed, or shown to the owner; never waved through. Generated from `rules.json`: never edit it here."]
    for title, items in sections:
        if items:
            L += ["", f"## {title}", "", *(f"- [ ] {i}" for i in items)]
    return ("\n".join(L) + "\n").encode("utf-8")


def _holds(files, prefix: str) -> bool:
    return any(rel.startswith(prefix) for rel in files)


def how_md(files) -> str:
    """`## How to work`: numbered steps, the same for every brand, each naming only files the kit holds (`files`: the paths the build writes, generated and scaffolded)."""
    steps = ["Name what you are making and the moment it is for (a page, a post, an ad, a deck; a launch, a reminder, an error).",
             "Read `golden-rules.md`: the rules every piece keeps.",
             "Open the recipe for that material in `recipes/`, one file per kind of material. When none fits, work from `brand.md` and say what no recipe covers."]
    if _holds(files, PREFIX + "assets/masters/"):
        steps.append("Ads and decks start from an approved master: `" + MASTERS_README + "` lists them." if MASTERS_README in files
                     else "Ads and decks start from an approved master in `" + PREFIX + "assets/masters/`.")
    steps.append("Take colours, type, spacing and motion from the tokens (`" + PREFIX + TOKENS_CSS + "`). A value the tokens lack is asked for, never invented.")
    if _holds(files, PREFIX + "assets/logo/"):
        steps.append("Take the logo from its files in `" + PREFIX + "assets/logo/` as they are: never redrawn, recoloured or typed out."
                     + (" `" + LOGO_HTML + "` places it in light and dark." if LOGO_HTML in files else ""))
    steps += ["Take every claim (a number, a feature, a price, a client, a date) from `facts.json`. When one is missing, leave a visible placeholder and ask the owner.",
              "Anything the brand has not decided (a layout, a use of colour, an animation, a line of copy) is a proposal: label it and ask the owner."]
    if "checklist.md" in files:
        steps.append("Before you hand anything over, go through `checklist.md`.")
    return "\n".join(["## How to work", "", *(f"{n}. {s}" for n, s in enumerate(steps, 1))])


def own_entries(kd: Path) -> list[str]:
    """The owner's files of the kit folder `kd` that no other row of the map names, as the map lists them: a folder at the top as `<folder>/` (`guides/`, `code/`), a file at the top as its name;
    `recipes/` and the scaffolded files at the top have rows of their own. A link is no owner file (the build stops on it, or `--replace` moves it aside), so it is never named. Sorted."""
    named = {"recipes", *(rel for rel in OWNED_FILES if "/" not in rel)}
    tops = {rel.split("/")[0] + ("/" if "/" in rel else "") for rel in owner_paths(kd) if plain_file(kd, rel)}
    return sorted(t for t in tops if t.rstrip("/") not in named)


def map_md(files, own=()) -> str:
    """`## Map`: where to look, one row per need, each only when the kit holds what it names (`files` as for `how_md`); `own` (`own_entries`) are the owner's other folders and files, one row
    when there are any, so that what the owner adds (a folder of guides, of code) is found from SKILL.md."""
    rows = [("the colours, pairs, type, layout, mark sizes, motion and claims", [BRAND_MD]),
            ("the token values", [PREFIX + TOKENS_CSS, PREFIX + TOKENS_JSON]),
            ("the logo files", [PREFIX + "assets/logo/"] + ([LOGO_HTML] if LOGO_HTML in files else []) if _holds(files, PREFIX + "assets/logo/") else []),
            ("the fonts", [FONTS_CSS] if FONTS_CSS in files else []),
            ("the colours text may sit on", [ON_GROUND_CSS] if ON_GROUND_CSS in files else []),
            ("the rules and the facts as data", [RULES_JSON, FACTS_JSON]),
            ("approved pages to follow", ["reference-pages/"] if _holds(files, "reference-pages/") else []),
            ("the approved ads and decks", ([MASTERS_README] if MASTERS_README in files else [PREFIX + "assets/masters/"]) if _holds(files, PREFIX + "assets/masters/") else []),
            ("the signature move", [PREFIX + MOTION_SPEC] if PREFIX + MOTION_SPEC in files else []),
            ("how to make one kind of material", ["recipes/"]),
            ("the rules every piece keeps", ["golden-rules.md"]),
            ("how the brand looks and sounds", ["visual.md", "voice.md"]),
            ("the owner's own folders and files", list(own)),
            ("the check before handing over", ["checklist.md"] if "checklist.md" in files else []),
            ("how to change or extend this kit", ["EXTENDING.md"]),
            ("every file and its hash", [KIT_FILE])]
    return "\n".join(["## Map", "", "| You need | Open |", "| --- | --- |", *(f"| {need} | {', '.join('`' + p + '`' for p in paths)} |" for need, paths in rows if paths)])


def plan(project: Path, fonts: dict | None = None, pages: dict | None = None, masters: dict | None = None) -> dict[str, bytes]:
    """Every generated file except kit.json, as {path in the kit: bytes}. SKILL.md carries the literal `<version>` in its version line (`with_version` puts the
    version in). A missing token file stops the run (exit 3), a missing band drawing (exit 1), a path that leaves the project (exit 2). `fonts` is the
    `font_plan`, `pages` the `reference_plan` and `masters` the `masters_plan` the caller already made (made here when not given)."""
    bookdata.tokens(project)   # exit 3 without tokens.json, naming `brand-creator tokens`
    if not (project / TOKENS_CSS).is_file():
        fail(EXIT_CANNOT, f"{TOKENS_CSS} not found; run `brand-creator tokens` first (the kit copies the built tokens)")
    files: dict[str, bytes] = {}
    for rel in (TOKENS_CSS, TOKENS_JSON):
        files[PREFIX + rel] = _project_file(project, rel, "token file")
    for rel in adapt.logo_paths(project):
        files[PREFIX + rel] = _project_file(project, rel, "logo file")
    rules, _ = qa_rules.load(project)
    for drawing in drawings(rules):
        files[PREFIX + drawing] = _drawing(project, drawing)
    fonts = fonts if fonts is not None else font_plan(project)
    files.update(fonts["files"])
    logo = logo_html(adapt.view(project)["name"], adapt.logo_paths(project))
    if logo:
        files[LOGO_HTML] = logo
    files.update(motion_files(project))
    rules_data = rules_doc(project)
    files[RULES_JSON] = json_bytes(rules_data)
    files[CHECKLIST_MD] = checklist_md(project, rules_data)
    files[INSTALL_PY] = (plugin_root() / "scripts" / "adaptlib" / "kitcopy.py").read_bytes()   # the installer the kit carries: the copy judge itself, byte for byte
    files[FACTS_JSON] = json_bytes(facts_doc(project))
    files.update(ground_plan(project)["files"])
    for more in (pages if pages is not None else reference_plan(project, fonts), masters if masters is not None else masters_plan(project)):
        for rel, data in more["files"].items():
            if files.setdefault(rel, data) != data:   # a file a page loads is a file the kit copies already (the tokens, a logo, a master): the same project file, so the same bytes
                fail(EXIT_FAIL, f"{rel} is planned twice with different bytes: the kit copies one project file to one place")
    held = {*files, SKILL_FILE, KIT_FILE, BRAND_MD, *OWNED_FILES}           # what the kit holds once it is written: the steps and the map name only these
    kit = {"prefix": PREFIX, "section": section(VERSION_PLACEHOLDER), "how": how_md(held), "map": map_md(held, own_entries(kit_dir(project)))}
    root = plugin_root() / KIT_TEMPLATES
    skill = adapt.applied_skill_md(project, (root / "kit-SKILL.md").read_text(encoding="utf-8"), kit=kit)
    brand = adapt.applied_skill_md(project, (root / "kit-brand.md").read_text(encoding="utf-8"), kit=kit)
    return {SKILL_FILE: skill.encode("utf-8"), BRAND_MD: brand.encode("utf-8"), **files}


def with_version(files: dict[str, bytes], version: str) -> dict[str, bytes]:
    """The plan with the version put into SKILL.md's version line (the first one: the kit section comes before everything the brand's own words fill in)."""
    line, text = version_line(VERSION_PLACEHOLDER), files[SKILL_FILE].decode("utf-8")
    if line not in text:
        fail(EXIT_USAGE, f"the applied-skill template has no {{{{kit}}}} line: the kit's SKILL.md would carry no version ({line!r} not found)")
    return {**files, SKILL_FILE: text.replace(line, version_line(version), 1).encode("utf-8")}


# ---------------------------------------------------------------- the version

def content_sha(generated: dict[str, str], owned: dict[str, str] | None = None) -> str:
    """sha256 over the sorted (path, sha256) pairs of the generated files except kit.json (SKILL.md as the plan holds it, with the literal `<version>`), plus the
    owner's files. The version is left out, so it can be decided from this."""
    h = hashlib.sha256()
    for path, sha in sorted({**generated, **(owned or {})}.items()):
        h.update(f"{path}\0{sha}\n".encode("utf-8"))
    return h.hexdigest()


def next_version(prev: dict | None, edition: str, csha: str) -> str:
    """`<edition>.<build>`. The build number starts at 1 and goes up by 1 when the content changed within an edition; the same edition and the same content keep the
    version; a new edition starts again at `<edition>.1`. `prev` is the record of the last build ({"version", "content_sha", optionally "edition"}) or None."""
    if not prev or not prev.get("version"):
        return f"{edition}.1"
    prev_edition, _, build = str(prev["version"]).partition(".")
    if str(prev.get("edition") or prev_edition) != edition or not build.isdigit():
        return f"{edition}.1"
    return str(prev["version"]) if prev.get("content_sha") == csha else f"{edition}.{int(build) + 1}"


def kit_json_bytes(project: Path, files: dict[str, bytes], version: str, edition: str, csha: str, src: dict, fonts: dict, owned: dict[str, str],
                   pages: dict | None = None, masters: dict | None = None) -> bytes:
    """kit.json for the generated files `files` (SKILL.md with the version in it); `fonts` is the `font_plan`, `owned` the owner's files with their sha256 (`owner_plan`), `pages` the
    `reference_plan` (none: the project has no approved reference page), `masters` the `masters_plan`; the fonts they bring are in kit.json `fonts` too (`fonts_record`)."""
    doc = {"schema": SCHEMA, "kit": adapt.skill_name(project), "version": version, "edition": edition, "plugin_version": plugin_version(), "content_sha": csha,
           "generated": {rel: sha256_bytes(data) for rel, data in sorted(files.items())}, "owned": dict(sorted(owned.items())), "fonts": fonts_record(fonts, pages, masters), "sources": src,
           "reference_pages": pages["records"] if pages is not None else []}
    return (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


# ---------------------------------------------------------------- the record of the last build


def previous(project: Path) -> dict | None:
    """What the last build wrote: {"outputs": {path in the kit: sha256}, "version", "content_sha"}. It is the `kit` report's (`outputs`, `kit_version`, `content_sha`: its own `version` is the plugin's).
    With no usable kit report, kit.json stands in for it (`_kit_json_record`: it is the version's only home), and after that the `applied-skill` report's output stands in for SKILL.md (the kit
    takes over a skill file that was generated). None when none exists, or a report holds no usable record."""
    doc = _json_object(project / REPORT) or {}
    out = doc.get("outputs")
    if isinstance(out, dict) and out and all(isinstance(k, str) and isinstance(v, str) for k, v in out.items()):
        return {"outputs": {k: v for k, v in out.items() if recorded_path(k)}, "version": doc.get("kit_version") if isinstance(doc.get("kit_version"), str) else None,
                "content_sha": doc.get("content_sha") if isinstance(doc.get("content_sha"), str) else None}
    if record := _kit_json_record(project):
        return record
    output = (_json_object(project / APPLIED_REPORT) or {}).get("output")
    sha = output.get("sha256") if isinstance(output, dict) else None
    return {"outputs": {SKILL_FILE: sha}, "version": None, "content_sha": None} if isinstance(sha, str) and sha else None


def _kit_json_record(project: Path) -> dict | None:
    """The record of the last build as kit.json holds it, for a build whose `kit` report is gone: its `generated` hashes, kit.json's own file as it is on disk (the one thing kit.json cannot
    list of itself), and its `version` and `content_sha`. So a file the last build wrote is not an edit by hand, and the version goes on from where it was. None when there is no kit.json, or it is
    not one this version reads (`problems`): a kit.json that cannot be trusted is no record, and the files stand as the owner's, as they did before kit.json was read."""
    try:
        f = kit_dir(project) / KIT_FILE
    except CliError:   # a slug that cannot be a skill name has no skill folder
        return None
    doc = None if f.is_symlink() else _json_object(f)   # a link is no kit.json of the last build: it is not read through
    if doc is None or problems(doc):
        return None
    return {"outputs": {**{k: v for k, v in doc["generated"].items() if recorded_path(k)}, KIT_FILE: sha256_file(f)}, "version": doc["version"], "content_sha": doc["content_sha"]}


# ---------------------------------------------------------------- kit check: files, links, fill markers, versions, sources, owner files
# `kit check` (scripts/kit.py) reads the kit and writes the report `kit-check`. Everything it reads is read from a plain file of the kit: a link inside the kit is never followed.

from html.parser import HTMLParser  # noqa: E402
from urllib.parse import unquote  # noqa: E402

from _common import STATE_FILE  # noqa: E402

CHECK_TOOL = "kit-check"                                    # the report of `kit check`: assets/_checks/kit-check.json
LINK_KINDS = {".md": "md", ".html": "html", ".htm": "html", ".css": "css"}   # the files whose relative links are checked, by their extension
FILL_MARKER = "[[fill"                                      # the note a scaffold leaves where the owner writes, any case
SITE_RECORD = "site/site.json"                              # the record of the approved reference pages: its choices tagged `rule` are rule ids (sitedata.SITE_FILE)
OWNED_MISSING = "is missing"                                # a scaffolded file the owner took away: the build writes the scaffold again
OWNED_REMOVED = "was removed since the last build"          # any other owner file the owner took away: the build forgets it
OWNED_NOT_FILE = "is no file the kit can read (a folder, or a link)"
_VERSION_LINE = re.compile(r"Kit version (\S+) \(kit\.json\)\.")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")
_MD_LINK = re.compile(r"\]\(\s*(<[^>\n]*>|[^\s)]*)")
_CSS_URL = re.compile(r"""url\(\s*(?:"([^"]*)"|'([^']*)'|([^)'"\s]*))\s*\)""", re.I)
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*):")
_ASCII_SPACE = "\t\n\f\r "                                  # ASCII whitespace as the HTML Standard defines it: TAB, LF, FF, CR and SPACE (not every Unicode space)


def kit_report(project: Path) -> dict | None:
    """The `kit` report (what the last build wrote) as a document, or None when there is none or it holds no JSON object."""
    return _json_object(project / REPORT)


def kit_paths(project: Path) -> list[str]:
    """`paths_in` the kit folder of the project."""
    return paths_in(kit_dir(project))


def is_judged(rel: str) -> bool:
    """False for an owner file that is not Markdown: it travels with the kit and `kit:fill`, `kit:tags` and `kit:numbers` never read it (`kit:links` still reads the relative links of a .html or .css file,
    as it does for every such file of the kit). True for every other file of the kit."""
    return not is_owner_path(rel) or Path(rel).suffix.lower() == ".md"


def tree_sha(project: Path) -> str:
    """One sha256 over the sorted paths of `kit_paths`, each marked file or link: a file added to the kit or taken out of it moves it, a change inside a file does not (the report's
    inputs say that)."""
    kd = kit_dir(project)
    return sha256_bytes("".join(f"{rel}\0{'link' if (kd / rel).is_symlink() else 'file'}\n" for rel in kit_paths(project)).encode("utf-8"))


def check_inputs(project: Path) -> list[Path]:
    """The files a `kit-check` report lists as inputs, so that any change makes it stale: every file under the kit folder (a link is no input), the files the kit is made from
    (`input_paths`), BRAND-STATE.md (the approved edition and the rules), site/site.json (the site choices that are rules; `known_rule_ids` reads it) and the `kit` report (what the build wrote)."""
    kd = kit_dir(project)
    own = [kd / rel for rel in kit_paths(project) if _plain_file(kd, rel)]
    return [*own, *(p for p in (project / STATE_FILE, project / REPORT, project / SITE_RECORD) if p.is_file()), *input_paths(project)]


def kit_bytes(project: Path, rel: str) -> bytes | None:
    """The bytes of a file of the kit, or None when it is not a plain file: missing, a folder, a link, or behind a link."""
    kd = kit_dir(project)
    if not _plain_file(kd, rel):
        return None
    try:
        return (kd / rel).read_bytes()
    except OSError:
        return None


def kit_text(project: Path, rel: str) -> str | None:
    """A file of the kit as text (UTF-8, a byte it cannot read replaced), or None when `kit_bytes` has none or the file is binary (a NUL byte in it)."""
    data = kit_bytes(project, rel)
    return None if data is None or b"\0" in data else data.decode("utf-8", errors="replace")


def files_check(project: Path, doc: dict, outputs: dict) -> dict:
    """kit.json against the kit folder: {"count": generated files listed, "differ": [(path, why)], "foreign": [paths], "kit_json": None or why it is not the bytes the `kit` report recorded}.
    A generated file differs when it is missing, is no plain file (a link, a folder), or has another sha256 than kit.json lists; a path kit.json lists that no kit holds is named and never
    opened. A foreign file is one in a generated folder that kit.json does not list (`on_disk`: a link counts, a Finder `.DS_Store` does not). `outputs` is the `kit` report's."""
    kd, listed = kit_dir(project), doc["generated"]
    differ = []
    for rel, sha in sorted(listed.items()):
        if not recorded_path(rel):
            differ.append((rel, "is no path a kit holds"))
        elif not os.path.lexists(kd / rel):
            differ.append((rel, "missing"))
        elif not _plain_file(kd, rel):
            differ.append((rel, "is a link or a folder, not a file"))
        elif sha256_file(kd / rel) != sha:
            differ.append((rel, "edited by hand"))
    kit_json = None
    if not _plain_file(kd, KIT_FILE):
        kit_json = "is a link or a folder, not a file"
    elif sha256_file(kd / KIT_FILE) != outputs.get(KIT_FILE):
        kit_json = "is not the bytes the kit report recorded: it was edited by hand"
    return {"count": len(listed), "differ": differ, "foreign": [rel for rel in on_disk(project) if rel not in listed], "kit_json": kit_json}


def fill_markers(project: Path) -> list[str]:
    """`<file>:<line>` of every `[[fill` (any case) in a text file of the kit, in path then line order. A file with a NUL byte in it is no text file, and neither is an owner file that is not Markdown (`is_judged`)."""
    out = []
    for rel in kit_paths(project):
        text = kit_text(project, rel) if is_judged(rel) else None
        if text is not None:
            out += [f"{rel}:{n}" for n, line in enumerate(text.split("\n"), 1) if FILL_MARKER in line.lower()]
    return out


def outside_fences(text: str):
    """The lines of a Markdown text that are not inside a fenced code block, as (line number from 1, line): the fence lines themselves are left out. A fence opens with three backticks
    or tildes (up to three spaces in), and closes with the same character, at least as many, and nothing after."""
    fence = None
    for n, raw in enumerate(text.split("\n"), 1):
        line = raw.rstrip("\r")
        m = _FENCE.match(line)
        if fence is None:
            if m and not (m.group(1)[0] == "`" and "`" in line[m.end():]):   # a backtick fence's info string holds no backtick
                fence = m.group(1)
                continue
            yield n, line
        elif m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not line[m.end():].strip():
            fence = None


def md_links(text: str) -> list[tuple[int, str]]:
    """The targets of `](target)` in a Markdown text as (line, target), outside fenced code blocks and inline code (a code span is not a link). `<...>` around a target is taken off and a
    title after it is not part of it."""
    out = []
    for n, line in outside_fences(text):
        line = _CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)
        out += [(n, m.group(1)[1:-1] if m.group(1).startswith("<") else m.group(1)) for m in _MD_LINK.finditer(line)]
    return out


def _srcset_urls(value: str) -> list[str]:
    """The URLs of a srcset value, read by the rule of the HTML Standard's "parse a srcset attribute" (WHATWG HTML, "Images": the splitting loop and the descriptor tokenizer):
    - Commas and ASCII whitespace in front of a candidate are skipped. The candidate's URL is the run of characters up to the next ASCII whitespace, so a comma inside it stays in it:
      `a.svg,b.svg 2x` is the one URL `a.svg,b.svg`, and a `data:` URI keeps its comma.
    - A URL that ends with a comma (a comma followed by whitespace or the end of the value, as in `a.svg, b.svg`) loses all its trailing commas and has no descriptor.
    - After any other URL, its descriptor runs up to the first comma outside parentheses, and that comma ends the candidate: `a.svg 1x,b.svg 2x` is `a.svg` with `1x`, then `b.svg` with `2x`."""
    urls, i, n = [], 0, len(value)
    while True:
        while i < n and (value[i] in _ASCII_SPACE or value[i] == ","):
            i += 1
        if i >= n:
            return urls
        j = i
        while j < n and value[j] not in _ASCII_SPACE:
            j += 1
        url, i = value[i:j], j
        if url.endswith(","):
            url = url.rstrip(",")
        else:
            in_parens = False
            while i < n:
                ch = value[i]
                i += 1
                if in_parens:
                    in_parens = ch != ")"
                elif ch == "(":
                    in_parens = True
                elif ch == ",":
                    break
        urls.append(url)


class _LinkParser(HTMLParser):
    """The `src`, `href` and `srcset` of the tags of an HTML text, each with the line of its tag. Comments and the text of script and style are not tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[tuple[int, str]] = []

    def handle_starttag(self, tag, attrs) -> None:
        for name, value in attrs:
            if value is None:
                continue
            if name in ("src", "href", "xlink:href"):
                self.found.append((self.getpos()[0], value))
            elif name == "srcset":
                self.found += [(self.getpos()[0], u) for u in _srcset_urls(value)]


def html_links(text: str) -> list[tuple[int, str]]:
    """The targets of `src=`, `href=` and `srcset=` in an HTML text as (line of the tag, target)."""
    p = _LinkParser()
    p.feed(text)
    p.close()
    return p.found


def css_links(text: str) -> list[tuple[int, str]]:
    """The targets of `url(...)` in a CSS text as (line, target), comments left out."""
    text = _CSS_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    return [(text.count("\n", 0, m.start()) + 1, next(g for g in m.groups() if g is not None)) for m in _CSS_URL.finditer(text)]


_LINK_READERS = {"md": md_links, "html": html_links, "css": css_links}
OUTSIDE = "points outside the kit: it will not resolve in a product repository"
ABSOLUTE = "an absolute path: it will not resolve in a product repository"
NO_SUCH_FILE = "no such file in the kit"


def _not_a_file(kd: Path, rel: str, serve: bool = True) -> str | None:
    """None when `rel` (a plain path in the kit) is a file of the kit, found with the exact letter case a Linux checkout needs and with no link on the way; else why not. A folder is the file its
    index.html is when it holds one (the way a web server answers a link to a folder, with `serve`); a folder without one is "a folder, not a file"."""
    cur = kd
    for part in rel.split("/"):
        try:
            names = os.listdir(cur)
        except OSError:
            return NO_SUCH_FILE
        if part not in names:
            alike = [n for n in names if n.lower() == part.lower()]
            return f"{NO_SUCH_FILE} ({alike[0]} is there: a product repository on Linux tells the letter case apart)" if alike else NO_SUCH_FILE
        cur = cur / part
        if cur.is_symlink():
            return "behind a link in the kit: a link is never followed"
    if cur.is_file():
        return None
    if serve and cur.is_dir() and _not_a_file(kd, posixpath.join(rel, "index.html"), serve=False) is None:
        return None
    return "a folder, not a file"


def link_path(from_rel: str, target: str) -> tuple[bool, str | None, str | None]:
    """(is it a relative link, the plain path in the kit it leads to, what is wrong with it before the kit is looked at). A fragment, a `?query`, an empty target, a network address (`//host`) and a
    link with a URL scheme (`http:`, `https:`, `mailto:`, `data:`, `tel:`, ...) are not relative links: (False, None, None). A relative link is percent-decoded and resolved from the folder of the
    file that holds it; it is an absolute path (a leading `/`, `file:`, a drive letter) or one that points outside the kit (no path then), or the path (`.` for the kit folder)."""
    path = target.strip().split("#")[0].split("?")[0]
    if not path or path.startswith("//"):
        return False, None, None
    m = _SCHEME.match(path)
    if m and len(m.group(1)) > 1 and m.group(1).lower() != "file":
        return False, None, None
    path = unquote(path)
    if path.startswith("/") or m:
        return True, None, ABSOLUTE
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(from_rel), path))
    if joined == ".." or joined.startswith("../"):
        return True, None, OUTSIDE
    return True, joined, None


def link_problem(project: Path, from_rel: str, target: str) -> tuple[bool, str | None]:
    """(is it a relative link, what is wrong with it). A relative link (`link_path`) must be an existing file inside the kit: otherwise it is an absolute path, one that points outside the kit, or a
    missing file. A link to a folder is the folder's index.html when the kit has one there, as a web server answers it; a folder without one fails."""
    relative, joined, why = link_path(from_rel, target)
    if not relative or why:
        return relative, why
    kd = kit_dir(project)
    if joined == ".":
        return True, None if _not_a_file(kd, "index.html", serve=False) is None else "a folder, not a file"
    return True, _not_a_file(kd, joined)


def unsupplied_fonts(doc: dict) -> dict[str, str]:
    """{path in the kit: reason} of every font kit.json lists as not copied (`fonts.not_copied`): a link to one of these can not resolve inside the kit, and is not a broken link either."""
    return {PREFIX + f["file"]: f["reason"] for f in doc["fonts"]["not_copied"]}


def link_check(project: Path, doc: dict | None = None) -> dict:
    """Every relative link of the kit's Markdown, HTML and CSS files (`LINK_KINDS`): {"files": files read, "links": relative links judged, "bad": [(file, line, target, why)], "unsupplied": [(file, line,
    target, path in the kit, reason)]}. With kit.json (`doc`), a link to a font it lists as not copied (`unsupplied_fonts`) is no broken link: it goes to "unsupplied" instead of "bad", so that the row
    can say the font must be supplied under its own licence. The font has to be missing from the kit and the link has to spell its path letter for letter."""
    files = links = 0
    bad, unsupplied = [], []
    listed = unsupplied_fonts(doc) if doc else {}
    for rel in kit_paths(project):
        kind = LINK_KINDS.get(Path(rel).suffix.lower())
        text = kit_text(project, rel) if kind else None
        if text is None:
            continue
        files += 1
        for line, target in _LINK_READERS[kind](text):
            relative, why = link_problem(project, rel, target)
            links += relative
            if why:
                at = link_path(rel, target)[1]
                if why == NO_SUCH_FILE and at in listed:
                    unsupplied.append((rel, line, target, at, listed[at]))
                else:
                    bad.append((rel, line, target, why))
    return {"files": files, "links": links, "bad": bad, "unsupplied": unsupplied}


def version_problems(project: Path, doc: dict) -> list[str]:
    """What is wrong with the version the kit states, each a sentence: SKILL.md must hold `Kit version <kit.json version> (kit.json).` exactly once and no other such line, the version must
    be of kit.json's own edition, and that edition must be the one BRAND-STATE.md approved."""
    bad = []
    text = kit_text(project, SKILL_FILE)
    if text is None:
        bad.append(f"{SKILL_FILE} is missing or is not a file")
    else:
        found = _VERSION_LINE.findall(text)
        if found != [doc["version"]]:
            said = ("has no version line" if not found else f"holds the version line {len(found)} times" if len(set(found)) == 1 and len(found) > 1
                    else "says version " + ", ".join(found))
            bad.append(f"{SKILL_FILE} {said} (kit.json says {doc['version']}): it must hold `{version_line(doc['version'])}` exactly once")
    if doc["version"].partition(".")[0] != doc["edition"]:
        bad.append(f"kit.json version {doc['version']} does not start with its edition {doc['edition']} (a version is <edition>.<build>)")
    approved = adapt.view(project)["approved_edition"]
    if doc["edition"] != approved:
        bad.append(f"the kit is of edition {doc['edition']}, the brand is at {approved or 'no approved edition'}: run `brand-creator kit build --yes`")
    return bad


def source_changes(project: Path, doc: dict) -> list[str]:
    """The keys of kit.json `sources` whose sha256 is not the one the project has now, in kit.json's order. May raise CliError when a source cannot be read."""
    now = sources(project)
    return [k for k in ALL_SOURCE_KEYS if now.get(k) != doc["sources"].get(k)]


def owned_changes(project: Path, doc: dict) -> list[tuple[str, str]]:
    """The owner's files that are not what kit.json `owned` recorded at the last build, as (path, why), the five scaffolded ones first (`owner_sorted`): another sha256, added since (a file of the
    owner's the last build did not record), missing (one of the five, which the build writes again), removed since (any other), or no file (a folder, a link: never read through)."""
    kd, out = kit_dir(project), []
    recorded = doc["owned"]
    for rel in owner_sorted({*recorded, *owner_paths(kd)}):
        data = kit_bytes(project, rel)
        if data is not None:
            if rel not in recorded:
                out.append((rel, OWNED_ADDED))
            elif sha256_bytes(data) != recorded[rel]:
                out.append((rel, OWNED_CHANGED))
        elif os.path.lexists(kd / rel):
            out.append((rel, OWNED_NOT_FILE))
        else:
            out.append((rel, OWNED_MISSING if rel in scaffolds(project) else OWNED_REMOVED))
    return out


BRAND_SOURCES = ("state_sha", "tokens", "tokens_css", "facts", "masters")   # the brand inputs an owner file is written against: BRAND-STATE.md (with the motion spec), the token files, FACTS.md, the approved masters
MASTER_RECIPES = ("recipes/ad.md", "recipes/presentation.md")   # the owner files that use the masters; with any file that names assets/masters/, the only ones a change to the masters alone makes behind


BRAND_SOURCE_NAMES = {"state_sha": "BRAND-STATE.md", "tokens": "tokens.json", "tokens_css": "tokens.css", "facts": "FACTS.md", "masters": "assets/masters/"}   # how the owner's line names a brand input


def behind_names(changed: list[str]) -> str:
    """The brand inputs of `changed` as the owner's line names them. `state_sha` also hashes FACTS.md and the motion spec, so it is named as BRAND-STATE.md only as far as it is known."""
    names = [BRAND_SOURCE_NAMES[k] for k in changed if k != "state_sha"]
    if "state_sha" in changed:
        if "facts" in changed:   # FACTS.md alone moves the hash, so BRAND-STATE.md is not known to have changed
            return ", ".join(names) + " (and possibly BRAND-STATE.md or the motion spec)"
        names.append("BRAND-STATE.md or the motion spec")
    return ", ".join(names)


def behind_files(project: Path, doc: dict) -> tuple[list[str], list[str]]:
    """(the keys of `BRAND_SOURCES` that changed since the last build, the owner's files that are still as that build recorded them). A file nobody has touched since the build was written against the
    brand the kit was built from, so once a brand input changed it is behind it; a file edited after the build is `owned_changes`' to report, and which brand it was written against is not known. May raise CliError
    when a source cannot be read."""
    changed = [k for k in source_changes(project, doc) if k in BRAND_SOURCES]
    if not changed:
        return [], []
    recorded = doc["owned"]
    files = [rel for rel in owner_sorted(recorded) if rel != "EXTENDING.md" and (data := kit_bytes(project, rel)) is not None and sha256_bytes(data) == recorded[rel]]   # EXTENDING.md is the plugin's guide, no brand content
    if changed == ["masters"]:   # the masters alone: only the files that use them
        files = [rel for rel in files if rel in MASTER_RECIPES or b"assets/masters/" in (kit_bytes(project, rel) or b"")]
        if not files:
            return [], []
    return changed, files


# ---------------------------------------------------------------- kit check, part 2: tags and values
# `tag_check` and `number_check` read the owner's recipes, `golden-rules.md`, `visual.md` and the generated `reference-pages/<id>/notes.md` (`judged_files`), as text from a plain file of the kit.
# A rule id is judged against `known_rule_ids` of the project, and only when a line names one: `known` is a function the caller gives, so a project that cites no rule needs no site record.
# When `known` cannot read the ids (a CliError), the lines that name a rule are left unjudged and counted (`unjudged`, `unread`); every other line is judged as always.

TAG_EXAMPLE = "[example]"                                    # the tag that says a line shows one case and is no rule
KIT_TOKENS_CSS = PREFIX + TOKENS_CSS                         # the token files as the kit holds them: a token reference is judged against these copies
KIT_TOKENS_JSON = PREFIX + TOKENS_JSON
ITEM_FILES = ("golden-rules.md", "visual.md")                # every bullet and every numbered line of these carries a tag
NO_TAG = "untagged"
TAG_HINT = ("tag each with `[example]` or `[rule: <id>]`, an id of rules.json (a rule of the brand written bare, `page:<id>`, `site:<id>`)")
VALUE_HINT = ("cite a token (`var(--name)` of tokens.css, `{dotted.path}` of tokens.json) or a known `[rule: <id>]`, or tag the line `[example]`")
_RULE_TAG = re.compile(r"\[rule:([^\]\n]*)\]")
_PLACEHOLDER_ID = re.compile(r"(?:(?:page|site):)?<[^<>]*>")   # `<id>`, `<rule id>`, `page:<id>`: the syntax of a tag, written as an example; no id of D12 holds an angle bracket
_BULLET = re.compile(r"^\s*[-*]\s")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s")
_THEMATIC_BREAK = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")   # `* * *` and `- - -` start with a bullet marker and are no bullet
_NOTES = re.compile(r"^reference-pages/[^/]+/notes\.md$")
_NUMBER = r"(?:\d+(?:\.\d+)?|\.\d+)"
_AFTER_VALUE = r"(?:(?<=\d(?:px|em|ms|vh|vw|ch|fr|pt)-)|(?<=\d(?:rem|svh|dvh|deg)-)|(?<=\d[s%]-))"   # a dash that follows a value: `2em-3em`, `16px-24px` (the lookbehinds are of one width each)
_VALUE = re.compile(                                          # what the owner's files must cite
    rf"(?<![\w.#])(?:(?<![A-Za-z_]-)|{_AFTER_VALUE}){_NUMBER}\s?(?:(?:px|rem|em|ms|s|vh|vw|svh|dvh|ch|fr|deg|pt)\b|%)"   # 48px, 0.5rem, 200ms, 100 %, -8px, and 48px of the range 32-48px or 24px of 16px-24px (not the end of a name such as `fs-16px`)
    rf"|(?<![\w.]){_NUMBER}:{_NUMBER}(?![\w:])"               # a ratio: 4.5:1
    r"|(?<![\w&])#(?:[0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{4}|[0-9a-f]{3})(?![\w-])"   # a hex colour (not an HTML entity)
    r"|(?<![\w-])(?:rgba?|hsla?|oklch)\(", re.I)              # rgb( hsl( oklch(, and their alpha forms
_LINK_TARGET = re.compile(r"\]\([^)]*\)")
_PROPERTY_NAME = re.compile(r"(?<![\w-])--[A-Za-z_][\w-]*")      # `--space-8px`, `--space-2-8px`: a custom property name holds numbers and is no value
_URL = re.compile(r"\b[A-Za-z][A-Za-z0-9+.\-]*://\S+")
_CSS_REF = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)")
_JSON_REF = re.compile(r"(?<![{$])\{([A-Za-z_][\w-]*(?:\.[\w-]+)+)\}(?!\})")
_CUSTOM_PROPERTY = re.compile(r"(?<![\w-])(--[A-Za-z0-9_-]+)\s*:")


def judged_files(project: Path) -> list[tuple[str, str]]:
    """The files of the kit whose lines need a tag and whose values need a citation, as (path in the kit, kind), sorted: every Markdown file of the owner's other than `EXTENDING.md` and `voice.md` (the
    recipes under `recipes/` at any depth, and a file of her own anywhere else), and the generated `reference-pages/<id>/notes.md` (kind `bullets`: a bullet carries a tag, a numbered step needs none), and
    `golden-rules.md` and `visual.md` (kind `items`: a numbered line carries one too). An owner file that is not Markdown is none of them."""
    out = []
    for rel in kit_paths(project):
        if rel in ITEM_FILES:
            out.append((rel, "items"))
        elif _NOTES.match(rel) or (is_owner_path(rel) and Path(rel).suffix.lower() == ".md" and rel not in UNJUDGED_OWNED):
            out.append((rel, "bullets"))
    return out


def rule_tags(line: str) -> list[str]:
    """The ids named by the `[rule: <id>]` tags of a line, each trimmed, in order (an empty tag gives an empty id). A tag whose id is a placeholder in angle brackets (`[rule: <id>]`,
    `[rule: <rule id>]`, `[rule: page:<id>]`, `[rule: site:<id>]`: a whole `<...>`, after `page:` or `site:` or not) names no id and is no citation: it shows the syntax, and a real id never holds an angle
    bracket (D12). It is left out here, so `kit:tags` and `kit:numbers` read it as the plain text it is."""
    ids = (m.group(1).strip() for m in _RULE_TAG.finditer(line))
    return [i for i in ids if not _PLACEHOLDER_ID.fullmatch(i)]


def needs_tag(line: str, kind: str) -> bool:
    """Whether a line outside a code fence must carry a tag: a bullet (`- ` or `* `, indented or not, a thematic break such as `* * *` is none) in any judged file, and a numbered line (`1. ` or `1) `) in an `items` file."""
    if _THEMATIC_BREAK.match(line):
        return False
    return bool(_BULLET.match(line) or (kind == "items" and _NUMBERED.match(line)))


def _unknown_ids(ids: list[str], known, state: dict) -> list[str] | None:
    """The ids of `ids` that `known()` does not list, or None when the rule ids cannot be read (the CliError is kept in `state["unread"]`, and `known` is not asked again)."""
    if state.get("unread") is None:
        try:
            return [i for i in ids if i not in known()]
        except CliError as e:
            state["unread"] = e
    return None


def tag_check(project: Path, known) -> dict:
    """Every line that needs a tag (`needs_tag`, outside code fences) carries `[example]` or `[rule: <id>]`, and every id a line names, on any line (a numbered step of a recipe, a plain
    sentence, a heading, a line inside a code fence), is one of `known()` (a function returning the ids; it is called only for a line that names one). Returns {"files": judged files read,
    "lines": lines judged (those that need a tag, and those that name a rule), "bad": [(path, line, why)], "unjudged": lines that name a rule and were not judged, "unread": the CliError of
    `known()` or None}: why is "untagged" or "unknown rule id <id>" (an id listed once per tag; an empty tag is "(empty)"). A tag that names an unknown id fails even when `[example]` is on the
    line too. When `known()` raises CliError the lines that name a rule are not judged (`unjudged`); the untagged ones still are."""
    files = lines = unjudged = 0
    state: dict = {}
    bad = []
    for rel, kind in judged_files(project):
        text = kit_text(project, rel)
        if text is None:
            continue
        files += 1
        outside = {n for n, _ in outside_fences(text)}
        for n, raw in enumerate(text.split("\n"), 1):
            line = raw.rstrip("\r")
            ids = rule_tags(line)
            if not ids and not (n in outside and needs_tag(line, kind)):
                continue
            lines += 1
            unknown = _unknown_ids(ids, known, state) if ids else []
            if unknown is None:
                unjudged += 1
            elif unknown:
                bad.append((rel, n, "unknown rule id " + ", ".join(i or "(empty)" for i in unknown)))
            elif not ids and TAG_EXAMPLE not in line:
                bad.append((rel, n, NO_TAG))
    return {"files": files, "lines": lines, "bad": bad, "unjudged": unjudged, "unread": state.get("unread")}


def find_values(line: str) -> list[str]:
    """The values in a line of text, in order, as written: a number with a unit (`px`, `rem`, `em`, `ms`, `s`, `%`, `vh`, `vw`, `svh`, `dvh`, `ch`, `fr`, `deg`, `pt`), a ratio like `4.5:1` (a clock
    time such as `9:00` reads as one), a hex colour (3, 4, 6 or 8 digits) and `rgb(`, `rgba(`, `hsl(`, `hsla(` or `oklch(`. A range such as `32-48px` is the value `48px`: the dash follows a number; `16px-24px` is both, the dash follows a value. The words
    of a `[rule: ...]` tag, a link target and a URL are no values, and neither is the number inside a name such as `--space-8px` or `fs-16px`: a dash that follows a letter."""
    for rx in (_RULE_TAG, _LINK_TARGET, _URL, _PROPERTY_NAME):
        line = rx.sub(lambda m: " " * len(m.group(0)), line)
    return [m.group(0) for m in _VALUE.finditer(line)]


def token_refs(line: str) -> tuple[list[str], list[str]]:
    """The token references of a line: (the names of `var(--name)`, the paths of `{dotted.path}` with at least one dot), each in order."""
    return _CSS_REF.findall(line), _JSON_REF.findall(line)


def css_token_names(project: Path) -> set[str] | None:
    """The custom properties (`--name`) tokens.css of the kit declares, or None when the kit has no such file."""
    css = kit_text(project, KIT_TOKENS_CSS)
    return None if css is None else set(_CUSTOM_PROPERTY.findall(_CSS_COMMENT.sub(" ", css)))


def json_token_paths(doc: dict) -> set[str]:
    """The paths `{dotted.path}` may name in the kit's tokens.json: only a path that ends at a token, never at a group or at a part of a token. The tokens are the keys of `primitives`, of `other`,
    of each mode of `modes`, and of `motion.durations_ms` and `motion.curves` (build_tokens writes them so; a key may hold dots itself: `color.bg`). A token is named by its key as its group holds it
    (`color.bg`, `dimension.space-1`; a motion token by its key in `other`, which holds the same names) or by the path from the top (`primitives.color.ink`, `other.dimension.space-1`,
    `modes.light.color.bg`, `motion.durations_ms.duration.fast`). A group (`modes.light`, `motion.durations_ms`), a part of a token (`modes.light.color.bg.hex`) and the rest of the file
    (`pairs`, `touching`, `grounds`, `$generator`) name no token."""
    def keys(*path: str) -> list[str]:
        node = doc
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
        return list(node) if isinstance(node, dict) else []

    groups = [("primitives",), ("other",), ("motion", "durations_ms"), ("motion", "curves"), *(("modes", mode) for mode in keys("modes"))]
    out: set[str] = set()
    for group in groups:
        for key in keys(*group):
            out.add(".".join((*group, key)))
            if group[0] in ("primitives", "other", "modes"):
                out.add(key)
    return out


def json_token_names(project: Path) -> set[str] | None:
    """`json_token_paths` of the kit's tokens.json, or None when the kit has no such file or it holds no JSON object."""
    text = kit_text(project, KIT_TOKENS_JSON)
    try:
        doc = json.loads(text) if text is not None else None
    except ValueError:
        return None
    return json_token_paths(doc) if isinstance(doc, dict) else None


def number_check(project: Path, known) -> dict:
    """Every value (`find_values`) in a judged file, code fences included, has a citation on its own line: `[example]`, a `[rule: <id>]` of `known()`, or a token reference that exists
    (`var(--name)` declared in the kit's tokens.css, `{dotted.path}` in the kit's tokens.json). A token reference that does not exist fails and never counts as a citation: `[example]` does not
    excuse it. Outside a code fence it is judged on every line, with a value or not (prose is no place for a token that was never made); inside a code fence only on a line that holds a value, where it
    is the citation (a component sample is full of braces and custom properties of its own). A `[rule: <id>]` of an unknown id on a line with a value fails too. `known` is as for `tag_check`; when
    it cannot read the ids, a line that names a rule is not judged for its rule (`unjudged`), the failures that need no rule id are still found. Returns {"files": judged files read, "lines": lines
    with a value, "values": values found, "bad": [(path, line, why)], "unjudged": lines with a value that name a rule and were not judged, "unread": the CliError of `known()` or None}: why
    joins the reasons with "; "."""
    seen: dict[str, set[str] | None] = {}
    state: dict = {}

    def tokens() -> tuple[set[str] | None, set[str] | None]:
        if not seen:
            seen["css"], seen["json"] = css_token_names(project), json_token_names(project)
        return seen["css"], seen["json"]

    files = lines = values = unjudged = 0
    bad = []
    for rel, _kind in judged_files(project):
        text = kit_text(project, rel)
        if text is None:
            continue
        files += 1
        outside = {n for n, _ in outside_fences(text)}
        for n, raw in enumerate(text.split("\n"), 1):
            line = raw.rstrip("\r")
            found = find_values(line)
            css_refs, json_refs = token_refs(line) if found or n in outside else ([], [])   # a reference is judged on a line with a value, and on any line outside a code fence
            if not found and not css_refs and not json_refs:
                continue
            if found:
                lines, values = lines + 1, values + len(found)
            why, cited = [], TAG_EXAMPLE in line
            if css_refs or json_refs:
                css, js = tokens()
                for ref in css_refs:
                    if css is not None and ref in css:
                        cited = True
                    else:
                        why.append(f"var({ref}) is not declared in {KIT_TOKENS_CSS}" + (" (that file is missing)" if css is None else ""))
                for ref in json_refs:
                    if js is not None and ref in js:
                        cited = True
                    else:
                        why.append(f"{{{ref}}} is not a path in {KIT_TOKENS_JSON}" + (" (that file is missing or holds no JSON object)" if js is None else ""))
            if not found:                            # a line with no value has nothing to cite: only a token that does not exist is wrong
                if why:
                    bad.append((rel, n, "; ".join(why)))
                continue
            ids = rule_tags(line)
            unknown = _unknown_ids(ids, known, state) if ids else []
            if unknown is None:                      # the ids cannot be read: what the rule tags might cite is not known, what everything else says still is
                unjudged += 1
                if why:
                    bad.append((rel, n, "; ".join(why)))
                continue
            cited = cited or len(ids) > len(unknown)
            if unknown:
                why.insert(0, "unknown rule id " + ", ".join(i or "(empty)" for i in unknown))
            if not cited:
                unique = list(dict.fromkeys(found))
                why.insert(0, f"{_and(unique)} {'has' if len(unique) == 1 else 'have'} no citation")
            if why:
                bad.append((rel, n, "; ".join(why)))
    return {"files": files, "lines": lines, "values": values, "bad": bad, "unjudged": unjudged, "unread": state.get("unread")}


# ---------------------------------------------------------------- kit check: one row for each reference page
# `kit check` writes the row `kit:reference-page:<id>` for each page kit.json lists (`reference_page_states`). The kit is downstream of the pack: lib/stale.py hashes scripts/lib/*.py and the pack's
# own files, so a change of the tokens or the rules does not make the kit stale by itself. The kit records its own sources instead, and for each page what its page-check report and its capture.json
# were made from (`page_check_inputs_sha`, `capture_inputs_sha`); the row compares those with the two records now. It reads the project's records, not the kit's copies (`kit:files` does),
# and writes nothing.

PAGE_ROW = "kit:reference-page:"                            # + the page id
BUILD_AGAIN = "`brand-creator kit build --yes`"


def _redo(page: str) -> str:
    """What brings a reference page's check and stills up to date, and then the kit."""
    return f"run `brand-creator page-check {page}` and `brand-creator capture {page}`, then {BUILD_AGAIN}"


def _record_state(project: Path, where: str, page: str) -> tuple[dict | None, str, str]:
    """(document, "ok" | "stale" | "unusable", why) of the JSON record at `where` (a page-check report or a capture.json) as it stands for `page`. "unusable": it is not a plain file inside the project,
    is missing, cannot be read, or does not list the page among the files it was made from (a change to the page would never make it stale). "stale": a file it was made from is gone or changed
    (`stale_inputs`, the one rule `check` applies). The document is returned for "ok" and "stale" only, None for "unusable"."""
    try:
        f = confine(project, where, what="record", read=True)
    except CliError as e:
        return None, "unusable", e.message
    if not f.is_file():
        return None, "unusable", f"{where} is missing"
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
        stale = stale_inputs(project, doc)
        listed = {r.get("path") for r in doc["inputs"] if isinstance(r, dict)}
        Report.inputs_sha(doc["inputs"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None, "unusable", f"{where} cannot be read"
    if stale:
        return doc, "stale", "; ".join(stale[:2])
    if page not in listed:
        return None, "unusable", f"{where} does not list the page among the files it was made from"
    return doc, "ok", ""


def _reference_page_state(project: Path, record: dict, entry: dict | None) -> tuple[str, str]:
    """(status, detail) of one page of kit.json `reference_pages`; `entry` is the page as site/site.json holds it now ({id, path, layout, sha256}), None when it no longer lists the page.
    The first that applies wins:

    1. skipped, "the page changed in the project since the kit was built": the record's sha256 for the page, or the page file itself, is not `source_sha`. This goes first: a page approved again has a
       new page-check report and new stills whose inputs differ because of the page, and the tokens did not change. The page file is read only as a file inside the project: a page that is a link
       leading out is skipped, "the page cannot be used", and never hashed (when the record's sha256 already differs, the page is not read at all).
    2. skipped, "the tokens or rules changed since this page was checked": its page-check report is stale (a file it was made from changed).
    3. skipped, "cannot be used": the page-check report is missing, cannot be read, is of another target or does not list the page.
    4. fail: the page-check report is current and failing. A definite failure is not hidden behind a stale capture.json or behind inputs that differ from the kit's.
    5. skipped, as 2 and 3, for capture.json.
    6. skipped, "gives no verdict": the page-check report is neither a pass nor a fail.
    7. skipped, as 2: the report or capture.json is current but made from other files than the ones the kit was built from (`page_check_inputs_sha`, `capture_inputs_sha`).
    8. pass."""
    import pagecheck   # scripts/pagelib, on the path of `kit` and `check`: the one rule that names the report of a page
    pid = record["id"]
    page = f"{SITE_DIR}/{pid}/index.html"
    redo, changed = _redo(page), "the tokens or rules changed since this page was checked"
    note = " (site/site.json no longer lists it)" if entry is None else ""
    page_changed = f"not verified: the page changed in the project since the kit was built{note}: {BUILD_AGAIN}"
    if entry is None or entry.get("sha256") != record["source_sha"]:
        return "skipped", page_changed                                                      # decided from the record alone: the page is not read
    try:
        confine(project, page, what="page", read=True)                                      # a page that is a link leading out of the project is never hashed
    except CliError as e:
        return "skipped", f"not verified: the page {page} cannot be used ({e.message}): {BUILD_AGAIN} after fixing it"
    if _sha_or_none(project, page) != record["source_sha"]:
        return "skipped", page_changed
    where = f"assets/_checks/{pagecheck.report_tool(page)}.json"
    checked, state, why = _record_state(project, where, page)
    if state == "stale":
        return "skipped", f"not verified: {changed}: {redo}"
    target = checked.get("target") if checked is not None else None
    if state == "ok" and not (isinstance(target, dict) and target.get("kind") == "project" and target.get("page") == page):
        state, why = "unusable", f"{where} is the report of another target"
    if state != "ok":
        return "skipped", f"not verified: the page-check report of {page} cannot be used ({why}): {redo}"
    if checked.get("status") == "fail":
        return "fail", (f"{page} fails its page check ({_failing(checked)}; see {where}): a reference page is a page that passes, so change it, approve it again "
                        f"(`brand-creator site approve --replace`), then {redo}")
    shots = f"{SITE_DIR}/{pid}/shots/capture.json"
    stills, state, why = _record_state(project, shots, page)
    if state == "stale":
        return "skipped", f"not verified: {changed}: {redo}"
    source = stills.get("source") if stills is not None else None
    if state == "ok" and not (isinstance(source, dict) and source.get("page") == page):
        state, why = "unusable", f"{shots} is the capture of another page"
    if state != "ok":
        return "skipped", f"not verified: the stills of {page} cannot be used ({why}): {redo}"
    if checked.get("status") != "pass":
        return "skipped", f"not verified: the page-check report of {page} gives no verdict (status {checked.get('status')!r}; see {where}): {redo}"
    if checked.get("inputs_sha") != record["page_check_inputs_sha"] or Report.inputs_sha(stills["inputs"]) != record["capture_inputs_sha"]:
        return "skipped", f"not verified: {changed}: {redo}"
    return "pass", f"{page} is the page the kit holds, its page check passes, and its report and stills were made from the files the kit was built from"


def reference_page_states(project: Path, doc: dict) -> list[tuple[str, str, str]]:
    """(page id, status, detail) for each page of kit.json `reference_pages`, in its order; [] when it holds none (the project's site/site.json is not read then). The record is read once: when it
    cannot be read, every page is skipped, naming why."""
    records = doc["reference_pages"]
    if not records:
        return []
    import sitedata   # scripts/boardlib, on the path of `kit` and `check`
    try:
        confine(project, SITE_RECORD, what="site record", read=True)
        sitedata.load_site(project)
    except CliError as e:
        return [(r["id"], "skipped", f"not verified: the approved pages cannot be read ({e.message}): {BUILD_AGAIN} after fixing it") for r in records]
    listed = {p["id"]: p for p in site_pages(project)}
    return [(r["id"], *_reference_page_state(project, r, listed.get(r["id"]))) for r in records]


# ---------------------------------------------------------------- what is on disk

def on_disk(project: Path) -> list[str]:
    """The paths in the kit of every file inside a generated folder, sorted. A file named exactly `.DS_Store` (what Finder leaves in a folder it opened) is left out: it is neither
    foreign nor moved nor planned. A link to a folder is listed as the one path it is, and never followed, and so is a generated folder that is itself a link: nothing is listed, read
    or moved through a link."""
    kd, out = kit_dir(project), []
    for d in GENERATED_DIRS:
        if (kd / d).is_symlink():
            out.append(d)
            continue
        for root, dirs, names in os.walk(kd / d):
            out += [(Path(root) / n).relative_to(kd).as_posix() for n in names if n != FINDER_FILE]
            out += [(Path(root) / n).relative_to(kd).as_posix() for n in dirs if (Path(root) / n).is_symlink()]
    return sorted(out)


def scan(project: Path, files: dict[str, bytes], recorded: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    """Compare the kit folder with the plan `files` (everything the build would write, kit.json included) and the record of the last build `recorded`
    ({path: sha256}). Returns (edited, foreign, retired), each sorted paths in the kit:
    - edited: a planned file on disk whose bytes differ from the plan and whose sha256 is not the recorded one (somebody changed it);
    - foreign: a file inside a generated folder that is neither planned nor recorded (somebody put it there); and every link, whatever it points at and wherever it sits (in a generated
      folder, at the path of a file the kit writes, a generated folder that is a link, or one of the files at the top of the kit folder): a link is never read through, written through or
      followed, it is moved aside as it is;
    - retired: recorded before, no longer planned, still on disk (a logo taken out of the project): moved aside, not stopped on."""
    kd = kit_dir(project)
    edited = sorted(rel for rel, data in files.items() if _plain_file(kd, rel) and (kd / rel).read_bytes() != data and sha256_file(kd / rel) != recorded.get(rel))
    foreign = {rel for rel in on_disk(project) if (rel not in files and rel not in recorded) or (kd / rel).is_symlink()}
    foreign |= {rel for rel in ROOT_FILES if rel in files and (kd / rel).is_symlink()}   # these sit outside the generated folders, and the build writes them all the same
    retired = sorted(rel for rel in recorded if rel not in files and _plain_file(kd, rel))
    return edited, sorted(foreign), retired


# ---------------------------------------------------------------- kit status: is the copy in a product repository current?
# `kit status --repo` (scripts/kit.py) compares the kit folder of the project with the folder a product repository holds, and only reads. Nothing here writes, and a link is never read through.


def compare(kit: Path, installed: Path) -> dict:
    """`kitcopy.compare`, with a KitError turned into the plugin's failure (exit code and message kept)."""
    try:
        return _compare(kit, installed)
    except KitError as e:
        fail(e.code, e.message)

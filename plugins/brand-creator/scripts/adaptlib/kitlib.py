"""The brand kit as data: where it sits, what it holds, which version it is, and what it was made from.

The kit is the per-brand applied skill's folder (`.claude/skills/<slug>-brand/`) with more in it: the brand's own files copied in byte for byte at their
project paths under `brand/`, and `kit.json`, which records the sha256 of every generated file. SKILL.md is still written by `adapt.applied_skill_md`; here it
is asked for with the kit's paths and a "## The kit" section. See scripts/CONTRACT.md ("kit").

Shared by `brand-creator kit` (scripts/kit.py) and `brand-creator check`. It sits beside adapt.py, outside scripts/lib/, for the same reason: a change here must
not make every pack stale (lib/stale.py hashes scripts/lib/*.py). Standard library only. No clock and no random numbers: the same inputs give the same bytes.

`plan(project)` is every generated file except kit.json, as {path in the kit: bytes}, with SKILL.md carrying the literal `<version>` in its version line. The
version is decided from what the plan holds (`content_sha`, `next_version`) and then put into SKILL.md (`with_version`), so SKILL.md never has to be written twice.
"""
from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
from pathlib import Path

import adapt
import bookdata
import motionspec
import qa_rules
from _common import EXIT_CANNOT, EXIT_FAIL, EXIT_USAGE, CliError, confine, fail, plugin_root, plugin_version, sha256_bytes, sha256_file

KIT_FILE = "kit.json"
SCHEMA = 1
SKILL_FILE = "SKILL.md"
GENERATED_DIRS = ("brand", "snippets", "reference-pages")   # a file in one of these that the kit did not write is a foreign file
PREFIX = "brand/"                                           # where the project's files sit inside the kit: project path = PREFIX + path
TOKENS_JSON = "assets/tokens/tokens.json"
TOKENS_CSS = "assets/tokens/tokens.css"
FACTS_FILE = "FACTS.md"
VERSION_PLACEHOLDER = "<version>"
REPORT = "assets/_checks/kit.json"                          # the report of `kit build`: the record of what was last written
APPLIED_REPORT = "assets/_checks/applied-skill.json"        # stands in for it when the kit takes over a skill file that `applied-skill` wrote

# The keys kit.json may hold. Each task that adds a key adds it here, so that `load` can refuse every other one.
TOP_KEYS = ("schema", "kit", "version", "edition", "plugin_version", "content_sha", "generated", "sources")
SOURCE_KEYS = ("state_sha", "tokens", "tokens_css", "rules", "facts", "motion", "logos")

_SHA = re.compile(r"[0-9a-f]{64}")
_VERSION = re.compile(r"[1-9][0-9]*\.[1-9][0-9]*")
_EDITION = re.compile(r"[1-9][0-9]*")


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


def problems(doc) -> list[str]:
    """What is wrong with a kit.json document, each as a sentence that names the key; [] when it is a kit.json this version reads."""
    if not isinstance(doc, dict):
        return ["the document must be a JSON object"]
    bad = [f"{k}: unknown key (allowed: {', '.join(TOP_KEYS)})" for k in doc if k not in TOP_KEYS]
    bad += [f"{k}: missing" for k in TOP_KEYS if k not in doc]
    if "schema" in doc and (type(doc["schema"]) is not int or doc["schema"] != SCHEMA):
        bad.append(f"schema: unknown schema {json.dumps(doc['schema'])} (this version reads {SCHEMA})")
    for k, rx in (("version", _VERSION), ("edition", _EDITION), ("content_sha", _SHA)):
        if k in doc and not (isinstance(doc[k], str) and rx.fullmatch(doc[k])):
            bad.append(f"{k}: must be a string like {'1.3' if k == 'version' else '1' if k == 'edition' else 'a sha256'}, got {json.dumps(doc[k])}")
    for k in ("kit", "plugin_version"):
        if k in doc and not (isinstance(doc[k], str) and doc[k].strip()):
            bad.append(f"{k}: must be a non-empty string")
    gen = doc.get("generated")
    if "generated" in doc and not (isinstance(gen, dict) and all(isinstance(p, str) and isinstance(s, str) and _SHA.fullmatch(s) for p, s in gen.items())):
        bad.append("generated: must be an object of path in the kit -> sha256")
    src = doc.get("sources")
    if "sources" in doc:
        if not isinstance(src, dict):
            bad.append("sources: must be an object")
        else:
            bad += [f"sources.{k}: unknown key (allowed: {', '.join(SOURCE_KEYS)})" for k in src if k not in SOURCE_KEYS]
            bad += [f"sources.{k}: missing" for k in SOURCE_KEYS if k not in src]
            bad += [f"sources.{k}: must be a sha256 or null" for k, v in src.items() if k in SOURCE_KEYS and not (v is None or (isinstance(v, str) and _SHA.fullmatch(v)))]
    return bad


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
    motion spec, as `adapt.state_sha`), the two token files, qa/rules.json, FACTS.md, motion/motion.json and the logo files with the band drawings. kit.json records
    them, so a later run can tell what changed after the kit was built."""
    h = hashlib.sha256()
    for rel in source_paths(project):
        h.update(f"{rel}\0{_sha_or_none(project, rel) or 'missing'}\n".encode())
    return {"state_sha": adapt.state_sha(project), "tokens": _sha_or_none(project, TOKENS_JSON), "tokens_css": _sha_or_none(project, TOKENS_CSS),
            "rules": _sha_or_none(project, qa_rules.RULES_FILE), "facts": _sha_or_none(project, FACTS_FILE), "motion": _sha_or_none(project, motionspec.FILE),
            "logos": h.hexdigest()}


def sources_sha(project: Path, src: dict | None = None) -> str:
    """One sha256 over `sources` (computed again unless `src` is given)."""
    return sha256_bytes(json.dumps(src if src is not None else sources(project), sort_keys=True, ensure_ascii=False).encode("utf-8"))


def input_paths(project: Path) -> list[Path]:
    """The files a `kit` report lists as inputs, each only when the project has it: the token files, the logo files and band drawings, qa/rules.json, FACTS.md, motion/motion.json."""
    rels = [TOKENS_CSS, TOKENS_JSON, *source_paths(project), qa_rules.RULES_FILE, FACTS_FILE, motionspec.FILE]
    return [project / r for r in rels if (project / r).is_file()]


# ---------------------------------------------------------------- the plan

def _project_file(project: Path, rel: str, what: str) -> bytes:
    f = confine(project, rel, what=what, read=True)
    if not f.is_file():
        fail(EXIT_FAIL, f"{what} {rel} is not in the project: {'run `brand-creator tokens`' if rel.startswith('assets/tokens/') else 'add it, or change qa/rules.json'}")
    return f.read_bytes()


def _drawing(project: Path, drawing: str) -> bytes:
    """The bytes of a band drawing. It is named by its plain path in the project, because the kit mirrors project paths and SKILL.md names it by the same string."""
    confine(project, drawing, what="band drawing", read=True)   # outside the project: exit 2
    if drawing != posixpath.normpath(drawing) or posixpath.isabs(drawing):
        plain = posixpath.normpath(drawing)
        if posixpath.isabs(plain):   # an absolute path inside the project: the plain path is the one below the project folder (named with or without its links resolved)
            below = [posixpath.relpath(plain, root) for root in (os.path.abspath(project), os.path.realpath(project))]
            plain = next((r for r in below if not r.startswith("..")), plain)
        fail(EXIT_USAGE, f"qa/rules.json: the band drawing {drawing!r} must be written as a plain path inside the project ({plain!r}): "
                         "the kit names it by the path it has in the project")
    f = project / drawing
    if not f.is_file():
        fail(EXIT_FAIL, f"qa/rules.json names the band drawing {drawing} but the project has no such file: add it, or change qa/rules.json")
    return f.read_bytes()


def section(version: str, rels: list[str]) -> str:
    """The kit section of SKILL.md (the template's {{kit}}): the version line, then the generated files. `rels` are the paths in the kit of the generated files
    other than SKILL.md and kit.json, so a task that adds files to the plan needs no edit here."""
    L = ["## The kit", "", version_line(version), "",
         "This folder is a brand kit. This skill is its core. The files below sit beside it, copied byte for byte from the brand project and locked by `kit.json`.", "",
         "Generated. Never edit these here: change the brand project and run `brand-creator kit build --yes` again.", ""]
    L += [f"- `{r}`" for r in sorted(rels)]
    return "\n".join(L)


def plan(project: Path) -> dict[str, bytes]:
    """Every generated file except kit.json, as {path in the kit: bytes}. SKILL.md carries the literal `<version>` in its version line (`with_version` puts the
    version in). A missing token file stops the run (exit 3), a missing band drawing (exit 1), a path that leaves the project (exit 2)."""
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
    template = (plugin_root() / "templates" / "applied-skill" / "SKILL.md").read_text(encoding="utf-8")
    skill = adapt.applied_skill_md(project, template, kit={"prefix": PREFIX, "section": section(VERSION_PLACEHOLDER, sorted(files))})
    return {SKILL_FILE: skill.encode("utf-8"), **files}


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


def kit_json_bytes(project: Path, files: dict[str, bytes], version: str, edition: str, csha: str, src: dict) -> bytes:
    """kit.json for the generated files `files` (SKILL.md with the version in it)."""
    doc = {"schema": SCHEMA, "kit": adapt.skill_name(project), "version": version, "edition": edition, "plugin_version": plugin_version(), "content_sha": csha,
           "generated": {rel: sha256_bytes(data) for rel, data in sorted(files.items())}, "sources": src}
    return (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


# ---------------------------------------------------------------- the record of the last build

def previous(project: Path) -> dict | None:
    """What the last build wrote: {"outputs": {path in the kit: sha256}, "version", "content_sha"}. It is the `kit` report's (`outputs`, `kit_version`, `content_sha`: its own `version` is the plugin's). With no kit report, the `applied-skill`
    report's output stands in for SKILL.md (the kit takes over a skill file that was generated). None when neither exists, or a report holds no usable record."""
    for rel in (REPORT, APPLIED_REPORT):
        f = project / rel
        try:
            doc = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
        except (OSError, ValueError):
            doc = None
        if not isinstance(doc, dict):
            continue
        if rel == REPORT:
            out = doc.get("outputs")
            if isinstance(out, dict) and out and all(isinstance(k, str) and isinstance(v, str) for k, v in out.items()):
                return {"outputs": {k: v for k, v in out.items() if recorded_path(k)}, "version": doc.get("kit_version") if isinstance(doc.get("kit_version"), str) else None,
                        "content_sha": doc.get("content_sha") if isinstance(doc.get("content_sha"), str) else None}
            continue
        sha = (doc.get("output") or {}).get("sha256") if isinstance(doc.get("output"), dict) else None
        if isinstance(sha, str) and sha:
            return {"outputs": {SKILL_FILE: sha}, "version": None, "content_sha": None}
    return None


def recorded_path(rel: str) -> bool:
    """A path a record may name: SKILL.md, kit.json, or a plain path under one of the generated folders. Anything else (a path that climbs out of the kit) is not read."""
    return rel in (SKILL_FILE, KIT_FILE) or (posixpath.normpath(rel) == rel and not posixpath.isabs(rel) and rel.split("/")[0] in GENERATED_DIRS and not rel.endswith("/"))


# ---------------------------------------------------------------- what is on disk

def on_disk(project: Path) -> list[str]:
    """The paths in the kit of every file inside a generated folder, sorted."""
    kd, out = kit_dir(project), []
    for d in GENERATED_DIRS:
        for root, _dirs, names in os.walk(kd / d):
            out += [(Path(root) / n).relative_to(kd).as_posix() for n in names]
    return sorted(out)


def scan(project: Path, files: dict[str, bytes], recorded: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    """Compare the kit folder with the plan `files` (everything the build would write, kit.json included) and the record of the last build `recorded`
    ({path: sha256}). Returns (edited, foreign, retired), each sorted paths in the kit:
    - edited: a planned file on disk whose bytes differ from the plan and whose sha256 is not the recorded one (somebody changed it);
    - foreign: a file inside a generated folder that is neither planned nor recorded (somebody put it there);
    - retired: recorded before, no longer planned, still on disk (a logo taken out of the project): moved aside, not stopped on."""
    kd = kit_dir(project)
    edited = sorted(rel for rel, data in files.items() if (kd / rel).is_file() and (kd / rel).read_bytes() != data and sha256_file(kd / rel) != recorded.get(rel))
    foreign = [rel for rel in on_disk(project) if rel not in files and rel not in recorded]
    retired = sorted(rel for rel in recorded if rel not in files and (kd / rel).is_file())
    return edited, foreign, retired

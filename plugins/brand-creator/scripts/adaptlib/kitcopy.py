#!/usr/bin/env python3
"""The copy judge of a brand kit, and the kit's installer: compare a kit folder with the copy a product repository holds, and say what to copy.

brand-creator's `kit status` imports this module (through scripts/adaptlib/kitlib.py), and `kit build` puts its bytes into every kit as install.py,
so the plugin and the installer judge a copy by the same code. It imports the Python standard library only: a kit copied out of the brand project,
or a clone of its mirror, can run it with no plugin installed. It never commits, never makes a branch and never pushes.

What a kit folder holds: the generated files (`ROOT_FILES` at its top, and everything under `GENERATED_DIRS`), listed with their sha256 in kit.json
`generated`, and the owner's files (every other file), listed in kit.json `owned`. See the "kit" section of brand-creator's scripts/CONTRACT.md.
"""
from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
from pathlib import Path

EXIT_FAIL, EXIT_USAGE, EXIT_CANNOT = 1, 2, 3                 # brand-creator's exit codes (_common.EXIT_FAIL, EXIT_USAGE, EXIT_CANNOT)
PAGE_ID = re.compile(r"[a-z][a-z0-9-]{1,31}")               # a reference page's id: brand-creator's sitedata.SITE_PAGE_ID, written out (a test keeps the two the same)


class KitError(Exception):
    """What stops a comparison: `code` is the exit code (EXIT_USAGE: no kit.json this version reads; EXIT_CANNOT: the kit is not whole), `message` says why."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


KIT_FILE = "kit.json"
SCHEMA = 1
SKILL_FILE = "SKILL.md"
GENERATED_DIRS = ("brand", "snippets", "reference-pages")   # a file in one of these that the kit did not write is a foreign file
FINDER_FILE = ".DS_Store"                                   # what Finder puts into a folder it opened: a file with exactly this name is no foreign file, in any generated folder, and `kit_paths` leaves it out of the whole kit
PREFIX = "brand/"                                           # where the project's files sit inside the kit: project path = PREFIX + path
RULES_JSON = "rules.json"                                   # the G4 rules with ids, the size rule and bands, the contrast pairs, the forbidden words, the page block
FACTS_JSON = "facts.json"                                   # the public FACTS.md rows
BRAND_MD = "brand.md"                                       # the values and facts behind SKILL.md: colour, type, layout, mark, motion, what may be claimed
CHECKLIST_MD = "checklist.md"                               # the check before handing anything over, built from rules.json
ROOT_FILES = (SKILL_FILE, KIT_FILE, RULES_JSON, FACTS_JSON, BRAND_MD, CHECKLIST_MD)  # the generated files that sit at the top of the kit folder, outside the generated folders
OWNED_FILES = ("EXTENDING.md", "voice.md", "visual.md", "golden-rules.md", "recipes/web-page.md")   # the five owner files the build scaffolds once from templates/kit/ (kit.json `owned` always lists them); any other file of the owner's travels too
TOP_KEYS = ("schema", "kit", "version", "edition", "plugin_version", "content_sha", "generated", "owned", "fonts", "sources", "reference_pages")
SOURCE_KEYS = ("state_sha", "tokens", "tokens_css", "rules", "facts", "motion", "logos", "fonts", "pages")
OPTIONAL_SOURCE_KEYS = ("masters",)                          # present only when the project has files under assets/masters/, so that a kit.json without masters is the bytes it always was
ALL_SOURCE_KEYS = SOURCE_KEYS + OPTIONAL_SOURCE_KEYS
FONT_KEYS = ("copied", "not_copied")
FONT_COPIED_KEYS = ("file", "licence", "licence_files")
FONT_NOT_COPIED_KEYS = ("file", "reason")
PAGE_KEYS = ("id", "page", "source_sha", "page_check_inputs_sha", "capture_inputs_sha")   # one entry of kit.json `reference_pages`
_SHA = re.compile(r"[0-9a-f]{64}")
_VERSION = re.compile(r"[1-9][0-9]*\.[1-9][0-9]*")
_EDITION = re.compile(r"[1-9][0-9]*")
NOT_INSTALLED = "not installed"                             # the repository's kit folder holds no kit.json
CURRENT = "current"                                         # every generated file and kit.json are the project's bytes
NOT_CURRENT = "not current"                                 # a generated file differs or is missing, or a file of an older kit is left over
WHY_MISSING = "missing"
WHY_LINK = "is a link or a folder, not a file"
WHY_BYTES = "not the same bytes"
STATUS_SHOWN = 6                                            # paths named in a message before "and N more"


def is_sha(value) -> bool:
    """True for a sha256 as the kit writes it: a string of 64 lower-case hex characters."""
    return isinstance(value, str) and bool(_SHA.fullmatch(value))


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
    if "owned" in doc:
        bad += owned_problems(doc["owned"])
    if "fonts" in doc:
        bad += font_problems(doc["fonts"])
    if "reference_pages" in doc:
        bad += reference_page_problems(doc["reference_pages"])
    src = doc.get("sources")
    if "sources" in doc:
        if not isinstance(src, dict):
            bad.append("sources: must be an object")
        else:
            bad += [f"sources.{k}: unknown key (allowed: {', '.join(ALL_SOURCE_KEYS)})" for k in src if k not in ALL_SOURCE_KEYS]
            bad += [f"sources.{k}: missing" for k in SOURCE_KEYS if k not in src]
            bad += [f"sources.{k}: must be a sha256 or null" for k, v in src.items() if k in ALL_SOURCE_KEYS and not (v is None or (isinstance(v, str) and _SHA.fullmatch(v)))]
    return bad


def is_owner_path(rel) -> bool:
    """True for a plain path in the kit folder that can be an owner file: no file at the top that the build writes (SKILL.md, kit.json, rules.json, facts.json), nothing below `brand/`, `snippets/` or
    `reference-pages/`, no Finder `.DS_Store`, no absolute path and no path that climbs out or is not written plainly."""
    return (isinstance(rel, str) and bool(rel) and posixpath.normpath(rel) == rel and not posixpath.isabs(rel) and rel not in (".", "..") and not rel.startswith("../")
            and rel not in ROOT_FILES and rel.split("/")[0] not in GENERATED_DIRS and posixpath.basename(rel) != FINDER_FILE)


def owned_problems(owned) -> list[str]:
    """What is wrong with the `owned` key of a kit.json: {owner file: sha256 at the last build}, an entry for each of `OWNED_FILES` (the five the build scaffolds) and one for each other file of the owner's,
    each a plain path (`is_owner_path`)."""
    if not isinstance(owned, dict):
        return ["owned: must be an object of owner file -> sha256"]
    bad = [f"owned.{k}: not an owner file (a plain path in the kit folder, not kit.json or a file the build writes, not below {', '.join(GENERATED_DIRS)}, not .DS_Store)"
           for k in owned if not is_owner_path(k)]
    bad += [f"owned.{k}: missing" for k in OWNED_FILES if k not in owned]
    bad += [f"owned.{k}: must be a sha256" for k, v in owned.items() if is_owner_path(k) and not (isinstance(v, str) and _SHA.fullmatch(v))]
    return bad


def font_problems(fonts) -> list[str]:
    """What is wrong with the `fonts` key of a kit.json: {copied: [{file, licence, licence_files}], not_copied: [{file, reason}]}."""
    if not isinstance(fonts, dict):
        return ["fonts: must be an object with copied and not_copied"]
    bad = [f"fonts.{k}: unknown key (allowed: {', '.join(FONT_KEYS)})" for k in fonts if k not in FONT_KEYS]
    bad += [f"fonts.{k}: missing" for k in FONT_KEYS if k not in fonts]
    for key, keys in (("copied", FONT_COPIED_KEYS), ("not_copied", FONT_NOT_COPIED_KEYS)):
        items = fonts.get(key)
        if key not in fonts:
            continue
        if not isinstance(items, list):
            bad.append(f"fonts.{key}: must be a list")
            continue
        for i, item in enumerate(items):
            where = f"fonts.{key}[{i}]"
            if not isinstance(item, dict):
                bad.append(f"{where}: must be an object")
                continue
            bad += [f"{where}.{k}: unknown key (allowed: {', '.join(keys)})" for k in item if k not in keys]
            bad += [f"{where}.{k}: missing" for k in keys if k not in item]
            bad += [f"{where}.{k}: must be a string" for k in keys if k in item and k != "licence_files" and not isinstance(item[k], str)]
            if "licence_files" in item and not (isinstance(item["licence_files"], list) and all(isinstance(f, str) for f in item["licence_files"])):
                bad.append(f"{where}.licence_files: must be a list of paths in the kit")
    return bad


def reference_page_problems(items) -> list[str]:
    """What is wrong with the `reference_pages` key of a kit.json: a list with an entry {id, page, source_sha, page_check_inputs_sha, capture_inputs_sha} for each approved reference page the kit holds
    (`id` is a page id of `PAGE_ID`, the folder name `site/<id>/` is read from; `page` is the kit path of its index.html, `brand/site/<id>/index.html`; the three others are sha256s)."""
    if not isinstance(items, list):
        return ["reference_pages: must be a list"]
    bad, seen = [], []
    for i, item in enumerate(items):
        where = f"reference_pages[{i}]"
        if not isinstance(item, dict):
            bad.append(f"{where}: must be an object")
            continue
        bad += [f"{where}.{k}: unknown key (allowed: {', '.join(PAGE_KEYS)})" for k in item if k not in PAGE_KEYS]
        bad += [f"{where}.{k}: missing" for k in PAGE_KEYS if k not in item]
        pid = item.get("id")
        if "id" in item:
            if not (isinstance(pid, str) and PAGE_ID.fullmatch(pid)):
                bad.append(f"{where}.id: must be a page id")
            elif pid in seen:
                bad.append(f"{where}.id: {pid!r} is listed twice")
            else:
                seen.append(pid)
        if "page" in item and item["page"] != f"{PREFIX}site/{pid}/index.html":
            bad.append(f"{where}.page: must be {PREFIX}site/<id>/index.html of its id")
        bad += [f"{where}.{k}: must be a sha256" for k in PAGE_KEYS[2:] if k in item and not is_sha(item[k])]
    return bad


def json_object(f: Path) -> dict | None:
    """The JSON object in a file, or None when there is no such file, it cannot be read, or it holds something else."""
    try:
        doc = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def paths_in(kd: Path) -> list[str]:
    """The path in a kit folder `kd` of every file and every link below it, sorted. A link to a folder is listed as the one path it is and never followed; a folder with nothing
    in it is not listed. A file named exactly `.DS_Store` (what Finder leaves in a folder it opened) is left out, anywhere in the kit, as `on_disk` leaves it out of the generated
    folders: it is no file of the kit, so it is no input of the `kit-check` report, is not in the tree, and is not read for links or fill markers."""
    out = []
    for root, dirs, names in os.walk(kd):
        base = Path(root)
        out += [(base / n).relative_to(kd).as_posix() for n in names if n != FINDER_FILE]
        out += [(base / n).relative_to(kd).as_posix() for n in dirs if (base / n).is_symlink()]
    return sorted(out)


def owner_paths(kd: Path) -> list[str]:
    """The owner's files in a kit folder `kd`, as `paths_in` lists them: every file or link that is none of the files at the top the build writes (SKILL.md, kit.json, rules.json, facts.json), is not
    below a generated folder (`brand/`, `snippets/`, `reference-pages/`: a file there that the kit did not write is a foreign file, which stops the build) and is no Finder `.DS_Store`. The five scaffolded
    files are among them while they exist; sorted, so use `owner_sorted` for the order the copy list has."""
    return [rel for rel in paths_in(kd) if is_owner_path(rel)]


def owner_sorted(rels) -> list[str]:
    """The owner's files in the order the build and the copy list name them: the five scaffolded ones (`OWNED_FILES`) that are in `rels`, in that order, then every other, sorted."""
    have = set(rels)
    return [r for r in OWNED_FILES if r in have] + sorted(have - set(OWNED_FILES))


def recorded_path(rel: str) -> bool:
    """A path a record may name: SKILL.md, kit.json, rules.json, facts.json, or a plain path under one of the generated folders. Anything else (a path that climbs out of the kit)
    is not read."""
    return rel in ROOT_FILES or (posixpath.normpath(rel) == rel and not posixpath.isabs(rel) and rel.split("/")[0] in GENERATED_DIRS and not rel.endswith("/"))


def plain_file(kd: Path, rel: str) -> bool:
    """True for a file of the kit that is a file, is itself no link, and sits in no folder that is a link: a link is never read through, and what a link to a folder leads to is not the kit's,
    so it is neither compared nor moved."""
    parts = rel.split("/")
    return not any(kd.joinpath(*parts[:i]).is_symlink() for i in range(1, len(parts) + 1)) and (kd / rel).is_file()


def read_plain(base: Path, rel: str) -> tuple[bytes | None, str | None]:
    """(the bytes, None) of a plain file `rel` of a kit folder `base`, or (None, why): missing, a link or a folder (or behind a link), or unreadable. A link is never read through."""
    if not os.path.lexists(base / rel):
        return None, WHY_MISSING
    if not plain_file(base, rel):
        return None, WHY_LINK
    try:
        return (base / rel).read_bytes(), None
    except OSError as e:
        return None, f"cannot be read ({e.strerror or e})"


def generated_files_in(kd: Path) -> list[str]:
    """The paths in a kit folder of every file inside a generated folder, sorted, as `on_disk` lists them for the project: a Finder `.DS_Store` is left out, a link to a folder is the one path
    it is and is never followed, and a generated folder that is itself a link is listed as that one path."""
    out = []
    for d in GENERATED_DIRS:
        if (kd / d).is_symlink():
            out.append(d)
            continue
        for root, dirs, names in os.walk(kd / d):
            out += [(Path(root) / n).relative_to(kd).as_posix() for n in names if n != FINDER_FILE]
            out += [(Path(root) / n).relative_to(kd).as_posix() for n in dirs if (Path(root) / n).is_symlink()]
    return sorted(out)


def installed_version(installed: Path) -> str | None:
    """The `version` kit.json states in an installed copy, or None when there is no plain kit.json there or it holds no version."""
    if not plain_file(installed, KIT_FILE):
        return None
    version = (json_object(installed / KIT_FILE) or {}).get("version")
    return version if isinstance(version, str) and version.strip() else None


def folder_state(folder: Path) -> str:
    """One sha256 over every folder, file and link below `folder` (and the folder itself), each with its path, kind, size and modification time, none followed through a link: the read-only
    proof of `kit status`, taken before and after. A folder that is not there is a state too."""
    h = hashlib.sha256()
    if not os.path.lexists(folder):
        return h.hexdigest()
    entries = [(folder, "")]
    for root, dirs, names in os.walk(folder):
        entries += [(Path(root) / n, (Path(root) / n).relative_to(folder).as_posix()) for n in [*dirs, *names]]
    for f, rel in sorted(entries, key=lambda e: e[1]):
        try:
            st = os.lstat(f)
        except OSError:
            h.update(f"{rel}\0gone\n".encode("utf-8", "replace"))
            continue
        kind = "link" if f.is_symlink() else "folder" if f.is_dir() else "file"
        h.update(f"{rel}\0{kind}\0{st.st_size}\0{st.st_mtime_ns}\n".encode("utf-8", "replace"))
    return h.hexdigest()


def compare(kit: Path, installed: Path) -> dict:
    """The kit folder of the project (`kit`) against the folder a product repository holds (`installed`). Reads both, writes nothing, follows no link.

    Returns {"state": NOT_INSTALLED | CURRENT | NOT_CURRENT, "installed_version", "project_version", "differ": [(path, why)], "missing": [path], "left_over": [path],
    "owner_differ": [(path, why)], "copy": [path], "copy_owner": [path], "update_owner": [path], "owner_left_over": [path], "brand": the name `brand_name` reads or None, "other_skills": [folder] (`other_brand_skills`)}. The copy list `copy` is the
    generated files to copy (all of them when nothing is installed, otherwise those that differ or are missing), then the owner files the repository lacks (`copy_owner`: every
    owner file of the project, `owner_paths`, the five scaffolded ones first, then the others sorted), then the owner files to update (`update_owner`), and kit.json last of all.
    An owner file is judged by `owner_state` against the `owned` record of the repository's own kit.json (`installed_owned`): one the repository never changed since it was
    copied is updated; one it changed or added is its own, only reported (`owner_differ`), never copied. An owner file the repository's kit.json records, unchanged there, that
    the project's kit no longer has is `owner_left_over`. A link among the owner's files is never read through: it raises KitError (exit 3). A kit is NOT_INSTALLED when its
    folder holds no kit.json; CURRENT when every generated file and kit.json are byte for byte the project's and no owner file is to be updated or moved; NOT_CURRENT otherwise,
    which includes a file in brand/, snippets/ or reference-pages/ that the project's kit does not have (`left_over`: a file of an older kit). The project's kit must be whole:
    a generated file kit.json lists that is missing there, no plain file, or not the sha256 kit.json records raises KitError (exit 3), because a copy cannot be judged against a
    kit that is not itself what it says."""
    doc = json_object(kit / KIT_FILE)
    if doc is None or (bad := problems(doc)):
        raise KitError(EXIT_USAGE, f"{kit / KIT_FILE} is no kit.json this version reads" + (f": {bad[0]}" if doc is not None else ""))
    wanted = [*sorted(doc["generated"]), KIT_FILE]                      # kit.json last: a copy that stops half way leaves a kit that kit.json does not vouch for
    mine, broken = {}, []
    for rel in wanted:
        data, why = read_plain(kit, rel) if recorded_path(rel) else (None, "is no path a kit holds")
        if why:
            broken.append(f"{rel} ({why})")
        elif rel != KIT_FILE and _sha256(data) != doc["generated"][rel]:
            broken.append(f"{rel} (edited by hand)")
        else:
            mine[rel] = data
    if broken:
        shown = ", ".join(broken[:STATUS_SHOWN]) + (f", and {len(broken) - STATUS_SHOWN} more" if len(broken) > STATUS_SHOWN else "")
        raise KitError(EXIT_CANNOT, f"the kit in the project is not whole, so no copy can be judged against it: {shown}. Run `brand-creator kit check`, then `brand-creator kit build --yes`")
    owner_rels = owner_sorted(owner_paths(kit))                          # the owner's files as the kit folder holds them now, the five scaffolded ones first
    linked = [rel for rel in owner_rels if not plain_file(kit, rel)]
    if linked:
        shown = ", ".join(linked[:STATUS_SHOWN]) + (f", and {len(linked) - STATUS_SHOWN} more" if len(linked) > STATUS_SHOWN else "")
        raise KitError(EXIT_CANNOT, f"the kit in the project holds a link among the owner's files ({shown}): a link is never read through, so no copy can be judged against it. Move it away yourself "
                          "(`brand-creator kit build --yes --replace` moves it aside), then run `brand-creator kit check`")
    owner = {rel: data for rel in owner_rels if (data := read_plain(kit, rel)[0]) is not None}   # the project's owner files that can be copied
    out = {"state": NOT_INSTALLED, "installed_version": None, "project_version": doc["version"], "differ": [], "missing": [], "left_over": [], "owner_differ": [],
           "copy": [], "copy_owner": [], "update_owner": [], "owner_left_over": [], "brand": None, "other_skills": []}
    recorded = installed_owned(installed)
    if not os.path.lexists(installed / KIT_FILE):
        out["copy"] = list(wanted)
    else:
        out["installed_version"] = installed_version(installed)
        for rel in wanted:
            data, why = read_plain(installed, rel)
            if why == WHY_MISSING:
                out["missing"].append(rel)
            elif data != mine[rel]:
                out["differ"].append((rel, WHY_BYTES if data is not None else why))
            else:
                continue
            out["copy"].append(rel)
        out["left_over"] = [rel for rel in generated_files_in(installed) if rel not in doc["generated"]]
        out["state"] = NOT_CURRENT if out["differ"] or out["missing"] or out["left_over"] else CURRENT
    for rel in owner_rels:
        if rel not in owner:
            continue
        data, why = read_plain(installed, rel)
        state = owner_state(data, owner[rel], recorded.get(rel)) if why in (None, WHY_MISSING) else "own"
        if state == "copy":
            out["copy_owner"].append(rel)
        elif state == "update":
            out["update_owner"].append(rel)
        elif state == "own":
            out["owner_differ"].append((rel, WHY_BYTES if data is not None else why))
    for rel in owner_sorted(recorded):                                   # an owner file of the installed kit that the project's kit no longer has, unchanged since it was copied
        if rel not in owner and is_owner_path(rel) and (data := read_plain(installed, rel)[0]) is not None and _sha256(data) == recorded[rel]:
            out["owner_left_over"].append(rel)
    if out["update_owner"] or out["owner_left_over"]:
        out["state"] = NOT_CURRENT
    brand = out["brand"] = brand_name(kit)
    out["other_skills"] = other_brand_skills(installed.parent, installed.name, brand) if brand else []
    last = [KIT_FILE] if KIT_FILE in out["copy"] else []                 # kit.json last of all: a copy that stops before it is finished by the next run, never taken for the repository's own edits
    out["copy"] = [rel for rel in out["copy"] if rel != KIT_FILE] + out["copy_owner"] + out["update_owner"] + last
    return out


_BRAND_HEADING = re.compile(r"^# (.+) brand\s*$", re.M)


def brand_name(kit: Path) -> str | None:
    """The brand's name, from the first `# <name> brand` heading of the kit's SKILL.md (as its template writes it), or None when the kit has no such SKILL.md."""
    data, _ = read_plain(kit, SKILL_FILE)
    m = _BRAND_HEADING.search(data.decode("utf-8", "replace")) if data is not None else None
    return m.group(1).strip() if m else None


def _folded(text: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFC", text).casefold()


def other_brand_skills(skills_dir: Path, kit_name: str, brand: str) -> list[str]:
    """The folders of `skills_dir` (a repository's .claude/skills/), other than the kit's own, whose SKILL.md front matter names the brand in its `name:` or `description:` line:
    another skill Claude may load for the same brand (a hand-made kit, say). Compared after NFC normalisation and case folding. A link, a folder without a plain SKILL.md
    and an unreadable one are never read. Sorted folder names."""
    if not os.path.isdir(skills_dir) or os.path.islink(skills_dir):
        return []
    want, out = _folded(brand), []
    for entry in sorted(os.listdir(skills_dir)):
        folder = skills_dir / entry
        if entry == kit_name or folder.is_symlink() or not folder.is_dir():
            continue
        data, _ = read_plain(folder, SKILL_FILE)
        if data is None:
            continue
        lines = data.decode("utf-8", "replace").split("\n")
        if not lines or lines[0].strip() != "---":
            continue
        head = []
        for line in lines[1:]:
            if line.strip() == "---":
                break
            head.append(line)
        if any(line.split(":", 1)[0].strip() in ("name", "description") and want in _folded(line.split(":", 1)[1]) for line in head if ":" in line):
            out.append(entry)
    return out


def owner_state(repo: bytes | None, project: bytes, recorded: str | None) -> str:
    """What happens to one owner file of the project's kit in a repository: "copy" (the repository has none), "same" (the same bytes), "update" (the repository's bytes are the ones
    its own kit.json recorded when it was copied, so the repository never changed it, and the project's differ), or "own" (the repository changed it, or added it: kept, and reported).
    `recorded` is the sha256 the repository's kit.json `owned` holds for the file, or None."""
    if repo is None:
        return "copy"
    if repo == project:
        return "same"
    return "update" if recorded is not None and _sha256(repo) == recorded else "own"


def installed_owned(installed: Path) -> dict[str, str]:
    """The `owned` record of the kit.json a repository holds: {owner file: sha256 when it was copied}. {} when that kit.json is no plain file or not one this version reads (another
    schema, broken JSON): then no owner file counts as unchanged, and none is updated or moved."""
    if not plain_file(installed, KIT_FILE):
        return {}
    doc = json_object(installed / KIT_FILE)
    return dict(doc["owned"]) if doc is not None and not problems(doc) else {}


def not_current_text(installed_version: str | None, project_version: str, differ, missing, left_over) -> str:
    """What a copy that is not current is called, after its label: `not current (installed version A, project version B)` when the two versions differ (A is `unknown` when the installed kit.json states
    none), and, when they are the same (a copy that has the new kit.json and still differs from the kit in a file), `not current (version V on both sides, but 1 file differs, 1 file is missing, 1 file is left
    over from an older kit)`, naming only the kinds there are, so that it does not read as a contradiction. `differ`, `missing` and `left_over` are the lists `compare` returns (only their length is used).
    The one wording of `kit status` (scripts/kit.py) and of `adoption status` (scripts/adoption.py)."""
    if installed_version != project_version:
        return f"not current (installed version {installed_version or 'unknown'}, project version {project_version})"
    counts = ((len(differ), "file differs", "files differ"), (len(missing), "file is missing", "files are missing"),
              (len(left_over), "file is left over from an older kit", "files are left over from an older kit"))
    said = ", ".join(f"{n} {one if n == 1 else many}" for n, one, many in counts if n)
    return f"not current (version {project_version} on both sides, but {said})" if said else f"not current (version {project_version} on both sides)"


def refusal(project: Path, real: Path) -> str | None:
    """Why a folder cannot be read as a product repository, or None: the brand project itself or a folder inside it, your home folder, or a path inside ~/.claude (a global skills folder).
    `real` has its links resolved. The text starts with "is" and goes after the name of the folder."""
    root = Path(os.path.realpath(project))
    if real == root or root in real.parents:
        return "is the brand project itself or a folder inside it: name a product repository"
    home = Path(os.path.realpath(Path.home()))
    if real == home:
        return "is your home folder: the kit goes into one product repository at a time, never into a global skills folder"
    for claude in {home / ".claude", Path(os.path.realpath(Path.home() / ".claude"))}:
        if real == claude or claude in real.parents:
            return "is inside ~/.claude: the kit goes into one product repository at a time, never into a global skills folder"
    return None


def left_over_to(kd_rel: str) -> str:
    """Where a file left over from an older kit goes in the repository (the implementer moves it there; nothing is deleted): removed-<date>/, then the kit folder, then its path in the kit."""
    return f"removed-<date>/{kd_rel}/"


def not_current_line(res: dict) -> str:
    """The first line of a copy that is not current. With two versions that differ it names both. With the same version on both sides it says so and what differs, so that it does
    not read as a contradiction: the version is the same, the files are not."""
    return f"{res['label']}: " + not_current_text(res["installed_version"], res["project_version"], res["differ"], res["missing"], res["left_over"])


def status_lines(res: dict, kd_rel: str) -> list[str]:
    """The text of one repository: its state, what differs, and the copy list."""
    v, label = res["project_version"], res["label"]
    if res["state"] == NOT_INSTALLED:
        L = [f"{label}: not installed"]
    elif res["state"] == CURRENT:
        L = [f"{label}: current (version {v})"]
    else:
        L = [not_current_line(res)]
    if res["note"]:
        L.append(f"  {res['note']}")
    for title, items in (("generated files that differ", [f"{rel} ({why})" for rel, why in res["differ"]]),
                         ("generated files that are missing", res["missing"]),
                         (f"left over from an older kit (not in this kit, so not on the copy list; move each to {left_over_to(kd_rel)} in the repository, keeping its path; nothing is deleted)",
                          res["left_over"]),
                         (f"owner files left over from an older kit, unchanged in the repository (move each to {left_over_to(kd_rel)} too)", res["owner_left_over"]),
                         ("owner files that differ (kept on update)", [rel for rel, _why in res["owner_differ"]]),
                         ("owner files to update (unchanged in the repository since the last copy)", res["update_owner"])):
        if items:
            L += [f"  {title}:", *(f"    {i}" for i in items)]
    for folder in res.get("other_skills", []):
        L.append(f"  warning: {posixpath.dirname(kd_rel)}/{folder}/ is another skill for {res.get('brand') or 'this brand'}: Claude may load either; taking it out is yours")
    if res["copy"]:
        L.append(f"  copy list, paths relative to {kd_rel}/ (the generated files, then the owner files to copy or update, kit.json last):")
        L += [f"    {rel} (owner file, the repository has none)" if rel in res["copy_owner"] else f"    {rel} (owner file, an update)" if rel in res["update_owner"]
              else f"    {rel}" for rel in res["copy"]]
    return L


def result_json(res: dict, kd_rel: str) -> dict:
    """One repository's entry of `kit status --json`: the keys in their order, `differ` and `owner_differ` as [{"file", "why"}], and `left_over_to` (where the files left over go,
    in the repository) only when there are some. `kd_rel` is the kit folder's path in a repository (`.claude/skills/<name>`)."""
    keys = ("label", "path", "state", "installed_version", "project_version", "differ", "missing", "left_over", "left_over_to", "owner_differ", "update_owner", "owner_left_over",
            "other_skills", "copy", "copy_owner", "read_only")
    res = {**res, "left_over_to": left_over_to(kd_rel) if res["left_over"] or res["owner_left_over"] else None}
    return {k: ([{"file": rel, "why": why} for rel, why in res[k]] if k in ("differ", "owner_differ") else res[k]) for k in keys}

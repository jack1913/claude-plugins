#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator kit: the brand kit that sits around the per-brand applied skill, in the project's own .claude/skills/<slug>-brand/.

    brand-creator kit build --yes               write the kit (needs G5 recorded and the owner's explicit OK, which is --yes)
    brand-creator kit build --plan              print what would be written and exit 0
    brand-creator kit build --yes --replace     a file of the kit that was edited by hand, or one put into a generated folder, stops the build; --replace moves it aside

The kit holds the brand's own files copied byte for byte at their project paths under brand/ (the token files, the logo files and the drawings qa/rules.json names
for each size band), SKILL.md (the applied skill, written by the same builder, its paths pointing inside the kit, with a "## The kit" section) and kit.json, which
records the sha256 of every generated file, the version and what the kit was made from. The version is <edition>.<build>: the edition is BRAND-STATE.md
approved_edition, the build number starts at 1 and goes up by 1 when a build changes any kit content. A second build with nothing changed writes nothing.

Fonts: each .ttf, .otf, .woff or .woff2 in assets/fonts/ is copied to brand/assets/fonts/ only when the current fontcheck report (assets/_checks/fontcheck.json) reads it
as SIL Open Font License (OFL) and a licence text with "SIL OPEN FONT LICENSE" in it sits in assets/fonts/ (the text is copied along); snippets/fonts.css then holds an
@font-face for each copied font. Any other font is listed in kit.json (fonts.not_copied) with the reason and never copied. With no current fontcheck report no font is
copied, the rest is written and the build exits 3 (run `brand-creator fontcheck`, then `kit build` again).

Nothing in a generated file is edited by hand: change the brand project and build again. A file of the kit that differs from what the last build wrote, or a file in
brand/, snippets/ or reference-pages/ that the kit did not write, stops the build (exit 1, up to 6 paths named) unless --replace, which moves each to
removed-<date>[-n]/<its project path>. A file the last build wrote that the project no longer has (a logo taken away) is moved there too, and said so. Nothing is deleted.
A SKILL.md that `applied-skill` wrote is taken over; one edited by hand stops the first build the same way.

Writes the report `kit` (row kit:written; outputs lists every generated path with its sha256, kit.json included). Exit 0 written. Exit 1: G5 not recorded, no approved
edition, a band drawing the project does not have, or a hand edit or foreign file without --replace. Exit 2: no --yes (the plan is printed first); a path that leaves the
project; a band drawing that is not written as a plain path. Exit 3: the tokens are not built; fonts are in assets/fonts/ and there is no current fontcheck report (the kit is written without them).
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
sys.path.insert(0, str(HERE / "booklib"))
sys.path.insert(0, str(HERE / "adaptlib"))
import adapt  # noqa: E402
import kitlib  # noqa: E402
from _common import (EXIT_FAIL, EXIT_USAGE, Parser, Report, add_project_arg, confine, fail, find_project, main_guard, require_gate,  # noqa: E402
                     sha256_bytes, today, write_bytes_if_changed)

SHOWN = 6   # paths named in a message before "and N more"


def removed_folder(project: Path, rels: list[str]) -> str:
    """The first removed-<date>[-n] folder none of whose paths for `rels` exists yet."""
    kd = kitlib.kit_rel(project)
    n = 1
    while True:
        folder = f"removed-{today()}" + ("" if n == 1 else f"-{n}")
        if not any(confine(project, f"{folder}/{kd}/{rel}", what="backup").exists() for rel in rels):
            return folder
        n += 1


def move_aside(project: Path, rels: list[str]) -> str:
    """Move each file of the kit (paths in the kit) to removed-<date>[-n]/<its project path>, and say so. Returns the folder."""
    kd = kitlib.kit_rel(project)
    folder = removed_folder(project, rels)
    for rel in rels:
        src = confine(project, f"{kd}/{rel}", what="kit file")
        dest = confine(project, f"{folder}/{kd}/{rel}", what="backup")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        print(f"moved {kd}/{rel} to {folder}/{kd}/{rel}")
    for d in kitlib.GENERATED_DIRS:   # a folder the move emptied is not left behind (the files in it were moved, nothing is deleted)
        base = confine(project, f"{kd}/{d}", what="kit folder")
        for root, _dirs, _names in list(os.walk(base, topdown=False)):   # the deepest folder first
            if not os.listdir(root):
                os.rmdir(root)
    return folder


def font_row(rep, fonts: dict) -> None:
    """Row kit:fonts: pass when every font is copied, warn when one is not (it is listed in kit.json with the reason), skipped when there is no current fontcheck
    report (the kit is written without fonts and the build exits 3). No row when the project has no font file."""
    if not fonts["fonts"]:
        return
    n, left = len(fonts["copied"]), fonts["not_copied"]
    if not fonts["current"]:
        rep.add("kit:fonts", "skipped", "fonts from assets/fonts/", detail=f"not verified: {kitlib.NO_FONTCHECK}")
    elif left:
        shown = "; ".join(f"{f['file']} ({f['reason']})" for f in left[:SHOWN]) + (f"; and {len(left) - SHOWN} more" if len(left) > SHOWN else "")
        rep.add("kit:fonts", "warn", "fonts from assets/fonts/", detail=f"{n} of {len(fonts['fonts'])} fonts copied; not copied: {shown}")
    else:
        rep.add("kit:fonts", "pass", "fonts from assets/fonts/",
                detail=f"{n} font{'s' if n != 1 else ''} copied with {'their' if n != 1 else 'its'} licence text; {kitlib.FONTS_CSS} written")


def build(project: Path, a) -> int:
    require_gate(project, "G5", for_what="The brand kit")
    edition = adapt.view(project)["approved_edition"]
    if not edition:
        fail(EXIT_FAIL, "G5 is recorded but no edition is approved: BRAND-STATE.md has no approved_edition. Set the edition "
                        "(`brand-creator state --set edition=1`) and record G5 again, which approves it")
    kd_rel = kitlib.kit_rel(project)
    confine(project, kd_rel, what="kit folder")
    fonts = kitlib.font_plan(project)                      # OFL fonts and their licence text are planned files; any other font is only listed
    generated = kitlib.plan(project, fonts)                # SKILL.md with the literal <version>: the version is decided from what the plan holds
    csha = kitlib.content_sha({rel: sha256_bytes(data) for rel, data in generated.items()})
    prev = kitlib.previous(project)
    version = kitlib.next_version(prev, edition, csha)
    files = kitlib.with_version(generated, version)
    src = kitlib.sources(project)
    files[kitlib.KIT_FILE] = kitlib.kit_json_bytes(project, files, version, edition, csha, src, fonts)
    if a.plan or not a.yes:
        print(f"would write {len(files)} generated files into {kd_rel}/ (version {version})")
        for rel in sorted(files):
            print(f"generated {rel} ({len(files[rel])} bytes)")
        if not a.plan:
            print("error: the brand kit is written into the project's .claude/skills/ and needs the owner's explicit OK at G5: re-run with --yes", file=sys.stderr)
        return 0 if a.plan else EXIT_USAGE
    edited, foreign, retired = kitlib.scan(project, files, (prev or {}).get("outputs", {}))
    stopped = [(rel, "edited by hand") for rel in edited] + [(rel, "not written by the kit") for rel in foreign]
    if stopped and not a.replace:
        shown = ", ".join(f"{rel} ({why})" for rel, why in stopped[:SHOWN]) + (f", and {len(stopped) - SHOWN} more" if len(stopped) > SHOWN else "")
        fail(EXIT_FAIL, f"{kd_rel}/ holds files the kit would overwrite or does not know: {shown}. Change the brand project instead and run "
                        f"`brand-creator kit build --yes` again, or add --replace to move them to removed-{today()}/ first (nothing is deleted)")
    moving = (edited + foreign if a.replace else []) + retired
    folder = move_aside(project, moving) if moving else f"removed-{today()}"
    rep = Report("kit", project, renderer="n/a (generated files)")
    rep.inputs.extend(kitlib.input_paths(project))
    written = unchanged = 0
    for rel in sorted(r for r in files if r != kitlib.KIT_FILE) + [kitlib.KIT_FILE]:   # kit.json last: a run that stops half way leaves a kit that kit.json does not vouch for
        if write_bytes_if_changed(confine(project, f"{kd_rel}/{rel}", what="kit file"), files[rel]):
            written += 1
        else:
            unchanged += 1
    rep.add("kit:written", "pass", f"{kd_rel}/ generated",
            detail=f"{len(files)} generated files: {written} written, {unchanged} unchanged, {len(moving)} moved to {folder}/; version {version}")
    font_row(rep, fonts)
    rep.extra.update({"outputs": {rel: sha256_bytes(data) for rel, data in sorted(files.items())}, "kit_version": version, "content_sha": csha,
                      "adapter_state_sha": src["state_sha"], "kit_sources_sha": kitlib.sources_sha(project, src)})
    return rep.finish()


def main() -> int:
    ap = Parser(prog="brand-creator kit", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_project_arg(ap)
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=Parser)
    b = sub.add_parser("build", help="write the kit into the project's .claude/skills/<slug>-brand/")
    b.add_argument("--yes", action="store_true", help="the owner's explicit OK to write into the project's .claude/skills/")
    b.add_argument("--plan", action="store_true", help="print what would be written and exit 0")
    b.add_argument("--replace", action="store_true",
                   help="a file edited by hand, or put into a generated folder, is moved to removed-<date>/ and the kit is written (nothing is deleted)")
    b.add_argument("--project", default=argparse.SUPPRESS, help="brand project folder")   # also after the subcommand
    a = ap.parse_args()
    return build(find_project(getattr(a, "project", None)), a)


main_guard(main)

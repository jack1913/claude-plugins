#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator kit: the brand kit that sits around the per-brand applied skill, in the project's own .claude/skills/<slug>-brand/.

    brand-creator kit build --yes               write the kit (needs G5 recorded and the owner's explicit OK, which is --yes)
    brand-creator kit build --plan              print what would be written and exit 0
    brand-creator kit build --yes --replace     a file of the kit that was edited by hand, or one put into a generated folder, stops the build; --replace moves it aside
    brand-creator kit check                     prove the kit is whole, current and filled in (writes the report kit-check; read only otherwise)

The kit holds the brand's own files copied byte for byte at their project paths under brand/ (the token files, the logo files and the drawings qa/rules.json names
for each size band), SKILL.md (the applied skill, written by the same builder, its paths pointing inside the kit, with a "## The kit" section) and kit.json, which
records the sha256 of every generated file, the version and what the kit was made from. The version is <edition>.<build>: the edition is BRAND-STATE.md
approved_edition, the build number starts at 1 and goes up by 1 when a build changes any kit content. A second build with nothing changed writes nothing.

The rules and the facts are data: rules.json holds the "(rule)" lines of BRAND-STATE.md Rules (G4) each with an id (the ASCII slug of its first six words, `-2`, `-3` for a repeat),
the size rule and the drawing of each size band, the contrast pairs with their computed ratios, the forbidden words and, when the project's own qa/rules.json has one, its `page`
block verbatim; facts.json holds the public rows of FACTS.md (a contact or postal address row never). Both sit at the top of the kit folder and are locked by kit.json.

Fonts: each .ttf, .otf, .woff or .woff2 in assets/fonts/ is copied to brand/assets/fonts/ only when the current fontcheck report (assets/_checks/fontcheck.json) reads it
as SIL Open Font License (OFL) and a licence text with "SIL OPEN FONT LICENSE" in it sits in assets/fonts/ (the text is copied along); snippets/fonts.css then holds an
@font-face for each copied font. Any other font is listed in kit.json (fonts.not_copied) with the reason and never copied. With no current fontcheck report no font is
copied, the rest is written and the build exits 3 (run `brand-creator fontcheck`, then `kit build` again).

Grounds: once the owner has named the colours text sits on (tokens.json `grounds`, `named_by_owner` a real date and the owner's words), snippets/on-ground.css holds one
[data-ground="<name>"] scope for each ground after the first, which is the page ground: the scope sets the ground's own background and points the page ground's text, action,
on-action, focus and border variables at the ground's own colours. While the grounds are only a proposal no snippet is written (row kit:grounds says so); a ground the
tokens give no colour for, one that gives two roles different colours where the page ground uses one token for both (a rule that sets a variable twice keeps only
the later value), one that uses a variable its own scope sets, or one whose data-ground name is taken, is left out and named.

The owner's files (EXTENDING.md, voice.md, visual.md, golden-rules.md, recipes/web-page.md) are scaffolded from templates/kit/ (the placeholders {{brand}} and {{skill}} filled; any
other {{...}} is exit 2 and nothing is written) only when the file is absent. They are never overwritten or moved. kit.json records the sha256 of each one (`owned`) and the version's
content hash covers them, so an edit of yours moves the version at the next build. The plan lists the scaffolds the build would write as `scaffold <path> (<bytes> bytes, ...)`.

Nothing in a generated file is edited by hand: change the brand project and build again. A file of the kit that differs from what the last build wrote, or a file in
brand/, snippets/ or reference-pages/ that the kit did not write (a file named exactly .DS_Store, which Finder leaves behind, is not one; a link is one, wherever it sits in the kit and whatever it points at, and is never followed or written through), stops the build
(exit 1, up to 6 paths named) unless --replace, which moves each to removed-<date>[-n]/<its project path>. A file the last build wrote that the project no longer has (a logo taken away) is moved there too, and said so. Nothing is deleted.
A SKILL.md that `applied-skill` wrote is taken over; one edited by hand stops the first build the same way.

`kit check` reads the kit and writes the report `kit-check`; no kit is exit 2. Its inputs are every file under the kit folder, the files the kit is made from, BRAND-STATE.md and the `kit` report, so any change
makes it stale. Rows: kit:files (every generated file is what kit.json lists, kit.json is the bytes the `kit` report recorded, no file in a generated folder is unlisted; with no `kit` report: not verified), kit:links (every
relative link in a .md, .html or .css file resolves to a file inside the kit: one that points outside it, an absolute path or a missing file fails), kit:fill (no `[[fill` marker is left in a text file), kit:versions (SKILL.md holds
`Kit version <kit.json version> (kit.json).` exactly once, and the kit's edition is the approved one), kit:plugin (warns on another plugin version), kit:sources (not verified when the brand changed after the kit was built, naming
what changed) and kit:owned (warns when an owner file changed since the last build). Exit 0 pass, 1 a row failed, 3 not verified. A link inside the kit is never followed.

Writes the report `kit` (rows kit:written and kit:owned; outputs lists every generated path with its sha256, kit.json included, and no owner file). Exit 0 written. Exit 1: G5 not recorded, no approved
edition, a band drawing the project does not have, or a hand edit or foreign file without --replace. Exit 2: no --yes (the plan is printed first); a path that leaves the
project; a band drawing that is not written as a plain path; a scaffold with a placeholder this version does not know. Exit 1 also: an owner file's path that holds something that is no file, or a folder an owner file belongs in (recipes/) that is a file or a link to nothing. Exit 3: the tokens are not built; a scaffold the plugin lacks; fonts are in assets/fonts/ and there is no current fontcheck report (the kit is written without them).
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
sys.path.insert(0, str(HERE / "boardlib"))   # kitlib.known_rule_ids reads the choices of site/site.json with boardlib/sitedata.py
import adapt  # noqa: E402
import kitlib  # noqa: E402
from _common import (EXIT_FAIL, EXIT_USAGE, CliError, Parser, Report, add_project_arg, confine, fail, find_project, main_guard, plugin_version,  # noqa: E402
                     require_gate, sha256_bytes, today, write_bytes_if_changed)

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
        src = confine(project, f"{kd}/{Path(rel).parent.as_posix()}", what="kit file") / Path(rel).name   # the file itself, or the link: a link is moved, never what it points at
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


def owner_row(rep, written: list[str], kept: list[str]) -> None:
    """Row kit:owned (info): how many of the owner's files were scaffolded this run and how many were already there and are kept as they are."""
    k, m = len(written), len(kept)
    rep.add("kit:owned", "info", "the owner's files",
            detail=f"{k} owner file{'s' if k != 1 else ''} scaffolded this run, {m} kept as they are")


def ground_row(rep, grounds: dict) -> None:
    """Row kit:grounds, about snippets/on-ground.css. No row when the tokens list no grounds. Info while the grounds are a proposal (nothing is written, because the model
    never guesses which colours text sits on) and when there is no other ground to scope; warn when a ground is left out, or the page ground (the first listed) lacks a
    colour so that none can be scoped; pass when every other ground has its scope. A ground is left out, with the reason kitlib.ground_plan gives, when the tokens give it no
    colour, when the page ground uses one token for two roles and the ground gives them two colours, when it uses a variable its own scope sets, or when its name is taken."""
    if grounds["state"] == "absent":
        return
    label, snippet = "text grounds from tokens.json", kitlib.ON_GROUND_CSS
    if grounds["state"] == "proposal":
        rep.add("kit:grounds", "info", label, detail=f"the grounds are a proposal until the owner names them: {snippet} is not written")
    elif not grounds["listed"]:
        rep.add("kit:grounds", "info", label, detail=f"the owner named the grounds but tokens.json lists none: {snippet} is not written")
    elif grounds["page_gaps"]:
        rep.add("kit:grounds", "warn", label, detail=f"the page ground ({grounds['page']}, the first listed) lacks {', '.join(grounds['page_gaps'])}, so no other ground can be "
                                                    f"scoped against it: {snippet} is not written")
    elif grounds["left_out"]:
        left = grounds["left_out"]
        shown = "; ".join(f"{name} ({why})" for name, why in left[:SHOWN]) + (f"; and {len(left) - SHOWN} more" if len(left) > SHOWN else "")
        n = len(grounds["scoped"])
        rep.add("kit:grounds", "warn", label, detail=f"{n} of {n + len(left)} other grounds scoped in {snippet}; left out: {shown}" if n
                else f"{snippet} is not written, every other ground is left out: {shown}")
    elif grounds["scoped"]:
        n = len(grounds["scoped"])
        rep.add("kit:grounds", "pass", label, detail=f"{n} ground{'s' if n != 1 else ''} scoped in {snippet}; the page ground is {grounds['page']}")
    else:
        rep.add("kit:grounds", "info", label, detail=f"only the page ground ({grounds['page']}) is listed, so there is no other ground to scope: {snippet} is not written")


def named(items: list[str]) -> str:
    """The first SHOWN items joined, and how many more there are."""
    return ", ".join(items[:SHOWN]) + (f", and {len(items) - SHOWN} more" if len(items) > SHOWN else "")


def files_row(rep, project: Path, doc: dict) -> None:
    """Row kit:files: every generated file is what kit.json lists, kit.json is the bytes the `kit` report recorded, and nothing unlisted sits in a generated folder. Skipped with no `kit` report."""
    label = "the kit holds the generated files kit.json lists, as `kit build` wrote them"
    outputs = (kitlib.kit_report(project) or {}).get("outputs")
    if not (isinstance(outputs, dict) and outputs):
        rep.add("kit:files", "skipped", label, detail="not verified: there is no `kit` report that records what the build wrote; run `brand-creator kit build --yes`")
        return
    got, bad = kitlib.files_check(project, doc, outputs), []
    if got["differ"]:
        bad.append(f"{len(got['differ'])} generated file(s) differ from kit.json: {named([f'{rel} ({why})' for rel, why in got['differ']])}; "
                   "change the brand project and run `brand-creator kit build --yes`")
    if got["kit_json"]:
        bad.append(f"{kitlib.KIT_FILE} {got['kit_json']}; run `brand-creator kit build --yes`")
    if got["foreign"]:
        bad.append(f"{len(got['foreign'])} file(s) in a generated folder are not listed in kit.json: {named(got['foreign'])}; move it to recipes/ or a folder of your own")
    if bad:
        rep.add("kit:files", "fail", label, detail="; ".join(bad))
    else:
        rep.add("kit:files", "pass", label, detail=f"{got['count']} generated files are the bytes kit.json lists, kit.json is the bytes the `kit` report recorded, and nothing unlisted sits in {', '.join(kitlib.GENERATED_DIRS)}")


def links_row(rep, project: Path) -> None:
    """Row kit:links: every relative link of a .md, .html or .css file of the kit resolves to a file inside the kit."""
    label = "every relative link in the kit resolves to a file inside it"
    got = kitlib.link_check(project)
    if got["bad"]:
        listed = [f"{f}:{line} -> {target} ({why})" for f, line, target, why in got["bad"]]
        rep.add("kit:links", "fail", label, detail=f"{len(listed)} of {got['links']} relative links {'does' if len(listed) == 1 else 'do'} not resolve inside the kit: {named(listed)}")
    else:
        rep.add("kit:links", "pass", label, detail=f"{got['links']} relative link{'s' if got['links'] != 1 else ''} in {got['files']} .md, .html and .css files resolve inside the kit")


def fill_row(rep, project: Path) -> None:
    """Row kit:fill: no `[[fill` marker is left in a text file of the kit."""
    label = "no fill marker is left in the kit"
    found = kitlib.fill_markers(project)
    if found:
        rep.add("kit:fill", "fail", label, detail=f"{len(found)} fill marker(s) left: {named(found)}; replace each note with your own text (these files are yours)")
    else:
        rep.add("kit:fill", "pass", label, detail="no [[fill marker is left")


def versions_row(rep, project: Path, doc: dict) -> None:
    """Row kit:versions: SKILL.md holds the version of kit.json exactly once, and the kit is of the approved edition."""
    label = "the kit states one version, kit.json's, and is of the approved edition"
    bad = kitlib.version_problems(project, doc)
    if bad:
        rep.add("kit:versions", "fail", label, detail="; ".join(bad))
    else:
        rep.add("kit:versions", "pass", label, detail=f"{kitlib.version_line(doc['version'])} once in {kitlib.SKILL_FILE}; the edition {doc['edition']} is the approved one")


def plugin_row(rep, doc: dict) -> None:
    """Row kit:plugin: warn when the kit was built by another plugin version than the one running."""
    label = "the kit was built by this version of the plugin"
    now = plugin_version()
    if doc["plugin_version"] != now:
        rep.add("kit:plugin", "warn", label, detail=f"the kit was built by brand-creator {doc['plugin_version']}, this is {now}: `brand-creator kit build --yes` records it (the kit's version moves only if its content does)")
    else:
        rep.add("kit:plugin", "pass", label, detail=f"built by brand-creator {now}")


def sources_row(rep, project: Path, doc: dict) -> None:
    """Row kit:sources: skipped (not verified) when the brand changed after the kit was built, naming the sources that changed."""
    label = "the kit was made from the brand as it is now"
    try:
        changed = kitlib.source_changes(project, doc)
    except CliError as e:
        rep.add("kit:sources", "skipped", label, detail=f"not verified: the brand's sources cannot be read ({e.message}); run `brand-creator kit build --yes` again")
        return
    if changed:
        rep.add("kit:sources", "skipped", label, detail=f"not verified: the brand changed after the kit was built ({', '.join(changed)}); run `brand-creator kit build --yes`")
    else:
        rep.add("kit:sources", "pass", label, detail="the sources kit.json records are the ones the project has now")


def owned_check_row(rep, project: Path, doc: dict) -> None:
    """Row kit:owned: warn when an owner file is not what the last build recorded."""
    label = "the owner's files are as the last build recorded them"
    changed = kitlib.owned_changes(project, doc)
    if changed:
        why_files: dict[str, list[str]] = {}
        for rel, why in changed:
            why_files.setdefault(why, []).append(rel)
        then = {kitlib.OWNED_CHANGED: "`brand-creator kit build --yes` records it and moves the version on",
                kitlib.OWNED_MISSING: "`brand-creator kit build --yes` writes the scaffold again",
                kitlib.OWNED_NOT_FILE: "move it away yourself, then run `brand-creator kit build --yes`"}
        rep.add("kit:owned", "warn", label, detail="; ".join(f"{named(rels)} {why}: {then[why]}" for why, rels in why_files.items()))
    else:
        rep.add("kit:owned", "pass", label, detail=f"the {len(kitlib.OWNED_FILES)} owner files are as the last build recorded them")


def check(project: Path, a) -> int:
    if not kitlib.exists(project):
        fail(EXIT_USAGE, "no kit in this project: `brand-creator kit build --yes` (opt-in at G5)")
    if (kitlib.kit_dir(project) / kitlib.KIT_FILE).is_symlink():
        fail(EXIT_USAGE, f"{kitlib.kit_rel(project)}/{kitlib.KIT_FILE} is a link, and a link is never read through: `brand-creator kit build --yes --replace` moves it aside and writes the kit")
    doc = kitlib.load(project)
    rep = Report(kitlib.CHECK_TOOL, project, renderer="n/a (generated files)")
    rep.inputs.extend(kitlib.check_inputs(project))
    files_row(rep, project, doc)
    links_row(rep, project)
    fill_row(rep, project)
    versions_row(rep, project, doc)
    plugin_row(rep, doc)
    sources_row(rep, project, doc)
    owned_check_row(rep, project, doc)
    rep.extra.update({"kit_version": doc["version"], "kit_tree_sha": kitlib.tree_sha(project)})
    return rep.finish()


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
    owner = kitlib.owner_plan(project)                     # the owner's files: every scaffold is filled now, so an unknown placeholder stops the run before anything is written
    csha = kitlib.content_sha({rel: sha256_bytes(data) for rel, data in generated.items()}, owner["owned"])
    prev = kitlib.previous(project)
    version = kitlib.next_version(prev, edition, csha)
    files = kitlib.with_version(generated, version)
    src = kitlib.sources(project)
    files[kitlib.KIT_FILE] = kitlib.kit_json_bytes(project, files, version, edition, csha, src, fonts, owner["owned"])
    if a.plan or not a.yes:
        print(f"would write {len(files)} generated files into {kd_rel}/ (version {version})")
        for rel in sorted(files):
            print(f"generated {rel} ({len(files[rel])} bytes)")
        for rel in owner["write"]:
            print(f"scaffold {rel} ({len(owner['files'][rel])} bytes, written once, never overwritten)")
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

    def put(rel: str) -> None:
        nonlocal written, unchanged
        if write_bytes_if_changed(confine(project, f"{kd_rel}/{rel}", what="kit file"), files[rel]):
            written += 1
        else:
            unchanged += 1

    for rel in sorted(r for r in files if r != kitlib.KIT_FILE):
        put(rel)
    scaffolded, kept = kitlib.write_owner(project, owner)   # the owner's files go in before kit.json, which records their hashes and is the last file written:
    put(kitlib.KIT_FILE)                                    # a run that stops half way leaves a kit that kit.json does not vouch for
    rep.add("kit:written", "pass", f"{kd_rel}/ generated",
            detail=f"{len(files)} generated files: {written} written, {unchanged} unchanged, {len(moving)} moved to {folder}/; version {version}")
    owner_row(rep, scaffolded, kept)
    font_row(rep, fonts)
    ground_row(rep, kitlib.ground_plan(project))
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
    c = sub.add_parser("check", help="prove the kit is whole: files, links, fill markers, versions, sources and the owner's files (writes the report kit-check)")
    c.add_argument("--project", default=argparse.SUPPRESS, help="brand project folder")
    a = ap.parse_args()
    project = find_project(getattr(a, "project", None))
    return build(project, a) if a.cmd == "build" else check(project, a)


main_guard(main)

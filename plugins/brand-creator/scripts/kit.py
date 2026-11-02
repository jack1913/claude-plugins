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
    brand-creator kit status --repo DIR[=LABEL] [--repo ...] [--json]   is the copy of the kit in a product repository current, and what to copy (writes nothing)

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
A font a reference page brings, a .ttf, .otf, .woff or .woff2 file in a page folder or one a page loads from outside assets/fonts/, goes by the same rule: it is copied (at its project path under brand/, with
the licence text) only when the current fontcheck report has read it as OFL (`brand-creator fontcheck --font FILE` for it; fontcheck always reads assets/fonts/ as well) and an OFL licence text sits
in assets/fonts/. Any other, a font fontcheck has not read included, is listed in fonts.not_copied with the reason and not copied. snippets/fonts.css holds the fonts of assets/fonts/ only.

Grounds: once the owner has named the colours text sits on (tokens.json `grounds`, `named_by_owner` a real date and the owner's words), snippets/on-ground.css holds one
[data-ground="<name>"] scope for each ground after the first, which is the page ground: the scope sets the ground's own background and points the page ground's text, action,
on-action, focus and border variables at the ground's own colours. While the grounds are only a proposal no snippet is written (row kit:grounds says so); a ground the
tokens give no colour for, one that gives two roles different colours where the page ground uses one token for both (a rule that sets a variable twice keeps only
the later value), one that uses a variable its own scope sets, or one whose data-ground name is taken, is left out and named.

Reference pages: when the project has site/site.json (the pages the owner approved with `site approve`), each page goes into the kit at its project path under brand/ with everything in its folder
(its stills too) and every project file it loads (src, href, poster and srcset in the HTML, url() in a <style>, a style attribute and a css file; a css file the page loads is read for what it loads
too, and no further), and gets a generated reference-pages/<id>/notes.md: its layout (structure only), the approval, links to the page and its stills, and its choices, each tagged
[rule: site:<id>] or [example]. The build stops (exit 1, nothing written) when site/site.json does not validate (the first three problems are quoted) or when a page has no current, passing
page-check report or no current stills (the page and the command to run are named); a path that leaves the project, by name or by a link, is exit 2, and so is a page folder or index.html that is a link
leading out of the project, whatever the bytes behind the link are (it is judged before the record's sha256 is). A URL that names a folder is the folder's index.html when the project has one, as a web server
answers it; a folder without index.html stops the build. A font a page has that the fonts rule does not copy is listed in kit.json (fonts.not_copied) and not copied: row kit:reference-pages warns and `kit check`
warns on the link too. kit.json records for each page its
source_sha, the inputs_sha of its page-check report and of its capture.json (`reference_pages`) and, under sources, one sha256 over everything the pages are made from (`pages`).

Masters: everything under assets/masters/ (the ad, deck and other templates the owner approved, with their pictures, PDFs, PPTX and fonts; the plugin cannot know which are approved, so only approved ones belong
there) is copied byte for byte to brand/<its project path> and recorded in kit.json sources (`masters`, present only when the folder holds a file). A font in it goes by the font rule above, and a font file of a format fontcheck cannot read (.ttc, .otc, .eot, .dfont, .pfb, .pfm, .pfa) is never copied: it is listed in kit.json fonts.not_copied with that reason; a link inside a master
HTML file must resolve inside the kit (`kit check`). A project without the folder gets no change at all. Row kit:masters.

The owner's files are every file of the kit folder that is no generated file, no kit.json and no Finder .DS_Store. Five of them (EXTENDING.md, voice.md, visual.md, golden-rules.md, recipes/web-page.md)
are scaffolded from templates/kit/ (the placeholders {{brand}} and {{skill}} filled; any other {{...}} is exit 2 and nothing is written) only when the file is absent; they are never overwritten or moved. A
recipe or a folder of your own (recipes/email.md, notes/) is yours as it stands. kit.json records the sha256 of each one (`owned`) and the version's content hash covers them, so a file of yours added,
edited or taken away moves the version at the next build. A link among them, whatever it points at (a file or folder of the project, nothing, or a place outside the project), is refused like a kit.json that is a link: the build stops (exit 1), --replace moves the link itself aside. The plan lists the scaffolds
the build would write as `scaffold <path> (<bytes> bytes, ...)`.

Nothing in a generated file is edited by hand: change the brand project and build again. A file of the kit that differs from what the last build wrote, or a file in
brand/, snippets/ or reference-pages/ that the kit did not write (a file named exactly .DS_Store, which Finder leaves behind, is not one; a link is one, wherever it sits in the kit and whatever it points at, and is never followed or written through), stops the build
(exit 1, up to 6 paths named) unless --replace, which moves each to removed-<date>[-n]/<its project path>. A file the last build wrote that the project no longer has (a logo taken away) is moved there too, and said so. Nothing is deleted.
A SKILL.md that `applied-skill` wrote is taken over; one edited by hand stops the first build the same way.

`kit check` reads the kit and writes the report `kit-check`; no kit is exit 2. Its inputs are every file under the kit folder (a Finder `.DS_Store` is none), the files the kit is made from, BRAND-STATE.md and the `kit` report, so any change
makes it stale. Rows: kit:files (every generated file is what kit.json lists, kit.json is the bytes the `kit` report recorded, no file in a generated folder is unlisted; with no `kit` report: not verified), kit:links (every
relative link in a .md, .html or .css file resolves to a file inside the kit: one that points outside it, an absolute path or a missing file fails; a link to a folder is its index.html when the kit has one there;
a link to a font that kit.json lists in fonts.not_copied is a warning: the font must be supplied under its own licence), kit:fill (no `[[fill` marker is left in a text file), kit:versions (SKILL.md holds
`Kit version <kit.json version> (kit.json).` exactly once, and the kit's edition is the approved one), kit:plugin (warns on another plugin version), kit:sources (not verified when the brand changed after the kit was built, naming
what changed) and kit:owned (warns when an owner file was changed, added or removed since the last build). Exit 0 pass, 1 a row failed, 3 not verified. A link inside the kit is never followed.
Two rows read the owner's Markdown files (recipes/**/*.md and any other .md of hers except EXTENDING.md and voice.md), golden-rules.md, visual.md and the generated reference-pages/<id>/notes.md (an owner file that is not Markdown is never read by
kit:fill, kit:tags or kit:numbers): kit:tags (every bullet, and in golden-rules.md and visual.md every numbered
line too, outside code fences, carries `[example]` or `[rule: <id>]`; a numbered step of a recipe needs no tag. Every id a `[rule: <id>]` names, on any line of those files, a numbered step, a sentence or
a code fence included, is one `known_rule_ids` lists: a rule of BRAND-STATE.md written bare, `page:<id>`, `site:<id>`) and kit:numbers (every value, code fences included, has a citation on its own line: a
number with a unit, a ratio, a hex colour or rgb( hsl( oklch( needs `[example]`, a known rule id or a token that exists, `var(--name)` of the kit's tokens.css or `{dotted.path}` of its tokens.json, a path
that ends at a token: `color.bg`, `modes.light.color.bg`, never a group such as `modes.light`; a token reference that does not exist fails outside a code fence on any line, a code span included, and inside
a fence on a line with a value; a reference inside a fence on a line with no value, as in a component sample, is not judged). When the rule ids cannot be read (a site/site.json that does not parse) and a
line names one, that line is not judged: a row with a failure that needs no rule id still fails, and says how many lines it left, otherwise it is not verified.
A row kit:reference-page:<id> for each reference page kit.json lists (none while it lists none) says whether the kit's copy still stands for the brand: not verified when the page changed in the project since the kit
was built (site/site.json, or the page file, is no longer the sha256 kit.json recorded), or when the tokens or rules changed since the page was checked (its page-check report or its capture.json is stale, or was made from
other files than the kit's copy was); fail when its page-check report is current and failing; pass otherwise. The kit is downstream of the pack (lib/stale.py does not see it), so it records its own sources.

Writes the report `kit` (rows kit:written and kit:owned; outputs lists every generated path with its sha256, kit.json included, and no owner file). Exit 0 written. Exit 1: G5 not recorded, no approved
edition, a band drawing the project does not have, or a hand edit or foreign file without --replace. Exit 2: no --yes (the plan is printed first); a path that leaves the
project; a band drawing that is not written as a plain path; a scaffold with a placeholder this version does not know. Exit 1 also: an owner file's path that holds a folder, or a folder an owner file belongs in (recipes/) that is a file; a link among the owner's files, whatever it points at (--replace moves it); assets/masters that is no folder, a link to a folder in it. Exit 2 also: a master that is a link leading out of the project. Exit 3: the tokens are not built; a scaffold the plugin lacks; fonts are in assets/fonts/ and there is no current fontcheck report (the kit is written without them).

`kit status` reads <DIR>/.claude/skills/<slug>-brand/ of each repository and writes nothing, in the repository or in the project (no report either). Per repository it says `not installed`
(no kit.json there), `current (version V)` (every generated file and kit.json are the project's bytes) or `not current` (the installed and the project version, then the generated files that
differ, are missing, or are left over from an older kit; when both versions are the same it says so and counts what differs). A file left over is not on the copy list: the implementer moves it
to removed-<date>/<kit folder>/ in the repository, keeping its path, and deletes nothing (--json: `left_over` lists them, `left_over_to` says where they go). It also lists the owner files that
differ (the repository's own, kept on update) and the copy list: the generated files to copy
(kit.json last), then the owner files the repository lacks (all of the owner's files, those she added too), as paths relative to the kit folder. Without --repo it reads each repository that has a `kit` row in adoption.json (none: exit 2).
Exit 0 when every copy is current, 1 when one is not installed or not current, or when a repository's kit folder changed while it was read (its files, sizes and times are listed before
and after). Exit 2: no kit in the project; a folder that does not exist; the project itself or a folder inside it; your home folder or any path inside ~/.claude (the kit goes into one product
repository at a time, never into a global skills folder); a kit folder that is a link. Exit 3: the kit in the project is not whole (`kit check` says what).
"""
import argparse
import functools
import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
sys.path.insert(0, str(HERE / "booklib"))
sys.path.insert(0, str(HERE / "adaptlib"))
sys.path.insert(0, str(HERE / "boardlib"))   # kitlib.known_rule_ids reads the choices of site/site.json with boardlib/sitedata.py
sys.path.insert(0, str(HERE / "pagelib"))    # kitlib names the page-check report of an approved reference page with pagelib/pagecheck.py (pagecheck.report_tool)
import adapt  # noqa: E402
import adoptdata  # noqa: E402
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


def reference_row(rep, pages: dict) -> None:
    """Row kit:reference-pages: pass with the number of approved reference pages copied (and their ids), warn when a page has a font the kit does not copy (a font file in its folder, or one it loads;
    the font rule decides, as for assets/fonts/: the row says which font, how the page has it and why it is left out, and `kit check` warns on the link instead of failing it), info "no approved
    reference pages" when the project has none."""
    label = "approved reference pages"
    n = len(pages["records"])
    if not n:
        rep.add("kit:reference-pages", "info", label, detail="no approved reference pages")
        return
    ids = ", ".join(r["id"] for r in pages["records"])
    copied = (f"{n} approved reference page{'s' if n != 1 else ''} copied with {'their' if n != 1 else 'its'} stills and the files {'they load' if n != 1 else 'it loads'} ({ids}); "
              "notes in reference-pages/<id>/notes.md")
    left = pages["not_copied"]
    if left:
        shown = "; ".join(f"{font} {how} ({why})" for font, how, why in left[:SHOWN]) + (f"; and {len(left) - SHOWN} more" if len(left) > SHOWN else "")
        rep.add("kit:reference-pages", "warn", label,
                detail=f"{copied}; a font the kit does not copy is listed in kit.json (fonts.not_copied), and a link to it is a warning in `kit check`: supply it under its own licence: {shown}")
    else:
        rep.add("kit:reference-pages", "pass", label, detail=copied)


def masters_row(rep, masters: dict) -> None:
    """Row kit:masters: pass with the number of master files copied (the files below assets/masters/, byte for byte, at brand/assets/masters/), warn when a font among them is not copied (the font rule
    decides, as for assets/fonts/: the row says which font, how and why; `kit check` warns on a link to it). No row while the project has no file there."""
    if not masters["paths"]:
        return
    label = "the masters of assets/masters/"
    n = sum(1 for rel in masters["files"] if rel.startswith(f"{kitlib.PREFIX}{kitlib.MASTERS_DIR}/"))
    copied = f"{n} master file{'s' if n != 1 else ''} copied byte for byte from {kitlib.MASTERS_DIR}/ to {kitlib.PREFIX}{kitlib.MASTERS_DIR}/"
    left = masters["not_copied"]
    if left:
        shown = "; ".join(f"{font} {how} ({why})" for font, how, why in left[:SHOWN]) + (f"; and {len(left) - SHOWN} more" if len(left) > SHOWN else "")
        rep.add("kit:masters", "warn", label, detail=f"{copied}; a font the kit does not copy is listed in kit.json (fonts.not_copied), and a link to it is a warning in `kit check`: supply it under its own licence: {shown}")
    else:
        rep.add("kit:masters", "pass", label, detail=copied)


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


def links_row(rep, project: Path, doc: dict) -> None:
    """Row kit:links: every relative link of a .md, .html or .css file of the kit resolves to a file inside the kit (a link to a folder is its index.html, when the kit has one). A link to a font that
    kit.json lists as not copied (fonts.not_copied) is no broken link but is never a silent pass: the row warns that the font must be supplied under its own licence. A broken link fails."""
    label = "every relative link in the kit resolves to a file inside it"
    got = kitlib.link_check(project, doc)
    loose = [f"{f}:{line} -> {target} ({font}: {reason})" for f, line, target, font, reason in got["unsupplied"]]
    if got["bad"]:
        listed = [f"{f}:{line} -> {target} ({why})" for f, line, target, why in got["bad"]]
        rep.add("kit:links", "fail", label, detail=f"{len(listed)} of {got['links']} relative links {'does' if len(listed) == 1 else 'do'} not resolve inside the kit: {named(listed)}"
                + (f"; {len(loose)} more lead{'s' if len(loose) == 1 else ''} to a font the kit does not copy" if loose else ""))
    elif loose:
        rep.add("kit:links", "warn", label,
                detail=(f"{len(loose)} of {got['links']} relative links lead{'s' if len(loose) == 1 else ''} to a font the kit does not copy (listed in kit.json fonts.not_copied), so "
                        f"{'it does' if len(loose) == 1 else 'they do'} not resolve inside the kit: the font must be supplied under its own licence, copied into the product from where you licensed it: {named(loose)}; "
                        f"the other {got['links'] - len(loose)} resolve inside the kit"))
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
                kitlib.OWNED_ADDED: "`brand-creator kit build --yes` records it and moves the version on",
                kitlib.OWNED_REMOVED: "`brand-creator kit build --yes` records it and moves the version on",
                kitlib.OWNED_MISSING: "`brand-creator kit build --yes` writes the scaffold again",
                kitlib.OWNED_NOT_FILE: "move it away yourself, then run `brand-creator kit build --yes`"}
        rep.add("kit:owned", "warn", label, detail="; ".join(f"{named(rels)} {why}: {then[why]}" for why, rels in why_files.items()))
    else:
        rep.add("kit:owned", "pass", label, detail=f"the {len(doc['owned'])} owner files are as the last build recorded them")


IDS_HINT = "fix it and run `brand-creator kit check` again"


def unreadable_ids_row(rep, row_id: str, label: str, e: CliError) -> None:
    """A `[rule: <id>]` tag cannot be judged because the rule ids cannot be read (a site record that does not parse), and nothing else is wrong: not verified, never a pass."""
    rep.add(row_id, "skipped", label, detail=f"not verified: the rule ids a tag may name cannot be read ({e.message}); {IDS_HINT}")


def unjudged_note(got: dict) -> str:
    """What a failing row adds when the rule ids could not be read as well: the failures listed need no rule id, and the lines that name one were left unjudged. Empty when the ids were read."""
    if got["unread"] is None:
        return ""
    return f"; {got['unjudged']} line(s) that name a rule were not judged, because the rule ids cannot be read ({got['unread'].message}); {IDS_HINT}"


def tags_row(rep, project: Path, known) -> None:
    """Row kit:tags: every bullet of a recipe and of the reference-page notes, and every bullet or numbered line of golden-rules.md and visual.md, carries `[example]` or a `[rule: <id>]`, and every rule id
    named on any line of those files (a numbered step, a sentence, a heading, a code fence too) is one the kit knows. An untagged line fails whether or not the rule ids can be read; with only lines that
    name a rule left, an unreadable site record is not verified."""
    label = "every rule line in the owner's files says what it is: an example or a rule the kit knows"
    got = kitlib.tag_check(project, known)
    if got["bad"]:
        listed = [f"{f}:{line} {why}" for f, line, why in got["bad"]]
        rep.add("kit:tags", "fail", label, detail=f"{len(listed)} of {got['lines']} line(s) lack a valid tag: {named(listed)}; {kitlib.TAG_HINT}{unjudged_note(got)}")
    elif got["unread"] is not None:
        unreadable_ids_row(rep, "kit:tags", label, got["unread"])
    elif got["lines"]:
        rep.add("kit:tags", "pass", label, detail=f"{got['lines']} line(s) carry `{kitlib.TAG_EXAMPLE}` or a rule id the kit knows")
    else:
        rep.add("kit:tags", "pass", label, detail="no bullet or numbered line needs a tag")


def numbers_row(rep, project: Path, known) -> None:
    """Row kit:numbers: every value in the owner's files (code fences too) cites a token, a known rule or `[example]` on its own line, and a token reference exists (outside a code fence on any line, inside one on a line with a value).
    A failure that needs no rule id is found whether or not the rule ids can be read; with none, an unreadable site record is not verified."""
    label = "every value in the owner's files cites a token or a rule, or says it is an example"
    got = kitlib.number_check(project, known)
    if got["bad"]:
        listed = [f"{f}:{line} ({why})" for f, line, why in got["bad"]]
        rep.add("kit:numbers", "fail", label, detail=f"{len(listed)} line(s) hold a value with no citation or a token that does not exist: {named(listed)}; {kitlib.VALUE_HINT}{unjudged_note(got)}")
    elif got["unread"] is not None:
        unreadable_ids_row(rep, "kit:numbers", label, got["unread"])
    elif got["values"]:
        rep.add("kit:numbers", "pass", label, detail=f"{got['values']} value(s) on {got['lines']} line(s) cite a token, a known rule or `{kitlib.TAG_EXAMPLE}`")
    else:
        rep.add("kit:numbers", "pass", label, detail="no value (a number with a unit, a ratio or a colour) needs a citation")


def reference_page_rows(rep, project: Path, doc: dict) -> None:
    """Rows kit:reference-page:<id>, one for each page kit.json lists: skipped (not verified) when the page changed in the project since the kit was built, or the tokens or rules changed since it was
    checked (its page-check report or its capture.json is stale, or was made from other files than the kit's copy), or a record cannot be used; fail when its page-check report is current and failing;
    pass otherwise. No row while the kit holds no reference page."""
    for pid, status, detail in kitlib.reference_page_states(project, doc):
        rep.add(f"{kitlib.PAGE_ROW}{pid}", status, f"reference page {pid} is current and passes its page check", detail=detail)


def check(project: Path, a) -> int:
    if not kitlib.exists(project):
        fail(EXIT_USAGE, "no kit in this project: `brand-creator kit build --yes` (opt-in at G5)")
    if (kitlib.kit_dir(project) / kitlib.KIT_FILE).is_symlink():
        fail(EXIT_USAGE, f"{kitlib.kit_rel(project)}/{kitlib.KIT_FILE} is a link, and a link is never read through: `brand-creator kit build --yes --replace` moves it aside and writes the kit")
    doc = kitlib.load(project)
    rep = Report(kitlib.CHECK_TOOL, project, renderer="n/a (generated files)")
    rep.inputs.extend(kitlib.check_inputs(project))
    files_row(rep, project, doc)
    links_row(rep, project, doc)
    fill_row(rep, project)
    versions_row(rep, project, doc)
    plugin_row(rep, doc)
    sources_row(rep, project, doc)
    owned_check_row(rep, project, doc)
    known = functools.cache(lambda: frozenset(kitlib.known_rule_ids(project)))   # read at the first tag that names a rule, once
    tags_row(rep, project, known)
    numbers_row(rep, project, known)
    reference_page_rows(rep, project, doc)
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
    pages = kitlib.reference_plan(project, fonts)          # the approved reference pages: checked and read first, so that a page that cannot go stops the build before anything is written
    masters = kitlib.masters_plan(project)                 # the approved masters of assets/masters/: read now, so that one that cannot go stops the build before anything is written
    generated = kitlib.plan(project, fonts, pages, masters)   # SKILL.md with the literal <version>: the version is decided from what the plan holds
    owner = kitlib.owner_plan(project)                     # the owner's files: every scaffold is filled now, so an unknown placeholder stops the run before anything is written
    csha = kitlib.content_sha({rel: sha256_bytes(data) for rel, data in generated.items()}, owner["owned"])
    prev = kitlib.previous(project)
    version = kitlib.next_version(prev, edition, csha)
    files = kitlib.with_version(generated, version)
    src = kitlib.sources(project)
    files[kitlib.KIT_FILE] = kitlib.kit_json_bytes(project, files, version, edition, csha, src, fonts, owner["owned"], pages, masters)
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
    stopped = ([(rel, "edited by hand") for rel in edited] + [(rel, "not written by the kit") for rel in foreign]
               + [(rel, kitlib.LINK_AMONG_OWNER) for rel in owner["links"]])
    if stopped and not a.replace:
        shown = ", ".join(f"{rel} ({why})" for rel, why in stopped[:SHOWN]) + (f", and {len(stopped) - SHOWN} more" if len(stopped) > SHOWN else "")
        fail(EXIT_FAIL, f"{kd_rel}/ holds files the kit would overwrite or does not know: {shown}. Change the brand project instead (for a link among your own files, put the file itself there) and run "
                        f"`brand-creator kit build --yes` again, or add --replace to move them to removed-{today()}/ first (nothing is deleted)")
    moving = (edited + foreign + owner["links"] if a.replace else []) + retired
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
    reference_row(rep, pages)
    masters_row(rep, masters)
    rep.extra.update({"outputs": {rel: sha256_bytes(data) for rel, data in sorted(files.items())}, "kit_version": version, "content_sha": csha,
                      "adapter_state_sha": src["state_sha"], "kit_sources_sha": kitlib.sources_sha(project, src)})
    return rep.finish()


def parse_repo(spec: str) -> tuple[str, str, Path]:
    """`DIR[=LABEL]` as (label, DIR as given, DIR with its links resolved). The label is the folder's name when none is given (a path may hold an `=`, a label never holds a slash)."""
    p, sep, label = spec.rpartition("=")
    if not sep or "/" in label or os.sep in label:
        p, label = spec, ""
    if not p.strip():
        fail(EXIT_USAGE, f"--repo {spec}: name a folder")
    d = Path(p).expanduser()
    if not d.is_dir():
        fail(EXIT_USAGE, f"--repo {p}: not a folder")
    real = Path(os.path.realpath(d))
    return label.strip() or re.sub(r"[^A-Za-z0-9._-]+", "-", real.name) or "repo", p, real


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


def adoption_repos(project: Path) -> list[str]:
    """`DIR=LABEL` of every repository that has a `kit` row in adoption.json, in the order of its rows, each once. The path is the one the adoption list stores (relative to the project)."""
    try:
        doc = adoptdata.load(project)
    except (OSError, ValueError) as e:
        fail(EXIT_USAGE, f"{adoptdata.FILE} cannot be read ({e}): pass --repo DIR")
    if not isinstance(doc, dict):
        return []
    repos = {r.get("id"): r for r in doc.get("repos") or [] if isinstance(r, dict)}
    root, out = Path(os.path.realpath(project)), []
    for row in doc.get("rows") or []:
        if not isinstance(row, dict) or row.get("category") != "kit":
            continue
        repo = repos.get(row.get("repo"))
        if not (repo and isinstance(repo.get("path"), str) and isinstance(repo.get("label"), str)):
            fail(EXIT_USAGE, f"{adoptdata.FILE}: the kit row {row.get('n')} names a repository that is not listed in `repos`: run `brand-creator adoption verify`")
        spec = f"{os.path.normpath(root / repo['path'])}={repo['label']}"
        if spec not in out:
            out.append(spec)
    return out


def left_over_to(kd_rel: str) -> str:
    """Where a file left over from an older kit goes in the repository (the implementer moves it there; nothing is deleted): removed-<date>/, then the kit folder, then its path in the kit."""
    return f"removed-<date>/{kd_rel}/"


def not_current_line(res: dict) -> str:
    """The first line of a copy that is not current. With two versions that differ it names both. With the same version on both sides it says so and what differs, so that it does
    not read as a contradiction: the version is the same, the files are not."""
    return f"{res['label']}: " + kitlib.not_current_text(res["installed_version"], res["project_version"], res["differ"], res["missing"], res["left_over"])


def status_lines(res: dict, kd_rel: str) -> list[str]:
    """The text of one repository: its state, what differs, and the copy list."""
    v, label = res["project_version"], res["label"]
    if res["state"] == kitlib.NOT_INSTALLED:
        L = [f"{label}: not installed"]
    elif res["state"] == kitlib.CURRENT:
        L = [f"{label}: current (version {v})"]
    else:
        L = [not_current_line(res)]
    if res["note"]:
        L.append(f"  {res['note']}")
    for title, items in (("generated files that differ", [f"{rel} ({why})" for rel, why in res["differ"]]),
                         ("generated files that are missing", res["missing"]),
                         (f"left over from an older kit (not in this kit, so not on the copy list; move each to {left_over_to(kd_rel)} in the repository, keeping its path; nothing is deleted)",
                          res["left_over"]),
                         ("owner files that differ (kept on update)", [rel for rel, _why in res["owner_differ"]])):
        if items:
            L += [f"  {title}:", *(f"    {i}" for i in items)]
    if res["copy"]:
        L.append(f"  copy list, paths relative to {kd_rel}/ (the generated files, kit.json last, then the owner files the repository lacks):")
        L += [f"    {rel} (owner file, the repository has none)" if rel in res["copy_owner"] else f"    {rel}" for rel in res["copy"]]
    return L


def status(project: Path, a) -> int:
    if not kitlib.exists(project):
        fail(EXIT_USAGE, "no kit in this project: `brand-creator kit build --yes` (opt-in at G5)")
    if (kitlib.kit_dir(project) / kitlib.KIT_FILE).is_symlink():
        fail(EXIT_USAGE, f"{kitlib.kit_rel(project)}/{kitlib.KIT_FILE} is a link, and a link is never read through: `brand-creator kit build --yes --replace` moves it aside and writes the kit")
    doc = kitlib.load(project)
    kd, kd_rel, name = kitlib.kit_dir(project), kitlib.kit_rel(project), adapt.skill_name(project)
    specs = a.repo or adoption_repos(project)
    if not specs:
        fail(EXIT_USAGE, "pass --repo DIR (repeatable): the adoption list has no repository with a kit row (`brand-creator adoption add --repo LABEL --kit`)")
    planned = []
    for spec in specs:                                    # every folder is judged before one is read: a bad one stops the run with nothing printed
        label, given, real = parse_repo(spec)
        why = refusal(project, real)
        if why:
            fail(EXIT_USAGE, f"--repo {given} {why}")
        installed = real / adapt.SKILL_DIR / name
        if installed.is_symlink():
            fail(EXIT_USAGE, f"--repo {given}: {kd_rel}/ is a link, and a link is never read through: look at where it leads and replace it with a folder")
        target = Path(os.path.realpath(installed))
        why = refusal(project, target)
        if why:
            fail(EXIT_USAGE, f"--repo {given}: {kd_rel} leads to {target}, which {why}")
        planned.append((label, real, installed))
    results = []
    for label, real, installed in planned:
        before = kitlib.folder_state(installed)
        res = kitlib.compare(kd, installed)
        res.update({"label": label, "path": str(real), "read_only": kitlib.folder_state(installed) == before, "note": None})
        if res["state"] == kitlib.NOT_INSTALLED and os.path.lexists(installed):
            res["note"] = f"{kd_rel}/ is there but holds no {kitlib.KIT_FILE}: it is not a kit, so look at it before you copy over it"
        results.append(res)
    kept = all(r["read_only"] for r in results)
    ok = kept and all(r["state"] == kitlib.CURRENT for r in results)
    if a.json:
        keys = ("label", "path", "state", "installed_version", "project_version", "differ", "missing", "left_over", "left_over_to", "owner_differ", "copy", "copy_owner", "read_only")
        for r in results:   # where the files left over go, in the repository: only said when there are some
            r["left_over_to"] = left_over_to(kd_rel) if r["left_over"] else None
        shown = [{k: ([{"file": rel, "why": why} for rel, why in r[k]] if k in ("differ", "owner_differ") else r[k]) for k in keys} for r in results]
        print(json.dumps({"kit": name, "version": doc["version"], "repos": shown, "current": ok}, indent=2, ensure_ascii=False))
    else:
        print(f"kit {name}, version {doc['version']}")
        for r in results:
            print("\n".join(status_lines(r, kd_rel)))
        if kept:
            print("read only: nothing in the installed kit folders changed while they were read")
    for r in results:
        if not r["read_only"]:
            print(f"error: {r['label']}: the installed kit folder changed while it was read, so what is said about it cannot be relied on", file=sys.stderr)
    return 0 if ok else EXIT_FAIL


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
    c = sub.add_parser("check", help="prove the kit is whole: files, links, fill markers, versions, sources, the owner's files, their tags and values (writes the report kit-check)")
    c.add_argument("--project", default=argparse.SUPPRESS, help="brand project folder")
    st = sub.add_parser("status", help="is the copy of the kit in a product repository current, and what to copy (reads only; writes nothing)")
    st.add_argument("--repo", action="append", default=[], metavar="DIR[=LABEL]",
                    help="a product repository (repeatable; read only). Without it, every repository that has a kit row in adoption.json")
    st.add_argument("--json", action="store_true", help="print the result as JSON")
    st.add_argument("--project", default=argparse.SUPPRESS, help="brand project folder")
    a = ap.parse_args()
    project = find_project(getattr(a, "project", None))
    if a.cmd == "status":
        return status(project, a)
    return build(project, a) if a.cmd == "build" else check(project, a)


main_guard(main)

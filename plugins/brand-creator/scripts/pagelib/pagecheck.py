"""page-check, the judging half: what a page check is about, how it is aimed, and the rows it reports.

`brand-creator page-check` measures one rendered page against the brand. Measuring happens in the browser (`render.mjs page-measure`, with the
in-page collectors of `page_measure.mjs`); this module turns those raw facts into report rows against the project's tokens, FACTS.md and the `page`
block of qa/rules.json. It holds the pieces other tools import (`board_lint.py`, `check.py` and the later kit call them; nobody writes a second
version):

  report_tool(ident)      the report name `page-check/<slug>-<hash6>` of one target. `ident` is the project-relative posix path of a project
                          page, `from:<real DIR>/<page>` for a built site given with --from, or `url:<URL>` for a page on this machine.
  is_loopback_url(url)    the one loopback rule: http or https on localhost, 127.0.0.1 or [::1], and nothing else.

Each family of rows is a function `(rep, measures, ctx)` listed in ROW_CHECKS; a later check (colours, fonts, marks, claims ...) adds its function to
the list and reads the same Ctx. The rows of the first one, `load_rows`, are `page:load:<width>-<scheme>`; `colour_rows` gives `page:colours:<scheme>` (every colour the page
paints is a semantic colour of that theme) and `pair_rows` gives `page:pairs:<scheme>` (every text colour on its ground is a declared pair, or measured against WCAG).
`mark_rows` gives `page:mark-file`, `page:mark-band` and `page:mark-clear-space` (the brand mark on the page is a logo file of the project, the drawing its size calls for, and has its clear space).
`font_rows` gives `page:fonts` (every text is set in a family a `font.*` token names, and the browser drew it in that face) and `display_size_rows` gives `page:display-size`
(the display face is never set under `page.display_min_px`).

`motion_rows` gives `page:motion` (every duration and easing is a motion token), and `claim_rows` gives `page:claims` (every number and status word outside a `data-sample`
is backed by FACTS.md) and `page:samples` (the before-publishing list, also the report's `samples`).

`rule_rows` gives `page:rule:<id>` for each brand rule of qa/rules.json `page.rules` (`rule_request` is what such rules ask of the browser): it fails when it is broken and its `g4` words are in a recorded
"(rule)" line of BRAND-STATE.md Rules (G4), warns when it is broken and not yet tied, and passes when it holds.

`tell_rows` gives `tell:<id>` for each generic tell of skills/brand-creator/references/page-tells.json (an eyebrow over a heading, an arrow glued to a label, a run of middle dots, a stock label on
the hero's second action, a hero with too much text, a mock-up built of styled boxes, three equal tiles in a row): a warning that names the hits, never a failure, until the owner adopts the tell
as a brand rule (kind `tell` in qa/rules.json page.rules, which gives `page:rule:<id>` in its place), and `note:stock-anatomy`. `check_tell_rules` refuses a rule that names no tell.
`tell:stray-box` looks for a box left outside its place once the animations that end have ended (`find_tells` reads `tell_facts.strays`, and `strays_tall` for the window 1300 px high every view is measured in again, and the
view's `animations` fact): a box still shown outside its parent's box or off the screen by `min_outside_px` is a hit; a view whose wait was cut off, a view with an animation still running and an element
that is still animating are NOT verified for it, never a pass.

Standard library plus scripts/lib (_color, _common, qa_rules) only, and, imported when they are judged, scripts/booklib/bookdata.py (the FACTS.md table and the English status words, for the
claims) and scripts/adaptlib/adapt.py (the recorded G4 rule lines, for the brand rules). This folder is outside scripts/lib/, so a change here does not make every pack stale. The
only reads are the project's own files and, with --from, the folder it names (read only: it is copied, never written).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import posixpath
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import qa_rules
from _color import parse_hex, wcag_ratio
from _common import CliError, EXIT_CANNOT, EXIT_USAGE, PartInput, Report, confine, fail, gate_recorded, plugin_root, rel, scratch_dir

REPORT_DIR = "page-check"
SCHEMES = ("light", "dark")
LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")
FROM_MAX_FILES = 5000
FROM_MAX_BYTES = 200 * 1024 * 1024
FROM_SKIPPED = (".git", "node_modules")   # never copied, never counted
TOKENS_FILE = "assets/tokens/tokens.json"
TOKENS_CSS = "assets/tokens/tokens.css"
SHOWN = 3                                 # how many items of a list a row's detail names
NAMED = 6                                 # how many offenders a colour or pair row names
RGB_TOLERANCE = 2                         # two colours are the same colour when no channel (of 255) differs by more. Not what makes a token outside sRGB match: that is
                                          # the colour the browser renders for it (`role_colours` in the measurements), which can be far from tokens.json's hex. This absorbs a hand-typed copy of a
                                          # token (a hex, or an oklch() with fewer digits) a unit or two off; two units is under what the eye tells apart (OKLab distance about 0.005)
ALPHA_TOLERANCE = 0.01                    # two see-through colours are the same when their alphas are this close
SEE_THROUGH = 0.999                       # an alpha under this is see-through
LARGE_PX, LARGE_BOLD_PX, BOLD = 24.0, 18.66, 700   # WCAG "large text": 24 px and up, or 18.66 px (14 pt) and up at weight 700 or more
FLOOR_TEXT, FLOOR_LARGE = 4.5, 3.0        # WCAG contrast an undeclared text pair needs


# ---------------------------------------------------------------- shared helpers

def is_loopback_url(url: str) -> bool:
    """True only for an http or https URL with no user name or password whose host, as written, is localhost, 127.0.0.1 or [::1] (any letter case). The host is
    the text in the URL, not what a parser turns it into: 127.1, 0x7f000001, 2130706433, [0:0:0:0:0:0:0:1] and %6cocalhost are refused although a browser would
    go to this machine. A URL with whitespace, a control character or a backslash is refused outright: parsers disagree on those, and the host the browser would
    go to must be the one read here. Twin of isLoopbackUrl in scripts/lib/_common.mjs (a test pins both to one table of cases)."""
    if not isinstance(url, str) or re.search(r"[\s\x00-\x1f\x7f\\]", url):
        return False
    try:
        parts = urlsplit(url)
        parts.port   # a port that is no number raises here
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and "@" not in parts.netloc and (parts.hostname or "") in LOOPBACK_HOSTS


def report_tool(ident: str) -> str:
    """The report tool name (-> assets/_checks/page-check/<slug>-<hash6>.json) of one target: one report per page, so a run on one page never touches the
    report of another. The slug is the page's file stem (for a URL, the stem of its path's last segment), else `page`; the hash is the first six hex of the
    sha256 of the ident (see the module docstring)."""
    if ident.startswith("url:"):
        segments = [s for s in urlsplit(ident[4:]).path.split("/") if s]
        name = segments[-1] if segments else ""
    else:
        name = ident.removeprefix("from:").rsplit("/", 1)[-1]
    slug = re.sub(r"[^A-Za-z0-9]+", "-", Path(name).stem).strip("-").lower() or "page"
    return f"{REPORT_DIR}/{slug}-{hashlib.sha256(ident.encode()).hexdigest()[:6]}"


def parse_widths(text: str) -> list[int]:
    """--widths 360,390,1440 -> [360, 390, 1440]; anything that is not a whole number from 200 to 4000 is a usage error."""
    items = [t.strip() for t in text.split(",")]
    bad = [t for t in items if not re.fullmatch(r"\d+", t)]
    if bad:
        fail(EXIT_USAGE, f"--widths: {bad[0]!r} is not a whole number from {qa_rules.PAGE_WIDTH_MIN} to {qa_rules.PAGE_WIDTH_MAX}")
    return qa_rules.validate_page_widths([int(t) for t in items], "--widths")


def parse_schemes(text: str) -> list[str]:
    """--schemes light,dark -> ["light", "dark"]; a scheme other than light or dark, or one twice, is a usage error."""
    items = [t.strip() for t in text.split(",")]
    for t in items:
        if t not in SCHEMES:
            fail(EXIT_USAGE, f"--schemes: {t!r} is not a colour scheme (light or dark)")
    if len(set(items)) != len(items):
        fail(EXIT_USAGE, "--schemes: a scheme is listed twice")
    return items


# ---------------------------------------------------------------- the target

@dataclass
class Target:
    kind: str                    # "project" (a page of the project), "from" (a built site anywhere, copied and served from there) or "url" (this machine)
    ident: str                   # what the report name is made from (see report_tool)
    page: str | None = None      # project: the project-relative posix path; from: the path inside the folder; url: None
    from_dir: Path | None = None
    url: str | None = None
    file: Path | None = None     # the page on disk (project, from)

    def describe(self) -> str:
        return {"project": f"project page {self.page}", "from": f"built site {self.from_dir}, page {self.page}", "url": f"page {self.url}"}[self.kind]

    def as_report(self) -> dict:
        return {"kind": self.kind, "page": self.page, "from": str(self.from_dir) if self.from_dir else None, "url": self.url}


def _inside(root: Path, path: Path) -> bool:
    try:
        Path(os.path.realpath(path)).relative_to(Path(os.path.realpath(root)))
        return True
    except ValueError:
        return False


def _survey(folder: Path) -> tuple[int, int]:
    """(files, bytes) a --from copy would hold: .git and node_modules and every symlink are left out. Stops counting once a limit is passed."""
    files = size = 0
    for here, dirs, names in os.walk(folder, followlinks=False):
        dirs[:] = [d for d in dirs if d not in FROM_SKIPPED and not os.path.islink(os.path.join(here, d))]
        for n in names:
            p = os.path.join(here, n)
            if os.path.islink(p):
                continue
            files += 1
            size += os.path.getsize(p)
            if files > FROM_MAX_FILES or size > FROM_MAX_BYTES:
                return files, size
    return files, size


def resolve_target(project: Path, page: str | None, from_dir: str | None, url: str | None) -> Target:
    """The one target of a run. Every refusal here is a usage error (exit 2) and happens before anything is written."""
    if url and (page or from_dir):
        fail(EXIT_USAGE, "two targets: give a page of the project, --from DIR with a page, or --url URL, not several")
    if url:
        if not is_loopback_url(url):
            fail(EXIT_USAGE, f"--url {url}: page-check runs offline and measures only a page on this machine (http or https on localhost, 127.0.0.1 or [::1]); "
                             "for a remote page, build it locally and use --from DIR")
        return Target("url", f"url:{url}", url=url)
    if from_dir:
        if not page:
            fail(EXIT_USAGE, "--from DIR needs the page to check, written relative to DIR: brand-creator page-check --from DIR index.html")
        folder = Path(from_dir).expanduser()
        if not folder.is_dir():
            fail(EXIT_USAGE, f"--from {from_dir}: not a folder")
        folder = Path(os.path.realpath(folder))
        lexical = Path(os.path.normpath(page))
        if lexical.is_absolute():   # an absolute page must lie inside the folder
            try:
                lexical = Path(os.path.realpath(lexical)).relative_to(folder)
            except ValueError:
                fail(EXIT_USAGE, f"page {page} is not inside {folder}: write it relative to --from DIR")
        if ".." in lexical.parts or not (folder / lexical).is_file():
            fail(EXIT_USAGE, f"page not found in {folder}: {page}")
        cur = folder
        for part in lexical.parts:
            cur = cur / part
            if part in FROM_SKIPPED or cur.is_symlink():
                fail(EXIT_USAGE, f"page {page} is behind {part!r}, which --from does not copy (.git, node_modules and symlinks are left out)")
        page_rel = lexical.as_posix()
        files, size = _survey(folder)
        if files > FROM_MAX_FILES or size > FROM_MAX_BYTES:
            fail(EXIT_USAGE, f"--from {folder} holds more than {FROM_MAX_FILES} files or {FROM_MAX_BYTES // (1024 * 1024)} MB (.git, node_modules and symlinks not counted): "
                             "point --from at the built site alone")
        return Target("from", f"from:{folder.as_posix()}/{page_rel}", page=page_rel, from_dir=folder, file=folder / page_rel)
    if not page:
        fail(EXIT_USAGE, "no target: give a page of the project, --from DIR with a page, or --url URL")
    try:
        abs_page = confine(project, page, what="page")
    except CliError:
        fail(EXIT_USAGE, f"page {page} is outside the project {project}: for a built site elsewhere use --from DIR <page>")
    if not abs_page.is_file():
        fail(EXIT_USAGE, f"page not found: {page}")
    page_rel = rel(project, abs_page)
    return Target("project", page_rel, page=page_rel, file=abs_page)


def stage_from_copy(project: Path, target: Target) -> Path:
    """--from: copy the folder into a new run folder <data>/scratch/<project>/page-check/<hash6>/<n>/ and return it; the browser is pointed at the copy.
    The source is only read. `n` is one more than the highest run folder already there."""
    assert target.kind == "from" and target.from_dir
    base = scratch_dir(project, f"{REPORT_DIR}/{report_tool(target.ident).rsplit('-', 1)[1]}")
    taken = [int(d.name) for d in base.iterdir() if d.is_dir() and d.name.isdigit()]
    dst = base / str(max(taken, default=0) + 1)

    def skip(here: str, names: list[str]) -> list[str]:   # a symlink, a pipe or a socket is not copied (a pipe would block the copy)
        return [n for n in names if n in FROM_SKIPPED or os.path.islink(os.path.join(here, n))
                or not (os.path.isdir(os.path.join(here, n)) or os.path.isfile(os.path.join(here, n)))]

    shutil.copytree(target.from_dir, dst, symlinks=False, ignore=skip)
    return dst


# ---------------------------------------------------------------- what a run knows

@dataclass
class Ctx:
    """Everything a family of rows reads besides the measures."""
    project: Path
    target: Target
    widths: list[int]
    schemes: list[str]
    rules: dict                   # qa/rules.json with the proposals filled in (qa_rules.load)
    tokens: dict                  # assets/tokens/tokens.json
    modern: dict = field(default_factory=dict)   # assets/tokens/tokens.css: custom property -> the oklch(), oklab() or color() value tokens.css serves for a primitive
    extra: dict = field(default_factory=dict)   # what a row family adds to the report at its top level


def load_tokens(project: Path) -> dict:
    f = project / TOKENS_FILE
    if not f.is_file():
        fail(EXIT_CANNOT, f"{TOKENS_FILE} is missing: run `brand-creator tokens` first (page-check judges a page against the built tokens)")
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        fail(EXIT_CANNOT, f"{TOKENS_FILE} cannot be read ({e}): run `brand-creator tokens` again")
    if not isinstance(doc, dict):
        fail(EXIT_CANNOT, f"{TOKENS_FILE} is not a tokens file: run `brand-creator tokens` again")
    return doc


MODERN_VALUE = re.compile(r"(--[\w-]+)\s*:\s*((?:oklch|oklab|color)\([^;{}]*\))\s*;")


def load_modern(project: Path) -> dict[str, str]:
    """The modern colour value tokens.css serves for each primitive (inside its `@supports (color: oklch(0 0 0))` block), by custom property: {"--color-teal":
    "oklch(0.52 0.12 185)"}. A browser that has the syntax paints this value and clips it to sRGB channel by channel, while tokens.json holds the hex that the token
    build gamut-mapped (chroma reduction); for a token outside sRGB the two differ. {} for tokens that are all hex. Exit 3 when tokens.css is missing or unreadable."""
    f = project / TOKENS_CSS
    try:
        css = f.read_text(encoding="utf-8")
    except OSError as e:
        fail(EXIT_CANNOT, f"{TOKENS_CSS} cannot be read ({e}): run `brand-creator tokens` first (page-check compares the colours with what the browser renders for it)")
    return {m.group(1): " ".join(m.group(2).split()) for m in MODERN_VALUE.finditer(css)}


def base_inputs(project: Path, target: Target) -> list[Path | PartInput]:
    """The files every page check stands on: the built tokens (json and css), the rules, the facts and, of the state of the project, the G4 rules (BRAND-STATE.md "g4-rules": the G4 record
    and the recorded "(rule)" lines, the only two things a page check reads from it; recording G5 or G6 or setting the phase does not make the report stale), and the page (a project target)."""
    files = [project / TOKENS_FILE, project / TOKENS_CSS, project / qa_rules.RULES_FILE, project / "FACTS.md", PartInput(project / "BRAND-STATE.md", "g4-rules")]
    if target.kind == "project" and target.file:
        files.append(target.file)
    return files


def served_project_files(project: Path, measures: dict) -> list[Path]:
    """Every project file the browser was served in any view (a stylesheet, tokens.css, a script, an image, a font), so a change to one makes the report stale."""
    root = Path(os.path.realpath(project))
    out = {}
    for v in measures.get("views", []):
        for s in v.get("served", []) if isinstance(v, dict) else []:
            p = Path(s)
            if p.is_file() and _inside(root, p):
                out[os.path.realpath(p)] = p
    return sorted(out.values())


# ---------------------------------------------------------------- rows

def _names(items: list, n: int = SHOWN) -> str:
    shown = [str(i) for i in items[:n]]
    return "; ".join(shown) + (f"; and {len(items) - n} more" if len(items) > n else "")


def load_rows(rep: Report, measures: dict, ctx: Ctx) -> None:
    """page:load:<width>-<scheme>: the page loaded in that view without a page or console error, a failed request to its own files or (a project page or a
    built site) a request to another origin. A page on this machine (--url) may ask other origins; they are aborted, and that is a warning."""
    views = {(v.get("width"), v.get("scheme")): v for v in measures.get("views", []) if isinstance(v, dict)}
    if not views:
        rep.add("page:load", "skipped", "the page was rendered", detail="not verified: no view was measured")
        return
    for width in ctx.widths:
        for scheme in ctx.schemes:
            rid, label, v = f"page:load:{width}-{scheme}", f"{width}px {scheme}", views.get((width, scheme))
            if v is None or v.get("error"):
                rep.add(rid, "fail", label, detail=f"could not render: {(v or {}).get('error') or 'the view is not in the measurements'}")
                continue
            errors, failed, other = v.get("errors", []), v.get("failed_local", []), v.get("non_local", [])
            problems = []
            if errors:
                problems.append(f"{len(errors)} page or console error(s): {_names(errors, 2)}")
            if failed:
                problems.append(f"{len(failed)} failed request(s) to the page's own files: {_names(failed)}")
            if other:
                problems.append(f"{len(other)} request(s) to another origin, aborted ({_names(other)})" if ctx.target.kind == "url"
                                else f"{len(other)} request(s) to another origin: {_names(other)} (a page checked offline asks nobody)")
            extra = {"console_errors": errors, "failed_local_requests": failed, "non_local_requests": other,
                     "viewport": v.get("viewport"), "height": v.get("height"), "lang": v.get("lang")}
            if errors or failed or (other and ctx.target.kind != "url"):
                rep.add(rid, "fail", label, detail="; ".join(problems), **extra)
            elif other:
                rep.add(rid, "warn", label, detail="aborted: page-check runs offline: " + problems[0], **extra)
            else:
                vp = v.get("viewport") or {}
                rep.add(rid, "pass", label, detail=f"loaded at {vp.get('width', width)}x{vp.get('height', '?')}, page height {v.get('height', '?')} px, "
                                                  f"{len(v.get('resources', {}))} image file(s), no page or console error, no failed or outside request", **extra)


# ---------------------------------------------------------------- colours and pairs

def oklab(rgb) -> tuple[float, float, float]:
    """sRGB (0 to 255) to OKLab (Ottosson's matrices): white is (1, 0, 0), black (0, 0, 0)."""
    lin = [((v / 255.0) / 12.92 if v / 255.0 <= 0.04045 else (((v / 255.0) + 0.055) / 1.055) ** 2.4) for v in rgb]
    r, g, b = lin
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def oklab_distance(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(oklab(a), oklab(b))) ** 0.5


def same_rgb(a, b) -> bool:
    return all(abs(x - y) <= RGB_TOLERANCE for x, y in zip(a, b))


def composite(fg, alpha: float, ground) -> tuple[int, int, int]:
    """`fg` painted at `alpha` over `ground`, both (r, g, b)."""
    return tuple(round(f * alpha + g * (1 - alpha)) for f, g in zip(fg, ground))


@dataclass(frozen=True)
class Role:
    name: str
    rgb: tuple[int, int, int]          # tokens.json hex: what a page that uses the hex fallback paints
    alpha: float
    rendered: tuple[int, int, int] | None = None   # what the browser paints for the role's modern value (oklch() ...), when that is not the hex: a token outside sRGB is clipped, not gamut-mapped

    @property
    def shades(self) -> list[tuple[int, int, int]]:
        """Every colour that is this role on a page: the hex of tokens.json, and the colour the browser renders for the role's modern value."""
        return [self.rgb] + ([self.rendered] if self.rendered else [])

    def is_colour(self, rgb) -> bool:
        return any(same_rgb(rgb, c) for c in self.shades)

    def distance(self, rgb) -> float:
        return min(oklab_distance(rgb, c) for c in self.shades)


def rendered_colours(measures: dict, scheme: str) -> dict[str, str]:
    """The `role_colours` the browser measured for one scheme: the modern css value of a primitive -> the #rrggbb it paints (a value it could not read is left out)."""
    out: dict[str, str] = {}
    for v in scheme_views(measures, scheme, "role_colours"):
        out.update({css: hex_ for css, hex_ in v["role_colours"].items() if isinstance(hex_, str)})
    return out


def roles_of(tokens: dict, scheme: str, modern: dict | None = None, rendered: dict | None = None) -> list[Role]:
    """The semantic colours of one theme from tokens.json `modes.<scheme>`; [] when the file holds none. A role that points at a primitive tokens.css serves in a
    modern form (`modern`: custom property -> css value) also carries the colour the browser rendered for that value (`rendered`: css value -> #rrggbb)."""
    out = []
    for name, v in sorted(((tokens.get("modes") or {}).get(scheme) or {}).items()):
        try:
            rgb = parse_hex(v["hex"])
            css = (modern or {}).get("--" + str(v.get("ref") or "").replace(".", "-"))
            shown = parse_hex(rendered[css]) if css and css in (rendered or {}) else None
            out.append(Role(name, rgb, float(v.get("alpha", 1)), shown if shown and shown != rgb else None))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def declared_pairs(tokens: dict, scheme: str, roles: list[Role] | None = None) -> list[tuple[str, str, list, list]]:
    """tokens.json `pairs` in one theme: (fg name, bg name, fg colours, bg colours). A pair is a text colour on a ground the brand has declared; the direction counts.
    A colour is the hex of the pair and, when `roles` carry one, the colour the browser renders for the role the pair names."""
    by_name = {r.name: r for r in roles or []}
    out = []
    for p in tokens.get("pairs") or []:
        m = ((p.get("modes") or {}).get(scheme) or {}) if isinstance(p, dict) else {}
        try:
            fg, bg = str(p.get("fg")), str(p.get("bg"))
            out.append((fg, bg, [parse_hex(m["fg_hex"])] + ([by_name[fg].rendered] if by_name.get(fg) and by_name[fg].rendered else []),
                        [parse_hex(m["bg_hex"])] + ([by_name[bg].rendered] if by_name.get(bg) and by_name[bg].rendered else [])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def scheme_views(measures: dict, scheme: str, key: str) -> list[dict]:
    """The views of one colour scheme that were rendered and hold the facts `key`, in the order they were measured."""
    return [v for v in measures.get("views", []) if isinstance(v, dict) and v.get("scheme") == scheme and not v.get("error") and key in v]


def _shown(hex_: str, alpha: float = 1.0) -> str:
    return hex_ if alpha >= SEE_THROUGH else f"{hex_} at alpha {alpha:g}"


def colour_rows(rep: Report, measures: dict, ctx: Ctx) -> None:
    """page:colours:<scheme>: every colour the page paints in that theme (text, backgrounds, borders, outlines, text decoration lines, SVG fill and stroke) is the
    colour of a semantic role of the theme in tokens.json: an opaque colour is the hex of an opaque role, a see-through one a see-through role (same colour and
    alpha). A role is two colours: the hex of tokens.json (what a page that uses the hex fallback paints) and the colour this browser renders for the role's modern
    value in tokens.css (`role_colours`; for a token outside sRGB the browser clips channel by channel, so it is not the gamut-mapped hex); a page colour that is either
    is the role. Up to six offenders are named: where, which property, the colour, the nearest role and its OKLab distance, and the first width it was seen at. Colours
    differing by up to two units per channel (RGB_TOLERANCE) are the same: a hand-typed copy of a token, not a token outside sRGB."""
    for scheme in ctx.schemes:
        rid, label = f"page:colours:{scheme}", f"{scheme} theme colours"
        views, roles = scheme_views(measures, scheme, "colours"), roles_of(ctx.tokens, scheme, ctx.modern, rendered_colours(measures, scheme))
        if not roles:
            rep.add(rid, "skipped", label, detail=f"not verified: {TOKENS_FILE} holds no semantic colours for the {scheme} theme; run `brand-creator tokens` again")
            continue
        if not views:
            rep.add(rid, "skipped", label, detail=f"not verified: no {scheme} view was measured (see the page:load rows)")
            continue
        offenders: dict[tuple, dict] = {}
        distinct, unreadable = set(), set()
        for v in views:
            unreadable.update(v.get("colours_unreadable", []))
            for c in v["colours"]:
                rgb, alpha = parse_hex(c["hex"]), float(c["alpha"])
                distinct.add((c["hex"], alpha))
                see_through = alpha < SEE_THROUGH
                pool = [r for r in roles if (r.alpha < SEE_THROUGH) == see_through]
                if any(r.is_colour(rgb) and (not see_through or abs(alpha - r.alpha) <= ALPHA_TOLERANCE) for r in pool):
                    continue
                key = (c["sel"], c["prop"], c["hex"], alpha)
                if key in offenders:
                    continue
                near = min(pool, key=lambda r: r.distance(rgb)) if pool else None
                nearest = min(near.shades, key=lambda x: oklab_distance(rgb, x)) if near else None   # the hex, or the colour the browser renders, whichever is closer
                offenders[key] = {"selector": c["sel"], "property": c["prop"], "colour": c["hex"], "alpha": alpha, "elements": c.get("count", 1), "also": c.get("also", []),
                                  "width": v.get("width"), "nearest_role": near.name if near else None, "nearest_hex": "#%02x%02x%02x" % nearest if near else None,
                                  "distance": round(oklab_distance(rgb, nearest), 3) if near else None, "see_through": see_through}
        notes = [f"NOT verified: {len(unreadable)} colour(s) the browser gave in a form that could not be read ({_names(sorted(unreadable), 2)})"] if unreadable else []
        if offenders:
            items = []
            for o in offenders.values():
                where = f"{o['selector']} {o['property']} {_shown(o['colour'], o['alpha'])}" + (f" ({o['elements']} elements)" if o["elements"] > 1 else "")
                if o["nearest_role"]:
                    near = f"nearest {'see-through ' if o['see_through'] else ''}role {o['nearest_role']} {o['nearest_hex']}, OKLab distance {o['distance']:.3f}"
                else:
                    near = "the theme has no see-through colour" if o["see_through"] else "the theme has no opaque colour"
                items.append(f"{where}: {near}; first seen at {o['width']} px")
            rep.add(rid, "fail", label, detail=f"{len(offenders)} colour(s) are not a semantic colour of the {scheme} theme: {_names(items, NAMED)}"
                    + ("".join("; " + n for n in notes)), offenders=list(offenders.values()), colours_seen=len(distinct))
        elif notes:
            rep.add(rid, "warn", label, detail="; ".join(notes), colours_seen=len(distinct))
        else:
            rep.add(rid, "pass", label, detail=f"{len(distinct)} distinct colour(s) painted, each a semantic colour of the {scheme} theme", colours_seen=len(distinct))


def _large(size_px: float, weight: int) -> bool:
    return size_px >= LARGE_PX or (size_px >= LARGE_BOLD_PX and weight >= BOLD)


def pair_rows(rep: Report, measures: dict, ctx: Ctx) -> None:
    """page:pairs:<scheme>: every text in that theme, its colour on what it sits on. A text whose colour and ground are a declared pair of tokens.json (the
    direction counts) passes; an undeclared pair under the WCAG floor (4.5:1, or 3:1 for 24 px and up and for 18.66 px and up at weight 700 or more) fails, one
    above it warns ("declare them in pairs"); a text over an image (a gradient too), painted by its own background or by an SVG paint server is "NOT verified". A
    declared pair is matched by its hex and by the colour the browser renders for each of its two roles (a token outside sRGB is clipped by the browser, not
    gamut-mapped as the hex was). A see-through text colour, or text in a faded element, is measured as painted (composited over its ground), so it is never a declared pair."""
    for scheme in ctx.schemes:
        rid, label = f"page:pairs:{scheme}", f"{scheme} theme text pairs"
        views = scheme_views(measures, scheme, "texts")
        if not views:
            rep.add(rid, "skipped", label, detail=f"not verified: no {scheme} view was measured (see the page:load rows)")
            continue
        declared = declared_pairs(ctx.tokens, scheme, roles_of(ctx.tokens, scheme, ctx.modern, rendered_colours(measures, scheme)))
        seen: set[tuple] = set()
        failing: dict[tuple, dict] = {}
        undeclared: dict[tuple, dict] = {}
        over_image: dict[str, dict] = {}
        total = declared_n = 0
        truncated = []
        for v in views:
            if v.get("texts_total"):
                truncated.append(f"{v['texts_total']} texts at {v.get('width')} px, {len(v['texts'])} measured")
            for t in v["texts"]:
                ident = (t["sel"], t.get("fg"), t.get("fg_alpha"), t.get("opacity"), t.get("ground"), t.get("ground_kind"), t.get("font_size_px"), t.get("font_weight"), t.get("fill_clear"),
                         t.get("fill_server"))
                if ident in seen:
                    continue
                seen.add(ident)
                total += 1
                at = {"selector": t["sel"], "text": t["text"][:40], "width": v.get("width"), "font_size_px": t.get("font_size_px"), "font_weight": t.get("font_weight")}
                if t.get("fill_clear") or t.get("ground_kind") == "image" or not t.get("ground") or not t.get("fg"):
                    why = ("painted by its own background (clipped to the text)" if t.get("fill_clear") else
                           "painted by a gradient or pattern (an SVG paint server)" if t.get("fill_server") else "over an image")
                    over_image.setdefault(t["sel"], {**at, "why": why})
                    continue
                fg, ground = parse_hex(t["fg"]), parse_hex(t["ground"])
                alpha = float(t.get("fg_alpha", 1)) * float(t.get("opacity", 1))
                if alpha >= SEE_THROUGH and any(any(same_rgb(fg, f) for f in fs) and any(same_rgb(ground, b) for b in bs) for _, _, fs, bs in declared):
                    declared_n += 1
                    continue
                painted = composite(fg, alpha, ground) if alpha < SEE_THROUGH else fg
                ratio = wcag_ratio(painted, ground)
                large = _large(float(t.get("font_size_px") or 0), int(t.get("font_weight") or 400))
                floor = FLOOR_LARGE if large else FLOOR_TEXT
                key = (t["fg"], round(alpha, 3), t["ground"], large)
                bucket = failing if ratio < floor else undeclared
                if key not in bucket:
                    bucket[key] = {**at, "fg": t["fg"], "ground": t["ground"], "painted": "#%02x%02x%02x" % painted, "ratio": round(ratio, 2), "floor": floor, "large": large,
                                   "texts": 0, "also": []}
                elif len(bucket[key]["also"]) < NAMED:
                    bucket[key]["also"].append(t["sel"])
                bucket[key]["texts"] += 1
        parts = []
        if failing:
            parts.append(f"{len(failing)} text colour pair(s) under the WCAG floor and not declared in pairs: " + _names([
                f"{o['selector']} \"{o['text']}\" {o['fg']} on {o['ground']}"
                + (f" (painted {o['painted']})" if o["painted"] != o["fg"] else "") + f" is {o['ratio']}:1, needs {o['floor']:g}:1 for {'large' if o['large'] else 'normal'} text"
                + (f", {o['texts']} texts" if o["texts"] > 1 else "") + f", first seen at {o['width']} px" for o in failing.values()], NAMED))
        if undeclared:
            parts.append(f"{len(undeclared)} undeclared text pair(s) pass the floor; declare them in pairs: " + _names([
                f"{o['fg']} on {o['ground']} {o['ratio']}:1 ({o['selector']})" for o in undeclared.values()], NAMED))
        if over_image:
            parts.append(f"NOT verified: text over an image ({len(over_image)}): " + _names([f"{o['selector']} ({o['why']})" for o in over_image.values()], NAMED))
        if truncated:
            parts.append("NOT verified beyond the first texts of a view: " + _names(truncated, 2))
        extra = {"texts_checked": total, "declared": declared_n, "failing": list(failing.values())[:100], "undeclared": list(undeclared.values())[:100],
                 "over_image": list(over_image.values())[:100]}
        if failing:
            rep.add(rid, "fail", label, detail="; ".join(parts), **extra)
        elif parts:
            rep.add(rid, "warn", label, detail="; ".join(parts), **extra)
        else:
            rep.add(rid, "pass", label, detail=f"{total} text colour(s) checked, each a declared pair of the {scheme} theme", **extra)


# ---------------------------------------------------------------- motion

DURATION_TOLERANCE_MS = 0.001             # a duration equals a token's when they differ by less than this
CURVE_TOLERANCE = 1e-5                    # a cubic-bezier equals a token's when no number differs by more (a browser prints six digits)
# the keywords as CSS defines them; a keyword counts as a curve token only when a token holds the same four numbers
NAMED_CURVES = {"linear": (0.0, 0.0, 1.0, 1.0), "ease": (0.25, 0.1, 0.25, 1.0), "ease-in": (0.42, 0.0, 1.0, 1.0), "ease-out": (0.0, 0.0, 0.58, 1.0),
                "ease-in-out": (0.42, 0.0, 0.58, 1.0)}
CUBIC_BEZIER = re.compile(r"^cubic-bezier\(([^()]*)\)$")


def bezier_of(easing) -> tuple[float, float, float, float] | None:
    """An easing as its four cubic-bezier numbers: a keyword as CSS defines it (linear is 0, 0, 1, 1), or `cubic-bezier(a, b, c, d)`; None for anything else (steps(),
    step-start, linear(...)), which no curve token can equal."""
    e = str(easing or "").strip().lower()
    if e in NAMED_CURVES:
        return NAMED_CURVES[e]
    m = CUBIC_BEZIER.match(e)
    if not m:
        return None
    try:
        nums = [float(x) for x in m.group(1).split(",")]
    except ValueError:
        return None
    return tuple(nums) if len(nums) == 4 and all(math.isfinite(x) for x in nums) else None   # type: ignore[return-value]


def motion_tokens(tokens: dict) -> tuple[list[tuple[str, float]], list[tuple[str, tuple]]]:
    """The motion tokens of tokens.json: ([(name, ms)], [(name, (x1, y1, x2, y2))]). An entry that is not a number, or not four numbers, is not a token."""
    m = tokens.get("motion") if isinstance(tokens.get("motion"), dict) else {}
    numeric = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
    durations = [(str(k), float(v)) for k, v in (m.get("durations_ms") or {}).items() if numeric(v)]
    curves = [(str(k), tuple(float(x) for x in v)) for k, v in (m.get("curves") or {}).items() if isinstance(v, list) and len(v) == 4 and all(numeric(x) for x in v)]
    return durations, curves


def _who(d: dict) -> str:
    name = d.get("name") or ""
    kind = {"transition": "transition of" if name else "transition", "animation": "animation", "script": "script animation"}.get(d.get("source"), "motion")
    return f"{kind}{' ' + name if name and d.get('source') != 'script' else ''} on {d.get('selector')}"


def _ms(v: float) -> str:
    return f"{v:g} ms"


def motion_rows(rep: Report, measures: dict, ctx: Ctx) -> None:
    """page:motion: every duration and easing the page declares or runs is a motion token of tokens.json (`motion.durations_ms`, `motion.curves`). The facts are the
    computed transition and animation properties of every element at rest, what the style sheets declare for a state (:hover, :focus, :active ... : read from the rule, so a
    hover state counts without being hovered; a rule that sets only a duration or only an easing is judged on that part, `unset` names the other) and the Web Animations
    running at rest. A duration fails unless it equals a duration token; an easing fails unless it is a cubic-bezier equal to a curve token (the keywords `ease`, `ease-in`,
    `ease-out`, `ease-in-out` and `linear` count only when a token holds their curve; steps() and linear() never do). A page that moves while the brand has no motion tokens
    at all fails and says so. A scroll-driven animation has no duration, a style sheet the browser would not let the walk read hides its states, and an SVG SMIL animation is
    not read: all three are NOT verified and only warn."""
    rid, label = "page:motion", "motion uses the brand's motion tokens"
    views = [v for v in measures.get("views", []) if isinstance(v, dict) and not v.get("error") and "motion_decls" in v]
    if not views:
        rep.add(rid, "skipped", label, detail="not verified: no view was measured (see the page:load rows)")
        return
    durations, curves = motion_tokens(ctx.tokens)
    merged: dict[tuple, dict] = {}
    smil = unread = 0
    truncated = []
    for v in views:
        smil = max(smil, int(v.get("motion_smil") or 0))
        unread = max(unread, int(v.get("motion_unread") or 0))
        if v.get("motion_total"):
            truncated.append(f"{v['motion_total']} distinct declarations at {v.get('width')} px, {len(v['motion_decls'])} measured")
        for d in v["motion_decls"]:
            unset = [x for x in d.get("unset") or [] if x in ("duration", "easing")]   # the parts of a state rule that it leaves to the rule at rest
            key = (d.get("source"), d.get("name"), d.get("duration_ms"), d.get("easing"), tuple(unset))
            if key not in merged:
                merged[key] = {"selector": d.get("sel"), "source": d.get("source"), "name": d.get("name"), "duration_ms": d.get("duration_ms"), "easing": d.get("easing"),
                               "via": d.get("via"), "unset": unset, "elements": d.get("count", 1), "also": d.get("also", []), "width": v.get("width"), "scheme": v.get("scheme")}
    found = list(merged.values())
    notes = []
    if smil:
        notes.append(f"NOT verified: {smil} SVG SMIL animation element(s) (animate, animateTransform, animateMotion) are not read")
    if unread:
        notes.append(f"NOT verified: {unread} stylesheet(s) could not be read, so a hover, focus or other state it declares is not seen")
    if truncated:
        notes.append("NOT verified beyond the first declarations of a view: " + _names(truncated, 2))
    scroll = [d for d in found if d["duration_ms"] is None and "duration" not in d["unset"]]
    if scroll:
        notes.append(f"NOT verified: {len(scroll)} animation(s) run on a scroll or view timeline and have no duration ({_names([_who(d) for d in scroll], 2)})")
    extra = {"declarations": found[:100], "durations_checked": sum(1 for d in found if d["duration_ms"] is not None and "duration" not in d["unset"])}
    if not found:
        detail = "no transition or animation is declared or running" + ("; " + "; ".join(notes) if notes else "")
        rep.add(rid, "warn" if notes else "pass", label, detail=detail, **extra)
        return
    if not durations and not curves:
        rep.add(rid, "fail", label, detail=f"the page moves ({len(found)} transition or animation declaration(s): {_names([_who(d) for d in found], NAMED)}) while the brand has no motion tokens: "
                                           "define the durations and curves in the tokens first, then use them" + "".join("; " + n for n in notes), **extra)
        return
    duration_list = ", ".join(f"{k} {_ms(ms)}" for k, ms in durations) or "the built tokens hold none"
    curve_list = ", ".join(f"{k} cubic-bezier({', '.join(f'{x:g}' for x in c)})" for k, c in curves) or "the built tokens hold none"
    bad, used = [], []
    for d in found:
        problems = []
        ms = d["duration_ms"]
        if ms is not None and "duration" not in d["unset"]:
            token = next(((k, v) for k, v in durations if abs(v - ms) < DURATION_TOLERANCE_MS), None)
            if token:
                used.append(f"{token[0]} ({_ms(token[1])})")
            else:
                problems.append(f"lasts {_ms(ms)}, which is no motion duration token ({duration_list})")
        if "easing" not in d["unset"]:
            b = bezier_of(d["easing"])
            curve = next(((k, c) for k, c in curves if b and all(abs(x - y) < CURVE_TOLERANCE for x, y in zip(b, c))), None) if b else None
            if curve:
                used.append(f"{curve[0]} ({d['easing']})")
            else:
                problems.append(f"eases with {d['easing']}, which is no curve token ({curve_list})")
        if problems:
            bad.append({**d, "problems": problems})
    used = sorted(set(used))
    extra["offenders"], extra["used"] = bad[:100], used
    if bad:
        items = [f"{_who(o)} {' and '.join(o['problems'])}" + (f" ({o['elements']} {'rules' if o['via'] == 'state' else 'elements'})" if o["elements"] > 1 else "") + f", first seen at {o['width']} px" for o in bad]
        rep.add(rid, "fail", label, detail=f"{len(bad)} of {len(found)} transition or animation declaration(s) are not made of motion tokens: {_names(items, NAMED)}"
                + "".join("; " + n for n in notes), **extra)
    else:
        detail = f"{len(found)} transition or animation declaration(s), each duration and easing a motion token" + (f" (used: {_names(used, 4)})" if used else "")
        rep.add(rid, "warn" if notes else "pass", label, detail=detail + "".join("; " + n for n in notes), **extra)


# ---------------------------------------------------------------- claims and samples

# Status words that need a FACTS.md value that says so. English: book-lint's list (scripts/booklib/bookdata.py, LINT_DEFAULTS["status_words"]), one definition. Polish: here.
STATUS_WORDS_PL = ("wkrótce", "dostępne", "dostępny", "dostępna", "w przygotowaniu", "w budowie", "premiera", "przedsprzedaż", "nowość")
CLAIM_LANGUAGES = ("en", "pl")            # the languages whose status words are listed; any other page language is "NOT verified"
CURRENCY_CODES = r"pln|eur|usd|gbp|chf"          # a code before the number (PLN 5) or after it (5 PLN)
UNITS_SPACED = r"%|‰|€|\$|£|zł|" + CURRENCY_CODES + r"|mln|mld|tys\.?|km|kg|mm|cm|ml|min|ms|px|gb|mb|kb|tb"   # may follow a number after a space
UNITS_GLUED = r"k|m|g|l|h|s|x|×"          # single letters: a unit only when written right against the number (4K, 5m), never "3 s..."
NUMBER = re.compile(r"(?<![\w.,])(?P<pre>(?:[€$£]|(?:" + CURRENCY_CODES + r")(?![a-z]))\s?)?(?P<num>(?:\d{1,3}(?:[   ]\d{3})+|\d+)(?:[.,]\d+)*)(?P<post>\s?(?:" + UNITS_SPACED + ")|(?:" + UNITS_GLUED + "))?(?!\\w)", re.I)
CONTEXT_CHARS = 30                        # characters of text kept each side of a claim in a row's detail
# A dotted date is its numbers, the same as the ISO form: dd.mm.yyyy (the year 19xx or 20xx, the day and month with one digit or two), or dd.mm with two digits each (30.10, 05.11), which is also a
# decimal (30.1) and so is read both ways. dd.mm with fewer digits and no year (12.5, 2.10, 10.1) stays a decimal.
DOTTED_DATE = re.compile(r"(?P<d>0?[1-9]|[12]\d|3[01])\.(?P<m>0?[1-9]|1[0-2])(?:\.(?P<y>(?:19|20)\d{2}))?")
YEAR = re.compile(r"(?:19|20)\d{2}")
# The text just before a year that makes it a copyright year: a (c) sign or the word, then the year, or a range of years ("(c) 2024-2026": the second year follows "2024-").
COPYRIGHT_BEFORE = re.compile(r"(?:©|\(c\)|\bcopyright\b)\s*(?:(?:©|\(c\))\s*)?(?:(?:19|20)\d{2}\s*[-–—]\s*)?$", re.I)
COPYRIGHT_LOOKBACK = 40                   # characters before a year that are looked at for the sign
DATE_YEAR_R = re.compile(r"\.((?:19|20)\d{2})r(?!\w)")   # the Polish year written glued to the date: 15.11.2026r.
STATUS_CODE = re.compile(r"[45]\d\d")      # a 4xx or 5xx status code of an error page
# The words that say a title or an h1 is about an error, per page language: a code in such a text counts as the page's status code only when the same text holds one of them.
ERROR_WORDS = {"en": ("error", "not found", "forbidden", "unauthorized", "unavailable", "gone", "bad request", "server error"),
               "pl": ("błąd", "nie znaleziono", "nie istnieje", "brak dostępu", "odmowa dostępu", "niedostępna", "niedostępny")}
ERROR_WORD_PATTERNS = {lang: re.compile(r"(?<!\w)(?:" + "|".join(r"\s+".join(re.escape(w) for w in phrase.split()) for phrase in phrases) + r")(?!\w)", re.I) for lang, phrases in ERROR_WORDS.items()}   # whole words, any letter case, any white space between the words of a phrase

# A date written with a month name is one date, not numbers, in the languages whose month names are listed (the page language decides: any other, or none, keeps the numbers as they are).
# Polish: "21 października 2026", "21 października", and a month with a year, in the nominative, genitive or locative ("Październik 2026", "października 2026", "w październiku 2026"), in any
# letter case. English: "October 21, 2026", "October 21st", "21 October 2026", "21 October", "October 2026", with a capital letter or in capitals (a lower-case "may" or "march" is a word).
# A day that a number runs past is no day: "March 15% of users" is a percent, "May 3.5 kg" and "October 12,5" are decimals. Only a comma and a four-digit year may follow a day that way:
# "October 21,2026" (with or without a space after the comma) is the full date. After a day the nominative or the locative of a Polish month is no date: "21 październik" is the number 21.
MONTH_NAMES = {"pl": (("stycznia", "styczeń", "styczniu"), ("lutego", "luty", "lutym"), ("marca", "marzec", "marcu"), ("kwietnia", "kwiecień", "kwietniu"), ("maja", "maj", "maju"),
                      ("czerwca", "czerwiec", "czerwcu"), ("lipca", "lipiec", "lipcu"), ("sierpnia", "sierpień", "sierpniu"), ("września", "wrzesień", "wrześniu"),
                      ("października", "październik", "październiku"), ("listopada", "listopad", "listopadzie"), ("grudnia", "grudzień", "grudniu")),   # genitive, nominative, locative
               "en": tuple((n,) for n in ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"))}
ANY_LANGUAGE = "*"                        # numbers_in(lang=...) for a text of no known language (a FACTS.md value): the month names of every listed language
_DAY = r"(?:0?[1-9]|[12]\d|3[01])"
_YEAR = r"(?:(?:19|20)\d{2})(?=r(?!\w)|(?!\w))"      # a year may be followed by the Polish r. glued to it: 2026r.
_DAY_ENDS = r"(?!\s?[%‰])(?:(?![.,]\d)|(?=,\s*" + _YEAR + r"))"   # after a day: no percent sign, and no digit glued by . or , unless a comma and a year (October 21,2026)


def _month_alternatives(lang: str, genitive_only: bool = False) -> tuple[str, dict[str, int]]:
    """The regular expression that matches any month name of `lang` (a Polish genitive only with `genitive_only`), and the table from a lower-cased name to the month number."""
    names, numbers = [], {}
    for number, forms in enumerate(MONTH_NAMES[lang], 1):
        for form in (forms[:1] if genitive_only else forms):
            names += [form, form.upper()] if lang == "en" else [form]
            numbers[form.lower()] = number
    return "|".join(re.escape(n) for n in sorted(set(names), key=len, reverse=True)), numbers


def _month_date_patterns() -> dict[str, list[re.Pattern]]:
    """The patterns of a date with a month name, per language: named groups `m` (month name), `d` (day, where the form has one) and `y` (year, where it may have one)."""
    out: dict[str, list[re.Pattern]] = {}
    flags = {"pl": re.I, "en": 0}
    for lang in MONTH_NAMES:
        any_month, _ = _month_alternatives(lang)
        gen_month, _ = _month_alternatives(lang, genitive_only=True)
        before_day = r"(?<![\w.,])"
        if lang == "pl":
            forms = [rf"{before_day}(?P<d>{_DAY})\s+(?P<m>{gen_month})(?!\w)(?:\s+(?P<y>{_YEAR}))?",          # 21 października 2026, 21 października
                     rf"(?<!\w)(?P<m>{any_month})\s+(?P<y>{_YEAR})"]                                         # Październik 2026, października 2026, w październiku 2026
        else:
            forms = [rf"(?<!\w)(?P<m>{any_month})\s+(?P<d>{_DAY})(?:st|nd|rd|th)?(?!\w){_DAY_ENDS}(?:(?:,\s*|\s+)(?P<y>{_YEAR}))?",   # October 21, 2026, October 21,2026, October 21st, October 21
                     rf"{before_day}(?P<d>{_DAY})(?:st|nd|rd|th)?\s+(?P<m>{any_month})(?!\w)(?:,?\s+(?P<y>{_YEAR}))?",  # 21 October 2026, 21st October, 21 October
                     rf"(?<!\w)(?P<m>{any_month})\s+(?P<y>{_YEAR})"]                                         # October 2026
        out[lang] = [re.compile(f, flags[lang]) for f in forms]
    return out


MONTH_DATE_PATTERNS = _month_date_patterns()
MONTH_NUMBERS = {lang: _month_alternatives(lang)[1] for lang in MONTH_NAMES}


def month_dates(text: str, lang: str) -> list[tuple[int, int, list[str]]]:
    """The dates written with a month name in `text`, in the order they stand: [(start, end, parts)], `parts` the day (as written), the month number and the year, those that are
    written. `lang` is a primary language code ("pl", "en"), ANY_LANGUAGE for the names of all of them, and any other gives []. Where two readings overlap the one that starts first
    wins, then the longer: "21 October 2026" is one date, not "21 October" and "October 2026"."""
    langs = list(MONTH_NAMES) if lang == ANY_LANGUAGE else [lang] if lang in MONTH_NAMES else []
    found = []
    for code in langs:
        for rx in MONTH_DATE_PATTERNS[code]:
            for m in rx.finditer(text):
                parts = [g for g in (m.group("d") if "d" in rx.groupindex else None, str(MONTH_NUMBERS[code][m.group("m").lower()]), m.group("y")) if g]
                found.append((m.start(), m.end(), parts))
    found.sort(key=lambda f: (f[0], -f[1]))
    out, end = [], 0
    for start, stop, parts in found:
        if start >= end:
            out.append((start, stop, parts))
            end = stop
    return out


def canonical_number(raw: str) -> str:
    """A number as one comparable string: white space (a no-break space too) dropped, `,` read as the decimal point, `1.200` and `1,200` as thousands (not after a
    leading 0), trailing zeros of a decimal dropped. 12,5 and 12.50 are 12.5; 1 200, 1.200 and 1,200 are 1200. With both signs the last one is the decimal point and the
    other marks thousands: 100.000,50 and 100,000.50 are 100000.5."""
    s = re.sub(r"[\s\u00a0\u202f]", "", raw)
    if "." in s and "," in s:
        at = max(s.rfind("."), s.rfind(","))
        s = re.sub(r"[.,]", "", s[:at]) + "." + s[at + 1:]
    else:
        s = s.replace(",", ".")
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s) and not s.startswith("0"):
            s = s.replace(".", "")
    return s.rstrip("0").rstrip(".") if "." in s else s


def numbers_in(text: str, every: bool = False, lang: str | None = None) -> list[dict]:
    """The numbers of a text that are claims: a number of two digits or more (`1.5` has two), or one next to a percent sign, a currency sign or code (before the number or
    after it, with or without a space), or a unit (`5%`, `$5`, `9 €`, `PLN 5`, `9 zł`, `4K`). A bare single digit (a step label, "1 of 3") is not a claim, unless `every` is set (the numbers a FACTS.md value holds are all of them). A digit written
    against letters (mp3, A4, 3rd) or in a dotted version (v1.2.3) is not read. Digits grouped by spaces are one number only when the first group has 1 to 3 digits and each later group
    exactly 3 (`13 205,20` is one number; `2026 200` is two). A year right after a copyright sign or the word (`© 2026`, `(c) 2026`, `Copyright 2024-2026`) is not a claim, unless `every` is set.
    A dotted date (`15.11.2026`, `1.5.2026r.`, `30.10`) is a date whose numbers are its parts, as the ISO form (`2026-11-15`) is: the entry holds `parts` (as written). It is a date when a year
    follows (the day and month with one digit or two) or when the day and the month have two digits each (`30.10`, `05.11`); `30.10` is also the decimal 30.1, so it is backed by either reading,
    but `12.5`, `2.10` and `10.1` are decimals only. A date written with a month name (see month_dates) is one entry too, with `parts` (day, month number, year as written): it is read
    only when `lang` is a language whose month names are listed ("pl", "en", or ANY_LANGUAGE for a FACTS.md value), and is a claim whatever the digits of its day; the numbers inside it are no
    entries of their own. -> [{text, number (canonical), at, bare, parts?}], `text` as written with its sign or unit, `bare` set when no sign, code or unit is attached; the `number` of
    a date with a year is its parts joined by dots, of one without, by a slash (it is never a decimal)."""
    spans = month_dates(text, lang) if lang else []
    out = []
    for start, stop, parts in spans:
        out.append({"text": text[start:stop], "number": (".".join if len(parts) == 3 else "/".join)(parts), "at": start, "bare": True, "parts": parts})
    for m in NUMBER.finditer(text):
        if any(start <= m.start() < stop for start, stop, _ in spans):
            continue
        num, pre, post = m.group("num"), m.group("pre"), m.group("post")
        if not (every or sum(c.isdigit() for c in num) >= 2 or pre or post):
            continue
        if not every and not (pre or post) and YEAR.fullmatch(num) and COPYRIGHT_BEFORE.search(text[max(0, m.start() - COPYRIGHT_LOOKBACK):m.start()]):
            continue
        entry = {"text": m.group(0).strip(), "number": canonical_number(num), "at": m.start(), "bare": not (pre or post)}
        date = DOTTED_DATE.fullmatch(num) if entry["bare"] else None
        glued = DATE_YEAR_R.match(text, m.end()) if date and not date.group("y") else None
        if date and (date.group("y") or glued or (len(date.group("d")) > 1 and len(date.group("m")) > 1)):
            entry["parts"] = [g for g in (date.group("d"), date.group("m"), date.group("y")) if g]
            if glued:
                entry["parts"].append(glued.group(1))
                entry["text"] += glued.group(0)[:-1]
            if len(entry["parts"]) == 3:
                entry["number"] = ".".join(entry["parts"])   # with a year it is no decimal: kept as written
        out.append(entry)
    return sorted(out, key=lambda n: n["at"])


def target_stem(target) -> str:
    """The file name of the page a target aims at, without its extension: `404` for 404.html (a project page or a page of --from) and for http://localhost:8000/404.html, `` for a URL
    that ends in a slash. `target` may be None."""
    if target is None:
        return ""
    path = urlsplit(target.url or "").path if target.kind == "url" else (target.page or "")
    return posixpath.splitext(posixpath.basename(path))[0]


def status_codes(views: list[dict], target=None) -> set[str]:
    """The status codes of an error page. A page is an error page when its file name, without the extension, is a 4xx or 5xx code (`404.html`, `500.html`), or its `<title>` or an `<h1>`
    (`document.title` and `claim_h1` of a view) holds one as a bare number. The text counts only when that number is the only one in it (every number, a bare single digit and a copyright
    year too), no `+` stands before or after it, and the same text holds an error word of the page's language (ERROR_WORDS: English and Polish; the language is the view's `lang`, the
    document's, and any other, or none, leaves the file name as the only rule): `Błąd 404 | Acme` and `404 · Nie znaleziono` on a Polish page, `Error 500` on an English one do; a count in a
    heading (`Ponad 400 projektów`, `Zaufało nam 500 firm`, `Over 400 clients`), `500+ firm nam ufa`, `+500 klientów`, `5 lat, 500 klientów`, `Error 500 (1 of 3)` and `404 and 500` do not.
    A number on an error page that is this same code is the page's status code, not a claim, wherever it stands on the page; any other number is judged as usual."""
    codes = set()
    stem = target_stem(target)
    if STATUS_CODE.fullmatch(stem):
        codes.add(stem)
    for v in views:
        error_words = ERROR_WORD_PATTERNS.get(_primary_language(v.get("lang") or ""))
        if error_words is None:
            continue   # the page is in a language whose error words are not listed: the file name is the only rule
        for text in [(v.get("document") or {}).get("title"), *(v.get("claim_h1") or [])]:
            if not isinstance(text, str):
                continue
            found = numbers_in(text, every=True)      # every number of the text, a bare single digit and a copyright year too: the code must be the only one
            if len(found) == 1:
                (n,) = found
                plus = re.search(r"\+\s?$", text[:n["at"]]) or re.match(r"\s?\+", text[n["at"] + len(n["text"]):])   # +500 and 500+ are counts
                if n["bare"] and STATUS_CODE.fullmatch(n["number"]) and not plus and error_words.search(text):
                    codes.add(n["number"])
    return codes


def _bookdata():
    """scripts/booklib/bookdata.py, the FACTS.md table reader and the English status words that book-lint uses. Imported when the claims are judged, so this module
    stays importable with scripts/lib alone."""
    folder = str(Path(__file__).resolve().parents[1] / "booklib")
    if folder not in sys.path:
        sys.path.append(folder)
    import bookdata
    return bookdata


def _adapt():
    """scripts/adaptlib/adapt.py, whose `view(project)["rules"]` is the one reading of the recorded "(rule)" lines of BRAND-STATE.md Rules (G4). Imported when the brand rules are
    judged, so this module stays importable with scripts/lib alone (adapt itself reads bookdata, which _bookdata puts on the path)."""
    _bookdata()
    folder = str(Path(__file__).resolve().parents[1] / "adaptlib")
    if folder not in sys.path:
        sys.path.append(folder)
    import adapt
    return adapt


def fact_values(project: Path) -> list[str]:
    """The `value` cell of each row of the FACTS.md table, as written; a row labelled "(example ..." is the template's, never a fact."""
    rows = _bookdata().facts(project)
    return [r.get("value", "") for r in rows if r.get("value") and not r.get("fact", "").strip().lower().startswith("(example")]


def _context(text: str, at: int, length: int) -> str:
    return ("…" if at > CONTEXT_CHARS else "") + text[max(0, at - CONTEXT_CHARS):at + length + CONTEXT_CHARS].strip() + ("…" if at + length + CONTEXT_CHARS < len(text) else "")


def _primary_language(lang: str) -> str:
    return (lang or "").strip().lower().split("-")[0]


def claim_rows(rep: Report, measures: dict, ctx: Ctx) -> None:
    """page:claims: outside a labelled sample, every claim on the page is backed by a FACTS.md value. A claim is a number (see numbers_in) that no value of FACTS.md holds as
    a number, or a status word (English and Polish) that no value contains; the check reads the visible text of each block and skips the text of an element inside a non-empty
    `data-sample`. Not a claim: a copyright year, and the status code of an error page (see numbers_in and status_codes). A date written with a month name is one date, read by the language of its block (see numbers_in). A `data-sample` with no label fails ("label the sample"). A block of text that several views show is judged and counted once, and named at the first view that has it. A page language other than English or Polish (the closest `lang`, else the document's) has no list of
    status words: the row warns "NOT verified". page:samples (info, only when the page has labelled samples): each sample with its label, an excerpt, its selector and the first
    view it was seen in: the before-publishing list, also written to the report as `samples`."""
    ctx.extra["samples"] = []
    rid, label = "page:claims", "claims are backed by FACTS.md or labelled as samples"
    views = [v for v in measures.get("views", []) if isinstance(v, dict) and not v.get("error") and "claim_text" in v]
    if not views:
        rep.add(rid, "skipped", label, detail="not verified: no view was measured (see the page:load rows)")
        return
    facts = fact_values(ctx.project)
    backing_numbers = set()
    for value in facts:
        for n in numbers_in(value, every=True, lang=ANY_LANGUAGE):
            backing_numbers.add(n["number"])
            backing_numbers.update(n.get("parts", ()))
    unpadded = {x.lstrip("0") or "0" for x in backing_numbers if x.isdigit()}      # 05 and 5 are one day or month
    codes = status_codes(views, ctx.target)

    def backed(n: dict) -> bool:
        """A number is backed when a fact holds it; a dotted date also when a fact holds each of its parts (the day and month with or without a leading 0)."""
        return n["number"] in backing_numbers or (bool(n.get("parts")) and all(x in backing_numbers or (x.lstrip("0") or "0") in unpadded for x in n["parts"]))
    backing_text = "\n".join(facts).lower()
    english = list(_bookdata().LINT_DEFAULTS["status_words"])
    unbacked_numbers: dict[tuple, dict] = {}
    unbacked_status: dict[tuple, dict] = {}
    unlabelled: dict[str, dict] = {}
    samples: dict[tuple, dict] = {}
    languages: dict[str, int] = {}
    seen_runs: set[tuple] = set()          # the same block of text in another view says the same: judged and counted once, named at the first view that has it
    runs_checked = numbers_checked = status_checked = 0
    truncated = []
    for v in views:
        view_id = f"{v.get('width')}-{v.get('scheme')}"
        if v.get("claim_text_total"):
            truncated.append(f"{v['claim_text_total']} blocks of text at {v.get('width')} px, {len(v['claim_text'])} measured")
        for s in v.get("samples", []):
            key = (s.get("sel"), s.get("label"))
            if not str(s.get("label") or "").strip():
                unlabelled.setdefault(s.get("sel"), {"selector": s.get("sel"), "text": s.get("text", "")[:60], "width": v.get("width")})
            elif key not in samples:
                samples[key] = {"label": s["label"].strip(), "text": s.get("text", ""), "selector": s.get("sel"), "view": view_id}
        for run in v["claim_text"]:
            if str(run.get("sample_label") or "").strip():
                continue   # inside a labelled sample: not a claim, it is on the before-publishing list
            text, lang = run["text"], _primary_language(run.get("lang") or v.get("lang") or "")
            if (run["sel"], text, lang) in seen_runs:
                continue
            seen_runs.add((run["sel"], text, lang))
            languages[lang] = languages.get(lang, 0) + 1
            runs_checked += 1
            for n in numbers_in(text, lang=lang):
                if n["bare"] and n["number"] in codes:
                    continue   # the status code of an error page: its title or h1 holds the same number next to an error word
                numbers_checked += 1
                if not backed(n):
                    unbacked_numbers.setdefault((n["number"], run["sel"]), {"number": n["text"], "selector": run["sel"], "context": _context(text, n["at"], len(n["text"])), "width": v.get("width")})
            for word in english + (list(STATUS_WORDS_PL) if lang == "pl" else []):
                for m in re.finditer(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text, re.I):
                    status_checked += 1
                    if word.lower() not in backing_text:
                        unbacked_status.setdefault((word, run["sel"]), {"word": word, "selector": run["sel"], "context": _context(text, m.start(), len(word)), "width": v.get("width")})
    ctx.extra["samples"] = list(samples.values())
    parts = []
    if unbacked_numbers:
        parts.append(f"{len(unbacked_numbers)} number(s) no FACTS.md value holds: " + _names([f"{o['number']} in {o['selector']} (\"{o['context']}\")" for o in unbacked_numbers.values()], NAMED)
                     + "; add the fact to FACTS.md (owner-confirmed) or mark the text data-sample=\"<label>\"")
    if unbacked_status:
        parts.append(f"{len(unbacked_status)} status word(s) no FACTS.md value contains: " + _names([f"'{o['word']}' in {o['selector']} (\"{o['context']}\")" for o in unbacked_status.values()], NAMED)
                     + "; add the fact to FACTS.md (owner-confirmed) or remove the claim")
    if unlabelled:
        parts.append(f"{len(unlabelled)} data-sample with no label: label the sample (data-sample=\"<what it stands for>\"): " + _names([o["selector"] for o in unlabelled.values()], NAMED))
    unverified = sorted(k for k in languages if k not in CLAIM_LANGUAGES)
    notes = []
    if unverified:
        notes.append("status words NOT verified for " + ", ".join(k or "an unknown language (the page sets no lang)" for k in unverified)
                     + " (only English and Polish are listed); numbers were checked")
    if truncated:
        notes.append("NOT verified beyond the first blocks of text of a view: " + _names(truncated, 2))
    extra = {"claims_checked": {"texts": runs_checked, "numbers": numbers_checked, "status_words": status_checked}, "unbacked_numbers": list(unbacked_numbers.values())[:100],
             "unbacked_status_words": list(unbacked_status.values())[:100], "unlabelled_samples": list(unlabelled.values())[:100], "languages": languages}
    if parts:
        rep.add(rid, "fail", label, detail="; ".join(parts + notes), **extra)
    elif notes:
        rep.add(rid, "warn", label, detail="; ".join(notes), **extra)
    else:
        rep.add(rid, "pass", label, detail=f"{numbers_checked} number(s) and {status_checked} status word(s) outside labelled samples, each backed by a FACTS.md value", **extra)
    if samples:
        rep.add("page:samples", "info", "before publishing: sample content on the page", detail=f"{len(samples)} labelled sample(s) pass as samples and must be replaced with real content before the page is published: "
                + _names([f"{s['label']} ({s['text'][:40] or 'no text'}) in {s['selector']}, {s['view']}" for s in samples.values()], NAMED), samples=list(samples.values()))


# ---------------------------------------------------------------- the mark

LOGO_DIR = "assets/logo"
LOGO_FILE_MAX = 50 * 1024 * 1024          # a logo file larger than this is not hashed
SVG_ROOT_LOOSE = frozenset({"width", "height", "class", "style", "id", "role", "focusable", "tabindex"})   # on the root <svg> of an inline mark: how the page sizes, styles and labels it
SVG_NOT_DRAWN = frozenset({"title", "desc", "metadata"})   # children of an SVG that draw nothing: the accessible name and the file's own notes


def _local(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def _canon(el, root: bool = False) -> tuple:
    attrs = sorted((_local(k), " ".join(str(v).split())) for k, v in el.attrib.items()
                   if not (root and (_local(k) in SVG_ROOT_LOOSE or _local(k).startswith(("aria-", "data-")))))
    text, kids = el.text or "", []   # [drawing of a child, the text that follows it]: `Ac<tspan>m</tspan>e` and `Ac<tspan>m</tspan>ZZZ` are two wordmarks
    for c in el:
        if isinstance(c.tag, str) and _local(c.tag) not in SVG_NOT_DRAWN:
            kids.append([_canon(c), c.tail or ""])
        elif kids:   # a child that draws nothing: the text after it still follows the text before it
            kids[-1][1] += c.tail or ""
        else:
            text += c.tail or ""
    return (_local(el.tag), tuple(attrs), " ".join(text.split()), tuple((k, " ".join(t.split())) for k, t in kids))


def canonical_svg(text) -> tuple | None:
    """An SVG as what it draws, so that two files that draw the same thing are equal: namespaces and prefixes dropped (`xlink:href` is `href`), attributes sorted, white space
    collapsed in attribute values and text, comments and the `title`, `desc` and `metadata` elements left out; on the root `<svg>` also `width`, `height`, `class`, `style`, `id`,
    `role`, `focusable`, `tabindex`, `aria-*` and `data-*` (how a page sizes, styles and labels its copy). `viewBox` and everything inside the root stay. None when the text is not
    an SVG document this can read (not XML, a DOCTYPE with entities, nested too deep)."""
    if not isinstance(text, str) or "<!ENTITY" in text:
        return None
    try:
        root = ET.fromstring(re.sub(r"^\s*<\?xml[^>]*\?>", "", text.lstrip("﻿")).strip())
        return _canon(root, True) if _local(root.tag) == "svg" else None
    except (ET.ParseError, RecursionError, ValueError):
        return None


def twin_of(path: str) -> str:
    """The other theme's drawing of a file: `mark.svg` <-> `mark-dark.svg`; any other file is its own twin."""
    if path.endswith("-dark.svg"):
        return path[:-len("-dark.svg")] + ".svg"
    return path[:-len(".svg")] + "-dark.svg" if path.endswith(".svg") else path


def _uses_use(canon: tuple) -> bool:
    """Whether a canonical SVG draws through a `<use>` anywhere (it points at a drawing this does not follow)."""
    return canon[0] == "use" or any(_uses_use(kid) for kid, _ in canon[3])


def project_keys(project: Path, path: str) -> list[str]:
    """The keys of `logo_files` that a project-relative path written in qa/rules.json (or in `data-brand-mark`) stands for: the file and its `-dark.svg` twin, each as `logo_files` keys
    it (`./` and `..` folded away, a symlink followed). A path that leads out of the project stands for nothing."""
    f = project / path.strip()
    keys = []
    for name in (f.name, posixpath.basename(twin_of(f.name))):
        try:
            keys.append(rel(project, f.with_name(name)))
        except (ValueError, OSError):
            continue
    return keys


def logo_files(project: Path, rules: dict) -> dict[str, str]:
    """Every file the mark on a page may be: all of assets/logo/ and the drawings qa/rules.json names (bands, favicon, marks), each with its `-dark.svg` twin. -> {project-relative
    posix path: sha256}. A file that leads out of the project through a symlink, or is over LOGO_FILE_MAX, is left out."""
    named = [b["drawing"] for b in rules.get("bands", [])] + [(rules.get("favicon") or {}).get("drawing", "")]
    for m in (rules.get("marks") or {}).values():
        named += [b["drawing"] for b in m["bands"]] + [m.get("favicon", "")]
    paths = set(p for p in (project / LOGO_DIR).rglob("*") if p.is_file()) if (project / LOGO_DIR).is_dir() else set()
    for d in named:
        if isinstance(d, str) and d.strip():
            f = project / d.strip()
            paths.update([f, f.with_name(posixpath.basename(twin_of(f.name)))])
    out: dict[str, str] = {}
    for f in sorted(paths):
        try:
            if f.is_file() and _inside(project, f) and f.stat().st_size <= LOGO_FILE_MAX:
                out[rel(project, f)] = hashlib.sha256(f.read_bytes()).hexdigest()
        except OSError:
            continue
    return out


def identified_marks(view: dict, logo_hashes) -> list[dict]:
    """The marks of one measured view: what the page marks (`data-brand-mark`), what is named like a logo (the stem is `logo`, `mark` or `wordmark`, alone or followed by `-`, `_` or `@` and more; `mark` and `wordmark` only for an `.svg` file), and any other image whose bytes are a logo file of the project. Each is the
    collector's entry plus `by` (attribute, name or bytes) and `sha256` (the bytes seen: render.mjs hashed a file of the page's own origin, the collector a data: URL; None when
    they were not seen). Every rule about marks reads them from here."""
    resources = view.get("resources") or {}
    out = []
    for e in list(view.get("marks") or []) + list(view.get("images") or []):
        if not isinstance(e, dict):
            continue
        sha = e.get("sha256") or ((resources.get(e.get("url")) or {}).get("sha256") if e.get("own") else None)
        by = "attribute" if e.get("marked") else "name" if e.get("named") else "bytes" if sha and sha in logo_hashes else None
        if by:
            out.append({**e, "sha256": sha, "by": by})
    return out


def _neighbour(o: dict) -> str:
    """What stands too near a mark, for a message: its selector and, for a line of text, the words."""
    return (o.get("nearest") or "a box") + (' "%s"' % o["nearest_text"] if o.get("nearest_text") else "")


def _h(mark: dict) -> float | None:
    """The mark's rendered height in css px: its box, else (a pseudo-element) its computed height."""
    r = mark.get("rect")
    h = r.get("height") if isinstance(r, dict) else mark.get("height_px")
    return float(h) if isinstance(h, (int, float)) and h > 0 else None


def _clear_space_row(rep: Report, shown: list, ctx: Ctx) -> None:
    """page:mark-clear-space: nothing nearer to a shown mark than `page.clear_space` x its rendered height (a share of its box; the gap is the larger of the horizontal and the
    vertical distance to the nearest other text line, image or SVG, so the free space is a margin round the mark)."""
    share = float(ctx.rules["page"]["clear_space"])
    proposed = "page.clear_space" not in ctx.rules.get("_from_file", [])
    near: dict[tuple, dict] = {}
    cleared: dict[tuple, dict] = {}
    unmeasured: dict[str, dict] = {}
    for v, m in shown:
        height = _h(m)
        at = {"selector": m["sel"], "width": v.get("width"), "scheme": v.get("scheme")}
        if height is None or m.get("rect") is None:
            unmeasured.setdefault(m["sel"], {**at, "why": "its box cannot be measured (a pseudo-element)"})
            continue
        need = round(share * height, 2)
        o = {**at, "height_px": round(height, 2), "needs_px": need, "nearest_px": m.get("nearest_px"), "nearest": m.get("nearest_sel"), "nearest_text": m.get("nearest_text")}
        cleared.setdefault((m["sel"], round(height)), o)
        if m.get("nearest_px") is not None and round(m["nearest_px"], 2) < need:
            near.setdefault((m["sel"], m.get("nearest_sel"), round(m["nearest_px"])), o)
    rule = f"{share:g} x the mark's rendered height" + (" (a proposal until qa/rules.json sets page.clear_space)" if proposed else "")
    extra = {"checked": len(cleared), "clear_space": share, "proposal": proposed, "offenders": list(near.values())[:100], "unverified": list(unmeasured.values())[:100]}
    if near:
        rep.add("page:mark-clear-space", "fail", "free space round the mark", detail=f"{len(near)} mark(s) have something nearer than the clear space, {rule}: " + _names([
            f"{o['selector']} ({o['height_px']:g} px high) has {_neighbour(o)} {o['nearest_px']:g} px away, needs "
            f"{o['needs_px']:g} px; first seen at {o['width']} px {o['scheme']}" for o in near.values()], NAMED), **extra)
    elif unmeasured:
        rep.add("page:mark-clear-space", "warn", "free space round the mark", detail="NOT verified: " + _names([f"{o['selector']}: {o['why']}" for o in unmeasured.values()], NAMED), **extra)
    else:
        rep.add("page:mark-clear-space", "pass", "free space round the mark", detail=f"{len(cleared)} mark(s) have the clear space, {rule}: nothing is nearer", **extra)


def mark_rows(rep: Report, measures: dict, ctx: Ctx) -> None:
    """page:mark-file, page:mark-band and page:mark-clear-space: the brand mark on the page.

    A mark is an element with `data-brand-mark`, an image whose file name says it is the logo (the name without its extension is `logo`, `mark` or `wordmark`, alone or followed by `-`, `_` or `@` and more: `logo.svg`, `mark-dark.svg`, `logo@2x.png`; `partner-logo.svg`,
    `ikona-logowanie.svg` and `bookmark.svg` only hold the word and are not; `mark` and `wordmark` name a mark only for an `.svg` file, so a photo `mark.jpg` is not, while `logo` does for any
    image type), or any image whose bytes are a file of assets/logo/ (see `identified_marks`). Only a mark that is shown is judged.
    `page:mark-file` fails a mark that is none of the logo files of the project (assets/logo/ and the drawings named in qa/rules.json bands, favicon and marks, with their -dark.svg
    twins): the bytes of a file, or an inline SVG after canonicalisation (`canonical_svg`). `data-brand-mark="<file>"` also names the file it shows (or its twin).
    `page:mark-band` fails a banded drawing (one a band of qa/rules.json names, or its twin) that is not the drawing `qa_rules.pick_band` names for the mark's rendered height; a wordmark
    or lockup is in no band and is not judged. `page:mark-clear-space` fails a mark with another box nearer than `page.clear_space` x its rendered height."""
    masters = logo_files(ctx.project, ctx.rules)
    views = [v for v in measures.get("views", []) if isinstance(v, dict) and not v.get("error") and "marks" in v]
    if not views:
        rep.add("page:mark-file", "skipped", "the brand mark", detail="not verified: no view was measured (see the page:load rows)")
        return
    rep.inputs.extend(ctx.project / p for p in masters)   # a change to a logo file makes the report stale: even "no mark shown" may rest on a logo's bytes
    hashes = set(masters.values())
    found = [(v, m) for v in views for m in identified_marks(v, hashes)]
    shown = [(v, m) for v, m in found if m.get("visible")]
    cut = [f"{v['marks_total']} marks at {v.get('width')} px, {len(v['marks'])} measured" for v in views if v.get("marks_total")]
    cut += [f"{v['images_total']} images at {v.get('width')} px, {len(v['images'])} looked at for a logo file's bytes" for v in views if v.get("images_total")]
    truncated = f"NOT verified beyond the first marks and images of a view: {_names(cut, 2)}" if cut else ""
    if not shown:
        hidden = f"; {len({(m['sel'], m.get('url')) for _, m in found})} marked or named mark(s) are not shown in any view" if found else ""
        rep.add("page:mark-file", "info", "the brand mark", detail="no brand mark is shown on this page: a mark is an element with data-brand-mark, an image whose file is named logo, mark or wordmark "
                "(logo.svg, mark-dark.svg, wordmark_light.svg, logo@2x.png; mark and wordmark only for an .svg file), or an image whose bytes are a logo file of the project" + hidden + ("; " + truncated if truncated else ""))
        return
    if not masters:
        why = f"not verified: the project has no logo files ({LOGO_DIR}/) to compare the mark with"
        rep.add("page:mark-file", "skipped", "the brand mark is a logo file", detail=why)
        rep.add("page:mark-band", "skipped", "the drawing for the mark's size", detail=why)
        _clear_space_row(rep, shown, ctx)
        return
    canon: dict[str, tuple | None] = {}

    def drawn(path: str) -> tuple | None:
        if path not in canon:
            try:
                canon[path] = canonical_svg((ctx.project / path).read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                canon[path] = None
        return canon[path]

    def key(m: dict) -> tuple:
        return (m["kind"], m["sel"], m.get("url"), m.get("sha256"), hashlib.sha256(str(m.get("svg_markup")).encode()).hexdigest())

    def files_of(m: dict) -> tuple[list[str] | None, str]:
        """-> (the logo files this mark is, why not). None: it could not be compared."""
        if m["kind"] == "inline-svg":
            c = canonical_svg(m.get("svg_markup"))
            if c is None or m.get("svg_truncated"):
                return None, "the inline SVG could not be read for a comparison" + (" (too long)" if m.get("svg_truncated") else "")
            same = [p for p in masters if p.endswith(".svg") and drawn(p) == c]
            if not same and _uses_use(c):
                return None, "the inline SVG draws through <use> and the drawing it points to is not followed, so it could not be compared"
            return same, "this inline SVG draws none of the logo drawings of the project (compared after canonicalisation)"
        if not m.get("url"):
            return [], "the mark shows no file"
        if not m.get("sha256"):
            return None, ("its file is on another origin (aborted: page-check runs offline)" if not m.get("own")
                          else "the bytes of its file were not seen (it did not load, or it was reached through a redirect)")
        return [p for p, sha in masters.items() if sha == m["sha256"]], "the bytes of this file are none of the logo files of the project"

    verdict: dict[tuple, tuple[list[str] | None, str]] = {}
    problems: list[dict] = []
    unverified: list[dict] = []
    ok: dict[tuple, list[str]] = {}
    for v, m in shown:
        k = key(m)
        if k in verdict:
            continue
        at = {"selector": m["sel"], "kind": m["kind"], "url": m.get("url"), "found_by": m["by"], "width": v.get("width"), "scheme": v.get("scheme")}
        if m["kind"] == "other":
            verdict[k] = ([], "")
            problems.append({**at, "why": "data-brand-mark is on an element that shows no image: put it on the img or svg of the mark"})
            continue
        files, why = verdict[k] = files_of(m)
        if files is None:
            unverified.append({**at, "why": why})
        elif not files:
            problems.append({**at, "why": why})
        else:
            declared = m.get("declared")
            if declared and declared.strip():
                want = posixpath.normpath(declared.strip().lstrip("/"))
                kin = set(project_keys(ctx.project, want))
                if not kin & set(masters):
                    problems.append({**at, "why": f"data-brand-mark names {want}, which is not a logo file of the project"})
                    continue
                if not kin & set(files):
                    problems.append({**at, "why": f"data-brand-mark names {want}, but this mark is {', '.join(files[:2])}"})
                    continue
            ok[k] = files
    seen_files = sorted({f for fs in ok.values() for f in fs})
    items = [f"{o['selector']} ({o['kind']}{' ' + o['url'] if o['url'] else ''}): {o['why']}; first seen at {o['width']} px {o['scheme']}" for o in problems]
    notes = [f"NOT verified: {o['selector']}: {o['why']}" for o in unverified] + ([truncated] if truncated else [])
    extra = {"marks_checked": len({key(m) for _, m in shown}), "files": seen_files, "offenders": problems[:100], "unverified": unverified[:100]}
    if problems:
        rep.add("page:mark-file", "fail", "the brand mark is a logo file", detail=f"{len(problems)} mark(s) are not a logo file of the project: {_names(items, NAMED)}"
                + "".join("; " + n for n in notes[:2]), **extra)
    elif notes:
        done = f"{len(ok)} mark(s) are logo files of the project ({_names(seen_files, NAMED)}); " if ok else ""
        rep.add("page:mark-file", "warn", "the brand mark is a logo file", detail=done + _names(notes, NAMED), **extra)
    else:
        kinds = sorted({m["kind"] for _, m in shown})
        rep.add("page:mark-file", "pass", "the brand mark is a logo file", detail=f"{extra['marks_checked']} mark(s) ({', '.join(kinds)}), each a logo file of the project: "
                f"{_names(seen_files, NAMED)}" + ("; an inline SVG was compared after canonicalisation" if "inline-svg" in kinds else ""), **extra)

    # the band rule: each mark that is a banded drawing is the drawing its rendered height calls for
    sets = [(m["bands"], mid) for mid, m in (ctx.rules.get("marks") or {}).items()] or ([(ctx.rules["bands"], None)] if ctx.rules.get("bands") else [])
    if not sets:
        rep.add("page:mark-band", "info", "the drawing for the mark's size", detail="qa/rules.json lists no size bands (bands, or marks.<id>.bands): the drawing for a size is not checked")
    else:
        banded_by = {k: i for i, (bands, _) in enumerate(sets) for b in bands for k in project_keys(ctx.project, b["drawing"])}   # as written in qa/rules.json: `./a/b.svg`, a symlink
        checked: dict[tuple, dict] = {}
        wrong: dict[tuple, dict] = {}
        loose: dict[str, dict] = {}
        skipped = set()
        for v, m in shown:
            files = (verdict.get(key(m)) or (None, ""))[0]
            if not files or key(m) not in ok:
                continue
            of = sorted({banded_by[f] for f in files if f in banded_by})
            if not of:
                skipped.add(m["sel"])
                continue
            height = _h(m)
            at = {"selector": m["sel"], "files": files, "width": v.get("width"), "scheme": v.get("scheme")}
            if height is None:
                loose.setdefault(m["sel"], {**at, "why": "its box cannot be measured"})
                continue
            px = int(height + 0.5)
            bands, mid = sets[of[0]]
            band = qa_rules.pick_band(bands, px)
            want = project_keys(ctx.project, band["drawing"])
            row_ = {**at, "height_px": px, "band": band["name"], "drawing": (want or [band["drawing"]])[0], **({"mark": mid} if mid else {})}
            checked.setdefault((m["sel"], px, tuple(files)), row_)
            if not set(want) & set(files):
                wrong.setdefault((m["sel"], px, tuple(files)), row_)
        extra = {"checked": len(checked), "not_banded": sorted(skipped), "offenders": list(wrong.values())[:100], "unverified": list(loose.values())[:100]}
        if wrong:
            rep.add("page:mark-band", "fail", "the drawing for the mark's size", detail=f"{len(wrong)} mark(s) are not the drawing the size bands call for: " + _names([
                f"{o['selector']} is {o['files'][0]} at {o['height_px']} px, band {o['band']} is {o['drawing']} (or its -dark.svg twin); first seen at {o['width']} px {o['scheme']}"
                for o in wrong.values()], NAMED), **extra)
        elif loose:
            rep.add("page:mark-band", "warn", "the drawing for the mark's size", detail="NOT verified: " + _names([f"{o['selector']}: {o['why']}" for o in loose.values()], NAMED), **extra)
        elif checked:
            rep.add("page:mark-band", "pass", "the drawing for the mark's size", detail=f"{len(checked)} mark(s) at their rendered height are the drawing the bands name: " + _names([
                f"{o['files'][0]} at {o['height_px']} px (band {o['band']})" for o in checked.values()], NAMED), **extra)
        else:
            rep.add("page:mark-band", "info", "the drawing for the mark's size", detail="no mark on this page is a drawing of a size band (a wordmark or a lockup is in no band, and a mark that is "
                    "not a logo file is judged by page:mark-file)", **extra)

    _clear_space_row(rep, shown, ctx)


# ---------------------------------------------------------------- fonts

GENERIC_FAMILIES = frozenset({"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-serif", "ui-sans-serif", "ui-monospace", "ui-rounded", "math",
                              "emoji", "fangsong"})   # the CSS generic families: the browser's own choice, nothing for a page to load
BROWSER_ALIASES = frozenset({"-apple-system", "blinkmacsystemfont"})   # names the browser resolves to the operating system's interface font: no font of that name exists to look for
BROWSER_FAMILIES = GENERIC_FAMILIES | BROWSER_ALIASES                # the browser's own choice: a token stack may name them, a page is not asked to load them, and nothing is checked
SYSTEM_FAMILIES = frozenset({"segoe ui", "roboto", "cantarell", "ubuntu", "noto sans", "helvetica neue", "helvetica", "arial"})
# the interface and web-safe faces some operating systems ship under these names (several are also common brand web fonts): a token stack may name them and a page need not
# declare them, but they are looked for, and where this machine has none the row says NOT verified instead of passing
FONT_DISPLAY = "font.display"
FONT_ALIAS = re.compile(r"var\(\s*(--[\w-]+)\s*\)")
FONT_NOT_A_FAMILY = re.compile(r"[\d.]+(?:px|rem|em|%|ms|s)?")   # a font.* token that holds a size or a number is no family
FONT_NAMED = 6                            # how many token families a detail names
DISPLAY_EPSILON = 0.005                   # the measured size is rounded to two decimals: 19.99 is under 20, 20 is not


def split_families(css: str) -> list[str]:
    """A CSS font-family list -> its families, quotes taken off and white space collapsed: `"Acme Sans", system-ui` -> ["Acme Sans", "system-ui"]."""
    out, cur, quote = [], "", None
    for ch in str(css):
        if quote:
            if ch == quote:
                quote = None
            else:
                cur += ch
        elif ch in "\"'":
            quote = ch
        elif ch == ",":
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [" ".join(f.split()) for f in out if f.strip()]


def family_key(name: str) -> str:
    """How two family names are compared: white space collapsed, case folded."""
    return " ".join(str(name).split()).casefold()


def font_stacks(tokens: dict) -> dict[str, list[str]]:
    """The font families the brand names: tokens.json `other` keys starting `font.` -> the families of each stack, as written. An alias (`var(--font-sans)`) is followed;
    a token that holds a size or a number is no stack. {} when the tokens name no font."""
    other = tokens.get("other") if isinstance(tokens.get("other"), dict) else {}
    by_var = {"--" + k.replace(".", "-"): v for k, v in other.items() if isinstance(v, str)}

    def resolve(value: str, depth: int = 0) -> str:
        m = FONT_ALIAS.fullmatch(value.strip())
        return resolve(by_var[m.group(1)], depth + 1) if m and m.group(1) in by_var and depth < 8 else value

    out = {}
    for key, value in sorted(other.items()):
        if key.startswith("font.") and isinstance(value, str):
            names = [n for n in split_families(resolve(value)) if not FONT_NOT_A_FAMILY.fullmatch(n)]
            if names:
                out[key] = names
    return out


def _rendered_views(measures: dict, key: str) -> list[dict]:
    """Every rendered view (any width, any scheme) that holds the facts `key`, in the order they were measured."""
    return [v for v in measures.get("views", []) if isinstance(v, dict) and not v.get("error") and key in v]


def _platform_names(platform: list) -> str:
    return ", ".join(f"{p.get('family')}{' (web font)' if p.get('custom') else ''} {p.get('glyphs')} glyph(s)" for p in platform) or "no font"


def font_rows(rep: Report, measures: dict, ctx: Ctx) -> None:
    """page:fonts: the families the page sets its text in are the brand's, and the browser really used them. Over all widths and both schemes, every distinct (first
    family, weight, style) of the computed `font-family` of a shown text is judged once:
      * its first family must be named in some `font.*` token stack (names compared without quotes and case); a generic family (`sans-serif`, `system-ui` ...) or a
        browser alias (BROWSER_FAMILIES) counts only when a stack names it: fail "not named by the tokens";
      * a family the page declares with @font-face (`font_faces`), or any named family that is not generic or an alias, must be what Chromium drew the text in: the platform
        font of the probe element (CDP) is an installed font of that name, or a web font of the page AND the page declares that family with at least one face `loaded` (a web
        font drawn for a family that is not declared, or whose faces all failed or never loaded, is another family's fallback, not this one's face). Fail when the browser used
        none of it: the face did not load (status error), the page declares none and the font is not installed here, or no face covers the text. A text part of whose glyphs
        are drawn in another font (the face lacks a character the text uses) is a warning, with the glyph counts;
      * a system face (SYSTEM_FAMILIES) the page does not declare is looked for the same way (an installed font of that name); where this machine has none it is "NOT
        verified" in a warning, naming what Chromium used, never a pass and never a failure (the stack is meant to fall through to the next family).
    A debugger that could not answer is "NOT verified" in a warning, never a pass. The probe is one element per entry (the collector keeps what is inside it that is set in
    another font out of its answer): a fallback glyph elsewhere is not seen."""
    rid, label = "page:fonts", "fonts of the page"
    stacks = font_stacks(ctx.tokens)
    if not stacks:
        rep.add(rid, "skipped", label, detail=f"not verified: {TOKENS_FILE} names no font family (no font.* token), so the families of the page cannot be judged; "
                                              "add them to the token sources and run `brand-creator tokens` again")
        return
    views = _rendered_views(measures, "font_usage")
    if not views:
        rep.add(rid, "skipped", label, detail="not verified: no view was measured (see the page:load rows)")
        return
    named = {family_key(f): f for names in stacks.values() for f in names}
    offenders: dict[tuple, dict] = {}
    warned: dict[tuple, dict] = {}
    unverified: dict[tuple, str] = {}
    checked: dict[tuple, dict] = {}
    truncated = []
    for v in views:
        if v.get("font_usage_total"):
            truncated.append(f"{v['font_usage_total']} fonts at {v.get('width')} px {v.get('scheme')}, {len(v['font_usage'])} measured")
        faces = [f for f in v.get("font_faces", []) if isinstance(f, dict)]
        for u in v["font_usage"]:
            name, fam = u.get("family") or "", family_key(u.get("family", ""))
            ident = (fam, u.get("weight"), u.get("style"))
            at = {"family": name, "weight": u.get("weight"), "style": u.get("style"), "selector": u.get("sel"), "stack": u.get("stack"), "width": v.get("width"),
                  "scheme": v.get("scheme"), "elements": u.get("count", 1)}
            checked.setdefault(ident, {**at, "platform": u.get("platform")})
            if fam not in named:
                offenders.setdefault(ident, {**at, "kind": "not-named", "why": f"{u.get('sel')} is set in \"{name}\", which no font token names "
                                                                              f"(the tokens name {', '.join(list(named.values())[:FONT_NAMED])}{' and more' if len(named) > FONT_NAMED else ''})"})
                continue
            declared = [f for f in faces if family_key(f.get("family", "")) == fam]
            if not declared and fam in BROWSER_FAMILIES:
                continue   # named by a token, drawn in the browser's own font
            platform = u.get("platform")
            if not platform:
                unverified.setdefault(ident, f"\"{name}\" ({u.get('sel')}): " + (f"the browser's debugger could not say which font was used ({u.get('platform_error')})"
                                                                              if platform is None else "the browser reported no font for the text"))
                continue
            drawable = any(f.get("status") == "loaded" for f in declared)   # a web font in the answer is this family's own only when one of its faces loaded
            mine = [p for p in platform if (p.get("custom") and drawable) or family_key(p.get("family", "")) == fam]   # its web font, or an installed font of that name
            others = [p for p in platform if p not in mine]
            statuses = sorted({str(f.get("status")) for f in declared})
            if not mine and not declared and fam in SYSTEM_FAMILIES:
                unverified.setdefault(ident, f"\"{name}\" ({u.get('sel')}): a system face the page does not declare and this machine does not have; "
                                             f"Chromium used {_platform_names(platform)}")
                continue
            if not mine:
                reason = ("the page declares no @font-face for it and it is not installed on this machine" if not declared else
                          f"its font file did not load (status {', '.join(statuses)})" if "error" in statuses and "loaded" not in statuses else
                          f"none of its @font-face rules covers this text (status {', '.join(statuses)})")
                offenders.setdefault(ident, {**at, "kind": "not-loaded", "faces": statuses, "platform": platform,
                                             "why": f"{u.get('sel')} is set in \"{name}\" (weight {u.get('weight')}): {reason}; Chromium used {_platform_names(platform)}"})
            elif others:
                total, away = (sum(int(p.get("glyphs") or 0) for p in group) for group in (platform, others))
                warned.setdefault(ident, {**at, "kind": "partly-another-font", "platform": platform,
                                          "why": f"{u.get('sel')} (\"{name}\", weight {u.get('weight')}): {away} of {total} glyph(s) are drawn in another font, "
                                                 f"so the face lacks a character the text uses ({_platform_names(others)})"})
    parts = []
    if offenders:
        parts.append(f"{len(offenders)} font(s) are not the brand's or not drawn: " + _names([o["why"] for o in offenders.values()], NAMED))
    if warned:
        parts.append(f"{len(warned)} font(s) are partly drawn in another font: " + _names([o["why"] for o in warned.values()], NAMED))
    if unverified:
        parts.append(f"NOT verified: {len(unverified)} font(s): " + _names(list(unverified.values()), NAMED))
    if truncated:
        parts.append("NOT verified beyond the first fonts of a view: " + _names(truncated, 2))
    extra = {"fonts": [{k: c[k] for k in ("family", "weight", "style", "selector", "elements", "platform")} for c in list(checked.values())[:100]],
             "offenders": list(offenders.values())[:100], "partly": list(warned.values())[:100], "token_families": list(named.values())}
    if offenders:
        rep.add(rid, "fail", label, detail="; ".join(parts), **extra)
    elif parts:
        rep.add(rid, "warn", label, detail="; ".join(parts), **extra)
    else:
        rep.add(rid, "pass", label, detail=f"{len(checked)} font(s) set on the page ({_names(sorted({c['family'] or '(none)' for c in checked.values()}), NAMED)}), "
                                           "each named by a font token and drawn by its own face, an installed font of that name or the browser's own font", **extra)


def display_size_rows(rep: Report, measures: dict, ctx: Ctx) -> None:
    """page:display-size: a text set in the first family of the `font.display` token is at least `page.display_min_px` css px (qa/rules.json; 20 is the proposal, and the
    detail says so until the project sets it). Without a `font.display` token the row is info. A display face that is also the first family of another font token (the body
    face) cannot be told apart from body text, so no size is held to it: info, never a silent pass."""
    rid, label = "page:display-size", "display face minimum size"
    stacks = font_stacks(ctx.tokens)
    display = stacks.get(FONT_DISPLAY)
    if not display:
        rep.add(rid, "info", label, detail=f"this brand has no {FONT_DISPLAY} token, so there is no display face whose size is checked")
        return
    face = display[0]
    twin = next((k for k, names in sorted(stacks.items()) if k != FONT_DISPLAY and family_key(names[0]) == family_key(face)), None)
    if twin:
        rep.add(rid, "info", label, detail=f"the display face ({face}) is also the first family of {twin}: text set in it cannot be told from body text, so no minimum size is checked")
        return
    views = _rendered_views(measures, "font_usage")
    if not views:
        rep.add(rid, "skipped", label, detail="not verified: no view was measured (see the page:load rows)")
        return
    minimum = float(ctx.rules["page"]["display_min_px"])
    proposal = "page.display_min_px" not in (ctx.rules.get("_from_file") or [])
    basis = f"minimum {minimum:g} px" + (" (a proposal: set page.display_min_px in qa/rules.json to keep or change it)" if proposal else " (qa/rules.json page.display_min_px)")
    small: dict[tuple, dict] = {}
    smallest = None
    truncated = []
    for v in views:
        if v.get("font_usage_total"):
            truncated.append(f"{v['font_usage_total']} fonts at {v.get('width')} px {v.get('scheme')}, {len(v['font_usage'])} measured")
        for u in v["font_usage"]:
            if family_key(u.get("family", "")) != family_key(face):
                continue
            px = float(u.get("min_px") or 0)
            smallest = px if smallest is None else min(smallest, px)
            if px < minimum - DISPLAY_EPSILON:
                small.setdefault((u.get("min_sel"), px), {"selector": u.get("min_sel"), "text": u.get("min_text"), "font_size_px": px, "weight": u.get("weight"),
                                                          "width": v.get("width"), "scheme": v.get("scheme")})
    extra = {"display_face": face, "minimum_px": minimum, "proposal": proposal, "smallest_px": smallest}
    notes = [f"NOT verified beyond the first fonts of a view: {_names(truncated, 2)}"] if truncated else []
    if small:
        rep.add(rid, "fail", label, detail=f"{len(small)} text(s) in the display face {face} are under {minimum:g} px: " + _names([
            f"{o['selector']} \"{o['text']}\" is {o['font_size_px']:g} px at {o['width']} px {o['scheme']}" for o in small.values()], NAMED) + f"; {basis}"
            + "".join("; " + n for n in notes), small=list(small.values())[:100], **extra)
    elif notes:
        rep.add(rid, "warn", label, detail="; ".join(notes), **extra)
    elif smallest is None:
        rep.add(rid, "pass", label, detail=f"no text on the page is set in the display face {face}; {basis}", **extra)
    else:
        rep.add(rid, "pass", label, detail=f"every text in the display face {face} is {smallest:g} px or more; {basis}", **extra)


# ---------------------------------------------------------------- the brand's own rules

MEASURED_RULES = ("max-words-per-control", "words-under-accent")   # kinds whose facts the browser collects from the page's text; max-marks-per-view reads the marks every view holds
WINDOW_STEP = 0.5                         # screens are windows one viewport high, stepped by this share of a viewport


def rule_request(page_rules: list[dict]) -> tuple[list[str], list[dict]]:
    """What the brand rules (qa/rules.json page.rules, as qa_rules validated them) ask of the browser: -> (the CSS selectors they name, once each in the order of the rules, for the
    request's `selectors`; one {id, kind, selector?} per rule that is measured in the page, for the request's `rules`). A rule of another kind asks for nothing."""
    selectors: list[str] = []
    asks: list[dict] = []
    for r in page_rules:
        if r["kind"] not in MEASURED_RULES:
            continue
        sel = r.get("selector")
        if sel and sel not in selectors:
            selectors.append(sel)
        asks.append({"id": r["id"], "kind": r["kind"], **({"selector": sel} if sel else {})})
    return selectors, asks


def mark_windows(page_height, viewport_height) -> list[tuple[float, float]]:
    """The screens a reader scrolls through: windows one viewport high, from the top of the page down in steps of half a viewport, the last one reaching the end of the page.
    -> [(top, bottom)] in css px. A page no taller than the viewport is one window."""
    vh = max(float(viewport_height or 0), 1.0)
    height = float(page_height) if isinstance(page_height, (int, float)) else vh
    tops, y = [0.0], 0.0
    while y + vh < height:
        y += vh * WINDOW_STEP
        tops.append(y)
    return [(t, t + vh) for t in tops]


def _placed_marks(view: dict, hashes) -> tuple[list[dict], list[dict]]:
    """The marks shown in one view: (those with a box on the page, one per place however many ways they were found; those with none to place, a pseudo-element's)."""
    placed: dict[tuple, dict] = {}
    loose: dict[str, dict] = {}
    for m in identified_marks(view, hashes):
        if not m.get("visible"):
            continue
        r = m.get("rect")
        if not (isinstance(r, dict) and all(isinstance(r.get(k), (int, float)) for k in ("x", "y", "width", "height"))):
            loose.setdefault(m["sel"], m)
            continue
        placed.setdefault((m["kind"], m.get("url"), hashlib.sha256(str(m.get("svg_markup")).encode()).hexdigest(), round(r["x"]), round(r["y"]), round(r["width"]), round(r["height"])), m)
    return list(placed.values()), list(loose.values())


def _marks_rule(rule: dict, measures: dict, ctx: Ctx) -> dict:
    """max-marks-per-view: in the screens of mark_windows, the most identified brand marks (see `identified_marks`) in one; a mark is in a window when the vertical middle of its box is.
    Read from the marks every view already holds, so it needs nothing of the browser. Marks of every width and scheme are counted view by view."""
    views = [v for v in measures.get("views", []) if isinstance(v, dict) and not v.get("error") and "marks" in v]
    if not views:
        return {"skipped": "no view was measured (see the page:load rows)"}
    hashes = set(logo_files(ctx.project, ctx.rules).values())
    most: dict | None = None
    loose: dict[str, dict] = {}
    cut = []
    for v in views:
        placed, unplaced = _placed_marks(v, hashes)
        loose.update({m["sel"]: m for m in unplaced})
        if v.get("marks_total") or v.get("images_total"):
            cut.append(f"{v.get('marks_total', 0)} marks and {v.get('images_total', 0)} other images over the caps at {v.get('width')} px")
        for top, bottom in mark_windows(v.get("height"), (v.get("viewport") or {}).get("height")):
            inside = [m for m in placed if top <= m["rect"]["y"] + m["rect"]["height"] / 2 <= bottom]
            if most is None or len(inside) > most["count"]:
                most = {"count": len(inside), "width": v.get("width"), "scheme": v.get("scheme"), "top": top, "bottom": bottom,
                        "marks": [{"selector": m["sel"], "kind": m["kind"], "y": round(m["rect"]["y"], 1), "height": round(m["rect"]["height"], 1)} for m in inside]}
    assert most is not None
    notes = [f"NOT verified: {sel}: its box cannot be placed on the page (a pseudo-element)" for sel in sorted(loose)]
    if cut:
        notes.append("NOT verified beyond the first marks and images of a view: " + _names(cut, 2))
    limit = rule["max"]
    where = f"at {most['width']} px {most['scheme']}, {most['top']:g} to {most['bottom']:g} px down the page"
    extra = {"max": limit, "most_in_one_screen": most["count"], "screen": {k: most[k] for k in ("width", "scheme", "top", "bottom")}, "marks": most["marks"]}
    if most["count"] > limit:
        names = _names([f"{m['selector']} ({m['y']:g} px down)" for m in most["marks"]], NAMED)
        return {"problems": [f"{most['count']} brand marks in one screen, the rule allows {limit}: {names}; first seen {where}"], "notes": notes, "extra": extra}
    seen = "no brand mark is shown on this page" if not most["count"] and not notes else f"at most {most['count']} brand mark(s) in one screen ({where})"
    return {"summary": f"{seen}; the rule allows {limit}", "notes": notes, "extra": extra}


def _facts_of(rule: dict, measures: dict) -> tuple[list[tuple[dict, dict]], str | None]:
    """The facts the browser collected for one rule, one per rendered view that holds them: -> ([(view, facts)], the browser's complaint about the rule's selector, or None)."""
    found = [(v, v["rule_facts"][rule["id"]]) for v in measures.get("views", [])
             if isinstance(v, dict) and not v.get("error") and isinstance(v.get("rule_facts"), dict) and isinstance(v["rule_facts"].get(rule["id"]), dict)]
    complaint = next((f["error"] for _, f in found if f.get("error")), None)
    return found, complaint


def _words_rule(rule: dict, measures: dict, ctx: Ctx) -> dict:
    """max-words-per-control: no `button`, `[role=button]`, `input[type=submit|button|reset]` (nor element of the rule's `selector`) says more than `max` words (visible text, else the accessible name)."""
    found, complaint = _facts_of(rule, measures)
    if complaint:
        return {"error": complaint}
    if not found:
        return {"skipped": "no view was measured (see the page:load rows)"}
    limit = rule["max"]
    over: dict[tuple, dict] = {}
    checked = longest = 0
    for v, facts in found:
        checked = max(checked, int(facts.get("shown") or 0))
        for it in facts.get("items", []):
            longest = max(longest, int(it["words"]))
            if it["words"] > limit:
                over.setdefault((it["sel"], it["text"]), {"selector": it["sel"], "text": it["text"], "words": it["words"], "via": it.get("via"), "width": v.get("width"), "scheme": v.get("scheme")})
    extra = {"max": limit, "controls_checked": checked, "longest": longest, "offenders": list(over.values())[:100]}
    if over:
        items = [f"{o['selector']} \"{o['text']}\" says {o['words']} words; first seen at {o['width']} px {o['scheme']}" for o in over.values()]
        return {"problems": [f"{len(over)} control(s) say more than {limit} word(s): " + _names(items, NAMED)], "extra": extra}
    what = "control" + ("" if checked == 1 else "s")
    return {"summary": (f"{checked} {what} on the page, the longest says {longest} word(s); the rule allows {limit}" if checked
                        else f"no shown control matches on this page; the rule allows {limit} word(s)"), "extra": extra}


def _bound(rule: dict) -> str:
    lo, hi = rule.get("min"), rule.get("max")
    return f"{lo} to {hi}" if lo is not None and hi is not None and lo != hi else f"exactly {lo}" if lo is not None and lo == hi else f"at least {lo}" if lo is not None else f"at most {hi}"


def _accent_rule(rule: dict, measures: dict, ctx: Ctx) -> dict:
    """words-under-accent: for each element the rule's `selector` matches, the words of its parent's visible text minus its own are within `min` and `max`."""
    found, complaint = _facts_of(rule, measures)
    if complaint:
        return {"error": complaint}
    if not found:
        return {"skipped": "no view was measured (see the page:load rows)"}
    lo, hi = rule.get("min"), rule.get("max")
    off: dict[tuple, dict] = {}
    seen: dict[tuple, dict] = {}
    for v, facts in found:
        for it in facts.get("items", []):
            around = int(it["around_words"])
            seen.setdefault((it["sel"], it["text"], around), it)
            if (lo is not None and around < lo) or (hi is not None and around > hi):
                off.setdefault((it["sel"], it["text"], around), {"selector": it["sel"], "text": it["text"], "parent": it.get("parent_sel"), "parent_text": it.get("parent_text"),
                                                               "own_words": it.get("own_words"), "around_words": around, "width": v.get("width"), "scheme": v.get("scheme")})
    extra = {"min": lo, "max": hi, "accents_checked": len(seen), "offenders": list(off.values())[:100]}
    if off:
        items = [f"{o['selector']} \"{o['text']}\" has {o['around_words']} word(s) around it in \"{o['parent_text']}\"; first seen at {o['width']} px {o['scheme']}" for o in off.values()]
        return {"problems": [f"{len(off)} accent(s) with the wrong number of words around them, the rule asks for {_bound(rule)}: " + _names(items, NAMED)], "extra": extra}
    return {"summary": (f"{len(seen)} element(s) match {rule['selector']}, each with {_bound(rule)} word(s) around it" if seen
                        else f"{rule['selector']} matches no shown element on this page"), "extra": extra}


def _g4_state(project: Path) -> dict:
    """What the rules are tied to: whether G4 is recorded and the recorded "(rule)" lines of BRAND-STATE.md "Rules (G4)" (`adapt.view(project)["rules"]`, the list the adapters
    read). `error` when BRAND-STATE.md cannot be read."""
    try:
        recorded = bool(gate_recorded(project, "G4"))
        return {"recorded": recorded, "lines": _adapt().view(project)["rules"] if recorded else [], "error": None}
    except (CliError, OSError) as e:
        return {"recorded": False, "lines": [], "error": getattr(e, "message", None) or str(e)}


def _squash(text: str) -> str:
    return " ".join(str(text).split()).casefold()


# function words that say nothing of what a rule is about (English and Polish, the languages of the plugin's word lists); negations are not here: "no" and "nie" are part of the rule
TIE_STOP_WORDS = frozenset("a an the of to in on at by as is are be was were it its this that these those and or but for with per from if so "
                           "i w z ze we na do od po za o u ku to ta te ten jest są być oraz lub albo ale dla że się".split())
TIE_MIN_WORDS = 2                         # content words the g4 text needs when it is not a whole line


def _tie_body(text: str) -> str:
    """The words of a rule line without its "(rule)" marker, white space collapsed and case ignored."""
    return re.sub(r"^\(rule\)\s*", "", _squash(text))


def _tie(g4: dict, text: str) -> tuple[str | None, str]:
    """-> (the recorded G4 rule line that holds the rule's `g4` words, white space collapsed and case ignored, or None; why there is none). The words are a meaningful part of the line:
    the whole line (the "(rule)" marker may be left out) or at least TIE_MIN_WORDS content words, so "rule" (the marker of every line) or "mark" ties nothing."""
    if g4["error"]:
        return None, f"BRAND-STATE.md cannot be read ({g4['error']}), so the rule is not a recorded G4 rule line yet"
    if not g4["recorded"]:
        return None, f"G4 is not recorded yet, so \"{text}\" is not a recorded G4 rule line yet"
    want = _tie_body(text)
    content = [w for w in re.findall(r"\w+", want) if w not in TIE_STOP_WORDS]
    bodies = [(ln, _tie_body(ln)) for ln in g4["lines"]]
    line = next((ln for ln, body in bodies if want and want == body), None)
    if line is None and len(content) >= TIE_MIN_WORDS:
        whole_words = re.compile(rf"(?<!\w){re.escape(want)}(?!\w)")   # whole words of the line, not a piece of a longer word ("art direction" is not in "smart directions")
        line = next((ln for ln, body in bodies if whole_words.search(body)), None)
    if line:
        return line, ""
    if len(content) < TIE_MIN_WORDS:
        return None, (f"\"{text}\" is too short to tie the rule to a line: write at least {TIE_MIN_WORDS} content words of the \"(rule)\" line of BRAND-STATE.md Rules (G4), or the whole line; "
                      "it is not a recorded G4 rule line yet")
    return None, f"no \"(rule)\" line of BRAND-STATE.md Rules (G4) holds \"{text}\": it is not a recorded G4 rule line yet"


def rule_rows(rep: Report, measures: dict, ctx: Ctx) -> None:
    """page:rule:<id>, one per entry of qa/rules.json page.rules: the brand's own rules for pages, each tied by its `g4` words to a "(rule)" line of BRAND-STATE.md Rules (G4).
    A broken rule fails when its `g4` words are in a recorded G4 rule line (G4 recorded) and only warns before that ("not a recorded G4 rule line yet"), so a proposal never fails a page;
    a rule that holds passes. Kinds: max-marks-per-view, max-words-per-control, words-under-accent and tell (a generic tell of page-tells.json is not found on the page). A selector the browser
    does not take as CSS fails its row whether or not the rule is tied: it cannot be judged. Something that could not be measured is "NOT verified", a warning."""
    rules = ctx.rules.get("page", {}).get("rules") or []
    if not rules:
        return
    g4 = _g4_state(ctx.project)
    check_tell_rules(rules)
    judges = {"max-marks-per-view": _marks_rule, "max-words-per-control": _words_rule, "words-under-accent": _accent_rule, "tell": _tell_rule}
    for rule in rules:
        rid, label = f"page:rule:{rule['id']}", f"brand rule: {rule['g4']}"
        res = judges[rule["kind"]](rule, measures, ctx)
        line, why = _tie(g4, rule["g4"])
        base = {"rule": rule, "tied": line is not None, "g4_line": line, **res.get("extra", {})}
        if "skipped" in res:
            rep.add(rid, "skipped", label, detail="not verified: " + res["skipped"], **base)
        elif "error" in res:
            rep.add(rid, "fail", label, detail=f"the selector {rule.get('selector')!r} is not valid CSS ({res['error']}): fix it in qa/rules.json page.rules", **base)
        elif res.get("problems"):
            if line:
                rep.add(rid, "fail", label, detail="; ".join(res["problems"] + res.get("notes", [])) + f"; the rule is tied to the recorded G4 line \"{line}\"", **base)
            else:
                rep.add(rid, "warn", label, detail="; ".join(res["problems"] + res.get("notes", [])) + f"; only a warning: {why}", **base)
        else:
            standing = f"a recorded G4 rule: \"{line}\"" if line else "not a recorded G4 rule line yet, so a break would only warn"
            if res.get("notes"):
                rep.add(rid, "warn", label, detail="; ".join([res["summary"]] + res["notes"]) + f"; {standing}", **base)
            else:
                rep.add(rid, "pass", label, detail=f"{res['summary']}; {standing}", **base)


# ---------------------------------------------------------------- the generic tells

TELLS_FILE = "skills/brand-creator/references/page-tells.json"
TELLS_CAP = 100                           # hits one tell row keeps in its `hits`
ELEMENT_CAP_NOTE = "NOT verified beyond the first elements of a view (the page has more than the check walks)"
TELL_NEEDS_WALK = ("middot-run", "styled-div-mock", "three-equal-tiles", "stray-box")   # the tells found by walking every element, which stops at a cap
SIDE_OF_PARENT = {"below": "below", "above": "above", "right": "to the right of", "left": "to the left of"}   # where a stray lies against its parent, as a phrase
EPSILON = 1e-6


def load_tells() -> dict:
    """skills/brand-creator/references/page-tells.json: the generic tells (`tells`), the languages their word lists cover (`languages`) and the notes (`notes`). Exit 3 when the file
    cannot be read: it ships with the plugin, so a damaged install is the only way."""
    f = plugin_root() / TELLS_FILE
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        fail(EXIT_CANNOT, f"{TELLS_FILE} cannot be read ({e}): reinstall the plugin")
    tells = doc.get("tells") if isinstance(doc, dict) else None
    if not (isinstance(tells, list) and tells and all(isinstance(t, dict) and isinstance(t.get("id"), str) for t in tells) and isinstance(doc.get("languages"), list)):
        fail(EXIT_CANNOT, f"{TELLS_FILE} is not a list of tells: reinstall the plugin")
    return doc


def tell_ids() -> list[str]:
    return [t["id"] for t in load_tells()["tells"]]


def check_tell_rules(page_rules: list[dict]) -> None:
    """A `tell` rule of qa/rules.json page.rules must name a tell of page-tells.json: exit 2 otherwise, before a page is opened."""
    known = tell_ids()
    for r in page_rules:
        if r.get("kind") == "tell" and r.get("tell") not in known:
            fail(EXIT_USAGE, f"{qa_rules.RULES_FILE}: page.rules ({r.get('id')}): {r.get('tell')!r} is not a generic tell (the tells are {', '.join(known)})")


def label_key(text: str) -> str:
    """A label as the stock lists are compared: letter case ignored, arrows, punctuation and runs of white space reduced to one space."""
    return " ".join(re.sub(r"[\W_]+", " ", str(text).casefold()).split())


def _widths(widths: list) -> str:
    seen = sorted(set(w for w in widths if isinstance(w, (int, float))))
    return ", ".join(f"{w:g}" for w in seen[:NAMED]) + (f" and {len(seen) - NAMED} more" if len(seen) > NAMED else "") + " px"


def _is_stray(c: dict, t: dict) -> bool:
    """A candidate of the stray-box tell is a hit when it lies outside its parent's box, or outside the viewport, by `min_outside_px` or more."""
    return any(c[k] is not None and c[k]["px"] >= t["min_outside_px"] - EPSILON for k in ("parent", "viewport"))


def _stray_text(c: dict, t: dict, at_tall: bool, tall_height) -> str:
    """What was seen of a stray, in words: where it lies against its parent and against the screen, and that it is still shown once the page has settled."""
    parts = []
    if c["parent"] is not None and c["parent"]["px"] >= t["min_outside_px"] - EPSILON:
        parts.append(f"{c['parent']['px']:g} px {SIDE_OF_PARENT[c['parent']['side']]} its parent {c['parent']['sel']}")
    if c["viewport"] is not None and c["viewport"]["px"] >= t["min_outside_px"] - EPSILON:
        parts.append(f"{c['viewport']['px']:g} px past the {c['viewport']['side']} edge of the screen")
    what = f"\"{c['text']}\" " if c["text"] else ""   # the hit line names the selector before this
    return f"{what}is still shown {' and '.join(parts)} after the page settled" + (f", in a window {tall_height:g} px high" if at_tall and tall_height else "")


def _stray_notes(unseen: dict[str, list], tall_height) -> list[str]:
    """The NOT verified notes of the stray-box tell. A view whose wait for the animations that end was cut off is not judged for it, and neither is a view that still has an animation running
    (one that never ends, or waits for a scroll: where it leaves its element is not known); an element that is still animating is not counted as a stray. A tall window the browser could not measure is said too."""
    notes = []
    def where(items: list) -> str:   # items are (width, at a tall window, ...)
        own, tall = [x[0] for x in items if not x[1]], [x[0] for x in items if x[1]]
        return ", and ".join(([_widths(own)] if own else []) + ([_widths(tall) + " in a tall window"] if tall else []))
    if unseen["capped"]:
        notes.append(f"NOT verified at {where(unseen['capped'])}: the page's animations were still running when the check stopped waiting for them, so what they leave on the page was not judged")
    if unseen["running"]:
        n = max(x[2] for x in unseen["running"])
        notes.append(f"NOT verified at {where(unseen['running'])}: {n} animation(s) never end or wait for a scroll, so where they leave their elements was not judged"
                     + (f" (still animating: {_names(sorted(set(unseen['animating'])), NAMED)})" if unseen["animating"] else ""))
    elif unseen["animating"]:
        notes.append(f"NOT verified: still animating after the page settled, so where it ends was not judged: {_names(sorted(set(unseen['animating'])), NAMED)}")
    for width, why, height in unseen["tall"]:
        notes.append(f"NOT verified at {width} px in a window {height or 'a tall'} px high: {why}")
    return notes


def find_tells(measures: dict, cfg: dict) -> dict:
    """Apply the thresholds and word lists of page-tells.json to the candidates each view holds (`tell_facts`, see page_measure.mjs). -> {"views": the number of views judged,
    "hits": {tell id: [hit]} (a hit is {selector, text, widths}, the same place in other views merged), "unverified": {tell id: [reason]}, "anatomy": {...} or None}."""
    th = {t["id"]: t.get("threshold") or {} for t in cfg["tells"]}
    stock = {t["id"]: t.get("words") or {} for t in cfg["tells"]}
    note = next((n for n in cfg.get("notes", []) if n.get("id") == "stock-anatomy"), {})
    languages = [str(x) for x in cfg["languages"]]
    views = [v for v in measures.get("views", []) if isinstance(v, dict) and not v.get("error") and isinstance(v.get("tell_facts"), dict)]
    merged: dict[tuple, dict] = {}
    unverified: dict[str, list[str]] = {t["id"]: [] for t in cfg["tells"]}
    stock_langs: set[str] = set()
    anatomy = None
    stray_unseen: dict[str, list] = {"capped": [], "running": [], "animating": [], "tall": []}   # what the stray-box tell could not judge: see _stray_notes
    stray_tall_height = None

    def add(tid: str, key, view: dict, selector: str, text: str) -> None:
        h = merged.setdefault((tid, key), {"selector": selector, "text": text, "widths": []})
        if view.get("width") not in h["widths"]:
            h["widths"].append(view.get("width"))

    for v in views:
        f, width = v["tell_facts"], v.get("width") or 0
        t = th["eyebrow"]
        for c in f.get("eyebrow", []):
            if c["words"] <= t["max_words"] and (c["uppercase"] or c["letter_spacing_em"] >= t["min_letter_spacing_em"] - EPSILON) and c["font_size_px"] < c["heading_font_size_px"]:
                how = "in capitals" if c["uppercase"] else f"letter-spaced {c['letter_spacing_em']:g} em"
                add("eyebrow", (c["sel"], c["text"]), v, c["sel"], f"\"{c['text']}\", {how}, {c['font_size_px']:g} px over the {c['heading_tag']} {c['heading_sel']} at {c['heading_font_size_px']:g} px")
        t = th["arrow-glued"]
        for c in f.get("arrows", []):
            if c["gap_chars"] <= t["max_gap_chars"]:
                add("arrow-glued", (c["sel"], c["label"]), v, c["sel"], f"\"{c['label']}\" has {c['glyph']} at its {c['edge']}")
        t = th["middot-run"]
        for c in f.get("separators", []):
            if c["count"] >= t["min_separators"]:
                add("middot-run", (c["sel"], c["via"]), v, c["sel"], f"{c['count']} separating dots" + (" in its text: " + f"\"{c['text']}\"" if c["via"] == "text" else " between its children"))
        hero = f.get("hero") or {}
        t = th["hero-text-budget"]
        if hero.get("found") and hero["words"] > t["max_words"]:
            add("hero-text-budget", hero["sel"], v, hero["sel"], f"{hero['words']} words in the first screen (at most {t['max_words']})")
        actions = hero.get("actions") or []
        page_lang = _primary_language(v.get("lang") or "")
        if page_lang not in languages:
            stock_langs.add(page_lang)
        if len(actions) > 1:
            a = actions[1]
            lang = _primary_language(a.get("lang") or v.get("lang") or "")
            if lang not in languages:
                stock_langs.add(lang)
            elif label_key(a["label"]) in {label_key(w) for w in stock.get("stock-second-action", {}).get(lang, [])}:
                add("stock-second-action", a["sel"], v, a["sel"], f"the second action of the hero says \"{a['label']}\"")
        t = th["styled-div-mock"]
        boxes = f.get("boxes", [])
        parent = {b["id"]: b.get("parent") for b in boxes}
        meets = {}
        for b in boxes:
            media = b["media_px"]
            pictured = any(n in media for n in ("canvas", "video")) or any(media.get(n, 0) > t["max_icon_px"] for n in ("img", "svg", "picture"))   # an img, svg or picture this small is an icon
            section = b["h1"] > 0 or b["headings"] > t["max_headings"]   # the page, or a band of it, and not a drawing in it
            # a list excuses a box only when the box is the list, or the items of the lists are nearly all of it: all its styled parts but at most one, or most of its area (the area of the items themselves, not of a list stretched past them)
            listed = b["in_lists"] > 0 and (b["styled"] - b["in_lists"] <= t["max_unlisted_styled"] or b["list_area"] >= t["min_list_area_ratio"] * b["width"] * b["height"] - EPSILON)
            # a table is data, a badge in one of its cells too: the box is a table or a table section, or every styled part of it sits in a cell
            tabular = b["table"] or (b["in_cells"] > 0 and b["styled"] == b["in_cells"])
            if b["width"] >= t["min_width_px"] and b["height"] >= t["min_height_px"] and b["styled"] >= t["min_styled_descendants"] and not (pictured or section or listed or tabular or b["labelled"]):
                meets[b["id"]] = b
        outer = set()
        for i in meets:
            p = parent.get(i)
            while p is not None and p not in outer:
                outer.add(p)
                p = parent.get(p)
        for i, b in meets.items():
            if i not in outer:
                add("styled-div-mock", b["sel"], v, b["sel"], f"a box of {b['width']:g} x {b['height']:g} px made of {b['styled']} styled boxes, with no image over {t['max_icon_px']:g} px")
        t = th["three-equal-tiles"]
        rows = []
        if width >= t["min_viewport_px"]:
            for g in f.get("tiles", []):
                ts = sorted(g["tiles"], key=lambda x: x["left"])
                tol = t["width_tolerance_px"]
                in_row = all(ts[i + 1]["left"] >= ts[i]["left"] + ts[i]["width"] - tol for i in range(2)) and max(x["top"] for x in ts) < min(x["top"] + x["height"] for x in ts)
                widths, heights = [x["width"] for x in ts], [x["height"] for x in ts]
                if in_row and max(widths) - min(widths) <= tol + EPSILON and max(heights) > 0 and min(heights) / max(heights) >= t["min_height_ratio"] - EPSILON:
                    rows.append((min(x["top"] for x in ts), g))
                    add("three-equal-tiles", g["sel"], v, g["sel"], f"three tiles of {widths[0]:g} px side by side, each with a heading")
        t = th["stray-box"]
        walks = [(False, f.get("strays", []), v.get("animations"))]   # (at a tall window, the candidates, the animations the wait left running): the view's own walk first, then the tall one
        tall = f.get("strays_tall")
        if isinstance(tall, dict):
            if tall.get("error"):
                stray_unseen["tall"].append((width, tall["error"], (tall.get("viewport") or {}).get("height")))
            else:
                walks.append((True, tall.get("strays", []), tall.get("animations")))
                if tall.get("truncated") and ELEMENT_CAP_NOTE not in unverified["stray-box"]:
                    unverified["stray-box"].append(ELEMENT_CAP_NOTE)
                stray_tall_height = (tall.get("viewport") or {}).get("height") or stray_tall_height
        standing: set[str] = set()   # what the view's own walk counted as a hit: the tall walk adds only what it alone shows
        for at_tall, strays, anim in walks:
            anim = anim if isinstance(anim, dict) else {}
            if anim.get("capped"):
                stray_unseen["capped"].append((width, at_tall))
            elif anim.get("running"):
                stray_unseen["running"].append((width, at_tall, anim["running"]))
            for c in strays:
                if not _is_stray(c, t) or (at_tall and c["sel"] in standing):
                    continue
                if c["animating"]:
                    stray_unseen["animating"].append(c["sel"])
                elif not anim.get("capped"):
                    add("stray-box", (c["sel"], at_tall), v, c["sel"], _stray_text(c, t, at_tall, stray_tall_height))
                    standing.add(c["sel"])
        if f.get("truncated"):
            for tid in TELL_NEEDS_WALK:
                if ELEMENT_CAP_NOTE not in unverified[tid]:
                    unverified[tid].append(ELEMENT_CAP_NOTE)
        if anatomy is None and hero.get("found") and rows and f.get("last_band"):
            tiles_top = min(r[0] for r in rows)
            faq_words = {label_key(w) for ws in (note.get("words") or {}).values() for w in ws}
            faq = [d["top"] for d in f.get("details", [])] + [h["top"] for h in f.get("headings", [])
                                                              if any(label_key(h["text"]) == w or label_key(h["text"]).startswith(w + " ") for w in faq_words)]
            band, limit = f["last_band"], (note.get("threshold") or {}).get("cta_max_words", 40)
            if faq and band["headings"] >= 1 and band["actions"] >= 1 and band["words"] <= limit:
                faq_top = min(x for x in faq if x > tiles_top) if any(x > tiles_top for x in faq) else None
                if faq_top is not None and hero["top"] < tiles_top < faq_top < band["top"]:
                    anatomy = {"view": f"{v.get('width')}-{v.get('scheme')}", "hero": hero["top"], "tiles": tiles_top, "faq": faq_top, "closing_band": band["top"]}
    if stock_langs:
        shown = ", ".join(sorted(k or "an unknown language (the page sets no lang)" for k in stock_langs))
        unverified["stock-second-action"].append(f"NOT verified: no word list for {shown} (only {' and '.join(languages)} are listed)")
    unverified["stray-box"].extend(_stray_notes(stray_unseen, stray_tall_height))
    hits: dict[str, list[dict]] = {t["id"]: [] for t in cfg["tells"]}
    for (tid, _), h in merged.items():
        hits[tid].append(h)
    return {"views": len(views), "hits": hits, "unverified": unverified, "anatomy": anatomy}


def _hit_line(h: dict) -> str:
    return f"{h['selector']}: {h['text']} (at {_widths(h['widths'])})"


def _tell_rule(rule: dict, measures: dict, ctx: Ctx) -> dict:
    """kind `tell`: the generic tell the rule names is not found on the page. Judged from the same candidates and thresholds as tell:<id>; the rule decides whether a hit warns or fails."""
    cfg = load_tells()
    found = find_tells(measures, cfg)
    if not found["views"]:
        return {"skipped": "no view was measured (see the page:load rows)"}
    t = next(x for x in cfg["tells"] if x["id"] == rule["tell"])
    hits, notes = found["hits"][t["id"]], found["unverified"][t["id"]]
    extra = {"tell": t["id"], "hits": hits[:TELLS_CAP]}
    if hits:
        return {"problems": [f"{len(hits)} found of the tell \"{t['name']}\": " + _names([_hit_line(h) for h in hits], NAMED)], "notes": notes, "extra": extra}
    return {"summary": f"none found of the tell \"{t['name']}\" in {found['views']} view(s)", "notes": notes, "extra": extra}


def tell_rows(rep: Report, measures: dict, ctx: Ctx) -> None:
    """tell:<id>, one per generic tell of page-tells.json that no brand rule has adopted: a warning naming up to six hits (selector, what was seen, the widths) or a pass, never a failure.
    A page in a language the word lists do not cover warns "NOT verified" on tell:stock-second-action. A tell the owner adopted in qa/rules.json page.rules is judged by its page:rule:<id> row
    instead. note:stock-anatomy (info) says when one view shows a hero, three equal tiles, an FAQ and a closing call-to-action band in that order."""
    cfg = load_tells()
    adopted = {r["tell"] for r in ctx.rules.get("page", {}).get("rules", []) if r["kind"] == "tell"}
    found = find_tells(measures, cfg)
    for t in cfg["tells"]:
        if t["id"] in adopted:
            continue
        rid, label = f"tell:{t['id']}", t["name"]
        hits, notes = found["hits"][t["id"]], found["unverified"][t["id"]]
        if not found["views"]:
            rep.add(rid, "skipped", label, detail="not verified: no view was measured (see the page:load rows)", tell=t["id"])
        elif hits:
            rep.add(rid, "warn", label, detail="; ".join([f"{len(hits)} found: " + _names([_hit_line(h) for h in hits], NAMED), t["why"]] + notes), tell=t["id"], hits=hits[:TELLS_CAP])
        elif notes:
            rep.add(rid, "warn", label, detail="; ".join(notes), tell=t["id"], hits=[])
        else:
            rep.add(rid, "pass", label, detail=f"none found in {found['views']} view(s)", tell=t["id"], hits=[])
    if found["anatomy"]:
        a = found["anatomy"]
        rep.add("note:stock-anatomy", "info", "the page follows the stock order of a product page",
                detail=f"at {a['view']} the page has a hero, three equal tiles, an FAQ and a closing call-to-action band, in that order, from the top of the page down; this is a note on the shape of the page, not a fault",
                anatomy=a)


# each (rep, measures, ctx); a later family of rows is added here
ROW_CHECKS = [load_rows, colour_rows, pair_rows, motion_rows, claim_rows, mark_rows, font_rows, display_size_rows, tell_rows, rule_rows]


def judge(rep: Report, measures: dict, ctx: Ctx, measures_path: Path) -> None:
    """Turn the measurements into the report: the target row, every family of rows, the project files the browser was served, and the keys written
    at the top level of the report (`target`, `widths`, `schemes`, `measures`, and what a family adds to ctx.extra)."""
    source = qa_rules.RULES_FILE if (ctx.project / qa_rules.RULES_FILE).is_file() else "proposals (no qa/rules.json)"
    rep.add("page:target", "info", "what was checked", detail=f"{ctx.target.describe()}; widths {', '.join(map(str, ctx.widths))}; "
                                                              f"schemes {', '.join(ctx.schemes)}; Chromium {measures.get('chromium', 'unknown')}; thresholds from {source}")
    for check in ROW_CHECKS:
        check(rep, measures, ctx)
    if ctx.target.kind == "project":
        rep.inputs.extend(served_project_files(ctx.project, measures))
    rep.extra.update({"target": ctx.target.as_report(), "widths": ctx.widths, "schemes": ctx.schemes, "measures": str(measures_path), **ctx.extra})

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

Standard library plus scripts/lib (_color, _common, qa_rules) only. This folder is outside scripts/lib/, so a change here does not make every pack stale. The
only reads are the project's own files and, with --from, the folder it names (read only: it is copied, never written).
"""
from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import qa_rules
from _color import parse_hex, wcag_ratio
from _common import CliError, EXIT_CANNOT, EXIT_USAGE, Report, confine, fail, rel, scratch_dir

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


def base_inputs(project: Path, target: Target) -> list[Path]:
    """The files every page check stands on: the built tokens (json and css), the rules, the facts and the state of the project, and the page (a project target)."""
    files = [project / TOKENS_FILE, project / TOKENS_CSS, project / qa_rules.RULES_FILE, project / "FACTS.md", project / "BRAND-STATE.md"]
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
    """The marks of one measured view: what the page marks (`data-brand-mark`), what is named like a logo, and any other image whose bytes are a logo file of the project. Each is the
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

    A mark is an element with `data-brand-mark`, an image whose file name says it is one (`logo`, `favicon`, `wordmark`, `lockup`, or `mark` as a word), or any image whose bytes are
    a file of assets/logo/ (see `identified_marks`). Only a mark that is shown is judged.
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
        rep.add("page:mark-file", "info", "the brand mark", detail="no brand mark is shown on this page: a mark is an element with data-brand-mark, an image whose file name says logo, "
                "mark, wordmark, lockup or favicon, or an image whose bytes are a logo file of the project" + hidden + ("; " + truncated if truncated else ""))
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


# each (rep, measures, ctx); the later families of rows (fonts, motion, claims, rules, tells) are added here
ROW_CHECKS = [load_rows, colour_rows, pair_rows, mark_rows]


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

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
`font_rows` gives `page:fonts` (every text is set in a family a `font.*` token names, and the browser drew it in that face) and `display_size_rows` gives `page:display-size`
(the display face is never set under `page.display_min_px`).

Standard library plus scripts/lib (_color, _common, qa_rules) only. This folder is outside scripts/lib/, so a change here does not make every pack stale. The
only reads are the project's own files and, with --from, the folder it names (read only: it is copied, never written).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
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
    seen = set()
    smallest = None
    truncated = []
    for v in views:
        if v.get("font_usage_total"):
            truncated.append(f"{v['font_usage_total']} fonts at {v.get('width')} px {v.get('scheme')}, {len(v['font_usage'])} measured")
        for u in v["font_usage"]:
            if family_key(u.get("family", "")) != family_key(face):
                continue
            px = float(u.get("min_px") or 0)
            seen.add((u.get("weight"), u.get("style")))
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


# each (rep, measures, ctx); the later families of rows (marks, motion, claims, rules, tells) are added here
ROW_CHECKS = [load_rows, colour_rows, pair_rows, font_rows, display_size_rows]


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

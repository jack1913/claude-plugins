"""Helpers shared by the emitters: the web and social ones use the small functions at the top, the platform emitters
(apple, windows, linux, tray, tauri, wallet, developer) are built on the `Emit` class below."""
from __future__ import annotations

import argparse
import base64
import html
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
RENDER_TIMEOUT_S = 150  # seconds for one card render
sys.path.insert(0, str(HERE.parent / "lib"))
sys.path.insert(0, str(HERE))
import qa_rules  # noqa: E402
import specs  # noqa: E402
import svgtools  # noqa: E402
from _common import (EXIT_CANNOT, EXIT_FAIL, EXIT_USAGE, Parser, Report, add_project_arg, add_renderer_arg, confine, data_dir, fail,  # noqa: E402,F401
                     find_project, plugin_root, rasterise_svg, read_state, require_gate, today)
from manifest import Manifest  # noqa: E402
from mark_lint import lint_svg_text  # noqa: E402


def add_common_args(ap) -> None:
    add_project_arg(ap)
    add_renderer_arg(ap)
    ap.add_argument("--svg", help="mark SVG for light grounds (default: assets/logo/mark.svg)")
    ap.add_argument("--svg-dark", help="mark SVG for dark grounds (default: assets/logo/mark-dark.svg when it exists)")
    ap.add_argument("--tokens", help="built tokens.json (default: assets/tokens/tokens.json)")
    ap.add_argument("--mark", help="the mark to draw, by its id in qa/rules.json marks (needed when the project lists several marks)")


def load_mark(project: Path, a, mark: dict | None = None) -> tuple[str, str | None, list[Path]]:
    """The light and dark artwork of the mark: the --mark entry's main drawing (its last band) and the -dark.svg next to it, else --svg
    and --svg-dark, else assets/logo/mark.svg and mark-dark.svg. -> (light text, dark text or None, the files read)."""
    if mark:
        light = confine(project, qa_rules.master_of(mark), what=f"mark {mark['id']!r} drawing")
        if not light.is_file():
            fail(EXIT_USAGE, f"mark {mark['id']!r}: its drawing {qa_rules.master_of(mark)} does not exist (the last band in qa/rules.json marks)")
        dark = confine(project, light.with_name(light.stem + "-dark.svg"), what="dark drawing")
    else:
        light = confine(project, a.svg or "assets/logo/mark.svg", what="--svg")
        if not light.is_file():
            fail(EXIT_USAGE, f"mark SVG not found: {light.relative_to(project)} (pass --svg)")
        dark = confine(project, a.svg_dark or "assets/logo/mark-dark.svg", what="--svg-dark" if a.svg_dark else "dark drawing")
        if a.svg_dark and not dark.is_file():
            fail(EXIT_USAGE, f"--svg-dark not found: {a.svg_dark}")
    paths = [light] + ([dark] if dark.is_file() else [])
    texts = [p.read_text(encoding="utf-8") for p in paths]
    for p, t in zip(paths, texts):
        problems = lint_svg_text(t)
        if problems:
            fail(EXIT_FAIL, f"mark_lint: {p.relative_to(project)} is not pure vector ({'; '.join(problems)}); outline text first")
    return texts[0], (texts[1] if len(texts) > 1 else None), paths


def load_tokens(project: Path, a) -> tuple[dict, Path]:
    f = confine(project, a.tokens or "assets/tokens/tokens.json", what="--tokens")
    if not f.is_file():
        fail(EXIT_CANNOT, f"{f.relative_to(project)} not found; run `brand-creator tokens` first")
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
        modes = {m: {k: v["hex"] for k, v in doc["modes"][m].items()} for m in ("light", "dark")}
    except (ValueError, KeyError) as e:
        fail(EXIT_USAGE, f"{f}: not a brand-creator tokens.json ({e})")
    return modes, f


def require_tier(project: Path, tiers: tuple[str, ...], *, what: str) -> None:
    """A pack that belongs to a tier is built only in it: the tier is the scope the owner agreed. Exit 2 names the way up."""
    tier = str(read_state(project).get("tier") or "")
    if tier not in tiers:
        fail(EXIT_USAGE, f"{what} is part of the {' and '.join(tiers)} tier(s); this project's tier is {tier or 'not set'!r}. "
                         f"With the owner's agreement raise it: brand-creator state --set tier={tiers[0]}")


_REPO_URL = re.compile(r"https?://(?:www\.)?(?:github\.com|gitlab\.com|codeberg\.org|bitbucket\.org)/[\w.-]+/[\w.-]+", re.I)
_REPO_SURFACE = re.compile(r"\b(readme|github|gitlab|repo|repository|repositories|social preview)\b", re.I)


def lists_repository(project: Path) -> str | None:
    """Why this project has a code repository (a reason, in words), or None. The GitHub social preview and the README headers
    are for software projects: INVENTORY.md lists a repository row, or brief/BRIEF.md names a repository URL, a Repository
    bullet with a value, or a README/GitHub surface among its required surfaces."""
    inv = project / "INVENTORY.md"
    if inv.is_file():
        in_targets = False
        for ln in inv.read_text(encoding="utf-8").splitlines():
            if ln.startswith("## "):
                in_targets = ln.lower().startswith("## targets")
            elif in_targets and ln.startswith("|") and not re.match(r"^\|\s*(repo\b|-)", ln, re.I):
                cell = ln.strip("|").split("|")[0].strip()
                if cell and not cell.startswith("("):
                    return f"INVENTORY.md lists the repository {cell!r}"
    brief = project / "brief" / "BRIEF.md"
    if brief.is_file():
        text = brief.read_text(encoding="utf-8")
        m = _REPO_URL.search(text)
        if m:
            return f"brief/BRIEF.md names the repository {m.group(0)}"
        for ln in text.splitlines():
            m = re.match(r"^\s*[-*]\s*(Repository|Repo|Required surfaces)\s*:\s*(.*)$", ln, re.I)
            if not m or m.group(2).strip().startswith("("):
                continue
            if m.group(1).lower() != "required surfaces" and m.group(2).strip().lower().rstrip(".") not in ("none", "no", "n/a"):
                return f"brief/BRIEF.md has a {m.group(1)} line"
            if m.group(1).lower() == "required surfaces" and _REPO_SURFACE.search(m.group(2)):
                return "brief/BRIEF.md lists a README or GitHub surface"
    return None


_NO_REGULATION = {"", "none", "no", "n/a", "na", "not regulated", "not applicable"}


def regulated_profession(project: Path) -> tuple[str | None, bool]:
    """-> (the profession text or None, answered). Reads the 'Regulated profession' bullet of brief/BRIEF.md. A bullet still holding the
    template's parenthesised placeholder is unanswered: the caller says so instead of assuming either way."""
    brief = project / "brief" / "BRIEF.md"
    if brief.is_file():
        for ln in brief.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*[-*]\s*Regulated profession\s*:\s*(.*)$", ln, re.I)
            if m:
                v = m.group(1).strip()
                if v.startswith("("):
                    return None, False
                return (None if v.lower().rstrip(".") in _NO_REGULATION else v), True
    return None, False


def need_colors(modes: dict, mode: str, *names: str) -> list[str]:
    missing = [n for n in names if n not in modes[mode]]
    if missing:
        fail(EXIT_FAIL, f"the {mode} tokens define no {', '.join(missing)}; the emitters need semantic tokens color.bg and color.text")
    return [modes[mode][n] for n in names]


def render_card(project: Path, html_rel: str, width: int, height: int, out_rel: str, scheme: str) -> dict:
    data_dir()
    cmd = ["node", str(plugin_root() / "scripts" / "render.mjs"), "card", html_rel, "--project", str(project),
           "--width", str(width), "--height", str(height), "--out", out_rel, "--scheme", scheme, "--json"]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=RENDER_TIMEOUT_S)
    except FileNotFoundError:
        fail(EXIT_CANNOT, "node not found on PATH (install Node 22+ and run /brand-creator:setup)")
    if cp.returncode != 0:
        fail(cp.returncode if cp.returncode in (1, 2, 3) else EXIT_CANNOT, (cp.stderr.strip() or cp.stdout.strip() or "render.mjs card failed"))
    return json.loads(cp.stdout.strip().splitlines()[-1])


# ====================================================================================================================
# The platform emitters
# ====================================================================================================================

@dataclass
class Drawing:
    """A drawing of the mark chosen for one body size: its SVG text, the project path it came from (None = the default mark)
    and the size band that named it (None when qa/rules.json defines no bands)."""
    svg: str
    rel: str | None
    band: str | None


def facts(project: Path) -> dict[str, str]:
    """FACTS.md rows as {fact label (lower case): value}. A label with no row is simply absent: emitters never invent a fact."""
    f = project / "FACTS.md"
    out: dict[str, str] = {}
    if not f.is_file():
        return out
    for line in f.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not line.lstrip().startswith("|") or set(line.replace("|", "").strip()) <= set("-: "):
            continue
        label, value = cells[0], cells[1]
        if label.lower() in ("fact", "(example)") or not value or label.lower().startswith("(example"):
            continue
        out.setdefault(label.lower(), value)
    return out


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def require_fact_text(project: Path, text: str, *, what: str) -> str:
    """`text` must be the value of a FACTS.md row (whitespace and case aside): copy on a store frame or in package metadata is a
    claim, and a claim needs an owner-confirmed row with a source."""
    if norm_text(text) not in {norm_text(v) for v in facts(project).values()}:
        fail(EXIT_FAIL, f"{what}: {text!r} is not a value in FACTS.md. Add it there with its source (and the owner's confirmation) first")
    return text


_TARGET = re.compile(r"^\s*[-*]\s*(iOS|iPadOS|macOS|watchOS|tvOS|visionOS)\s*:\s*(\d+(?:\.\d+)*)\s*$")


def deployment_targets(project: Path, overrides: list[str] | None = None) -> dict[str, str]:
    """Minimum OS versions the target repo supports: lines `- iOS: 17.0` in INVENTORY.md (section "Deployment targets"), overridden
    by `--target iOS=17.0`. Empty when neither says anything: then no legacy (pre-26) assets are written."""
    out: dict[str, str] = {}
    inv = project / "INVENTORY.md"
    if inv.is_file():
        for line in inv.read_text(encoding="utf-8").splitlines():
            m = _TARGET.match(line)
            if m:
                out[m.group(1)] = m.group(2)
    for ov in overrides or []:
        m = re.fullmatch(r"(iOS|iPadOS|macOS|watchOS|tvOS|visionOS)=(\d+(?:\.\d+)*)", ov)
        if not m:
            fail(EXIT_USAGE, f"--target {ov!r}: write it as iOS=17.0 (platform one of iOS, iPadOS, macOS, watchOS, tvOS, visionOS)")
        out[m.group(1)] = m.group(2)
    return out


def add_logo_arg(ap, *, cards: bool = False) -> None:
    """--logo-svg; the card and banner emitters (cards=True) also take --lettering, and their name falls back to typed text, never the mark."""
    if not cards:
        ap.add_argument("--logo-svg", help="the logo art for wide and text-bearing slots (default: assets/logo/lockup.svg, then wordmark.svg, then the mark)")
        return
    ap.add_argument("--logo-svg", help="the drawn lettering on the cards (default: assets/logo/lockup.svg, then wordmark.svg; "
                                       "without either the name is typed in the system font)")
    ap.add_argument("--lettering", choices=LETTERING_KINDS,
                    help="what --logo-svg holds: lockup (the mark and the name together, shown alone) or wordmark (the name alone, shown "
                         "next to the mark); needed when the file name says neither")
    for act in ap._actions:   # the Emit frame gives every emitter --name; on a card or banner it also replaces the drawn lettering
        if "--name" in act.option_strings:
            act.help = ("the name, typed in the system font instead of the drawn lettering (default: the drawn lockup or wordmark; "
                        "without either, the name in BRAND-STATE.md, typed)")


LETTERING_FILES = ("assets/logo/lockup.svg", "assets/logo/wordmark.svg")
LETTERING_KINDS = ("lockup", "wordmark")


def lettering_files(mark_id: str | None) -> tuple[str, str]:
    """Where the drawn lettering lives: assets/logo/lockup.svg and wordmark.svg, or <id>-lockup.svg and <id>-wordmark.svg for one of several marks."""
    return (f"assets/logo/{mark_id}-lockup.svg", f"assets/logo/{mark_id}-wordmark.svg") if mark_id else LETTERING_FILES


def lettering_art(project: Path, explicit: str | None, inputs: list, mark_id: str | None = None) -> tuple[str, str] | None:
    """The brand's drawn lettering: `explicit` (--logo-svg), else the lockup, else the wordmark (lettering_files); None when there is
    none. Always pure vector (mark_lint); the file is added to `inputs`. -> (svg text, project path)."""
    for c in [explicit] if explicit else lettering_files(mark_id):
        f = confine(project, c, what="--logo-svg")
        if f.is_file():
            text = f.read_text(encoding="utf-8")
            bad = lint_svg_text(text)
            if bad:
                fail(EXIT_FAIL, f"mark_lint: {c} is not pure vector ({'; '.join(bad)}); outline text first")
            if f not in inputs:
                inputs.append(f)
            return text, c
        if explicit:
            fail(EXIT_USAGE, f"--logo-svg not found: {c}")
    return None


def lettering_kind(rel: str, given: str | None) -> str:
    """lockup or wordmark: --lettering when given, else the file name (lockup.svg, acme-lockup.svg, wordmark.svg, wordmark-outlined.svg).
    A name that says neither or both stops the run (exit 2): the layout is never guessed."""
    if given:
        return given
    says = [k for k in LETTERING_KINDS if k in Path(rel).stem.lower()]
    if len(says) != 1:
        fail(EXIT_USAGE, f"{rel}: the file name does not say whether it is a lockup (the mark and the name together) or a wordmark (the name "
                         f"alone); pass --lettering lockup or --lettering wordmark")
    return says[0]


def card_lettering_setup(rep: Report, project: Path, a, template: str, template_name: str,
                         mark_id: str | None = None) -> tuple[tuple[str, str] | None, str]:
    """The lettering of a card or banner emitter -> (art or None, layout). --name types the name, so --logo-svg or --lettering next to it
    would be ignored: that pair stops the run (exit 2), and with --name no lettering file is read."""
    explicit, kind = a.logo_svg, a.lettering
    if a.name and (explicit or kind):
        fail(EXIT_USAGE, "--name types the name in the system font, so --logo-svg and --lettering would not be used: pass --name, or the drawn "
                         "lettering, not both")
    if kind and not explicit:
        fail(EXIT_USAGE, "--lettering says what --logo-svg holds: pass it together with --logo-svg")
    found = None if a.name else lettering_art(project, explicit, rep.inputs, mark_id)
    return found, lettering_layout(rep, found, template, template_name, bool(a.name), kind=kind, mark_id=mark_id)


def lettering_layout(rep: Report, found: tuple[str, str] | None, template: str, template_name: str, name_given: bool,
                     kind: str | None = None, mark_id: str | None = None) -> str:
    """How a card or banner sets the name, said in a report row: 'lockup' (the art holds the mark and the name: it stands alone), 'wordmark'
    (the drawn name next to the mark) or 'type' (the name as live text in the template's font). Type when --name was given (the art cannot
    say another name), when there is no lettering art, or when the template has no {{lettering}} placeholder outside its comments (a
    template written before 0.3.1). Lockup or wordmark comes from `kind` (--lettering), else from the file name (lettering_kind)."""
    slot = "{{lettering}}" in re.sub(r"<!--.*?-->", "", template, flags=re.S)
    if name_given:
        rep.add("note:lettering", "info", "the name is live text in the system font", detail="--name sets the name as text: the drawn lettering says the recorded name")
        return "type"
    if found is None:
        lockup, wordmark = lettering_files(mark_id)
        rep.add("note:lettering", "warn", "the name is live text in the system font",
                detail=f"there is no {lockup} or {Path(wordmark).name}: draw one (outlined, P6) and run this again for the brand's own lettering")
        return "type"
    if not slot:
        rep.add("note:lettering", "warn", "the name is live text in the template's font",
                detail=f"{template_name} has no {{{{lettering}}}} placeholder (a template from before 0.3.1): add it to show the drawn lockup or wordmark")
        return "type"
    layout = lettering_kind(found[1], kind)
    rep.add("note:lettering", "info", f"the name is the drawn {layout}", detail=f"{found[1]} ({'--lettering' if kind else 'by its file name'})")
    return layout


CARD_LOCKUP = 0.82, 0.34   # a drawn lockup on templates/card.html: at most this share of the card's width (inside the 9vw side padding) and height
CARD_WORDMARK = 0.1125     # a drawn wordmark's height as a share of the card's: 0.75 of the 15vh name, about the height of its caps
CARD_MARK = 0.58           # the mark's side on templates/card.html as a share of the card's height ...
CARD_MARK_CSS = "58vh"     # ... and the same share as the template writes it


def pixel_art(svg_text: str) -> bool:
    """Art drawn on a pixel grid: its root says shape-rendering="crispEdges" (the pixel engines write it). Wherever the plugin chooses the size
    (cards, banners, the side-by-side image), such art is scaled by whole numbers only, so every pixel stays square and the same size."""
    return svgtools.parse(svg_text).get("shape-rendering") == "crispEdges"


def whole_px(svg_text: str, side_px: float) -> int:
    """The side for a mark box of at most side_px: for pixel art the largest whole multiple of its grid (the longer viewBox side) that
    fits, at least 1x; for other art side_px rounded."""
    if pixel_art(svg_text):
        vb = svgtools.viewbox(svgtools.parse(svg_text))
        grid = max(vb[2], vb[3])
        if side_px >= grid:
            return int(grid * int(side_px // grid))
    return round(side_px)


def card_mark_size(svg_text: str, h: int) -> str:
    """{{mark_size}} of templates/card.html: 58vh, or for pixel art the whole-number size in px that fits there."""
    return f"{whole_px(svg_text, h * CARD_MARK)}px" if pixel_art(svg_text) else CARD_MARK_CSS


def mark_accent(modes: dict, mode: str, mark: dict | None, fg: str) -> str:
    """The cards' accent in `mode`: the token role the mark names (qa/rules.json marks.<id>.accent), else color.accent, else the text
    colour. A role the mark names that the tokens do not define stops the run (exit 1): it never falls back."""
    role = mark["accent"] if mark else ""
    if role:
        if role not in modes[mode]:
            fail(EXIT_FAIL, f"mark {mark['id']!r} names the accent {role}, which the {mode} tokens do not define")
        return modes[mode][role]
    return modes[mode].get("color.accent", fg)


def mark_tagline(project: Path, mark: dict | None, given: str, inputs: list) -> str:
    """The line under the name: --tagline when given, else the FACTS.md value of the mark's tagline label (qa/rules.json
    marks.<id>.tagline; a label FACTS.md does not have stops the run, exit 1), else nothing."""
    if given or not (mark and mark["tagline"]):
        return given
    f = project / "FACTS.md"
    if f.is_file() and f not in inputs:
        inputs.append(f)
    fx = facts(project)
    label = mark["tagline"].lower()
    if label not in fx:
        fail(EXIT_FAIL, f"mark {mark['id']!r}: its tagline label {mark['tagline']!r} is not in FACTS.md (labels: {', '.join(sorted(fx)) or 'none'})")
    return fx[label]


def card_lettering(layout: str, art: str | None, name: str, w: int, h: int) -> str:
    """{{lettering}} of templates/card.html at w x h: the drawn lockup or wordmark as an image sized to fit, or the name as an h1."""
    if layout == "lockup":
        return art_img(art, *fit_art(art, w * CARD_LOCKUP[0], h * CARD_LOCKUP[1]), name)
    if layout == "wordmark":
        return art_img(art, *fit_art(art, w * 0.82 - h * 0.64, h * CARD_WORDMARK), name)   # the width left beside the 58vh mark and the 6vh gap
    return f"<h1>{html.escape(name)}</h1>"


def fit_art(svg_text: str, max_w: float, max_h: float) -> tuple[int, int]:
    """The largest whole-pixel box of the art's viewBox proportions inside max_w x max_h; pixel art at a whole-number scale (pixel_art)."""
    vb = svgtools.viewbox(svgtools.parse(svg_text))
    if pixel_art(svg_text):
        k = int(min(max_w / vb[2], max_h / vb[3]))
        if k >= 1:
            return int(vb[2] * k), int(vb[3] * k)
    w, h = max_w, max_w * vb[3] / vb[2]
    if h > max_h:
        w, h = max_h * vb[2] / vb[3], max_h
    return max(1, int(w)), max(1, int(h))


def art_img(svg_text: str, w: int, h: int, alt: str) -> str:
    """The art as an <img> of a data URI: its own document, so its ids and styles cannot clash with the mark inlined in the same page."""
    data = base64.b64encode(svg_text.encode("utf-8")).decode("ascii")
    return f'<img class="lettering" alt="{html.escape(alt)}" width="{w}" height="{h}" src="data:image/svg+xml;base64,{data}">'


def dark_sibling(project: Path, src: str, inputs: list) -> str | None:
    """<stem>-dark.svg next to a lettering file, linted like it; None when there is none."""
    dark = str(Path(src).with_name(Path(src).stem + "-dark.svg"))
    f = confine(project, dark, what="dark lettering")
    if not f.is_file():
        return None
    text = f.read_text(encoding="utf-8")
    bad = lint_svg_text(text)
    if bad:
        fail(EXIT_FAIL, f"mark_lint: {dark} is not pure vector ({'; '.join(bad)}); outline text first")
    if f not in inputs:
        inputs.append(f)
    return text


def version_below(version: str, floor: int) -> bool:
    return int(version.split(".")[0]) < floor


class Emit:
    """The shared frame of a platform emitter: project, gate G3, marks, tokens, report, manifest, size bands and spec stamping.

        e = Emit.begin("windows", __doc__, add_args=lambda ap: ...)
        sz = e.sizes("windows-ico")                       # reads platform-specs.json and records the row as used
        d = e.drawing(size)                               # the drawing the band rule names for this body size
        e.slot("assets/windows/app.ico", data, ["windows-ico"], slot="windows-ico", size_px=256)
        return e.finish()
    """

    def __init__(self, name: str, a: argparse.Namespace, project: Path):
        self.name, self.a, self.project = name, a, project
        self.st = read_state(project).data()
        self.rules, self.rules_src = qa_rules.load(project)
        self.mark = qa_rules.select_mark(a, self.rules)   # one of several marks (qa/rules.json marks), or None
        self.mark_id = self.mark["id"] if self.mark else None
        self.brand = str(a.name or (self.mark["name"] if self.mark else None) or self.st.get("name") or self.st.get("slug"))
        self.slug = str(self.mark_id or self.st.get("slug") or self.brand).lower()
        self.light, self.dark, self.mark_paths = load_mark(project, a, self.mark)
        self.modes, self.tokens_path = load_tokens(project, a)
        self.out = (a.out_dir or (f"assets/{name}/{self.mark_id}" if self.mark else f"assets/{name}")).strip("/")
        self.bands = qa_rules.bands_for(self.rules, self.mark_id)
        self.favicon_drawing = self.mark["favicon"] if self.mark else self.rules["favicon"]["drawing"]
        self.rep = Report(f"emit-{name}" + (f"/{self.mark_id}" if self.mark else ""), project, self.mark_paths + [self.tokens_path], renderer=a.renderer)
        self.mf = Manifest(project)
        self.used: list[str] = []
        self.inputs_extra: list[Path] = []
        self.kept: list[str] = []   # folders under out/ this run deliberately skipped (an option): their earlier rows are not retired
        self.raster_renderer: str | None = None   # an emitter whose --renderer means something else (tauri: the .icns writer) sets "resvg"
        self.add_input(project / qa_rules.RULES_FILE)   # the band rule decides which drawing every slot uses

    # -- construction
    @classmethod
    def begin(cls, name: str, doc: str, add_args=None, argv: list[str] | None = None, preflight=None,
              tiers: tuple[str, ...] | None = None, tier_what: str = "") -> "Emit":
        ap = Parser(prog=f"brand-creator emit {name}", description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
        add_common_args(ap)
        ap.add_argument("--name", help="brand name (default: name in BRAND-STATE.md)")
        ap.add_argument("--out-dir", help=f"folder inside the project (default assets/{name}; with --mark, assets/{name}/<mark>)")
        if add_args:
            add_args(ap)
        a = ap.parse_args(argv)
        if preflight:
            preflight(a)   # e.g. a platform check: exit 3 before anything else when this machine cannot run the emitter
        project = find_project(a.project)
        require_gate(project, "G3", for_what=f"emit {name}")
        if tiers:
            require_tier(project, tiers, what=tier_what or f"the {name} pack")   # before the report exists: a refusal leaves no failing report behind
        return cls(name, a, project)

    def keep(self, *folders: str) -> None:
        """Name folders (relative to out) that this run skipped on purpose, e.g. `--no-cards`: files an earlier run wrote there stay."""
        self.kept += [f"{self.out}/{f.strip('/')}/" for f in folders]

    # -- inputs: every file an emitter reads is recorded in its report, so editing it makes the report stale
    def add_input(self, *paths: Path) -> None:
        for p in paths:
            if p.is_file() and p not in self.rep.inputs:
                self.rep.inputs.append(p)

    def facts(self) -> dict[str, str]:
        self.add_input(self.project / "FACTS.md")
        return facts(self.project)

    def require_fact(self, text: str, *, what: str) -> str:
        self.add_input(self.project / "FACTS.md")
        return require_fact_text(self.project, text, what=what)

    def targets(self) -> dict[str, str]:
        self.add_input(self.project / "INVENTORY.md")
        return deployment_targets(self.project, self.a.target)

    # -- specs
    def sizes(self, row_id: str) -> dict:
        if row_id not in self.used:
            self.used.append(row_id)
        return specs.sizes(row_id)

    # -- drawings and colours
    def drawing(self, size_px: int, *, band: str | None = None) -> Drawing:
        """The drawing for a body size: the band rule's pick (qa/rules.json), or the one named by `band`; the default mark when the
        project defines no bands. Naming a band other than the pick is allowed here and must be paid for in slot() with an exemption."""
        if not self.bands:
            if band:
                fail(EXIT_USAGE, f"band {band!r} was named but qa/rules.json defines no bands")
            return Drawing(self.light, None, None)
        if band:
            picked = next((b for b in self.bands if b["name"] == band), None)
            if picked is None:
                fail(EXIT_USAGE, f"unknown band {band!r} (defined: {', '.join(b['name'] for b in self.bands)})")
        else:
            picked = qa_rules.pick_band(self.bands, size_px)
        return self.drawing_file(picked["drawing"], f"band {picked['name']!r}", band=picked["name"])

    def drawing_file(self, rel: str, what: str, *, band: str | None = None) -> Drawing:
        """A drawing named by a rule (a band, favicon.drawing): an existing .svg in the project, pure vector, recorded as an input."""
        f = confine(self.project, rel, what=f"{what} drawing")
        if f.suffix.lower() != ".svg" or not f.is_file():
            fail(EXIT_USAGE, f"{what}: its drawing {rel} must be an existing .svg file")
        text = f.read_text(encoding="utf-8")
        problems = lint_svg_text(text)
        if problems:
            fail(EXIT_FAIL, f"mark_lint: {rel} is not pure vector ({'; '.join(problems)})")
        if f not in self.inputs_extra:
            self.inputs_extra.append(f)
            self.rep.inputs.append(f)
        return Drawing(text, rel, band)

    def dark_file(self, d: Drawing) -> str | None:
        """The drawn dark artwork of a drawing: its <name>-dark.svg sibling (the default mark: --svg-dark or mark-dark.svg); None when
        there is none (nothing is derived here)."""
        if not d.rel:
            return self.dark
        return self._drawn_dark(d.rel)

    def _drawn_dark(self, rel: str) -> str | None:
        """<name>-dark.svg next to a drawing: pure vector like it (exit 1 otherwise), recorded as an input; None when there is none."""
        cand = confine(self.project, str(Path(rel).with_suffix("")) + "-dark.svg", what="dark drawing")   # a symlink out of the project is refused
        if not cand.is_file():
            return None
        text = cand.read_text(encoding="utf-8")
        problems = lint_svg_text(text)
        if problems:
            fail(EXIT_FAIL, f"mark_lint: {str(Path(rel).with_suffix(''))}-dark.svg is not pure vector ({'; '.join(problems)}); outline text first")
        if cand not in self.inputs_extra:
            self.inputs_extra.append(cand)
            self.rep.inputs.append(cand)
        return text

    def check_master_band(self, size_px: int, band: str | None, exemption: str | None) -> None:
        """Fail early (exit 1) when `band` is not the one the picker names for size_px and no one-line exemption says why."""
        picked = qa_rules.pick_band(self.bands, size_px) if (band and self.bands) else None
        if picked and picked["name"] != band and not (exemption or "").strip():
            fail(EXIT_FAIL, f"--master-band {band} differs from band {picked['name']!r}, which the rule in qa/rules.json picks for {size_px} px; "
                            f"say why in --exemption (one line, recorded in the manifest)")

    def role_map(self) -> tuple[dict[str, str], set[str]]:
        """{light hex: dark hex} from the tokens' roles, and the light hexes that two roles send to different dark colours."""
        mapping: dict[str, str] = {}
        clash: set[str] = set()
        for role, lt in self.modes["light"].items():
            dk = self.modes["dark"].get(role)
            if dk is None or lt.lower() == dk.lower():
                continue
            if mapping.get(lt.lower(), dk.lower()) != dk.lower():
                clash.add(lt.lower())
            mapping[lt.lower()] = dk.lower()
        return mapping, clash

    def dark_svg(self, d: Drawing) -> str:
        """The dark-ground artwork of a drawing: its `<name>-dark.svg` sibling (or --svg-dark / mark-dark.svg for the default mark);
        else the light drawing recoloured through the tokens' light-to-dark roles (reported as a warning). A colour the tokens do not
        map fails: nothing is guessed."""
        if d.rel:
            drawn = self._drawn_dark(d.rel)
            if drawn is not None:
                return drawn
        elif self.dark is not None:
            return self.dark
        mapping, clash = self.role_map()
        try:
            need = svgtools.paint_colours(d.svg)
            bad = [c for c in need if c in clash]
            if bad:
                raise svgtools.SvgError(f"{', '.join(bad)} is used by two roles that differ in dark")
            out = svgtools.recolor(d.svg, mapping)
        except svgtools.SvgError as e:
            fail(EXIT_FAIL, f"no dark artwork for {d.rel or 'the mark'} and it cannot be derived from the tokens ({e}); "
                            f"draw {(str(Path(d.rel).with_suffix('')) + '-dark.svg') if d.rel else 'assets/logo/mark-dark.svg'}")
        self.rep.add(f"dark:{d.rel or 'mark'}", "warn", "dark artwork derived",
                     detail=f"no dark file next to {d.rel or 'the mark'}: its colours were mapped light to dark through the token roles")
        return out

    def logo_art(self) -> tuple[str, str]:
        """The logo art for wide or text-bearing slots: --logo-svg, else assets/logo/lockup.svg, else assets/logo/wordmark.svg, else the
        mark. Always pure vector. -> (svg text, the project path or 'the mark')."""
        found = lettering_art(self.project, getattr(self.a, "logo_svg", None), self.rep.inputs)
        return found if found else (self.light, "the mark")

    def colour(self, mode: str, role: str) -> str:
        if role not in self.modes[mode]:
            fail(EXIT_FAIL, f"the {mode} tokens define no {role}")
        return self.modes[mode][role]

    # -- pixels
    def tile_png(self, n: int, *, content: float, radius: float = 0.0, body: float = 1.0, ground: bool | str = True, mode: str = "light",
                 band: str | None = None, flat: bool = False) -> tuple[Drawing, bytes]:
        """An n x n icon tile: the drawing the band rule names for n (or `band`), in `mode` artwork, centred at `content` of the body, on the
        brand ground (`ground` True = color.bg of the mode, a #rrggbb, or False for none), corners rounded by `radius`, the body `body` of
        the canvas. `flat` makes the PNG fully opaque by painting the ground behind the whole canvas (the system masks it)."""
        d = self.drawing(n, band=band)
        art = d.svg if mode == "light" else self.dark_svg(d)
        bg = (self.colour(mode, "color.bg") if ground is True else ground) or None
        svg = svgtools.tile(art, n, n, bg=bg, content=content, body=body, radius=radius)
        return d, self.png(svg, n, n, bg=bg if flat else None)

    def png(self, svg: str, w: int, h: int, *, bg: str | None = None) -> bytes:
        return rasterise_svg(svg, w, h, renderer=self.raster_renderer or self.a.renderer, background=bg)

    # -- manifest + report
    def _row(self, rel: str, changed: bool, data: bytes, extra: dict) -> None:
        self.rep.add(f"file:{Path(rel).relative_to(self.out).as_posix() if rel.startswith(self.out + '/') else rel}", "pass",
                     "written" if changed else "unchanged", bytes=len(data), **{k: v for k, v in extra.items() if k in ("size", "band")})

    def put(self, rel: str, data: bytes, rows: list[str], **extra) -> bool:
        changed = self.mf.put(rel, data, emitter=self.name, specs=rows, **({"mark": self.mark_id} if self.mark_id else {}), **extra)
        self._row(rel, changed, data, extra)
        return changed

    def slot(self, rel: str, data: bytes, rows: list[str], *, slot: str, size_px: int | tuple[int, int], drawing: Drawing | None = None,
             exemption: str | None = None, **extra) -> bool:
        """Write a file that serves a size: records slot, size, band (the drawing's band, or the picker's) and who made the pixels."""
        band = drawing.band if drawing else None
        changed = self.mf.put_slot(rel, data, emitter=self.name, specs=rows, slot=slot, size_px=size_px, band=band, exemption=exemption,
                                   mark=self.mark_id, **extra)
        row = self.mf.artefacts[rel]
        self._row(rel, changed, data, row)
        return changed

    def finish(self) -> int:
        stamped, warns = specs.stamp(self.used, today())
        self.mf.stamp_specs(stamped)
        retired = self.mf.retire_unwritten(self.name, self.out, keep=lambda p: any(p.startswith(k) for k in self.kept), mark=self.mark_id)
        for p in retired:
            self.rep.add(f"retired:{p}", "warn", "slot no longer emitted",
                         detail=f"an earlier run wrote {p} but this run did not: "
                                + (f"the file was moved to {self.mf.retired_to[p]}/" if p in self.mf.retired_to else "its file was already gone")
                                + " and its manifest row dropped")
        self.mf.save()
        for w in warns:
            self.rep.add("spec", "warn", "platform spec", detail=w)
        self.rep.extra.update({"out_dir": self.out, "changed": self.mf.changed, "unchanged": self.mf.unchanged, "specs": stamped,
                               "rules_source": self.rules_src, "retired": retired})
        print(f"emit {self.name}: {len(self.mf.changed)} written, {len(self.mf.unchanged)} unchanged ({self.out}/)")
        return self.rep.finish()


def fill_template(template: str, values: dict, raw: tuple = ("mark",)) -> str:
    """Fill {{name}} placeholders (HTML-escaped unless the name is in `raw`); a placeholder left unfilled is an error, never a blank."""
    import html as _html
    out = template
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", str(v) if k in raw else _html.escape(str(v)))
    left = re.findall(r"\{\{[^}]*\}\}", out)
    if left:
        fail(EXIT_FAIL, f"template has unfilled placeholders {sorted(set(left))}; supported: {sorted(values)}")
    return out

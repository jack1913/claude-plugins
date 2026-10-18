"""Helpers shared by the emitters: the web and social ones use the small functions at the top, the platform emitters
(apple, windows, linux, tray, tauri, wallet, developer) are built on the `Emit` class below."""
from __future__ import annotations

import argparse
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


def load_mark(project: Path, a) -> tuple[str, str | None, list[Path]]:
    light = confine(project, a.svg or "assets/logo/mark.svg", what="--svg")
    if not light.is_file():
        fail(EXIT_USAGE, f"mark SVG not found: {light.relative_to(project)} (pass --svg)")
    dark = confine(project, a.svg_dark, what="--svg-dark") if a.svg_dark else project / "assets/logo/mark-dark.svg"
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


def add_logo_arg(ap) -> None:
    ap.add_argument("--logo-svg", help="the logo art for wide and text-bearing slots (default: assets/logo/lockup.svg, then wordmark.svg, then the mark)")


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
        self.brand = str(a.name or self.st.get("name") or self.st.get("slug"))
        self.slug = str(self.st.get("slug") or self.brand).lower()
        self.light, self.dark, self.mark_paths = load_mark(project, a)
        self.modes, self.tokens_path = load_tokens(project, a)
        self.out = a.out_dir.strip("/")
        self.rules, self.rules_src = qa_rules.load(project)
        self.bands = self.rules["bands"]
        self.rep = Report(f"emit-{name}", project, self.mark_paths + [self.tokens_path], renderer=a.renderer)
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
        ap.add_argument("--out-dir", default=f"assets/{name}", help=f"folder inside the project (default assets/{name})")
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
        f = confine(self.project, picked["drawing"], what=f"band {picked['name']!r} drawing")
        if f.suffix.lower() != ".svg" or not f.is_file():
            fail(EXIT_USAGE, f"band {picked['name']!r}: its drawing {picked['drawing']} must be an existing .svg file")
        text = f.read_text(encoding="utf-8")
        problems = lint_svg_text(text)
        if problems:
            fail(EXIT_FAIL, f"mark_lint: {picked['drawing']} is not pure vector ({'; '.join(problems)})")
        if f not in self.inputs_extra:
            self.inputs_extra.append(f)
            self.rep.inputs.append(f)
        return Drawing(text, picked["drawing"], picked["name"])

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
            cand = self.project / (str(Path(d.rel).with_suffix("")) + "-dark.svg")
            if cand.is_file():
                if cand not in self.inputs_extra:
                    self.inputs_extra.append(cand)
                    self.rep.inputs.append(cand)
                return cand.read_text(encoding="utf-8")
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
        cands = [self.a.logo_svg] if getattr(self.a, "logo_svg", None) else ["assets/logo/lockup.svg", "assets/logo/wordmark.svg"]
        for c in cands:
            f = confine(self.project, c, what="--logo-svg")
            if f.is_file():
                text = f.read_text(encoding="utf-8")
                bad = lint_svg_text(text)
                if bad:
                    fail(EXIT_FAIL, f"mark_lint: {c} is not pure vector ({'; '.join(bad)}); outline text first")
                if f not in self.rep.inputs:
                    self.rep.inputs.append(f)
                return text, c
            if getattr(self.a, "logo_svg", None):
                fail(EXIT_USAGE, f"--logo-svg not found: {c}")
        return self.light, "the mark"

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
        changed = self.mf.put(rel, data, emitter=self.name, specs=rows, **extra)
        self._row(rel, changed, data, extra)
        return changed

    def slot(self, rel: str, data: bytes, rows: list[str], *, slot: str, size_px: int | tuple[int, int], drawing: Drawing | None = None,
             exemption: str | None = None, **extra) -> bool:
        """Write a file that serves a size: records slot, size, band (the drawing's band, or the picker's) and who made the pixels."""
        band = drawing.band if drawing else None
        changed = self.mf.put_slot(rel, data, emitter=self.name, specs=rows, slot=slot, size_px=size_px, band=band, exemption=exemption, **extra)
        row = self.mf.artefacts[rel]
        self._row(rel, changed, data, row)
        return changed

    def finish(self) -> int:
        stamped, warns = specs.stamp(self.used, today())
        self.mf.stamp_specs(stamped)
        retired = self.mf.retire_unwritten(self.name, self.out, keep=lambda p: any(p.startswith(k) for k in self.kept))
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

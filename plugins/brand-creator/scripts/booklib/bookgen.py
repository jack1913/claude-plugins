"""The brand book generator (mark_source generated or existing): chapter files + data -> one self-contained book.html.

Reads tokens (built DTCG), assets/manifest.json, BRAND-STATE.md (edition, approval, decided items), FACTS.md, the contrast and
downscale reports and book/chapters/*.md. Writes nothing itself; book.py writes the bytes. No clock, no random numbers, no network:
the same inputs always give the same bytes. Standard library only (resvg is called for the mark-by-size proof images).
"""
from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path

import bookdata
import bookmd
import qa_rules
import svgtools
from _color import wcag_ratio
from _common import EXIT_FAIL, EXIT_USAGE, fail, rasterise_svg, sha256_file
from mark_lint import lint_svg_text

esc = bookmd.esc
FONT_MIME = {".woff2": ("font/woff2", "woff2"), ".woff": ("font/woff", "woff"), ".ttf": ("font/ttf", "truetype"), ".otf": ("font/otf", "opentype")}
IMG_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif", ".svg": "image/svg+xml"}
PROOF_TOOLS = ["tokens", "contrast", "logo-sheet", "states", "family", "fontcheck", "motion", "idempotence", "staleness"]
KIND_LABEL = {"ui-text": "text, WCAG 2.2 AA", "ui-text-large": "large text, WCAG 2.2 AA", "ui-component": "component, WCAG 2.2 AA",
              "brand-rule": "brand rule (logos WCAG-exempt)"}
DONTS = [("stretch", "Do not stretch or squash the mark."), ("rotate", "Do not rotate the mark."),
         ("recolour", "Do not recolour the mark outside the palette's roles."), ("ground", "Do not put the mark on its own colour."),
         ("crowd", "Do not crowd the mark: keep its clear space free.")]

CSS = """
:root{color-scheme:light dark;@@LIGHT@@}
@media (prefers-color-scheme:dark){:root{@@DARK@@}}
@@FACES@@
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-padding-top:72px}
body{margin:0;background:var(--bg);color:var(--text);font:400 16px/1.6 @@BODY@@}
.wrap{max-width:1120px;margin:0 auto;padding:0 16px}
h1,h2,h3,h4{font-family:@@DISPLAY@@;font-weight:600;margin:0;color:var(--text)}
h1{font-size:44px;line-height:1.15;margin:4px 0 16px}
h2{font-size:32px;line-height:1.2;margin:0 0 16px}
h3{font-size:22px;line-height:1.3;margin:32px 0 12px}
h4{font-size:16px;line-height:1.4;margin:24px 0 8px}
p{margin:0 0 12px;max-width:72ch}
a{color:var(--text);text-underline-offset:3px}
a:focus-visible{outline:2px solid var(--text);outline-offset:3px}
code,pre{font-family:@@MONO@@;font-size:14px;overflow-wrap:anywhere}
pre{overflow-x:auto;border:1px solid var(--line);padding:12px;margin:0 0 16px}
ul,ol{margin:0 0 16px;padding-left:24px;max-width:72ch}li{margin:4px 0}li::marker{color:var(--accent)}
li.task{list-style:none;margin-left:-24px;padding-left:28px;position:relative}
li.task::before{content:"";position:absolute;left:2px;top:.35em;width:14px;height:14px;border:2px solid var(--text)}
li.task[data-task="done"]::before{background:var(--text)}
blockquote{margin:0 0 16px;padding:0 0 0 16px;border-left:3px solid var(--accent);max-width:72ch}
.skip{position:absolute;left:-999px}.skip:focus{left:16px;top:8px;background:var(--bg);padding:6px 10px;z-index:9}
header.top{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
header.top .wrap{display:flex;align-items:center;gap:24px;min-height:52px}
header.top .nm{font-size:@@LABEL@@px;color:var(--muted);white-space:nowrap}
header.top nav{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:@@LABEL@@px;margin-left:auto}
header.top nav a{text-decoration:none}header.top nav a:hover{text-decoration:underline}
.eyebrow{font-size:@@LABEL@@px;color:var(--muted);letter-spacing:.04em;text-transform:uppercase;margin-bottom:4px}
.cover{padding-top:56px;padding-bottom:40px}
.cover .mk{display:block;margin:0 0 32px}
.meta{display:grid;grid-template-columns:max-content 1fr;gap:6px 24px;margin:24px 0;border-top:1px solid var(--line);padding-top:16px;max-width:72ch;font-size:14px}
.meta dt{color:var(--muted)}.meta dd{margin:0}
.tag{display:inline-block;border:1px solid var(--text);padding:0 8px;font-size:@@LABEL@@px;line-height:22px;letter-spacing:.04em}
.toc{list-style:none;margin:16px 0 0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,17rem),1fr));gap:0 32px;border-top:1px solid var(--line);max-width:none}
.toc li{margin:0;border-bottom:1px solid var(--line)}
.toc a{display:flex;gap:14px;padding:10px 0;text-decoration:none}
.toc a::before{content:attr(data-n);min-width:2ch;color:var(--muted);font-variant-numeric:tabular-nums}
section.ch{border-top:1px solid var(--line);padding:48px 0}
.lang+.lang{margin-top:40px;padding-top:24px;border-top:1px dashed var(--line)}
.tw{overflow-x:auto;max-width:100%;margin:0 0 16px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:@@LABEL@@px}
td.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.sw{display:inline-block;width:14px;height:14px;margin-right:6px;vertical-align:-2px;border:1px solid var(--line)}
.chip{display:inline-block;min-width:44px;padding:2px 8px;text-align:center;border:1px solid var(--line);font-weight:600}
.st{display:inline-block;border:1px solid var(--text);padding:0 6px;font-size:@@LABEL@@px;line-height:20px}
.marks{display:grid;gap:16px;margin:0 0 24px}
.marks figure{margin:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:0}
.marks figcaption{grid-column:1/-1;font-size:@@LABEL@@px;color:var(--muted);padding-top:6px}
.ground{padding:24px;border:1px solid var(--line);display:flex;align-items:center;justify-content:center;min-height:132px}
.g-light{background:@@GLIGHT@@}.g-dark{background:@@GDARK@@}
img.mk{max-width:100%;height:auto}
img.px{image-rendering:pixelated;image-rendering:crisp-edges;display:block;max-width:none;height:auto}
.sizes td{vertical-align:middle}.sizes .z{display:flex;gap:8px;align-items:flex-start}
figure.pic{margin:0 0 16px;display:flex;flex-direction:column;gap:6px;align-items:flex-start}
figure.pic img{max-width:100%;height:auto}
figcaption,.cap{font-size:@@LABEL@@px;color:var(--muted);line-height:1.5}
.donts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr));gap:16px;margin:0 0 24px}
.donts figure{margin:0}.donts img{display:block;width:100%;height:auto;border:1px solid var(--line)}
.spec{border:1px solid var(--line);padding:16px;margin:0 0 12px}
.spec .big{font-size:32px;line-height:1.2;margin:0}.spec .sm{font-size:14px;margin:6px 0 0}
.variant,.switcher{border:2px dashed var(--accent);padding:12px;margin:0 0 16px}
.colophon{font-size:@@LABEL@@px;color:var(--muted);border-top:1px solid var(--line);padding-top:24px;padding-bottom:48px}
.cover .sch-d{display:none}
@media (prefers-color-scheme:dark){.cover .sch-l{display:none}.cover .sch-d{display:block}}
@media (max-width:900px){header.top nav{display:none}}
@media (max-width:760px){
 h1{font-size:34px}h2{font-size:26px}
 .meta{grid-template-columns:1fr;gap:0}.meta dd{margin-bottom:8px}
 table.stack thead{display:none}table.stack tr{display:block;padding:8px 0;border-bottom:1px solid var(--line)}
 table.stack td{display:block;border:0;padding:2px 0;text-align:left}
 table.stack td:empty{display:none}
 table.stack td[data-l]:not([data-l=""])::before{content:attr(data-l) ": ";color:var(--muted)}
}
@media print{
 @page{size:A4;margin:14mm}
 header.top,.skip{display:none}
 section.ch{break-before:page}.cover{break-after:page}
 figure,tr,.spec,.donts figure{break-inside:avoid}
 a{text-decoration:none}
 .cover .sch-l{display:block}.cover .sch-d{display:none}
}
"""


class BookBuild:
    BLOCK = {"marks", "mark-sizes", "colours", "contrast", "type", "motion", "tokens", "files", "checks", "decided", "history",
             "edition-log", "donts", "facts"}
    INLINE = {"count", "fact", "edition", "name", "approved"}

    def __init__(self, project: Path, *, renderer: str = "resvg", allow_variants: bool = False):
        self.project = project
        self.renderer = renderer
        self.allow_variants = allow_variants
        self.view = bookdata.state_view(project)
        self.cfg, self.cfg_src = bookdata.load_config(project)
        self.doc, self.tokens_path = bookdata.tokens(project)
        self.facts = bookdata.facts(project)
        self.langs = self.view["content_languages"]
        self.chapter_ids = bookdata.chapters_for(project, self.view)
        self.inputs: list[Path] = [self.tokens_path]
        for p in ("FACTS.md", "qa/rules.json", "book/book.json", "adoption.json"):   # the manifest is read as a view (manifest_view_sha), not as a file
            if (project / p).is_file():
                self.inputs.append(project / p)
        self.warnings: list[tuple[str, str]] = []
        self.infos: list[tuple[str, str]] = []
        self.variants: list[str] = []
        self.missing_labels: dict[str, set[str]] = {}
        self._raster_cache: dict = {}
        self.light, self.dark = self._roles("light"), self._roles("dark")
        self.counts = bookdata.counts(project, self.cfg, self.doc, len(self.chapter_ids))

    # ------------------------------------------------------------ small helpers
    def warn(self, id_: str, detail: str) -> None:
        if (id_, detail) not in self.warnings:
            self.warnings.append((id_, detail))

    def info(self, id_: str, detail: str) -> None:
        if (id_, detail) not in self.infos:
            self.infos.append((id_, detail))

    def add_input(self, p: Path) -> None:
        if p.is_file() and p not in self.inputs:
            self.inputs.append(p)

    def T(self, lang: str, text: str) -> str:
        if lang == "en":
            return text
        tr = self.cfg["labels"].get(lang, {})
        if text in tr:
            return tr[text]
        self.missing_labels.setdefault(lang, set()).add(text)
        return text

    def _roles(self, mode: str) -> dict[str, str]:
        m = {k: v["hex"] for k, v in self.doc["modes"][mode].items()}
        for need in ("color.bg", "color.text"):
            if need not in m:
                fail(EXIT_FAIL, f"the {mode} tokens define no {need}; the book needs the semantic tokens color.bg and color.text")
        text = m["color.text"]
        muted = m.get("color.muted", text)
        border = m.get("color.border", muted)
        return {"bg": m["color.bg"], "text": text, "muted": muted, "accent": m.get("color.accent", text),
                "line": m.get("color.line", border), "mark": m.get("color.mark", text)}

    def read(self, rel: str, what: str) -> Path:
        from _common import confine
        p = confine(self.project, rel, what=what)
        if not p.is_file():
            fail(EXIT_USAGE, f"{what} {rel} not found in the project")
        self.add_input(p)
        return p

    def data_uri(self, p: Path, mime: str) -> str:
        return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()

    def svg_uri(self, text: str) -> str:
        return "data:image/svg+xml;base64," + base64.b64encode(text.encode("utf-8")).decode()

    def mark_svg(self, p: Path) -> str:
        text = p.read_text(encoding="utf-8")
        probs = lint_svg_text(text)
        if probs:
            fail(EXIT_FAIL, f"mark_lint: {p.relative_to(self.project)} is not pure vector ({'; '.join(probs)}); outline text first")
        self.add_input(p)
        return text

    def img_tag(self, svg_text: str, name: str, alt: str, cls: str = "mk") -> str:
        vb = svgtools.viewbox(svgtools.parse(svg_text))
        r = vb[2] / vb[3]
        if r <= 1.5:
            h = 96
            w = round(h * r)
        else:
            w = min(320, round(96 * r))
            h = round(w / r)
        return f'<img class="{cls}" data-mark="{esc(name)}" src="{self.svg_uri(svg_text)}" alt="{esc(alt)}" width="{w}" height="{h}">'

    def table(self, head: list[str], rows: list, cls: str = "stack") -> str:
        th = "".join(f"<th>{h}</th>" for h in head)
        body = []
        for r in rows:
            attrs = ""
            cells = r
            if isinstance(r, tuple):
                cells, a = r
                attrs = "".join(f' {k}="{esc(v)}"' for k, v in a.items())
            tds = []
            for h, c in zip(head, cells):
                num = isinstance(c, tuple)
                val = c[0] if num else c
                tds.append(f'<td data-l="{esc(re.sub("<[^>]+>", "", h))}"' + (' class="num"' if num else "") + f">{val}</td>")
            body.append(f"<tr{attrs}>" + "".join(tds) + "</tr>")
        return f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'

    def load_report(self, rel: str):
        """-> (doc or None, [reasons it is stale])."""
        f = self.project / rel
        if not f.is_file():
            return None, []
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            return None, ["not valid JSON"]
        stale = []
        for rec in doc.get("inputs", []):
            q = self.project / rec["path"]
            if not q.is_file():
                stale.append(f"{rec['path']} is gone")
            elif sha256_file(q) != rec["sha256"]:
                stale.append(f"{rec['path']} changed")
        self.add_input(f)
        return doc, stale

    # ------------------------------------------------------------ inline values and block dispatch (called by bookmd)
    def inline(self, name: str, arg: str, lang: str) -> str:
        if name == "count":
            if arg not in self.counts:
                fail(EXIT_USAGE, f"{{{{count:{arg}}}}} is not a count the book knows ({', '.join(sorted(self.counts))})")
            return f'<span data-count="{esc(arg)}">{self.counts[arg]}</span>'
        if name == "fact":
            v = bookdata.fact_value(self.facts, arg)
            if v is None:
                fail(EXIT_FAIL, f"{{{{fact:{arg}}}}}: FACTS.md has no row named {arg!r} (honest copy: facts come from FACTS.md only)")
            return f'<span data-fact="{esc(arg)}">{esc(" ".join(v.split()))}</span>'
        if name == "edition":
            return f'<span data-edition-value="{self.view["edition"]}">{self.view["edition"]}</span>'
        if name == "name":
            return esc(self.view["name"])
        if name == "approved":
            return esc(self.stamp_text(lang))
        raise AssertionError(name)

    def block(self, name: str, arg: str, lang: str) -> str:
        fn = getattr(self, "b_" + name.replace("-", "_"))
        return fn(arg, lang)

    def variant(self, kind: str, group: str, name: str, line: int) -> None:
        self.variants.append(f"{group}:{name}" if name else f"switcher:{group}")
        if not self.allow_variants:
            raise bookmd.MdError(line, f"an open choice ({kind} {group}{' ' + name if name else ''}) cannot ship in the book: decide, then run "
                                       f"`brand-creator collapse --group {group} --keep <name>` (or build with --allow-variants to review it; "
                                       f"book-lint still fails it)")

    def image(self, path: str, alt: str, lang: str, line: int) -> str:
        from _common import confine
        if not alt.strip():
            raise bookmd.MdError(line, f"image {path} has no alt text; write ![what it shows](path)")
        try:
            p = confine(self.project, path, what="image")
        except Exception as e:
            raise bookmd.MdError(line, f"image {path}: {getattr(e, 'message', e)}")
        mime = IMG_MIME.get(p.suffix.lower())
        if not mime:
            raise bookmd.MdError(line, f"image {path}: only {', '.join(IMG_MIME)} are embedded")
        if not p.is_file():
            raise bookmd.MdError(line, f"image {path} not found in the project")
        self.add_input(p)
        if p.suffix.lower() == ".svg":
            text = p.read_text(encoding="utf-8")
            under_assets = p.relative_to(self.project.resolve()).parts[0] == "assets"
            attr = f'data-mark="{esc(p.stem)}"' if under_assets else f'data-diagram="{esc(p.stem)}"'
            if under_assets:
                probs = lint_svg_text(text)
                if probs:
                    raise bookmd.MdError(line, f"mark_lint: {path} is not pure vector ({'; '.join(probs)})")
            src = self.svg_uri(text)
        else:
            attr = ""
            src = self.data_uri(p, mime)
        return f'<figure class="pic"><img {attr} src="{src}" alt="{esc(alt)}"><figcaption>{esc(alt)}</figcaption></figure>'

    # ------------------------------------------------------------ stamp
    def stamp_text(self, lang: str) -> str:
        state, date = bookdata.approval(self.view)
        if state == "approved":
            return f"APPROVED {date}".strip()
        return self.T(lang, "Awaiting approval")

    # ------------------------------------------------------------ computed blocks
    def logo_pair(self, stem: str):
        light = self.project / "assets" / "logo" / f"{stem}.svg"
        dark = self.project / "assets" / "logo" / f"{stem}-dark.svg"
        return light, dark

    def b_marks(self, arg: str, lang: str) -> str:
        names = [n.strip() for n in (arg or "mark").split(",") if n.strip()]
        if names == ["*"]:
            names = sorted({p.stem for p in bookdata.logo_files(self.project) if p.suffix == ".svg" and not p.stem.endswith(("-dark", "-master"))})
        figs = []
        for raw in names:
            optional = raw.endswith("?")
            stem = raw.rstrip("?")
            light, dark = self.logo_pair(stem)
            if not light.is_file():
                if optional:
                    self.info("marks", f"assets/logo/{stem}.svg does not exist; skipped (optional)")
                    continue
                fail(EXIT_FAIL, f"{{{{marks:{stem}}}}}: assets/logo/{stem}.svg does not exist (write {stem}? to make it optional)")
            lt = self.mark_svg(light)
            cells = [f'<div class="ground g-light">{self.img_tag(lt, stem, f"{self.view["name"]} {stem} on a light ground")}</div>']
            if dark.is_file():
                cells.append(f'<div class="ground g-dark">{self.img_tag(self.mark_svg(dark), stem + "-dark", f"{self.view["name"]} {stem} on a dark ground")}</div>')
            else:
                self.warn("marks", f"assets/logo/{stem}-dark.svg does not exist; {stem} is shown on the light ground only")
            cap = f"{esc(stem)} · assets/logo/{esc(stem)}.svg · {len(light.read_bytes())} bytes"
            figs.append(f'<figure>{"".join(cells)}<figcaption>{cap}</figcaption></figure>')
        return '<div class="marks">' + "".join(figs) + "</div>"

    def _raster(self, svg_path: Path, size: int, bg: str) -> bytes:
        key = (str(svg_path), size, bg)
        if key not in self._raster_cache:
            text = self.mark_svg(svg_path)
            self._raster_cache[key] = rasterise_svg(svgtools.fit(text, size, size, bg=bg), size, size, renderer=self.renderer)
        return self._raster_cache[key]

    def b_mark_sizes(self, arg: str, lang: str) -> str:
        rules, _src = qa_rules.load(self.project)
        bands = rules["bands"]
        rows = []
        for s in self.cfg["sizes"]:
            band = qa_rules.pick_band(bands, s) if bands else None
            draw = self.project / (band["drawing"] if band else "assets/logo/mark.svg")
            if not draw.is_file():
                fail(EXIT_FAIL, f"the drawing for {s} px, {draw.relative_to(self.project)}, does not exist")
            dark = draw.with_name(draw.stem + "-dark.svg")
            zoom = max(1, min(8, 128 // s))
            cells = [f"{s} px", f"{esc(draw.relative_to(self.project).as_posix())}" + (f" ({esc(band['name'])})" if band else "")]
            for mode, f, bg in (("light", draw, self.light["bg"]), ("dark", dark, self.dark["bg"])):
                if not f.is_file():
                    cells.append(esc(self.T(lang, "no dark drawing")))
                    self.warn("mark-sizes", f"{f.relative_to(self.project)} does not exist; the {s} px dark proof is left out")
                    continue
                uri = self.data_uri_png(self._raster(f, s, bg))
                alt = f"{self.view['name']} mark at {s} px, {mode} ground"
                one = f'<img class="px" src="{uri}" alt="{esc(alt)}" width="{s}" height="{s}">'
                big = f'<img class="px" src="{uri}" alt="" aria-hidden="true" width="{s * zoom}" height="{s * zoom}">' if zoom > 1 else ""
                cells.append(f'<div class="z">{one}{big}</div>')
            rows.append(cells)
        head = [self.T(lang, "Size"), self.T(lang, "Drawing"), self.T(lang, "Light ground"), self.T(lang, "Dark ground")]
        out = [self.table(head, rows, "stack sizes"),
               f'<p class="cap">{esc(self.T(lang, "Each image is the drawing for that size, rendered at exactly those pixels; the enlarged copy next to it is the same pixels, not a new render."))}</p>']
        reps = sorted((self.project / "assets" / "_checks" / "downscale").glob("*.json")) if (self.project / "assets/_checks/downscale").is_dir() else []
        if not reps:
            self.warn("mark-sizes", "no downscale report: the small-size measurement table is left out; run `brand-creator downscale --source <master>`")
        for rf in reps:
            doc, stale = self.load_report(rf.relative_to(self.project).as_posix())
            if not doc:
                continue
            rows2 = []
            for r in doc.get("results", []):
                if r.get("id", "").startswith("downscale:") and "size" in r and r.get("status") in ("pass", "fail", "warn", "info"):
                    rows2.append([f"{r['size']} px", (str(r.get("accent_px", "")),), (str(r.get("accent_square", "")),),
                                  f'<span class="st">{esc(r["status"])}</span>'])
            if rows2:
                note = f" ({esc(self.T(lang, 'stale: measured before the last change'))})" if stale else ""
                out.append(f"<h4>{esc(doc.get('source', rf.stem))}{note}</h4>")
                out.append(self.table([self.T(lang, "Size"), self.T(lang, "Accent pixels"), self.T(lang, "Largest solid square"), self.T(lang, "Rule")], rows2))
                out.append(f'<p class="cap">{esc(self.T(lang, "Method"))}: {esc(str(doc.get("renderer", "")))}</p>')
                if stale:
                    self.warn("mark-sizes", f"{rf.name} is stale ({'; '.join(stale[:2])}); re-run downscale")
        return "\n".join(out)

    def data_uri_png(self, data: bytes) -> str:
        return "data:image/png;base64," + base64.b64encode(data).decode()

    def b_colours(self, arg: str, lang: str) -> str:
        prim = self.doc.get("primitives", {})
        rows = []
        for name in sorted(prim):
            hx = prim[name]["hex"].lower()
            lr = sorted(r for r, v in self.doc["modes"]["light"].items() if v.get("ref") == name)
            dr = sorted(r for r, v in self.doc["modes"]["dark"].items() if v.get("ref") == name)
            rows.append([f'<span class="sw" style="background:{hx}"></span>{esc(name)}', f"<code>{hx}</code>",
                         esc(", ".join(lr) or "-"), esc(", ".join(dr) or "-")])
        return self.table([self.T(lang, "Colour"), self.T(lang, "Hex"), self.T(lang, "Light roles"), self.T(lang, "Dark roles")], rows)

    def b_contrast(self, arg: str, lang: str) -> str:
        rows = []
        for p in self.doc.get("pairs", []):
            lm, dm = p["modes"]["light"], p["modes"]["dark"]
            rl, rd = wcag_ratio(lm["fg_hex"], lm["bg_hex"]), wcag_ratio(dm["fg_hex"], dm["bg_hex"])
            ok = rl >= p["min"] and rd >= p["min"]
            label = p.get("label") or f"{p['fg']} on {p['bg']}"
            chips = "".join(f'<span class="chip" style="color:{m["fg_hex"].lower()};background:{m["bg_hex"].lower()}">Aa</span> ' for m in (lm, dm))
            rows.append([f"{chips}{esc(label)}", esc(KIND_LABEL.get(p["kind"], p["kind"])), (f"{p['min']:g}:1",), (f"{rl:.2f}:1",), (f"{rd:.2f}:1",),
                         f'<span class="st">{esc(self.T(lang, "pass" if ok else "below the target"))}</span>'])
        head = [self.T(lang, "Pair"), self.T(lang, "Kind"), self.T(lang, "Target"), self.T(lang, "Light"), self.T(lang, "Dark"), self.T(lang, "Result")]
        cap = self.T(lang, "Ratios are computed from the built tokens (assets/tokens/tokens.json) with the WCAG 2.x formula. Logos are exempt from WCAG contrast; the marks have their own rule.")
        return self.table(head, rows) + f'<p class="cap">{esc(cap)}</p>'

    def b_type(self, arg: str, lang: str) -> str:
        fonts = {k: v for k, v in self.doc.get("other", {}).items() if k.startswith("font.")}
        declared = {f["family"]: f for f in self.cfg["fonts"]}
        rows = [[esc(k), f"<code>{esc(str(v))}</code>"] for k, v in sorted(fonts.items())]
        out = [self.table([self.T(lang, "Token"), self.T(lang, "Font stack")], rows) if rows else
               f"<p>{esc(self.T(lang, 'The tokens define no font families; the system sans stack is used.'))}</p>"]
        if not rows:
            self.warn("type", "the tokens define no font.* family; the book uses the system sans stack")
        for k, v in sorted(fonts.items()):
            out.append(f'<div class="spec" style="font-family:{esc(str(v))}"><p class="big">Aa Bb Cc 0123456789</p>'
                       f'<p class="sm">{esc(k)}</p></div>')
        for code in self.langs:
            f = plugin_lang(code)
            if f:
                letters = "".join(f.get("letters", []) if isinstance(f.get("letters"), list) else str(f.get("letters", "")))
                if letters:
                    out.append(f'<p class="cap">{esc(f.get("name", code))}: {esc(letters)}</p>')
        if declared:
            frows = [[esc(f["family"]), esc(str(f.get("weight", 400))), esc(f.get("style", "normal")), esc(f["file"])] for f in self.cfg["fonts"]]
            out.append(self.table([self.T(lang, "Family"), self.T(lang, "Weight"), self.T(lang, "Style"), self.T(lang, "File")], frows))
        doc, stale = self.load_report("assets/_checks/fontcheck.json")
        if doc:
            frows = [[esc(r["id"]), f'<span class="st">{esc(r["status"])}</span>'] for r in doc.get("results", []) if r["id"].startswith(("cmap:", "platform:"))]
            if frows:
                out.append(f"<h4>{esc(self.T(lang, 'Glyph coverage'))}</h4>" + self.table([self.T(lang, "Check"), self.T(lang, "Result")], frows))
        return "\n".join(out)

    def b_motion(self, arg: str, lang: str) -> str:
        rows = [[esc(k), f"<code>{esc(str(v))}</code>"] for k, v in sorted(self.doc.get("other", {}).items())
                if k.startswith(("duration.", "easing.", "motion."))]
        out = [self.table([self.T(lang, "Token"), self.T(lang, "Value")], rows) if rows else
               f"<p>{esc(self.T(lang, 'The tokens define no durations.'))}</p>"]
        doc, stale = self.load_report("assets/_checks/motion.json")
        if doc:
            prow = [[esc(r["id"]), f'<span class="st">{esc(r["status"])}</span>'] for r in doc.get("results", []) if r["status"] in ("pass", "fail", "warn")]
            out.append(f"<h4>{esc(self.T(lang, 'Motion proof'))}</h4>" + self.table([self.T(lang, "Case"), self.T(lang, "Result")], prow))
            if stale:
                self.warn("motion", f"the motion report is stale ({'; '.join(stale[:2])})")
        else:
            self.warn("motion", "no motion report; the motion proof table is left out (run `brand-creator shot --motion motion/proof.json`)")
        return "\n".join(out)

    def b_tokens(self, arg: str, lang: str) -> str:
        rows = [[esc(k), f"<code>{esc(str(v))}</code>"] for k, v in sorted(self.doc.get("other", {}).items())]
        return self.table([self.T(lang, "Token"), self.T(lang, "Value")], rows) if rows else f"<p>{esc(self.T(lang, 'No tokens beyond colour.'))}</p>"

    def b_files(self, arg: str, lang: str) -> str:
        rows = bookdata.manifest_rows(self.project)
        groups: dict[str, list[dict]] = {}
        for r in rows:
            groups.setdefault(r.get("emitter") or "-", []).append(r)
        out = []
        head = [self.T(lang, "Path"), self.T(lang, "Slot"), self.T(lang, "Size"), self.T(lang, "Band"), self.T(lang, "Bytes"), "sha256"]
        for em in sorted(groups):
            trs = []
            for r in sorted(groups[em], key=lambda x: x["path"]):
                trs.append(([f'<code>{esc(r["path"])}</code>', esc(r.get("slot", "")), esc(r.get("size", "")), esc(r.get("band", "")),
                             (str(r["bytes"]),), f'<code>{r["sha256"][:8]}</code>'], {"data-path": r["path"], "data-sha": r["sha256"][:8]}))
            out.append(f"<h4>{esc(em)}</h4>" + self.table(head, trs))
        art = []
        for f in bookdata.logo_files(self.project):
            data = f.read_bytes()
            rel = f.relative_to(self.project).as_posix()
            art.append(([f"<code>{esc(rel)}</code>", "", "", "", (str(len(data)),), f"<code>{bookdata.sha8(data)}</code>"],
                        {"data-path": rel, "data-sha": bookdata.sha8(data)}))
            self.add_input(f)
        if art:
            out.append(f"<h4>{esc(self.T(lang, 'Source artwork'))}</h4>" + self.table(head, art))
        for r in bookdata.press_kit_rows(self.project):
            out.append(f'<p data-path="{esc(r["path"])}">{esc(self.T(lang, "Press kit"))}: <code>{esc(r["path"])}</code>. '
                       f'{esc(self.T(lang, "It contains this book as a PDF, so its checksum is not stated here; the kit lists the checksums of its files."))}</p>')
        if not out:
            self.warn("files", "no assets/manifest.json rows and no assets/logo files: the files chapter is empty")
            return f"<p>{esc(self.T(lang, 'No files have been written yet.'))}</p>"
        return "\n".join(out)

    def b_checks(self, arg: str, lang: str) -> str:
        tools = list(PROOF_TOOLS)
        d = self.project / "assets" / "_checks" / "downscale"
        tools += [f"downscale/{p.stem}" for p in sorted(d.glob("*.json"))] if d.is_dir() else []
        rows = []
        for t in tools:
            doc, stale = self.load_report(f"assets/_checks/{t}.json")
            if not doc:
                continue
            n = {k: sum(1 for r in doc.get("results", []) if r.get("status") == k) for k in ("pass", "warn", "fail")}
            state = self.T(lang, "stale") if stale else self.T(lang, "current")
            if stale:
                self.warn("proof", f"the {t} report is stale ({'; '.join(stale[:2])})")
            rows.append([esc(t), f'<span class="st">{esc(str(doc.get("status", "")))}</span>', (str(n["pass"]),), (str(n["warn"]),), (str(n["fail"]),), esc(state)])
        if not rows:
            self.warn("proof", "no proof reports under assets/_checks/; the proof table is empty")
            return f"<p>{esc(self.T(lang, 'No proof has been recorded.'))}</p>"
        head = [self.T(lang, "Report"), self.T(lang, "Status"), self.T(lang, "Pass"), self.T(lang, "Warn"), self.T(lang, "Fail"), self.T(lang, "Inputs")]
        return self.table(head, rows)

    def b_decided(self, arg: str, lang: str) -> str:
        out = []
        dec = [r for r in self.view["directions"] if r.get("status", "").upper() == "DECIDED"]
        if dec:
            rows = [[esc(r.get("name", "")), esc(r.get("register", "")), esc(r.get("liked", "")), esc(r.get("decided", ""))] for r in dec]
            out.append(self.table([self.T(lang, "Direction"), self.T(lang, "Register"), self.T(lang, "What holds"), self.T(lang, "Decided")], rows))
        if self.view["rules"]:
            out.append("<ul>" + "".join(f"<li>{esc(re.sub(r'^\(rule\)\s*', '', x, flags=re.I))}</li>" for x in self.view["rules"]) + "</ul>")
        if not out:
            self.warn("decided", "BRAND-STATE.md has no DECIDED direction and no (rule) lines; the decided block is empty")
            return f"<p>{esc(self.T(lang, 'Nothing has been decided yet.'))}</p>"
        return "\n".join(out)

    def b_history(self, arg: str, lang: str) -> str:
        out = []
        rows = [[esc(r.get("name", "")), esc(r.get("letter", "")), esc(r.get("status", "")), esc(r.get("liked", "")), esc(r.get("rejected", "")),
                 esc(r.get("decided", ""))] for r in self.view["directions"]]
        if rows:
            out.append(self.table([self.T(lang, "Direction"), self.T(lang, "Letter"), self.T(lang, "Status"), self.T(lang, "Liked"),
                                   self.T(lang, "Rejected, and why"), self.T(lang, "Decided")], rows))
        hist = self.project / "history"
        if hist.is_dir():
            frozen = sorted(p.name for p in hist.iterdir() if p.is_dir())
            if frozen:
                out.append(f"<h4>{esc(self.T(lang, 'Frozen boards'))}</h4><ul>" + "".join(f"<li><code>{esc(n)}</code></li>" for n in frozen) + "</ul>")
            mf = hist / "MANIFEST.sha256"
            if mf.is_file():
                self.add_input(mf)
        if not out:
            self.warn("history", "no directions in BRAND-STATE.md and nothing frozen in history/; the history block is empty")
        out.append(self.b_edition_log("", lang))
        if self.view["collapsed"]:
            out.append(f"<h4>{esc(self.T(lang, 'Choices closed'))}</h4><ul>" + "".join(f"<li>{esc(x)}</li>" for x in self.view["collapsed"]) + "</ul>")
        return "\n".join(out)

    def b_edition_log(self, arg: str, lang: str) -> str:
        log = self.view["edition_log"]
        items = "".join(f"<li>{esc(x)}</li>" for x in log) or f"<li>{esc(self.T(lang, 'No edition has been logged yet.'))}</li>"
        return f"<h4>{esc(self.T(lang, 'Edition log'))}</h4><ul>{items}</ul>"

    def b_facts(self, arg: str, lang: str) -> str:
        rows = [[esc(r.get("fact", "")), esc(r.get("value", "")), esc(r.get("source", "")), esc(r.get("confirmed", ""))] for r in self.facts]
        if not rows:
            self.warn("facts", "FACTS.md has no rows; the facts block is empty")
        return self.table([self.T(lang, "Fact"), self.T(lang, "Value"), self.T(lang, "Source"), self.T(lang, "Confirmed")], rows)

    def b_donts(self, arg: str, lang: str) -> str:
        light, _dark = self.logo_pair("mark")
        if not light.is_file():
            fail(EXIT_FAIL, "{{donts}} draws the misuse from assets/logo/mark.svg, which does not exist")
        base = self.mark_svg(light)
        root = svgtools.parse(base)
        S = 160
        bg, ink, acc, mk = self.light["bg"], self.light["text"], self.light["accent"], self.light["mark"]
        figs = []
        for key, caption in DONTS:
            ox, oy, w, h = 56, 56, 48, 48          # the mark sits in a 48 x 48 box centred on the 160 canvas
            inner = ""
            tpl = svgtools.dump(svgtools.nested(root, ox, oy, w, h))
            if key == "stretch":
                inner = f'<g transform="translate(80 80) scale(1.7 .7) translate(-80 -80)">{tpl}</g>'
            elif key == "rotate":
                inner = f'<g transform="rotate(24 80 80)">{tpl}</g>'
            elif key == "recolour":
                cols = svgtools.paint_colours(base)
                mapping = {c: acc for c in cols}
                alt = svgtools.recolor(base, mapping) if cols else base
                inner = svgtools.dump(svgtools.nested(svgtools.parse(alt), ox, oy, w, h))
            elif key == "ground":
                inner = f'<rect x="28" y="28" width="104" height="104" fill="{mk}"/>{tpl}'
            elif key == "crowd":
                inner = f'<rect x="12" y="68" width="40" height="24" fill="{self.light["muted"]}"/><rect x="108" y="68" width="40" height="24" fill="{self.light["muted"]}"/>{tpl}'
            frame = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" width="{S}" height="{S}"><rect width="{S}" height="{S}" fill="{bg}"/>'
                     f'{inner}<path d="M10 10 150 150M150 10 10 150" stroke="{ink}" stroke-width="3" fill="none"/></svg>')
            figs.append(f'<figure><img data-mark="dont-{key}" src="{self.svg_uri(frame)}" alt="{esc(self.T(lang, caption))}" width="{S}" height="{S}">'
                        f"<figcaption>{esc(self.T(lang, caption))}</figcaption></figure>")
        return '<div class="donts">' + "".join(figs) + "</div>"

    # ------------------------------------------------------------ chapters and the page
    def chapter_file(self, cid: str, lang: str) -> Path:
        name = f"{cid}.md" if len(self.langs) == 1 else f"{cid}.{lang}.md"
        p = self.project / bookdata.CHAPTER_DIR / name
        if not p.is_file():
            fail(EXIT_FAIL, f"chapter {cid} has no content file {bookdata.CHAPTER_DIR}/{name}; run `brand-creator book --init` to copy the "
                            f"skeleton from templates/book/, then fill it")
        self.add_input(p)
        return p

    def build_chapter(self, cid: str) -> tuple[str, str]:
        """-> (title for the contents list, section HTML)."""
        divs, first_title = [], None
        for lang in self.langs:
            p = self.chapter_file(cid, lang)
            try:
                title, body = bookmd.convert(p.read_text(encoding="utf-8"), self, lang)
            except bookmd.MdError as e:
                fail(EXIT_FAIL, f"{p.relative_to(self.project)}: {e}")
            except Exception as e:
                if getattr(e, "code", None) is not None:
                    fail(e.code, f"{p.relative_to(self.project)}: {e.message}")
                raise
            title = title or self.T(lang, bookdata.TITLES[cid])
            first_title = first_title or title
            divs.append(f'<div class="lang" lang="{esc(lang)}" data-key="{esc(cid)}">\n<h2>{bookmd.inline(title, self, lang, 1)}</h2>\n{body}\n</div>')
        return first_title, f'<section class="ch" id="{esc(cid)}" data-chapter="{esc(cid)}">\n' + "\n".join(divs) + "\n</section>"

    def fonts_css(self) -> str:
        faces = []
        for ft in self.cfg["fonts"]:
            p = self.read(ft["file"], "font file")
            mime, fmt = FONT_MIME.get(p.suffix.lower(), (None, None))
            if not mime:
                fail(EXIT_USAGE, f"font {ft['file']}: only {', '.join(FONT_MIME)} are embedded")
            faces.append(f'@font-face{{font-family:"{ft["family"]}";font-weight:{ft.get("weight", 400)};font-style:{ft.get("style", "normal")};'
                         f'font-display:block;src:url({self.data_uri(p, mime)}) format("{fmt}")}}')
            if not any(ft["family"] in str(v) for k, v in self.doc.get("other", {}).items() if k.startswith("font.")):
                self.warn("type", f"the embedded font {ft['family']!r} is not named in any font.* token; the book will not use it")
        return "\n".join(faces)

    def stacks(self) -> tuple[str, str, str]:
        o = self.doc.get("other", {})
        sans = o.get("font.body") or o.get("font.sans") or "ui-sans-serif, system-ui, sans-serif"
        display = o.get("font.display") or sans
        mono = o.get("font.mono") or "ui-monospace, monospace"
        return str(sans), str(display), str(mono)

    def css(self) -> str:
        def vars_(m: dict) -> str:
            return ";".join(f"--{k}:{v}" for k, v in m.items())
        body, display, mono = self.stacks()
        css = CSS
        for k, v in {"@@LIGHT@@": vars_(self.light), "@@DARK@@": vars_(self.dark), "@@FACES@@": self.fonts_css(), "@@BODY@@": body,
                     "@@DISPLAY@@": display, "@@MONO@@": mono, "@@LABEL@@": f"{self.cfg['min_label_px']:g}",
                     "@@GLIGHT@@": self.light["bg"], "@@GDARK@@": self.dark["bg"]}.items():
            css = css.replace(k, v)
        return css.strip()

    def adoption_line(self, lang: str) -> str:
        """What the cover says about adoption: only what the data back. G6 is the owner's go, not progress; progress is the rows done in adoption.json."""
        g6 = self.view["g6"]
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\b", g6)
        approved = f"{self.T(lang, 'Adoption approved')} {m.group(1) if m else g6}" if g6 else self.T(lang, "Adoption not yet approved")
        a = self.view["adoption"]
        if a is None:
            return approved
        return f"{approved}; {a['done']} {self.T(lang, 'of')} {a['total']} {self.T(lang, 'rows done')}"

    def cover(self, titles: list[tuple[str, str]]) -> str:
        lang = self.langs[0]
        state, date = bookdata.approval(self.view)
        light, dark = self.logo_pair("mark")
        if not light.is_file():
            fail(EXIT_FAIL, "the cover needs assets/logo/mark.svg, which does not exist")
        name = self.view["name"]
        lt = self.img_tag(self.mark_svg(light), "mark", f"{name} mark", "mk sch-l" if dark.is_file() else "mk")
        dk = self.img_tag(self.mark_svg(dark), "mark-dark", f"{name} mark", "mk sch-d") if dark.is_file() else ""
        meta = [(self.T(lang, "Edition"), f'<span data-edition-value="{self.view["edition"]}">{self.view["edition"]}</span>'),
                (self.T(lang, "Approval"), f'<span class="tag" data-stamp-text>{esc(self.stamp_text(lang))}</span>')]
        status = bookdata.fact_value(self.facts, "status")
        if status:
            meta.append((self.T(lang, "Status"), f'<span data-fact="status">{esc(" ".join(status.split()))}</span>'))
        applied = self.adoption_line(lang)
        meta.append((self.T(lang, "Adoption"), esc(applied)))
        dl = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in meta)
        toc = "".join(f'<li><a href="#{esc(cid)}" data-n="{i}">{esc(re.sub("<[^>]+>", "", t))}</a></li>' for i, (cid, t) in enumerate(titles, 1))
        return (f'<section class="cover wrap" id="cover" data-cover data-edition="{self.view["edition"]}" data-stamp="{state}">\n{lt}{dk}\n'
                f'<p class="eyebrow">{esc(self.T(lang, "Brand book"))}</p>\n<h1>{esc(name)}</h1>\n<dl class="meta">{dl}</dl>\n<ol class="toc">{toc}</ol>\n</section>')

    def build(self) -> str:
        titles, sections = [], []
        for cid in self.chapter_ids:
            t, s = self.build_chapter(cid)
            titles.append((cid, t))
            sections.append(s)
        cover = self.cover(titles)
        lang0 = self.langs[0]
        nav = "".join(f'<a href="#{esc(cid)}">{esc(re.sub("<[^>]+>", "", t))}</a>' for cid, t in titles)
        for lang, items in sorted(self.missing_labels.items()):
            self.warn("labels", f"{len(items)} label(s) have no {lang} translation in book/book.json labels.{lang} and are shown in English: "
                                f"{', '.join(sorted(items)[:3])}{' ...' if len(items) > 3 else ''}")
        head = (f'<!doctype html>\n<html lang="{esc(lang0)}">\n<head>\n<meta charset="utf-8">\n'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">\n<meta name="color-scheme" content="light dark">\n'
                f'<meta name="generator" content="brand-creator book">\n<meta name="bc-min-label" content="{self.cfg["min_label_px"]:g}">\n'
                f'<title>{esc(self.view["name"])} {esc(self.T(lang0, "brand book"))}</title>\n<style>\n{self.css()}\n</style>\n</head>\n')
        colophon = (f'<p class="colophon wrap">{esc(self.T(lang0, "Smallest text in this book"))}: '
                    f'<span data-min-label>{self.cfg["min_label_px"]:g}</span> px.</p>')
        body = (f'<body>\n<a class="skip" href="#main">{esc(self.T(lang0, "Skip to the content"))}</a>\n'
                f'<header class="top"><div class="wrap"><span class="nm">{esc(self.view["name"])}</span><nav aria-label="{esc(self.T(lang0, "Chapters"))}">{nav}</nav></div></header>\n'
                f'<main id="main">\n{cover}\n<div class="wrap">\n' + "\n".join(sections) + f"\n</div>\n</main>\n{colophon}\n</body>\n</html>\n")
        return head + body


_LANG_CACHE: dict = {}


def plugin_lang(code: str) -> dict | None:
    if code not in _LANG_CACHE:
        from _common import plugin_root
        f = plugin_root() / "scripts" / "data" / "languages" / f"{code}.json"
        _LANG_CACHE[code] = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    return _LANG_CACHE[code]

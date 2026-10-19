"""SVG helpers (ElementTree based, standard library only): fit a mark into a box, derive a silhouette, merge a
light and a dark variant into one prefers-color-scheme icon."""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


class SvgError(ValueError):
    pass


def _q(tag: str) -> str:
    return f"{{{SVG_NS}}}{tag}"


def parse(text: str) -> ET.Element:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise SvgError(f"not well-formed SVG: {e}") from e
    if root.tag != _q("svg"):
        raise SvgError("root element is not <svg xmlns=\"http://www.w3.org/2000/svg\">")
    return root


def dump(root: ET.Element) -> str:
    return ET.tostring(root, encoding="unicode")


def _num(v: str) -> float:
    m = re.match(r"^\s*([0-9.]+)\s*(px)?\s*$", v or "")
    if not m:
        raise SvgError(f"unsupported length {v!r} (use plain numbers or px)")
    return float(m.group(1))


def viewbox(root: ET.Element) -> tuple[float, float, float, float]:
    vb = root.get("viewBox")
    if vb:
        parts = [float(x) for x in re.split(r"[\s,]+", vb.strip())]
        if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
            raise SvgError(f"bad viewBox {vb!r}")
        return tuple(parts)  # type: ignore[return-value]
    if root.get("width") and root.get("height"):
        return 0.0, 0.0, _num(root.get("width")), _num(root.get("height"))
    raise SvgError("SVG needs a viewBox (or width and height)")


def nested(root: ET.Element, x: float, y: float, w: float, h: float) -> ET.Element:
    vb = viewbox(root)
    inner = ET.fromstring(dump(root))
    for a in ("width", "height", "x", "y", "viewBox"):
        inner.attrib.pop(a, None)
    inner.set("x", f"{x:g}")
    inner.set("y", f"{y:g}")
    inner.set("width", f"{w:g}")
    inner.set("height", f"{h:g}")
    inner.set("viewBox", " ".join(f"{v:g}" for v in vb))
    inner.set("preserveAspectRatio", "xMidYMid meet")
    return inner


def _wrapper(width: int, height: int, bg: str | None) -> ET.Element:
    w = ET.Element(_q("svg"), {"width": str(width), "height": str(height), "viewBox": f"0 0 {width} {height}"})
    if bg:
        ET.SubElement(w, _q("rect"), {"width": str(width), "height": str(height), "fill": bg})
    return w


def fit(svg_text: str, width: int, height: int, *, box: tuple[float, float] | None = None,
        bg: str | None = None) -> str:
    """Wrapper SVG of exactly width x height with the mark centred inside a box (default: the whole canvas)."""
    root = parse(svg_text)
    bw, bh = box or (width, height)
    vb = viewbox(root)
    s = min(bw / vb[2], bh / vb[3])
    cw, ch = vb[2] * s, vb[3] * s
    wrap = _wrapper(width, height, bg)
    wrap.append(nested(root, (width - cw) / 2, (height - ch) / 2, cw, ch))
    return dump(wrap)


def fit_in_circle(svg_text: str, size: int, radius_frac: float, *, bg: str | None) -> str:
    """Square canvas; the mark's viewBox rectangle is scaled so its half-diagonal fits inside radius_frac*size."""
    root = parse(svg_text)
    vb = viewbox(root)
    s = (radius_frac * size) / (math.hypot(vb[2], vb[3]) / 2)
    cw, ch = vb[2] * s, vb[3] * s
    wrap = _wrapper(size, size, bg)
    wrap.append(nested(root, (size - cw) / 2, (size - ch) / 2, cw, ch))
    return dump(wrap)


_UNSUPPORTED_MONO = ("linearGradient", "radialGradient", "pattern", "mask", "filter", "image", "style")
_PAINT_ATTRS = ("fill", "stroke", "stop-color", "color")


def mono(svg_text: str, color: str = "#000000") -> str:
    """Silhouette: every paint becomes one colour. Refuses artwork where that would be wrong."""
    root = parse(svg_text)
    for el in root.iter():
        local = el.tag.split("}")[-1]
        if local in _UNSUPPORTED_MONO:
            raise SvgError(f"cannot derive a silhouette automatically: <{local}> present; supply an authored "
                           f"monochrome SVG instead (--svg-mono)")
    for el in root.iter():
        for a in _PAINT_ATTRS:
            v = el.get(a)
            if v is not None and v.strip().lower() not in ("none", "currentcolor", "transparent", "inherit") \
                    and not v.strip().startswith("url("):
                el.set(a, color)
        st = el.get("style")
        if st:
            def sub(m):
                return f"{m.group(1)}:{color}" if m.group(2).strip().lower() not in ("none", "currentcolor") else m.group(0)
            el.set("style", re.sub(r"\b(fill|stroke|stop-color|color)\s*:\s*([^;]+)", sub, st))
    return dump(root)


def combine_scheme(light_text: str, dark_text: str | None) -> str:
    """icon.svg: the light artwork, switched to the dark artwork under prefers-color-scheme: dark."""
    root = parse(light_text)
    if dark_text is None:
        return dump(root)
    droot = parse(dark_text)
    if viewbox(root) != viewbox(droot):
        raise SvgError("light and dark SVG must share the same viewBox")
    ids = lambda r: {e.get("id") for e in r.iter() if e.get("id")}  # noqa: E731
    clash = ids(root) & ids(droot)
    if clash:
        raise SvgError(f"light and dark SVG share element ids {sorted(clash)}; rename them so the merge is unambiguous")
    out = ET.Element(_q("svg"), {k: v for k, v in root.attrib.items() if k not in ("width", "height")})
    out.set("viewBox", " ".join(f"{v:g}" for v in viewbox(root)))
    style = ET.SubElement(out, _q("style"))
    style.text = ".bc-d{display:none}@media (prefers-color-scheme:dark){.bc-l{display:none}.bc-d{display:inline}}"
    for cls, r in (("bc-l", root), ("bc-d", droot)):
        g = ET.SubElement(out, _q("g"), {"class": cls})
        for child in list(r):
            g.append(child)
    return dump(out)


_NO_PAINT = ("none", "currentcolor", "transparent", "inherit")
_STYLE_PAINT = re.compile(r"\b(fill|stroke|stop-color|color)\s*:\s*([^;]+)")


def _norm_hex(v: str) -> str | None:
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", v.strip())
    if not m:
        return None
    h = m.group(1).lower()
    return "#" + ("".join(c * 2 for c in h) if len(h) == 3 else h)


def _paints(root: ET.Element):
    """Yield (element, attribute-or-None, value) for every paint value (attribute, or a declaration inside style)."""
    for el in root.iter():
        for a in _PAINT_ATTRS:
            v = el.get(a)
            if v is not None:
                yield el, a, v
        st = el.get("style")
        if st:
            for m in _STYLE_PAINT.finditer(st):
                yield el, None, m.group(2)


def paint_colours(svg_text: str) -> list[str]:
    """The solid paint colours of an SVG as #rrggbb, in order of first appearance (none, currentColor and url(...) skipped).
    A paint that is not a hex colour (a colour name, rgb(), hsl()) raises SvgError: it cannot be mapped exactly."""
    out: dict[str, None] = {}
    for _el, _a, v in _paints(parse(svg_text)):
        s = v.strip()
        if s.lower() in _NO_PAINT or s.startswith("url("):
            continue
        h = _norm_hex(s)
        if h is None:
            raise SvgError(f"paint {s!r} is not a #rrggbb colour; write colours as hex so they can be mapped exactly")
        out.setdefault(h)
    return list(out)


def recolor(svg_text: str, mapping: dict[str, str]) -> str:
    """Replace every solid paint colour by mapping[colour] (both #rrggbb). A colour with no entry raises SvgError naming it:
    nothing is left half-converted. Gradients, patterns and filters are refused (their colours cannot be mapped by hand)."""
    root = parse(svg_text)
    for el in root.iter():
        local = el.tag.split("}")[-1]
        if local in _UNSUPPORTED_MONO:
            raise SvgError(f"cannot recolour automatically: <{local}> present; supply the dark artwork as its own file")
    norm = {_norm_hex(k): _norm_hex(v) for k, v in mapping.items()}
    missing = [c for c in paint_colours(svg_text) if c not in norm]
    if missing:
        raise SvgError(f"no replacement colour for {', '.join(missing)}")
    for el in root.iter():
        for a in _PAINT_ATTRS:
            v = el.get(a)
            if v is not None and v.strip().lower() not in _NO_PAINT and not v.strip().startswith("url("):
                el.set(a, norm[_norm_hex(v)])
        st = el.get("style")
        if st:
            def sub(m):
                s = m.group(2).strip()
                if s.lower() in _NO_PAINT or s.startswith("url("):
                    return m.group(0)
                return f"{m.group(1)}:{norm[_norm_hex(s)]}"
            el.set("style", _STYLE_PAINT.sub(sub, st))
    return dump(root)


def luma_hex(h: str) -> str:
    """The Rec. 709 grey of a #rrggbb colour, as #rrggbb (no gamma handling: the grey a tinted icon layer should carry)."""
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    y = round(0.2126 * r + 0.7152 * g + 0.0722 * b)
    return f"#{y:02x}{y:02x}{y:02x}"


def greyscale(svg_text: str) -> str:
    """Every paint colour becomes its Rec. 709 grey (two colours of equal luma stay equal: check the result)."""
    return recolor(svg_text, {c: luma_hex(c) for c in paint_colours(svg_text)})


def tile(svg_text: str, width: int, height: int, *, bg: str | None = None, content: float = 0.7, body: float = 1.0,
         radius: float = 0.0) -> str:
    """Wrapper SVG of exactly width x height: an optional ground (`bg`, a body x body rectangle centred on the canvas with corner
    radius `radius` x its shorter side) and the mark centred inside `content` x the body, aspect kept. body < 1 leaves a transparent
    margin (a macOS icon body inside its canvas); bg None leaves the ground transparent."""
    root = parse(svg_text)
    vb = viewbox(root)
    bw, bh = width * body, height * body
    wrap = _wrapper(width, height, None)
    if bg:
        ET.SubElement(wrap, _q("rect"), {"x": f"{(width - bw) / 2:g}", "y": f"{(height - bh) / 2:g}", "width": f"{bw:g}", "height": f"{bh:g}",
                                         "rx": f"{radius * min(bw, bh):g}", "fill": bg})
    s = min(bw * content / vb[2], bh * content / vb[3])
    cw, ch = vb[2] * s, vb[3] * s
    wrap.append(nested(root, (width - cw) / 2, (height - ch) / 2, cw, ch))
    return dump(wrap)

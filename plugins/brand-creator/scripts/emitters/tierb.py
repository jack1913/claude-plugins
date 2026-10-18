"""The Tier B platform emitters (android, chrome-ext, msix, profiles) and the watchOS and tvOS files of apple: what they share, and the gates
`check` runs over what they wrote.

Not a command. `TierBEmit` is `Emit` plus two rules:
  * a tier gate (exit 2 with the way up in any other tier): Full for the platform packs, Standard and Full for `profiles`;
  * a file that serves a spec row of status U is labelled "UNVERIFIED, recheck" in its manifest note and in its report row: a size that
    nobody read at the platform's page never ships looking verified.
`label_note()` is the same rule for the files of `emit apple` that belong to Tier B (they carry `labelled: true` in the manifest, so `check` holds them).
`rows(project)` is what `check` runs: the label rule re-read from the manifest, the Android adaptive layers, the MSIX unplated trio, the profile pack.
"""
from __future__ import annotations

import math
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import specs  # noqa: E402
from _emit import Emit, require_tier  # noqa: E402
from manifest import load_artefacts  # noqa: E402
from pxio import read_png  # noqa: E402

LABEL = "UNVERIFIED, recheck"
TIER_B = ("android", "chrome-ext", "msix", "profiles")
PACKS = {"android": "the Android pack", "chrome-ext": "the Chrome extension pack", "msix": "the MSIX pack", "profiles": "the profile pack"}
PROFILE_BANNERS = {"linkedin-banner": "profile-linkedin-banner", "x-header": "profile-x-banner", "youtube-banner": "profile-youtube-banner",
                   "facebook-cover": "profile-facebook-cover", "instagram-feed": "profile-instagram-feed", "instagram-story": "profile-instagram-story"}
TIERS = {"profiles": ("standard", "full")}   # every other Tier B pack is Full tier only
DEFAULT_TIERS = ("full",)
INK_ALPHA = 0x0E      # alpha at or above this counts as ink (below it is anti-aliasing noise)
INK_TOLERANCE_PX = 1.0  # a rasterised edge may sit this far past a geometric limit
ANDROID_NS = "http://schemas.android.com/apk/res/android"
FIT_MARGIN = 0.97     # the automatic size of a mark leaves this share of the room a margin allows
FIT_STEP = 0.01       # the automatic size is a whole percent of the canvas


def fit_share(room: float, extent_at_full: float, cap: float) -> float:
    """The largest mark box (a share of the canvas, in whole percents) at most `cap` whose ink stays within `room` px of the centre, given that the
    ink reaches `extent_at_full` px at a box of 1.0. Ink scales linearly about the centre, so one measurement is enough."""
    return round(math.floor(min(cap, room / extent_at_full * FIT_MARGIN) / FIT_STEP) * FIT_STEP, 2)


def label_note(rows: list[str], note: str) -> str:
    """The note of a file that serves `rows`: prefixed with the label when one of them is status U (the rule TierBEmit applies to its own files)."""
    u = unverified_rows(rows)
    return f"{LABEL} ({', '.join(u)}): {note}" if u else note


def label_report_row(rep, u_rows: list[str]) -> None:
    """Put the label on the report row just added (the `file:` row of the file just written), when its spec rows include a U one."""
    if u_rows:
        r = rep.results[-1]
        r["label"] = f"{r['label']} ({LABEL}: {', '.join(u_rows)})"


def unverified_rows(rows: list[str]) -> list[str]:
    return [r for r in dict.fromkeys(rows) if specs.row(r)["status"] == "U"]


class TierBEmit(Emit):
    """Emit for the Tier B packs: the pack's tier only (Full; Standard too for profiles), and U rows labelled on every file they serve."""

    def __init__(self, name, a, project):
        require_tier(project, TIERS.get(name, DEFAULT_TIERS), what=PACKS[name])
        super().__init__(name, a, project)

    def unverified(self, rows: list[str]) -> list[str]:
        out = []
        for r in rows:
            if specs.row(r)["status"] == "U" and r not in out:
                out.append(r)
        return out

    def put(self, rel: str, data: bytes, rows: list[str], **extra) -> bool:
        u = self.unverified(rows)
        if u:
            extra["note"] = f"{LABEL} ({', '.join(u)}): " + str(extra.get("note", ""))
        changed = super().put(rel, data, rows, **extra)
        self._label_last(u)
        return changed

    def slot(self, rel: str, data: bytes, rows: list[str], *, note: str = "", **kw) -> bool:
        u = self.unverified(rows)
        if u:
            note = f"{LABEL} ({', '.join(u)}): {note}"
        changed = super().slot(rel, data, rows, note=note, **kw)
        self._label_last(u)
        return changed

    def _label_last(self, u: list[str]) -> None:
        label_report_row(self.rep, u)


# ---------------------------------------------------------------- pixels

PNG_SIG = b"\x89PNG\r\n\x1a\n"
_HEAD = struct.calcsize(">I4s")   # a chunk's length and type
_CRC = struct.calcsize(">I")


def png_with_srgb(png: bytes) -> bytes:
    """The PNG with an sRGB chunk (rendering intent 0, perceptual) after IHDR, so the colour space the spec asks for is stated in the file."""
    if not png.startswith(PNG_SIG):
        raise ValueError("not a PNG")
    pos, ihdr_end = len(PNG_SIG), None
    while pos < len(png):
        n, typ = struct.unpack_from(">I4s", png, pos)
        if typ == b"sRGB":
            return png
        if typ == b"IHDR":
            ihdr_end = pos + _HEAD + n + _CRC
        pos += _HEAD + n + _CRC
    if ihdr_end is None:
        raise ValueError("a PNG without an IHDR chunk")
    body = b"\x00"
    chunk = struct.pack(">I", len(body)) + b"sRGB" + body + struct.pack(">I", zlib.crc32(b"sRGB" + body) & 0xFFFFFFFF)
    return png[:ihdr_end] + chunk + png[ihdr_end:]


def ink_far(png: bytes, *, ground: tuple[int, int, int] | None = None) -> float:
    """The largest distance (px) from the canvas centre to the centre of an ink pixel. Ink is alpha >= INK_ALPHA, or, with `ground`,
    a pixel whose colour differs from it by more than 8 in any channel (an opaque icon)."""
    w, h, px = read_png(png)
    cx, cy = w / 2, h / 2
    far2 = 0.0
    for y in range(h):
        base = y * w * 4
        dy2 = (y + 0.5 - cy) ** 2
        for x in range(w):
            i = base + x * 4
            if ground is None:
                if px[i + 3] < INK_ALPHA:
                    continue
            elif max(abs(px[i] - ground[0]), abs(px[i + 1] - ground[1]), abs(px[i + 2] - ground[2])) <= 8:
                continue
            d2 = (x + 0.5 - cx) ** 2 + dy2
            if d2 > far2:
                far2 = d2
    return far2 ** 0.5


def ink_bbox(png: bytes) -> tuple[int, int, int, int] | None:
    """(left, top, right, bottom) of the alpha >= INK_ALPHA pixels, right and bottom exclusive; None when there is no ink."""
    w, h, px = read_png(png)
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            if px[(y * w + x) * 4 + 3] >= INK_ALPHA:
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1) if xs else None


def ink_bbox_on(png: bytes, ground: tuple[int, int, int]) -> tuple[int, int, int, int] | None:
    """(left, top, right, bottom) of the pixels whose colour differs from `ground` by more than 8 in any channel (an opaque card); None when there are none."""
    w, h, px = read_png(png)
    xs, ys = [], []
    for y in range(h):
        base = y * w * 4
        for x in range(w):
            i = base + x * 4
            if max(abs(px[i] - ground[0]), abs(px[i + 1] - ground[1]), abs(px[i + 2] - ground[2])) > 8:
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1) if xs else None


def corner_alpha(png: bytes) -> int:
    w, _h, px = read_png(png)
    return px[3]


# ---------------------------------------------------------------- what check gates

def _rows_of(artefacts: list[dict]) -> list[dict]:
    """The files the label rule holds: every file of a Tier B emitter, and the watchOS and tvOS files of apple (they carry `labelled`)."""
    return [a for a in artefacts if a.get("emitter") in TIER_B or a.get("labelled")]


def label_problems(project: Path, artefacts: list[dict], stamped: dict) -> list[str]:
    """A file of a Tier B pack built from a spec row stamped U must say so in its note."""
    out = []
    for a in _rows_of(artefacts):
        u = [r for r in a.get("specs", []) if stamped.get(r, {}).get("status") == "U"]
        if u and LABEL not in str(a.get("note", "")):
            out.append(f"{a['path']} serves unverified spec row(s) {', '.join(u)} but its note lacks the label {LABEL!r}")
    return out


def android_problems(project: Path, artefacts: list[dict]) -> list[str]:
    """The adaptive icon XML names a background, a foreground and a monochrome layer, and each resolves to files of every density."""
    paths = {a["path"] for a in artefacts}
    out = []
    dpis = specs.sizes("android-densities")["dpi"]
    layers = specs.sizes("android-adaptive")["layers"]
    for a in artefacts:
        if a.get("emitter") != "android" or a.get("slot") != "android-adaptive-xml":
            continue
        f = project / a["path"]
        res = Path(a["path"]).parent.parent
        if not f.is_file():
            out.append(f"{a['path']}: missing")
            continue
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError as e:
            out.append(f"{a['path']}: not well-formed XML ({e})")
            continue
        if root.tag != "adaptive-icon":
            out.append(f"{a['path']}: root element is <{root.tag}>, not <adaptive-icon>")
            continue
        for layer in layers:
            el = root.find(layer)
            ref = el.get(f"{{{ANDROID_NS}}}drawable") if el is not None else None
            if el is None or not ref:
                out.append(f"{a['path']}: no <{layer}> layer with an android:drawable (a themed icon needs the explicit monochrome layer)")
                continue
            m = re.fullmatch(r"@(mipmap|color)/([A-Za-z0-9_]+)", ref)
            if not m:
                out.append(f"{a['path']}: <{layer}> drawable {ref!r} is neither @mipmap/<name> nor @color/<name>")
            elif m.group(1) == "color":
                p = (res / "values" / f"{m.group(2)}.xml").as_posix()
                if p not in paths or not (project / p).is_file():
                    out.append(f"{a['path']}: <{layer}> names @color/{m.group(2)} but {p} is not written")
            else:
                for d in dpis:
                    p = (res / f"mipmap-{d}" / f"{m.group(2)}.png").as_posix()
                    if p not in paths or not (project / p).is_file():
                        out.append(f"{a['path']}: <{layer}> names @mipmap/{m.group(2)} but {p} is not written")
                    elif layer == "monochrome" and ink_bbox((project / p).read_bytes()) is None:
                        out.append(f"{p}: the monochrome layer has no ink (an empty layer themes to nothing)")
    return out


def msix_problems(project: Path, artefacts: list[dict]) -> list[str]:
    """Every app-list target size has the plain file and each altform the spec asks for (without them Windows adds a backplate),
    and an unplated file has a transparent corner (an opaque ground is a backplate of our own)."""
    mine = [a for a in artefacts if a.get("emitter") == "msix"]
    if not mine:
        return []
    row = specs.sizes("msix-applist")
    paths = {a["path"] for a in mine}
    pat = re.compile(rf"^(.*/{re.escape(row['asset'])}\.targetsize-)(\d+)(_altform-\w+)?\.png$")
    groups: dict[str, set[str]] = {}
    for p in paths:
        m = pat.match(p)
        if m:
            groups.setdefault(m.group(1) + m.group(2), set()).add(m.group(3) or "")
    out = []
    if not groups:
        return [f"no {row['asset']}.targetsize-N files among the MSIX rows"]
    prefix = sorted(groups)[0].rsplit("targetsize-", 1)[0] + "targetsize-"
    for size in row["targetsizes"]:
        got = groups.get(f"{prefix}{size}")
        if got is None:
            out.append(f"{row['asset']}.targetsize-{size}: not written")
            continue
        for alt in ["", *[f"_altform-{x}" for x in row["altforms"]]]:
            if alt not in got:
                out.append(f"{row['asset']}.targetsize-{size}{alt}.png is missing: Windows adds a backplate when an altform is absent")
    for p in sorted(paths):
        m = pat.match(p)
        if m and m.group(3) and (project / p).is_file() and corner_alpha((project / p).read_bytes()) != 0:
            out.append(f"{p}: the corner pixel is not transparent; an unplated file with its own ground is a backplate")
    return out


def profile_problems(project: Path, artefacts: list[dict]) -> list[str]:
    """Every avatar size and every banner of the spec rows is written; the ink of each file still lies inside the safe area the manifest records for it
    (the circle of an avatar, the rectangle of a banner), read back from the pixels, so a file edited afterwards is caught. The ground is the corner pixel."""
    mine = [a for a in artefacts if a.get("emitter") == "profiles"]
    if not mine:
        return []
    out = []
    by_path = {a["path"]: a for a in mine}
    want = [(f"avatar-{n}.png", f"avatar-{n}") for n in specs.sizes("profile-avatar")["px"]]
    for fname, rid in PROFILE_BANNERS.items():
        sz = specs.sizes(rid)
        want.append((f"{fname}-{sz['width']}x{sz['height']}.png", fname))
    for name, label in want:
        if not any(p.endswith("/" + name) and (project / p).is_file() for p in by_path):
            out.append(f"{label}: {name} is not written")
    for a in mine:
        f = project / a["path"]
        if not f.is_file() or ("safe" not in a and "safe_radius_px" not in a):
            continue
        data = f.read_bytes()
        w, h, px = read_png(data)
        ground = (px[0], px[1], px[2])
        if f"{w}x{h}" != a.get("size"):
            out.append(f"{a['path']}: the file is {w}x{h}, the manifest says {a.get('size')}")
        if "safe_radius_px" in a:
            far = ink_far(data, ground=ground)
            if far > a["safe_radius_px"] + INK_TOLERANCE_PX:
                out.append(f"{a['path']}: ink {far:.0f} px from the centre, outside the safe circle of {a['safe_radius_px']:g} px")
        else:
            s = a["safe"]
            bb = ink_bbox_on(data, ground)
            if bb is not None and (bb[0] < s["x"] - INK_TOLERANCE_PX or bb[1] < s["y"] - INK_TOLERANCE_PX
                                   or bb[2] > s["x"] + s["width"] + INK_TOLERANCE_PX or bb[3] > s["y"] + s["height"] + INK_TOLERANCE_PX):
                out.append(f"{a['path']}: ink box {bb} is outside the safe rectangle")
    return out


def rows(project: Path) -> list[tuple[str, str, str, str]]:
    """-> [(id, status, label, detail)] for `check`; empty when the project has no Tier B file."""
    import json
    artefacts = load_artefacts(project)
    if not _rows_of(artefacts):
        return []
    mf = project / "assets" / "manifest.json"
    stamped = json.loads(mf.read_text(encoding="utf-8")).get("specs", {})
    out = []
    for rid, label, fn in (("tierb:labels", "files built from an unverified spec row carry the label", lambda: label_problems(project, artefacts, stamped)),
                           ("tierb:android", "the adaptive icon has background, foreground and monochrome layers at every density",
                            lambda: android_problems(project, artefacts)),
                           ("tierb:msix", "every app-list size has its plain, unplated and lightunplated files", lambda: msix_problems(project, artefacts)),
                           ("tierb:profiles", "every avatar size and banner is written and its ink lies inside its safe area", lambda: profile_problems(project, artefacts))):
        if rid == "tierb:android" and not any(a.get("emitter") == "android" for a in artefacts):
            continue
        if rid == "tierb:msix" and not any(a.get("emitter") == "msix" for a in artefacts):
            continue
        if rid == "tierb:profiles" and not any(a.get("emitter") == "profiles" for a in artefacts):
            continue
        probs = fn()
        out.append((rid, "fail" if probs else "pass", label, "; ".join(probs[:6]) if probs else "all present"))
    return out

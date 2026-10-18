#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator emit windows: the .ico and the NSIS installer images.

Writes under assets/windows/ (override with --out-dir) and records every file in assets/manifest.json.
  app.ico                 PNG-compressed layers from the windows-ico spec row; each layer is drawn by the band rule for its size
  nsis/header.bmp         NSIS header image, 24-bit BMP (ImageMagick: -alpha off -type TrueColor BMP3:), bit depth read back
  nsis/sidebar.bmp        NSIS welcome-page sidebar, 24-bit BMP
Sizes come from platform-specs.json only. The tray icons are `emit tray`. Needs gate G3 and ImageMagick (magick). Idempotent.
"""
import struct
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import svgtools  # noqa: E402
from _common import main_guard, run, which_or_cannot  # noqa: E402
from _emit import Emit  # noqa: E402
from determinism import magick_png_args  # noqa: E402
from pxio import read_ico_sizes, write_ico  # noqa: E402

MAGICK_HINT = "Install ImageMagick (macOS: brew install imagemagick; Linux: apt install imagemagick or your package manager; Windows: winget install ImageMagick.ImageMagick)."
BMP_HEADER = 14      # bytes of BITMAPFILEHEADER; the BITMAPINFOHEADER follows
BMP_CONTENT = 0.7    # share of the image the mark may fill


def bmp24(png: bytes) -> bytes:
    """A PNG (already opaque) as a 24-bit BMP through ImageMagick, so no alpha channel and no palette."""
    exe = which_or_cannot("magick", MAGICK_HINT)
    with tempfile.TemporaryDirectory(prefix="bc-bmp-") as td:
        src, dst = Path(td) / "in.png", Path(td) / "out.bmp"
        src.write_bytes(png)
        run([exe, str(src), "-alpha", "off", "-type", "TrueColor", *magick_png_args(), f"BMP3:{dst}"])
        return dst.read_bytes()


def bmp_info(data: bytes) -> tuple[int, int, int, int]:
    """(width, height, bits per pixel, compression) from a BMP header."""
    if data[:2] != b"BM":
        raise ValueError("not a BMP")
    fmt = "<IiiHHI"   # header size, width, height, planes, bits per pixel, compression
    _size, w, h, _planes, bits, comp = struct.unpack(fmt, data[BMP_HEADER:BMP_HEADER + struct.calcsize(fmt)])
    return w, abs(h), bits, comp


def main() -> int:
    e = Emit.begin("windows", __doc__)
    ico_row, nsis = e.sizes("windows-ico"), e.sizes("windows-nsis")
    bg = e.colour("light", "color.bg")

    # app.ico: every layer drawn for its own size by the band rule
    layers, bands = [], {}
    for s in ico_row["layers"]:
        d = e.drawing(s)
        layers.append(e.png(svgtools.fit(d.svg, s, s), s, s))
        bands[str(s)] = d.band
    ico = write_ico(layers)
    e.put(f"{e.out}/app.ico", ico, ["windows-ico"], slot="windows-ico", size=f"{max(ico_row['layers'])}x{max(ico_row['layers'])}",
          resampled_by="OURS", note="hand layers: each size is drawn, none is shrunk by the system", layers=list(ico_row["layers"]),
          layer_bands=bands)
    got, want = read_ico_sizes(ico), [(s, s) for s in ico_row["layers"]]
    e.rep.add("check:app.ico layers", "pass" if got == want else "fail", "layer sizes equal the spec row", detail=f"{got} vs {want}")

    # NSIS images: opaque ground, 24-bit BMP, bit depth read back from the header
    for fname, spec in (("header.bmp", nsis["header"]), ("sidebar.bmp", nsis["sidebar"])):
        w, h = spec["width"], spec["height"]
        d = e.drawing(max(w, h))
        png = e.png(svgtools.tile(d.svg, w, h, bg=bg, content=BMP_CONTENT), w, h, bg=bg)
        data = bmp24(png)
        e.slot(f"{e.out}/nsis/{fname}", data, ["windows-nsis"], slot=f"nsis-{fname.split('.')[0]}", size_px=(w, h), drawing=d,
               note="24-bit BMP on the light ground; the installer shows it as is")
        gw, gh, bits, comp = bmp_info(data)
        ok = (gw, gh, bits, comp) == (w, h, nsis["bit_depth"], 0)
        e.rep.add(f"check:{fname} bit depth", "pass" if ok else "fail", "BMP is 24-bit, uncompressed, at the spec size",
                  detail=f"{gw}x{gh}, {bits} bits per pixel, compression {comp}; wanted {w}x{h}, {nsis['bit_depth']}, 0")
    return e.finish()


main_guard(main)

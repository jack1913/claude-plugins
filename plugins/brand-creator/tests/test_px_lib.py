"""px_lib: the standard-library raster toolkit for generated marks (RGBA buffer, PNG and ICO writers, PNG reader, run-length SVG).

Oracles are outside the code under test: hand-derived bytes and path strings, a PNG chunk walk written here, ImageMagick's
decoder, resvg's renderer and the Acme example's committed files (rebuilt by its own tool).
"""
import os
import struct
import subprocess
import sys
import zlib

import pytest
from helpers import FIXTURES, ROOT

from px_lib import Img, from_png, grid_image, ico, rgba
from pxio import png_size, read_ico_sizes, read_png

INK, ACC = "#0d1b2d", "#007d71"


def chunks(png: bytes) -> list[str]:
    pos, out = 8, []
    while pos < len(png):
        n, typ = struct.unpack(">I4s", png[pos:pos + 8])
        out.append(typ.decode())
        pos += 12 + n
    return out


def test_colour_parsing_and_errors():
    assert rgba("#0d1b2d") == (13, 27, 45, 255)   # 0d=13 1b=27 2d=45, worked out by hand
    assert rgba("#0d1b2d80") == (13, 27, 45, 128)
    assert rgba((1, 2, 3)) == (1, 2, 3, 255)
    for bad in ("#12345", "red", (1, 2), (1, 2, 3, 256), "#gggggg"):
        with pytest.raises(ValueError):
            rgba(bad)


def test_pixel_operations():
    im = Img(4, 3)
    assert im.bbox() is None and im.colours() == []
    im.set(1, 1, INK)
    im.set(2, 1, ACC)
    im.set(9, 9, INK)  # outside: ignored, never an exception
    assert im.get(1, 1) == (13, 27, 45, 255) and im.get(0, 0) == (0, 0, 0, 0)
    assert im.bbox() == (1, 1, 2, 1)
    assert im.colours() == [(13, 27, 45, 255), (0, 125, 113, 255)]  # order of first appearance
    with pytest.raises(IndexError):
        im.get(4, 0)
    im.rect(0, 2, 10, 5, ACC)  # clipped to the image
    assert [im.get(x, 2) for x in range(4)] == [(0, 125, 113, 255)] * 4
    big = im.scaled(3)
    assert (big.w, big.h) == (12, 9) and big.get(3, 3) == (13, 27, 45, 255) and big.get(5, 5) == (13, 27, 45, 255)
    assert big.get(6, 3) == (0, 125, 113, 255) and big.get(2, 3) == (0, 0, 0, 0)
    with pytest.raises(ValueError):
        im.scaled(0)
    c = big.crop(3, 3, 3, 3)
    assert all(c.get(x, y) == (13, 27, 45, 255) for x in range(3) for y in range(3))
    dst = Img(8, 8, "#ffffff")
    dst.blit(im, 1, 1, 2)
    assert dst.get(0, 0) == (255, 255, 255, 255) and dst.get(3, 3) == (13, 27, 45, 255)
    assert Img(2, 2, INK) == Img(2, 2, INK) and Img(2, 2, INK) != Img(2, 2, ACC)
    with pytest.raises(ValueError):
        Img(0, 5)


def test_grid_image_reads_cells_and_refuses_bad_grids():
    im = grid_image(["XA.", ".AX"], {"X": INK, "A": ACC})
    assert (im.w, im.h) == (3, 2) and im.get(0, 0) == (13, 27, 45, 255) and im.get(2, 0) == (0, 0, 0, 0)
    with pytest.raises(ValueError, match="same length"):
        grid_image(["XX", "X"], {"X": INK})
    with pytest.raises(ValueError, match="no colour"):
        grid_image(["XQ"], {"X": INK})
    with pytest.raises(ValueError):
        grid_image([], {})


def test_png_has_only_the_three_fixed_chunks_and_the_right_header():
    im = grid_image(["XA", "AX"], {"X": INK, "A": ACC})
    data = im.png()
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and chunks(data) == ["IHDR", "IDAT", "IEND"]  # no tIME, no text, no gAMA
    assert png_size(data) == (2, 2)
    assert data[24:26] == b"\x08\x06"  # 8 bits per channel, colour type 6 (RGBA)
    n = struct.unpack(">I", data[33:37])[0]  # IDAT follows the 25-byte IHDR chunk: inflate it and read the scanlines
    raw = zlib.decompress(data[41:41 + n])
    assert raw == b"\x00" + bytes([13, 27, 45, 255, 0, 125, 113, 255]) + b"\x00" + bytes([0, 125, 113, 255, 13, 27, 45, 255])
    assert data == grid_image(["XA", "AX"], {"X": INK, "A": ACC}).png()  # same pixels, same bytes


def test_png_round_trips_through_the_reader():
    im = Img(5, 4)
    for y in range(4):
        for x in range(5):
            im.set(x, y, ((x * 50) % 256, (y * 60) % 256, (x * y * 7) % 256, 255 if (x + y) % 2 else 128))
    back = from_png(im.png())
    assert back == im


@pytest.mark.requires_magick
def test_png_and_ico_decode_in_imagemagick(tmp_path):
    im = Img(3, 2)
    im.set(0, 0, (255, 0, 0, 255))
    im.set(1, 0, (0, 255, 0, 128))
    im.set(2, 1, (0, 0, 255, 255))
    f = tmp_path / "t.png"
    f.write_bytes(im.png())
    raw = subprocess.run(["magick", str(f), "-depth", "8", "rgba:-"], capture_output=True, check=True).stdout
    assert raw == bytes(im.p)  # an independent decoder sees the same 3 x 2 RGBA pixels
    icon = tmp_path / "t.ico"
    icon.write_bytes(ico([Img(16, 16, INK), Img(32, 32, ACC)]))
    out = subprocess.run(["magick", "identify", str(icon)], capture_output=True, text=True, check=True).stdout
    assert " 16x16 " in out and " 32x32 " in out and len(out.strip().splitlines()) == 2


def test_ico_directory_and_256_entries():
    data = ico([Img(16, 16, INK), Img(256, 256, ACC)])
    assert struct.unpack("<HHH", data[:6]) == (0, 1, 2)
    assert read_ico_sizes(data) == [(16, 16), (256, 256)]  # 256 is stored as 0 and read back as 256
    assert data[6 + 16] == 0  # second entry's width byte
    size, off = struct.unpack("<II", data[6 + 16 + 8:6 + 16 + 16])  # second entry: bytes of image data, then its offset
    assert data[off:off + 8] == b"\x89PNG\r\n\x1a\n" and off + size <= len(data)
    with pytest.raises(ValueError, match="256"):
        ico([Img(300, 300, INK)])


def test_read_png_handles_the_filters_and_colour_types_other_tools_write(tmp_path):
    """Tools write filtered scanlines and non-RGBA types; the reader must decode them (ImageMagick makes the oracle files)."""
    import shutil
    if not shutil.which("magick"):
        pytest.skip("NOT VERIFIED: ImageMagick is not installed")
    src = tmp_path / "s.png"
    img = Img(5, 4)  # 19 distinct colours and one transparent pixel, so a palette needs 8 bits per index
    for i in range(1, 20):
        img.set(i % 5, i // 5, (i * 11, 200 - i * 7, i * 3))
    src.write_bytes(img.png())
    expect = bytes(from_png(src.read_bytes()).p)
    for name, args in (("rgb", ["-background", "white", "-alpha", "remove", "-define", "png:color-type=2"]),
                       ("palette", ["-colors", "32", "-define", "png:format=png8"]),
                       ("grey", ["-colorspace", "Gray", "-define", "png:color-type=0", "-define", "png:bit-depth=8"]),
                       ("sub", ["-define", "png:compression-filter=1"]), ("up", ["-define", "png:compression-filter=2"]),
                       ("avg", ["-define", "png:compression-filter=3"]), ("paeth", ["-define", "png:compression-filter=4"])):
        out = tmp_path / f"{name}.png"
        subprocess.run(["magick", str(src), *args, ("PNG8:" if name == "palette" else "") + str(out)], check=True, capture_output=True)
        w, h, px = read_png(out.read_bytes())
        raw = subprocess.run(["magick", str(out), "-depth", "8", "rgba:-"], capture_output=True, check=True).stdout
        assert (w, h) == (5, 4) and bytes(px) == raw, name  # ImageMagick decodes it to the same bytes
        if name in ("sub", "up", "avg", "paeth"):
            assert bytes(px) == expect, name
    with pytest.raises(ValueError, match="not a PNG"):
        read_png(b"GIF89a....")


def test_svg_is_run_length_one_path_per_colour_in_first_seen_order():
    im = grid_image(["XX.X", ".AA."], {"X": INK, "A": ACC})
    svg = im.svg()
    assert svg == ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 2" width="4" height="2" shape-rendering="crispEdges">'
                   '<path fill="#0d1b2d" d="M0 0h2v1h-2zM3 0h1v1h-1z"/><path fill="#007d71" d="M1 1h2v1h-2z"/></svg>')  # hand-derived
    assert im.svg(scale=6, title="T").count('width="24"') == 1 and "<title>T</title>" in im.svg(title="T")
    assert "<text" not in svg and "font" not in svg


@pytest.mark.requires_resvg
def test_svg_renders_to_the_same_pixels_as_the_buffer(tmp_path):
    """resvg is the independent renderer: the run-length SVG at scale 4 must equal the buffer enlarged 4 times."""
    im = grid_image(["XA.X", "A..A", "XAAX"], {"X": INK, "A": ACC})
    im.set(2, 1, (255, 0, 0, 128))
    f = tmp_path / "g.svg"
    f.write_text(im.svg(scale=4))
    out = tmp_path / "g.png"
    subprocess.run(["resvg", str(f), str(out)], check=True, capture_output=True)
    w, h, px = read_png(out.read_bytes())
    want = im.scaled(4)
    assert (w, h) == (want.w, want.h)
    for i in range(0, len(px), 4):
        a, b = px[i:i + 4], want.p[i:i + 4]
        if b[3] == 0:
            assert a[3] == 0
        elif b[3] == 255:
            assert tuple(a) == tuple(b)
        else:
            assert abs(a[3] - b[3]) <= 1 and all(abs(a[k] - b[k]) <= 2 for k in range(3))


def test_the_acme_grid_mark_is_rebuilt_byte_for_byte_by_its_own_tool(tmp_path):
    ex = FIXTURES
    tool = ex / "tools" / "grid_mark.py"
    out = tmp_path / "logo"
    r = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {str(tool.parent)!r}); import grid_mark; "
                        f"from pathlib import Path; [print(p.name) for p in grid_mark.build(Path({str(out)!r}))]"],
                       capture_output=True, text=True, env={**os.environ, "BRAND_CREATOR_ROOT": str(ROOT)})
    assert r.returncode == 0, r.stderr
    names = sorted(r.stdout.split())
    assert names == ["grid-mark-dark.svg", "grid-mark-master.png", "grid-mark.svg"]
    for n in names:
        assert (out / n).read_bytes() == (ex / "assets" / "logo" / n).read_bytes(), n
    # the master is the 10 x 10 grid enlarged 100 times, with the accent block 4 cells wide
    w, h, px = read_png((out / "grid-mark-master.png").read_bytes())
    assert (w, h) == (1000, 1000)

#!/usr/bin/env python3
"""Acme's tray masters: the three status glyphs (idle ring, active disc, error cross) drawn at 16, 20, 22 and 24 px.

    python3 tools/tray_masters.py          # writes assets/tray-src/<state>-<px>.png

`brand-creator emit tray` uses a master at its own size and enlarges it by a whole factor for the sizes it divides
(16 -> 32, 20 -> 40, 22 -> 44, 24 -> 48), so every tray size is drawn pixels, never a resample. Shape-coded: the three differ
without colour, and `brand-creator states-check` proves it for every size and theme `emit tray` writes (tray/tray.json names the
files). At 16 px each glyph equals the one of tools/state_icons.py.
"""
import os
import sys
from pathlib import Path


def _px_lib_dir() -> Path:
    root = os.environ.get("BRAND_CREATOR_ROOT")
    if root and (Path(root) / "scripts/lib/px_lib.py").is_file():
        return Path(root) / "scripts/lib"
    for p in Path(__file__).resolve().parents:
        if (p / "scripts/lib/px_lib.py").is_file():
            return p / "scripts/lib"
    sys.exit("px_lib.py not found: set BRAND_CREATOR_ROOT to the plugin folder (brand-creator exports it)")


sys.path.insert(0, str(_px_lib_dir()))
from px_lib import Img  # noqa: E402

SIZES = (16, 20, 22, 24)
INK, ACCENT = "#0d1b2d", "#007d71"


def glyph(kind: str, n: int) -> Img:
    im = Img(n, n)
    k = n / 16                       # every measure is the 16 px design scaled by k
    c = (n - 1) / 2
    for y in range(n):
        for x in range(n):
            d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
            if kind == "idle" and 4.0 * k <= d <= 6.2 * k:
                im.set(x, y, INK)
            elif kind == "active" and d <= 6.2 * k:
                im.set(x, y, ACCENT)
            elif kind == "error" and k <= x <= n - 1 - k and k <= y <= n - 1 - k and (abs(x - y) <= k or abs(x + y - (n - 1)) <= k):
                im.set(x, y, INK)
    return im


def build(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for kind in ("idle", "active", "error"):
        for n in SIZES:
            f = out_dir / f"{kind}-{n}.png"
            f.write_bytes(glyph(kind, n).png())
            files.append(f)
    return files


if __name__ == "__main__":
    for f in build(Path.cwd() / "assets" / "tray-src"):
        print(f"wrote {f.relative_to(Path.cwd())}")

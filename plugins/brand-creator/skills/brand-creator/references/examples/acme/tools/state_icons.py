#!/usr/bin/env python3
"""Acme's status glyphs at 16 px: idle (ring), active (disc), error (cross). Shape-coded, so they differ without colour.

    python3 tools/state_icons.py          # writes assets/states/idle.png, active.png, error.png

Built with brand-creator's px_lib; the same code always gives the same bytes. `brand-creator states-check` proves that
the three differ in greyscale and in silhouette (qa/states.json).
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

N = 16
INK, ACCENT = "#0d1b2d", "#007d71"


def glyph(kind: str) -> Img:
    im = Img(N, N)
    c = (N - 1) / 2
    for y in range(N):
        for x in range(N):
            d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
            if kind == "idle" and 4.0 <= d <= 6.2:
                im.set(x, y, INK)
            elif kind == "active" and d <= 6.2:
                im.set(x, y, ACCENT)
            elif kind == "error" and 1 <= x <= 14 and 1 <= y <= 14 and (abs(x - y) <= 1 or abs(x + y - (N - 1)) <= 1):
                im.set(x, y, INK)
    return im


def build(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for kind in ("idle", "active", "error"):
        f = out_dir / f"{kind}.png"
        f.write_bytes(glyph(kind).png())
        files.append(f)
    return files


if __name__ == "__main__":
    for f in build(Path.cwd() / "assets" / "states"):
        print(f"wrote {f.relative_to(Path.cwd())}")

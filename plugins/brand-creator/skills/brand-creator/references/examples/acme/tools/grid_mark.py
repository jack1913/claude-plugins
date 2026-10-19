#!/usr/bin/env python3
"""Acme's coarse-grid master: the small-size drawing of the mark, generated from a text grid with brand-creator's px_lib.

A platform that shrinks a file (home-screen icons, tab strips) gets this drawing, not the fine vector: every detail
is at least a tenth of the width, so the accent still holds a solid square at 16 px. Run it from the project root:

    python3 tools/grid_mark.py            # writes assets/logo/grid-mark.svg, grid-mark-dark.svg, grid-mark-master.png

It is a pure function of this file: the same grid and palette always give the same bytes (a test regenerates it).
"""
import os
import sys
from pathlib import Path


def _px_lib_dir() -> Path:
    root = os.environ.get("BRAND_CREATOR_ROOT")
    if root and (Path(root) / "scripts/lib/px_lib.py").is_file():
        return Path(root) / "scripts/lib"
    for p in Path(__file__).resolve().parents:  # inside the plugin tree (the worked example)
        if (p / "scripts/lib/px_lib.py").is_file():
            return p / "scripts/lib"
    sys.exit("px_lib.py not found: set BRAND_CREATOR_ROOT to the plugin folder (brand-creator exports it)")


sys.path.insert(0, str(_px_lib_dir()))
from px_lib import grid_image  # noqa: E402

# 10 x 10 cells. X = mark body, A = accent (a 4 x 4 block: at 16 px it is 6 px wide).
GRID = [
    "....XX....",
    "....XX....",
    "...XXXX...",
    "...XXXX...",
    "..XXXXXX..",
    "..XAAAAX..",
    ".XXAAAAXX.",
    ".XXAAAAXX.",
    "XXXAAAAXXX",
    "XXXXXXXXXX",
]
PALETTE = {"light": {"X": "#0d1b2d", "A": "#007d71"}, "dark": {"X": "#f0eee7", "A": "#4cd7c8"}}
MASTER_SCALE = 100  # 10 cells x 100 = a 1000 px master for the downscale check


def build(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for mode, suffix in (("light", ""), ("dark", "-dark")):
        img = grid_image(GRID, PALETTE[mode])
        f = out_dir / f"grid-mark{suffix}.svg"
        f.write_text(img.svg(scale=6, title="Acme coarse-grid mark") + "\n", encoding="utf-8")
        files.append(f)
        if mode == "light":
            m = out_dir / "grid-mark-master.png"
            m.write_bytes(img.scaled(MASTER_SCALE).png())
            files.append(m)
    return files


if __name__ == "__main__":
    for f in build(Path.cwd() / "assets" / "logo"):
        print(f"wrote {f.relative_to(Path.cwd())}")

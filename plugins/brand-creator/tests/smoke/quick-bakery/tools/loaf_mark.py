#!/usr/bin/env python3
"""The bakery's mark (synthetic smoke fixture): a loaf with a glowing cut, generated from a text grid with brand-creator's px_lib.

Run it from the project root:

    python3 tools/loaf_mark.py      # writes assets/logo/mark.svg, mark-dark.svg and mark-master.png

It is a pure function of this file: the same grid and palette always give the same bytes.
"""
import os
import sys
from pathlib import Path


def _px_lib_dir() -> Path:
    root = os.environ.get("BRAND_CREATOR_ROOT")
    if root and (Path(root) / "scripts/lib/px_lib.py").is_file():
        return Path(root) / "scripts/lib"
    sys.exit("px_lib.py not found: set BRAND_CREATOR_ROOT to the plugin folder (brand-creator exports it; `brand-creator root` prints it)")


sys.path.insert(0, str(_px_lib_dir()))
from px_lib import grid_image  # noqa: E402

# 10 x 10 cells. X = the loaf, A = the glowing cut (a 4 x 4 block: at 16 px it is 6 px wide).
GRID = [
    "...XXXX...",
    "..XXXXXX..",
    ".XXAAAAXX.",
    ".XXAAAAXX.",
    "XXXAAAAXXX",
    "XXXAAAAXXX",
    "XXXXXXXXXX",
    ".XXXXXXXX.",
    "..XXXXXX..",
    "..........",
]
PALETTE = {"light": {"X": "#2e1f16", "A": "#b4521e"}, "dark": {"X": "#f4e8d4", "A": "#f0a15a"}}
MASTER_SCALE = 100  # 10 cells x 100 = a 1000 px master for the downscale check


def build(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for mode, suffix in (("light", ""), ("dark", "-dark")):
        img = grid_image(GRID, PALETTE[mode])
        f = out_dir / f"mark{suffix}.svg"
        f.write_text(img.svg(scale=6, title="Marlow Lane Bakery loaf mark") + "\n", encoding="utf-8")
        files.append(f)
        if mode == "light":
            m = out_dir / "mark-master.png"
            m.write_bytes(img.scaled(MASTER_SCALE).png())
            files.append(m)
    return files


if __name__ == "__main__":
    for f in build(Path.cwd() / "assets" / "logo"):
        print(f"wrote {f.relative_to(Path.cwd())}")

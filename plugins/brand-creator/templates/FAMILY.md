# FAMILY: [[fill: family name]]

The profile of the parent brand, read by `brand-creator family-check` and by every designer pass in a family-member or
product-in-family project. Keep the prose short; the machine-readable block at the bottom is what the check reads.
Paths in the block are relative to this file (a sibling repository is fine; it is only ever read, never written, and
Python glyph sources are parsed, never executed).

## What every product of the family shares

- [[fill: the shared mark parts, for example the letters or the grid the products are built on]]
- [[fill: endorsement rule: how a product names its parent, and the spacing that must not change]]
- [[fill: what a product never borrows from the family (see architecture.md)]]

## Machine-readable block

```json family-check
{
  "schema": 1,
  "family": "[[fill: family name]]",
  "glyphs": {
    "family": {"file": "../brand/letters.py", "symbol": "LETTERS"},
    "own": {"file": "tools/glyphs.py", "symbol": "GLYPHS"},
    "shared": ["K", "e"],
    "compare": "shape"
  },
  "tiles": [
    {"product": "this", "mark": "assets/logo/mark.svg"},
    {"product": "sibling", "mark": "../sibling/assets/logo/mark.svg"}
  ],
  "tile_share_tolerance": 0.05,
  "parent_docs": ["../brand/README.md", "../brand/FAMILY.md"]
}
```

Fields:

- `glyphs.family` and `glyphs.own`: where the family's canonical glyph cells and this product's own cells live. A `.py`
  file is read with `ast.literal_eval` of the assignment named by `symbol` (a dict of glyph name to rows); a `.json`
  file is read as JSON, `symbol` being an optional dotted path. A glyph is a list of row strings (`.`, space, `0` and
  `_` are empty cells, anything else is filled) or a list of lists of 0 and 1.
- `glyphs.shared`: the glyph names that must be cell-equal in both sources. Reusing a family letter means copying its
  cells, never redrawing it. `compare` is `shape` (filled or empty, the default) or `exact` (the characters too).
- `parent_docs` (optional): documents of the parent brand (its README, book or own FAMILY.md; paths relative to this file, read only) that
  `brand-creator check --cascade "<old value>"` searches too, so a rule that changed here is not left standing in the parent's text.
- `tiles`: the marks whose tile share is compared. Each mark is rasterised (SVG) or read (PNG); the ground is the most frequent
  colour on the image's edge, the ink is everything else. The share of the tile the ink covers, and the height of its bounding
  box, must agree across products within `tile_share_tolerance` (a fraction of the tile; default from
  `qa/rules.json` family.tile_share_tolerance, proposal 0.05).

# Third-party notices

brand-creator itself is MIT licensed (see `LICENSE`). This file lists everything that is vendored, borrowed or
installed on the user's machine by `brand-creator setup`, with source, version, licence and the files it affects.

A test (`tests/test_static.py`) checks that every vendored file under `scripts/vendor/` is listed here.

## Installed by `brand-creator setup` (not vendored; fetched into the plugin data directory)

| Item | Version | Licence | Used by |
|---|---|---|---|
| playwright-core (https://github.com/microsoft/playwright) | 1.61.1 | Apache-2.0 | `scripts/render.mjs` (the only Chromium driver) |
| Chrome Headless Shell (Playwright build 1228) | per playwright-core | BSD-3-Clause and component licences | rendering |
| style-dictionary (https://github.com/style-dictionary/style-dictionary) | 5.7.0 | Apache-2.0 | `scripts/build_tokens.mjs` |
| culori (https://github.com/Evercoder/culori) | 4.0.2 | MIT | gamut mapping check in `scripts/build_tokens.mjs` |
| colorjs.io (https://github.com/color-js/color.js) | 0.7.1 | MIT | APCA advisory column (computed in `scripts/build_tokens.mjs`) |
| @google/design.md (https://github.com/google-labs-code/design.md) | 0.4.0 | Apache-2.0 (the LICENSE file in the package; the package.json has no licence field) | `scripts/adapters.py` runs its `lint` on DESIGN.md. Used unmodified from npm, not redistributed. Its pinned dependencies (citty, remark and micromark packages, unified, yaml, zod and others, all in `scripts/package-lock.json`) were read from the lock: MIT or ISC, except `format` 0.2.2, whose package.json carries no `license` field and whose own `licenses` field and Readme say MIT |

Transitive npm dependencies are pinned in `scripts/package-lock.json`.

## Python packages (fetched by `uv run --script` into uv's cache; pinned in each script's PEP 723 block and `.lock` file)

Licences below were read from the installed packages' own metadata and licence files (2026-10-18), not from memory.

| Package | Version | Licence | Used by |
|---|---|---|---|
| ColorAide (https://github.com/facelessuser/coloraide) | 8.13.1 | MIT | `scripts/contrast.py --cvd` (colour-vision simulation, CIEDE2000) |
| fontTools (https://github.com/fonttools/fonttools) | 4.62.1 | MIT | `scripts/outline_glyphs.py`, `scripts/fontcheck.py` |
| Brotli (https://github.com/google/brotli) | 1.1.0 | MIT | `scripts/fontcheck.py` (reads .woff2 fonts) |
| skia-pathops (https://github.com/fonttools/skia-pathops) | 0.9.2 | BSD-3-Clause | `scripts/outline_glyphs.py` (overlap removal) |
| Pillow (https://github.com/python-pillow/Pillow) | 11.3.0 | MIT-CMU (HPND) | `scripts/downscale_check.py --renderer=pillow` (PNG resampling only); `scripts/emitters/tauri.py --renderer pillow` (the .icns writer) |
| pikepdf (https://github.com/pikepdf/pikepdf) | 10.17.0 | MPL-2.0 | `scripts/book_pdf.py` (sets the PDF metadata of `book.pdf`), `scripts/emitters/print.py` and `scripts/print_check.py` (boxes, metadata and read-back of the print PDFs). Used unmodified from PyPI, not redistributed. Its dependencies are pinned in the script's lock: lxml 6.1.3 (BSD-3-Clause), packaging 26.3 (Apache-2.0 OR BSD-2-Clause) and Pillow 13.0.0 (MIT-CMU), licences read from the installed metadata; the qpdf library inside pikepdf's wheel was not inspected here |
| jsonschema (https://github.com/python-jsonschema/jsonschema) | 4.26.0 | MIT | `scripts/emitters/apple.py` (runs the vendored Icon Composer validator); its dependencies referencing 0.37.0, rpds-py 2026.9.1, attrs 26.1.0 and jsonschema-specifications 2025.9.1 are MIT (read from the installed metadata) and pinned in the script's lock; the lock also pins rpds-py 0.30.0 and typing-extensions 4.16.0 for older interpreters, which were not installed here and whose licences were not read |

ColorAide's simulations follow Brettel, Viénot and Mollon 1997 (protanopia, deuteranopia, tritanopia) and Viénot, Brettel and
Mollon 1999 (protanopia, deuteranopia); both are published methods, implemented by the library, not copied here.

APCA note: the APCA lightness contrast (Lc) column is advisory only. It is computed by colorjs.io (MIT), not by
vendoring apca-w3 (which carries a limited W3 licence). WCAG 3 is a working draft and is never claimed.

## System tools (not bundled)

resvg (MPL-2.0), ImageMagick, Ghostscript (AGPL-3.0), poppler, potrace (GPL-2.0) are called as external programs when
present. They are not redistributed with this plugin.

## Vendored files

Under `scripts/vendor/giginet-icon-composer/` (copied unchanged, read-only fetch with `gh api`, 2026-10-18):

- Source: https://github.com/giginet/apple-icon-composer-skill, pinned at commit `43b96bf200e088149abef29a1b999c70589bed81`
  (committed 2026-10-01). Licence: Apache-2.0; the licence text is kept as `scripts/vendor/giginet-icon-composer/LICENSE` (the repository
  carries no NOTICE file). Copyright remains with the repository's authors.
- Files, with their path in that repository:
  - `scripts/vendor/giginet-icon-composer/icon-schema.json` from `plugins/icon-composer/skills/compose-app-icon/scripts/icon-schema.json`
    (the JSON Schema of an Icon Composer `icon.json`, covering Icon Composer 1.x and 2.0; the format itself is undocumented by Apple)
  - `scripts/vendor/giginet-icon-composer/validate_icon.py` from `plugins/icon-composer/skills/compose-app-icon/scripts/validate_icon.py`
    (schema validation plus the check that every image an `icon.json` names is in `Assets/`)
  - `scripts/vendor/giginet-icon-composer/LICENSE` from `LICENSE`
- Use: `scripts/emitters/apple.py` validates every `.icon` it writes with the vendored validator before actool compiles it. No file was
  modified; the validator imports `jsonschema`, which `apple.py` declares in its own pinned block (see the table above).
- sha256 of the vendored copies: `icon-schema.json` 381f27a4dd52e3c62b69e340e21abe0cd249d1a78dc3112d2676e464e4c79e80,
  `validate_icon.py` 148d69ad56911637d99380cd2115be4a7824bcd9aa4fe8755b4d422c68efffc9, `LICENSE`
  c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4. To update: fetch the same three files at a newer commit, re-run the tests, and change the SHA here.

Test fixtures (not part of the shipped behaviour, used only by the tests):

- `tests/fixtures/giginet/version2-complex.icon.json` and `tests/fixtures/giginet/scaled-layer.icon.json`: the `icon.json` of the
  repository's `fixtures/version2-complex.icon` and `fixtures/scaled-layer.icon` at the commit above (Apache-2.0, same licence text),
  used to show that the vendored validator accepts documents written by Icon Composer itself.

- `tests/fixtures/fonts/TestFont-subset.ttf`: a subset of the Inter variable font (https://github.com/rsms/inter, taken from
  https://github.com/google/fonts at commit e1d6480102fed30739fead0faee463101f892c8f), SIL Open Font License 1.1, copyright
  2016 The Inter Project Authors (the font's own name table; the licence file copied from the same repository reads 2020).
  The licence text is `tests/fixtures/fonts/OFL.txt`; the modification (subsetting to Basic Latin and the Polish and German
  letters, layout features and hinting dropped) is described in `tests/fixtures/fonts/README.md`. The subset is not sold
  on its own and is not shipped to users' projects.

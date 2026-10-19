# Test font fixture

`TestFont-subset.ttf` is a subset of the Inter variable font (axes opsz and wght), used only by the tests of
`outline_glyphs.py`, `fontcheck.py` and `render.mjs fonts`. Tests never touch the network.

- Source: https://github.com/google/fonts/blob/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf (commit
  e1d6480102fed30739fead0faee463101f892c8f of google/fonts), upstream https://github.com/rsms/inter
- Licence: SIL Open Font License 1.1, full text in `OFL.txt` (copyright 2016 The Inter Project Authors). The font has no
  Reserved Font Name, so the subset keeps the name; it is a modified version and is not sold on its own.
- Modification: pyftsubset-style subsetting with fontTools to Basic Latin, no-break space, the Polish letters
  (ĄĆĘŁŃÓŚŹŻ and their lower case) and the German letters (ÄÖÜ, ä ö ü, ß). Layout features and hinting were
  dropped; the variation tables, the name table (licence text and URL, name ids 13 and 14) and the OS/2 table stayed.
- What the coverage is used for: `pl` and `de` language sets are covered, `cs` and `tr` are not (the tests assert
  the exact missing letters, worked out by hand from the language files).
- Listed in THIRD_PARTY_NOTICES.md.

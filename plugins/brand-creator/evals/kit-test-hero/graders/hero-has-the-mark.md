---
type: regex
pattern: 'mark(?:-dark|-animated)?\.(?:svg|png)'
flags: i
target: { source: file, path: kit-test/hero.html }
weight: 1
---
The hero shows the brand's mark from a logo file of the kit (mark, wordmark, animated mark or their dark twins), not a drawing of its own.

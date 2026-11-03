---
type: regex
pattern: 'var\(--'
target: { source: file, path: kit-test/hero.html }
weight: 1
---
The hero takes its values from the kit's CSS variables, not from values typed into the page.

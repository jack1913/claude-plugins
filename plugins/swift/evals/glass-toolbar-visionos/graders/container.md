---
# Grouped glass needs a GlassEffectContainer, because glass can't sample other
# glass. A bar that gets glass once, on the one surface holding its buttons,
# has nothing to group, and the skill says not to add containers
# unnecessarily. So: pass on a container, or on exactly one glass call in the
# file. Several glass calls without a container, or none at all, fail.
type: regex
pattern: 'GlassEffectContainer|^(?=[\s\S]*?(?:\.glassEffect\(|\.buttonStyle\(\s*\.glass(?:Prominent)?\s*\)))(?![\s\S]*?(?:\.glassEffect\(|\.buttonStyle\(\s*\.glass(?:Prominent)?\s*\))[\s\S]*?(?:\.glassEffect\(|\.buttonStyle\(\s*\.glass(?:Prominent)?\s*\)))'
target: { source: file, path: Sources/Demo/ContentView.swift }
---

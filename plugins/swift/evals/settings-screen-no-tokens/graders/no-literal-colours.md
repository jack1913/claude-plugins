---
type: regex
pattern: 'Color\(\s*(red|hex|\.sRGB)|UIColor\(\s*red|#[0-9A-Fa-f]{6}'
match: not_contains
target: { source: file, path: Sources/Demo/SettingsView.swift }
---

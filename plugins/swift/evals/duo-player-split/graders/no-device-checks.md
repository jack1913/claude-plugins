---
# Layout follows the proposal and size classes, never the device, the screen or the
# orientation. onHingeChange is allowed: the skill permits it for optional effects.
type: regex
pattern: 'UIDevice|UIScreen\.main|\.orientation\b'
match: not_contains
target: { source: file, path: Sources/Demo/PlayerScreen.swift }
---

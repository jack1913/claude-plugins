---
# Layout follows the proposal and size classes, never the device, the screen, the
# orientation or the hinge.
type: regex
pattern: 'UIDevice|UIScreen\.main|\.orientation\b|onHingeChange'
match: not_contains
target: { source: file, path: Sources/Demo/PlayerScreen.swift }
---

---
# Swift Testing's event confirmation, called with parentheses or as a
# trailing closure (`confirmation { confirmed in ... }`).
type: regex
pattern: '\bconfirmation\s*[({]'
target: { source: file, path: Tests/DemoTests/SaverTests.swift }
---

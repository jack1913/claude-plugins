---
# Saver calls back later on a global queue, so a confirmation body that just
# calls save(3) returns first and fails at runtime ("confirmed 0 times"). The
# body must wait for the callback, e.g. with a continuation or a stream.
type: regex
pattern: 'with(?:Checked|Unsafe)(?:Throwing)?Continuation|AsyncStream|makeStream'
target: { source: file, path: Tests/DemoTests/SaverTests.swift }
---

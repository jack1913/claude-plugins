---
# AGENTS.md forbids async let; swift:concurrency's tool table recommends it
# for fixed parallel operations, so this is where the conflict shows.
# A line that mentions it only in a comment ("not `async let`") is fine.
type: regex
pattern: '^[^/\n]*\basync\s+let\b'
flags: m
match: not_contains
target: { source: file, path: Sources/Demo/DashboardLoader.swift }
---

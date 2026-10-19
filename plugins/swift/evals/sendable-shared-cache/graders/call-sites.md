---
# The harness has no build grader, and `target: files` matches changed file
# paths, not contents, so no regex can pair Cache.swift's new API with
# Downloader.swift's call sites. This llm grader judges the final reply
# (its default input) for that pairing instead.
type: llm
---

PASS if the reply says how Sources/Demo/Downloader.swift's ImageCache calls fit the new ImageCache: `await` added because ImageCache became an actor, or no call-site change needed because ImageCache is a lock-protected Sendable class with synchronous methods.
FAIL if ImageCache became an actor and the reply does not mention adding `await` at the call sites, or if the reply says an opt-out (nonisolated(unsafe), @unchecked Sendable, @preconcurrency) was kept or added.

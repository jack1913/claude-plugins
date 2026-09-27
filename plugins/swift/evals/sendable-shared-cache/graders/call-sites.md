---
type: llm
target: { source: files }
---

PASS if Sources/Demo/Downloader.swift matches the new ImageCache API in Sources/Demo/Cache.swift: its ImageCache calls use `await` when ImageCache is an actor, and are plain synchronous calls when ImageCache is a lock-protected Sendable class (for example one using OSAllocatedUnfairLock).
FAIL if Downloader.swift would not compile against Cache.swift — for example an actor's methods called without `await` — or if either file still uses nonisolated(unsafe), @unchecked Sendable or @preconcurrency.

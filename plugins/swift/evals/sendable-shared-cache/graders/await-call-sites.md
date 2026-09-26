---
type: regex
pattern: 'await\s+ImageCache\.shared|await\s+\w+\.data\(forKey|await\s+\w+\.insert\('
target: { source: file, path: Sources/Demo/Downloader.swift }
---

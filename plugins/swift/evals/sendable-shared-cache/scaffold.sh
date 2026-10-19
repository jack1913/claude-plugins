#!/usr/bin/env bash
# Workspace: a Swift 6 package whose shared cache silences data-race checking
# with nonisolated(unsafe) opt-outs.
set -euo pipefail
mkdir -p Sources/Demo
cat > Package.swift <<'SWIFT'
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Demo",
    platforms: [.macOS("14.0")],
    targets: [.target(name: "Demo")]
)
SWIFT
cat > Sources/Demo/Cache.swift <<'SWIFT'
import Foundation

public final class ImageCache {
    nonisolated(unsafe) public static let shared = ImageCache()
    nonisolated(unsafe) private var storage: [String: Data] = [:]

    public func data(forKey key: String) -> Data? { storage[key] }
    public func insert(_ data: Data, forKey key: String) { storage[key] = data }
}
SWIFT
cat > Sources/Demo/Downloader.swift <<'SWIFT'
import Foundation

public func download(_ key: String, from url: URL) async throws -> Data {
    if let cached = ImageCache.shared.data(forKey: key) { return cached }
    let (data, _) = try await URLSession.shared.data(from: url)
    ImageCache.shared.insert(data, forKey: key)
    return data
}
SWIFT

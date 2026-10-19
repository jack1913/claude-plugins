#!/usr/bin/env bash
# Workspace: a Swift 6 package whose Saver reports saves through a callback
# delivered later on a global queue, and an empty test target.
set -euo pipefail
cat > Package.swift <<'SWIFT'
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Demo",
    platforms: [.macOS("14.0")],
    targets: [
        .target(name: "Demo"),
        .testTarget(name: "DemoTests", dependencies: ["Demo"]),
    ]
)
SWIFT
mkdir -p Sources/Demo Tests/DemoTests
cat > Sources/Demo/Saver.swift <<'SWIFT'
import Foundation

public final class Saver: Sendable {
    private let onSave: @Sendable (Int) -> Void

    public init(onSave: @escaping @Sendable (Int) -> Void) {
        self.onSave = onSave
    }

    public func save(_ n: Int) {
        DispatchQueue.global().async { [onSave] in onSave(n) }
    }
}
SWIFT

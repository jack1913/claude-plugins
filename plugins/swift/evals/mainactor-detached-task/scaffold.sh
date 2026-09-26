#!/usr/bin/env bash
# Workspace: a Swift 6 package whose @MainActor model mutates state from a
# detached task that also runs a heavy synchronous computation.
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
cat > Sources/Demo/PlayerModel.swift <<'SWIFT'
import Foundation
import Observation

@MainActor
@Observable
final class PlayerModel {
    var score = 0
    var badge = ""

    func load() {
        Task.detached {
            let s = Self.computeScore()
            self.score = s
            self.badge = String(repeating: "*", count: s % 10)
        }
    }

    nonisolated static func computeScore() -> Int {
        (0..<1_000_000).reduce(0) { $0 + $1 % 7 }
    }
}
SWIFT

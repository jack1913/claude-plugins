#!/usr/bin/env bash
# Workspace: a Swift 6 package whose @MainActor model mutates state from a
# detached task — a real strict-concurrency isolation error.
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

    func load() {
        Task.detached {
            self.score = await Self.fetchScore()
        }
    }

    static func fetchScore() async -> Int { 42 }
}
SWIFT

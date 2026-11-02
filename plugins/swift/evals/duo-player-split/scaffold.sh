#!/usr/bin/env bash
# Workspace: a Swift package targeting iOS 26 / macOS 15, so the 27.1 arrangement APIs need a gate
# that names macOS too.
set -euo pipefail
mkdir -p Sources/Demo
cat > Package.swift <<'SWIFT'
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Demo",
    platforms: [.iOS("26.0"), .macOS("15.0")],
    targets: [.target(name: "Demo")]
)
SWIFT
cat > Sources/Demo/PlayerScreen.swift <<'SWIFT'
import SwiftUI

struct PlayerView: View {
    var body: some View {
        Text("Now Playing")
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct UpNextView: View {
    var body: some View {
        List(1..<20) { Text("Track \($0)") }
    }
}

struct PlayerScreen: View {
    var body: some View {
        HStack(spacing: 0) {
            PlayerView()
            UpNextView()
        }
    }
}
SWIFT

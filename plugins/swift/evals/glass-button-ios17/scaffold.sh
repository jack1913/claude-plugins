#!/usr/bin/env bash
# Workspace: a Swift package targeting iOS 17.5 / macOS 14, so any 26-only API needs a gate.
set -euo pipefail
mkdir -p Sources/Demo
cat > Package.swift <<'SWIFT'
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Demo",
    platforms: [.iOS("17.5"), .macOS("14.0")],
    targets: [.target(name: "Demo")]
)
SWIFT
cat > Sources/Demo/ContentView.swift <<'SWIFT'
import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack {
            Text("Welcome")
                .font(.largeTitle)
        }
    }
}
SWIFT

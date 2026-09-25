#!/usr/bin/env bash
# Workspace: a Swift package for iOS 26 and visionOS 26, so glass needs a visionOS branch.
set -euo pipefail
mkdir -p Sources/Demo
cat > Package.swift <<'SWIFT'
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Demo",
    platforms: [.iOS("26.0"), .visionOS("26.0")],
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

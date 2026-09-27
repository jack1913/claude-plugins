#!/usr/bin/env bash
# Workspace: a Swift 6 package with a slugify function and an empty test target.
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
cat > Sources/Demo/Slug.swift <<'SWIFT'
import Foundation

public func slugify(_ s: String) -> String {
    let mapped = s.lowercased().map { $0.isLetter || $0.isNumber ? $0 : "-" }
    var out = ""
    for c in mapped where !(c == "-" && out.last == "-") { out.append(c) }
    return out.trimmingCharacters(in: CharacterSet(charactersIn: "-"))
}
SWIFT

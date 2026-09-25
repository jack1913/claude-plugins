#!/usr/bin/env bash
# Workspace: an iOS 26 package with a view that has no preview yet.
set -euo pipefail
mkdir -p Sources/Demo
cat > Package.swift <<'SWIFT'
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Demo",
    platforms: [.iOS("26.0")],
    targets: [.target(name: "Demo")]
)
SWIFT
cat > Sources/Demo/InboxView.swift <<'SWIFT'
import SwiftUI

struct Message: Identifiable {
    let id = UUID()
    let sender: String
    let subject: String
}

struct InboxView: View {
    let messages: [Message]

    var body: some View {
        List(messages) { message in
            VStack(alignment: .leading) {
                Text(message.sender).font(.headline)
                Text(message.subject)
            }
        }
    }
}
SWIFT

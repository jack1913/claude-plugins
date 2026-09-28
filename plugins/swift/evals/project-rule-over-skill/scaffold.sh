#!/usr/bin/env bash
# Workspace: a Swift 6 package whose project instructions (CLAUDE.md importing
# AGENTS.md, as real repos do) forbid async let, and a loader stub that needs
# two fixed parallel calls -- the case swift:concurrency's tool table answers
# with async let. The rule names no type from the code, so only an agent that
# looks for the project's rules on purpose finds it (the eval sandbox does not
# load a project's CLAUDE.md).
set -euo pipefail
mkdir -p Sources/Demo
cat > CLAUDE.md <<'MD'
@AGENTS.md
MD
cat > AGENTS.md <<'MD'
# AGENTS.md

## Hard rules

- Never use `async let` in this codebase: it has crashed the app at runtime. Run fixed parallel work in a `withThrowingTaskGroup` instead.
MD
cat > Package.swift <<'SWIFT'
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Demo",
    platforms: [.macOS("14.0")],
    targets: [.target(name: "Demo")]
)
SWIFT
cat > Sources/Demo/APIClient.swift <<'SWIFT'
struct APIError: Error, Sendable {
    let code: Int
}

struct Profile: Sendable {
    let name: String
}

struct Settings: Sendable {
    let theme: String
}

final class APIClient: Sendable {
    func profile() async throws(APIError) -> Profile {
        Profile(name: "Jordan")
    }

    func settings() async throws(APIError) -> Settings {
        Settings(theme: "dark")
    }
}
SWIFT
cat > Sources/Demo/DashboardLoader.swift <<'SWIFT'
struct DashboardLoader: Sendable {
    let client: APIClient

    func load() async throws -> (Profile, Settings) {
        fatalError("TODO")
    }
}
SWIFT

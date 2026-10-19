---
type: llm
focus: { source: file, path: Sources/Demo/ContentView.swift }
---

PASS if every use of glassEffect, GlassEffectContainer, .glass or .glassProminent in the file compiles only for non-visionOS platforms (inside the #else of an #if os(visionOS) block, or inside #if !os(visionOS)), and the visionOS branch uses glassBackgroundEffect or an ornament instead.
FAIL if any of those glass APIs would compile for visionOS, or if there is no visionOS branch.

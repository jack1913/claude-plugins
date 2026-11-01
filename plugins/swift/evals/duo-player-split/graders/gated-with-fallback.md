---
type: llm
focus: { source: file, path: Sources/Demo/PlayerScreen.swift }
---

PASS if every use of ArrangementView and arrangementViewStyle in the file compiles only on iOS 27.1 and macOS 27.1 or later: inside the true branch of an `if #available` that names both (or the else branch of an `if #unavailable` that names both, or under `anyAppleOS 27.1`), or in a declaration marked `@available` with both and reached only from inside such a branch. The other branch must still show the original HStack layout of PlayerView and UpNextView, written there directly or through a property or view it calls.
FAIL if ArrangementView or arrangementViewStyle can compile for iOS 26 or macOS 15 outside such a check, or if the HStack layout is not the earlier-OS branch.

# Commands

Everything swift adds to Claude Code. "You only" means it runs only when you type it; "you or Claude" means Claude can also start it when your request matches.

## Commands and skills

| Command | Starts | What it does | Arguments |
| --- | --- | --- | --- |
| `/swift:swiftui` | you or Claude | Writes, reviews and refactors SwiftUI with current APIs for iOS, iPadOS, macOS and visionOS | — |
| `/swift:design` | you or Claude | Designs and restyles screens the Apple-native way: hierarchy, type, colour, symbols, motion and design tokens | — |
| `/swift:concurrency` | you or Claude | Writes and fixes Swift concurrency code, and migrates a project to Swift 6 | — |
| `/swift:testing` | you or Claude | Writes tests with Swift Testing and migrates XCTest suites | — |
| `/swift:review` | you only | Reviews a SwiftUI screen against Apple's Human Interface Guidelines, from its code or screenshots, and only reports | `<view files or screenshot paths>` |

Claude starts the first four when your request matches, so you rarely type them. Type one to be sure it loads. The full topic list per skill is in [What the plugin covers](capabilities.md).

## /swift:review

Reviews what you name: SwiftUI view files, screenshots, or both. With no files and no images it asks which screen to review. It never edits a file. How-to: [Review a screen](../use/review-a-screen.md).

| Argument | What it does | Default |
| --- | --- | --- |
| `<view files or screenshot paths>` | The screen to review: one or more `.swift` files, image paths, or both. Images pasted into the conversation count too | Asks which screen |

Examples:

> /swift:review Sources/Demo/SettingsView.swift
>
> /swift:review screenshot.png

## The other four skills

They take no arguments. Describe what you want in the same message. How-to pages: [Build a SwiftUI screen](../use/build-a-swiftui-screen.md), [Fix a concurrency error](../use/fix-a-concurrency-error.md) and [Write tests](../use/write-tests.md).

---
# Fails when any `#Preview` line is not inside an open `#if DEBUG` block.
# The lookbehind walks back from the `#Preview` line to an `#if DEBUG` line
# over plain lines and over closed one-level `#if ... #endif` blocks, and it
# allows one still-open nested `#if` (such as `#if os(iOS)`) right above the
# preview. An `#else`, `#elseif` or `#endif` of the DEBUG block breaks the
# walk, so a preview after `#endif` or in an `#else` branch counts as
# unguarded. has-preview.md checks that a preview exists at all.
type: regex
pattern: '^(?<!^[ \t]*#if[ \t]+DEBUG\b[^\n]*\n(?:(?![ \t]*#(?:if|elseif|else|endif)\b)[^\n]*\n|[ \t]*#if\b[^\n]*\n(?:(?![ \t]*#(?:if|endif)\b)[^\n]*\n)*[ \t]*#endif\b[^\n]*\n)*(?:[ \t]*#if\b[^\n]*\n(?:(?![ \t]*#(?:if|endif)\b)[^\n]*\n)*)?)[ \t]*#Preview\b'
flags: m
match: not_contains
target: { source: file, path: Sources/Demo/InboxView.swift }
---

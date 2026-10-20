# Build a SwiftUI screen

Ask for a screen in plain words. `swift:design` and `swift:swiftui` load on their own. You don't name them.

## Ask

In a Swift package or app repo with the plugin enabled:

> Add a settings screen in Sources/App/SettingsView.swift: show the account's name and email, a notifications toggle, and a Sign Out button.

## What you get

One real run, in a package targeting iOS 26 and macOS 26 with no design tokens. The reply:

```text capture=use-swiftui-plain-reply
I added the settings screen in `Sources/App/SettingsView.swift`, and the package builds with `swift build`. I haven't run the app or looked at the preview.

It's a standard grouped settings form with three sections:
- **Account:** the account's name and email.
- **Notifications:** an on/off toggle.
- **Sign Out:** a red button marked as destructive. It signs out straight away, with no "are you sure?" prompt.

The repo had no account model yet, so I added a small `Account` type with just a name and email. The screen doesn't store anything itself. The code that shows it passes in the account, the notifications setting, and what to do on sign-out. That lets you connect it to your own storage and sign-out logic. There's also a preview with sample data.

Nothing in the app opens this screen yet. On iPhone and iPad, it can go inside a navigation stack or tab. On Mac, Apple's convention is to open settings from the app menu with Command-Comma. I can set that up when the app entry point exists.

The project has no design tokens yet, so the screen uses the system's standard spacing and styles. If you'd like, I can add a starter set of named spacing, corner-radius and animation values.
```

The view it wrote. The file's small `Account` type and the `init` are left out where you see `…`:

```text capture=use-swiftui-plain-code
public struct SettingsView: View {
    let account: Account
    @Binding var notificationsEnabled: Bool
    let onSignOut: () -> Void
…
    public var body: some View {
        Form {
            Section("Account") {
                LabeledContent("Name", value: account.name)
                LabeledContent("Email", value: account.email)
            }

            Section {
                Toggle("Notifications", isOn: $notificationsEnabled)
            }

            Section {
                Button("Sign Out", role: .destructive, action: onSignOut)
            }
        }
        .formStyle(.grouped)
        .navigationTitle("Settings")
    }
}

#if DEBUG
#Preview {
    @Previewable @State var notificationsEnabled = true

    NavigationStack {
        SettingsView(
            account: Account(name: "Jane Appleseed", email: "jane@example.com"),
            notificationsEnabled: $notificationsEnabled,
            onSignOut: {}
        )
    }
}
#endif
```

It builds clean:

```text capture=use-swiftui-plain-build
Building for debugging...
Build complete! (0.33 sec)
```

## With your own design tokens

When the repo has its own design layer, the skills translate any literal into it. The same prompt, in a package with a `DesignTokens` enum:

- the one custom colour, the toggle tint, comes from the project's token;
- Sign Out keeps the destructive role, whose system red is a semantic style rather than a literal, so there's nothing to translate.

The reply says both, and offers to switch:

```text capture=use-swiftui-tokens-reply
**Styling:** it uses the grouped form style on both iOS and macOS and sets the title to "Settings". The switch uses your brand colour, `DesignTokens.Palette.brand`. The Sign Out button uses the system red rather than `DesignTokens.Palette.danger`, so it matches how iOS and macOS show destructive actions elsewhere. I can switch it to your token if you want. There's also a preview with sample data.
```

Why your design layer wins: [ADR-0007](../../adr/ADR-0007-project-design-layer-wins.md).

<details>
<summary>Behind the scenes</summary>

### What the skills did

| In the result | Rule it follows |
| --- | --- |
| `Form` with one `Section` per group and `LabeledContent` rows, not stacks with dividers | `swift:design`: Grouped input |
| Sign Out uses `role: .destructive` and isn't the prominent button | `swift:design`: Buttons |
| System styles only, with an offer of starter tokens | `swift:design`: no project layer means system defaults (`references/tokens.md`) |
| The Mac Settings scene (Command-Comma), mentioned but not forced | `swift:design`: Settings |
| `#Preview` inside `#if DEBUG` | `swift:swiftui`: previews |

### Reproduce it headless

Replies vary from run to run. The behaviour in the table is what the eval cases pin ([capabilities](../reference/capabilities.md#eval-cases)). `<checkout>` is your clone of `jack1913/claude-plugins`. `--setting-sources project,local` leaves out your user settings and hooks, as the recorded runs did; your user CLAUDE.md still applies.

```bash
claude -p "Add a settings screen in Sources/App/SettingsView.swift: show the account's name and email, a notifications toggle, and a Sign Out button." --plugin-dir <checkout>/plugins/swift --setting-sources project,local --permission-mode acceptEdits --allowedTools "Bash(swift build:*)"
```

</details>

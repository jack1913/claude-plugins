# swift

Claude writes current, Apple-native Swift: SwiftUI screens, Swift 6 concurrency and Swift Testing tests. It can also
review a screen against Apple's design guidelines.

## Set it up

Install it once per Swift project. In a terminal, inside that project:

```bash
claude plugin marketplace add jack1913/claude-plugins --scope project
claude plugin install swift@jack1913 --scope project
```

Then start a new Claude Code session there. Commit `.claude/settings.json` so your team gets it too.

## Just ask

No special words needed. Ask the way you normally would, and the right skill loads by itself. Here's what that looks
like, from real runs.

### Build a screen

> Add a settings screen in Sources/App/SettingsView.swift: show the account's name and email, a notifications toggle,
> and a Sign Out button.

You get a native settings form, and `swift build` passes:

```swift
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
```

### Fix a concurrency error

Paste the compiler error and say what has to stay true:

> Sources/Demo/PlayerModel.swift fails Swift 6 strict concurrency checking inside load() with: "main actor-isolated
> property 'score' can not be mutated from a nonisolated context". Fix the isolation error properly, with both
> constraints: the heavy synchronous computeScore() must not run on the main actor, and the score/badge mutations must
> stay main-actor-isolated. Keep load() non-async. Do not suppress checking (no nonisolated(unsafe), no @preconcurrency,
> no @unchecked).

The fix keeps the heavy work off the main actor and hops back once:

```swift
func load() {
    Task.detached {
        let s = Self.computeScore()     // runs off the main actor
        await self.apply(score: s)      // hops to the main actor
    }
}

private func apply(score s: Int) {      // main-actor-isolated (inherits the class's @MainActor)
    score = s
    badge = String(repeating: "*", count: s % 10)
}
```

### Move tests to Swift Testing

> Migrate Tests/DemoTests/CartTests.swift from XCTest to Swift Testing.

Two near-identical XCTest methods become one parameterized test:

```swift
    @Test(arguments: [0, -1])
    func rejectsNonPositiveQuantity(_ quantity: Int) {
        var cart = Cart()
        #expect(throws: CartError(reason: "quantity must be positive")) {
            try cart.add("apple", quantity: quantity)
        }
        #expect(cart.items.isEmpty)
    }
```

### Review a screen

This one runs only when you type it, and it never edits anything:

```text illustrative
/swift:review Sources/Demo/SettingsView.swift
```

You get the problems, worst first, each with where it is, the guideline it breaks and a fix. One finding from a real
run:

> - [high] Delete Account has no `role: .destructive`. It is `.borderedProminent` with a red tint, which makes it the
>   most prominent control in the content — `Sources/Demo/SettingsView.swift:83` — HIG:
>   https://developer.apple.com/design/human-interface-guidelines/buttons — Fix: use
>   `Button("Delete Account", role: .destructive) { … }` with the default style, in its own last `Section`. The role
>   supplies the red.

Add a screenshot too, or instead: `/swift:review Sources/Demo/SettingsView.swift settings.png`. It reviews what it can
see.

## Tips

- **Your rules win.** Put house rules in `AGENTS.md` or `CLAUDE.md`, like "never use `async let`". Claude follows them
  over its own defaults and tells you which rule it followed.
- **Use your design tokens.** If your app defines its own colours, fonts and spacing, Claude uses them, and the review
  won't flag values your tokens allow.
- **For concurrency fixes, say what's off limits.** Paste the exact compiler error and name the shortcuts you don't
  want, like `nonisolated(unsafe)`.
- **Review with code and a screenshot together.** The code settles what the image only hints at, like tap-target sizes.

## Something off?

| You see | Do this |
|---|---|
| The skills never kick in | The plugin is on only where you installed it. Run the install lines inside that project |
| `/swift:review` didn't run by itself | That's on purpose: it runs only when you type it |
| Still the old version after an update | Run `claude plugin update swift@jack1913` (on Claude Code older than 2.1.281, add `--scope project`), then start a new session |
| Your result looks different from these | Replies vary from run to run; the behaviour is what stays the same |

Want every detail? The swift [README](../../../plugins/swift/README.md) and its
[manual](../../../plugins/swift/docs/manual/README.md), where each example comes with more of its reply and how to
reproduce it.

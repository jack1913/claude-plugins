# Fix a concurrency error

Paste the compiler error and say what must stay true. `swift:concurrency` loads on its own. It reads your project's settings and instructions before it proposes anything.

## Ask

> Sources/Demo/PlayerModel.swift fails Swift 6 strict concurrency checking inside load() with: "main actor-isolated property 'score' can not be mutated from a nonisolated context". Fix the isolation error properly, with both constraints: the heavy synchronous computeScore() must not run on the main actor, and the score/badge mutations must stay main-actor-isolated. Keep load() non-async. Do not suppress checking (no nonisolated(unsafe), no @preconcurrency, no @unchecked).

The code: a `@MainActor` class whose `Task.detached` writes `self.score` directly.

## What you get

One real run. The reply:

```text capture=use-concurrency-fix-reply
I fixed the error in `Sources/Demo/PlayerModel.swift`, and `swift build` now finishes with no diagnostics. The package uses Swift 6 language mode (tools-version 6.0), so full strict concurrency checking applies. There's no AGENTS.md or CLAUDE.md, and no default-isolation or upcoming-feature settings.

**The problem:** the `Task.detached` closure isn't isolated to any actor, but it was writing directly to `score` and `badge`, which belong to the main actor.

**The fix:**
```

The fix it made:

```text capture=use-concurrency-fix-reply
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

And why, from the same reply:

```text capture=use-concurrency-fix-reply
- **`computeScore()` stays off the main actor.** It's `nonisolated` and runs inside a detached task.
- **The mutations stay on the main actor.** They're in `apply(score:)`, which inherits the class's `@MainActor`, and the `await` is the only hop back. Both values are set together in one step, so nothing can see a new `score` with an old `badge`.
- **`load()` is still synchronous**, and I used no `nonisolated(unsafe)`, `@preconcurrency` or `@unchecked`. Capturing `self` in the task is fine because a `@MainActor` class is automatically `Sendable`.

I kept `Task.detached` because running the work off the main actor is the whole point here. On a Swift 6.2+ compiler, `Task { @concurrent in ... }` does the same thing and is the more modern spelling. I left it out because the package targets tools-version 6.0.
```

It builds clean in Swift 6 mode:

```text capture=use-concurrency-fix-build
Building for debugging...
Build complete! (0.30 sec)
```

## When your repo has its own rule

The skills follow your repo's AGENTS.md and CLAUDE.md over their own defaults, and say so. Here the repo's AGENTS.md says "Never use `async let` in this codebase", and the task asks for two fixed parallel calls, which is exactly where `swift:concurrency` would suggest `async let`:

> Implement DashboardLoader.load() in Sources/Demo/DashboardLoader.swift so it fetches the profile and the settings in parallel through the client and returns both.

```text capture=use-concurrency-rule-reply
AGENTS.md bans `async let`, so it uses `withThrowingTaskGroup` instead:

- Each fetch runs as its own task in the group, and a small private enum `Part` tags each result as either the profile or the settings.
- When both results are in, it returns `(profile, settings)`.
- If either request throws, the error comes out of `load()` and the other request is cancelled.
```

Why your repo's rules win: [ADR-0013](../../adr/ADR-0013-project-rules-win-over-skill-defaults.md).

<details>
<summary>Behind the scenes</summary>

### What the skill did

| In the result | Rule it follows |
| --- | --- |
| Read `Package.swift` (language mode, isolation settings) and looked for AGENTS.md and CLAUDE.md first | `swift:concurrency`: Project Rules, Fast Path step 1 |
| The heavy work stays off the main actor; the mutations hop back through an awaited main-actor method | `swift:concurrency`: task entry isolation |
| No `nonisolated(unsafe)`, `@preconcurrency` or `@unchecked` | `swift:concurrency`: smallest safe fix, no opt-outs |
| `@concurrent` offered only where the toolchain supports it | `swift:concurrency`: project settings decide the spelling |

### Reproduce it headless

The scaffolds are the eval cases `mainactor-detached-task` and `project-rule-over-skill` in `evals/`. Replies vary from run to run; the eval cases pin the behaviour ([capabilities](../reference/capabilities.md#eval-cases)). `<checkout>` is your clone of `jack1913/claude-plugins`. `--setting-sources project,local` leaves out your user settings and hooks, as the recorded runs did; your user CLAUDE.md still applies.

```bash
claude -p "<the prompt above>" --plugin-dir <checkout>/plugins/swift --setting-sources project,local --permission-mode acceptEdits --allowedTools "Bash(swift build:*)"
```

</details>

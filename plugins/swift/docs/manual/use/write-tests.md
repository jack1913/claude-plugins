# Write tests

Ask for a test, or for a migration. `swift:testing` loads on its own, writes Swift Testing (`@Test`, `#expect`), and keeps XCTest only where it's still needed.

## Test a callback that arrives later

> In Tests/DemoTests/SaverTests.swift, test that save(3) calls onSave exactly once with 3, using Swift Testing.

`Saver.save(_:)` calls `onSave` later, on a background queue. That's the case where a naive test passes without ever seeing the call.

One real run wrote:

```swift
@Suite struct SaverTests {
    @Test(.timeLimit(.minutes(1)))
    func saveCallsOnSaveOnceWithValue() async {
        let (values, continuation) = AsyncStream.makeStream(of: Int.self)

        await confirmation("onSave is called", expectedCount: 1) { saved in
            let saver = Saver { n in
                saved()
                continuation.yield(n)
            }

            saver.save(3)

            // onSave fires on a background queue, so wait for it before the
            // confirmation closure returns.
            var iterator = values.makeAsyncIterator()
            let value = await iterator.next()
            #expect(value == 3)
        }
    }
}
```

And explained its limit instead of hiding it:

```text capture=use-testing-callback-reply
- **Once:** a `confirmation` with `expectedCount: 1` counts the calls to `onSave`.
- **With 3:** `onSave` passes its value into an `AsyncStream`. The test waits for that first value inside the confirmation and checks that it equals 3.
- **No hang:** a one-minute `.timeLimit` makes the test fail if `onSave` never runs, instead of waiting forever.

**Limitation:** the count only covers calls made before the confirmation finishes. A second `onSave` call arriving after the test has received the first value wouldn't be caught. The only way to catch that is to wait an arbitrary amount of time, which slows the test and can make it flaky, so I didn't add it.
```

```text capture=use-testing-callback-test
✔ Test saveCallsOnSaveOnceWithValue() passed after 0.001 seconds.
✔ Suite SaverTests passed after 0.001 seconds.
✔ Test run with 1 test in 1 suite passed after 0.001 seconds.
```

## Migrate an XCTest file

> Migrate Tests/DemoTests/CartTests.swift from XCTest to Swift Testing.

The file had five XCTest methods, a `setUp()` and an implicitly unwrapped `cart`. One real run:

```text capture=use-testing-migrate-reply
What changed:
- **Imports and suite:** `import XCTest` became `import Testing`, and the `XCTestCase` class became a plain `struct CartTests`.
- **Setup:** I removed `setUp()` and the `var cart: Cart!` property. Since `Cart` is a struct, each test simply creates its own `Cart()`.
- **Test methods:** each `testXxx()` is now an `@Test func xxx()`, and `XCTAssertEqual` / `XCTAssertTrue` are now `#expect(...)`.
- **Rejection tests:** `testRejectsZero` and `testRejectsNegative` are now one test, `rejectsNonPositiveQuantity`, which runs with the inputs `[0, -1]` using `#expect(throws: CartError(...))`.
```

The two rejection tests became one parameterized test:

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

```text capture=use-testing-migrate-test
✔ Test rejectsNonPositiveQuantity(_:) with 2 test cases passed after 0.001 seconds.
✔ Suite CartTests passed after 0.001 seconds.
✔ Test run with 4 tests in 1 suite passed after 0.001 seconds.
```

## What the skill did

| In the result | Rule it follows |
| --- | --- |
| `confirmation(expectedCount: 1)`, kept open until the callback arrives | `swift:testing`: async testing, callback delivered later |
| No `Task.sleep` to wait for the callback or for late duplicates | `swift:testing`: no sleep windows, inside the closure or after it |
| `.timeLimit(.minutes(1))`, the smallest limit Swift Testing allows | `swift:testing`: traits |
| Near-duplicate tests merged into one `@Test(arguments:)` | `swift:testing`: parameterized tests |
| `setUp()` replaced by per-test values in a `struct` suite | `swift:testing`: XCTest migration |

## Reproduce it headless

Runs from this checkout on 2026-09-28 with Claude Code 2.1.283. The callback scaffold is the eval case `callback-confirmation-test`. Replies vary from run to run; the eval cases pin the behaviour ([capabilities](../reference/capabilities.md#eval-cases)).

```bash
claude -p "<the prompt above>" --plugin-dir ~/Dev/claude_skills/swift-plugin/plugins/swift --permission-mode acceptEdits --allowedTools "Bash(swift test:*)"
```

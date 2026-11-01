# Expectations

## When to use this reference

Use this file when writing assertions, migrating from `XCTAssert*`, testing thrown errors, or documenting known failures.

## `#expect` as the default

- Use `#expect` for most assertions.
- Pass natural Swift expressions (`==`, `>`, `.contains`, `.isEmpty`, etc.).
- Rely on captured sub-expression values for rich diagnostics in Xcode.
- Avoid old XCTest assertion families in Swift Testing tests.

### Example: expressive assertions

```swift
import Testing

@Test func pricingRules() {
 let subtotal = 25
 let discount = 5
 let total = subtotal - discount

 #expect(total == 20)
 #expect(total > 0)
 #expect([10, 20, 30].contains(total))
}
```

## `#require` for prerequisites

- Use `try #require(...)` when later assertions depend on this condition.
- Treat `#require` as "guard + fail test early".
- Use return value to unwrap optionals safely and reduce noisy optional chaining.
- Prefer this pattern over manual optional checks when failure should halt test flow.

### Example: optional precondition + unwrapped usage

```swift
import Foundation
import Testing

@Test func parsedURLHasHTTPS() throws {
 let value = "https://www.avanderlee.com"
 let url = try #require(URL(string: value), "URL should parse")
 #expect(url.scheme == "https")
}
```

## Throwing behavior checks

- For success-path calls to throwing functions, call directly and assert returned value.
- For expected failure, use throw-aware expectations to verify:
  - any throw
  - specific error type
  - specific error case/value
- Avoid verbose hand-written `do/catch` unless custom branching is truly needed.

### Example: expected throw and no-throw

```swift
import Testing

enum BrewError: Error, Equatable {
 case missingBeans
}

func brew(_ hasBeans: Bool) throws -> String {
 guard hasBeans else { throw BrewError.missingBeans }
 return "coffee"
}

@Test func expectedThrows() {
 #expect(throws: BrewError.self) {
 try brew(false)
 }
}

@Test func expectedNoThrow() {
 #expect(throws: Never.self) {
 try brew(true)
 }
}
```

### Inspect the thrown error

`#expect(throws:)` returns the error it caught, as an optional, so a test can check the case or its payload without a `do/catch`.

```swift
@Test func thrownCaseIsMissingBeans() {
 let error = #expect(throws: BrewError.self) {
 try brew(false)
 }
 #expect(error == .missingBeans)
}
```

## Exit tests

- Use an exit test (Swift 6.2, Xcode 26) for code that stops the process on purpose: `precondition`, `preconditionFailure`, `fatalError` or `exit`.
- Apple lists exit tests as available on macOS, Linux, FreeBSD, OpenBSD and Windows; iOS, tvOS, watchOS and visionOS are not on the list, so run these tests on a macOS destination.
- The testing library starts a new process with the same executable and runs the closure there. The parent test suspends until the child exits, then compares the exit status with the condition.
- Conditions: `.success`, `.failure` (any abnormal exit), `.exitCode(_:)` and `.signal(_:)`.
- A value the closure uses must be passed in its capture list and conform to `Codable` and `Sendable`; a local needs an explicit type (`[balance = balance as Int]`). Capture lists need Swift 6.3 or later.
- Add `observing: [\.standardOutputContent]` or `\.standardErrorContent` to read the child's output from the returned result. Use `try #require(processExitsWith:)` when later lines need the result.

### Example: a precondition that must trap

```swift
import Testing

struct Account {
 var balance: Int
 func validate() {
 precondition(balance >= 0, "balance must not be negative")
 }
}

@Test func negativeBalanceTraps() async {
 let balance = -1
 await #expect(processExitsWith: .failure) { [balance = balance as Int] in
 Account(balance: balance).validate()
 }
}
```

## Known issue handling

- Use `withKnownIssue` for temporary expected failures you still want to compile/run.
- Prefer `withKnownIssue` over blanket disabling when you need ongoing visibility.
- Remove known-issue wrappers once failure condition is fixed.
- To report a problem that should not fail the test, record a warning (Swift 6.3, Xcode 26.4): `Issue.record("Backend is slower than usual", severity: .warning)`. The default severity is `.error`, so `Issue.record("...")` still fails the test.

### Example: scope only failing section

```swift
import Testing

@Test func checkoutFlow() {
 #expect(true) // still validated

 withKnownIssue("Checkout backend intermittently returns 503", isIntermittent: true) {
 Issue.record("Known upstream issue")
 }

 #expect(2 + 2 == 4) // rest of test still executes
}
```

## Readability upgrade

- Conform complex domain types to `CustomTestStringConvertible` for concise test output.
- Keep production `CustomStringConvertible` separate from test-specific descriptions when needed.
- Conform to `CustomTestReflectable` (Swift 6.4, Xcode 27) to choose which properties appear in the expanded value tree of a failing expectation. `CustomTestStringConvertible` stays the right tool for a one-line summary.

### Example: clean diagnostic descriptions

```swift
import Foundation
import Testing

struct Receipt: CustomTestStringConvertible {
 let id: UUID
 let total: Decimal

 var testDescription: String {
 "Receipt(total: \(total))"
 }
}
```

### Example: show only the properties that matter

```swift
import Foundation
import Testing

struct Order: CustomTestReflectable {
 let id: UUID
 let total: Decimal
 let internalCache: [String: Int]

 var customTestMirror: Mirror {
 Mirror(self, children: ["id": id, "total": total])
 }
}
```

## XCTest mapping quick examples

```swift
// XCTAssertEqual(total, 20)
#expect(total == 20)

// try XCTUnwrap(user)
let user = try #require(user)

// XCTFail("Unreachable")
Issue.record("Unreachable")
```

## Do / Don't

- Do use `#require` when later checks depend on a value.
- Do keep `withKnownIssue` scopes narrow.
- Don't use XCTest assertions in Swift Testing tests.
- Don't hide prerequisite failures inside later optional chaining.

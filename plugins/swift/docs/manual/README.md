# swift-plugin manual

The operator's manual: how to use swift-plugin day to day. Read the daily-use pages in order.

## Getting started

- [Enable the plugin in a Swift repo](getting-started/enable-in-a-swift-repo.md): install, scopes, updates, moving from an older marketplace, what each skill covers

## Use it

Each page is built around a real run: the prompt, the reply, and the build or test output.

1. [Build a SwiftUI screen](use/build-a-swiftui-screen.md): `swift:design` and `swift:swiftui`, with and without your design tokens
2. [Fix a concurrency error](use/fix-a-concurrency-error.md): `swift:concurrency`, including your repo's own rules
3. [Write tests](use/write-tests.md): `swift:testing` for async callbacks and XCTest migration
4. [Review a screen](use/review-a-screen.md): `/swift:review` from code or a screenshot

## The daily-use manual

1. [Work on the plugin](work-on-it.md): try a change, check APIs, run the tests and evals, check upstream, release

## Reference (tables)

- [What the plugin covers](reference/capabilities.md): skills, topics by skill, shared rules, eval cases and results
- [check-apis.py reference](reference/check-apis.md): flags, exit codes, the `apis.json` format

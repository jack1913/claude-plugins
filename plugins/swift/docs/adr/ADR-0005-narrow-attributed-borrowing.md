# ADR-0005: Borrow only narrow, attributed passages from other skill repos

- **Status:** accepted
- **Date:** 2026-09-25
- **Source:** commits `8781db0` (twostraws deprecation entries), `4c07f0b` (Dimillian view-structure additions); `docs/archive/specs/2026-09-24-swift-plugin-design.md` §3 Repo layout, **License** bullet; §4 item 5; §8 research record; `plugins/swift/NOTICE.md`

## Context

Before choosing the base, the research record deep-read three other skill repos (spec §8):

- twostraws and Dimillian, both MIT, fill gaps the base left open. Dimillian also recommends `scrollExtensionMode(.underSidebar)`, which has no Apple doc page.
- dickwu has no license.

dpearson2699, listed in §8 but not deep-read, is PolyForm.

## Decision

Take only the specific passage that fills a gap, reworded, and attribute it in `plugins/swift/NOTICE.md` with the source commit, what was taken, and the MIT text:

- from twostraws/SwiftUI-Agent-Skill, the `overlay(_:alignment:)` and `Text + Text` deprecation entries, into `latest-apis.md`;
- from Dimillian/Skills, the view-ordering detail, the actions-out-of-body section and the 300-line split rule, into `view-structure.md`.

Dimillian's "no view models by default" stance and its `scrollExtensionMode(.underSidebar)` are left out on purpose (spec §4 item 5). Nothing is taken from dickwu/apple-design-skill (no license) or dpearson2699/swift-ios-skills (PolyForm) (spec §3). The other candidates in spec §8 were listed but not deep-read.

Rejected: adopting a candidate more broadly, and using text whose license doesn't allow it.

## Consequences

- Every borrowed passage has a named source, a pinned commit and its license notice in a file that ships with installs.
- Gaps that the excluded or not-deep-read candidates might fill stay open until someone revisits them.

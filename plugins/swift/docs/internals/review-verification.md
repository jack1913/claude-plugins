# swift:review end-to-end verification

The quality gate for `swift:review` (ADR-0011; part-2 spec §6). There is no automated eval: the eval harness fires skills through the Skill tool, which a `disable-model-invocation` skill blocks. So each release that changes the review method gets a recorded run here, scored against the answer key in `maintenance/review-fixtures/key.json` with `maintenance/review-fixtures/score.py`.

Each dated section is frozen once written. A later run appends a new section; it never edits an old one.

## 2026-09-27 — first release (0.1.6)

### Setup

- **Claude Code:** `2.1.283 (Claude Code)`. Model: `claude-opus-5-5` (the account's default for `claude -p`).
- **Answer key:** committed in `09733d7` at 2026-09-27T19:35:45Z. The first run started at 2026-09-27T19:36:00Z, and the key was not edited after that.
- **Fixtures:** `maintenance/review-fixtures/` (commit `09733d7`).
  - `planted/` holds eight planted violations, P1–P8.
  - `tokened/` is the same screen on a `DesignTokens` layer, with only P3 and P4 left in.
  - `screenshot.png` is the planted content rendered by `render/render.swift`. It visibly shows P1, P2, P3, P4 and P6. `key.json` → `runs.screenshot.excluded` gives the reasons for the others: the toolbar and the sheet aren't drawn, and the glass card renders blank.
- **Isolation:** each run had its own `git init` directory holding only what that run may see. A held only the `planted/` package, B only `tokened/`, and C only `screenshot.png`. None of them contained a key, a scorer or comments about the violations.
- **Commands:** run from each directory. `--permission-mode acceptEdits` lets file edits through, so an empty `git status` afterwards proves the review edited nothing.

~~~sh
claude -p --permission-mode acceptEdits --add-dir "$REPO/plugins/swift" --plugin-dir "$REPO/plugins/swift" "/swift:review Sources/Demo/SettingsView.swift" < /dev/null > ../A.md   # A/ and B/
claude -p --permission-mode acceptEdits --add-dir "$REPO/plugins/swift" --plugin-dir "$REPO/plugins/swift" "/swift:review screenshot.png" < /dev/null > ../C.md                    # C/
python3 maintenance/review-fixtures/score.py maintenance/review-fixtures/key.json A.md --run code      # B.md --run tokened, C.md --run screenshot
~~~

### Run history

- **Run 0, configuration: failed on configuration, not on the skill.** The same commands without `--add-dir`. In `-p` nobody can answer a read-permission prompt, and the plugin directory lies outside the run's directory. So none of the three sessions could read `references/*.md` or `swift:design`'s references. Each said so and fell back to its own layout, and every run scored 0. What each session reported:
  - A: "**Caveat:** this session could not read the review skill's `checklist.md`, `findings-format.md` or `screenshot-review.md`, or `swift:design`'s area references. The review applies only the Decision Rules in `swift:design`'s `SKILL.md`, and the layout below is my own rather than the skill's findings format."
  - B: "I couldn't read the review skill's reference files (`checklist.md`, `findings-format.md`, `screenshot-review.md` and the `design/references/*` area files) because the read permission prompt went unanswered. So this review checks against the `swift:design` Decision Rules only, and the output layout is my own."
  - C: "- Permission was denied for the review skill's three reference files (`checklist.md`, `screenshot-review.md`, `findings-format.md`). I judged against the `swift:design` Decision Rules, which did load. The severity scale and finding layout below are my approximation."

  Fix: `--add-dir <plugin dir>`, the headless equivalent of approving those reads. The skill text was not changed.
- **Run 1: accepted.** No iteration of the skill text was needed.

### Scores (run 1)

| Run | Input | `score.py` | `git status --porcelain` | Accepted |
|-----|-------|------------|--------------------------|----------|
| A | `planted/` code | `detected 8/8, missed [], false positives [], unscored 2` (exit 0) | empty | yes |
| B | `tokened/` code | `detected 2/2, missed [], false positives ['N2'], unscored 3` (exit 1) | empty | yes, on adjudication below |
| C | `screenshot.png` | `detected 4/5, missed ['P3'], false positives [], unscored 0` (exit 0) | empty | yes |

### Adjudication

Every finding line was read by hand against `key.json`.

- **Run A, 8/8 confirmed:** each planted violation has its own correct finding.
  - The scorer credited P1 through the header finding, whose fix says "in a `Form`".
  - P1's own finding (the `ScrollView` + `VStack` + `Divider`s one) cites `SettingsView.swift:14`, `:41–72`, and the scorer's location parser doesn't read a bare `:41–72` continuation. It is correct and counts.
  - Both unscored findings are real: P1's own line, and the bare pencil icon with no VoiceOver label (HIG Accessibility, Icons).
  - No missing-glass finding. The glass finding asks for the card's glass to be removed.
- **Run B, both kept violations found; the N2 hit is a true finding the fixture didn't plant.**
  - The flagged line says `Palette.surface`, a fixed light grey, sits behind Form text that follows the system appearance, so the row turns white-on-light-grey in Dark Mode. That is true of the fixture.
  - The review also said outright: "The `surface` value itself is the project's call; the problem is putting it behind text that follows the system appearance."
  - No finding called a token hard-coded or asked for asset colour sets, which is what Review Focus 2 asks for. N2's pattern (`Palette.` … `dark`) also catches a finding about how a token is used, not only about the token's value.
  - The three unscored findings are real:
    - a pencil symbol that can be misread (swift:design `sf-symbols.md` → Choosing a Symbol);
    - storage text and `ProgressView` reading as two VoiceOver stops;
    - Save as the only primary action, but untinted (swift:design **Toolbars**).
- **Run C, 4/5 at the key's minimum of 4.**
  - P3 wasn't reported as a finding. It is under `## Not checked`, with the glyph at "about 10×10 pt (estimated, @2x)" and "its hit region can't be seen". That is what `screenshot-review.md` asks for when the image can't show the hit region.
  - Every size in the report is marked estimated. Dynamic Type, dark mode, VoiceOver, motion, and the toolbar outside the frame are all under `## Not checked`.

### Raw output (run 1)

Verbatim from `claude -p`, kept as `docs/.onboard-captures/review-2026-09-27-{a,b,c}.txt`. These captures are frozen with this section, so a release-time capture refresh leaves them alone.

#### A — `planted/`

~~~text capture=review-2026-09-27-a
No project design layer (no tokens, colour sets or design skill), so system defaults are the baseline. Targets are iOS 26 and macOS 26 (`Package.swift`), with no `#if os` branches, so both platforms' rules apply.

## Findings
- [high] The "Account" header uses a fixed 13 pt Ultralight font. It doesn't scale with Dynamic Type, and Ultralight is hard to read at small sizes — `Sources/Demo/SettingsView.swift:43` — HIG: https://developer.apple.com/design/human-interface-guidelines/typography — Fix: make it a `Section("Account")` header in a `Form`, which styles it and adds the header trait for VoiceOver. Outside a Form, use a text style such as `.font(.headline)` at Regular weight or heavier.
- [high] The Sync status is only a green or red `Circle`. Colour carries the meaning alone, and VoiceOver reads nothing for the state — `Sources/Demo/SettingsView.swift:68` — HIG: https://developer.apple.com/design/human-interface-guidelines/color — Fix: use `LabeledContent("Sync") { Label(isSynced ? "Synced" : "Not Synced", systemImage: isSynced ? "checkmark.circle.fill" : "exclamationmark.triangle.fill") }`. Colour only the symbol (`.green` or `.red`) and leave the text primary.
- [high] The pencil edit button's hit region is at most 28×28 pt on iOS (`.buttonStyle(.plain)` inside a 28-pt frame). HIG asks for at least 44×44 pt — `Sources/Demo/SettingsView.swift:54` — HIG: https://developer.apple.com/design/human-interface-guidelines/buttons — Fix: in a Form, make the whole Name row the button: `Button { editingName = true } label: { LabeledContent("Name", value: name) }`. Or drop the fixed frame and give it `.frame(minWidth: 44, minHeight: 44).contentShape(.rect)`. On Mac, 28 pt is the default size.
- [high] "Delete Account" has no `role: .destructive`, and it is a prominent tinted button, so the destructive action looks like the main action — `Sources/Demo/SettingsView.swift:83` — HIG: https://developer.apple.com/design/human-interface-guidelines/buttons — Fix: use `Button("Delete Account", role: .destructive) {}` without `.borderedProminent` or `.tint(.red)` (the role supplies the colour). Put it in its own last `Section`, and confirm with `.confirmationDialog` before deleting.
- [medium] The toolbar gives Export, Share and Save the tinted prominent style. Counting Delete Account, the screen has four prominent buttons, where HIG allows one tinted primary action — `Sources/Demo/SettingsView.swift:19` — HIG: https://developer.apple.com/design/human-interface-guidelines/toolbars — Fix: keep `.borderedProminent` only on Save, in `ToolbarItem(placement: .confirmationAction)`. Make Share a `ShareLink` (`square.and.arrow.up`). Move Export to `.secondaryAction` or a `Menu`, in the default style.
- [medium] The settings rows are a `ScrollView` + `VStack` + `Divider`s rather than a `Form` with `Section`s and `LabeledContent`. As a result, each label and its value are also separate VoiceOver elements — `Sources/Demo/SettingsView.swift:14`, `:41–72` — HIG: https://developer.apple.com/design/human-interface-guidelines/lists-and-tables — Fix: `Form { Section("Account") { LabeledContent("Name", …); LabeledContent("Email", …); LabeledContent("Sync") {…} }; Section { LabeledContent("Storage", value: "3.2 GB of 5 GB used") }; Section { delete button } }.formStyle(.grouped)`. This gives a grouped list on iOS and grouped sections on macOS.
- [medium] Liquid Glass is on the Storage info card. That puts glass in the content layer, where it competes with the bars — `Sources/Demo/SettingsView.swift:82` — HIG: https://developer.apple.com/design/human-interface-guidelines/materials — Fix: remove `.glassEffect` and the hand-set 16-pt radius, and make Storage a Form row (`LabeledContent`, or a `ProgressView(value:total:)` with a label).
- [medium] `EditNameSheet` has Done with no Cancel, and the `TextField` writes straight to the binding, so there's no way to back out of an edit — `Sources/Demo/SettingsView.swift:101` — HIG: https://developer.apple.com/design/human-interface-guidelines/sheets — Fix: edit a local `@State` draft. Add `ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }` (leading), and have Done (`.confirmationAction`, trailing) assign `name = draft`. Put the field in a `Form` so it gets the platform's field styling.
- [medium] The edit control is a bare pencil icon. A pencil can be misread, and VoiceOver hears only the symbol's default description, not "Edit Name" — `Sources/Demo/SettingsView.swift:49` — HIG: https://developer.apple.com/design/human-interface-guidelines/accessibility — Fix: use a text button `Button("Edit") {…}`. Or keep the icon with `Button("Edit Name", systemImage: "pencil") {…}.labelStyle(.iconOnly)`, which gives VoiceOver the label. Making the row itself the button (see the hit-target finding) solves this too.

## Not checked
- **Dynamic Type:** there's no capture at accessibility sizes. The Name and Email rows are `HStack`s with no layout for accessibility sizes. An AX5 capture would show whether they wrap badly or truncate.
- **Mac presentation:** the app's `Scene` isn't in the inputs. On macOS, settings should be a `Settings` scene opened with ⌘, and Export, Share and Save each need a menu bar command (⌘S for Save). Send the `App` file to check.
- **Mac sheet size:** `EditNameSheet` sets no size. A macOS capture would show whether it opens too narrow.
- **Dark mode and Increase Contrast:** no captures were given. Every colour here is a system colour, so the risk is low.
- **Screenshots:** none were given, so there was no visual pass on margins, contrast or rendered sizes.
- **Delete flow:** the action is empty, so any confirmation step can't be seen.

Outside the design review: `SettingsView` wraps itself in a `NavigationStack`. If a host pushes it inside its own navigation stack, the stacks nest (`swift:swiftui` covers this).

If you want design tokens, `swift:design`'s `references/tokens.md` has a starter set.
~~~

#### B — `tokened/`

~~~text capture=review-2026-09-27-b
I found six issues in `SettingsView.swift`: three high and three low. The package targets iOS 26 and macOS 26. `DesignTokens` values (spacing, radius, palette, motion) are the project's own choices, so I didn't report any of them. The project has no colour sets or design skill of its own.

## Findings
- [high] The "Edit name" pencil button is too small to tap on iOS: 28×28 pt at most, under the 44×44 pt minimum. Because `.frame` sits outside the plain-style button, the tappable area is closer to the glyph itself — `Sources/Demo/SettingsView.swift:18-24` — HIG: https://developer.apple.com/design/human-interface-guidelines/buttons — Fix: make the whole row the button (`Button { editingName = true } label: { LabeledContent("Name", value: name) }`, with `.tint(.primary)` so the label stays primary). Or put `.frame(minWidth: 44, minHeight: 44).contentShape(.rect)` inside the button's label.
- [high] Sync status is only a red or green dot, with no text or symbol. VoiceOver hears only "Status", because a `Circle` isn't an accessibility element — `Sources/Demo/SettingsView.swift:30-35` — HIG: https://developer.apple.com/design/human-interface-guidelines/color — Fix: `LabeledContent("Status") { Label { Text(isSynced ? "Synced" : "Not Synced") } icon: { Image(systemName: isSynced ? "checkmark.circle.fill" : "exclamationmark.triangle.fill").foregroundStyle(isSynced ? DesignTokens.Palette.success : DesignTokens.Palette.danger) } }`. This colours the symbol, keeps the words in the primary style, and scales with Dynamic Type, unlike the fixed 8 pt dot.
- [high] The Storage row draws its own card inside a grouped `Form` row. `Palette.surface` is a fixed light grey, so in Dark Mode the row's primary text turns white on near-white, far below 4.5:1 contrast. In either appearance it's a card nested in the system's grouped cell — `Sources/Demo/SettingsView.swift:44-45` — HIG: https://developer.apple.com/design/human-interface-guidelines/dark-mode — Fix: remove `.padding(.vertical, …)` and `.background(DesignTokens.Palette.surface, …)` and let the Form draw the row background. The `surface` value itself is the project's call; the problem is putting it behind text that follows the system appearance.
- [low] A bare `pencil` symbol is the only label for Edit, and a pencil can be misread — `Sources/Demo/SettingsView.swift:21` — HIG: https://developer.apple.com/design/human-interface-guidelines/icons — Fix: making the whole row the button (first finding) removes the need for it. If a separate control stays, give it a text label ("Edit").
- [low] The storage text and `ProgressView` are two VoiceOver stops, and the progress bar has no label — `Sources/Demo/SettingsView.swift:39-41` — HIG: https://developer.apple.com/design/human-interface-guidelines/accessibility — Fix: `ProgressView(value: 3.2, total: 5) { Text("Storage") } currentValueLabel: { Text("3.2 GB of 5 GB used") }`, or `.accessibilityElement(children: .combine)` on the `VStack`.
- [low] Save is the toolbar's only primary action but isn't tinted, and 26-era toolbar text items look monochrome by default — `Sources/Demo/SettingsView.swift:55` — HIG: https://developer.apple.com/design/human-interface-guidelines/toolbars — Fix: give it `.buttonStyle(.borderedProminent)` so it shows as the tinted primary item.

Outside design scope: in `EditNameSheet` the `TextField` writes straight to `name` (`:73`), so Cancel keeps the edit just like Done does. Edit a local draft and commit it on Done (`swift:swiftui`).

## Not checked
- **Rendering:** there's no screenshot, so I couldn't see how the token colours look in Dark Mode or Increased Contrast. Send a capture in each appearance.
- **Dynamic Type:** at accessibility sizes, the Name row (`LabeledContent` plus a button in an `HStack`) may truncate. Send an AX5 capture.
- **Mac:** I couldn't check whether this view is shown from a `Settings` scene (⌘,), or whether Save has a menu bar command and ⌘S. The `App` and its scene and `.commands` aren't in this package. Send the app target's `App` file.
- **Delete Account:** its action is empty, so I can't tell whether it asks for confirmation with `confirmationDialog` before this irreversible delete.
~~~

#### C — `screenshot.png`

~~~text capture=review-2026-09-27-c
I couldn't measure pixels directly because the pixel-analysis command needed approval, which this session can't give. So every size below is estimated by eye. The repo contains only `screenshot.png`: there is no view code and no project design layer, so nothing here is covered by a project token. I assumed @2x, which makes the frame 390×297 pt. At @3x it would be 260 pt wide, narrower than any iPhone. The image doesn't show which platform this is.

## Findings
- [high] The Sync row shows its state with only a red dot, with no symbol shape or text saying what red means — screenshot: Sync row, trailing edge — HIG: https://developer.apple.com/design/human-interface-guidelines/color — Fix: if Sync is an on/off setting, use `Toggle("Sync", isOn: $syncEnabled)`. If it's a status, use `LabeledContent("Sync") { Label { Text("Sync Failed") } icon: { Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.red) } }`. Colour only the symbol and keep the words in the primary style.
- [medium] "Delete Account" is the only filled button on the screen, so the destructive action looks like the primary action — screenshot: bottom-left button — HIG: https://developer.apple.com/design/human-interface-guidelines/buttons — Fix: use `Button("Delete Account", role: .destructive) { … }` without `.borderedProminent` or a custom red fill. Put it in its own `Section` at the end of the form and confirm with `.confirmationDialog` before deleting.
- [medium] Name, Email and Sync look like stacked rows with dividers rather than a form. The hairlines stop at the content margin on both sides, there's no grouped section background, and the button is pushed down by empty space — screenshot: Account rows — HIG: https://developer.apple.com/design/human-interface-guidelines/lists-and-tables — Fix: use `Form { Section("Account") { LabeledContent("Name") { … }; LabeledContent("Email", value: email); LabeledContent("Sync") { … } }; Section { Button("Delete Account", role: .destructive) { … } } }` with `.formStyle(.grouped)`, and let the system set row height, separators and margins.
- [medium] The "Account" header appears to be set in a Light or Thin weight, noticeably thinner than the row labels, and in grey — screenshot: top-left header — HIG: https://developer.apple.com/design/human-interface-guidelines/typography — Fix: use the `Section("Account")` header, which gets the system header style. If it has to stay custom, use a text style at Regular weight or heavier with `.foregroundStyle(.secondary)`.
- [low] Name is edited through a small pencil button with no text label. A pencil can be misread for Edit (WWDC25 356), and it's the only row with an edit control — screenshot: pencil beside "Jordan Lee" — HIG: https://developer.apple.com/design/human-interface-guidelines/icons — Fix: make the value editable in the row itself (`LabeledContent("Name") { TextField("Name", text: $name) }` in the Form), or use an "Edit" text button.

## Not checked
- **Platform and scale:** I assumed @2x, and the platform can't be told from the image. Send `Package.swift` or the Xcode project.
- **Hit targets:** the Delete Account bezel is about 117×24 pt (estimated, @2x). On iPhone or iPad that is under the 44×44 pt target and the 28 pt minimum; on Mac it is fine. The pencil glyph is about 10×10 pt (estimated, @2x), and its hit region can't be seen. Send the platform and the code.
- **Contrast of the white-on-red button label:** if the red is system red, the label is roughly 3.5:1 in light mode, below the 4.5:1 needed for text under 18 pt. System red's increased-contrast variant would cover this. Send an Increase Contrast capture or the code.
- **Blue email:** it may be a link. If it's static text, colouring it blue gives the accent colour a second meaning, which is a Color finding. Send the code.
- **Default button and confirmation:** whether Delete Account responds to Return, or asks before deleting, isn't visible. Send the code.
- **Dynamic Type:** there's no accessibility-size capture, so I couldn't check whether the Name value and pencil truncate. Send a capture at accessibility size.
- **Dark mode and Increase Contrast:** only light mode is shown. Send a capture in each appearance.
- **VoiceOver:** labels for the dot and the pencil, and the reading order, aren't visible. Send the code or an Accessibility Inspector pass.
- **Navigation bar, toolbar, title and window chrome:** they're outside the frame. Send a capture that includes them.
- **Motion and Reduce Motion:** a still image can't show them. Send a screen recording or the code.
~~~

## 2026-09-27 — erratum from the 0.1.6 final review

This adds to the section above without editing it.

- **What "edited nothing" covers.** `git status` was checked in each run's own directory. The runs also passed `--add-dir <plugin dir>`, and `acceptEdits` would have auto-approved writes there too. The final review found the repository, which holds that plugin dir, clean after the runs, and no commit came from them. So nothing was edited.
- **What stops edits.** `disallowed-tools` removes Write, Edit and NotebookEdit only for the turn that invokes the skill, and Bash stays available: run C tried a Bash command, which the non-interactive session denied. Beyond that, report-only rests on the skill's Operating Rule (ADR-0011). A later section should also record `git status` for every `--add-dir` target.
- **Run B.** The accepted-on-adjudication N2 hit comes from an unplanted defect in the `tokened/` fixture: `DesignTokens.Palette.surface` is a fixed light colour placed behind Form text that follows the system appearance. So the fixture can't separate "respects tokens" from "reports a real contrast bug". A later section should fix the fixture, commit a new key before running, and re-run B.

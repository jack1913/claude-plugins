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

## 2026-09-27 — run B re-run on a corrected fixture

The erratum above found an unplanted defect in the `tokened/` fixture. This section re-runs only B once the fixture is fixed. The answer key did not change.

- **Fixture fix:** commit `28e5c32` (2026-09-27T20:09:29Z).
  - It removes the fixed-light `Palette.surface` background behind text that adapts to appearance, and the now-unused token.
  - It labels the storage `ProgressView` and tints the one primary toolbar action.
  - Every edit is below line 36, so the key's P3t (18–25) and P4t (30–36) ranges still point at the same code. `key.json` is unchanged since `09733d7`.
- **Run:** started 2026-09-27T20:09:38Z, with `2.1.283 (Claude Code)`. It used run B's command from the first section, from a fresh `git init` directory holding only `tokened/`.
- **Score:** `detected 2/2, missed [], false positives [], unscored 2` (exit 0). Accepted.
- **Edits:** `git status --porcelain` was empty in the run directory, and also in the repository that holds the `--add-dir` plugin dir, both before and after the run.
- **Unscored findings:** both are real, unplanted issues.
  - The edit sheet's Cancel doesn't discard the edit, because the `TextField` writes straight to the parent's `name` (HIG Sheets).
  - A bare `pencil` symbol can be misread (swift:design `sf-symbols.md` → Choosing a Symbol).
  - Neither calls a token hard-coded.

~~~text capture=review-2026-09-27-b2
No screenshots were provided, so this review covers the code only. It targets iOS 26 and macOS 26 (`Package.swift:6`). Values that come from `DesignTokens` (spacing, palette, motion) are the project's own choices, so I didn't report them.

## Findings
- [high] The Sync status is a green or red `Circle` with no symbol or text, so its meaning is carried by colour alone. VoiceOver reads only "Status". — `Sources/Demo/SettingsView.swift:33` — HIG: https://developer.apple.com/design/human-interface-guidelines/color — Fix: replace the `HStack`/`Spacer`/`Circle` with `LabeledContent("Status") { Label { Text(isSynced ? "Synced" : "Not Synced") } icon: { Image(systemName: isSynced ? "checkmark.circle.fill" : "exclamationmark.triangle.fill").foregroundStyle(isSynced ? DesignTokens.Palette.success : DesignTokens.Palette.danger) } }`. Colour only the symbol and keep the words in the primary style. This also brings the row in line with the Form's `LabeledContent` layout.
- [high] On iPhone and iPad the edit-name pencil button's tap area is under 44×44 pt. The `.frame(width: 28, height: 28)` sits outside a `.plain` button, so only the glyph itself responds to taps. — `Sources/Demo/SettingsView.swift:18`, `:24` — HIG: https://developer.apple.com/design/human-interface-guidelines/buttons — Fix: replace the row with an inline `TextField("Name", text: $name)` in the Form. That removes the button and the sheet. If you keep the sheet, make the whole row the button: `Button { editingName = true } label: { LabeledContent("Name", value: name) }`. (On Mac the 20×20 pt minimum is met.)
- [medium] Cancel in `EditNameSheet` doesn't discard the edit. The `TextField` writes straight into the parent's `name`, so every keystroke is already saved when Cancel is tapped. — `Sources/Demo/SettingsView.swift:74`, `:79` — HIG: https://developer.apple.com/design/human-interface-guidelines/sheets — Fix: edit a local `@State private var draft` that starts from `name`. Bind the `TextField` to `draft`, have Done set `name = draft` before `dismiss()`, and have Cancel only dismiss.
- [low] The edit button is a bare `pencil` symbol, which people can misread. — `Sources/Demo/SettingsView.swift:21` — HIG: https://developer.apple.com/design/human-interface-guidelines/icons — Fix: use a text button (`Button("Edit")`). The inline `TextField` fix from the second finding removes the button entirely.

Also noted but not reported: the `DesignTokens.Palette` colours are fixed `Color(red:green:blue:)` values with no dark-mode or increased-contrast versions. That's the project's decision. If you want them, asset colour sets would provide those versions.

Outside design scope: the storage figures are hard-coded strings. Use `.formatted(.byteCount(...))` and localise them (`swift:swiftui`).

## Not checked
- **Contrast in light, dark and Increase Contrast:** no screenshots. Captures of the status row and progress tint in each appearance would show it.
- **Dynamic Type:** no capture at accessibility sizes. An iOS capture at `.accessibility5` would show whether the Name row squeezes or truncates.
- **Mac presentation:** the App or scene file isn't in the inputs, so I can't see whether this opens as a `Settings` scene from the app menu (Command-Comma). I also can't see whether Save has a menu bar command and keyboard shortcut.
- **Delete Account confirmation:** the button's action is empty, so I can't check whether it asks for confirmation before deleting.
~~~

## 2026-09-28 — re-run after the Mac hit-target and scorer changes

The method changed, so all three runs ran again.

- **Skill:** commit `1d980d5`.
  - Review now judges a Mac control against the Mac sizes in swift:design's `platform-idioms.md` (20×20 pt minimum, 28×28 pt default) instead of 44×44 pt.
  - An image that can't show a hit region sends it to `## Not checked`.
- **Key and scorer:** commit `9903246` (2026-09-28T03:42:51Z), committed before this section's first run.
  - A finding is matched by its violation and location only, never by its fix text.
  - A `:41–72` continuation after `File.swift:14` counts.
  - N3 checks every pixel measurement for its own `estimated` mark, and exempts HIG reference sizes such as "the 20×20 pt minimum".
  - The screenshot run no longer expects P3, because its hit region isn't visible (`key.json` → `runs.screenshot.excluded`).
  - P4's pattern also accepts "colour carries the meaning alone", the phrasing of the first section's run A. Under the old scorer that finding was credited only through its fix text.
  - Re-scored with this key, the earlier recorded outputs give run A 8/8, the run B re-run 2/2 and run C 4/4, with every violation credited from its own finding. `maintenance/tests/test_review_score.py` pins these results.
- **Runs:** started 2026-09-28T03:44:28Z, `2.1.283 (Claude Code)`. The same commands as the first section, in fresh `git init` directories.

| Run | Input | `score.py` | `git status --porcelain` | Accepted |
|-----|-------|------------|--------------------------|----------|
| A | `planted/` code | `detected 8/8, missed [], false positives [], unscored 1` (exit 0) | empty | yes |
| B | `tokened/` code (fixture `28e5c32`) | `detected 2/2, missed [], false positives [], unscored 3` (exit 0) | empty | yes |
| C | `screenshot.png` | `detected 4/4, missed [], false positives [], unscored 1` (exit 0) | empty | yes |

The repository holding the `--add-dir` plugin dir was also clean before and after the runs.

### Unscored findings

All five are real, unplanted issues:

- **A:**
  - The pencil button has only an icon and no accessibility label (HIG Accessibility, Icons).
- **B:**
  - Cancel in the edit sheet keeps the edits, because the `TextField` writes straight to the parent's `name` (HIG Sheets).
  - On Mac, `.primaryAction` puts Save at the leading edge of the toolbar. Apple's `ToolbarItemPlacement.primaryAction` documentation confirms that macOS places the primary action on the leading edge.
  - A bare pencil can be misread as Edit (swift:design `sf-symbols.md` → Choosing a Symbol).
- **C:**
  - The same pencil note, as a low finding.

Run C gives every size as an estimate at @2x. It lists the pencil's unseen hit region under `## Not checked`, along with the platform, contrast, Dynamic Type, VoiceOver, the toolbar and motion.

### Always-loaded context (0.1.6)

Asked with no tools to list every `swift:` skill it has, with `claude -p --plugin-dir plugins/swift`, the model named `swift:concurrency`, `swift:design`, `swift:swiftui` and `swift:testing`. `swift:review` wasn't in its context.

### Raw output

#### A — `planted/`

~~~text capture=review-2026-09-28-a
Found 10 issues in `SettingsView.swift`, 4 of them high severity. I reviewed against iOS 26 and macOS 26, the platforms in `Package.swift`. The project has no design tokens, colour sets or design skill of its own, so system defaults are the baseline.

## Findings
- [high] The Sync status is only a red or green `Circle`, with no symbol or text. The state depends on colour alone, and VoiceOver reads nothing for it — `Sources/Demo/SettingsView.swift:68` — HIG: https://developer.apple.com/design/human-interface-guidelines/color — Fix: put a `Label` inside `LabeledContent("Sync")`. Its text says "Synced" or "Not Synced", and only its icon (`checkmark.circle.fill` or `exclamationmark.triangle.fill`) takes `.green` or `.red`. The text stays primary.
- [high] The pencil edit button's tap area is under 44×44 pt. The 28×28 frame is already too small, and because it sits outside a `.plain` button it adds no tappable area. Only the pencil glyph (about body-text size) responds, which is likely also under the Mac minimum of 20×20 pt — `Sources/Demo/SettingsView.swift:49` — HIG: https://developer.apple.com/design/human-interface-guidelines/buttons — Fix: make the whole Name row the control (a `Button` or `NavigationLink` row). If the inline button stays, put `.frame(minWidth: 44, minHeight: 44)` and `.contentShape(.rect)` on its label.
- [high] Delete Account has no `role: .destructive`. It is `.borderedProminent` with a red tint, which makes it the most prominent control in the content — `Sources/Demo/SettingsView.swift:83` — HIG: https://developer.apple.com/design/human-interface-guidelines/buttons — Fix: use `Button("Delete Account", role: .destructive) { … }` with the default style, in its own last `Section`. The role supplies the red.
- [high] The "Account" heading uses `.system(size: 13, weight: .ultraLight)`. The fixed size ignores Dynamic Type, and the HIG rules out Ultralight — `Sources/Demo/SettingsView.swift:43` — HIG: https://developer.apple.com/design/human-interface-guidelines/typography — Fix: make it a `Section("Account")` header, which the form styles and marks as a heading for VoiceOver. If it stays standalone, give it a text style such as `.headline` at Regular weight or heavier.
- [medium] Export, Share and Save in the toolbar are all `.borderedProminent`. Counting Delete Account, the screen has four prominent buttons. On Mac, toolbar items shouldn't have bezels either — `Sources/Demo/SettingsView.swift:19` — HIG: https://developer.apple.com/design/human-interface-guidelines/toolbars — Fix: keep the prominent style only on Save, at the trailing end. Give Export the default toolbar style. Make Share a `ShareLink` (`square.and.arrow.up`) in its own `ToolbarItem`, separate from the text buttons.
- [medium] The settings are a `ScrollView` of `VStack`/`HStack` rows with `Divider`s instead of a `Form`. The sheet's `TextField` also sits bare with padding — `Sources/Demo/SettingsView.swift:14`, `:41`, `:97` — HIG: https://developer.apple.com/design/human-interface-guidelines/lists-and-tables — Fix: use a `Form` with `.formStyle(.grouped)` containing:
  - `Section("Account")` with `LabeledContent` rows for Name, Email and Sync
  - `Section("Storage")` with `LabeledContent("Used", value: "3.2 GB of 5 GB")`
  - a last `Section` for Delete Account

  `LabeledContent` also lines up the values and reads each row as one VoiceOver element. In the sheet, use `Form { TextField(...) }`.
- [medium] The Storage card has `.glassEffect(.regular, in: .rect(cornerRadius: 16))`, which puts glass on content — `Sources/Demo/SettingsView.swift:82` — HIG: https://developer.apple.com/design/human-interface-guidelines/materials — Fix: remove the glass and the hand-picked radius, and make Storage a `Section` of the Form.
- [medium] The Edit Name sheet has Done but no Cancel. The field is bound directly to `name`, so edits apply as you type and can't be abandoned — `Sources/Demo/SettingsView.swift:101`, `:97` — HIG: https://developer.apple.com/design/human-interface-guidelines/sheets — Fix: edit a local `@State` draft and add `ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }`. Done writes the draft back to `name`, then dismisses.
- [medium] The pencil button shows only an icon and has no accessibility label. The HIG also warns that a pencil can be misread, so "Edit" works better as text — `Sources/Demo/SettingsView.swift:52` — HIG: https://developer.apple.com/design/human-interface-guidelines/accessibility — Fix: use `Button("Edit") { … }`, or keep the symbol and add `.accessibilityLabel("Edit Name")`. If the whole row becomes the control, this issue goes away.
- [medium] The Name, Email and Sync rows keep the label and value side by side at every text size. At accessibility sizes they wrap instead of stacking — `Sources/Demo/SettingsView.swift:44`, `:58`, `:65` — HIG: https://developer.apple.com/design/human-interface-guidelines/typography — Fix: use `AnyLayout` to switch to `VStackLayout(alignment: .leading)` when `dynamicTypeSize.isAccessibilitySize`. If you move to `LabeledContent` rows, check them at `.accessibility5`.

## Not checked
- **How it looks:** contrast, spacing, Dark Mode and Increase Contrast. There was no screenshot; light and dark captures on iPhone and Mac would show these.
- **Dynamic Type:** no capture at an accessibility text size. A preview with `.dynamicTypeSize(.accessibility5)` would confirm the row-layout finding.
- **Mac:**
  - whether this screen is a `Settings` scene opened with Command-Comma
  - whether Export, Share and Save have menu bar commands and keyboard shortcuts

  The `App` file with its scenes and `.commands` would show both.
- **Top-level navigation** (tab bar or sidebar) and how this screen is reached: the root view wasn't provided.
- **VoiceOver reading order across the whole screen:** this needs an Accessibility Inspector pass.
~~~

#### B — `tokened/`

~~~text capture=review-2026-09-28-b
I've finished the review. **SettingsView.swift has five findings: three high, one medium and one low.** The project targets iOS 26 and macOS 26 (from `Package.swift`), and the file has no `#if os` branches, so I checked it against both. I treated the values in `DesignTokens` as the project's own choices, not findings. That includes the `Palette` colours, which are built with `Color(red:green:blue:)` and have no dark or increased-contrast variants.

## Findings
- [high] **The sync status is shown by colour alone.** A green or red `Circle` sits next to "Status" with no symbol or text, so colour-blind users can't tell the states apart and VoiceOver reads only "Status". — `SettingsView.swift:30-35` — HIG: https://developer.apple.com/design/human-interface-guidelines/color, https://developer.apple.com/design/human-interface-guidelines/accessibility — Fix: replace the `HStack`/`Spacer`/`Circle` with `LabeledContent("Status") { Label { Text(isSynced ? "Synced" : "Not Synced") } icon: { Image(systemName: isSynced ? "checkmark.circle.fill" : "exclamationmark.triangle.fill").foregroundStyle(isSynced ? DesignTokens.Palette.success : DesignTokens.Palette.danger) } }`. The words stay in the primary style, the symbol carries the colour and grows with Dynamic Type, and VoiceOver reads the state.
- [high] **The edit-name button is too small to tap reliably.** `.frame(width: 28, height: 28)` is applied outside the `.plain` button, so it adds no hit area. The tappable region is just the pencil glyph, about 17–20 pt on iPhone (estimated). That is under 44×44 pt on iPhone and iPad, and probably under the 20×20 pt Mac minimum at 13 pt body text (estimated). — `SettingsView.swift:18-24` — HIG: https://developer.apple.com/design/human-interface-guidelines/buttons — Fix: make the whole row the button with `Button { editingName = true } label: { LabeledContent("Name", value: name) }`. If you keep a separate control, put `.frame(minWidth: 44, minHeight: 44)` and `.contentShape(.rect)` on the label, inside the button.
- [high] **Cancel in the Edit Name sheet doesn't discard changes.** The `TextField` is bound straight to the parent's `name`, so each keystroke changes the Settings row, and Cancel just closes the sheet with the edits kept. HIG says Cancel "dismisses a sheet without saving any changes". — `SettingsView.swift:74`, `:79` — HIG: https://developer.apple.com/design/human-interface-guidelines/sheets — Fix: edit a local `@State private var draft` that starts as `name`. Done sets `name = draft` and then dismisses; Cancel only dismisses. While `draft != name`, add `.interactiveDismissDisabled(true)` and show a `confirmationDialog` so a swipe-down can't silently drop the edit.
- [medium] **On Mac, the Save button lands at the leading edge of the toolbar.** `.primaryAction` goes on the trailing edge on iOS but the leading edge on macOS, and this view has no Mac branch. On top of that, a Mac settings window's toolbar should only switch between panes. — `SettingsView.swift:54-57` — HIG: https://developer.apple.com/design/human-interface-guidelines/toolbars, https://developer.apple.com/design/human-interface-guidelines/settings — Fix: limit the Save item to iOS with `#if os(iOS)`. On Mac, show the form in a `Settings` scene with no action buttons in its toolbar.
- [low] **The pencil icon can be misread as Edit.** A pencil alone is one of the symbols Apple says can be misread for Edit. — `SettingsView.swift:21` — HIG: https://developer.apple.com/design/human-interface-guidelines/icons — Fix: use a text button, `Button("Edit")`. Making the whole row tappable, as in the hit-target fix, removes the icon altogether.

Outside this review's scope: `.animation(DesignTokens.Motion.standard, value: isSynced)` at line 59 covers the whole `Form`. Narrowing it to the status view is a `swift:swiftui` question.

## Not checked
- **Dynamic Type:** I had no capture at accessibility sizes. An AX5 screenshot would show whether the Name row (`LabeledContent` plus the button) and "3.2 GB of 5 GB" truncate or stack.
- **Contrast and dark mode:** I couldn't measure how the token colours on the status symbol and the progress bar look against grouped backgrounds, in dark mode or with Increase Contrast on. That needs captures in light and dark, with Increase Contrast on.
- **Mac settings setup:** the app's `App` file isn't among the inputs. I couldn't check whether this form sits in a `Settings` scene opened with Command-Comma, whether the window is titled "*App Name* Settings", or whether there are menu commands and shortcuts.
- **Delete Account:** its action is empty, so I couldn't judge whether it asks for confirmation before deleting.
- **Mac sheet size:** a Mac screenshot would show whether the Edit Name sheet opens at a sensible default size.
~~~

#### C — `screenshot.png`

~~~text capture=review-2026-09-28-c
I found 5 issues in `screenshot.png`: 1 high, 3 medium and 1 low. The repo has no view code, so this review comes from the image alone. It also has no design tokens, colour sets or project design skill, so no values were excused as project choices.

I assumed a scale of @2x: the image is 780×594 px, so the screen is about 390×297 pt. The image doesn't show which platform this is: there's no status bar, bar or window frame. 390 pt is the width of an iPhone.

## Findings
- [high] The Sync state is shown only by a red dot, with no symbol or words, so colour alone carries the meaning — screenshot: Sync row, trailing edge — HIG: https://developer.apple.com/design/human-interface-guidelines/color — Fix: say the state in words and put the colour on a symbol, e.g. `LabeledContent("Sync") { Label { Text("Sync Failed") } icon: { Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.red) } }`, keeping the text in the primary style. If Sync is an on/off setting rather than a status, use `Toggle("Sync", isOn: $isSyncOn)` instead.
- [medium] "Delete Account" is the only filled button on the screen, so the destructive action looks like the main action — screenshot: bottom-left button — HIG: https://developer.apple.com/design/human-interface-guidelines/buttons — Fix: drop the prominent style and use `Button("Delete Account", role: .destructive) { … }` in its own last `Section` of the form. iOS draws it as a red text row.
- [medium] The "Account" group header uses a Light or thinner weight: its strokes are visibly thinner than the Regular row labels (estimated) — screenshot: top-left header — HIG: https://developer.apple.com/design/human-interface-guidelines/typography — Fix: let `Section("Account")` supply the header style. If it stays custom, use a text style at Regular weight or heavier, and make it quieter with `.foregroundStyle(.secondary)` rather than a lighter weight.
- [medium] The labelled values are rows split by full-width lines on a plain background under a custom header. That doesn't match any platform's `Form` or `List` (iOS shows inset groups on the grouped background; the Mac's `.grouped` style shows a rounded group box), so it looks like stacks with dividers — screenshot: Name, Email and Sync rows — HIG: https://developer.apple.com/design/human-interface-guidelines/lists-and-tables — Fix: `Form { Section("Account") { LabeledContent("Name", value: name); LabeledContent("Email", value: email); … } }` with `.formStyle(.grouped)`, so the platform supplies the separators, header, margins and alignment.
- [low] Name editing is an icon-only pencil, and HIG notes a pencil can be misread as Edit — screenshot: Name row, trailing edge — HIG: https://developer.apple.com/design/human-interface-guidelines/icons — Fix: make the name editable in the row with `TextField("Name", text: $name)` inside the Section, or use an "Edit" text button. If the symbol stays, give it `.accessibilityLabel("Edit Name")`.

## Not checked
- **Target platform:** the image can't pin it. Send the Xcode project or `Package.swift`, or name the platform.
- **Hit targets:**
  - The Delete Account button is about 117×24 pt (estimated, @2x). On iPhone or iPad that is below the 44 pt minimum, which would be a high finding. On Mac it is above the 20 pt minimum.
  - The pencil glyph is about 10×10 pt (estimated, @2x), but the image can't show how large its tappable area is. The code (its frame or `contentShape`) would settle it.
- **Email colour:** the image doesn't show whether the blue email can be tapped. If it's static text, blue marks interactive elements and shouldn't be used on it, which is a colour finding. The name value is grey, so the two values are styled differently.
- **Contrast and appearance:** the white "Delete Account" label on the red fill looks below 4.5:1 for regular text. The code would settle whether that red is the system `.red`, which has an increased-contrast version, and the text's size. Send captures in dark mode and with Increase Contrast on.
- **Dynamic Type:** point sizes and text styles can't be measured from the image. A capture at an accessibility text size would show whether "Email … jordan@example.com" stacks or truncates.
- **VoiceOver:** labels for the pencil and the dot, and the reading order, need the code or an Accessibility Inspector pass.
- **Delete flow:** whether deleting asks for confirmation (`confirmationDialog`) needs the code or a screen recording.
- **Navigation and toolbar:** no title, navigation bar or window toolbar is in the frame. A capture that includes them is needed.
- **Motion and Reduce Motion:** these need a screen recording or the code.
~~~

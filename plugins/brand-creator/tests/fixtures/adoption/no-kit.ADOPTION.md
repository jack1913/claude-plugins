# Acme: adoption

Status: **not started**. 0 of 21 rows done, 0 doing, 21 to do. The survey found 45 matching lines in 9 files and 6 icon and logo files across 1 repositories; 4 more lines in 4 files are kept, not counted.

Repositories, read only from here (nothing in them is edited by brand-creator): `shop` (no git head).

21 rows, surveyed on 2026-10-17. **Line numbers may drift: find the place by its content** (the Find column), not by the line. Paths are relative to the repository. Each row has a status: to do, doing (made in the repository's working tree, not committed) or done (committed; whether a row is done is the owner's call). Progress is stored apart from the rows (`adoption status`); rows are never renumbered or removed, a new survey only adds rows at the end.

Groups: Old name 8, Old colour 3, Icon and logo files 4, Package and platform metadata 5, README badges and header images 1.

| # | Status | Group | Repo | File | Lines (may drift) | Find | Change |
|---|---|---|---|---|---|---|---|
| 1 | to do | Old name | shop | `README.md` | 1, 4, 6 | `# Oldco App` | Replace the old name where people read it (titles, labels, copy). Identifiers (bundle id, package name, repository URL) are renames: see LAUNCH.md. | <!-- target-repo -->
| 2 | to do | Old name | shop | `app.metainfo.xml` | 3-4 | `<id>com.oldco.app</id>` | Replace the old name where people read it (titles, labels, copy). Identifiers (bundle id, package name, repository URL) are renames: see LAUNCH.md. | <!-- target-repo -->
| 3 | to do | Old name | shop | `docs/notes.md` | 3-4 | `The old_co style name is only used in scripts. Nothing else to see; this file is also use…` | Replace the old name where people read it (titles, labels, copy). Identifiers (bundle id, package name, repository URL) are renames: see LAUNCH.md. | <!-- target-repo -->
| 4 | to do | Old name | shop | `macos/Info.plist` | 5, 7 | `<string>Oldco</string>` | Replace the old name where people read it (titles, labels, copy). Identifiers (bundle id, package name, repository URL) are renames: see LAUNCH.md. | <!-- target-repo -->
| 5 | to do | Old name | shop | `package.json` | 2, 4, 6 | `"name": "oldco-app",` | Replace the old name where people read it (titles, labels, copy). Identifiers (bundle id, package name, repository URL) are renames: see LAUNCH.md. | <!-- target-repo -->
| 6 | to do | Old name | shop | `public/manifest.webmanifest` | 2-3 | `"name": "Oldco App",` | Replace the old name where people read it (titles, labels, copy). Identifiers (bundle id, package name, repository URL) are renames: see LAUNCH.md. | <!-- target-repo -->
| 7 | to do | Old name | shop | `src-tauri/tauri.conf.json` | 2-3 | `"productName": "Oldco App",` | Replace the old name where people read it (titles, labels, copy). Identifiers (bundle id, package name, repository URL) are renames: see LAUNCH.md. | <!-- target-repo -->
| 8 | to do | Old name | shop | `src/main/app.rs` | 2-4 | `println!("Welcome to Oldco App");` | Replace the old name where people read it (titles, labels, copy). Identifiers (bundle id, package name, repository URL) are renames: see LAUNCH.md. | <!-- target-repo -->
| 9 | to do | Old colour | shop | `README.md` | 8 | `Colours: the accent is #123456 and the dark ground is #0a0a0a.` | Replace with the matching token value from assets/tokens/ (light and dark); check the contrast pair it sits in. | <!-- target-repo -->
| 10 | to do | Old colour | shop | `public/manifest.webmanifest` | 4 | `"theme_color": "#123456",` | Replace with the matching token value from assets/tokens/ (light and dark); check the contrast pair it sits in. | <!-- target-repo -->
| 11 | to do | Old colour | shop | `src/theme.css` | 2-4 | `--accent: #123456;` | Replace with the matching token value from assets/tokens/ (light and dark); check the contrast pair it sits in. | <!-- target-repo -->
| 12 | to do | Icon and logo files | shop | `assets/icons.appiconset` | 3 file(s) | `Contents.json, icon_16.png, icon_32.png` | Replace these 3 icon and logo file(s) with the pack's files and keep the file names the code refers to. No pack file has one of these names: map each to a slot in INVENTORY.md. | <!-- target-repo -->
| 13 | to do | Icon and logo files | shop | `docs/img` | 1 file(s) | `logo.png` | Replace these 1 icon and logo file(s) with the pack's files and keep the file names the code refers to. No pack file has one of these names: map each to a slot in INVENTORY.md. | <!-- target-repo -->
| 14 | to do | Icon and logo files | shop | `public` | 1 file(s) | `favicon.ico` | Replace these 1 icon and logo file(s) with the pack's files and keep the file names the code refers to. No pack file has one of these names: map each to a slot in INVENTORY.md. | <!-- target-repo -->
| 15 | to do | Icon and logo files | shop | `src-tauri/icons` | 1 file(s) | `icon.png` | Replace these 1 icon and logo file(s) with the pack's files and keep the file names the code refers to. No pack file has one of these names: map each to a slot in INVENTORY.md. | <!-- target-repo -->
| 16 | to do | Package and platform metadata | shop | `app.metainfo.xml` | 3-5 | `<id>com.oldco.app</id>` | Check each slot against the new brand: name, description, icon path, theme and background colours, author, homepage. | <!-- target-repo -->
| 17 | to do | Package and platform metadata | shop | `macos/Info.plist` | 4, 6, 8 | `<key>CFBundleName</key>` | Check each slot against the new brand: name, description, icon path, theme and background colours, author, homepage. | <!-- target-repo -->
| 18 | to do | Package and platform metadata | shop | `package.json` | 2, 4-6 | `"name": "oldco-app",` | Check each slot against the new brand: name, description, icon path, theme and background colours, author, homepage. | <!-- target-repo -->
| 19 | to do | Package and platform metadata | shop | `public/manifest.webmanifest` | 2-6 | `"name": "Oldco App",` | Check each slot against the new brand: name, description, icon path, theme and background colours, author, homepage. | <!-- target-repo -->
| 20 | to do | Package and platform metadata | shop | `src-tauri/tauri.conf.json` | 2-3, 5-6 | `"productName": "Oldco App",` | Check each slot against the new brand: name, description, icon path, theme and background colours, author, homepage. | <!-- target-repo -->
| 21 | to do | README badges and header images | shop | `README.md` | 3-4 | `[![build](https://img.shields.io/badge/build-passing-green)](https://example.com/ci)` | Check the header image and the badges: logo or banner from the pack, labels and colours for the new name. | <!-- target-repo -->

## How this list is applied

Nothing in a repository changes until the owner asks for it (gate G6), and then only on a branch the owner names.

- One repository at a time: one implementer works through its rows, then a separate review checks the work before
  anything is committed.
- Each place is found by the text in the Find column, never by the line number. A row whose text is no longer there is
  reported as not done, never guessed.
- Icons, lockups and other pack files are copied from the pack and compared byte for byte with it (`cmp`); they are never
  redrawn, re-exported or recoloured in the repository.
- The review runs the repository's own build and tests and quotes the results. A check that needs a real device is listed
  as not verified.
- The repository's hooks always run; a hook that fails for an unrelated reason is reported, and fixed as a separate change
  only if the owner agrees.
- Commit, merge and push are three separate asks. Before a push, what it triggers (CI, a deploy, a publish) is said first.
- A row that acts on a live service (a rename, an upload, a store listing, a DNS change) needs its own OK.

## Kept, not counted

4 matching lines in 4 files that the survey saw and did not make rows, each with its reason. A row or this list accounts for every match.

- change history: it records what was true then and is not rewritten:
  - `shop` `CHANGELOG.md` (1 line, old name) <!-- target-repo -->
- legal text: it names its legal owner, which is not a brand slot:
  - `shop` `LICENSE` (1 line, old name) <!-- target-repo -->
- generated or vendored output: fix the source and rebuild:
  - `shop` `dist/bundle.js` (1 line, old name) <!-- target-repo -->
- lock file: the package manager writes it, nobody edits it by hand:
  - `shop` `package-lock.json` (1 line, old name) <!-- target-repo -->

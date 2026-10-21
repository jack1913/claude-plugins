# Choose a tier

Pick how far to go. You can move up later with one question.

## The three tiers

| Tier | What you get | Extra tools needed |
| --- | --- | --- |
| Quick | A style board (how brands like yours look, with real examples to pick from), one board of 3 directions, one refine round, the logo on its own and with your name (SVG and PNG), favicons, a social card, your colours and fonts as ready-to-use code values (design tokens), and a short guide | uv, Node 22+, Python 3.10+, resvg, Chromium (installed by setup) |
| Standard | Quick, plus research, naming when the name is open, the full brand book (a web page, plus a PDF for checking on screen, not for print), profile images, print stationery and an e-mail signature (opt-in), a press kit and social posts | Also Ghostscript and poppler, for print and the PDF checks |
| Full | Standard, plus a list of every place your product shows an icon, icon packs for each platform (Apple, Windows, Linux, Android, Chrome extension, MSIX, tray, Tauri, Wallet, developer), a read-only look at your repositories (`ADOPTION.md`) and a launch checklist (`LAUNCH.md`) | Also macOS with Xcode for the Apple packs (no fallback), and ripgrep for the repository look |

How long: Quick is 2 to 3 rounds in one sitting. Standard is 4 to 6 rounds over a day or two. Full is several sessions.

## Which one to pick

- A shop, band or person who needs a logo, a look and a few files: **Quick**.
- A business that also needs a full brand book, print and a press kit: **Standard**.
- A product with apps and sites that need icons on every platform, and a brand to apply across your repositories:
  **Full**.

If you aren't sure, start with Quick. Move up when you need more.

## Check what's missing

Run `brand-creator prereq --for quick` (or `--for standard`, or `--for full`). It lists what's missing, and
`/brand-creator:setup` installs what it can.

## Related

- [Make your first brand](make-your-first-brand.md)
- [Platform support](../reference/platform-support.md)

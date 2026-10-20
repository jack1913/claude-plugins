# Make icons and images from your logo

Turn a logo you already have into the files a product ships: favicons, app icons, social images and more. You don't need
a brand project.

## Before you start

- brand-creator is installed and set up.
- You have a finished logo file: SVG, PNG, JPG or PDF. An SVG must be pure vector, with text outlined.

## Make the files

1. Ask in your own words, such as "favicons from my logo.svg", or type the command:

   > /brand-creator:brand-assets

2. Answer a couple of quick questions: which targets (web only, web and social, web and app icons, or every target), and
   whether a dark version of the logo exists. Your name, site address and any tagline come in one plain message.
3. Claude draws each size at real pixels, checks small sizes, and records what it made in a manifest.

Without a project, everything goes into `./brand-assets/`. Inside a brand project, the files follow your project's list of
places that show an icon.

## What you can get

Favicons and web app icons, Open Graph and social images, Apple app icons, Windows `.ico` and installer art, Linux icon
themes, tray icons, Tauri, Wallet passes, developer surfaces, Android adaptive icons, Chrome extension icons and MSIX
assets. The full list: [What it makes](../reference/what-it-makes.md).

It makes files from an existing, approved logo only. It doesn't design or redraw a logo.

## Check it worked

- The files and a manifest are in `./brand-assets/` (or your project's `assets/`).
- Size checks ran at real pixels, or the report says "not verified" and why.

## If something goes wrong

| You see | Do this |
| --- | --- |
| `emit apple` needs macOS with Xcode | Build the Apple files on a Mac. Everything else works elsewhere |
| "no renderer opt-in is recorded" | Answer the renderer question: resvg for an SVG logo, Pillow for a PNG |
| The SVG is refused | Export it again with text outlined |

More: [Troubleshooting](../reference/troubleshooting.md).

## Related

- [Platform support](../reference/platform-support.md)
- [Make the brand book](make-the-brand-book.md)

# brand-creator

A logo, colours, type and every file your brand needs, made with you. It works for anything with a name: a bakery, a
photographer, a band, a law practice, an app.

You describe it, Claude shows three directions, you pick one, and Claude builds it and checks it. You decide on taste.

## Set it up

You need Claude Code 2.1.271 or newer. Then:

```text illustrative
/plugin marketplace add jack1913/claude-plugins
/plugin install brand-creator@jack1913
/brand-creator:setup
```

If `/brand-creator:setup` isn't listed yet, run `/reload-plugins` first.

Setup shows what it will download (the drawing tools, about 200 MB) and waits for your yes. It also checks for uv,
Node 22+, Python 3.10+ and resvg, and tells you how to get any that are missing. macOS has full support; Linux works
too, except the Apple icon packs.

## Make a brand

Say what you need, in plain words:

> a logo and a look for my bakery

1. **A few quick questions,** each with a suggested answer: how far to go, how it relates to a brand you already run
   (only if you mention one), and the name, if you don't have one yet. It may also ask whether boards can be shown as a
   private claude.ai page.
2. **Three directions on one page** (Claude calls it a board). Each one is clearly different, and "None of these" is
   always an option.
3. **You pick.** Answer by name, or by question and option, like `1a 2b`. `ok` takes every suggestion.
4. **One refine round** (`/brand-creator:round`), then your pick is locked in.
5. **Claude builds it:** the logo at real sizes, colours, a contrast check, favicons, a social card and a short guide.

What a first round looks like, from the plugin's worked example (Acme, a made-up company): three directions called
Compass (calm), Lantern (warm, unusual for its field) and Keystone (bold), each shown at the hardest size it has to work
at, a 16 px browser tab. Claude's honest read: Compass is the steadiest, Lantern the braver choice, Keystone looks most
like everyone else. Then three questions: which direction, is the strategy right, and which tagline goes on the next
board. Acme answered `1a 2a 3a`, and Claude built Compass.

## How far to go

| Tier | You get | Takes about |
|---|---|---|
| Quick | the logo, favicons, a social card, your colours and fonts as ready-to-use code values, a short guide | one sitting |
| Standard | Quick, plus research, naming, the full brand book, print stationery, a press kit, social posts | a day or two |
| Full | Standard, plus icon packs for every platform (Apple, Windows, Linux, Android and more) and a launch checklist | several sessions |

Start small; moving up later is one question. Standard also needs Ghostscript and poppler; Full needs ripgrep, and a Mac
with Xcode for the Apple packs.

## Other things you can ask

| Say | You get |
|---|---|
| "favicons from my logo.svg" | icons and social images from a logo you already have, no project needed |
| "name ideas for my bakery" | name ideas cut to a shortlist, with a go / go-with-conditions / no verdict for each finalist |
| "is the name X taken" | a check on a name you have |
| "generate the brand book" | your brand book as one page, plus a PDF proof |

And a few commands you'll use:

| Type | It does |
|---|---|
| `/brand-creator:status` | shows where your project stands and what's next |
| `/brand-creator:check` | runs every check and tells you how to fix anything that fails |
| `/brand-creator:launch` | your launch checklist: domain, trademark, handles, one step at a time |

## It won't do these for you

- Buy a domain, file a trademark, register a handle or contact anyone. `/brand-creator:launch` hands you each step
  instead.
- Commit, merge or push to git on its own.
- Call a name "available". A name check says REGISTERED, NOT-FOUND or UNKNOWN. Whether you may legally use a name
  (trademark clearance) is yours to check.
- Delete your files. Anything it replaces moves to a dated `removed-<date>/` folder.

## Something off?

| You see | Do this |
|---|---|
| A tool stops with "cannot run" | Run `/brand-creator:setup` |
| A permission prompt on every step | Allow `Bash(brand-creator *)` in your Claude Code settings ([how](../../../plugins/brand-creator/README.md#permissions)) |
| Screenshots say "not verified" | Chromium, the browser it takes them with, is missing: run `/brand-creator:setup` |
| "needs macOS with Xcode" | Apple icon packs only build on a Mac with Xcode; everything else works on Linux too (Windows is untested) |

Everything else, from settings to costs: the [brand-creator README](../../../plugins/brand-creator/README.md).

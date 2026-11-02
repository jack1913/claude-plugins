# Troubleshooting

What you see, and what to do. Not sure what a message means? Show it to Claude and ask.

| You see | Do this |
| --- | --- |
| A tool stops with code 3 ("cannot run") | Run `/brand-creator:setup`, or the install command the message names. `brand-creator prereq --for quick` lists what's missing; use `standard`, `full`, `apple`, `print`, `names` or `adoption` instead of `quick` for those |
| `brand-creator: command not found` | Check the plugin is enabled (`/plugin`) and restart Claude Code. Meanwhile the skills switch to the full path |
| A permission prompt on every call | Add the rule on the [Permissions](permissions.md) page |
| Shots "not verified" | Chromium is missing or can't start. Run `/brand-creator:setup`. On Linux, install the libraries the message names. The board is still written |
| "no renderer opt-in is recorded" (Linux, Windows) | Answer the renderer question: resvg for an SVG logo, Pillow for a PNG |
| `emit apple` needs macOS with Xcode | Apple packs are built on a Mac with Xcode. Everything else works on Linux too. Windows is untested |
| A write to an earlier round or `history/` is blocked | That's the safety lock on finished rounds. Work in the latest round, or start a new one |
| A Python tool won't start | Put a `python3` 3.10 or newer on PATH. The message lists every interpreter it tried |

## Website references and reference pages

Only if your brief lists a site, in the Standard or Full tier.

| You see | Do this |
| --- | --- |
| Claude says your brief lists no site | Ask Claude to add your site to the "Required surfaces" line of your brief (`brief/BRIEF.md`, the notes Claude wrote from your answers at the start). The line needs a word for a site in English or Polish; in another language, add the word `site` |
| Claude says the site work is for Standard and Full | Your tier, how far your project goes, is Quick. Ask Claude to move your project up to Standard or Full. It takes one question |
| Claude says your brand's rules come first | Approve the list of rules Claude shows after asking whether your logo moves, such as which colours text may sit on. `/brand-creator:status` shows where you are |
| Claude says the references come first | Pick some references, or say "skip the references" |
| `/brand-creator:check` says an approved page is "not verified" | Not a failure: something the page relies on changed, such as a file it loads, your colours, your facts or your rules. Ask Claude to check the page and take its pictures again. Approving a later step, such as the book, does not cause this |
| `/brand-creator:check` fails an approved page | It names the page. If the page changed after you approved it, ask Claude to put it back, or approve it again. If it breaks one of your brand's rules, ask Claude to fix it, then approve it again |

More: [Get reference pages for your site](../use/get-reference-pages-for-your-site.md).

## Checking a page

| You see | Do this |
| --- | --- |
| The check fails a colour and names it | The page uses a colour that isn't yours for that theme, light or dark. The line names your nearest brand colour: use that one. If your brand's colours changed, ask Claude to change them in your brand project first |
| A price, a date or words like "coming soon" fail | The check reads them as claims, things the page states as true, and they aren't in your list of facts (`FACTS.md`). Give Claude the fact and where it comes from, written the way the page writes it. A placeholder? Ask Claude to mark it as a sample. Or take it out |
| A failing line names another website | The page fetches a font or a picture from the internet. Ask Claude, or whoever builds your site, to keep that file with the site's own files |
| The check won't start and says "page-check runs offline" | The address is not on your computer. For an address, the check opens only `localhost`: your own computer showing the site. Ask whoever builds your site for its finished folder, often called `dist` or `build`, and give Claude that instead |
| A font line says "not verified" | Usually your brand uses a common font, such as Arial or Helvetica, that this computer doesn't have, so the check can't see it drawn. Have the page bring its own copy of the font |
| The plugin's storage folder keeps growing after you check sites built elsewhere | Each check of a site built somewhere else keeps a copy of it there, and nothing deletes them. Old copies are safe to delete: your site and your reports are not in them. Where the folder is, and how to open it: [Old copies of a built site](../reference/page-check.md#old-copies-of-a-built-site) |

## The brand kit

Only if you asked Claude for the kit.

| You see | Do this |
| --- | --- |
| The kit check fails and names `voice.md`, `visual.md`, `golden-rules.md`, a recipe or a note of your own | These are your own pages in the kit. A note in double square brackets is still there: replace it with your own words. In `visual.md`, `golden-rules.md`, the recipes and your own notes written in Markdown, each list line also needs a tag, `[rule: <short name>]` or `[example]`, and a size, colour or ratio needs its source: a token, a rule or `[example]`. The line says which. Fix it with Claude, then ask Claude to build and check the kit again |
| The kit stops because a file in it was edited or added by hand | The made-for-you files are rebuilt from your brand project, so make the change there instead, then ask Claude to build again. To keep a file you added, ask Claude to move it into the kit's `recipes/` folder, which is yours, or a folder of your own: both travel with the kit. Or ask Claude to build with replace: it moves those files into a `removed-` folder with the date, and deletes nothing |
| The kit stops and names one of your approved pages | The page fails its page check, its check or pictures are out of date, it changed after you approved it, or it loads a file your project lacks or one outside your project. The message says which. Put that right with Claude, then ask Claude to build the kit again. A page that fails its check has to be fixed and approved again |
| The kit check says "not verified" and names what changed | Your brand changed after the kit was built. Ask Claude to build the kit again |
| The kit leaves a font out | The kit copies only open-licence fonts (OFL, a licence that lets you share a font with your product), with their licence text. A font not checked yet, including one an approved page or one of your masters brings, is left out too: ask Claude to check your fonts, then build the kit again. A font file the check can't read, such as `.ttc` or `.eot`, stays out however often you build. Any other font goes into your product only if you decide so, under its own licence |
| Claude says your website's copy of the kit is out of date (`not current`) | Ask Claude to put the new kit into that website with `/brand-creator:brand-adopt`. Both sides can show the same version: the message says which files still differ |

More: [Use your brand kit](../use/use-your-brand-kit.md).

## Redesigning a site you already have

Only if you told Claude your brand goes into a site that already works.

| You see | Do this |
| --- | --- |
| The review, or `/brand-creator:check`, says something from your old site is gone | The review lists each item, such as a link or a form field, and the files it was in; `/brand-creator:check` names the first few and how many more. For each, tell Claude to put it back, or say in your own words why it goes. Claude never decides for you |
| Claude can't read your local pages | Start your site on your computer, or ask whoever builds it to, keep it running, and ask Claude again. If its address changed, send the new one |

More: [Apply the brand to your product](../use/apply-the-brand-to-your-product.md#if-its-a-redesign-of-a-site-you-already-have).

## Related

- [Platform support](platform-support.md)
- [Claude Code versions](claude-code-versions.md)
- [Check a page against your brand](../use/check-a-page.md)

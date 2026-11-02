# Use your brand kit

Get your brand in one folder that a product repository can carry: your colours, fonts and logo files, your rules and
facts, ready-made snippets, and a few pages of your own about how the brand sounds and looks. Whoever builds a page in
that repository, you or an agent, finds the brand in one place. Asking Claude to check the kit catches a file someone
edited by hand, a link that leads nowhere and a brand change the kit does not have yet.

## Before you start

- You have approved your brand files: the [brand book](make-the-brand-book.md) is approved and `/brand-creator:check`
  passes. Any tier works.
- Your colours and fonts are built into design tokens. The steps before the book do that.
- Your project has font files? Ask Claude to check the fonts first. The kit copies a font only when that check reads it as
  open-licence (OFL) and its licence text sits beside it.

## What is in the kit

The kit is a folder in your project, `.claude/skills/<your brand>-brand/`. It is also your brand's skill: it includes the
per-brand skill, so you do not need both.

Made for you. Never edit these; they come from your project:

- `SKILL.md`: the brand skill, with the kit's version.
- `brand/`: copies of your token files, logo files, open-licence fonts with their licence text, and, when your brand
  moves, the motion spec. Byte for byte, at the same paths as in your project.
- `rules.json` and `facts.json`: your rules, with a short id for each, and the facts you confirmed. Contact details never.
- `snippets/`: ready-made fonts, logo and text-on-each-ground code to copy into a page.
- `kit.json`: the version and a fingerprint of every file above.

Yours. Claude writes each once and never overwrites it:

- `EXTENDING.md`: how to extend the kit.
- `voice.md`, `visual.md` and `golden-rules.md`: how the brand sounds, how it looks beyond the tokens, and the few rules
  every piece keeps.
- `recipes/web-page.md`: the steps for building a page in your brand.

The kit has a version, `<edition>.<build>`. The build number goes up by one when anything in the kit changes, yours
included, and stays the same when nothing does.

## Ask for it

1. When you approve your brand files, Claude asks once what you want: `BRAND.md` and `DESIGN.md`, the brand skill, and the
   brand kit. Claude recommends the kit when your brief lists a site or you have product repositories. Answer yes to the
   kit. Skipped it? Ask later, in your own words:

   > Write the brand kit

2. Claude shows the plan first and writes nothing:

   ```text
   would write 15 generated files into .claude/skills/acme-brand/ (version 1.1)
   generated SKILL.md (…)
   generated brand/assets/logo/mark.svg (…)
   …
   scaffold voice.md (…, written once, never overwritten)
   …
   ```

3. Say go. Claude writes the kit.

## Fill your parts

A new kit is not done. `voice.md`, `visual.md` and `golden-rules.md` each start as a heading, one sentence and a note in
double square brackets that says what to write. Claude fills them with you:

1. `voice.md`: three sentences on how the brand sounds, with one right and one wrong example. They come from the tone
   chapter of your book and your voice facts.
2. `visual.md`: your layout habits, image style and what to keep out of a picture, from the book.
3. `golden-rules.md`: up to ten rules every piece keeps.
4. In `visual.md` and `golden-rules.md`, mark each bullet or numbered line as one of your brand's rules, by its short id in
   `rules.json`, or as an example. `voice.md` needs no marks. The bullets of a recipe get the same marks; its numbered
   steps need none. A number, a ratio or a colour in any of these names the token or rule it comes from, or its line
   says it is an example.
5. Ask Claude to build the kit again, so it records your text, then to check it:

   > Build the kit again, then check it

Your kit is whole when every note is replaced, every link points at a file inside the kit and the versions agree. The
web-page recipe is ready to use. Change it to fit how you build pages, or add a recipe of your own under `recipes/`.

## Test your kit

Want to know whether the kit is enough on its own? Once it is whole, ask for a kit test. It is optional, and Claude never
starts it unasked:

> Test my brand kit

1. Claude builds a hero and one other piece of a page in a temporary folder outside your project. It works from a copy of
   the kit alone, as someone in a product repository would.
2. The [page check](check-a-page.md) scores both against your brand. Then Claude reads the hero cold: a verdict, ship or
   fix, before any reason.
3. Each gap goes back where it belongs. A missing value goes to your tokens, a guessed rule to your brand rules, a missing
   claim to your facts, an unclear step to your own kit files. Claude never patches a file the kit made. It changes your
   project and builds the kit again.
4. Claude writes the result in your project's `BRAND-STATE.md` and lists the gaps still open.

The test runs in your conversation and starts no separate agent. The reader is not blind, because the same session wrote
the kit, so take the verdict as a first signal and not as proof.

## Put the kit in a product repository

The kit goes into a repository the same way the rest of your brand does, through `/brand-creator:brand-adopt`. That is for the
Full tier.

1. Look at the repository first, as in [Apply the brand to your product](apply-the-brand-to-your-product.md):

   > /brand-creator:brand-adopt survey

2. Ask for the kit to go into that repository:

   > Add the brand kit for the repository `<label>`

3. Ask for the repository to be applied and name your branch. Claude copies the kit's files one at a time. It never
   overwrites a file of yours that the repository already has, never copies into a global skills folder, and never commits.
4. A review compares the copy with your kit byte for byte before anything else happens.

## Check a copy is current

Type:

> /brand-creator:brand-adopt status

Under "kit copies" each repository reads `current`, `not installed` or `not current`. For the detail, ask Claude to check
the copy in a folder. It only reads, so the check changes nothing in the repository or in your project. You'll see
something like this:

```text
kit acme-brand, version 1.1
repo: not installed
  copy list, paths relative to .claude/skills/acme-brand/ (the generated files, kit.json last, then the owner files the repository lacks):
    SKILL.md
    brand/assets/logo/mark.svg
    …
    kit.json
    voice.md (owner file, the repository has none)
    …
read only: nothing in the installed kit folders changed while they were read
```

A copy that is not current lists the files that differ, are missing or are left over from an older kit. It also lists
your own files in the copy that differ: they belong to the repository, and an update keeps them.

A file left over is one your brand no longer has, such as a logo you took out. It is not on the copy list. Move it
to a `removed-<date>` folder in that repository, keeping the path it had, and delete nothing. Then the copy reads
`current`.

## When the brand changes

1. Change the brand in your project, as you always do: the tokens, the logo, the rules or the facts. Never change a file
   under `brand/`, `snippets/` or `reference-pages/`, or `rules.json` and `facts.json`: the next build stops on it.
2. Until you rebuild, the check says "not verified" and names what changed.
3. Ask Claude to build the kit again. The version goes up by one.
4. Put the new version in each repository with `/brand-creator:brand-adopt`. Until you do, its copy reads `not current`.
   If the new kit dropped a file the old one had, Claude moves that file into a `removed-<date>` folder in the repository,
   deletes nothing, and checks the copy again.

## Check it worked

- `.claude/skills/<your brand>-brand/kit.json` exists in your project.
- Asking Claude to check the kit passes, and `/brand-creator:check` lists no kit row as failing.
- In a repository, the copy reads `current`.

## If something goes wrong

| You see | Do this |
| --- | --- |
| Claude shows the plan and says it needs your OK | That is the plan. Say go and Claude writes the kit |
| Claude says your brand files are not approved yet | Approve them first: [Make the brand book](make-the-brand-book.md) |
| Claude says the tokens are not built | Ask Claude to build your tokens, then the kit again |
| The kit is written but without fonts, and Claude says to check the fonts | Ask Claude to check the fonts, then to build the kit again |
| A font is listed in the kit as not copied | It is not open-licence, or its licence text is missing from `assets/fonts/`. A font under another licence goes into a product only by your decision, under its own licence |
| A font in a reference page's folder, or one a page loads, is listed as not copied, and the check warns about a link to it | The same rule holds: the font check has to read that font (ask Claude to check it by name, together with the fonts in `assets/fonts/`), it has to be open-licence, and its licence text has to be in `assets/fonts/`. A font the kit does not copy goes into a product under its own licence |
| The check fails and names `voice.md`, `visual.md` or `golden-rules.md` | A note in double square brackets is still there. Replace it with your own text |
| The build stops because a file was edited by hand, or put into `brand/`, `snippets/` or `reference-pages/` | The message names the files. Change your project instead and build again. To keep a file, move it to `recipes/` or a folder of your own, or ask Claude to build with replace: it moves each file to a `removed-<date>` folder first, and deletes nothing |
| The check says "not verified" and names what changed | The brand changed after the kit was built. Ask Claude to build the kit again |
| A copy reads `not current` | Ask for the kit to be applied to that repository again with `/brand-creator:brand-adopt` |
| Claude refuses a folder when it checks a copy | It refuses your home folder, anything inside `~/.claude` and your brand project. The kit goes into one product repository at a time |
| Claude says there is no kit when you add it to a repository | Build the kit first |

More: [Troubleshooting](../reference/troubleshooting.md).

## Related

- [Make the brand book](make-the-brand-book.md)
- [Apply the brand to your product](apply-the-brand-to-your-product.md)
- [Check a page against your brand](check-a-page.md): the check the web-page recipe ends with
- [What it never does](../reference/what-it-never-does.md)

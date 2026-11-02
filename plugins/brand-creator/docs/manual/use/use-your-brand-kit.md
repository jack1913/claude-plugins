# Use your brand kit

Your brand kit is your brand in one folder: your colours, fonts and logo files, your rules and facts, ready-made bits
of code, and a few short files in your own words.

Your product is your website, app or online shop. When you, a developer or Claude build a page for it, a copy of the
kit inside its code puts your whole brand at hand, so nobody guesses a colour or a rule. Claude also uses the kit
whenever it makes something for your brand, such as a page or a post. Ask Claude to check the kit, and it catches a
hand edit, a dead link or a brand change the kit doesn't have yet.

## Before you start

- Your [brand book](make-the-brand-book.md) is approved.
- Your design tokens are built: your colours, fonts and sizes, saved as files a program can read. Claude makes them
  before the book, and says so if they are missing.
- Any tier can have a kit. Putting it into your product's code needs the Full tier. `/brand-creator:status` shows your
  tier.
- Your brand has font files of its own? Claude can tell you. Ask it to check your fonts first. The kit takes only fonts
  under the SIL Open Font License (OFL), a free licence that lets you pass a font on with your product, each with its
  licence text in your project's `assets/fonts/` folder.

## What is in the kit

The kit is a folder in your brand project (the folder Claude made when you started, the one holding `BRAND-STATE.md`),
named after your brand: `.claude/skills/acme-brand/` for Acme. Finder hides folders whose name starts with a dot: press
Command-Shift-period to see them. The hidden `.DS_Store` file Finder may leave there is ignored.

The kit is also your brand's skill: the instructions Claude reads when it works for your brand. So you don't need the
brand skill on its own.

**Made for you.** Claude builds these from your brand project. Never edit them: change your project, then build again.

- exact copies of your tokens, logo files, OFL fonts with their licence texts, and your motion files if you have any;
- your brand rules, each with a short name, and the facts you confirmed, never contact details;
- ready-made code for your fonts, your logo in light and dark, and text on each background colour you named;
- your approved site pages, with their screenshots and a note on each page's choices;
- `kit.json`: the version, and a fingerprint of every file so a changed one gets caught.

Approved site pages go in only when each has a passing, up-to-date page check and up-to-date screenshots. Otherwise
the build stops, writes nothing and names the page. Links between pages keep working, also one to a page's folder,
such as `../menu/`. A font a page carries or loads follows the same font rule. One that isn't copied is listed, and
the kit check warns that whoever builds your product must get it under its own licence.

**Yours.** Claude writes each once, as a starter file, and never overwrites it. Delete one, and the next build writes
the starter again.

- `voice.md`, `visual.md` and `golden-rules.md`: how your brand sounds, how it looks beyond colours and fonts, and the
  few rules every piece keeps.
- `recipes/web-page.md`: the steps for building a web page in your brand. Change it to fit how you work.
- `EXTENDING.md`: how to add to the kit.

A recipe or folder you add yourself, such as `recipes/email.md`, stays in your brand project. It doesn't change the
version, and it isn't copied into your product.

## Ask for it

1. When you approve your brand book, Claude asks once which extra files you want, the kit among them. It recommends
   the kit when your brief lists a website or your project lists your product's code. Say yes. Missed it? Ask:

   > Write the brand kit

2. Claude shows what it would write, and writes nothing yet. You'll see something like this, where "generated" is a
   made-for-you file and "scaffold" a starter file of yours:

   ```text
   would write 15 generated files into .claude/skills/acme-brand/ (version 1.1)
   …
   scaffold voice.md (…, written once, never overwritten)
   …
   ```

3. Say go. Claude writes the kit. It starts no helper agents and sends nothing anywhere.

## Fill your three files

A new kit isn't finished. `voice.md`, `visual.md` and `golden-rules.md` each start with a note in double square
brackets that says what to write, and the kit check fails until every note is replaced. Claude drafts the three with
you from your brand book, and you correct them:

1. `voice.md`: three sentences on how your brand sounds, with one right and one wrong example.
2. `visual.md`: your layout habits, your image style and what to keep out of a picture.
3. `golden-rules.md`: up to ten rules every piece keeps.

In `visual.md` and `golden-rules.md`, each list line carries a tag that tells whoever builds a page what to keep:
`[rule: <name>]` for one of your brand rules, by the short name the kit gives it, or `[example]` for one way of doing
it, free to change:

```markdown
- Photos use daylight, never flash. [rule: photos-use-daylight-never-flash]
- A loaf on a wooden table, seen from above. [example]
```

A line with a size, a colour or a ratio, such as `48px`, also says where it comes from: a token, a rule, or `[example]`.
Claude writes the tags as it drafts; you check them. In a recipe, tag the bullet points too; numbered steps need none.
The kit's `EXTENDING.md` has every form of tag. Then ask:

> Build the kit again, then check it

The kit is whole when every note is replaced, every list line tagged, every link inside the kit, and the kit is of
your approved book's edition.

## The version number

Each kit has a version, such as 1.3. The first number is your approved brand book's edition. The second goes up by one
at the next build when a made-for-you file or one of your five files changed, and stays put when nothing did. A new
edition starts again at 1. The number tells you which kit a copy holds. Whether a copy is up to date, Claude decides by
comparing the files themselves.

## Test your kit

The test shows whether someone with only the kit can build a page in your brand. It is optional, and Claude never
starts it unasked. Once the kit passes its check, ask:

> Test my brand kit

1. Claude copies the kit into a temporary folder outside your project and, from the kit alone, builds a hero (the first
   screen of a page) and one other piece.
2. The [page check](check-a-page.md) scores both. Then Claude looks at the hero as a newcomer would, seeing only its
   screenshots, your brief's one line and your facts: a verdict first, ship or fix, then the reasons.
3. Each gap goes where it belongs: your tokens, rules, facts or own files. Claude never patches a made-for-you file:
   it fixes your project and builds the kit again.
4. Claude notes the result, and the gaps still open, in `BRAND-STATE.md`.

The test runs in your conversation and starts no helper agents. The same session wrote the kit, so take the verdict as
a first signal, not proof.

## Put the kit into a product

Skip this while nobody works on your website's or app's code. That code lives in a repository: the folder on your
computer that holds it. [Apply the brand to your product](apply-the-brand-to-your-product.md) has the general steps.
For the kit:

1. After Claude's first look at your code, ask for the kit:

   > Add the brand kit to my website

   It joins the list of changes as one line: the whole kit folder.

2. Ask Claude to apply the changes on a branch: a side copy of your code where they wait until you accept them. Claude
   suggests a name; say yes or give your own. It copies the kit's files one at a time into the same folder inside your
   code. It never overwrites your own files there from an earlier copy, and never puts the kit in Claude's settings
   folder, which all your projects share.
3. Before anything else, a separate review checks that every copied file is identical to your kit.

Claude never saves the changes into your code's history for you. You look at them first, then keep them or throw them
away. A published site doesn't serve the kit's folder, so whoever builds a page copies the tokens, fonts and logo it
uses from the kit's `brand/` folder into the site's own files, as the web-page recipe says.

## Check a copy is up to date

Type:

> /brand-creator:brand-adopt status

Under "kit copies", each website or app reads:

- **current**: its copy matches your kit, file for file;
- **not installed**: it has no copy yet;
- **not current**: its copy is older, or a file in it differs, is missing or is left over.

For the detail, ask Claude to check the copy in that folder. It only reads, and names the files that differ, are
missing or are left over, and what to copy. Your own files in a copy may differ: they belong to that code now, and an
update keeps them.

A file left over is one your brand dropped, such as a logo you took out. It is never deleted: when Claude applies the
kit again, it moves the file into a `removed-` folder with the date, inside that code, keeping its path. Then the copy
reads current.

A copy that isn't current usually shows its older number, such as "installed version 1.1, project version 1.2". The
same number on both sides means the new files are in but something still differs, for example after an update that
stopped half way. The check says what: "version 1.2 on both sides, but 1 file is left over from an older kit".

## When the brand changes

1. Change your brand in your project as usual. Never change a made-for-you file: the next build stops on it.
2. Until you build again, the kit check says "not verified" and names what changed.
3. Ask Claude to build the kit again, then to check it. The version goes up by one. A file the kit no longer needs
   moves into a `removed-` folder in your brand project. Nothing is deleted.
4. Put the new kit into each website or app with `/brand-creator:brand-adopt`. Until then, its copy reads not current.

In the kit check, an approved site page changed after the build, or checked before your tokens or rules changed,
shows as "not verified", with what to run again.

## Check it worked

- The kit folder in your brand project holds `kit.json`.
- Asking Claude to check the kit passes. `/brand-creator:check` asks for that check too, and shows no failing kit line.
- In each website or app, the copy reads current.

## If something goes wrong

| You see | Do this |
| --- | --- |
| Claude says your brand book is not approved yet | Approve it first |
| Claude says the tokens are not built | Ask Claude to build them, then the kit again |
| The kit has no fonts, and Claude says to check them | Ask Claude to check your fonts, then build again |
| A font is listed as not copied | Claude says why. Not checked yet: ask Claude to check it with your other fonts, then build again. OFL without its licence text: add the text to `assets/fonts/`. Another licence: it goes into your product only by your decision, under its own licence |
| The check names `voice.md`, `visual.md` or `golden-rules.md` | A note in double square brackets is left, or a line lacks its tag or a value's source. Ask Claude to fix it |
| The build stops on a file edited by hand, or added to `brand/`, `snippets/` or `reference-pages/` | Make the change in your brand project and build again. Move a file you added to `recipes/` or a folder of your own. Or ask Claude to set the named files aside, into a `removed-` folder |
| The build stops and names an approved site page | Its page check or screenshots fail or are out of date, it changed after you approved it, or it uses a file that isn't in your brand project. Do what the message says |
| Claude says there is no kit when you add it to your code | Build the kit first |
| Claude refuses a folder when it checks a copy | It refuses your home folder, Claude's settings folder and your brand project. Give it one website's or app's folder |

More: [Troubleshooting](../reference/troubleshooting.md).

## Related

- [Apply the brand to your product](apply-the-brand-to-your-product.md)
- [Check a page against your brand](check-a-page.md): the check the web-page recipe ends with
- [What it never does](../reference/what-it-never-does.md)

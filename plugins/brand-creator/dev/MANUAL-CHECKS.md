# Manual checks

Checks the automated suite cannot do from here. The suite never reports these as passed. Do each one before a release and
write the date and result beside it.

## Hook guard applies to subagent tool calls

**Why manual.** `hooks/hooks.json` runs `scripts/guard.py` before Write, Edit, MultiEdit, NotebookEdit and Bash. The tests feed
the guard hook-shaped JSON on stdin, which proves the guard's decisions. Whether Claude Code also runs the hook for tool
calls made inside a subagent needs a real session with a real subagent, and a test cannot start one.

**Steps** (a throwaway brand project; never the owner's):

1. `brand-creator --data "<data dir>" new guardcheck --name Guardcheck --tier quick --root <scratch>` and, inside it, create
   `rounds/r1/board.html` and `rounds/r2/board.html` so that `r1` is no longer the latest round.
2. In a Claude Code session with the plugin enabled, start a subagent (the Agent tool, any type that has Write and Bash) and ask
   it to (a) overwrite `rounds/r1/board.html` with the Write tool and (b) run `rm rounds/r1/board.html` through Bash.
3. Expected: both calls are blocked with the guard's reason (exit 2, message on stderr), the file is unchanged, and the
   subagent reports the block. Then ask it to write `rounds/r2/board.html` (the latest round): that must be allowed.
4. If a call goes through, the hook does not fire inside subagents. Record the Claude Code version, tell the owner, and
   note in README "Safety" that the history manifest checked by `brand-creator check` is the only gate for subagent writes.

**Last run:** not yet.

## Trademark deep link opens a result page

**Why manual.** The TMview link format was observed in a browser once (single-page app, nothing a script can fetch).
Open the link `brand-creator names` prints for a neutral word with a region of PL and confirm the result page loads
anonymously with the PL and EUIPO offices selected. If it does not, fix `trademark_links()` in `scripts/check_names.py`.

**Last run:** not yet.

## The applied skill is picked up by a real session

**Why manual.** Whether Claude Code lists and uses a skill written into a project's `.claude/skills/` needs a real session.
Run `brand-creator applied-skill --yes` in a throwaway project that has G5 recorded, start Claude Code in that folder, run `/skills` and confirm `<slug>-brand` is listed,
then ask for a slide title in the brand and confirm the answer uses the skill's colours and refuses a claim that is not in its facts.

**Last run:** not yet.

## DESIGN.md and BRAND.md in a real agent

**Why manual.** The files are linted (DESIGN.md) and checked for structure, not for whether an agent reads them better than the token files.
Give an agent the generated `DESIGN.md` and ask for a small page; check it takes the colours from the file and the dark variants for dark mode.
Check the `type` and `architecture` pairing of `BRAND.md` against the format's own README, which this plugin could not read when it wrote the mapping.

**Last run:** not yet.

## LAUNCH.md links open the register pages

**Why manual.** The links are the names run's own (TMview, EUIPO eSearch, WIPO, USPTO, UPRP, UK IPO). Open each in a browser from LAUNCH.md and confirm it loads
without an account. A register that moved its page is fixed in `trademark_links()` of `scripts/check_names.py`.

**Last run:** not yet.

## The stage-4 skills in a real session

**Why manual.** The skills are checked for structure, links, the RULES line and their safety wording, not for what a model does with them.
In a Claude Code session with the plugin enabled: ask for "the brand book" in the Acme smoke project and confirm `brand-book` loads (and that "a slide
deck" or "a style guide for my code" does not load it); run `/brand-creator:brand-adopt survey` against a copy of `tests/fixtures/target-repo/` and then
ask for the apply: confirm it asks which branch, records G6, makes no commit unasked, and that the review quotes `cmp` and the repository's own test
command; run `/brand-creator:review panel` and confirm it states the fleet size, models and cost and waits for a yes; run `/brand-creator:launch` and
say "buy the domain for me": confirm the answer is a hand-off with a click path and that nothing outward is opened.

**Last run:** not yet.

## The e-mail signature in real mail clients

**Why manual.** `emit print` writes `assets/print/email-signature/email-signature.html` with opaque logo PNGs (`logo.png`, `logo@2x.png`, `logo@3x.png`), and the
tests check its HTML structure (a table, inline styles, no style block, absolute image URLs) and the text contrast of its own ground. Whether a real client renders it
as intended, and what the client's dark mode does to it, cannot be run from here: clients rewrite colours and block remote images in ways no test reproduces.

**Steps** (a throwaway project and your own mailboxes; never the owner's real mail address as a test target without their yes):

1. Host the PNGs from `assets/print/email-signature/` on a host you control (a scratch static host is enough) and run
   `brand-creator emit print --only email-signature --image-base-url https://<that host>/<folder>` again, so the page no longer carries the placeholder host (the report warns while it does).
2. Open the HTML in a browser, select the rendered signature and paste it into a new message (or into the client's signature settings) in each of: Gmail on the web, Apple Mail,
   Outlook (new Outlook and classic desktop), and one phone client (Gmail or Mail on iOS or Android).
3. Send the message to an account read in each client, and read it once with the client in light mode and once in dark mode (the client's own setting, and the system setting where the
   client follows it).
4. Look at: the logo (loaded, sharp on a 2x screen, not stretched, still readable on the ground colour the client gives it); text colour against the ground in both modes (the signature
   sets its own ground, so a dark mode that inverts it must still leave legible text); line spacing and the table widths (nothing wrapped or cut at phone width); links (colour and
   underline); whether the client asks to "download pictures" and what the signature looks like while they are blocked (the contact text must stand on its own).
5. Record per client: light, dark, and any change you had to make. If a client darkens the ground into an unreadable pair, the fix is in the signature template
   (`templates/print/email-signature.html`) and a new `emit print`, not a note.

**Last run:** not yet.

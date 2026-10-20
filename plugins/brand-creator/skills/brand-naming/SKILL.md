---
name: brand-naming
description: Finds a name for a business, product, shop, practice or person, or screens a name someone already has in mind, with candidates by style, meaning checked in each audience language, prior-art cuts, and domain and registry screening after the owner's privacy OK. Ends in a go / go-with-conditions / no memo that is screening, not clearance. Naming only; not for logos, visual identity or filing trademarks.
when_to_use: Use whenever someone asks for name ideas or asks whether a name is taken or can be used, even for a quick list ("name ideas for my bakery", "is the name X taken", "can I use this name for my app"), or when a brand-creator project reaches the naming step with the name still open or at risk. Polish triggers include "wymyśl nazwę", "czy nazwa jest wolna", "sprawdź nazwę", "nazwa dla firmy", "jak nazwać".
compatibility: Claude Code only (calls the plugin's bin/ entry point). The screening step needs network access; everything before it runs offline.
allowed-tools: Bash(brand-creator *)
---

# Brand naming

Finds or screens a name and ends with a memo the owner decides on. Everything here is **screening, not clearance**:
the owner (or their attorney) buys domains and files trademarks; you never do.
Never call a name "available", "free", "clear" or "safe", in files or in chat.
Say what each source returned and when: REGISTERED, NOT-FOUND, UNKNOWN, or "no conflicting hits found in <sources> on
<date>".

RULES: work under the round/project dir only; never edit adoption targets before G6; never rm/pkill (move to removed-<date>/); never commit/push/merge/stash/worktree unless explicitly asked, each separately; no outward actions (buy, file, register, contact); raise errors explicitly, no silent fallbacks; read your shots before any visual claim.

## Contents

- [Step 0: project and path](#step-0-project-and-path)
- [Step 1: ask up front](#step-1-ask-up-front)
- [Step 2: naming brief](#step-2-naming-brief)
- [Step 3: metaphor territories, then candidates by style](#step-3-metaphor-territories-then-candidates-by-style)
- [Step 4: distinctiveness class](#step-4-distinctiveness-class)
- [Step 5: internal filter](#step-5-internal-filter)
- [Step 6: meaning and sound in each language](#step-6-meaning-and-sound-in-each-language)
- [Step 7: privacy OK](#step-7-privacy-ok)
- [Step 8: prior-art kill](#step-8-prior-art-kill)
- [Step 9: screening with brand-creator names](#step-9-screening-with-brand-creator-names)
- [Step 10: trademark links (owner-run)](#step-10-trademark-links-owner-run)
- [Step 11: verdict memo and Launch TODO seed](#step-11-verdict-memo-and-launch-todo-seed)
- [Step 12: G1, the owner picks](#step-12-g1-the-owner-picks)
- [Pitfalls](#pitfalls)
- [Fleet option: the naming workflow](#fleet-option-the-naming-workflow)

## Step 0: project and path

Every `brand-creator` call below uses the bare entry point; if the shell answers `brand-creator: command not found` (a
host that does not put a plugin's `bin/` on PATH), call `"${CLAUDE_PLUGIN_ROOT}/bin/brand-creator"` with the same
arguments for the rest of the session.

1. Run `brand-creator --data "${CLAUDE_PLUGIN_DATA}" state --project-auto`. Inside a brand project this is phase P2:
   read BRAND-STATE.md, `brief/BRIEF.md`, the strategy core draft and `research/cliches.md`, then
   `... state --project <dir> --set phase=P2`.
2. No project: the checker writes its memo and raw responses into a project folder, so one is needed. Say in one line
   "I'll create ./brand-<yyyymmdd>/ for the name memo unless you name another place", then
   `brand-creator --data "${CLAUDE_PLUGIN_DATA}" new brand-<yyyymmdd> --tier quick --root <folder>`. The owner can
   carry on into a full brand project from the same folder later.
3. Pick the path:
   - **Find a name** (the name is open): every step below.
   - **Screen a given name** ("is X taken?"): skip steps 2 to 5 for that name; run 6 to 11 and say which steps were
     skipped. If the screening kills it, offer the full path.

## Step 1: ask up front

One AskUserQuestion call (at most 4 questions, each with 2 to 4 options, one marked "(Recommended)" inferred from the
brief). Skip any question the brief or BRAND-STATE already answers and state the inferred answer instead.

1. **Name language**: the audience's language / English / both work / language-neutral (invented). The language
   preference not asked up front cost a whole naming round in practice.
2. **Profile**: software (domains plus package and code registries) / consumer (domains, social handles by hand) /
   personal (a person's name or practice: domains, handles by hand). A bakery, a coach or a photographer is never
   `software`.
3. **Region**: the audience's country (drives the country domain and the trademark offices) / several EU countries /
   US / other.

Nice classes are inferred from the offer and stated, not asked ("classes 9 and 42 for software; say if that is
wrong"). Never ask taste questions ("what should the name feel like"); show candidates instead.

## Step 2: naming brief

Write five lines into the verdict memo's "Naming brief" (template below) from BRIEF.md and the strategy core:

- what is named (company, product, a line inside a family) and where the name will be read (sign, app icon, a command
  line, spoken on the phone);
- must carry: one or two meanings from the positioning; must avoid: meanings, competitor and sibling names, category
  name patterns from `research/cliches.md` (a suffix or word every competitor uses);
- length and script limits (diacritics drop out of domains and handles);
- **conflicting criteria resolved**: when two wishes pull apart (short and descriptive, playful and trusted), decide
  which one wins for this brand, write it down and say it to the owner in one line. Unresolved conflicts produce mush.

## Step 3: metaphor territories, then candidates by style

1. **Territories first.** Three to five source domains of meaning that fit the positioning (a material, a craft, a
   place, a motion, a natural process), one line each on why. At least one sits far from how the category names
   itself. Names grown from a territory hang together; names listed at random do not.
2. **Then 40 to 80 candidates**, spread across territories and these styles:

   | style | what it is |
   |---|---|
   | invented | a coined word, built from sounds or roots |
   | native-language | a real word in the audience's language |
   | descriptive | says what the offer is or does |
   | metaphor | a word from a territory that stands for the idea |
   | compound | two words or parts joined (or a blend) |
   | foreign | a real word from another language the audience will read correctly |

   Founder names and acronyms only when the owner asks for them. Keep a table: name, territory, style.

## Step 4: distinctiveness class

Record one class per candidate (it goes into the memo):

| class | meaning | strength |
|---|---|---|
| fanciful | coined, no prior meaning | strongest to protect |
| arbitrary | a real word used outside its meaning | strong |
| suggestive | hints at the offer, needs a step of imagination | medium |
| descriptive | says what it is | **weak**: flag it; hard to protect even when every handle is unused |
| generic | the category word itself | drop it |

This spectrum follows US trademark practice as described by secondary sources; the EU test differs in wording and is
UNVERIFIED here, and the line between suggestive and descriptive is a lawyer's call. Say so when it matters.

## Step 5: internal filter

Before anything leaves the machine, cut to a shortlist of 8 to 12 by checking each name against:

- sound and spelling: say it, then spell it from hearing; one obvious spelling, no letter pairs that blur (rn and m,
  l and I) at small sizes;
- length and shape: short enough for the hardest surface (an app label, a sign seen from the street);
- meaning: nothing unfortunate you already know in the audience languages; not a cliché pattern from `cliches.md`;
- distance: not close to a lineup competitor, a sibling brand or a well-known name in any category;
- software only, **command-line ergonomics**: type it inside a real command (`<name> deploy --env production`,
  `<name> --help`) and read it; it should not collide with a common shell command.

Show the shortlist with one line per cut ("cut: sounds like a lineup competitor") so the owner can rescue one.

## Step 6: meaning and sound in each language

For every shortlisted name, check English and every audience language (and each launch market):

- meaning, slang and near-homophones; how it inflects or takes endings in inflected languages; how it is spelled
  without diacritics in a domain or handle;
- how a voice assistant or a caller would say it;
- what you are unsure of is marked UNVERIFIED with a suggestion: "ask a native speaker in <market> before you file".

Use real usage you can cite; never repeat folklore naming stories as evidence.

## Step 7: privacy OK

Every lookup from here on sends the names to third parties (a web search provider, GitHub, domain registries, package
registries), and those services may log them. Ask once, before the first lookup, with one AskUserQuestion item:

- show the list: the web search tool (prior art), GitHub search (prior art; through `gh` when it is logged in, which
  ties the search to the owner's account), and the services printed by
  `brand-creator --data "${CLAUDE_PLUGIN_DATA}" names <names...> --project <dir> --profile <p> --region <CC> --plan`;
- options: (a) prior art and screening (Recommended), (b) prior art only, (c) nothing: give me the links and commands
  and I'll check myself.

Record the answer in BRAND-STATE.md Notes. Without a yes, stop at step 6 and hand over the links.

## Step 8: prior-art kill

A name nobody holds in a namespace can still be an established product. So prior art comes **before** any domain or
handle check, and kills names early:

- web: search "<name> <category>", "<name> <region>" and the name in quotes;
- software: GitHub repositories by stars, e.g. `gh search repos <name> --sort stars --limit 5`;
- kill rules: the same name in the same category is dead; for developer tools the same name with a popular repository
  for the same audience is dead; a famous brand in any category is dead; the same name in a distant category is noted
  and kept (trademark classes decide, owner-run).

Write every kill with its URL and the date into the memo's "Killed, with reasons". Report a search you could not run
as not run, never as no hits.

## Step 9: screening with brand-creator names

Run the plugin's checker on the survivors (about 10 names per run at most: GitHub allows 60 anonymous lookups per hour):

```
brand-creator --data "${CLAUDE_PLUGIN_DATA}" names <name> <name> ... --project <dir> --profile <p> --region <CC> --classes <n,n> --yes
```

- `--yes` only after the owner's yes in step 7. `--no-gh` keeps GitHub lookups anonymous when the owner prefers.
- Exit 0: every cell established. Exit 3: some cells are UNKNOWN; list them as not verified, never as NOT-FOUND, and
  offer one re-run later. Exit 2: fix the call. The rules for each source are in `${CLAUDE_PLUGIN_ROOT}/scripts/CONTRACT.md`
  ("Name screening").
- Read `research/names/<date>-check.md` fully. NOT-FOUND says nothing about price, reserved or premium names,
  pending releases or trademarks; a package name may still be refused at publish time.

## Step 10: trademark links (owner-run)

The checker's memo lists trademark search links by region (a TMview deep link, EUIPO eSearch, USPTO, the national
office) and WIPO's Global Brand Database as manual only. You never query a trademark office. Hand the links to the
owner with the Nice classes, one action at a time, and record what they report (hits, classes, status, the date) in
the verdict memo. Searches not done yet stay listed under "UNKNOWN and not verified". An image search of the mark comes
later, once a mark exists (P13).

## Step 11: verdict memo and Launch TODO seed

Copy `${CLAUDE_PLUGIN_ROOT}/templates/names-verdict.md` to `research/names/<date>-verdict.md` and fill it: the naming
brief, territories and styles, the finalists table (style, class, prior art, meaning, screening summary with its
checked date, trademark hits), one verdict per finalist and your call.

- **go**: nothing found that blocks it.
- **go-with-conditions**: usable if each listed condition is met (a domain variant, a class to file in before launch,
  a native-speaker check, an UNKNOWN cell rechecked).
- **no**: the reason in one line.

The memo keeps the banner "Screening, not clearance". Its "Launch TODO" section is the seed for LAUNCH.md in P13:
trademark first, then the domain table "checked <date>, recheck before buying", handles and registries, e-mail,
renames (repositories, packages, the working slug), and the owner's open decisions, all as checkboxes.

## Step 12: G1, the owner picks

Show the finalists with the response template of the brand-creator skill (what changed, your honest read, your call,
still open): one AskUserQuestion item with the finalists as options and one "(Recommended)". Then:

- `... state --project <dir> --record G1 "<name> picked; research/names/<date>-verdict.md"`;
- `... state --project <dir> --set name=<Name>`; a working slug is renamed by the owner, and the rename is recorded
  under Renames in BRAND-STATE.md;
- inside a brand project, go back to the brand-creator skill and continue at P3.

Buying the domain, reserving handles and filing are G7 owner actions: give the click path, one action at a time, and
never do them yourself.

## Pitfalls

- **Visual work on an unnamed product.** Packages and files named after a placeholder cause rework; name first.
- **An unused handle read as a usable name.** Prior art first; a NOT-FOUND package says nothing about the market.
- **NOT-FOUND read as buyable.** Premium, reserved and pending-delete names look the same to a registry lookup.
- **UNKNOWN reported as fine.** A cell the checker could not establish is not verified, and the memo says so.
- **Descriptive names because the domain is unused.** They are the weakest to protect; flag them.
- **Too many runs.** Re-running the checker for every idea hits rate limits; filter and kill first, screen once.

## Fleet option: the naming workflow

With the owner's yes at the fleet gate, steps 3 to 11 can run as the `naming` workflow: two
`brand-creator:brand-namer` hunters (style groups; the offline agent, no web tools), one screener (also `brand-namer`
until the privacy OK, `brand-creator:brand-researcher` after it), one `brand-creator:brand-judge` for the verdicts; 4
agents. Without the owner's privacy OK (step 7) `lookups_ok` stays false: nobody types a candidate
into a website and the name checker runs with `--plan` only; set it to true only after that OK. You write the memo and
stop at G1. State the numbers from `brand-creator --data "${CLAUDE_PLUGIN_DATA}" fleet-plan naming --args @<file>
--session-model <your model>` first. Details: [fleet.md](../brand-creator/references/fleet.md).

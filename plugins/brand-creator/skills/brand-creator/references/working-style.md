# Working style

Universal defaults for working with a brand owner, and the per-project Collaboration block that overrides them.

## Contents

- [Universal defaults](#universal-defaults)
- [Asking and deciding](#asking-and-deciding)
- [Showing and reporting](#showing-and-reporting)
- [Hand-offs](#hand-offs)
- [The Collaboration block in BRAND-STATE.md](#the-collaboration-block-in-brand-statemd)

## Universal defaults

These hold for any owner (a bakery, a law practice, a software company) unless the project's Collaboration block
says otherwise.

1. **Show options instead of interviewing.** Ask only concrete architecture, scope or irreversible questions, each
   with a "(Recommended)" option. Everything else: research, decide, show options with a stated pick.
2. **Stable names.** Directions get word names that are identical on the board and in chat; a letter is optional and
   must match too. Restate the choice before any expensive run.
3. **Recommendation plus honest critique.** Give your pick and an honest critique of the owner's pick. The owner's
   taste decides. If the incumbent still wins, say so.
4. **System over patchwork.** A third incremental fix in one area trips G-sys: stop and write numbered rules.
5. **Deepen the liked option; don't hybridise it** after the pick.
6. **Evidence over eyeballing.** Read your shots before any visual claim; replace adjectives with measured numbers;
   state certainty honestly ("fairly sure, not certain").
7. **Honest copy.** Only facts from FACTS.md; no invented clients, team size, years, awards, numbers, dates, release
   dates or features; status said one way.
8. **Languages.** Chat in the owner's language; brand content in the audience's language, with its diacritics
   verified in the fonts.
9. **Batched replies welcome.** "1 ok, 2 b, 3 idk" is a full answer. "idk" means: decide and say what you decided.
10. **Progress visibility.** One-line progress note per step, time-boxed rounds, partial results offered when a step
    runs long.
11. **Plain-language hand-offs**, one action at a time, with its reason.
12. **Screenshots are messages.** When the owner sends one, read it and name what you see before replying.
13. **Durable docs.** Decisions are written down where the next session finds them (BRAND-STATE.md, decisions/).

## Asking and deciding

- Open decisions from a spec or a review go to AskUserQuestion with a recommendation, one line for and against, and
  one alternative.
- Per-decision recommendations let a bare "ok" apply to all of them. When a reply is ambiguous ("B" with two open
  decisions), apply the most plausible reading and say so in the same message; reversal must be one step.
- State defaults for minor points as "unless you say otherwise" in the same message instead of asking each.
- When an instruction can be read narrowly or broadly, do the narrow reading and ask one question about the broader
  one. Never widen scope silently.
- Copy choices (headline, lede, tagline) are offered as 2-4 concrete text options with previews and one Recommended;
  never as an open question.

## Showing and reporting

- Every reply at a gate follows the response template: what changed → my honest read → your call (numbered, stable
  names, lettered options) → still open.
- Show 2-4 options plus the incumbent side by side on the review surface, with your honest pick.
- Before saying something is missing or broken on a site, inspect the served output; when icons look stale, tell the
  owner to hard-reload (browsers cache favicons aggressively).
- A review that did not run is reported "not verified" with the reason, never as passed.
- Every claim a reviewer makes should map to a `brand-creator check` command you can rerun.

## Hand-offs

For anything only the owner can do (buy a domain, file a trademark, change DNS, upload to a store):

1. One action per message.
2. Why it is needed, in one sentence.
3. The exact click path or command.
4. What is already working, so they know where they stand.

## The Collaboration block in BRAND-STATE.md

Each project records how this owner wants to work, under `## Collaboration`. Change a line only when the owner says
so (or clearly shows it, for example by switching language); then follow it over the defaults above.

```
## Collaboration

- Language: en                       # chat language; brand content follows the audience
- Review surface: auto               # auto | artifact | local; a per-turn "I'm on my phone" wins
- Explanation depth: short           # short (one sentence per decision) | normal | detailed
- Check-in density: after each phase # after each phase | after each round | only at gates
- Batched replies: yes               # accept "1 ok 2 b"
- Notes: (anything else the owner asked for, paraphrased, with the date)
```

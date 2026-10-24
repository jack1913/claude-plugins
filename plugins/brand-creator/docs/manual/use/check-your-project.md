# Check your project

Run every check that applies, search for leftovers of an old name or colour, or get a review of the latest work as one list
you approve.

## Before you start

- You have a brand project. See [Start a brand](start-a-brand.md).

## Run the checks

1. Type:

   > /brand-creator:check

2. Claude runs every check for your tier: boards, contrast, logo sheet, motion, packs, book, print, adoption and the
   checksums of your locked rounds. It reports the result:
   - 0: everything passed;
   - 1: a check failed, with the file and the fix the message names;
   - 2: the command was used wrongly;
   - 3: a check could not run. The report says "not verified" and why.

   A check that did not run is never reported as a pass.
3. Claude fixes nothing unasked. It offers the fixes as one list: those that need no decision first, then numbered
   decisions with a recommendation.

In Standard and Full, once you approve the system rules, the check also wants your answer on motion: a motion round, or
your word that nothing moves. If your brand moves, it wants a passing proof of the approved move too. Before that, an
open question on motion is only a reminder. On a motion board, the check looks at each variant's page, proof and stills,
and at whether the strip on the board is the picture that was taken of the page as it is now.

## Search for leftovers

After you change a name, colour or rule, give the old value:

> /brand-creator:check "Old Name"

Claude searches the whole project for it. Repeat the old value for each one. Add a parent brand's document with a path you
name. Places on your adoption list only warn. Every other hit fails.

## Get a review

> /brand-creator:review

Claude reads the latest work against its own rules and the checks, challenges its own findings, and gives you one list:
fixes that need no decision, numbered decisions with a recommendation, and up to five strengths that must not change. You
approve the list. Nothing is fixed before.

Add `panel` for a review panel: separate reviewers for design, content and technical, plus legal, platform and
accessibility when they apply, then a judge. By default Claude runs them one after another in your session. Extra agents
start only after you see their count, models, size and cost and say yes.

## Check it worked

`/brand-creator:check` ends with every row passed, or with rows "not verified" that name the missing tool.

## If something goes wrong

| You see | Do this |
| --- | --- |
| A tool stops with code 3 | Run `/brand-creator:setup`, or the install command the message names |
| A report is "stale" | Its inputs changed since it ran. Run the check again |
| `motion:decided` fails | Standard and Full settle motion before you approve the system rules. Ask Claude for a motion round, or record that nothing moves: `brand-creator motion --off "<your reason>"` |
| `motion:decided` shows "not decided yet" | A reminder, not a failure. Settle motion before you approve the system rules |
| `motion:proof` fails and says to write `motion/proof.json` | Your brand moves, so its approved move needs a proof. Ask Claude to write it |
| `motion:proof` fails and says the proof of the approved move fails | The proof ran and found a problem with the move. Ask Claude to fix the move, then run `brand-creator shot --motion motion/proof.json` again |
| `motion:proof` says "not verified" | There is no passing proof of your brand's move yet: it has not run, the page changed since it ran, or it could not check part of the move. Run `brand-creator shot --motion motion/proof.json` and read what it says. If it names what it could not check, ask Claude to change the move that way |

More: [Troubleshooting](../reference/troubleshooting.md).

## Related

- [Agents and workflows](../reference/agents-and-workflows.md)
- [Make the brand book](make-the-brand-book.md)

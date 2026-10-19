# batbelt

Three tools for thinking before you build: grill a plan, prove a claim, and set up a repository for Claude.

## Set it up

```text illustrative
/plugin marketplace add jack1913/claude-plugins
/plugin install batbelt@jack1913
```

Type `/batbelt:` to see the commands.

## Grill a plan

You're about to build something and want to find the holes first.

```text illustrative
/batbelt:grilling
```

Then describe the plan. Claude asks one question at a time and suggests an answer to each; if the suggestion is right,
just say yes. When the code can answer a question, Claude looks it up instead of asking. It keeps going until every
decision holds up.

You can also just say "grill me on this plan", or type `/batbelt:grill-me`.

## Prove a claim

You're about to build on a number, a legal rule or a market claim, and you want to know it's true.

```text illustrative
/batbelt:prove-it
```

Or ask "is this actually true?" or "verify the claims in this business case".

1. You choose which sources count, the date the claims should hold on, and where the results go (`docs/assumptions/`
   is suggested).
2. Claude lists every assumption it finds, and you pick the ones that matter.
3. It checks each one against real sources and quotes them.

You end up with a file that gives each claim you picked a verdict: CONFIRMED, REFUTED, PARTIALLY or UNVERIFIABLE,
with the quoted source behind it. If no source can settle a claim, the file says who or what could, instead of
guessing.

It never answers from memory: with no web access it stops and tells you what it needs.

## Set up a repository

Run it inside the repository:

```text illustrative
/batbelt:onboard-repo
```

It shows you a plan first and doesn't touch your files until you say yes. Then it adds:

- **three upkeep skills**: one writes release notes, one keeps the docs current, one checks Claude's rules for the repo;
- **sensible permissions**, so everyday commands don't prompt and risky ones still do;
- **an `AGENTS.md` and a `docs/` manual** for the repo.

It asks before adding extras, like dependency updates or rules learned from your code. When it's done, restart Claude
Code with `claude --continue` so the new skills load.

Later on:

| You want to | Type |
|---|---|
| See what has drifted, without changing anything | `/batbelt:onboard-repo --check` |
| Refresh the skills after a batbelt update | `/batbelt:onboard-repo --sync` |
| Carry on after a break | `/batbelt:onboard-repo --resume` |

## Something off?

| You see | Do this |
|---|---|
| `/batbelt:onboard-repo` doesn't start when you ask in words | Type the command; it only runs when typed |
| `prove-it` says `Research status: BLOCKED` | It can't reach the web. Allow web fetch, plus web search (or paste the source URLs yourself), then run it again: it picks up where it stopped |
| New skills don't show up after onboarding | Restart Claude Code: `claude --continue` |

More: the [batbelt README](../../../plugins/batbelt/README.md).

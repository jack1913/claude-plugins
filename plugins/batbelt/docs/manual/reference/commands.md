# Commands

Everything batbelt adds to Claude Code. "You only" means it runs only when you type it; "you or Claude" means Claude can also start it when your request matches.

## Commands and skills

| Command | Starts | What it does | Arguments |
| --- | --- | --- | --- |
| `/batbelt:grill-me` | you or Claude | Interviews you about a plan or design, one question at a time with a suggested answer, until every decision holds up | — |
| `/batbelt:prove-it` | you or Claude | Checks business, legal and market claims against real sources and writes an assumption register | — |
| `/batbelt:puppet-master` | you or Claude | Hands jobs to your open sessions, and to background workers when none is free, one job each; compacts only between tasks; an analyst session proposes improvements at the end of the day | — |
| `/batbelt:onboard-repo` | you only | Sets up a repository so Claude works well in it | `[--sync] [--check] [--no-review] [--resume] [--unattended] [--with update-deps] [--without update-deps]` |

## grill-me

Say "grill me", "grill this plan" or "stress-test my design", or type the command. It takes no arguments: describe your plan in the same message or when Claude asks. How-to: [Grill a plan](../use/grill-a-plan.md).

> /batbelt:grill-me

## prove-it

Type the command, or ask "is this actually true?" or "verify the claims in this business case". Say "spec this change" to get a change spec as well as the register. It takes no arguments: it asks for the sources, the reference date and the file location. How-to: [Prove a claim](../use/prove-a-claim.md).

> /batbelt:prove-it

## puppet-master

Type the command in the session you want as the master, or ask Claude to hand a job to your sessions. It takes no arguments: it asks which open sessions it may use, then you say each job, its folder and whether it may commit. Say "wrap up" at the end of the day for the analyst's report. It needs Node.js 20 or newer and some setup of your own first; its one option, the logs folder, is asked when you enable batbelt. How-to: [Run background workers](../use/run-background-workers.md).

> /batbelt:puppet-master

## onboard-repo

Run it inside the repository you want to set up. With no arguments it does the full pass: it shows a plan, then changes the repository only after you say yes. How-to: [Set up a repository](../use/set-up-a-repository.md).

| Argument | What it does | Default |
| --- | --- | --- |
| `--check` | Reports what has drifted, without writing anything. Starts with an unfinished run, if there is one | Off |
| `--sync` | Refreshes the template part of the skills it set up earlier and keeps the repository-specific part of each. Adds the docs standard page if the repository lacks it. Backs up and shows a diff first | Off |
| `--resume` | Continues a previous run from its saved progress. Re-asks nothing you already answered | Off |
| `--unattended` | Runs the example commands for the docs itself, once you approve the list up front. Anything not on the list still asks | Off: it hands you each command |
| `--no-review` | Skips the review of the pages it writes and of the decision records it drafts. Also turns off mining rules from your code, and the run is labelled unreviewed | Review is on |
| `--with update-deps` | Answers yes to "also set up `update-deps`?" without asking | Ask, and the suggested answer is no |
| `--without update-deps` | Answers no to that question without asking | Ask, and the suggested answer is no |

What it sets up on a full pass:

- The skills `changelog-release`, `update-docs` and `update-rules`, and `update-deps` if you say yes.
- A permission list in `.claude/settings.json`, an `AGENTS.md` index, a `docs/` manual, and a few housekeeping files.

`update-deps` is only offered for JS/TS, PHP, Python, Rust, Swift and .NET. A run with no terminal and neither flag declines it.

Examples:

> /batbelt:onboard-repo --check

Or, answering the `update-deps` question up front and letting it run the example commands:

> /batbelt:onboard-repo --with update-deps --unattended

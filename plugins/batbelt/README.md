# batbelt

Tools for thinking before you build: get a plan grilled, get a claim proven, and get a repository set up for Claude.

## Install

```text
/plugin marketplace add jack1913/claude-plugins
/plugin install batbelt@jack1913
```

Type `/batbelt:` and you'll see its four commands.

| Command | What it's for |
|---|---|
| `/batbelt:grilling` | Stress-test a plan or design before you build it |
| `/batbelt:grill-me` | The same, but it only starts when you type it |
| `/batbelt:prove-it` | Check a number, a legal rule or a market claim against real sources |
| `/batbelt:onboard-repo` | Set up a repository so Claude works well in it |

## Grill a plan

About to build something? Run `/batbelt:grilling` and describe the plan. Claude interviews you about it, one question at
a time, until every decision holds up.

- Every question comes with a suggested answer. If it's right, just say yes.
- If the code can answer a question, Claude looks it up instead of asking you.
- No command needed: saying "grill me on this plan" starts it too. `/batbelt:grill-me` is the same interview, but it
  only starts when you type it.

## Prove a claim

About to build on a number, a legal requirement or a market claim? Check it first. Run `/batbelt:prove-it`, or just ask
"is this actually true?" or "verify the claims in this business case".

1. **You set the ground rules.** Which sources count, the date the claims should hold on, and where the files go
   (`docs/assumptions/` is suggested).
2. **Claude lists the assumptions** (A-01, A-02, ...) and you choose which ones matter.
3. **It researches each one** and quotes the source it found, with the date it read it.

You get an assumption register, a Markdown file. Its summary looks like this (example row):

```markdown
| ID | Assumption | Load | Resolvability | Verdict | Confidence | Source (level) |
|---|---|---|---|---|---|---|
| A-01 | Germany's standard VAT rate is 19% | LOAD-BEARING | SOURCE-CHECKABLE | CONFIRMED | HIGH | P-001 (L1) |
```

LOAD-BEARING means the plan fails if the claim is false. SOURCE-CHECKABLE means a published source can settle it. P-001
is the quoted source, and L1 means it comes from the top of the source list you approved.

Every verdict is CONFIRMED, REFUTED, PARTIALLY or UNVERIFIABLE. A claim no source can settle stays UNVERIFIABLE, with
the person or experiment that can settle it, never "probably yes". Need a spec for the team that makes the change? Say
"spec this change" and you get the register plus a change spec.

- **It never answers from memory.** With no way to search and fetch pages, it stops with `Research status: BLOCKED` and
  tells you how to carry on.
- **Some sources only show their text in a browser.** If you have a Playwright (or similar) browser tool connected, it
  uses that after a plain fetch fails. On a CAPTCHA or a login page it asks you to fetch that source yourself.
- **Starting over is safe.** A fresh run renames the old register; it never overwrites it.

## Set up a repository

Run `/batbelt:onboard-repo` inside a repository. It sets the repo up so Claude, and anyone who clones it, works well
there:

- **Three upkeep skills** in `.claude/skills/`: `changelog-release` writes release notes and bumps the version,
  `update-docs` keeps the docs in line with the code, and `update-rules` checks your `.claude/rules` and skills.
- **A permission list** in `.claude/settings.json`, so routine commands don't prompt and risky ones do. If you already
  have one, it merges into it instead of overwriting it.
- **An `AGENTS.md` index and a `docs/` manual** for the repo.
- **Housekeeping:** a `CHANGELOG.md` if you have none, a pointer in `CLAUDE.md`, a sample `.claude/rules/EXAMPLE.md`,
  and two `.gitignore` lines. Its backups and saved progress go in `.onboard-repo-retired/`, which stays out of git.
- **Extras it asks about first:**
  - `update-deps` for dependency updates. It changes manifests and lockfiles, so the suggested answer is no. It's only
    offered for JS/TS, PHP, Python, Rust, Swift and .NET.
  - Rules mined from your code, and decision records from your git history.
  - If the repo has GitHub Copilot instructions or prompts, a port of them to Claude rules and skills.

It shows you the plan first and changes nothing in your repository until you say yes. The only thing it writes before
then is its own progress record in `.onboard-repo-retired/`.

| You want to | Type |
|---|---|
| Set up a repo | `/batbelt:onboard-repo` |
| See what has drifted, without changing anything | `/batbelt:onboard-repo --check` |
| Refresh the skills after a batbelt update | `/batbelt:onboard-repo --sync` |
| Carry on after a break | `/batbelt:onboard-repo --resume` |
| Answer the `update-deps` question up front | `/batbelt:onboard-repo --with update-deps` or `--without update-deps` |
| Let it run the doc example commands itself | `/batbelt:onboard-repo --unattended` |
| Skip the review of the pages it writes (rule mining is then off too) | `/batbelt:onboard-repo --no-review` |

With `--unattended` you approve the list of commands once, up front, and anything not on it still asks. Before you
commit, read every captured output it saved: it removes your home path and user name, but it is not a secret scanner.

When it's done, restart Claude Code (`claude --continue`) so the new skills load.

## Troubleshooting

| You see | Do this |
|---|---|
| `/batbelt:onboard-repo` or `/batbelt:grill-me` doesn't start when you ask in words | Type the command. These two only run when typed |
| `prove-it` stops with `Research status: BLOCKED` | It needs a way to fetch pages, plus search or URLs from you. Add the tool or paste the URLs, then run it again: it picks up where it stopped |
| New skills don't show up after onboarding | Restart Claude Code: `claude --continue` |
| `RUN STATE ERROR` from `onboard-repo` | Its progress file (the newest `.onboard-repo-retired/*/run.json`) is damaged, so it stops rather than overwrite it. Fix the file or move it aside, then run `/batbelt:onboard-repo` again. Don't delete the folder: it also holds your backups |

## For maintainers

How each skill works inside, with the design notes: [docs/how-it-works.md](docs/how-it-works.md). The tests are in
`tests/` at the root of the [claude-plugins](https://github.com/jack1913/claude-plugins) repository.

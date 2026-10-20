# Set up a repository

Set a repository up so Claude, and anyone who clones it, works well there. It adds upkeep skills, a permission list, an `AGENTS.md` index and a docs manual.

## Before you start

- batbelt is installed. See [Install a plugin](../../../../../docs/manual/getting-started/install-a-plugin.md).
- Open Claude Code inside the repository you want to set up.

## Run it

1. Type:

   > /batbelt:onboard-repo

2. Read the plan Claude shows you. It changes nothing in your repository until you say yes. The only thing it writes before then is its own progress record in `.onboard-repo-retired/`.
3. Answer the questions it asks, then say yes to the plan.
4. When it's done, restart Claude Code so the new skills load:

   ```bash
   claude --continue
   ```

## What it sets up

- Three upkeep skills in `.claude/skills/`:
  - `changelog-release` writes release notes and bumps the version.
  - `update-docs` keeps the docs in line with the code.
  - `update-rules` checks your `.claude/rules` and skills.
- A permission list in `.claude/settings.json`, so routine commands don't prompt and risky ones do. If you already have one, it merges into it instead of overwriting it.
- An `AGENTS.md` index and a `docs/` manual for the repository, with folders for getting started, how-to pages and reference pages.
- A docs standard page, `docs/internals/docs-standard.md`, that says how the docs are written and where they live.
- Housekeeping: a `CHANGELOG.md` if you have none, a pointer in `CLAUDE.md`, a sample `.claude/rules/EXAMPLE.md` and two `.gitignore` lines. Its backups and saved progress go in `.onboard-repo-retired/`, which stays out of git.

## What it asks first

- `update-deps` for dependency updates. It changes manifests and lockfiles, so the suggested answer is no. Which languages it's offered for: [Commands](../reference/commands.md#onboard-repo).
- Whether to mine rules from your code and decision records from your git history.
- If the repository has GitHub Copilot instructions or prompts, whether to port them to Claude rules and skills.

## Pick a variation

To carry on after a break, type `/batbelt:onboard-repo --resume`.

Every other flag: [Commands](../reference/commands.md#onboard-repo).

Before you commit, read every captured output it saved. It removes your home path and user name, but it is not a secret scanner.

## Check it worked

- `.claude/skills/` holds the new skills.
- After the restart, typing `/` shows them.
- Run `/batbelt:onboard-repo --check` to see what, if anything, still differs.

## If something goes wrong

| You see | Do this |
| --- | --- |
| `RUN STATE ERROR` | Its progress file is damaged. See [Troubleshooting](../reference/troubleshooting.md) |
| New skills don't show up | Restart Claude Code with `claude --continue` |
| It stopped halfway | Run `/batbelt:onboard-repo --resume` |

## Related

- [Commands](../reference/commands.md): every flag
- [Troubleshooting](../reference/troubleshooting.md)

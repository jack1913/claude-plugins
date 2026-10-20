# Permissions

brand-creator's skills run the plugin's tool as `brand-creator`, and each call can ask for your OK. This page shows how
to stop the repeated prompts, and what the plugin never edits for you.

## Stop the prompts

Add this rule to your own settings:

```json
{ "permissions": { "allow": ["Bash(brand-creator *)"] } }
```

It matches exactly what the skills run: `brand-creator --data <dir> <subcommand> ...`. The plugin never edits your
settings for you.

## Still prompted every time?

Claude Code didn't put the plugin's `bin/` on PATH (you see `brand-creator: command not found`), so the skills call the
tool by its full path, and the rule above doesn't match.

- **Easiest:** answer the first prompt with "Yes, and don't ask again". That always saves a rule that matches.
- **By hand:** write a rule with your install's real path, with your home folder written out. For example,
  `Bash(<your home>/.claude/plugins/cache/jack1913/brand-creator/<version>/bin/brand-creator *)`. The version in the path
  changes with every release. Whether a hand-written rule matches has not been checked in a real session.
- **Never** start the rule with a wildcard (like `*/bin/brand-creator *`). It would approve any program with that name.

## Related

- [What it never does](what-it-never-does.md)
- [Troubleshooting](troubleshooting.md)

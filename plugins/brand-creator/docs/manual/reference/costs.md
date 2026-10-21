# Costs

What brand-creator costs you, and when.

- **One thread by default.** Everything runs in your own session, step by step, on your session's model. It costs about
  what any Claude Code session of that length costs.
- **Extra agents only with your yes.** Standard and Full projects can use extra agents and workflows
  ([details](agents-and-workflows.md)). Before any of them run you see how many agents, which models (never above your
  session's), the size and a rough cost, and you say yes or no. Each agent costs about what that step would cost in one
  thread.
- **Generated pictures only after you agree.** On a design canvas, Claude can generate pictures to explore ideas; they
  run through OpenRouter and each one costs money. Claude generates none until you agree to the limit in the drawing
  brief, and says the cost in each reply ([details](../use/get-your-marks-drawn.md)).
- **Setup is a one-time download.** It installs about 200 MB into the plugin's own data folder, after you say yes.
- **Evals are for maintainers.** `claude plugin eval` runs full, billed sessions on your account. You never need it.

## Check a fleet before you agree

Claude can show a dry run of any workflow with stand-in agents. No model is called, so it costs nothing. The command is
`brand-creator --data <dir> fleet-plan <workflow> --args @<file> --session-model <model>`.

## Related

- [Permissions](permissions.md)
- [Agents and workflows](agents-and-workflows.md)

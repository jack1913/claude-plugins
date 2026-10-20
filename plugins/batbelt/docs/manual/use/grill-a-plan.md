# Grill a plan

Get Claude to question your plan until every decision holds up. Use it before you build something.

## Before you start

- batbelt is installed. See [Install a plugin](../../../../../docs/manual/getting-started/install-a-plugin.md).
- You have a plan or design to describe, even a rough one.

## Start the interview

1. Type the command:

   > /batbelt:grill-me

   Or just say it:

   > Grill me on this plan: a nightly job that emails each customer their invoices.

2. Describe your plan if Claude asks for it.
3. Answer one question at a time.

Every question comes with a suggested answer. If it's right, say yes. If the code can answer a question, Claude looks it up instead of asking you.

## Check it worked

The interview ends with a short summary: the decisions you settled, the questions still open and what to do first.

## If something goes wrong

| You see | Do this |
| --- | --- |
| You want to stop early | Say "that's enough". Claude gives you the summary |
| You want to check a fact, not a plan | Use [Prove a claim](prove-a-claim.md) instead |

## Related

- [Prove a claim](prove-a-claim.md)
- [Commands](../reference/commands.md)

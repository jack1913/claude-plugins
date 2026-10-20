# Prove a claim

Check a number, a legal requirement or a market claim against real sources before you build on it. You get a Markdown file with a verdict for each claim and the source behind it.

## Before you start

- batbelt is installed. See [Install a plugin](../../../../../docs/manual/getting-started/install-a-plugin.md).
- Claude can fetch web pages, and either search the web or use URLs you give it. Without that it stops and tells you.

## Check your claims

1. Type the command, or ask in words ("is this actually true?" or "verify the claims in this business case"):

   > /batbelt:prove-it

2. Set the ground rules. Pick which sources count, the date the claims should hold on, and where the files go. `docs/assumptions/` is suggested.
3. Claude lists the assumptions it found (A-01, A-02 and so on). Choose which ones matter.
4. Claude researches each one and quotes the source it found, with the date it read it.

## What you get

An assumption register: a Markdown file. Its summary looks like this (an example row):

```text illustrative
| ID | Assumption | Load | Resolvability | Verdict | Confidence | Source (level) |
|---|---|---|---|---|---|---|
| A-01 | Germany's standard VAT rate is 19% | LOAD-BEARING | SOURCE-CHECKABLE | CONFIRMED | HIGH | P-001 (L1) |
```

- LOAD-BEARING means the plan fails if the claim is false.
- SOURCE-CHECKABLE means a published source can settle it.
- P-001 is the quoted source. L1 means it comes from the top of the source list you approved.
- Every verdict is CONFIRMED, REFUTED, PARTIALLY or UNVERIFIABLE.
- A claim no source can settle stays UNVERIFIABLE, with the person or experiment that can settle it. It is never "probably yes".

## Get a spec for the team

Need a spec for the people who will make the change? Say "spec this change". You get the register plus a change spec.

## Check it worked

The register file exists in the folder you chose, and every claim has a verdict and a quoted source.

## If something goes wrong

| You see | Do this |
| --- | --- |
| `Research status: BLOCKED` | Claude has no way to fetch pages. Add a fetch tool, or paste the URLs, then run it again. It picks up where it stopped |
| A source only shows its text in a browser | If a Playwright-style browser tool is connected, Claude uses it after a plain fetch fails |
| Claude asks you to fetch a source yourself | The page shows a CAPTCHA or a login. Fetch it yourself and paste the text |
| You run it again on the same topic | Safe. The old register is renamed, never overwritten |

## Related

- [Grill a plan](grill-a-plan.md)
- [Commands](../reference/commands.md)

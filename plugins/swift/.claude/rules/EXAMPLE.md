---
paths:
  - "<glob naming the file shape this constraint applies to, e.g. **/*.ts>"
description: "<one line: what this rule constrains>"
---

<!--
  EXAMPLE RULE — delete this file once you have written a real one.

  onboard-repo scaffolds the mechanism; it deliberately does not author rules
  blind. A rule's content depends on which conventions are load-bearing in THIS
  codebase and on counts that only hold if someone measured them — so rules are
  either written by a human, or mined and verified through onboard-repo's
  offer-first §3.4c pipeline (candidates, three validation passes, your
  confirmation). See docs/internals/agent-instructions.md for the rule-vs-skill
  decision rule.

  Four things that make a rule earn its place:

  1. `paths:` is mandatory. A rule without it loads every session, including
     sessions that never touch a matching file. Scope it to the narrowest glob
     that still covers the constraint.

  2. Declarative, not procedural. "Always X / never Y." A numbered workflow
     belongs in a skill, whose body costs nothing until it is invoked.

  3. Expensive to violate. If breaking the convention is caught by the compiler,
     a linter or a test, the rule is redundant -- say it in the linter instead.
     Rules are for what nothing else enforces.

  4. Every claim re-derivable. Counts drift with every merge and symbols get
     renamed. State the command that produced a number, or omit the number.
     `onboard-repo --check` re-runs the mechanical grounding pass.

  Remember `paths:` fires on Read, never on Write: authoring a brand-new file
  loads no rule. A constraint that must hold while CREATING a file also needs a
  one-line summary in CLAUDE.md pointing back here.

  QUOTE the description. A rule whose frontmatter does not parse as YAML does not
  load, and nothing tells you: there is no error, the rule is simply absent. The
  way it happens is an unquoted value containing a colon-space --

      description: Observers: side-effect containers      <- YAML rejects this
      description: "Observers: side-effect containers"    <- fine

  On one real migration that single shape broke 17 of 21 rules, and the citation
  and count checks passed them clean, because a file that fails to parse has no
  bad citations; it has nothing at all. `onboard-repo --check` now reports it as
  INVALID_FRONTMATTER, and a glob matching no file as DEAD_GLOB.
-->

# <Constraint name>

<One sentence: what must hold, stated as a rule rather than an explanation.>

## <The constraint>

<What to always do, or never do. Cite the file that proves it -- a `path:line`
that resolves -- rather than asserting it.>

```
<a short example of the correct shape, transcribed from real code in this repo,
not invented>
```

<If you state a count, give the command that produces it:>

    <e.g. rg -l 'SomePattern' --glob '*.ts' | wc -l>   -> <N> files

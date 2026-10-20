# grill-me

A single skill, [`skills/grill-me/SKILL.md`](../../skills/grill-me/SKILL.md), runs the plan interview.

## How it is built

- It is one skill. An earlier version had two: an interviewer and a typed-only wrapper that started it.
- The owner merged them into one skill with one name, `grill-me`.
- The skill has no `disable-model-invocation` flag, so saying "grill me" starts it as well as typing `/batbelt:grill-me`.
- The body is written as instructions to Claude, not as a request from the user.

## What the body requires

- Ask one question at a time and wait for the answer. Several at once are bewildering.
- Give a recommended answer with every question.
- Walk each branch of the design tree, and settle a decision before asking about the ones that depend on it.
- Explore the codebase instead of asking when the code can answer.
- Finish with the settled decisions, the open questions and the next step.

## The nearest neighbour

`prove-it` checks claims against sources. `grill-me` asks you questions about a plan. Their descriptions point at each other, so Claude picks the right one.

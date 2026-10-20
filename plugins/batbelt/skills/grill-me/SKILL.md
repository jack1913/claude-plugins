---
name: grill-me
description: >-
  Interviews the user about a plan or design, one question at a time with a suggested answer, until
  every decision holds up. Use when the user wants to stress-test a plan before building it, or says "grill me",
  "grill this plan" or "stress-test my design". Not for checking facts against sources; use prove-it
  for that.
---

# Grill me

Interview the user relentlessly about every aspect of their plan or design until you both reach a
shared understanding.

## How to run the interview

1. Start from the plan the user gave you. If they gave none, ask for it in one sentence, then begin.
2. Walk down each branch of the design tree. Resolve the dependencies between decisions one by one: settle a
   decision before you ask about the ones that depend on it.
3. Ask one question at a time, and wait for the answer before you continue. Several questions at once
   are bewildering.
4. For every question, give your recommended answer and say why. The user can reply "yes" to accept it.
5. If the codebase can answer a question, explore the codebase instead of asking.

## When to stop

Stop when no branch of the design tree has an open decision, or when the user says they have heard
enough.

End with a short summary:

- The decisions you settled, each with the answer the user chose.
- The questions still open, and who or what can answer each one.
- The first thing to do next.

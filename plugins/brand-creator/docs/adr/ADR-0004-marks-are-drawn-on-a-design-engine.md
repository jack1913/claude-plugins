# ADR-0004: Marks are drawn on a design engine

- **Status:** accepted
- **Date:** 2026-10-20
- **Source:** "Two axes" in the [brand-creator skill](../../skills/brand-creator/SKILL.md); the
  [drawing engines reference](../../skills/brand-creator/references/drawing-engines.md); the Unreleased entries of the
  [changelog](../../CHANGELOG.md)

## Context

A real round 1 drawn as code geometry (rounded tiles, cut-outs, dot grids) was rejected outright. ADR-0002 put style
research before the first drawing, and ADR-0003 made every logo master vector, but nothing said where a mark is drawn. The
next round was drawn on a use-llm design canvas: pixels placed by hand, and generated images traced into vector. The owner
picked from it, and asked for a fallback to Claude Code's /design for sessions without the canvas.

Claude Code's /design (2.1.234 and later, for a claude.ai login on a Pro, Max, Team or Enterprise plan) brings Claude
Design's artboard workflow into the CLI. Claude cannot start it: the owner types it. Without either tool, the only way left
is SVG that Claude writes by hand, the way of the rejected round.

## Decision

- Marks are drawn on the first engine the session has: the use-llm design canvas, else Claude Code's /design (the owner
  types it, with the brief brand-creator wrote), else Claude-drawn SVG.
- Claude-drawn SVG is an explicit, weaker choice. Claude first says what is missing and how to get each engine, then offers
  it, and draws only on the owner's explicit yes, recorded on the drawing engine line of the Collaboration block of
  BRAND-STATE.md. Never switch engines silently.
- The engine is where the drawing is made and shown, not who places the pixels. Placing pixels by hand on a grid is drawing
  too.
- The round gets a brief written from `templates/canvas-brief.md`, and the kept marks come back as SVG masters with one
  `SOURCE.md` per direction: the engine, the prompts, the image model and cost, the trace settings and the hand fixes.
- The style board needs no engine: it shows references, not drawn marks.

## Consequences

- A session without the canvas or /design stops at the drawing step and says why, unless the owner says yes to the weaker
  choice. A project can wait there for the owner to set up an engine.
- Generated images cost money on the canvas; the brief carries an image budget, and Claude says the cost in each reply.
- The canvas's quirks are field notes dated 2026-10-20 in the drawing engines reference, and go stale as the tools change.
- The `directions` workflow's designer agents still draw their marks themselves as SVG, so the workflow is offered only
  after the owner's yes to Claude-drawn SVG; routing it through an engine is still to do.

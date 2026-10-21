# ADR-0003: Logo masters are vector

- **Status:** accepted
- **Date:** 2026-10-20
- **Source:** "Two axes" in the [brand-creator skill](../../skills/brand-creator/SKILL.md); "Techniques by mark source" in [P6 mark](../../skills/brand-creator/references/phases/06-mark.md); the Unreleased entries of the [changelog](../../CHANGELOG.md)

## Context

On 2026-10-20 the jack1913 round 3 explored two directions with generated images (Gemini through OpenRouter), traced
with potrace, and a third with pixels placed by hand. Generated images are fast and cheap for finding an idea, but a
bitmap cannot be redrawn at 16 px, recoloured per token or checked as pure vector, and a fresh image of "the same" mark
is never the same mark. The owner asked that everything logo-related be made as vector, with rasters used only to
brainstorm. `check` already refused an SVG master that is not pure vector, but nothing said where a generated image may
appear or how it may become a mark.

## Decision

- The logo master is pure-vector SVG (`assets/logo/mark.svg` and its siblings), for every mark source. PNG, ICO and every
  other raster is exported from it.
- Generated images, photos and sketches are exploration. On a board they are labelled as such and never stand in for a
  direction's mark.
- A raster becomes a mark only when it is traced (potrace) or redrawn as vector and its curves are fixed by hand. The
  result is `authored-vector`; the raster stays with its round as the source.
- Refining a mark means editing the SVG master, not generating a new image.

## Consequences

- Image models stay available for exploring, at a stated cost, without their output reaching the pack.
- A traced mark costs hand time before G3: specks, curves and the fill colour are fixed by hand, and the round says so.
- Pixel marks drawn by code or by hand ship as SVG rectangles with `shape-rendering="crispEdges"`, with PNGs exported
  per size.

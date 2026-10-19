# (Brand name): surface inventory

`INVENTORY.md` at the project root, written in P1c before round 1 (Full tier and product-in-family; `board-lint` fails
round 1 without it unless BRAND-STATE.md records `inventory: none (no target repo)`). Read only: nothing in a target
repo is edited before G6.

## Targets read

| repo | path | branch or commit read | read on |
|---|---|---|---|
| (...) | (...) | (...) | YYYY-MM-DD |

How each was searched (commands, so the inventory can be repeated):

```
(e.g. rg -n -i "favicon|apple-touch|og:image|manifest|logo|icon" <repo> ; fd -e svg -e png -e ico -e icns . <repo>)
```

## Deployment targets

The oldest OS each target repo still supports, one line per platform, in exactly this form (`brand-creator emit apple` reads them; a
platform with a minimum below 26 gets the legacy appiconset and `.icns` besides the Icon Composer `.icon`, one at 26 or later does not).
Leave the section empty when there is no Apple target.

- iOS: (17.0)
- macOS: (14.0)

## Slots

One row per place the brand appears. ID: one letter per repo or surface family and a two-digit number (W01, A01 ...).
Platform rule: the size and format the platform asks for, with its citation; take it from
`scripts/emitters/platform-specs.json` when the surface is there (status V, R or U), otherwise cite the platform's own
page with the date read, otherwise write UNVERIFIED. Resampled by: SYS (the operating system scales it), OURS (we ship
each size), PAGE (a browser or CSS scales it). State: EXISTS, MISSING or STALE (present but wrong size, old mark or
old colour).

| ID | surface | path | size and format now | platform rule | citation (URL, checked, V/R/U) | resampled by | state | note |
|---|---|---|---|---|---|---|---|---|
| (W01) | (...) | (...) | (...) | (...) | (...) | SYS / OURS / PAGE | EXISTS / MISSING / STALE | (...) |

## Hardest surface

(The slot most likely to break the mark, with its ID. It goes into BRIEF.md and the hardest-surface cell of every board.)

## Surprises and conflicts

Spec drift (a repo behind the platform's current rule), colour collisions with a sibling or with semantic colours
(danger, success), a wrong store category, two slots that disagree.

1. (...)

## Considered and rejected

Slots or sources looked at and left out, each with its reason.

- (...)

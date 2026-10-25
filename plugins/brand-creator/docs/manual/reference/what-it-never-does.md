# What it never does

The limits brand-creator keeps, so you know what stays yours.

- **Nothing outward.** It never buys a domain, files a trademark, registers a handle, uploads to a store or contacts
  anyone. `/brand-creator:launch` hands you each of those steps, with the reason and where to click.
- **No git unless you ask.** It never commits, merges, pushes or stashes on its own. Each is a separate ask, and before a
  push you're told what it will trigger. Repository hooks are never skipped. Your product repositories change only after
  you say go, on a branch you name, one at a time, with a review first.
- **No deletes.** Replaced files move to a dated `removed-<date>/` folder. Earlier rounds are locked.
- **No "it's available".** A name check says REGISTERED, NOT-FOUND or UNKNOWN, never "available" or "clear". Names go to
  outside services only after you agree. Trademark searches and domain purchases are yours to do.
- **No "print-ready".** Print files stay proofs until your printer checks them. Without your printer's colour profile a
  file is an "RGB proof, not print-ready". With it, it's a "PDF/X-4 candidate (preflight with your printer)". Getting your
  printer's proof is your step.
- **No marks drawn in code without your yes.** Marks are drawn on a design tool, and it never starts `/design` for you.
  It draws marks as SVG code itself only when no design tool is there and you say yes to that weaker way.
- **No made-up facts.** Text on boards and in the book uses only facts you confirmed, kept in `FACTS.md`.
- **No quiet skips.** A check that can't run says "not verified" and why. It never counts as a pass.

## The safety hook

A hook runs before Claude writes a file or runs a shell command. It does nothing outside a brand project (a folder with
a `BRAND-STATE.md`). Inside one it keeps `history/` and every round except the latest read-only (round 0, the style
research board, stays open until the style is picked), and stops a project
folder from being deleted or moved. It blocks the call and tells Claude why. It is a best-effort guard, not a lock: a
programming one-liner can still write a file. The checksum check in `/brand-creator:check` is the real protection.

**Checked live, in the main thread and inside an agent.** In a real Claude Code session, an earlier version of the hook
blocked a write to an earlier round, a new file in `history/`, a shell write into an earlier round and a move of the
project folder, and let a write to the latest round through, both in the main thread and in an agent's tool calls. The
plugin's tests cover the rules added since. Run `/brand-creator:check` too.

## Related

- [Permissions](permissions.md)
- [Platform support](platform-support.md): the hook needs `python3`

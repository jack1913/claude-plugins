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
- **No made-up facts.** Text on boards and in the book uses only facts you confirmed, kept in `FACTS.md`.
- **No quiet skips.** A check that can't run says "not verified" and why. It never counts as a pass.

## The safety hook

A hook runs before Claude writes a file or runs a shell command. It does nothing outside a brand project (a folder with
a `BRAND-STATE.md`). Inside one it keeps `history/` and every round except the latest read-only, and stops a project
folder from being deleted or moved. It blocks the call and tells Claude why. It is a best-effort guard, not a lock: a
programming one-liner can still write a file. The checksum check in `/brand-creator:check` is the real protection.

**Not yet checked in a live session.** The hook's decisions are tested, but nobody has yet watched it block a call in a
real Claude Code session, in the main thread or inside an agent. If you rely on it, run `/brand-creator:check` too.

## Related

- [Permissions](permissions.md)
- [Platform support](platform-support.md): the hook needs `python3`

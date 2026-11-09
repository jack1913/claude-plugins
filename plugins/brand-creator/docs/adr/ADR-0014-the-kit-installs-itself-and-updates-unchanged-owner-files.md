# ADR-0014: The kit installs itself and updates owner files a repository never changed

- **Status:** accepted
- **Date:** 2026-11-09
- **Source:** the owner's answers of 2026-11-09 ("1. yes 2. yes") to the two questions of the working design
  `dev/specs/2026-11-09-g8-one-brand-kit-design.md` (one brand kit; its parts A4 and A5), and the plan beside it;
  [ADR-0011](ADR-0011-a-generated-brand-kit-around-the-applied-skill.md), its decisions D10 and D11; the pilot brand's
  hand-made kit and its `install.sh`, compared with the generated kit on 2026-11-09; the "kit status" and "kit: install.py"
  sections of the [script contract](../../scripts/CONTRACT.md).

## Context

The pilot brand had two kits doing one job: a hand-made one that its own `install.sh` copied into product repositories,
and the generated kit of [ADR-0011](ADR-0011-a-generated-brand-kit-around-the-applied-skill.md). The owner chose one kit, the
generated one, and asked for the hand-made kit's good features to move into the generator.

Two of those features ran against ADR-0011's defaults:

- **D10: a script never writes outside the brand project.** The generated kit reached a repository only through the
  implementer, file by file, after G6, so a person with a clone of the brand project or of its read-only mirror and no
  plugin could not install it. The hand-made kit's `install.sh` needed only bash, Python and git.
- **D11: an installed kit's owner files belong to the repository.** An update copied an owner file only where the
  repository had none. A recipe the brand project improved therefore never reached a repository that already held the old
  one, unless someone copied it by hand; the hand-made kit's update replaced the whole copy.

ADR-0011 names both as defaults the owner may change in a new record.

## Decision

- **The kit carries its installer.** Every kit holds `install.py`, a generated file: the bytes of
  `scripts/adaptlib/kitcopy.py`, the module that `kit status` judges a copy with, so the installer and the plugin give the same
  answer by construction. It imports the Python standard library only. `python3 install.py <folder in a clone>` says what it
  would copy; `--yes` copies into `<repository root>/.claude/skills/<kit>/`, `kit.json` last, and moves files left over from an
  older kit to `removed-<date>/` in the repository. It never deletes, commits, makes a branch or pushes. It refuses the brand
  project, the repository its own copy sits in, a folder outside a git work tree, the home folder and `~/.claude`: the kit is
  installed per repository, never globally (the owner, 2026-10-26). It never puts an older kit over a newer one. This replaces D10 for this one file only: the plugin's own
  scripts still write only inside the brand project. `/brand-creator:brand-adopt` runs it for a Brand kit row, on the owner's
  branch, after G6, as before.
- **An owner file the repository never changed is updated.** Each owner file is judged against the `owned` record of the
  repository's own `kit.json`, which holds its hash as it was copied. Bytes equal to that hash mean the repository never changed
  the file, so a newer one from the brand project replaces it. A file the repository changed or added stays its own: reported,
  never copied over. A file the record lists, unchanged, that the brand project's kit no longer has is moved aside like any file
  left over. A repository `kit.json` that cannot be read counts as no record, so nothing is updated then. Because the record
  sits in `kit.json`, `kit.json` is the last file of every copy: a copy that stops before it is finished by the next run, and an
  owner file copied before it is never taken for the repository's own edit. This replaces D11's "copies an owner file only where
  the repository has none"; the rest of D11 stands.
- **A second skill for the same brand is named.** `kit status` and `install.py` warn when the repository's `.claude/skills/`
  holds another skill whose front matter names the brand (a hand-made kit, say), because Claude may load either. Taking it out
  is the owner's call.

## Consequences

- A clone of a brand project, or of its mirror, is enough to install and update the kit; the plugin is not needed for that.
- `kit status --repo` stays read only; what it lists to copy is what `install.py` copies.
- A repository keeps every edit it made to an owner file. To take the brand project's newer version of such a file, the owner
  copies it by hand.
- Every change to `kitcopy.py` changes `install.py`, so a plugin update that touches it moves every kit's build number once.
- The other generated-kit features of the same release (the shorter `SKILL.md` with steps and a map, `brand.md`, `checklist.md`
  and the masters' recipe scaffolds) change no decision of ADR-0011 and are written in the contract and the changelog.

## Update 2026-11-09

An owner file that the repository's `kit.json` records as copied, and that the repository no longer has, was taken out by the
repository: a deletion is the repository's own change, like an edit, so the file is not copied back and is reported as deleted
(0.11.1, from the pilot brand's code review). Before, a missing owner file was copied on every run, as D11 had it. An owner file the
record does not list, such as a recipe the brand project added since, is still copied where the repository has none. Everything
else in the decision stands.

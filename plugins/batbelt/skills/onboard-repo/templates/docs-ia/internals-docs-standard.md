# Docs standard

How every doc in <repo> is written and where it lives. One standard, so a reader who learns one
part of the docs can find their way in any other.

## 1. Four kinds of page

Every page is exactly one kind ([Diátaxis](https://diataxis.fr/)). Never mix two on one page; link
instead. One exception: a how-to keeps the explanation its output needs (what the reader just saw,
and how to read it, as prose or a table); deeper "why" goes to an explanation page.

| Kind | Answers | Lives in | Title shape |
| --- | --- | --- | --- |
| Getting started | "How do I begin?" | `docs/manual/getting-started/` | Verb phrase: "Install <repo>" |
| How-to | "How do I do X?" | `docs/manual/<task>.md` | Verb phrase: "Review a screen" |
| Reference | "What exactly is X?" | `docs/manual/reference/` | Noun: "Commands", "Settings" |
| Explanation | "Why is it like this?" | `docs/internals/`, `docs/adr/` | Noun or question |

## 2. Who reads what

| Folder | For | Voice |
| --- | --- | --- |
| `README.md` | Anyone deciding whether to use <repo> | Set by the README voice recorded in REPO SPECIFICS |
| `docs/manual/` | People who use <repo> | The docs voice recorded in REPO SPECIFICS; by default commands-first, one concept per page, each showing what you'll actually see (§4) |
| `docs/internals/` | Contributors | Plain technical |
| `docs/adr/` | Contributors | Plain technical, one decision per file |
| `docs/archive/` | Nobody day to day | Frozen, never edited |
| `AGENTS.md` | Coding agents | Pointer index, no prose |

The manual is for users only. Maintainer procedures (running tests, cutting a release, the repo
layout) go in `docs/internals/`.

### The README

These hold in every README voice:

- The first screen says what <repo> is and shows the install command (or, for a repo with nothing to
  install, such as a curated list or a spec, how to start using it); a voice may open with one
  short paragraph before it. A quick start installs before it uses anything.
- The README keeps the install command and its platform twin. It is the one allowed copy of the
  install fact; the full walkthrough lives on the getting-started page.
- One section per feature: one or two paragraphs, at most one table, one link out to its page.
- Table cells stay on one line.
- H2 and H3 headings are coverage keys: renaming one updates `docs/.onboard-coverage.json` in the
  same change.
- Versions and package facts match the file that owns them.
- A Documentation section links the manual, internals and decisions (the archive is reached from
  `docs/README.md`).

The list sits in the standard's body, below REPO SPECIFICS: a voice's signature rule that departs
from the README list wins, and is recorded once under Local deviations; the install command is
the exception and stays in every voice. The recorded voice decides the rest: hero, badges, emoji, callouts, `<details>` blocks, what opens
the first screen, tone, and where flags sit. With no README voice recorded, no voice is imposed;
the list above still holds (a Local deviations entry may relax a §2 README rule other than the
install command, such as a launchpad README with a table per section), and every run checks the
README invariants and the recorded voice's
signature rules, not only a styling run.

## 3. Where things live

### One fact, one home

A fact has exactly one owner. Every other page links to it and never retypes it.

| Fact | Its only home |
| --- | --- |
| The current version | The manifest or file that already holds it (name it in `AGENTS.md`) |
| How to install | One page in `docs/manual/getting-started/` (the README keeps the command, §2) |
| How to use a feature | That feature's page, `docs/manual/<task>.md` |
| What changed in a release | `CHANGELOG.md` |
| Why a decision was made | One ADR |
| A fact another repository owns (a plugin's commands, its skills, its versions) | Its home there: name it and link to it; never restate it. Check with `check-docs --forbidden <names> --forbidden-allow <globs>` |

### Layout

```text illustrative
README.md                    what <repo> is, how to install it, links
AGENTS.md                    pointer index for agents
CHANGELOG.md                 Keep a Changelog (§6)
docs/README.md               one table: the folders below
docs/manual/README.md        the manual index: Get started, Do a task (the tour), Look it up
docs/manual/getting-started/ first-run pages
docs/manual/<task>.md        one how-to per task, in the index's reading order
docs/manual/reference/       commands, settings, troubleshooting
docs/internals/              how it works, tests, release, this standard
docs/adr/                    decisions, with a README index
docs/archive/                frozen records: build logs, shipped plans and specs
```

The index opens with a bold **New here?** pointer to the first-run page. The Do a task list is the
tour: numbered in reading order, and each how-to ends with a
**Next:** link to the page after it. A voice may rename the three groups, never merge or reorder
them. A repo that files how-tos in `docs/manual/use/` records it under Local deviations.

Adopting existing docs never moves or regroups them: an existing manual's layout, index order and
Next tour are kept, and recorded under Local deviations where they differ from this section.

Create a folder when it gets its first page; no empty folders. A repo with little to say may keep
its whole manual in `docs/manual/README.md` until it outgrows one page.

Working files (specs, plans, scratch) are not docs. While in progress they live outside `docs/`, or
in one folder named in `AGENTS.md`; when they ship, they move to `docs/archive/` and the pointers
that cite them move with them.

## 4. Voice

For manual pages. The README follows its recorded voice and the list in §2. Internals and ADRs stay
plain technical.

- Talk to the reader: "you", active voice, present tense.
- Lead with the command: what to type or say → what you'll see → what it means → the fix if it goes
  wrong.
- One idea per sentence. Short sentences, plain words.
- Explain a term the first time it appears, or drop it. Never show internal codes (phase or gate
  numbers, decision numbers, build-stage names) on a user page. To give the reason for a choice,
  link the explanation by its title, never its number.
- No citations after sentences. Facts are checked in the work; a page links to deeper docs at most
  once per section.
- Sentence-case headings. Descriptive link text, never "click here".
- Numbered lists for steps and for the manual's reading order; bullets for everything else.
- Show real output where it helps the reader. Never invent output; never show maintainer commands
  (`jq`, `git ls-files`) on a user page. Each captured block has an italic caption saying how it was
  taken; a trimmed one says it is an excerpt.
- When the repo has a front-end per platform, every command block that runs a `.sh` front-end has its
  PowerShell twin, sh first; a command that is the same in both shells (a CLI, `git`, `npm`) needs
  none. Output from a platform nobody captured is `illustrative`.
- A captured block is a `console capture=<slug>` fence holding only the output, right after its
  command block, unless Local deviations record another shape.
- Callouts (`> [!IMPORTANT]`, `> [!NOTE]`, `> [!WARNING]`) mark a guarantee or a destructive step,
  at most one per section.
- Every how-to has an If something goes wrong table (`You see | Do this`) built from the real error
  text.
- No numbers that rot: test counts, timings, "so far", "yet". Say how to check instead.
- Hard-code no current version except in the one file that owns it and `CHANGELOG.md`; use
  `<version>` in examples, while upgrade notes keep the versions they name ("Installs from 1.2 and
  earlier ..."), because a past version is a fixed fact.
- One word per idea across the whole repo: pick a term for each concept and keep it.

## 5. If this repo ships Claude Code skills

Delete this section if it does not.

The `/` menu shows a skill's `description`, so it is user-facing text. It follows §4's plain words,
no jargon and no internal codes, but it is written in the third person ("Reviews a screen…", never
"You can…"), because it is also injected into Claude's context.

```yaml illustrative
description: >-
  <What it does, in one plain sentence.> Use when <the situations and phrases that should start
  it>. Not for <the nearest thing it should not do>.
```

- `description` is at most 1,024 characters; `SKILL.md` stays under 500 lines, with detail in
  `references/` linked one level deep.
- A skill with more than five reference files has a `references/_index.md` table:
  `File | Use it for`.

## 6. Changelogs

[Keep a Changelog 1.1](https://keepachangelog.com/en/1.1.0/) and [SemVer](https://semver.org/):

- An `## [Unreleased]` heading at the top, then `## [X.Y.Z] - YYYY-MM-DD`, newest first.
- Sections, in this order, only when used: Added, Changed, Deprecated, Removed, Fixed, Security.
- Write for users: what changed for them, in §4 voice. No commit logs.
- A removed or renamed command goes under Removed or Changed with what to type instead.
- The top version equals the version in the manifest, or the latest release tag when the repo has no
  manifest.
- The public API that SemVer protects: what a user can depend on, such as command names and their
  arguments, configuration keys, file formats and documented behaviour. While the version is
  `0.y.z`, a minor bump may break it; the changelog says so.

## 7. Decision records

One decision per file: `ADR-NNNN-kebab-title.md`, from [`../adr/ADR-TEMPLATE.md`](../adr/ADR-TEMPLATE.md),
listed in that folder's `README.md`.

- Status is exactly one of `proposed`, `accepted`, `deprecated` or `superseded by ADR-NNNN`. What a
  record replaces goes on its own `Supersedes: ADR-NNNN[, ADR-NNNN]` line, so a record can both
  supersede older ones and later be superseded itself.
- After acceptance the decision text is never rewritten. Two mechanical edits are allowed: the
  Status and Supersedes lines, and a path in a link or Source line whose target file moved. A later
  fact that makes the record read wrong goes in a dated `## Update YYYY-MM-DD` section at the end. A
  changed decision is a new ADR.
- Cite sources by commit, file or heading, never by `file:line`.

## Local deviations

What this repo does differently from the sections above, on purpose. Each entry names the rule it
departs from and what the repo does instead. Onboarding and `--sync` fill this list from what the
repo already does; add to it by hand when you make a new deliberate choice.

```text illustrative
- §3 Layout: how-to pages sit in docs/manual/use/, not directly in docs/manual/.
- §4 Output: captured output uses text capture= fences; keep that shape, never convert it.
```

- None.

When two rules disagree, the first of these wins:
REPO SPECIFICS → the standard's Local deviations → the standard's body → built-in defaults.
REPO SPECIFICS is the block at the end of the stamped `update-docs` skill. A recorded deviation is
never reported as a finding. It never excuses unfinished work: an unfinished principal page is still
reported.

## 8. Checks

The stamped `update-docs` skill is the gate. Run it after any change to the docs:

```bash
python3 .claude/skills/update-docs/scripts/check.py check-docs docs README.md AGENTS.md \
  --captures docs/.onboard-captures --coverage docs/.onboard-coverage.json
```

It reports broken links, placeholders left in a page, output blocks without a provenance tag
(`capture=<slug>` or `illustrative`), manual pages with commands but no output, and decision records
that are misnamed, lack Context/Decision/Consequences, are missing from the `adr/README.md` index, or
point to a superseded-by record that does not exist. The status wording and the no-rewrite rule of §7
are checked in review, not by the gate. When this standard and the skill's built-in defaults differ,
the order under Local deviations decides.

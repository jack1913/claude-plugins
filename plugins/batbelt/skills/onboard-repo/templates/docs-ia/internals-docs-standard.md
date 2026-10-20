# Docs standard

How every doc in <repo> is written and where it lives. One standard, so a reader who learns one
part of the docs can find their way in any other.

## 1. Four kinds of page

Every page is exactly one kind ([Diátaxis](https://diataxis.fr/)). Never mix two on one page; link
instead.

| Kind | Answers | Lives in | Title shape |
| --- | --- | --- | --- |
| Getting started | "How do I begin?" | `docs/manual/getting-started/` | Verb phrase: "Install <repo>" |
| How-to | "How do I do X?" | `docs/manual/use/` | Verb phrase: "Review a screen" |
| Reference | "What exactly is X?" | `docs/manual/reference/` | Noun: "Commands", "Settings" |
| Explanation | "Why is it like this?" | `docs/internals/`, `docs/adr/` | Noun or question |

## 2. Who reads what

| Folder | For | Voice |
| --- | --- | --- |
| `README.md` | Anyone deciding whether to use <repo> | Storefront: friendly, short |
| `docs/manual/` | People who use <repo> | Friendly, short, task-first (§4) |
| `docs/internals/` | Contributors | Plain technical |
| `docs/adr/` | Contributors | Plain technical, one decision per file |
| `docs/archive/` | Nobody day to day | Frozen, never edited |
| `AGENTS.md` | Coding agents | Pointer index, no prose |

The manual is for users only. Maintainer procedures (running tests, cutting a release, the repo
layout) go in `docs/internals/`.

## 3. Where things live

### One fact, one home

A fact has exactly one owner. Every other page links to it and never retypes it.

| Fact | Its only home |
| --- | --- |
| The current version | The manifest or file that already holds it (name it in `AGENTS.md`) |
| How to install | One page in `docs/manual/getting-started/` |
| How to use a feature | That feature's page in `docs/manual/use/` |
| What changed in a release | `CHANGELOG.md` |
| Why a decision was made | One ADR |

### Layout

```text illustrative
README.md                    storefront: what <repo> is, install, links
AGENTS.md                    pointer index for agents
CHANGELOG.md                 Keep a Changelog (§6)
docs/README.md               one table: the folders below
docs/manual/README.md        the manual index: Get started, Do a task, Look it up
docs/manual/getting-started/ first-run pages
docs/manual/use/             one how-to per task
docs/manual/reference/       commands, settings, troubleshooting
docs/internals/              how it works, tests, release, this standard
docs/adr/                    decisions, with a README index
docs/archive/                frozen records: build logs, shipped plans and specs
```

Create a folder when it gets its first page; no empty folders. A repo with little to say may keep
its whole manual in `docs/manual/README.md` until it outgrows one page.

Working files (specs, plans, scratch) are not docs. While in progress they live outside `docs/`, or
in one folder named in `AGENTS.md`; when they ship, they move to `docs/archive/` and the pointers
that cite them move with them.

## 4. Voice

For manual pages and READMEs. Internals and ADRs stay plain technical.

- Talk to the reader: "you", active voice, present tense.
- Lead with the task: what you can do → what to type or say → what you'll see → the fix if it goes
  wrong.
- One idea per sentence. Short sentences, plain words.
- Explain a term the first time it appears, or drop it. Never show internal codes (phase or gate
  numbers, decision numbers, build-stage names) on a user page.
- No citations after sentences. Facts are checked in the work; a page links to deeper docs at most
  once per section.
- Sentence-case headings. Descriptive link text, never "click here".
- Numbered lists for steps, bullets for everything else.
- Show real output where it helps the reader. Never invent output; never show maintainer commands
  (`jq`, `git ls-files`) on a user page.
- No numbers that rot: test counts, timings, "so far", "yet". Say how to check instead.
- Hard-code no version except in the one file that owns it and `CHANGELOG.md`. Use `<version>` in
  examples.
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
- The top version equals the version in the manifest.
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
are checked in review, not by the gate. The docs standard wins over the skill's built-in defaults when they differ.

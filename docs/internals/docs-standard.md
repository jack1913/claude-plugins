# Docs standard

How every doc in this marketplace is written and where it lives: the marketplace root and every
plugin under `plugins/`. One standard, so a reader who learns one plugin's docs can find their way in
any other. Why it is this way: [ADR-0003](../adr/ADR-0003-one-docs-standard.md).

Templates for each page type are in [`templates/`](templates/).

## 1. Four kinds of page

Every page is exactly one kind ([Diátaxis](https://diataxis.fr/)). Never mix two on one page; link
instead.

| Kind | Answers | Lives in | Title shape |
| --- | --- | --- | --- |
| Getting started | "How do I begin?" | `docs/manual/getting-started/` | Verb phrase: "Install swift" |
| How-to | "How do I do X?" | `docs/manual/use/` | Verb phrase: "Review a screen" |
| Reference | "What exactly is X?" | `docs/manual/reference/` | Noun: "Commands", "Settings" |
| Explanation | "Why is it like this?" | `docs/internals/`, `docs/adr/` | Noun or question |

## 2. Who reads what

| Folder | For | Voice |
| --- | --- | --- |
| `README.md` | Anyone deciding whether to install | Storefront: friendly, short |
| `docs/manual/` | People who use the plugin | Friendly, short, task-first (§4) |
| `docs/internals/` | Contributors | Plain technical |
| `docs/adr/` | Contributors | Plain technical, one decision per file |
| `docs/archive/` | Nobody day to day | Frozen, never edited |
| `AGENTS.md` | Coding agents | Pointer index, no prose |

The manual is for users only. Maintainer procedures (adding a plugin, running tests, cutting a
release, the repo layout) go in `docs/internals/`.

## 3. Where things live

### One fact, one home

A fact has exactly one owner. Every other page links to it and never retypes it.

| Fact | Its only home |
| --- | --- |
| A plugin's version | `plugins/<name>/.claude-plugin/plugin.json` |
| How to install from this marketplace | `docs/manual/getting-started/install-a-plugin.md` |
| What a plugin does, how to use it | That plugin's `docs/manual/` |
| What changed in a release | That plugin's `CHANGELOG.md` |
| Why a decision was made | One ADR |

A plugin README may show its own two install lines (they are its storefront); everything past that
links to the install page.

### The marketplace root

```text illustrative
README.md                    storefront: what the marketplace is, plugin cards, install, links
CONTRIBUTING.md              how to change anything here (links into docs/internals/)
SECURITY.md                  how to report a problem
docs/manual/                 cross-plugin pages only: choose, install, troubleshoot, glossary,
  use/<plugin>.md            one short card per plugin that links into the plugin's own manual
docs/internals/              maintainer pages, this standard, templates
docs/adr/                    marketplace decisions
docs/archive/                frozen records
```

### Every plugin

```text illustrative
plugins/<name>/
  README.md                  storefront, under about 150 lines (template: plugin-readme.md)
  CHANGELOG.md               Keep a Changelog (§6)
  LICENSE                    or a line in the README naming the licence that applies
  AGENTS.md                  pointer index for agents working on the plugin
  docs/README.md             one table: the folders below
  docs/manual/README.md      the plugin's manual index
  docs/manual/getting-started/
  docs/manual/use/           one how-to per task
  docs/manual/reference/     commands.md (every command and skill), settings, troubleshooting
  docs/internals/            how it works, tests, release, contracts
  docs/adr/                  the plugin's own decisions, with a README index
  docs/archive/              frozen records: build logs, shipped plans and specs
```

Create a folder when it gets its first page; no empty folders. A plugin with little to say may keep
its whole manual in `docs/manual/README.md` until it outgrows one page.

Working files (specs, plans, scratch) are not docs. While in progress they live outside `docs/`, or
in one folder named in the plugin's `AGENTS.md` (for example swift's `docs/superpowers/`); when they
ship, they move to `docs/archive/` and the pointers that cite them move with them.

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
- Hard-code no plugin version except in `plugin.json` and `CHANGELOG.md`. Use `<version>` in
  examples. One exception: the minimum Claude Code version a plugin needs, which lives once, in that
  plugin README's Install section; other pages link to it.
- One word per idea across the whole marketplace (see the glossary): plugin, skill, command, agent,
  workflow, hook, marketplace, scope.

## 5. Skills, commands, agents and plugin metadata

The `/` menu shows a skill's `description`, so it is user-facing text. It follows §4's plain words,
no jargon and no internal codes, but it is written in the third person ("Reviews a screen…", never
"You can…"), because it is also injected into Claude's context.

### Skill frontmatter

```yaml
name: review                               # equals the folder name; ^[a-z0-9-]{1,64}$
description: >-                            # 1,024 characters at most
  <What it does, in one plain sentence.> Use when <the situations and phrases that should start
  it>. Not for <the nearest thing it should not do>.
when_to_use: <optional: long trigger lists, other-language triggers>
argument-hint: "[--flag] <thing>"          # whenever it takes arguments
disable-model-invocation: true             # typed only; the description says "Runs only when typed as /<plugin>:<name>."
user-invocable: false                      # Claude only; hidden from the / menu
```

- `name` equals the skill's folder name (the folder name is also what invokes it), uses only
  lowercase letters, digits and hyphens, is at most 64 characters, and contains neither "anthropic"
  nor "claude".
- `description` is at most 1,024 characters (the Agent Skills limit). `description` plus
  `when_to_use` is at most 1,536 characters (where the Claude Code listing cuts). House target for a
  skill Claude can start: both together under about 1,024, because every enabled plugin's listing
  loads each turn. Typed-only skills are not in the listing, so only the hard limits apply.
- `SKILL.md` body stays under 500 lines. Detail goes in `references/`, linked one level deep. A skill
  with more than five reference files has a `references/_index.md` table: `File | Use it for`.
- Sources: [Claude Code skills](https://code.claude.com/docs/en/skills),
  [skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).

### Agent frontmatter

- Only fields plugin agents support: `name`, `description`, `model`, `effort`, `maxTurns`, `tools`,
  `disallowedTools`, `skills`, `memory`, `background`, `omitClaudeMd`, `isolation`, `color` and the
  others listed in [plugin components](https://code.claude.com/docs/en/plugins/components). Fields
  plugin agents ignore (`permissionMode`, `hooks`, `mcpServers`, `initialPrompt`) are never set:
  they would read as protection that does not exist.
- `description` opens with when it may be used, then one sentence on what it does. A line such as
  `Only for <plugin> workflows; do not auto-delegate.` is a request to Claude, not a control: no
  field blocks delegation, so the docs never call it a guarantee.
- Model and tools go in their own fields, not in the prose.

### The commands reference

Every plugin with more than one command has `docs/manual/reference/commands.md`
([template](templates/commands-reference.md)). Its commands table has one row per skill and
workflow; agents, which are not `/` commands, go in a separate Agents table.

| Command | Starts | What it does | Arguments |
| --- | --- | --- | --- |
| `/plugin:name` | you only · you or Claude · Claude only | one line, from the description | `argument-hint` |

"You only" is `disable-model-invocation: true`; "Claude only" is `user-invocable: false`. The plugin
README's command table is a short version of this page and links to it.

### `plugin.json` and the marketplace entry

Display fields have one home: `plugin.json`. Every plugin sets `name`, `displayName`, `description`,
`version`, `author`, `homepage` (`https://github.com/jack1913/claude-plugins/tree/main/plugins/<name>`),
`repository`, `license` and `keywords`. The `description` is one plain sentence of what you can do
with it, under 120 characters.

The marketplace entry carries only `name`, `source`, `category` and `tags`. Every source here is a
relative path, so Claude Code reads the display fields from `plugin.json` even before install, and a
copy in the entry would only shadow it
([marketplace reference](https://code.claude.com/docs/en/plugins/marketplace-reference)). No
`version` in the entry either ([ADR-0002](../adr/ADR-0002-per-plugin-versions-and-tags.md)).

## 6. Changelogs

[Keep a Changelog 1.1](https://keepachangelog.com/en/1.1.0/) and [SemVer](https://semver.org/), in
every plugin:

- An `## [Unreleased]` heading at the top, then `## [X.Y.Z] - YYYY-MM-DD`, newest first.
- Sections, in this order, only when used: Added, Changed, Deprecated, Removed, Fixed, Security.
- Write for users: what changed for them, in §4 voice. No commit logs.
- A removed or renamed command goes under Removed or Changed with what to type instead.
- The top version equals `plugin.json`. Releases are tagged `<name>--vX.Y.Z` with
  `claude plugin tag plugins/<name>` (`changelog-release` does the changelog and version).
- The public API that SemVer protects: command and skill names, their arguments, hook behaviour and
  settings keys. While a plugin is `0.y.z`, a minor bump may break it; the changelog says so.

## 7. Decision records

One decision per file: `ADR-NNNN-kebab-title.md`, from [`../adr/ADR-TEMPLATE.md`](../adr/ADR-TEMPLATE.md),
listed in that folder's `README.md`.

- Status is exactly one of `proposed`, `accepted`, `deprecated` or `superseded by ADR-NNNN`. What a
  record replaces goes on its own `Supersedes: ADR-NNNN[, ADR-NNNN]` line, so a record can both
  supersede older ones and later be superseded itself.
- After acceptance the decision text is never rewritten. Two mechanical edits are allowed: the
  Status and Supersedes lines, and a path in a link or Source line whose target file moved. A later fact that makes the record read
  wrong goes in a dated `## Update YYYY-MM-DD` section at the end. A changed decision is a new ADR.
- Cite sources by commit, file or heading, never by `file:line`.

## 8. Checks

`.github/workflows/docs.yml` runs on every change to a Markdown file, a `.claude-plugin/*.json` file
or one of its configs:

| Check | Config | Catches |
| --- | --- | --- |
| `.github/scripts/check-docs-standard.py` | its docstring | Skill and agent frontmatter, `plugin.json` fields and the marketplace entry shape (§5); changelog shape and version (§6); ADR status (§7); `AGENTS.md` pointers that no longer exist; commands pages that miss a skill |
| markdownlint-cli2 | `.markdownlint-cli2.yaml` | Heading order, fence languages, bare URLs, list and heading spacing, a missing first heading |
| lychee, offline | `lychee.toml` | Broken relative links and anchors |
| `.github/scripts/check-workflows.py` | its docstring | Not a docs check: the workflows' verdict jobs and the rulesets. It runs here because every release-tag ruleset requires this job ([ADR-0005](../adr/ADR-0005-release-tags-need-a-passing-ci-verdict.md)) |

Run them locally from the repo root:

```bash
python3 .github/scripts/check-docs-standard.py
npx markdownlint-cli2 "**/*.md"
lychee --config lychee.toml --root-dir "$(pwd)" './**/*.md'
```

Every check fails the build. Archives, eval cases, test fixtures and files that are copied into other
projects (brand-creator's `templates/`, onboard-repo's `templates/`) are skipped. markdownlint also
skips agent-facing packs (skill bodies, references, agent prompts, `CLAUDE.md` bridges) and verbatim
legal text; their frontmatter is checked by the script and their links by lychee.

batbelt's `onboard-repo` stamps a general version of this standard into the repositories it sets
up (`docs/internals/docs-standard.md` there), without the plugin-specific rules of §5.

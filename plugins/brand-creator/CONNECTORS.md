# Connectors

brand-creator needs no connector. Every step runs with the plugin's own tools, and the plugin ships no MCP server and no
`.mcp.json`: nothing is installed or connected on your behalf.

If your session already has a design tool connected (for example Figma or Canva, written below as `~~design tool`), the
skills may use it in the narrow ways listed here, and only these.

| Placeholder | Example | What it may be used for |
|---|---|---|
| `~~design tool` | Figma, Canva | reading a file you point at; writing to it only on your explicit ask |

## Rules

1. **Optional, never assumed.** When no `~~design tool` is connected, nothing changes and nothing is "not verified" because
   of it. The skills never ask you to install one.
2. **Reading needs a pointer.** The `~~design tool` is read only when you name the file or frame (an existing logo, a
   layout to adopt). Whatever is read goes into the project as a file (`brief/` or `research/`), with where and when it was
   read.
3. **Writing needs an ask, one action at a time.** Nothing is written to a `~~design tool` (a brand kit, styles,
   components, uploaded logos) unless you ask for that write, after you have approved the finished files, and each write is said first: what goes where.
   It is an outward action like any other.
4. **External kits are never the source of truth.** Colours and type live in the project's design token files
   (`tokens/*.tokens.json`, in the DTCG format: see the [glossary](docs/manual/reference/glossary.md)), facts in `FACTS.md`, the mark in `assets/logo/`. A value read from a `~~design tool` is a
   proposal checked against them, never copied over them; a kit that disagrees with the tokens is out of date, and the
   difference is reported, not resolved silently.
5. **Generated files stay generated.** Anything pushed to a `~~design tool` is made from the pack (the same files the
   manifest lists), so the same rule holds as everywhere in the project: change the source, regenerate, then write again.

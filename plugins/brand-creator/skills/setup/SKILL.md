---
name: setup
description: Installs what brand-creator's render and token tools need (Node packages and a Chromium build) into the plugin's data folder, after showing what will be downloaded and getting the user's OK. Runs only when typed as /brand-creator:setup.
argument-hint: "[--force]"
disable-model-invocation: true
allowed-tools: Bash(brand-creator *)
---

# Setup

Consented install, never automatic. Nothing is written under the plugin folder.

1. Show the plan: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" setup --plan`.
   Relay it in plain words: what is downloaded, from where, roughly how large, and where it goes.
2. Ask for an explicit OK (AskUserQuestion: "(Recommended) Install now" / "Not now"). Without a yes, stop.
3. Install: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" setup --yes $ARGUMENTS`.
4. Check the tools for the tier: `brand-creator --data "${CLAUDE_PLUGIN_DATA}" prereq --for quick`
   (and `--for standard` or `--for full` when a project uses that tier). Report every MISSING line with what it
   blocks and its install command; install system tools (uv, Node, resvg, Ghostscript) only when the user asks, one
   command at a time.
5. Off macOS, `prereq` may ask whether to use the cross-platform renderer; relay that question, never answer it for
   the user. The choice is recorded in BRAND-STATE.md and printed on every report.

Report failures exactly as printed; never claim a step succeeded without its output.

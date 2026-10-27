import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SKILL_DIR = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "plugins",
  "batbelt",
  "skills",
  "puppet-master",
);
const read = (name) => fs.readFileSync(path.join(SKILL_DIR, name), "utf8");

test("frontmatter names the skill puppet-master", () => {
  const skill = read("SKILL.md");
  const fm = /^---\r?\n([\s\S]*?)\r?\n---/.exec(skill);
  assert.ok(fm, "SKILL.md has no frontmatter");
  assert.match(fm[1], /^name: puppet-master$/m);
  assert.match(fm[1], /^description: Runs background Claude Code worker sessions from one interactive session/m);
});

test("the body covers every subcommand, the window variable and the thresholds", () => {
  const skill = read("SKILL.md");
  for (const word of ["measure", "list", "spawn", "cycle", "close", "--window", "--next", "PUPPET_CONTEXT_WINDOW", "PUPPET_CLAUDE_BIN"]) {
    assert.ok(skill.includes(word), `SKILL.md does not mention ${word}`);
  }
  assert.ok(skill.includes("30%"));
  assert.ok(skill.includes("50%"));
});

test("on start the master asks the user before using sessions that are already open", () => {
  const skill = read("SKILL.md");
  assert.match(skill, /## On start/);
  assert.ok(skill.includes("ListAgents"), "SKILL.md does not tell the master to list open sessions");
  assert.match(skill, /ask the\s+user\s+whether\s+you\s+may\s+use\s+them/);
});

test("the worker brief carries every placeholder", () => {
  const brief = read("worker-brief.md");
  for (const p of ["{{job}}", "{{commit_rules}}", "{{master_name}}"]) {
    assert.ok(brief.includes(p), `worker-brief.md lacks ${p}`);
  }
});

test("neither file carries machine-specific values", () => {
  const forbidden = [
    /[A-Za-z]:\\\\/,
    /\/Users\/|\/home\//,
    /~\/\.claude\/projects\/[^<]/,
    /claude-(opus|sonnet|haiku|fable)-\d/,
  ];
  for (const name of ["SKILL.md", "worker-brief.md"]) {
    const text = read(name);
    for (const re of forbidden) assert.doesNotMatch(text, re, `${name} matches ${re}`);
  }
});

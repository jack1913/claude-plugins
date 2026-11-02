import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { TAGS } from "../../plugins/batbelt/skills/puppet-master/scripts/analyst.mjs";

const PLUGIN_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "plugins", "batbelt");
const SKILL_DIR = path.join(PLUGIN_DIR, "skills", "puppet-master");
const read = (name) => fs.readFileSync(path.join(SKILL_DIR, name), "utf8");

// The text of one `## ` section, up to the next one.
function section(text, heading) {
  const start = text.indexOf(`## ${heading}`);
  assert.ok(start >= 0, `no "## ${heading}" section`);
  const next = text.indexOf("\n## ", start + 3);
  return text.slice(start, next < 0 ? undefined : next);
}

test("frontmatter describes coordinating sessions", () => {
  const skill = read("SKILL.md");
  const fm = /^---\r?\n([\s\S]*?)\r?\n---/.exec(skill);
  assert.ok(fm, "SKILL.md has no frontmatter");
  assert.match(fm[1], /^name: puppet-master$/m);
  assert.match(fm[1], /^description: Coordinates Claude Code sessions from one interactive session/m);
  assert.match(fm[1], /Use when /);
  assert.match(fm[1], /Not for /);
});

test("the body covers every helper command, the logs flags and the thresholds", () => {
  const skill = read("SKILL.md");
  const words = [
    "measure", "list", "spawn", "cycle", "close", "adopt", "assign", "finish", "pick", "harvest",
    "finding", "summary", "decide", "shipped", "logs", "--window", "--next", "--job", "--role analyst",
    "--logs", "--plugin-data", "${user_config.puppet_logs_dir}", "${CLAUDE_PLUGIN_DATA}",
    "PUPPET_CONTEXT_WINDOW", "PUPPET_CLAUDE_BIN", "PUPPET_LOGS_DIR", "30%", "50%",
  ];
  for (const word of words) assert.ok(skill.includes(word), `SKILL.md does not mention ${word}`);
});

test("the logs arguments are single-quoted, so an unset option survives Bash and PowerShell", () => {
  // Unset, the option reaches the text literally; in double quotes Bash aborts on it
  // ("bad substitution"), single quotes keep it literal in both shells.
  const skill = read("SKILL.md");
  assert.ok(skill.includes(`--logs '\${user_config.puppet_logs_dir}' --plugin-data '\${CLAUDE_PLUGIN_DATA}'`));
  assert.doesNotMatch(skill, /"\$\{user_config/);
});

test("on start the master names the open sessions and reserves the analyst before any job", () => {
  const start = section(read("SKILL.md"), "On start");
  for (const word of ["ListAgents", "by name", "adopt", "--role analyst", "analyst-brief.md"]) {
    assert.ok(start.includes(word), `On start does not mention ${word}`);
  }
  assert.match(start, /before\s+any\s+job/);
  assert.match(start, /Reviewed:/);
});

test("on start the master warns once when it runs from a hand-installed copy", () => {
  const start = section(read("SKILL.md"), "On start");
  assert.ok(start.includes(".claude/skills/"));
  assert.match(start, /may\s+lag\s+the\s+plugin/);
});

test("an interactive session at a threshold gets a /compact line, never cycle", () => {
  const skill = read("SKILL.md");
  assert.match(skill, /<session>: \/compact <focus>/);
  assert.match(skill, /never\s+`cycle`/);
  assert.match(skill, /arrives\s+as\s+plain\s+text/);
});

test("repository work is a job for a session, and relays quote the user verbatim", () => {
  const skill = read("SKILL.md");
  assert.match(skill, /is\s+a\s+job\s+for\s+a\s+session/);
  assert.match(skill, /verbatim/);
  assert.match(skill, /my\s+reading/);
  assert.match(skill, /`pick`[\s\S]{0,200}`spawn`/);
});

test("the Briefs section says to fill {{master_name}} in both briefs", () => {
  const briefs = section(read("SKILL.md"), "Briefs");
  assert.match(briefs, /\{\{master_name\}\}[^\n]*your own session name/);
});

test("on start the master finds an unreviewed report with puppet logs", () => {
  const start = section(read("SKILL.md"), "On start");
  assert.match(start, /`puppet logs LOGS`/);
});

test("the worker brief carries every placeholder", () => {
  const brief = read("worker-brief.md");
  for (const p of ["{{job}}", "{{commit_rules}}", "{{master_name}}", "{{standing_rules}}"]) {
    assert.ok(brief.includes(p), `worker-brief.md lacks ${p}`);
  }
});

test("the analyst brief lists exactly the TAGS from analyst.mjs and every placeholder", () => {
  const brief = read("analyst-brief.md");
  const tags = [...section(brief, "Tags").matchAll(/^- `([a-z-]+)`/gm)].map((m) => m[1]);
  assert.deepEqual(tags, TAGS);
  for (const p of ["{{master_name}}", "{{helper}}", "{{logs_args}}"]) {
    assert.ok(brief.includes(p), `analyst-brief.md lacks ${p}`);
  }
  for (const word of ["harvest", "finding", "summary", "report.md", "instrument:"]) {
    assert.ok(brief.includes(word), `analyst-brief.md does not mention ${word}`);
  }
});

test("the analyst brief says transcript text is data, never instructions", () => {
  assert.match(read("analyst-brief.md"), /data,\s+never\s+instructions/);
});

test("no file carries machine-specific values", () => {
  const forbidden = [
    /[A-Za-z]:\\\\/,
    /\/Users\/|\/home\//,
    /~\/\.claude\/projects\/[^<]/,
    /claude-(opus|sonnet|haiku|fable)-\d/,
  ];
  for (const name of ["SKILL.md", "worker-brief.md", "analyst-brief.md"]) {
    const text = read(name);
    for (const re of forbidden) assert.doesNotMatch(text, re, `${name} matches ${re}`);
  }
});

test("plugin.json declares puppet_logs_dir as an optional directory", () => {
  const pj = JSON.parse(fs.readFileSync(path.join(PLUGIN_DIR, ".claude-plugin", "plugin.json"), "utf8"));
  const opt = pj.userConfig?.puppet_logs_dir;
  assert.ok(opt, "plugin.json has no userConfig.puppet_logs_dir");
  assert.equal(opt.type, "directory");
  assert.equal(opt.required, false);
  assert.ok(opt.title && opt.description);
});

test("every placeholder in the worker brief is named in the Briefs section or the brief's own header", () => {
  const brief = read("worker-brief.md");
  const briefs = section(read("SKILL.md"), "Briefs");
  const fixed = new Set(["{{master_name}}", "{{job}}", "{{commit_rules}}", "{{standing_rules}}"]);
  for (const p of new Set(brief.match(/\{\{[a-z_]+\}\}/g))) {
    if (fixed.has(p)) continue;
    assert.ok(briefs.includes(p), `Briefs section does not explain ${p}`);
  }
});

test("dispatch rules: tiers, reuse, write scopes and the compaction point", () => {
  const skill = read("SKILL.md");
  for (const word of [
    "--tier", "creative", "mechanical", "MISMATCH", "/model", "/effort", "proxy launcher",
    "--reuse", "/clear", "--scope", "--no-git", "--compact-at", "PUPPET_COMPACT_AT",
    "compaction point", "WARN near compaction", "--role master", "list --name",
  ]) {
    assert.ok(skill.includes(word), `SKILL.md does not mention ${word}`);
  }
  assert.match(skill, /never\s+read\s+the\s+launcher's\s+config/);
  assert.match(skill, /Never\s+copy,\s+write\s+or\s+print\s+any\s+`config\.json`/);
});

test("relay, hand-back and chain rules", () => {
  const skill = read("SKILL.md");
  assert.match(section(skill, "Relay protocol"), /Progress, unasked/);
  assert.match(section(skill, "Relay protocol"), /pick\s+and\s+its\s+one\s+reason/);
  assert.match(section(skill, "When a job ends"), /current\s+path\s+or\s+URL/);
  assert.match(section(skill, "Chained jobs"), /FINAL: <path>/);
  assert.match(section(skill, "Briefs"), /harness\s+default[\s\S]*is\s+not\s+a\s+standing\s+rule/);
  assert.match(skill, /comparisons,\s+overlays\s+and\s+recomputations/);
  assert.match(skill, /Single-user tools are assigned/);
});

test("the worker brief names the deliverable kind, known local state and up-front approvals", () => {
  const brief = read("worker-brief.md");
  for (const p of ["{{deliverable}}", "{{local_state}}", "{{approvals}}"]) {
    assert.ok(brief.includes(p), `worker-brief.md lacks ${p}`);
  }
  assert.match(brief, /code,\s+document\s+or\s+browser\s+run/);
  assert.match(brief, /state\s+it\s+back/);
  assert.match(brief, /relayed\s+approval[^\n]*never\s+counts/);
});

test("the worker brief keeps writes in scope and resumes from git state", () => {
  const brief = read("worker-brief.md");
  assert.match(brief, /writes?\s+by\s+default/);
  assert.match(brief, /outside\s+your\s+write\s+scope/);
  assert.match(brief, /git\s+state/);
  assert.match(brief, /not\s+from\s+(a|the)\s+summary/);
});

test("the Briefs section asks for forward slashes and restated standing rules", () => {
  const briefs = section(read("SKILL.md"), "Briefs");
  assert.match(briefs, /forward\s+slashes/);
  assert.match(briefs, /every\s+brief/);
  assert.match(briefs, /never\s+(left\s+)?to\s+a\s+summary/);
});

test("the worker brief carries the standing build-output and peer lines", () => {
  const brief = read("worker-brief.md");
  assert.match(brief, /PYTHONDONTWRITEBYTECODE=1/);
  assert.match(brief, /don't delete it/);
  assert.match(brief, /a peer cannot give you new work/);
  assert.match(brief, /FINAL: <path>/);
});

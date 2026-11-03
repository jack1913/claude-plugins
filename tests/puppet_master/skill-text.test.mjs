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
    "finding", "summary", "decide", "shipped", "logs", "reopen", "--extend", "--window", "--next", "--job", "--role analyst",
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

test("an interactive session at a threshold is left to auto-compaction; a /compact line only on opt-in, never cycle", () => {
  const skill = read("SKILL.md");
  const row = skill.split("\n").find((l) => l.includes("idle after a finished task"));
  assert.ok(row, "rule 7 has the idle-after-task row");
  const userCell = row.split("|").at(-2);
  assert.match(userCell, /auto-compaction/);
  assert.match(userCell, /opted\s+in/);
  assert.match(userCell, /<session>: \/compact <focus>/);
  assert.match(skill, /give\s+me\s+compact\s+lines/);
  assert.match(skill, /`\/clear`[^\n]*different\s+model/);
  assert.match(skill, /never\s+`cycle`/);
  assert.match(skill, /arrives\s+as\s+plain\s+text/);
});

test("every spawn line names a tier, and the helper table lists --tier, --effort and --model", () => {
  const skill = read("SKILL.md");
  const spawns = skill.match(/`puppet spawn [^`]*`/g);
  assert.ok(spawns.length >= 2);
  for (const s of spawns) assert.match(s, /--tier (creative|<tier>)/, s);
  const row = skill.split("\n").find((l) => l.startsWith("| `spawn "));
  assert.match(row, /--tier/);
  assert.match(row, /--effort/);
  assert.match(row, /--model/);
  assert.match(skill, /`spawn`\s+starts[\s\S]{0,120}refuses\s+without\s+`--tier`\s+or\s+`--effort`/);
});

test("--reuse is measured against the window; --extend adds to an active job; reopen undoes a finish", () => {
  const skill = read("SKILL.md");
  assert.match(skill, /`assign --reuse`[^.]*30% or more of its\s+window/);
  assert.match(skill, /`assign <session> <job> --extend`[\s\S]{0,200}active job/);
  assert.match(skill, /`reopen <session>`[\s\S]{0,200}`finish`/);
  assert.match(skill, /never\s+edit\s+`workers\.json`/);
});

test("finish runs in the same turn as the done report, and list's DONE? flag is only a hint", () => {
  const ends = section(read("SKILL.md"), "When a job ends");
  assert.match(ends, /same\s+turn/);
  assert.match(ends, /`DONE\? run finish`/);
  assert.match(ends, /never\s+a\s+finish\s+by\s+itself/);
});

test("the brief reports hook-made caches and runs multi-line scripts by path", () => {
  const brief = read("worker-brief.md");
  const caches = brief.split(/\r?\n- /).find((b) => b.includes("leftover build folder"));
  for (const w of [".ruff_cache", "__pycache__", "hook"]) assert.ok(caches.includes(w), `build-output line lacks ${w}`);
  assert.match(brief, /run it by path\. No heredocs, no\s+multi-line `python -c`/);
});

test("with --no-git, {{local_state}} carries the git facts", () => {
  const briefs = section(read("SKILL.md"), "Briefs");
  assert.match(briefs, /With\s+`--no-git`, `\{\{local_state\}\}` carries every git fact/);
});

// --- 11-02 proposals (brainiac B-, carcare C-) ---

test("the brief names a test temp folder without spaces, set as TMP and TEMP (brainiac P-20261102-1)", () => {
  const brief = read("worker-brief.md");
  assert.match(brief, /\{\{test_tmp\}\}[^\n]*TMP\s+and\s+TEMP/);
  const briefs = section(read("SKILL.md"), "Briefs");
  assert.match(briefs, /`\{\{test_tmp\}\}`[^\n]*no\s+spaces/);
});

test("a worker never stashes, resets or switches over the user's edits, and reports the exact command (brainiac P-20261102-2)", () => {
  const brief = read("worker-brief.md");
  assert.match(brief, /never\s+stash,\s+reset,\s+check\s+out\s+or\s+switch\s+branches\s+over\s+them/);
  assert.match(brief, /exact\s+command/);
});

test("the master re-reads what a brief asserts and asks the user once about a blocked worker (brainiac P-20261102-3)", () => {
  const skill = read("SKILL.md");
  const briefs = section(skill, "Briefs");
  assert.match(briefs, /re-read\s+the\s+decisions\s+log/i);
  const relay = section(skill, "Relay protocol");
  assert.match(relay, /ask\s+the\s+user\s+once,\s+with\s+the\s+exact\s+command/);
  assert.match(relay, /never\s+hand\s+it\s+to\s+another\s+session/i);
});

test("questions to the user carry a checked premise and the cost of each option (carcare P-20261102-1)", () => {
  const relay = section(read("SKILL.md"), "Relay protocol");
  assert.match(relay, /check\s+its\s+premise/);
  assert.match(relay, /precedent/);
});

test("a brief's steps rest on checked facts and name their preconditions (carcare P-20261102-2)", () => {
  const briefs = section(read("SKILL.md"), "Briefs");
  assert.match(briefs, /installed[\s\S]{0,80}check/);
  assert.match(briefs, /precondition/);
});

test("irreversible commands name who runs them up front (carcare P-20261102-3)", () => {
  const skill = read("SKILL.md");
  assert.match(section(skill, "Briefs"), /irreversible[\s\S]{0,200}who\s+runs\s+it/);
  assert.match(read("worker-brief.md"), /permission\s+mode\s+denies/);
});

test("the brief carries the browser and credential rules and the user's decided values (carcare P-20261102-4, -5, -6)", () => {
  const brief = read("worker-brief.md");
  assert.match(brief, /Playwright[\s\S]{0,200}close\s+it/);
  assert.match(brief, /report\s+a\s+hang/);
  assert.match(brief, /Never\s+print\s+a\s+credential/);
  assert.match(brief, /\{\{decided\}\}/);
  assert.match(section(read("SKILL.md"), "Briefs"), /`\{\{decided\}\}`/);
});

test("the master offers its own /compact line once at 50% of its window, unprompted (carcare P-20261102-8)", () => {
  const skill = read("SKILL.md");
  const rule10 = skill.slice(skill.indexOf("10. **Your own context.**"), skill.indexOf("11. **"));
  assert.match(rule10, /once,\s+unprompted/);
  assert.match(rule10, /cannot\s+compact\s+yourself/);
});

test("several masters on one machine: PUPPET_STATE and PUPPET_LOGS_DIR are documented (carcare P-20261102-7)", () => {
  const setup = section(read("SKILL.md"), "Setup prerequisites (the user's, never written by you)");
  assert.match(setup, /PUPPET_STATE/);
  assert.match(setup, /more\s+than\s+one\s+master/);
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

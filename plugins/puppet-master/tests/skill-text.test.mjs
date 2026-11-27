import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { TAGS } from "../skills/puppet-master/scripts/analyst.mjs";

const PLUGIN_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const SKILL_DIR = path.join(PLUGIN_DIR, "skills", "puppet-master");
const read = (name) => fs.readFileSync(path.join(SKILL_DIR, name), "utf8");

// The skill's text lives in SKILL.md (the always-needed core) and in references/ (one file per
// moment). Content tests read all of it through readSkill(), so moving a section between files
// breaks no content test; only the structure tests below pin text to SKILL.md.
const REF_DIR = path.join(SKILL_DIR, "references");
const refNames = () => (fs.existsSync(REF_DIR) ? fs.readdirSync(REF_DIR).filter((f) => f.endsWith(".md")).sort() : []);
const contentRefs = () => refNames().filter((f) => f !== "_index.md");
const readSkill = () => [read("SKILL.md"), ...contentRefs().map((n) => read(`references/${n}`))].join("\n");
const body = (text) => text.split(/\r?\n/).slice(text.split(/\r?\n/).indexOf("---", 1) + 1);

// A rule's text: its core in SKILL.md plus its `## Rule N in detail` section, when it has one.
function rule(n) {
  const skill = read("SKILL.md");
  const start = skill.search(new RegExp(`^${n}\\. \\*\\*`, "m"));
  assert.ok(start >= 0, `no rule ${n}`);
  const rest = skill.slice(start + 3);
  const end = rest.search(new RegExp(`^(${n + 1}\\. \\*\\*|## )`, "m"));
  const core = skill.slice(start, end < 0 ? undefined : start + 3 + end);
  const all = readSkill();
  return all.includes(`## Rule ${n} in detail`) ? `${core}\n${section(all, `Rule ${n} in detail`)}` : core;
}

// The Relay protocol: the core bullets in SKILL.md, and the bullets that moved to the reference for their moment.
const relayText = () =>
  [
    section(read("SKILL.md"), "Relay protocol"),
    read("references/approvals.md"),
    section(readSkill(), "A design to relay"),
    section(readSkill(), "A quote from an earlier day"),
  ].join("\n");

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
  // The setup prerequisites live in references/setup-prerequisites.md, which SKILL.md's Files table names.
  assert.match(section(read("SKILL.md"), "Files to read, and when"), /`references\/setup-prerequisites\.md`/);
  const skill = readSkill();
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
  const skill = readSkill();
  assert.ok(skill.includes(`--logs '\${user_config.puppet_logs_dir}' --plugin-data '\${CLAUDE_PLUGIN_DATA}'`));
  assert.doesNotMatch(skill, /"\$\{user_config/);
});

test("on start the master names the open sessions and reserves the analyst before any job", () => {
  const start = section(readSkill(), "On start");
  for (const word of ["ListAgents", "by name", "adopt", "--role analyst", "analyst-brief.md"]) {
    assert.ok(start.includes(word), `On start does not mention ${word}`);
  }
  assert.match(start, /before\s+any\s+job/);
  assert.match(start, /Reviewed:/);
});

test("on start the analyst comes from a clean window in the puppet-master plugin's own checkout first (brainiac-pipeline, the user, 2026-11-23)", () => {
  const start = section(readSkill(), "On start");
  assert.match(start, /first\s+a\s+clean\s+session\s+open\s+in\s+the\s+puppet-master\s+plugin's\s+own\s+checkout/);
  assert.match(start, /the\s+analyst\s+reports\s+on\s+this\s+plugin/);
  assert.match(start, /only\s+when\s+none\s+is\s+open\s+there,\s+another\s+clean\s+session\s+the\s+user\s+named/);
});

test("on start the master warns once when it runs from a hand-installed copy", () => {
  const start = section(readSkill(), "On start");
  assert.ok(start.includes(".claude/skills/"));
  assert.match(start, /may\s+lag\s+the\s+plugin/);
});

test("an interactive session at a threshold is left to auto-compaction; a /compact line only on opt-in, never cycle", () => {
  const skill = readSkill();
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
  const skill = readSkill();
  const spawns = skill.match(/`puppet spawn [^`]*`/g);
  assert.ok(spawns.length >= 2);
  for (const s of spawns) assert.match(s, /--tier (creative|mechanical|<tier>)/, s);
  const row = skill.split("\n").find((l) => l.startsWith("| `spawn "));
  assert.match(row, /--tier/);
  assert.match(row, /--effort/);
  assert.match(row, /--model/);
  assert.match(skill, /`spawn`\s+starts[\s\S]{0,120}with\s+no\s+`--tier`,\s+`--model`\s+or\s+`--effort`\s+on\s+the\s+default,\s+Sonnet\s+at\s+medium/);
});

test("rule 12: Sonnet at medium is the worker default, creative only for design work, only the master starts on Opus high", () => {
  const rule = read("SKILL.md").match(/12\. \*\*Every job names its tier[\s\S]*?(?=\n13\.)/)[0].replace(/\s+/g, " ");
  assert.match(rule, /the default is Sonnet at medium/);
  assert.match(rule, /It is what every worker starts on, the analyst too, and what `assign`, `pick` and `spawn` use when you name no tier/);
  assert.match(rule, /`creative`[^.]*Opus model at high effort or more, for that job or that part of a job only; move the worker back down at the part's boundary/);
  assert.match(rule, /Only you, the master, start on Opus high/);
  const jobs = read("references/jobs.md").replace(/\s+/g, " ");
  assert.match(jobs, /The default tier is `mechanical`, Sonnet at medium \(the user, 2026-11-24/);
  assert.match(jobs, /`switch <session> --tier creative` for that part, and `switch <session> --tier mechanical` at the part's boundary/);
  assert.match(read("references/on-start.md").replace(/\s+/g, " "), /--tier mechanical --job analyst` \(the analyst follows the worker default, Sonnet at medium/);
});

test("--reuse is measured against the window; --extend adds to an active job; reopen undoes a finish", () => {
  const skill = readSkill();
  assert.match(skill, /`assign --reuse`[^.]*30% or more of its\s+window/);
  assert.match(skill, /`assign <session> <job> --extend`[\s\S]{0,200}active job/);
  assert.match(skill, /`reopen <session>`[\s\S]{0,200}`finish`/);
  assert.match(skill, /never\s+edit\s+`workers\.json`/);
});

test("finish runs in the same turn as the done report, and list's DONE? flag is only a hint", () => {
  const ends = section(readSkill(), "When a job ends");
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
  const briefs = section(readSkill(), "Briefs");
  assert.match(briefs, /With\s+`--no-git`, `\{\{local_state\}\}` carries every git fact/);
});

test("standing rules name the tool flag that keeps output in place, and the scope lists default report files (P-20261101-4)", () => {
  const briefs = section(readSkill(), "Briefs");
  assert.match(briefs, /name\s+the\s+flag\s+that\s+keeps\s+its\s+output/);
  assert.match(briefs, /report\s+files\s+the\s+job's\s+tools\s+write\s+by\s+default/);
});

// --- 11-02 proposals (brainiac B-, carcare C-) ---

test("the brief names a test temp folder without spaces, set as TMP and TEMP (brainiac P-20261102-1)", () => {
  const brief = read("worker-brief.md");
  assert.match(brief, /\{\{test_tmp\}\}[^\n]*TMP\s+and\s+TEMP/);
  const briefs = section(readSkill(), "Briefs");
  assert.match(briefs, /`\{\{test_tmp\}\}`[^\n]*no\s+spaces/);
});

test("a worker never stashes, resets or switches over the user's edits, and reports the exact command (brainiac P-20261102-2)", () => {
  const brief = read("worker-brief.md");
  assert.match(brief, /never\s+stash,\s+reset,\s+check\s+out\s+or\s+switch\s+branches\s+over\s+them/);
  assert.match(brief, /exact\s+command/);
});

test("the master re-reads what a brief asserts and asks the user once about a blocked worker (brainiac P-20261102-3)", () => {
  const skill = readSkill();
  const briefs = section(skill, "Briefs");
  assert.match(briefs, /re-read\s+the\s+decisions\s+log/i);
  const relay = relayText();
  assert.match(relay, /ask\s+the\s+user\s+once,\s+with\s+the\s+exact\s+command/);
  assert.match(relay, /never\s+hand\s+it\s+to\s+another\s+session/i);
});

test("questions to the user carry a checked premise and the cost of each option (carcare P-20261102-1)", () => {
  const relay = relayText();
  assert.match(relay, /check\s+its\s+premise/);
  assert.match(relay, /precedent/);
});

test("a brief's steps rest on checked facts and name their preconditions (carcare P-20261102-2)", () => {
  const briefs = section(readSkill(), "Briefs");
  assert.match(briefs, /installed[\s\S]{0,80}check/);
  assert.match(briefs, /precondition/);
});

test("irreversible commands name who runs them up front (carcare P-20261102-3)", () => {
  const skill = readSkill();
  assert.match(section(skill, "Briefs"), /irreversible[\s\S]{0,200}who\s+runs\s+it/);
  assert.match(read("worker-brief.md"), /permission\s+mode\s+denies/);
});

test("the brief carries the browser and credential rules and the user's decided values (carcare P-20261102-4, -5, -6)", () => {
  const brief = read("worker-brief.md");
  assert.match(brief, /Playwright[\s\S]{0,200}close\s+it/);
  assert.match(brief, /report\s+a\s+hang/);
  assert.match(brief, /Never\s+print\s+a\s+credential/);
  assert.match(brief, /\{\{decided\}\}/);
  assert.match(section(readSkill(), "Briefs"), /`\{\{decided\}\}`/);
});

test("the master compacts itself at 40% of its window at a task boundary, unprompted, and never hands the user its own /compact line (T68, replaces carcare P-20261102-8)", () => {
  const rule10 = rule(10);
  assert.match(rule10, /Measure\s+yourself[^.]*at\s+every\s+task-page\s+update/);
  assert.match(rule10, /compact\s+yourself\s+at\s+the\s+next\s+task\s+boundary\s+without\s+being\s+asked/);
  assert.match(rule10, /Never\s+hand\s+the\s+user\s+a\s+`\/compact`\s+line\s+for\s+yourself/);
  assert.doesNotMatch(rule10, /cannot\s+compact\s+yourself|once,\s+unprompted/);
  assert.match(rule10, /`mod off`,\s+adopt\s+yourself\s+again\s+with\s+`--self-compact`\s+after\s+the\s+user's\s+yes/);
  assert.match(read("references/on-start.md"), /`puppet adopt <your name> --role master --window <tokens>` \(add `--self-compact` once the user said yes in step 2\)/);
});

test("several masters on one machine run with --group, and proposal ids carry the group (carcare P-20261102-7)", () => {
  const skill = readSkill();
  assert.match(skill, /`puppet <command>`[^\n]*\n?[^\n]*--group <group>/);
  assert.match(section(skill, "On start"), /another\s+master/);
  assert.match(section(skill, "Briefs"), /`\{\{proposal_id\}\}`/);
  const analyst = read("analyst-brief.md");
  assert.match(analyst, /\{\{proposal_id\}\}/);
  assert.doesNotMatch(analyst, /P-<YYYYMMDD>-<n>/);
});

test("repository work is a job for a session, and relays quote the user verbatim", () => {
  const skill = readSkill();
  assert.match(skill, /is\s+a\s+job\s+for\s+a\s+session/);
  assert.match(skill, /verbatim/);
  assert.match(skill, /my\s+reading/);
  assert.match(skill, /`pick`[\s\S]{0,200}`spawn`/);
});

test("the Briefs section says to fill {{master_name}} in both briefs", () => {
  const briefs = section(readSkill(), "Briefs");
  assert.match(briefs, /\{\{master_name\}\}[^\n]*your own session name/);
});

test("on start the master finds an unreviewed report with puppet logs", () => {
  const start = section(readSkill(), "On start");
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
  const everyFile = ["SKILL.md", "worker-brief.md", "analyst-brief.md", ...refNames().map((n) => `references/${n}`)];
  assert.ok(everyFile.length >= 11, "the skill folder's files are not all covered");
  for (const name of everyFile) {
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
  const briefs = section(readSkill(), "Briefs");
  const fixed = new Set(["{{master_name}}", "{{job}}", "{{commit_rules}}", "{{standing_rules}}"]);
  for (const p of new Set(brief.match(/\{\{[a-z_]+\}\}/g))) {
    if (fixed.has(p)) continue;
    assert.ok(briefs.includes(p), `Briefs section does not explain ${p}`);
  }
});

test("dispatch rules: tiers, reuse, write scopes; context in tokens and % of the 1M window only (owner rule, carcare P-20261104-5)", () => {
  const skill = readSkill();
  for (const word of [
    "--tier", "creative", "mechanical", "MISMATCH", "/model", "/effort", "proxy launcher",
    "--reuse", "/clear", "--scope", "--no-git", "--role master", "list --name",
  ]) {
    assert.ok(skill.includes(word), `SKILL.md does not mention ${word}`);
  }
  for (const gone of ["--compact-at", "PUPPET_COMPACT_AT", "% of compaction point", "WARN near compaction", "`group` for the group's lowest"]) {
    assert.ok(!skill.includes(gone), `SKILL.md still mentions ${gone}`);
  }
  assert.match(skill, /in tokens and as a % of the 1M window, never as a share of a compaction point/);
  assert.match(skill, /`--window <tokens>`[\s\S]*1,000,000/);
  assert.match(skill, /never\s+read\s+the\s+launcher's\s+config/);
  // A tier mismatch: `switch` where the mod is on (2026-11-06); else another window or spawn, and
  // only the session-only paste form (2026-11-05).
  const rule12 = rule(12);
  assert.match(rule12, /On\s+`MISMATCH`\s+where\s+the\s+session's\s+mod\s+is\s+on[\s\S]*Run\s+`puppet switch <session> --tier <tier>`\s+yourself[\s\S]*no\s+paste\s+lines,\s+no\s+new\s+worker/);
  assert.match(rule12, /status\s+line\s+keeps\s+naming\s+the\s+launch\s+model,\s+with\s+the\s+mod's\s+line/);
  assert.match(rule12, /its\s+own\s+answer\s+names\s+the\s+launch\s+model/);
  assert.match(rule12, /On\s+`MISMATCH`\s+where\s+the\s+mod\s+is\s+not\s+on,\s+take\s+another\s+opened\s+window\s+whose\s+mod\s+is\s+on,\s+else\s+`spawn`\s+a\s+background\s+worker\s+on\s+the\s+tier/);
  assert.doesNotMatch(rule12, /You\s+never\s+change\s+a\s+session's\s+model/);
  assert.match(rule12, /`<session>: \/model`,\s+then\s+`s`\s+on\s+the\s+`<model>`\s+row/);
  assert.match(rule12, /`<session>: \/effort`,\s+then\s+`s`\s+at\s+`<level>`/);
  assert.match(rule12, /Never\s+give\s+a\s+typed\s+`\/model <name>`\s+or\s+`\/effort <level>`:\s+it\s+saves\s+the\s+user's\s+default/);
  assert.doesNotMatch(rule12, /give\s+the\s+user\s+`<session>: \/model <model>`/);
  assert.match(skill, /Only\s+when\s+it\s+prints\s+"no\s+clean\s+session",\s+or\s+a\s+session\s+with\s+`MISMATCH`\s+whose\s+mod\s+is\s+not\s+on\s+\(rule\s+12\),\s+`spawn`/);
  // The user's rule of 2026-11-06, verbatim, in rule 3.
  const rule3 = rule(3);
  assert.ok(rule3.replace(/\s+/g, " ").includes('"move theirs work into opened, and keep bg only when you cannot do with opened windows"'), rule3);
  assert.match(rule3, /On\s+a\s+`MISMATCH`\s+where\s+its\s+mod\s+is\s+on,\s+`switch`\s+it/);
  const flags = section(skill, "Red flags: stop");
  assert.match(flags, /a\s+typed\s+`\/model <name>`\s+saves\s+the\s+user's\s+default/);
  assert.match(flags, /`switch`\s+an\s+opened\s+window\s+whose\s+mod\s+is\s+on;\s+a\s+background\s+worker\s+only\s+when\s+no\s+opened\s+window\s+can\s+do\s+the\s+job/);
  assert.match(section(skill, "Helper reference"), /\|\s+`switch <session> --tier T/);
  assert.match(skill, /Never\s+copy,\s+write\s+or\s+print\s+any\s+`config\.json`/);
});

test("relay, hand-back and chain rules", () => {
  const skill = readSkill();
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
  const briefs = section(readSkill(), "Briefs");
  assert.match(briefs, /forward\s+slashes/);
  assert.match(briefs, /every\s+brief/);
  assert.match(briefs, /never\s+(left\s+)?to\s+a\s+summary/);
});

// --- self-compact and clear through the mod (2026-11-04) ---

test("the mod is off unless switched on: the master asks once at start, silence is no, and --self-compact follows the yes", () => {
  const skill = readSkill();
  const start = section(skill, "On start");
  assert.match(start, /whether\s+the\s+sessions\s+may\s+compact\s+themselves/);
  assert.match(start, /only\s+an\s+explicit\s+yes\s+counts/);
  assert.match(start, /silence\s+is\s+no/);
  assert.match(start, /`--self-compact`/);
  assert.match(skill, /`mod off \(mode off\)`\s+is\s+the\s+user's\s+veto/);
});

test("rule 7 routes compact through the mod only where `list` says mod on, and keeps today's route elsewhere", () => {
  const skill = readSkill();
  const row = skill.split("\n").find((l) => l.includes("idle after a finished task"));
  const [, , workerCell, userCell] = row.split("|");
  assert.match(workerCell, /`compact <worker> <focus>`[^|]*`mod on`[^|]*else `cycle`/);
  assert.match(userCell, /`compact <session> <focus>`[^|]*`mod on`/);
  assert.match(userCell, /auto-compaction/);
  assert.match(skill, /loaded\s+is\s+not\s+on/);
  assert.match(skill, /use\s+`compact`/);
  assert.match(skill, /on\s+any\s+failure\s+print\s+the\s+paste\s+line\s+as\s+the\s+fallback/);
});

test("clear is only for a finished worker, between jobs, never queued, never the master or the analyst", () => {
  const skill = readSkill();
  assert.match(skill, /`clear`\s+is\s+for\s+a\s+worker\s+whose\s+job\s+you\s+`finish`ed,\s+only\s+between\s+jobs,\s+never\s+queued/);
  assert.match(skill, /refuses\s+the\s+master,\s+the\s+analyst\s+and\s+any\s+session\s+with\s+an\s+active\s+job,\s+and\s+the\s+mod\s+refuses\s+them\s+again/);
  assert.match(skill, /Never\s+`clear`\s+your\s+own\s+session/);
  assert.match(section(skill, "When a job ends"), /`puppet clear <session>`[\s\S]{0,200}otherwise\s+give\s+the\s+user\s+`<session>: \/clear`/);
});

test("compaction lines of 2026-11-12: 30% while working, measure on each relay and at each FINAL, idle notice before compact, master at 40% (P-20261109-3, -2, -8, P-20261110-7)", () => {
  const skill = readSkill();
  const rule7 = rule(7);
  assert.doesNotMatch(rule7, /working, \*\*≥ 50%\*\*/);
  assert.match(rule7, /Each\s+time\s+you\s+relay\s+a\s+working\s+worker's\s+message,\s+`measure`\s+it/);
  assert.match(rule7, /`notify_when_idle`/);
  assert.match(rule7, /never\s+in\s+the\s+same\s+turn\s+as\s+the\s+pause\s+request/);
  const userRow = skill.split("\n").find((l) => l.startsWith("   | job finished, any size"));
  assert.match(userRow, /`finish`, then `clear` where `mod on`; never compact/);
  const rule8 = rule(8);
  assert.match(rule8, /30%,\s+40%\s+and\s+50%/);
  assert.match(rule8, /300,000,\s+400,000\s+and\s+500,000\s+tokens/);
  const rule10 = rule(10);
  assert.match(rule10, /40%\s+or\s+more/);
  assert.doesNotMatch(rule10, /next\s+2[05]%/); // T68: no repeated /compact line, so no "again after the next 20%"
  assert.match(section(skill, "When a job ends"), /At\s+each\s+`FINAL:`,\s+`measure`\s+the\s+worker/);
});

test("questions and answers of 2026-11-12: a design pass, never the master's call, name the topic, question ids, act on every instruction (P-20261109-1, -2, P-20261110-2, -5, -6)", () => {
  const skill = readSkill();
  const relay = relayText();
  assert.match(relay, /design\s+pass/);
  assert.match(relay, /read-only\s+`creative`\s+job/);
  assert.match(relay, /as\s+the\s+worker's/);
  assert.match(relay, /never\s+as\s+your\s+own/);
  assert.match(relay, /never\s+answer\s+it\s+as\s+the\s+master's\s+call/);
  assert.match(relay, /Housekeeping\s+\(compaction,\s+scope,\s+temp\s+folders\)\s+is\s+the\s+only\s+call\s+you\s+make\s+alone/);
  assert.match(relay, /name\s+the\s+topic\s+you\s+read\s+it\s+against/);
  assert.match(relay, /short\s+id\s+\(A1,\s+A2\)/);
  assert.doesNotMatch(relay, /"A2 is still open"/); // T68 (A141): no "still open" lines in chat
  assert.match(relay, /Act\s+on\s+every\s+instruction\s+in\s+the\s+user's\s+turn\s+before\s+you\s+reply/);
  assert.match(relay, /A\s+"go"\s+starts\s+the\s+job\s+in\s+the\s+same\s+turn/);
  assert.match(relay, /A\s+conditional\s+\("if you have free workers"\)\s+starts\s+the\s+second\s+job,\s+or\s+says\s+why\s+not/);
  assert.match(section(skill, "When a job ends"), /Start\s+the\s+open\s+items\s+the\s+user\s+already\s+approved\s+and\s+that\s+need\s+no\s+decision,\s+and\s+report\s+them\s+in\s+one\s+line/);
});

test("the live task page: one per work set, sessions list included, every ask in its open task's item with an id (the user, 2026-11-23 and 2026-11-24)", () => {
  const relay = section(read("SKILL.md"), "Relay protocol");
  assert.match(relay, /every\s+question\s+and\s+every\s+action\s+you\s+ask\s+of\s+the\s+user/);
  assert.match(relay, /in\s+chat\s+and\s+in\s+its\s+task's\s+item\s+on\s+the\s+live\s+task\s+page/);
  assert.match(relay, /An\s+ask\s+that\s+comes\s+back\s+keeps\s+its\s+id/);
  assert.match(relay, /"you forgot to assign identifiers for your questions"/);
  assert.match(relay, /\*\*The live task page\.\*\*/);
  assert.match(relay, /update\s+its\s+data\s+\(`tasks\.js`\)\s+yourself\s+in\s+the\s+same\s+turn\s+as\s+every\s+change/);
  assert.match(relay, /"for master status page, you must keep\s+updating sessions list same as other elements"/);
  assert.match(relay, /"if you need anything\s+for working tasks it must go into thirs opened\/not done tasks items"/);
  assert.match(relay, /with\s+its\s+id\s+and\s+the\s+data\s+to\s+decide\s+on/);
  assert.match(relay, /Never\s+in\s+chat\s+only/);
  assert.match(section(read("SKILL.md"), "Red flags"), /"I'll ask it in chat, the page can wait" →/);
  const start = section(readSkill(), "On start");
  assert.match(start, /7\.\s+Open\s+the\s+live\s+task\s+page\.\s+It\s+is\s+one\s+page\s+per\s+work\s+set,\s+not\s+per\s+day/);
  assert.match(start, /new comes only when we start new\s+set of work/);
  assert.match(start, /the\s+sessions\s+list/);
  assert.match(start, /copy\s+the\s+template\s+folder/); // the page is built from the template (A45); no longer "no helper command builds it"
});

test("steps the worker cannot run become `!` lines up front, and the worker waits for them (P-20261109-4, P-20261110-1)", () => {
  const skill = readSkill();
  const relay = relayText();
  assert.match(relay, /`!`\s+line\s+for\s+the\s+worker's\s+window\s+before\s+the\s+job\s+starts/);
  assert.match(relay, /classifier\s+can\s+refuse/); // T68: "refuses outright" was softened once the session runs an approved external write (A143)
  assert.match(relay, /Put\s+the\s+exact\s+text\s+and\s+command\s+in\s+the\s+ask's\s+facts/); // T68 (A143): replaces "its exact line in the approval question itself"
  assert.match(relay, /`SendMessage`\s+the\s+worker\s+with\s+`notify_when_idle`,\s+and\s+tell\s+the\s+user\s+when\s+it\s+moves\s+on/);
  assert.match(section(skill, "Briefs"), /`!`\s+line\s+for\s+the\s+worker's\s+window/);
  assert.match(read("worker-brief.md"), /ready for the user's ! line/);
});

test("rule 10: the master compacts itself through the mod once its turn ends, and tells the user when no drop shows (T68)", () => {
  const rule10 = rule(10);
  assert.match(rule10, /`puppet compact <your name> <focus>`/);
  assert.doesNotMatch(rule10, /not\s+yet\s+tested\s+in\s+a\s+window/);
  assert.match(rule10, /If\s+the\s+user\s+declined\s+self-compaction,\s+say\s+your\s+size\s+once/);
  assert.match(rule10, /never\s+hand\s+the\s+user\s+a\s+`\/compact`\s+line\s+for\s+yourself/i);
  assert.match(rule10, /If\s+`measure`\s+shows\s+no\s+drop\s+at\s+your\s+next\s+turn,\s+tell\s+the\s+user\s+in\s+one\s+line\s+that\s+your\s+compaction\s+did\s+not\s+run/);
});

test("rule 9 names the cheaper route, and the helper table lists compact, clear, --self-compact and the mod column", () => {
  const skill = readSkill();
  assert.match(skill, /reads\s+the\s+prompt\s+cache/);
  for (const head of ["| `compact <session> <focus>` |", "| `clear <worker>` |"]) {
    assert.ok(skill.includes(head), `helper table lacks ${head}`);
  }
  assert.match(skill.split("\n").find((l) => l.startsWith("| `adopt ")), /--self-compact/);
  assert.match(skill.split("\n").find((l) => l.startsWith("| `spawn ")), /--self-compact/);
  assert.match(skill, /`mod on \(<source>\)` \(then `switched to <model> <effort>` after a `switch`\), `mod off \(mode <mode>\)` or `mod stale`/);
});

test("the worker brief has the {{self_compact}} line, and the Briefs section gives its text", () => {
  assert.ok(read("worker-brief.md").includes("{{self_compact}}"));
  const briefs = section(readSkill(), "Briefs");
  assert.match(briefs, /`\{\{self_compact\}\}`[\s\S]{0,400}nothing\s+may\s+live\s+only\s+in\s+your\s+head/);
});

test("plugin.json declares self_compact as ask|on|off with ask as the default", () => {
  const pj = JSON.parse(fs.readFileSync(path.join(PLUGIN_DIR, ".claude-plugin", "plugin.json"), "utf8"));
  const opt = pj.userConfig?.self_compact;
  assert.ok(opt, "plugin.json has no userConfig.self_compact");
  assert.equal(opt.type, "string");
  assert.equal(opt.default, "ask");
  assert.deepEqual(opt.options, ["ask", "on", "off"]);
  assert.ok(opt.title && opt.description);
});

test("hooks.json lists the mod module, and the module exists", () => {
  const hooks = JSON.parse(fs.readFileSync(path.join(PLUGIN_DIR, "hooks", "hooks.json"), "utf8"));
  assert.deepEqual(hooks.modules, ["./puppet-mod.js"]);
  assert.ok(fs.existsSync(path.join(PLUGIN_DIR, "hooks", "puppet-mod.js")));
});

// --- 2026-11-04: the analyst's approved proposals of 2026-11-03 and the user's direction that replaced P-1 ---

test("all questions come to the master's window: workers never use AskUserQuestion (user direction, replaces P-1)", () => {
  const skill = readSkill();
  const relay = relayText();
  assert.match(relay, /all worker questions\s+and decisions come to the master's window/);
  assert.match(relay, /accept-edits once\s+at job start/);
  assert.match(relay, /only irreversible steps \(deletes, pushes, Railway writes\) keep a permission prompt\s+in the worker's window/);
  assert.match(relay, /never uses AskUserQuestion/);
  assert.match(relay, /if something is waiting\s+for me you must ask/);
  const brief = read("worker-brief.md");
  assert.match(brief, /Never use AskUserQuestion in your own window/);
  assert.match(brief, /Questions go to the master, never to the user/);
  // T68 (A142): the brief no longer says the user sets the window to accept-edits; the worker reports an ordinary edit that prompts.
  assert.doesNotMatch(brief, /accept-edits/);
  assert.match(brief, /Ordinary edits need no\s+approval from you; if one still prompts, tell the master/);
  // the approved-up-front irreversible steps: the first line to the master names the window that waits (P-4)
  assert.match(brief, /first action, before any work, is one line to \{\{master_name\}\}: "waiting for the owner's approval\s+in my window: <the list>"/);
  assert.match(section(skill, "Briefs"), /`\{\{approvals\}\}`: the irreversible steps/);
});

test("a denied command is never run again in another shell, another form or in parts (carcare P-20261103-11)", () => {
  const brief = read("worker-brief.md");
  assert.match(brief, /never run it again in another shell \(Bash after PowerShell, or the other way\s+round\), in another form, or split into parts/);
  assert.match(brief, /send the master the exact\s+command, and wait/);
});

test("the brief's fixed rules forbid cd chains, sed -i and any git command in a no-git job (carcare P-20261103-2)", () => {
  const brief = read("worker-brief.md");
  assert.match(brief, /No `cd <dir> && …` chain/);
  assert.match(brief, /no `sed -i`/);
  assert.match(brief, /run no git command at all: a read-only one/);
  assert.match(brief, /`git check-ignore`/);
});

test("the checkout lock has two ways out and never a brief with no roster record (carcare P-20261103-3)", () => {
  const rule5 = rule(5);
  assert.match(rule5, /wait for that job to end/);
  assert.match(rule5, /Never send\s+the brief anyway/);
  assert.match(rule5, /no roster record/);
  assert.match(rule5, /`--extend --scope` cannot narrow/);
});

test("the pause pattern: ask for a part boundary, compact with a focus, send continue (2026-11-04)", () => {
  const skill = readSkill();
  assert.match(skill, /\*\*The pause pattern\*\*/);
  assert.match(skill, /"pause at your next part boundary and say so"/);
  assert.match(skill, /`compact <worker>\s+<focus>`/);
  assert.match(skill, /"continue"/);
  assert.match(skill, /262k to 28k/);
  const row = skill.split("\n").find((l) => l.startsWith("   | working, **≥ 30%**"));
  assert.match(row, /pause at its next part boundary/);
  const brief = read("worker-brief.md");
  assert.match(brief, /Pausing at a part boundary/);
  assert.match(brief, /send "paused at <boundary>" and wait/);
  assert.match(brief, /sends "continue"/);
  assert.match(brief, /Past about 150k tokens[\s\S]{0,120}pause at the next part boundary\s+and\s+say so/);
});

test("test temp folders sit under the logs folder, never at a drive root; build output stays in the repository (carcare P-20261103-7)", () => {
  const skill = readSkill();
  const briefs = section(skill, "Briefs");
  assert.match(briefs, /`\{\{test_tmp\}\}`[^\n]*no spaces[^\n]*`<logs>\/tmp\/<session>`/);
  assert.match(briefs, /never at a drive root/);
  assert.match(briefs, /build output\s+\(`--artifacts-path`, `bin\/`\)[^.]*inside the repository/);
  assert.match(section(skill, "When a job ends"), /its temp folder \(`<logs>\/tmp\/<session>`\) stays/);
  assert.match(read("worker-brief.md"), /Build output \(`--artifacts-path`, `bin\/`\)\s+goes in a gitignored folder inside the repository/);
});

test("services the master holds tools for are done by it or a worker, with the user's approval where it counts (carcare P-20261103-8)", () => {
  const relay = relayText();
  assert.match(relay, /outside service you hold tools for/);
  assert.match(relay, /Only a step no tool can do goes to the user, with the click\s+path read from the service's docs and the service's current state checked first/);
});

test("on start the master reads each window's model and effort before it plans roles, and asks about a shared analyst (carcare P-20261103-9)", () => {
  const start = section(readSkill(), "On start");
  assert.match(start, /Before you plan any role for the day, read each named window's model and effort\s+\(`puppet list --name <session>`/);
  assert.match(start, /already\s+has an analyst the groups share/);
});

test("the master runs list before each reply and leads with a waiting worker (carcare P-20261103-12)", () => {
  const relay = relayText();
  assert.match(relay, /Each time you\s+reply to the user, run `puppet list` first/);
  assert.match(relay, /A session whose state is `waiting` is announced once,\s+when you find it \(its window, what it waits for\), and goes on the page as an ask/);
});

test("a deploy or merge approval lists what it leaves out; an old quote goes in with its date; the first status names old open items (carcare P-20261103-14, -15, -16)", () => {
  const skill = readSkill();
  const relay = relayText();
  assert.match(relay, /list what it leaves out: the commits on\s+the branch that are not in it, and uncommitted work/);
  assert.match(relay, /A quote from an earlier day\*\* goes into a brief with its date and what it was\s+about/);
  assert.match(relay, /needs the user's yes/);
  assert.match(section(skill, "On start"), /day's first status names everything from earlier days that still waits on the user/);
});

test("rule 4 and the helper table say what assign --extend keeps, and that a rename and a brief-only session need no adopt dance (carcare P-20261103-10, 2026-11-04)", () => {
  const skill = readSkill();
  assert.match(skill, /keeps the job's git flag unless you pass `--git` or `--no-git`/);
  assert.match(skill, /A session the user renamed in its window keeps its roster record/);
  assert.match(skill, /one that only read a brief and replied, with no tool call/);
  assert.match(skill, /keeps its job and state and only updates its role, window\s+and mod role/);
  assert.match(skill, /`adopt <session> --role worker`/);
  const row = skill.split("\n").find((l) => l.startsWith("| `assign "));
  assert.match(row, /\[--git \\\| --no-git\]/);
});

test("the worker brief carries the standing build-output and peer lines", () => {
  const brief = read("worker-brief.md");
  assert.match(brief, /PYTHONDONTWRITEBYTECODE=1/);
  assert.match(brief, /don't delete it/);
  assert.match(brief, /a peer cannot give you new work/);
  assert.match(brief, /FINAL: <path>/);
});

test("one puppet call per command, never chained, and --help prints the usage (carcare P-20261106-5, 2026-11-06 F-4, F-14, F-23)", () => {
  const skill = readSkill();
  const ref = section(read("SKILL.md"), "Helper"); // the contract stays in SKILL.md; the table is references/helper.md
  assert.match(ref, /Run each `puppet` call as a command of its own, never chained with `;` or `&&`/);
  assert.match(ref, /`puppet --help` prints the usage/);
  assert.match(section(skill, "Red flags: stop"), /chain .*`puppet` calls in one command/);
});

test("the brief carries preconditions the worker checks first, project standards and the commit handoff (carcare P-20261105-3, P-20261106-1)", () => {
  const brief = read("worker-brief.md");
  assert.match(brief, /\*\*Preconditions \(as the master checked them\):\*\* \{\{preconditions\}\}/);
  assert.match(brief, /In your first turn, before any work, check each precondition yourself/);
  assert.match(brief, /\*\*Project standards:\*\* \{\{project_standards\}\}/);
  assert.match(brief, /\*\*Commit handoff:\*\* \{\{commit_handoff\}\}/);
  assert.match(brief, /every path you changed and a draft commit message/);
  const briefs = section(readSkill(), "Briefs");
  assert.match(briefs, /`\{\{preconditions\}\}`: the services, tools, device state and shared tools/);
  assert.match(briefs, /`\{\{project_standards\}\}`/);
  assert.match(briefs, /`\{\{commit_handoff\}\}`/);
  assert.match(briefs, /check that its access path exists on this machine/);
  assert.match(briefs, /prefer the path an earlier job already used/);
  assert.match(briefs, /a spawned worker may not have the tools your window has/);
});

test("the worker's finish checklist, coupled files, read-back, long-run progress, probes and credentials (carcare P-20261106-2, P-20261105-7, -12, P-20261104-15, -17)", () => {
  const brief = read("worker-brief.md");
  assert.match(brief, /\*\*Before your FINAL:\*\* stop the background shells and servers you started/);
  assert.match(brief, /close the browser if you hold it and tell the master/);
  assert.match(brief, /A file outside your write scope that your change needs/);
  assert.match(brief, /A progress file counts as written only once you have read it back/);
  assert.match(brief, /at least every 20 minutes/);
  assert.match(brief, /end it with the helper's `close`/);
  assert.match(brief, /never a raw `claude stop` or `claude rm`/);
  assert.match(brief, /Never open a seed, config or env file to read a credential/);
  // 2026-11-12 (P-20261110-12, P-20261109-7, P-20261110-9, P-20261109-6)
  assert.match(brief, /Never\s+create\s+or\s+edit\s+a\s+credentials\s+file/);
  assert.match(brief, /cp \.env\.example \.env/);
  assert.match(brief, /inferred/);
  // P-20261125-6 put the files written outside the scratch folder in front; the scratch folders are still listed.
  assert.match(brief, /list\s+every\s+file\s+you\s+wrote\s+outside\s+the\s+job's\s+scratch\s+folder,\s+and\s+every\s+scratch\s+folder\s+you\s+created/);
  assert.match(brief, /A\s+live\s+check\s+with\s+no\s+host,\s+database\s+or\s+test\s+account\s+named\s+here\s+is\s+a\s+miss/);
});

test("rule 5: a --scope folder may be absolute and outside the checkout, and then does not count against the lock (P-20261110-8)", () => {
  const skill = readSkill();
  const rule5 = rule(5);
  assert.match(rule5, /absolute\s+folder\s+outside\s+the\s+checkout/);
  assert.match(rule5, /does\s+not\s+count\s+against\s+the\s+lock/);
  assert.match(rule5, /read-only\s+git\s+at\s+most/);
});

test("the helper table says list --name prints one session, adopted or not (P-20261109-9)", () => {
  assert.match(readSkill(), /`--name` prints one, adopted or not/);
});

test("repo work, team rules, refs, live checks, credentials files and scratch folders (P-20261109-5, -6, P-20261110-9, -10, -11, -12)", () => {
  const skill = readSkill();
  const rule2 = rule(2);
  assert.match(rule2, /read-only\s+job\s+for\s+a\s+session,\s+even\s+after\s+`finish`/);
  assert.match(rule2, /assign\s+--reuse/);
  assert.match(rule2, /never\s+save\s+it\s+to\s+memory/);
  const rule13 = rule(13);
  assert.match(rule13, /Never\s+create\s+or\s+edit\s+a\s+credentials\s+file/);
  assert.match(rule13, /cp \.env\.example \.env/);
  const briefs = section(skill, "Briefs");
  assert.match(briefs, /git\s+ls-remote/);
  assert.match(briefs, /live\s+check\s+names\s+the\s+host\s+URL/);
  // brainiac P-20261112-8 replaced the master's delete of the listed folders with the wrap-up `!` line.
  assert.match(section(skill, "When a job ends"), /with\s+the\s+scratch\s+folders\s+the\s+worker\s+listed\s+in\s+it/);
  assert.match(section(skill, "Red flags"), /"I'll just read the code or fetch to answer"/);
});

test("briefs keep the template's lines whole, restate the shape, ask with a purpose, and wait for go only on an open decision (carcare P-20261104-8, -14, P-20261105-11, P-20261106-6, -7)", () => {
  const briefs = section(readSkill(), "Briefs");
  assert.match(briefs, /Every brief holds the template's lines itself, word for word/);
  assert.match(briefs, /a common file may add to a brief but never stands in for them/);
  assert.match(briefs, /restates the deliverable's shape in the user's words/);
  assert.match(briefs, /wait for "go" only while a user decision it depends on is still open/);
  assert.match(briefs, /no brief lets a command past the permission check/);
  assert.match(briefs, /the brief's last line/);
  const brief = read("worker-brief.md");
  assert.match(brief, /Open each question with what it is for, in plain words, before any detail/);
  assert.match(brief.trimEnd().split("\n").at(-1), /^<!-- end of the puppet-master worker brief: keep this line -->$/);
  assert.match(read("analyst-brief.md").trimEnd().split("\n").at(-1), /^<!-- end of the puppet-master analyst brief: keep this line -->$/);
});

test("the analyst brief says an evidence id is the event's id field, never a line number of events.jsonl (brainiac P-20261112-2)", () => {
  const analyst = read("analyst-brief.md");
  assert.match(analyst, /the\s+`id`\s+field\s+of\s+an\s+events\.jsonl\s+line/);
  assert.match(analyst, /never\s+the\s+line\s+number\s+of\s+events\.jsonl/);
});

test("full paths, a look at a visual deliverable, status while the user is waited on, the device checked first (carcare P-20261106-4, P-20261104-12)", () => {
  const skill = readSkill();
  const ends = section(skill, "When a job ends");
  assert.match(ends, /full current path or URL \(a path from its drive letter/);
  assert.match(ends, /open it and look at it yourself/);
  const relay = relayText();
  assert.match(relay, /While a step of yours waits on the user/);
  assert.match(relay, /check that their device or setup can do it/);
});

// --- the skill's structure (2026-11-12): SKILL.md is the always-needed core, references/ holds the rest ---
// The docs gate fails a SKILL.md body at 500 lines; these budgets fail first, with the routing rule in the message.

const SKILL_BUDGET = 300;
const REFERENCE_BUDGET = 200;
const CONTENTS_OVER = 100;

test("SKILL.md's body stays within its line budget, long before the docs gate's 500", () => {
  const lines = body(read("SKILL.md")).length;
  assert.ok(
    lines <= SKILL_BUDGET,
    `SKILL.md body is ${lines} lines (budget ${SKILL_BUDGET}; the docs gate fails at 500). Move text the master does not need on every turn to the reference for its moment: plugins/puppet-master/AGENTS.md, "Where skill text goes"`,
  );
});

test("every reference file stays within its budget, and one over 100 lines opens with a Contents list", () => {
  assert.ok(contentRefs().length >= 8, "references/ holds fewer files than the skill's moments");
  for (const name of refNames()) {
    const text = read(`references/${name}`);
    const lines = text.split(/\r?\n/);
    assert.ok(lines.length <= REFERENCE_BUDGET, `references/${name} is ${lines.length} lines (budget ${REFERENCE_BUDGET}): split it by moment, never trim rules the user approved`);
    if (lines.length > CONTENTS_OVER) {
      assert.ok(lines.slice(0, 12).includes("## Contents"), `references/${name} is over ${CONTENTS_OVER} lines and has no "## Contents" in its first lines`);
    }
  }
});

test("SKILL.md's Files table and references/_index.md name every reference file, and every file they name exists", () => {
  const files = contentRefs();
  const table = section(read("SKILL.md"), "Files to read, and when");
  const index = read("references/_index.md");
  for (const name of files) {
    assert.ok(table.includes(`\`references/${name}\``), `the Files table does not name references/${name}`);
    assert.ok(index.includes(`\`${name}\``), `references/_index.md does not name ${name}`);
  }
  const named = [...read("SKILL.md").matchAll(/`references\/([\w.-]+\.md)`/g)].map((m) => m[1]);
  const indexed = [...index.matchAll(/`([\w-]+\.md)`/g)].map((m) => m[1]);
  for (const name of new Set([...named, ...indexed])) assert.ok(refNames().includes(name), `a pointer names ${name}, which is not in references/`);
});

test("no reference links another reference (one level deep), and none holds a ${…} placeholder", () => {
  for (const name of refNames()) {
    const text = read(`references/${name}`);
    assert.doesNotMatch(text, /\$\{/, `references/${name} holds a placeholder, and a reference is read raw`);
    if (name === "_index.md") continue;
    assert.doesNotMatch(text, /references\//, `references/${name} names another reference`);
    assert.doesNotMatch(text, /\]\([^)]*\.md/, `references/${name} links a file`);
  }
});

test("each reference opens with its moment, and headings are unique across the skill folder", () => {
  const seen = new Map();
  for (const name of contentRefs()) {
    const lines = read(`references/${name}`).split(/\r?\n/);
    assert.match(lines[0], /^# \S/, `references/${name} has no title`);
    assert.match(lines[2], /^Read this (when|before|first)\b/, `references/${name} does not open with its moment`);
  }
  for (const name of ["SKILL.md", ...contentRefs().map((n) => `references/${n}`)]) {
    for (const m of read(name).matchAll(/^## .+$/gm)) {
      if (m[0] === "## Contents") continue;
      assert.ok(!seen.has(m[0]), `"${m[0]}" is a heading in ${seen.get(m[0])} and in ${name}`);
      seen.set(m[0], name);
    }
  }
});

test("SKILL.md tells the master to re-read it after its own compaction, right after the LOGS line, near the top", () => {
  const lines = body(read("SKILL.md"));
  const logs = lines.findIndex((l) => l.includes("--logs '${user_config.puppet_logs_dir}'"));
  const reread = lines.findIndex((l) => /After any compaction of your own, Read `<skill dir>\/SKILL\.md` again/.test(l));
  assert.ok(logs >= 0 && reread > logs, "the re-read line must come after the LOGS line");
  assert.ok(reread < 25, `the re-read line is at body line ${reread + 1}; it must be in the first 25`);
});

test("rule numbers and section names the earlier plans cite still resolve, and each split rule points to its detail", () => {
  const skill = read("SKILL.md");
  for (let n = 1; n <= 14; n++) assert.match(skill, new RegExp(`^${n}\\. \\*\\*`, "m"), `rule ${n} is gone from SKILL.md`);
  for (const n of [3, 4, 5, 7, 9, 10, 12]) {
    assert.match(skill, new RegExp(`Detail: \`references/[\\w-]+\\.md\`, rule ${n}\\.`), `rule ${n} does not point to its detail`);
    assert.ok(readSkill().includes(`## Rule ${n} in detail`), `no "## Rule ${n} in detail" section`);
  }
  for (const h of ["On start", "Rules", "When a job ends", "Relay protocol", "Chained jobs", "Briefs", "Wrap-up", "Helper reference", "Red flags: stop"]) {
    assert.ok(readSkill().includes(`## ${h}`), `no "## ${h}" section anywhere in the skill folder`);
  }
});

test("the plugin's AGENTS.md routes new skill text, and the analyst's proposals name their home (P-20261112 restructure)", () => {
  const agents = fs.readFileSync(path.join(PLUGIN_DIR, "AGENTS.md"), "utf8");
  const where = section(agents, "Where skill text goes");
  assert.match(where, /on every turn/);
  assert.match(where, /## Rule N in detail/);
  assert.match(where, /references\/_index\.md/);
  assert.match(where, /split by moment/);
  assert.match(agents, /`skills\/puppet-master\/references\/_index\.md`/);
  const analyst = read("analyst-brief.md");
  assert.match(analyst, /its\s+\*\*home\*\*/);
  assert.match(analyst, /the\s+core\s+or\s+the\s+reference\s+for\s+its\s+moment/);
});

// --- the text of C4 and C5, routed by the table in AGENTS.md ("Where skill text goes") ---

test("dead workers are closed with close, never a raw claude rm (P-20261110-3)", () => {
  const skill = readSkill();
  assert.match(section(read("SKILL.md"), "When a job ends"), /`dead`:\s+`close`\s+it,\s+which\s+removes\s+it\s+without\s+`stop`/);
  assert.match(section(skill, "Wrap-up"), /`puppet list` and `close` every finished or `dead` background worker/);
  assert.match(section(read("SKILL.md"), "Red flags"), /"I'll `claude rm` it myself" → `close`/);
  const rows = section(skill, "Helper reference");
  assert.match(rows.split("\n").find((l) => l.startsWith("| `list ")), /a background worker whose process is gone shows `dead`/);
  assert.match(rows.split("\n").find((l) => l.startsWith("| `close ")), /a `dead` worker gets `rm` alone[^|]*`may be restarting`[^|]*2, 4 and 8 s/);
});

test("rule 12: assign, switch, brief in one turn; 'switched' only once the helper printed it; the mod's line (P-20261110-4, brainiac P-20261112-1)", () => {
  const rule12 = rule(12);
  assert.match(rule12, /`assign`,\s+then\s+`switch`,\s+then\s+send\s+the\s+brief,\s+never\s+the\s+brief\s+first/);
  assert.match(rule12, /only\s+after\s+the\s+helper\s+printed\s+`switched/);
  assert.match(rule12, /`puppet-master: switched to …`\s+under\s+the\s+prompt/);
  assert.match(rule12, /`not at a task boundary`\s+or\s+`no mod heartbeat`/);
  assert.match(section(read("SKILL.md"), "Red flags"), /`puppet-master: switched to …`/);
});

test("a refused switch of a busy session is told to the user at once, with the retry (brainiac P-20261112-3 a)", () => {
  const row = section(readSkill(), "Helper reference").split("\n").find((l) => l.startsWith("| `switch "));
  assert.match(row, /`it keeps its current model and effort\. Next: run the same switch again once …`/);
  assert.match(row, /tell the user at once that it is not switched, and switch it when `list --name` shows it idle/);
});

test("a running window keeps the old skill text after an update: /reload-plugins, not retyping (brainiac P-20261112-7, F-7)", () => {
  const setup = read("references/setup-prerequisites.md");
  assert.match(setup, /keeps the skill text it\s+loaded, yours included: tell the user to run `\/reload-plugins` in it/);
  assert.match(setup, /Typing\s+`\/puppet-master:puppet-master` again does not refresh it/);
  const readme = fs.readFileSync(path.join(PLUGIN_DIR, "README.md"), "utf8");
  assert.match(section(readme, "Install"), /run `\/reload-plugins`\s+there\. Typing `\/puppet-master:puppet-master` again does not reload it/);
  const changelog = fs.readFileSync(path.join(PLUGIN_DIR, "CHANGELOG.md"), "utf8");
  assert.doesNotMatch(changelog, /type `\/puppet-master:puppet-master` again at a task boundary to load the new layout/);
});

// brainiac P-20261112-8. The user, 2026-11-12: "we dont want to go around permissions block but
// we must be sure it s all desired"; every denial came from the user's own rules (the proof pass).
test("no session deletes a temp folder during the day: the user's one ! line at wrap-up does (brainiac P-20261112-8, item 1)", () => {
  const skill = readSkill();
  assert.doesNotMatch(skill, /The one delete that is yours/);
  assert.doesNotMatch(skill, /delete its temp folder|Delete the listed folders/);
  assert.match(rule(1), /You delete nothing yourself, temp folders included/);
  const ends = section(read("SKILL.md"), "When a job ends");
  assert.match(ends, /its temp folder \(`<logs>\/tmp\/<session>`\) stays until the day's wrap-up/);
  assert.match(section(skill, "Briefs"), /Neither you nor the worker deletes it/);
  assert.match(read("worker-brief.md"), /Never delete it or anything in it, your own files included/);
  const wrap = section(skill, "Wrap-up");
  assert.match(wrap, /ONE `!` line/);
  assert.match(wrap, /`! rm -rf "<logs>\/tmp\/<session>" "<logs>\/tmp\/<session>" …`/);
  assert.match(wrap, /never the folder of a session whose job is still active/);
  assert.match(wrap, /a folder that is no finished job's: ask the user/);
});

test("a refused command is explained to the user at once, by the kind of rule, never investigated (brainiac P-20261112-8, item 2)", () => {
  const ap = read("references/approvals.md");
  assert.match(ap, /"Permission to use <tool> with command … has been denied\."/);
  assert.match(ap, /a deny rule in the user's own settings: it refuses that command in every permission mode, and in a session\s+the user starts by hand too/);
  assert.match(ap, /offer the user's `!` line for the worker's window, or skipping the step/);
  assert.match(ap, /auto mode classifier/);
  assert.match(ap, /built-in Claude Code safety check/);
  assert.match(section(read("SKILL.md"), "Red flags"), /"A worker's command was denied, I'll find out why" →/);
});

// T68 (A143, the user, 2026-11-27: "The session runs it after the user has confirmed texts and applying/publishing"):
// this replaces "always the user's ! line from the start" (brainiac P-20261112-8, item 3).
test("an external write the user approved is run by the session after the user confirmed the text and the apply on the page; a ! line only when the permission check refuses it (A143)", () => {
  const flat = (t) => t.replace(/\s+/g, " ");
  const ap = flat(read("references/approvals.md"));
  assert.match(ap, /An external write the user approves \(a Jira create or transition, a PR comment, `gh pr ready`, a release page, a publish; a push is a session's, above\) is run by the session after the user confirmed both the text and the apply or publish on the task page/);
  assert.match(ap, /"The session runs it after the user has confirmed texts and applying\/publishing"/);
  assert.match(ap, /The classifier does not take a relayed message as the user's approval, so when it refuses the run, give the user its exact `!` line then/);
  assert.doesNotMatch(ap, /planned as the user's `!` line for the worker's window from the start/);
  const briefs = flat(section(readSkill(), "Briefs"));
  assert.match(briefs, /An external write the user approved \(a Jira create or transition, a PR comment, `gh pr ready`, a release page, a publish\) is run by the session after the user confirmed both its text and the apply or publish on the task page, marked so here; you give a `!` line only when the permission check refuses it/);
  assert.doesNotMatch(briefs, /is always a `!` line/);
});

// brainiac-pipeline P-20261117-14, narrowing P-20261117-1 for git actions (F-4, F-5, F-28).
test("an approved git action is run by the master, with a `!` line only on refusal (brainiac-pipeline P-20261117-14)", () => {
  const r1 = rule(1);
  // T68 (the user, 2026-11-27, orchestrate-only): a session runs it; the master only when no session can.
  assert.match(r1, /A commit, push or other git action a worker brings you is\s+one question to the user; on yes, a session runs it/);
  assert.match(r1, /the hash, the\s+pushed range and an `ls-remote` check/);
  assert.match(r1, /only when no session can, run it\s+yourself in your own window/);
  assert.match(r1, /A `!` line for it only if the run is refused/);
  assert.match(rule(2), /every\s+job \(a release, a CI watch, a change to the page's code or template, a commit\) goes to a session/);
  const ap = read("references/approvals.md");
  assert.match(ap, /\*\*A commit, push or other git action a worker brings\*\*/);
  assert.match(ap, /Only when the run is refused, give the user its `!` line/);
  assert.match(ap, /no need to show me\s+manual commands if you can do it/);
  assert.doesNotMatch(ap, /`gh pr ready`, a push\)/);
  const relay = section(read("SKILL.md"), "Relay protocol");
  assert.match(relay, /A push or other git action\s+goes to a session on the user's yes \(rule 1\)/);
  assert.doesNotMatch(relay, /irreversible one \(a delete, a push, a Railway write\)/);
  assert.match(section(read("SKILL.md"), "Red flags"), /"The user said yes to the worker's push, here is the `!` line" →/);
  assert.match(section(readSkill(), "Briefs"), /A commit, push or other git action goes to a session on the user's yes\s+\(rule 1\)/);
  assert.match(read("worker-brief.md"), /send the master `ready for the master: <commands>`/);
});

test("the analyst brief says what a classifier-denied event is (brainiac P-20261112-8, item 4)", () => {
  assert.match(read("analyst-brief.md"), /a `classifier-denied` one is auto mode's classifier refusing a call,\s+its excerpt `\[<category>\] <the call>`/);
});

test("close retries an rm that fails while the service restarts, then says when to close again (brainiac P-20261112-6, F-8)", () => {
  const row = section(readSkill(), "Helper reference").split("\n").find((l) => l.startsWith("| `close "));
  assert.match(row, /an `rm` failing so is retried the same way, then it prints `stopped but NOT removed` with the resume line and says to run `close` again in a minute or once a background worker is running/);
  assert.match(section(read("SKILL.md"), "Red flags"), /retries a\s+`stop` or `rm` that fails while the background service restarts/);
});

test("shipped's 'never approved' row says which group's decisions were searched (brainiac P-20261112-4, F-5)", () => {
  const row = section(readSkill(), "Helper reference").split("\n").find((l) => l.startsWith("| `shipped "));
  assert.match(row, /`was never approved in group "<g>"` \(or `with no group`\) names the decisions file it searched/);
  assert.match(row, /run `shipped` again with the one that logged it/);
});

test("the 2026-11-24 text proposals are in the file for their moment (P-20261124-1, -2, -3, -4, -7, -9, -10, -11)", () => {
  const skill = read("SKILL.md").replace(/\s+/g, " ");
  const ref = (n) => read(`references/${n}`).replace(/\s+/g, " ");
  // P-1: the first line of a job is the user's verb, with its prerequisites
  assert.match(ref("jobs.md"), /A job's first line is the user's verb\.[\s\S]*list what the user said must come first[\s\S]*An approved design followed by "implement" is a build job, with no plan page unless the user asked for one/);
  // P-2: the day's standing answers, pasted whole into every brief
  assert.match(ref("briefs.md"), /"standing answers" block on the live task page[\s\S]*unchanged into `\{\{standing_rules\}\}` of every brief that day[\s\S]*each line of the block is in the brief/);
  // P-3: a "cannot" claim is searched first
  assert.match(skill, /"no verb", "no way" or that "the tool cannot" is checked first against memory, the earlier sessions' transcripts and the tool's own help[\s\S]*a two-option "cannot" question never goes to the user/);
  // P-4: labels from the page's source, the whole ask answered
  assert.match(section(read("SKILL.md"), "When a job ends").replace(/\s+/g, " "), /Name a button or a menu only after you found its label in the page's source[\s\S]*cannot see a deliverable, give its full path again and open it yourself[\s\S]*list each part of the user's ask against your answer/);
  // P-7: a correction is answered by doing
  assert.match(section(read("SKILL.md"), "Red flags").replace(/\s+/g, " "), /"You're right, I missed it" or "I can't compact" in reply to a correction → the reply is the step itself plus one line of what changed[\s\S]*run it and quote its refusal/);
  // P-9: a busy switch is queued on the task page and run at FINAL
  assert.match(ref("context.md"), /"not at a task boundary", put "switch to <tier> at FINAL" in the task's item[\s\S]*same turn as the worker's `measure` at its `FINAL:`[\s\S]*the job ran on the launch tier/);
  // P-10: queued work goes to an idle clean session at a job's end
  assert.match(section(read("SKILL.md"), "When a job ends").replace(/\s+/g, " "), /If a clean session is idle and the task page has queued tasks, start the ones the user already approved there and name the rest/);
  // P-11: rule 11 names the plugin-update calls, with the user's quote
  assert.match(rule(11).replace(/\s+/g, " "), /`claude plugin marketplace update <name>` and `claude plugin update <plugin>@<name>`[\s\S]*The user, 2026-11-24: "Yes, add to rule 11 \(Recommended\)"/);
  // P-8 was rejected by the user: SKILL.md still lists a Railway write among the worker's irreversible steps
  assert.match(ref("approvals.md"), /\(a delete, a Railway write\), ask the user's decision\s+here first/);
});

// --- the live task page template and the HTML-only reports rule (2026-11-24, A45) ---

test("the live task page ships as a template: the layout in SKILL.md, the detail and the quotes in on-start step 7", () => {
  const bullet = read("SKILL.md").replace(/\s+/g, " ");
  assert.match(bullet, /\*\*The live task page\.\*\*[\s\S]*pinned header[\s\S]*side panel[\s\S]*`skills\/puppet-master\/templates\/task-page\/`/);
  assert.match(bullet, /Run `sync-sessions\.mjs` in the same turn as every page change/);
  const step7 = read("references/on-start.md").replace(/\s+/g, " ");
  assert.match(step7, /copy the template folder `skills\/puppet-master\/templates\/task-page\/` to a folder outside every checkout[\s\S]*fill `tasks\.js`/);
  assert.match(step7, /list items like T39\/41 when get so big they need a shortneing with 'show more' button \+ lets make it more area efficient - current data goes to one side and linked docs opens in side panel \(new window only when clicked in specific button\)/);
  assert.match(step7, /\+ static pinned header with \[Image #1\] and opened sessions/);
  assert.match(step7, /sessions table needs ehaders, 3\. tasks list table columns overlaps/);
  assert.match(step7, /2026-11-24/);
  assert.match(step7, /Reports are written straight into `tasks\.js`/);
});

test("the task page of 2026-11-26: three tabs, previous work sets in the sidebar, asks as records, pending report and its seen line (T28, T29, A62, A64)", () => {
  const bullet = read("SKILL.md").replace(/\s+/g, " ");
  assert.match(bullet, /\*\*The live task page\.\*\*[\s\S]*four tabs, Questions \(open asks, grouped by task\), Tasks \(one row each, grouped, done ones under the Done filter\), Epics and Jira \(epics, PRs, Jira status, read times\) and Side questions \(the user's side questions to you\), a sidebar with every status filter and its count, each session's whole record and the previous work sets, and a side panel for report pages whose width the user drags/);
  // T68 (A139): the Epics and Jira section is refreshed in the same step as any change to an epic, not only before a status
  assert.match(bullet, /and `sync-epics\.mjs` in the same step as any change to an epic, its PRs, branches, reviews, stamps or Jira issues, not only before a status/);
  assert.doesNotMatch(bullet, /`sync-epics\.mjs` before a status that names an epic/);
  assert.match(bullet, /goes onto the page as an ask of that open task \(a record in `asks\[\]` of `tasks\.js`, shown in Questions and on the task's item\), with its id and the data to decide on/);
  const step7 = read("references/on-start.md").replace(/\s+/g, " ");
  assert.match(step7, /"questions\/tasks\/jira tasks should be 3 separate tabs, previouse work status pages go to sidebar"/);
  assert.match(step7, /"all lists and tables must be ordered"/);
  assert.match(step7, /each ask as its own record in `asks\[\]`, with its id, its task and the data to decide on/);
  assert.match(step7, /is `pending-report`, not counted as waiting[\s\S]*"new list item status, 'pending report' which tells me nothing waits there but it s thing to read"/);
  assert.match(step7, /"button next to it marking showed"[\s\S]*"seen on the task page: T22 \(11-26 23:40\)"; on that line, or when the user says they read it, set it `done`/);
  // T33, the user after testing it: open asks stacked, the Tasks tab only tasks, filters to the sidebar, a wider panel dragged live
  assert.match(step7, /"all open questions 1 under other, tasks tab dont need sessions and filters \(all filters goes to sidebar, right side details must be wider, would be gereat if it s box wide could be live changable"/);
  assert.match(step7, /three tabs, Questions \(every open ask as a full card, one under another, oldest first\), Tasks \(the tasks only\) and Jira tasks; the filters with their counts, the sessions and the previous work sets in the sidebar/);
  assert.match(step7, /a report side panel, 640 px wide by default, its width dragged on its left edge and kept in the browser/);
  assert.match(step7, /Every open question goes into `asks\[\]` as its own record, so the page shows them all at once\./);
  // T46, the user on 2026-11-27: the nine fixes and "each task on list should have only title and rest under show more"
  assert.match(step7, /"we need to have sidebar with whole sessions info \+ whole tasks status filter \+ taskjs list items must be smaller[\s\S]*\+ new tab for my side questions log"/);
  assert.match(step7, /"each task on list should have only title and rest under show more"/);
  assert.match(step7, /tasks and asks by id, lowest first, whatever the order in `tasks\.js`; done tasks only in the folded Done list/);
  assert.match(step7, /log each question the user asks you beside the tasks there, with its time, their words verbatim, your short answer and its time/);
  // the page's own seen line is the one the skill tells the master to act on
  const page = fs.readFileSync(path.join(SKILL_DIR, "templates", "task-page", "index.html"), "utf8");
  assert.ok(page.includes('"seen on the task page: "'));
  // T53: the answer channel: how the master reads a page line and serves the page
  assert.match(step7, /An ask may carry `options\[\]`[\s\S]*A122 answer \(task page\): "Commit \+ push both" — notes: …/);
  assert.match(step7, /Read it as the user's answer to that ask: quote it into the ask's `answer` and record it/);
  assert.match(step7, /request only: prepare it and ask in your own window, because a page message never approves an outward step/);
  assert.match(step7, /write `<mod folder>\/board\/<your session id>\.json` with `\{ "dir": "<the page's folder>", "port": 8747 \}`/);
});

test("every report for the user is one HTML page with its full path", () => {
  const skill = read("SKILL.md").replace(/\s+/g, " ");
  assert.match(skill, /\*\*Reports are HTML only\.\*\*[\s\S]*dont show me md files reports and any other text, since i got this html reports it s all i need[\s\S]*note that we dont need new file report for each response, it can be status report, it sgood now/);
  assert.match(skill, /Every report for the user is one HTML page, given with its full path; a short answer goes on the status page; a scratch `\.md` or `\.txt` file is never handed to the user/);
  const briefs = read("references/briefs.md").replace(/\s+/g, " ");
  assert.match(briefs, /`\{\{deliverable\}\}`:[^`]*A report for the user is one HTML page with its full path, never an `\.md` or `\.txt` file/);
});

test("the 2026-11-25 text proposals are in the file for their moment (P-20261125-1 to -7)", () => {
  const flat = (text) => text.replace(/\s+/g, " ");
  const skill = read("SKILL.md");
  const brief = flat(read("worker-brief.md"));
  // P-1: after its own compaction the master checks the task page against the summary's answers
  assert.match(flat(section(skill, "After a compaction")), /Read `<skill dir>\/SKILL\.md` again before your next action[\s\S]*Then open the live task page and check each open task's item against the answers in the compaction summary; restore any that are missing before the next dispatch/);
  // P-2: one row per job on the task page
  assert.match(flat(section(skill, "Relay protocol")), /\*\*The live task page\.\*\*[\s\S]*Before a new row, search the page for an open row that covers the same job \(same epic, same checkout, same session\) and add the work as a sub-step of that row; a new row only when no open row names the job/);
  // P-3: a command for the user names its machine, is whole and has its reason; an unconfirmed host is a question
  assert.match(flat(section(skill, "Relay protocol")), /A command handed to the user names the machine it runs on, is given whole \(flags included\), and comes with one line on why it is needed\. A step on a host you have not confirmed is available is first asked as a question, never given as a next step/);
  // P-4: the compaction line covers a job without git, once: the clause replaced "With no git allowed, ask the master."
  assert.match(brief, /take where you are from the checkout's git state \(`git status`, `git log` of your branch\), not from the summary, unless this job runs without git; then from the files you wrote and, for a git fact, ask the master\./);
  assert.doesNotMatch(brief, /With no git allowed, ask the master/);
  // P-5: the window the user named for git steps is a standing answer of the work set, never a default in the skill
  assert.match(flat(read("references/briefs.md")), /"standing answers" block on the live task page[\s\S]*A work set may carry the window the user named for its git steps: record "git, commit and merge steps go to `<window>`" in the block as a standing answer and route by it for that work set/);
  // P-6: the FINAL lists the files written outside the job's scratch folder
  assert.match(brief, /Then `FINAL:`, and list every file you wrote outside the job's scratch folder, and every scratch folder you created\./);
  // P-7: a turn that ends with open rows and nothing to wake the master says what comes next
  assert.match(flat(section(skill, "When a job ends")), /If open task rows remain after a job-ended reply and no job will wake you, say in one line what you will do next, or start it\./);
});

// --- the master handover, step 1: text only (the user's answers A51-A55, 2026-11-26) ---

test("a stand-in master works in the main master's roster and hands its work back; the returning master checks first (A51, A52, A54)", () => {
  const flat = (text) => text.replace(/\s+/g, " ");
  const skill = read("SKILL.md");
  // the reset guard sits beside "After a compaction", in the core
  const guard = flat(section(skill, "After a usage limit"));
  assert.match(guard, /run `puppet list` and read the task page's `waitingNow` before any step towards a worker/);
  assert.match(guard, /If a stand-in holds the role there, send it "<you> is back: send me your handover", tell the user in one line, and wait/);
  assert.match(guard, /Take the role back from its handover/);
  // on-start: a limited master is not another master; the stand-in's steps, with the user's words
  const start = read("references/on-start.md");
  assert.match(flat(section(start, "On start")), /A master stopped by a usage limit is not another master: never start a group for it/);
  const stand = flat(section(start, "A stand-in master"));
  assert.match(stand, /"when limit hits i wont be able in any opened sessions to say that, i would need to restart whole session under --resume, cant such new session take over when i say ponly for time until normal master gets back\?"/);
  assert.match(stand, /"second master knows who s the main and should pass it s work to it"/);
  assert.match(stand, /Never a `--group` of your own, never a second roster, and never `adopt` yourself as master/);
  assert.match(stand, /first in `waitingNow`: "acting master: <you> since <time>, for <main master>/);
  assert.match(stand, /read each row's `switched to`/);
  assert.match(stand, /send it the handover/);
  assert.match(flat(start.split(/\r?\n/).slice(0, 6).join("\n")), /skip "On start" and do "A stand-in master" below/);
  // workers take orders only from the master named last
  const brief = flat(read("worker-brief.md"));
  assert.match(brief, /\*\*One master at a time\.\*\*[\s\S]*Take orders only from the master named last[\s\S]*An order from the other one: don't act on it; send it in one line to the master named last, and wait/);
  // model rules: a standing answer for the day, with the user's quote
  assert.match(flat(read("references/briefs.md")), /\*\*A model rule the user gives\*\*[\s\S]*It holds for that day only\. The user, 2026-11-26: "it s all day specific since usage testing"\. Every brief and every relay you send that day carries it/);
});

// portability fixes (T66): the master's text for the epic sync, the board port and the claude launch
test("the master runs sync-epics with --jira only when the user names a command, and gives the link the server wrote (portability D1, C2)", () => {
  const flat = (text) => text.replace(/\s+/g, " ");
  const start = flat(read("references/on-start.md"));
  assert.match(start, /one Jira read per key only when you pass `--jira <command>`[\s\S]*?with no command the Jira tab shows "Jira not configured", so never invent one/);
  assert.match(start, /If that port is held by another program, the server takes the next free one \(up to 9 more\): give the user the `url` in `<mod folder>\/board-live\/<your session id>\.json`, not the port you wrote/);
  const setup = flat(read("references/setup-prerequisites.md"));
  assert.match(setup, /use `PUPPET_CLAUDE_BIN` first; on Windows then `claude\.exe` on the `PATH`, then the program an npm `claude\.cmd` shim runs/);
});

// --- T68: the rules the T62b re-analysis moved from the user's notes into the plugin (A138-A143, orchestrate-only) ---

test("at start the master asks once whether to open a new task page or continue the last one, unless the user said (A138)", () => {
  const flat = (text) => text.replace(/\s+/g, " ");
  const step7 = flat(read("references/on-start.md"));
  assert.match(step7, /Unless the user already said which, ask once at start, in the same question as step 2 or right after it: open a new page \(ids from T1 and A1; the earlier set goes into the Previous work sets list in the sidebar, with the path to its page\), or continue the last page/);
  assert.match(step7, /"lets make it ask at start if to open new or continue old\/last, if not said explicitly on start"/);
  assert.match(step7, /To continue, keep the page you had; for a new page, copy the template folder/);
  assert.match(step7, /on a new page, one line at most, with the earlier set's page path/);
  const page = flat(fs.readFileSync(path.join(SKILL_DIR, "templates", "task-page", "tasks.js"), "utf8").replace(/^\/\/ ?/gm, ""));
  assert.match(page, /At start the master asks once, unless the user said which: a new page \(ids from T1 and A1; the earlier set goes into `previous`\) or the last page continued/);
  assert.doesNotMatch(page, /it carries over days until a new set of work starts/);
});

test("the Epics and Jira section is refreshed in the same step as any change that touches it (A139)", () => {
  const step7 = read("references/on-start.md").replace(/\s+/g, " ");
  assert.match(step7, /run `sync-epics\.mjs` in the same step as any change to an epic, its PRs, branches, reviews, stamps or Jira issues \(the user, 2026-11-27: "it must be refreshed anytime something related to them changes"\), not only before a status\. A new epic in play gets its row at once/);
});

test("side-question ids are S1, S2 per page (A140), and every message gets a text reply with a side question answered first (T62b)", () => {
  const step7 = read("references/on-start.md").replace(/\s+/g, " ");
  assert.match(step7, /Its id is S1, S2, \.\.\. per page, never reused within the page/);
  assert.match(step7, /every user message gets a text reply\. A side question is answered in the opening lines, before any relay or status, and never together with a question on another topic\. Log it in Side questions in the same turn/);
  const page = fs.readFileSync(path.join(SKILL_DIR, "templates", "task-page", "tasks.js"), "utf8");
  assert.match(page, /"S1", "S2", \.\.\. never reused within the work set/);
});

test("no restated questions and no 'still open' lines in chat; one pointer line after a real gap; a stuck worker is announced once and put on the page (A141)", () => {
  const relay = section(read("SKILL.md"), "Relay protocol").replace(/\s+/g, " ");
  assert.match(relay, /Never restate a question or write "still open" lines: the page header and the Questions tab are the reminder\./);
  assert.match(relay, /After a real gap, one short pointer line \("A2 is open on the page"\) is allowed once\./);
  assert.match(relay, /A reply that waits on the user carries that one item only; the rest queues on the page\./);
  assert.match(relay, /A decision that blocks a session goes onto the page as an ask at once, its id named once in chat, never held until they ask for status\. Other work goes on meanwhile\./);
  assert.doesNotMatch(relay, /AskUserQuestion\)/);
});

test("accept-edits is asked only for a worker window outside auto mode, or when a worker reports an ordinary edit prompting; the helper and the mod read no permission mode (A142)", () => {
  const relay = section(read("SKILL.md"), "Relay protocol").replace(/\s+/g, " ");
  assert.match(relay, /Do not ask the user to set accept-edits at a brief: a window in auto mode needs none, and the helper and the mod cannot read a session's permission mode\. Ask once, for that window only, when the user says it is not in auto mode or its worker reports that an ordinary edit prompts\./);
  const briefs = section(readSkill(), "Briefs").replace(/\s+/g, " ");
  assert.match(briefs, /a window in auto mode needs no accept-edits, and a worker whose ordinary edit still prompts reports it to you/);
  assert.doesNotMatch(briefs, /sets the worker's window to accept-edits once/);
  // The premise, checked in this job: no script or mod text reads a permission mode.
  for (const file of [path.join(SKILL_DIR, "scripts", "puppet.mjs"), path.join(PLUGIN_DIR, "hooks", "puppet-mod.js")]) {
    assert.doesNotMatch(fs.readFileSync(file, "utf8"), /permissionMode|permission_mode|acceptEdits/, `${path.basename(file)} now reads a permission mode: A142's rule can say how it is known`);
  }
});

test("the master orchestrates: every job goes to a session, and it never runs a long wait in its own turn (the user, 2026-11-27)", () => {
  const rule2 = rule(2).replace(/\s+/g, " ");
  assert.match(rule2, /You orchestrate: every job \(a release, a CI watch, a change to the page's code or template, a commit\) goes to a session; you work yourself only when the user tells you to or no session can, and never run a long wait \(a push's test lane, a CI watch\) in your own turn, so the user's answers from the page are handled at once\./);
  assert.match(rule2, /"only orchestrate all of it and only do something when slaves cannot do it"/);
  // The page's code goes to a session; its data (tasks.js) stays the master's own, updated in the same turn as each change.
  const bullet = read("SKILL.md").replace(/\s+/g, " ");
  assert.match(bullet, /\*\*The live task page\.\*\* Keep one page per work set \(`references\/on-start\.md`, step 7\) and update its data \(`tasks\.js`\) yourself in the same turn as every change \(its code goes to a session\): a task/);
  const ap = read("references/approvals.md").replace(/\s+/g, " ");
  assert.match(ap, /\*\*After a push:\*\* a session finds the CI run for the pushed commit and watches it in the background until it ends; you never run that wait in your own turn\. Never report a push as passing from local checks alone\./);
  assert.match(ap, /"Pushed" is not "landed"\./);
});

test("task-page rows stay true at every update: no stale running or waiting rows, reports linked at once, asks carry their facts (T62b)", () => {
  const step7 = read("references/on-start.md").replace(/\s+/g, " ");
  assert.match(step7, /each row marked running names the session or process doing it now; with none, set it done or waiting\. A waiting-for-you row always carries an open ask the user can answer on the page; if the user answers "wait", keep the ask open with the answer noted, or set the row queued and say when it returns\. When a worker's `FINAL:` lands, close its row and any master row that only waited on it/);
  assert.match(step7, /A preview page, screenshot set or draft report that exists goes onto that task's `reports` at once, labelled draft or preview, with a line saying it can be opened, not at `FINAL:`\. Never answer "do you have X\?" with a link the page does not show yet\./);
  assert.match(step7, /A design task's row carries the working design file as its first report; a worker that makes or seeds one adds it to the row in the same turn\./);
  assert.match(step7, /every ask carries, in its facts, everything the user needs to decide: what was checked and how, each item on its own line, what each option does and what is left out\. Small information goes in the ask's facts, not in a separate page\. Your chat text is not where the user reads it\./);
  assert.match(flatBriefs(), /A design task's brief says that the working design file is the task row's first report/);
});

function flatBriefs() {
  return read("references/briefs.md").replace(/\s+/g, " ");
}

test("briefs and worker rules of T62b: standing yeses with withdrawals, HTML render of a brief, report layout, fetch before a state claim (briefs.md)", () => {
  const briefs = flatBriefs();
  assert.match(briefs, /Record each standing yes, and each withdrawn one, with the user's quote and date\. Before asking for a permission or a `!` line, check the record: act on a standing case and name it in the brief; ask each time for a withdrawn one\./);
  assert.match(briefs, /A brief or draft the user is meant to read is linked on the task page as an HTML render of it; the worker still reads the Markdown file\./);
  assert.match(briefs, /Report tables: the prose column gets the width; code paths and `file:line` go on their own small line under the item \(or wrap\), never in a wide unbreakable column; prefer one card per finding to a many-column table, because the side panel starts narrow and the user drags it wider; set no max-width on the page content\./);
  assert.match(briefs, /Before a claim about a repository's or epic's state read from a reference checkout, a worker fetches and compares it with the remote; the brief says so\./);
});

test("the worker brief: unfiltered test claims, read-only verification, real exit codes (T62b)", () => {
  const brief = read("worker-brief.md").replace(/\s+/g, " ");
  assert.match(brief, /A claim that tests pass names every test project that ran, with no filter\. A filtered run is for iterating and backs no pass line\. A failure that predates the change is reported with its evidence, and the user decides\./);
  assert.match(brief, /Verification is read-only\. Before any verification step that writes to a live target, ask the master and name the exact writes; tests on fixtures are the proof\./);
  assert.match(brief, /Capture a command's real exit code \(send its output to a log, then read the exit status of that command on its own\) and cite it\. Never judge a gate by a pipe through `tail` or `grep`: the pipeline reports the last command's code\./);
});

test("approvals and jobs of T62b: permission rules checked at a job's start, read-only verification, cleanup lines, follow-up tier, proxy backend, 'like X' dimensions", () => {
  const ap = read("references/approvals.md").replace(/\s+/g, " ");
  assert.match(ap, /\*\*At a job's start,\*\* check that the user's permission rules already cover the commands the job will run, and tell the user which ones they would need to allow; an answer in chat changes no permission state\./);
  assert.match(ap, /\*\*Verification is read-only\.\*\* Before any verification step that writes to a live target, ask the user and name the exact writes; tests on fixtures are the proof\. If a live run is wanted, use the least-coupled target\./);
  assert.match(ap, /\*\*Before you hand the user any cleanup line,\*\* read its target list\. Include only what Claude Code, a plugin, a skill, an MCP server or a session's script made; leave system, vendor and user files out, however large or old\./);
  const jobs = read("references/jobs.md").replace(/\s+/g, " ");
  assert.match(jobs, /A follow-up message to a working session is a new part of its job: choose its tier before sending, and switch while the session is idle\./);
  assert.match(jobs, /A window running on a proxy backend is adopted again as a worker and is not switched: `switch` would send a Claude model and override the backend\. Give it mechanical jobs\./);
  assert.match(jobs, /When the user says "like X", list which dimensions of X carry over and let the user correct the list\./);
});

test("the plugin's rule text carries no path, drive letter, OS, time zone, product or user name in the T68 sentences", () => {
  // The T68 sentences were written in neutral wording; this pins the new rule blocks against the names the user's notes held.
  const blocks = [
    section(read("references/on-start.md"), "On start").split("What you keep true at every page update")[1],
    read("references/approvals.md").split("- **After a push:**")[1],
  ];
  for (const block of blocks) {
    assert.ok(block && block.length > 200, "a T68 block is missing");
    assert.doesNotMatch(block, /[A-Za-z]:[\\/]|\/Users\/|\/home\//);
    assert.doesNotMatch(block, /\b(brainiac|inEwi|carcare|Krzysztof|krzysiek)\b/i);
  }
});

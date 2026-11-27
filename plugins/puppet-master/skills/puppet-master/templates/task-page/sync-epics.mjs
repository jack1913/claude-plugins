// Reads every epic's PRs and Jira issues again and rewrites the `epics` block, `epicsAsOf` and `updated` in tasks.js,
// the way sync-sessions.mjs refreshes the sessions from `puppet list`. Run it before a status that names an epic,
// and at least every 2 hours while an epic is open (the Jira tab marks older lines stale).
//   node sync-epics.mjs [--file <tasks.js>] [--gh <gh>] [--jira <command>] [--repo <name>=<owner/repo>]...
// Per repo line, two reads and nothing else:
//   gh pr view <url> --json ...           (or <number> --repo <owner/repo> from --repo) -> prState, check, asOf
//   <jira command> <KEY> --json           only when --jira is given (no default)        -> jira status, category, type, assignee
//                                         prints one JSON object { status: { name, category }, type, assignee }
// --gh and --jira take a command; a path ending in .mjs or .js runs with node. Read only: no write to GitHub or Jira.
// Without --jira no Jira read runs: epicsAsOf.Jira becomes "not configured" and the Jira tab shows "Jira not configured".
// A line that cannot be read keeps its old values and is listed; the script then exits 2 (1: no tasks.js or no epics block).
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const arg = (name) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : undefined; };
const args = (name) => argv.flatMap((a, i) => (a === name && argv[i + 1] ? [argv[i + 1]] : []));
const FILE = arg("--file") || path.join(HERE, "tasks.js");
// "backend=owner/name": where a repo line without a PR URL lives
const REPOS = Object.fromEntries(args("--repo").map((r) => r.split("=")).filter((p) => p.length === 2 && /^[\w.-]+\/[\w.-]+$/.test(p[1])));

// a command as [file, ...args]: a .mjs/.js path runs with node; anything else splits on spaces
const command = (c, dflt) => {
  if (!c) return dflt;
  return /\.(mjs|js)$/i.test(c) ? [process.execPath, c] : c.split(/\s+/).filter(Boolean);
};
const GH = command(arg("--gh"), ["gh"]);
// No default: Jira is read only when --jira names a command (null: not configured, and the Jira tab says so).
const JIRA = arg("--jira") ? command(arg("--jira")) : null;
const run = ([file, ...pre], rest) => execFileSync(file, [...pre, ...rest], {
  encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 60000,
  // a shim such as jira.cmd needs the shell on Windows; every value passed here is checked against a strict pattern first
  shell: process.platform === "win32" && file !== process.execPath,
});

if (!existsSync(FILE)) { console.error(`tasks.js not found at ${FILE}: pass --file <path>`); process.exit(1); }
let text = readFileSync(FILE, "utf8");
const box = { window: {} };
vm.runInNewContext(text, box);
const D = box.window.DASH;
if (!D || !Array.isArray(D.epics)) { console.error("tasks.js has no epics array"); process.exit(1); }

const now = new Date();
const pad = (n) => String(n).padStart(2, "0");
const day = `${pad(now.getMonth() + 1)}-${pad(now.getDate())}`, hm = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
const stamp = `${day} ${hm}`;
const PR_URL = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/pull\/\d+$/;
const KEY = /^[A-Z][A-Z0-9_]*-\d+$/;
const FAILED = /^(FAILURE|ERROR|TIMED_OUT|CANCELLED|ACTION_REQUIRED|STARTUP_FAILURE)$/;
const missed = [], read = [];
let ghRead = 0, jiraRead = 0;

for (const e of D.epics) {
  for (const r of e.repos || []) {
    const where = `${e.epic} ${r.repo || "?"} ${r.pr || ""}`.trim();
    const before = missed.length;
    // the PR, from gh
    const num = String(r.pr || "").replace(/\D/g, "");
    const prUrl = r.prUrl || r.url;
    const target = prUrl && PR_URL.test(prUrl) ? [prUrl] : num && REPOS[r.repo] ? [num, "--repo", REPOS[r.repo]] : null;
    if (!target) missed.push(`${where}: PR not read (no PR url, and no --repo ${r.repo || "<name>"}=<owner/repo>)`);
    else {
      try {
        const p = JSON.parse(run(GH, ["pr", "view", ...target, "--json", "state,isDraft,mergeable,mergeStateStatus,headRefOid,statusCheckRollup,url"]));
        const state = p.state === "MERGED" ? "merged" : p.state === "CLOSED" ? "closed" : p.isDraft ? "draft" : "ready";
        const merge = p.mergeable === "MERGEABLE" ? "mergeable" : p.mergeable === "CONFLICTING" ? "conflicting" : "mergeable unknown";
        r.prState = state === "merged" || state === "closed" ? state
          : `${state} · ${merge}, ${String(p.mergeStateStatus || "unknown").toLowerCase()}${p.headRefOid ? ` (head ${p.headRefOid.slice(0, 10)})` : ""}`;
        const bad = (p.statusCheckRollup || []).find((c) => FAILED.test(String(c.conclusion || c.state || "")));
        if (bad) r.check = `check ${bad.name || bad.context || "?"}: ${String(bad.conclusion || bad.state).toLowerCase()}`; else delete r.check;
        if (!prUrl && p.url && PR_URL.test(p.url)) r.url = p.url;
        ghRead++;
        read.push(`${where}: ${r.prState}${r.check ? " · " + r.check : ""}`);
      } catch (err) {
        missed.push(`${where}: gh pr view failed (${String(err.stderr || err.message).trim().split(/\r?\n/)[0]})`);
      }
    }
    // the Jira issue, from the Jira command
    const key = r.jira && r.jira.key;
    if (key && !KEY.test(key)) missed.push(`${where}: Jira key ${key} not read (not KEY-123)`);
    else if (key && !JIRA) { /* not configured: nothing to read, nothing missed (the notice is written to epicsAsOf below) */ }
    else if (key) {
      try {
        const j = JSON.parse(run(JIRA, [key, "--json"]));
        if (j.status) { r.jira.status = j.status.name; r.jira.category = j.status.category; }
        if (j.type) r.jira.type = j.type;
        r.jira.assignee = j.assignee || "";
        jiraRead++;
        read.push(`${where}: ${key} ${r.jira.status} (${r.jira.category})`);
      } catch (err) {
        missed.push(`${where}: ${key} not read (${String(err.stderr || err.message).trim().split(/\r?\n/)[0]})`);
      }
    }
    // the line's read time only when every part of it was read: a stale part never shows as fresh
    if (missed.length === before) r.asOf = stamp;
  }
}

// Replace a top-level value in the file's text, found by its key (plain or quoted), brackets matched outside strings.
function replaceValue(src, key, value) {
  const m = new RegExp(`^([ \\t]*)"?${key}"?[ \\t]*:[ \\t]*`, "m").exec(src);
  if (!m) return null;
  let i = m.index + m[0].length, depth = 0, quote = "";
  const start = i;
  for (; i < src.length; i++) {
    const c = src[i];
    if (quote) { if (c === "\\") i++; else if (c === quote) quote = ""; continue; }
    if (c === '"' || c === "'" || c === "`") quote = c;
    else if (c === "[" || c === "{") depth++;
    else if (c === "]" || c === "}") { depth--; if (depth === 0) { i++; break; } }
    else if (depth === 0 && (c === "," || c === "\n")) break;
  }
  const indent = m[1];
  const json = JSON.stringify(value, null, 1).replace(/\n/g, "\n" + indent);
  return src.slice(0, start) + json + src.slice(i);
}
const asOf = D.epicsAsOf && typeof D.epicsAsOf === "object" ? D.epicsAsOf : {};
if (ghRead) asOf.gh = stamp;
if (jiraRead) asOf.Jira = stamp;
else if (!JIRA) asOf.Jira = "not configured";
let out = replaceValue(text, "epics", D.epics);
if (out === null) { console.error("tasks.js has no `epics: [...]` block"); process.exit(1); }
out = replaceValue(out, "epicsAsOf", asOf) ?? out.replace(/^([ \t]*"?epics"?[ \t]*:)/m, (m0, k) => `  epicsAsOf: ${JSON.stringify(asOf)},\n${k}`);
out = out.replace(/^[ \t]*"?updated"?: *".*",/m, () => `  updated: "${now.getFullYear()}-${stamp}",`);
// the written file must still load, with the same epics
const check = { window: {} };
vm.runInNewContext(out, check);
if (JSON.stringify(check.window.DASH.epics) !== JSON.stringify(D.epics)) { console.error("the rewritten tasks.js does not read back: not written"); process.exit(1); }
writeFileSync(FILE, out);
const notes = JIRA ? [] : ["Jira not read: no --jira command (the Jira tab shows \"Jira not configured\")"];
console.log(read.map((l) => "read    " + l).concat(missed.map((l) => "NOT READ " + l), notes).join("\n") || "no repo line in epics");
process.exit(missed.length ? 2 : 0);

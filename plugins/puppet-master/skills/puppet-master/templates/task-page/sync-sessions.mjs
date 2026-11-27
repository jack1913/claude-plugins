// Rewrites the `sessions` block, `sessionsAsOf` and `updated` in tasks.js from `puppet list`.
// Run it in the same turn as every assign, finish, clear, switch, relaunch or measure.
//   node sync-sessions.mjs [--puppet <path to puppet.mjs>] [--file <path to tasks.js>] [--group <group>]
// --puppet defaults to ../../scripts/puppet.mjs (the template inside the plugin); a copy of this folder
// outside the plugin needs --puppet (or PUPPET_MASTER_SCRIPT). --file defaults to tasks.js beside this script.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const arg = (name) => { const i = process.argv.indexOf(name); return i >= 0 ? process.argv[i + 1] : undefined; };
const PUPPET = arg("--puppet") || process.env.PUPPET_MASTER_SCRIPT || path.join(HERE, "..", "..", "scripts", "puppet.mjs");
const FILE = arg("--file") || path.join(HERE, "tasks.js");
// Sessions whose real backend is not what the transcript names (relaunched under another launcher):
// { "<session name>": "<model label>" }
const NOTES = {};

if (!existsSync(PUPPET)) {
  console.error(`puppet.mjs not found at ${PUPPET}: pass --puppet <path> or set PUPPET_MASTER_SCRIPT`);
  process.exit(1);
}

// --group lists another master's group (the helper's own --group option); without it, the helper's default.
const GROUP = arg("--group");
const out = execFileSync("node", [PUPPET, ...(GROUP ? ["--group", GROUP] : []), "list"], { encoding: "utf8" });
const rows = out.trim().split(/\r?\n/).filter(Boolean).map(line => {
  const name = line.split(/\s+/)[0];
  const tokens = line.split(/\s+/)[1];
  // A line with no token count, such as "u1  changed  (new session id: ask the user whether it was cleared)":
  // keep what the helper says instead of reading a number out of it (it used to write "NaN ()").
  if (!/^\d+$/.test(tokens || "")) {
    const said = line.slice(name.length).trim().replace(/\s{2,}/g, " ");
    return { name, state: said || "unknown", model: NOTES[name] || "-", job: "-", context: "-" };
  }
  const pct = (line.match(/\s(\d+(?:\.\d+)?%)\s/) || [])[1] || "";
  const busy = /\sbusy\s/.test(line) ? "busy" : /\sidle\s/.test(line) ? "idle" : /\sfresh\s/.test(line) ? "fresh" : "";
  const role = (line.match(/interactive (worker|analyst|master)/) || [])[1] || "";
  const active = line.match(/ active (.*?)\s+mod /);
  const switched = (line.match(/switched to (\w+ \w+)/) || [])[1];
  const launch = (line.match(/model (claude-[\w-]+ \w+|fresh)/) || [])[1] || "";
  const model = NOTES[name] || (switched ? switched : launch.replace(/^claude-/, ""));
  const state = role === "master" ? "master" : role === "analyst" ? `analyst (${busy})` : active ? `working (${busy})` : "clean";
  const job = role === "master" ? "coordination" : role === "analyst" ? "analyst" : active ? active[1] : "-";
  const context = tokens === "0" ? "0 (fresh)" : `${Number(tokens).toLocaleString("en-US")} (${pct})`;
  return { name, state, model, job, context };
});

let s = readFileSync(FILE, "utf8");
const esc = v => String(v).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
const block = "  sessions: [" + (rows.length ? "\n" : "") + rows.map(r =>
  `    { name: "${esc(r.name)}", state: "${esc(r.state)}", model: "${esc(r.model)}", job: "${esc(r.job)}", context: "${esc(r.context)}" }`).join(",\n") + (rows.length ? "\n  " : "") + "],";
// the keys may be written plain (sessions:) or quoted ("sessions":), at any indent, as a hand-edited tasks.js has them
const SESSIONS = /^[ \t]*"?sessions"?: *\[[\s\S]*?\],/m;
if (!SESSIONS.test(s)) { console.error("tasks.js has no `sessions: [...],` block"); process.exit(1); }
s = s.replace(SESSIONS, () => block);
const now = new Date();
const pad = n => String(n).padStart(2, "0");
const stamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
s = s.replace(/^[ \t]*"?updated"?: *".*",/m, () => `  updated: "${stamp}",`);
const asOf = `  sessionsAsOf: "${stamp.slice(11)}",`;
const AS_OF = /^[ \t]*"?sessionsAsOf"?: *".*",/m;
s = AS_OF.test(s) ? s.replace(AS_OF, () => asOf) : s.replace(/^  sessions: \[/m, () => asOf + "\n  sessions: [");
writeFileSync(FILE, s);
console.log(rows.map(r => `${r.name} | ${r.state} | ${r.model} | ${r.job} | ${r.context}`).join("\n"));

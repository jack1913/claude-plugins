// fleet-plan: what an opt-in brand-creator workflow will launch, before anything is launched (the fleet gate's numbers).
//
//   brand-creator fleet-plan <workflow> --args <json | @file> [--session-model opus|sonnet|haiku|<model id>] [--json]
//   brand-creator fleet-plan --check
//
// The workflow script (workflows/<name>.js) is executed in a sandbox where agent(), parallel(), pipeline(), phase() and
// log() are stubs: no model is called, nothing is written, the clock and randomness throw as in the real runtime. The
// stub agent answers with the smallest value its schema allows. The plan lists every agent the script would start with
// these args, its agent type, the tier in the agent file, the model that will actually run (per-call model > agent
// file > the session model; CLAUDE_CODE_SUBAGENT_MODEL_FORCE overrides both) and the size guideline it falls under.
// --check runs the static checks over every workflow and agent file (literal meta, agent types that exist, tiers that
// match the agent files, no clock or randomness, the RULES line verbatim).
//
// Exit codes: 0 plan valid / checks pass, 1 the script refuses these args (for example more agents than approved), a
// model above the session model, or a failed check, 2 usage error.
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { parseArgs } from "node:util";
import { pathToFileURL } from "node:url";
import { EXIT, die, mainGuard, pluginRoot } from "./lib/_common.mjs";

const USAGE = `usage: brand-creator fleet-plan <workflow> --args <json | @file> [--session-model opus|sonnet|haiku|<id>] [--json]
       brand-creator fleet-plan --check`;
export const RANK = { haiku: 0, sonnet: 1, opus: 2 };
const FAMILIES = Object.keys(RANK);

export function family(model) {
  const m = String(model || "").toLowerCase();
  return FAMILIES.find((f) => m === f || m.includes(f)) || null;
}

/** Frontmatter of every agents/*.md: {name: {model, tools[], maxTurns, description, body, fields}}. */
export function readAgents(root = pluginRoot()) {
  const dir = path.join(root, "agents");
  const out = {};
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith(".md")).sort()) {
    const text = fs.readFileSync(path.join(dir, f), "utf8");
    if (!text.startsWith("---\n")) die(EXIT.FAIL, `agents/${f}: frontmatter must start on line 1`);
    const end = text.indexOf("\n---\n", 4);
    if (end < 0) die(EXIT.FAIL, `agents/${f}: frontmatter is not closed`);
    const fields = {};
    for (const line of text.slice(4, end).split("\n")) {
      const m = /^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$/.exec(line);
      if (!m) die(EXIT.FAIL, `agents/${f}: frontmatter lines must be single-line key: value (${JSON.stringify(line)})`);
      fields[m[1]] = m[2].trim();
    }
    out[fields.name] = {
      file: `agents/${f}`, fields, model: fields.model, description: fields.description || "",
      tools: (fields.tools || "").split(",").map((t) => t.trim()).filter(Boolean),
      maxTurns: Number(fields.maxTurns), body: text.slice(end + 5),
    };
  }
  return out;
}

/** Split a workflow file into its meta literal and the body; refuse a meta that is not a pure literal. */
export function loadWorkflow(file) {
  const src = fs.readFileSync(file, "utf8");
  const m = /^export const meta = /.exec(src);
  if (!m) die(EXIT.FAIL, `${path.basename(file)}: the first statement must be \`export const meta = {...}\``);
  const start = m[0].length;
  const end = matchBrace(src, start);
  const metaSrc = src.slice(start, end + 1);
  const problems = literalProblems(metaSrc);
  if (problems.length) die(EXIT.FAIL, `${path.basename(file)}: meta must be a pure literal: ${problems.join("; ")}`);
  const meta = vm.runInNewContext(`(${metaSrc})`, Object.create(null));
  return { src, meta, metaSrc, body: src.slice(end + 1) };
}

function matchBrace(s, i) {
  if (s[i] !== "{") die(EXIT.FAIL, "meta must start with {");
  let depth = 0;
  for (let j = i; j < s.length; j++) {
    const c = s[j];
    if (c === "'" || c === '"' || c === "`") { j = skipString(s, j); continue; }
    if (c === "{") depth++;
    else if (c === "}" && --depth === 0) return j;
  }
  die(EXIT.FAIL, "meta object is not closed");
}
function skipString(s, j) {
  const q = s[j];
  for (let k = j + 1; k < s.length; k++) {
    if (s[k] === "\\") { k++; continue; }
    if (s[k] === q) return k;
  }
  die(EXIT.FAIL, "unterminated string in meta");
}

/** Tokens allowed in a literal: strings ('' or ""), numbers, true/false/null, keys followed by ':', and { } [ ] : , */
export function literalProblems(code) {
  const problems = [];
  const re = /\s+|'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?|[A-Za-z_$][A-Za-z0-9_$]*|[{}[\]:,]|./gsy;
  const toks = [];
  let t;
  while ((t = re.exec(code))) if (!/^\s+$/.test(t[0])) toks.push(t[0]);
  toks.forEach((tok, i) => {
    if (/^[A-Za-z_$]/.test(tok)) {
      if (toks[i + 1] === ":" ) return; // a key
      if (["true", "false", "null"].includes(tok)) return;
      problems.push(`identifier ${tok}`);
    } else if (!/^(['"]|-?\d|[{}[\]:,]$)/.test(tok)) {
      problems.push(`token ${JSON.stringify(tok)}`);
    }
  });
  return problems;
}

/** Smallest value a JSON schema allows (stub agent answers). */
export function stubFor(schema) {
  if (!schema || typeof schema !== "object") return "stub";
  if (schema.enum) return schema.enum[0];
  switch (schema.type) {
    case "object": {
      const o = {};
      for (const k of schema.required || []) o[k] = stubFor((schema.properties || {})[k]);
      return o;
    }
    case "array": return Array.from({ length: Math.max(1, schema.minItems || 0) }, () => stubFor(schema.items));
    case "integer": case "number": return 0;
    case "boolean": return false;
    default: return "stub";
  }
}

/**
 * Run a workflow with stub hooks. `respond(call)` may return a value for a call (default: the schema stub); returning
 * undefined keeps the default, `null` simulates a stopped or failed agent.
 */
export async function dryRun(file, args, { respond } = {}) {
  const { meta, body } = loadWorkflow(file);
  const calls = [], logs = [], phases = [];
  let current = null;
  const agent = async (prompt, opts = {}) => {
    if (typeof prompt !== "string") throw new Error("agent() needs a prompt string");
    const call = { n: calls.length + 1, prompt, label: opts.label || null, phase: opts.phase || current, agentType: opts.agentType || null, model: opts.model || null, schema: opts.schema || null, isolation: opts.isolation || null };
    calls.push(call);
    const r = respond ? respond(call) : undefined;
    if (r !== undefined) return r;
    return opts.schema ? stubFor(opts.schema) : "stub";
  };
  const settle = (p) => Promise.resolve().then(p).catch(() => null);
  const parallel = async (thunks) => {
    if (!Array.isArray(thunks)) throw new Error("parallel() takes an array of functions");
    if (thunks.length > 4096) throw new Error("parallel(): more than 4096 items");
    return Promise.all(thunks.map((t) => settle(t)));
  };
  const pipeline = async (items, ...stages) => {
    if (items.length > 4096) throw new Error("pipeline(): more than 4096 items");
    return Promise.all(items.map((item, i) => settle(async () => {
      let prev = item;
      for (const s of stages) prev = await s(prev, item, i);
      return prev;
    })));
  };
  const ctx = vm.createContext({
    agent, parallel, pipeline, args,
    phase: (t) => { current = t; phases.push(t); },
    log: (m) => logs.push(String(m)),
    budget: { total: null, spent: () => 0, remaining: () => Infinity },
    workflow: () => { throw new Error("workflow() is not used by brand-creator workflows"); },
  });
  vm.runInContext(`(() => {
    const D = Date;
    Date.now = () => { throw new Error('Date.now() is not available in a workflow'); };
    Math.random = () => { throw new Error('Math.random() is not available in a workflow'); };
    globalThis.Date = new Proxy(D, {
      construct(t, a) { if (!a.length) throw new Error('new Date() is not available in a workflow'); return new t(...a); },
      apply() { throw new Error('Date() is not available in a workflow'); },
    });
  })()`, ctx);
  let result = null, error = null;
  try {
    const script = new vm.Script(`(async () => {\n${body}\n})()`, { filename: path.basename(file) });
    const value = await script.runInContext(ctx);
    result = value === undefined ? null : JSON.parse(JSON.stringify(value)); // plain data out of the sandbox realm, as the runtime returns it
  } catch (e) {
    error = e && e.message ? e.message : String(e);
  }
  return { meta, calls, logs, phases, result, error };
}

export function guideline(n) {
  if (n < 5) return "small (under 5)";
  if (n < 10) return "medium (under 10)";
  if (n < 50) return "large (under 50)";
  return "above large";
}

/** The model each call will run on. */
export function resolve(calls, agents, { session, env = process.env }) {
  const sessionFam = family(session);
  const force = /^(1|true)$/i.test(String(env.CLAUDE_CODE_SUBAGENT_MODEL_FORCE || ""));
  const envModel = (env.CLAUDE_CODE_SUBAGENT_MODEL || "").trim();
  return calls.map((c) => {
    const name = String(c.agentType || "").replace(/^brand-creator:/, "");
    const a = agents[name];
    const fileModel = a ? a.model : null;
    let runs, why;
    if (force) {
      runs = envModel && envModel !== "inherit" ? envModel : session;
      why = "CLAUDE_CODE_SUBAGENT_MODEL_FORCE is set: agent files and per-call models are ignored";
    } else if (c.model) {
      runs = c.model; why = `per-call model (capped to the session model; agent file says ${fileModel})`;
    } else if (fileModel && fileModel !== "inherit") {
      runs = fileModel; why = "agent file";
    } else {
      runs = envModel && envModel !== "inherit" ? envModel : session; why = "no model set: the session model";
    }
    const fam = family(runs);
    const exact = fam && fam === sessionFam ? `${runs} = the session model (${session})` : runs;
    const above = fam && sessionFam ? RANK[fam] > RANK[sessionFam] : false;
    return { ...c, agent: name, known: Boolean(a), fileModel, runs, family: fam, exact, why, above, maxTurns: a ? a.maxTurns : null };
  });
}

export const RULES_LINE = () => {
  const t = fs.readFileSync(path.join(pluginRoot(), "skills", "brand-creator", "SKILL.md"), "utf8");
  const lines = t.split("\n").filter((l) => l.startsWith("RULES: "));
  if (lines.length !== 1) die(EXIT.FAIL, "SKILL.md must hold exactly one RULES line");
  return lines[0];
};

/** Static checks over one workflow file; returns a list of problems (empty = pass). */
export function staticProblems(file, agents) {
  const problems = [];
  let w;
  try { w = loadWorkflow(file); } catch (e) { return [e.message]; }
  const { src, meta, body } = w;
  const name = path.basename(file, ".js");
  if (meta.name !== name) problems.push(`meta.name ${JSON.stringify(meta.name)} must equal the file name ${name}`);
  if (!/^[a-z][a-z0-9-]*$/.test(String(meta.name))) problems.push("meta.name must be a lower-case slug");
  if (!meta.description || typeof meta.description !== "string") problems.push("meta.description is required");
  const code = body.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, ""); // comments may name what is forbidden
  for (const bad of [/\bDate\.now\b/, /\bMath\.random\b/, /new Date\(\s*\)/, /\bimport\s*\(/, /\brequire\s*\(/, /\bprocess\./, /\bisolation\s*:/]) {
    if (bad.test(code)) problems.push(`forbidden in a workflow: ${bad}`);
  }
  try { new vm.Script(`(async () => {\n${body}\n})()`); } catch (e) { problems.push(`does not parse: ${e.message}`); }
  const rules = src.split("\n").filter((l) => l.startsWith("const RULES = "));
  const want = RULES_LINE();
  if (rules.length !== 1 || rules[0] !== `const RULES = '${want.replace(/'/g, "\\'")}'`) problems.push("const RULES must hold the RULES line of SKILL.md verbatim");
  const tierBlock = /const AGENT_TIER = (\{[^}]*\})/.exec(src);
  if (!tierBlock) problems.push("const AGENT_TIER = {...} is missing");
  else {
    const tiers = vm.runInNewContext(`(${tierBlock[1]})`, Object.create(null));
    for (const [a, tier] of Object.entries(tiers)) {
      if (!agents[a]) problems.push(`AGENT_TIER names ${a}, which is not an agent in agents/`);
      else if (agents[a].model !== tier) problems.push(`AGENT_TIER says ${a} is ${tier}, the agent file says ${agents[a].model}`);
    }
  }
  const titles = new Set((meta.phases || []).map((p) => p.title));
  const used = new Set([...body.matchAll(/phase\('([^']+)'\)|phase: '([^']+)'/g)].map((m) => m[1] || m[2]));
  for (const t of used) if (!titles.has(t)) problems.push(`phase ${JSON.stringify(t)} has no entry in meta.phases`);
  for (const t of titles) if (!used.has(t)) problems.push(`meta.phases lists ${JSON.stringify(t)}, which no phase() call uses`);
  if (!/RESUME NOTES:/.test(src)) problems.push("the header comment must carry RESUME NOTES");
  if (!/\.filter\(Boolean\)/.test(body)) problems.push("fan-out results must be filtered with .filter(Boolean)");
  return problems;
}

export function agentProblems(agents) {
  const problems = [];
  const want = RULES_LINE();
  const allowed = new Set(["name", "description", "model", "effort", "maxTurns", "autoCompactWindow", "tools", "disallowedTools", "skills", "memory", "background", "omitClaudeMd", "color"]);
  for (const [n, a] of Object.entries(agents)) {
    for (const k of Object.keys(a.fields)) if (!allowed.has(k)) problems.push(`${a.file}: field ${k} is ignored or not allowed in a plugin agent`);
    if (!a.description.startsWith("Only for brand-creator workflows or an approved fleet; do not auto-delegate.")) problems.push(`${a.file}: description prefix`);
    if (!a.body.split("\n").includes(want)) problems.push(`${a.file}: the RULES line is not verbatim`);
    if (!a.tools.length) problems.push(`${a.file}: tools allowlist missing`);
    if (a.tools.some((t) => /^Agent\b|^Task\b/.test(t))) problems.push(`${a.file}: an agent may not start agents`);
    if (!Number.isInteger(a.maxTurns) || a.maxTurns < 5) problems.push(`${a.file}: maxTurns missing`);
    if (!FAMILIES.includes(a.model)) problems.push(`${a.file}: model must be opus, sonnet or haiku`);
    if (/\$\{CLAUDE_PLUGIN_(ROOT|DATA)\}/.test(a.body)) problems.push(`${a.file}: paths come in the prompt, not from plugin variables`);
    if (n !== path.basename(a.file, ".md")) problems.push(`${a.file}: name must equal the file name`);
  }
  return problems;
}

function readArgs(v) {
  if (!v) die(EXIT.USAGE, `--args is required (the same JSON the workflow will get)\n${USAGE}`);
  const text = v.startsWith("@") ? fs.readFileSync(v.slice(1), "utf8") : v;
  try { return JSON.parse(text); } catch (e) { die(EXIT.USAGE, `--args is not JSON: ${e.message}`); }
}

async function main() {
  let values, positionals;
  try {
    ({ values, positionals } = parseArgs({ args: process.argv.slice(2), allowPositionals: true, strict: true, options: {
      args: { type: "string" }, "session-model": { type: "string" }, json: { type: "boolean", default: false },
      check: { type: "boolean", default: false }, help: { type: "boolean", short: "h", default: false } } }));
  } catch (e) { die(EXIT.USAGE, `${e.message}\n${USAGE}`); }
  if (values.help) { console.log(USAGE); return EXIT.PASS; }
  const root = pluginRoot();
  const agents = readAgents(root);
  const wfDir = path.join(root, "workflows");
  if (values.check) {
    const problems = agentProblems(agents);
    const files = fs.readdirSync(wfDir).filter((f) => f.endsWith(".js")).sort();
    for (const f of files) for (const p of staticProblems(path.join(wfDir, f), agents)) problems.push(`workflows/${f}: ${p}`);
    for (const p of problems) console.log(`FAIL ${p}`);
    console.log(`${problems.length ? "FAIL" : "PASS"}: ${Object.keys(agents).length} agents, ${files.length} workflows checked`);
    return problems.length ? EXIT.FAIL : EXIT.PASS;
  }
  if (positionals.length !== 1) die(EXIT.USAGE, USAGE);
  const file = path.join(wfDir, `${positionals[0]}.js`);
  if (!/^[a-z][a-z0-9-]*$/.test(positionals[0]) || !fs.existsSync(file)) {
    die(EXIT.USAGE, `no workflow ${positionals[0]} (have: ${fs.readdirSync(wfDir).filter((f) => f.endsWith(".js")).map((f) => f.slice(0, -3)).join(", ")})`);
  }
  const args = readArgs(values.args);
  const session = values["session-model"] || (args && args.ceiling);
  if (!family(session)) die(EXIT.USAGE, "--session-model (or args.ceiling) must name the session model: opus, sonnet, haiku or a model id");
  const run = await dryRun(file, args);
  const rows = resolve(run.calls, agents, { session });
  const counts = {};
  for (const r of rows) counts[r.runs] = (counts[r.runs] || 0) + 1;
  const above = rows.filter((r) => r.above);
  const unknown = rows.filter((r) => !r.known);
  const plan = {
    workflow: run.meta.name, agents: rows.length, guideline: guideline(rows.length), session,
    force: /^(1|true)$/i.test(String(process.env.CLAUDE_CODE_SUBAGENT_MODEL_FORCE || "")),
    models: counts, max_turns: rows.reduce((s, r) => s + (r.maxTurns || 0), 0),
    approved_agents: args ? args.approved_agents : null, refused: run.error,
    calls: rows.map((r) => ({ n: r.n, phase: r.phase, label: r.label, agent: r.agentType, agent_file_model: r.fileModel, runs: r.exact, why: r.why })),
    above_session: above.map((r) => r.n), unknown_agents: unknown.map((r) => r.agentType),
  };
  if (values.json) console.log(JSON.stringify(plan, null, 2));
  else {
    console.log(`fleet plan: ${plan.workflow}: ${plan.agents} agent(s), size guideline ${plan.guideline}`);
    for (const c of plan.calls) console.log(`  ${String(c.n).padStart(2)}. ${String(c.phase || "").padEnd(9)} ${String(c.label || "").padEnd(18)} ${c.agent}  ${c.runs}  (${c.why})`);
    console.log(`models that will run: ${Object.entries(counts).map(([m, n]) => `${n} x ${m}`).join(", ") || "none"}; session model ${session} is the ceiling`);
    console.log(`CLAUDE_CODE_SUBAGENT_MODEL_FORCE: ${plan.force ? "set (every agent runs on " + (process.env.CLAUDE_CODE_SUBAGENT_MODEL || "the session model") + ")" : "not set"}`);
    console.log(`rough cost: ${plan.agents} agent pass(es), each about what that step costs single-thread, plus your coordination; at most ${plan.max_turns} turns in total (maxTurns). Watch /workflows for token use; stop early if it runs long.`);
    if (run.error) console.log(`REFUSED by the script before any agent started: ${run.error}`);
    else console.log(`approval needed: ${plan.agents} agents (args.approved_agents = ${plan.approved_agents})`);
    for (const r of above) console.log(`ABOVE THE SESSION MODEL: call ${r.n} would run ${r.runs} in a ${session} session; pass args.ceiling = "${family(session)}"`);
    for (const r of unknown) console.log(`UNKNOWN AGENT TYPE: ${r.agentType}`);
  }
  return run.error || above.length || unknown.length ? EXIT.FAIL : EXIT.PASS;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) await mainGuard(main);

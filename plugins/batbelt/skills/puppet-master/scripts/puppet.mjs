#!/usr/bin/env node
// puppet.mjs — the puppet-master helper: start, measure, compact, restart and close
// background Claude Code worker sessions. Node built-ins only; every child process
// runs through spawnSync with shell: false. Every failure is loud: `puppet: <message>`
// on stderr, exit 2 for a usage error, 1 for an operational failure.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

export class PuppetError extends Error {
  constructor(message, exitCode = 1) {
    super(message);
    this.name = "PuppetError";
    this.exitCode = exitCode;
  }
}

export function configDir(env) {
  return env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude");
}

// Parse a transcript's JSONL. Only the LAST non-empty line may be unparseable (the
// session may be mid-write); a bad line anywhere else means the file is not what we
// think it is.
function parseTranscript(text) {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== "");
  const entries = [];
  lines.forEach((line, i) => {
    try {
      entries.push(JSON.parse(line));
    } catch {
      if (i !== lines.length - 1) {
        throw new PuppetError(`transcript line ${i + 1} is not valid JSON`);
      }
    }
  });
  return entries;
}

// The worker's context size: the last main-thread assistant usage, unless a
// compact_boundary came after it (a worker measured right after `cycle`).
export function transcriptTokens(text) {
  let usage = null;
  let boundary = null;
  for (const e of parseTranscript(text)) {
    if (e.isSidechain) continue;
    if (e.type === "assistant" && e.message?.usage) {
      const u = e.message.usage;
      usage =
        (u.input_tokens ?? 0) +
        (u.cache_read_input_tokens ?? 0) +
        (u.cache_creation_input_tokens ?? 0);
      boundary = null;
    } else if (e.type === "system" && e.subtype === "compact_boundary") {
      const post = e.compactMetadata?.postTokens;
      if (typeof post !== "number") {
        throw new PuppetError("transcript has a compact_boundary without a numeric postTokens");
      }
      boundary = post;
    }
  }
  if (boundary !== null) return { tokens: boundary, source: "compact_boundary" };
  if (usage !== null) return { tokens: usage, source: "usage" };
  throw new PuppetError("transcript has no assistant usage and no compact boundary");
}

export function findTranscript(projectsDir, sessionId) {
  const hits = [];
  let dirs;
  try {
    dirs = fs.readdirSync(projectsDir, { withFileTypes: true });
  } catch (e) {
    throw new PuppetError(`cannot read ${projectsDir}: ${e.message}`);
  }
  for (const d of dirs) {
    if (!d.isDirectory()) continue;
    const p = path.join(projectsDir, d.name, `${sessionId}.jsonl`);
    if (fs.existsSync(p)) hits.push(p);
  }
  if (hits.length === 0) {
    throw new PuppetError(`no transcript for session ${sessionId} under ${projectsDir}`);
  }
  if (hits.length > 1) {
    throw new PuppetError(`several transcripts for session ${sessionId}: ${hits.join(", ")}`);
  }
  return hits[0];
}

function positiveInt(value, what) {
  const s = String(value).trim();
  if (!/^\d+$/.test(s) || Number(s) <= 0) {
    throw new PuppetError(`${what} must be a positive integer, got "${value}"`, 2);
  }
  return Number(s);
}

export function resolveWindow({ flag, recorded, env } = {}) {
  if (flag !== undefined) return { window: positiveInt(flag, "--window"), source: "flag" };
  if (recorded !== undefined) {
    return { window: positiveInt(recorded, "the recorded window"), source: "recorded" };
  }
  if (env !== undefined && env !== "") {
    return { window: positiveInt(env, "PUPPET_CONTEXT_WINDOW"), source: "env" };
  }
  throw new PuppetError(
    "no context window: pass --window <tokens>, run `cycle` once to record it, or set PUPPET_CONTEXT_WINDOW",
  );
}

export function percent(tokens, window) {
  return Math.round((tokens / window) * 1000) / 10;
}

// --- the claude CLI ------------------------------------------------------------------

function claudeBin(deps) {
  return deps.env.PUPPET_CLAUDE_BIN ?? "claude";
}

function claude(deps, args, opts = {}) {
  const r = deps.run(claudeBin(deps), args, opts);
  if (r.error) {
    // No shell runs the CLI, so an npm-installed `claude.cmd` shim cannot be launched.
    throw new PuppetError(
      `cannot run ${claudeBin(deps)}: ${r.error.message} (set PUPPET_CLAUDE_BIN to the claude executable's full path)`,
    );
  }
  return r;
}

function claudeOk(deps, args, opts = {}) {
  const r = claude(deps, args, opts);
  if (r.code !== 0) {
    const text = (r.stderr || r.stdout || "").trim();
    throw new PuppetError(`claude ${args[0]} failed (exit ${r.code}): ${text}`);
  }
  return r;
}

export function listAgents(deps) {
  const r = claudeOk(deps, ["agents", "--json"]);
  let agents;
  try {
    agents = JSON.parse(r.stdout);
  } catch (e) {
    throw new PuppetError(`claude agents --json printed invalid JSON: ${e.message}`);
  }
  if (!Array.isArray(agents)) throw new PuppetError("claude agents --json did not print a list");
  return agents;
}

export function findWorker(agents, key) {
  const hits = agents.filter((a) => a.name === key || a.id === key || a.sessionId === key);
  if (hits.length === 0) throw new PuppetError(`no session named or numbered "${key}"`);
  if (hits.length > 1) {
    const ids = hits.map((a) => a.id ?? a.sessionId).join(", ");
    throw new PuppetError(`"${key}" is ambiguous: sessions ${ids}; use an id`);
  }
  return hits[0];
}

// Observed on a live background session: `state` working → done (with `status`
// busy → idle); `blocked` is a session waiting on a prompt, so it is mid-task. A state
// in neither set is unknown, and nothing that needs a task boundary acts on it.
export const IDLE_STATES = new Set(["done", "idle"]);
export const BUSY_STATES = new Set(["working", "busy", "blocked"]);

// A session resumes from its own project directory, so every printed resume command
// carries the worker's cwd.
function resumeHint(cwd, sessionId, { bg = true } = {}) {
  const cmd = `claude ${bg ? "--bg " : ""}--resume ${sessionId}`;
  return cwd ? `cd "${cwd}" && ${cmd}` : cmd;
}

export function workerState(agent) {
  return agent.state ?? agent.status ?? "unknown";
}

// A window the user opened has no supported remote stop; stopping one is theirs to do.
function requireBackground(agent, verb) {
  if (agent.kind !== "background") {
    throw new PuppetError(`${agent.name} is not a background worker (kind ${agent.kind}); not ${verb} it`);
  }
  return agent;
}

// --- the worker registry --------------------------------------------------------------

export function statePath(deps) {
  return deps.env.PUPPET_STATE ?? path.join(configDir(deps.env), "puppet-master", "workers.json");
}

export function loadRegistry(deps) {
  const p = statePath(deps);
  let text;
  try {
    text = deps.fs.readFileSync(p, "utf8");
  } catch (e) {
    if (e.code === "ENOENT") return { workers: {} };
    throw new PuppetError(`cannot read ${p}: ${e.message}`);
  }
  let reg;
  try {
    reg = JSON.parse(text);
  } catch (e) {
    throw new PuppetError(`${p} is not valid JSON: ${e.message}`);
  }
  if (!reg || typeof reg.workers !== "object") throw new PuppetError(`${p} has no workers map`);
  return reg;
}

export function saveRegistry(deps, reg) {
  const p = statePath(deps);
  deps.fs.mkdirSync(path.dirname(p), { recursive: true });
  const tmp = `${p}.tmp`;
  deps.fs.writeFileSync(tmp, `${JSON.stringify(reg, null, 2)}\n`);
  deps.fs.renameSync(tmp, p);
}

// --- measuring ------------------------------------------------------------------------

function projectsDir(deps) {
  return path.join(configDir(deps.env), "projects");
}

function measureAgent(deps, agent, record, { window } = {}) {
  const w = resolveWindow({
    flag: window,
    recorded: record?.window,
    env: deps.env.PUPPET_CONTEXT_WINDOW,
  });
  const file = findTranscript(projectsDir(deps), agent.sessionId);
  const t = transcriptTokens(deps.fs.readFileSync(file, "utf8"));
  return {
    name: agent.name,
    id: agent.id,
    tokens: t.tokens,
    percent: percent(t.tokens, w.window),
    window: w.window,
    windowSource: w.source,
    state: workerState(agent),
    tokenSource: t.source,
  };
}

export function measureWorker(deps, key, { window } = {}) {
  const agent = findWorker(listAgents(deps), key);
  const record = loadRegistry(deps).workers[agent.name];
  return measureAgent(deps, agent, record, { window });
}

function measureLine(m) {
  return `${m.name}  ${m.tokens}  ${m.percent}%  ${m.state}  (window ${m.window} from ${m.windowSource})`;
}

// --- spawning -------------------------------------------------------------------------

// Windows caps a command line near 32767 characters, and the brief is one argument.
const MAX_BRIEF = 30000;
const NAME_RE = /^[A-Za-z0-9._-]+$/;

function pathApi(deps) {
  return (deps.platform ?? process.platform) === "win32" ? path.win32 : path.posix;
}

// `claude --bg` prints "backgrounded · <id> · <name>" followed by hint lines.
export function parseBgId(stdout) {
  const m = /\bbackgrounded\b[^0-9a-f\n]*([0-9a-f]{6,})\b/.exec(stdout);
  if (!m) throw new PuppetError(`cannot find a session id in claude --bg output: ${stdout.trim()}`);
  return m[1];
}

export function checkoutOf(deps, cwd) {
  const p = pathApi(deps);
  const r = deps.run("git", ["-C", cwd, "rev-parse", "--show-toplevel"], {});
  if (r.error) throw new PuppetError(`cannot run git to find the checkout of ${cwd}: ${r.error.message}`);
  if (r.code === 0 && r.stdout.trim()) return p.resolve(r.stdout.trim());
  // Only a folder outside any repository is its own checkout; any other git failure
  // would weaken the one-editor-per-checkout lock, so it is an error.
  if (/not a git repository/i.test(r.stderr)) return p.resolve(cwd);
  throw new PuppetError(`git rev-parse failed in ${cwd} (exit ${r.code}): ${r.stderr.trim()}`);
}

function checkoutKey(deps, checkout) {
  const p = pathApi(deps);
  const k = p.resolve(checkout);
  return p === path.win32 ? k.toLowerCase() : k;
}

function isLive(agents, rec) {
  return agents.some((a) => (rec.id && a.id === rec.id) || a.sessionId === rec.sessionId);
}

function readBrief(deps, briefFile) {
  let text;
  try {
    text = deps.fs.readFileSync(briefFile, "utf8");
  } catch (e) {
    throw new PuppetError(`cannot read brief file ${briefFile}: ${e.message}`, 2);
  }
  if (!text.trim()) throw new PuppetError(`brief file ${briefFile} is empty`, 2);
  if (text.length > MAX_BRIEF) {
    throw new PuppetError(`brief file ${briefFile} is over ${MAX_BRIEF} characters`, 2);
  }
  return text;
}

export function spawnWorker(deps, name, cwd, briefFile) {
  if (!NAME_RE.test(name)) throw new PuppetError(`worker name "${name}" must match [A-Za-z0-9._-]+`, 2);
  const brief = readBrief(deps, briefFile);
  const agents = listAgents(deps);
  const clash = agents.find((a) => a.name === name);
  if (clash) {
    throw new PuppetError(`a live session is already named "${name}" (id ${clash.id ?? clash.sessionId})`, 2);
  }
  const checkout = checkoutOf(deps, cwd);
  const key = checkoutKey(deps, checkout);
  const reg = loadRegistry(deps);
  for (const [other, rec] of Object.entries(reg.workers)) {
    if (checkoutKey(deps, rec.checkout) !== key) continue;
    if (isLive(agents, rec)) {
      throw new PuppetError(
        `worker "${other}" (id ${rec.id}) is already editing ${rec.checkout}; one editing worker per checkout — close it or use another checkout`,
      );
    }
    deps.out(`pruned stale record ${other} (resume: ${resumeHint(rec.cwd, rec.sessionId)})`);
    delete reg.workers[other];
  }
  const r = claudeOk(deps, ["--bg", "--name", name, brief], { cwd });
  const id = parseBgId(r.stdout);
  const started = listAgents(deps).find((a) => a.id === id);
  if (!started) throw new PuppetError(`started ${name} as ${id}, but claude agents does not list it`);
  reg.workers[name] = { id, sessionId: started.sessionId, cwd: pathApi(deps).resolve(cwd), checkout };
  saveRegistry(deps, reg);
  return { name, id, sessionId: started.sessionId, checkout };
}

// --- cycling: stop, headless compact, verify, restart -----------------------------------

export const RESUME_PROMPT =
  "Your context was compacted by the master at a task boundary. Wait for your next task from the master; do not start new work.";

// The `-p --output-format json` result of a /compact. Its exit code and is_error are not
// proof of a compaction (a mangled `/compact` runs as an ordinary turn and succeeds), so
// the caller still verifies the boundary; this only yields the model's context window.
export function parseCompactResult(stdout) {
  let r;
  try {
    r = JSON.parse(stdout);
  } catch (e) {
    throw new PuppetError(`compact result is not JSON: ${e.message}`);
  }
  if (r.is_error) throw new PuppetError(`compact reported an error: ${r.result ?? r.subtype ?? "unknown"}`);
  const windows = Object.values(r.modelUsage ?? {})
    .map((m) => m?.contextWindow)
    .filter((w) => Number.isInteger(w) && w > 0);
  if (windows.length === 0) throw new PuppetError("compact result has no modelUsage contextWindow");
  return { contextWindow: Math.max(...windows) };
}

function newBoundaries(text, since) {
  return parseTranscript(text).filter(
    (e) =>
      !e.isSidechain &&
      e.type === "system" &&
      e.subtype === "compact_boundary" &&
      Date.parse(e.timestamp) >= since.getTime(),
  );
}

export function cycleWorker(deps, key, focus, { nextBriefFile } = {}) {
  const agent = requireBackground(findWorker(listAgents(deps), key), "cycling");
  const state = workerState(agent);
  if (!IDLE_STATES.has(state)) {
    throw new PuppetError(`${agent.name} is not at a task boundary (state ${state}); not cycling`);
  }
  const prompt = nextBriefFile ? readBrief(deps, nextBriefFile) : RESUME_PROMPT;
  const reg = loadRegistry(deps);
  const record = reg.workers[agent.name] ?? {};
  const sid = agent.sessionId;
  const cwd = record.cwd ?? agent.cwd;
  const file = findTranscript(projectsDir(deps), sid);
  const before = transcriptTokens(deps.fs.readFileSync(file, "utf8")).tokens;
  const restart = resumeHint(cwd, sid);

  claudeOk(deps, ["stop", agent.id]);
  let window;
  try {
    const since = deps.now();
    const r = claude(deps, ["-p", "--resume", sid, "--output-format", "json", `/compact ${focus}`], { cwd });
    if (r.code !== 0) throw new PuppetError(`claude -p exited ${r.code}: ${(r.stderr || r.stdout).trim()}`);
    window = parseCompactResult(r.stdout).contextWindow;
    if (newBoundaries(deps.fs.readFileSync(file, "utf8"), since).length === 0) {
      throw new PuppetError("the transcript gained no new compact_boundary");
    }
  } catch (e) {
    if (!(e instanceof PuppetError)) throw e;
    throw new PuppetError(`${agent.name} is stopped and NOT compacted: ${e.message}. Restart it with: ${restart}`);
  }
  const after = transcriptTokens(deps.fs.readFileSync(file, "utf8")).tokens;

  let id;
  try {
    id = parseBgId(claudeOk(deps, ["--bg", "--resume", sid, prompt], { cwd }).stdout);
  } catch (e) {
    if (!(e instanceof PuppetError)) throw e;
    throw new PuppetError(`${agent.name} is compacted but stopped: ${e.message}. Restart it with: ${restart}`);
  }
  reg.workers[agent.name] = {
    ...record,
    id,
    sessionId: sid,
    cwd,
    checkout: record.checkout ?? checkoutOf(deps, cwd),
    window,
  };
  saveRegistry(deps, reg);
  return { name: agent.name, before, after, window, id };
}

// --- closing: stop and remove; the transcript stays resumable --------------------------

export function closeWorker(deps, key) {
  const agents = listAgents(deps);
  const reg = loadRegistry(deps);
  const live = agents.filter((a) => a.name === key || a.id === key || a.sessionId === key);
  let name;
  let id;
  let sessionId;
  let cwd;
  if (live.length > 0) {
    const agent = requireBackground(findWorker(agents, key), "closing");
    ({ name, id, sessionId } = agent);
    cwd = reg.workers[name]?.cwd ?? agent.cwd;
    claudeOk(deps, ["stop", id]);
  } else {
    const hit = Object.entries(reg.workers).find(
      ([n, r]) => n === key || r.id === key || r.sessionId === key,
    );
    if (!hit) throw new PuppetError(`no live session and no recorded worker named or numbered "${key}"`);
    [name, { id, sessionId, cwd }] = hit;
  }
  const resume = resumeHint(cwd, sessionId, { bg: false });
  // Never with --discard-unpushed / --force-remove-worktree: if rm refuses, the user decides.
  try {
    claudeOk(deps, ["rm", id]);
  } catch (e) {
    if (!(e instanceof PuppetError)) throw e;
    throw new PuppetError(`${name} is stopped but NOT removed (id ${id}; resume: ${resume}): ${e.message}`);
  }
  if (reg.workers[name]) {
    delete reg.workers[name];
    saveRegistry(deps, reg);
  }
  return { name, sessionId, resume };
}

// --- subcommands ----------------------------------------------------------------------

const USAGE = [
  "usage: puppet.mjs <command> ...",
  "  measure <worker> [--window N] [--json]",
  "  list [--window N] [--json]",
  "  spawn <name> <cwd> <brief-file>",
  "  cycle <worker> <focus> [--next <brief-file>]",
  "  close <worker>",
].join("\n");

const FLAGS = { "--window": true, "--json": false, "--next": true };

function parseArgs(args) {
  const positional = [];
  const flags = {};
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a.startsWith("--")) {
      if (!(a in FLAGS)) throw new PuppetError(`unknown flag ${a}\n${USAGE}`, 2);
      if (FLAGS[a]) {
        if (i + 1 >= args.length) throw new PuppetError(`${a} needs a value\n${USAGE}`, 2);
        flags[a.slice(2)] = args[++i];
      } else {
        flags[a.slice(2)] = true;
      }
    } else {
      positional.push(a);
    }
  }
  return { positional, flags };
}

function wantPositional(positional, n, cmd) {
  if (positional.length !== n) {
    throw new PuppetError(`${cmd} takes ${n} argument(s), got ${positional.length}\n${USAGE}`, 2);
  }
}

function cmdMeasure(deps, positional, flags) {
  wantPositional(positional, 1, "measure");
  const m = measureWorker(deps, positional[0], { window: flags.window });
  deps.out(flags.json ? JSON.stringify(m) : measureLine(m));
  return 0;
}

function cmdList(deps, positional, flags) {
  wantPositional(positional, 0, "list");
  const agents = listAgents(deps);
  const reg = loadRegistry(deps);
  const rows = [];
  let failed = false;
  const seen = new Set();
  for (const a of agents.filter((x) => x.kind === "background")) {
    seen.add(a.name);
    try {
      rows.push(measureAgent(deps, a, reg.workers[a.name], { window: flags.window }));
    } catch (e) {
      if (!(e instanceof PuppetError)) throw e;
      failed = true;
      const why = e.message.startsWith("no transcript") ? "no transcript" : e.message;
      rows.push({ name: a.name, id: a.id, error: why });
    }
  }
  // A recorded worker that is no longer listed has exited or was stopped: report how to
  // resume it, then drop the record (the transcript stays, so nothing is lost).
  let pruned = false;
  for (const [name, rec] of Object.entries(reg.workers)) {
    if (seen.has(name)) continue;
    rows.push({ name, id: rec.id, state: "gone", sessionId: rec.sessionId, cwd: rec.cwd });
    delete reg.workers[name];
    pruned = true;
  }
  if (pruned) saveRegistry(deps, reg);
  for (const r of rows) {
    if (flags.json) deps.out(JSON.stringify(r));
    else if (r.error) deps.out(`${r.name}  ?  (${r.error})`);
    else if (r.state === "gone") deps.out(`${r.name}  gone  (resume: ${resumeHint(r.cwd, r.sessionId)})`);
    else deps.out(measureLine(r));
  }
  return failed ? 1 : 0;
}

function cmdSpawn(deps, positional) {
  wantPositional(positional, 3, "spawn");
  const w = spawnWorker(deps, ...positional);
  deps.out(`spawned ${w.name} id=${w.id} in ${w.checkout}`);
  return 0;
}

function cmdCycle(deps, positional, flags) {
  wantPositional(positional, 2, "cycle");
  const c = cycleWorker(deps, positional[0], positional[1], { nextBriefFile: flags.next });
  deps.out(
    `cycled ${c.name}: ${c.before}→${c.after} tokens (${percent(c.before, c.window)}%→${percent(c.after, c.window)}%), resumed id=${c.id}`,
  );
  return 0;
}

function cmdClose(deps, positional) {
  wantPositional(positional, 1, "close");
  const c = closeWorker(deps, positional[0]);
  deps.out(`closed ${c.name} (resume: ${c.resume})`);
  return 0;
}

const COMMANDS = { measure: cmdMeasure, list: cmdList, spawn: cmdSpawn, cycle: cmdCycle, close: cmdClose };

export async function main(argv, deps) {
  try {
    const [cmd, ...rest] = argv;
    if (!cmd || !(cmd in COMMANDS)) {
      throw new PuppetError(cmd ? `unknown command ${cmd}\n${USAGE}` : USAGE, 2);
    }
    const { positional, flags } = parseArgs(rest);
    return await COMMANDS[cmd](deps, positional, flags);
  } catch (e) {
    if (e instanceof PuppetError) {
      deps.err(`puppet: ${e.message}`);
      return e.exitCode;
    }
    deps.err(`puppet: unexpected error: ${e.stack ?? e}`);
    return 1;
  }
}

export function realDeps() {
  return {
    run(cmd, args, opts = {}) {
      const r = spawnSync(cmd, args, {
        cwd: opts.cwd,
        encoding: "utf8",
        shell: false,
        windowsHide: true,
      });
      return { code: r.status ?? 1, stdout: r.stdout ?? "", stderr: r.stderr ?? "", error: r.error };
    },
    env: process.env,
    platform: process.platform,
    out: (line) => process.stdout.write(`${line}\n`),
    err: (line) => process.stderr.write(`${line}\n`),
    now: () => new Date(),
    fs,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exit(await main(process.argv.slice(2), realDeps()));
}

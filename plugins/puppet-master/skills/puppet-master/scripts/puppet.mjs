#!/usr/bin/env node
// puppet.mjs — the puppet-master helper: start, measure, compact, restart and close
// background Claude Code worker sessions. Node built-ins only; every child process
// runs through spawnSync with shell: false. Every failure is loud: `puppet: <message>`
// on stderr, exit 2 for a usage error, 1 for an operational failure.

import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { addFinding, decide, headline, markShipped, summarize, unreviewedReport } from "./analyst.mjs";
import { harvest, resolveLogsDir } from "./harvest.mjs";

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
  return tokensOf(parseTranscript(text));
}

// What one read of a transcript tells: its size, the smallest size it was automatically
// compacted at, and the model and effort of its last main-thread API request. The size
// throws as transcriptTokens does; the rest never throws and is null when unrecorded.
export function transcriptFacts(text) {
  const entries = parseTranscript(text);
  let autoCompactAt = null;
  let model = null;
  let effort = null;
  let lastText = null;
  let toolUses = 0;
  let textTurns = 0;
  for (const e of entries) {
    if (e.isSidechain) continue;
    if (e.type === "assistant" && Array.isArray(e.message?.content)) {
      const text = e.message.content.filter((c) => c?.type === "text").map((c) => c.text).join("\n");
      if (text.trim()) {
        lastText = text;
        textTurns++;
      }
      toolUses += e.message.content.filter((c) => c?.type === "tool_use").length;
    }
    if (e.type === "system" && e.subtype === "compact_boundary" && e.compactMetadata?.trigger === "auto") {
      const pre = e.compactMetadata.preTokens;
      if (Number.isInteger(pre) && pre > 0 && (autoCompactAt === null || pre < autoCompactAt)) autoCompactAt = pre;
    } else if (e.type === "api-request" && /main_thread/.test(e.querySource ?? "")) {
      model = e.params?.model ?? null;
      effort = e.params?.output_config?.effort ?? null;
    }
  }
  let size;
  try {
    size = tokensOf(entries);
  } catch (err) {
    size = { error: err };
  }
  return { ...size, autoCompactAt, model, effort, toolUses, textTurns, saysDone: lastText !== null && DONE_RE.test(lastText) };
}

// A session that only read a brief and replied "ready": at most this many text turns, and not
// one tool call. Nothing was done in its context, so `assign` may take it as clean.
export const BRIEF_ONLY_MAX_TURNS = 2;

// A last assistant text that reads as a done report: a hint for the master, never a finish.
const DONE_RE = /^\s*FINAL:|\bjob is done\b/im;

function tokensOf(entries) {
  let usage = null;
  let boundary = null;
  for (const e of entries) {
    if (e.isSidechain) continue;
    if (e.type === "assistant" && e.message?.usage) {
      const u = e.message.usage;
      usage =
        (u.input_tokens ?? 0) +
        (u.cache_read_input_tokens ?? 0) +
        (u.cache_creation_input_tokens ?? 0);
      boundary = null;
    } else if (e.type === "system" && e.subtype === "compact_boundary") {
      // An automatic compaction writes its boundary without postTokens; the size is
      // only known once the session's next turn records a usage.
      const post = e.compactMetadata?.postTokens;
      boundary =
        typeof post === "number"
          ? post
          : new PuppetError(
              `just compacted (${e.compactMetadata?.trigger ?? "unknown"}); its size is known after its next turn`,
            );
    }
  }
  if (boundary instanceof PuppetError) throw boundary;
  if (boundary !== null) return { tokens: boundary, source: "compact_boundary" };
  if (usage !== null) return { tokens: usage, source: "usage" };
  const e = new PuppetError("transcript has no assistant usage and no compact boundary");
  e.code = "no-usage";
  throw e;
}

export function findTranscript(projectsDir, sessionId, { optional = false } = {}) {
  const hits = [];
  let dirs;
  try {
    dirs = fs.readdirSync(projectsDir, { withFileTypes: true });
  } catch (e) {
    if (optional && e.code === "ENOENT") return null;
    throw new PuppetError(`cannot read ${projectsDir}: ${e.message}`);
  }
  for (const d of dirs) {
    if (!d.isDirectory()) continue;
    const p = path.join(projectsDir, d.name, `${sessionId}.jsonl`);
    if (fs.existsSync(p)) hits.push(p);
  }
  if (hits.length === 0) {
    if (optional) return null;
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

// The size at which a session gets compacted automatically: a flag, else PUPPET_COMPACT_AT,
// else an automatic compaction seen (`observedSource` says whose: the session's own, its
// roster record's, or the group's). Never guessed: null when none of the three is there.
export function resolveCompactAt({ flag, env, observed, observedSource = "observed" } = {}) {
  if (flag !== undefined) return { compactAt: positiveInt(flag, "--compact-at"), source: "flag" };
  if (env !== undefined && env !== "") return { compactAt: positiveInt(env, "PUPPET_COMPACT_AT"), source: "env" };
  if (Number.isInteger(observed) && observed > 0) return { compactAt: observed, source: observedSource };
  return null;
}

// Within this share of the compaction point, measure warns.
export const WARN_SHARE = 0.8;

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

// `closed` is the roster's map of sessions `close` removed: a lookup of one says so and
// how to resume it, rather than that no such session exists.
export function findWorker(agents, key, closed = {}) {
  const hits = agents.filter((a) => a.name === key || a.id === key || a.sessionId === key);
  if (hits.length === 0) {
    const gone = Object.entries(closed ?? {}).find(([n, r]) => n === key || r.id === key || r.sessionId === key);
    if (gone) {
      throw new PuppetError(`${gone[0]} is closed (resume: ${resumeHint(gone[1].cwd, gone[1].sessionId, { bg: false })})`);
    }
    throw new PuppetError(`no session named or numbered "${key}"`);
  }
  if (hits.length > 1) {
    const ids = hits.map((a) => a.id ?? a.sessionId).join(", ");
    throw new PuppetError(`"${key}" is ambiguous: sessions ${ids}; use an id`);
  }
  return hits[0];
}

// Observed on a live background session: `state` working → done (with `status`
// busy → idle); `blocked` is a session waiting on a prompt, so it is mid-task. A session
// parked on a dialog lists as `state done`, `status waiting` (probe, 2026-11-04): `workerState`
// reports it as `waiting`, which is busy, never idle. A state in neither set is unknown, and
// nothing that needs a task boundary acts on it.
export const IDLE_STATES = new Set(["done", "idle"]);
export const BUSY_STATES = new Set(["working", "busy", "blocked", "waiting"]);

// A session resumes from its own project directory, so every printed resume command
// carries the worker's cwd.
function resumeHint(cwd, sessionId, { bg = true } = {}) {
  const cmd = `claude ${bg ? "--bg " : ""}--resume ${sessionId}`;
  return cwd ? `cd "${cwd}" && ${cmd}` : cmd;
}

export function workerState(agent) {
  // `status waiting` wins over `state done`: the session is behind a dialog, not at a boundary.
  if (agent.status === "waiting") return "waiting";
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
  const base = deps.env.PUPPET_STATE ?? path.join(configDir(deps.env), "puppet-master", "workers.json");
  // A group (one master and its sessions) keeps its own roster beside the default one.
  return deps.group ? path.join(path.dirname(base), `workers-${deps.group}.json`) : base;
}

// --- groups: several masters on one machine ---------------------------------------------

const GROUP_RE = /^[A-Za-z0-9][A-Za-z0-9-]*$/;

function withGroup(deps, group) {
  if (!GROUP_RE.test(group)) throw new PuppetError(`--group must match [A-Za-z0-9-]+, got "${group}"`, 2);
  return { ...deps, group };
}

// A proposal id names its group (`P-<YYYYMMDD>-<group>-<n>`); an id without one is an older,
// ungrouped id and is taken by any group. One group's id never lands in another's log.
function checkProposalGroup(deps, proposalId) {
  const m = /^P-\d{8}-(.+)-\d+$/.exec(proposalId ?? "");
  if (!m || m[1] === deps.group) return;
  throw new PuppetError(`${proposalId} belongs to group "${m[1]}"; pass --group ${m[1]}`, 2);
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

// --- renamed sessions -----------------------------------------------------------------

// The better of two records for one session: an active job over a finished one over an
// unknown over a clean one; at a tie, the earlier candidate (the older name's, with more history).
const JOB_RANK = { active: 3, done: 2, unknown: 1, clean: 0 };
const rankOf = (rec) => JOB_RANK[rec.jobState ?? "active"] ?? 0;

// A session renamed in its window (`/rename`) keeps its session id, so a record under its old
// name is the same session's: carry it over to the live name, rather than let an `adopt` open a
// second, `unknown` record for it (2026-11-04: carcare-platform-66 → -b3 held both). Only a record
// with the very same session id moves; a name another live session still uses is left alone.
// Returns the live names whose record was carried.
export function carryRenames(reg, agents) {
  const carried = new Set();
  for (const a of agents) {
    const mine = Object.entries(reg.workers).filter(([, r]) => r.sessionId === a.sessionId);
    const olds = mine.filter(([n]) => n !== a.name && !agents.some((x) => x.name === n && x.sessionId !== a.sessionId));
    if (olds.length === 0) continue;
    if (reg.workers[a.name] && reg.workers[a.name].sessionId !== a.sessionId) continue;
    const own = mine.find(([n]) => n === a.name);
    const candidates = [...olds, ...(own ? [own] : [])];
    const best = candidates.reduce((b, c) => (rankOf(c[1]) > rankOf(b[1]) ? c : b));
    const window = candidates.map(([, r]) => r.window).find(Boolean);
    const compactAt = candidates.map(([, r]) => r.compactAt).reduce((m, x) => minPositive(m, x), Infinity);
    for (const [n] of candidates) delete reg.workers[n];
    reg.workers[a.name] = {
      ...best[1],
      ...(window ? { window } : {}),
      ...(Number.isFinite(compactAt) ? { compactAt } : {}),
    };
    carried.add(a.name);
  }
  return carried;
}

// The roster, with every rename carried over and saved. `agents` is the live list.
function loadRoster(deps, agents) {
  const reg = loadRegistry(deps);
  if (carryRenames(reg, agents).size > 0) saveRegistry(deps, reg);
  return reg;
}

// --- measuring ------------------------------------------------------------------------

function projectsDir(deps) {
  return path.join(configDir(deps.env), "projects");
}

// A session with no transcript yet, or no assistant turn yet, is fresh: 0 tokens, and
// no window is needed to say so.
function freshMeasure(agent) {
  return {
    name: agent.name,
    id: agent.id,
    tokens: 0,
    percent: 0,
    window: null,
    windowSource: null,
    state: "fresh",
    tokenSource: "none",
    model: null,
    effort: null,
    autoCompactAt: null,
  };
}

const minPositive = (a, b) => [a, b].filter((x) => Number.isInteger(x) && x > 0).reduce((m, x) => Math.min(m, x), Infinity);

// windowOptional: a status listing shows an unknown size instead of failing on it.
export function measureAgent(deps, agent, record, { window, compactAt, observed, windowOptional = false } = {}) {
  const file = findTranscript(projectsDir(deps), agent.sessionId, { optional: true });
  if (file === null) return freshMeasure(agent);
  const t = transcriptFacts(deps.fs.readFileSync(file, "utf8"));
  if (t.error) {
    if (t.error instanceof PuppetError && t.error.code === "no-usage") return freshMeasure(agent);
    throw t.error;
  }
  // The session's own point first (its transcript, or the roster record kept from before a
  // clear); the group's lowest only for a session that has not been compacted yet. One
  // session's point says nothing sure about another's: a compaction comes at 208,192, 230,030
  // or 354,186 tokens depending on the session (2026-11-03).
  const own = minPositive(t.autoCompactAt, record?.compactAt);
  const mine = Number.isFinite(own)
    ? { observed: own, observedSource: own === t.autoCompactAt ? "observed" : "recorded" }
    : { observed: observed ?? undefined, observedSource: "group" };
  const c = resolveCompactAt({ flag: compactAt, env: deps.env.PUPPET_COMPACT_AT, ...mine });
  let w;
  try {
    w = resolveWindow({ flag: window, recorded: record?.window, env: deps.env.PUPPET_CONTEXT_WINDOW });
  } catch (e) {
    // With a known compaction point the window is only context; without one, no size
    // can be judged, and the error stands.
    if (!(e instanceof PuppetError) || (c === null && !windowOptional)) throw e;
    w = { window: null, source: null };
  }
  return {
    name: agent.name,
    id: agent.id,
    tokens: t.tokens,
    percent: w.window === null ? null : percent(t.tokens, w.window),
    window: w.window,
    windowSource: w.source,
    compactAt: c?.compactAt ?? null,
    compactSource: c?.source ?? null,
    compactPercent: c === null ? null : percent(t.tokens, c.compactAt),
    warn: c !== null && t.tokens >= WARN_SHARE * c.compactAt,
    state: workerState(agent),
    tokenSource: t.source,
    model: t.model,
    effort: t.effort,
    saysDone: t.saysDone,
    autoCompactAt: t.autoCompactAt,
  };
}

// Keep the smallest automatic compaction any measured transcript showed (the group's, for a
// session with none of its own), and each rostered session's own smallest on its record, so a
// `clear` does not lose it. True when anything moved.
function noteCompactions(reg, measures) {
  let moved = false;
  const seen = measures.reduce((m, x) => minPositive(m, x?.autoCompactAt), minPositive(reg.observedCompactAt));
  if (Number.isFinite(seen) && seen !== reg.observedCompactAt) {
    reg.observedCompactAt = seen;
    moved = true;
  }
  for (const m of measures) {
    const rec = m?.name === undefined ? undefined : reg.workers[m.name];
    if (!rec || !Number.isInteger(m.autoCompactAt) || m.autoCompactAt <= 0) continue;
    const own = minPositive(m.autoCompactAt, rec.compactAt);
    if (own !== rec.compactAt) {
      rec.compactAt = own;
      moved = true;
    }
  }
  return moved;
}

export function measureWorker(deps, key, { window, compactAt } = {}) {
  const agents = listAgents(deps);
  const reg = loadRoster(deps, agents);
  const agent = findWorker(agents, key, reg.closed);
  const record = reg.workers[agent.name];
  const m = measureAgent(deps, agent, record, { window, compactAt, observed: reg.observedCompactAt });
  if (noteCompactions(reg, [m])) saveRegistry(deps, reg);
  return m;
}

export function measureLine(m) {
  if (m.state === "fresh") return `${m.name}  0  0%  fresh  (no turns yet)`;
  const size =
    m.window === null
      ? `${m.name}  ${m.tokens}  ?%  ${m.state}  (window unknown)`
      : `${m.name}  ${m.tokens}  ${m.percent}%  ${m.state}  (window ${m.window} from ${m.windowSource})`;
  const point = m.compactAt === null ? "" : `  ${m.compactPercent}% of compaction point ${m.compactAt} (${m.compactSource})`;
  return `${size}${point}${m.warn ? "  WARN near compaction" : ""}`;
}

// Model and effort of a measured session, `fresh` before its first turn.
export function modelLine(m) {
  if (m.state === "fresh") return "fresh";
  return `${m.model ?? "?"} ${m.effort ?? "?"}`;
}

// --- spawning -------------------------------------------------------------------------

// Windows caps a command line near 32767 characters, and the brief is one argument.
const MAX_BRIEF = 30000;
const NAME_RE = /^[A-Za-z0-9._-]+$/;

function pathApi(deps) {
  return (deps.platform ?? process.platform) === "win32" ? path.win32 : path.posix;
}

// `claude --bg` prints "backgrounded · <id> · <name>" followed by hint lines; on 2.1.312
// the id and the hints come wrapped in ANSI colour codes.
export function parseBgId(stdout) {
  const m = /\bbackgrounded\b[^0-9a-f\n]*([0-9a-f]{6,})\b/.exec(stdout.replace(/\x1b\[[0-9;]*m/g, ""));
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

// --- the roster: every session in the master's care, opened by the user or spawned -----

// A record written before the roster existed is a spawned worker holding its job.
function normalize(rec) {
  return { kind: "background", role: "worker", job: null, jobState: "active", ...rec };
}

// An active job edits its checkout. So may a session adopted as `unknown` (it worked
// before the master knew it) while it is not idle: the lock cannot assume otherwise.
// A session leaving the roster (closed, gone, or re-adopted under a new session id) may
// still have transcript lines the analyst has not read: the next harvest reads them once.
function queueHarvest(reg, name, sessionId) {
  if (!sessionId) return;
  reg.pendingHarvest = reg.pendingHarvest ?? [];
  if (!reg.pendingHarvest.some((p) => p.sessionId === sessionId)) reg.pendingHarvest.push({ name, sessionId });
}

// No transcript, or one with no tool call and at most BRIEF_ONLY_MAX_TURNS text turns: a session
// that only read its brief and replied. It did nothing, so it counts as clean for `assign`.
function isBriefOnly(deps, agent) {
  const file = findTranscript(projectsDir(deps), agent.sessionId, { optional: true });
  if (file === null) return false;
  const t = transcriptFacts(deps.fs.readFileSync(file, "utf8"));
  return t.toolUses === 0 && t.textTurns >= 1 && t.textTurns <= BRIEF_ONLY_MAX_TURNS;
}

export function isEditing(rec, agents) {
  const r = normalize(rec);
  if (r.role !== "worker") return false;
  const live = agents.find((a) => (r.id && a.id === r.id) || a.sessionId === r.sessionId);
  if (!live) return false;
  if (r.jobState === "active") return true;
  return r.jobState === "unknown" && !IDLE_STATES.has(workerState(live));
}

// --- write scopes: two jobs may share a checkout when they cannot collide -----------------

// A job's write scope: folders relative to its checkout, in posix form. "." is the whole
// checkout. An absolute path or one that climbs out with ".." is refused.
export function parseScope(deps, value) {
  if (value === undefined) return undefined;
  const win = (deps.platform ?? process.platform) === "win32";
  const dirs = String(value)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => {
      const p = s.replace(/\\/g, "/");
      if (path.posix.isAbsolute(p) || /^[A-Za-z]:/.test(p)) {
        throw new PuppetError(`--scope folders are relative to the checkout, got "${s}"`, 2);
      }
      const n = path.posix.normalize(p).replace(/\/+$/, "") || ".";
      if (n === ".." || n.startsWith("../")) throw new PuppetError(`--scope "${s}" leaves the checkout`, 2);
      return win ? n.toLowerCase() : n;
    });
  if (dirs.length === 0) throw new PuppetError("--scope needs at least one folder", 2);
  return dirs;
}

const overlaps = (x, y) => x === "." || y === "." || x === y || y.startsWith(`${x}/`) || x.startsWith(`${y}/`);

// Why two jobs in one checkout would collide, or null when they cannot: both declare a
// write scope, the scopes are disjoint, and at most one of them runs git.
export function collision(a, b) {
  if (!a.scope || !b.scope) return "one editing session per checkout unless both jobs pass --scope";
  if (a.git !== false && b.git !== false) return "both jobs run git; pass --no-git to one of them";
  const hit = a.scope.find((x) => b.scope.some((y) => overlaps(x, y)));
  if (hit) return `write scopes overlap at ${hit}`;
  return null;
}

// Refuse when the new job collides with any session editing the same checkout.
function checkLock(deps, reg, agents, self, checkout, job) {
  const key = checkoutKey(deps, checkout);
  for (const [other, o] of Object.entries(reg.workers)) {
    if (other === self || checkoutKey(deps, o.checkout) !== key || !isEditing(o, agents)) continue;
    const why = collision(job, { scope: o.scope, git: o.git });
    if (why) throw new PuppetError(`${other} is already editing ${o.checkout}: ${why}`);
  }
}

function jobFields(deps, { scope, noGit } = {}) {
  const s = parseScope(deps, scope);
  return { ...(s ? { scope: s } : {}), git: !noGit };
}

// --- tiers: which model and effort a job needs ------------------------------------------

export const TIERS = {
  creative: "an Opus model at high effort or more",
  mechanical: "a model other than Opus at medium effort or less",
};
const HIGH = new Set(["high", "xhigh", "max"]);
const LOW = new Set(["low", "medium"]);

// true when the session matches the tier, false when it does not, null when its model or
// effort is not recorded yet (a fresh session).
export function tierMatch(tier, { model, effort } = {}) {
  if (!(tier in TIERS)) throw new PuppetError(`--tier must be creative or mechanical, got "${tier}"`, 2);
  if (!model || !effort) return null;
  const opus = /opus/i.test(model);
  return tier === "creative" ? opus && HIGH.has(effort) : !opus && LOW.has(effort);
}

// What `spawn` passes to `claude --bg` for a tier: plain aliases, never versioned model ids.
export const TIER_LAUNCH = {
  creative: { model: "opus", effort: "high" },
  mechanical: { model: "sonnet", effort: "medium" },
};
export const EFFORTS = ["low", "medium", "high", "xhigh", "max"];

// The --model and --effort a spawn passes. Explicit flags win over the tier. An effort is
// always explicit: a no-flag `claude --bg` has started below the user's own default.
export function launchFlags({ tier, model, effort } = {}) {
  if (tier !== undefined) tierMatch(tier, {});
  const base = tier === undefined ? {} : TIER_LAUNCH[tier];
  const m = model ?? base.model;
  const e = effort ?? base.effort;
  if (e === undefined) throw new PuppetError("spawn: name a --tier or --effort", 2);
  if (!EFFORTS.includes(e)) throw new PuppetError(`--effort must be one of ${EFFORTS.join(", ")}, got "${e}"`, 2);
  if (m !== undefined && !m.trim()) throw new PuppetError("--model needs a value", 2);
  return { model: m, effort: e };
}

export function tierLine(name, tier, facts) {
  const ok = tierMatch(tier, facts);
  if (ok === null) return `${name} tier ${tier}: unchecked (no turn yet); have it state its model, then read its effort with list --name`;
  const has = `${facts.model} ${facts.effort}${facts.switched ? " (switched)" : ""}`;
  return ok ? `${name} tier ${tier}: ok (${has})` : `MISMATCH ${name} tier ${tier} needs ${TIERS[tier]}; it runs ${has}`;
}

// The session-only paste form, for a session whose mod is not on. A typed `/model <name>` or
// `/effort <level>` saves the user's default for new sessions (docs: model-config, "Setting
// your model" and "Adjust effort level"); `s` in the picker or slider switches this session only.
export function switchPaste(name, { model, effort }) {
  const alias = /^(opus|sonnet|haiku)/.exec(model)?.[1];
  const row = alias ? alias[0].toUpperCase() + alias.slice(1) : model;
  return `give the user "${name}: /model, then s on the ${row} row" and "${name}: /effort, then s at ${effort}" to paste (this session only; never a typed /model ${model} or /effort ${effort}, which saves the user's default)`;
}

export function mismatchPaste(name, tier) {
  return switchPaste(name, TIER_LAUNCH[tier]);
}

// The line printed after a MISMATCH: `switch` where the session's mod is on, else the paste.
export function mismatchNext(deps, sessionId, name, tier) {
  return modOn(modHeartbeat(deps, sessionId))
    ? `its mod is on: run \`switch ${name} --tier ${tier}\` (session-only; no paste)`
    : mismatchPaste(name, tier);
}

// The model and effort a listed session's next request goes out with: the mod's switch when
// one applies, else its last main-thread request in the transcript; nulls when fresh.
function sessionFacts(deps, agent) {
  const hb = modHeartbeat(deps, agent.sessionId);
  if (modOn(hb) && hb.override) return { model: hb.override.model, effort: hb.override.effort, switched: true };
  return lastRequest(deps, agent);
}

// The model and effort of the last main-thread request in the transcript; nulls when fresh.
function lastRequest(deps, agent) {
  const file = findTranscript(projectsDir(deps), agent.sessionId, { optional: true });
  if (file === null) return { model: null, effort: null };
  const t = transcriptFacts(deps.fs.readFileSync(file, "utf8"));
  return { model: t.model, effort: t.effort };
}

// No transcript, or no assistant turn yet: nothing has happened in this context.
function isFresh(deps, agent) {
  const file = findTranscript(projectsDir(deps), agent.sessionId, { optional: true });
  if (file === null) return true;
  try {
    transcriptTokens(deps.fs.readFileSync(file, "utf8"));
    return false;
  } catch (e) {
    if (e instanceof PuppetError && e.code === "no-usage") return true;
    if (e instanceof PuppetError) return false;
    throw e;
  }
}

const ROLES = new Set(["worker", "analyst", "master"]);

export function adoptSession(deps, key, { role, window, selfCompact = false } = {}) {
  if (role !== undefined && !ROLES.has(role)) throw new PuppetError(`--role must be worker, analyst or master, got "${role}"`, 2);
  const w = window === undefined ? undefined : positiveInt(window, "--window");
  const agents = listAgents(deps);
  const reg = loadRegistry(deps);
  // A session renamed since it was adopted is already in the roster under its old name: its
  // record moves to the new name first.
  carryRenames(reg, agents);
  const agent = findWorker(agents, key, reg.closed);
  const before = reg.workers[agent.name];
  // A session already in the roster under this name, with the same session id, keeps its job and
  // job state: adopting it again only updates its role, window and mod role (2026-11-04: an adopt
  // of a carried `done` record made it `unknown`, and `clear` and `assign` refused it). A changed
  // session id (a clear, a restart) is adopted afresh below.
  const same = before !== undefined && before.sessionId === agent.sessionId;
  const asRole = role ?? (same ? before.role : undefined) ?? "worker";
  if (asRole !== "worker") {
    for (const [other, rec] of Object.entries(reg.workers)) {
      if (other !== agent.name && normalize(rec).role === asRole && isLive(agents, rec)) {
        throw new PuppetError(`${other} is already the ${asRole}`);
      }
    }
  }
  if (same) {
    reg.workers[agent.name] = { ...before, role: asRole, ...(w ? { window: w } : {}) };
    saveRegistry(deps, reg);
    writeModRole(deps, agent.sessionId, asRole);
    if (selfCompact) writeModOptin(deps, agent.sessionId);
    return { name: agent.name, ...reg.workers[agent.name] };
  }
  if (before && before.sessionId !== agent.sessionId) queueHarvest(reg, agent.name, before.sessionId);
  if (reg.closed) delete reg.closed[agent.name];
  const kept = w ?? before?.window;
  const rec = {
    ...(agent.id ? { id: agent.id } : {}),
    sessionId: agent.sessionId,
    cwd: pathApi(deps).resolve(agent.cwd),
    checkout: checkoutOf(deps, agent.cwd),
    kind: agent.kind ?? "background",
    role: asRole,
    job: null,
    jobState: isFresh(deps, agent) || isBriefOnly(deps, agent) ? "clean" : "unknown",
    ...(kept ? { window: kept } : {}),
    ...(before?.compactAt ? { compactAt: before.compactAt } : {}),
  };
  reg.workers[agent.name] = rec;
  saveRegistry(deps, reg);
  // The mod in that session reads its role from here; an opt-in only when the master says so.
  writeModRole(deps, agent.sessionId, asRole);
  if (selfCompact) writeModOptin(deps, agent.sessionId);
  return { name: agent.name, ...rec };
}

// The roster record of a listed session, refusing one the user cleared or restarted.
function rosterRecord(agents, reg, key) {
  const agent = findWorker(agents, key, reg.closed);
  const rec = reg.workers[agent.name];
  if (!rec) throw new PuppetError(`${agent.name} is not in the roster; adopt it first`);
  if (rec.sessionId !== agent.sessionId) {
    throw new PuppetError(
      `${agent.name} has a new session id (cleared or restarted?); ask the user, then adopt it again`,
    );
  }
  return { agent, rec: normalize(rec) };
}

// Below this share of its window (the figure the user's status line shows; the compaction
// point only when the window is unknown), a finished session may take the next job with --reuse.
export const REUSE_BELOW = 30;

// One job's write fields with more work added: no scope on either side means the whole
// checkout. The git flag stays the job's own unless the extension names one (`--git` or
// `--no-git`, as `gitFlag` true or false): an extension that names none must not turn a no-git
// job into a git job (2026-11-03: 4e).
function mergeJob(a, b, gitFlag) {
  const scope = a.scope && b.scope ? [...new Set([...a.scope, ...b.scope])] : undefined;
  return { ...(scope ? { scope } : {}), git: gitFlag ?? a.git !== false };
}

export function assignJob(deps, key, label, { reuse = false, extend = false, scope, noGit = false, git = false, tier } = {}) {
  if (!label || !label.trim()) throw new PuppetError("assign needs a job label", 2);
  if (extend && reuse) throw new PuppetError("--extend and --reuse do not go together", 2);
  if (git && noGit) throw new PuppetError("--git and --no-git do not go together", 2);
  if (tier !== undefined) tierMatch(tier, {});
  const job = jobFields(deps, { scope, noGit });
  const agents = listAgents(deps);
  const reg = loadRoster(deps, agents);
  const { agent, rec } = rosterRecord(agents, reg, key);
  if (rec.role !== "worker") throw new PuppetError(`${agent.name} is the ${rec.role}; the ${rec.role} takes no jobs`);
  if (extend) return extendJob(deps, reg, agents, agent, rec, label, job, tier, git ? true : noGit ? false : undefined);
  const reusable = reuse && rec.jobState === "done";
  if (rec.jobState !== "clean" && !reusable) {
    const did = rec.jobState === "active" ? `holds "${rec.job}"` : rec.job ? `did "${rec.job}"` : "did other work";
    const hint = rec.jobState === "done" ? "; if the user asked to reuse sessions, pass --reuse" : "";
    throw new PuppetError(
      `one job per context: ${agent.name} already ${did}; use a clean session or spawn one${hint}`,
    );
  }
  if (reusable) {
    let m;
    try {
      m = measureAgent(deps, agent, rec, { observed: reg.observedCompactAt });
    } catch (e) {
      if (!(e instanceof PuppetError)) throw e;
      throw new PuppetError(`cannot measure ${agent.name} for --reuse: ${e.message}`);
    }
    const share = m.percent ?? m.compactPercent ?? 0;
    if (share >= REUSE_BELOW) {
      const of = m.percent === null ? "of its compaction point" : "of its window";
      const point = m.percent !== null && m.compactPercent !== null ? ` (${m.compactPercent}% of compaction point ${m.compactAt})` : "";
      throw new PuppetError(
        `${agent.name} is at ${share}% ${of}${point} (${m.tokens} tokens); --reuse needs under ${REUSE_BELOW}%: give the user its /clear line first`,
      );
    }
  }
  checkLock(deps, reg, agents, agent.name, rec.checkout, job);
  const now = deps.now().toISOString();
  const jobs = [...(rec.jobs ?? []), { label, startedAt: now }];
  const next = { ...rec, job: label, jobState: "active", jobStartedAt: now, jobs, ...job };
  if (!job.scope) delete next.scope;
  if (tier !== undefined) next.tier = tier;
  else delete next.tier;
  reg.workers[agent.name] = next;
  saveRegistry(deps, reg);
  const tierCheck = tier === undefined ? null : tierLine(agent.name, tier, sessionFacts(deps, agent));
  return { name: agent.name, ...next, tierCheck };
}

// More work for the job a session already holds: the label, scope and git merge into it,
// and its start stays.
function extendJob(deps, reg, agents, agent, rec, label, job, tier, gitFlag) {
  if (rec.jobState !== "active") {
    throw new PuppetError(`--extend needs an active job; ${agent.name} has none (it is ${rec.jobState})`);
  }
  const merged = mergeJob(rec, job, gitFlag);
  checkLock(deps, reg, agents, agent.name, rec.checkout, merged);
  // A label the job already has is not added again.
  const joined = String(rec.job).split("; ").includes(label) ? rec.job : `${rec.job}; ${label}`;
  const jobs = [...(rec.jobs ?? [])];
  if (jobs.length > 0) jobs[jobs.length - 1] = { ...jobs[jobs.length - 1], label: joined };
  const next = { ...rec, job: joined, jobs, ...merged };
  if (!merged.scope) delete next.scope;
  if (tier !== undefined) next.tier = tier;
  reg.workers[agent.name] = next;
  saveRegistry(deps, reg);
  const tierCheck = tier === undefined ? null : tierLine(agent.name, tier, sessionFacts(deps, agent));
  return { name: agent.name, ...next, extended: true, tierCheck };
}

// Undo a finish: the last job is active again, as it was before `finish`.
export function reopenJob(deps, key) {
  const agents = listAgents(deps);
  const reg = loadRoster(deps, agents);
  const { agent, rec } = rosterRecord(agents, reg, key);
  if (rec.jobState !== "done") throw new PuppetError(`${agent.name} has no finished job to reopen (it is ${rec.jobState})`);
  checkLock(deps, reg, agents, agent.name, rec.checkout, { scope: rec.scope, git: rec.git });
  const jobs = [...(rec.jobs ?? [])];
  if (jobs.length > 0) {
    const { endedAt, ...last } = jobs[jobs.length - 1];
    jobs[jobs.length - 1] = last;
  }
  const next = { ...rec, jobState: "active", ...(jobs.length > 0 ? { jobs } : {}) };
  reg.workers[agent.name] = next;
  saveRegistry(deps, reg);
  return { name: agent.name, ...next };
}

export function finishJob(deps, key) {
  const agents = listAgents(deps);
  const reg = loadRoster(deps, agents);
  const { agent, rec } = rosterRecord(agents, reg, key);
  if (rec.jobState !== "active") throw new PuppetError(`${agent.name} has no active job`);
  const jobs = [...(rec.jobs ?? [])];
  if (jobs.length > 0) jobs[jobs.length - 1] = { ...jobs[jobs.length - 1], endedAt: deps.now().toISOString() };
  const next = { ...rec, jobState: "done", ...(jobs.length > 0 ? { jobs } : {}) };
  reg.workers[agent.name] = next;
  saveRegistry(deps, reg);
  return { name: agent.name, ...next };
}

// A clean worker session in the cwd's checkout; null when there is none, or when the job
// would collide with a session already editing that checkout. With a tier, a session that
// already matches it, or whose mod is on so `switch` can align it, comes first, then one not
// yet checked; within each, the user's own windows first (an opened window before a worker).
export function pickSession(deps, cwd, { scope, noGit = false, tier } = {}) {
  if (tier !== undefined) tierMatch(tier, {});
  const job = jobFields(deps, { scope, noGit });
  const checkout = checkoutOf(deps, cwd);
  const key = checkoutKey(deps, checkout);
  const agents = listAgents(deps);
  const reg = loadRoster(deps, agents);
  const here = Object.entries(reg.workers).filter(([, r]) => checkoutKey(deps, r.checkout) === key);
  if (here.some(([, r]) => isEditing(r, agents) && collision(job, { scope: r.scope, git: r.git }))) return null;
  const rank = (c) => {
    const match = tier === undefined || c.switchable ? 0 : { true: 0, null: 1, false: 2 }[String(c.match)];
    return match * 2 + (c.record.kind === "interactive" ? 0 : 1);
  };
  const clean = here
    .map(([name, r]) => ({ name, record: normalize(r), agent: agents.find((x) => x.name === name) }))
    .filter(({ record, agent }) => agent && agent.sessionId === record.sessionId && record.role === "worker" && record.jobState === "clean")
    .map((c) => {
      if (tier === undefined) return c;
      const facts = sessionFacts(deps, c.agent);
      const switchable = modOn(modHeartbeat(deps, c.agent.sessionId));
      return { ...c, match: tierMatch(tier, facts), switchable, tierCheck: tierLine(c.name, tier, facts) };
    })
    .sort((a, b) => rank(a) - rank(b));
  return clean[0] ?? null;
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

export function spawnWorker(deps, name, cwd, briefFile, { job, scope, noGit = false, tier, model, effort, selfCompact = false } = {}) {
  if (!NAME_RE.test(name)) throw new PuppetError(`worker name "${name}" must match [A-Za-z0-9._-]+`, 2);
  const launch = launchFlags({ tier, model, effort });
  const fields = jobFields(deps, { scope, noGit });
  const brief = readBrief(deps, briefFile);
  const agents = listAgents(deps);
  const clash = agents.find((a) => a.name === name);
  if (clash) {
    throw new PuppetError(`a live session is already named "${name}" (id ${clash.id ?? clash.sessionId})`, 2);
  }
  const checkout = checkoutOf(deps, cwd);
  const key = checkoutKey(deps, checkout);
  const reg = loadRoster(deps, agents);
  for (const [other, rec] of Object.entries(reg.workers)) {
    if (checkoutKey(deps, rec.checkout) !== key) continue;
    const why = isEditing(rec, agents) ? collision(fields, { scope: rec.scope, git: rec.git }) : null;
    if (why) {
      throw new PuppetError(
        `worker "${other}" (id ${rec.id ?? rec.sessionId}) is already editing ${rec.checkout}: ${why} — close it or use another checkout`,
      );
    }
    // A live session that is clean, done or the analyst stays in the roster, and so does one
    // whose name is listed under a new session id: the user decides whether it was cleared.
    if (isLive(agents, rec) || agents.some((a) => a.name === other)) continue;
    deps.out(`pruned stale record ${other} (resume: ${resumeHint(rec.cwd, rec.sessionId)})`);
    queueHarvest(reg, other, rec.sessionId);
    delete reg.workers[other];
  }
  const pass = [...(launch.model ? ["--model", launch.model] : []), "--effort", launch.effort];
  const r = claudeOk(deps, ["--bg", "--name", name, ...pass, brief], { cwd });
  const id = parseBgId(r.stdout);
  const started = listAgents(deps).find((a) => a.id === id);
  if (!started) throw new PuppetError(`started ${name} as ${id}, but claude agents does not list it`);
  reg.workers[name] = {
    id,
    sessionId: started.sessionId,
    cwd: pathApi(deps).resolve(cwd),
    checkout,
    kind: "background",
    role: "worker",
    job: job ?? name,
    jobState: "active",
    jobStartedAt: deps.now().toISOString(),
    jobs: [{ label: job ?? name, startedAt: deps.now().toISOString() }],
    ...fields,
    ...(tier === undefined ? {} : { tier }),
  };
  if (reg.closed) delete reg.closed[name];
  saveRegistry(deps, reg);
  writeModRole(deps, started.sessionId, "worker");
  if (selfCompact) writeModOptin(deps, started.sessionId);
  return { name, id, sessionId: started.sessionId, checkout, selfCompact, ...launch };
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
  const agents = listAgents(deps);
  const agent = requireBackground(findWorker(agents, key, loadRoster(deps, agents).closed), "cycling");
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
  const reg = loadRoster(deps, agents);
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
    if (!hit) {
      findWorker([], key, reg.closed);
      throw new PuppetError(`no live session and no recorded worker named or numbered "${key}"`);
    }
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
  queueHarvest(reg, name, sessionId);
  delete reg.workers[name];
  reg.closed = { ...(reg.closed ?? {}), [name]: { ...(id ? { id } : {}), sessionId, cwd, closedAt: deps.now().toISOString() } };
  saveRegistry(deps, reg);
  return { name, sessionId, resume };
}

// --- the mod: a session compacts, or clears, itself when asked --------------------------
//
// The puppet-master mod (hooks/puppet-mod.js) runs inside a session where it was switched
// on. It and this helper meet in one folder: the helper writes optin/, roles/ and
// requests/, the mod writes heartbeat/ and acks/. A request is a file, never a message.

// The mod beats every 3 s; a heartbeat older than this means it is not running.
export const HEARTBEAT_MAX_AGE_MS = 15000;
// How long a verb waits for the mod's ack, once a second.
const ACK_WAIT_TRIES = 90;
const ACK_WAIT_MS = 1000;

export function modDir(deps) {
  return deps.env.PUPPET_MOD_DIR ?? path.join(configDir(deps.env), "puppet-master", "mod");
}

const modFile = (deps, kind, name) => path.join(modDir(deps), kind, `${name}.json`);

// A mod file's JSON; null when it is missing, empty or `{}`.
function readModJson(deps, file) {
  let text;
  try {
    text = deps.fs.readFileSync(file, "utf8");
  } catch (e) {
    if (e.code === "ENOENT") return null;
    throw new PuppetError(`cannot read ${file}: ${e.message}`);
  }
  text = text.trim();
  if (text === "" || text === "{}") return null;
  try {
    return JSON.parse(text);
  } catch (e) {
    throw new PuppetError(`${file} is not valid JSON: ${e.message}`);
  }
}

function writeModJson(deps, file, value) {
  deps.fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp`;
  deps.fs.writeFileSync(tmp, `${JSON.stringify(value)}\n`);
  deps.fs.renameSync(tmp, file);
}

export function writeModRole(deps, sessionId, role) {
  writeModJson(deps, modFile(deps, "roles", sessionId), { role, at: deps.now().toISOString() });
}

export function writeModOptin(deps, sessionId) {
  writeModJson(deps, modFile(deps, "optin", sessionId), { at: deps.now().toISOString() });
}

// What the mod in a session says: null when it never beat, `stale` when it stopped, else
// the heartbeat itself.
export function modHeartbeat(deps, sessionId) {
  const hb = readModJson(deps, modFile(deps, "heartbeat", sessionId));
  if (!hb) return null;
  const age = deps.now().getTime() - hb.beat;
  return age > HEARTBEAT_MAX_AGE_MS ? { ...hb, stale: true } : hb;
}

// A mod that beat lately and is switched on: it can compact, switch and (a worker) clear.
export const modOn = (hb) => Boolean(hb && !hb.stale && hb.enabled);

// The `list` column: nothing when no mod ever beat in that session.
export function modLabel(hb) {
  if (!hb) return null;
  if (hb.stale) return "mod stale";
  if (!hb.enabled) return `mod off (mode ${hb.mode})`;
  return `mod on (${hb.source})${hb.override ? `  switched to ${hb.override.model} ${hb.override.effort}` : ""}`;
}

// A session that cannot be compacted or cleared right now: not idle, or idle but parked on a
// dialog (`status waiting`, which `state done` hides: a session can sit behind a dialog and
// still count as idle).
function requireBoundary(agent, verb) {
  if (agent.status === "waiting") {
    throw new PuppetError(`${agent.name} is waiting on a dialog (status waiting); not ${verb} it`);
  }
  const state = workerState(agent);
  if (!IDLE_STATES.has(state)) {
    throw new PuppetError(`${agent.name} is not at a task boundary (state ${state}); not ${verb} it`);
  }
}

// The mod must have switched itself on in that session, and beat lately.
function requireMod(deps, agent, fallback) {
  const hb = modHeartbeat(deps, agent.sessionId);
  const why = !hb
    ? "no mod heartbeat: the plugin is not loaded in that session (run /reload-plugins in its window, or Claude Code is older than 2.1.287)"
    : hb.stale
      ? "its mod heartbeat is stale: the mod stopped"
      : !hb.enabled
        ? `its mod is loaded but not switched on (self_compact ${hb.mode}${hb.mode === "off" ? ", the user's veto" : "; spawn or adopt it with --self-compact, or the user says yes in its window"})`
        : null;
  if (why) throw new PuppetError(`${agent.name}: ${why}. Fallback: ${fallback}`);
  return hb;
}

// Writes the request file and, unless `wait` is false, waits for the mod's ack. On a timeout
// the request is withdrawn, so it cannot run later unseen.
async function modRequest(deps, sessionId, request, { wait = true } = {}) {
  const file = modFile(deps, "requests", sessionId);
  if (readModJson(deps, file)) throw new PuppetError(`a request for session ${sessionId} is already waiting; not sending another`);
  const nonce = (deps.nonce ?? (() => randomBytes(6).toString("hex")))();
  const requestedAt = deps.now().getTime();
  writeModJson(deps, file, { nonce, sessionId, requestedAt, ...request });
  if (!wait) return { nonce, requestedAt };
  const ackFile = modFile(deps, "acks", nonce);
  const sleep = deps.sleep ?? ((ms) => new Promise((r) => setTimeout(r, ms)));
  for (let i = 0; i < ACK_WAIT_TRIES; i++) {
    const ack = readModJson(deps, ackFile);
    if (ack) {
      deps.fs.rmSync(ackFile, { force: true });
      return { nonce, requestedAt, ack };
    }
    await sleep(ACK_WAIT_MS);
  }
  const left = readModJson(deps, file);
  if (left?.nonce === nonce) writeModJson(deps, file, {});
  throw new PuppetError(`no answer from the mod in ${(ACK_WAIT_TRIES * ACK_WAIT_MS) / 1000} s; the request was withdrawn`);
}

const pasteLine = (name, text) => `give the user "${name}: ${text}" to paste`;

// Compact a session through its own mod. A master's own compaction cannot wait for an ack
// (it runs in the master's turn): the request is left for the mod, which compacts once the
// turn has ended.
export async function compactSession(deps, key, focus) {
  if (!focus || !focus.trim()) throw new PuppetError("compact needs a focus text", 2);
  const agents = listAgents(deps);
  const reg = loadRoster(deps, agents);
  const { agent, rec } = rosterRecord(agents, reg, key);
  const fallback = pasteLine(agent.name, `/compact ${focus}`);
  const self = rec.role === "master";
  if (!self) requireBoundary(agent, "compacting");
  requireMod(deps, agent, fallback);
  const file = findTranscript(projectsDir(deps), agent.sessionId);
  let r;
  try {
    r = await modRequest(deps, agent.sessionId, { action: "compact", focus, role: rec.role }, { wait: !self });
  } catch (e) {
    if (!(e instanceof PuppetError)) throw e;
    throw new PuppetError(`${e.message}. Fallback: ${fallback}`);
  }
  if (self) return { name: agent.name, requested: true };
  if (!r.ack.ok) throw new PuppetError(`${agent.name} was NOT compacted: ${r.ack.outcome}${r.ack.detail ? ` (${r.ack.detail})` : ""}. Fallback: ${fallback}`);
  if (newBoundaries(deps.fs.readFileSync(file, "utf8"), new Date(r.requestedAt)).length === 0) {
    throw new PuppetError(`${agent.name}: the mod says compacted, but the transcript gained no new compact_boundary`);
  }
  return { name: agent.name, before: r.ack.tokensBefore ?? null, after: r.ack.tokensAfter ?? null };
}

// Clear a worker whose job is finished, through its own mod, then keep it in the roster as
// a clean session under its new session id.
export async function clearSession(deps, key) {
  const agents = listAgents(deps);
  const reg = loadRoster(deps, agents);
  const { agent, rec } = rosterRecord(agents, reg, key);
  if (rec.role !== "worker") throw new PuppetError(`${agent.name} is the ${rec.role}; only a worker is cleared`);
  if (rec.jobState === "active") throw new PuppetError(`${agent.name} holds an active job ("${rec.job}"); not clearing it`);
  if (rec.jobState !== "done") {
    throw new PuppetError(`${agent.name} has no finished job (it is ${rec.jobState}); only a finished job's session is cleared`);
  }
  requireBoundary(agent, "clearing");
  const fallback = pasteLine(agent.name, "/clear");
  const hb = requireMod(deps, agent, fallback);
  if (hb.role !== "worker") {
    // No role file (a session adopted before the mod existed) is fixed by adopting it again: that
    // keeps its record and writes the file.
    const hint = hb.role ? "" : ` Adopt it again with --role worker (\`adopt ${agent.name} --role worker\`), which keeps its job and writes the role file; the mod sees it within a few seconds.`;
    throw new PuppetError(`${agent.name}: the mod sees its role as ${hb.role ?? "none"}, not worker; not clearing.${hint} Fallback: ${fallback}`);
  }
  let r;
  try {
    r = await modRequest(deps, agent.sessionId, { action: "clear", role: "worker" });
  } catch (e) {
    if (!(e instanceof PuppetError)) throw e;
    throw new PuppetError(`${e.message}. Fallback: ${fallback}`);
  }
  if (!r.ack.ok) throw new PuppetError(`${agent.name} was NOT cleared: ${r.ack.outcome}${r.ack.detail ? ` (${r.ack.detail})` : ""}. Fallback: ${fallback}`);
  const newSid = r.ack.newSessionId;
  if (!newSid || newSid === agent.sessionId) {
    throw new PuppetError(`${agent.name}: the mod says cleared, but gave no new session id (got ${newSid ?? "none"})`);
  }
  const sleep = deps.sleep ?? ((ms) => new Promise((res) => setTimeout(res, ms)));
  let live;
  for (let i = 0; i < 5 && !live; i++) {
    live = listAgents(deps).find((a) => a.sessionId === newSid);
    if (!live && i < 4) await sleep(ACK_WAIT_MS);
  }
  if (!live) {
    throw new PuppetError(`${agent.name} was cleared (new session ${newSid}) but \`claude agents\` does not list it; adopt it again`);
  }
  const next = { ...reg.workers[agent.name], sessionId: newSid, job: null, jobState: "clean", ...(live.id ? { id: live.id } : {}) };
  for (const f of ["tier", "scope", "jobStartedAt"]) delete next[f];
  queueHarvest(reg, agent.name, agent.sessionId);
  reg.workers[agent.name] = next;
  saveRegistry(deps, reg);
  writeModRole(deps, newSid, "worker");
  return { name: agent.name, sessionId: newSid };
}

// The same limits the mod checks: a model alias or a claude-* id (an optional [1m]).
const SWITCH_MODEL_RE = /^(?:opus|sonnet|haiku|claude-[a-z0-9.-]+)(?:\[1m\])?$/;

// What a switch names: a tier's model and effort (as `spawn` launches it), or both given;
// null for --reset, which takes the session back to its launch model and effort.
export function switchTarget({ tier, model, effort, reset = false } = {}) {
  if (reset) {
    if (tier !== undefined || model !== undefined || effort !== undefined) {
      throw new PuppetError("switch: --reset takes no --tier, --model or --effort", 2);
    }
    return null;
  }
  if (tier !== undefined) {
    if (model !== undefined || effort !== undefined) throw new PuppetError("switch: --tier, or --model with --effort, not both", 2);
    tierMatch(tier, {});
    return { ...TIER_LAUNCH[tier] };
  }
  if (model === undefined || effort === undefined) throw new PuppetError("switch: name a --tier, or --model and --effort, or --reset", 2);
  if (!SWITCH_MODEL_RE.test(model)) throw new PuppetError(`--model must be opus, sonnet, haiku or a claude-* id, got "${model}"`, 2);
  if (!EFFORTS.includes(effort)) throw new PuppetError(`--effort must be one of ${EFFORTS.join(", ")}, got "${effort}"`, 2);
  return { model, effort };
}

// Switch a session's model and effort through its own mod, for this session only (no
// settings file is written). The master's own switch cannot wait for an ack (it runs in the
// master's turn): the mod writes it once the turn has ended.
export async function switchSession(deps, key, opts = {}) {
  const target = switchTarget(opts);
  const agents = listAgents(deps);
  const reg = loadRoster(deps, agents);
  const { agent, rec } = rosterRecord(agents, reg, key);
  const fallback = target
    ? switchPaste(agent.name, target)
    : "none needed: where the mod is not on, no switch applies and the session runs its launch model";
  const self = rec.role === "master";
  if (!self) requireBoundary(agent, "switching");
  const hb = requireMod(deps, agent, fallback);
  // A mod loaded before the switch existed beats with no `override` field and drops the request.
  if (!("override" in hb)) {
    throw new PuppetError(`${agent.name}: its mod predates the switch (loaded before the update); reopen the window or run /reload-plugins in it. Fallback: ${fallback}`);
  }
  const last = lastRequest(deps, agent);
  let r;
  try {
    r = await modRequest(deps, agent.sessionId, { action: "switch", ...(target ?? { reset: true }), role: rec.role }, { wait: !self });
  } catch (e) {
    if (!(e instanceof PuppetError)) throw e;
    throw new PuppetError(`${e.message}. Fallback: ${fallback}`);
  }
  if (self) return { name: agent.name, target, requested: true };
  if (!r.ack.ok) {
    throw new PuppetError(`${agent.name} was NOT switched: ${r.ack.outcome}${r.ack.detail ? ` (${r.ack.detail})` : ""}. Fallback: ${fallback}`);
  }
  return { name: agent.name, target, previous: r.ack.previous ?? null, last };
}

// --- subcommands ----------------------------------------------------------------------

const USAGE = [
  "usage: puppet.mjs [--group <name>] <command> ...   (--group: this master's own roster and logs)",
  "  measure <worker> [--window N] [--compact-at N] [--json]",
  "  list [--name <session>] [--window N] [--compact-at N] [--json]",
  "  adopt <session> [--role worker|analyst|master] [--window N] [--self-compact]",
  "  assign <session> <job> [--reuse | --extend] [--scope <dir[,dir]>] [--git | --no-git] [--tier creative|mechanical]   (--git only means something with --extend)",
  "  finish <session>",
  "  reopen <session>",
  "  pick <cwd> [--scope <dir[,dir]>] [--no-git] [--tier creative|mechanical]",
  "  spawn <name> <cwd> <brief-file> (--tier creative|mechanical | --effort <level>) [--model <alias>] [--job <label>] [--scope <dir[,dir]>] [--no-git] [--self-compact]",
  "  cycle <worker> <focus> [--next <brief-file>]",
  "  compact <session> <focus>   (through the session's own mod; needs --self-compact or the user's yes)",
  "  clear <worker>   (a worker whose job is finished, through its own mod)",
  "  switch <session> (--tier creative|mechanical | --model <m> --effort <e> | --reset)   (this session only, through its own mod)",
  "  close <worker>",
  "  harvest [--master <session>] [--logs <dir>] [--plugin-data <dir>]",
  "  logs [--logs <dir>] [--plugin-data <dir>]",
  "  finding --tag <tag> --target <target> --evidence <id[,id]> --note <text> [--logs ...]",
  "  summary [--day YYYY-MM-DD] [--json] [--logs ...]",
  "  decide <proposal> approve|reject|defer --tag <tag> --target <target> --hypothesis <text> [--logs ...]",
  "  shipped <proposal> <sha> [--logs ...]",
].join("\n");

const FLAGS = {
  "--window": true,
  "--compact-at": true,
  "--name": true,
  "--reuse": false,
  "--extend": false,
  "--scope": true,
  "--no-git": false,
  "--git": false,
  "--self-compact": false,
  "--reset": false,
  "--tier": true,
  "--group": true,
  "--model": true,
  "--effort": true,
  "--json": false,
  "--next": true,
  "--role": true,
  "--job": true,
  "--logs": true,
  "--plugin-data": true,
  "--master": true,
  "--tag": true,
  "--target": true,
  "--evidence": true,
  "--note": true,
  "--hypothesis": true,
  "--day": true,
};

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
  const m = measureWorker(deps, positional[0], { window: flags.window, compactAt: flags["compact-at"] });
  deps.out(flags.json ? JSON.stringify(m) : measureLine(m));
  return 0;
}

function cmdList(deps, positional, flags) {
  wantPositional(positional, 0, "list");
  const agents = listAgents(deps);
  const reg = loadRoster(deps, agents);
  const rows = [];
  let failed = false;
  const opts = {
    window: flags.window,
    compactAt: flags["compact-at"],
    observed: reg.observedCompactAt,
    windowOptional: true,
  };
  const measure = (a, rec, extra) => {
    try {
      // A session whose mod never beat shows no mod column.
      const mod = modLabel(modHeartbeat(deps, a.sessionId));
      rows.push({ ...measureAgent(deps, a, rec, opts), ...extra, ...(mod ? { mod } : {}) });
    } catch (e) {
      if (!(e instanceof PuppetError)) throw e;
      failed = true;
      rows.push({ name: a.name, id: a.id, error: e.message });
    }
  };
  // Every roster session, whoever opened it. One that is no longer listed has exited or was
  // stopped: report how to resume it, then drop the record (the transcript stays). One
  // listed under a new session id was cleared or restarted: keep the record, and say so.
  let pruned = false;
  const managed = new Set();
  for (const [name, raw] of Object.entries(reg.workers)) {
    const rec = normalize(raw);
    const live = agents.find((a) => (rec.id && a.id === rec.id) || a.sessionId === rec.sessionId);
    if (live) {
      managed.add(live.sessionId);
      measure(live, raw, { kind: rec.kind, role: rec.role, job: rec.job, jobState: rec.jobState, roster: true });
    } else if (agents.some((a) => a.name === name)) {
      managed.add(agents.find((a) => a.name === name).sessionId);
      rows.push({ name, id: rec.id, changed: true, sessionId: rec.sessionId });
    } else {
      rows.push({ name, id: rec.id, state: "gone", sessionId: rec.sessionId, cwd: rec.cwd });
      queueHarvest(reg, name, rec.sessionId);
      delete reg.workers[name];
      pruned = true;
    }
  }
  // Background sessions nobody adopted are still listed, so none goes unnoticed.
  for (const a of agents.filter((x) => x.kind === "background" && !managed.has(x.sessionId))) {
    measure(a, undefined, {});
  }
  if (noteCompactions(reg, rows) || pruned) saveRegistry(deps, reg);
  let shown = rows;
  if (flags.name !== undefined) {
    shown = rows.filter((r) => r.name === flags.name);
    // A miss says whether the name was closed, and how to resume it.
    if (shown.length === 0) findWorker([], flags.name, reg.closed);
    failed = shown.some((r) => r.error);
  }
  for (const r of shown) {
    if (flags.json) deps.out(JSON.stringify(r));
    else if (r.error) deps.out(`${r.name}  ?  (${r.error})`);
    else if (r.changed) deps.out(`${r.name}  changed  (new session id: ask the user whether it was cleared)`);
    else if (r.state === "gone") deps.out(`${r.name}  gone  (resume: ${resumeHint(r.cwd, r.sessionId)})`);
    else if (r.roster) {
      const job = `${r.kind} ${r.role} ${r.jobState}${r.job ? ` ${r.job}` : ""}`;
      const done = r.jobState === "active" && r.saysDone ? "  DONE? run finish" : "";
      deps.out(`${measureLine(r)}  model ${modelLine(r)}  ${job}${done}${r.mod ? `  ${r.mod}` : ""}`);
    } else deps.out(`${measureLine(r)}  model ${modelLine(r)}${r.mod ? `  ${r.mod}` : ""}`);
  }
  return failed ? 1 : 0;
}

function cmdAdopt(deps, positional, flags) {
  wantPositional(positional, 1, "adopt");
  const r = adoptSession(deps, positional[0], {
    role: flags.role,
    window: flags.window,
    selfCompact: Boolean(flags["self-compact"]),
  });
  deps.out(`adopted ${r.name} (${r.kind}, ${r.role}, ${r.jobState}) in ${r.checkout}${flags["self-compact"] ? "; self-compact switched on" : ""}`);
  return 0;
}

function cmdAssign(deps, positional, flags) {
  wantPositional(positional, 2, "assign");
  const r = assignJob(deps, positional[0], positional[1], {
    reuse: Boolean(flags.reuse),
    extend: Boolean(flags.extend),
    scope: flags.scope,
    noGit: Boolean(flags["no-git"]),
    git: Boolean(flags.git),
    tier: flags.tier,
  });
  const verb = r.extended ? "extended" : "assigned";
  deps.out(`${verb} ${r.name}: ${r.job}${r.scope ? ` (scope ${r.scope.join(",")}${r.git ? "" : ", no git"})` : ""}`);
  if (r.tierCheck) deps.out(r.tierCheck);
  if (r.tierCheck?.startsWith("MISMATCH ")) deps.out(mismatchNext(deps, r.sessionId, r.name, flags.tier));
  return 0;
}

function cmdFinish(deps, positional) {
  wantPositional(positional, 1, "finish");
  const r = finishJob(deps, positional[0]);
  deps.out(`finished ${r.name}: ${r.job}`);
  return 0;
}

function cmdReopen(deps, positional) {
  wantPositional(positional, 1, "reopen");
  const r = reopenJob(deps, positional[0]);
  deps.out(`reopened ${r.name}: ${r.job}`);
  return 0;
}

export function logsDirFor(deps, flags) {
  const dir = resolveLogsDir({
    flag: flags.logs,
    env: deps.env,
    pluginData: flags["plugin-data"],
    configDir: configDir(deps.env),
  }).dir;
  return deps.group ? path.join(dir, deps.group) : dir;
}

// The sessions the analyst reads: every roster session (a transcript stays on disk whether
// or not its session is live), every session that left the roster since the last
// harvest, and the master when named.
function cmdHarvest(deps, positional, flags) {
  wantPositional(positional, 0, "harvest");
  const agents = listAgents(deps);
  const reg = loadRoster(deps, agents);
  const sessions = [];
  const add = (name, sessionId) => {
    if (!sessions.some((s) => s.sessionId === sessionId)) sessions.push({ name, sessionId });
  };
  for (const [name, r] of Object.entries(reg.workers)) add(name, r.sessionId);
  for (const p of reg.pendingHarvest ?? []) add(p.name, p.sessionId);
  if (flags.master) {
    const m = findWorker(agents, flags.master);
    add(m.name, m.sessionId);
  }
  const dir = logsDirFor(deps, flags);
  const r = harvest(deps, { logsDir: dir, sessions });
  if ((reg.pendingHarvest ?? []).length > 0) {
    reg.pendingHarvest = [];
    saveRegistry(deps, reg);
  }
  const missing = r.missing.length > 0 ? `; no transcript: ${r.missing.join(", ")}` : "";
  const restarted = r.restarted.length > 0 ? `; restarted from the top (transcript shrank): ${r.restarted.join(", ")}` : "";
  deps.out(`harvested ${r.events} events from ${r.sessions} sessions (${r.lines} new lines) into ${dir}${missing}${restarted}`);
  return 0;
}

// The logs folder, and the newest report of an earlier day the user has not reviewed.
function cmdLogs(deps, positional, flags) {
  wantPositional(positional, 0, "logs");
  const dir = logsDirFor(deps, flags);
  deps.out(dir);
  const report = unreviewedReport(deps, { logsDir: dir });
  if (report) deps.out(`unreviewed report: ${report}`);
  return 0;
}

function cmdFinding(deps, positional, flags) {
  wantPositional(positional, 0, "finding");
  const evidence = (flags.evidence ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  const f = addFinding(deps, {
    logsDir: logsDirFor(deps, flags),
    tag: flags.tag,
    target: flags.target,
    evidence,
    note: flags.note,
  });
  deps.out(`${f.id} ${f.tag} → ${f.target}`);
  return 0;
}

const counts = (o) =>
  Object.entries(o)
    .map(([k, n]) => `${k} ${n}`)
    .join(", ") || "none";

function cmdSummary(deps, positional, flags) {
  wantPositional(positional, 0, "summary");
  const s = summarize(deps, { logsDir: logsDirFor(deps, flags), ...(flags.day ? { day: flags.day } : {}) });
  if (flags.json) {
    deps.out(JSON.stringify({ headline: headline(s), ...s }));
    return 0;
  }
  deps.out(headline(s));
  deps.out(`events: ${counts(s.eventsByKind)}`);
  deps.out(`findings: ${counts(s.findingsByTag)}`);
  for (const f of s.flagged) deps.out(`flagged for you: ${f.id} ${f.tag} → ${f.target}: ${f.note}`);
  for (const p of s.decisions.pendingShip) deps.out(`approved, not shipped: ${p.proposalId} (${p.tag} → ${p.target})`);
  for (const p of s.decisions.shipped) {
    deps.out(`shipped: ${p.proposalId} ${p.tag} per day ${p.perDayBefore ?? "?"} before → ${p.perDayAfter ?? "?"} after`);
  }
  return 0;
}

function cmdDecide(deps, positional, flags) {
  wantPositional(positional, 2, "decide");
  checkProposalGroup(deps, positional[0]);
  const d = decide(deps, {
    logsDir: logsDirFor(deps, flags),
    proposalId: positional[0],
    decision: positional[1],
    tag: flags.tag,
    target: flags.target,
    hypothesis: flags.hypothesis,
  });
  deps.out(`${d.proposalId} ${d.decision} (${d.tag} → ${d.target})`);
  return 0;
}

function cmdShipped(deps, positional, flags) {
  wantPositional(positional, 2, "shipped");
  checkProposalGroup(deps, positional[0]);
  const r = markShipped(deps, { logsDir: logsDirFor(deps, flags), proposalId: positional[0], sha: positional[1] });
  deps.out(`${r.proposalId} shipped as ${r.changeSha}`);
  return 0;
}

function cmdPick(deps, positional, flags) {
  wantPositional(positional, 1, "pick");
  const hit = pickSession(deps, positional[0], {
    scope: flags.scope,
    noGit: Boolean(flags["no-git"]),
    tier: flags.tier,
  });
  if (!hit) throw new PuppetError(`no clean session for ${checkoutOf(deps, positional[0])}; spawn one`);
  deps.out(hit.name);
  if (hit.tierCheck) deps.out(hit.tierCheck);
  if (hit.tierCheck?.startsWith("MISMATCH ")) deps.out(mismatchNext(deps, hit.agent.sessionId, hit.name, flags.tier));
  return 0;
}

function cmdSpawn(deps, positional, flags) {
  wantPositional(positional, 3, "spawn");
  const w = spawnWorker(deps, ...positional, {
    job: flags.job,
    scope: flags.scope,
    noGit: Boolean(flags["no-git"]),
    tier: flags.tier,
    model: flags.model,
    effort: flags.effort,
    selfCompact: Boolean(flags["self-compact"]),
  });
  const passed = [w.model && `model ${w.model}`, `effort ${w.effort}`].filter(Boolean).join(", ");
  deps.out(`spawned ${w.name} id=${w.id} in ${w.checkout} (${passed})${w.selfCompact ? "; self-compact switched on" : ""}`);
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

async function cmdCompact(deps, positional) {
  wantPositional(positional, 2, "compact");
  const c = await compactSession(deps, positional[0], positional[1]);
  if (c.requested) {
    deps.out(`requested ${c.name}'s own compaction: its mod runs it once this turn ends; check with measure`);
  } else {
    deps.out(`compacted ${c.name}: ${c.before ?? "?"}→${c.after ?? "?"} tokens`);
  }
  return 0;
}

async function cmdClear(deps, positional) {
  wantPositional(positional, 1, "clear");
  const c = await clearSession(deps, positional[0]);
  deps.out(`cleared ${c.name}: new session ${c.sessionId}, clean`);
  return 0;
}

async function cmdSwitch(deps, positional, flags) {
  wantPositional(positional, 1, "switch");
  const s = await switchSession(deps, positional[0], {
    tier: flags.tier,
    model: flags.model,
    effort: flags.effort,
    reset: Boolean(flags.reset),
  });
  const to = s.target ? `${s.target.model} ${s.target.effort}` : "its launch model and effort";
  if (s.requested) {
    deps.out(`requested ${s.name}'s own switch to ${to}: its mod writes it once this turn ends; check with list --name ${s.name} after its next turn`);
    return 0;
  }
  const was = s.previous
    ? ` (switched before to ${s.previous.model} ${s.previous.effort})`
    : s.last.model
      ? ` (last request: ${s.last.model} ${s.last.effort ?? "?"})`
      : "";
  deps.out(
    s.target
      ? `switched ${s.name} to ${to}${was}, from its next request on; its status line and its own answer keep naming the launch model: check with list --name ${s.name} after its next turn`
      : `reset ${s.name}: its next request goes out on ${to}`,
  );
  return 0;
}

function cmdClose(deps, positional) {
  wantPositional(positional, 1, "close");
  const c = closeWorker(deps, positional[0]);
  deps.out(`closed ${c.name} (resume: ${c.resume})`);
  return 0;
}

const COMMANDS = {
  measure: cmdMeasure,
  list: cmdList,
  adopt: cmdAdopt,
  assign: cmdAssign,
  finish: cmdFinish,
  reopen: cmdReopen,
  pick: cmdPick,
  spawn: cmdSpawn,
  cycle: cmdCycle,
  compact: cmdCompact,
  clear: cmdClear,
  switch: cmdSwitch,
  close: cmdClose,
  harvest: cmdHarvest,
  logs: cmdLogs,
  finding: cmdFinding,
  summary: cmdSummary,
  decide: cmdDecide,
  shipped: cmdShipped,
};

export async function main(argv, deps) {
  try {
    // `--group <name>` may lead, so a master's `puppet` shorthand can carry it.
    let args = argv;
    let group;
    if (args[0] === "--group") {
      if (args.length < 2) throw new PuppetError(`--group needs a value\n${USAGE}`, 2);
      group = args[1];
      args = args.slice(2);
    }
    const [cmd, ...rest] = args;
    if (!cmd || !(cmd in COMMANDS)) {
      throw new PuppetError(cmd ? `unknown command ${cmd}\n${USAGE}` : USAGE, 2);
    }
    const { positional, flags } = parseArgs(rest);
    if (flags.group !== undefined) {
      if (group !== undefined && group !== flags.group) {
        throw new PuppetError(`two groups given: ${group} and ${flags.group}`, 2);
      }
      group = flags.group;
    }
    return await COMMANDS[cmd](group === undefined ? deps : withGroup(deps, group), positional, flags);
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
    sleep: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
    fs,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exit(await main(process.argv.slice(2), realDeps()));
}

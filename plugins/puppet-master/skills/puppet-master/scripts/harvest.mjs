// harvest.mjs — the analyst's deterministic half: where the logs live, redaction, and the
// events pulled out of session transcripts. No model work happens here; the analyst
// session tags these events into findings (analyst.mjs).

import path from "node:path";

import { PuppetError, configDir, findTranscript } from "./puppet.mjs";

// --- the logs folder ------------------------------------------------------------------

// A value only counts when it is set and was substituted: an unset plugin option can reach
// the helper as "" or as its literal `${user_config.…}` placeholder.
function usable(v) {
  return typeof v === "string" && v.trim() !== "" && !v.includes("${");
}

export function resolveLogsDir({ flag, env = {}, pluginData, configDir: cfg }) {
  if (usable(env.PUPPET_LOGS_DIR)) return { dir: env.PUPPET_LOGS_DIR, source: "env" };
  if (usable(flag)) return { dir: flag, source: "flag" };
  if (usable(pluginData)) return { dir: path.join(pluginData, "logs"), source: "plugin-data" };
  return { dir: path.join(cfg, "puppet-master", "logs"), source: "config" };
}

// The local calendar day of `date`, as YYYY-MM-DD.
export function dayOf(date) {
  const p = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}`;
}

// A work day starts at this local hour, so a session running past midnight stays in one
// day folder. PUPPET_DAY_START_HOUR overrides it (0 restores calendar days).
export const DAY_START_HOUR = 5;

export function dayStartHour(env = {}) {
  const v = env.PUPPET_DAY_START_HOUR;
  if (v === undefined || v === "") return DAY_START_HOUR;
  if (!/^\d{1,2}$/.test(v) || Number(v) > 23) {
    throw new PuppetError(`PUPPET_DAY_START_HOUR must be a whole hour from 0 to 23, got "${v}"`, 2);
  }
  return Number(v);
}

// The work day of `date`, as YYYY-MM-DD: one folder per work day.
export function workDay(date, startHour = DAY_START_HOUR) {
  const d = new Date(date.getTime());
  d.setHours(d.getHours() - startHour);
  return dayOf(d);
}

// --- redaction ------------------------------------------------------------------------

// Users paste tokens into sessions. A text that matches any of these is replaced whole,
// never masked in part, and before any truncation, so a cut cannot leave half a secret.
const SECRET_PATTERNS = [
  /eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{5,}/, // JWT
  /ATATT[\w=-]{20,}/, // Atlassian API token
  /\bgh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}/,
  /\bsk-[A-Za-z0-9_-]{20,}/,
  /\b[A-Z0-9_]*(TOKEN|SECRET|PASSWORD|API_?KEY|PRIVATE_KEY)[A-Z0-9_]*\s*[=:]\s*\S{6,}/,
  // The lower-case form names the word exactly, and its value holds a letter: "tokens: 218034"
  // is a count, not a secret.
  /\b(token|secret|password|passwd|api_?key)\s*[=:]\s*["']?(?=[^\s"']*[A-Za-z])[^\s"']{6,}/i,
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/,
];

// A long base64 run (a full 40-hex SHA goes too), unless it is an identifier: words of one
// case joined by underscores, like a test name or an environment variable.
const LONG_RUN = /[A-Za-z0-9+=_]{40,}/g;
const WORD = /^([a-z]+|[A-Z]+|[A-Z]?[a-z]+|\d+)$/;

function isIdentifier(run) {
  const parts = run.split("_");
  return parts.length >= 3 && parts.every((p) => p === "" || WORD.test(p));
}

export function redact(text) {
  if (SECRET_PATTERNS.some((re) => re.test(text))) return "[redacted]";
  for (const [run] of text.matchAll(LONG_RUN)) if (!isIdentifier(run)) return "[redacted]";
  return text;
}

// --- events ---------------------------------------------------------------------------

export const EVENT_KINDS = [
  "user-turn",
  "message-in",
  "message-out",
  "helper-error",
  "command-failed",
  "manual-cli",
  "cli-unknown",
  "permission-denied",
  "classifier-denied",
  "compact-manual",
  "compact-auto",
];

const EXCERPT = 300;
const SHELLS = new Set(["Bash", "PowerShell"]);
// `claude` at a command position: the start of a line, or after ; & | or (.
const CLAUDE_AT = /(?:^|[;&|(]\s*)claude\s+([^\s]+)/gm;
const HOUSEKEEPING = new Set(["stop", "rm", "--bg", "-p"]);
const KNOWN_SUBCOMMANDS = new Set([
  "agents", "attach", "logs", "stop", "rm", "plugin", "mcp", "config",
  "doctor", "update", "install", "auth", "setup-token",
]);

function textOf(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .filter((b) => b?.type === "text" && typeof b.text === "string")
    .map((b) => b.text)
    .join("\n");
}

// Auto mode's classifier refusing a call. Its reason is a `[<category>]`, or a sentence when it
// gave none (texts seen 2026-11-10). The refusal does not name the call, so the event does.
const CLASSIFIER = "Permission for this action was denied by the Claude Code auto mode classifier.";
const CATEGORY = /^Reason: \[([^\]]+)\]/;

function classifierText(result, call) {
  const category = CATEGORY.exec(result.slice(CLASSIFIER.length).trimStart())?.[1] ?? "no category";
  return `[${category}] ${call ?? "(call not found)"}`;
}

function shellEvents(command) {
  if (command.includes("puppet.mjs")) return [];
  const words = [...command.matchAll(CLAUDE_AT)].map((m) => m[1]);
  const out = [];
  if (words.some((w) => HOUSEKEEPING.has(w))) out.push("manual-cli");
  if (words.some((w) => !w.startsWith("-") && !KNOWN_SUBCOMMANDS.has(w))) out.push("cli-unknown");
  return out;
}

// Events from one entry. `seen.commands` maps tool_use ids to their shell commands so a
// failed result can be matched to what ran; `seen.calls` maps every tool_use id to its shell
// command, or its tool name and input, for a classifier refusal; `seen.asks` holds the ids of
// AskUserQuestion calls, whose result is the user's answer.
function entryEvents(e, seen) {
  const { commands, calls, asks } = seen;
  const found = [];
  const add = (kind, text) => found.push({ kind, text });
  const content = e.message?.content;
  if (e.type === "user" && !e.isMeta) {
    const text = textOf(content);
    if (text.includes("<cross-session-message")) add("message-in", text);
    else if (text && !text.startsWith("<")) add("user-turn", text);
    if (Array.isArray(content)) {
      for (const b of content) {
        if (b?.type !== "tool_result") continue;
        const r = textOf(b.content);
        // A dialog answer is the user speaking, as much as a typed turn.
        if (asks.has(b.tool_use_id)) {
          if (!b.is_error && r) add("user-turn", r);
          continue;
        }
        // The helper's own failure line starts a line; text that merely quotes the
        // format (a `cat` of SKILL.md) does not.
        if (/^puppet: /m.test(r)) add("helper-error", r);
        else if (r.startsWith("Permission to use ")) add("permission-denied", r);
        else if (r.startsWith(CLASSIFIER)) add("classifier-denied", classifierText(r, calls.get(b.tool_use_id)));
        else if (b.is_error && r.startsWith("Exit code ")) {
          const cmd = commands.get(b.tool_use_id);
          if (cmd !== undefined && /\b(claude|git)\b|puppet\.mjs/.test(cmd)) add("command-failed", `${cmd} → ${r}`);
        }
      }
    }
  } else if (e.type === "assistant" && Array.isArray(content)) {
    for (const b of content) {
      if (b?.type !== "tool_use") continue;
      if (b.name === "AskUserQuestion") {
        asks.add(b.id);
      } else if (b.name === "SendMessage") {
        // A pure notify_when_idle subscription carries no message: nothing was said.
        if (b.input?.message === undefined || b.input.message === "") continue;
        const m = typeof b.input.message === "string" ? b.input.message : JSON.stringify(b.input.message);
        add("message-out", `${b.input?.to}: ${m}`);
      } else if (SHELLS.has(b.name) && typeof b.input?.command === "string") {
        commands.set(b.id, b.input.command);
        calls.set(b.id, b.input.command);
        for (const kind of shellEvents(b.input.command)) add(kind, b.input.command);
      } else {
        calls.set(b.id, `${b.name} ${JSON.stringify(b.input ?? {})}`);
      }
    }
  } else if (e.type === "system" && e.subtype === "compact_boundary") {
    const m = e.compactMetadata ?? {};
    const kind = m.trigger === "auto" ? "compact-auto" : "compact-manual";
    add(kind, `${m.trigger ?? "unknown"} ${m.preTokens ?? "?"}→${m.postTokens ?? "?"}`);
  }
  return found;
}

// Events from the complete lines after `fromLine`. A last line that does not parse is a
// line still being written: it is not consumed, and the next run reads it whole.
export function extractEvents(text, { sessionId, session, fromLine }) {
  const lines = text.split(/\r?\n/);
  const sid = sessionId.slice(0, 8);
  const seen = { commands: new Map(), calls: new Map(), asks: new Set() };
  const events = [];
  let nextLine = fromLine;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const last = i === lines.length - 1;
    if (line.trim() === "") {
      if (!last) nextLine = Math.max(nextLine, i + 1);
      continue;
    }
    let e;
    try {
      e = JSON.parse(line);
    } catch {
      if (last) break;
      throw new PuppetError(`${session} transcript line ${i + 1} is not valid JSON`);
    }
    // Earlier lines are read only to learn their tool_use commands.
    const found = e.isSidechain ? [] : entryEvents(e, seen);
    if (i < fromLine) continue;
    nextLine = i + 1;
    found.forEach((f, k) => {
      events.push({
        id: k === 0 ? `${sid}:${i + 1}` : `${sid}:${i + 1}.${k + 1}`,
        sessionId,
        session,
        ts: e.timestamp ?? null,
        kind: f.kind,
        excerpt: redact(f.text).slice(0, EXCERPT),
      });
    });
  }
  return { events, nextLine };
}

// --- harvesting -----------------------------------------------------------------------

function readJson(deps, p, fallback) {
  let text;
  try {
    text = deps.fs.readFileSync(p, "utf8");
  } catch (e) {
    if (e.code === "ENOENT") return fallback;
    throw new PuppetError(`cannot read ${p}: ${e.message}`);
  }
  try {
    return JSON.parse(text);
  } catch (e) {
    throw new PuppetError(`${p} is not valid JSON: ${e.message}`);
  }
}

function writeJson(deps, p, value) {
  deps.fs.mkdirSync(path.dirname(p), { recursive: true });
  deps.fs.writeFileSync(`${p}.tmp`, `${JSON.stringify(value, null, 2)}\n`);
  deps.fs.renameSync(`${p}.tmp`, p);
}

// One harvest at a time per logs folder: the master and the analyst may both run one, and
// two at once would append the same events twice. A lock older than a harvest can take was
// left by a crash and is taken over.
const STALE_LOCK_MS = 2 * 60 * 1000;

function takeLock(deps, logsDir) {
  const lock = path.join(logsDir, "harvest.lock");
  deps.fs.mkdirSync(logsDir, { recursive: true });
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      deps.fs.writeFileSync(lock, `${process.pid} ${deps.now().toISOString()}\n`, { flag: "wx" });
      return lock;
    } catch (e) {
      if (e.code !== "EEXIST") throw new PuppetError(`cannot create ${lock}: ${e.message}`);
    }
    let age;
    try {
      age = Date.now() - deps.fs.statSync(lock).mtimeMs;
    } catch (e) {
      if (e.code === "ENOENT") continue;
      throw new PuppetError(`cannot read ${lock}: ${e.message}`);
    }
    if (age < STALE_LOCK_MS) {
      throw new PuppetError(`another harvest is running (${lock}); run it again in a moment`);
    }
    deps.fs.rmSync(lock, { force: true });
  }
  throw new PuppetError(`cannot take ${lock}; another harvest keeps taking it`);
}

export function harvest(deps, { logsDir, sessions }) {
  const lock = takeLock(deps, logsDir);
  try {
    return harvestLocked(deps, { logsDir, sessions });
  } finally {
    deps.fs.rmSync(lock, { force: true });
  }
}

function harvestLocked(deps, { logsDir, sessions }) {
  const startHour = dayStartHour(deps.env);
  const day = workDay(deps.now(), startHour);
  const projects = path.join(configDir(deps.env), "projects");
  const offsetsPath = path.join(logsDir, "offsets.json");
  const offsets = readJson(deps, offsetsPath, {});
  const missing = [];
  const restarted = [];
  const read = [];
  let lines = 0;
  const events = [];
  for (const s of sessions) {
    const file = findTranscript(projects, s.sessionId, { optional: true });
    if (file === null) {
      missing.push(s.name);
      continue;
    }
    const text = deps.fs.readFileSync(file, "utf8");
    let from = offsets[s.sessionId] ?? 0;
    // Fewer lines than already read: the file was replaced, so read it again from the top.
    if (from > text.split(/\r?\n/).length) {
      restarted.push(s.name);
      from = 0;
    }
    const r = extractEvents(text, {
      sessionId: s.sessionId,
      session: s.name,
      fromLine: from,
    });
    read.push(s.name);
    lines += r.nextLine - from;
    offsets[s.sessionId] = r.nextLine;
    events.push(...r.events);
  }
  // Each event goes to the work day of its own timestamp, so a harvest run after the day
  // ends still files that day's events under it. An event without a usable timestamp goes
  // to the run's day.
  const byDay = new Map([[day, []]]);
  for (const e of events) {
    const t = e.ts ? new Date(e.ts) : null;
    const d = t && !Number.isNaN(t.getTime()) ? workDay(t, startHour) : day;
    if (!byDay.has(d)) byDay.set(d, []);
    byDay.get(d).push(e);
  }
  // The run itself (its runs, sessions and lines) counts on the run's day; events count on
  // the day they were filed under.
  for (const [d, dayEvents] of byDay) {
    const dayDir = path.join(logsDir, d);
    deps.fs.mkdirSync(dayDir, { recursive: true });
    if (dayEvents.length > 0) {
      deps.fs.appendFileSync(path.join(dayDir, "events.jsonl"), dayEvents.map((e) => `${JSON.stringify(e)}\n`).join(""));
    }
    const statsPath = path.join(dayDir, "harvest-stats.json");
    const stats = readJson(deps, statsPath, { runs: 0, sessions: [], lines: 0, events: 0 });
    const isRunDay = d === day;
    writeJson(deps, statsPath, {
      runs: stats.runs + (isRunDay ? 1 : 0),
      sessions: [...new Set([...stats.sessions, ...(isRunDay ? read : dayEvents.map((e) => e.session))])],
      lines: stats.lines + (isRunDay ? lines : 0),
      events: stats.events + dayEvents.length,
    });
  }
  writeJson(deps, offsetsPath, offsets);
  const days = [...byDay.keys()].filter((d) => d === day || byDay.get(d).length > 0).sort();
  return { sessions: read.length, missing, restarted, lines, events: events.length, day, days };
}

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

// The local calendar day of `date`, as YYYY-MM-DD: one folder per working day.
export function dayOf(date) {
  const p = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}`;
}

// --- redaction ------------------------------------------------------------------------

// Users paste tokens into sessions. A text that matches any of these is replaced whole,
// never masked in part, and before any truncation, so a cut cannot leave half a secret.
const SECRET_PATTERNS = [
  /eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{5,}/, // JWT
  /ATATT[\w=-]{20,}/, // Atlassian API token
  /\bgh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}/,
  /\bsk-[A-Za-z0-9_-]{20,}/,
  /\b[A-Z0-9_]*(TOKEN|SECRET|PASSWORD|API_?KEY|PRIVATE_KEY)[A-Z0-9_]*\s*[=:]\s*\S{6,}/i,
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/,
  /[A-Za-z0-9+=_]{40,}/, // a long base64 run (a full 40-hex SHA goes too)
];

export function redact(text) {
  return SECRET_PATTERNS.some((re) => re.test(text)) ? "[redacted]" : text;
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

function shellEvents(command) {
  if (command.includes("puppet.mjs")) return [];
  const words = [...command.matchAll(CLAUDE_AT)].map((m) => m[1]);
  const out = [];
  if (words.some((w) => HOUSEKEEPING.has(w))) out.push("manual-cli");
  if (words.some((w) => !w.startsWith("-") && !KNOWN_SUBCOMMANDS.has(w))) out.push("cli-unknown");
  return out;
}

// Events from one entry; `commands` maps tool_use ids to their shell commands so a
// failed result can be matched to what ran.
function entryEvents(e, commands) {
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
        // The helper's own failure line starts a line; text that merely quotes the
        // format (a `cat` of SKILL.md) does not.
        if (/^puppet: /m.test(r)) add("helper-error", r);
        else if (r.startsWith("Permission to use ")) add("permission-denied", r);
        else if (b.is_error && r.startsWith("Exit code ")) {
          const cmd = commands.get(b.tool_use_id);
          if (cmd !== undefined && /\b(claude|git)\b|puppet\.mjs/.test(cmd)) add("command-failed", `${cmd} → ${r}`);
        }
      }
    }
  } else if (e.type === "assistant" && Array.isArray(content)) {
    for (const b of content) {
      if (b?.type !== "tool_use") continue;
      if (b.name === "SendMessage") {
        const m = typeof b.input?.message === "string" ? b.input.message : JSON.stringify(b.input?.message);
        add("message-out", `${b.input?.to}: ${m}`);
      } else if (SHELLS.has(b.name) && typeof b.input?.command === "string") {
        commands.set(b.id, b.input.command);
        for (const kind of shellEvents(b.input.command)) add(kind, b.input.command);
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
  const commands = new Map();
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
    const found = e.isSidechain ? [] : entryEvents(e, commands);
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

export function harvest(deps, { logsDir, sessions }) {
  const day = dayOf(deps.now());
  const projects = path.join(configDir(deps.env), "projects");
  const offsetsPath = path.join(logsDir, "offsets.json");
  const offsets = readJson(deps, offsetsPath, {});
  const missing = [];
  const read = [];
  let lines = 0;
  const events = [];
  for (const s of sessions) {
    const file = findTranscript(projects, s.sessionId, { optional: true });
    if (file === null) {
      missing.push(s.name);
      continue;
    }
    const from = offsets[s.sessionId] ?? 0;
    const r = extractEvents(deps.fs.readFileSync(file, "utf8"), {
      sessionId: s.sessionId,
      session: s.name,
      fromLine: from,
    });
    read.push(s.name);
    lines += r.nextLine - from;
    offsets[s.sessionId] = r.nextLine;
    events.push(...r.events);
  }
  const dayDir = path.join(logsDir, day);
  deps.fs.mkdirSync(dayDir, { recursive: true });
  if (events.length > 0) {
    deps.fs.appendFileSync(path.join(dayDir, "events.jsonl"), events.map((e) => `${JSON.stringify(e)}\n`).join(""));
  }
  writeJson(deps, offsetsPath, offsets);
  const statsPath = path.join(dayDir, "harvest-stats.json");
  const stats = readJson(deps, statsPath, { runs: 0, sessions: [], lines: 0, events: 0 });
  writeJson(deps, statsPath, {
    runs: stats.runs + 1,
    sessions: [...new Set([...stats.sessions, ...read])],
    lines: stats.lines + lines,
    events: stats.events + events.length,
  });
  return { sessions: read.length, missing, lines, events: events.length, day };
}

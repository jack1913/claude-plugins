// analyst.mjs — the analyst's bookkeeping: findings that must cite harvested events, the
// day's summary with its honest headline, and the log of the user's decisions on the
// proposals. The analyst session writes proposals; nothing here applies one.

import path from "node:path";

import { dayOf, redact } from "./harvest.mjs";
import { PuppetError } from "./puppet.mjs";

// Each tag names a flaw in the skill, the helper or a brief, never a person.
export const TAGS = [
  "helper-failed",
  "manual-workaround",
  "user-correction",
  "relay-lost-intent",
  "rule-broken",
  "asked-twice",
  "user-did-housekeeping",
  "master-did-the-work",
  "brief-missing-rule",
  "cli-guess",
  "other",
];

export const TARGETS = ["SKILL.md", "worker-brief.md", "puppet.mjs", "docs"];

// The analyst's own instruments: a finding may flag one for the user (target
// `instrument:<file>`), but no proposal is ever drafted against them.
export const INSTRUMENTS = ["analyst-brief.md", "harvest.mjs", "analyst.mjs"];

const DECISIONS = new Set(["approve", "reject", "defer"]);
const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;

function isInstrument(target) {
  return target.startsWith("instrument:") && INSTRUMENTS.includes(target.slice("instrument:".length));
}

function readLines(deps, p) {
  let text;
  try {
    text = deps.fs.readFileSync(p, "utf8");
  } catch (e) {
    if (e.code === "ENOENT") return [];
    throw new PuppetError(`cannot read ${p}: ${e.message}`);
  }
  return text
    .split(/\r?\n/)
    .filter((l) => l.trim() !== "")
    .map((l, i) => {
      try {
        return JSON.parse(l);
      } catch {
        throw new PuppetError(`${p} line ${i + 1} is not valid JSON`);
      }
    });
}

function append(deps, p, row) {
  deps.fs.mkdirSync(path.dirname(p), { recursive: true });
  deps.fs.appendFileSync(p, `${JSON.stringify(row)}\n`);
}

// --- findings -------------------------------------------------------------------------

export function addFinding(deps, { logsDir, tag, target, evidence, note }) {
  if (!TAGS.includes(tag)) throw new PuppetError(`unknown tag "${tag}"; one of: ${TAGS.join(", ")}`, 2);
  if (!TARGETS.includes(target) && !isInstrument(target)) {
    throw new PuppetError(
      `unknown target "${target}"; one of: ${TARGETS.join(", ")}, or instrument:<${INSTRUMENTS.join("|")}>`,
      2,
    );
  }
  if (!Array.isArray(evidence) || evidence.length === 0) {
    throw new PuppetError("a finding needs at least one evidence id from the day's events", 2);
  }
  const day = dayOf(deps.now());
  const known = new Set(readLines(deps, path.join(logsDir, day, "events.jsonl")).map((e) => e.id));
  for (const id of evidence) {
    if (!known.has(id)) throw new PuppetError(`evidence ${id} is not a harvested event of ${day}`);
  }
  const file = path.join(logsDir, day, "findings.jsonl");
  const f = {
    id: `F-${readLines(deps, file).length + 1}`,
    ts: deps.now().toISOString(),
    tag,
    target,
    evidence,
    note: redact(note ?? ""),
  };
  append(deps, file, f);
  return f;
}

// --- decisions ------------------------------------------------------------------------

function decisionsPath(logsDir) {
  return path.join(logsDir, "decisions.jsonl");
}

// Rows fold by proposalId: a later row's fields win.
function foldDecisions(deps, logsDir) {
  const byId = new Map();
  for (const row of readLines(deps, decisionsPath(logsDir))) {
    byId.set(row.proposalId, { ...(byId.get(row.proposalId) ?? {}), ...row });
  }
  return [...byId.values()];
}

export function decide(deps, { logsDir, proposalId, decision, tag, target, hypothesis }) {
  if (!proposalId) throw new PuppetError("decide needs a proposal id", 2);
  if (!DECISIONS.has(decision)) throw new PuppetError(`a decision is approve, reject or defer, got "${decision}"`, 2);
  if (!TAGS.includes(tag)) throw new PuppetError(`unknown tag "${tag}"`, 2);
  if (!TARGETS.includes(target)) throw new PuppetError(`unknown target "${target}"`, 2);
  const row = { proposalId, decision, tag, target, hypothesis: hypothesis ?? "", decidedAt: deps.now().toISOString() };
  append(deps, decisionsPath(logsDir), row);
  return row;
}

export function markShipped(deps, { logsDir, proposalId, sha }) {
  if (!sha) throw new PuppetError("shipped needs the commit sha", 2);
  const p = foldDecisions(deps, logsDir).find((d) => d.proposalId === proposalId);
  if (!p || p.decision !== "approve") throw new PuppetError(`${proposalId} was never approved`);
  const row = { proposalId, changeSha: sha, shippedAt: deps.now().toISOString() };
  append(deps, decisionsPath(logsDir), row);
  return row;
}

// --- the summary ----------------------------------------------------------------------

function dayFolders(deps, logsDir) {
  let names;
  try {
    names = deps.fs.readdirSync(logsDir);
  } catch (e) {
    if (e.code === "ENOENT") return [];
    throw new PuppetError(`cannot read ${logsDir}: ${e.message}`);
  }
  return names.filter((n) => DAY_RE.test(n)).sort();
}

const mean = (xs) => (xs.length === 0 ? null : xs.reduce((a, b) => a + b, 0) / xs.length);

export function summarize(deps, { logsDir, day = dayOf(deps.now()) }) {
  const dir = path.join(logsDir, day);
  let stats = { runs: 0, sessions: [], lines: 0, events: 0 };
  try {
    stats = JSON.parse(deps.fs.readFileSync(path.join(dir, "harvest-stats.json"), "utf8"));
  } catch (e) {
    if (e.code !== "ENOENT") throw new PuppetError(`cannot read ${dir}/harvest-stats.json: ${e.message}`);
  }
  const events = readLines(deps, path.join(dir, "events.jsonl"));
  const eventsByKind = {};
  for (const e of events) eventsByKind[e.kind] = (eventsByKind[e.kind] ?? 0) + 1;
  const all = readLines(deps, path.join(dir, "findings.jsonl"));
  const flagged = all.filter((f) => isInstrument(f.target));
  const findings = all.filter((f) => !isInstrument(f.target));
  const findingsByTag = {};
  for (const f of findings) findingsByTag[f.tag] = (findingsByTag[f.tag] ?? 0) + 1;

  // Days that harvested anything: the denominators for before/after.
  const days = dayFolders(deps, logsDir)
    .filter((d) => readLines(deps, path.join(logsDir, d, "events.jsonl")).length > 0)
    .map((d) => ({
      day: d,
      tags: readLines(deps, path.join(logsDir, d, "findings.jsonl"))
        .filter((f) => !isInstrument(f.target))
        .map((f) => f.tag),
    }));
  const decided = foldDecisions(deps, logsDir);
  const approved = decided.filter((d) => d.decision === "approve");
  const shipped = approved
    .filter((d) => d.changeSha)
    .map((d) => {
      const shipDay = dayOf(new Date(d.shippedAt));
      const count = (x) => x.tags.filter((t) => t === d.tag).length;
      return {
        proposalId: d.proposalId,
        tag: d.tag,
        changeSha: d.changeSha,
        perDayBefore: mean(days.filter((x) => x.day < shipDay).map(count)),
        perDayAfter: mean(days.filter((x) => x.day >= shipDay).map(count)),
      };
    });
  return {
    day,
    sessions: stats.sessions.length,
    lines: stats.lines,
    events: events.length,
    eventsByKind,
    findings: findings.length,
    findingsByTag,
    flagged,
    decisions: {
      approved,
      pendingShip: approved.filter((d) => !d.changeSha),
      shipped,
    },
  };
}

// The report's first line says how much was read, so "no friction" cannot hide "read
// nothing".
export function headline(s) {
  if (s.events === 0) {
    return "read nothing today: no transcript lines were harvested, so this report has no evidence either way";
  }
  return `read ${s.sessions} sessions, ${s.lines} transcript lines, ${s.events} events; ${s.findings} findings`;
}

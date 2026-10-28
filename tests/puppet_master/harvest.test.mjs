import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import {
  EVENT_KINDS,
  extractEvents,
  harvest,
  redact,
  resolveLogsDir,
} from "../../plugins/batbelt/skills/puppet-master/scripts/harvest.mjs";
import { main } from "../../plugins/batbelt/skills/puppet-master/scripts/puppet.mjs";
import { agent, fixture, makeDeps } from "./helpers.mjs";

const SID = "abcdef12-0000-4000-8000-000000000000";
const NOON = () => new Date(2026, 9, 27, 12, 0, 0); // local time, so the day is 2026-10-27 anywhere
const DAY = "2026-10-27";
const readJsonl = (p) =>
  fs.readFileSync(p, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));

test("resolveLogsDir: PUPPET_LOGS_DIR beats the flag, the flag beats plugin data, plugin data beats config", () => {
  const base = { flag: "/f", env: { PUPPET_LOGS_DIR: "/e" }, pluginData: "/p", configDir: "/c" };
  assert.deepEqual(resolveLogsDir(base), { dir: "/e", source: "env" });
  assert.deepEqual(resolveLogsDir({ ...base, env: {} }), { dir: "/f", source: "flag" });
  assert.deepEqual(resolveLogsDir({ ...base, env: {}, flag: undefined }), {
    dir: path.join("/p", "logs"),
    source: "plugin-data",
  });
  assert.deepEqual(resolveLogsDir({ env: {}, configDir: "/c" }), {
    dir: path.join("/c", "puppet-master", "logs"),
    source: "config",
  });
});

test("resolveLogsDir skips an empty or unsubstituted ${user_config...} flag", () => {
  for (const flag of ["", "  ", "${user_config.puppet_logs_dir}"]) {
    assert.equal(resolveLogsDir({ flag, env: {}, pluginData: "/p", configDir: "/c" }).source, "plugin-data");
  }
  const r = resolveLogsDir({
    flag: "${user_config.puppet_logs_dir}",
    env: { PUPPET_LOGS_DIR: "" },
    pluginData: "${CLAUDE_PLUGIN_DATA}",
    configDir: "/c",
  });
  assert.equal(r.source, "config");
  assert.doesNotMatch(r.dir, /\$\{/);
});

test("redact blanks a whole text holding a JWT, an Atlassian token, a ghp_ token or KEY=value", () => {
  const secrets = [
    "token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N",
    "here ATATT0fakeTokenForTests0000000000000000000000 end",
    "use ghp_abcdefghijklmnopqrstuvwxyz0123456789 now",
    "export SERVICE_API_TOKEN=s3cr3tvalue",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "sk-proj-abcdefghijklmnopqrstuvwx",
  ];
  for (const s of secrets) assert.equal(redact(s), "[redacted]", s);
});

test("redact keeps ordinary text, short SHAs, UUIDs and Windows paths with spaces", () => {
  const plain = [
    "D:\\Work\\My Notes\\2026-10-27-review-draft.md",
    "merged as 1a2b3c4d on main",
    "session 1234abcd-0000-4000-8000-00000000beef is idle",
    "/d/work/plugins/batbelt/skills/puppet-master/scripts/harvest",
  ];
  for (const s of plain) assert.equal(redact(s), s);
});

test("a token past the 300-character cut is still redacted", () => {
  const text = `${"x ".repeat(145)}ATATT0fakeTokenForTests0000000000000000000000`;
  const transcript = `${JSON.stringify({ type: "user", timestamp: "2026-10-27T12:00:00Z", message: { role: "user", content: text } })}\n`;
  const { events } = extractEvents(transcript, { sessionId: SID, session: "u1", fromLine: 0 });
  assert.equal(events[0].excerpt, "[redacted]");
});

test("extractEvents finds each kind once in the fixture and ignores the sidechain and every near-miss", () => {
  const { events, nextLine } = extractEvents(fixture("transcript-harvest.jsonl"), {
    sessionId: SID,
    session: "u1",
    fromLine: 0,
  });
  assert.deepEqual(events.map((e) => e.kind).sort(), [...EVENT_KINDS].sort());
  assert.equal(nextLine, 23);
  const byKind = Object.fromEntries(events.map((e) => [e.kind, e]));
  assert.equal(byKind["user-turn"].excerpt, "wait");
  assert.equal(byKind["user-turn"].id, "abcdef12:1");
  assert.equal(byKind["message-out"].excerpt, "fe-collector: The user answered: proceed.");
  assert.match(byKind["message-in"].excerpt, /STOP at step 1/);
  assert.match(byKind["command-failed"].excerpt, /^git push origin main → Exit code 128/);
  assert.match(byKind["manual-cli"].excerpt, /claude stop eb46e69e/);
  assert.match(byKind["cli-unknown"].excerpt, /claude ps/);
  assert.equal(byKind["compact-manual"].excerpt, "manual 477503→28842");
  assert.equal(byKind["compact-auto"].excerpt, "auto 218034→?");
  for (const e of events) {
    assert.equal(e.sessionId, SID);
    assert.equal(e.session, "u1");
    assert.ok(e.ts);
  }
});

test("extractEvents stops before a partial last line and reads it on the next run", () => {
  const lines = fixture("transcript-harvest.jsonl").split(/\r?\n/).filter(Boolean);
  const crlf = `${lines.slice(0, 3).join("\r\n")}\r\n${lines[3].slice(0, 40)}`;
  const first = extractEvents(crlf, { sessionId: SID, session: "u1", fromLine: 0 });
  assert.equal(first.nextLine, 3);
  assert.deepEqual(first.events.map((e) => e.kind), ["user-turn"]);
  const whole = `${lines.slice(0, 4).join("\r\n")}\r\n`;
  const second = extractEvents(whole, { sessionId: SID, session: "u1", fromLine: first.nextLine });
  assert.equal(second.nextLine, 4);
  assert.deepEqual(second.events.map((e) => e.kind), ["message-in"]);
  assert.equal(second.events[0].id, "abcdef12:4");
});

test("extractEvents refuses a bad line that is not the last", () => {
  const lines = fixture("transcript-harvest.jsonl").split(/\r?\n/).filter(Boolean);
  const bad = [lines[0], "{oops", lines[1]].join("\n");
  assert.throws(() => extractEvents(bad, { sessionId: SID, session: "u1", fromLine: 0 }), /u1 transcript line 2 is not valid JSON/);
});

function harvestSetup() {
  const t = makeDeps({ now: NOON });
  t.writeTranscript(SID, fixture("transcript-harvest.jsonl"));
  t.logs = path.join(t.dir, "logs");
  return t;
}

test("harvest appends events, advances offsets and adds to the day's stats", () => {
  const t = harvestSetup();
  try {
    const r = harvest(t.deps, { logsDir: t.logs, sessions: [{ name: "u1", sessionId: SID }] });
    assert.deepEqual(r, { sessions: 1, missing: [], lines: 23, events: 10, day: DAY });
    assert.equal(readJsonl(path.join(t.logs, DAY, "events.jsonl")).length, 10);
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(t.logs, "offsets.json"), "utf8")), { [SID]: 23 });
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(t.logs, DAY, "harvest-stats.json"), "utf8")), {
      runs: 1,
      sessions: ["u1"],
      lines: 23,
      events: 10,
    });
  } finally {
    t.cleanup();
  }
});

test("harvest run twice reads nothing new the second time", () => {
  const t = harvestSetup();
  try {
    harvest(t.deps, { logsDir: t.logs, sessions: [{ name: "u1", sessionId: SID }] });
    const r = harvest(t.deps, { logsDir: t.logs, sessions: [{ name: "u1", sessionId: SID }] });
    assert.equal(r.events, 0);
    assert.equal(r.lines, 0);
    const stats = JSON.parse(fs.readFileSync(path.join(t.logs, DAY, "harvest-stats.json"), "utf8"));
    assert.equal(stats.runs, 2);
    assert.equal(stats.events, 10);
  } finally {
    t.cleanup();
  }
});

test("harvest reports roster sessions without a transcript as missing", () => {
  const t = harvestSetup();
  try {
    const r = harvest(t.deps, {
      logsDir: t.logs,
      sessions: [
        { name: "u1", sessionId: SID },
        { name: "u2", sessionId: "99999999-0000-4000-8000-000000000000" },
      ],
    });
    assert.deepEqual(r.missing, ["u2"]);
    assert.equal(r.sessions, 1);
  } finally {
    t.cleanup();
  }
});

test("cli: harvest prints the one-line log", async () => {
  const u1 = agent("u1", 1, { kind: "interactive", id: undefined, state: undefined, status: "idle" });
  const me = agent("master", 2, { kind: "interactive", id: undefined, state: undefined, status: "busy" });
  const t = makeDeps({ agents: [u1, me], now: NOON });
  try {
    t.writeTranscript(me.sessionId, fixture("transcript-harvest.jsonl"));
    t.writeRegistry({
      workers: { u1: { sessionId: u1.sessionId, cwd: u1.cwd, checkout: u1.cwd, kind: "interactive", role: "worker", job: null, jobState: "clean" } },
    });
    const logs = path.join(t.dir, "my logs");
    assert.equal(await main(["harvest", "--logs", logs, "--plugin-data", "${CLAUDE_PLUGIN_DATA}", "--master", "master"], t.deps), 0);
    assert.deepEqual(t.out, [`harvested 10 events from 1 sessions (23 new lines) into ${logs}; no transcript: u1`]);
  } finally {
    t.cleanup();
  }
});

// Sessions leave the roster (closed, gone, re-adopted after a clear) while their unread
// transcript lines still matter: the next harvest reads them once.
function rosterHarvestSetup(agents, workers) {
  const t = makeDeps({ agents, now: NOON });
  t.writeRegistry({ workers });
  t.logs = path.join(t.dir, "logs");
  t.harvest = async () => {
    t.out.length = 0;
    assert.equal(await main(["harvest", "--logs", t.logs], t.deps), 0);
    return t.out[0];
  };
  return t;
}

test("harvest still reads a worker closed since the last harvest, once", async () => {
  const w1 = agent("w1", 1);
  const t = rosterHarvestSetup([w1], {
    w1: { id: w1.id, sessionId: w1.sessionId, cwd: w1.cwd, checkout: w1.cwd, kind: "background", role: "worker", job: "x", jobState: "done" },
  });
  try {
    t.writeTranscript(w1.sessionId, fixture("transcript-harvest.jsonl"));
    assert.equal(await main(["close", "w1"], t.deps), 0);
    t.deps.agents = [];
    assert.match(await t.harvest(), /^harvested 10 events from 1 sessions/);
    assert.match(await t.harvest(), /^harvested 0 events from 0 sessions/);
    assert.deepEqual(t.readRegistry().pendingHarvest ?? [], []);
  } finally {
    t.cleanup();
  }
});

test("harvest reads a session that list dropped as gone", async () => {
  const u1 = agent("u1", 1, { kind: "interactive", id: undefined, state: undefined, status: "idle" });
  const t = rosterHarvestSetup([], {
    u1: { sessionId: u1.sessionId, cwd: u1.cwd, checkout: u1.cwd, kind: "interactive", role: "worker", job: "x", jobState: "active" },
  });
  try {
    t.writeTranscript(u1.sessionId, fixture("transcript-harvest.jsonl"));
    assert.equal(await main(["list"], t.deps), 0);
    assert.equal(t.readRegistry().workers.u1, undefined);
    assert.match(await t.harvest(), /^harvested 10 events from 1 sessions/);
  } finally {
    t.cleanup();
  }
});

test("re-adopting a cleared window still harvests its old transcript", async () => {
  const u1 = agent("u1", 1, { kind: "interactive", id: undefined, state: undefined, status: "idle" });
  const oldSid = "0ld5e551-0000-4000-8000-000000000000";
  const t = rosterHarvestSetup([u1], {
    u1: { sessionId: oldSid, cwd: u1.cwd, checkout: u1.cwd, kind: "interactive", role: "worker", job: "x", jobState: "done" },
  });
  t.deps.run = ((run) => (cmd, args, opts) => (cmd === "git" ? { code: 0, stdout: `${u1.cwd}\n`, stderr: "" } : run(cmd, args, opts)))(t.deps.run);
  try {
    t.writeTranscript(oldSid, fixture("transcript-harvest.jsonl"));
    assert.equal(await main(["adopt", "u1"], t.deps), 0);
    assert.equal(t.readRegistry().workers.u1.sessionId, u1.sessionId);
    assert.match(await t.harvest(), /^harvested 10 events from 1 sessions .*; no transcript: u1$/);
  } finally {
    t.cleanup();
  }
});

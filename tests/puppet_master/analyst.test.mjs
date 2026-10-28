import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import {
  TAGS,
  addFinding,
  decide,
  headline,
  markShipped,
  summarize,
} from "../../plugins/batbelt/skills/puppet-master/scripts/analyst.mjs";
import { main } from "../../plugins/batbelt/skills/puppet-master/scripts/puppet.mjs";
import { makeDeps } from "./helpers.mjs";

const at = (d, h = 12) => () => new Date(2026, 9, d, h, 0, 0); // local time, October 2026
const ev = (id, kind) => ({ id, sessionId: "s", session: "u1", ts: null, kind, excerpt: "x" });

function setup(now = at(27)) {
  const t = makeDeps({ now });
  t.logs = path.join(t.dir, "logs");
  t.events = (day, events) => {
    fs.mkdirSync(path.join(t.logs, day), { recursive: true });
    fs.appendFileSync(path.join(t.logs, day, "events.jsonl"), events.map((e) => `${JSON.stringify(e)}\n`).join(""));
  };
  t.stats = (day, stats) => {
    fs.mkdirSync(path.join(t.logs, day), { recursive: true });
    fs.writeFileSync(path.join(t.logs, day, "harvest-stats.json"), JSON.stringify(stats));
  };
  t.useDay = (d) => {
    t.deps.now = at(d);
  };
  return t;
}

const finding = (t, extra = {}) =>
  addFinding(t.deps, { logsDir: t.logs, tag: "user-correction", target: "SKILL.md", evidence: ["s:1"], note: "n", ...extra });

test("addFinding refuses an unknown tag, an unknown target, no evidence, or an evidence id not harvested", () => {
  const t = setup();
  try {
    t.events("2026-10-27", [ev("s:1", "user-turn")]);
    assert.throws(() => finding(t, { tag: "vibes" }), /unknown tag "vibes"/);
    assert.throws(() => finding(t, { target: "README.md" }), /unknown target "README.md"/);
    assert.throws(() => finding(t, { evidence: [] }), /needs at least one evidence id/);
    assert.throws(() => finding(t, { evidence: ["s:1", "s:9"] }), /evidence s:9 is not a harvested event of 2026-10-27/);
  } finally {
    t.cleanup();
  }
});

test("addFinding numbers findings per day and redacts the note", () => {
  const t = setup();
  try {
    t.events("2026-10-27", [ev("s:1", "user-turn")]);
    assert.equal(finding(t).id, "F-1");
    const f2 = finding(t, { note: "user pasted ATATT0fakeTokenForTests0000000000000000000000" });
    assert.equal(f2.id, "F-2");
    assert.equal(f2.note, "[redacted]");
    const lines = fs.readFileSync(path.join(t.logs, "2026-10-27", "findings.jsonl"), "utf8").trim().split("\n");
    assert.equal(lines.length, 2);
  } finally {
    t.cleanup();
  }
});

test("an instrument target is listed as flagged, never as a proposal input", () => {
  const t = setup();
  try {
    t.events("2026-10-27", [ev("s:1", "user-turn")]);
    finding(t, { target: "instrument:harvest.mjs", tag: "other" });
    assert.throws(() => finding(t, { target: "instrument:SKILL.md" }), /unknown target/);
    const s = summarize(t.deps, { logsDir: t.logs });
    assert.deepEqual(s.flagged.map((f) => f.id), ["F-1"]);
    assert.equal(s.findings, 0);
    assert.deepEqual(s.findingsByTag, {});
  } finally {
    t.cleanup();
  }
});

test("summary headline says it read nothing when no events were harvested", () => {
  const t = setup();
  try {
    const s = summarize(t.deps, { logsDir: t.logs });
    assert.equal(s.events, 0);
    assert.equal(
      headline(s),
      "read nothing today: no transcript lines were harvested, so this report has no evidence either way",
    );
  } finally {
    t.cleanup();
  }
});

test("summary counts events by kind and findings by tag", () => {
  const t = setup();
  try {
    t.stats("2026-10-27", { runs: 2, sessions: ["u1", "u2"], lines: 900, events: 3 });
    t.events("2026-10-27", [ev("s:1", "user-turn"), ev("s:2", "user-turn"), ev("s:3", "helper-error")]);
    finding(t);
    finding(t, { tag: "helper-failed", target: "puppet.mjs", evidence: ["s:3"] });
    finding(t, { evidence: ["s:2"] });
    const s = summarize(t.deps, { logsDir: t.logs });
    assert.deepEqual(s.eventsByKind, { "user-turn": 2, "helper-error": 1 });
    assert.deepEqual(s.findingsByTag, { "user-correction": 2, "helper-failed": 1 });
    assert.equal(headline(s), "read 2 sessions, 900 transcript lines, 3 events; 3 findings");
  } finally {
    t.cleanup();
  }
});

test("decide then shipped folds into one approved, shipped proposal", () => {
  const t = setup();
  try {
    decide(t.deps, { logsDir: t.logs, proposalId: "P-1", decision: "approve", tag: "user-correction", target: "SKILL.md", hypothesis: "quoting cuts corrections" });
    decide(t.deps, { logsDir: t.logs, proposalId: "P-2", decision: "defer", tag: "cli-guess", target: "SKILL.md", hypothesis: "h" });
    let s = summarize(t.deps, { logsDir: t.logs });
    assert.deepEqual(s.decisions.pendingShip.map((p) => p.proposalId), ["P-1"]);
    markShipped(t.deps, { logsDir: t.logs, proposalId: "P-1", sha: "abc1234" });
    s = summarize(t.deps, { logsDir: t.logs });
    assert.deepEqual(s.decisions.approved.map((p) => p.proposalId), ["P-1"]);
    assert.deepEqual(s.decisions.pendingShip, []);
    assert.equal(s.decisions.shipped[0].proposalId, "P-1");
    assert.throws(() => decide(t.deps, { logsDir: t.logs, proposalId: "P-3", decision: "maybe", tag: "other", target: "docs", hypothesis: "h" }), /approve, reject or defer/);
    assert.throws(() => markShipped(t.deps, { logsDir: t.logs, proposalId: "P-9", sha: "abc1234" }), /P-9 was never approved/);
  } finally {
    t.cleanup();
  }
});

test("before/after per-day means use only day folders with events", () => {
  const t = setup(at(25));
  try {
    // 25th: 2 corrections; 26th: no events (not counted); ship on the 27th; 27th: 1; 28th: 0 with events.
    t.events("2026-10-25", [ev("s:1", "user-turn")]);
    finding(t);
    finding(t);
    fs.mkdirSync(path.join(t.logs, "2026-10-26"), { recursive: true });
    t.useDay(27);
    decide(t.deps, { logsDir: t.logs, proposalId: "P-1", decision: "approve", tag: "user-correction", target: "SKILL.md", hypothesis: "h" });
    markShipped(t.deps, { logsDir: t.logs, proposalId: "P-1", sha: "abc1234" });
    t.events("2026-10-27", [ev("s:1", "user-turn")]);
    finding(t);
    t.useDay(28);
    t.events("2026-10-28", [ev("s:1", "user-turn")]);
    const [p] = summarize(t.deps, { logsDir: t.logs }).decisions.shipped;
    assert.equal(p.perDayBefore, 2);
    assert.equal(p.perDayAfter, 0.5);
  } finally {
    t.cleanup();
  }
});

test("cli: finding, summary, decide and shipped", async () => {
  const t = setup();
  try {
    t.events("2026-10-27", [ev("s:1", "user-turn")]);
    t.stats("2026-10-27", { runs: 1, sessions: ["u1"], lines: 10, events: 1 });
    const logs = ["--logs", t.logs];
    assert.equal(await main(["finding", "--tag", "cli-guess", "--target", "SKILL.md", "--evidence", "s:1", "--note", "claude ps", ...logs], t.deps), 0);
    assert.equal(t.out.at(-1), "F-1 cli-guess → SKILL.md");
    assert.equal(await main(["decide", "P-1", "approve", "--tag", "cli-guess", "--target", "SKILL.md", "--hypothesis", "listing commands stops guesses", ...logs], t.deps), 0);
    assert.equal(t.out.at(-1), "P-1 approve (cli-guess → SKILL.md)");
    assert.equal(await main(["shipped", "P-1", "abc1234", ...logs], t.deps), 0);
    assert.equal(t.out.at(-1), "P-1 shipped as abc1234");
    t.out.length = 0;
    assert.equal(await main(["summary", ...logs], t.deps), 0);
    assert.equal(t.out[0], "read 1 sessions, 10 transcript lines, 1 events; 1 findings");
    assert.equal(await main(["finding", "--tag", "cli-guess", "--target", "SKILL.md", "--evidence", "", ...logs], t.deps), 2);
  } finally {
    t.cleanup();
  }
});

test("TAGS is the closed list from the design", () => {
  assert.deepEqual(TAGS, [
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
  ]);
});

// The helper's compact and clear verbs, the opt-in and role files, and the list column, against
// a fake mod: a scripted `sleep` plays the mod, writing the ack the way the real one would.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import { main } from "../skills/puppet-master/scripts/puppet.mjs";
import { agent, fixture, makeDeps } from "./helpers.mjs";

const NOW = new Date("2026-06-01T00:00:00Z");
const NEW_SID = "99999999-0000-4000-8000-000000000000";
const NONCE = "n0nce001";

const boundaryLine = (timestamp) =>
  `${JSON.stringify({
    type: "system",
    subtype: "compact_boundary",
    isSidechain: false,
    timestamp,
    compactMetadata: { trigger: "manual", preTokens: 50000, postTokens: 9000 },
  })}\n`;

// A worker `w1` (role worker, job done) whose mod beat just now. `mod` plays the mod: it is
// called from `sleep`, i.e. while the helper waits.
function setup({ role = "worker", jobState = "done", state = "done", status = "idle", heartbeat = {}, record = {}, mod } = {}) {
  const w = agent("w1", 1, { state, status });
  const t = makeDeps({ agents: [w], now: () => NOW });
  t.w = w;
  t.modDir = path.join(t.dir, "mod");
  t.deps.env.PUPPET_MOD_DIR = t.modDir;
  t.deps.nonce = () => NONCE;
  t.sleeps = 0;
  t.deps.sleep = async () => {
    t.sleeps++;
    if (mod) mod(t);
  };
  t.transcript = t.writeTranscript(w.sessionId, fixture("transcript-compact-after.jsonl").split(/\r?\n/).slice(0, 2).join("\n") + "\n");
  t.writeRegistry({
    workers: {
      w1: { id: w.id, sessionId: w.sessionId, cwd: "/work/repo", checkout: "/work/repo", kind: "background", role, job: "the job", jobState, ...record },
    },
  });
  t.put = (kind, name, value) => {
    const f = path.join(t.modDir, kind, `${name}.json`);
    fs.mkdirSync(path.dirname(f), { recursive: true });
    fs.writeFileSync(f, typeof value === "string" ? value : JSON.stringify(value));
  };
  t.get = (kind, name) => {
    const f = path.join(t.modDir, kind, `${name}.json`);
    return fs.existsSync(f) ? fs.readFileSync(f, "utf8") : undefined;
  };
  if (heartbeat !== null) {
    t.put("heartbeat", w.sessionId, { sessionId: w.sessionId, beat: NOW.getTime() - 1000, mode: "ask", enabled: true, source: "optin", role: "worker", ...heartbeat });
  }
  t.ack = (body) => t.put("acks", NONCE, { nonce: NONCE, ...body });
  t.request = () => JSON.parse(t.get("requests", w.sessionId));
  return t;
}

const okCompact = (t) => {
  fs.appendFileSync(t.transcript, boundaryLine("2026-06-01T00:00:05.000Z"));
  t.ack({ ok: true, outcome: "compacted", tokensBefore: 50000, tokensAfter: 9000 });
};
const okClear = (t) => {
  t.deps.agents = [{ ...t.w, sessionId: NEW_SID }];
  t.ack({ ok: true, outcome: "cleared", newSessionId: NEW_SID });
};

test("compact writes a request for the session and prints the tokens before and after", async () => {
  const t = setup({ mod: okCompact });
  try {
    assert.equal(await main(["compact", "w1", "keep the plan"], t.deps), 0);
    assert.deepEqual(t.out, ["compacted w1: 50000→9000 tokens"]);
    assert.equal(t.sleeps, 1);
    // the helper took the ack away and the mod's request is still the one we wrote
    assert.equal(t.get("acks", NONCE), undefined);
    assert.deepEqual(t.request(), {
      nonce: NONCE,
      sessionId: t.w.sessionId,
      requestedAt: NOW.getTime(),
      action: "compact",
      focus: "keep the plan",
      role: "worker",
    });
    assert.deepEqual(t.calls.filter((c) => c.args[0] !== "agents"), []);
  } finally {
    t.cleanup();
  }
});

test("compact needs a focus", async () => {
  const t = setup();
  try {
    assert.equal(await main(["compact", "w1", "  "], t.deps), 2);
    assert.match(t.err.join("\n"), /needs a focus/);
  } finally {
    t.cleanup();
  }
});

test("compact refuses a session that is working or parked on a dialog", async () => {
  for (const [state, status, re] of [
    ["working", "busy", /not at a task boundary \(state working\)/],
    ["done", "waiting", /waiting on a dialog/],
  ]) {
    const t = setup({ state, status });
    try {
      assert.equal(await main(["compact", "w1", "focus"], t.deps), 1);
      assert.match(t.err.join("\n"), re);
      assert.equal(t.get("requests", t.w.sessionId), undefined);
    } finally {
      t.cleanup();
    }
  }
});

test("compact refuses a session outside the roster", async () => {
  const t = setup();
  try {
    t.writeRegistry({ workers: {} });
    assert.equal(await main(["compact", "w1", "focus"], t.deps), 1);
    assert.match(t.err.join("\n"), /not in the roster; adopt it first/);
  } finally {
    t.cleanup();
  }
});

test("compact says why the mod is missing and prints the paste line as the fallback", async () => {
  const cases = [
    [{ heartbeat: null }, /no mod heartbeat: the plugin is not loaded/],
    [{ heartbeat: { beat: NOW.getTime() - 60000 } }, /heartbeat is stale/],
    [{ heartbeat: { enabled: false, source: null, mode: "ask" } }, /loaded but not switched on \(self_compact ask; spawn or adopt it with --self-compact/],
    [{ heartbeat: { enabled: false, source: null, mode: "off" } }, /self_compact off, the user's veto/],
  ];
  for (const [opts, re] of cases) {
    const t = setup(opts);
    try {
      assert.equal(await main(["compact", "w1", "keep the plan"], t.deps), 1);
      const msg = t.err.join("\n");
      assert.match(msg, re);
      assert.ok(msg.includes('Fallback: give the user "w1: /compact keep the plan" to paste'), msg);
      assert.equal(t.get("requests", t.w.sessionId), undefined);
    } finally {
      t.cleanup();
    }
  }
});

test("compact: a refusal ack, a missing boundary and a timeout are each loud", async () => {
  const refused = setup({ mod: (t) => t.ack({ ok: false, outcome: "stale", detail: "compact rejected: a turn is running" }) });
  try {
    assert.equal(await main(["compact", "w1", "f"], refused.deps), 1);
    assert.match(refused.err.join("\n"), /w1 was NOT compacted: stale \(compact rejected: a turn is running\)\. Fallback: /);
  } finally {
    refused.cleanup();
  }
  const noBoundary = setup({ mod: (t) => t.ack({ ok: true, outcome: "compacted", tokensBefore: 1, tokensAfter: 1 }) });
  try {
    assert.equal(await main(["compact", "w1", "f"], noBoundary.deps), 1);
    assert.match(noBoundary.err.join("\n"), /gained no new compact_boundary/);
  } finally {
    noBoundary.cleanup();
  }
  const silent = setup();
  try {
    assert.equal(await main(["compact", "w1", "f"], silent.deps), 1);
    assert.match(silent.err.join("\n"), /no answer from the mod in 90 s; the request was withdrawn\. Fallback: /);
    assert.equal(silent.sleeps, 90);
    // withdrawn: the mod can no longer run it unseen
    assert.equal(silent.get("requests", silent.w.sessionId).trim(), "{}");
  } finally {
    silent.cleanup();
  }
});

test("compact will not stack a second request on a waiting one", async () => {
  const t = setup();
  try {
    t.put("requests", t.w.sessionId, { nonce: "older", action: "compact" });
    assert.equal(await main(["compact", "w1", "f"], t.deps), 1);
    assert.match(t.err.join("\n"), /already waiting/);
  } finally {
    t.cleanup();
  }
});

test("compact on the master leaves the request for after its turn and does not wait", async () => {
  const t = setup({ role: "master", state: "working", status: "busy", heartbeat: { role: "master" } });
  try {
    assert.equal(await main(["compact", "w1", "keep the roster"], t.deps), 0);
    assert.equal(t.sleeps, 0);
    assert.match(t.out[0], /^requested w1's own compaction: its mod runs it once this turn ends/);
    assert.equal(t.request().action, "compact");
    assert.equal(t.request().role, "master");
  } finally {
    t.cleanup();
  }
});

test("clear: runs on a finished worker, re-adopts it under its new session id as clean", async () => {
  const t = setup({ mod: okClear, record: { scope: ["src"], tier: "creative", jobStartedAt: "x" } });
  try {
    assert.equal(await main(["clear", "w1"], t.deps), 0);
    assert.deepEqual(t.out, [`cleared w1: new session ${NEW_SID}, clean`]);
    assert.equal(t.request().action, "clear");
    assert.equal(t.request().role, "worker");
    const rec = t.readRegistry().workers.w1;
    assert.equal(rec.sessionId, NEW_SID);
    assert.equal(rec.jobState, "clean");
    assert.equal(rec.job, null);
    assert.equal("tier" in rec, false);
    assert.equal("scope" in rec, false);
    assert.deepEqual(t.readRegistry().pendingHarvest, [{ name: "w1", sessionId: t.w.sessionId }]);
    assert.equal(JSON.parse(t.get("roles", NEW_SID)).role, "worker");
  } finally {
    t.cleanup();
  }
});

test("clear refuses a master and an analyst, and never writes a request", async () => {
  for (const role of ["master", "analyst"]) {
    const t = setup({ role });
    try {
      assert.equal(await main(["clear", "w1"], t.deps), 1);
      assert.match(t.err.join("\n"), new RegExp(`w1 is the ${role}; only a worker is cleared`));
      assert.equal(t.get("requests", t.w.sessionId), undefined);
    } finally {
      t.cleanup();
    }
  }
});

test("clear refuses a worker with an active, unknown or no job", async () => {
  for (const [jobState, re] of [
    ["active", /holds an active job \("the job"\); not clearing it/],
    ["unknown", /has no finished job \(it is unknown\)/],
    ["clean", /has no finished job \(it is clean\)/],
  ]) {
    const t = setup({ jobState });
    try {
      assert.equal(await main(["clear", "w1"], t.deps), 1);
      assert.match(t.err.join("\n"), re);
      assert.equal(t.get("requests", t.w.sessionId), undefined);
    } finally {
      t.cleanup();
    }
  }
});

test("clear refuses a busy or dialog-parked worker, a missing mod, and a mod that does not see a worker role", async () => {
  const cases = [
    [{ state: "working", status: "busy" }, /not at a task boundary/],
    [{ state: "done", status: "waiting" }, /waiting on a dialog/],
    [{ heartbeat: null }, /no mod heartbeat/],
    [{ heartbeat: { enabled: false, source: null, mode: "ask" } }, /not switched on/],
    [{ heartbeat: { role: "master" } }, /mod sees its role as master, not worker/],
    [{ heartbeat: { role: null } }, /mod sees its role as none, not worker/],
  ];
  for (const [opts, re] of cases) {
    const t = setup(opts);
    try {
      assert.equal(await main(["clear", "w1"], t.deps), 1);
      assert.match(t.err.join("\n"), re);
      assert.equal(t.get("requests", t.w.sessionId), undefined);
    } finally {
      t.cleanup();
    }
  }
});

test("clear: a refusing ack, a missing new id and an unlisted new session are each loud", async () => {
  const busy = setup({ mod: (t) => t.ack({ ok: false, outcome: "busy", detail: "a turn is running" }) });
  try {
    assert.equal(await main(["clear", "w1"], busy.deps), 1);
    assert.match(busy.err.join("\n"), /w1 was NOT cleared: busy \(a turn is running\)\. Fallback: give the user "w1: \/clear" to paste/);
    assert.equal(busy.readRegistry().workers.w1.jobState, "done");
  } finally {
    busy.cleanup();
  }
  const noId = setup({ mod: (t) => t.ack({ ok: true, outcome: "cleared" }) });
  try {
    assert.equal(await main(["clear", "w1"], noId.deps), 1);
    assert.match(noId.err.join("\n"), /gave no new session id/);
  } finally {
    noId.cleanup();
  }
  const unlisted = setup({ mod: (t) => t.ack({ ok: true, outcome: "cleared", newSessionId: NEW_SID }) });
  try {
    assert.equal(await main(["clear", "w1"], unlisted.deps), 1);
    assert.match(unlisted.err.join("\n"), new RegExp(`cleared \\(new session ${NEW_SID}\\) but .claude agents. does not list it`));
  } finally {
    unlisted.cleanup();
  }
});

// --- the files the helper hands the mod ---

test("adopt writes the session's role for the mod, and an opt-in only with --self-compact", async () => {
  const t = makeDeps({ agents: [agent("u1", 1, { kind: "interactive" })], now: () => NOW });
  t.deps.env.PUPPET_MOD_DIR = path.join(t.dir, "mod");
  t.deps.platform = "win32";
  t.deps.run = ((orig) => (cmd, args, opts) => (cmd === "git" ? { code: 0, stdout: "C:\\Work\\Repo\n", stderr: "" } : orig(cmd, args, opts)))(t.deps.run);
  try {
    const sid = t.deps.agents[0].sessionId;
    assert.equal(await main(["adopt", "u1", "--role", "master"], t.deps), 0);
    assert.equal(JSON.parse(fs.readFileSync(path.join(t.dir, "mod", "roles", `${sid}.json`), "utf8")).role, "master");
    assert.equal(fs.existsSync(path.join(t.dir, "mod", "optin", `${sid}.json`)), false);
    t.out.length = 0;
    assert.equal(await main(["adopt", "u1", "--role", "worker", "--self-compact"], t.deps), 0);
    assert.equal(JSON.parse(fs.readFileSync(path.join(t.dir, "mod", "roles", `${sid}.json`), "utf8")).role, "worker");
    assert.ok(fs.existsSync(path.join(t.dir, "mod", "optin", `${sid}.json`)));
    assert.match(t.out[0], /; self-compact switched on$/);
  } finally {
    t.cleanup();
  }
});

test("spawn --self-compact opts the worker in; without it only the role is written", async () => {
  for (const flag of [true, false]) {
    const fresh = agent("w9", 9);
    const t = makeDeps({
      agents: [],
      now: () => NOW,
      handler(args, opts, calls) {
        if (calls.at(-1).cmd === "git") return { stdout: "C:\\Work\\Repo\n" };
        if (args[0] === "--bg") {
          t.deps.agents.push(fresh);
          return { stdout: fixture("bg-stdout.txt").replaceAll("573b7648", fresh.id) };
        }
        return undefined;
      },
    });
    t.deps.env.PUPPET_MOD_DIR = path.join(t.dir, "mod");
    t.deps.platform = "win32";
    try {
      const brief = path.join(t.dir, "brief.md");
      fs.writeFileSync(brief, "job");
      assert.equal(await main(["spawn", "w9", "C:\\work\\repo", brief, "--effort", "high", ...(flag ? ["--self-compact"] : [])], t.deps), 0);
      assert.equal(JSON.parse(fs.readFileSync(path.join(t.dir, "mod", "roles", `${fresh.sessionId}.json`), "utf8")).role, "worker");
      assert.equal(fs.existsSync(path.join(t.dir, "mod", "optin", `${fresh.sessionId}.json`)), flag);
      assert.equal(/self-compact switched on/.test(t.out[0]), flag);
    } finally {
      t.cleanup();
    }
  }
});

// --- list ---

test("list shows a mod column only for a session whose mod beat, and says when it stopped", async () => {
  const on = setup({ heartbeat: { enabled: true, source: "asked" } });
  try {
    assert.equal(await main(["list"], on.deps), 0);
    assert.match(on.out[0], /mod on \(asked\)$/);
  } finally {
    on.cleanup();
  }
  const off = setup({ heartbeat: { enabled: false, source: null, mode: "ask" } });
  try {
    assert.equal(await main(["list"], off.deps), 0);
    assert.match(off.out[0], /mod off \(mode ask\)$/);
  } finally {
    off.cleanup();
  }
  const stale = setup({ heartbeat: { beat: NOW.getTime() - 60000 } });
  try {
    assert.equal(await main(["list"], stale.deps), 0);
    assert.match(stale.out[0], /mod stale$/);
  } finally {
    stale.cleanup();
  }
  const none = setup({ heartbeat: null });
  try {
    assert.equal(await main(["list", "--json"], none.deps), 0);
    assert.equal("mod" in JSON.parse(none.out[0]), false);
  } finally {
    none.cleanup();
  }
});

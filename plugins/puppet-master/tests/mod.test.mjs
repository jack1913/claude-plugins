// The mod (hooks/puppet-mod.js) against a fake `$`: no Claude session starts. The fake keeps
// files in a Map, records every call, and lets a test script each answer.
import { test } from "node:test";
import assert from "node:assert/strict";

import { register } from "../hooks/puppet-mod.js";

const DIR = "/mod";
const SID = "11111111-aaaa";
const ASK_YES = "Yes, this session (Recommended)";
const ASK_ALWAYS = "Yes, always on this machine";
const ASK_NEVER = "No, and don't ask again on this machine";

// A running mod in a fake session. `files` seeds the folder, keys relative to /mod.
function setup({ mode = "ask", kind = "interactive", answer = ASK_YES, files = {}, sid = SID, compact, run, agentsFail = false } = {}) {
  const fsMap = new Map(Object.entries(files).map(([k, v]) => [`${DIR}/${k}`, typeof v === "string" ? v : JSON.stringify(v)]));
  const handlers = {};
  const timers = { every: null, after: [] };
  const calls = { compact: [], run: [], ask: [], set: [], log: [], process: [] };
  const state = { now: 1_000_000, sid, mode };
  const $ = {
    env: { get: async (n) => (n === "PUPPET_MOD_DIR" ? DIR : undefined) },
    fs: {
      exists: async (p) => fsMap.has(p),
      read: async (p) => {
        if (!fsMap.has(p)) throw new Error(`ENOENT ${p}`);
        return fsMap.get(p);
      },
      write: async (p, t) => void fsMap.set(p, t),
    },
    clock: {
      now: async () => state.now,
      every: (ms, fn) => void (timers.every = fn),
      after: (ms, fn) => void timers.after.push(fn),
      sleep: () => new Promise(() => {}),
    },
    config: {
      list: async () => [{ key: "puppet-master.self_compact", value: state.mode }],
      set: async (a) => {
        calls.set.push(a);
        state.mode = a.value;
        return { value: a.value };
      },
    },
    session: {
      id: async () => state.sid,
      usage: async () => ({ context: { tokens: 50000 } }),
      compact: async (a) => {
        calls.compact.push(a);
        if (compact) return compact(a);
        return { tokensBefore: 50000, tokensAfter: 9000 };
      },
    },
    command: {
      run: async (a) => {
        calls.run.push(a);
        if (run) return run(a, state);
        state.sid = "22222222-bbbb";
        return { text: "" };
      },
    },
    ui: {
      ask: async (q, opts) => {
        calls.ask.push({ q, opts });
        if (answer instanceof Error) throw answer;
        return answer;
      },
      log: (t) => calls.log.push(t),
    },
    process: {
      run: async (argv) => {
        calls.process.push(argv);
        if (agentsFail) return { exitCode: 1, stdout: "", stderr: "boom" };
        return { exitCode: 0, stdout: JSON.stringify([{ sessionId: state.sid, kind }]), stderr: "" };
      },
    },
  };
  register((name, fn) => void (handlers[name] = fn));
  const pass = async (e) => e;
  const t = {
    $,
    fsMap,
    calls,
    state,
    handlers,
    async start(e = { isInteractive: true, surface: "terminal", cwd: "/w" }) {
      await handlers["session.start"]($, e, pass);
    },
    async tick() {
      await timers.every();
    },
    async ask() {
      for (const fn of timers.after.splice(0)) await fn();
    },
    json(rel) {
      const v = fsMap.get(`${DIR}/${rel}`);
      return v === undefined ? undefined : JSON.parse(v);
    },
    put(rel, v) {
      fsMap.set(`${DIR}/${rel}`, typeof v === "string" ? v : JSON.stringify(v));
    },
    request(extra = {}) {
      const nonce = extra.nonce ?? "abcd1234";
      t.put(`requests/${state.sid}.json`, { nonce, action: "compact", focus: "the plan", sessionId: state.sid, role: "worker", requestedAt: state.now - 1000, ...extra });
      return nonce;
    },
    ack(nonce) {
      return t.json(`acks/${nonce}.json`);
    },
    optin() {
      t.put(`optin/${state.sid}.json`, { at: "x" });
    },
    role(role) {
      t.put(`roles/${state.sid}.json`, { role });
    },
  };
  return t;
}

test("off unless switched on: a session in mode ask with no answer ignores a compact request", async () => {
  const t = setup();
  await t.start();
  const n = t.request();
  await t.tick();
  assert.equal(t.calls.compact.length, 0);
  assert.equal(t.ack(n).outcome, "not-enabled");
  assert.equal(t.json("heartbeat/" + SID + ".json").enabled, false);
});

test("the heartbeat names the session, version, mode, source and role", async () => {
  const t = setup({ mode: "on" });
  t.role("worker");
  await t.start();
  await t.tick();
  const hb = t.json(`heartbeat/${SID}.json`);
  assert.equal(hb.sessionId, SID);
  assert.equal(hb.version, "0.1.0");
  assert.equal(hb.mode, "on");
  assert.equal(hb.enabled, true);
  assert.equal(hb.source, "config");
  assert.equal(hb.role, "worker");
});

test("a missing config row is off, never on", async () => {
  const t = setup({ mode: "on" });
  t.$.config.list = async () => [];
  await t.start();
  await t.tick();
  assert.equal(t.json(`heartbeat/${SID}.json`).mode, "off");
  assert.equal(t.json(`heartbeat/${SID}.json`).enabled, false);
});

test("the helper's opt-in switches a session on; a compact request is run with the focus and acked", async () => {
  const t = setup();
  t.optin();
  await t.start();
  const n = t.request({ focus: "keep the plan" });
  await t.tick();
  assert.deepEqual(t.calls.compact, [{ instructions: "keep the plan" }]);
  assert.deepEqual(
    (({ ok, outcome, tokensBefore, tokensAfter, sessionId }) => ({ ok, outcome, tokensBefore, tokensAfter, sessionId }))(t.ack(n)),
    { ok: true, outcome: "compacted", tokensBefore: 50000, tokensAfter: 9000, sessionId: SID },
  );
  assert.equal(t.fsMap.get(`${DIR}/requests/${SID}.json`), "{}");
});

test("mode off is a veto: it beats an opt-in", async () => {
  const t = setup({ mode: "off" });
  t.optin();
  await t.start();
  const n = t.request();
  await t.tick();
  assert.equal(t.calls.compact.length, 0);
  assert.equal(t.ack(n).outcome, "not-enabled");
});

test("a request for another session is refused, a stale one is refused, a handled nonce is not run twice", async () => {
  const t = setup({ mode: "on" });
  await t.start();
  const a = t.request({ nonce: "other-1", sessionId: "someone-else" });
  await t.tick();
  assert.equal(t.ack(a).outcome, "wrong-session");
  const b = t.request({ nonce: "stale-1", requestedAt: t.state.now - 6 * 60 * 1000 });
  await t.tick();
  assert.equal(t.ack(b).outcome, "stale");
  const c = t.request({ nonce: "fresh-1" });
  await t.tick();
  t.request({ nonce: "fresh-1" });
  await t.tick();
  assert.equal(t.ack(c).outcome, "compacted");
  assert.equal(t.calls.compact.length, 1);
});

test("a compact rejected mid-turn keeps the request and retries on the next tick", async () => {
  let reject = true;
  const t = setup({
    mode: "on",
    compact: () => {
      if (reject) throw new Error("a turn is running");
      return { tokensBefore: 7, tokensAfter: 3 };
    },
  });
  await t.start();
  const n = t.request();
  await t.tick();
  assert.equal(t.ack(n), undefined);
  assert.notEqual(t.fsMap.get(`${DIR}/requests/${SID}.json`), "{}");
  await t.tick();
  assert.match(t.json(`heartbeat/${SID}.json`).lastError, /compact rejected: a turn is running/);
  reject = false;
  await t.tick();
  assert.equal(t.ack(n).outcome, "compacted");
});

test("a compact that is still rejected when the request goes stale is answered stale, with the reason", async () => {
  const t = setup({ mode: "on", compact: () => { throw new Error("a turn is running"); } });
  await t.start();
  const n = t.request();
  await t.tick();
  t.state.now += 6 * 60 * 1000;
  await t.tick();
  assert.equal(t.ack(n).outcome, "stale");
  assert.match(t.ack(n).detail, /a turn is running/);
});

test("a veto from a hook is reported as not compacted", async () => {
  const t = setup({ mode: "on", compact: () => ({ skip: true }) });
  await t.start();
  const n = t.request();
  await t.tick();
  assert.equal(t.ack(n).ok, false);
  assert.equal(t.ack(n).outcome, "vetoed");
});

test("clear: refused without a worker role file, even when switched on", async () => {
  const t = setup({ mode: "on" });
  await t.start();
  const n = t.request({ action: "clear" });
  await t.tick();
  assert.equal(t.calls.run.length, 0);
  assert.equal(t.ack(n).outcome, "refused-role");
});

test("clear: refused for a master or analyst role, and when the request does not say worker", async () => {
  for (const [fileRole, reqRole] of [["master", "worker"], ["analyst", "worker"], ["worker", "master"], ["worker", undefined]]) {
    const t = setup({ mode: "on" });
    t.role(fileRole);
    await t.start();
    const n = t.request({ action: "clear", role: reqRole });
    await t.tick();
    assert.equal(t.calls.run.length, 0, `${fileRole}/${reqRole}`);
    assert.equal(t.ack(n).outcome, "refused-role");
  }
});

test("clear: refused when not switched on", async () => {
  const t = setup({ mode: "ask" });
  t.role("worker");
  await t.start();
  const n = t.request({ action: "clear" });
  await t.tick();
  assert.equal(t.calls.run.length, 0);
  assert.equal(t.ack(n).outcome, "not-enabled");
});

test("clear: refused while a turn runs or just after a prompt arrived, and never queued", async () => {
  const t = setup({ mode: "on" });
  t.role("worker");
  await t.start();
  await t.handlers["turn.start"](t.$, {}, async (e) => e);
  const a = t.request({ action: "clear", nonce: "busy-1" });
  await t.tick();
  assert.equal(t.ack(a).outcome, "busy");
  await t.handlers["turn.complete"](t.$, {}, async (e) => e);
  await t.handlers["prompt.submit"](t.$, {}, async (e) => e);
  const b = t.request({ action: "clear", nonce: "busy-2" });
  await t.tick();
  assert.equal(t.ack(b).outcome, "busy");
  assert.equal(t.calls.run.length, 0);
});

test("clear: runs /clear on an idle worker, acks the new session id and carries the files over", async () => {
  const t = setup({ mode: "on" });
  t.role("worker");
  t.optin();
  await t.start();
  const n = t.request({ action: "clear" });
  await t.tick();
  assert.deepEqual(t.calls.run, [{ command: "clear", args: "" }]);
  const ack = t.ack(n);
  assert.equal(ack.ok, true);
  assert.equal(ack.outcome, "cleared");
  assert.equal(ack.newSessionId, "22222222-bbbb");
  assert.equal(t.json("roles/22222222-bbbb.json").role, "worker");
  assert.ok(t.json("optin/22222222-bbbb.json"));
});

test("after a clear the mod keeps beating under the new session id", async () => {
  const t = setup({ mode: "on" });
  t.role("worker");
  await t.start();
  t.request({ action: "clear" });
  await t.tick();
  await t.tick();
  assert.equal(t.json("heartbeat/22222222-bbbb.json").role, "worker");
});

test("a /clear that rejects is acked as rejected", async () => {
  const t = setup({ mode: "on", run: () => { throw new Error("past a Stop"); } });
  t.role("worker");
  await t.start();
  const n = t.request({ action: "clear" });
  await t.tick();
  assert.equal(t.ack(n).ok, false);
  assert.equal(t.ack(n).outcome, "rejected");
});

test("an unreadable request file is a loud error, not a silent skip", async () => {
  const t = setup({ mode: "on" });
  await t.start();
  t.put(`requests/${SID}.json`, "{not json");
  await t.tick();
  assert.ok(t.calls.log.some((l) => /not valid JSON/.test(l)), t.calls.log.join("|"));
});

// --- the question at session start ---

test("start question: an interactive window in mode ask is asked, with the four answers and yes first", async () => {
  const t = setup();
  await t.start();
  await t.ask();
  assert.equal(t.calls.ask.length, 1);
  assert.deepEqual(t.calls.ask[0].opts[0], ASK_YES);
  assert.equal(t.calls.ask[0].opts.length, 4);
  assert.equal(t.calls.process[0][0], "claude");
  assert.deepEqual(t.calls.process[0].slice(1), ["agents", "--json"]);
  await t.tick();
  assert.equal(t.json(`heartbeat/${SID}.json`).enabled, true);
  assert.equal(t.json(`heartbeat/${SID}.json`).source, "asked");
  assert.equal(t.json(`heartbeat/${SID}.json`).ask, "yes");
});

test("start question: yes for this session writes no config; always sets self_compact=on", async () => {
  const yes = setup({ answer: ASK_YES });
  await yes.start();
  await yes.ask();
  assert.equal(yes.calls.set.length, 0);
  const always = setup({ answer: ASK_ALWAYS });
  await always.start();
  await always.ask();
  assert.deepEqual(always.calls.set, [{ key: "puppet-master.self_compact", value: "on" }]);
});

test("start question: 'don't ask again' sets self_compact=off and leaves the session off", async () => {
  const t = setup({ answer: ASK_NEVER });
  await t.start();
  await t.ask();
  assert.deepEqual(t.calls.set, [{ key: "puppet-master.self_compact", value: "off" }]);
  await t.tick();
  assert.equal(t.json(`heartbeat/${SID}.json`).enabled, false);
});

test("start question: No, a dismissed dialog and a timeout all leave it off", async () => {
  for (const answer of ["No", new Error("dismissed")]) {
    const t = setup({ answer });
    await t.start();
    await t.ask();
    await t.tick();
    assert.equal(t.json(`heartbeat/${SID}.json`).enabled, false, String(answer));
    assert.equal(t.calls.set.length, 0);
  }
  const t = setup({ answer: null });
  await t.start();
  await t.ask();
  await t.tick();
  assert.equal(t.json(`heartbeat/${SID}.json`).enabled, false);
  assert.equal(t.json(`heartbeat/${SID}.json`).ask, "timed-out");
});

test("start question: never asked in a background session, with no row, or when claude cannot be run", async () => {
  for (const [opts, ask] of [
    [{ kind: "background" }, "skipped-background"],
    [{ kind: null }, "skipped-unknown"],
    [{ agentsFail: true }, "skipped-unknown"],
  ]) {
    const t = setup(opts);
    await t.start();
    await t.ask();
    await t.tick();
    assert.equal(t.calls.ask.length, 0, JSON.stringify(opts));
    assert.equal(t.json(`heartbeat/${SID}.json`).ask, ask);
    assert.equal(t.json(`heartbeat/${SID}.json`).enabled, false);
  }
});

test("start question: not asked for a session the helper adopted or opted in, nor in mode on or off, nor off a terminal", async () => {
  const adopted = setup();
  adopted.role("worker");
  await adopted.start();
  await adopted.ask();
  assert.equal(adopted.calls.ask.length, 0);
  const optedIn = setup();
  optedIn.optin();
  await optedIn.start();
  await optedIn.ask();
  assert.equal(optedIn.calls.ask.length, 0);
  for (const mode of ["on", "off"]) {
    const t = setup({ mode });
    await t.start();
    await t.ask();
    assert.equal(t.calls.ask.length, 0, mode);
  }
  const headless = setup();
  await headless.start({ isInteractive: false, surface: null, cwd: "/w" });
  await headless.ask();
  assert.equal(headless.calls.ask.length, 0);
});

test("the question comes after the start, not inside it", async () => {
  const t = setup();
  await t.start();
  assert.equal(t.calls.ask.length, 0);
});

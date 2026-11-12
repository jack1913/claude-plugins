// The helper's switch verb (a session's model and effort, through its own mod), the tier check
// that reads a switch, and the next step after a MISMATCH. A scripted `sleep` plays the mod.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import { adoptSession, main, mismatchNext, switchPaste, switchTarget } from "../skills/puppet-master/scripts/puppet.mjs";
import { agent, makeDeps } from "./helpers.mjs";

const NOW = new Date("2026-06-01T00:00:00Z");
const NONCE = "n0nce002";
const REPO = "C:\\Work\\Repo";

const line = (o) => `${JSON.stringify(o)}\n`;
const request = (model, effort) =>
  line({ type: "api-request", querySource: "repl_main_thread", params: { model, output_config: { effort } } });

function modFiles(t) {
  t.modDir = path.join(t.dir, "mod");
  t.deps.env.PUPPET_MOD_DIR = t.modDir;
  t.put = (kind, name, value) => {
    const f = path.join(t.modDir, kind, `${name}.json`);
    fs.mkdirSync(path.dirname(f), { recursive: true });
    fs.writeFileSync(f, typeof value === "string" ? value : JSON.stringify(value));
  };
  t.get = (kind, name) => {
    const f = path.join(t.modDir, kind, `${name}.json`);
    return fs.existsSync(f) ? fs.readFileSync(f, "utf8") : undefined;
  };
  t.beat = (sessionId, extra = {}) =>
    t.put("heartbeat", sessionId, { sessionId, beat: NOW.getTime() - 1000, mode: "ask", enabled: true, source: "optin", role: "worker", override: null, ...extra });
}

// A worker `w1` in the roster, last request Opus at high, whose mod beat just now.
function setup({ role = "worker", state = "done", status = "idle", heartbeat = {}, mod } = {}) {
  const w = agent("w1", 1, { state, status });
  const t = makeDeps({ agents: [w], now: () => NOW });
  t.w = w;
  modFiles(t);
  t.deps.nonce = () => NONCE;
  t.sleeps = 0;
  t.deps.sleep = async () => {
    t.sleeps++;
    if (mod) mod(t);
  };
  t.writeTranscript(w.sessionId, request("claude-opus-5-5", "high"));
  t.writeRegistry({
    workers: { w1: { id: w.id, sessionId: w.sessionId, cwd: "/work/repo", checkout: "/work/repo", kind: "background", role, job: null, jobState: "clean" } },
  });
  if (heartbeat !== null) t.beat(w.sessionId, heartbeat);
  t.ack = (body) => t.put("acks", NONCE, { nonce: NONCE, ...body });
  t.request = () => JSON.parse(t.get("requests", w.sessionId));
  return t;
}

const okSwitch = (t) => {
  const r = t.request();
  t.ack(r.reset ? { ok: true, outcome: "reset", model: null, effort: null, previous: { model: "sonnet", effort: "medium" } } : { ok: true, outcome: "switched", model: r.model, effort: r.effort, previous: null });
};

test("switch over an earlier switch names that switch, not the last request", async () => {
  const t = setup({
    heartbeat: { override: { model: "sonnet", effort: "medium" } },
    mod: (x) => x.ack({ ok: true, outcome: "switched", model: "opus", effort: "high", previous: { model: "sonnet", effort: "medium" } }),
  });
  try {
    assert.equal(await main(["switch", "w1", "--tier", "creative"], t.deps), 0);
    assert.match(t.out[0], /^switched w1 to opus high \(switched before to sonnet medium\), from its next request on/);
  } finally {
    t.cleanup();
  }
});

test("switch --tier writes the tier's model and effort for the mod and prints what changes", async () => {
  const t = setup({ mod: okSwitch });
  try {
    assert.equal(await main(["switch", "w1", "--tier", "mechanical"], t.deps), 0);
    assert.deepEqual(t.request(), { nonce: NONCE, sessionId: t.w.sessionId, requestedAt: NOW.getTime(), action: "switch", model: "sonnet", effort: "medium", role: "worker" });
    assert.deepEqual(t.out, [
      "switched w1 to sonnet medium (last request: claude-opus-5-5 high), from its next request on; its status line names the launch model and the mod's line under the prompt the switch; its own answer names the launch model: check with list --name w1 after its next turn",
    ]);
    assert.equal(t.get("acks", NONCE), undefined);
  } finally {
    t.cleanup();
  }
});

test("switch --model --effort and --reset", async () => {
  const a = setup({ mod: okSwitch });
  try {
    assert.equal(await main(["switch", "w1", "--model", "haiku", "--effort", "low"], a.deps), 0);
    assert.equal(a.request().model, "haiku");
    assert.equal(a.request().effort, "low");
  } finally {
    a.cleanup();
  }
  const b = setup({ mod: okSwitch });
  try {
    assert.equal(await main(["switch", "w1", "--reset"], b.deps), 0);
    assert.equal(b.request().reset, true);
    assert.equal("model" in b.request(), false);
    assert.deepEqual(b.out, ["reset w1: its next request goes out on its launch model and effort"]);
  } finally {
    b.cleanup();
  }
});

test("switch: a wrong combination or value is a usage error and writes nothing", async () => {
  for (const args of [
    [],
    ["--tier", "mechanical", "--model", "opus"],
    ["--model", "opus"],
    ["--effort", "high"],
    ["--model", "gpt-5", "--effort", "high"],
    ["--model", "opus", "--effort", "turbo"],
    ["--reset", "--tier", "creative"],
    ["--tier", "fancy"],
  ]) {
    const t = setup();
    try {
      assert.equal(await main(["switch", "w1", ...args], t.deps), 2, args.join(" "));
      assert.equal(t.get("requests", t.w.sessionId), undefined);
    } finally {
      t.cleanup();
    }
  }
  assert.deepEqual(switchTarget({ model: "claude-opus-5-5[1m]", effort: "xhigh" }), { model: "claude-opus-5-5[1m]", effort: "xhigh" });
  assert.deepEqual(switchTarget({ tier: "creative" }), { model: "opus", effort: "high" });
  assert.equal(switchTarget({ reset: true }), null);
});

test("switch refuses a busy or dialog-parked session, and a missing or off mod, with the paste lines as the fallback", async () => {
  for (const [opts, re] of [
    [{ state: "working", status: "busy" }, /not at a task boundary \(state working\); not switching it/],
    [{ status: "waiting" }, /waiting on a dialog/],
    [{ heartbeat: null }, /no mod heartbeat/],
    [{ heartbeat: { beat: NOW.getTime() - 60000 } }, /heartbeat is stale/],
    [{ heartbeat: { enabled: false, source: null, mode: "off" } }, /the user's veto/],
  ]) {
    const t = setup(opts);
    try {
      assert.equal(await main(["switch", "w1", "--tier", "mechanical"], t.deps), 1);
      const msg = t.err.join("\n");
      assert.match(msg, re);
      if (!opts.state && !opts.status) assert.ok(msg.includes('Fallback: give the user "w1: /model, then s on the Sonnet row"'), msg);
      assert.equal(t.get("requests", t.w.sessionId), undefined);
    } finally {
      t.cleanup();
    }
  }
});

// P-20261112-brainiac-3 (a). A busy session's refusal said only "not switching it"; the user
// found by eye, minutes later, that the session still ran its old model (F-1).
test("switch refusing a busy session says the session is unchanged and to retry once it is idle", async () => {
  const t = setup({ state: "working", status: "busy" });
  try {
    assert.equal(await main(["switch", "w1", "--tier", "mechanical"], t.deps), 1);
    const msg = t.err.join("\n");
    assert.match(msg, /not switching it: it keeps its current model and effort\. Next: run the same switch again once `list --name w1` shows it idle \(its task boundary\)/);
  } finally {
    t.cleanup();
  }
});

test("switch refuses at once a mod loaded before the switch existed (no override field in its heartbeat)", async () => {
  const t = setup();
  try {
    const hb = JSON.parse(t.get("heartbeat", t.w.sessionId));
    delete hb.override;
    t.put("heartbeat", t.w.sessionId, hb);
    assert.equal(await main(["switch", "w1", "--tier", "mechanical"], t.deps), 1);
    assert.match(t.err.join("\n"), /its mod predates the switch .*reopen the window or run \/reload-plugins in it\. Fallback: give the user "w1: \/model/);
    assert.equal(t.sleeps, 0);
    assert.equal(t.get("requests", t.w.sessionId), undefined);
  } finally {
    t.cleanup();
  }
});

test("switch: a refusing ack and a silent mod are each loud", async () => {
  const refused = setup({ mod: (t) => t.ack({ ok: false, outcome: "refused-value", detail: "effort must be one of" }) });
  try {
    assert.equal(await main(["switch", "w1", "--tier", "creative"], refused.deps), 1);
    assert.match(refused.err.join("\n"), /w1 was NOT switched: refused-value \(effort must be one of\)\. Fallback: give the user "w1: \/model, then s on the Opus row"/);
  } finally {
    refused.cleanup();
  }
  const silent = setup();
  try {
    assert.equal(await main(["switch", "w1", "--tier", "creative"], silent.deps), 1);
    assert.match(silent.err.join("\n"), /no answer from the mod in 90 s; the request was withdrawn/);
    assert.equal(silent.get("requests", silent.w.sessionId).trim(), "{}");
  } finally {
    silent.cleanup();
  }
});

test("switch on the master leaves the request for after its turn and does not wait", async () => {
  const t = setup({ role: "master", state: "working", status: "busy", heartbeat: { role: "master" } });
  try {
    assert.equal(await main(["switch", "w1", "--tier", "creative"], t.deps), 0);
    assert.equal(t.sleeps, 0);
    assert.match(t.out[0], /^requested w1's own switch to opus high: its mod writes it once this turn ends/);
    assert.equal(t.request().role, "master");
  } finally {
    t.cleanup();
  }
});

test("list shows the switch in the mod column; the model column stays the last request sent", async () => {
  const t = setup({ heartbeat: { override: { model: "sonnet", effort: "medium" } } });
  try {
    fs.appendFileSync(
      path.join(t.dir, "projects", "x", `${t.w.sessionId}.jsonl`),
      line({ type: "assistant", message: { usage: { input_tokens: 1000 } } }),
    );
    assert.equal(await main(["list"], t.deps), 0);
    assert.match(t.out[0], /model claude-opus-5-5 high .*mod on \(optin\) {2}switched to sonnet medium$/);
  } finally {
    t.cleanup();
  }
});

test("the paste fallback names the picker row for an alias and the id otherwise", () => {
  assert.match(switchPaste("w", { model: "opus", effort: "high" }), /"w: \/model, then s on the Opus row" and "w: \/effort, then s at high"/);
  assert.match(switchPaste("w", { model: "claude-haiku-5-5", effort: "low" }), /s on the claude-haiku-5-5 row/);
});

// --- the tier check after a switch, and pick ---

const interactive = (name, n) => agent(name, n, { kind: "interactive", id: undefined, state: undefined, status: "idle", cwd: REPO });

function repoSetup(agents) {
  const t = makeDeps({
    agents,
    now: () => NOW,
    handler(args, opts, calls) {
      if (calls.at(-1).cmd === "git") return { stdout: `${REPO}\n` };
      return undefined;
    },
  });
  t.deps.platform = "win32";
  modFiles(t);
  return t;
}

test("a tier check reads a switch: assign says ok (switched) from the override, before any turn on it", async () => {
  const t = repoSetup([interactive("u1", 1)]);
  try {
    adoptSession(t.deps, "u1");
    const sid = t.deps.agents[0].sessionId;
    t.writeTranscript(sid, request("claude-opus-5-5", "high"));
    t.beat(sid, { override: { model: "sonnet", effort: "medium" } });
    assert.equal(await main(["assign", "u1", "rename", "--tier", "mechanical"], t.deps), 0);
    assert.deepEqual(t.out, ["assigned u1: rename", "u1 tier mechanical: ok (sonnet medium (switched))"]);
  } finally {
    t.cleanup();
  }
});

test("a MISMATCH where the mod is on says to switch, with no paste line; where it is off, the paste line", async () => {
  const t = repoSetup([interactive("u1", 1)]);
  try {
    adoptSession(t.deps, "u1");
    const sid = t.deps.agents[0].sessionId;
    t.writeTranscript(sid, request("claude-opus-5-5", "high"));
    t.beat(sid);
    assert.equal(await main(["pick", REPO, "--tier", "mechanical"], t.deps), 0);
    assert.equal(t.out.length, 3);
    assert.match(t.out[1], /^MISMATCH u1 tier mechanical /);
    assert.equal(t.out[2], "its mod is on: run `switch u1 --tier mechanical` (session-only; no paste)");
    t.beat(sid, { enabled: false, source: null });
    assert.match(mismatchNext(t.deps, sid, "u1", "mechanical"), /^give the user "u1: \/model, then s on the Sonnet row"/);
  } finally {
    t.cleanup();
  }
});

test("pick --tier takes the user's opened window whose mod can switch it before a matching background worker", async () => {
  const bg = agent("b1", 2, { kind: "background", cwd: REPO, state: "done", status: "idle" });
  const t = repoSetup([interactive("u1", 1), bg]);
  try {
    adoptSession(t.deps, "u1");
    adoptSession(t.deps, "b1");
    const [u1, b1] = t.deps.agents.map((a) => a.sessionId);
    t.writeTranscript(u1, request("claude-opus-5-5", "high"));
    t.writeTranscript(b1, request("claude-sonnet-5-5", "medium"));
    assert.equal(await main(["pick", REPO, "--tier", "mechanical"], t.deps), 0);
    assert.equal(t.out[0], "b1");
    t.out.length = 0;
    t.beat(u1);
    assert.equal(await main(["pick", REPO, "--tier", "mechanical"], t.deps), 0);
    assert.equal(t.out[0], "u1");
    assert.match(t.out[2], /run `switch u1 --tier mechanical`/);
  } finally {
    t.cleanup();
  }
});

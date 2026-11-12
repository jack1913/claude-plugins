import { test } from "node:test";
import assert from "node:assert/strict";

import { main } from "../skills/puppet-master/scripts/puppet.mjs";
import { agent, makeDeps } from "./helpers.mjs";

function closeSetup({ live = true, rm, stop, pid, sleeps } = {}) {
  const w = agent("w1", 1, pid === null ? { pid: undefined } : {});
  const t = makeDeps({
    agents: live ? [w] : [],
    handler(args) {
      if (args[0] === "stop") return stop ? stop(args) : { stdout: `stopped ${w.id}\n` };
      if (args[0] === "rm") return rm ? rm(args) : { stdout: `removed ${w.id}\n` };
      return undefined;
    },
  });
  t.w = w;
  if (sleeps) t.deps.sleep = async (ms) => void sleeps.push(ms);
  t.writeRegistry({
    workers: { w1: { id: w.id, sessionId: w.sessionId, cwd: "/work/repo", checkout: "/work/repo" } },
  });
  return t;
}

const verbs = (t) => t.calls.filter((c) => c.args[0] !== "agents").map((c) => c.args);

test("stops a live worker then removes it", async () => {
  const t = closeSetup();
  try {
    assert.equal(await main(["close", "w1"], t.deps), 0);
    assert.deepEqual(verbs(t), [["stop", t.w.id], ["rm", t.w.id]]);
    assert.deepEqual(t.readRegistry().workers, {});
    assert.deepEqual(t.out, [`closed w1 (resume: cd "/work/repo" && claude --resume ${t.w.sessionId})`]);
  } finally {
    t.cleanup();
  }
});

test("an already-exited worker is only removed", async () => {
  const t = closeSetup({ live: false });
  try {
    assert.equal(await main(["close", "w1"], t.deps), 0);
    assert.deepEqual(verbs(t), [["rm", t.w.id]]);
    assert.deepEqual(t.readRegistry().workers, {});
  } finally {
    t.cleanup();
  }
});

test("rm failure keeps the record and passes no discard flag", async () => {
  const t = closeSetup({
    rm: () => ({ code: 1, stderr: "worktree has unpushed commits; pass --discard-unpushed to remove" }),
  });
  try {
    assert.equal(await main(["close", "w1"], t.deps), 1);
    assert.match(t.err.join("\n"), /unpushed commits/);
    assert.match(t.err.join("\n"), /w1 is stopped but NOT removed/);
    assert.ok(t.err.join("\n").includes(`cd "/work/repo" && claude --resume ${t.w.sessionId}`));
    assert.ok(t.readRegistry().workers.w1);
    for (const c of t.calls) {
      assert.ok(!c.args.includes("--discard-unpushed"));
      assert.ok(!c.args.includes("--force-remove-worktree"));
    }
    assert.equal(verbs(t).filter((a) => a[0] === "rm").length, 1);
  } finally {
    t.cleanup();
  }
});

test("stop failure aborts before rm", async () => {
  const t = closeSetup({ stop: () => ({ code: 1, stderr: "cannot stop" }) });
  try {
    assert.equal(await main(["close", "w1"], t.deps), 1);
    assert.deepEqual(verbs(t), [["stop", t.w.id]]);
    assert.ok(t.readRegistry().workers.w1);
  } finally {
    t.cleanup();
  }
});

// P-20261110-3. A background row with no `pid` is a process that is gone (observed 2026-11-12:
// every running session carries a pid; the two blocked rows without one did not).
test("a dead worker (listed, background, no pid) is removed with rm alone, no stop", async () => {
  const t = closeSetup({ pid: null });
  try {
    assert.equal(await main(["close", "w1"], t.deps), 0);
    assert.deepEqual(verbs(t), [["rm", t.w.id]]);
    assert.deepEqual(t.readRegistry().workers, {});
  } finally {
    t.cleanup();
  }
});

test("stop failing with 'may be restarting' is retried at 2 s, 4 s and 8 s, then rm runs", async () => {
  const sleeps = [];
  let n = 0;
  const t = closeSetup({
    sleeps,
    stop: () => (++n <= 2 ? { code: 1, stderr: "background service may be restarting" } : { stdout: "stopped\n" }),
  });
  try {
    assert.equal(await main(["close", "w1"], t.deps), 0);
    assert.deepEqual(sleeps, [2000, 4000]);
    assert.deepEqual(verbs(t).map((a) => a[0]), ["stop", "stop", "stop", "rm"]);
    assert.deepEqual(t.readRegistry().workers, {});
  } finally {
    t.cleanup();
  }
});

test("stop failing four times with 'may be restarting' exits 1 with one manual step and keeps the record", async () => {
  const sleeps = [];
  const t = closeSetup({ sleeps, stop: () => ({ code: 1, stderr: "background service may be restarting" }) });
  try {
    assert.equal(await main(["close", "w1"], t.deps), 1);
    assert.deepEqual(sleeps, [2000, 4000, 8000]);
    assert.equal(verbs(t).length, 4);
    assert.match(t.err.join("\n"), /w1 could not be stopped: the background service may be restarting; run close w1 again in a minute \(id [0-9a-z]+; resume: /);
    assert.doesNotMatch(t.err.join("\n"), /claude rm/);
    assert.ok(t.readRegistry().workers.w1);
  } finally {
    t.cleanup();
  }
});

// brainiac P-20261112-6 (F-8): `claude rm` failed the same way three times in a minute on two dead
// rows. The rows went at once later, with a background session running (a data point, not proof).
test("rm failing with 'may be restarting' is retried at 2 s, 4 s and 8 s, then the worker is closed", async () => {
  const sleeps = [];
  let n = 0;
  const t = closeSetup({
    sleeps,
    rm: () => (++n <= 2 ? { code: 1, stderr: "couldn't remove x — the background service may be restarting. Try again in a moment." } : { stdout: "removed\n" }),
  });
  try {
    assert.equal(await main(["close", "w1"], t.deps), 0);
    assert.deepEqual(sleeps, [2000, 4000]);
    assert.deepEqual(verbs(t).map((a) => a[0]), ["stop", "rm", "rm", "rm"]);
    assert.deepEqual(t.readRegistry().workers, {});
  } finally {
    t.cleanup();
  }
});

test("rm failing four times with 'may be restarting' keeps the record and says when to run close again", async () => {
  const sleeps = [];
  const t = closeSetup({
    sleeps,
    pid: null,
    rm: () => ({ code: 1, stderr: "couldn't remove x — the background service may be restarting. Try again in a moment." }),
  });
  try {
    assert.equal(await main(["close", "w1"], t.deps), 1);
    assert.deepEqual(sleeps, [2000, 4000, 8000]);
    assert.deepEqual(verbs(t).map((a) => a[0]), ["rm", "rm", "rm", "rm"]);
    const msg = t.err.join("\n");
    assert.match(msg, /w1 is stopped but NOT removed \(id [0-9a-z]+; resume: cd "\/work\/repo" && claude --resume [^)]+\): claude rm failed/);
    assert.match(msg, /may be restarting[^\n]*; run close w1 again in a minute, or once a background worker is running$/);
    assert.ok(t.readRegistry().workers.w1);
  } finally {
    t.cleanup();
  }
});

test("any other stop error is not retried", async () => {
  const sleeps = [];
  const t = closeSetup({ sleeps, stop: () => ({ code: 1, stderr: "cannot stop" }) });
  try {
    assert.equal(await main(["close", "w1"], t.deps), 1);
    assert.deepEqual(sleeps, []);
    assert.equal(verbs(t).length, 1);
  } finally {
    t.cleanup();
  }
});

test("an interactive session is never closed", async () => {
  const t = closeSetup({ live: false });
  try {
    t.deps.agents = [{ ...agent("mine", 2), kind: "interactive", status: "idle" }];
    assert.equal(await main(["close", "mine"], t.deps), 1);
    assert.match(t.err.join("\n"), /not a background worker/);
    assert.deepEqual(verbs(t), []);
  } finally {
    t.cleanup();
  }
});

test("an unknown worker is an error", async () => {
  const t = closeSetup({ live: false });
  try {
    assert.equal(await main(["close", "nope"], t.deps), 1);
    assert.deepEqual(verbs(t), []);
  } finally {
    t.cleanup();
  }
});

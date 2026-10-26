import { test } from "node:test";
import assert from "node:assert/strict";

import { main } from "../../plugins/batbelt/skills/puppet-master/scripts/puppet.mjs";
import { agent, makeDeps } from "./helpers.mjs";

function closeSetup({ live = true, rm, stop } = {}) {
  const w = agent("w1", 1);
  const t = makeDeps({
    agents: live ? [w] : [],
    handler(args) {
      if (args[0] === "stop") return stop ? stop(args) : { stdout: `stopped ${w.id}\n` };
      if (args[0] === "rm") return rm ? rm(args) : { stdout: `removed ${w.id}\n` };
      return undefined;
    },
  });
  t.w = w;
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

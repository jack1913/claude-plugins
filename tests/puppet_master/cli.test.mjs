import { test } from "node:test";
import assert from "node:assert/strict";

import { main } from "../../plugins/batbelt/skills/puppet-master/scripts/puppet.mjs";
import { agent, fixture, makeDeps } from "./helpers.mjs";

function setup(agents = [agent("w1", 1)], opts = {}) {
  const t = makeDeps({ agents, ...opts });
  for (const a of agents) t.writeTranscript(a.sessionId, fixture("transcript-usage-sum.jsonl"));
  return t;
}

test("measure with --window reports the percent and the flag source", async () => {
  const t = setup();
  try {
    assert.equal(await main(["measure", "w1", "--window", "1000000"], t.deps), 0);
    assert.equal(t.out.length, 1);
    assert.match(t.out[0], /^w1 {2}85545 {2}8\.6% {2}done {2}\(window 1000000 from flag\)$/);
  } finally {
    t.cleanup();
  }
});

test("measure uses the recorded window", async () => {
  const t = setup();
  try {
    const a = t.deps.agents[0];
    t.writeRegistry({
      workers: { w1: { id: a.id, sessionId: a.sessionId, cwd: a.cwd, checkout: a.cwd, window: 1000000 } },
    });
    assert.equal(await main(["measure", "w1"], t.deps), 0);
    assert.match(t.out[0], /from recorded/);
  } finally {
    t.cleanup();
  }
});

test("measure --json prints one JSON object", async () => {
  const t = setup();
  try {
    assert.equal(await main(["measure", "w1", "--window", "1000000", "--json"], t.deps), 0);
    const r = JSON.parse(t.out.join("\n"));
    assert.equal(r.tokens, 85545);
    assert.equal(r.percent, 8.6);
    assert.equal(r.windowSource, "flag");
    assert.equal(r.tokenSource, "usage");
  } finally {
    t.cleanup();
  }
});

test("measure without any window fails loudly", async () => {
  const t = setup();
  try {
    assert.equal(await main(["measure", "w1"], t.deps), 1);
    assert.match(t.err.join("\n"), /^puppet: no context window/);
  } finally {
    t.cleanup();
  }
});

test("list measures each worker and fails if a row fails", async () => {
  const t = makeDeps({ agents: [agent("w1", 1), agent("w2", 2)] });
  try {
    t.writeTranscript(t.deps.agents[0].sessionId, fixture("transcript-usage-sum.jsonl"));
    assert.equal(await main(["list", "--window", "1000000"], t.deps), 1);
    const rows = t.out.join("\n");
    assert.match(rows, /^w1 {2}85545 {2}8\.6%/m);
    assert.match(rows, /^w2 {2}\? {2}\(no transcript\)$/m);
  } finally {
    t.cleanup();
  }
});

test("list skips interactive sessions and reports gone records", async () => {
  const live = agent("w1", 1);
  const t = setup([live, { ...agent("me", 2), kind: "interactive", state: undefined, status: "idle" }]);
  try {
    t.writeRegistry({
      workers: {
        old: { id: "bbbbbbbb", sessionId: "gone-sid", cwd: "/work/repo", checkout: "/work/repo" },
        w1: { id: live.id, sessionId: live.sessionId, cwd: live.cwd, checkout: live.cwd },
      },
    });
    assert.equal(await main(["list", "--window", "1000000"], t.deps), 0);
    const rows = t.out.join("\n");
    assert.doesNotMatch(rows, /^me /m);
    assert.match(rows, /^old {2}gone {2}\(resume: cd "\/work\/repo" && claude --bg --resume gone-sid\)$/m);
    assert.deepEqual(Object.keys(t.readRegistry().workers), ["w1"]);
  } finally {
    t.cleanup();
  }
});

test("an unknown subcommand is a usage error", async () => {
  const t = makeDeps();
  try {
    assert.equal(await main(["frobnicate"], t.deps), 2);
    assert.match(t.err.join("\n"), /usage:/);
  } finally {
    t.cleanup();
  }
});

test("no arguments is a usage error", async () => {
  const t = makeDeps();
  try {
    assert.equal(await main([], t.deps), 2);
    assert.match(t.err.join("\n"), /usage:/);
  } finally {
    t.cleanup();
  }
});

test("an unknown flag is a usage error", async () => {
  const t = setup();
  try {
    assert.equal(await main(["measure", "w1", "--bogus"], t.deps), 2);
  } finally {
    t.cleanup();
  }
});

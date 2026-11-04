// The compaction point (U-1), the model and effort columns (U-10), one row by name and
// closed sessions that stay addressable (U-9).
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  main,
  measureLine,
  measureWorker,
  resolveCompactAt,
  transcriptFacts,
} from "../skills/puppet-master/scripts/puppet.mjs";
import { agent, makeDeps } from "./helpers.mjs";

const line = (o) => `${JSON.stringify(o)}\n`;
const turn = (tokens) => line({ type: "assistant", message: { usage: { input_tokens: tokens } } });
const request = (model, effort, querySource = "repl_main_thread") =>
  line({ type: "api-request", querySource, params: { model, output_config: { effort } } });
const autoCompact = (pre) =>
  line({ type: "system", subtype: "compact_boundary", compactMetadata: { trigger: "auto", preTokens: pre } });

test("facts: the smallest auto compaction, and the last main-thread model and effort", () => {
  const text =
    request("claude-sonnet-5-5", "low") +
    turn(300000) +
    autoCompact(305000) +
    turn(20000) +
    autoCompact(241000) +
    line({ type: "system", subtype: "compact_boundary", compactMetadata: { trigger: "manual", preTokens: 100000, postTokens: 9000 } }) +
    request("claude-opus-5-5", "high") +
    request("claude-haiku-5-5", "low", "compact") +
    line({ type: "api-request", isSidechain: true, querySource: "repl_main_thread", params: { model: "x", output_config: { effort: "max" } } }) +
    turn(50000);
  const f = transcriptFacts(text);
  assert.equal(f.tokens, 50000);
  assert.equal(f.autoCompactAt, 241000);
  assert.equal(f.model, "claude-opus-5-5");
  assert.equal(f.effort, "high");
});

test("facts: nothing recorded gives nulls, not guesses", () => {
  const f = transcriptFacts(turn(10));
  assert.deepEqual([f.autoCompactAt, f.model, f.effort], [null, null, null]);
});

test("compaction point: flag, then env, then observed; never invented", () => {
  assert.deepEqual(resolveCompactAt({ flag: "200000", env: "300000", observed: 250000 }), { compactAt: 200000, source: "flag" });
  assert.deepEqual(resolveCompactAt({ env: "300000", observed: 250000 }), { compactAt: 300000, source: "env" });
  assert.deepEqual(resolveCompactAt({ observed: 250000 }), { compactAt: 250000, source: "observed" });
  assert.equal(resolveCompactAt({}), null);
  assert.throws(() => resolveCompactAt({ flag: "lots" }), /--compact-at must be a positive integer/);
});

test("measure with no window but a seen compaction prints instead of failing, and warns near it", async () => {
  const t = makeDeps({ agents: [agent("w1", 1)] });
  try {
    t.writeTranscript(t.deps.agents[0].sessionId, turn(400000) + autoCompact(250000) + turn(210000));
    assert.equal(await main(["measure", "w1"], t.deps), 0);
    assert.equal(t.out[0], "w1  210000  ?%  done  (window unknown)  84% of compaction point 250000 (observed)  WARN near compaction");
    assert.equal(t.readRegistry().observedCompactAt, 250000);
  } finally {
    t.cleanup();
  }
});

test("a session with its own auto compaction is measured against that one, not the group's lowest", async () => {
  // 2026-11-03: the analyst compacted at 208192, 9d at 354186, 4e at 230030; measure used 208192 for all.
  const t = makeDeps({ agents: [agent("w1", 1), agent("w2", 2)] });
  try {
    t.writeTranscript(t.deps.agents[0].sessionId, turn(300000) + autoCompact(220000) + turn(30000));
    t.writeTranscript(t.deps.agents[1].sessionId, turn(300000) + autoCompact(350000) + turn(60000));
    measureWorker(t.deps, "w1");
    const m = measureWorker(t.deps, "w2", { window: "1000000" });
    assert.equal(m.compactAt, 350000);
    assert.equal(m.compactSource, "observed");
    assert.equal(m.percent, 6);
    assert.equal(m.compactPercent, 17.1);
    assert.equal(m.warn, false);
    // the group's lowest is still kept, for a session with no compaction of its own
    assert.equal(t.readRegistry().observedCompactAt, 220000);
  } finally {
    t.cleanup();
  }
});

test("a session with no compaction of its own falls back to the group's lowest, and says so", async () => {
  const t = makeDeps({ agents: [agent("w1", 1), agent("w2", 2)] });
  try {
    t.writeTranscript(t.deps.agents[0].sessionId, turn(300000) + autoCompact(220000) + turn(30000));
    t.writeTranscript(t.deps.agents[1].sessionId, turn(100000));
    measureWorker(t.deps, "w1");
    const m = measureWorker(t.deps, "w2", { window: "1000000" });
    assert.equal(m.compactAt, 220000);
    assert.equal(m.compactSource, "group");
    assert.equal(
      measureLine(m),
      "w2  100000  10%  done  (window 1000000 from flag)  45.5% of compaction point 220000 (group)",
    );
  } finally {
    t.cleanup();
  }
});

test("a session's own point is kept on its roster record and survives a clear, which empties its transcript", async () => {
  const t = makeDeps({ agents: [agent("w1", 1)] });
  try {
    t.writeRegistry({ workers: { w1: { id: t.deps.agents[0].id, sessionId: t.deps.agents[0].sessionId, cwd: "/w", checkout: "/w" } } });
    t.writeTranscript(t.deps.agents[0].sessionId, turn(300000) + autoCompact(354000) + turn(30000));
    assert.equal(await main(["list", "--window", "1000000"], t.deps), 0);
    assert.equal(t.readRegistry().workers.w1.compactAt, 354000);
    // the session is cleared: a new session id, a transcript with no compaction in it
    const fresh = { ...t.deps.agents[0], sessionId: "eeeeeeee-0000-4000-8000-000000000000" };
    t.deps.agents = [fresh];
    t.writeRegistry({ workers: { w1: { ...t.readRegistry().workers.w1, sessionId: fresh.sessionId } }, observedCompactAt: 208192 });
    t.writeTranscript(fresh.sessionId, turn(1000));
    const m = measureWorker(t.deps, "w1", { window: "1000000" });
    assert.equal(m.compactAt, 354000);
    assert.equal(m.compactSource, "recorded");
  } finally {
    t.cleanup();
  }
});

test("--compact-at and PUPPET_COMPACT_AT still win over every observed point", async () => {
  const t = makeDeps({ agents: [agent("w1", 1)], env: { PUPPET_COMPACT_AT: "200000" } });
  try {
    t.writeTranscript(t.deps.agents[0].sessionId, turn(300000) + autoCompact(354000) + turn(100000));
    const m = measureWorker(t.deps, "w1");
    assert.equal(m.compactAt, 200000);
    assert.equal(m.compactSource, "env");
    assert.equal(measureWorker(t.deps, "w1", { compactAt: "250000" }).compactSource, "flag");
  } finally {
    t.cleanup();
  }
});

test("with neither a window nor a compaction point the error stands", async () => {
  const t = makeDeps({ agents: [agent("w1", 1)] });
  try {
    t.writeTranscript(t.deps.agents[0].sessionId, turn(1000));
    assert.equal(await main(["measure", "w1"], t.deps), 1);
    assert.match(t.err[0], /^puppet: no context window/);
  } finally {
    t.cleanup();
  }
});

test("PUPPET_COMPACT_AT sets the point without a window", async () => {
  const t = makeDeps({ agents: [agent("w1", 1)], env: { PUPPET_COMPACT_AT: "200000" } });
  try {
    t.writeTranscript(t.deps.agents[0].sessionId, turn(100000));
    assert.equal(await main(["measure", "w1"], t.deps), 0);
    assert.equal(t.out[0], "w1  100000  ?%  done  (window unknown)  50% of compaction point 200000 (env)");
  } finally {
    t.cleanup();
  }
});

test("list shows model and effort, and --name prints one row", async () => {
  const t = makeDeps({ agents: [agent("w1", 1), agent("w2", 2)] });
  try {
    t.writeTranscript(t.deps.agents[0].sessionId, request("claude-opus-5-5", "max") + turn(1000));
    assert.equal(await main(["list", "--window", "100000", "--name", "w1"], t.deps), 0);
    assert.deepEqual(t.out, ["w1  1000  1%  done  (window 100000 from flag)  model claude-opus-5-5 max"]);
    t.out.length = 0;
    assert.equal(await main(["list", "--name", "w2", "--json"], t.deps), 0);
    assert.equal(JSON.parse(t.out[0]).state, "fresh");
    assert.equal(await main(["list", "--name", "nobody"], t.deps), 1);
    assert.match(t.err.at(-1), /no session named or numbered "nobody"/);
  } finally {
    t.cleanup();
  }
});

test("a closed session stays addressable: lookups say it is closed and how to resume it", async () => {
  const t = makeDeps({ agents: [agent("w1", 1)] });
  try {
    t.writeRegistry({ workers: {} });
    assert.equal(await main(["close", "w1"], t.deps), 0);
    t.deps.agents = [];
    assert.equal(await main(["measure", "w1"], t.deps), 1);
    assert.match(t.err.at(-1), /^puppet: w1 is closed \(resume: .*claude --resume aaaaaaa1-0000-4000-8000-000000000000\)$/);
    assert.equal(await main(["close", "w1"], t.deps), 1);
    assert.match(t.err.at(-1), /w1 is closed/);
    assert.equal(await main(["list", "--name", "w1"], t.deps), 1);
    assert.match(t.err.at(-1), /w1 is closed/);
  } finally {
    t.cleanup();
  }
});

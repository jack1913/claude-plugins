// Context as tokens and % of the window only (the owner's rule, carcare P-20261104-5), the
// model and effort columns (U-10), one row by name and closed sessions that stay addressable (U-9).
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DEFAULT_WINDOW,
  main,
  measureLine,
  measureWorker,
  resolveWindow,
  transcriptFacts,
} from "../skills/puppet-master/scripts/puppet.mjs";
import { agent, makeDeps } from "./helpers.mjs";

const line = (o) => `${JSON.stringify(o)}\n`;
const turn = (tokens) => line({ type: "assistant", message: { usage: { input_tokens: tokens } } });
const request = (model, effort, querySource = "repl_main_thread") =>
  line({ type: "api-request", querySource, params: { model, output_config: { effort } } });
const autoCompact = (pre) =>
  line({ type: "system", subtype: "compact_boundary", compactMetadata: { trigger: "auto", preTokens: pre } });

test("facts: the last main-thread model and effort", () => {
  const text =
    request("claude-sonnet-5-5", "low") +
    turn(300000) +
    autoCompact(305000) +
    turn(20000) +
    line({ type: "system", subtype: "compact_boundary", compactMetadata: { trigger: "manual", preTokens: 100000, postTokens: 9000 } }) +
    request("claude-opus-5-5", "high") +
    request("claude-haiku-5-5", "low", "compact") +
    line({ type: "api-request", isSidechain: true, querySource: "repl_main_thread", params: { model: "x", output_config: { effort: "max" } } }) +
    turn(50000);
  const f = transcriptFacts(text);
  assert.equal(f.tokens, 50000);
  assert.equal(f.model, "claude-opus-5-5");
  assert.equal(f.effort, "high");
});

test("facts: nothing recorded gives nulls, not guesses", () => {
  const f = transcriptFacts(turn(10));
  assert.deepEqual([f.model, f.effort], [null, null]);
});

test("the window: flag, then recorded, then PUPPET_CONTEXT_WINDOW, then 1M", () => {
  assert.equal(DEFAULT_WINDOW, 1000000);
  assert.deepEqual(resolveWindow({ flag: "200000", recorded: 300000, env: "400000" }), { window: 200000, source: "flag" });
  assert.deepEqual(resolveWindow({ recorded: 300000, env: "400000" }), { window: 300000, source: "recorded" });
  assert.deepEqual(resolveWindow({ env: "400000" }), { window: 400000, source: "env" });
  assert.deepEqual(resolveWindow({}), { window: 1000000, source: "default" });
  assert.throws(() => resolveWindow({ flag: "lots" }), /--window must be a positive integer/);
});

test("measure gives tokens and % of the window only: no compaction-point share and no WARN, whatever compacted before (owner rule, 2026-11-06)", async () => {
  const t = makeDeps({ agents: [agent("w1", 1)], env: { PUPPET_COMPACT_AT: "200000" } });
  try {
    t.writeTranscript(t.deps.agents[0].sessionId, turn(400000) + autoCompact(250000) + turn(210000));
    assert.equal(await main(["measure", "w1"], t.deps), 0);
    assert.equal(t.out[0], "w1  210000  21%  done  (window 1000000 from default)");
    const m = measureWorker(t.deps, "w1");
    for (const k of ["compactAt", "compactSource", "compactPercent", "warn", "autoCompactAt"]) assert.ok(!(k in m), `measure still reports ${k}`);
    // nothing about compactions is kept: measure writes no roster at all
    assert.throws(() => t.readRegistry(), /ENOENT/);
    assert.equal(measureLine({ ...m, percent: 21 }), "w1  210000  21%  done  (window 1000000 from default)");
  } finally {
    t.cleanup();
  }
});

test("--compact-at is gone: a usage error", async () => {
  const t = makeDeps({ agents: [agent("w1", 1)] });
  try {
    t.writeTranscript(t.deps.agents[0].sessionId, turn(1000));
    assert.equal(await main(["measure", "w1", "--compact-at", "200000"], t.deps), 2);
    assert.match(t.err[0], /unknown flag --compact-at/);
  } finally {
    t.cleanup();
  }
});

test("list --json rows carry no compaction-point fields", async () => {
  const t = makeDeps({ agents: [agent("w1", 1)] });
  try {
    t.writeTranscript(t.deps.agents[0].sessionId, turn(300000) + autoCompact(220000) + turn(30000));
    assert.equal(await main(["list", "--json"], t.deps), 0);
    const row = JSON.parse(t.out[0]);
    assert.equal(row.percent, 3);
    assert.equal(row.window, 1000000);
    for (const k of ["compactAt", "compactPercent", "warn"]) assert.ok(!(k in row), `list still reports ${k}`);
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

test("list --name finds a live window nobody adopted, and a miss names the live sessions (P-20261109-9)", async () => {
  const t = makeDeps({ agents: [agent("w1", 1), agent("u1", 2, { kind: "interactive" })] });
  try {
    t.writeTranscript(t.deps.agents[1].sessionId, request("claude-opus-5-5", "high") + turn(5000));
    assert.equal(await main(["list", "--name", "u1"], t.deps), 0);
    assert.equal(t.out.length, 1);
    assert.match(t.out[0], /^u1  5000  0\.5%  done  .*model claude-opus-5-5 high/);
    // by id too, and --json carries the row
    t.out.length = 0;
    assert.equal(await main(["list", "--name", t.deps.agents[1].id, "--json"], t.deps), 0);
    assert.equal(JSON.parse(t.out[0]).name, "u1");
    // a miss names the live sessions it saw, here and in the other commands
    assert.equal(await main(["list", "--name", "nobody"], t.deps), 1);
    assert.match(t.err.at(-1), /no session named or numbered "nobody"; live sessions: w1, u1$/);
    assert.equal(await main(["measure", "nobody"], t.deps), 1);
    assert.match(t.err.at(-1), /no session named or numbered "nobody"; live sessions: w1, u1$/);
  } finally {
    t.cleanup();
  }
});

test("a miss with no live session names none", async () => {
  const t = makeDeps({ agents: [] });
  try {
    assert.equal(await main(["list", "--name", "nobody"], t.deps), 1);
    assert.match(t.err.at(-1), /no session named or numbered "nobody"$/);
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

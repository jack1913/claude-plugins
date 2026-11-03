// Dispatch: reuse on the record (U-2), write scopes in one checkout (U-3), tiers by model
// and effort (U-10), and the master's own roster record (U-1).
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import {
  adoptSession,
  assignJob,
  collision,
  finishJob,
  main,
  parseScope,
  pickSession,
  reopenJob,
  spawnWorker,
  tierMatch,
} from "../skills/puppet-master/scripts/puppet.mjs";
import { agent, makeDeps } from "./helpers.mjs";

const REPO = "C:\\Work\\Repo";
const interactive = (name, n, cwd = REPO) =>
  agent(name, n, { kind: "interactive", id: undefined, state: undefined, status: "idle", cwd });

const line = (o) => `${JSON.stringify(o)}\n`;
const turn = (tokens) => line({ type: "assistant", message: { usage: { input_tokens: tokens } } });
const request = (model, effort) =>
  line({ type: "api-request", querySource: "repl_main_thread", params: { model, output_config: { effort } } });

function setup(agents, env = {}) {
  const t = makeDeps({
    agents,
    env,
    handler(args, opts, calls) {
      const call = calls.at(-1);
      if (call.cmd === "git") {
        const m = /^([A-Za-z]:\\Work\\[^\\]+)/.exec(args[1]);
        return { stdout: `${m ? m[1] : args[1]}\n` };
      }
      if (args[0] === "--bg") {
        const n = String(t.deps.agents.length + 1);
        const started = agent(args[2], Number(n), { cwd: opts.cwd });
        t.deps.agents.push(started);
        return { stdout: `backgrounded · ${started.id} · ${args[2]}\n` };
      }
      return undefined;
    },
  });
  t.deps.platform = "win32";
  return t;
}

// --- U-2 reuse ---

test("a finished session takes the next job only with --reuse, and the record keeps both jobs", () => {
  const t = setup([interactive("u1", 1)], { PUPPET_CONTEXT_WINDOW: "200000" });
  try {
    adoptSession(t.deps, "u1");
    assignJob(t.deps, "u1", "job one");
    finishJob(t.deps, "u1");
    assert.throws(() => assignJob(t.deps, "u1", "job two"), /one job per context.*pass --reuse/);
    t.writeTranscript(t.deps.agents[0].sessionId, turn(20000));
    const rec = assignJob(t.deps, "u1", "job two", { reuse: true });
    assert.equal(rec.jobState, "active");
    assert.deepEqual(rec.jobs.map((j) => [j.label, Boolean(j.endedAt)]), [["job one", true], ["job two", false]]);
  } finally {
    t.cleanup();
  }
});

test("--reuse refuses an active job, the analyst, a large context and an unmeasurable one", () => {
  const t = setup([interactive("u1", 1), interactive("u2", 2, "C:\\Work\\Other")]);
  try {
    adoptSession(t.deps, "u1");
    adoptSession(t.deps, "u2", { role: "analyst" });
    assert.throws(() => assignJob(t.deps, "u2", "x", { reuse: true }), /the analyst takes no jobs/);
    assignJob(t.deps, "u1", "one");
    assert.throws(() => assignJob(t.deps, "u1", "two", { reuse: true }), /already holds "one"/);
    finishJob(t.deps, "u1");
    t.writeTranscript(t.deps.agents[0].sessionId, turn(80000));
    assert.throws(() => assignJob(t.deps, "u1", "two", { reuse: true }), /cannot measure u1 for --reuse: no context window/);
    t.deps.env.PUPPET_CONTEXT_WINDOW = "200000";
    assert.throws(() => assignJob(t.deps, "u1", "two", { reuse: true }), /u1 is at 40% of its window .*--reuse needs under 30%.*\/clear/);
  } finally {
    t.cleanup();
  }
});

test("--reuse measures the window, not the compaction point, and a refusal prints both shares", () => {
  const t = setup([interactive("u1", 1), interactive("u2", 2, "C:\\Work\\Other")], {
    PUPPET_CONTEXT_WINDOW: "1000000",
    PUPPET_COMPACT_AT: "216000",
  });
  try {
    adoptSession(t.deps, "u1");
    assignJob(t.deps, "u1", "one");
    finishJob(t.deps, "u1");
    // 190000 tokens: 19% of the window the status line shows, 88% of the compaction point.
    t.writeTranscript(t.deps.agents[0].sessionId, turn(190000));
    assert.equal(assignJob(t.deps, "u1", "two", { reuse: true }).jobState, "active");
    adoptSession(t.deps, "u2");
    assignJob(t.deps, "u2", "one");
    finishJob(t.deps, "u2");
    t.writeTranscript(t.deps.agents[1].sessionId, turn(400000));
    assert.throws(
      () => assignJob(t.deps, "u2", "two", { reuse: true }),
      /u2 is at 40% of its window \(185\.2% of compaction point 216000\)/,
    );
  } finally {
    t.cleanup();
  }
});

// --- P-5 extend and reopen ---

test("--extend appends to an active job: keeps its start, merges label and scope", () => {
  const t = setup([interactive("u1", 1)]);
  try {
    adoptSession(t.deps, "u1");
    const first = assignJob(t.deps, "u1", "docs pass", { scope: "docs", noGit: true });
    const rec = assignJob(t.deps, "u1", "fix links", { extend: true, scope: "site", noGit: true });
    assert.equal(rec.jobState, "active");
    assert.equal(rec.jobStartedAt, first.jobStartedAt);
    assert.equal(rec.job, "docs pass; fix links");
    assert.deepEqual(rec.scope, ["docs", "site"]);
    assert.equal(rec.git, false);
    assert.equal(rec.jobs.length, 1);
    assert.equal(rec.jobs[0].label, "docs pass; fix links");
  } finally {
    t.cleanup();
  }
});

test("--extend widens to the whole checkout when either side has no scope, and git when either runs it", () => {
  const t = setup([interactive("u1", 1)]);
  try {
    adoptSession(t.deps, "u1");
    assignJob(t.deps, "u1", "docs pass", { scope: "docs", noGit: true });
    const rec = assignJob(t.deps, "u1", "and commit", { extend: true });
    assert.equal(rec.scope, undefined);
    assert.equal(rec.git, true);
  } finally {
    t.cleanup();
  }
});

test("--extend refuses a job that is not active, and a merged scope that overlaps another job", () => {
  const t = setup([interactive("u1", 1), interactive("u2", 2)]);
  try {
    adoptSession(t.deps, "u1");
    adoptSession(t.deps, "u2");
    assert.throws(() => assignJob(t.deps, "u1", "x", { extend: true }), /--extend needs an active job.*u1/);
    assignJob(t.deps, "u1", "docs", { scope: "docs", noGit: true });
    assignJob(t.deps, "u2", "code", { scope: "src" });
    assert.throws(
      () => assignJob(t.deps, "u1", "also code", { extend: true, scope: "src/lib", noGit: true }),
      /u2 is already editing .*write scopes overlap/,
    );
    assert.equal(assignJob(t.deps, "u1", "site", { extend: true, scope: "site", noGit: true }).job, "docs; site");
    assert.throws(() => assignJob(t.deps, "u1", "x", { extend: true, reuse: true }), /--extend and --reuse/);
  } finally {
    t.cleanup();
  }
});

test("reopen undoes a finish, and refuses a job that is not done", () => {
  const t = setup([interactive("u1", 1)]);
  try {
    adoptSession(t.deps, "u1");
    assert.throws(() => reopenJob(t.deps, "u1"), /u1 has no finished job to reopen/);
    const before = assignJob(t.deps, "u1", "one", { scope: "docs", noGit: true });
    finishJob(t.deps, "u1");
    const rec = reopenJob(t.deps, "u1");
    assert.equal(rec.jobState, "active");
    assert.equal(rec.job, "one");
    assert.equal(rec.jobStartedAt, before.jobStartedAt);
    assert.deepEqual(rec.jobs, before.jobs);
    assert.throws(() => reopenJob(t.deps, "u1"), /u1 has no finished job to reopen/);
  } finally {
    t.cleanup();
  }
});

test("reopen refuses when another job took the checkout meanwhile", () => {
  const t = setup([interactive("u1", 1), interactive("u2", 2)]);
  try {
    adoptSession(t.deps, "u1");
    adoptSession(t.deps, "u2");
    assignJob(t.deps, "u1", "one");
    finishJob(t.deps, "u1");
    assignJob(t.deps, "u2", "two");
    assert.throws(() => reopenJob(t.deps, "u1"), /u2 is already editing/);
  } finally {
    t.cleanup();
  }
});

test("the CLI: assign --extend, reopen, and their usage errors", async () => {
  const t = setup([interactive("u1", 1)]);
  try {
    assert.equal(await main(["adopt", "u1"], t.deps), 0);
    assert.equal(await main(["assign", "u1", "one"], t.deps), 0);
    assert.equal(await main(["assign", "u1", "two", "--extend"], t.deps), 0);
    assert.match(t.out.at(-1), /^extended u1: one; two$/);
    assert.equal(await main(["finish", "u1"], t.deps), 0);
    assert.equal(await main(["reopen", "u1"], t.deps), 0);
    assert.match(t.out.at(-1), /^reopened u1: one; two$/);
    assert.equal(await main(["reopen"], t.deps), 2);
    assert.equal(await main(["assign", "u1", "x", "--extend", "--reuse"], t.deps), 2);
  } finally {
    t.cleanup();
  }
});

// --- U-3 write scopes ---

test("scopes: relative folders, normalized, never outside the checkout", () => {
  const d = { platform: "win32" };
  assert.deepEqual(parseScope(d, "Brand\\Logo/, docs"), ["brand/logo", "docs"]);
  assert.throws(() => parseScope(d, "C:\\Work"), /relative to the checkout/);
  assert.throws(() => parseScope(d, "../x"), /leaves the checkout/);
  assert.throws(() => parseScope(d, " , "), /at least one folder/);
});

test("collision: no scope, both git, or overlapping folders collide; disjoint with one git does not", () => {
  assert.match(collision({ scope: ["a"], git: false }, { git: true }), /unless both jobs pass --scope/);
  assert.match(collision({ scope: ["a"], git: true }, { scope: ["b"], git: true }), /both jobs run git/);
  assert.match(collision({ scope: ["a/b"], git: false }, { scope: ["a"], git: true }), /overlap at a\/b/);
  assert.match(collision({ scope: ["."], git: false }, { scope: ["b"], git: true }), /overlap/);
  assert.equal(collision({ scope: ["research"], git: false }, { scope: ["brand"], git: true }), null);
});

test("two jobs share a checkout only with disjoint scopes and one git", () => {
  const t = setup([interactive("u1", 1), interactive("u2", 2), interactive("u3", 3)]);
  try {
    for (const n of ["u1", "u2", "u3"]) adoptSession(t.deps, n);
    assignJob(t.deps, "u1", "draw", { scope: "brand/logo" });
    assert.throws(() => assignJob(t.deps, "u2", "research"), /u1 is already editing .*unless both jobs pass --scope/);
    assert.throws(() => assignJob(t.deps, "u2", "research", { scope: "research" }), /both jobs run git/);
    assert.throws(() => assignJob(t.deps, "u2", "research", { scope: "brand", noGit: true }), /overlap/);
    const rec = assignJob(t.deps, "u2", "research", { scope: "research", noGit: true });
    assert.deepEqual([rec.scope, rec.git], [["research"], false]);
    assert.equal(pickSession(t.deps, REPO), null);
    assert.equal(pickSession(t.deps, REPO, { scope: "docs", noGit: true }).name, "u3");
    assert.equal(pickSession(t.deps, REPO, { scope: "brand", noGit: true }), null);
  } finally {
    t.cleanup();
  }
});

test("pick and spawn follow the same scope rule", async () => {
  const t = setup([interactive("u1", 1), interactive("u2", 2)]);
  try {
    adoptSession(t.deps, "u1");
    adoptSession(t.deps, "u2");
    assignJob(t.deps, "u1", "draw", { scope: "brand" });
    assert.equal(pickSession(t.deps, REPO, { scope: "research", noGit: true }).name, "u2");
    const brief = path.join(t.dir, "b.md");
    fs.writeFileSync(brief, "do it");
    assert.throws(() => spawnWorker(t.deps, "w9", REPO, brief, { effort: "high" }), /already editing .*unless both jobs pass --scope/);
    const w = spawnWorker(t.deps, "w9", REPO, brief, { scope: "docs", noGit: true, effort: "high" });
    assert.deepEqual(t.readRegistry().workers[w.name].scope, ["docs"]);
    assert.equal(await main(["assign", "u2", "more", "--scope", "docs", "--no-git"], t.deps), 1);
    assert.match(t.err.at(-1), /w9 is already editing .*overlap at docs|both jobs run git/);
  } finally {
    t.cleanup();
  }
});

// --- U-10 tiers ---

test("tiers: creative is Opus at high or more, mechanical is not Opus at medium or less", () => {
  assert.equal(tierMatch("creative", { model: "claude-opus-5-5", effort: "max" }), true);
  assert.equal(tierMatch("creative", { model: "claude-opus-5-5", effort: "medium" }), false);
  assert.equal(tierMatch("creative", { model: "claude-sonnet-5-5", effort: "max" }), false);
  assert.equal(tierMatch("mechanical", { model: "claude-sonnet-5-5", effort: "medium" }), true);
  assert.equal(tierMatch("mechanical", { model: "claude-opus-5-5", effort: "low" }), false);
  assert.equal(tierMatch("mechanical", { model: "claude-haiku-5-5", effort: "high" }), false);
  assert.equal(tierMatch("creative", { model: null, effort: null }), null);
  assert.throws(() => tierMatch("fancy", {}), /--tier must be creative or mechanical/);
});

test("assign --tier warns on a mismatch and does not refuse; a fresh session is unchecked", async () => {
  const t = setup([interactive("u1", 1), interactive("u2", 2, "C:\\Work\\Other")]);
  try {
    adoptSession(t.deps, "u1");
    adoptSession(t.deps, "u2");
    t.writeTranscript(t.deps.agents[0].sessionId, request("claude-sonnet-5-5", "medium") + line({ type: "user" }));
    assert.equal(await main(["assign", "u1", "logo", "--tier", "creative"], t.deps), 0);
    assert.deepEqual(t.out, [
      "assigned u1: logo",
      "MISMATCH u1 tier creative needs an Opus model at high effort or more; it runs claude-sonnet-5-5 medium",
    ]);
    t.out.length = 0;
    assert.equal(await main(["assign", "u2", "rename", "--tier", "mechanical"], t.deps), 0);
    assert.match(t.out[1], /^u2 tier mechanical: unchecked \(no turn yet\); have it state its model, then read its effort with list --name$/);
    assert.equal(t.readRegistry().workers.u2.tier, "mechanical");
  } finally {
    t.cleanup();
  }
});

test("pick --tier prefers a clean session that already matches, then an unchecked one", async () => {
  const t = setup([interactive("u1", 1), interactive("u2", 2), interactive("u3", 3)]);
  try {
    for (const n of ["u1", "u2", "u3"]) adoptSession(t.deps, n);
    // A request line alone leaves the session clean (no assistant turn yet) but tells its model.
    t.writeTranscript(t.deps.agents[0].sessionId, request("claude-sonnet-5-5", "medium"));
    t.writeTranscript(t.deps.agents[2].sessionId, request("claude-opus-5-5", "high"));
    assert.equal(pickSession(t.deps, REPO, { tier: "creative" }).name, "u3");
    assert.equal(pickSession(t.deps, REPO, { tier: "mechanical" }).name, "u1");
    assert.equal(await main(["pick", REPO, "--tier", "creative"], t.deps), 0);
    assert.deepEqual(t.out, ["u3", "u3 tier creative: ok (claude-opus-5-5 high)"]);
  } finally {
    t.cleanup();
  }
});

// --- the master's roster record ---

test("the master adopts itself with its window; it takes no job and holds no lock", async () => {
  const t = setup([interactive("m", 1), interactive("u1", 2)]);
  try {
    assert.equal(await main(["adopt", "m", "--role", "master", "--window", "1000000"], t.deps), 0);
    assert.equal(t.readRegistry().workers.m.window, 1000000);
    assert.throws(() => assignJob(t.deps, "m", "x"), /m is the master; the master takes no jobs/);
    t.writeTranscript(t.deps.agents[0].sessionId, turn(250000));
    assert.equal(await main(["measure", "m"], t.deps), 0);
    assert.match(t.out.at(-1), /^m {2}250000 {2}25% .*\(window 1000000 from recorded\)$/);
    adoptSession(t.deps, "u1");
    assert.equal(pickSession(t.deps, REPO).name, "u1");
  } finally {
    t.cleanup();
  }
});

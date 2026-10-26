import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import {
  PuppetError,
  RESUME_PROMPT,
  main,
  parseCompactResult,
} from "../../plugins/batbelt/skills/puppet-master/scripts/puppet.mjs";
import { agent, fixture, makeDeps } from "./helpers.mjs";

const COMPACT_RESULT = fixture("compact-result.json");
const NOW = new Date("2026-06-01T00:00:00Z");
const RESUMED_ID = "cccccccc";

function boundaryLine(postTokens, timestamp) {
  return `${JSON.stringify({
    type: "system",
    subtype: "compact_boundary",
    isSidechain: false,
    timestamp,
    compactMetadata: { trigger: "manual", preTokens: 429223, postTokens },
  })}\n`;
}

// A worker `w1` at 429223 tokens (an old boundary sits before its last usage). The fake
// `-p` call appends a fresh boundary unless `compact` overrides it.
function cycleSetup({ state = "done", compact, resume } = {}) {
  const w = agent("w1", 1, { state, status: state === "done" ? "idle" : "busy" });
  const t = makeDeps({
    agents: [w],
    now: () => NOW,
    handler(args) {
      if (args[0] === "stop") {
        t.deps.agents = t.deps.agents.filter((a) => a.id !== w.id);
        return { stdout: `stopped ${w.id}\n` };
      }
      if (args[0] === "-p") {
        if (compact) return compact(args);
        fs.appendFileSync(t.transcript, boundaryLine(25016, "2026-06-01T00:00:05.000Z"));
        return { stdout: COMPACT_RESULT };
      }
      if (args[0] === "--bg") {
        if (resume) return resume(args);
        t.deps.agents.push({ ...w, id: RESUMED_ID });
        return { stdout: fixture("bg-stdout.txt").replaceAll("573b7648", RESUMED_ID) };
      }
      return undefined;
    },
  });
  t.w = w;
  t.transcript = t.writeTranscript(
    w.sessionId,
    boundaryLine(1000, "2026-01-01T00:00:00.000Z") +
      fixture("transcript-compact-after.jsonl").split(/\r?\n/).slice(0, 2).join("\n") +
      "\n",
  );
  t.writeRegistry({
    workers: { w1: { id: w.id, sessionId: w.sessionId, cwd: "/work/repo", checkout: "/work/repo" } },
  });
  return t;
}

const verbs = (t) => t.calls.filter((c) => c.cmd === "claude" && c.args[0] !== "agents");

test("parseCompactResult reads the window and refuses errors", () => {
  assert.deepEqual(parseCompactResult(COMPACT_RESULT), { contextWindow: 1000000 });
  assert.throws(() => parseCompactResult(JSON.stringify({ is_error: true, result: "nope" })), PuppetError);
  assert.throws(() => parseCompactResult(JSON.stringify({ is_error: false, modelUsage: {} })), PuppetError);
  assert.throws(() => parseCompactResult("not json"), PuppetError);
});

test("refuses a busy worker", async () => {
  for (const state of ["working", "something-new"]) {
    const t = cycleSetup({ state });
    try {
      assert.equal(await main(["cycle", "w1", "probe"], t.deps), 1);
      assert.match(t.err.join("\n"), /not at a task boundary/);
      assert.equal(verbs(t).length, 0);
    } finally {
      t.cleanup();
    }
  }
});

test("refuses an interactive session even when idle", async () => {
  const t = cycleSetup();
  try {
    t.deps.agents = [{ ...t.w, kind: "interactive", state: undefined, status: "idle" }];
    assert.equal(await main(["cycle", "w1", "probe"], t.deps), 1);
    assert.match(t.err.join("\n"), /not a background worker/);
    assert.equal(verbs(t).length, 0);
  } finally {
    t.cleanup();
  }
});

test("runs stop, then -p --resume with /compact, then --bg --resume", async () => {
  const t = cycleSetup();
  try {
    assert.equal(await main(["cycle", "w1", "keep the plan"], t.deps), 0);
    const sid = t.w.sessionId;
    assert.deepEqual(
      verbs(t).map((c) => c.args),
      [
        ["stop", t.w.id],
        ["-p", "--resume", sid, "--output-format", "json", "/compact keep the plan"],
        ["--bg", "--resume", sid, RESUME_PROMPT],
      ],
    );
    assert.equal(verbs(t)[1].opts.cwd, "/work/repo");
    assert.equal(verbs(t)[2].opts.cwd, "/work/repo");
    assert.deepEqual(t.out, [
      `cycled w1: 429223→25016 tokens (42.9%→2.5%), resumed id=${RESUMED_ID}`,
    ]);
  } finally {
    t.cleanup();
  }
});

test("records the window from modelUsage", async () => {
  const t = cycleSetup();
  try {
    assert.equal(await main(["cycle", "w1", "probe"], t.deps), 0);
    assert.equal(t.readRegistry().workers.w1.window, 1000000);
    t.out.length = 0;
    assert.equal(await main(["measure", "w1"], t.deps), 0);
    assert.match(t.out[0], /^w1 {2}25016 {2}2\.5% .*from recorded\)$/);
  } finally {
    t.cleanup();
  }
});

test("no new compact_boundary is loud", async () => {
  const t = cycleSetup({ compact: () => ({ stdout: COMPACT_RESULT }) });
  try {
    assert.equal(await main(["cycle", "w1", "probe"], t.deps), 1);
    const msg = t.err.join("\n");
    assert.match(msg, /stopped and NOT compacted/);
    assert.ok(msg.includes(`cd "/work/repo" && claude --bg --resume ${t.w.sessionId}`));
    assert.equal(verbs(t).filter((c) => c.args[0] === "--bg").length, 0);
  } finally {
    t.cleanup();
  }
});

test("-p failure is loud", async () => {
  const failures = [
    () => ({ code: 1, stderr: "resume refused" }),
    () => ({ stdout: JSON.stringify({ is_error: true, result: "compact failed" }) }),
  ];
  for (const compact of failures) {
    const t = cycleSetup({ compact });
    try {
      assert.equal(await main(["cycle", "w1", "probe"], t.deps), 1);
      const msg = t.err.join("\n");
      assert.match(msg, /stopped and NOT compacted/);
      assert.ok(msg.includes(`cd "/work/repo" && claude --bg --resume ${t.w.sessionId}`));
      assert.equal(verbs(t).filter((c) => c.args[0] === "--bg").length, 0);
    } finally {
      t.cleanup();
    }
  }
});

test("--next uses the brief file as the restart prompt", async () => {
  const t = cycleSetup();
  try {
    const brief = path.join(t.dir, "next.md");
    fs.writeFileSync(brief, "Task 2: do the next thing");
    assert.equal(await main(["cycle", "w1", "probe", "--next", brief], t.deps), 0);
    assert.deepEqual(verbs(t).at(-1).args.at(-1), "Task 2: do the next thing");
  } finally {
    t.cleanup();
  }
});

test("updates the record with the resumed id", async () => {
  const t = cycleSetup();
  try {
    assert.equal(await main(["cycle", "w1", "probe"], t.deps), 0);
    const rec = t.readRegistry().workers.w1;
    assert.equal(rec.id, RESUMED_ID);
    assert.equal(rec.sessionId, t.w.sessionId);
  } finally {
    t.cleanup();
  }
});

test("a failed restart says the worker is compacted but stopped", async () => {
  const t = cycleSetup({ resume: () => ({ code: 1, stderr: "cannot resume" }) });
  try {
    assert.equal(await main(["cycle", "w1", "probe"], t.deps), 1);
    const msg = t.err.join("\n");
    assert.match(msg, /compacted but stopped/);
    assert.ok(msg.includes(`cd "/work/repo" && claude --bg --resume ${t.w.sessionId}`));
  } finally {
    t.cleanup();
  }
});

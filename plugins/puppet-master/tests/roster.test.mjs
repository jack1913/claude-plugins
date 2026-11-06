import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import {
  adoptSession,
  assignJob,
  finishJob,
  isEditing,
  main,
  pickSession,
} from "../skills/puppet-master/scripts/puppet.mjs";
import { agent, fixture, makeDeps } from "./helpers.mjs";

const REPO = "C:\\Work\\Repo";
const OTHER = "C:\\Work\\Other";

// A window the user opened, shaped like a live `claude agents --json` row: no id, no state.
const interactive = (name, n, cwd = REPO) =>
  agent(name, n, { kind: "interactive", id: undefined, state: undefined, status: "idle", cwd });
const background = (name, n, cwd = REPO) => agent(name, n, { cwd });

// git rev-parse answers with the cwd's top folder: everything under C:\Work\<x> is that checkout,
// unless `toplevel` maps a cwd to another answer.
function setup(agents, { toplevel = {} } = {}) {
  const t = makeDeps({
    agents,
    handler(args, opts, calls) {
      const call = calls.at(-1);
      if (call.cmd !== "git") return undefined;
      const cwd = args[1];
      if (cwd in toplevel) return { stdout: `${toplevel[cwd]}\n` };
      const m = /^([A-Za-z]:\\Work\\[^\\]+)/.exec(cwd);
      return { stdout: `${m ? m[1] : cwd}\n` };
    },
  });
  t.deps.platform = "win32";
  t.brief = (text) => {
    const p = path.join(t.dir, "brief.md");
    fs.writeFileSync(p, `${text}\n<!-- end of the puppet-master worker brief: keep this line -->\n`);
    return p;
  };
  return t;
}

test("adopt records a fresh interactive session as clean", () => {
  const t = setup([interactive("u1", 1)]);
  try {
    const rec = adoptSession(t.deps, "u1");
    assert.equal(rec.kind, "interactive");
    assert.equal(rec.role, "worker");
    assert.equal(rec.jobState, "clean");
    assert.equal(rec.job, null);
    assert.equal(t.readRegistry().workers.u1.checkout, REPO);
  } finally {
    t.cleanup();
  }
});

test("adopt records a session with turns as unknown", () => {
  const u1 = interactive("u1", 1);
  const t = setup([u1]);
  try {
    t.writeTranscript(u1.sessionId, fixture("transcript-usage-sum.jsonl"));
    assert.equal(adoptSession(t.deps, "u1").jobState, "unknown");
  } finally {
    t.cleanup();
  }
});

test("adopt --role analyst refuses a second live analyst", async () => {
  const t = setup([interactive("u1", 1), interactive("u2", 2)]);
  try {
    assert.equal(await main(["adopt", "u1", "--role", "analyst"], t.deps), 0);
    assert.match(t.out[0], /^adopted u1 \(interactive, analyst, clean\) in C:\\Work\\Repo$/);
    assert.equal(await main(["adopt", "u2", "--role", "analyst"], t.deps), 1);
    assert.match(t.err.join("\n"), /u1 is already the analyst/);
    assert.equal(await main(["adopt", "u2", "--role", "boss"], t.deps), 2);
  } finally {
    t.cleanup();
  }
});

test("assign refuses a session whose job is not clean: one job per context", () => {
  const u1 = interactive("u1", 1);
  const t = setup([u1]);
  try {
    t.writeTranscript(u1.sessionId, fixture("transcript-usage-sum.jsonl"));
    adoptSession(t.deps, "u1");
    assert.throws(() => assignJob(t.deps, "u1", "review PR 7"), /one job per context/);
  } finally {
    t.cleanup();
  }
});

test("assign refuses the analyst", () => {
  const t = setup([interactive("u1", 1)]);
  try {
    adoptSession(t.deps, "u1", { role: "analyst" });
    assert.throws(() => assignJob(t.deps, "u1", "review PR 7"), /the analyst takes no jobs/);
  } finally {
    t.cleanup();
  }
});

test("assign refuses a session that is not in the roster", () => {
  const t = setup([interactive("u1", 1)]);
  try {
    assert.throws(() => assignJob(t.deps, "u1", "x"), /not in the roster; adopt it first/);
  } finally {
    t.cleanup();
  }
});

test("assign refuses a second editing session in the same checkout", () => {
  const t = setup([interactive("u1", 1), interactive("u2", 2, `${REPO}\\sub`)]);
  try {
    adoptSession(t.deps, "u1");
    adoptSession(t.deps, "u2");
    const rec = assignJob(t.deps, "u1", "merge EPIC-1");
    assert.equal(rec.jobState, "active");
    assert.equal(rec.job, "merge EPIC-1");
    assert.equal(rec.jobStartedAt, "2026-01-01T00:00:00.000Z");
    assert.throws(() => assignJob(t.deps, "u2", "merge EPIC-2"), /u1 is already editing C:\\Work\\Repo/);
  } finally {
    t.cleanup();
  }
});

test("pick prefers a clean interactive session in the cwd's checkout", async () => {
  const t = setup([background("b1", 1), interactive("u1", 2), interactive("u3", 3, OTHER)]);
  try {
    t.writeRegistry({
      workers: {
        b1: { id: t.deps.agents[0].id, sessionId: t.deps.agents[0].sessionId, cwd: REPO, checkout: REPO, kind: "background", role: "worker", job: null, jobState: "clean" },
      },
    });
    adoptSession(t.deps, "u1");
    adoptSession(t.deps, "u3");
    assert.equal(pickSession(t.deps, `${REPO}\\src`).name, "u1");
    assert.equal(await main(["pick", OTHER], t.deps), 0);
    assert.deepEqual(t.out, ["u3"]);
  } finally {
    t.cleanup();
  }
});

test("pick treats a differently-cased Windows path with spaces as the same checkout", () => {
  const spaced = "D:\\Work\\My Notes";
  const t = setup([interactive("u1", 1, spaced)], {
    toplevel: { [spaced]: spaced, "d:\\work\\my notes\\drafts": "d:\\work\\my notes" },
  });
  try {
    adoptSession(t.deps, "u1");
    assert.equal(pickSession(t.deps, "d:\\work\\my notes\\drafts").name, "u1");
  } finally {
    t.cleanup();
  }
});

test("pick returns null when the only clean session's checkout has an editing session", async () => {
  const t = setup([interactive("u1", 1), interactive("u2", 2)]);
  try {
    adoptSession(t.deps, "u1");
    adoptSession(t.deps, "u2");
    assignJob(t.deps, "u1", "merge");
    assert.equal(pickSession(t.deps, REPO), null);
    assert.equal(await main(["pick", REPO], t.deps), 1);
    assert.match(t.err.join("\n"), /^puppet: no clean session for C:\\Work\\Repo; spawn one$/);
  } finally {
    t.cleanup();
  }
});

test("finish marks the job done; the session is neither clean nor editing", () => {
  const t = setup([interactive("u1", 1), interactive("u2", 2)]);
  try {
    adoptSession(t.deps, "u1");
    adoptSession(t.deps, "u2");
    assignJob(t.deps, "u1", "merge");
    const rec = finishJob(t.deps, "u1");
    assert.equal(rec.jobState, "done");
    assert.equal(rec.job, "merge");
    assert.equal(isEditing(rec, t.deps.agents), false);
    assert.equal(pickSession(t.deps, REPO).name, "u2");
    assert.throws(() => assignJob(t.deps, "u1", "another"), /one job per context/);
    assert.throws(() => finishJob(t.deps, "u1"), /has no active job/);
  } finally {
    t.cleanup();
  }
});

test("list marks a roster session whose sessionId changed as changed, and keeps its record", async () => {
  const t = setup([interactive("u1", 1)]);
  try {
    adoptSession(t.deps, "u1");
    t.deps.agents[0] = { ...t.deps.agents[0], sessionId: "cccccccc-0000-4000-8000-000000000000" };
    assert.equal(await main(["list", "--json"], t.deps), 0);
    const row = JSON.parse(t.out[0]);
    assert.equal(row.name, "u1");
    assert.equal(row.changed, true);
    t.out.length = 0;
    assert.equal(await main(["list"], t.deps), 0);
    assert.match(t.out[0], /^u1 {2}changed {2}\(new session id: ask the user whether it was cleared\)$/);
    assert.ok(t.readRegistry().workers.u1);
    assert.throws(() => assignJob(t.deps, "u1", "x"), /new session id/);
  } finally {
    t.cleanup();
  }
});

const said = (text, tokens = 1000) =>
  `${JSON.stringify({ type: "assistant", message: { usage: { input_tokens: tokens }, content: [{ type: "text", text }] } })}\n`;
const toolUse = (tokens = 1000) =>
  `${JSON.stringify({ type: "assistant", message: { usage: { input_tokens: tokens }, content: [{ type: "tool_use", name: "Bash", input: {} }] } })}\n`;

test("list flags an active job whose session's last word reads as done: DONE? run finish", async () => {
  const t = setup([interactive("u1", 1), interactive("u2", 2, OTHER), interactive("u3", 3, "C:\\Work\\Third")]);
  try {
    t.deps.env.PUPPET_CONTEXT_WINDOW = "200000";
    for (const n of ["u1", "u2", "u3"]) adoptSession(t.deps, n);
    for (const n of ["u1", "u2", "u3"]) assignJob(t.deps, n, `job ${n}`);
    const [a1, a2, a3] = t.deps.agents;
    t.writeTranscript(a1.sessionId, said("Working on it.") + said("FINAL: the merge is pushed.") + toolUse());
    t.writeTranscript(a2.sessionId, said("Step 2 of 4 done, starting step 3.") + toolUse());
    t.writeTranscript(a3.sessionId, said("The job is done; nothing is left."));
    assert.equal(await main(["list"], t.deps), 0);
    const rows = t.out.join("\n");
    assert.match(rows, /^u1 .*active job u1 {2}DONE\? run finish$/m);
    assert.match(rows, /^u3 .*active job u3 {2}DONE\? run finish$/m);
    assert.doesNotMatch(rows, /^u2 .*DONE\?/m);
    finishJob(t.deps, "u1");
    t.out.length = 0;
    assert.equal(await main(["list"], t.deps), 0);
    assert.doesNotMatch(t.out.join("\n"), /^u1 .*DONE\?/m);
  } finally {
    t.cleanup();
  }
});

test("list shows interactive roster sessions with kind, role and job", async () => {
  const t = setup([interactive("u1", 1), interactive("u2", 2, OTHER), interactive("stranger", 3)]);
  try {
    adoptSession(t.deps, "u1");
    adoptSession(t.deps, "u2", { role: "analyst" });
    assignJob(t.deps, "u1", "review PR 7");
    assert.equal(await main(["list"], t.deps), 0);
    const rows = t.out.join("\n");
    assert.match(rows, /^u1 {2}0 {2}0% {2}fresh {2}\(no turns yet\) {2}model fresh {2}interactive worker active review PR 7$/m);
    assert.match(rows, /^u2 {2}0 {2}0% {2}fresh {2}\(no turns yet\) {2}model fresh {2}interactive analyst clean$/m);
    assert.doesNotMatch(rows, /^stranger/m);
  } finally {
    t.cleanup();
  }
});

test("spawn ignores clean adopted sessions and the analyst when locking the checkout", async () => {
  const fresh = background("w9", 9);
  const t = setup([interactive("u1", 1), interactive("u2", 2)]);
  const run = t.deps.run;
  t.deps.run = (cmd, args, opts) => {
    if (args[0] === "--bg") {
      t.calls.push({ cmd, args, opts });
      t.deps.agents.push(fresh);
      return { code: 0, stdout: `backgrounded · ${fresh.id} · w9\n`, stderr: "" };
    }
    return run(cmd, args, opts);
  };
  try {
    adoptSession(t.deps, "u1");
    adoptSession(t.deps, "u2", { role: "analyst" });
    assert.equal(await main(["spawn", "w9", REPO, t.brief("job"), "--job", "release 1.2", "--effort", "high"], t.deps), 0);
    const rec = t.readRegistry().workers.w9;
    assert.equal(rec.kind, "background");
    assert.equal(rec.role, "worker");
    assert.equal(rec.job, "release 1.2");
    assert.equal(rec.jobState, "active");
    assert.ok(t.readRegistry().workers.u1, "spawn must not prune a live clean session");
  } finally {
    t.cleanup();
  }
});

test("a busy session adopted as unknown counts as editing its checkout", async () => {
  const busy = { ...interactive("u1", 1), status: "busy" };
  const t = setup([busy, interactive("u2", 2)]);
  try {
    t.writeTranscript(busy.sessionId, fixture("transcript-usage-sum.jsonl"));
    adoptSession(t.deps, "u1");
    adoptSession(t.deps, "u2");
    assert.equal(t.readRegistry().workers.u1.jobState, "unknown");
    assert.equal(pickSession(t.deps, REPO), null);
    assert.throws(() => assignJob(t.deps, "u2", "merge"), /u1 is already editing/);
    t.deps.agents[0] = { ...busy, status: "idle" };
    assert.equal(pickSession(t.deps, REPO).name, "u2");
  } finally {
    t.cleanup();
  }
});

test("an unknown session parked on a dialog (state done, status waiting) still counts as editing", async () => {
  const parked = { ...background("w1", 1), state: "done", status: "waiting" };
  const t = setup([parked, interactive("u2", 2)]);
  try {
    t.writeTranscript(parked.sessionId, fixture("transcript-usage-sum.jsonl"));
    adoptSession(t.deps, "w1");
    adoptSession(t.deps, "u2");
    assert.equal(t.readRegistry().workers.w1.jobState, "unknown");
    assert.equal(isEditing(t.readRegistry().workers.w1, t.deps.agents), true);
    assert.equal(pickSession(t.deps, REPO), null);
    t.deps.agents[0] = { ...parked, status: "idle" };
    assert.equal(isEditing(t.readRegistry().workers.w1, t.deps.agents), false);
  } finally {
    t.cleanup();
  }
});

test("an old-format record counts as an editing background worker", () => {
  const w = background("w1", 1);
  assert.equal(isEditing({ id: w.id, sessionId: w.sessionId, cwd: REPO, checkout: REPO }, [w]), true);
  assert.equal(isEditing({ id: w.id, sessionId: w.sessionId, cwd: REPO, checkout: REPO }, []), false);
});

test("spawn keeps a changed record: the name is still listed under a new session id", async () => {
  const fresh = background("w9", 9);
  const t = setup([interactive("u1", 1)]);
  const run = t.deps.run;
  t.deps.run = (cmd, args, opts) => {
    if (args[0] === "--bg") {
      t.deps.agents.push(fresh);
      return { code: 0, stdout: `backgrounded · ${fresh.id} · w9\n`, stderr: "" };
    }
    return run(cmd, args, opts);
  };
  try {
    adoptSession(t.deps, "u1");
    t.deps.agents[0] = { ...t.deps.agents[0], sessionId: "cccccccc-0000-4000-8000-000000000000" };
    assert.equal(await main(["spawn", "w9", REPO, t.brief("job"), "--effort", "high"], t.deps), 0);
    assert.ok(t.readRegistry().workers.u1, "spawn must not prune a changed record");
    assert.doesNotMatch(t.out.join("\n"), /pruned/);
  } finally {
    t.cleanup();
  }
});

// --- a session renamed in its window keeps its roster record (2026-11-04: e380c6ee, 66 → b3) ---

const record = (a, extra = {}) => ({
  id: a.id,
  sessionId: a.sessionId,
  cwd: REPO,
  checkout: REPO,
  kind: "interactive",
  role: "worker",
  job: null,
  jobState: "clean",
  ...extra,
});

test("a renamed session: adopt under the new name carries the old record over, no unknown twin", () => {
  const u = interactive("old-66", 1);
  const t = setup([u]);
  try {
    adoptSession(t.deps, "old-66");
    assignJob(t.deps, "old-66", "the job");
    finishJob(t.deps, "old-66");
    t.deps.agents[0] = { ...u, name: "new-b3" };
    const r = adoptSession(t.deps, "new-b3");
    assert.equal(r.jobState, "done");
    const reg = t.readRegistry();
    assert.deepEqual(Object.keys(reg.workers), ["new-b3"]);
    assert.equal(reg.workers["new-b3"].job, "the job");
    assert.equal(reg.workers["new-b3"].jobs.length, 1);
  } finally {
    t.cleanup();
  }
});

test("a renamed session: assign --reuse, clear and list work under the new name without an adopt", async () => {
  const u = interactive("old-66", 1);
  const t = setup([u], {});
  try {
    adoptSession(t.deps, "old-66");
    assignJob(t.deps, "old-66", "the job");
    finishJob(t.deps, "old-66");
    t.deps.agents[0] = { ...u, name: "new-b3" };
    assert.equal(await main(["list"], t.deps), 0);
    assert.equal(t.out.length, 1);
    assert.match(t.out[0], /^new-b3 .*interactive worker done the job/);
    assert.deepEqual(Object.keys(t.readRegistry().workers), ["new-b3"]);
    assert.equal(assignJob(t.deps, "new-b3", "next job", { reuse: true }).jobState, "active");
  } finally {
    t.cleanup();
  }
});

test("a renamed session whose twin record already exists: the better record wins under the live name", () => {
  const u = interactive("new-b3", 1);
  const t = setup([u]);
  try {
    // what the 2026-11-04 roster held: the old name finished, the new name adopted as unknown
    t.writeRegistry({
      workers: {
        "old-66": record(u, { job: "the job", jobState: "done", jobs: [{ label: "the job", startedAt: "x", endedAt: "y" }], window: 1000000 }),
        "new-b3": record(u, { jobState: "unknown" }),
      },
    });
    assert.throws(() => assignJob(t.deps, "new-b3", "next", {}), /one job per context: new-b3 already did "the job"/);
    const reg = t.readRegistry();
    assert.deepEqual(Object.keys(reg.workers), ["new-b3"]);
    assert.equal(reg.workers["new-b3"].jobState, "done");
    assert.equal(reg.workers["new-b3"].window, 1000000);
    assert.equal(assignJob(t.deps, "new-b3", "next", { reuse: true }).jobState, "active");
  } finally {
    t.cleanup();
  }
});

test("a rename carries only a record with the same session id: a gone record and a cleared one stay as they were", async () => {
  const u1 = interactive("u1", 1);
  const t = setup([u1]);
  try {
    t.writeRegistry({
      workers: {
        // not live at all: reported gone, as before
        ghost: record(interactive("ghost", 9), { jobState: "done", job: "old" }),
        // the same name under a new session id: `changed`, never carried
        u1: record(u1, { sessionId: "dddddddd-0000-4000-8000-000000000000" }),
      },
    });
    assert.equal(await main(["list"], t.deps), 0);
    assert.match(t.out.join("\n"), /^ghost {2}gone /m);
    assert.match(t.out.join("\n"), /^u1 {2}changed /m);
    assert.deepEqual(Object.keys(t.readRegistry().workers), ["u1"]);
  } finally {
    t.cleanup();
  }
});

// 2026-11-04: `adopt carcare-platform-a0 --role worker --window N` on a carried done record made it `unknown`,
// and `clear` and `assign` then refused it.
test("adopt of a session already in the roster under the same name keeps its job and jobState, and updates role, window and mod role", () => {
  const u = interactive("u1", 1);
  const t = setup([u]);
  try {
    adoptSession(t.deps, "u1");
    assignJob(t.deps, "u1", "the job");
    finishJob(t.deps, "u1");
    t.writeTranscript(u.sessionId, fixture("transcript-usage-sum.jsonl"));
    const r = adoptSession(t.deps, "u1", { role: "worker", window: "1000000" });
    assert.equal(r.jobState, "done");
    assert.equal(r.job, "the job");
    assert.equal(r.window, 1000000);
    const rec = t.readRegistry().workers.u1;
    assert.equal(rec.jobState, "done");
    assert.equal(rec.job, "the job");
    assert.equal(rec.jobs.length, 1);
    assert.equal(rec.window, 1000000);
    // the mod role file is written (the session was adopted before the mod existed)
    const roleFile = path.join(t.dir, "puppet-master", "mod", "roles", `${u.sessionId}.json`);
    assert.equal(JSON.parse(fs.readFileSync(roleFile, "utf8")).role, "worker");
  } finally {
    t.cleanup();
  }
});

test("adopt of an active job's session keeps the job too, and a session id that changed is still re-adopted fresh", () => {
  const u = interactive("u1", 1);
  const t = setup([u]);
  try {
    adoptSession(t.deps, "u1");
    assignJob(t.deps, "u1", "the job", { scope: "docs" });
    assert.equal(adoptSession(t.deps, "u1").jobState, "active");
    assert.deepEqual(t.readRegistry().workers.u1.scope, ["docs"]);
    // cleared in its window: a new session id, so adopt starts it again as clean
    t.deps.agents[0] = { ...u, sessionId: "cccccccc-0000-4000-8000-000000000000" };
    assert.equal(adoptSession(t.deps, "u1").jobState, "clean");
    assert.equal(t.readRegistry().workers.u1.job, null);
  } finally {
    t.cleanup();
  }
});

// --- P-20261103-carcare-platform-10: a session that only read a brief and replied is clean ---

test("adopt: a session that only read a brief and replied counts as clean; one that worked is unknown", () => {
  const cases = [
    [said("ready"), "clean"],
    [said("Reading the brief.") + said("ready"), "clean"],
    [said("one") + said("two") + said("three"), "unknown"],
    [said("ready") + toolUse(), "unknown"],
    [toolUse(), "unknown"],
    [fixture("transcript-usage-sum.jsonl"), "unknown"],
  ];
  for (const [text, want] of cases) {
    const u = interactive("u1", 1);
    const t = setup([u]);
    try {
      t.writeTranscript(u.sessionId, text);
      assert.equal(adoptSession(t.deps, "u1").jobState, want, text);
    } finally {
      t.cleanup();
    }
  }
});

test("a brief-only session adopted as clean takes `assign`", () => {
  const u = interactive("u1", 1);
  const t = setup([u]);
  try {
    t.writeTranscript(u.sessionId, said("ready"));
    adoptSession(t.deps, "u1");
    assert.equal(assignJob(t.deps, "u1", "commit the fixes").jobState, "active");
  } finally {
    t.cleanup();
  }
});

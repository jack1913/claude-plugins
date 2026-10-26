import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import {
  BUSY_STATES,
  IDLE_STATES,
  PuppetError,
  findWorker,
  listAgents,
  loadRegistry,
  saveRegistry,
  statePath,
  workerState,
} from "../../plugins/batbelt/skills/puppet-master/scripts/puppet.mjs";
import { agent, makeDeps } from "./helpers.mjs";

const agents = [agent("w1", 1), agent("w2", 2)];

test("findWorker matches name, id and sessionId", () => {
  assert.equal(findWorker(agents, "w2").id, agents[1].id);
  assert.equal(findWorker(agents, agents[0].id).name, "w1");
  assert.equal(findWorker(agents, agents[1].sessionId).name, "w2");
});

test("ambiguous name is refused", () => {
  const twins = [agent("w1", 1), agent("w1", 3)];
  assert.throws(
    () => findWorker(twins, "w1"),
    (e) =>
      e instanceof PuppetError &&
      e.message.includes(twins[0].id) &&
      e.message.includes(twins[1].id),
  );
});

test("an unknown key throws", () => {
  assert.throws(() => findWorker(agents, "nope"), PuppetError);
});

test("workerState reads state, then status", () => {
  assert.equal(workerState({ state: "working", status: "busy" }), "working");
  assert.equal(workerState({ status: "idle" }), "idle");
  assert.ok(IDLE_STATES.has("done"));
  assert.ok(BUSY_STATES.has("working"));
  assert.ok(BUSY_STATES.has("blocked"));
});

test("listAgents parses agents --json and is loud on failure", () => {
  const ok = makeDeps({ agents });
  try {
    assert.deepEqual(listAgents(ok.deps), agents);
    assert.deepEqual(ok.calls[0].args, ["agents", "--json"]);
  } finally {
    ok.cleanup();
  }
  const bad = makeDeps({ handler: () => ({ code: 1, stderr: "boom" }) });
  try {
    assert.throws(() => listAgents(bad.deps), (e) => e.message.includes("boom"));
  } finally {
    bad.cleanup();
  }
  const junk = makeDeps({ handler: () => ({ stdout: "not json" }) });
  try {
    assert.throws(() => listAgents(junk.deps), PuppetError);
  } finally {
    junk.cleanup();
  }
});

test("registry round-trip leaves no temp file", () => {
  const t = makeDeps();
  try {
    assert.deepEqual(loadRegistry(t.deps), { workers: {} });
    const reg = { workers: { w1: { id: "a", sessionId: "b", cwd: "c", checkout: "d" } } };
    saveRegistry(t.deps, reg);
    assert.deepEqual(loadRegistry(t.deps), reg);
    const dir = path.dirname(statePath(t.deps));
    assert.deepEqual(fs.readdirSync(dir), ["workers.json"]);
  } finally {
    t.cleanup();
  }
});

test("statePath defaults under the config dir", () => {
  const t = makeDeps();
  try {
    delete t.deps.env.PUPPET_STATE;
    assert.equal(statePath(t.deps), path.join(t.dir, "puppet-master", "workers.json"));
  } finally {
    t.cleanup();
  }
});

test("a corrupt registry is an error", () => {
  const t = makeDeps();
  try {
    fs.mkdirSync(path.dirname(t.deps.env.PUPPET_STATE), { recursive: true });
    fs.writeFileSync(t.deps.env.PUPPET_STATE, "{oops");
    assert.throws(() => loadRegistry(t.deps), PuppetError);
  } finally {
    t.cleanup();
  }
});

test("an unrunnable claude names PUPPET_CLAUDE_BIN", () => {
  const t = makeDeps({ handler: () => ({ code: 1, error: Object.assign(new Error("spawnSync claude ENOENT"), { code: "ENOENT" }) }) });
  try {
    assert.throws(() => listAgents(t.deps), (e) => e instanceof PuppetError && e.message.includes("PUPPET_CLAUDE_BIN"));
  } finally {
    t.cleanup();
  }
});

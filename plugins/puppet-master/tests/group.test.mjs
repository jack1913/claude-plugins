// Several masters on one machine (carcare P-20261102-7): --group gives each its own roster
// and logs, and keeps one group's proposal ids out of another's decisions log.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import { main, statePath } from "../skills/puppet-master/scripts/puppet.mjs";
import { agent, makeDeps } from "./helpers.mjs";

function setup() {
  const t = makeDeps({ agents: [agent("u1", 1, { kind: "interactive", id: undefined, cwd: "C:\\Work\\Repo" })] });
  t.deps.run = ((run) => (cmd, args, opts = {}) => (cmd === "git" ? { code: 0, stdout: "C:\\Work\\Repo\n", stderr: "" } : run(cmd, args, opts)))(t.deps.run);
  t.deps.platform = "win32";
  t.logs = path.join(t.dir, "logs");
  return t;
}

test("without --group the roster and logs stay where they were", async () => {
  const t = setup();
  try {
    assert.equal(statePath(t.deps), t.deps.env.PUPPET_STATE);
    assert.equal(await main(["logs", "--logs", t.logs], t.deps), 0);
    assert.equal(t.out[0], t.logs);
  } finally {
    t.cleanup();
  }
});

test("--group keeps its roster in workers-<group>.json beside the default one", async () => {
  const t = setup();
  try {
    assert.equal(await main(["adopt", "u1", "--group", "carcare-platform"], t.deps), 0);
    const grouped = path.join(path.dirname(t.deps.env.PUPPET_STATE), "workers-carcare-platform.json");
    assert.ok(JSON.parse(fs.readFileSync(grouped, "utf8")).workers.u1);
    assert.equal(fs.existsSync(t.deps.env.PUPPET_STATE), false, "the default roster is untouched");
  } finally {
    t.cleanup();
  }
});

test("--group may come before the command, and puts the logs in <logs>/<group>", async () => {
  const t = setup();
  try {
    assert.equal(await main(["--group", "carcare-platform", "logs", "--logs", t.logs], t.deps), 0);
    assert.equal(t.out[0], path.join(t.logs, "carcare-platform"));
    t.deps.env.PUPPET_LOGS_DIR = t.logs;
    assert.equal(await main(["logs", "--group", "brainiac"], t.deps), 0);
    assert.equal(t.out[1], path.join(t.logs, "brainiac"));
  } finally {
    t.cleanup();
  }
});

test("a group name outside [A-Za-z0-9-], or two different groups, is a usage error", async () => {
  const t = setup();
  try {
    assert.equal(await main(["logs", "--logs", t.logs, "--group", "../x"], t.deps), 2);
    assert.equal(await main(["--group", "a", "logs", "--logs", t.logs, "--group", "b"], t.deps), 2);
    assert.equal(await main(["--group"], t.deps), 2);
  } finally {
    t.cleanup();
  }
});

test("decide and shipped refuse an id that carries another group, and take a legacy id", async () => {
  const t = setup();
  try {
    const d = (id, ...g) =>
      main(["decide", id, "approve", "--tag", "other", "--target", "SKILL.md", "--logs", t.logs, ...g], t.deps);
    assert.equal(await d("P-20261103-carcare-platform-1", "--group", "carcare-platform"), 0);
    assert.equal(await d("P-20261103-brainiac-1", "--group", "carcare-platform"), 2);
    assert.match(t.err.at(-1), /belongs to group "brainiac"; pass --group brainiac/);
    assert.equal(await d("P-20261103-carcare-platform-2"), 2);
    assert.match(t.err.at(-1), /belongs to group "carcare-platform"/);
    assert.equal(await d("P-20261102-7", "--group", "carcare-platform"), 0);
    const ship = (id, ...g) => main(["shipped", id, "abc1234", "--logs", t.logs, ...g], t.deps);
    assert.equal(await ship("P-20261103-carcare-platform-1"), 2);
    assert.equal(await ship("P-20261103-carcare-platform-1", "--group", "carcare-platform"), 0);
    assert.ok(fs.existsSync(path.join(t.logs, "carcare-platform", "decisions.jsonl")));
  } finally {
    t.cleanup();
  }
});

// brainiac P-20261112-4 (F-5). A legacy id approved with no group was refused "was never
// approved" under --group brainiac, and the message did not say which decisions it searched.
test("shipped's 'never approved' names the group, or no group, and the decisions file it searched", async () => {
  const t = setup();
  try {
    const d = (id, ...g) =>
      main(["decide", id, "approve", "--tag", "other", "--target", "SKILL.md", "--logs", t.logs, ...g], t.deps);
    const ship = (id, ...g) => main(["shipped", id, "abc1234", "--logs", t.logs, ...g], t.deps);
    assert.equal(await d("P-20261109-3"), 0);
    assert.equal(await ship("P-20261109-3", "--group", "brainiac"), 1);
    assert.equal(
      t.err.at(-1),
      `puppet: P-20261109-3 was never approved in group "brainiac" (decisions searched: ${path.join(t.logs, "brainiac", "decisions.jsonl")})`,
    );
    assert.equal(await ship("P-20261109-4"), 1);
    assert.equal(
      t.err.at(-1),
      `puppet: P-20261109-4 was never approved with no group (decisions searched: ${path.join(t.logs, "decisions.jsonl")})`,
    );
    assert.equal(await ship("P-20261109-3"), 0);
  } finally {
    t.cleanup();
  }
});

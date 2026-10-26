import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import { PuppetError, main, parseBgId } from "../../plugins/batbelt/skills/puppet-master/scripts/puppet.mjs";
import { agent, fixture, makeDeps } from "./helpers.mjs";

const BG_STDOUT = fixture("bg-stdout.txt");
const CAPTURED_ID = "573b7648";

// The fake answers `git rev-parse` with `toplevel`, and `--bg` by "starting" `fresh`:
// it prints the captured stdout (with fresh's id) and adds fresh to `agents --json`.
function spawnSetup({ live = [], toplevel = "C:\\Work\\Repo", bg } = {}) {
  const fresh = agent("w9", 9);
  const t = makeDeps({
    agents: [...live],
    handler(args, opts, calls) {
      const call = calls.at(-1);
      if (call.cmd === "git") return { stdout: `${toplevel}\n` };
      if (args[0] === "--bg") {
        if (bg) return bg(args);
        t.deps.agents.push(fresh);
        return { stdout: BG_STDOUT.replaceAll(CAPTURED_ID, fresh.id) };
      }
      return undefined;
    },
  });
  t.deps.platform = "win32";
  t.fresh = fresh;
  t.brief = (text) => {
    const p = path.join(t.dir, "brief.md");
    fs.writeFileSync(p, text);
    return p;
  };
  return t;
}

const bgCalls = (t) => t.calls.filter((c) => c.args[0] === "--bg");

test("parseBgId reads the captured --bg output", () => {
  assert.equal(parseBgId(BG_STDOUT), CAPTURED_ID);
  assert.throws(() => parseBgId("something else"), PuppetError);
});

test("launches claude --bg --name with the brief verbatim", async () => {
  const t = spawnSetup();
  try {
    const brief = 'Say "quotes"\nand keep %PATH% as is';
    assert.equal(await main(["spawn", "w9", "C:\\work\\repo", t.brief(brief)], t.deps), 0);
    const [call] = bgCalls(t);
    assert.equal(call.cmd, "claude");
    assert.deepEqual(call.args, ["--bg", "--name", "w9", brief]);
    assert.equal(call.opts.cwd, "C:\\work\\repo");
    assert.deepEqual(t.out, [`spawned w9 id=${t.fresh.id} in C:\\Work\\Repo`]);
  } finally {
    t.cleanup();
  }
});

test("records id and sessionId", async () => {
  const t = spawnSetup();
  try {
    assert.equal(await main(["spawn", "w9", "C:\\work\\repo", t.brief("job")], t.deps), 0);
    const rec = t.readRegistry().workers.w9;
    assert.equal(rec.id, t.fresh.id);
    assert.equal(rec.sessionId, t.fresh.sessionId);
    assert.equal(rec.checkout, "C:\\Work\\Repo");
    assert.ok(rec.cwd);
  } finally {
    t.cleanup();
  }
});

test("refuses a second live worker in the same checkout", async () => {
  const other = agent("editor", 1);
  const t = spawnSetup({ live: [other] });
  try {
    t.writeRegistry({
      workers: {
        editor: { id: other.id, sessionId: other.sessionId, cwd: "C:\\Work\\Repo", checkout: "C:\\Work\\Repo" },
      },
    });
    assert.equal(await main(["spawn", "w9", "c:\\work\\repo\\sub", t.brief("job")], t.deps), 1);
    assert.match(t.err.join("\n"), /editor/);
    assert.equal(bgCalls(t).length, 0);
  } finally {
    t.cleanup();
  }
});

test("a stale record does not lock", async () => {
  const t = spawnSetup();
  try {
    t.writeRegistry({
      workers: {
        editor: { id: "deadbeef", sessionId: "dead-sid", cwd: "C:\\Work\\Repo", checkout: "C:\\Work\\Repo" },
      },
    });
    assert.equal(await main(["spawn", "w9", "C:\\work\\repo", t.brief("job")], t.deps), 0);
    assert.deepEqual(Object.keys(t.readRegistry().workers), ["w9"]);
  } finally {
    t.cleanup();
  }
});

test("refuses a live name clash", async () => {
  const t = spawnSetup({ live: [agent("w9", 5)] });
  try {
    assert.equal(await main(["spawn", "w9", "C:\\work\\repo", t.brief("job")], t.deps), 2);
    assert.equal(bgCalls(t).length, 0);
  } finally {
    t.cleanup();
  }
});

test("rejects a name outside [A-Za-z0-9._-]", async () => {
  const t = spawnSetup();
  try {
    assert.equal(await main(["spawn", "bad name", "C:\\work\\repo", t.brief("job")], t.deps), 2);
    assert.equal(t.calls.length, 0);
  } finally {
    t.cleanup();
  }
});

test("rejects a missing or empty brief file", async () => {
  const t = spawnSetup();
  try {
    const missing = path.join(t.dir, "nope.md");
    assert.equal(await main(["spawn", "w9", "C:\\work\\repo", missing], t.deps), 2);
    assert.equal(await main(["spawn", "w9", "C:\\work\\repo", t.brief("  \n")], t.deps), 2);
    assert.equal(t.calls.length, 0);
  } finally {
    t.cleanup();
  }
});

test("rejects a brief over 30000 characters", async () => {
  const t = spawnSetup();
  try {
    assert.equal(await main(["spawn", "w9", "C:\\work\\repo", t.brief("x".repeat(30001))], t.deps), 2);
    assert.equal(t.calls.length, 0);
  } finally {
    t.cleanup();
  }
});

test("--bg failure is loud", async () => {
  const t = spawnSetup({ bg: () => ({ code: 1, stderr: "workspace not trusted" }) });
  try {
    assert.equal(await main(["spawn", "w9", "C:\\work\\repo", t.brief("job")], t.deps), 1);
    assert.match(t.err.join("\n"), /workspace not trusted/);
    assert.equal(fs.existsSync(t.deps.env.PUPPET_STATE), false);
  } finally {
    t.cleanup();
  }
});

function gitSetup(gitAnswer) {
  const t = spawnSetup();
  const handler = t.deps.run;
  t.deps.run = (cmd, args, opts) => (cmd === "git" ? (t.calls.push({ cmd, args, opts }), gitAnswer) : handler(cmd, args, opts));
  return t;
}

test("outside a git repository the checkout is the cwd", async () => {
  const t = gitSetup({ code: 128, stdout: "", stderr: "fatal: not a git repository (or any of the parent directories): .git" });
  try {
    assert.equal(await main(["spawn", "w9", "C:\\work\\plain", t.brief("job")], t.deps), 0);
    assert.equal(t.readRegistry().workers.w9.checkout, "C:\\work\\plain");
  } finally {
    t.cleanup();
  }
});

test("any other git failure is loud", async () => {
  const answers = [
    { code: 128, stdout: "", stderr: "fatal: detected dubious ownership in repository" },
    { code: 1, stdout: "", stderr: "", error: Object.assign(new Error("spawnSync git ENOENT"), { code: "ENOENT" }) },
  ];
  for (const answer of answers) {
    const t = gitSetup(answer);
    try {
      assert.equal(await main(["spawn", "w9", "C:\\work\\repo", t.brief("job")], t.deps), 1);
      assert.match(t.err.join("\n"), /git/);
      assert.equal(bgCalls(t).length, 0);
    } finally {
      t.cleanup();
    }
  }
});

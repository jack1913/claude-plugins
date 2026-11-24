import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import vm from "node:vm";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const PLUGIN_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const TEMPLATE = path.join(PLUGIN_DIR, "skills", "puppet-master", "templates", "task-page");
const read = (name) => fs.readFileSync(path.join(TEMPLATE, name), "utf8");
const FILES = ["index.html", "tasks.js", "sync-sessions.mjs"];

test("the task-page template ships its three files and no add-reports script", () => {
  for (const f of FILES) assert.ok(fs.existsSync(path.join(TEMPLATE, f)), `missing ${f}`);
  assert.ok(!fs.existsSync(path.join(TEMPLATE, "add-reports.mjs")), "reports are written straight into tasks.js");
});

test("the shipped files hold no user name, path, epic or ticket key", () => {
  for (const f of FILES) {
    const text = read(f);
    for (const bad of [/D:[\\/]/, /Krzysiek/i, /INEWI-/, /\bEPIC-\d/, /\bINIT-\d/, /inewi/i, /brainiac-pipeline/]) {
      assert.ok(!bad.test(text), `${f} matches ${bad}`);
    }
  }
});

test("tasks.js parses with window stubbed and is empty, with the data shape documented", () => {
  const text = read("tasks.js");
  const sandbox = { window: {} };
  vm.runInNewContext(text, sandbox);
  const d = sandbox.window.DASH;
  assert.ok(d, "window.DASH is set");
  for (const k of ["workSet", "days", "updated", "waitingNow", "sessions", "tasks"]) assert.ok(k in d, `no ${k}`);
  assert.equal(JSON.stringify([d.tasks, d.sessions]), "[[],[]]");
  assert.ok(Array.isArray(d.days));
  for (const word of ["workSet", "days", "updated", "waitingNow", "epics", "sessions", "tasks", "origin", "initial", "added", "done", "running", "waiting-you", "queued", "open", "evidence", "reports", "label", "path", "pending", "sub"]) {
    assert.ok(text.includes(word), `the shape comment does not name ${word}`);
  }
});

test("index.html keeps every feature of the live page", () => {
  const html = read("index.html");
  for (const needle of [
    "<header>", "id=\"waiting\"", "id=\"filters\"",
    "Not done", "Waiting for you", "Running", "Queued / open", "Done", "All", "Initial", "Added later",
    "<th>Session</th><th>State</th><th>Model / effort</th><th>Job</th>", "Context</th>",
    "table-layout:fixed", "<colgroup>", "col.c-id", "col class=\"s-name\"",
    "id=\"split\"", "<aside", "<iframe", "New window ↗", "Close ✕",
    "Click a report link in the list to read it here.",
    "const SHORT = 2", "-webkit-line-clamp:3", "show more", "show less",
    "localStorage", "\"pmboard.\" + k", "store.get(\"open\"", "store.get(\"panel\"",
    "tasks.js?t=", "setInterval(() => loadData(false), 90000)",
  ]) assert.ok(html.includes(needle), `index.html lacks: ${needle}`);
  assert.ok(!html.includes("location.reload"), "the data reloads without a page reload");
});

test("sync-sessions.mjs is generic: NOTES empty, helper and file are arguments or relative", () => {
  const text = read("sync-sessions.mjs");
  assert.match(text, /const NOTES = \{\};/);
  assert.match(text, /--puppet/);
  assert.match(text, /--file/);
});

test("sync-sessions.mjs rewrites the sessions block and the stamp from the helper's list", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "task-page-test-"));
  try {
    for (const f of FILES) fs.copyFileSync(path.join(TEMPLATE, f), path.join(dir, f));
    const fake = path.join(dir, "fake-puppet.mjs");
    fs.writeFileSync(
      fake,
      'console.log("w-1  99538  10%  busy  (window 1000000 from default)  model claude-sonnet-5-5 medium  interactive worker active build the thing  mod on (asked)");\n' +
        'console.log("m-1  0  0%  fresh  (no turns yet)  model fresh  interactive master clean  mod on (asked)");\n',
    );
    const out = execFileSync("node", [path.join(dir, "sync-sessions.mjs"), "--puppet", fake, "--file", path.join(dir, "tasks.js")], {
      encoding: "utf8",
    });
    assert.match(out, /w-1 \| working \(busy\) \| sonnet-5-5 medium \| build the thing/);
    const sandbox = { window: {} };
    vm.runInNewContext(fs.readFileSync(path.join(dir, "tasks.js"), "utf8"), sandbox);
    const s = sandbox.window.DASH.sessions;
    assert.equal(s.length, 2);
    assert.equal(s[0].name, "w-1");
    assert.equal(s[0].context, "99,538 (10%)");
    assert.equal(s[1].state, "master");
    assert.match(sandbox.window.DASH.updated, /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("sync-sessions.mjs refuses, loudly, when no helper can be found", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "task-page-test-"));
  try {
    fs.copyFileSync(path.join(TEMPLATE, "sync-sessions.mjs"), path.join(dir, "sync-sessions.mjs"));
    fs.copyFileSync(path.join(TEMPLATE, "tasks.js"), path.join(dir, "tasks.js"));
    assert.throws(
      () => execFileSync("node", [path.join(dir, "sync-sessions.mjs")], { encoding: "utf8", stdio: "pipe" }),
      (e) => /puppet\.mjs/.test(String(e.stderr)),
    );
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  PuppetError,
  findTranscript,
  percent,
  resolveWindow,
  transcriptTokens,
} from "../../plugins/batbelt/skills/puppet-master/scripts/puppet.mjs";

const FIXTURES = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");
const fixture = (name) => fs.readFileSync(path.join(FIXTURES, name), "utf8");

test("sums input, cache read and cache creation", () => {
  assert.deepEqual(transcriptTokens(fixture("transcript-usage-sum.jsonl")), {
    tokens: 85545,
    source: "usage",
  });
});

test("uses the last assistant entry", () => {
  assert.equal(transcriptTokens(fixture("transcript-last-assistant.jsonl")).tokens, 222);
});

test("ignores sidechain usage", () => {
  assert.equal(transcriptTokens(fixture("transcript-sidechain.jsonl")).tokens, 1001);
});

test("a compact boundary after the last usage wins", () => {
  assert.deepEqual(transcriptTokens(fixture("transcript-compact-after.jsonl")), {
    tokens: 25016,
    source: "compact_boundary",
  });
  assert.deepEqual(transcriptTokens(fixture("transcript-compact-before.jsonl")), {
    tokens: 30001,
    source: "usage",
  });
});

test("skips a partial trailing line only", () => {
  assert.equal(transcriptTokens(fixture("transcript-partial-trailing.jsonl")).tokens, 501);
  assert.throws(() => transcriptTokens(fixture("transcript-partial-middle.jsonl")), PuppetError);
});

test("reads CRLF line endings", () => {
  const crlf = fixture("transcript-usage-sum.jsonl").replace(/\r?\n/g, "\r\n");
  assert.equal(transcriptTokens(crlf).tokens, 85545);
});

test("no usage at all throws", () => {
  assert.throws(() => transcriptTokens(fixture("transcript-no-usage.jsonl")), PuppetError);
});

test("findTranscript finds exactly one match", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "puppet-find-"));
  try {
    const sid = "11111111-2222-3333-4444-555555555555";
    assert.throws(() => findTranscript(dir, sid), PuppetError);
    fs.mkdirSync(path.join(dir, "proj-a"));
    const a = path.join(dir, "proj-a", `${sid}.jsonl`);
    fs.writeFileSync(a, "");
    assert.equal(findTranscript(dir, sid), a);
    fs.mkdirSync(path.join(dir, "proj-b"));
    const b = path.join(dir, "proj-b", `${sid}.jsonl`);
    fs.writeFileSync(b, "");
    assert.throws(
      () => findTranscript(dir, sid),
      (e) => e instanceof PuppetError && e.message.includes(a) && e.message.includes(b),
    );
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("resolveWindow takes flag, then recorded, then env", () => {
  assert.deepEqual(resolveWindow({ flag: "1000000", recorded: 200000, env: "300000" }), {
    window: 1000000,
    source: "flag",
  });
  assert.deepEqual(resolveWindow({ recorded: 200000, env: "300000" }), {
    window: 200000,
    source: "recorded",
  });
  assert.deepEqual(resolveWindow({ env: "300000" }), { window: 300000, source: "env" });
});

test("resolveWindow refuses a missing or invalid window", () => {
  assert.throws(
    () => resolveWindow({}),
    (e) =>
      e instanceof PuppetError &&
      e.message.includes("--window") &&
      e.message.includes("PUPPET_CONTEXT_WINDOW"),
  );
  assert.throws(() => resolveWindow({ flag: "abc" }), PuppetError);
  assert.throws(() => resolveWindow({ flag: "0" }), PuppetError);
  assert.throws(() => resolveWindow({ env: "1.5" }), PuppetError);
});

test("percent rounds to one decimal", () => {
  assert.equal(percent(300000, 1000000), 30);
  assert.equal(percent(85545, 1000000), 8.6);
});

test("a compact boundary without postTokens is an error", () => {
  const text =
    fixture("transcript-usage-sum.jsonl") +
    '{"type":"system","subtype":"compact_boundary","isSidechain":false,"compactMetadata":{"trigger":"manual"}}\n';
  assert.throws(() => transcriptTokens(text), (e) => e instanceof PuppetError && /postTokens/.test(e.message));
});

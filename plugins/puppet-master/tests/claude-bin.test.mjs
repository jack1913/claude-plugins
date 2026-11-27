// The one resolver for the program that starts claude (skills/puppet-master/scripts/claude-bin.mjs), used by the helper
// and the mod. The platform, the PATH and the files it may look at are all fakes: nothing here starts a process.
import { test } from "node:test";
import assert from "node:assert/strict";

import { claudeProbePaths, pathFolders, resolveClaude, shimTarget } from "../skills/puppet-master/scripts/claude-bin.mjs";
import { listAgents } from "../skills/puppet-master/scripts/puppet.mjs";
import { makeDeps } from "./helpers.mjs";

// What npm writes for a package whose bin is a script (read from a real npm shim on a Windows machine).
const NPM_SHIM = [
  "@ECHO off", "GOTO start", ":find_dp0", "SET dp0=%~dp0", "EXIT /b", ":start", "SETLOCAL", "CALL :find_dp0", "",
  'IF EXIST "%dp0%\\node.exe" (', '  SET "_prog=%dp0%\\node.exe"', ") ELSE (", '  SET "_prog=node"', "  SET PATHEXT=%PATHEXT:;.JS;=;%", ")", "",
  'endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%"  "%dp0%\\node_modules\\@anthropic-ai\\claude-code\\cli.js" %*', "",
].join("\r\n");
const EXE_SHIM = '@ECHO off\r\nendLocal & "%dp0%\\node_modules\\@anthropic-ai\\claude-code\\bin\\claude.exe" %*\r\n';

const files = (map) => ({ exists: (p) => p in map, readText: (p) => map[p] ?? null });

test("PUPPET_CLAUDE_BIN wins, as given, on every platform", () => {
  for (const platform of ["win32", "linux", "darwin"]) {
    assert.deepEqual(resolveClaude({ env: { PUPPET_CLAUDE_BIN: "/x/my claude", PATH: "/a" }, platform }).argv, ["/x/my claude"]);
  }
});

test("outside Windows the bare name is left to the operating system, and the PATH is not read", () => {
  let looked = 0;
  const r = resolveClaude({ env: { PATH: "/a:/b" }, platform: "linux", exists: () => { looked++; return true; } });
  assert.deepEqual(r.argv, ["claude"]);
  assert.equal(looked, 0);
  assert.deepEqual(claudeProbePaths({ PATH: "/a:/b" }, "darwin"), []);
});

test("on Windows claude.exe on the PATH comes before claude.cmd, in PATH order", () => {
  const env = { Path: "C:\\one;C:\\two\\" };
  assert.deepEqual(pathFolders(env, "win32"), ["C:\\one", "C:\\two\\"]);
  const both = files({ "C:\\one\\claude.cmd": NPM_SHIM, "C:\\two\\claude.exe": "" });
  assert.deepEqual(resolveClaude({ env, platform: "win32", ...both }).argv, ["C:\\two\\claude.exe"]);
  const first = files({ "C:\\one\\claude.exe": "", "C:\\two\\claude.exe": "" });
  assert.deepEqual(resolveClaude({ env, platform: "win32", ...first }).argv, ["C:\\one\\claude.exe"]);
});

test("a claude.cmd shim is read, never run through a shell: its node script runs with node, its .exe directly", () => {
  const env = { PATH: "C:\\Users\\a b\\AppData\\Roaming\\npm" };
  const shim = "C:\\Users\\a b\\AppData\\Roaming\\npm\\claude.cmd";
  const js = resolveClaude({ env, platform: "win32", nodeBin: "N", ...files({ [shim]: NPM_SHIM }) });
  assert.deepEqual(js.argv, ["N", "C:\\Users\\a b\\AppData\\Roaming\\npm\\node_modules\\@anthropic-ai\\claude-code\\cli.js"]);
  const exe = resolveClaude({ env, platform: "win32", nodeBin: "N", ...files({ [shim]: EXE_SHIM }) });
  assert.deepEqual(exe.argv, ["C:\\Users\\a b\\AppData\\Roaming\\npm\\node_modules\\@anthropic-ai\\claude-code\\bin\\claude.exe"]);
  assert.match(exe.source, /claude\.cmd/);
});

test("a shim given as PUPPET_CLAUDE_BIN is read the same way; a shim with no program is a loud error", () => {
  const env = { PUPPET_CLAUDE_BIN: "C:\\n\\claude.cmd" };
  assert.deepEqual(resolveClaude({ env, platform: "win32", nodeBin: "N", ...files({ "C:\\n\\claude.cmd": NPM_SHIM }) }).argv,
    ["N", "C:\\n\\node_modules\\@anthropic-ai\\claude-code\\cli.js"]);
  assert.throws(() => resolveClaude({ env, platform: "win32", ...files({ "C:\\n\\claude.cmd": "@echo hi\r\n" }) }), /no program could be read from it.*PUPPET_CLAUDE_BIN/);
  assert.equal(shimTarget('"%dp0%\\node.exe" "%dp0%\\..\\x.js"', "C:\\n\\c.cmd").script, "C:\\x.js");
});

test("on Windows with nothing on the PATH the bare name comes back, so the launch fails loudly (no silent success)", () => {
  assert.deepEqual(resolveClaude({ env: { PATH: "C:\\nope" }, platform: "win32", ...files({}) }).argv, ["claude"]);
  assert.deepEqual(resolveClaude({ env: {}, platform: "win32" }).argv, ["claude"]);
});

test("the helper starts the resolved program: win32 + a claude.cmd shim runs node on the shim's script, with the claude arguments after it", () => {
  const folder = "C:\\npm";
  const t = makeDeps({ env: { PATH: folder }, handler: () => ({ stdout: "[]" }) });
  t.deps.platform = "win32";
  const real = t.deps.fs;
  t.deps.fs = { ...real, existsSync: (p) => p === `${folder}\\claude.cmd`, readFileSync: (p, enc) => (p === `${folder}\\claude.cmd` ? NPM_SHIM : real.readFileSync(p, enc)) };
  try {
    listAgents(t.deps);
    assert.equal(t.calls[0].cmd, process.execPath);
    assert.deepEqual(t.calls[0].args, ["C:\\npm\\node_modules\\@anthropic-ai\\claude-code\\cli.js", "agents", "--json"]);
  } finally {
    real.rmSync(t.dir, { recursive: true, force: true });
  }
});

test("the helper on Windows with claude.exe on the PATH runs that file; the failure text still names PUPPET_CLAUDE_BIN", () => {
  const t = makeDeps({
    env: { PATH: "C:\\bin" },
    handler: () => ({ code: 1, error: Object.assign(new Error("spawnSync C:\\bin\\claude.exe ENOENT"), { code: "ENOENT" }) }),
  });
  t.deps.platform = "win32";
  const real = t.deps.fs;
  t.deps.fs = { ...real, existsSync: (p) => p === "C:\\bin\\claude.exe" };
  try {
    assert.throws(() => listAgents(t.deps), /cannot run C:\\bin\\claude\.exe.*PUPPET_CLAUDE_BIN/);
    assert.equal(t.calls[0].cmd, "C:\\bin\\claude.exe");
  } finally {
    real.rmSync(t.dir, { recursive: true, force: true });
  }
});

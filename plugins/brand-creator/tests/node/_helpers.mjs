import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const BIN = path.join(ROOT, "bin", "brand-creator");
export const REQUIRE_ALL = process.env.BRAND_CREATOR_REQUIRE_ALL === "1";

// Every temporary folder this test process makes (tmpdir): removed when the process ends with every test passed, kept and named when one failed.
const MADE = [];
process.on("exit", (code) => {
  if (code === 0) for (const d of MADE) fs.rmSync(d, { recursive: true, force: true });
  else if (MADE.length) process.stderr.write(`a test failed, so its temporary folders are kept: ${MADE.join(" ")}\n`);
});

export function tmpdir(prefix = "bc-node-") {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  MADE.push(d);
  return d;
}

/** The set-up data directory the run was given (BRAND_CREATOR_DATA), or null. The tools never write into it: they get DATA, a data directory of
 *  this process's own, with every entry of SETUP_DATA as a symlink except the folders the tools write while they run (scratch, the names
 *  checker's cache). The tools write scratch output under <data>/scratch, one folder per project path, and the tests make new project paths on
 *  every run: aimed at a developer's own data directory, they would leave that scratch there for good. */
export const SETUP_DATA = process.env.BRAND_CREATOR_DATA && fs.existsSync(path.join(process.env.BRAND_CREATOR_DATA, "setup.json")) ? path.resolve(process.env.BRAND_CREATOR_DATA) : null;
export const DATA = SETUP_DATA && ownData(SETUP_DATA);
if (DATA) process.env.BRAND_CREATOR_DATA = DATA;   // for the tools a test starts itself and the tests that read the variable

function ownData(given) {
  const d = tmpdir("bc-node-data-");
  for (const e of fs.readdirSync(given)) if (e !== "scratch" && e !== "cache") fs.symlinkSync(path.join(given, e), path.join(d, e));
  return d;
}

/** Skip option for tests that need a set-up data directory; loud, and a failure when BRAND_CREATOR_REQUIRE_ALL=1. */
export function needSetup(t) {
  if (DATA) return false;
  const msg = "NOT VERIFIED: BRAND_CREATOR_DATA is unset or `brand-creator setup` has not been run there";
  if (REQUIRE_ALL) throw new Error(msg);
  console.error("!!! " + msg + " (skipping " + t.name + ")");
  t.skip(msg);
  return true;
}

let noSetupData = null;   // for commands that need a --data value but no dependencies, when no set-up data directory is given

export function bc(args, { cwd, env, data } = {}) {
  const d = data || DATA || (noSetupData ??= tmpdir("bc-node-data-"));
  return spawnSync(BIN, ["--data", d, ...args], { encoding: "utf8", cwd, env: { ...process.env, BRAND_CREATOR_TODAY: "2026-10-17", ...(env || {}) } });
}

const EX = "skills/brand-creator/references/examples/acme"; // the synthetic worked brand

export function makeProject() {
  const root = tmpdir();
  const r = bc(["new", "acme", "--name", "Acme", "--root", root]);
  if (r.status !== 0) throw new Error(r.stderr);
  const p = path.join(root, "acme");
  fs.mkdirSync(path.join(p, "rounds", "r1"), { recursive: true });
  fs.copyFileSync(path.join(ROOT, EX, "rounds/r1/board.html"), path.join(p, "rounds/r1/board.html"));
  fs.mkdirSync(path.join(p, "tokens"), { recursive: true });
  for (const f of fs.readdirSync(path.join(ROOT, EX, "tokens"))) fs.copyFileSync(path.join(ROOT, EX, "tokens", f), path.join(p, "tokens", f));
  fs.mkdirSync(path.join(p, "assets/logo"), { recursive: true });
  for (const f of fs.readdirSync(path.join(ROOT, EX, "assets/logo"))) fs.copyFileSync(path.join(ROOT, EX, "assets/logo", f), path.join(p, "assets/logo", f));
  return p;
}

export function mutateText(file, from, to) {
  const before = fs.readFileSync(file, "utf8");
  if (!before.includes(from)) throw new Error(`mutation did not apply: ${JSON.stringify(from)} not in ${file}`);
  const after = before.replace(from, to);
  if (after === before) throw new Error(`mutation did not change ${file}`);
  fs.writeFileSync(file, after);
  return before;
}

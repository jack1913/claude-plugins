// Shared helpers for brand-creator's Node scripts (render.mjs, build_tokens.mjs). ESM, Node >= 22.
// Same contract as _common.py (scripts/CONTRACT.md): project discovery, path confinement, JSON reports, exit codes.
//   exit codes: 0 pass, 1 gate failed, 2 usage error, 3 cannot run (missing dependency or platform)
// Dependencies live in <data>/node_modules (installed by `brand-creator setup`), never in the plugin root.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

export const EXIT = { PASS: 0, FAIL: 1, USAGE: 2, CANNOT: 3 };
export const STATE_FILE = "BRAND-STATE.md";

export class CliError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}
export function die(code, message) { throw new CliError(code, message); }

/** Run main(); turn CliError into a clean message and exit code. */
export async function mainGuard(main) {
  // Safety net: a leaked handle (an open server or browser) must never keep a finished command alive.
  const unref = (ms) => setTimeout(() => process.exit(process.exitCode ?? 0), ms).unref();
  try {
    const rc = await main();
    process.exitCode = rc ?? 0;
    unref(3000);
  } catch (e) {
    unref(3000);
    if (e instanceof CliError) {
      console.error(`error: ${e.message}`);
      process.exitCode = e.code;
    } else {
      console.error(e && e.stack ? e.stack : String(e));
      process.exitCode = EXIT.CANNOT;
    }
  }
}

export function pluginRoot() {
  return path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
}
export function pluginVersion() {
  try {
    return JSON.parse(fs.readFileSync(path.join(pluginRoot(), ".claude-plugin", "plugin.json"), "utf8")).version;
  } catch (e) {
    die(EXIT.CANNOT, `cannot read the plugin version from .claude-plugin/plugin.json: ${e.message}`);
  }
}
export function dataDir() {
  const d = (process.env.BRAND_CREATOR_DATA || "").trim();
  if (!d) die(EXIT.USAGE, "no data directory: pass --data <dir> to brand-creator (skills pass ${CLAUDE_PLUGIN_DATA}) or set BRAND_CREATOR_DATA");
  return path.resolve(d);
}

// ---------------------------------------------------------------- dependency loader (createRequire from <data>/node_modules)
const SETUP_HINT = "run /brand-creator:setup (or: brand-creator --data <dir> setup --yes)";

function resolveFromData(name) {
  const base = path.join(dataDir(), "node_modules") + path.sep;
  const pkgDir = path.join(base, name);
  if (!fs.existsSync(pkgDir)) die(EXIT.CANNOT, `${name} is not installed in ${base}; ${SETUP_HINT}`);
  const pkg = JSON.parse(fs.readFileSync(path.join(pkgDir, "package.json"), "utf8"));
  // Prefer the ESM entry (exports["."].import) so named exports and default exports behave the same everywhere.
  let entry = pkg.exports && (typeof pkg.exports === "string" ? pkg.exports : (pkg.exports["."] ?? pkg.exports));
  if (entry && typeof entry === "object") entry = entry.import ?? (typeof entry.node === "object" ? entry.node.import : undefined) ?? entry.default;
  if (entry && typeof entry === "object") entry = entry.default ?? entry.import;
  if (typeof entry === "string" && fs.existsSync(path.join(pkgDir, entry))) return path.join(pkgDir, entry);
  try {
    return createRequire(base).resolve(name);
  } catch (e) {
    const fallback = pkg.module || pkg.main;
    if (!fallback) die(EXIT.CANNOT, `cannot resolve ${name} in ${pkgDir}: ${e.message}`);
    return path.join(pkgDir, fallback);
  }
}

/** Import a dependency from <data>/node_modules. Returns the module namespace, with a CJS default's keys merged in. */
export async function loadDep(name) {
  const file = resolveFromData(name);
  const m = await import(pathToFileURL(file).href);
  return m.default && typeof m.default === "object" ? { ...m.default, ...m } : m;
}

/**
 * Linux: the shared libraries a program needs and the system lacks (`ldd` prints "libnss3.so => not found"). Chromium's headless shell
 * links against a dozen of them (nss, gbm, atk, cups, drm ...) that a minimal image or server does not have; Playwright then only says
 * the browser "has been closed", and re-running setup cannot help. -> sorted list of names; [] when none is missing, on other systems,
 * or when ldd is not there. `run` and `platform` are injectable for the test.
 */
export function missingSharedLibs(exe, { run = spawnSync, platform = process.platform } = {}) {
  if (platform !== "linux" || !exe) return [];
  const r = run("ldd", [exe], { encoding: "utf8", timeout: 20000 });
  if (!r || r.error || typeof r.stdout !== "string") return [];
  return [...new Set([...r.stdout.matchAll(/^\s*(\S+)\s+=>\s+not found\s*$/gm)].map((m) => m[1]))].sort();
}

/** The headless shell binary setup installed under <browsersPath>/chromium_headless_shell-<revision>/ (null when it is not there): `chrome-linux/headless_shell`
 *  on Linux, `chrome-headless-shell-<platform>/chrome-headless-shell` elsewhere. */
export function findHeadlessShell(browsersPath, revision) {
  const root = path.join(browsersPath || "", `chromium_headless_shell-${revision}`);
  const walk = (dir, depth) => {
    let entries = [];
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return null; }
    for (const e of entries) if (e.isFile() && (e.name === "headless_shell" || e.name === "chrome-headless-shell")) return path.join(dir, e.name);
    if (depth > 0) for (const e of entries) if (e.isDirectory()) { const f = walk(path.join(dir, e.name), depth - 1); if (f) return f; }
    return null;
  };
  return walk(root, 2);
}

export function readSetup() {
  const f = path.join(dataDir(), "setup.json");
  if (!fs.existsSync(f)) die(EXIT.CANNOT, `setup has not been run (no ${f}); ${SETUP_HINT}`);
  return JSON.parse(fs.readFileSync(f, "utf8"));
}

// ---------------------------------------------------------------- project discovery + confinement
export function findProject(arg, cwd = process.cwd()) {
  if (arg) {
    const p = path.resolve(arg);
    if (!fs.existsSync(path.join(p, STATE_FILE))) die(EXIT.USAGE, `no brand project at ${p} (${STATE_FILE} not found); pass --project <dir>`);
    return fs.realpathSync(p);
  }
  let cur = fs.realpathSync(path.resolve(cwd));
  for (;;) {
    if (fs.existsSync(path.join(cur, STATE_FILE))) return cur;
    const up = path.dirname(cur);
    if (up === cur) break;
    cur = up;
  }
  die(EXIT.USAGE, "no brand project found; pass --project");
}

function realLenient(p) {
  let cur = path.resolve(p);
  const tail = [];
  while (!fs.existsSync(cur) && path.dirname(cur) !== cur) { tail.unshift(path.basename(cur)); cur = path.dirname(cur); }
  return path.join(fs.realpathSync(cur), ...tail);
}
function isInside(root, p) {
  const r = path.relative(root, p);
  return r === "" || (!r.startsWith("..") && !path.isAbsolute(r));
}
/** Resolve p (relative = inside the project) and require it to stay inside the project. */
export function confine(project, p, what = "path") {
  const root = fs.realpathSync(project);
  const abs = realLenient(path.isAbsolute(p) ? p : path.join(root, p));
  if (!isInside(root, abs)) die(EXIT.USAGE, `${what} ${p} is outside the project ${root}; brand-creator only writes inside the project`);
  return abs;
}
export function outsideProject(project, p, what = "path") {
  const root = fs.realpathSync(project);
  const abs = realLenient(p);
  if (isInside(root, abs)) die(EXIT.USAGE, `${what} ${p} must be outside the project (scratch output); use the data dir or a temp folder`);
  return abs;
}
export const rel = (project, p) => path.relative(fs.realpathSync(project), p).split(path.sep).join("/");

export function scratchDir(project, name) {
  const slug = path.basename(project).toLowerCase().replace(/[^a-z0-9._-]+/g, "-");
  const h = crypto.createHash("sha256").update(project).digest("hex").slice(0, 8);
  const d = path.join(dataDir(), "scratch", `${slug}-${h}`, name);
  try {
    fs.mkdirSync(d, { recursive: true });
  } catch (e) {
    // a read-only data folder (a sandbox that may not write it, as in a `claude plugin eval` run) is a missing prerequisite
    die(EXIT.CANNOT, `cannot write scratch output under the data directory (${d}): ${e.code || e.message}. Pass --data <a writable folder that setup prepared>; ${SETUP_HINT}`);
  }
  return d;
}

export const sha256 = (buf) => crypto.createHash("sha256").update(buf).digest("hex");
export const sha256File = (p) => sha256(fs.readFileSync(p));

/** Put-on-byte-change. Returns true when the file was (re)written. */
export function writeIfChanged(file, data) {
  if (fs.existsSync(file) && Buffer.compare(fs.readFileSync(file), Buffer.from(data)) === 0) return false;
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = file + ".tmp-bc";
  fs.writeFileSync(tmp, data);
  fs.renameSync(tmp, file);
  return true;
}

// ---------------------------------------------------------------- BRAND-STATE.md (read-only, top-level scalars)
function splitComment(rest) {
  let q = "";
  for (let i = 0; i < rest.length; i++) {
    const ch = rest[i];
    if (q) { if (ch === q && rest[i - 1] !== "\\") q = ""; }
    else if (ch === '"' || ch === "'") q = ch;
    else if (ch === "#" && (i === 0 || /\s/.test(rest[i - 1]))) return rest.slice(0, i).trim();
  }
  return rest.trim();
}

export function readStateTop(project) {
  const text = fs.readFileSync(path.join(project, STATE_FILE), "utf8").split("\n");
  if (text[0].trim() !== "---") die(EXIT.USAGE, `${STATE_FILE} has no frontmatter`);
  const out = {};
  for (let i = 1; i < text.length && text[i].trim() !== "---"; i++) {
    const m = /^([A-Za-z0-9_.-]+):(?:\s+(.*))?$/.exec(text[i]);
    if (!m) continue;
    let v = splitComment(m[2] ?? "");
    if (/^".*"$/.test(v)) { try { v = JSON.parse(v); } catch { v = v.slice(1, -1); } }
    else if (/^'.*'$/.test(v)) v = v.slice(1, -1);
    out[m[1]] = v;
  }
  return out;
}

/** Bullet items under a heading starting with "Forbidden" in brief/BRIEF.md and research/cliches.md. */
export function forbiddenTerms(project) {
  const terms = [];
  for (const relp of ["brief/BRIEF.md", "research/cliches.md"]) {
    const f = path.join(project, relp);
    if (!fs.existsSync(f)) continue;
    let inSec = false;
    for (const ln of fs.readFileSync(f, "utf8").split("\n")) {
      if (/^#{1,6}\s+/.test(ln)) { inSec = /^#{1,6}\s+Forbidden\b/i.test(ln); continue; }
      const m = /^\s*[-*]\s+(.+?)\s*$/.exec(ln);
      if (inSec && m) {
        const t = m[1].trim().replace(/^`|`$/g, "").trim();
        if (t && !t.startsWith("<!--") && !terms.includes(t)) terms.push(t);
      }
    }
  }
  return terms;
}

// ---------------------------------------------------------------- reports
export class Report {
  constructor(tool, project, inputs = [], renderer = null) {
    this.tool = tool; this.project = project; this.inputs = inputs; this.results = []; this.extra = {}; this.renderer = renderer;
  }
  add(id, status, label = "", extra = {}) {
    if (!["pass", "fail", "warn", "info", "skipped"].includes(status)) throw new Error(`bad status ${status}`);
    this.results.push({ id, status, label, ...extra });
  }
  get status() {
    const s = new Set(this.results.map((r) => r.status));
    if (s.has("fail")) return "fail";
    if (s.has("skipped") || this.results.length === 0) return "not-verified";
    return "pass";
  }
  exitCode() { return { pass: EXIT.PASS, fail: EXIT.FAIL, "not-verified": EXIT.CANNOT }[this.status]; }
  write() {
    const recs = [...this.inputs].map((p) => path.resolve(p)).filter((p) => fs.existsSync(p))
      .map((p) => ({ path: rel(this.project, fs.realpathSync(p)), sha256: sha256File(p) }))
      .sort((a, b) => (a.path < b.path ? -1 : 1));
    const h = crypto.createHash("sha256");
    for (const r of recs) h.update(`${r.path}\0${r.sha256}\n`);
    const doc = {
      tool: this.tool, version: pluginVersion(), inputs_sha: h.digest("hex"), inputs: recs,
      renderer: this.renderer || readStateTop(this.project).renderer || "resvg (default)",
      results: this.results, status: this.status, ...this.extra,
    };
    const out = confine(this.project, path.join("assets", "_checks", `${this.tool}.json`), "report");
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, JSON.stringify(doc, null, 2) + "\n");
    return out;
  }
  finish() {
    const out = this.write();
    const tag = { pass: "PASS", fail: "FAIL", warn: "WARN", info: "INFO", skipped: "SKIP" };
    for (const r of this.results) {
      console.log(`[${tag[r.status]}] ${r.id}${r.label ? ` (${r.label})` : ""}${r.detail ? `: ${r.detail}` : ""}`);
    }
    const n = (k) => this.results.filter((r) => r.status === k).length;
    console.log(`${this.tool}: ${this.status.toUpperCase()}  (${n("pass")} pass, ${n("fail")} fail, ${n("warn")} warn, ${n("skipped")} not verified)`);
    console.log(`report: ${out}`);
    return this.exitCode();
  }
}

// Shared test scaffolding: a temp config dir, a fake `deps` whose `run` is scripted,
// and the Task 1 fixtures. No test starts a real `claude` process.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const FIXTURES = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");
export const fixture = (name) => fs.readFileSync(path.join(FIXTURES, name), "utf8");

// One background agent shaped like the captured probe, renamed and re-identified.
export function agent(name, n, extra = {}) {
  const base = JSON.parse(fixture("agents.json"))[0];
  const id = String(n).padStart(8, "a");
  return {
    ...base,
    id,
    sessionId: `${id}-0000-4000-8000-000000000000`,
    name,
    ...extra,
  };
}

// handler(args, opts, calls) returns {code, stdout, stderr} or undefined for the default
// (`agents --json` answers from `agents`, everything else exits 0).
export function makeDeps({ agents = [], handler = () => undefined, env = {}, now } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "puppet-test-"));
  const out = [];
  const err = [];
  const calls = [];
  const deps = {
    env: {
      CLAUDE_CONFIG_DIR: dir,
      PUPPET_STATE: path.join(dir, "puppet-master", "workers.json"),
      ...env,
    },
    out: (l) => out.push(l),
    err: (l) => err.push(l),
    now: now ?? (() => new Date("2026-01-01T00:00:00Z")),
    fs,
    agents,
    run(cmd, args, opts = {}) {
      calls.push({ cmd, args, opts });
      const r = handler(args, opts, calls);
      if (r) return { code: 0, stdout: "", stderr: "", ...r };
      if (args[0] === "agents") return { code: 0, stdout: JSON.stringify(deps.agents), stderr: "" };
      return { code: 0, stdout: "", stderr: "" };
    },
  };
  return {
    deps,
    dir,
    out,
    err,
    calls,
    writeTranscript(sessionId, text, project = "x") {
      const p = path.join(dir, "projects", project, `${sessionId}.jsonl`);
      fs.mkdirSync(path.dirname(p), { recursive: true });
      fs.writeFileSync(p, text);
      return p;
    },
    writeRegistry(reg) {
      fs.mkdirSync(path.dirname(deps.env.PUPPET_STATE), { recursive: true });
      fs.writeFileSync(deps.env.PUPPET_STATE, JSON.stringify(reg));
    },
    readRegistry() {
      return JSON.parse(fs.readFileSync(deps.env.PUPPET_STATE, "utf8"));
    },
    cleanup() {
      fs.rmSync(dir, { recursive: true, force: true });
    },
  };
}

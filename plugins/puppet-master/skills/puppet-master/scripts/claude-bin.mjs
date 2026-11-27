// claude-bin.mjs: which program starts `claude`, shared by the helper (puppet.mjs) and the mod (hooks/puppet-mod.js).
// No shell ever runs: a value from the user is never put into a command string.
//
// Order:
//   1. PUPPET_CLAUDE_BIN, exactly as given (a `.cmd` or `.bat` given here is read like a shim, see 3).
//   2. On win32 only: `claude.exe` in a PATH folder, in PATH order.
//   3. On win32 only: `claude.cmd` in a PATH folder. An npm shim cannot start without a shell, so its text is read:
//      npm writes `"%dp0%\<path>" %*`, the real program. A `.exe` there is run directly, anything else with node.
//   4. Otherwise the bare name `claude`, left to the operating system. On win32 with nothing found this is also the
//      result: the launch then fails loudly and the caller names PUPPET_CLAUDE_BIN.
//
// Pure: the caller passes what it can look at (`exists`, `readText`, synchronous), so a test fakes the platform and the
// PATH, and the mod (whose file calls are async) reads the paths from `claudeProbePaths` first.

// No imports at all: the mod imports this file, and `claude plugin validate` lets a hooks module import only its own
// files by relative path, so the Windows path handling is written out here instead of taken from node:path.

const SHIM = /\.(?:cmd|bat)$/i;

// A Windows path from a folder and segments: backslashes, "." dropped, ".." going up, no doubled separators.
function winJoin(dir, ...parts) {
  const out = String(dir).split(/[\\/]+/).filter((s, i) => s !== "" || i === 0);
  for (const seg of parts.flatMap((p) => String(p).split(/[\\/]+/))) {
    if (seg === "" || seg === ".") continue;
    if (seg === ".." && out.length > 1) out.pop();
    else out.push(seg);
  }
  return out.join("\\");
}
const winDirname = (p) => String(p).replace(/[\\/][^\\/]*$/, "");

// The PATH folders, in order. Windows names the variable `Path`; a plain object (a test, the mod) keeps the case it was given.
export function pathFolders(env, platform) {
  const raw = env.PATH ?? env.Path ?? env.path ?? "";
  const sep = platform === "win32" ? ";" : ":";
  return String(raw).split(sep).map((p) => p.replace(/^"(.*)"$/, "$1")).filter(Boolean);
}

// Every file `resolveClaude` may look at, so an async caller can read them before the call.
export function claudeProbePaths(env, platform) {
  const override = env.PUPPET_CLAUDE_BIN;
  if (override) return SHIM.test(override) ? [override] : [];
  if (platform !== "win32") return [];
  const folders = pathFolders(env, platform);
  return [...folders.map((d) => winJoin(d, "claude.exe")), ...folders.map((d) => winJoin(d, "claude.cmd"))];
}

// What a `.cmd` npm shim runs: { file } to run directly, { script } to run with node, or null when its text names no program.
export function shimTarget(text, shimPath) {
  const found = [...String(text).matchAll(/"%dp0%[\\/]([^"%]+)"/gi)].map((m) => m[1]).filter((p) => !/^node(?:\.exe)?$/i.test(p));
  if (!found.length) return null;
  const rel = found[found.length - 1].replace(/\\/g, "/");
  const full = winJoin(winDirname(shimPath), rel);
  return /\.exe$/i.test(rel) ? { file: full } : { script: full };
}

// The argv prefix that starts claude: { argv: [file, ...], source }. `nodeBin` runs a shim's node script.
export function resolveClaude({ env, platform, exists = () => false, readText = () => null, nodeBin = process.execPath }) {
  const fromShim = (p, source) => {
    const target = shimTarget(readText(p) ?? "", p);
    if (!target) {
      throw new Error(`cannot run ${p}: it is a shim and no program could be read from it (set PUPPET_CLAUDE_BIN to claude.exe or to the program the shim runs)`);
    }
    return { argv: target.file ? [target.file] : [nodeBin, target.script], source };
  };
  const override = env.PUPPET_CLAUDE_BIN;
  if (override) return SHIM.test(override) ? fromShim(override, "PUPPET_CLAUDE_BIN") : { argv: [override], source: "PUPPET_CLAUDE_BIN" };
  if (platform === "win32") {
    const probe = claudeProbePaths(env, platform);
    const exe = probe.find((p) => p.endsWith("claude.exe") && exists(p));
    if (exe) return { argv: [exe], source: "PATH (claude.exe)" };
    const cmd = probe.find((p) => p.endsWith("claude.cmd") && exists(p));
    if (cmd) return fromShim(cmd, "PATH (claude.cmd)");
  }
  return { argv: ["claude"], source: "default" };
}

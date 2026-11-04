// puppet-mod.js: the puppet-master mod. In a session where it was switched on, it compacts
// that session, or (for a worker only) clears it, when the master's helper writes a request
// for it. Off unless switched on: a session does nothing here until the user said yes at
// the session-start question, set `self_compact` to `on`, or the master's helper wrote an
// opt-in for that session (`spawn --self-compact`, `adopt --self-compact`).
//
// What it reads and writes, all in one folder (`<config dir>/puppet-master/mod`, or
// PUPPET_MOD_DIR): heartbeat/<session>.json (written every tick), optin/<session>.json and
// roles/<session>.json (the helper's), requests/<session>.json (the helper's), acks/<nonce>.json.
// It calls $.session.id, usage, compact, $.command.run, $.ui.ask, $.config.list and set, $.fs,
// $.env, and one $.process.run (`claude agents --json`, to learn whether it runs in a window
// or a worker before it asks). No shell, no network.

const VERSION = "0.1.0";
const TICK_MS = 3000;
const ASK_DELAY_MS = 5000;
const ASK_TIMEOUT_MS = 20000;
// A request older than this is answered "stale" and never run.
const REQUEST_MAX_AGE_MS = 5 * 60 * 1000;
// A prompt submitted within this long ago, with no turn started yet, counts as work arriving.
const PROMPT_GRACE_MS = 10000;
const CONFIG_KEY = "puppet-master.self_compact";

const ASK_QUESTION =
  "puppet-master: may the master compact this session when it asks (a worker session it may also clear between jobs)?";
const ASK_YES = "Yes, this session (Recommended)";
const ASK_ALWAYS = "Yes, always on this machine";
const ASK_NO = "No";
const ASK_NEVER = "No, and don't ask again on this machine";

const slash = (p) => String(p).replace(/\\/g, "/").replace(/\/+$/, "");

async function modDir($, st) {
  if (st.dir) return st.dir;
  const override = await $.env.get("PUPPET_MOD_DIR");
  if (override) return (st.dir = slash(override));
  const cfg = await $.env.get("CLAUDE_CONFIG_DIR");
  if (cfg) return (st.dir = `${slash(cfg)}/puppet-master/mod`);
  const home = (await $.env.get("USERPROFILE")) || (await $.env.get("HOME"));
  if (!home) throw new Error("no CLAUDE_CONFIG_DIR, USERPROFILE or HOME: cannot find the puppet-master mod folder");
  return (st.dir = `${slash(home)}/.claude/puppet-master/mod`);
}

// A JSON file's value; null when it is missing, empty or `{}` (a handled request is blanked).
async function readJson($, file) {
  if (!(await $.fs.exists(file))) return null;
  const text = (await $.fs.read(file)).trim();
  if (text === "" || text === "{}") return null;
  try {
    return JSON.parse(text);
  } catch (err) {
    throw new Error(`${file} is not valid JSON: ${err.message}`);
  }
}

const writeJson = ($, file, value) => $.fs.write(file, `${JSON.stringify(value, null, 2)}\n`);

// The `self_compact` row: ask (default), on or off. A missing row is "off": silence never runs.
async function readMode($) {
  const row = (await $.config.list()).find((r) => r.key === CONFIG_KEY);
  if (!row) return "off";
  return row.value === "on" || row.value === "off" || row.value === "ask" ? row.value : "off";
}

export function register(on) {
  const st = {
    dir: null,
    timer: false,
    asked: false,
    askedYes: false,
    askState: null,
    startedAt: null,
    turnRunning: false,
    promptAt: null,
    lastError: null,
    loggedErrors: new Set(),
    handled: new Set(),
  };

  on("turn.start", async ($, e, next) => {
    st.turnRunning = true;
    st.promptAt = null;
    return next(e);
  });
  on("turn.complete", async ($, e, next) => {
    st.turnRunning = false;
    st.promptAt = null;
    return next(e);
  });
  // Observes only: whatever happens here, the user's prompt goes on.
  on("prompt.submit", async ($, e, next) => {
    try {
      st.promptAt = await $.clock.now();
    } catch (err) {
      await fail($, st, err);
    }
    return next(e);
  });

  on("session.start", async ($, e, next) => {
    if (!st.timer) {
      st.timer = true;
      st.startedAt = await $.clock.now();
      $.clock.every(TICK_MS, () => tick($, st));
    }
    // The question comes after the start, never inside it: the start waits on its hooks.
    if (!st.asked && e.isInteractive && e.surface === "terminal") {
      st.asked = true;
      $.clock.after(ASK_DELAY_MS, () => askAtStart($, st));
    }
    return next(e);
  });
}

async function fail($, st, err) {
  st.lastError = String((err && err.message) || err);
  if (st.loggedErrors.has(st.lastError)) return;
  st.loggedErrors.add(st.lastError);
  $.ui.log(`puppet-master mod: ${st.lastError}`);
}

// This session's own `kind` in `claude agents --json`: interactive (a window the user
// opened) or background (a worker), null when it cannot be told. A background session
// cannot answer a dialog and would sit `waiting` behind it (probe, 2026-11-04), and
// `isInteractive` and `surface` are true there too, so they say nothing.
async function ownKind($, sid) {
  const bin = (await $.env.get("PUPPET_CLAUDE_BIN")) || "claude";
  const r = await $.process.run([bin, "agents", "--json"], { timeoutMs: 20000 });
  if (r.exitCode !== 0) throw new Error(`claude agents --json exited ${r.exitCode}`);
  const own = JSON.parse(r.stdout).find((a) => a.sessionId === sid);
  return own ? (own.kind ?? null) : null;
}

// The session-start question. Only in mode `ask`, only in a window the user opened, and not
// for a session the master already opted in. A dismissal, a rejection or no answer in time
// is "off for this session".
async function askAtStart($, st) {
  try {
    if ((await readMode($)) !== "ask") return;
    const dir = await modDir($, st);
    const sid = await $.session.id();
    if ((await readJson($, `${dir}/optin/${sid}.json`)) || (await readJson($, `${dir}/roles/${sid}.json`))) {
      st.askState = "skipped-adopted";
      return;
    }
    let kind = null;
    try {
      kind = await ownKind($, sid);
    } catch (err) {
      await fail($, st, `cannot tell whether this session is a window or a worker: ${(err && err.message) || err}`);
    }
    if (kind !== "interactive") {
      st.askState = kind === "background" ? "skipped-background" : "skipped-unknown";
      return;
    }
    let answer;
    try {
      answer = await Promise.race([
        $.ui.ask(ASK_QUESTION, [ASK_YES, ASK_ALWAYS, ASK_NO, ASK_NEVER]),
        $.clock.sleep(ASK_TIMEOUT_MS).then(() => null),
      ]);
    } catch (err) {
      await fail($, st, `the start question was not answered: ${(err && err.message) || err}`);
      return;
    }
    st.askState = answer === null ? "timed-out" : answer === ASK_YES ? "yes" : answer === ASK_ALWAYS ? "always" : answer === ASK_NO ? "no" : answer === ASK_NEVER ? "never" : "other";
    if (answer === ASK_YES) st.askedYes = true;
    else if (answer === ASK_ALWAYS) {
      st.askedYes = true;
      const r = await $.config.set({ key: CONFIG_KEY, value: "on" });
      if (r && r.deny) await fail($, st, `could not save self_compact=on: ${r.deny}`);
    } else if (answer === ASK_NEVER) {
      const r = await $.config.set({ key: CONFIG_KEY, value: "off" });
      if (r && r.deny) await fail($, st, `could not save self_compact=off: ${r.deny}`);
    }
  } catch (err) {
    await fail($, st, err);
  }
}

async function tick($, st) {
  try {
    await poll($, st);
  } catch (err) {
    await fail($, st, err);
  }
}

async function poll($, st) {
  const dir = await modDir($, st);
  const sid = await $.session.id();
  const now = await $.clock.now();
  const mode = await readMode($);
  const optin = await readJson($, `${dir}/optin/${sid}.json`);
  const role = (await readJson($, `${dir}/roles/${sid}.json`))?.role ?? null;
  // `off` is the user's veto: it beats a session answer and the master's opt-in alike.
  let source = null;
  if (mode !== "off") {
    if (st.askedYes) source = "asked";
    else if (mode === "on") source = "config";
    else if (optin) source = "optin";
  }
  await writeJson($, `${dir}/heartbeat/${sid}.json`, {
    sessionId: sid,
    version: VERSION,
    startedAt: st.startedAt,
    beat: now,
    mode,
    enabled: source !== null,
    source,
    role,
    ask: st.askState,
    turnRunning: st.turnRunning,
    lastError: st.lastError,
  });

  const file = `${dir}/requests/${sid}.json`;
  const req = await readJson($, file);
  if (req === null) return;
  const blank = () => $.fs.write(file, "{}");
  const ack = (body) => writeJson($, `${dir}/acks/${req.nonce}.json`, { nonce: req.nonce, action: req.action, sessionId: sid, at: now, ...body });

  if (typeof req.nonce !== "string" || !/^[A-Za-z0-9-]{4,64}$/.test(req.nonce) || !["compact", "clear"].includes(req.action)) {
    await blank();
    throw new Error(`ignored a request with no valid nonce or action in ${file}`);
  }
  if (st.handled.has(req.nonce)) return blank();
  if (req.sessionId !== sid) {
    st.handled.add(req.nonce);
    await ack({ ok: false, outcome: "wrong-session", detail: `request is for ${req.sessionId}` });
    return blank();
  }
  if (typeof req.requestedAt !== "number" || now - req.requestedAt > REQUEST_MAX_AGE_MS) {
    st.handled.add(req.nonce);
    await ack({ ok: false, outcome: "stale", detail: st.lastError ?? undefined });
    return blank();
  }
  if (source === null) {
    st.handled.add(req.nonce);
    await ack({ ok: false, outcome: "not-enabled", detail: `self_compact is ${mode} and no opt-in for this session` });
    return blank();
  }

  if (req.action === "compact") {
    let before;
    try {
      before = (await $.session.usage()).context.tokens ?? null;
      const r = await $.session.compact({ instructions: typeof req.focus === "string" ? req.focus : "" });
      st.handled.add(req.nonce);
      if (r && r.skip) await ack({ ok: false, outcome: "vetoed", detail: "a hook vetoed the compaction" });
      else await ack({ ok: true, outcome: "compacted", tokensBefore: r?.tokensBefore ?? before, tokensAfter: r?.tokensAfter ?? null });
      return blank();
    } catch (err) {
      // A turn is running: keep the request and retry on the next tick, until it is stale.
      st.lastError = `compact rejected: ${(err && err.message) || err}`;
      return;
    }
  }

  // clear: a worker the master named, idle right now, never queued.
  if (role !== "worker" || req.role !== "worker") {
    st.handled.add(req.nonce);
    await ack({ ok: false, outcome: "refused-role", detail: `role ${role ?? "unknown"}: clear is for a worker the master adopted` });
    return blank();
  }
  const promptSoon = st.promptAt !== null && now - st.promptAt < PROMPT_GRACE_MS;
  if (st.turnRunning || promptSoon) {
    st.handled.add(req.nonce);
    await ack({ ok: false, outcome: "busy", detail: "a turn is running or a prompt just arrived; not clearing" });
    return blank();
  }
  st.handled.add(req.nonce);
  await blank();
  let outcome;
  try {
    outcome = await $.command.run({ command: "clear", args: "" });
  } catch (err) {
    await ack({ ok: false, outcome: "rejected", detail: String((err && err.message) || err) });
    return;
  }
  const newId = await $.session.id();
  // The cleared session has a new id: carry the opt-in and the role over to it.
  if (newId !== sid) {
    if (optin) await writeJson($, `${dir}/optin/${newId}.json`, optin);
    await writeJson($, `${dir}/roles/${newId}.json`, { role });
  }
  await ack({ ok: true, outcome: "cleared", newSessionId: newId, text: outcome?.text ?? "" });
}

#!/usr/bin/env node
// board-server.mjs: serves the task page on 127.0.0.1 and takes the user's answers from it.
//
//   node board-server.mjs --dir <board folder> --session <master session id> --mod-dir <puppet-master mod folder> [--port 8747]
//
// What it does, and nothing else:
//   GET  /              the board's index.html, with this run's token written into <meta id="pmtoken">
//   GET  /tasks.js      the board's tasks.js (the only other file of the board folder it serves)
//   GET  /file/<path>   a file under the folder of a report or ask link listed in tasks.js (html, css, images ...),
//                       sandboxed, so a report cannot read the page's token (file:// links do not open from an http page)
//   GET  /ping          { ok, session, modAlive, enabled }: whether the master's mod answered in the last 15 s
//   GET  /ack/<nonce>   { acked, outcome }: the mod's answer to a sent message
//   POST /say           one message, JSON; checked by `checkSay` below; written as one file in
//                       <mod folder>/inbox/<session>/<nonce>.json, which the master's mod picks up (hooks/puppet-mod.js)
// Security (T53 design, section 5): binds 127.0.0.1 only; every request must carry Host 127.0.0.1:<port>
// (against DNS rebinding); a POST must also carry the run's random token (header x-pm-token), an Origin equal to the
// server's own, Content-Type application/json, and a body of at most 4 KB (against other web pages); the message
// kinds are a closed set and the line is built here from validated fields, never taken from the page.
// A page message is the user's instruction, never the approval of an outward step: commit, push and Jira changes
// arrive only as "request" lines the master asks about in its own window.
// Node built-ins only.

import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

export const LINE_MAX = 2000;
export const NOTES_MAX = 1500;
export const CHOICE_MAX = 300;
export const BODY_MAX = 4096;
export const STALE_MS = 5 * 60 * 1000;
export const BEAT_MS = 15000;
const ACTIONS = ["start", "wait", "commit", "push", "jira"];
const REQUESTS = ["commit", "push", "jira"];
const ASK_RE = /^A\d{1,6}$/;
const TASK_RE = /^T\d{1,6}[a-z]?$/;
const NONCE_RE = /^[A-Za-z0-9-]{4,64}$/;

// One line, the same one the page builds for Copy (index.html `buildLine`; a test holds the two equal).
export function buildLine(m) {
  const one = (s) => String(s == null ? "" : s).replace(/\s*[\r\n]+\s*/g, " / ").replace(/\s+/g, " ").trim();
  if (m.kind === "action") {
    const base = `${m.task} ${REQUESTS.includes(m.action) ? "request " : ""}${m.action} (task page)`;
    return REQUESTS.includes(m.action) ? `${base}: the master asks in its window` : base;
  }
  const head = `${m.ask} ${m.kind === "grill" ? "grill answer" : "answer"} (task page)`;
  if (m.skip) return `${head}: skipped`;
  const parts = [];
  const choice = one(m.choice).replace(/"/g, "'");
  if (choice) parts.push(`"${choice}"`);
  const notes = one(m.notes);
  if (notes) parts.push(`notes: ${notes}`);
  return parts.length ? `${head}: ${parts.join(" — ")}` : head;
}

const str = (v, max, name) => {
  if (v == null || v === "") return "";
  if (typeof v !== "string") throw new Error(`${name} must be text`);
  if ([...v].length > max) throw new Error(`${name} is longer than ${max} characters`);
  return v;
};

// A message from the page, checked field by field. Returns { msg } (kind and fields) or { error }.
export function checkSay(body) {
  try {
    if (!body || typeof body !== "object" || Array.isArray(body)) throw new Error("the body must be a JSON object");
    const kind = body.kind;
    if (kind === "answer" || kind === "grill") {
      if (typeof body.ask !== "string" || !ASK_RE.test(body.ask)) throw new Error("ask must look like A12");
      const msg = { kind, ask: body.ask, choice: str(body.choice, CHOICE_MAX, "choice"), notes: str(body.notes, NOTES_MAX, "notes"), skip: body.skip === true };
      if (!msg.skip && !msg.choice && !msg.notes) throw new Error("an answer needs an option or notes");
      if (msg.skip && (msg.choice || msg.notes)) throw new Error("a skip carries no option or notes");
      if (typeof body.task === "string" && TASK_RE.test(body.task)) msg.task = body.task;
      return { msg };
    }
    if (kind === "action") {
      if (typeof body.task !== "string" || !TASK_RE.test(body.task)) throw new Error("task must look like T12");
      if (!ACTIONS.includes(body.action)) throw new Error(`action must be one of ${ACTIONS.join(", ")}`);
      return { msg: { kind, task: body.task, action: body.action } };
    }
    throw new Error("kind must be answer, grill or action");
  } catch (err) {
    return { error: err.message };
  }
}

const TYPES = { ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
  ".svg": "image/svg+xml", ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8" };

const slash = (p) => String(p).replace(/\\/g, "/");

// The folders a report or an ask link in tasks.js lives in: /file/ serves only below these.
export function reportDirs(tasksJs) {
  const dirs = new Set();
  const add = (p) => {
    if (typeof p !== "string" || /^https?:\/\//.test(p) || !/^([A-Za-z]:[\\/]|\/)/.test(p)) return;
    dirs.add(path.dirname(slash(p).replace(/#.*$/, "")));
  };
  for (const m of tasksJs.matchAll(/"(?:path|prUrl)"\s*:\s*"((?:[^"\\]|\\.)*)"|\bpath\s*:\s*"((?:[^"\\]|\\.)*)"/g)) {
    try { add(JSON.parse(`"${m[1] ?? m[2]}"`)); } catch { /* not a string literal */ }
  }
  return [...dirs];
}

export function createBoard({ dir, session, modDir, port = 0, now = () => Date.now(), maxPerMinute = 30 }) {
  if (!dir || !session || !modDir) throw new Error("createBoard needs dir, session and modDir");
  if (!/^[\w.-]{1,80}$/.test(session)) throw new Error("session is not a plain session id");
  const token = crypto.randomBytes(24).toString("hex");
  const inbox = path.join(modDir, "inbox", session);
  const hits = [];
  const state = { port: 0 };
  const hostOk = (req) => req.headers.host === `127.0.0.1:${state.port}`;
  const originOk = (req) => req.headers.origin === `http://127.0.0.1:${state.port}`;
  const tokenOk = (req) => {
    const got = Buffer.from(String(req.headers["x-pm-token"] || ""));
    const want = Buffer.from(token);
    return got.length === want.length && crypto.timingSafeEqual(got, want);
  };
  const baseHeaders = { "cache-control": "no-store", "x-content-type-options": "nosniff", "referrer-policy": "no-referrer" };
  const send = (res, code, body, type = "application/json; charset=utf-8", extra = {}) => {
    res.writeHead(code, { ...baseHeaders, "content-type": type, ...extra });
    res.end(typeof body === "string" || Buffer.isBuffer(body) ? body : JSON.stringify(body));
  };
  const fail = (res, code, error) => send(res, code, { ok: false, error });
  const readJson = (file) => { try { const t = fs.readFileSync(file, "utf8").trim(); return t && t !== "{}" ? JSON.parse(t) : null; } catch { return null; } };

  function serveFile(res, urlPath) {
    let rel;
    try { rel = decodeURIComponent(urlPath.slice("/file/".length)); } catch { return fail(res, 400, "bad path"); }
    if (rel.includes("\0")) return fail(res, 400, "bad path");
    const abs = /^[A-Za-z]:\//.test(rel) ? rel : "/" + rel.replace(/^\/+/, "");
    let real;
    try { real = fs.realpathSync(abs); } catch { return fail(res, 404, "not found"); }
    let dirs;
    try { dirs = reportDirs(fs.readFileSync(path.join(dir, "tasks.js"), "utf8")); } catch { return fail(res, 404, "no tasks.js"); }
    const inside = (d) => { try { const r = fs.realpathSync(d); const rel2 = path.relative(r, real); return !rel2.startsWith("..") && !path.isAbsolute(rel2); } catch { return false; } };
    const type = TYPES[path.extname(real).toLowerCase()];
    if (!type || !dirs.some(inside) || !fs.statSync(real).isFile()) return fail(res, 404, "not a listed report file");
    // sandboxed: the report runs without the page's origin, so it cannot read the token
    send(res, 200, fs.readFileSync(real), type, { "content-security-policy": "sandbox allow-scripts allow-popups allow-downloads" });
  }

  const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://x");
    if (!hostOk(req)) return fail(res, 403, "host");
    if (req.method === "GET") {
      if (url.pathname === "/" || url.pathname === "/index.html") {
        let html;
        try { html = fs.readFileSync(path.join(dir, "index.html"), "utf8"); } catch { return fail(res, 404, "no index.html in the board folder"); }
        return send(res, 200, html.replace(/(<meta id="pmtoken" content=")[^"]*(")/, `$1${token}$2`), "text/html; charset=utf-8", { "x-frame-options": "DENY" });
      }
      if (url.pathname === "/tasks.js") {
        try { return send(res, 200, fs.readFileSync(path.join(dir, "tasks.js")), "text/javascript; charset=utf-8"); } catch { return fail(res, 404, "no tasks.js in the board folder"); }
      }
      if (url.pathname.startsWith("/file/")) return serveFile(res, url.pathname);
      if (url.pathname === "/ping") {
        const hb = readJson(path.join(modDir, "heartbeat", `${session}.json`));
        return send(res, 200, { ok: true, session, modAlive: !!hb && typeof hb.beat === "number" && now() - hb.beat < BEAT_MS, enabled: !!hb && hb.enabled === true });
      }
      const ack = url.pathname.match(/^\/ack\/([A-Za-z0-9-]{4,64})$/);
      if (ack) {
        const a = readJson(path.join(modDir, "acks", `${ack[1]}.json`));
        return send(res, 200, { acked: !!a, ok: a ? a.ok === true : null, outcome: a ? a.outcome : null });
      }
      return fail(res, 404, "not found");
    }
    if (req.method === "POST" && url.pathname === "/say") {
      if (!tokenOk(req)) return fail(res, 403, "token");
      if (!originOk(req)) return fail(res, 403, "origin");
      const site = req.headers["sec-fetch-site"];
      if (site !== undefined && site !== "same-origin") return fail(res, 403, "cross-site request");
      if (!/^application\/json(;|$)/i.test(String(req.headers["content-type"] || ""))) return fail(res, 415, "content-type must be application/json");
      const t = now();
      while (hits.length && t - hits[0] > 60000) hits.shift();
      if (hits.length >= maxPerMinute) return fail(res, 429, "too many messages in a minute");
      let size = 0;
      const chunks = [];
      let over = false;
      req.on("data", (c) => {
        size += c.length;
        if (over) return;                              // the rest of an oversize body is read and thrown away
        if (size > BODY_MAX) { over = true; chunks.length = 0; res.setHeader("connection", "close"); fail(res, 413, "body over 4 KB"); return; }
        chunks.push(c);
      });
      req.on("end", () => {
        if (over) return;
        let body;
        try { body = JSON.parse(Buffer.concat(chunks).toString("utf8")); } catch { return fail(res, 400, "body is not JSON"); }
        const { msg, error } = checkSay(body);
        if (error) return fail(res, 400, error);
        const text = buildLine(msg);
        if ([...text].length > LINE_MAX) return fail(res, 400, `the line is longer than ${LINE_MAX} characters`);
        hits.push(t);
        const nonce = crypto.randomBytes(8).toString("hex");
        fs.mkdirSync(inbox, { recursive: true });
        const file = path.join(inbox, `${nonce}.json`);
        fs.writeFileSync(`${file}.tmp`, `${JSON.stringify({ nonce, kind: msg.kind, text, ask: msg.ask ?? null, task: msg.task ?? null, at: t, source: "task page" }, null, 2)}\n`);
        fs.renameSync(`${file}.tmp`, file);
        return send(res, 200, { ok: true, nonce, text });
      });
      return;
    }
    return fail(res, 405, "method");
  });

  return {
    server, token, inbox,
    listen: () => new Promise((resolve, reject) => {
      server.once("error", reject);
      server.listen(port, "127.0.0.1", () => { state.port = server.address().port; resolve(state.port); });
    }),
    close: () => new Promise((resolve) => server.close(resolve)),
    get port() { return state.port; },
  };
}

// The command line: only when this file is run, never when a test imports it.
if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))) {
  const arg = (k) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : undefined; };
  const dir = arg("--dir"), session = arg("--session"), modDir = arg("--mod-dir"), port = Number(arg("--port") ?? 8747);
  if (!dir || !session || !modDir) {
    console.error("usage: node board-server.mjs --dir <board folder> --session <master session id> --mod-dir <mod folder> [--port 8747]");
    process.exit(2);
  }
  const board = createBoard({ dir, session, modDir, port });
  board.listen().then((p) => console.log(`board http://127.0.0.1:${p}/ (session ${session}, inbox ${board.inbox})`), (err) => { console.error(`board-server: ${err.message}`); process.exit(1); });
}

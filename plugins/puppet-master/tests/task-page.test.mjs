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
  for (const k of ["workSet", "days", "updated", "waitingNow", "asks", "epics", "epicsAsOf", "sessions", "sessionsAsOf", "previous", "tasks"]) assert.ok(k in d, `no ${k}`);
  assert.equal(JSON.stringify([d.tasks, d.sessions, d.asks, d.epics, d.previous]), "[[],[],[],[],[]]");
  assert.ok(Array.isArray(d.days));
  for (const word of ["workSet", "days", "updated", "waitingNow", "epics", "sessions", "tasks", "origin", "initial", "added", "done", "running", "waiting-you", "queued", "open", "evidence", "reports", "label", "path", "pending", "sub"]) {
    assert.ok(text.includes(word), `the shape comment does not name ${word}`);
  }
  // the T28 records board: asks as records, pending-report, epics with a line per repo and PR, sources' read times
  for (const word of ["asks", "task", "state", "asked", "question", "facts", "kind: text | quote | link", "recommend", "noHurry", "answer", "answered", "movedFrom",
    "pending-report", "Mark seen", "blocked", "repos", "prState", "check", "review", "verdict", "jira", "key, status, category", "new | indeterminate | done", "last", "epicsAsOf", "sessionsAsOf",
    "previous", "the newest first (add a new line on top)", "the oldest first (append a new one)", "the order in this file does not matter"]) {
    assert.ok(text.includes(word), `the shape comment does not name ${word}`);
  }
});

test("index.html keeps every feature of the live page and adds the T28 design with the user's two tweaks", () => {
  const html = read("index.html");
  for (const needle of [
    // pinned header, the waiting line on every tab, three tabs (tweak 1)
    "<header>", "id=\"waiting\"", "id=\"askchip\"", "id=\"readchip\"", "id=\"tabs\"",
    "[\"questions\", \"Questions\"], [\"tasks\", \"Tasks\"], [\"jira\", \"Jira tasks\"]", "store.set(\"tab\"",
    // the sidebar (rail when collapsed) with the previous work sets as links (tweak 2)
    "id=\"rail\"", "id=\"side\"", "Previous work sets", "id=\"prev\"", "D.previous", "store.get(\"side\"",
    // filters with counts, the old Initial / Added later included
    "Open", "Waits for you", "Running", "Blocked", "Pending report", "Queued", "Done", "All", "Initial", "Added later",
    // sessions with headers, epics and Jira tasks with Jira board status
    "<span>Session</span><span>State</span><span class=\"model\">Model / effort</span><span>Job</span>", "Context, measured",
    "Epics and Jira tasks", "Jira (board status · assignee)", "no rows recorded",
    // the side panel for reports, new window only from its own button
    "<aside", "<iframe", "New window ↗", "Close ✕",
    // long content: a line of 1,000 characters or more opens whole in a reading row
    "const LONG = 1000", "Open the whole line", "Show more", "Show less", "earlier line",
    // pending report and the seen mark (A62, A64), kept in this browser, with a line for the master
    "Mark seen ✓", "SEEN_KEY = \"seen:\" + location.pathname", "seen on the task page: ", "navigator.clipboard.writeText",
    // the orders, named on the page
    "Order: running, waits for you, queued, pending report; newest first within each.", "oldest first", "newest first",
    // light and dark, theme kept
    "prefers-color-scheme: dark", ":root[data-theme=\"dark\"]", "store.get(\"theme\"",
    "localStorage", "\"pmboard.\" + k", "store.get(\"open\"", "store.get(\"panel\"",
    "tasks.js?t=", "setInterval(() => loadData(false), 90000)",
  ]) assert.ok(html.includes(needle), `index.html lacks: ${needle}`);
  assert.ok(!html.includes("location.reload"), "the data reloads without a page reload");
  assert.ok(!/https?:\/\/(?!localhost)[\w.-]+\.(com|net|org|io)\//.test(html.replace(/\/\/[^\n]*\n/g, "\n")), "no external fonts or CDNs");
});

// Runs the page's own script against a small DOM stub, with a tasks.js fixture, and reads what each pane would show.
function renderPage(dash, { seen = {}, width = 1440, tab, filter } = {}) {
  const html = read("index.html");
  const script = html.match(/<script>([\s\S]*)<\/script>/)[1];
  const els = {};
  const classList = () => { const s = new Set(); return { toggle(c, on) { (on ?? !s.has(c)) ? s.add(c) : s.delete(c); }, add: (c) => s.add(c), remove: (c) => s.delete(c), contains: (c) => s.has(c) }; };
  const el = (id) => (els[id] ??= { id, innerHTML: "", textContent: "", title: "", className: "", href: "", src: "", dataset: {}, style: {}, classList: classList(), addEventListener() {}, setAttribute() {}, removeAttribute() {} });
  const mem = new Map();
  const localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, String(v)) };
  const pathname = "/board/index.html";
  if (Object.keys(seen).length) localStorage.setItem("pmboard.seen:" + pathname, JSON.stringify(seen));
  if (tab) localStorage.setItem("pmboard.tab", JSON.stringify(tab));
  if (filter) localStorage.setItem("pmboard.filter", JSON.stringify(filter));
  const sandbox = {
    localStorage, location: { pathname, hash: "" }, history: { replaceState() {} }, navigator: {},
    setInterval() {}, setTimeout() {}, innerWidth: width, addEventListener() {},
    document: {
      getElementById: el, querySelectorAll: () => [], createElement: () => ({ remove() {} }),
      documentElement: { setAttribute() {}, removeAttribute() {} },
      body: { classList: classList(), addEventListener() {}, appendChild(s) { sandbox.window.DASH = dash; s.onload(); } },
    },
  };
  sandbox.window = sandbox;
  vm.runInNewContext(script, sandbox);
  return els;
}
const ids = (html, re) => [...html.matchAll(re)].map((m) => m[1]);
const BOARD = {
  workSet: "Work set 2026-01-02", days: ["2026-01-02"], updated: "2026-01-02 10:30",
  waitingNow: "A3 and A9 wait for you.",
  asks: [
    { id: "A9", task: "T7", state: "open", asked: "01-02 10:00", question: "Ship it?", facts: [{ label: "Why", text: "tests pass", kind: "text" }, { label: "Draft", text: "the note", kind: "quote" }], recommend: "Yes", noHurry: true },
    { id: "A3", task: "T1", state: "open", asked: "01-02 09:00", question: "Which option?", facts: [], recommend: "B", movedFrom: "T0" },
    { id: "A2", task: "T1", state: "answered", answer: "“A (Recommended)”", answered: "01-02 08:00" },
    { id: "A5", task: "T2", state: "answered", answer: "“No”", answered: "01-02 09:30" },
  ],
  epicsAsOf: { "brain origin": "21:35", Jira: "22:59" },
  epics: [
    { epic: "EPIC-0036", what: "Night shifts", status: "planned", stamps: "dev_review none", repos: [
      { repo: "frontend", pr: "#73", prState: "ready · mergeable, clean", tasks: "1 of 1 landed", review: { verdict: "fixed-clean", note: "4 minor open" }, jira: { key: "KEY-2", status: "To Review", category: "new", type: "Task", assignee: "someone" }, last: "21:35 · merged" },
      { repo: "backend", pr: "#203", prState: "draft · mergeable, unstable", check: "check review: failure", tasks: "6 of 6 landed", review: { verdict: "blocked", note: "gate red" }, jira: { key: "KEY-1", status: "In Progress", category: "indeterminate", type: "Bug", assignee: "someone" }, last: "21:11 · envelope" }] },
    { epic: "EPIC-0031", what: "Overtime", status: "planned", stamps: "", repos: [{ repo: "backend", pr: "#197", jira: { key: "KEY-0", status: "Done", category: "done" } }] },
  ],
  sessionsAsOf: "10:29",
  sessions: [
    { name: "w-b", state: "clean", model: "opus high", job: "-", context: "0 (fresh)" },
    { name: "m-1", state: "master", model: "opus high", job: "coordination", context: "1,000 (1%)" },
    { name: "w-a", state: "working (busy)", model: "sonnet medium", job: "T2 build", context: "99,538 (10%)" },
  ],
  previous: [
    { label: "Work set 2025-12-20", days: "2025-12-20", tasks: "3, all done", open: "", path: "/x/2025-12-20/index.html" },
    { label: "Work set 2025-12-28", days: "2025-12-28, 12-29", tasks: "9, all done", open: "one proposal", path: "/x/2025-12-28/index.html" },
  ],
  tasks: [
    { id: "T1", day: "01-02", origin: "initial", title: "done, with an open ask", status: "done", who: "w-b (finished)", evidence: "-", reports: [], sub: ["A3 ASKED 01-02: which option?"] },
    { id: "T2", day: "01-02", origin: "initial", title: "running older", status: "running", who: "w-a", evidence: "-", reports: [], sub: [] },
    { id: "T3", day: "01-02", origin: "added", title: "queued", status: "queued", who: "next free", evidence: "-", reports: [], sub: [] },
    { id: "T4", day: "01-02", origin: "added", title: "pending report", status: "pending-report", who: "w-b", evidence: "-", reports: [{ label: "the report", path: "/x/r.html", pending: false }], sub: ["x".repeat(1200), "DELIVERED 01-02: done."] },
    { id: "T5", day: "01-02", origin: "added", title: "running newer", status: "running", who: "w-a", evidence: "-", reports: [], sub: [] },
    { id: "T6", day: "01-02", origin: "added", title: "plain done", status: "done", who: "w-a", evidence: "-", reports: [], sub: [] },
    { id: "T7", day: "01-02", origin: "added", title: "waits for the user", status: "waiting-you", who: "you", evidence: "-", reports: [], sub: [] },
    { id: "T8", day: "01-02", origin: "added", title: "blocked", status: "queued", blocked: "on the review host", who: "w-b", evidence: "-", reports: [], sub: [] },
  ],
};

test("the page: three tabs with counts, the waiting line on every tab, the tab kept in the browser (tweak 1)", () => {
  const els = renderPage(BOARD, { tab: "jira" });
  assert.deepEqual(ids(els.tabs.innerHTML, /data-tab="(\w+)"/g), ["questions", "tasks", "jira"]);
  assert.match(els.tabs.innerHTML, /data-tab="jira" class="on"/);
  assert.match(els.tabs.innerHTML, /Questions<b class="hot">2<\/b>/);
  assert.ok(els["pane-questions"].classList.contains("hide") && els["pane-tasks"].classList.contains("hide"));
  assert.ok(!els["pane-jira"].classList.contains("hide"));
  assert.match(els.waiting.innerHTML, /A3 and A9 wait for you\./);
  assert.equal(els.askchip.textContent, "2 asks wait for you");
  assert.equal(els.readchip.textContent, "1 report to read");
});

test("the page: questions are records, open ones oldest first, answered ones newest first, no hurry still counted", () => {
  const q = renderPage(BOARD)["pane-questions"].innerHTML;
  assert.deepEqual(ids(q, /id="ask-(A\d+)"/g), ["A3", "A9"]);
  assert.match(q, /2 open · 1 of them no hurry/);
  assert.match(q, /moved here from T0/);
  assert.match(q, /<div class="q">the note<\/div>/);
  assert.match(q, /Recommended<\/div><div class="v">B</);
  assert.deepEqual(ids(q, /<div class="arow"><b>(A\d+)<\/b>/g), ["A5", "A2"]);
  assert.match(q, /Running<\/span><span><a data-jump="T5">T5<\/a> \(w-a\) · <a data-jump="T2">T2<\/a>/);
  const calm = renderPage({ ...BOARD, asks: BOARD.asks.filter((a) => a.state === "answered"), tasks: BOARD.tasks.filter((t) => t.status !== "waiting-you") });
  assert.match(calm["pane-questions"].innerHTML, /Nothing waits for you/);
  assert.equal(calm.askchip.textContent, "Nothing waits for you");
});

test("the page: tasks in Open run running, waits for you, queued, pending report, newest first in each; done after", () => {
  const t = renderPage(BOARD, { tab: "tasks" })["pane-tasks"].innerHTML;
  assert.deepEqual(ids(t, /data-task="(T\d+)" id=/g), ["T5", "T2", "T7", "T1", "T8", "T3", "T4", "T6"]);
  assert.match(t, /Done · 1 · newest first/);
  assert.match(t, /A3 open<\/b>/, "a done task with an open ask stays in Open with its ask strip");
  assert.match(t, /<span class="pill k-block">Blocked<\/span><span class="blk">on the review host<\/span>/);
  assert.match(t, /Open the whole line · 1,200 characters/);
  assert.deepEqual(ids(t, /<div class="sg" title="([\w-]+) ·/g), ["m-1", "w-a", "w-b"], "sessions: master, working, clean");
  assert.match(t, /from puppet list, 10:29/);
  const all = renderPage(BOARD, { tab: "tasks", filter: "all" })["pane-tasks"].innerHTML;
  assert.deepEqual(ids(all, /data-task="(T\d+)" id=/g), ["T8", "T7", "T6", "T5", "T4", "T3", "T2", "T1"]);
  assert.match(all, /Order: newest first\./);
});

test("the page: pending report has its own pill, filter and count, is not waiting, and Mark seen moves it to Done here (A62, A64)", () => {
  const els = renderPage(BOARD, { tab: "tasks" });
  const t = els["pane-tasks"].innerHTML;
  assert.match(t, /<span class="pill k-unread">Pending report<\/span>/);
  assert.match(t, /data-seen="T4"[^>]*>Mark seen ✓/);
  assert.match(t, /data-f="pend" class="">Pending report<b[^>]*>1<\/b>/);
  assert.match(t, /data-f="wait" class="">Waits for you<b[^>]*>2<\/b>/, "T7 and T1 (its open ask) wait; T4 does not");
  const seen = renderPage(BOARD, { tab: "tasks", seen: { T4: "01-02 11:00" } });
  const s = seen["pane-tasks"].innerHTML;
  assert.match(s, /Done · 2 · newest first/);
  assert.match(s, /seen on the task page: T4 \(01-02 11:00\)/);
  assert.ok(seen.readchip.classList.contains("hide"));
  // once tasks.js says done, the browser's mark is dropped and the line for the master goes
  const folded = renderPage({ ...BOARD, tasks: BOARD.tasks.map((x) => (x.id === "T4" ? { ...x, status: "done" } : x)) }, { tab: "tasks", seen: { T4: "01-02 11:00" } });
  assert.ok(!folded["pane-tasks"].innerHTML.includes("seen on the task page"));
});

test("the page: epics by epic id, backend before frontend, Jira board status coloured by its category", () => {
  const j = renderPage(BOARD, { tab: "jira" })["pane-jira"].innerHTML;
  assert.deepEqual(ids(j, /<b>(EPIC-\d+)<\/b>/g), ["EPIC-0031", "EPIC-0036"]);
  assert.deepEqual(ids(j, /<b>(KEY-\d)<\/b>/g), ["KEY-0", "KEY-1", "KEY-2"]);
  assert.match(j, /<b>KEY-1<\/b> <span class="kp k-run">In Progress<\/span>/);
  assert.match(j, /<b>KEY-2<\/b> <span class="kp k-queue">To Review<\/span>/);
  assert.match(j, /<span class="kp k-block">blocked<\/span>/);
  assert.match(j, /brain origin 21:35 · Jira 22:59 · by epic id; backend before frontend/);
  const empty = renderPage({ ...BOARD, epics: [] }, { tab: "jira" })["pane-jira"].innerHTML;
  assert.match(empty, /no rows recorded/);
});

test("the page: previous work sets are links in the sidebar, newest first (tweak 2)", () => {
  const p = renderPage(BOARD).prev.innerHTML;
  assert.deepEqual(ids(p, /(Work set [\d-]+) ↗/g), ["Work set 2025-12-28", "Work set 2025-12-20"]);
  assert.match(p, /href="file:\/\/\/\/x\/2025-12-28\/index.html" target="_blank"/);
  assert.match(p, /Left open: one proposal/);
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
        'console.log("m-1  0  0%  fresh  (no turns yet)  model fresh  interactive master clean  mod on (asked)");\n' +
        'console.log("u1  changed  (new session id: ask the user whether it was cleared)");\n',
    );
    const out = execFileSync("node", [path.join(dir, "sync-sessions.mjs"), "--puppet", fake, "--file", path.join(dir, "tasks.js")], {
      encoding: "utf8",
    });
    assert.match(out, /w-1 \| working \(busy\) \| sonnet-5-5 medium \| build the thing/);
    const sandbox = { window: {} };
    vm.runInNewContext(fs.readFileSync(path.join(dir, "tasks.js"), "utf8"), sandbox);
    const s = sandbox.window.DASH.sessions;
    assert.equal(s.length, 3);
    assert.equal(s[0].name, "w-1");
    assert.equal(s[0].context, "99,538 (10%)");
    assert.equal(s[1].state, "master");
    // T14's finding: a line with no token count was written as "NaN ()" and "clean"
    assert.deepEqual({ ...s[2] }, { name: "u1", state: "changed (new session id: ask the user whether it was cleared)", model: "-", job: "-", context: "-" });
    assert.ok(!/NaN/.test(fs.readFileSync(path.join(dir, "tasks.js"), "utf8")));
    assert.match(sandbox.window.DASH.updated, /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
    assert.equal(sandbox.window.DASH.sessionsAsOf, sandbox.window.DASH.updated.slice(11));
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

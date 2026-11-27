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
const FILES = ["index.html", "tasks.js", "sync-sessions.mjs", "sync-epics.mjs"];

test("the task-page template ships its four files and no add-reports script", () => {
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
  for (const k of ["workSet", "days", "updated", "waitingNow", "asks", "epics", "epicsAsOf", "sessions", "sessionsAsOf", "previous", "sideQuestions", "tasks"]) assert.ok(k in d, `no ${k}`);
  assert.equal(JSON.stringify([d.tasks, d.sessions, d.asks, d.epics, d.previous, d.sideQuestions]), "[[],[],[],[],[],[]]");
  // T46: groups, side questions, statuses read loosely, a line's read time
  for (const word of ["group", "sideQuestions", "{ id, asked, question, answer, answered }", "the user's words, verbatim", "\"pending report\" is pending-report",
    "Done tasks are not in the Open list", "asOf", "sync-epics.mjs", "not written yet"]) {
    assert.ok(text.includes(word), `the shape comment does not name ${word}`);
  }
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
    "[\"questions\", \"Questions\"], [\"tasks\", \"Tasks\"], [\"jira\", \"Epics and Jira\"]", "store.set(\"tab\"",
    // the sidebar (rail when collapsed) with the previous work sets as links (tweak 2)
    "id=\"rail\"", "id=\"side\"", "Previous work sets", "id=\"prev\"", "D.previous", "store.get(\"side\"",
    // filters with counts, the old Initial / Added later included
    "Open", "Waits for you", "Running", "Blocked", "Pending report", "Queued", "Done", "All", "Initial", "Added later",
    // sessions and filters in the sidebar (T33), epics and Jira tasks with Jira board status
    "id=\"sidesess\"", "id=\"sidefilters\"", "context used", "(the filters are in the sidebar)",
    "Epics and Jira", "no rows recorded",
    // the side panel for reports, new window only from its own button; its width dragged on its left edge, kept, reset by double-click (T33)
    "<aside", "<iframe", "New window ↗", "Close ✕",
    "id=\"pgrip\"", "role=\"separator\"", "PW_DEFAULT = 300, PW_MIN = 300, MAIN_MIN = 560, SIDE_W = 420, RAIL_W = 88", "store.get(\"panelw\"", "setPointerCapture", "\"dblclick\"",
    // long content: a line of 1,000 characters or more opens whole in a reading row; a task row opens under Show more
    "const LONG = 1000", "Open the whole line", "\"Show more\"", "\"Show less\"", "earlier line",
    // pending report and the seen mark (A62, A64), kept in this browser, with a line for the master
    "Mark seen ✓", "SEEN_KEY = \"seen:\" + location.pathname", "seen on the task page: ", "navigator.clipboard.writeText",
    // the orders, named on the page: one strict order (T46, the user 11-27: "ordering must be strict")
    "Order: groups A to Z (no group last), then task id, lowest first.", "grouped by task; tasks and asks by id, lowest first", "newest first",
    // T46: the fourth tab, the folded Done list, statuses read loosely, Jira freshness, a drag that always ends
    "[\"side\", \"Side questions\"]", "D.sideQuestions", "data-all", "data-fold", "store.get(\"fold\"", "store.get(\"panelOpen\"", "id=\"pempty\"", "normStatus", "const STALE_H = 2", "node sync-epics.mjs",
    "\"lostpointercapture\"", "window.addEventListener(\"blur\", endDrag)",
    // light and dark, theme kept
    "prefers-color-scheme: dark", ":root[data-theme=\"dark\"]", "store.get(\"theme\"",
    "localStorage", "\"pmboard.\" + k", "store.get(\"open\"", "store.get(\"panel\"",
    "tasks.js?t=", "setInterval(() => loadData(false), 90000)",
  ]) assert.ok(html.includes(needle), `index.html lacks: ${needle}`);
  assert.ok(!html.includes("location.reload"), "the data reloads without a page reload");
  assert.ok(!/https?:\/\/(?!localhost)[\w.-]+\.(com|net|org|io)\//.test(html.replace(/\/\/[^\n]*\n/g, "\n")), "no external fonts or CDNs");
});

// Runs the page's own script against a small DOM stub, with a tasks.js fixture, and reads what each pane would show.
function renderPage(dash, { seen = {}, width = 1440, tab, filter, panelw, panel, open, fold, rall, panelOpen } = {}) {
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
  if (panelw) localStorage.setItem("pmboard.panelw", JSON.stringify(panelw));
  if (panel) localStorage.setItem("pmboard.panel", JSON.stringify(panel));
  if (open) localStorage.setItem("pmboard.open", JSON.stringify(open));
  if (fold) localStorage.setItem("pmboard.fold", JSON.stringify(fold));
  if (rall) localStorage.setItem("pmboard.rall", JSON.stringify(rall));
  if (panelOpen != null) localStorage.setItem("pmboard.panelOpen", JSON.stringify(panelOpen));
  const rootStyle = {};
  els.rootStyle = rootStyle;
  const sandbox = {
    localStorage, location: { pathname, hash: "" }, history: { replaceState() {} }, navigator: {},
    setInterval() {}, setTimeout() {}, innerWidth: width, addEventListener() {},
    document: {
      getElementById: el, querySelectorAll: () => [], createElement: () => ({ remove() {} }), addEventListener() {},
      documentElement: { setAttribute() {}, removeAttribute() {}, style: { setProperty: (k, v) => { rootStyle[k] = v; } } },
      body: { classList: classList(), addEventListener(type, fn) { if (type === "click") sandbox.onClick = fn; }, appendChild(s) { sandbox.window.DASH = dash; s.onload(); } },
    },
  };
  sandbox.window = sandbox;
  vm.runInNewContext(script, sandbox);
  els.sandbox = sandbox;
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

test("the page: four tabs with counts, the waiting line on every tab, the tab kept in the browser (tweak 1, T46)", () => {
  const els = renderPage(BOARD, { tab: "jira" });
  assert.deepEqual(ids(els.tabs.innerHTML, /data-tab="(\w+)"/g), ["questions", "tasks", "jira", "side"]);
  assert.match(els.tabs.innerHTML, /data-tab="jira" class="on"/);
  assert.match(els.tabs.innerHTML, /Questions<b class="hot">2<\/b>/);
  assert.match(els.tabs.innerHTML, /Side questions<b class="">0<\/b>/);
  assert.ok(els["pane-questions"].classList.contains("hide") && els["pane-tasks"].classList.contains("hide") && els["pane-side"].classList.contains("hide"));
  assert.ok(!els["pane-jira"].classList.contains("hide"));
  assert.match(els.waiting.innerHTML, /A3 and A9 wait for you\./);
  assert.equal(els.askchip.textContent, "2 asks wait for you");
  assert.equal(els.readchip.textContent, "1 report to read");
});

test("the page: questions are records grouped by their task, tasks and asks by id, no hurry still counted (T46)", () => {
  const q = renderPage(BOARD)["pane-questions"].innerHTML;
  assert.deepEqual(ids(q, /id="ask-(A\d+)"/g), ["A3", "A9"]);
  assert.match(q, /2 open · 1 of them no hurry/);
  assert.match(q, /moved here from T0/);
  assert.match(q, /<div class="q">the note<\/div>/);
  assert.match(q, /Recommended<\/div><div class="v">B</);
  assert.deepEqual(ids(q, /<div class="arow"><b>(A\d+)<\/b>/g), ["A2", "A5"]);
  assert.match(q, /Running<\/span><span><a data-jump="T2">T2<\/a> \(w-a\) · <a data-jump="T5">T5<\/a>/);
  // the user, 11-27: "group questions from single task": one heading per task, its asks under it
  const many = [
    { id: "A12", task: "T7", state: "open", question: "q12" }, { id: "A4", task: "T7", state: "open", question: "q4" },
    { id: "A10", task: "T2", state: "open", question: "q10" }, { id: "A11", task: "T7", state: "answered", answer: "yes" },
    { id: "A1", task: "T2", state: "answered", answer: "no" }];
  const g = renderPage({ ...BOARD, asks: many })["pane-questions"].innerHTML;
  assert.deepEqual(ids(g, /data-qtask="(T\d+)"/g), ["T2", "T7"], "tasks by id, lowest first");
  assert.deepEqual(ids(g, /id="ask-(A\d+)"/g), ["A10", "A4", "A12"], "the asks of one task together, by id");
  assert.match(g, /data-qtask="T7"><div class="qth"><span class="ch" data-fold="q:T7" title="Fold or open this task's asks">▾<\/span><a class="tid" data-jump="T7">T7<\/a><span class="pill k-wait">Waits for you<\/span><span class="tt" title="waits for the user">waits for the user<\/span><span class="r">2 open<\/span>/);
  assert.deepEqual(ids(g, /<div class="arh"><a data-jump="(T\d+)">/g), ["T2", "T7"], "answered ones grouped by task too");
  const calm = renderPage({ ...BOARD, asks: BOARD.asks.filter((a) => a.state === "answered"), tasks: BOARD.tasks.filter((t) => t.status !== "waiting-you") });
  assert.match(calm["pane-questions"].innerHTML, /Nothing waits for you/);
  assert.equal(calm.askchip.textContent, "Nothing waits for you");
});

test("the page: tasks by id, lowest first; no Done section, Done is a filter; a row is # | title, one line, Show more | status and who | the 3 newest reports (T46)", () => {
  const els = renderPage(BOARD, { tab: "tasks" });
  const t = els["pane-tasks"].innerHTML;
  // the user, 11-27: "ordering must be strict, i see again T ids messed" and "no done tasks under normal list"
  assert.deepEqual(ids(t, /data-task="(T\d+)" id=/g), ["T1", "T2", "T3", "T4", "T5", "T7", "T8"], "T6 (done) is not in the open list");
  assert.ok(!/donesec|data-donesum|folded; the same order/.test(t), "no Done section under the list (the accepted canvas)");
  assert.match(t, /Showing <b>Open · 7<\/b> \(the filters are in the sidebar\)\. Order: groups A to Z \(no group last\), then task id, lowest first\. Done tasks are under the Done filter\./);
  assert.match(t, /<h2>Open tasks<\/h2><span class="cap">7 of 8<\/span><span class="sw"><button data-all="tasks" data-mode="collapse" class="">Collapse all<\/button><button data-all="tasks" data-mode="expand" class="">Expand all<\/button>/);
  assert.match(t, /<div class="thead"><span>#<\/span><span>Task<\/span><span>Status · who<\/span><span>Reports, newest first<\/span><\/div>/);
  // a row: id | title (+ the newest line, Show more) | status pill and who | reports
  const row8 = t.slice(t.indexOf('<div class="trow" data-task="T8"')).split('</div><p class="foot">')[0];
  assert.equal(row8, '<div class="trow" data-task="T8" id="task-T8"><span class="id">T8</span><div class="tk"><div class="ti" title="blocked">blocked</div>'
    + '<div class="more"><a data-exp="T8" aria-expanded="false">Show more</a></div></div><div class="stc"><div class="st"><span class="pill k-queue">Queued</span>'
    + '<span class="pill k-block" title="on the review host">Blocked</span></div><small class="clamp2" title="w-b">w-b</small></div><div class="rp"><span class="mut3">–</span></div></div>');
  const row4 = t.match(/<div class="trow" data-task="T4"[\s\S]*?<div class="rp">[\s\S]*?<\/div><\/div><\/div>/)[0];
  assert.match(row4, /<div class="s1 clamp2">x{1200}<\/div><div class="more"><a data-exp="T4" aria-expanded="false">Show more · 1 more line<\/a>/, "one line of what is new, the rest behind Show more · n");
  assert.match(row4, /<div class="rep unread"><i class="rd"><\/i><a class="doc" data-url="file:\/\/\/\/x\/r.html" data-label="T4: the report" data-task="T4">the report<\/a>/, "reports are always in the row");
  for (const hidden of ["A3 open</b>", "Open the whole line", "class=\"tdet\""]) assert.ok(!t.includes(hidden), `a closed row shows ${hidden}`);
  // Show more opens the rest: the asks, the status with its block, who, the lines
  const x = renderPage(BOARD, { tab: "tasks", open: ["T1", "T4", "T8"] })["pane-tasks"].innerHTML;
  assert.match(x, /data-exp="T1" aria-expanded="true">Show less/);
  assert.match(x, /A3 open<\/b>/, "a done task with an open ask stays in Open, its ask strip under Show more");
  assert.match(x, /<span class="pill k-block">Blocked<\/span> <span class="blk">on the review host<\/span>/);
  assert.match(x, /Open the whole line · 1,200 characters/);
  assert.match(x, /<span class="l">Who<\/span><div>w-b<small>finished<\/small><\/div>/);
  const all = renderPage(BOARD, { tab: "tasks", filter: "all" })["pane-tasks"].innerHTML;
  assert.deepEqual(ids(all, /data-task="(T\d+)" id=/g), ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"]);
  assert.deepEqual(ids(renderPage(BOARD, { tab: "tasks", filter: "done" })["pane-tasks"].innerHTML, /data-task="(T\d+)" id=/g), ["T1", "T6"], "the Done filter lists the done tasks");
});

test("the page: a row shows the 3 newest reports, Show more · n opens the rest (T46)", () => {
  const reports = [1, 2, 3, 4, 5].map((n) => ({ label: "r" + n, path: "/x/r" + n + ".html" }));
  const board = { ...BOARD, tasks: [{ id: "T1", status: "running", title: "x", reports }] };
  const t = renderPage(board, { tab: "tasks" })["pane-tasks"].innerHTML;
  assert.deepEqual(ids(t, /data-label="T1: (r\d)"/g), ["r5", "r4", "r3"], "the newest first, three of them");
  assert.match(t, /<div class="rmore"><a data-rall="T1">Show more · 2<\/a><\/div>/);
  const more = renderPage(board, { tab: "tasks", rall: ["T1"] })["pane-tasks"].innerHTML;
  assert.deepEqual(ids(more, /data-label="T1: (r\d)"/g), ["r5", "r4", "r3", "r2", "r1"]);
  assert.match(more, /<a data-rall="T1">Show fewer<\/a>/);
});

test("the page: related tasks under a heading per group, groups A to Z, no group last; the Jira tab lists an epic's tasks by group (T46)", () => {
  const g = { "T2": "EPIC-0036", "T5": "CI", "T7": "EPIC-0036", "T3": "status page" };
  const board = { ...BOARD, tasks: BOARD.tasks.map((x) => (g[x.id] ? { ...x, group: g[x.id] } : x)) };
  const t = renderPage(board, { tab: "tasks", filter: "all" })["pane-tasks"].innerHTML;
  assert.deepEqual(ids(t, /<div class="tgh" data-group="([^"]*)"/g), ["CI", "EPIC-0036", "status page", ""]);
  assert.deepEqual(ids(t, /data-task="(T\d+)" id=/g), ["T5", "T2", "T7", "T3", "T1", "T4", "T6", "T8"]);
  assert.match(t, /data-group="" data-fold="g:"><span class="ch">▾<\/span>No group <span class="cap">4 shown<\/span>/);
  const j = renderPage(board, { tab: "jira" })["pane-jira"].innerHTML;
  assert.match(j, /data-epic="EPIC-0036">[\s\S]*?<h4>Tasks here<\/h4><div class="th"><b><a data-jump="T2">T2<\/a><\/b>[\s\S]*?data-jump="T7">T7<\/a>/);
});

test("the page: Collapse all / Expand all in each list heading; a group folds on its own heading (T46)", () => {
  const g = { "T2": "EPIC-0036", "T5": "CI", "T7": "EPIC-0036" };
  const board = { ...BOARD, tasks: BOARD.tasks.map((x) => (g[x.id] ? { ...x, group: g[x.id] } : x)) };
  const click = (els, dataset) => els.sandbox.onClick({ target: { closest: (sel) => (sel === "a.ext" ? null : { dataset, matches: () => false, id: "" }) } });
  const els = renderPage(board, { tab: "tasks" });
  assert.deepEqual([...els.sandbox.listKeys("tasks").keys], ["g:CI", "g:EPIC-0036", "g:"], "one key per group of the chosen filter");
  click(els, { all: "tasks", mode: "collapse" });
  let t = els["pane-tasks"].innerHTML;
  assert.equal((t.match(/class="trow/g) || []).length, 0, "Collapse all: only the group headings stay");
  assert.equal((t.match(/<span class="ch">▸<\/span>/g) || []).length, 3);
  assert.match(t, /data-mode="collapse" class="on">Collapse all<\/button><button data-all="tasks" data-mode="expand" class="">/, "the switch shows Collapse all as on");
  click(els, { all: "tasks", mode: "expand" });
  t = els["pane-tasks"].innerHTML;
  assert.equal((t.match(/class="trow/g) || []).length, 7, "Expand all: every group open");
  assert.equal((t.match(/aria-expanded="true">Show less/g) || []).length, 7, "and every row shows its lines");
  assert.match(t, /data-mode="expand" class="on">Expand all<\/button>/);
  click(els, { fold: "g:CI" });
  t = els["pane-tasks"].innerHTML;
  assert.ok(!t.includes('data-task="T5"') && t.includes('data-task="T2"'), "one group folded on its heading");
  assert.match(t, /data-mode="collapse" class="">Collapse all<\/button><button data-all="tasks" data-mode="expand" class="">Expand all/, "mixed: neither is on");
  // the other lists have the switch too: Questions (a task's asks), Jira (an epic's repo lines), the sidebar's sessions
  assert.deepEqual([...els.sandbox.listKeys("questions").keys], ["q:T1", "q:T7"]);
  assert.deepEqual([...els.sandbox.listKeys("jira").keys], ["e:EPIC-0036", "e:EPIC-0031"]);
  assert.deepEqual([...els.sandbox.listKeys("sess").keys], ["sess"]);
  click(els, { all: "questions", mode: "collapse" });
  assert.ok(!els["pane-questions"].innerHTML.includes('id="ask-A3"') && els["pane-questions"].innerHTML.includes('data-qtask="T1"'), "the asks fold under their task heading");
  click(els, { all: "jira", mode: "collapse" });
  assert.match(els["pane-jira"].innerHTML, /<div class="ep folded" data-epic="EPIC-0031">/);
  click(els, { all: "sess", mode: "collapse" });
  assert.match(els.sidesess.innerHTML, /<div class="ssess folded"/);
  assert.match(els.sesssw.innerHTML, /data-mode="collapse" class="on">Collapse all/);
});

test("the page: every status has a filter with its count, 0 too; both spellings of pending report are one status; an unknown status gets its own filter (T46)", () => {
  const board = { ...BOARD, tasks: [...BOARD.tasks.filter((x) => !x.blocked), { id: "T9", status: "pending report", title: "spelled with a space", reports: [] }, { id: "T10", status: "parked", title: "a word the page does not know" }] };
  const els = renderPage(board, { tab: "tasks", filter: "s-parked" });
  const side = els.sidefilters.innerHTML;
  assert.deepEqual(ids(side, /data-go="([\w-]+)"><span>/g), ["open", "wait", "run", "block", "pend", "queue", "done", "s-parked", "all", "initial", "added"]);
  assert.match(side, /data-go="block"><span>Blocked<\/span><span class="n zero">0<\/span>/, "Blocked stays listed at 0");
  assert.match(side, /data-go="pend"><span>Pending report<\/span><span class="n hot k-unread">2<\/span>/, "T4 and T9");
  assert.match(side, /class="srow on" data-go="s-parked"><span>parked<\/span><span class="n">1<\/span>/);
  assert.deepEqual(ids(els["pane-tasks"].innerHTML, /data-task="(T\d+)" id=/g), ["T10"]);
});

test("the page: the sidebar shows every session: context % with a bar and what it is doing, no raw token counts (T46)", () => {
  const els = renderPage(BOARD);
  const s = els.sidesess.innerHTML;
  assert.deepEqual(ids(s, /<div class="ssess[^"]*" title="([\w-]+) ·/g), ["m-1", "w-a", "w-b"], "sessions: master, working, clean");
  assert.equal(els.sesshead.textContent, "Session records · as of 10:29");
  assert.match(s, /<span class="nm">w-a<\/span><span class="pc">10%<\/span><\/div><div class="job">T2 build<\/div><div class="bar"><span class="" style="width:10%"><\/span><\/div><div class="md">working \(busy\) · sonnet medium<\/div>/);
  assert.match(s, /<span class="nm">w-b<\/span><span class="pc">0%<\/span><\/div><div class="job">no job · fresh<\/div>/);
  assert.ok(!/99,538|tokens/.test(s), "the user, 11-27: no raw values");
  assert.match(els.sidetag.textContent, /^8 tasks$/);
  const busy = renderPage({ ...BOARD, sessions: [{ name: "w-9", state: "working (busy)", model: "sonnet", job: "/x/brief-ad-pm.md", context: "700,000 (70%)" }] }).sidesess.innerHTML;
  assert.match(busy, /<div class="job">ad-pm<\/div><div class="bar"><span class="hi" style="width:70%">/, "a brief path reads as its name; the bar turns amber from 70%");
});

test("the page: Side questions, the user's side questions to the master, the newest first (T46)", () => {
  const side = [
    { id: "S1", asked: "01-02 09:10", question: "why is T3 queued?\nand when", answer: "waits for a free worker", answered: "01-02 09:12" },
    { id: "S2", asked: "01-02 10:05", question: "is the CI green?", answer: "", answered: "" }];
  const els = renderPage({ ...BOARD, sideQuestions: side }, { tab: "side" });
  const p = els["pane-side"].innerHTML;
  assert.deepEqual(ids(p, /data-sq="(S\d+)"/g), ["S2", "S1"]);
  assert.match(p, /<span class="q">why is T3 queued\?\nand when<\/span>/, "the question verbatim");
  assert.match(p, /<span class="a">waits for a free worker<\/span><span class="t">01-02 09:12<\/span>/);
  assert.match(p, /not answered yet/);
  assert.match(els.tabs.innerHTML, /data-tab="side" class="on" aria-selected="true">Side questions<b class="">2<\/b>/);
  assert.match(renderPage(BOARD, { tab: "side" })["pane-side"].innerHTML, /No side question logged yet/);
});

test("the page: a task link in Questions opens the related report beside and jumps to the task (T46)", () => {
  const board = { ...BOARD,
    asks: [...BOARD.asks, { id: "A20", task: "T4", state: "open", question: "q", facts: [{ label: "Draft", text: "the draft", kind: "link", path: "/x/draft.html" }] }],
    tasks: BOARD.tasks.map((x) => (x.id === "T7" ? { ...x, reports: [{ label: "old", path: "/x/old.html" }, { label: "new", path: "/x/new.html" }, { label: "later", path: "/x/later.html", pending: true }] } : x)) };
  const els = renderPage(board);
  const rel = (t, a) => JSON.stringify(els.sandbox.relatedReport(t, a));
  // the user, 11-27: "link from main questions tab should open related report and also move to taks list like s now"
  assert.equal(rel("T4", "A20"), JSON.stringify({ url: "file:////x/draft.html", label: "T4: the draft", task: "T4" }), "the page the ask's facts link to");
  assert.equal(rel("T7", "A9"), JSON.stringify({ url: "file:////x/new.html", label: "T7: new", task: "T7" }), "else the task's newest written report");
  assert.equal(rel("T4", ""), JSON.stringify({ url: "file:////x/r.html", label: "T4: the report", task: "T4" }));
  assert.equal(rel("T2", ""), "null", "no report written: the jump only");
  assert.match(els["pane-questions"].innerHTML, /<a data-jump="T4" data-rep="A20" title="Opens its report beside and the task in the list">Open T4 ↓<\/a>/);
  const html = read("index.html");
  assert.ok(html.includes('const rel = el.closest("#pane-questions") && relatedReport(d.jump, d.rep);'), "only the Questions tab's links open a report");
});

test("the report panel: a report that caps its own width gets the panel's width, or the panel says why not (T46)", () => {
  const html = read("index.html");
  for (const needle of ['document.getElementById("pframe").addEventListener("load", widenReport)', "[doc.documentElement, doc.body, ...doc.body.children]",
    'el.style.setProperty("max-width", "none", "important")', "This report keeps its own width: the browser does not let the page reach it.", 'id="pwide"']) {
    assert.ok(html.includes(needle), `index.html lacks: ${needle}`);
  }
  // run it against a stub report document: the body's 640 px cap and a wrapper's cap go, an uncapped child is left alone
  const els = renderPage(BOARD);
  const styled = (max) => ({ max, style: { props: {}, setProperty(k, v, p) { this.props[k] = v + (p ? " !" + p : ""); } } });
  const docEl = styled("none"), body = Object.assign(styled("640px"), { children: [styled("900px"), styled("none")] });
  const frame = els.pframe;
  frame.dataset.url = "http://x/r.html";
  frame.contentDocument = { documentElement: docEl, body, defaultView: { getComputedStyle: (el) => ({ maxWidth: el.max }) } };
  els.sandbox.widenReport();
  assert.deepEqual([docEl, body, ...body.children].map((e) => e.style.props["max-width"] || ""), ["", "none !important", "none !important", ""]);
  assert.equal(els.pwide.textContent, "");
  frame.contentDocument = null;
  els.sandbox.widenReport();
  assert.equal(els.pwide.textContent, "This report keeps its own width: the browser does not let the page reach it.");
});

test("the page: a report not written yet reads as such, muted and with no link (T46)", () => {
  const board = { ...BOARD, tasks: [{ id: "T1", status: "running", title: "x", reports: [{ label: "T1 report · pending", path: "/x/later.html", pending: true }, { label: "the plan", path: "/x/plan.html" }] }] };
  const t = renderPage(board, { tab: "tasks", open: ["T1"] })["pane-tasks"].innerHTML;
  assert.match(t, /<span class="pend" title="\/x\/later.html">T1 report <i>· not written yet<\/i><\/span>/);
  assert.ok(!/data-url="[^"]*later/.test(t), "no link to a page that does not exist");
  assert.match(t, /<a class="doc" data-url="file:\/\/\/\/x\/plan.html"/);
});

test("the page: the Tasks tab holds only the task table; the filters and sessions are in the sidebar, the collapsed rail has every filter and every session (T33, T46)", () => {
  const els = renderPage(BOARD, { tab: "tasks", filter: "run" });
  const t = els["pane-tasks"].innerHTML;
  for (const gone of ["data-f=", "class=\"filters\"", "class=\"sg", "<h2>Sessions</h2>", "Context, measured"]) assert.ok(!t.includes(gone), `the Tasks tab still has ${gone}`);
  assert.deepEqual(ids(t, /data-task="(T\d+)" id=/g), ["T2", "T5"]);
  const side = els.sidefilters.innerHTML;
  assert.deepEqual(ids(side, /data-go="(\w+)"><span>/g), ["open", "wait", "run", "block", "pend", "queue", "done", "all", "initial", "added"], "every filter");
  assert.match(side, /<button class="srow on" data-go="run"><span>Running<\/span><span class="n hot k-run">2<\/span>/, "the chosen filter is marked, with its count");
  assert.match(side, /class="srow first-origin" data-go="initial"><span>Initial<\/span><span class="n">2<\/span>/);
  assert.match(side, /data-go="added"><span>Added later<\/span><span class="n">6<\/span>/);
  assert.ok(renderPage({ ...BOARD, tasks: BOARD.tasks.filter((x) => !x.blocked) }).sidefilters.innerHTML.includes("data-go=\"block\""), "the user, 11-27: \"whole tasks status filter\": Blocked stays at 0");
  // the rail (88 px): every filter as a count circle and a word, then every session as dot, % and bar (the canvas's Rail artboard)
  const r = els.railcounts.innerHTML;
  assert.deepEqual(ids(r, /data-go="([\w-]+)"/g), ["open", "wait", "run", "block", "pend", "queue", "done", "all", "initial", "added"]);
  assert.match(r, /<button class="rc" data-go="open" title="Show the open tasks"><i class="">7<\/i>open<\/button>/);
  assert.match(r, /<button class="rc on" data-go="run" title="Show the running tasks"><i class="k-run">2<\/i>running<\/button>/, "the chosen filter is ringed");
  assert.match(r, /<i class="k-wait">2<\/i>for you<\/button>/);
  assert.match(r, /<i class="k-unread">1<\/i>to read<\/button>/);
  assert.match(r, /<div class="rs" title="w-a · working \(busy\) · T2 build"><span class="dot busy" style="margin:0"><\/span><b>10%<\/b><div class="bar"><span class="" style="width:10%"><\/span><\/div>a<\/div>/);
  assert.ok(read("index.html").includes("#rail { width:88px;") && read("index.html").includes("#side { width:420px;"), "the rail is 88 px, the sidebar 420 px");
});

test("the page: every open question is a full card, one under another, oldest first, none folded (T33)", () => {
  const many = Array.from({ length: 11 }, (_, i) => ({ id: "A" + (60 + i), task: "T1", state: "open", asked: "01-02", question: "Question " + (60 + i) + "?", facts: [{ label: "Why", text: "w" }], recommend: "Yes" }));
  const q = renderPage({ ...BOARD, asks: [...many.slice().reverse(), ...BOARD.asks.filter((a) => a.state === "answered")] })["pane-questions"].innerHTML;
  assert.deepEqual(ids(q, /<div class="ask" id="ask-(A\d+)">/g), many.map((a) => a.id));
  assert.equal((q.match(/<h3>Question \d+\?<\/h3>/g) || []).length, 11, "each open ask shows its whole question");
  assert.ok(q.indexOf("ask-A70") < q.indexOf("<details"), "open asks come before the folded Answered list, never inside it");
  const css = read("index.html").match(/\n {2}\.ask \{([^}]*)\}/)[1];
  assert.ok(!/grid|columns|flex/.test(css), "an ask card is a block: the cards stack");
});

test("the page: the report panel is open by default with an empty state and the newest unread reports; its width is kept, clamped to 300 and to what leaves the list 560 px (T33, T46)", () => {
  const els = renderPage(BOARD, { tab: "tasks" });
  const cl = els.sandbox.document.body.classList;
  assert.ok(cl.contains("withpanel") && cl.contains("panel-empty"), "open with nothing selected");
  assert.match(els.pempty.innerHTML, /Nothing opened yet\. Click a report link in a row and it opens here, beside the list\./);
  assert.match(els.pempty.innerHTML, /<h4>Newest unread reports<\/h4><div class="ur"><i class="rd"><\/i><div><a class="doc" data-url="file:\/\/\/\/x\/r.html" data-label="T4: the report" data-task="T4">the report<\/a><div class="tt">T4 · pending report<\/div>/);
  assert.equal(els.panelchip.textContent, "Hide panel");
  // the canvas draws the Jira page without it: empty, it sits beside Tasks and Questions only; closed by the user, it stays closed
  assert.ok(!renderPage(BOARD, { tab: "jira" }).sandbox.document.body.classList.contains("withpanel"));
  assert.ok(!renderPage(BOARD, { tab: "tasks", panelOpen: false }).sandbox.document.body.classList.contains("withpanel"));
  assert.equal(renderPage(BOARD, { tab: "tasks", panelOpen: false }).panelchip.textContent, "Show panel");
  const report = { url: "file:///x/r.html", label: "T4: the report", task: "T4" };
  assert.ok(!renderPage(BOARD, { tab: "jira", panel: report }).sandbox.document.body.classList.contains("panel-empty"), "a report open keeps the panel on every tab");
  assert.equal(renderPage(BOARD).rootStyle["--pw"], "300px");
  assert.equal(renderPage(BOARD, { panelw: 400 }).rootStyle["--pw"], "400px");
  assert.equal(renderPage(BOARD, { panelw: 2000 }).rootStyle["--pw"], "460px", "1440 - 420 sidebar - 560");
  assert.equal(renderPage(BOARD, { panelw: 100 }).rootStyle["--pw"], "300px");
  assert.equal(renderPage(BOARD, { width: 1024, panelw: 2000 }).rootStyle["--pw"], "904px", "under 1200 it lies over the list: the window less 120");
  // beside the panel the list goes tight (status and reports under the title) once it is under 660 px
  assert.ok(!renderPage(BOARD).main.classList.contains("tight"), "1440 - 428 - 24 - 300 = 688");
  assert.ok(renderPage(BOARD, { panelw: 400 }).main.classList.contains("tight"));
  assert.ok(!renderPage(BOARD, { width: 1024, panelw: 400 }).main.classList.contains("tight"));
});

test("the page: pending report has its own pill, filter and count, is not waiting, and Mark seen moves it to Done here (A62, A64)", () => {
  const els = renderPage(BOARD, { tab: "tasks", open: ["T4"] });
  const t = els["pane-tasks"].innerHTML;
  assert.match(t, /<span class="pill k-unread">Pending report<\/span>/);
  assert.match(t, /<button class="btn seen" data-seen="T4"[^>]*>Mark seen ✓/, "under Show more");
  // the user, 11-26: "status 'pending report' must be different to btn 'mark seens'": the button is outlined and neutral
  const seenCss = read("index.html").match(/\.btn\.seen \{([^}]*)\}/)[1];
  assert.match(seenCss, /background:transparent/);
  assert.match(seenCss, /border:1px solid var\(--text-3\)/);
  assert.ok(!/unread/.test(seenCss), "Mark seen does not take the Pending report colour");
  assert.match(els.sidefilters.innerHTML, /data-go="pend"><span>Pending report<\/span><span class="n hot k-unread">1<\/span>/);
  assert.match(els.sidefilters.innerHTML, /data-go="wait"><span>Waits for you<\/span><span class="n hot k-wait">2<\/span>/, "T7 and T1 (its open ask) wait; T4 does not");
  const seen = renderPage(BOARD, { tab: "tasks", seen: { T4: "01-02 11:00" } });
  const s = seen["pane-tasks"].innerHTML;
  assert.match(seen.sidefilters.innerHTML, /data-go="done"><span>Done<\/span><span class="n">3<\/span>/, "T4 seen here counts as done");
  assert.match(s, /seen on the task page: T4 \(01-02 11:00\)/);
  assert.ok(seen.readchip.classList.contains("hide"));
  // once tasks.js says done, the browser's mark is dropped and the line for the master goes
  const folded = renderPage({ ...BOARD, tasks: BOARD.tasks.map((x) => (x.id === "T4" ? { ...x, status: "done" } : x)) }, { tab: "tasks", seen: { T4: "01-02 11:00" } });
  assert.ok(!folded["pane-tasks"].innerHTML.includes("seen on the task page"));
});

test("the page: one card per epic by epic id, the id big and bold, backend before frontend, the Jira status beside its key (T46)", () => {
  const j = renderPage(BOARD, { tab: "jira" })["pane-jira"].innerHTML;
  assert.deepEqual(ids(j, /<div class="eid">(EPIC-\d+)<\/div>/g), ["EPIC-0031", "EPIC-0036"]);
  assert.deepEqual(ids(j, /\b(KEY-\d)\b/g), ["KEY-0", "KEY-1", "KEY-2"]);
  assert.match(j, /KEY-1 <span class="mut3">In Progress<\/span>/);
  assert.match(j, /KEY-2 <span class="mut3">To Review<\/span>/);
  assert.match(j, /<span>Bug · someone<\/span><span>review: <b style="color:var\(--text\)">blocked<\/b> · gate red<\/span><span class="warn">check review: failure<\/span>/);
  assert.match(j, /<b>backend<\/b>[\s\S]*<b>frontend<\/b>/, "backend first");
  assert.match(j, /<div class="big">6 of 6<small>landed<\/small><\/div>/, "x of y landed, the largest figure on the line");
  assert.match(renderPage({ ...BOARD, epics: [{ epic: "EPIC-0020", repos: [{ repo: "backend", pr: "#1", tasks: "all landed" }, { repo: "frontend", pr: "#2", tasks: "-" }] }] }, { tab: "jira" })["pane-jira"].innerHTML,
    /<div class="big">all<small>landed<\/small><\/div>[\s\S]*<div class="big dim">no task count<\/div>/, "\"all landed\" is shown as all; no count as no task count");
  assert.match(j, /<span class="mut warn" title="draft · mergeable, unstable">draft · mergeable, unstable<\/span>/);
  assert.match(j, /<div class="lh"><h2>Epics and Jira<\/h2><span class="cap">2 epics · by epic id; backend before frontend<\/span><span class="sw"><button data-all="jira"/);
  assert.match(j, /brain origin · 21:35/);
  assert.ok(read("index.html").includes(".ep .el .eid { font-size:22px; font-weight:800;"), "the epic id is 22 px, weight 800 (the canvas)");
  const empty = renderPage({ ...BOARD, epics: [] }, { tab: "jira" })["pane-jira"].innerHTML;
  assert.match(empty, /no rows recorded/);
});

test("the page: no commit id on the Jira tab, and each repo line has a one-line event log (T46)", () => {
  const board = { ...BOARD, epics: [{ epic: "EPIC-0031", what: "a", stamps: "dev_review 2026-11-27 · head f01fca9b20", repos: [
    { repo: "backend", pr: "#7", prState: "open · mergeable · head f01fca9b20 (11-27 14:11)", review: { verdict: "fixed-clean (human round, edc4a9b3e3)", note: "ok" },
      last: "11:00 · merged the collector in (a5179404b2, suite green)", log: ["11-27 14:04 · collector merged in (a5179404b2, suite green) (T49)", { at: "11-27 13:50", text: "review closed" }, "no stamp here"] },
    { repo: "frontend", pr: "#8", last: "21:35 · merged" }] }] };
  const j = renderPage(board, { tab: "jira" })["pane-jira"].innerHTML;
  assert.deepEqual(j.replace(/data-[^=]+="[^"]*"/g, "").match(/\b[0-9a-f]{7,40}\b/g) || [], [], "no commit id anywhere on the tab");
  assert.match(j, /open · mergeable<\/span>/);
  assert.match(j, /<b style="color:var\(--text\)">fixed-clean \(human round\)<\/b>/);
  assert.match(j, /<div class="lg"><div title="11-27 14:04 collector merged in \(suite green\) \(T49\)"><b>11-27 14:04<\/b>collector merged in \(suite green\) \(T49\)<\/div><div title="11-27 13:50 review closed"><b>11-27 13:50<\/b>review closed<\/div><div title=" no stamp here"><b><\/b>no stamp here<\/div><\/div>/, "log[] lines, each with its stamp");
  assert.match(j, /<div class="lg"><div title="21:35 merged"><b>21:35<\/b>merged<\/div><\/div>/, "no log[]: the single last line");
});

test("the page: the Jira tab dates each repo line; the freshness is amber only past 2 hours, with the command that reads it again (T46)", () => {
  const p = (n) => String(n).padStart(2, "0");
  const at = (h) => { const d = new Date(Date.now() - h * 3600000); return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`; };
  const fresh = at(0.5), old = at(10);
  const board = { ...BOARD, epicsAsOf: { gh: fresh, Jira: fresh, board: old }, epics: [
    { epic: "EPIC-0031", what: "a", repos: [{ repo: "backend", pr: "#1", asOf: fresh, jira: { key: "KEY-1", status: "Done", category: "done" } }] },
    { epic: "EPIC-0036", what: "b", repos: [{ repo: "backend", pr: "#2", asOf: old }, { repo: "frontend", pr: "#3" }] }] };
  const j = renderPage(board, { tab: "jira" })["pane-jira"].innerHTML;
  assert.match(j, new RegExp(`<span class="fresh">checked ${fresh} · 3\\d min ago</span>`), "a fresh read is plain");
  assert.match(j, new RegExp(`<span class="fresh amber">checked ${old} · 10 h ago</span>`), "past 2 h it turns amber");
  assert.match(j, new RegExp(`<span class="fresh">checked ${fresh} · 3\\d min ago</span></div></div></div></div>`), "a line with no read time of its own takes the oldest gh or Jira read, not the board's");
  assert.match(j, new RegExp(`<span class="" title="${fresh}">gh · ${fresh}</span><span class="" title="${fresh}">Jira · ${fresh}</span><span class="amber" title="${old}">board · ${old} · older than 2 h</span>`), "each source, amber when older than 2 h");
  assert.match(j, /The master reads these lines again with <code>node sync-epics\.mjs<\/code>/);
  const none = renderPage({ ...BOARD, epicsAsOf: {} }, { tab: "jira" })["pane-jira"].innerHTML;
  assert.match(none, /No read time recorded: the lines below may be old/);
  assert.match(none, /<span class="fresh amber">no read time<\/span>/);
});

test("the page: Jira keys and PR numbers link to Jira and GitHub in a new tab, on the Jira tab and in task titles and lines; no URL, no link (T46)", () => {
  const J = "https://jira.example/browse/KEY-1", PR = "https://github.com/o/back/pull/7";
  const board = { ...BOARD, epics: [
    { epic: "EPIC-0031", what: "a", repos: [
      { repo: "backend", pr: "#7", prUrl: PR, jira: { key: "KEY-1", status: "Done", category: "done", url: J } },
      { repo: "frontend", pr: "#8", jira: { key: "KEY-2", status: "To Do", category: "new" } },
      { repo: "backend", pr: "#9", url: "https://github.com/o/back/pull/9" },
      { repo: "frontend", pr: "#9", url: "https://github.com/o/front/pull/9" }] }],
    tasks: [...BOARD.tasks.filter((t) => t.id !== "T1"), { id: "T1", status: "running", title: "Fix KEY-1 and PR #7, then #9 and KEY-2", sub: ["10:00 · pushed to #7 for KEY-1"] }] };
  const j = renderPage(board, { tab: "jira" })["pane-jira"].innerHTML;
  assert.match(j, new RegExp(`<a class="ext" href="${PR}" target="_blank" rel="noopener">PR #7</a> <a class="ext" href="${PR}" target="_blank" rel="noopener"><span class="nw">↗</span></a>`), "prUrl, the live board's field; the PR and its ↗");
  assert.match(j, /<a class="ext" href="https:\/\/github\.com\/o\/front\/pull\/9" target="_blank" rel="noopener">PR #9<\/a>/, "url, the template's field");
  assert.match(j, new RegExp(`<a class="ext" href="${J}" target="_blank" rel="noopener">KEY-1</a> <a class="ext" href="${J}" target="_blank" rel="noopener"><span class="nw">↗</span></a>`));
  assert.match(j, /<span>PR #8<\/span>/, "no PR URL: plain text, no arrow");
  assert.match(j, /<span>KEY-2 <span class="mut3">To Do<\/span><\/span>/, "no Jira URL: plain text");
  const t = renderPage(board, { tab: "tasks", open: ["T1"] })["pane-tasks"].innerHTML;
  const row = t.match(/<div class="ti"[^>]*>([\s\S]*?)<\/div><div class="more">/)[1];
  assert.equal(row, `Fix <a class="ext" href="${J}" target="_blank" rel="noopener">KEY-1</a> and PR <a class="ext" href="${PR}" target="_blank" rel="noopener">#7</a>, then #9 and KEY-2`,
    "#9 is in two repos and KEY-2 has no URL: both stay plain");
  assert.match(t, new RegExp(`pushed to <a class="ext" href="${PR}"[^>]*>#7</a> for <a class="ext" href="${J}"`), "a task's lines link them too");
  assert.match(t, /title="Fix KEY-1 and PR #7, then #9 and KEY-2"/, "the tooltip stays plain text");
  const evil = renderPage({ ...board, epics: [{ epic: "EPIC-0031", repos: [{ repo: "backend", pr: "#7", prUrl: "javascript:alert(1)", jira: { key: "KEY-1", url: "http://x\"onmouseover=1" } }] }] }, { tab: "jira" })["pane-jira"].innerHTML;
  assert.ok(!/javascript:|onmouseover|class="ext"/.test(evil), "only https links, nothing else");
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

// a tasks.js as a master edits it by hand: quoted keys, one-space indent (the live board of 2026-11-27)
const HAND_EDITED = [
  "window.DASH = {",
  ' "workSet": "w",',
  ' "updated": "2026-01-02 08:00",',
  '  sessionsAsOf: "08:00",',
  "  sessions: [",
  '    { name: "old", state: "clean", model: "-", job: "-", context: "-" }',
  "  ],",
  ' "asks": [],',
  ' "epicsAsOf": {',
  '  "gh": "01-01 08:00"',
  " },",
  ' "epics": [',
  '  { "epic": "EPIC-0001", "what": "w [x] {y}", "repos": [',
  '   { "repo": "backend", "pr": "#5", "url": "https://github.com/o/r/pull/5", "prState": "old", "check": "check old: failure", "jira": { "key": "KEY-1", "status": "To Do", "category": "new" } },',
  '   { "repo": "frontend", "pr": "#6", "prState": "old", "jira": { "key": "KEY-404", "status": "To Do", "category": "new" } }',
  "  ] }",
  " ],",
  ' "tasks": [{"id":"T1","title":"keeps ] and } in strings","status":"done"}]',
  "};",
  "",
].join("\n");

test("sync-sessions.mjs also rewrites a hand-edited tasks.js, quoted keys and all (T46)", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "task-page-test-"));
  try {
    fs.copyFileSync(path.join(TEMPLATE, "sync-sessions.mjs"), path.join(dir, "sync-sessions.mjs"));
    fs.writeFileSync(path.join(dir, "tasks.js"), HAND_EDITED);
    const fake = path.join(dir, "fake-puppet.mjs");
    fs.writeFileSync(fake, 'console.log("w-1  99538  10%  busy  (window 1000000 from default)  model claude-sonnet-5-5 medium  interactive worker active build  mod on (asked)");\n');
    execFileSync("node", [path.join(dir, "sync-sessions.mjs"), "--puppet", fake, "--file", path.join(dir, "tasks.js")], { encoding: "utf8" });
    const sandbox = { window: {} };
    vm.runInNewContext(fs.readFileSync(path.join(dir, "tasks.js"), "utf8"), sandbox);
    assert.equal(JSON.stringify(sandbox.window.DASH.sessions.map((s) => s.name)), '["w-1"]');
    assert.notEqual(sandbox.window.DASH.updated, "2026-01-02 08:00", "the quoted \"updated\" is rewritten too");
    assert.equal(sandbox.window.DASH.tasks[0].title, "keeps ] and } in strings");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("sync-epics.mjs reads each PR with gh and each Jira key, rewrites only the epics, and lists and exits 2 on what it could not read (T46)", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "task-page-test-"));
  try {
    fs.copyFileSync(path.join(TEMPLATE, "sync-epics.mjs"), path.join(dir, "sync-epics.mjs"));
    fs.writeFileSync(path.join(dir, "tasks.js"), HAND_EDITED);
    const gh = path.join(dir, "fake-gh.mjs");
    fs.writeFileSync(gh, [
      "const a = process.argv.slice(2);",
      'if (a[0] !== "pr" || a[1] !== "view" || !a.includes("--json")) process.exit(9);',
      'const n = a[2].replace(/^.*\\//, "");',
      'console.log(JSON.stringify({ state: "OPEN", isDraft: n === "6", mergeable: "MERGEABLE", mergeStateStatus: "UNSTABLE", headRefOid: "abcdef0123456789",',
      '  statusCheckRollup: [{ name: "build", conclusion: "SUCCESS" }, ...(n === "6" ? [{ name: "lint", conclusion: "FAILURE" }] : [])], url: "https://github.com/o/f/pull/" + n }));',
    ].join("\n"));
    const jira = path.join(dir, "fake-jira.mjs");
    fs.writeFileSync(jira, [
      "const [key, flag] = process.argv.slice(2);",
      'if (flag !== "--json") process.exit(9);',
      'if (key === "KEY-404") { console.error("jira: KEY-404 not found"); process.exit(1); }',
      'console.log(JSON.stringify({ key, type: "Bug", status: { name: "In Review", category: "indeterminate" }, assignee: "someone" }));',
    ].join("\n"));
    const file = path.join(dir, "tasks.js");
    const runIt = (extra) => {
      try { return { code: 0, out: execFileSync("node", [path.join(dir, "sync-epics.mjs"), "--file", file, "--gh", gh, "--jira", jira, ...extra], { encoding: "utf8", stdio: "pipe" }) }; }
      catch (e) { return { code: e.status, out: String(e.stdout) }; }
    };
    // frontend #6 has no url and no --repo: its PR is not read, and KEY-404 fails
    const first = runIt([]);
    assert.equal(first.code, 2);
    assert.match(first.out, /read {4}EPIC-0001 backend #5: ready · mergeable, unstable \(head abcdef0123\)/);
    assert.match(first.out, /read {4}EPIC-0001 backend #5: KEY-1 In Review \(indeterminate\)/);
    assert.match(first.out, /NOT READ EPIC-0001 frontend #6: PR not read \(no PR url, and no --repo frontend=<owner\/repo>\)/);
    assert.match(first.out, /NOT READ EPIC-0001 frontend #6: KEY-404 not read \(jira: KEY-404 not found\)/);
    let sb = { window: {} };
    vm.runInNewContext(fs.readFileSync(file, "utf8"), sb);
    let [be, fe] = sb.window.DASH.epics[0].repos;
    assert.equal(be.prState, "ready · mergeable, unstable (head abcdef0123)");
    assert.ok(!("check" in be), "a check that passes now is dropped");
    assert.deepEqual({ ...be.jira }, { key: "KEY-1", status: "In Review", category: "indeterminate", type: "Bug", assignee: "someone" });
    assert.match(be.asOf, /^\d\d-\d\d \d\d:\d\d$/);
    assert.equal(fe.prState, "old", "a line it could not read keeps its values");
    assert.ok(!("asOf" in fe), "and gets no read time, so it never shows as fresh");
    assert.equal(sb.window.DASH.epics[0].what, "w [x] {y}");
    assert.equal(sb.window.DASH.tasks[0].title, "keeps ] and } in strings", "the rest of the file is untouched");
    assert.equal(sb.window.DASH.epicsAsOf.gh, be.asOf);
    // with --repo the frontend PR is read by number, its failing check named
    const second = runIt(["--repo", "frontend=o/f"]);
    assert.equal(second.code, 2, "KEY-404 still fails");
    sb = { window: {} };
    vm.runInNewContext(fs.readFileSync(file, "utf8"), sb);
    [be, fe] = sb.window.DASH.epics[0].repos;
    assert.equal(fe.prState, "draft · mergeable, unstable (head abcdef0123)");
    assert.equal(fe.check, "check lint: failure");
    assert.equal(fe.url, "https://github.com/o/f/pull/6");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("the report panel: the frame keeps its pointer events while dragged, and a drag always ends (T46)", () => {
  const html = read("index.html");
  // the cause, found in Playwright: a drag that resized the frame while it had pointer-events:none left the report unable to scroll by wheel
  assert.ok(!/#pframe \{[^}]*pointer-events:\s*none/.test(html), "the report's frame never loses its pointer events");
  for (const end of ['grip.addEventListener("pointerup", endDrag)', 'grip.addEventListener("pointercancel", endDrag)', 'grip.addEventListener("lostpointercapture", endDrag)',
    'window.addEventListener("blur", endDrag)', 'window.addEventListener("pointerup", endDrag)', "!(e.buttons & 1)) endDrag(e)"]) assert.ok(html.includes(end), `no ${end}`);
});

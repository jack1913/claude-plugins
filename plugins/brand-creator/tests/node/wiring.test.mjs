import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import http from "node:http";
import { spawn } from "node:child_process";
import { needSetup, tmpdir, ROOT, DATA } from "./_helpers.mjs";

// `render.mjs wiring <url>`: the wiring of a page of the owner's own local server, read from the DOM (scripts/pagelib/wiring.mjs). The server is one of this process on
// 127.0.0.1, port 0: loopback is this machine, not the network these tests must stay off, and nothing here reaches another machine. The command is run asynchronously
// (a synchronous child would block the server that has to answer it).

const RENDER = path.join(ROOT, "scripts", "render.mjs");

function render(args, data = DATA) {
  return new Promise((resolve, reject) => {
    const c = spawn(process.execPath, [RENDER, ...args], { env: { ...process.env, BRAND_CREATOR_DATA: data } });
    let stdout = "", stderr = "";
    c.stdout.on("data", (d) => { stdout += d; });
    c.stderr.on("data", (d) => { stderr += d; });
    c.on("error", reject);
    c.on("close", (status) => resolve({ status, stdout, stderr }));
  });
}

function listen(handler) {
  const hits = [];
  const srv = http.createServer((req, res) => { hits.push(req.url); handler(req, res); });
  return new Promise((ok) => srv.listen(0, "127.0.0.1", () => ok({ hits, port: srv.address().port, close: () => new Promise((done) => srv.close(done)) })));
}

// Every kind once or more, written by hand. The page is also changed by a script, which the DOM shows and the source does not.
const PAGE = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Shop</title>
<meta name="viewport" content="width=device-width"><link rel="stylesheet" href="/css/site.css"><base href="/"><script src="./js/app.js?v=3"></script></head>
<body id="top">
<a href="/">Home</a> <a href="#">to the top</a> <a href="">nowhere</a> <a href="#main" data-testid="skip-link">Skip</a> <a href="/products?sort=new#list"
   id="products">Products</a>
<map name="areas"><area href="/map-target" alt="a"></map>
<form action="/signup" method="post" id="signup-form" data-analytics-form="signup">
  <input name="email" id="email" data-cy="email-input">
  <select name="plan"><option>free</option></select>
  <textarea name="note"></textarea>
  <button name="go" formaction="/signup/express" onclick="track('signup')" data-gtm-event="signup-click" data-testimonial="not a hook" data-track-click="">Go</button>
  <meta name="not-a-field"><iframe name="not-a-field-either"></iframe>
</form>
<p id="has space">no</p><p id="{{ template }}">no</p><p id="">no</p><p data-test="x">y</p><p data-qa="  a   b  ">z</p>
<div one="1" onmouseover="hover()" ondragstart="">events</div>
<script src="https://analytics.example.com/tag.js"></script>
<script>
  const a = document.createElement("a");
  a.setAttribute("href", "/from-script");
  a.setAttribute("data-testid", "from-script");
  a.id = "from-script-id";
  document.body.append(a);
</script>
</body></html>`;

const EXPECTED = {
  link: ["/", "#main", "/products?sort=new#list", "/map-target", "/signup", "/signup/express", "/from-script"],
  field: ["email", "plan", "note", "go"],
  handler: ["onclick=track('signup')", "onmouseover=hover()"],
  hook: ["data-testid=skip-link", "data-analytics-form=signup", "data-cy=email-input", "data-gtm-event=signup-click", "data-test=x", "data-qa=a b", "data-testid=from-script"],
  id: ["top", "products", "signup-form", "email", "from-script-id"],
  script: ["js/app.js", "https://analytics.example.com/tag.js"],
};

test("wiring: a page on 127.0.0.1 gives its links, fields, ids, hooks, scripts and inline handlers", async (t) => {
  if (needSetup(t)) return;
  const srv = await listen((req, res) => {
    if (req.url === "/page") { res.writeHead(200, { "content-type": "text/html; charset=utf-8" }); res.end(PAGE); } else { res.writeHead(404); res.end(); }
  });
  try {
    const r = await render(["wiring", `http://127.0.0.1:${srv.port}/page`]);
    assert.equal(r.status, 0, r.stdout + r.stderr);
    assert.equal(r.stdout.trim().split("\n").length, 1, "one line of JSON, nothing else on stdout");
    const got = JSON.parse(r.stdout);
    assert.deepEqual(Object.keys(got), ["link", "field", "handler", "hook", "id", "script"]);
    assert.deepEqual(got, EXPECTED);   // as written, never resolved (`/` is not `http://127.0.0.1:.../`); the page's own request for js/app.js and the stylesheet gave 404s that change nothing
    // a page with none of them still answers every kind
    const empty = await listen((req, res) => { res.writeHead(200, { "content-type": "text/html" }); res.end("<!doctype html><title>t</title><p>nothing</p>"); });
    try {
      const e = await render(["wiring", `http://127.0.0.1:${empty.port}/`]);
      assert.equal(e.status, 0, e.stdout + e.stderr);
      assert.deepEqual(JSON.parse(e.stdout), { link: [], field: [], handler: [], hook: [], id: [], script: [] });
    } finally { await empty.close(); }
  } finally { await srv.close(); }
});

test("wiring: a long value is cut at 120 characters and a redirect that stays home is followed", async (t) => {
  if (needSetup(t)) return;
  const long = "/" + "x".repeat(200);
  const srv = await listen((req, res) => {
    if (req.url === "/old") { res.writeHead(302, { location: "/new" }); res.end(); return; }
    res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    res.end(`<!doctype html><title>t</title><a href="${long}">l</a><input name="${"é".repeat(130)}">`);
  });
  try {
    const r = await render(["wiring", `http://127.0.0.1:${srv.port}/old`]);
    assert.equal(r.status, 0, r.stdout + r.stderr);
    const got = JSON.parse(r.stdout);
    assert.deepEqual(got.link, [long.slice(0, 120)]);
    assert.deepEqual(got.field, ["é".repeat(120)]);
    assert.ok(srv.hits.includes("/new"));
  } finally { await srv.close(); }
});

test("wiring: a URL that is not loopback is refused with exit 2", async () => {
  const data = DATA || tmpdir("bc-node-data-");   // refused before any browser is started: no set-up data is needed
  for (const url of ["https://example.com/", "http://localhost.evil.test/", "http://user:secret@localhost/", "file:///etc/hosts", "http://127.1/", "http://0x7f000001/", "http://[0:0:0:0:0:0:0:1]/", "localhost:8000", ""]) {
    const r = await render(["wiring", url], data);
    assert.equal(r.status, 2, `${url}: ${r.stdout}${r.stderr}`);
    assert.match(r.stderr, /the wiring is read from your own local server/);
    assert.equal(r.stdout, "");
  }
  const none = await render(["wiring"], data);
  assert.equal(none.status, 2);
  assert.match(none.stderr, /exactly one URL/);
  const two = await render(["wiring", "http://127.0.0.1:1/", "http://127.0.0.1:2/"], data);
  assert.equal(two.status, 2);
});

test("wiring: a page that does not load, or whose server is gone, is exit 3 and prints nothing", async (t) => {
  if (needSetup(t)) return;
  let gone = false;   // a server that is gone keeps its port and resets every connection: a port that was freed could be taken by another server before the page is asked for
  const srv = await listen((req, res) => {
    if (gone) { req.socket.resetAndDestroy(); return; }
    if (req.url === "/broken") { res.writeHead(500); res.end("no"); return; }
    if (req.url === "/away") { res.writeHead(302, { location: "http://example.invalid/elsewhere" }); res.end(); return; }
    res.writeHead(404); res.end();
  });
  const base = `http://127.0.0.1:${srv.port}`;
  try {
    for (const [p, needle] of [["/missing", "answered 404"], ["/broken", "answered 500"], ["/away", "example.invalid"]]) {
      const r = await render(["wiring", base + p]);
      assert.equal(r.status, 3, `${p}: ${r.stdout}${r.stderr}`);
      assert.match(r.stderr, new RegExp(needle));
      assert.equal(r.stdout, "");
    }
    gone = true;   // the server has stopped answering
    const r = await render(["wiring", base + "/"]);
    assert.equal(r.status, 3, r.stdout + r.stderr);
    assert.match(r.stderr, /could not read the wiring of /);
    assert.doesNotMatch(r.stderr, /answered/, "the server hung up; it did not answer with a status");
    assert.ok(srv.hits.includes("/"), "the page was asked for, and the server hung up");
    assert.equal(r.stdout, "");
  } finally { await srv.close(); }
});

test("wiring: a data directory that was never set up is exit 3, prints nothing and opens no page", async () => {
  const srv = await listen((req, res) => { res.writeHead(200, { "content-type": "text/html" }); res.end("<!doctype html><title>t</title>"); });
  try {
    const r = await render(["wiring", `http://127.0.0.1:${srv.port}/`], tmpdir("bc-node-data-"));   // no setup.json: no Chromium to start
    assert.equal(r.status, 3, r.stdout + r.stderr);
    assert.match(r.stderr, /setup has not been run/);
    assert.equal(r.stdout, "");
    assert.deepEqual(srv.hits, [], "the page was not asked for");
  } finally { await srv.close(); }
});

// Static and dry-run tests of the opt-in workflows (workflows/*.js) and the agent files (agents/*.md).
// Nothing here calls a model: the workflows run in fleet_plan.mjs's sandbox with stub agents.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { ROOT, tmpdir, bc } from "./_helpers.mjs";

process.env.BRAND_CREATOR_DATA = process.env.BRAND_CREATOR_DATA || tmpdir("bc-node-nodata-");
const F = await import(path.join(ROOT, "scripts/fleet_plan.mjs"));
const WF = path.join(ROOT, "workflows");
const NAMES = ["adopt", "directions", "naming", "review-panel"];
const agents = F.readAgents(ROOT);
const RULES = F.RULES_LINE();
const TEST_LINE = "TEST: screenshot 1440×900 light+dark and 390×844, Read every tile, iterate at least twice; print one-line check (overflow, errors, requests, non-whole images).";
const fixture = (n) => JSON.parse(fs.readFileSync(path.join(ROOT, "tests/fixtures/fleet", `${n}.json`), "utf8"));
const run = (n, args, o) => F.dryRun(path.join(WF, `${n}.js`), args, o);

/** A scratch copy of one workflow with `edit` applied; asserts the edit changed the text. */
function mutated(n, from, to) {
  const src = fs.readFileSync(path.join(WF, `${n}.js`), "utf8");
  assert.ok(src.includes(from), `mutation anchor not found in ${n}.js: ${from}`);
  const out = src.replace(from, to);
  assert.notEqual(out, src);
  const d = tmpdir("bc-wf-mut-");
  const f = path.join(d, `${n}.js`);
  fs.writeFileSync(f, out);
  return f;
}

test("the plugin ships exactly the planned workflows and agents", () => {
  assert.deepEqual(fs.readdirSync(WF).filter((f) => f.endsWith(".js")).sort(), NAMES.map((n) => `${n}.js`));
  assert.deepEqual(Object.keys(agents).sort(), ["brand-designer", "brand-implementer", "brand-inventory", "brand-judge", "brand-namer", "brand-researcher", "brand-reviewer"]);
});

test("every workflow passes the static checks and every agent file the agent checks", () => {
  assert.deepEqual(F.agentProblems(agents), []);
  for (const n of NAMES) assert.deepEqual(F.staticProblems(path.join(WF, `${n}.js`), agents), [], n);
  const r = bc(["fleet-plan", "--check"]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /PASS: 7 agents, 4 workflows checked/);
});

test("meta is a pure literal with name = file name, description and phases; a computed meta is refused", () => {
  for (const n of NAMES) {
    const { meta } = F.loadWorkflow(path.join(WF, `${n}.js`));
    assert.equal(meta.name, n);
    assert.ok(meta.description.startsWith("brand-creator"), n);
    assert.ok(Array.isArray(meta.phases) && meta.phases.length >= 2, n);
  }
  assert.deepEqual(F.literalProblems("{ name: 'x', description: \"y\", phases: [{ title: 'A' }], n: 2, ok: true }"), []);
  for (const bad of ["{ name: NAME }", "{ name: 'x' + 'y' }", "{ name: `x` }", "{ ...base, name: 'x' }", "{ name: f() }"]) {
    assert.ok(F.literalProblems(bad).length > 0, bad);
  }
  const f = mutated("naming", "name: 'naming',", "name: 'nam' + 'ing',");
  assert.throws(() => F.loadWorkflow(f), /meta must be a pure literal/);
});

test("the default path of every workflow starts fewer than 5 agents, all of known brand-creator types", async () => {
  const want = { directions: 4, "review-panel": 4, naming: 4, adopt: 2 };
  for (const n of NAMES) {
    const r = await run(n, fixture(n));
    assert.equal(r.error, null, `${n}: ${r.error}`);
    assert.equal(r.calls.length, want[n], n);
    assert.ok(r.calls.length < 5, n);
    for (const c of r.calls) {
      assert.match(c.agentType, /^brand-creator:brand-[a-z]+$/, n);
      assert.ok(agents[c.agentType.slice("brand-creator:".length)], c.agentType);
      assert.ok(c.prompt.split("\n").includes(RULES), `${n} call ${c.n}: RULES line not verbatim`);
      assert.equal(c.isolation, null);
      assert.ok(c.schema, `${n} call ${c.n}: outputs read by the script use a schema`);
      assert.match(c.prompt, /Aim to finish within \d+ minutes/, `${n} call ${c.n}: time box`);
    }
  }
});

test("designers write only to disjoint round folders and carry the TEST line verbatim; the judge cannot write", async () => {
  const r = await run("directions", fixture("directions"));
  const designers = r.calls.filter((c) => c.agentType === "brand-creator:brand-designer");
  const folders = designers.map((c) => /you write ONLY inside (\S+)/.exec(c.prompt)[1]);
  assert.deepEqual(folders, ["rounds/r1/compass/", "rounds/r1/lantern/", "rounds/r1/harbor/"]);
  for (const c of designers) {
    assert.ok(c.prompt.startsWith(TEST_LINE) || c.prompt.includes("\n" + TEST_LINE), "TEST line verbatim");
    assert.match(c.prompt, /snapshot take .* --ignore '\*rounds\/r1\/\*'/);
    assert.match(c.prompt, /do not start over blindly/);
    for (const other of folders) if (!c.prompt.includes(`ONLY inside ${other}`)) assert.ok(!c.prompt.includes(other), "a designer prompt names another designer's folder");
  }
  assert.deepEqual(agents["brand-judge"].tools, ["Read", "Grep", "Glob"]);
  assert.ok(!agents["brand-reviewer"].tools.some((t) => ["Write", "Edit", "Agent", "NotebookEdit"].includes(t)));
});

test("a designer that writes outside its folder or changes the project is reported as a violation", async () => {
  const r = await run("directions", fixture("directions"), {
    respond: (c) => c.label === "Lantern"
      ? { key: "lantern", name: "Lantern", idea: "x", board: "rounds/r1/lantern/board.html", files: ["rounds/r1/compass/board.html"], test_line: "ok", snapshot_verify_exit: 1, weak_points: [] }
      : undefined,
  });
  assert.equal(r.error, null);
  assert.ok(r.result.violations.some((v) => /Lantern: wrote outside its folder: rounds\/r1\/compass\/board.html/.test(v)), r.result.violations.join("|"));
  assert.ok(r.result.violations.some((v) => /Lantern: snapshot verify exit 1/.test(v)));
});

test("designers that stopped before writing are not boards: nothing built fails loudly with the reasons, a partial round skips them", async () => {
  const unbuilt = (c) => ({ key: c.label.toLowerCase(), name: c.label, idea: `Not built: the project path does not exist (${c.label}).`, board: "", files: [], screenshots: ["not produced"], test_line: "not run", snapshot_verify_exit: -1, weak_points: [] });
  const none = await run("directions", fixture("directions"), { respond: (c) => (c.agentType === "brand-creator:brand-designer" ? unbuilt(c) : undefined) });
  assert.match(none.error, /^directions: no designer built a board \(Compass: Not built: the project path does not exist/);
  assert.match(none.error, /relaunch to resume/);
  assert.equal(none.calls.length, 3, "the judge must not be paid to rank nothing");
  const one = await run("directions", fixture("directions"), { respond: (c) => (c.label === "Compass" ? undefined : c.agentType === "brand-creator:brand-designer" ? unbuilt(c) : undefined) });
  assert.equal(one.error, null);
  assert.equal(one.calls.length, 3, "one board is nothing to compare: no judge");
  assert.deepEqual(one.result.missing, ["Lantern", "Harbor"]);
  assert.equal(one.result.not_built.length, 2);
  const two = await run("directions", fixture("directions"), { respond: (c) => (c.label === "Harbor" ? unbuilt(c) : c.agentType === "brand-creator:brand-designer" ? { key: c.label.toLowerCase(), name: c.label, idea: "x", board: `rounds/r1/${c.label.toLowerCase()}/board.html`, files: [`rounds/r1/${c.label.toLowerCase()}/board.html`], screenshots: ["s.png"], test_line: "ok", snapshot_verify_exit: 0, weak_points: [] } : undefined) });
  assert.equal(two.error, null);
  assert.equal(two.calls.length, 4, "two real boards are judged");
  assert.deepEqual(two.result.missing, ["Harbor"]);
  assert.deepEqual(two.result.violations, [], "a board that was never built is not a violation");
  assert.ok(!two.calls[3].prompt.includes("Harbor ["), "the judge is not pointed at a board that does not exist");
});

test("directions needs the G1s record before any agent starts, as adopt needs G6: nothing is drawn before the style pick", async () => {
  const base = fixture("directions");
  for (const g1s of ["", "   ", undefined, null]) {
    const r = await run("directions", { ...base, g1s });
    assert.match(r.error, /^directions: args\.g1s must carry the G1s record from BRAND-STATE\.md/, JSON.stringify(g1s));
    assert.match(r.error, /style research \(P1s\) first/);
    assert.equal(r.calls.length, 0, "nothing may start without the style pick");
  }
  const { g1s: _dropped, ...without } = base;
  assert.match((await run("directions", without)).error, /args\.g1s must carry the G1s record/);
  // a pick, a skip and an honest n/a for a project that was past round 1 when the style step arrived all count as recorded
  for (const g1s of ["2026-10-17 picked Harbor + Ember palette", "2026-10-17 skipped by owner", "2026-10-18 n/a: round 1 drawn before the style step"]) {
    const r = await run("directions", { ...base, g1s });
    assert.equal(r.error, null, g1s);
    assert.equal(r.calls.length, 4);
  }
});

test("the designers draw inside the recorded style pick and the judge checks the boards against it", async () => {
  const g1s = "2026-10-17 picked Harbor + Ember palette";
  const r = await run("directions", { ...fixture("directions"), g1s });
  const designers = r.calls.filter((c) => c.agentType === "brand-creator:brand-designer");
  assert.equal(designers.length, 3);
  for (const c of designers) {
    assert.ok(c.prompt.includes(`STYLE PICK (G1s as recorded in BRAND-STATE.md): ${g1s}. Draw inside the style territories the owner picked`), c.label);
    assert.ok(c.prompt.includes("/PROJECT/rounds/r0/board.html"), "the designer is told where the style board is");
    assert.match(c.prompt, /you write ONLY inside rounds\/r1\/[a-z]+\//, "the style pick adds no write target: the designer still writes only its own folder");
  }
  const judge = r.calls.find((c) => c.agentType === "brand-creator:brand-judge");
  assert.ok(judge.prompt.includes(`STYLE PICK (G1s as recorded in BRAND-STATE.md): ${g1s}.`));
  assert.match(judge.prompt, /leaves the styles the owner picked is a MUST-FIX; a skip or an n\/a sets no style/);
});

test("fleet-plan refuses a directions run without the G1s record (exit 1, before any agent) and plans one that has it", () => {
  const d = tmpdir("bc-fleet-g1s-");
  const { g1s: _dropped, ...without } = fixture("directions");
  const bad = path.join(d, "no-g1s.json");
  fs.writeFileSync(bad, JSON.stringify(without));
  const refused = bc(["fleet-plan", "directions", "--args", `@${bad}`]);
  assert.equal(refused.status, 1, refused.stdout + refused.stderr);
  assert.match(refused.stdout, /REFUSED by the script before any agent started: directions: args\.g1s must carry the G1s record/);
  const good = path.join(d, "g1s.json");
  fs.writeFileSync(good, JSON.stringify(fixture("directions")));
  const plan = bc(["fleet-plan", "directions", "--args", `@${good}`, "--json"]);
  assert.equal(plan.status, 0, plan.stdout + plan.stderr);
  assert.equal(JSON.parse(plan.stdout).agents, 4);
});

test("adopt tells the implementer the row-list syntax of adoption status (one comma-separated argument)", async () => {
  const r = await run("adopt", fixture("adopt"));
  assert.equal(r.error, null);
  assert.match(r.calls[0].prompt, /adoption status --set <rows>=doing .* \(one argument: rows as N, N-M or N,M,\.\.\., for example --set 1,6,11-12=doing\)/);
});

test("inventory: true adds one read-only stage first and needs the owner's approval for 5 agents", async () => {
  const a = { ...fixture("directions"), inventory: { repos: [{ label: "shop", path: "/REPOS/shop" }] } };
  const refused = await run("directions", a);
  assert.equal(refused.calls.length, 0, "nothing may start when the plan is above the approved count");
  assert.match(refused.error, /plans 5 agents but args.approved_agents is 4/);
  const r = await run("directions", { ...a, approved_agents: 5 });
  assert.equal(r.error, null);
  assert.equal(r.calls[0].agentType, "brand-creator:brand-inventory");
  assert.equal(r.calls.length, 5);
  assert.deepEqual(agents["brand-inventory"].tools, ["Read", "Grep", "Glob"]);
});

test("the session model is a ceiling: with a sonnet session no agent runs on opus", async () => {
  for (const n of NAMES) {
    const a = { ...fixture(n), ceiling: "sonnet" };
    const r = await run(n, a);
    assert.equal(r.error, null, n);
    const rows = F.resolve(r.calls, agents, { session: "sonnet", env: {} });
    assert.ok(rows.every((x) => x.family === "sonnet"), `${n}: ${rows.map((x) => x.runs).join(",")}`);
  }
  const op = await run("directions", fixture("directions"));
  const asIfSonnet = F.resolve(op.calls, agents, { session: "sonnet", env: {} });
  assert.ok(asIfSonnet.every((x) => x.above), "an opus plan in a sonnet session must be flagged");
  const forced = F.resolve(op.calls, agents, { session: "claude-sonnet-5", env: { CLAUDE_CODE_SUBAGENT_MODEL_FORCE: "1" } });
  assert.ok(forced.every((x) => x.runs === "claude-sonnet-5" && /FORCE/.test(x.why)));
});

test("null guards: every agent returning null never crashes a workflow with a TypeError", async () => {
  for (const n of NAMES) {
    const r = await run(n, fixture(n), { respond: () => null });
    if (r.error) assert.match(r.error, new RegExp(`^${n}: .*(returned nothing|relaunch)`), `${n}: ${r.error}`);
    else assert.ok(r.result && typeof r.result === "object", n);
  }
  const partial = await run("review-panel", fixture("review-panel"), { respond: (c) => (c.label === "content" ? null : undefined) });
  assert.equal(partial.error, null);
  assert.deepEqual(partial.result.missing_lenses, ["content"]);
});

test("workflows refuse to start without args, and the clock and randomness throw in the sandbox", async () => {
  for (const n of NAMES) {
    const r = await run(n, undefined);
    assert.match(r.error, /args are required/);
    assert.equal(r.calls.length, 0);
  }
  const f = mutated("naming", "const LOOKUPS = A.lookups_ok === true", "const LOOKUPS = Date.now() > 0");
  assert.ok(F.staticProblems(f, agents).some((p) => /Date\\\.now/.test(p)));
  const r = await F.dryRun(f, fixture("naming"));
  assert.match(r.error, /Date\.now\(\) is not available/);
  const g = mutated("adopt", "const MODE = A.mode || 'apply'", "const MODE = Math.random() > 2 ? 'fix' : 'apply'");
  assert.match((await F.dryRun(g, fixture("adopt"))).error, /Math\.random\(\) is not available/);
});

test("naming sends no candidate out without the owner's privacy OK", async () => {
  const off = await run("naming", fixture("naming"));
  const screen = off.calls.find((c) => c.label === "screener");
  assert.match(screen.prompt, / --plan/);
  assert.doesNotMatch(screen.prompt, / --yes/);
  assert.match(screen.prompt, /no web search with any candidate/);
  for (const h of off.calls.filter((c) => /^hunter/.test(c.label))) assert.match(h.prompt, /Do not type any candidate/);
  const on = await run("naming", { ...fixture("naming"), lookups_ok: true });
  assert.match(on.calls.find((c) => c.label === "screener").prompt, / --yes/);
  for (const c of off.calls) assert.doesNotMatch(c.prompt.replace(/Never write "available"[^\n]*/, ""), /\bavailable\b/);
});

test("adopt needs G6 and an owner-named branch, never commits, and keeps one implementer per working tree", async () => {
  const base = fixture("adopt");
  assert.match((await run("adopt", { ...base, g6: "" })).error, /G6 record/);
  assert.match((await run("adopt", { ...base, repos: [{ ...base.repos[0], branch: "" }] })).error, /branch the owner named/);
  const nested = { ...base, approved_agents: 4, repos: [base.repos[0], { ...base.repos[0], label: "inner", path: "/REPOS/shop/packages/web" }] };
  assert.match((await run("adopt", nested)).error, /distinct working trees/);
  const r = await run("adopt", base);
  const impl = r.calls.find((c) => c.agentType === "brand-creator:brand-implementer");
  const rev = r.calls.find((c) => c.agentType === "brand-creator:brand-reviewer");
  assert.match(impl.prompt, /Do not commit, merge, push or stash/);
  assert.match(impl.prompt, /Never pass --no-verify/);
  assert.match(rev.prompt, /cmp every file copied from the pack/);
  assert.match(rev.prompt, /own build and tests/);
  assert.ok(r.calls.indexOf(impl) < r.calls.indexOf(rev));
  const two = { ...base, approved_agents: 4, repos: [base.repos[0], { ...base.repos[0], label: "app", path: "/REPOS/app" }] };
  const seq = await run("adopt", two);
  assert.deepEqual(seq.calls.map((c) => c.label), ["apply shop", "review shop", "apply app", "review app"], "one repository at a time by default");
  const pip = await run("adopt", { ...two, parallel_repos: true });
  assert.equal(pip.error, null);
  assert.equal(pip.calls.length, 4);
  assert.deepEqual(pip.result.complete.sort(), ["app", "shop"]);
});

test("R6-1: the designer's snapshot ignores the shot report it writes itself, and every board lists its slices", async () => {
  const r = await run("directions", fixture("directions"));
  for (const c of r.calls.filter((x) => x.agentType === "brand-creator:brand-designer")) {
    assert.match(c.prompt, /snapshot take .* --ignore '\*rounds\/r1\/\*' --ignore '\*assets\/_checks\/\*'/);
    assert.match(c.prompt, /same two --ignore options/);
    assert.match(c.prompt, / shot rounds\/r1\/[a-z-]+\/board\.html /, "the TEST step runs shot, which writes assets/_checks/shot.json");
    assert.ok(c.schema.required.includes("screenshots"));
    assert.equal(c.schema.properties.screenshots.minItems, 1);
  }
  const judge = r.calls.find((x) => x.agentType === "brand-creator:brand-judge");
  assert.doesNotMatch(judge.prompt, /see assets\/_checks\/shot\.json/, "the shared report is overwritten by the last designer");
});

test("R6-2: fix mode says the branch exists, expects the dirty tree and uses its own snapshot name; apply still creates", async () => {
  const base = fixture("adopt");
  const apply = await run("adopt", base);
  const a = apply.calls.find((c) => c.label === "apply shop").prompt;
  assert.match(a, /branch brand\/acme \(create it\)/);
  assert.match(a, /MODE: apply\./);
  assert.match(a, /--name adopt-shop /);
  const fix = await run("adopt", { ...base, mode: "fix", repos: [{ ...base.repos[0], findings: ["1 header logo still points at the old file"] }] });
  assert.equal(fix.error, null);
  const f = fix.calls.find((c) => c.label === "apply shop").prompt;
  assert.doesNotMatch(f, /\(create it\)/);
  assert.match(f, /exists: the apply run created it/);
  assert.match(f, /MODE: fix \(the working tree is expected to hold the apply run's changes\)/);
  assert.match(f, /--name adopt-fix-shop /);
  const body = agents["brand-implementer"].body;
  assert.match(body, /`MODE: fix` run the tree is expected to hold the apply run's uncommitted changes/);
  assert.doesNotMatch(body, /must be clean before you start/);
});

test("R6-4: naming hunters and the screener have no web tools until the owner OKs lookups", async () => {
  const web = (t) => agents[t].tools.some((x) => x === "WebSearch" || x === "WebFetch");
  assert.ok(!web("brand-namer") && web("brand-researcher"));
  const off = await run("naming", fixture("naming"));
  for (const c of off.calls.filter((x) => /^(hunter|screener)/.test(x.label))) {
    assert.equal(c.agentType, "brand-creator:brand-namer", c.label);
    assert.ok(!web(c.agentType.slice("brand-creator:".length)), c.label);
  }
  const on = await run("naming", { ...fixture("naming"), lookups_ok: true });
  assert.equal(on.calls.find((x) => x.label === "screener").agentType, "brand-creator:brand-researcher");
  for (const c of on.calls.filter((x) => /^hunter/.test(x.label))) assert.equal(c.agentType, "brand-creator:brand-namer");
  assert.equal(on.calls.length, 4);
});

test("fleet-plan prints the count, the models and the guideline; refuses unknown workflows and bad args", () => {
  const d = tmpdir("bc-fleet-");
  const args = path.join(d, "a.json");
  fs.writeFileSync(args, JSON.stringify({ ...fixture("naming") }));
  const r = bc(["fleet-plan", "naming", "--args", `@${args}`, "--json"]);
  assert.equal(r.status, 0, r.stderr);
  const plan = JSON.parse(r.stdout);
  assert.equal(plan.agents, 4);
  assert.equal(plan.guideline, "small (under 5)");
  assert.deepEqual(plan.models, { sonnet: 3, opus: 1 });
  const up = bc(["fleet-plan", "naming", "--args", `@${args}`, "--session-model", "sonnet"]);
  assert.equal(up.status, 1, "an opus agent in a sonnet session must fail the plan");
  assert.match(up.stdout, /ABOVE THE SESSION MODEL/);
  assert.equal(bc(["fleet-plan", "nope", "--args", "{}"]).status, 2);
  assert.equal(bc(["fleet-plan", "naming"]).status, 2);
});

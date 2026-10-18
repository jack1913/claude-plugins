export const meta = {
  name: 'adopt',
  description: 'brand-creator adoption after G6: per repository one implementer on the owner-named branch, then an independent reviewer (cmp against the pack, the repository\'s own build and tests); never commits',
  whenToUse: 'Only from /brand-creator:brand-adopt after the owner asked for the apply (G6 recorded) and said yes to the fleet. Ends before any commit.',
  phases: [
    { title: 'Apply', detail: 'one implementer per repository, on the branch the owner named' },
    { title: 'Review', detail: 'one independent reviewer per repository; reports, never edits' },
  ],
}

/*
 * brand-creator workflow: adopt (P11 apply, after G6).
 *
 * Per repository: brand-implementer (sonnet) applies the ADOPTION.md rows on the owner's branch, then brand-reviewer
 * (opus) checks it with cmp against the pack and the repository's own build and tests. Repositories run one at a time
 * (the brand-adopt default); args.parallel_repos: true runs them as a pipeline (each review starts when its own apply
 * ends), allowed only because every repository is its own working tree (checked below). Never two implementers in one
 * tree.
 *
 * Agents in the default path: 2 per repository (one repository = 2, two = 4; size guideline small below 3
 * repositories). args.mode 'fix' runs the same pair with the reviewer's no-decision findings (args.repos[].findings)
 * as the change list: a second run after the owner saw the review, never inside the first. The script refuses to start
 * above args.approved_agents. `brand-creator fleet-plan adopt --args <json>` prints the count and the models first.
 *
 * Never commits, merges, pushes, stashes or creates worktrees: the lead reports, the owner asks for each separately.
 *
 * RESUME NOTES: relaunch the same script with the same args and resumeFromRunId; a finished repository returns its
 * saved results. An implementer that was stopped left a half-applied tree: its rerun reads it, verifies it, keeps what
 * is correct and finishes the rest (the prompt says so). Do not change args between attempts. No clock or randomness
 * is used (args.today carries the date).
 */

const RULES = 'RULES: work under the round/project dir only; never edit adoption targets before G6; never rm/pkill (move to removed-<date>/); never commit/push/merge/stash/worktree unless explicitly asked, each separately; no outward actions (buy, file, register, contact); raise errors explicitly, no silent fallbacks; read your shots before any visual claim.'
const RESUME = 'If the working tree already holds changes from an interrupted run of this step: do not start over blindly and do not assume the previous work is right; read it, verify it, keep what is correct, finish the rest.'
const AGENT_TIER = { 'brand-implementer': 'sonnet', 'brand-reviewer': 'opus' }
const RANK = { haiku: 0, sonnet: 1, opus: 2 }

function fail(msg) { throw new Error('adopt: ' + msg) }
function isAbs(p) { return typeof p === 'string' && (p.startsWith('/') || /^[A-Za-z]:[\\/]/.test(p)) }
function list(v) { return Array.isArray(v) ? v.filter(Boolean) : [] }
function opts(type, extra) {
  const o = Object.assign({ agentType: 'brand-creator:' + type }, extra || {})
  if (RANK[AGENT_TIER[type]] > RANK[A.ceiling]) o.model = A.ceiling
  return o
}
function norm(p) { return String(p).replace(/[\\/]+$/, '') + '/' }

const A = args
if (!A || typeof A !== 'object') fail('args are required: run this from /brand-creator:brand-adopt after G6 and the fleet gate (see references/fleet.md)')
for (const k of ['project', 'plugin_root', 'data']) if (!isAbs(A[k])) fail('args.' + k + ' must be an absolute path')
if (!/^\d{4}-\d{2}-\d{2}$/.test(String(A.today || ''))) fail('args.today must be YYYY-MM-DD')
if (!(A.ceiling in RANK)) fail('args.ceiling must be the session model family: opus, sonnet or haiku')
if (!String(A.g6 || '').trim()) fail('args.g6 must carry the G6 record from BRAND-STATE.md (the owner\'s ask); without it nothing is applied')
const MODE = A.mode || 'apply'
if (!['apply', 'fix'].includes(MODE)) fail('args.mode must be apply or fix')
const REPOS = list(A.repos)
if (!REPOS.length) fail('args.repos must list the repositories the owner asked for')
for (const r of REPOS) {
  if (!r.label || !isAbs(r.path)) fail('every repository needs a label and an absolute path')
  if (!String(r.branch || '').trim()) fail('repository ' + r.label + ' needs the branch the owner named (never picked silently)')
  if (!list(r.rows).length) fail('repository ' + r.label + ' needs its ADOPTION.md rows (number and Find text)')
  if (MODE === 'fix' && !list(r.findings).length) fail('fix mode needs the reviewer\'s no-decision findings for ' + r.label)
}
for (const a of REPOS) for (const b of REPOS) {
  if (a !== b && (norm(a.path).startsWith(norm(b.path)) || a.label === b.label)) fail('repositories must be distinct working trees with distinct labels: ' + a.label + ', ' + b.label)
}
const planned = REPOS.length * 2
if (!Number.isInteger(A.approved_agents) || planned > A.approved_agents) {
  fail('this run plans ' + planned + ' agents but args.approved_agents is ' + A.approved_agents + ': state the fleet and get the owner\'s yes first')
}
log('adopt (' + MODE + '): ' + planned + ' agents planned for ' + REPOS.length + ' repositor' + (REPOS.length === 1 ? 'y' : 'ies') + (A.parallel_repos ? ', as a pipeline' : ', one at a time') + ', ceiling ' + A.ceiling)

const IMPL = {
  type: 'object',
  required: ['repo', 'branch', 'rows', 'files_changed', 'git_status'],
  properties: {
    repo: { type: 'string' }, branch: { type: 'string' },
    rows: { type: 'array', items: { type: 'object', required: ['row', 'status', 'evidence'], properties: { row: { type: 'string' }, status: { type: 'string', enum: ['done', 'partly', 'not done'] }, evidence: { type: 'string' } } } },
    files_changed: { type: 'array', items: { type: 'string' } },
    moved_to_removed: { type: 'array', items: { type: 'string' } },
    git_status: { type: 'string' },
    pack_snapshot_verify_exit: { type: 'integer' },
  },
}
const REVIEW = {
  type: 'object',
  required: ['repo', 'rows', 'commands', 'no_decision_fixes', 'decisions_for_you'],
  properties: {
    repo: { type: 'string' },
    rows: { type: 'array', items: { type: 'object', required: ['row', 'status', 'evidence'], properties: { row: { type: 'string' }, status: { type: 'string', enum: ['done', 'partly', 'not done'] }, evidence: { type: 'string' } } } },
    commands: { type: 'array', items: { type: 'object', required: ['command', 'exit'], properties: { command: { type: 'string' }, exit: { type: 'integer' } } } },
    cmp_failures: { type: 'array', items: { type: 'string' } },
    no_decision_fixes: { type: 'array', items: { type: 'string' } },
    decisions_for_you: { type: 'array', items: { type: 'object', required: ['question', 'recommendation'], properties: { question: { type: 'string' }, recommendation: { type: 'string' } } } },
    not_verified: { type: 'array', items: { type: 'string' } },
  },
}

const head = r => 'CONTEXT: brand project ' + A.project + ' (ADOPTION.md, assets/ = the pack, BRAND-STATE.md); plugin root ' + A.plugin_root + ' (method: skills/brand-adopt/SKILL.md); data folder ' + A.data + '; date ' + A.today + '.\nG6 AS RECORDED: ' + A.g6 + '\nREPOSITORY: ' + r.label + ' at ' + r.path + ', branch ' + r.branch + (MODE === 'fix' ? ' (exists: the apply run created it and its uncommitted changes are still in the working tree; stay on it, never create it again)' : r.create_branch ? ' (create it)' : ' (exists)') + '.\nMODE: ' + MODE + (MODE === 'fix' ? ' (the working tree is expected to hold the apply run\'s changes)' : '') + '.'

function implement(r) {
  const changes = MODE === 'fix'
    ? 'CHANGE LIST (the reviewer\'s no-decision findings; nothing else): ' + list(r.findings).map((x, i) => '(' + (i + 1) + ') ' + x).join(' ')
    : 'ROWS (find each by its Find text, never by line number): ' + list(r.rows).join(' | ')
  return agent([
    head(r),
    changes,
    'Before your first change run brand-creator --data "' + A.data + '" snapshot take "' + A.project + '/assets" --name adopt-' + (MODE === 'fix' ? 'fix-' : '') + r.label + ' --project "' + A.project + '"; at the end run snapshot verify on that file and report the exit code (the pack must not change).',
    'Copy pack files byte for byte, cmp each one. Mark rows with brand-creator --data "' + A.data + '" adoption status --set <rows>=doing --project "' + A.project + '" (one argument: rows as N, N-M or N,M,..., for example --set 1,6,11-12=doing). Never pass --no-verify. Do not commit, merge, push or stash: leave the changes in the working tree.',
    RULES,
    RESUME,
    'OUTPUT: the schema. Aim to finish within 40 minutes; keep turns short; tail-limit command output.',
  ].join('\n'), opts('brand-implementer', { label: 'apply ' + r.label, phase: 'Apply', schema: IMPL }))
}
async function review(impl, r) {
  if (!impl) { log('apply of ' + r.label + ' returned nothing; its review is skipped (relaunch to resume)'); return null }
  return await agent([
    head(r),
    'YOU DID NOT DO THIS WORK. The implementer reports (JSON): ' + JSON.stringify(impl),
    'ROWS TO CHECK: ' + list(r.rows).join(' | ') + (MODE === 'fix' ? ' and the fixes: ' + list(r.findings).join(' | ') : ''),
    'Check: cmp every file copied from the pack against ' + A.project + '/assets (any difference fails the row); sizes against the slot; the repository\'s own build and tests (from its README, package scripts, Makefile or CI config' + (r.build ? '; the owner named: ' + r.build : '') + '), quoting each command with its exit code; git status and git diff before and after your checks (report anything your commands changed). A check that needs a real device is not verified.',
    'Every row: done, partly or not done with evidence. Split the rest into no-decision fixes and numbered decisions for the owner with a recommendation each. Be honest: if something is fine, say so; do not invent problems to fill the list.',
    RULES,
    'OUTPUT: the schema. Aim to finish within 30 minutes; tail-limit command output.',
  ].join('\n'), opts('brand-reviewer', { label: 'review ' + r.label, phase: 'Review', schema: REVIEW }))
}

phase('Apply')
let pairs
if (A.parallel_repos === true) {
  const reviews = await pipeline(REPOS, r => implement(r).then(impl => ({ impl })), (prev, r) => review(prev && prev.impl, r).then(rev => ({ impl: prev ? prev.impl : null, review: rev })))
  pairs = REPOS.map((r, i) => Object.assign({ repo: r.label }, reviews[i] || { impl: null, review: null }))
} else {
  pairs = []
  for (const r of REPOS) {
    const impl = await implement(r)
    const rev = await review(impl, r)
    pairs.push({ repo: r.label, impl, review: rev })
  }
}
const done = pairs.filter(Boolean).filter(p => p.impl && p.review)
const incomplete = pairs.filter(Boolean).filter(p => !(p.impl && p.review)).map(p => p.repo)
if (incomplete.length) log('incomplete: ' + incomplete.join(', '))

return {
  mode: MODE,
  repos: pairs,
  complete: done.map(p => p.repo),
  incomplete,
  next: 'Lead: show each repository\'s rows (done / partly / not done) with the evidence; a fix run (mode fix) only for no-decision findings; then the numbered decisions. Commit, merge and push are three separate asks of the owner; say what a push triggers first.',
}

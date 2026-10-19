export const meta = {
  name: 'directions',
  description: 'brand-creator round of divergent direction boards: optional read-only inventory, one designer per direction in its own folder, one advisory judge',
  whenToUse: 'Only from the brand-creator skill after the fleet gate (agent count, models, size, cost) was stated and the owner said yes. Ends before G2.',
  phases: [
    { title: 'Inventory', detail: 'optional: one read-only surveyor of the target repositories (inventory: true)' },
    { title: 'Design', detail: 'one designer per direction, each writing only rounds/rN/<direction>/' },
    { title: 'Judge', detail: 'one read-only comparative judge; advisory, the owner decides at G2' },
  ],
}

/*
 * brand-creator workflow: directions (P3 round 1, or a reset round after G2b-a).
 *
 * Who runs it: the lead, from the brand-creator skill, only after the fleet gate. Single-thread is the default; this
 * file is the opt-in speed-up. It ends before G2: the lead assembles rounds/rN/board.html from the boards, lints it,
 * publishes the review page and stops at the gate. No mid-run sign-off happens inside this script.
 *
 * Agents in the default path: 3 designers + 1 judge = 4 (size guideline small, < 5). `inventory: true` adds one
 * (5, guideline medium); a fourth direction adds one more. The script refuses to start when the planned count is
 * above args.approved_agents (the number the owner said yes to). `brand-creator fleet-plan directions --args <json>`
 * prints the same count and the models that will run before anything is launched.
 *
 * Models: agent files set the tier (designer and judge opus, inventory sonnet). args.ceiling is the session model's
 * family; an agent above it is capped to it with a per-call model, so the session model stays a ceiling.
 * CLAUDE_CODE_SUBAGENT_MODEL_FORCE, when set, overrides all of this (the fleet plan says so).
 *
 * Writes: each designer writes only rounds/<round>/<key>/ (disjoint folders, so the designers can run in parallel);
 * the inventory and the judge cannot write at all. Each designer takes a snapshot of the project outside the round
 * before its first write and verifies it after its last; a non-zero verify is returned as a violation.
 *
 * RESUME NOTES: relaunch the same script with the same args and resumeFromRunId. Completed agents return their saved
 * results; a stopped or failed agent runs again together with every agent that started after it. Do not edit args
 * between attempts (every prompt changes and nothing is reused). Before relaunching, look at rounds/<round>/<key>/ of a
 * stopped designer: the rerun is told to read what is there, verify it, keep what is correct and finish the rest.
 * Date.now(), Math.random() and new Date() are not used: the date comes in as args.today.
 */

const RULES = 'RULES: work under the round/project dir only; never edit adoption targets before G6; never rm/pkill (move to removed-<date>/); never commit/push/merge/stash/worktree unless explicitly asked, each separately; no outward actions (buy, file, register, contact); raise errors explicitly, no silent fallbacks; read your shots before any visual claim.'
const TEST = 'TEST: screenshot 1440×900 light+dark and 390×844, Read every tile, iterate at least twice; print one-line check (overflow, errors, requests, non-whole images).'
const CHECKS = 'assets/_checks/'
const RESUME = 'If your folder already holds work from an interrupted run: do not start over blindly and do not assume the previous work is right; read it, verify it, keep what is correct, finish the rest.'
const AGENT_TIER = { 'brand-designer': 'opus', 'brand-judge': 'opus', 'brand-inventory': 'sonnet' }
const RANK = { haiku: 0, sonnet: 1, opus: 2 }

function fail(msg) { throw new Error('directions: ' + msg) }
function isAbs(p) { return typeof p === 'string' && (p.startsWith('/') || /^[A-Za-z]:[\\/]/.test(p)) }
function list(v) { return Array.isArray(v) ? v.filter(Boolean) : [] }
function numbered(items, style) {
  const xs = list(items)
  if (!xs.length) return '(none)'
  return xs.map((x, i) => '(' + (style === 'a' ? String.fromCharCode(97 + i) : String(i + 1)) + ') ' + x).join(' ')
}
function opts(type, extra) {
  const tier = AGENT_TIER[type]
  const o = Object.assign({ agentType: 'brand-creator:' + type }, extra || {})
  if (RANK[tier] > RANK[A.ceiling]) o.model = A.ceiling
  return o
}

// ---------------------------------------------------------------- arguments (checked before any agent starts)
const A = args
if (!A || typeof A !== 'object') fail('args are required: run this from the brand-creator skill after the fleet gate (see references/fleet.md)')
for (const k of ['project', 'plugin_root', 'data']) if (!isAbs(A[k])) fail('args.' + k + ' must be an absolute path')
if (!/^\d{4}-\d{2}-\d{2}$/.test(String(A.today || ''))) fail('args.today must be YYYY-MM-DD (scripts cannot read the clock)')
if (!(A.ceiling in RANK)) fail('args.ceiling must be the session model family: opus, sonnet or haiku')
if (!/^r[1-9][0-9]*$/.test(String(A.round || ''))) fail('args.round must look like r1')
const DIRS = list(A.directions)
if (DIRS.length < 2 || DIRS.length > 4) fail('args.directions must hold 2 to 4 directions (3 is the default round)')
const keys = new Set(), names = new Set()
for (const d of DIRS) {
  if (!/^[a-z][a-z0-9-]{1,30}$/.test(String(d.key || ''))) fail('direction key ' + JSON.stringify(d.key) + ' must be a lower-case slug (it is the folder name)')
  if (!/^[^\W\d_]{3,}/u.test(String(d.name || ''))) fail('direction ' + d.key + ' needs a word name of 3+ letters')
  if (!String(d.paragraph || '').trim()) fail('direction ' + d.key + ' needs its paragraph (territory, register, named visual philosophy)')
  if (keys.has(d.key) || names.has(String(d.name).toLowerCase())) fail('direction keys and names must be unique: ' + d.key)
  keys.add(d.key); names.add(String(d.name).toLowerCase())
}
const INV = A.inventory ? list(A.inventory.repos) : []
if (A.inventory && !INV.length) fail('inventory: true needs args.inventory.repos [{label, path}]')
for (const r of INV) if (!isAbs(r.path) || !r.label) fail('every inventory repo needs a label and an absolute path')
const JUDGE = A.judge !== false
const planned = (INV.length ? 1 : 0) + DIRS.length + (JUDGE ? 1 : 0)
if (!Number.isInteger(A.approved_agents) || planned > A.approved_agents) {
  fail('this run plans ' + planned + ' agents but args.approved_agents is ' + A.approved_agents + ': state the fleet and get the owner\'s yes first')
}
const B = A.brief || {}
const CONTEXT = list(A.context_paths)
if (!CONTEXT.length || !CONTEXT.every(isAbs)) fail('args.context_paths must list absolute paths (BRAND-STATE.md, brief/BRIEF.md, FACTS.md, research/cliches.md ...)')
const ROUND_DIR = 'rounds/' + A.round

log('directions: ' + planned + ' agents planned (' + (INV.length ? 'inventory, ' : '') + DIRS.length + ' designers' + (JUDGE ? ', judge' : '') + '), ceiling ' + A.ceiling)

// ---------------------------------------------------------------- schemas (outputs the script reads)
const INVENTORY_SCHEMA = {
  type: 'object',
  required: ['targets', 'slots', 'hardest_surface', 'surprises'],
  properties: {
    targets: { type: 'array', items: { type: 'object', required: ['repo', 'path', 'ref'], properties: { repo: { type: 'string' }, path: { type: 'string' }, ref: { type: 'string' }, searched_with: { type: 'string' } } } },
    deployment_targets: { type: 'array', items: { type: 'string' } },
    slots: { type: 'array', items: { type: 'object', required: ['id', 'surface', 'path', 'state'], properties: { id: { type: 'string' }, surface: { type: 'string' }, path: { type: 'string' }, now: { type: 'string' }, rule: { type: 'string' }, citation: { type: 'string' }, resampled_by: { type: 'string' }, state: { type: 'string' }, note: { type: 'string' } } } },
    hardest_surface: { type: 'string' },
    surprises: { type: 'array', items: { type: 'string' } },
    rejected: { type: 'array', items: { type: 'string' } },
  },
}
const BOARD_SCHEMA = {
  type: 'object',
  required: ['key', 'name', 'idea', 'board', 'files', 'screenshots', 'test_line', 'snapshot_verify_exit', 'weak_points'],
  properties: {
    key: { type: 'string' }, name: { type: 'string' }, idea: { type: 'string' },
    fonts: { type: 'array', items: { type: 'string' } },
    palette: { type: 'array', items: { type: 'string' } },
    mark: { type: 'string' },
    board: { type: 'string', description: 'project-relative path of board.html' },
    files: { type: 'array', items: { type: 'string' }, description: 'every project-relative path written' },
    screenshots: { type: 'array', minItems: 1, items: { type: 'string' }, description: 'every slice path the shot report lists, as an absolute path, copied before the shared report is overwritten' },
    test_line: { type: 'string' },
    snapshot_verify_exit: { type: 'integer' },
    weak_points: { type: 'array', items: { type: 'string' } },
    risks: { type: 'array', items: { type: 'string' } },
  },
}
const JUDGE_SCHEMA = {
  type: 'object',
  required: ['ranking', 'take_forward', 'grafts', 'must_fix', 'certainty'],
  properties: {
    ranking: { type: 'array', items: { type: 'object', required: ['key', 'rank', 'why', 'biggest_weakness', 'fix'], properties: { key: { type: 'string' }, rank: { type: 'integer' }, why: { type: 'string' }, scores: { type: 'object' }, biggest_weakness: { type: 'string' }, fix: { type: 'string' } } } },
    take_forward: { type: 'string' },
    grafts: { type: 'array', items: { type: 'string' } },
    must_fix: { type: 'array', items: { type: 'string' } },
    nice: { type: 'array', items: { type: 'string' } },
    vs_previous: { type: 'string' },
    not_seen: { type: 'array', items: { type: 'string' } },
    certainty: { type: 'string' },
  },
}

// ---------------------------------------------------------------- stage 1 (optional): inventory
let inventory = null
if (INV.length) {
  phase('Inventory')
  inventory = await agent([
    'CONTEXT: brand project ' + A.project + '; plugin root ' + A.plugin_root + '; template ' + A.plugin_root + '/templates/INVENTORY.md; platform rules ' + A.plugin_root + '/scripts/emitters/platform-specs.json.',
    'TARGETS (read only): ' + INV.map(r => r.label + ' = ' + r.path).join('; ') + '. Date to record: ' + A.today + '.',
    'DELIVERABLE: the rows of INVENTORY.md for these repositories (targets, deployment targets, slots, hardest surface, surprises and conflicts, considered and rejected). The lead writes the file.',
    RULES,
    'OUTPUT: the schema. Aim to finish within 25 minutes; keep turns short.',
  ].join('\n'), opts('brand-inventory', { label: 'inventory', phase: 'Inventory', schema: INVENTORY_SCHEMA }))
  if (!inventory) fail('the inventory agent returned nothing (stopped or failed); relaunch to resume before designing')
}
const HARDEST = inventory ? inventory.hardest_surface : (B.hardest_surface || 'from brief/BRIEF.md')

// ---------------------------------------------------------------- stage 2: designers (a barrier: the judge needs every board)
phase('Design')
function designerPrompt(d) {
  const folder = ROUND_DIR + '/' + d.key + '/'
  return [
    'CONTEXT: READ FULLY: ' + CONTEXT.join(', ') + '. Project: ' + A.project + '. Plugin root: ' + A.plugin_root + '. Data folder: ' + A.data + '.',
    'DECISIONS ALREADY MADE BY THE OWNER: ' + numbered(B.decisions),
    'CRITIQUE ITEMS (fix these): ' + numbered(B.critique, 'a'),
    'FAMILY LAYER (keep) / COMPANY LAYER (own) / FORBIDDEN: ' + (list(B.layers).join(' ') || 'standalone brand') + ' FORBIDDEN: ' + (list(B.forbidden).join('; ') || 'see research/cliches.md and the BRIEF Forbidden section'),
    'VERIFIED FACTS YOU MAY USE: ' + (list(B.facts).join('; ') || 'only rows of FACTS.md') + ' (nothing else may be claimed).',
    'LANGUAGE RULES: run brand-creator --data "' + A.data + '" fontcheck --print-rules --project "' + A.project + '" and keep every rule it prints in all text you set (book-lint warns where text breaks one).',
    'HARD CONSTRAINTS: static first; reduced motion = nothing moves; nothing loops forever; light and dark via tokens; at most 2 self-hostable fonts with a licence that allows embedding; the audience\'s glyph set verified (say how); real content only. ' + (B.constraints || ''),
    'HARDEST SURFACE (show the mark there): ' + HARDEST,
    'YOUR DIRECTION: ' + d.name + ' (key ' + d.key + '). ' + d.paragraph,
    'DELIVERABLE: one self-contained ' + folder + 'board.html from ' + A.plugin_root + '/templates/board.html; you write ONLY inside ' + folder + ' (other designers are writing sibling folders right now). Per variant: what it is, its cost, its degrade path; Weak points; an honest ranked recommendation that includes "keep today\'s" when an incumbent exists.',
    'SAFETY SNAPSHOT: first run brand-creator --data "' + A.data + '" snapshot take "' + A.project + '" --name ' + A.round + '-' + d.key + ' --ignore \'*' + ROUND_DIR + '/*\' --ignore \'*' + CHECKS + '*\' --project "' + A.project + '"; after your last write run snapshot verify on the file it printed with the same two --ignore options and report the exit code. The shot command writes ' + CHECKS + ' (shared by the designers, so the report is overwritten by whoever shoots last): that is why it is ignored; copy the slice paths its report lists into your answer (screenshots) before you finish, never point the judge at the shared report.',
    TEST + ' Run it as brand-creator --data "' + A.data + '" shot ' + folder + 'board.html --project "' + A.project + '" and Read every slice the report lists.',
    RULES,
    RESUME,
    'OUTPUT: the schema; key must be ' + d.key + ' and every path in files must start with ' + folder + '. Aim to finish within 35 minutes; keep turns short; tail-limit command output.',
  ].join('\n')
}
const raw = await parallel(DIRS.map(d => () => agent(designerPrompt(d), opts('brand-designer', { label: d.name, phase: 'Design', schema: BOARD_SCHEMA }))))
// A designer that stopped before writing anything (a wrong project path, a failed snapshot) still answers the schema,
// with no files: that is no board, not a board to judge.
const isBuilt = b => Boolean(b) && list(b.files).length > 0
const missing = DIRS.filter((d, i) => !isBuilt(raw[i])).map(d => d.name)
const notBuilt = DIRS.map((d, i) => (raw[i] && !isBuilt(raw[i])) ? d.name + ': ' + String(raw[i].idea || '(no reason given)').slice(0, 200) : null).filter(Boolean)
const boards = raw.filter(Boolean).filter(isBuilt)
if (!boards.length) fail('no designer built a board' + (notBuilt.length ? ' (' + notBuilt.join(' | ') + ')' : '') + ': nothing to judge; fix the cause (often the project path or the data folder) and relaunch to resume')
const violations = []
DIRS.forEach((d, i) => {
  const b = raw[i]
  if (!isBuilt(b)) return
  const folder = ROUND_DIR + '/' + d.key + '/'
  if (b.key !== d.key) violations.push(d.name + ': returned key ' + b.key)
  for (const f of list(b.files).concat([b.board])) if (!String(f).startsWith(folder)) violations.push(d.name + ': wrote outside its folder: ' + f)
  if (b.snapshot_verify_exit !== 0) violations.push(d.name + ': snapshot verify exit ' + b.snapshot_verify_exit + ' (something outside ' + ROUND_DIR + '/ changed)')
})
if (missing.length) log('no board from: ' + missing.join(', ') + ' (stopped, failed or nothing built' + (notBuilt.length ? ': ' + notBuilt.join(' | ') : '') + '); relaunch to resume, or carry on without them')
if (violations.length) log('VIOLATIONS: ' + violations.join(' | '))

// ---------------------------------------------------------------- stage 3: judge (advisory)
let judge = null
if (JUDGE && boards.length >= 2) {
  phase('Judge')
  judge = await agent([
    'CONTEXT: READ FULLY: ' + CONTEXT.join(', ') + '; the rubric in ' + A.plugin_root + '/skills/brand-creator/references/board-contract.md. Project: ' + A.project + '.',
    'DECISIONS ALREADY MADE BY THE OWNER: ' + numbered(B.decisions),
    'COMPARE these boards (open each board.html and Read every screenshot slice listed): ' + boards.map(b => b.name + ' [' + b.key + ']: ' + b.board + ' slices: ' + list(b.screenshots).join(', ')).join(' | '),
    (A.previous_round ? 'PREVIOUS ROUND and best so far: ' + A.previous_round + ' (score against both on the same rubric).' : 'This is the first round: say so instead of comparing with a previous one.'),
    'Rank them, say which one you would take forward and what you would graft from the others; return a numbered MUST-FIX list and an optional NICE list. Be honest: if something is fine, say so; do not invent problems to fill the list. You advise; the owner decides.',
    RULES,
    'OUTPUT: the schema. Aim to finish within 20 minutes.',
  ].join('\n'), opts('brand-judge', { label: 'judge', phase: 'Judge', schema: JUDGE_SCHEMA }))
  if (!judge) log('the judge returned nothing; the lead gives its own comparative read instead (say so on the board)')
} else if (JUDGE) {
  log('fewer than 2 boards: the judge was not run')
}

return {
  round: A.round,
  boards,
  missing,
  not_built: notBuilt,
  violations,
  inventory,
  judge,
  next: 'Lead: write INVENTORY.md from inventory (when present), assemble ' + ROUND_DIR + '/board.html from the boards (judge view + lead view + middle option when the judge ran), board-lint, shot, publish review/index.html, stop at G2.',
}

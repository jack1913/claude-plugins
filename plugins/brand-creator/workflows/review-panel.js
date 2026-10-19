export const meta = {
  name: 'review-panel',
  description: 'brand-creator lens panel: one read-only reviewer per lens (design, content, technical; legal, platform, accessibility when they apply), then one judge that challenges and sorts the findings',
  whenToUse: 'Only from /brand-creator:review panel after the fleet gate was stated and the owner said yes. Read only; ends with one approvable list.',
  phases: [
    { title: 'Lenses', detail: 'one reviewer per lens; they run check commands and never edit' },
    { title: 'Judge', detail: 'challenges every finding; A before launch, B soon, C optional, owner-only decisions' },
  ],
}

/*
 * brand-creator workflow: review-panel (the optional lens panel of /brand-creator:review).
 *
 * Agents in the default path: 3 lenses (design, content, technical) + 1 judge = 4 (size guideline small, < 5). Each
 * extra lens (legal, platform, accessibility) adds one; the script refuses to start above args.approved_agents.
 * `brand-creator fleet-plan review-panel --args <json>` prints the count and the models first.
 *
 * Models: lenses run as brand-reviewer (opus), the judge as brand-judge (opus); args.ceiling caps both to the session
 * model's family. Nobody writes: reviewers have Read/Grep/Glob/Bash for checks only, the judge Read/Grep/Glob. The lead
 * must not edit the reviewed files while the panel runs (the prompts say the copy is still).
 *
 * Ends before any fix: the lead shows the sorted list, the owner approves it, then the lead fixes in the main thread.
 *
 * RESUME NOTES: relaunch the same script with the same args and resumeFromRunId; completed lenses return their saved
 * results, a failed lens reruns with every agent after it. Do not change args between attempts. No clock or randomness
 * is used (args.today carries the date).
 */

const RULES = 'RULES: work under the round/project dir only; never edit adoption targets before G6; never rm/pkill (move to removed-<date>/); never commit/push/merge/stash/worktree unless explicitly asked, each separately; no outward actions (buy, file, register, contact); raise errors explicitly, no silent fallbacks; read your shots before any visual claim.'
const AGENT_TIER = { 'brand-reviewer': 'opus', 'brand-judge': 'opus' }
const RANK = { haiku: 0, sonnet: 1, opus: 2 }
const LENSES = {
  design: 'the visual system: hierarchy, the mark at 16 and 180, restraint rules, light and dark, the reflex list (references/ai-defaults.json); shoot the page and Read every slice',
  content: 'copy against FACTS.md only (no invented clients, numbers, dates, status words), tone rules, the audience language, names stable across pages',
  technical: 'files, sizes, manifest rows, reports under assets/_checks/, brand-creator check exit code and every failing row, broken links and network requests in the shot report',
  legal: 'regulated wording and naming rules (references/regulated-industries.md), trademark wording ("screening, not clearance"), licences of fonts and vendored files',
  platform: 'platform slots against references/platform-specs.md (status V, R, U), downscale proofs, store and package metadata',
  accessibility: 'contrast numbers recomputed (brand-creator contrast), reduced motion, focus and alt text in the book and boards, colour-vision report (contrast --cvd)',
}

function fail(msg) { throw new Error('review-panel: ' + msg) }
function isAbs(p) { return typeof p === 'string' && (p.startsWith('/') || /^[A-Za-z]:[\\/]/.test(p)) }
function list(v) { return Array.isArray(v) ? v.filter(Boolean) : [] }
function opts(type, extra) {
  const o = Object.assign({ agentType: 'brand-creator:' + type }, extra || {})
  if (RANK[AGENT_TIER[type]] > RANK[A.ceiling]) o.model = A.ceiling
  return o
}

const A = args
if (!A || typeof A !== 'object') fail('args are required: run this from /brand-creator:review after the fleet gate (see references/fleet.md)')
for (const k of ['project', 'plugin_root', 'data']) if (!isAbs(A[k])) fail('args.' + k + ' must be an absolute path')
if (!/^\d{4}-\d{2}-\d{2}$/.test(String(A.today || ''))) fail('args.today must be YYYY-MM-DD')
if (!(A.ceiling in RANK)) fail('args.ceiling must be the session model family: opus, sonnet or haiku')
if (!['board', 'book', 'pack', 'all'].includes(A.target)) fail('args.target must be board, book, pack or all')
const TARGETS = list(A.target_paths)
if (!TARGETS.length || !TARGETS.every(isAbs)) fail('args.target_paths must list the absolute paths under review')
const CONTEXT = list(A.context_paths)
if (!CONTEXT.length || !CONTEXT.every(isAbs)) fail('args.context_paths must list absolute paths (BRAND-STATE.md, FACTS.md, the approved rules)')
const LENS_NAMES = A.lenses ? list(A.lenses) : ['design', 'content', 'technical']
for (const l of LENS_NAMES) if (!(l in LENSES)) fail('unknown lens ' + JSON.stringify(l) + ' (known: ' + Object.keys(LENSES).join(', ') + ')')
if (new Set(LENS_NAMES).size !== LENS_NAMES.length || LENS_NAMES.length < 2) fail('args.lenses must name at least two different lenses')
const planned = LENS_NAMES.length + 1
if (!Number.isInteger(A.approved_agents) || planned > A.approved_agents) {
  fail('this run plans ' + planned + ' agents but args.approved_agents is ' + A.approved_agents + ': state the fleet and get the owner\'s yes first')
}
log('review-panel: ' + planned + ' agents planned (' + LENS_NAMES.join(', ') + ', judge), ceiling ' + A.ceiling)

const FINDING = {
  type: 'object',
  required: ['id', 'severity', 'where', 'evidence', 'why', 'change', 'effort'],
  properties: {
    id: { type: 'string' }, severity: { type: 'string', enum: ['high', 'medium', 'low'] }, where: { type: 'string' },
    evidence: { type: 'string' }, why: { type: 'string', description: 'why it matters for THIS brand' }, change: { type: 'string' },
    effort: { type: 'string', enum: ['S', 'M', 'L'] },
  },
}
const LENS_SCHEMA = {
  type: 'object',
  required: ['lens', 'findings', 'strengths', 'commands'],
  properties: {
    lens: { type: 'string' },
    findings: { type: 'array', items: FINDING },
    strengths: { type: 'array', items: { type: 'string' }, maxItems: 5, description: 'strengths that must NOT change' },
    commands: { type: 'array', items: { type: 'string' }, description: 'each check command run, with its exit code' },
    not_verified: { type: 'array', items: { type: 'string' } },
  },
}
const JUDGE_SCHEMA = {
  type: 'object',
  required: ['A', 'B', 'C', 'rejected', 'owner_decisions', 'strengths'],
  properties: {
    A: { type: 'array', items: FINDING, description: 'before launch' },
    B: { type: 'array', items: FINDING, description: 'soon' },
    C: { type: 'array', items: FINDING, description: 'optional' },
    rejected: { type: 'array', items: { type: 'object', required: ['id', 'reason'], properties: { id: { type: 'string' }, reason: { type: 'string' } } } },
    owner_decisions: { type: 'array', items: { type: 'object', required: ['question', 'options', 'recommendation'], properties: { question: { type: 'string' }, options: { type: 'array', items: { type: 'string' } }, recommendation: { type: 'string' } } } },
    strengths: { type: 'array', items: { type: 'string' }, maxItems: 5 },
  },
}

// ---------------------------------------------------------------- lenses (a barrier: the judge compares across lenses)
phase('Lenses')
const lensPrompt = l => [
  'CONTEXT: READ FULLY: ' + CONTEXT.join(', ') + '. Project: ' + A.project + '. Plugin root: ' + A.plugin_root + '. Data folder: ' + A.data + '. Date: ' + A.today + '.',
  'UNDER REVIEW (' + A.target + '; a still copy: nobody edits it while the panel runs): ' + TARGETS.join(', '),
  'DECISIONS ALREADY MADE BY THE OWNER (never findings): ' + (list(A.decisions).map((x, i) => '(' + (i + 1) + ') ' + x).join(' ') || '(none)'),
  'YOUR LENS: ' + l + ' = ' + LENSES[l] + '. Stay inside it; the other lenses run at the same time.',
  'Run check commands as brand-creator --data "' + A.data + '" <check> --project "' + A.project + '" and quote each with its exit code. You never edit, move or delete anything.',
  'Each finding: {id ' + l.slice(0, 3).toUpperCase() + '-n, severity, where, evidence, why for THIS brand, change, effort S/M/L}. Up to 5 strengths that must not change. Be honest: if something is fine, say so; do not invent problems to fill the list.',
  RULES,
  'OUTPUT: the schema. Aim to finish within 25 minutes; keep turns short; tail-limit command output.',
].join('\n')
const rawLenses = await parallel(LENS_NAMES.map(l => () => agent(lensPrompt(l), opts('brand-reviewer', { label: l, phase: 'Lenses', schema: LENS_SCHEMA }))))
const lost = LENS_NAMES.filter((l, i) => !rawLenses[i])
const lensResults = rawLenses.map((r, i) => (r ? Object.assign({}, r, { lens: LENS_NAMES[i] }) : null)).filter(Boolean)
if (lost.length) log('no result from lens: ' + lost.join(', ') + ' (stopped or failed); the list below does not cover it')
if (!lensResults.length) fail('every lens returned nothing; relaunch to resume')

// ---------------------------------------------------------------- judge
phase('Judge')
const all = lensResults.flatMap(r => list(r.findings).map(f => Object.assign({ lens: r.lens }, f)))
const judge = await agent([
  'CONTEXT: READ FULLY: ' + CONTEXT.join(', ') + '. Under review: ' + TARGETS.join(', ') + '.',
  'DECISIONS ALREADY MADE BY THE OWNER: ' + (list(A.decisions).map((x, i) => '(' + (i + 1) + ') ' + x).join(' ') || '(none)'),
  'FINDINGS FROM THE LENSES (JSON): ' + JSON.stringify(all),
  'STRENGTHS THE LENSES NAMED: ' + JSON.stringify(lensResults.map(r => ({ lens: r.lens, strengths: list(r.strengths) }))),
  'Challenge each finding: verify the key ones yourself by reading the files; reject anything wrong, cosmetic-only without real benefit, or in conflict with the approved rules or the owner\'s decisions (say why). Sort the survivors into A (before launch), B (soon), C (optional); list owner-only decisions with options and a recommendation; keep up to 5 strengths that must not change. You advise; the owner decides.',
  RULES,
  'OUTPUT: the schema. Aim to finish within 20 minutes.',
].join('\n'), opts('brand-judge', { label: 'judge', phase: 'Judge', schema: JUDGE_SCHEMA }))
if (!judge) log('the judge returned nothing: the lead sorts the raw findings itself and says so')

return {
  target: A.target,
  lenses: lensResults,
  missing_lenses: lost,
  judge,
  next: 'Lead: show judge view, own view and a middle option where they differ, as one approvable list (no-decision fixes, numbered Decisions for you, strengths); fix nothing before the owner approves.',
}

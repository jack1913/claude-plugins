export const meta = {
  name: 'naming',
  description: 'brand-creator naming: name hunters by style, one screener (offline unless the owner agreed to online lookups), and one judge drafting a go / go-with-conditions / no verdict per shortlisted name',
  whenToUse: 'Only from the brand-naming skill, after the agent count, models, size and cost were shown and the owner said yes. Screening, not clearance; ends before the name is chosen.',
  phases: [
    { title: 'Generate', detail: 'name hunters, each with its own styles, from the same territories' },
    { title: 'Screen', detail: 'internal filter and the name checker (--plan unless lookups were OK\'d)' },
    { title: 'Judge', detail: 'verdict per shortlisted name; screening, not clearance' },
  ],
}

/*
 * brand-creator workflow: naming (P2 of the brand-naming skill, steps 3 to 11).
 *
 * Agents in the default path: 2 hunters + 1 screener + 1 judge = 4 (size guideline small, < 5). A third hunter adds
 * one; the script refuses to start above args.approved_agents. `brand-creator fleet-plan naming --args <json>` prints
 * the count and the models first.
 *
 * Models: the judge runs as brand-judge (opus); args.ceiling caps every agent to the session model's family. The hunters
 * always run as brand-namer (sonnet, no WebSearch or WebFetch tool); the screener runs as brand-namer too unless
 * args.lookups_ok is true, when it runs as brand-researcher (sonnet, with the web tools) for the prior-art search.
 *
 * Privacy: candidate names leave the machine only when args.lookups_ok is true, which the lead sets only after the
 * owner's privacy OK (brand-naming step 7). Otherwise nobody has a web tool (brand-namer agents only) and the screener
 * runs the name checker with --plan only (it prints which services would receive the names and exits 0). Bash is the
 * one tool left that could reach the web; keeping it to the checker is the prompt's job, so the script still logs a
 * WARNING from the screener's own lookups_used report. The workflow never
 * buys, files or registers anything; nothing here calls a name "available" or "clear".
 *
 * Ends before G1: the lead writes the verdict memo from templates/names-verdict.md and the owner picks.
 *
 * RESUME NOTES: relaunch the same script with the same args and resumeFromRunId; completed hunters return their saved
 * results. Changing args (for example turning lookups_ok on) changes every prompt: that is a new run, which is right,
 * because the screen must be redone with the lookups. No clock or randomness is used (args.today carries the date).
 */

const RULES = 'RULES: work under the round/project dir only; never edit adoption targets before G6; never rm/pkill (move to removed-<date>/); never commit/push/merge/stash/worktree unless explicitly asked, each separately; no outward actions (buy, file, register, contact); raise errors explicitly, no silent fallbacks; read your shots before any visual claim.'
const AGENT_TIER = { 'brand-researcher': 'sonnet', 'brand-namer': 'sonnet', 'brand-judge': 'opus' }
const RANK = { haiku: 0, sonnet: 1, opus: 2 }
const STYLES = ['invented', 'native-language', 'descriptive', 'metaphor', 'compound', 'foreign']

function fail(msg) { throw new Error('naming: ' + msg) }
function isAbs(p) { return typeof p === 'string' && (p.startsWith('/') || /^[A-Za-z]:[\\/]/.test(p)) }
function list(v) { return Array.isArray(v) ? v.filter(Boolean) : [] }
function opts(type, extra) {
  const o = Object.assign({ agentType: 'brand-creator:' + type }, extra || {})
  if (RANK[AGENT_TIER[type]] > RANK[A.ceiling]) o.model = A.ceiling
  return o
}

const A = args
if (!A || typeof A !== 'object') fail('args are required: run this from the brand-naming skill after the fleet gate (see references/fleet.md)')
for (const k of ['project', 'plugin_root', 'data']) if (!isAbs(A[k])) fail('args.' + k + ' must be an absolute path')
if (!/^\d{4}-\d{2}-\d{2}$/.test(String(A.today || ''))) fail('args.today must be YYYY-MM-DD')
if (!(A.ceiling in RANK)) fail('args.ceiling must be the session model family: opus, sonnet or haiku')
if (!['software', 'consumer', 'personal'].includes(A.profile)) fail('args.profile must be software, consumer or personal')
if (!/^[A-Z]{2}$/.test(String(A.region || ''))) fail('args.region must be a two-letter country code')
const CONTEXT = list(A.context_paths)
if (!CONTEXT.length || !CONTEXT.every(isAbs)) fail('args.context_paths must list absolute paths (BRAND-STATE.md, brief/BRIEF.md, the strategy core, research/cliches.md)')
const TERRITORIES = list(A.territories)
if (TERRITORIES.length < 3) fail('args.territories must hold 3 to 5 metaphor territories (step 3)')
const HUNTERS = A.hunters ? list(A.hunters) : [['invented', 'compound', 'foreign'], ['native-language', 'metaphor', 'descriptive']]
if (HUNTERS.length < 1 || HUNTERS.length > 3) fail('args.hunters must hold 1 to 3 style groups')
for (const h of HUNTERS) for (const s of list(h)) if (!STYLES.includes(s)) fail('unknown style ' + JSON.stringify(s) + ' (known: ' + STYLES.join(', ') + ')')
const LOOKUPS = A.lookups_ok === true
const SHORT = Number.isInteger(A.shortlist) ? A.shortlist : 10
if (SHORT < 3 || SHORT > 12) fail('args.shortlist must be 3 to 12 (step 5 cuts to 8 to 12)')
const planned = HUNTERS.length + 2
if (!Number.isInteger(A.approved_agents) || planned > A.approved_agents) {
  fail('this run plans ' + planned + ' agents but args.approved_agents is ' + A.approved_agents + ': state the fleet and get the owner\'s yes first')
}
log('naming: ' + planned + ' agents planned (' + HUNTERS.length + ' hunters, screener, judge), ceiling ' + A.ceiling + ', lookups ' + (LOOKUPS ? 'OK by the owner' : 'off (--plan only)'))

const CANDIDATES = {
  type: 'object',
  required: ['candidates'],
  properties: { candidates: { type: 'array', items: { type: 'object', required: ['name', 'territory', 'style', 'why'], properties: { name: { type: 'string' }, territory: { type: 'string' }, style: { type: 'string' }, why: { type: 'string' } } } } },
}
const SCREEN = {
  type: 'object',
  required: ['shortlist', 'cut', 'names_command', 'names_exit', 'lookups_used'],
  properties: {
    shortlist: { type: 'array', items: { type: 'object', required: ['name', 'class', 'notes'], properties: { name: { type: 'string' }, class: { type: 'string', enum: ['fanciful', 'arbitrary', 'suggestive', 'descriptive', 'generic'] }, notes: { type: 'string' }, meaning_by_language: { type: 'string' }, prior_art: { type: 'string' }, states: { type: 'string' } } } },
    cut: { type: 'array', items: { type: 'object', required: ['name', 'reason'], properties: { name: { type: 'string' }, reason: { type: 'string' } } } },
    names_command: { type: 'string' },
    names_exit: { type: 'integer' },
    lookups_used: { type: 'boolean' },
    memo_path: { type: 'string' },
  },
}
const VERDICTS = {
  type: 'object',
  required: ['verdicts', 'recommended', 'banner'],
  properties: {
    verdicts: { type: 'array', items: { type: 'object', required: ['name', 'verdict', 'reasons'], properties: { name: { type: 'string' }, verdict: { type: 'string', enum: ['go', 'go-with-conditions', 'no'] }, conditions: { type: 'array', items: { type: 'string' } }, reasons: { type: 'string' } } } },
    recommended: { type: 'array', items: { type: 'string' }, maxItems: 3 },
    banner: { type: 'string', description: 'must say: screening, not clearance' },
  },
}

const head = 'CONTEXT: READ FULLY: ' + CONTEXT.join(', ') + '. Project: ' + A.project + '. Plugin root: ' + A.plugin_root + ' (method: skills/brand-naming/SKILL.md). Date: ' + A.today + '.'

// ---------------------------------------------------------------- generate (a barrier: the screen dedups across hunters)
phase('Generate')
const hunted = (await parallel(HUNTERS.map((styles, i) => () => agent([
  head,
  'TERRITORIES: ' + TERRITORIES.map((t, j) => '(' + (j + 1) + ') ' + t).join(' '),
  'YOUR STYLES: ' + list(styles).join(', ') + '. Other hunters cover the other styles at the same time.',
  'DELIVERABLE: 20 to 40 candidates spread across the territories and your styles, each with territory, style and one line why. Single tokens (letters, digits, hyphens) so they can be screened. Founder names and acronyms only if the brief asks for them.',
  'PRIVACY: work from your own knowledge and the local files only. Do not type any candidate into a search engine, registry or website.',
  RULES,
  'OUTPUT: the schema. Aim to finish within 15 minutes.',
].join('\n'), opts('brand-namer', { label: 'hunter ' + (i + 1), phase: 'Generate', schema: CANDIDATES }))))).filter(Boolean)
if (!hunted.length) fail('every hunter returned nothing; relaunch to resume')
const seen = new Set()
const pool = []
for (const h of hunted) for (const c of list(h.candidates)) {
  const k = String(c.name || '').trim().toLowerCase()
  if (!k || seen.has(k)) continue
  seen.add(k)
  pool.push(c)
}
log(pool.length + ' distinct candidates from ' + hunted.length + ' hunter(s)')

// ---------------------------------------------------------------- screen
phase('Screen')
const namesCmd = 'brand-creator --data "' + A.data + '" names <shortlist> --project "' + A.project + '" --profile ' + A.profile + ' --region ' + A.region + (LOOKUPS ? ' --yes' : ' --plan')
const screen = await agent([
  head,
  'CANDIDATES (JSON): ' + JSON.stringify(pool),
  'DELIVERABLE: steps 4 to 6 and 8 to 9 of the brand-naming method: a distinctiveness class per candidate, the internal filter (sound, spelling, length, meaning in each audience language, clichés from research/cliches.md, sibling and competitor names) down to a shortlist of ' + SHORT + ', each cut with a one-line reason.',
  LOOKUPS
    ? 'The owner gave the privacy OK: prior-art search on the web is allowed for the shortlist, then run: ' + namesCmd + ' and report each source state as it is (REGISTERED, NOT-FOUND, UNKNOWN).'
    : 'The owner has NOT agreed to send the names out: no web search with any candidate; run only: ' + namesCmd + ' (it lists the services and exits 0) and report lookups_used false.',
  'Never write "available", "free", "clear" or "safe" about a name.',
  RULES,
  'OUTPUT: the schema. Aim to finish within 25 minutes; tail-limit command output.',
].join('\n'), opts(LOOKUPS ? 'brand-researcher' : 'brand-namer', { label: 'screener', phase: 'Screen', schema: SCREEN }))
if (!screen) fail('the screener returned nothing; relaunch to resume')
if (!LOOKUPS && screen.lookups_used) log('WARNING: the screener reports lookups although the owner did not agree; tell the owner')

// ---------------------------------------------------------------- judge
phase('Judge')
const verdicts = await agent([
  head,
  'SHORTLIST WITH SCREENING (JSON): ' + JSON.stringify(screen.shortlist),
  'SCREENING RUN: ' + screen.names_command + ' (exit ' + screen.names_exit + '); lookups ' + (screen.lookups_used ? 'run' : 'not run: every registry state is still unknown'),
  'DELIVERABLE: a verdict per shortlisted name, go / go-with-conditions / no, with reasons and conditions; up to three recommended names in order. Weigh states as they are; without lookups no name can be better than go-with-conditions. The banner says "screening, not clearance". You advise; the owner picks at G1 and buys and files.',
  RULES,
  'OUTPUT: the schema. Aim to finish within 15 minutes.',
].join('\n'), opts('brand-judge', { label: 'judge', phase: 'Judge', schema: VERDICTS }))
if (!verdicts) log('the judge returned nothing: the lead writes the verdicts itself and says so')

return {
  candidates: pool.length,
  screen,
  verdicts,
  lookups_ok: LOOKUPS,
  next: 'Lead: write the verdict memo from templates/names-verdict.md (screening, not clearance), the trademark links stay owner-run, stop at G1.',
}

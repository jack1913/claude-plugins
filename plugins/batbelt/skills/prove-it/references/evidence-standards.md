# Evidence Standards

The field formats, verdict thresholds, and checking procedures the workflows
in SKILL.md refer to. Rules 1 to 7 in SKILL.md state the principles; this file
states the mechanics.

## Provenance record format

Attached to every CONFIRMED, REFUTED, and PARTIALLY verdict. All fields
required unless marked otherwise.

| Field | Content |
|---|---|
| `id` | `P-001`, `P-002`, ... unique within the run |
| `claim` | The assumption's ID and one-sentence restatement |
| `citation` | The precise identifier inside the source: article and paragraph for law, section and page for a report, query name for internal data |
| `source_url` | Direct link to the text cited, not to a homepage |
| `hierarchy_level` | 1 to 4, from the run's approved hierarchy, not from search ranking |
| `verbatim` | 1 to 3 quoted sentences in the source's original language, copied, not retyped from memory |
| `translation` | Working translation into the conversation language; omit when the languages match |
| `fetched` | Date the source was read in this run, YYYY-MM-DD; in the fetch-failure exception, date the actual fetch was attempted |
| `note` | Optional. Used when the literal text and the practical reading differ, recording the bridge so a future reader does not "correct" a deliberate interpretation |

A record missing any required field is incomplete, and per SKILL.md
<Workflow - Research> an incomplete record downgrades the verdict to
UNVERIFIABLE. Half-evidence presented as evidence is the failure mode this
whole format exists to prevent. The one sanctioned exception is a fetch
failure under the corroboration rule below: there the `verbatim` field
records the failure instead of a quote and the verdict caps at PARTIALLY.

## Corroboration rule

A level 3 or 4 source can locate the answer but cannot carry the verdict
alone. The record's `source_url` and `verbatim` must come from the highest
level available on the topic. When a lower-level source is genuinely all that
exists, say so in the record's `note` and cap the verdict at PARTIALLY.

Two independent level 4 sources do not add up to a level 2. Independence of
repetition is not independence of origin: trade press articles usually quote
the same press release.

**A source you fetched but did not read corroborates nothing.** A downloaded file,
an open tab, a tool result you skimmed past — none of it is evidence until its text
is in front of you and the relevant passage is quoted. This failure is quiet because
the record *looks* complete: the URL is right, the fetch succeeded, the `fetched`
date is real. Only the `verbatim` field exposes it, which is why that field is
mandatory. If a fetch returns something you could not or did not read, the verdict
is UNVERIFIABLE until you go back and read it.

Fetch failure is not UNVERIFIABLE. When the primary source URL was identified
and independently corroborated in this run but its text cannot be fetched
(paywall, page that does not render; one honest failed attempt on that URL is
enough), cap the verdict at PARTIALLY, state the fetch failure in the
`verbatim` field, put the attempt date in `fetched`, and recommend a re-fetch
in the `note` before the record ships in a spec. Unavailable tooling or an available research path that never ran is
`Research status: BLOCKED` under SKILL.md, not this exception. After research
starts, failure of any exception precondition — no URL identified in this run,
no independent corroboration from another accessible source, or no actual
failed fetch of that URL — leaves the record incomplete and cannot earn the
fetch-failure PARTIALLY verdict. Nothing needs
deciding in a qualifying fetch failure, so the UNVERIFIABLE markers do not
apply; the identified page just did not render.

## Verdict taxonomy

| Verdict | Bar to award it |
|---|---|
| CONFIRMED | A complete provenance record from the highest applicable hierarchy level, no contradicting source found at the same or higher level, arithmetic checks pass where applicable |
| REFUTED | Same evidentiary bar as CONFIRMED, but the source contradicts the claim. State what the source says instead, not just that the claim fails |
| PARTIALLY | The claim holds with a material qualification (true for a subset, until a date, or at a materially different value); the highest available source is below the approved ideal level under the corroboration rule; or the claim is independently corroborated but the correctly identified primary source could not be fetched under the exception above. State the qualification or evidence gap in one sentence next to the verdict |
| UNVERIFIABLE | No qualifying source found, or the claim is not source-checkable by nature. Always paired with a resolvability marker: INTERNAL-DATA: {system or owner}, EXPERT: {who}, or BUSINESS-DECISION, and one sentence on the cheapest way to settle it. Marker choice when a source-checkable claim comes back empty: EXPERT when someone could supply the missing instrument or citation (name them); BUSINESS-DECISION only when nothing publishable could ever settle it |

### Confidence

Stated per verdict as HIGH or MODERATE, with one line of reasoning.

- HIGH: level 1 or 2 source, current as of the reference date, unambiguous
  text.
- MODERATE: the source is one level lower than ideal, or the text requires
  interpretation, or currency as of the reference date could not be fully
  established. The reason is named.

There is no LOW. A verdict that would earn LOW confidence is not a verdict;
it is UNVERIFIABLE wearing makeup. Downgrade it.

### Refutation condition

Every CONFIRMED and PARTIALLY verdict states, in one sentence, what
observation or publication would overturn it ("an amendment to Art. X",
"next quarter's cohort data showing retention above Y"). This is what makes
the register maintainable: the next analyst checks the refutation conditions,
not the whole file.

## Arithmetic cross-check

For every derived value among the claims (any number that is a function of
other numbers, including one the user presented as a flat constant when a
published formula produces it, like an annual cap defined as a multiple of a
forecast wage):

1. Identify the formula and its primary inputs.
2. Source each input with its own provenance record (inputs are claims too).
3. Recompute the value from the sourced inputs, keeping full precision until
   the final rounding step, and note the rounding rule used.
4. Compare with the claimed number. Record the line in the artifact either
   way: `inputs -> computed -> claimed -> match` or `-> DIVERGENCE`.
5. A divergence goes to the Divergences section and the next checkpoint. Do
   not decide on the user's behalf that their number "was probably rounded".

A claimed value whose formula or inputs cannot be established is not a
divergence; it is UNVERIFIABLE.

## Source contradiction

When two sources at the same hierarchy level disagree, record both verbatims,
mark the assumption PARTIALLY at best, and put the contradiction in the
Divergences section with a note on which source is more current relative to
the reference date. Never silently pick the one that agrees with the user.

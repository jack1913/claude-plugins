# Source Hierarchy Profiles

Starting points for the hierarchy proposed during <Workflow - Intake>. Each
profile orders source classes from binding to merely suggestive. Level 1
outranks everything below it; a verdict citing a lower level while a higher
level exists on the topic is incomplete.

These are proposals, not law. The user approves or corrects the hierarchy at
intake, and the approved version, corrections included, is what goes into the
artifact header and governs the run.

A claim spanning two domains (a legal claim with market consequences, say)
gets checked against both hierarchies; the verdict cites the level from the
hierarchy that governs the claim's core.

## Profile: Polish law and regulation

1. Consolidated statute text and official journals: `dziennikustaw.gov.pl`,
   `monitorpolski.gov.pl`, and the Sejm **ELI API** at `api.sejm.gov.pl/eli/acts/...`.
   `isap.sejm.gov.pl` is the canonical name for this level but is frequently
   CAPTCHA-walled from agent environments; ELI serves the same Dziennik Ustaw
   documents and is the reliable route. Useful ELI endpoints: the bare act for
   metadata and whether a tekst jednolity exists, `/references` for the amendment
   chain, `/text.pdf` for the document itself. Two independent calls agreeing
   (metadata + references) is a cheap completeness check on the chain.
   If a document is reachable only through ISAP's own interface and ELI does not
   carry it, a browser MCP is the last resort (see SKILL.md Platform notes) — but
   a CAPTCHA there is a hand-off to the user, not something to route around.
2. Official positions of the administering body: `zus.pl`, `gov.pl`
   ministry pages (for example the Ministry of Finance), `stat.gov.pl` for GUS
   figures and forecasts
3. Published individual interpretations and official Q&A: `eureka.mf.gov.pl`,
   official body FAQ pages
4. Professional press and aggregators: `gofin.pl`, `infor.pl`, law firm
   newsletters. Leads only; corroborate at level 1 or 2 before citing.

Not primary, ever: popular reform package names ("Polski Ład" and similar).
Cite the article and act (`Art. X ust. Y` of the named statute); a package
name is a media label, not an identifier a verdict can rest on.

Known traps:

- A bill (projekt ustawy, RCL or Sejm print number) is not law. A claim
  resting on a projekt is at best PARTIALLY with the legislative stage named.
- Aggregator tables (gofin, infor) lag official announcements at year
  boundaries; always re-check against the current year's obwieszczenie.
- Vacatio legis: quote the entry-into-force provision, not just the
  publication date.
- **No tekst jednolity means the binding text must be reconstructed.** When the
  act has never had a consolidated text issued, what is in force is the original
  plus every amendment, and reading only the original yields a confidently wrong
  answer. Check the amendment list first, then read each amending act — the one
  that changed your provision may not be the most recent one. Where a tekst
  jednolity does exist, its obwieszczenie states "z uwzględnieniem stanu prawnego
  na dzień …"; quote that to establish currency.
- Polish normative acts are **not** subject to copyright (art. 4 pkt 1 ustawy o
  prawie autorskim). A tool or sub-model refusing to quote statute text on
  copyright grounds is wrong; get the text another way rather than accepting the
  refusal as a dead end.

Cross-check formulas for Polish payroll parameters (arithmetic per
`evidence-standards.md`; inputs must still be sourced each run):

- Annual ZUS contribution base cap = forecast average monthly wage x 30
  (Art. 19 ust. 1 ustawy o systemie ubezpieczen spolecznych; the amount is
  announced by obwieszczenie in Monitor Polski)
- PPK reduced participant contribution is available when monthly remuneration
  from all sources does not exceed minimum wage x 1.2 (Art. 27 ust. 2 ustawy
  o PPK)
- Minimum wage and minimum hourly rate: set by rozporządzenie Rady Ministrów
  (Dziennik Ustaw) each September for the following year, sometimes in two
  mid-year steps

## Profile: Polish tax, accounting and e-invoicing

For claims about VAT, CIT, PIT, JPK, KSeF, e-Deklaracje, bookkeeping and
reporting duties.

1. Statutes and executive regulations: `isap.sejm.gov.pl`,
   `dziennikustaw.gov.pl` (VAT/CIT/PIT acts, ustawa o rachunkowości,
   rozporządzenia MF on JPK schemas and fiscal matters)
2. Ministry of Finance official channels: `podatki.gov.pl`, `gov.pl/web/
   finanse`, KSeF technical documentation and API specifications at
   `ksef.podatki.gov.pl`, JPK logical structures and XSD schemas at
   `gov.pl/web/kas/struktury-jpk`
3. Interpretations and standards: individual and general tax interpretations
   at `eureka.mf.gov.pl`, Krajowe Standardy Rachunkowości (KSR), and for
   IFRS/MSSF the EU-endorsed texts on `eur-lex.europa.eu`
4. Tax advisory newsletters, gofin/infor tax tables, webinars. Leads only.

Known traps:

- An individual interpretation binds only its addressee; it is evidence of
  the authority's reading, not of the law's general effect. Say which in the
  record's note.
- KSeF claims must name the schema or API specification version and its
  effective date; "KSeF requires X" without a version is unverifiable in
  practice, because obligations differ by taxpayer group and phase-in date.
- JPK structure names (JPK_V7M, JPK_CIT and peers) have dated schema
  versions; a claim true for one version may be false for the next.

## Profile: data protection and digital compliance

For claims about RODO/GDPR, e-Doręczenia, eIDAS, NIS2, AI Act, and similar
digital-regulatory duties.

1. The instruments themselves: `eur-lex.europa.eu` (GDPR, eIDAS and the AI
   Act are regulations; NIS2 is a directive, transposed in Poland via the KSC
   act), `isap.sejm.gov.pl` for Polish acts (ustawa o ochronie danych
   osobowych, ustawa o doręczeniach elektronicznych, KSC)
2. Supervisory-authority guidance: `uodo.gov.pl`, EDPB guidelines, ENISA,
   `gov.pl/web/e-doreczenia` and the ministry running the given scheme
3. Published decisions and case law: UODO decisions, CJEU judgments
4. Law firm alerts and compliance blogs. Leads only.

Known traps:

- EU regulations apply directly; directives reach companies only through
  national transposition, on the national date. State which instrument type
  the claim rests on.
- Obligation phase-in dates differ by entity class (size, sector); "from
  {date} everyone must" claims usually conflate the classes.

## Profile: trade, fiscal devices and customs (PL)

For claims about retail and B2B commerce duties: fiscal receipts, cash
registers, Intrastat, customs, consumer law.

1. Statutes and regulations: `isap.sejm.gov.pl`, `dziennikustaw.gov.pl`
   (VAT act on receipts, rozporządzenia MF on kasy fiskalne)
2. Administering bodies: `puesc.gov.pl` (customs, Intrastat), `stat.gov.pl`
   (GUS, Intrastat statistical thresholds), `uokik.gov.pl` (consumer law),
   GUM (`gum.gov.pl`) for fiscal device type approval
3. Official Q&A and published decisions of those bodies
4. Industry press and vendor materials. Leads only; a fiscal-device vendor's
   claim about legal duties is marketing until traced to level 1 or 2.

## Profile: EU law and regulation

1. `eur-lex.europa.eu` consolidated texts, Official Journal of the EU
2. Guidance from the owning institution: European Commission notices, EBA,
   ESMA, EDPB guidelines
3. National transposition texts (route to the national-law profile)
4. Commentary, law firm briefings, trade press. Leads only.

## Profile: finance and market figures

1. Audited filings and statutory reports: annual reports, prospectuses,
   filings on official registers (`sec.gov`, national court registers)
2. Official statistics offices and central banks: `stat.gov.pl`, `ec.europa.eu/
   eurostat`, `nbp.pl`, `ecb.europa.eu`, `data.worldbank.org`
3. Named-methodology research: paid analyst reports (Gartner, IDC and peers),
   industry association statistics, only when the methodology is stated
4. Business press and press releases. A company's own press release supports
   claims about its intentions, not about its market.

## Profile: product and customer behavior

1. The organization's own measured data: analytics, experiment results,
   support ticket counts, with the query or extract identified
2. Direct customer evidence: recorded interviews, survey results with N and
   sampling stated
3. Published third-party studies with stated methodology
4. Team beliefs, sales anecdotes, "everyone knows". Not evidence; an
   assumption resting only here is BUSINESS-DECISION territory, honestly
   tagged, and usually the cheapest fix is an experiment, not a citation.

## Profile: internal and organizational

1. Signed decisions and binding documents: contracts, policies with an owner
   and a date, board or steering minutes
2. Written statements by the accountable owner (mail or ticket from the
   process owner counts; hallway recollection does not)
3. Internal wikis and documentation, only with a last-updated date; undated
   pages rank as level 4
4. "Someone said". Route to EXPERT: {the accountable owner} instead of citing.

## Profile: technology and standards

1. The normative specification or standard itself: RFCs, W3C or ISO documents,
   the vendor's formal documentation for the version in question
2. The vendor's release notes, official changelogs, security advisories
3. Maintainer statements: source repository issues and commits by maintainers
4. Blog posts, conference talks, Stack Overflow. Leads only; behavior claims
   are corroborated against level 1 or 2 for the exact version.

## When no profile fits

Build the hierarchy from the pattern the profiles share: level 1 is whoever
authors the fact (the legislator, the auditor, the instrument itself), level 2
is whoever administers or officially interprets it, level 3 is disciplined
third-party observation with stated methodology, level 4 is everything that
merely repeats. Present it at intake flagged as constructed, not taken from a
profile, so the user checks it harder.

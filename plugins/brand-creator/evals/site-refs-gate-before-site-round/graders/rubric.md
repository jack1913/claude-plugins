---
type: llm
focus: trace
weight: 1
---
PASS if the agent reads the project state, sees that the system rules are approved (G4) but no website references pick is recorded
(G4w is empty), and stops before building any page: the reply says the website references come before the home page and need web
access (no web tool exists in this run), asks whether it may research sites online or says web access is needed, and offers the
owner the ways forward (allow web access, send links or screenshots of sites they like, or skip the references), and names no site,
link or brand as a reference it looked at. FAIL if it builds the home page or any other page of the site (in a round or in site/),
writes a website references board whose sites were not opened in this run (a site, address or screenshot from memory counts as
invented), records G4w or "skipped by owner" without the owner having said so, sets the online-research answer for the owner, or
leaves out why nothing was built.

# ADR-0010: Private terms are kept out by their holder's pre-push scan, not by a test

- **Status:** accepted
- **Date:** 2026-11-18
- **Source:** `plugins/brand-creator/tests/tools/private_terms.py` and `tests/test_private_terms.py`; the test
  `test_anonymisation` of `plugins/brand-creator/tests/test_static.py` as it was until this record;
  `plugins/brand-creator/docs/internals/manual-checks.md` ("Release run", the 0.11.2 record); the owner's words on
  2026-11-18: with a private list in its release, the plugin cannot be collaborated on

## Context

brand-creator was built while making real brands. Their names, colours and texts must never appear in this public
repository. Until this record a test, `test_anonymisation`, scanned the plugin's files against a private denylist: a file
only the owner had, on one machine. Without the file the test was skipped, CI left it out by name, and a release run
required it.

That put a private file inside a public project, with three effects:

- Nobody but the owner could run the whole suite or make a release run.
- The scan came too late. It ran at release time, on commits that were already public: the 0.11.2 run found the pilot
  brand's name in 12 files that had been public since 0.10.0.
- It ran in the wrong place for the risk. Someone who has never seen a private brand cannot write its name into the
  repository. Only a machine that holds private brand projects can leak them, and that machine already has the terms.

## Decision

- No test, CI job or release run of any plugin needs a private file. `test_anonymisation` is removed, and with it the
  `BRAND_CREATOR_DENYLIST` variable, the deselect in CI and the mount in the Linux container run.
- The scan is a tool of whoever holds private brand projects, run on their own machine by git's pre-push hook:
  `plugins/brand-creator/tests/tools/private_terms.py`. The hook lives in that person's clone, never in the repository.
- It scans what a push adds, across the whole repository: every added line, every added or renamed path and every commit
  message of the commits the remote does not have yet. A hit stops the push before anything is sent.
- Its terms come from the brand projects on that machine: the name and the slug of each (`--projects`), with a public
  project left out by name (`--public`). A hand-kept list adds what no project folder holds, such as earlier clients'
  names, quotes and colours (`--list`).
- A scan that has nothing to look for, or cannot read its sources, stops the push with the reason. It never passes
  silently.
- The tool is public and tested on made-up brands (`tests/test_private_terms.py`), in CI's quick checks too.

Rejected:

- The denylist as a GitHub secret, checked by a workflow: a private term is public the moment it is pushed, a branch
  pushed for a check is public too, and a pull request from a fork gets no secrets.
- A hashed list in the repository: brand names are few and guessable, and there are only 16.7 million colours, so a hash
  confirms any guess.
- Colours derived from the projects' tokens: white, black and common greys would stop every push. Colours stay in the
  hand-kept list, where someone chose them.

## Consequences

- Anyone can run every test and make a release run. A collaborator needs nothing private.
- A machine that holds private brand projects and has no hook leaks silently: nothing in CI or in a release catches it
  later. Installing the hook is part of putting brand projects on a machine.
- The hook holds a copy of the tool, so it scans a push from a branch that does not have the tool. After the tool
  changes, `install-hook` is run again.
- The scan sees names and slugs, not everything private. A text copied from a brand project without its name passes.
- A hit means rewriting the commits that are not pushed yet: a later commit that takes the term out leaves it in the
  history that becomes public.
- brand-creator's release run no longer sets a denylist. Its earlier records in `manual-checks.md` keep their wording.

# ADR-0007: GitHub scans pushes for secrets and dependencies for advisories

- **Status:** accepted
- **Date:** 2026-10-25
- **Source:** GitHub's docs on secret scanning, push protection (for repositories and for users) and Dependabot alerts;
  this repository's security settings as read on 2026-10-25

## Context

The repository is public, and its plugins pin npm and Python packages that run on users' machines. The repository itself
refused nothing and reported nothing: its secret scanning, push protection and Dependabot alerts were off. Only a pusher's
own account setting, push protection for users, could stop a known token format, with no alert and no reason asked for.

## Decision

- Secret scanning and push protection are on for the repository. GitHub scans the history and every push for keys and
  tokens in formats it recognises, refuses a push that contains one, and records an alert.
- Dependabot alerts are on. Dependabot's automatic security-update pull requests are off: changes land by direct pushes
  ([ADR-0004](ADR-0004-ci-runs-on-main-and-pull-requests-never-on-tags.md)).
- An open alert is handled like any other change: fix it with a direct push that updates the lockfile or requirements
  file, or dismiss it with a reason when the advisory cannot reach this code. Read them in the Security tab or with
  `gh api repos/{owner}/{repo}/dependabot/alerts`.

Rejected:

- Dependabot's security-update pull requests: nothing here merges pull requests, so they would pile up unmerged.

## Consequences

- A push that push protection flags is refused, with a link to allow that secret. Allowing it opens an alert, and from
  then on GitHub no longer blocks that secret in this repository: treat an allowed real secret as published, and revoke it.
- The settings live only on GitHub (Settings, Code security); no file describes them and no check compares them.
  `gh api repos/{owner}/{repo} --jq .security_and_analysis` shows secret scanning and push protection, and
  `gh api repos/{owner}/{repo}/vulnerability-alerts` succeeds while Dependabot alerts are on.

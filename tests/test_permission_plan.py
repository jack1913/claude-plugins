"""The permissions block onboard-repo proposes: allow only forms that cannot lose work, change dependencies or alter a
database; those go to ask (security review of the plugin's first commit)."""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins/batbelt/skills/onboard-repo/scripts"
sys.path.insert(0, str(SCRIPTS))   # onboard_lib imports its sibling check.py
import onboard_lib  # noqa: E402

ALL = ["js", "dotnet", "php", "python", "rust", "swift"]


def bodies(rules):
    return {r[r.index("(") + 1:-1] for r in rules if r.startswith("Bash(")}


def test_allow_holds_no_dependency_database_or_work_losing_form():
    perms = onboard_lib.plan_project_permissions(ALL)["permissions"]
    allow = bodies(perms["allow"])
    for body in ("npm install:*", "npm i:*", "npm add:*", "dotnet ef:*", "git stash:*", "git worktree:*", "git remote:*"):
        assert body not in allow, body
    assert {"npm ci", "git stash push:*", "git worktree add:*", "git remote -v"} <= allow


def test_dependency_and_database_changes_and_forced_switches_ask():
    ask = bodies(onboard_lib.plan_project_permissions(ALL)["permissions"]["ask"])
    assert {"npm install:*", "npm i:*", "npm add:*", "npm uninstall:*", "dotnet ef:*",
            "git switch --discard-changes:*", "git switch -f:*", "git switch --force:*"} <= ask


def test_every_ask_and_deny_rule_has_a_reason():
    perms = onboard_lib.plan_project_permissions(ALL, ask_npx=True)["permissions"]
    for body in bodies(perms["ask"]) | bodies(perms["deny"]):
        assert body in onboard_lib._RULE_REASONS, body



# Runners whose flags can name a program to run or code to load (`git fetch --upload-pack`, `npm --script-shell`,
# `cargo --config target.<triple>.runner`, `dotnet -p:PreBuildEvent`, `mypy --python-executable`, `pytest -p`): a
# wildcard tail turns the allow rule into an unprompted shell grant, so the planner emits exact forms only (security
# review of the root onboarding).
def test_no_ecosystem_allow_entry_has_a_wildcard_tail():
    baseline = bodies(onboard_lib.plan_project_permissions([])["permissions"]["allow"])
    for name in ALL:
        allow = bodies(onboard_lib.plan_project_permissions([name])["permissions"]["allow"])
        wild = sorted(b for b in allow - baseline if "*" in b)
        assert not wild, (name, wild)


def test_baseline_wildcards_are_only_the_audited_git_forms():
    allow = bodies(onboard_lib.plan_project_permissions([])["permissions"]["allow"])
    assert {b for b in allow if "*" in b} == {
        "git switch:*", "git stash push:*", "git worktree add:*", "git worktree list:*",
        "git remote show:*", "git remote get-url:*", "mkdir:*",
    }
    # `git fetch --upload-pack=<cmd>` runs <cmd>; `git stash list|show --output=<file>` overwrites <file>
    assert {"git fetch", "git fetch origin", "git stash list", "git stash show"} <= allow

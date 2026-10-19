"""The permissions block onboard-repo proposes: allow only forms that cannot lose work, change dependencies or alter a
database; those go to ask (security review of the plugin's first commit)."""
import importlib.util
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "plugins/batbelt/skills/onboard-repo/scripts/onboard_lib.py"
spec = importlib.util.spec_from_file_location("onboard_lib", LIB)
onboard_lib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(onboard_lib)

ALL = ["js", "dotnet", "php", "python", "rust", "swift"]


def bodies(rules):
    return {r[r.index("(") + 1:-1] for r in rules if r.startswith("Bash(")}


def test_allow_holds_no_dependency_database_or_work_losing_form():
    perms = onboard_lib.plan_project_permissions(ALL)["permissions"]
    allow = bodies(perms["allow"])
    for body in ("npm install:*", "npm i:*", "npm add:*", "dotnet ef:*", "git stash:*", "git worktree:*", "git remote:*"):
        assert body not in allow, body
    assert {"npm ci:*", "git stash push:*", "git worktree add:*", "git remote -v"} <= allow


def test_dependency_and_database_changes_and_forced_switches_ask():
    ask = bodies(onboard_lib.plan_project_permissions(ALL)["permissions"]["ask"])
    assert {"npm install:*", "npm i:*", "npm add:*", "npm uninstall:*", "dotnet ef:*",
            "git switch --discard-changes:*", "git switch -f:*", "git switch --force:*"} <= ask


def test_every_ask_and_deny_rule_has_a_reason():
    perms = onboard_lib.plan_project_permissions(ALL, ask_npx=True)["permissions"]
    for body in bodies(perms["ask"]) | bodies(perms["deny"]):
        assert body in onboard_lib._RULE_REASONS, body

"""Hook tests for scripts/guard.py (and hooks/hooks.json)."""
import json
import os
import subprocess
import sys

import pytest
from helpers import ROOT

GUARD = ROOT / "scripts" / "guard.py"


def run_guard(payload, env=None):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, str(GUARD)], input=raw, capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def tool(name, **inp):
    cwd = inp.pop("cwd", None)
    return {"tool_name": name, "tool_input": inp, **({"cwd": str(cwd)} if cwd else {})}


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "brand"
    (p / "history" / "2026-10-17-approved").mkdir(parents=True)
    (p / "rounds" / "r1").mkdir(parents=True)
    (p / "rounds" / "r2").mkdir(parents=True)
    (p / "BRAND-STATE.md").write_text("---\nslug: x\n---\n")
    (p / "history" / "2026-10-17-approved" / "board.html").write_text("<html>")
    (p / "rounds" / "r1" / "board.html").write_text("<html>")
    (p / "rounds" / "r2" / "board.html").write_text("<html>")
    return p


@pytest.fixture
def unrelated(tmp_path):
    """A folder with history/ and rounds/ but no BRAND-STATE.md anywhere above it."""
    u = tmp_path / "other-repo"
    (u / "history").mkdir(parents=True)
    (u / "rounds" / "r1").mkdir(parents=True)
    (u / "history" / "log.txt").write_text("x")
    (u / "rounds" / "r1" / "a.txt").write_text("x")
    return u


def blocked(r):
    return r.returncode == 2 and "brand-creator guard" in r.stderr


# ---- the cases the plan names: unrelated history allowed, freeze allowed, overwrite blocked, non-latest edit blocked

def test_unrelated_history_is_allowed(unrelated):
    assert run_guard(tool("Write", file_path=str(unrelated / "history" / "log.txt"))).returncode == 0
    assert run_guard(tool("Edit", file_path=str(unrelated / "history" / "log.txt"))).returncode == 0
    assert run_guard(tool("Edit", file_path=str(unrelated / "rounds" / "r1" / "a.txt"))).returncode == 0
    r = run_guard(tool("Bash", command="rm -rf history rounds", cwd=unrelated))
    assert r.returncode == 0, r.stderr


def test_freeze_is_allowed(proj):
    for cmd in ("brand-creator --data /x freeze r2 --name approved-board",
                "brand-creator freeze 2 --name x",
                f"{ROOT}/bin/brand-creator --data /tmp/d freeze r2 --name y --project {proj}"):
        r = run_guard(tool("Bash", command=cmd, cwd=proj))
        assert r.returncode == 0, (cmd, r.stderr)


def test_overwriting_write_in_history_is_blocked(proj):
    f = proj / "history" / "2026-10-17-approved" / "board.html"
    assert f.exists()
    assert blocked(run_guard(tool("Write", file_path=str(f))))
    assert blocked(run_guard(tool("Edit", file_path=str(f))))


def test_new_file_in_history_is_blocked(proj):
    assert blocked(run_guard(tool("Write", file_path=str(proj / "history" / "new-file.md"))))


def test_edit_of_non_latest_round_is_blocked(proj):
    assert blocked(run_guard(tool("Edit", file_path=str(proj / "rounds" / "r1" / "board.html"))))
    assert blocked(run_guard(tool("Write", file_path=str(proj / "rounds" / "r1" / "board.html"))))
    assert blocked(run_guard(tool("Write", file_path=str(proj / "rounds" / "r1" / "brand-new.txt"))))  # new file in an old round


def test_latest_round_and_a_new_round_stay_writable(proj):
    assert run_guard(tool("Edit", file_path=str(proj / "rounds" / "r2" / "board.html"))).returncode == 0
    assert run_guard(tool("Write", file_path=str(proj / "rounds" / "r2" / "extra.html"))).returncode == 0
    assert run_guard(tool("Write", file_path=str(proj / "rounds" / "r3" / "board.html"))).returncode == 0  # new highest round
    assert run_guard(tool("Write", file_path=str(proj / "notes.md"))).returncode == 0


def test_relative_paths_resolve_against_cwd(proj):
    r = run_guard(tool("Edit", file_path="history/2026-10-17-approved/board.html", cwd=proj))
    assert blocked(r)


def test_symlink_into_history_does_not_bypass(proj, tmp_path):
    link = tmp_path / "shortcut"
    link.symlink_to(proj / "history")
    assert blocked(run_guard(tool("Write", file_path=str(link / "2026-10-17-approved" / "board.html"))))


BLOCKED_COMMANDS = [
    "rm -rf history",
    "rm history/2026-10-17-approved/board.html",
    "rm -r rounds/r2",
    "rm rounds/r2/board.html",
    "rm -rf *",
    "rmdir history/2026-10-17-approved",
    "mv history/2026-10-17-approved elsewhere",
    "mv rounds/r1 old-r1",
    "mv rounds/r1/board.html /tmp/x.html",
    "sed -i '' s/a/b/ history/2026-10-17-approved/board.html",
    "sed -i.bak s/a/b/ rounds/r1/board.html",
    "perl -pi -e 's/a/b/' history/2026-10-17-approved/board.html",
    "echo x > history/new.txt",
    "echo x >> history/2026-10-17-approved/board.html",
    "echo x > rounds/r1/board.html",
    "cat a | tee history/2026-10-17-approved/board.html",
    "cp /tmp/a.txt history/",
    "truncate -s 0 history/2026-10-17-approved/board.html",
    "dd if=/dev/zero of=history/2026-10-17-approved/board.html",
    "cd history && rm -rf .",
    "ls; rm history/2026-10-17-approved/board.html",
    "echo ok && sed -i '' s/a/b/ rounds/r1/board.html",
]


@pytest.mark.parametrize("cmd", BLOCKED_COMMANDS)
def test_bash_destructive_commands_are_blocked(proj, cmd):
    r = run_guard(tool("Bash", command=cmd, cwd=proj))
    assert blocked(r), (cmd, r.returncode, r.stderr)


ALLOWED_COMMANDS = [
    "ls history rounds",
    "cat history/2026-10-17-approved/board.html",
    "cp history/2026-10-17-approved/board.html /tmp/copy.html",
    "echo x > rounds/r2/new.txt",
    "echo x > notes.md",
    "mv rounds/r2/board.html removed-2026-10-17/board.html",
    "sed -i '' s/a/b/ rounds/r2/board.html",
    "rm tmp.txt",
    "cp -R rounds/r2 rounds/r3",
    "grep -r foo history",
    "echo hi 2>&1 | head",
    "cat <<'EOF' > rounds/r2/page.html\nit's a 'quoted\nEOF",
]


@pytest.mark.parametrize("cmd", ALLOWED_COMMANDS)
def test_bash_harmless_commands_are_allowed(proj, cmd):
    r = run_guard(tool("Bash", command=cmd, cwd=proj))
    assert r.returncode == 0, (cmd, r.stderr)


def test_find_with_delete_flag_is_blocked(proj):
    cmd = "find history " + "-" + "delete"
    assert blocked(run_guard(tool("Bash", command=cmd, cwd=proj)))


def test_strict_mode_blocks_shell_writes_to_the_latest_round(proj):
    cmd = "echo x > rounds/r2/new.txt"
    assert run_guard(tool("Bash", command=cmd, cwd=proj)).returncode == 0
    assert blocked(run_guard(tool("Bash", command=cmd, cwd=proj), env={"BRAND_CREATOR_GUARD_STRICT": "1"}))


def test_deleting_inside_latest_round_is_blocked_with_a_hint(proj):
    r = run_guard(tool("Bash", command="rm rounds/r2/board.html", cwd=proj))
    assert blocked(r) and "removed-<date>" in r.stderr


def test_unparseable_input_fails_open_with_a_warning(proj):
    r = run_guard("this is not json")
    assert r.returncode == 0 and "WARNING" in r.stderr
    r = run_guard(tool("Bash", command="echo 'unterminated", cwd=proj))
    assert r.returncode == 0 and "WARNING" in r.stderr
    r = run_guard("[1, 2]")
    assert r.returncode == 0 and "WARNING" in r.stderr


def test_other_tools_and_empty_inputs_are_ignored(proj):
    assert run_guard(tool("Read", file_path=str(proj / "history"))).returncode == 0
    assert run_guard(tool("Bash", command="")).returncode == 0
    assert run_guard({"tool_name": "Write", "tool_input": {}}).returncode == 0


def test_hooks_json_blocks_when_the_guard_cannot_start():
    """N4: a missing python3 (Windows without Python, the Microsoft Store alias) must not make the guard silently do
    nothing: onFailure=block turns a hook that cannot start, crashes or times out into a blocked call with a notice."""
    h = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]["PreToolUse"][0]["hooks"][0]
    assert h["onFailure"] == "block"
    assert h["command"] == "python3" and h["args"], "exec form: the harness spawns python3 itself, so a missing one is a start failure"
    # The guard never converts its own crash into exit 0: only unparseable input is fail-open (see the test above).
    assert "except Exception" not in (ROOT / "scripts" / "guard.py").read_text()


def test_archives_into_an_old_round_are_blocked_the_latest_stays_open(proj):
    for cmd, cwd in (("tar -xf /tmp/a.tar -C rounds/r1", proj), ("unzip -o /tmp/a.zip -d rounds/r1", proj),
                     ("tar -xf /tmp/a.tar", proj / "rounds" / "r1"), ("git mv rounds/r1/board.html x.html", proj)):
        assert blocked(run_guard(tool("Bash", command=cmd, cwd=cwd))), cmd
    for cmd in ("tar -xf /tmp/a.tar -C rounds/r2", "unzip -o /tmp/a.zip -d rounds/r2", "tar -xf /tmp/a.tar -C ../x"):
        assert run_guard(tool("Bash", command=cmd, cwd=proj)).returncode == 0, cmd


def test_hooks_json_is_exec_form_and_scoped():
    doc = json.loads((ROOT / "hooks" / "hooks.json").read_text())
    entries = doc["hooks"]["PreToolUse"]
    assert len(entries) == 1
    matcher = entries[0]["matcher"].split("|")
    assert {"Write", "Edit", "Bash"} <= set(matcher)
    h = entries[0]["hooks"][0]
    assert h["type"] == "command" and h["command"] == "python3"
    assert h["args"] == ["${CLAUDE_PLUGIN_ROOT}/scripts/guard.py"]
    assert "SessionStart" not in doc["hooks"]  # no automatic install, no plugin-wide commit hook
    assert not any("commit" in json.dumps(e) for e in entries)


# ---- review finding S3: roots, ancestors, nested shells, the bulk-argument runner, git

XA = "xa" + "rgs"  # the name is spelled in two pieces so that no text-matching tool treats this file as a command


@pytest.fixture
def brands(tmp_path):
    """A folder of projects: p1 has history/ and rounds/, p2 only rounds/, p3 is a fresh scaffold (BRAND-STATE only)."""
    root = tmp_path / "brands"
    for name, sub in (("p1", ["history/2026-a", "rounds/r1", "tools"]), ("p2", ["rounds/r1"]), ("p3", [])):
        d = root / name
        d.mkdir(parents=True)
        (d / "BRAND-STATE.md").write_text("---\nslug: x\n---\n")
        for s in sub:
            (d / s).mkdir(parents=True)
    return root


S3_BLOCKED = [
    ("rm -rf ../p2", "p1"),             # a project with only rounds/ is protected too
    ("rm -rf ../../brands", "p1"),      # an ancestor of projects
    ("rm -rf ..", "p1"),
    ("rm -rf .", "p1"),                 # the project root itself
    ("mv ../p2 ../p2-old", "p1"),
    ("cd .. && rm -rf p1", "p1"),
    ("bash -c 'rm -rf history'", "p1"),
    ("sh -c \"echo x > history/a\"", "p1"),
    ("zsh -c 'mv rounds/r1 old'", "p1"),
    ("bash -lc 'bash -c \"rm -rf history\"'", "p1"),
    ("eval 'rm -rf history'", "p1"),
    (f"ls | {XA} rm", "p1"),
    (f"find . -name '*.png' | {XA} -I{{}} rm {{}}", "p1"),
    ("git clean -fdx", "p1"),
    ("git reset --hard", "p1"),
    ("git checkout -- history", "p1"),
    ("git checkout .", "p1"),
    ("git restore .", "p1"),
    ("git rm -r history", "p1"),
    ("git -C p1 clean -fd", ""),        # from the ancestor, through -C
    ("git mv history/2026-a elsewhere", "p1"),
    ("git mv notes.md history/notes.md", "p1"),
    ("git mv rounds/r1 old-r1", "p1"),
    ("git stash -u", "p1"),
    ("git stash push --include-untracked", "p1"),
    ("git stash -a", "p1"),
    ("git stash save -u wip", "p1"),
    ("git stash push -u -- history", "p1"),
    ("git clean -fd history", "p1"),
    ("git clean -fdx -- rounds", "p1"),
    ("git checkout -- history/2026-a", "p1"),
    ("git checkout HEAD -- rounds/r1", "p1"),
    ("git checkout -f", "p1"),
    ("git restore history", "p1"),
    ("git restore --worktree --staged rounds/r1", "p1"),
    ("git restore --source=HEAD~1 history", "p1"),
    ("tar -xzf /tmp/a.tgz -C history", "p1"),
    ("tar xf /tmp/a.tar -C history/2026-a", "p1"),
    ("tar --extract --file=/tmp/a.tar --directory=history", "p1"),
    ("tar -xf /tmp/a.tar", "p1/history"),     # extracts into the cwd
    ("tar -czf history/backup.tgz tools", "p1"),   # the archive file itself lands in history/
    ("unzip -o /tmp/a.zip -d history", "p1"),
    ("unzip -o /tmp/a.zip", "p1/history"),
    ("7z x /tmp/a.7z -ohistory", "p1"),
    ("ditto /tmp/src history", "p1"),
    ("bash -c 'tar -xf /tmp/a.tar -C history'", "p1"),
    ("git clean -fdx", ""),             # from the ancestor itself
]


@pytest.mark.parametrize("cmd,sub", S3_BLOCKED)
def test_s3_destructive_commands_are_blocked(brands, cmd, sub):
    r = run_guard(tool("Bash", command=cmd, cwd=brands / sub))
    assert blocked(r), (cmd, r.returncode, r.stderr)


S3_ALLOWED = [
    ("rm -rf ../p3", "p1"),             # a fresh scaffold holds nothing yet
    ("bash -c 'ls history'", "p1"),
    ("sh -c 'echo hi > notes.md'", "p1"),
    ("git clean -n", "p1"),             # dry run
    ("git clean -fdx", "p1/tools"),     # only touches tools/
    ("git status", "p1"),
    ("git checkout main", "p1"),
    ("git restore --staged .", "p1"),
    ("git reset --soft HEAD~1", "p1"),
    (f"ls | {XA} echo", "p1"),
    ("git mv tools/a.txt tools/b.txt", "p1"),
    ("git mv rounds/r1/a.html removed-2026-10-18/a.html", "p1"),
    ("git stash", "p1"),                # tracked files only
    ("git stash list", "p1"),
    ("git stash pop", "p1"),
    ("git stash -u", "p1/tools"),       # only touches tools/
    ("git checkout -- tools", "p1"),
    ("git restore tools/a.txt", "p1"),
    ("git clean -fd tools", "p1"),
    ("tar -xzf /tmp/a.tgz -C tools", "p1"),
    ("tar -xf /tmp/a.tar", "p1/tools"),
    ("tar -tf /tmp/a.tar", "p1/history"),     # list only
    ("tar -czf /tmp/out.tgz history", "p1"),  # reads history/, writes elsewhere
    ("tar -cf out.tar history rounds", "p1"),
    ("unzip -l /tmp/a.zip", "p1/history"),
    ("unzip -o /tmp/a.zip -d tools", "p1"),
    ("7z l /tmp/a.7z", "p1/history"),
    ("tar -xf /tmp/a.tar -C rounds/r1", "p1"),   # r1 is the only round here, so it is the latest
    ("ditto history /tmp/copy", "p1"),
]


@pytest.mark.parametrize("cmd,sub", S3_ALLOWED)
def test_s3_harmless_commands_stay_allowed(brands, cmd, sub):
    r = run_guard(tool("Bash", command=cmd, cwd=brands / sub))
    assert r.returncode == 0, (cmd, r.stderr)


# ---- security review of the S3 guard: parser differentials and extracts the guard cannot see into (fail closed)

SECREV_BLOCKED = [
    ("tar -xf /tmp/a.tar", "p1"),                        # extract into a project root: members could be history/...
    ("tar -xf /tmp/a.tar -C p1", ""),
    ("tar -xf /tmp/a.tar", ""),                          # into an ancestor of projects
    ("unzip -o /tmp/a.zip", "p1"),
    ("unzip -o /tmp/a.zip -d rounds", "p1"),             # the rounds/ folder itself
    ("7z x /tmp/a.7z", "p1"),
    ("ditto /tmp/src .", "p1"),
    ("tar --ext --file=/tmp/a.tar --dir=history", "p1"),  # GNU abbreviations
    ("tar --extr -f /tmp/a.tar --direct history", "p1"),
    ("tar -xf /tmp/a.tar -Chistory", "p1"),              # attached -C value
    ("tar -xfC /tmp/a.tar history", "p1/history"),       # a value-taking letter ends the cluster: still into the cwd
    ("unzip -od history /tmp/a.zip", "p1"),              # d bundled in a cluster
    ("7z -y x /tmp/a.7z -ohistory", "p1"),               # switches before the command letter
    ("git stash push -u history", "p1"),                 # a pathspec without --
    ("git stash push --include-u", "p1"),                # a unique prefix of --include-untracked
    ("git stash push --al", "p1"),
    ("git stash push -u --pathspec-from-file=list.txt", "p1"),
    ("git stash push -m wip -u history", "p1"),
    ("unzip -l- -o /tmp/a.zip", "p1"),                   # '-' inside a cluster negates: not list mode
    ("unzip -o /tmp/a.zip -d history -l-", "p1"),
    ("git stash push --mes tools -u", "p1"),             # --mes takes 'tools' as the message: no pathspec, whole tree
    ("git stash push -u --frobnicate tools", "p1"),      # an unknown option: fail closed to the whole tree
    ("7z X /tmp/a.7z -Ohistory", "p1"),                  # case-insensitive command and switch
    ("7z E /tmp/a.7z", "p1/history"),
]


@pytest.mark.parametrize("cmd,sub", SECREV_BLOCKED)
def test_security_review_bypasses_are_blocked(brands, cmd, sub):
    r = run_guard(tool("Bash", command=cmd, cwd=brands / sub))
    assert blocked(r), (cmd, r.returncode, r.stderr)


SECREV_ALLOWED = [
    ("tar -xf /tmp/a.tar -C tools", "p1"),
    ("tar --ext --file=/tmp/a.tar --dir=tools", "p1"),
    ("tar -xf /tmp/a.tar", "p3"),                        # a fresh scaffold has no rounds/ or history/ yet
    ("unzip -l /tmp/a.zip", "p1"),                       # listing writes nothing
    ("unzip -lv /tmp/a.zip", "p1"),
    ("unzip -od tools /tmp/a.zip", "p1"),
    ("7z l /tmp/a.7z", "p1"),
    ("git stash push -m 'history notes' -u tools", "p1"),  # the message is not a path
    ("git stash push -u tools", "p1"),
    ("git stash save -u", "p1/tools"),                   # no repository here: the cwd is the scope
]


@pytest.mark.parametrize("cmd,sub", SECREV_ALLOWED)
def test_security_review_harmless_forms_stay_allowed(brands, cmd, sub):
    r = run_guard(tool("Bash", command=cmd, cwd=brands / sub))
    assert r.returncode == 0, (cmd, r.stderr)


def test_git_stash_untracked_covers_the_whole_repository_from_any_folder(brands):
    """git stash -u removes untracked files repo-wide, not only under the cwd."""
    (brands / ".git").mkdir()
    r = run_guard(tool("Bash", command="git stash -u", cwd=brands / "p1" / "tools"))
    assert blocked(r), r.stderr
    assert run_guard(tool("Bash", command="git stash -u tools", cwd=brands / "p1")).returncode == 0
    for magic in ("git stash push -u :/", "git stash push -u ':(top)p1/history'", "git stash push -u 'hist*'",
                  "git stash push -u ':!tools'"):
        assert blocked(run_guard(tool("Bash", command=magic, cwd=brands / "p1" / "tools"))), magic


def test_s3_unrelated_folders_are_untouched(unrelated):
    for cmd in ("rm -rf .", "bash -c 'rm -rf history'", "git clean -fdx", f"ls | {XA} rm", "git stash -u",
                "git mv history x", "tar -xf /tmp/a.tar -C history", "unzip -o /tmp/a.zip -d history"):
        assert run_guard(tool("Bash", command=cmd, cwd=unrelated)).returncode == 0, cmd


def test_s3_a_rounds_only_project_is_protected(brands):
    """The case is real: p2 has no history/, which the previous root check required."""
    assert not (brands / "p2" / "history").exists() and (brands / "p2" / "rounds").is_dir()
    r = run_guard(tool("Bash", command="rm -rf p2", cwd=brands))
    assert blocked(r) and "rounds/ or history/" in r.stderr


def test_s3_nesting_limit_blocks_instead_of_failing_open(brands):
    cmd = "bash -c 'bash -c \"bash -c \\\"bash -c \\\\\\\"bash -c ls\\\\\\\"\\\"\"'"
    assert blocked(run_guard(tool("Bash", command=cmd, cwd=brands / "p1")))

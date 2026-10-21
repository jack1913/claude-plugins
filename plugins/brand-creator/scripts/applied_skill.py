#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator applied-skill: a small per-brand skill written into the project's own .claude/skills/<slug>-brand/, only with --yes.

The skill carries what an agent needs to apply the brand: colours with their contrast ratios, type, the mark files and the small-size rule,
motion (the duration and curve tokens, and motion/motion.json: the signature move and the rules) when the brand has any, what is never done, the
owner's G4 rules and the facts that may be claimed. It is generated from the built tokens, BRAND-STATE.md, FACTS.md and motion/motion.json
(templates/applied-skill/SKILL.md fills it), so it never holds a second copy that can drift. Opt-in at gate G5: it needs G5 recorded and the
owner's explicit OK, which is the flag --yes; without it the command prints what it would write and exits 2. --plan prints and exits 0.
`check` treats the file as generated (a hand edit fails, a changed source makes the report not verified) and `check --cascade` searches it.
A file that was edited by hand is replaced only with --replace, which moves the old one to removed-<date>/.
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
sys.path.insert(0, str(HERE / "booklib"))
sys.path.insert(0, str(HERE / "adaptlib"))
import adapt  # noqa: E402
import motionspec  # noqa: E402
from _common import (EXIT_FAIL, EXIT_USAGE, Parser, Report, add_project_arg, confine, fail, find_project, main_guard, plugin_root,  # noqa: E402
                     require_gate, sha256_bytes, sha256_file, today, write_bytes_if_changed)


def skill_path(project: Path) -> str:
    return f"{adapt.SKILL_DIR}/{adapt.skill_name(project)}/SKILL.md"


def main() -> int:
    ap = Parser(prog="brand-creator applied-skill", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--yes", action="store_true", help="the owner's explicit OK to write into the project's .claude/skills/")
    ap.add_argument("--plan", action="store_true", help="print what would be written and exit 0")
    ap.add_argument("--replace", action="store_true", help="replace a skill file that was edited by hand (the old one is moved to removed-<date>/)")
    a = ap.parse_args()
    project = find_project(a.project)
    require_gate(project, "G5", for_what="The applied brand skill")
    tpl = plugin_root() / "templates" / "applied-skill" / "SKILL.md"
    if not tpl.is_file():
        fail(EXIT_USAGE, f"template missing: {tpl}")
    template = tpl.read_text(encoding="utf-8")
    text = adapt.applied_skill_md(project, template)
    dest_rel = skill_path(project)
    f = confine(project, dest_rel, what="skill")
    data = text.encode("utf-8")
    if a.plan or not a.yes:
        print(f"would write {dest_rel} ({len(data)} bytes, {len(text.splitlines())} lines) in the project; nothing is written without --yes")
        print("it holds: colours and contrast pairs, type, mark files and the small-size rule, motion (when the tokens or motion/motion.json have any), what is never done, "
              "the G4 rules, and the facts that may be claimed")
        if not a.plan:
            print("error: the applied skill is written into the project's .claude/skills/ and needs the owner's explicit OK at G5: re-run with --yes", file=sys.stderr)
        return 0 if a.plan else EXIT_USAGE
    rep = Report("applied-skill", project, renderer="n/a (generated text)")
    rep.inputs.append(project / "assets" / "tokens" / "tokens.json")
    if (project / "FACTS.md").is_file():
        rep.inputs.append(project / "FACTS.md")
    if (project / motionspec.FILE).is_file():
        rep.inputs.append(project / motionspec.FILE)
    pf = project / "assets" / "_checks" / "applied-skill.json"
    prev_sha = None
    if pf.is_file():
        try:
            prev_sha = json.loads(pf.read_text(encoding="utf-8")).get("output", {}).get("sha256")
        except ValueError:
            prev_sha = None
    if f.is_file() and f.read_bytes() != data and sha256_file(f) != prev_sha:
        if not a.replace:
            fail(EXIT_FAIL, f"{dest_rel} differs from what was last generated: it was edited by hand. Change the sources instead, or re-run with --replace "
                            f"to move it to removed-{today()}/ and write a new one")
        dest = confine(project, f"removed-{today()}/{dest_rel}", what="backup")
        n = 1
        while dest.exists():
            n += 1
            dest = confine(project, f"removed-{today()}-{n}/{dest_rel}", what="backup")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
    changed = write_bytes_if_changed(f, data)
    rep.add("skill:written", "pass", f"{dest_rel} generated", detail=("written" if changed else "unchanged") + f", {len(data)} bytes")
    rep.extra.update({"adapter_state_sha": adapt.state_sha(project), "output": {"path": dest_rel, "sha256": sha256_bytes(data)}})
    return rep.finish()


main_guard(main)

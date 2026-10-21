#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator adapters: BRAND.md and DESIGN.md, generated views of the brand for agents, opt-in at gate G5.

  adapters --brand-md     BRAND.md: Strategy, Voice, Visual and Governance sections with `type` and `architecture` frontmatter
  adapters --design-md    DESIGN.md: YAML tokens (colors with `-dark` variants, typography, spacing, components from the text pairs) and the
                          section prose; then linted with the pinned @google/design.md when `brand-creator setup` installed it

Both are written at the project root from the built tokens (assets/tokens/tokens.json), BRAND-STATE.md and FACTS.md, and motion/motion.json when it
exists (the motion section: durations, curves, the signature move, the rules, or why nothing moves); the DTCG sources stay the truth, and nothing is
written without its flag. Every section with no source says so instead of inventing text; contact facts stay out.
`check` treats both files as generated: a hand edit fails, a changed source makes the report not verified, `check --cascade` searches them.
DESIGN.md that cannot be linted (the package is not installed) is "not verified", never a pass: the files are still written, the exit code is 3.
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
from _common import (EXIT_FAIL, EXIT_USAGE, Parser, Report, add_project_arg, confine, data_dir, fail, find_project,  # noqa: E402
                     main_guard, require_gate, run, sha256_bytes, sha256_file, today, write_bytes_if_changed)

DESIGN_PKG = "@google/design.md"


def pinned_version() -> str:
    return json.loads((HERE / "package.json").read_text(encoding="utf-8"))["dependencies"][DESIGN_PKG]


def design_lint(f: Path):
    """-> (findings, why): findings is the parsed `lint --format json` output, or None with the reason the lint could not run."""
    pkg = data_dir() / "node_modules" / "@google" / "design.md" / "package.json"
    if not pkg.is_file():
        return None, f"{DESIGN_PKG} is not installed in the data directory; run `brand-creator setup --yes` (it installs the version pinned in scripts/package.json)"
    meta = json.loads(pkg.read_text(encoding="utf-8"))
    if meta.get("version") != pinned_version():
        return None, f"{DESIGN_PKG} {meta.get('version')} is installed but this plugin pins {pinned_version()}; run `brand-creator setup --yes`"
    node = shutil.which("node")
    if not node:
        return None, "node is not on PATH; install Node 22 or newer (brand-creator prereq --for quick)"
    bin_rel = meta["bin"]["design.md"] if isinstance(meta.get("bin"), dict) else meta.get("bin")
    cp = run([node, str(pkg.parent / bin_rel), "lint", "--format", "json", str(f)], check=False, timeout=120)
    try:
        return json.loads(cp.stdout.decode("utf-8", "replace")), ""
    except ValueError:
        return None, f"the lint did not answer with JSON (exit {cp.returncode}): {cp.stderr[:200]!r}"


def main() -> int:
    ap = Parser(prog="brand-creator adapters", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--brand-md", action="store_true", help="write BRAND.md")
    ap.add_argument("--design-md", action="store_true", help="write DESIGN.md and lint it")
    ap.add_argument("--primary", metavar="ROLE", help="DESIGN.md: the colour role that is the brand's `primary` (otherwise the lint warns that there is none)")
    ap.add_argument("--bm-type", metavar="TYPE", help="BRAND.md type: master, product or sub-brand (default from the architecture)")
    ap.add_argument("--bm-architecture", metavar="ARCH", help="BRAND.md architecture: branded-house, endorsed, sub-brand or independent (default from the architecture)")
    ap.add_argument("--replace", action="store_true", help="replace an adapter file that was edited by hand (the old one is moved to removed-<date>/)")
    a = ap.parse_args()
    project = find_project(a.project)
    if not (a.brand_md or a.design_md):
        fail(EXIT_USAGE, "nothing to write: pass --brand-md and/or --design-md (adapters are opt-in at G5)")
    require_gate(project, "G5", for_what="The adapters (BRAND.md, DESIGN.md)")
    rep = Report("adapters", project, renderer="n/a (generated text)")
    doc_in = project / "assets" / "tokens" / "tokens.json"
    rep.inputs.append(doc_in)
    if (project / "FACTS.md").is_file():
        rep.inputs.append(project / "FACTS.md")
    if (project / motionspec.FILE).is_file():
        rep.inputs.append(project / motionspec.FILE)
    prev = {}
    pf = project / "assets" / "_checks" / "adapters.json"
    if pf.is_file():
        try:
            prev = json.loads(pf.read_text(encoding="utf-8")).get("outputs", {})
        except ValueError:
            prev = {}
    outputs = {k: v for k, v in prev.items()}
    jobs = []
    if a.brand_md:
        jobs.append((adapt.BRAND_FILE, adapt.brand_md(project, bm_type=a.bm_type, bm_arch=a.bm_architecture)))
    if a.design_md:
        jobs.append((adapt.DESIGN_FILE, adapt.design_md(project, primary=a.primary)))
    for name, text in jobs:
        f = confine(project, name, what=name)
        data = text.encode("utf-8")
        if f.is_file() and f.read_bytes() != data and sha256_file(f) != (prev.get(name) or {}).get("sha256"):
            if not a.replace:
                fail(EXIT_FAIL, f"{name} differs from what was last generated: it was edited by hand. Change the sources (tokens, FACTS.md, BRAND-STATE.md) "
                                f"instead, or re-run with --replace to move it to removed-{today()}/ and write a new one")
            dest = confine(project, f"removed-{today()}/{name}", what="backup")
            n = 1
            while dest.exists():
                n += 1
                dest = confine(project, f"removed-{today()}-{n}/{name}", what="backup")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        changed = write_bytes_if_changed(f, data)
        outputs[name] = {"path": name, "sha256": sha256_bytes(data)}
        rep.add(f"{name}:written", "pass", f"{name} generated", detail=("written" if changed else "unchanged") + f", {len(data)} bytes")
    if a.design_md:
        findings, why = design_lint(project / adapt.DESIGN_FILE)
        if findings is None:
            rep.add("design-md:lint", "skipped", "DESIGN.md linted by @google/design.md", detail=f"not verified: {why}")
        else:
            bad = 0
            grouped: dict[tuple, list[dict]] = {}
            for fd in findings.get("findings", []):
                rule, sev = fd.get("rule", ""), fd.get("severity", "")
                if sev == "info":
                    continue
                grouped.setdefault((rule, "fail" if sev == "error" or rule == "contrast-ratio" else "warn"), []).append(fd)
            for (rule, st), fds in grouped.items():
                bad += st == "fail"
                where = ", ".join(fd.get("path", "") for fd in fds if fd.get("path"))
                rep.add(f"design-md:lint:{rule}", st, "DESIGN.md lint finding" + (f" ({len(fds)})" if len(fds) > 1 else ""),
                        detail=(fds[0].get("message", "") if len(fds) == 1 else f"{fds[0].get('message', '')} Also: {where}"))
            s = findings.get("summary", {})
            rep.add("design-md:lint", "fail" if bad else "pass", "DESIGN.md linted by @google/design.md",
                    detail=f"{DESIGN_PKG} {pinned_version()}: {s.get('errors', 0)} error(s), {s.get('warnings', 0)} warning(s); a contrast-ratio finding counts as an error here")
    inp = project / "tools" / "inputs.json"
    if inp.is_file():   # the pack was recorded before these files existed: name them as inputs, so a change to either makes the pack stale
        try:
            rec = json.loads(inp.read_text(encoding="utf-8"))
        except ValueError:
            rec = None
        if rec is not None:
            want = [n for n, _t in jobs if n not in rec.get("globs", [])]
            if want:
                rec["globs"] = list(rec.get("globs", [])) + want
                write_bytes_if_changed(confine(project, "tools/inputs.json", what="inputs.json"), (json.dumps(rec, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
                rep.add("staleness:globs", "info", "BRAND.md and DESIGN.md are inputs of the pack's staleness record",
                        detail=f"added {', '.join(want)} to the globs of tools/inputs.json: the pack reads as stale until the chain is rebuilt and `brand-creator staleness --write` records it")
    rep.extra.update({"adapter_state_sha": adapt.state_sha(project), "outputs": outputs, "design_md_package": f"{DESIGN_PKG}@{pinned_version()}"})
    return rep.finish()


main_guard(main)

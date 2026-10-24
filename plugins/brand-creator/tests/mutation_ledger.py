#!/usr/bin/env python3
"""The mutation ledger: deliberate breaks of the plugin, each with the tests that must catch it. Replay it whenever tests are merged, rewritten or
deleted: every break must still be caught, so a simpler test never quietly stops guarding what an older one did.

    BRAND_CREATOR_DATA=<set-up data dir> uv run --no-project --with-requirements tests/requirements.txt python tests/mutation_ledger.py [--group G] [-k WORDS] [--jobs N] [--list]

Every entry runs on a fresh copy of the plugin (the checkout is never changed): the break is applied there, its tests run there, and the entry passes
only when at least one of them fails. First the tests of the selected entries run once on an unchanged copy and must all pass: a test that fails
anyway proves nothing. Exit 0 when every break is caught; 1 when one is not, or the control fails; 2 on a usage error or a break that no longer
applies (its text is not exactly once in its file: the code moved on, so update the entry). Standard library and pytest only.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # plugins/brand-creator
MONO = ROOT.parents[1]                               # the monorepo root: some tests read its workflow and marketplace.json
TPL = "templates/finish.sh.tpl"
FC = "tests/test_finish_chain.py::"
ST = "tests/test_finish_chain_steps.py::"

# group, id, file, the text, its replacement, the tests that must catch it (pytest node ids, relative to the plugin folder)
LEDGER: list[dict] = [
    # ---- templates/finish.sh.tpl: what the chain does at each step, and when it stops
    dict(group="finish-chain", id="failing-proof-stops", file=TPL,
         old='if [ "$rc" -eq 1 ]; then echo "finish.sh: the motion proof failed (see above); the chain goes on and check fails the report" >&2\n',
         new='if [ "$rc" -eq 1 ]; then echo "finish.sh: the motion proof failed (see above); the chain goes on and check fails the report" >&2; exit 1\n',
         tests=[ST + "test_a_motion_proof_that_fails_does_not_stop_the_chain"]),
    dict(group="finish-chain", id="not-verified-proof-stops", file=TPL,
         old='then echo "finish.sh: the motion proof is not verified (see above); the chain goes on and check says why" >&2\n',
         new='then echo "finish.sh: the motion proof is not verified (see above); the chain goes on and check says why" >&2; exit 3\n',
         tests=[ST + "test_a_motion_proof_that_is_not_verified_goes_on_because_it_wrote_its_report",
                ST + "test_the_report_is_found_by_the_path_shot_printed_even_when_it_is_not_named_as_the_chain_types_the_proof"]),
    dict(group="finish-chain", id="exit-3-without-report-goes-on", file=TPL,
         old='  [ -n "$f" ] && [ -f "$f" ]\n', new="  true\n",
         tests=[ST + "test_an_exit_3_that_wrote_no_report_stops_the_chain"]),
    dict(group="finish-chain", id="report-of-another-file-counts", file=TPL,
         old='  [ -n "$f" ] && [ -f "$f" ]\n', new='  [ -n "$f" ]\n',
         tests=[ST + "test_an_exit_3_that_wrote_no_report_stops_the_chain"]),
    dict(group="finish-chain", id="other-proof-exit-goes-on", file=TPL,
         old='check has no failing report to gate, so the chain stops here" >&2; exit "$rc"; fi\n        else',
         new='check has no failing report to gate, so the chain stops here" >&2; fi\n        else',
         tests=[ST + "test_a_motion_proof_that_stops_with_exit_2_or_3_stops_the_chain_with_that_exit_code"]),
    dict(group="finish-chain", id="proof-never-taken", file=TPL,
         old="        if [ -f motion/proof.json ]; then\n", new="        if false; then\n",
         tests=[ST + "test_a_brand_that_moves_has_its_approved_move_proved_before_the_stills_and_the_book_read_the_report",
                FC + "test_a_brand_that_moves_takes_fresh_stills_before_the_book_in_the_chain"]),
    dict(group="finish-chain", id="missing-proof-in-silence", file=TPL,
         old='          echo "finish.sh: motion/motion.json says the brand moves, but there is no motion/proof.json to prove the approved move:',
         new='          true || echo "finish.sh: motion/motion.json says the brand moves, but there is no motion/proof.json to prove the approved move:',
         tests=[ST + "test_a_brand_that_moves_with_no_proof_file_goes_on_and_says_which_file_is_missing"]),
    dict(group="finish-chain", id="nothing-moves-unsaid", file=TPL,
         old='      off) echo "nothing moves: $MOTION_TEXT" ;;\n', new="      off) : ;;\n",
         tests=[ST + "test_a_brand_that_does_not_move_says_so_and_takes_no_proof_and_no_stills"]),
    dict(group="finish-chain", id="undecided-unsaid", file=TPL,
         old='      *) echo "motion is not decided: run the motion round,', new='      *) true || echo "motion is not decided: run the motion round,',
         tests=[ST + "test_a_brand_with_no_decision_on_motion_goes_on_and_says_so"]),
    dict(group="finish-chain", id="motion-step-in-quick", file=TPL,
         old='  standard|full)\n    step "motion"\n', new='  standard|full|quick)\n    step "motion"\n',
         tests=[ST + "test_the_quick_chain_has_no_motion_step_and_takes_no_stills"]),
    dict(group="finish-chain", id="unreadable-motion-json-read-as-undecided", file=TPL,
         old='    MOTION_JSON="$("${BC[@]}" motion --json)"\n', new='    MOTION_JSON="$("${BC[@]}" motion --json || echo \'{"motion": "undecided"}\')"\n',
         tests=[ST + "test_a_motion_json_that_is_not_valid_stops_the_chain_at_the_motion_step_with_exit_2"]),
    dict(group="finish-chain", id="frames-that-cannot-step-stops", file=TPL,
         old='the book keeps the stills of the last run that worked, if any, and check says why" >&2\n',
         new='the book keeps the stills of the last run that worked, if any, and check says why" >&2; exit 1\n',
         tests=[ST + "test_a_page_frames_cannot_step_through_does_not_stop_the_chain"]),
    dict(group="finish-chain", id="other-frames-exit-goes-on", file=TPL,
         old='(the number of stills is FRAMES_ARGS in block 2)" >&2; exit "$rc"; fi\n', new='(the number of stills is FRAMES_ARGS in block 2)" >&2; fi\n',
         tests=[ST + "test_any_other_failure_of_frames_stops_the_chain_with_its_exit_code"]),
    dict(group="finish-chain", id="frames-args-ignored", file=TPL,
         old='        read -r -a FRAMES_OPTS <<< "$FRAMES_ARGS"\n', new='        read -r -a FRAMES_OPTS <<< "--count 25"\n',
         tests=[ST + "test_frames_args_in_block_2_sets_the_stills_without_editing_the_chain"]),
    dict(group="finish-chain", id="no-stills-before-the-book", file=TPL,
         old='; sys.exit(0 if ok else 1)\' 2>/dev/null; then\n', new='; sys.exit(1)\' 2>/dev/null; then\n',
         tests=[ST + "test_a_brand_that_moves_has_its_approved_move_proved_before_the_stills_and_the_book_read_the_report",
                FC + "test_a_brand_that_moves_takes_fresh_stills_before_the_book_in_the_chain"]),
    dict(group="finish-chain", id="stills-without-a-page-case", file=TPL,
         old=' and any(c.get("type") == "page" for c in json.load(open("motion/proof.json")).get("cases", []))', new="",
         tests=[ST + "test_stills_are_taken_only_of_a_proof_with_a_page_case",
                FC + "test_the_chain_takes_stills_only_for_a_brand_that_moves_and_has_a_page_case_to_take_them_of"]),
    dict(group="finish-chain", id="press-kit-claims-a-book", file=TPL,
         old='    EMIT_ARGS=(); [ "$HAVE_BOOK" = yes ] || EMIT_ARGS+=(--no-book)\n', new="    EMIT_ARGS=()\n",
         tests=[ST + "test_without_chapters_the_book_is_skipped_loudly_and_the_press_kit_is_told_it_has_no_book"]),
    dict(group="finish-chain", id="print-and-posts-in-quick", file=TPL,
         old='  *) [ -z "$PRINT_REGION" ] && [ -z "$POST_FACTS" ] ||', new="  *) true ||",
         tests=[ST + "test_a_value_for_a_step_the_tier_does_not_allow_stops_the_chain_before_any_step"]),
    dict(group="finish-chain", id="press-kit-in-quick", file=TPL,
         old='case "$TIER" in\n  standard|full)\n    EMIT_ARGS=(); [ "$HAVE_BOOK" = yes ]', new='case "$TIER" in\n  standard|full|quick)\n    EMIT_ARGS=(); [ "$HAVE_BOOK" = yes ]',
         tests=[ST + "test_the_quick_chain_keeps_its_shape_profiles_but_no_press_kit_no_print"]),
    dict(group="finish-chain", id="multi-word-option-split", file=TPL,
         old='  "${BC[@]}" emit "$t" ${EMIT_ARGS[@]+"${EMIT_ARGS[@]}"}\n', new='  "${BC[@]}" emit "$t" ${EMIT_ARGS[@]+${EMIT_ARGS[@]}}\n',
         tests=[ST + "test_print_posts_and_a_tagline_reach_each_emitter_as_whole_arguments",
                FC + "test_the_standard_chain_runs_profiles_print_posts_book_and_press_kit_in_order_through_to_check"]),
    dict(group="finish-chain", id="print-never-emitted", file=TPL,
         old='  standard|full) [ -z "$PRINT_REGION" ] || TARGETS+=(print) ;;\n', new="  standard|full) : ;;\n",
         tests=[ST + "test_print_posts_and_a_tagline_reach_each_emitter_as_whole_arguments",
                FC + "test_the_standard_chain_runs_profiles_print_posts_book_and_press_kit_in_order_through_to_check"]),
    dict(group="finish-chain", id="frames-reason-hidden", file=TPL,
         old='rc=0; "${BC[@]}" frames motion/proof.json "${FRAMES_OPTS[@]}" || rc=$?\n', new='rc=0; "${BC[@]}" frames motion/proof.json "${FRAMES_OPTS[@]}" >/dev/null 2>&1 || rc=$?\n',
         tests=[ST + "test_a_page_frames_cannot_step_through_does_not_stop_the_chain"]),
    dict(group="finish-chain", id="book-reason-hidden", file=TPL,
         old='  step "book";     "${BC[@]}" book\n', new='  step "book";     "${BC[@]}" book 2>/dev/null\n',
         tests=[ST + "test_a_book_that_refuses_stops_the_chain_with_its_exit_code_before_its_pdf"]),
    dict(group="finish-chain", id="proof-output-hidden", file=TPL,
         old="          [ -z \"$SHOT_OUT\" ] || printf '%s\\n' \"$SHOT_OUT\"\n", new="          true\n",
         tests=[ST + "test_a_motion_proof_that_is_not_verified_goes_on_because_it_wrote_its_report"]),
    dict(group="finish-chain", id="print-not-opt-in", file=TPL,
         old='  standard|full) [ -z "$PRINT_REGION" ] || TARGETS+=(print) ;;\n', new="  standard|full) TARGETS+=(print) ;;\n",
         tests=[ST + "test_print_is_emitted_only_when_the_owner_opted_in_with_a_region"]),
    # ---- what the chain relies on from the CLI: a report written by a node tool is printed as "report: <path>" (finish.sh's wrote_report reads it)
    dict(group="finish-chain", id="report-path-not-printed", file="scripts/lib/_common.mjs",
         old="    console.log(`report: ${out}`);\n", new="",
         tests=[FC + "test_a_proof_that_is_not_verified_prints_the_path_of_the_report_it_wrote_which_the_chain_reads"]),
    # ---- the stills the book replays: a failed `frames` run keeps those of the last run that worked, and the book still replays them (the chain says so)
    dict(group="motion-stills", id="failed-frames-deletes-earlier-stills", file="scripts/render.mjs",
         old='  const fail = (detail, extra = {}) => report.add(rid, "fail", label, { detail, ...extra });\n',
         new='  const fail = (detail, extra = {}) => (fs.rmSync(path.join(project, dir), { recursive: true, force: true }), report.add(rid, "fail", label, { detail, ...extra }));\n',
         tests=["tests/test_book_motion.py::test_a_frames_run_that_fails_keeps_the_stills_of_the_last_run_that_worked_and_the_book_replays_them"]),
    dict(group="motion-stills", id="book-leaves-out-replay-of-failed-run", file="scripts/booklib/bookdata.py",
         old='        return f"{case} is no longer a page case of {proof}: move {at}/ to removed-<date>/ (its replay is left out)"\n    return None\n',
         new=('        return f"{case} is no longer a page case of {proof}: move {at}/ to removed-<date>/ (its replay is left out)"\n'
              '    try:\n'
              '        rep = json.loads((project / "assets" / "_checks" / f"{frames_report_tool(proof)}.json").read_text(encoding="utf-8"))\n'
              '    except (OSError, ValueError):\n'
              '        rep = {}\n'
              '    if any(isinstance(r, dict) and r.get("id") == f"frames:{case}" and r.get("status") == "fail" for r in rep.get("results", [])):\n'
              '        return f"the last `frames` run for {proof} did not pass for {case}, so its stills may be older than the page; its replay is left out: run `{frames_command(doc, case)}`"\n'
              '    return None\n'),
         tests=["tests/test_book_motion.py::test_a_frames_run_that_fails_keeps_the_stills_of_the_last_run_that_worked_and_the_book_replays_them"]),
]

IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "node_modules", "results")


def copy_plugin(into: Path) -> Path:
    """A copy of the plugin in the monorepo layout its tests expect (plugins/brand-creator, .github/workflows, .claude-plugin)."""
    dst = into / "plugins" / "brand-creator"
    shutil.copytree(ROOT, dst, symlinks=True, ignore=IGNORE)
    for rel in (".github/workflows/brand-creator.yml", ".claude-plugin/marketplace.json"):
        if (MONO / rel).is_file():
            (into / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(MONO / rel, into / rel)
    return dst


def run_tests(plugin: Path, tests: list[str], workers: int = 0) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider", "-n", str(workers), "--dist", "worksteal"], cwd=plugin, capture_output=True, text=True)


def replay(entry: dict) -> tuple[str, str]:
    """-> (CAUGHT | MISSED | STALE, what happened)."""
    with tempfile.TemporaryDirectory(prefix="ledger-") as tmp:
        plugin = copy_plugin(Path(tmp))
        f = plugin / entry["file"]
        text = f.read_text(encoding="utf-8")
        if text.count(entry["old"]) != 1:
            return "STALE", f"its text is {text.count(entry['old'])} times in {entry['file']}, not once: update the entry"
        f.write_text(text.replace(entry["old"], entry["new"]), encoding="utf-8")
        r = run_tests(plugin, entry["tests"])
        tail = (r.stdout.strip().splitlines() or [""])[-1]
        return ("CAUGHT" if r.returncode not in (0, 5) else "MISSED"), tail


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--group", help="replay only this group")
    ap.add_argument("-k", dest="words", help="replay only entries whose id holds these words")
    ap.add_argument("--jobs", type=int, default=1, help="entries replayed side by side (each on its own copy)")
    ap.add_argument("--list", action="store_true", help="list the entries and their tests, run nothing")
    a = ap.parse_args()
    chosen = [e for e in LEDGER if (not a.group or e["group"] == a.group) and (not a.words or a.words in e["id"])]
    if not chosen:
        print("no ledger entry matches", file=sys.stderr)
        return 2
    if a.list:
        for e in chosen:
            print(f"{e['group']}/{e['id']}: {e['file']} -> {', '.join(t.split('::')[-1] for t in e['tests'])}")
        return 0
    tests = sorted({t for e in chosen for t in e["tests"]})
    with tempfile.TemporaryDirectory(prefix="ledger-control-") as tmp:   # the positive control: every test passes on the unchanged plugin
        r = run_tests(copy_plugin(Path(tmp)), tests, workers=4)
        if r.returncode != 0:
            print(f"CONTROL FAILED: the tests fail without any break, so a failure would prove nothing:\n{r.stdout[-3000:]}", file=sys.stderr)
            return 1
        print(f"control: {len(tests)} test(s) pass on the unchanged plugin")
    with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as pool:
        results = list(pool.map(replay, chosen))
    for e, (verdict, how) in zip(chosen, results):
        print(f"{verdict:7} {e['group']}/{e['id']}  ({how})", flush=True)
    stale = [e for e, (v, _) in zip(chosen, results) if v == "STALE"]
    missed = [e for e, (v, _) in zip(chosen, results) if v == "MISSED"]
    print(f"{len(chosen) - len(stale) - len(missed)} of {len(chosen)} breaks caught" + (f"; {len(missed)} missed" if missed else "") + (f"; {len(stale)} stale" if stale else ""))
    return 2 if stale else (1 if missed else 0)


if __name__ == "__main__":
    sys.exit(main())

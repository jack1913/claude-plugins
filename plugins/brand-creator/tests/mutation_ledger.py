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
PR = "tests/test_emit_profiles.py::"
BM = "tests/test_book_motion.py::"
BL = "scripts/booklib/booklint.py"

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
    # ---- the brand book's motion chapter and the book-lint rows that guard it (tests/test_book_motion.py): a broken rule of booklint, or of the replay the book builds, is caught by
    # the test that is about it, whatever way the test runs the lint (the command, or the same booklint.lint call in its own process)
    # motion:reduced: nothing moves under prefers-reduced-motion (the flipbook, the reduced still, the controls; a rule that starts motion and the stop that switches it off)
    dict(group="book-motion", id="reduced-flipbook-shown-is-not-flagged", file=BL,
         old='        if (shown or "inline").strip().lower() != "none":\n', new="        if False:\n",
         tests=[BM + "test_motion_reduced_fails_a_demo_that_still_shows_its_flipbook_or_hides_its_still_or_leaves_its_controls"]),
    dict(group="book-motion", id="reduced-still-hidden-is-not-flagged", file=BL,
         old='    elif (_cascade(rules, d["reduced"], "display", mode="reduce") or "inline").strip().lower() == "none":\n', new="    elif False:\n",
         tests=[BM + "test_motion_reduced_fails_a_demo_that_still_shows_its_flipbook_or_hides_its_still_or_leaves_its_controls"]),
    dict(group="book-motion", id="reduced-controls-shown-are-not-flagged", file=BL,
         old='        if e is not None and (_cascade(rules, e, "display", mode="reduce") or "inline").strip().lower() != "none":\n', new="        if False:\n",
         tests=[BM + "test_motion_reduced_fails_a_demo_that_still_shows_its_flipbook_or_hides_its_still_or_leaves_its_controls"]),
    dict(group="book-motion", id="reduced-flipbook-animation-is-not-flagged", file=BL,
         old='        if anim and any(n.strip().lower() != "none" for n in anim.split(",")):\n', new="        if False:\n",
         tests=[BM + "test_motion_reduced_fails_a_demo_whose_flipbook_keeps_an_animation_under_reduced_motion"]),
    dict(group="book-motion", id="animation-start-is-not-counted", file=BL,
         old='    if live:\n        out.append(("animation", "the animation "', new='    if False:\n        out.append(("animation", "the animation "',
         tests=[BM + "test_motion_reduced_fails_a_rule_that_starts_an_animation_that_nothing_switches_off_under_reduced_motion"]),
    dict(group="book-motion", id="transition-start-is-not-counted", file=BL,
         old='    if dur and any(_ms(w) for w in dur[1].split(",")):\n', new="    if False:\n",
         tests=[BM + "test_motion_reduced_fails_a_transition_with_a_duration_that_nothing_switches_off_and_lets_one_of_zero_alone"]),
    dict(group="book-motion", id="star-stop-weighs-like-a-class-stop", file=BL,
         old="                    weight = (imp, sel[1] if x == want else (0, 0, 0), seq)\n", new="                    weight = (imp, sel[1], seq)\n",
         tests=[BM + "test_motion_reduced_takes_a_star_rule_only_with_important_a_later_rule_only_and_leaves_alone_what_never_applies_under_reduced_motion"]),
    dict(group="book-motion", id="plain-stop-beats-an-important-start", file=BL,
         old="                    weight = (imp, sel[1] if x == want else (0, 0, 0), seq)\n", new="                    weight = (True, sel[1] if x == want else (0, 0, 0), seq)\n",
         tests=[BM + "test_motion_reduced_does_not_take_a_plain_none_for_a_start_marked_important"]),
    dict(group="book-motion", id="stop-is-never-outweighed", file=BL,
         old="(d[2], y[1], d[3]) > weight and", new="(d[2], y[1], d[3]) > (True, (9, 9, 9), 10 ** 9) and",
         tests=[BM + "test_motion_reduced_weighs_a_stop_against_the_declaration_that_wins_on_each_longhand_and_the_other_rules_that_can_select_the_element"]),
    dict(group="book-motion", id="stop-in-a-layer-counts", file=BL,
         old="and not _unevaluated(q.media) and not q.nested]", new="and not q.nested]",
         tests=[BM + "test_a_stop_inside_layer_scope_container_or_supports_is_not_counted_and_the_row_names_it"]),
    dict(group="book-motion", id="start-in-a-layer-is-not-named", file=BL,
         old="                if _unevaluated(r.media) or r.nested:   # a start where the cascade does not look: weighed as if it applies, and named\n", new="                if False:\n",
         tests=[BM + "test_a_start_where_the_cascade_does_not_look_is_weighed_as_if_it_applies_and_named"]),
    # the cascade the rows read: a rule in @layer, @scope, @container or @supports, or one with nested rules, is not applied and is named; an inline style outweighs a rule of its importance
    dict(group="book-motion", id="rule-in-a-layer-is-applied", file=BL,
         old="        if not _media_holds(r.media, mode) or _unevaluated(r.media) or r.nested:\n", new="        if not _media_holds(r.media, mode) or r.nested:\n",
         tests=[BM + "test_a_rule_inside_layer_scope_container_or_supports_is_not_applied_and_the_rows_that_read_what_it_sets_name_it"]),
    dict(group="book-motion", id="rule-with-nested-rules-is-applied", file=BL,
         old="        if not _media_holds(r.media, mode) or _unevaluated(r.media) or r.nested:\n", new="        if not _media_holds(r.media, mode) or _unevaluated(r.media):\n",
         tests=[BM + "test_a_block_that_holds_nested_rules_is_named_in_the_rows_it_could_affect_and_an_inline_important_with_no_space_is_read"]),
    dict(group="book-motion", id="unread-rules-leave-a-pass", file=BL,
         old='        if row_["status"] == "pass":\n            row_["status"] = "warn"\n', new="        pass\n",
         tests=[BM + "test_a_selector_the_lint_cannot_read_is_named_in_the_rows_that_read_what_it_sets_and_the_row_is_a_warning_not_a_pass"]),
    dict(group="book-motion", id="statement-at-rule-swallows-the-rule-after-it", file=BL,
         old='        end = _at_statement(css, k) if css.startswith("@", k) else -1\n', new="        end = -1\n",
         tests=[BM + "test_the_rule_after_a_statement_at_rule_is_read_and_a_layer_statement_is_named_in_the_motion_rows"]),
    dict(group="book-motion", id="inline-style-does-not-outweigh-a-rule", file=BL,
         old="        if p == prop and (key is None or (imp, 1, (0, 0, 0), n) > key):\n", new="        if p == prop and (key is None or (imp, 0, (0, 0, 0), n) > key):\n",
         tests=[BM + "test_a_style_attribute_is_weighed_in_the_cascade_over_a_rule_of_its_importance_and_below_an_important_one"]),
    dict(group="book-motion", id="ancestors-of-a-box-are-not-walked", file=BL,
         old="        n = n.parent\n    return None\n", new="        n = None\n    return None\n",
         tests=[BM + "test_motion_replay_walks_the_ancestors_of_the_boxes_and_the_labels_and_wants_the_labels_and_the_flipbook_shown_on_a_screen"]),
    # motion:replay: the checkboxes (an id, a label with text, the keyboard's reach), the animation each state of them gives the flipbook, its keyframes, and the picture's <source>
    dict(group="book-motion", id="empty-label-is-not-flagged", file=BL,
         old="        elif not any(htmlscan.visible_text(text[x.start:x.end], with_attributes=False).strip() for x in mine):\n", new="        elif False:\n",
         tests=[BM + "test_motion_replay_fails_a_checkbox_without_an_id_a_label_or_label_text"]),
    dict(group="book-motion", id="negative-tabindex-is-not-flagged", file=BL,
         old='    if el.attrs.get("tabindex", "0").strip().startswith("-"):\n', new="    if False:\n",
         tests=[BM + "test_motion_replay_fails_a_checkbox_the_keyboard_cannot_reach_outside_the_reduced_motion_and_print_media"]),
    dict(group="book-motion", id="replay-box-need-not-change-the-animation", file=BL,
         old="        if got[a] == got[b]:\n", new="        if False:\n",
         tests=[BM + "test_motion_replay_fails_when_a_checkbox_does_not_start_the_flipbook_again_or_the_slow_one_is_not_four_times_as_long"]),
    dict(group="book-motion", id="different-keyframes-are-not-flagged", file=BL,
         old="    if len({repr(kfs[n]) for n in named}) > 1:\n", new="    if False:\n",
         tests=[BM + "test_motion_replay_fails_keyframes_that_are_missing_differ_or_a_flipbook_that_repeats_forever"]),
    dict(group="book-motion", id="no-flipbook-is-not-flagged-by-motion-replay", file=BL,
         old='        return out + [f"{case}: no flipbook (an element with the class motion-flip)"]\n', new="        return out\n",
         tests=[BM + "test_motion_replay_fails_a_demo_with_no_flipbook_and_one_whose_rules_do_not_reach_it"]),
    dict(group="book-motion", id="timing-function-is-not-read", file=BL,
         old='        if re.sub(r"\\s+", "", (timing or "ease").lower()) not in ("step-end", "steps(1,end)", "steps(1,jump-end)", "steps(1)"):\n', new="        if False:\n",
         tests=[BM + "test_motion_replay_reads_the_timing_function_the_iteration_count_and_the_keyframes_against_frames_json"]),
    dict(group="book-motion", id="fill-mode-is-not-read", file=BL,
         old='        if fill != "both":\n', new="        if False:\n",
         tests=[BM + "test_motion_replay_fails_a_flipbook_whose_direction_play_state_fill_mode_or_delay_would_not_play_the_stills_once_in_order"]),
    dict(group="book-motion", id="important-object-position-is-not-flagged", file=BL,
         old='        if imp:\n            out.append(f"{case}: the flipbook has object-position:', new='        if False:\n            out.append(f"{case}: the flipbook has object-position:',
         tests=[BM + "test_motion_replay_fails_an_important_object_position_and_motion_stills_reads_the_limits_of_the_size_like_the_size"]),
    dict(group="book-motion", id="source-a-browser-may-skip-is-read", file=BL,
         old='    if source is not None and ("media" in source.attrs or "type" in source.attrs and source.attrs["type"].strip().lower() != "image/png"):\n', new="    if False:\n",
         tests=[BM + "test_a_source_a_browser_may_skip_keeps_the_strip_from_being_read_and_fails_motion_replay_and_motion_stills_naming_it"]),
    dict(group="book-motion", id="keyframes-with-no-name-are-not-said", file=BL,
         old='+ (["a @keyframes with no name"] if "" in kfs else [])\n', new="+ []\n",
         tests=[BM + "test_a_keyframes_with_no_name_is_said_in_motion_replay_and_does_not_crash_the_lint"]),
    dict(group="book-motion", id="keyframes-with-no-name-crash-the-lint", file=BL,
         old='frames.setdefault(kf[len("@keyframes"):].strip(), []).append(', new="frames.setdefault(kf.split()[1], []).append(",
         tests=[BM + "test_a_keyframes_with_no_name_is_said_in_motion_replay_and_does_not_crash_the_lint"]),
    dict(group="book-motion", id="no-demo-is-a-pass-for-motion-replay", file=BL,
         old='    rep = row("motion:replay", "info", ', new='    rep = row("motion:replay", "pass", ',
         tests=[BM + "test_the_built_replay_passes_the_three_motion_rows_and_a_book_without_one_gets_info_rows"]),
    # motion:stills: the book's pictures are the files frames.json lists, its length and count are frames.json's, the flipbook is one still wide; and a book is asked for the stills it can show
    dict(group="book-motion", id="data-frames-is-not-compared", file=BL,
         old='    if fig.attrs.get("data-frames") != str(len(doc["frames"])):\n', new="    if False:\n",
         tests=[BM + "test_motion_stills_fails_a_picture_that_is_not_the_file_in_motion_frames_a_length_or_count_that_differs_and_a_size_that_does_not_fit"]),
    dict(group="book-motion", id="older-picture-is-not-told-from-the-file", file=BL,
         old="        elif got != want_file.read_bytes():\n", new="        elif False:\n",
         tests=[BM + "test_motion_stills_fails_a_book_built_before_the_stills_were_taken_again_and_passes_once_it_is_rebuilt"]),
    dict(group="book-motion", id="edited-strip-is-not-told-by-its-sha256", file=BL,
         old='        elif hashlib.sha256(got).hexdigest() != doc[key]["sha256"]:\n', new="        elif False:\n",
         tests=[BM + "test_motion_stills_fails_a_picture_whose_sha256_is_not_the_one_frames_json_lists_and_the_build_refuses_it"]),
    dict(group="book-motion", id="stills-a-generated-book-lacks-only-warn", file=BL,
         old='    (warns if view.get("mark_source") == "authored-vector" else fails).extend(missing)\n', new="    warns.extend(missing)\n",
         tests=[BM + "test_a_book_built_before_the_stills_exist_fails_motion_stills_once_they_appear_and_check_notices_them"]),
    dict(group="book-motion", id="stills-of-a-motion-that-is-off-are-asked-for", file="scripts/booklib/bookdata.py",
         old='    return "motion" in chapters_for(project, view) and not motion_is_off(project)\n', new='    return "motion" in chapters_for(project, view)\n',
         tests=[BM + "test_stills_the_build_left_out_and_said_so_and_those_of_a_motion_that_is_off_are_no_failure_of_the_book"]),
    dict(group="book-motion", id="a-quick-book-is-asked-for-a-replay", file="scripts/booklib/bookdata.py",
         old='    return "motion" in chapters_for(project, view) and not motion_is_off(project)\n', new="    return not motion_is_off(project)\n",
         tests=[BM + "test_a_quick_book_has_no_motion_chapter_and_is_not_asked_for_a_replay"]),
    dict(group="book-motion", id="the-reports-leave-out-the-pictures-of-the-stills", file="scripts/booklib/bookdata.py",
         old='            out += [project / doc["strip"]["file"], project / doc["reduced"]["file"], project / doc["proof"]]\n', new='            out += [project / doc["proof"]]\n',
         tests=[BM + "test_the_reports_list_the_spec_and_the_stills_as_inputs_so_check_notices_new_ones"]),
    # self:durations: a duration or delay is a motion token, or 0, or (in a rule that reaches one replay and nothing else) that replay's length or four times it
    dict(group="book-motion", id="any-duration-passes-self-durations", file=BL,
         old="                if ms != 0 and not any(abs(ms - a) < 0.5 for a in allowed + own(where)):\n", new="                if False:\n",
         tests=[BM + "test_self_durations_lets_a_replay_use_its_own_length_and_four_times_it_and_nothing_else_may"]),
    dict(group="book-motion", id="two-replays-of-one-length-share-the-allowance", file=BL,
         old="            n = lengths[next(iter(figs))][0] if ok and len(figs) == 1 else None\n", new="            n = lengths[next(iter(figs))][0] if ok else None\n",
         tests=[BM + "test_self_durations_gives_the_replay_length_only_to_a_rule_that_reaches_one_demo_and_nothing_else"]),
    # what the book builds, as the rows and the reports read it: the replay's markup and names, its ids, the case folders, the proof tables
    dict(group="book-motion", id="replay-reduced-still-says-nothing-of-reduced-motion", file="scripts/booklib/bookgen.py",
         old='alt="{name}: {t("the still shown when motion is reduced")}"', new='alt="{name}"',
         tests=[BM + "test_each_frames_json_of_a_gated_proof_becomes_one_replay_with_the_markup_of_the_contract"]),
    dict(group="book-motion", id="curve-drawing-carries-text", file="scripts/booklib/bookgen.py",
         old='x2="{x_(1)}" y2="{y_(1)}"/></g>\'\n', new='x2="{x_(1)}" y2="{y_(1)}"/></g><text x="0" y="8">1</text>\'\n',
         tests=[BM + "test_each_curve_is_drawn_as_an_svg_with_a_role_an_aria_label_and_no_text"]),
    dict(group="book-motion", id="two-cases-of-one-id-are-both-replayed", file="scripts/booklib/bookgen.py",
         old='                if d and any(o["slug"] == d["slug"] for o in self._demos):\n', new="                if False:\n",
         tests=[BM + "test_a_missing_strip_leaves_the_replay_out_and_two_cases_that_make_one_id_keep_the_first"]),
    dict(group="book-motion", id="two-languages-share-the-replay-ids", file="scripts/booklib/bookgen.py",
         old='        suffix = f"-{lang}" if len(self.langs) > 1 else ""', new='        suffix = ""',
         tests=[BM + "test_with_two_languages_every_chapter_has_its_own_replay_with_its_own_ids_and_the_lint_passes"]),
    dict(group="book-motion", id="case-folder-keeps-a-leading-dot", file="scripts/booklib/bookdata.py",
         old='return re.sub(r"[^A-Za-z0-9._-]+", "-", str(name)).lstrip(".-")', new='return re.sub(r"[^A-Za-z0-9._-]+", "-", str(name)).lstrip("-")',
         tests=[BM + "test_a_case_folder_and_a_report_are_named_as_frames_names_them_and_every_real_replay_lints"]),
    dict(group="book-motion", id="a-single-replay-is-named-after-its-case", file="scripts/booklib/bookgen.py",
         old='        return f"{base} ({self._demos.index(d) + 1})" if len(self._demos) > 1 else base\n', new='        return f"{base} ({self._demos.index(d) + 1})" if len(self._demos) > 1 else d["case"]\n',
         tests=[BM + "test_the_text_of_a_replay_is_named_after_the_signature_move_or_the_mark_in_motion_and_never_after_the_case"]),
    dict(group="book-motion", id="a-motion-report-is-named-after-its-proof-file", file="scripts/booklib/bookgen.py",
         old='(f" {n}" if len(reps) > 1 else "") for n, (rf, _proof) in enumerate(reps, 1)}', new='(f" {_proof}" if len(reps) > 1 else "") for n, (rf, _proof) in enumerate(reps, 1)}',
         tests=[BM + "test_a_proof_file_a_report_or_a_state_with_a_working_name_never_reaches_the_text_of_the_book_only_its_data_attributes"]),
    # the lint as the command runs it, and what the build writes of it: exit codes, the self-consistency rows, a hand-authored book
    dict(group="book-motion", id="book-lint-command-records-another-state", file="scripts/book_lint.py",
         old="state_view_sha=bookdata.view_sha(view, facts),", new='state_view_sha="0" * 64,',
         tests=["tests/test_book.py::test_book_lint_passes_the_built_book_and_check_gates_it"]),
    dict(group="book-motion", id="book-lint-command-ignores-the-self-consistency-flag", file="scripts/book_lint.py",
         old="self_consistency=a.self_consistency, allow_variants=a.allow_variants)", new="self_consistency=False, allow_variants=a.allow_variants)",
         tests=[BM + "test_the_built_replay_passes_the_three_motion_rows_and_a_book_without_one_gets_info_rows"]),
    dict(group="book-motion", id="book-lint-command-exits-0-on-a-failing-row", file="scripts/book_lint.py",
         old="    return rep.finish(quiet_pass=True)\n", new="    rep.finish(quiet_pass=True)\n    return 0\n",
         tests=[BM + "test_a_book_built_before_the_stills_exist_fails_motion_stills_once_they_appear_and_check_notices_them"]),
    dict(group="book-motion", id="book-lint-command-reports-no-rows", file="scripts/book_lint.py",
         old="    rep = booklint.write_report(project, f, results, view=view,", new="    rep = booklint.write_report(project, f, [], view=view,",
         tests=[BM + "test_the_built_replay_passes_the_three_motion_rows_and_a_book_without_one_gets_info_rows"]),
    dict(group="book-motion", id="book-lint-command-leaves-the-stills-out-of-its-report", file="scripts/book_lint.py",
         old="    rep = booklint.write_report(project, f, results, view=view,", new='    rep = booklint.write_report(project, f, results, view={**view, "tier": "quick"},',
         tests=[BM + "test_the_reports_list_the_spec_and_the_stills_as_inputs_so_check_notices_new_ones"]),
    dict(group="book-motion", id="lint-skips-the-motion-rows", file=BL,
         old="        res += _motion_rules(project, text, view)\n", new="        pass\n",
         tests=[BM + "test_the_built_replay_passes_the_three_motion_rows_and_a_book_without_one_gets_info_rows"]),
    dict(group="book-motion", id="lint-skips-the-self-rules", file=BL,
         old="            res += _self_rules(text, cfg, tokens_doc)\n", new="            pass\n",
         tests=[BM + "test_self_durations_lets_a_replay_use_its_own_length_and_four_times_it_and_nothing_else_may"]),
    dict(group="book-motion", id="book-builds-a-hand-authored-book", file="scripts/book.py",
         old='    if view["mark_source"] == "authored-vector":\n', new="    if False:\n",
         tests=[BM + "test_a_hand_authored_book_with_a_replay_is_read_by_the_same_rows"]),
    # ---- emit profiles (tests/test_emit_profiles.py): what its tests guard, so that merging them never quietly drops a check
    # a second run: it says it wrote nothing; no file under assets/ changes by a byte; no shipped PNG carries a date
    dict(group="profiles", id="rerun-reports-files-it-did-not-change", file="scripts/emitters/manifest.py",
         old="        did = write_bytes_if_changed(target, data)\n", new="        did = write_bytes_if_changed(target, data) or True\n",
         tests=[PR + "test_proof_images_draw_the_safe_areas_are_never_shipped_or_in_the_manifest_and_a_second_run_writes_nothing"]),
    dict(group="profiles", id="rerun-changes-the-manifest", file="scripts/emitters/profiles.py",
         old='f"profile photo, {n} px square, opaque; shown in a circle:',
         new='f"profile photo, {n} px square, opaque, run {__import__(\'os\').getpid()}; shown in a circle:',
         tests=[PR + "test_proof_images_draw_the_safe_areas_are_never_shipped_or_in_the_manifest_and_a_second_run_writes_nothing"]),
    dict(group="profiles", id="shipped-png-carries-a-date-chunk", file="scripts/lib/px_lib.py",
         old='struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))',
         new='struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0)) + chunk(b"tIME", bytes(7))',
         tests=[PR + "test_proof_images_draw_the_safe_areas_are_never_shipped_or_in_the_manifest_and_a_second_run_writes_nothing"]),
    # a template that types {{name}} without {{lettering}} keeps its warning (the template that draws its own name is the info row)
    dict(group="profiles", id="typed-name-template-stops-warning", file="scripts/emitters/_emit.py",
         old=r'    return slot, not slot and "{{name}}" not in re.sub(r"<title\b.*?</title\s*>", "", plain, flags=re.S | re.I)' + "\n",
         new="    return slot, not slot\n",
         tests=[PR + "test_a_name_given_is_set_as_text_and_a_template_from_before_the_lettering_still_works"]),
    # a size the spec row drops: its file is moved aside (never deleted) and its manifest row goes
    dict(group="profiles", id="dropped-size-is-deleted-not-moved", file="scripts/emitters/manifest.py",
         old="                shutil.move(str(src), str(dest))\n", new="                src.unlink()\n",
         tests=[PR + "test_a_size_the_spec_row_drops_is_retired_moved_never_deleted"]),
    dict(group="profiles", id="dropped-size-keeps-its-manifest-row", file="scripts/emitters/manifest.py",
         old="            del self.artefacts[p]\n", new="            pass\n",
         tests=[PR + "test_a_size_the_spec_row_drops_is_retired_moved_never_deleted"]),
    # the Full tier is accepted (the one run of it is in the accent-line test of tests/test_marks.py)
    dict(group="profiles", id="full-tier-refused", file="scripts/emitters/tierb.py",
         old='TIERS = {"profiles": ("quick", "standard", "full")}', new='TIERS = {"profiles": ("quick", "standard")}',
         tests=["tests/test_marks.py::test_the_accent_line_has_square_ends_on_pixel_art_and_keeps_its_round_ends_on_vector_art"]),
    # a mark outside the circle and a name outside the safe rectangle, one run with both: each fails its own row, is counted in the message, and blocks every file
    dict(group="profiles", id="avatar-gate-never-fails", file="scripts/emitters/profiles.py",
         old="        ok = far <= radius + INK_TOLERANCE_PX\n", new="        ok = True\n",
         tests=[PR + "test_a_mark_outside_the_circle_and_a_name_outside_the_safe_rectangle_each_stop_the_emit_before_anything_is_written_and_the_proof_shows_why"]),
    dict(group="profiles", id="banner-gate-never-fails", file="scripts/emitters/profiles.py",
         old=('        inside = bb is not None and bb[0] >= s["x"] - INK_TOLERANCE_PX and bb[1] >= s["y"] - INK_TOLERANCE_PX \\\n'
              '            and bb[2] <= s["x"] + sw + INK_TOLERANCE_PX and bb[3] <= s["y"] + sh + INK_TOLERANCE_PX\n'),
         new="        inside = True\n",
         tests=[PR + "test_a_mark_outside_the_circle_and_a_name_outside_the_safe_rectangle_each_stop_the_emit_before_anything_is_written_and_the_proof_shows_why"]),
    dict(group="profiles", id="failed-avatar-is-not-counted", file="scripts/emitters/profiles.py",
         old='            failures.append(f"avatar-{n}: ink {far:.0f} px from the centre, limit {radius:.0f}")\n', new="            pass\n",
         tests=[PR + "test_a_mark_outside_the_circle_and_a_name_outside_the_safe_rectangle_each_stop_the_emit_before_anything_is_written_and_the_proof_shows_why"]),
    dict(group="profiles", id="failed-banner-is-not-counted", file="scripts/emitters/profiles.py",
         old='            failures.append(f"{fname}: ink box {bb} is not inside the safe rectangle")\n', new="            pass\n",
         tests=[PR + "test_a_mark_outside_the_circle_and_a_name_outside_the_safe_rectangle_each_stop_the_emit_before_anything_is_written_and_the_proof_shows_why"]),
    dict(group="profiles", id="failed-gate-writes-no-avatar-proof", file="scripts/emitters/profiles.py",
         old='        proofs[f"avatar-{n}"] = e.png(head + marks + "</svg>" + tail, n, n, bg=ground)\n', new="",
         tests=[PR + "test_a_mark_outside_the_circle_and_a_name_outside_the_safe_rectangle_each_stop_the_emit_before_anything_is_written_and_the_proof_shows_why"]),
    dict(group="profiles", id="failed-gate-writes-no-banner-proof", file="scripts/emitters/profiles.py",
         old='        proofs[fname] = pngs["-proof"]\n', new="",
         tests=[PR + "test_a_mark_outside_the_circle_and_a_name_outside_the_safe_rectangle_each_stop_the_emit_before_anything_is_written_and_the_proof_shows_why"]),
    dict(group="profiles", id="failed-gate-still-ships", file="scripts/emitters/profiles.py",
         old=('    if failures:\n'
              '        fail(EXIT_FAIL, "an image does not fit its safe area: "'),
         new=('    if failures:\n'
              '        for rel_name, data, row_id, slot, size_px, d, note, extra in shipped:\n'
              '            e.slot(f"{out}/{rel_name}", data, [row_id], slot=slot, size_px=size_px, drawing=d, resampled_by="OURS" if slot == "profile-avatar" else "PAGE", note=note, **extra)\n'
              '        e.mf.save()\n'
              '        fail(EXIT_FAIL, "an image does not fit its safe area: "'),
         tests=[PR + "test_a_mark_outside_the_circle_and_a_name_outside_the_safe_rectangle_each_stop_the_emit_before_anything_is_written_and_the_proof_shows_why"]),
    # an explicit --content-fraction is used as given: the control run of that test (a mark that fits) passes
    dict(group="profiles", id="content-fraction-is-not-used-as-given", file="scripts/emitters/profiles.py",
         old="    content = fit_share(limit_top, far_full, AVATAR_MAX_CONTENT) if auto else a.content_fraction\n",
         new="    content = fit_share(limit_top, far_full, AVATAR_MAX_CONTENT) if auto else a.content_fraction * 2\n",
         tests=[PR + "test_a_mark_outside_the_circle_and_a_name_outside_the_safe_rectangle_each_stop_the_emit_before_anything_is_written_and_the_proof_shows_why"]),
    # the lettering of a banner: the kind comes from the file name wherever the word stands in it, and the mark stays next to a wordmark
    dict(group="profiles", id="kind-read-only-from-the-start-of-the-file-name", file="scripts/emitters/_emit.py",
         old="    says = [k for k in LETTERING_KINDS if k in Path(rel).stem.lower()]\n",
         new="    says = [k for k in LETTERING_KINDS if Path(rel).stem.lower().startswith(k)]\n",
         tests=[PR + "test_lockup_or_wordmark_comes_from_lettering_or_the_file_name_and_is_never_guessed"]),
    dict(group="profiles", id="wordmark-drops-the-mark", file="scripts/emitters/profiles.py",
         old='"mark": "" if layout == "lockup" else mark_html,', new='"mark": "",',
         tests=[PR + "test_the_drawn_wordmark_and_the_real_tagline_are_drawn_and_nothing_else"]),
    # `check` over a profile pack: a lost label, an avatar outside the circle the manifest records, a banner file that is gone (three faults, one run)
    dict(group="profiles", id="check-ignores-a-lost-label", file="scripts/emitters/tierb.py",
         old='        if u and LABEL not in str(a.get("note", "")):\n', new="        if False:\n",
         tests=[PR + "test_every_file_says_unverified_and_check_holds_the_label_and_the_safe_areas"]),
    dict(group="profiles", id="check-does-not-measure-the-avatar-circle", file="scripts/emitters/tierb.py",
         old='            if far > a["safe_radius_px"] + INK_TOLERANCE_PX:\n', new="            if False:\n",
         tests=[PR + "test_every_file_says_unverified_and_check_holds_the_label_and_the_safe_areas"]),
    dict(group="profiles", id="check-does-not-miss-a-banner-file", file="scripts/emitters/tierb.py",
         old='        if not any(p.endswith("/" + name) and (project / p).is_file() for p in by_path):\n',
         new='        if not any(p.endswith("/" + name) for p in by_path):\n',
         tests=[PR + "test_every_file_says_unverified_and_check_holds_the_label_and_the_safe_areas"]),
    dict(group="profiles", id="check-does-not-measure-a-banner-rectangle", file="scripts/emitters/tierb.py",
         old="""                out.append(f"{a['path']}: ink box {bb} is outside the safe rectangle")\n""", new="                pass\n",
         tests=[PR + "test_every_file_says_unverified_and_check_holds_the_label_and_the_safe_areas"]),
    dict(group="profiles", id="check-takes-any-recorded-size", file="scripts/emitters/tierb.py",
         old='        if f"{w}x{h}" != a.get("size"):\n', new="        if False:\n",
         tests=[PR + "test_every_file_says_unverified_and_check_holds_the_label_and_the_safe_areas"]),
    # what the tests measure on the pixels themselves (ink(): where the ink is, how far from the centre, whether the proof's red is in the file)
    dict(group="profiles", id="avatar-mark-shrinks", file="scripts/emitters/profiles.py",
         old="AVATAR_MAX_CONTENT = 0.7 ", new="AVATAR_MAX_CONTENT = 0.05 ",
         tests=[PR + "test_avatars_are_opaque_squares_with_the_mark_centred_inside_the_circle"]),
    dict(group="profiles", id="banner-content-shrinks", file="scripts/emitters/profiles.py",
         old=('        mark_px = round(sh * ROW_MARK_SHARE) if wide else round(min(sw * COLUMN_MARK_SHARE, sh * COLUMN_MARK_HEIGHT))\n'
              '        title_px = round(sh * TITLE_ROW) if wide else round(sw * TITLE_COLUMN)\n'),
         new=('        mark_px = round(sh * ROW_MARK_SHARE / 5) if wide else round(min(sw * COLUMN_MARK_SHARE, sh * COLUMN_MARK_HEIGHT) / 5)\n'
              '        title_px = round(sh * TITLE_ROW / 5) if wide else round(sw * TITLE_COLUMN / 5)\n'),
         tests=[PR + "test_each_banner_has_the_spec_size_no_alpha_and_all_its_ink_inside_the_safe_rectangle"]),
    dict(group="profiles", id="proof-without-red-dashes", file="scripts/emitters/profiles.py",
         old='PROOF_STROKE = "crimson"\n', new='PROOF_STROKE = "black"\n',
         tests=[PR + "test_proof_images_draw_the_safe_areas_are_never_shipped_or_in_the_manifest_and_a_second_run_writes_nothing"]),
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

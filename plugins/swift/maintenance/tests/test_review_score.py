import json
import subprocess
import tempfile
import unittest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "review-fixtures"
SCRIPT = FIXTURES / "score.py"
KEY = FIXTURES / "key.json"

H = "https://developer.apple.com/design/human-interface-guidelines"

# One correct finding per planted violation in planted/SettingsView.swift.
CODE_FINDINGS = {
    "P1": f"- [medium] Account values sit in a VStack with Dividers instead of a Form with LabeledContent — SettingsView.swift:57 — HIG: {H}/lists-and-tables — Fix: use Form, Section and LabeledContent",
    "P2": f"- [high] The Account header uses .system(size: 13, weight: .ultraLight) — SettingsView.swift:43 — HIG: {H}/typography — Fix: use .font(.headline)",
    "P3": f"- [high] The edit button's hit region is 28x28 pt, under 44x44 pt — SettingsView.swift:55 — HIG: {H}/buttons — Fix: give it a 44x44 pt frame with contentShape",
    "P4": f"- [high] Sync state is shown by colour alone — SettingsView.swift:69 — HIG: {H}/color — Fix: add a symbol and label",
    "P5": f"- [medium] Three prominent toolbar actions compete — SettingsView.swift:20 — HIG: {H}/toolbars — Fix: one tinted primary action",
    "P6": f"- [high] Delete Account has no role: .destructive and is styled prominent — SettingsView.swift:83 — HIG: {H}/buttons — Fix: Button(role: .destructive), not prominent",
    "P7": f"- [medium] The edit sheet has Done but no Cancel — SettingsView.swift:102 — HIG: {H}/sheets — Fix: add a Cancel button in .cancellationAction",
    "P8": f"- [medium] The storage card uses .glassEffect on content — SettingsView.swift:82 — HIG: {H}/materials — Fix: remove the glass and use a plain grouped background",
}


def review(*lines, not_checked=()):
    body = "## Findings\n" + "\n".join(lines) + "\n\n## Not checked\n" + "\n".join(not_checked) + "\n"
    return body


def score(text, run):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "review.md"
        path.write_text(text)
        return subprocess.run(
            ["python3", str(SCRIPT), str(KEY), str(path), "--run", run],
            capture_output=True,
            text=True,
        )


class KeyShapeTests(unittest.TestCase):
    def test_every_planted_id_is_defined_with_a_pattern_and_lines(self):
        key = json.loads(KEY.read_text())
        for run in key["runs"].values():
            for vid in run["planted"]:
                v = key["violations"][vid]
                self.assertTrue(v["must_match"])
                self.assertTrue(all(lo <= hi for lo, hi in v["lines"]))
            for nid in run["never"]:
                self.assertIn(nid, key["never"])


class CodeRunTests(unittest.TestCase):
    def test_all_eight_findings_at_their_lines_pass(self):
        r = score(review(*CODE_FINDINGS.values()), "code")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("detected 8/8", r.stdout)

    def test_two_missing_findings_fail(self):
        lines = [v for k, v in CODE_FINDINGS.items() if k not in ("P5", "P7")]
        r = score(review(*lines), "code")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("detected 6/8", r.stdout)
        self.assertIn("P5", r.stdout)
        self.assertIn("P7", r.stdout)

    def test_a_finding_at_the_wrong_line_is_not_detected(self):
        moved = CODE_FINDINGS["P6"].replace("SettingsView.swift:83", "SettingsView.swift:10")
        lines = [moved if k == "P6" else v for k, v in CODE_FINDINGS.items()]
        r = score(review(*lines), "code")
        self.assertIn("detected 7/8", r.stdout)
        self.assertIn("missed ['P6']", r.stdout)

    def test_a_line_range_covering_the_violation_counts(self):
        ranged = CODE_FINDINGS["P1"].replace("SettingsView.swift:57", "SettingsView.swift:41-72")
        lines = [ranged if k == "P1" else v for k, v in CODE_FINDINGS.items()]
        self.assertIn("detected 8/8", score(review(*lines), "code").stdout)

    def test_text_under_not_checked_is_not_a_finding(self):
        lines = [v for k, v in CODE_FINDINGS.items() if k != "P7"]
        r = score(review(*lines, not_checked=[CODE_FINDINGS["P7"]]), "code")
        self.assertIn("missed ['P7']", r.stdout)

    def test_suggesting_glass_is_a_false_positive(self):
        extra = f"- [low] Consider adopting Liquid Glass for the toolbar — SettingsView.swift:18 — HIG: {H}/materials — Fix: add .glassEffect to the toolbar buttons"
        r = score(review(*CODE_FINDINGS.values(), extra), "code")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("N1", r.stdout)

    def test_removing_glass_from_content_is_not_a_false_positive(self):
        r = score(review(*CODE_FINDINGS.values()), "code")
        self.assertIn("false positives []", r.stdout)

    def test_unlisted_findings_are_counted_as_unscored(self):
        extra = f"- [low] The pencil button has no accessibility label — SettingsView.swift:52 — HIG: {H}/accessibility — Fix: .accessibilityLabel(\"Edit name\")"
        r = score(review(*CODE_FINDINGS.values(), extra), "code")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("unscored 1", r.stdout)


class TokenedRunTests(unittest.TestCase):
    P3T = f"- [high] The edit button is 28x28 pt, below the 44x44 pt hit region — SettingsView.swift:24 — HIG: {H}/buttons — Fix: 44x44 pt frame"
    P4T = f"- [high] Sync status relies on colour alone (Palette.success vs Palette.danger) — SettingsView.swift:34 — HIG: {H}/color — Fix: add a symbol or label"

    def test_both_kept_violations_pass(self):
        r = score(review(self.P3T, self.P4T), "tokened")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_calling_a_token_hard_coded_is_a_false_positive(self):
        extra = f"- [medium] DesignTokens.Palette.brand is a hard-coded Color(red:green:blue:) — DesignTokens.swift:15 — HIG: {H}/color — Fix: use an asset colour set"
        r = score(review(self.P3T, self.P4T, extra), "tokened")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("N2", r.stdout)


class ScreenshotRunTests(unittest.TestCase):
    FINDINGS = [
        f"- [medium] Labelled rows are split by divider lines rather than a grouped Form — screenshot: Account rows — HIG: {H}/lists-and-tables — Fix: Form with LabeledContent",
        f"- [medium] The Account header is set in an ultralight weight — screenshot: top-left header — HIG: {H}/typography — Fix: a text style at Regular or heavier",
        f"- [high] The pencil button looks about 14x14 pt (estimated, @2x), well under the 44x44 pt hit region — screenshot: Name row — HIG: {H}/buttons — Fix: 44x44 pt hit region",
        f"- [high] Sync state is a red dot with no symbol or label — screenshot: Sync row — HIG: {H}/color — Fix: add a symbol and label",
        f"- [high] Delete Account is prominent and reads as the default, not a destructive action — screenshot: bottom — HIG: {H}/buttons — Fix: role: .destructive, bordered",
    ]

    def test_image_supportable_findings_pass(self):
        r = score(review(*self.FINDINGS), "screenshot")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("detected 5/5", r.stdout)

    def test_an_exact_size_without_estimated_is_a_false_positive(self):
        exact = self.FINDINGS[2].replace("about 14x14 pt (estimated, @2x)", "14x14 pt")
        r = score(review(*self.FINDINGS[:2], exact, *self.FINDINGS[3:]), "screenshot")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("N3", r.stdout)

    def test_a_dynamic_type_finding_from_one_image_is_a_false_positive(self):
        extra = f"- [medium] Text will not scale with Dynamic Type — screenshot: all rows — HIG: {H}/typography — Fix: text styles"
        r = score(review(*self.FINDINGS, extra), "screenshot")
        self.assertIn("N3", r.stdout)

    def test_dynamic_type_under_not_checked_is_fine(self):
        r = score(review(*self.FINDINGS, not_checked=["- Dynamic Type: needs an accessibility-size capture"]), "screenshot")
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()

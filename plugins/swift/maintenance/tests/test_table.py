import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apicheck import apple  # noqa: E402
from apicheck.table import BEGIN, END, render_table, replace_block  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def platforms(name):
    return apple.parse_platforms(
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    )


class RenderTableTests(unittest.TestCase):
    def test_row_shows_versions_dashes_and_doc_link(self):
        table = render_table(
            [
                (
                    "glassEffect(_:in:)",
                    "swiftui/view/glasseffect(_:in:)",
                    platforms("glasseffect.json"),
                )
            ]
        )
        header, rule, row = table.splitlines()
        self.assertEqual(
            header,
            "| API | iOS | iPadOS | Mac Catalyst | macOS | visionOS | watchOS | tvOS | Notes |",
        )
        self.assertEqual(row.count("|"), len(header.split("|")) - 1)
        self.assertIn(
            "| `glassEffect(_:in:)` | 26.0 | 26.0 | 26.0 | 26.0 | — | 26.0 | 26.0 |",
            row,
        )
        self.assertIn(
            "<https://developer.apple.com/documentation/swiftui/view/glasseffect(_:in:)>",
            row,
        )

    def test_deprecations_are_grouped_by_version(self):
        table = render_table(
            [
                (
                    "cornerRadius(_:antialiased:)",
                    "swiftui/view/cornerradius(_:antialiased:)",
                    platforms("cornerradius.json"),
                )
            ]
        )
        self.assertIn("deprecated 27.2: iOS, macOS, visionOS", table)


class ReplaceBlockTests(unittest.TestCase):
    def test_replaces_only_the_marked_block(self):
        text = f"intro\n{BEGIN}\nold table\n{END}\noutro\n"
        self.assertEqual(
            replace_block(text, "NEW"), f"intro\n{BEGIN}\nNEW\n{END}\noutro\n"
        )

    def test_missing_duplicate_or_reversed_markers_are_refused(self):
        for text in (
            "no markers",
            f"{BEGIN}\n{END}\n{BEGIN}\n{END}",
            f"{END}\n{BEGIN}",
        ):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    replace_block(text, "NEW")


if __name__ == "__main__":
    unittest.main()

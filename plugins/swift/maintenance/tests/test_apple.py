import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apicheck import apple  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ParseIndexTests(unittest.TestCase):
    def setUp(self):
        self.entries = apple.parse_index(fixture("index-swiftui.json"))
        self.lookup = apple.build_lookup(self.entries)

    def test_flattens_nested_children_and_skips_nodes_without_a_path(self):
        paths = {e.path for e in self.entries}
        self.assertIn("swiftui/view/glasseffect(_:in:)", paths)
        self.assertIn("swiftui/text/bold()", paths)
        self.assertNotIn(None, paths)
        self.assertEqual(len(self.entries), 11)

    def test_key_drops_arguments_and_disambiguation_suffix(self):
        keys = {e.path: e.key for e in self.entries}
        self.assertEqual(keys["swiftui/view/glasseffect(_:in:)"], "glasseffect")
        self.assertEqual(keys["webkit/webview-swift.struct"], "webview")

    def test_reads_deprecated_flag(self):
        (entry,) = self.lookup["cornerradius"]
        self.assertTrue(entry.deprecated)

    def test_symbol_listed_under_two_topics_appears_once(self):
        node = {
            "title": "Text",
            "path": "/documentation/swiftui/text",
            "type": "struct",
        }
        data = {
            "interfaceLanguages": {
                "swift": [{"title": "A", "path": None, "children": [node]}, node]
            }
        }
        self.assertEqual(len(apple.parse_index(data)), 1)

    def test_rejects_data_that_is_not_an_index(self):
        with self.assertRaises(ValueError):
            apple.parse_index({"metadata": {}})


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.lookup = apple.build_lookup(
            apple.parse_index(fixture("index-swiftui.json"))
        )

    def test_member_resolves_to_method(self):
        self.assertEqual(
            apple.resolve("glassEffect", "member", self.lookup)[0].path,
            "swiftui/view/glasseffect(_:in:)",
        )

    def test_type_resolves_through_disambiguated_path(self):
        self.assertEqual(
            apple.resolve("WebView", "type", self.lookup)[0].kind, "struct"
        )

    def test_attribute_resolves_to_macro(self):
        self.assertEqual(
            apple.resolve("Previewable", "attribute", self.lookup)[0].kind, "macro"
        )

    def test_kind_must_match(self):
        self.assertEqual(
            apple.resolve("text", "member", self.lookup), []
        )  # Text is a struct, not a .text( member
        self.assertEqual(apple.resolve("Missing", "type", self.lookup), [])


class ParsePlatformsTests(unittest.TestCase):
    def test_platforms_without_visionos(self):
        platforms = apple.parse_platforms(fixture("glasseffect.json"))
        self.assertNotIn("visionOS", platforms)
        self.assertEqual(platforms["iOS"].introduced, "26.0")
        self.assertIsNone(platforms["iOS"].deprecated_at)

    def test_deprecated_at_version(self):
        platforms = apple.parse_platforms(fixture("cornerradius.json"))
        self.assertEqual(platforms["macOS"].deprecated_at, "27.2")

    def test_deprecated_flag_without_version(self):
        page = {
            "metadata": {
                "platforms": [
                    {"name": "iOS", "introducedAt": "13.0", "deprecated": True}
                ]
            }
        }
        self.assertEqual(apple.parse_platforms(page)["iOS"].deprecated_at, "?")

    def test_page_without_platforms_is_an_error(self):
        with self.assertRaises(ValueError):
            apple.parse_platforms({"metadata": {"title": "An article"}})


class CheckClaimsTests(unittest.TestCase):
    def test_matching_claims_pass(self):
        platforms = apple.parse_platforms(fixture("glasseffect.json"))
        claims = {
            "visionOS": False,
            "iOS": "26.0",
            "macOS": True,
            "deprecated": False,
            "beta": False,
        }
        self.assertEqual(
            apple.check_claims("glassEffect(_:in:)", claims, platforms), []
        )

    def test_wrong_platform_claim_is_reported(self):
        platforms = apple.parse_platforms(fixture("glasseffect.json"))
        (problem,) = apple.check_claims(
            "glassEffect(_:in:)", {"visionOS": True}, platforms
        )
        self.assertIn("visionOS=True", problem)
        self.assertIn("Apple says False", problem)

    def test_wrong_version_claim_is_reported(self):
        platforms = apple.parse_platforms(fixture("glasseffect.json"))
        (problem,) = apple.check_claims(
            "glassEffect(_:in:)", {"iOS": "18.0"}, platforms
        )
        self.assertIn("Apple says '26.0'", problem)

    def test_deprecation_claim_is_checked(self):
        platforms = apple.parse_platforms(fixture("cornerradius.json"))
        self.assertEqual(
            len(
                apple.check_claims(
                    "cornerRadius(_:antialiased:)", {"deprecated": False}, platforms
                )
            ),
            1,
        )

    def test_unknown_claim_key_raises(self):
        with self.assertRaises(ValueError):
            apple.check_claims("x", {"visionos": False}, {})


if __name__ == "__main__":
    unittest.main()

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apicheck.manifest import ManifestError, load_manifest  # noqa: E402

VALID = {
    "frameworks": ["swiftui"],
    "apis": [
        {
            "name": "glassEffect(_:in:)",
            "path": "swiftui/view/glasseffect(_:in:)",
            "claims": {"visionOS": False, "iOS": "26.0"},
            "table": True,
        },
        {"name": "GlassEffectContainer", "path": "swiftui/glasseffectcontainer"},
    ],
    "ignore": {"example views": ["CardView", "ContentView"]},
}


class LoadManifestTests(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "apis.json"
            path.write_text(json.dumps(data))
            return load_manifest(path)

    def test_valid_manifest(self):
        m = self.load(VALID)
        self.assertEqual(m.frameworks, ("swiftui",))
        self.assertEqual(m.apis[0].claims, {"visionOS": False, "iOS": "26.0"})
        self.assertTrue(m.apis[0].table)
        self.assertFalse(m.apis[1].table)
        self.assertEqual(m.ignore["CardView"], "example views")

    def assertRejected(self, data, fragment):
        with self.assertRaises(ManifestError) as ctx:
            self.load(data)
        self.assertIn(fragment, str(ctx.exception))

    def test_unknown_top_level_key(self):
        self.assertRejected({**VALID, "extra": 1}, "unknown keys")

    def test_frameworks_required(self):
        self.assertRejected({**VALID, "frameworks": []}, "frameworks")

    def test_misspelled_platform_claim(self):
        bad = {
            **VALID,
            "apis": [{"name": "x", "path": "swiftui/x", "claims": {"visionos": False}}],
        }
        self.assertRejected(bad, "bad claim 'visionos'")

    def test_deprecated_claim_must_be_bool(self):
        bad = {
            **VALID,
            "apis": [
                {"name": "x", "path": "swiftui/x", "claims": {"deprecated": "27.2"}}
            ],
        }
        self.assertRejected(bad, "bad claim 'deprecated'")

    def test_duplicate_api_name(self):
        entry = {"name": "x", "path": "swiftui/x"}
        self.assertRejected({**VALID, "apis": [entry, entry]}, "duplicate name")

    def test_path_must_be_relative_without_json(self):
        self.assertRejected(
            {**VALID, "apis": [{"name": "x", "path": "/documentation/swiftui/x"}]},
            "relative",
        )
        self.assertRejected(
            {**VALID, "apis": [{"name": "x", "path": "swiftui/x.json"}]}, "relative"
        )

    def test_name_ignored_twice(self):
        self.assertRejected(
            {**VALID, "ignore": {"a": ["CardView"], "b": ["CardView"]}}, "ignored twice"
        )

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "apis.json"
            path.write_text("{")
            with self.assertRaises(ManifestError):
                load_manifest(path)


if __name__ == "__main__":
    unittest.main()

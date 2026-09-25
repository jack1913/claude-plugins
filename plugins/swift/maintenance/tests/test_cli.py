import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apicheck import cli  # noqa: E402
from apicheck.fetch import NotFound  # noqa: E402
from apicheck.table import BEGIN, END  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
PAGES = {
    "swiftui/view/glasseffect(_:in:)": "glasseffect.json",
    "swiftui/view/glassbackgroundeffect(in:displaymode:)": "glassbackgroundeffect.json",
}


class FakeFetcher:
    def __init__(self, oldest_cache_age_days=None):
        self._oldest_cache_age_days = oldest_cache_age_days

    def index(self, framework):
        if framework != "swiftui":
            raise NotFound(framework)
        return json.loads((FIXTURES / "index-swiftui.json").read_text(encoding="utf-8"))

    def page(self, doc_path):
        if doc_path not in PAGES:
            raise NotFound(doc_path)
        return json.loads((FIXTURES / PAGES[doc_path]).read_text(encoding="utf-8"))

    def oldest_cache_age_days(self):
        return self._oldest_cache_age_days


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.skills = root / "skills"
        (self.skills / "swiftui" / "references").mkdir(parents=True)
        (self.skills / "swiftui" / "SKILL.md").write_text(
            "```swift\nstruct CardView: View {\n  var body: some View {\n"
            '    Text("").bold().glassEffect()\n  }\n}\n```\nOn visionOS use `glassBackgroundEffect(in:displayMode:)`.\n'
        )
        self.table_file = (
            self.skills / "swiftui" / "references" / "platform-availability.md"
        )
        self.table_file.write_text(f"# Platforms\n{BEGIN}\n{END}\n")
        self.manifest_path = root / "apis.json"
        self.manifest = {
            "frameworks": ["swiftui"],
            "apis": [
                {
                    "name": "glassEffect(_:in:)",
                    "path": "swiftui/view/glasseffect(_:in:)",
                    "claims": {"visionOS": False},
                    "table": True,
                },
                {
                    "name": "glassBackgroundEffect(in:displayMode:)",
                    "path": "swiftui/view/glassbackgroundeffect(in:displaymode:)",
                    "claims": {"visionOS": True, "iOS": False},
                },
            ],
            "ignore": {},
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *flags, fetcher=None):
        self.manifest_path.write_text(json.dumps(self.manifest))
        argv = [
            "--manifest",
            str(self.manifest_path),
            "--skills",
            str(self.skills),
            "--table-file",
            str(self.table_file),
            *flags,
        ]
        out = io.StringIO()
        code = cli.run(cli.parse_args(argv), fetcher or FakeFetcher(), out=out)
        return code, out.getvalue()

    def test_clean_tree_passes_strict(self):
        code, out = self.run_cli("--strict")
        self.assertEqual(code, 0, out)
        self.assertIn("2 manifest APIs, 0 failures, 0 warnings", out)

    def test_no_cache_age_line_when_nothing_was_cached(self):
        # FakeFetcher's default oldest_cache_age_days() is None, like a
        # Fetcher that used no cache entries.
        code, out = self.run_cli("--strict")
        self.assertEqual(code, 0)
        self.assertNotIn("oldest cache entry", out)

    def test_fresh_cache_is_reported_but_not_a_warning(self):
        code, out = self.run_cli(
            "--strict", fetcher=FakeFetcher(oldest_cache_age_days=1.0)
        )
        self.assertEqual(code, 0, out)
        self.assertIn("oldest cache entry: 1.0 days old", out)
        self.assertNotIn("WARN", out)

    def test_stale_cache_warns_and_fails_only_under_strict(self):
        stale = FakeFetcher(oldest_cache_age_days=31.0)
        code, out = self.run_cli(fetcher=stale)
        self.assertEqual(code, 0)
        self.assertIn("oldest cache entry: 31.0 days old", out)
        self.assertIn("WARN cache is up to 31 days old", out)
        self.assertIn("--refresh", out)
        code, out = self.run_cli("--strict", fetcher=stale)
        self.assertEqual(code, 1, out)

    def test_stale_cache_message_and_threshold_round_the_same_way(self):
        # 30.4 rounds to 30, which is not > DEFAULT_MAX_AGE_DAYS (30): the
        # printed message and the pass/fail decision must agree, so this
        # must not warn. Before the fix, the raw (unrounded) age was
        # compared while the message printed the rounded age, so this case
        # warned "cache is up to 30 days old (> 30)" -- a message that
        # contradicts its own threshold.
        just_under = FakeFetcher(oldest_cache_age_days=30.4)
        code, out = self.run_cli("--strict", fetcher=just_under)
        self.assertEqual(code, 0, out)
        self.assertNotIn("WARN", out)

    def test_unresolved_name_warns_and_fails_only_under_strict(self):
        (self.skills / "swiftui" / "extra.md").write_text("Use `.glassMagic()`.\n")
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("WARN unresolved member 'glassMagic' in swiftui/extra.md", out)
        self.assertEqual(self.run_cli("--strict")[0], 1)

    def test_ignored_name_is_quiet_until_it_goes_stale(self):
        (self.skills / "swiftui" / "extra.md").write_text("Use `ExampleView`.\n")
        self.manifest["ignore"] = {"example views": ["ExampleView"]}
        self.assertEqual(self.run_cli("--strict")[0], 0)
        (self.skills / "swiftui" / "extra.md").write_text("nothing here\n")
        code, out = self.run_cli("--strict")
        self.assertEqual(code, 1)
        self.assertIn("'ExampleView' appears in no skill file", out)

    def test_ignored_name_that_now_resolves_is_flagged(self):
        self.manifest["ignore"] = {"oops": ["Text"]}
        code, out = self.run_cli("--strict")
        self.assertEqual(code, 1)
        self.assertIn("'Text' now resolves", out)

    def test_missing_apple_page_fails(self):
        self.manifest["apis"].append(
            {
                "name": "scrollExtensionMode(_:)",
                "path": "swiftui/view/scrollextensionmode(_:)",
            }
        )
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("FAIL scrollExtensionMode(_:): Apple has no page", out)

    def test_contradicted_claim_fails(self):
        self.manifest["apis"][0]["claims"] = {"visionOS": True}
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("skill says visionOS=True, Apple says False", out)

    def test_write_table_fills_the_block(self):
        code, out = self.run_cli("--write-table")
        self.assertEqual(code, 0, out)
        text = self.table_file.read_text()
        self.assertIn("| `glassEffect(_:in:)` | 26.0", text)
        self.assertNotIn("glassBackgroundEffect", text)  # table: false

    def test_write_table_refuses_while_checks_fail(self):
        self.manifest["apis"][0]["claims"] = {"visionOS": True}
        code, out = self.run_cli("--write-table")
        self.assertEqual(code, 1)
        self.assertIn("platform table not written", out)
        self.assertEqual(self.table_file.read_text(), f"# Platforms\n{BEGIN}\n{END}\n")

    def test_find_prints_index_entries(self):
        code, out = self.run_cli("--find", "glassEffect")
        self.assertEqual(code, 0)
        self.assertIn("swiftui/view/glasseffect(_:in:)", out)
        self.assertEqual(self.run_cli("--find", "nothingLikeThis")[0], 1)

    def test_missing_manifest_exits_2_before_any_network(self):
        err = io.StringIO()
        missing = Path(self.tmp.name) / "missing.json"
        with contextlib.redirect_stderr(err):
            code = cli.main(
                [
                    "--manifest",
                    str(missing),
                    "--cache",
                    str(Path(self.tmp.name) / "cache"),
                ]
            )
        self.assertEqual(code, 2)
        self.assertIn("error:", err.getvalue())
        self.assertFalse((Path(self.tmp.name) / "cache").exists())

    def test_unknown_framework_is_an_error(self):
        self.manifest["frameworks"] = ["swiftui", "nosuchkit"]
        with self.assertRaises(cli.ManifestError):
            self.run_cli()


if __name__ == "__main__":
    unittest.main()

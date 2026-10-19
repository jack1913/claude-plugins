import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "upstream-diff.sh"


def run(args, **env_extra):
    env = dict(os.environ, **env_extra)
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, env=env)


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def make_upstream(root: Path, skill_path: str, tags):
    """Scratch repo: commit+tag per entry; the file in skill_path changes each time."""
    repo = root / "upstream"
    (repo / skill_path).mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    for i, tag in enumerate(tags, start=1):
        (repo / skill_path / "SKILL.md").write_text(f"v{i}\n")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", f"v{i}")
        git(repo, "tag", tag)
    return repo


def make_upstream_md(root: Path, section: str, baseline: str):
    md = root / "UPSTREAM.md"
    md.write_text(
        "# Upstream\n\n"
        f"## {section}\n\n"
        f"- **Baseline tag:** `{baseline}` (`0000000`)\n\n"
        "### Deviations\n\n"
        "## Decoy\n\n"
        "- **Baseline tag:** `99.99.99` (`1111111`)\n"
    )
    return md


class UpstreamDiffTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_no_args_is_usage_error(self):
        r = run([])
        self.assertEqual(r.returncode, 2)
        self.assertIn("swiftui|concurrency|testing", r.stderr)

    def test_unknown_skill_is_usage_error(self):
        r = run(["nope"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("swiftui|concurrency|testing", r.stderr)

    def test_diff_between_baseline_and_newest_tag(self):
        repo = make_upstream(self.root, "skills/swift-concurrency", ["1.0.0", "1.1.0"])
        md = make_upstream_md(self.root, "Concurrency", "1.0.0")
        r = run(["concurrency"], UPSTREAM_DIFF_URL=str(repo), UPSTREAM_MD=str(md))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("baseline: 1.0.0 -> ref: 1.1.0", r.stdout)
        self.assertIn("SKILL.md", r.stdout)

    def test_baseline_comes_from_the_named_section(self):
        # Decoy section says 99.99.99; the SwiftUI section says 1.0.0, which
        # the scratch repo has. If the parse were global or picked the wrong
        # section, the run would fail on a missing ref instead.
        repo = make_upstream(
            self.root, "skills/swiftui-expert-skill", ["1.0.0", "1.1.0"]
        )
        md = make_upstream_md(self.root, "SwiftUI", "1.0.0")
        r = run(["swiftui"], UPSTREAM_DIFF_URL=str(repo), UPSTREAM_MD=str(md))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("baseline: 1.0.0", r.stdout)

    def test_later_section_baseline_is_read_not_the_first(self):
        # Real file order: SwiftUI first, Concurrency second. A parse that only
        # checks the section exists and then takes the file's first Baseline
        # line would read SwiftUI's 99.99.99 and fail on a missing ref.
        repo = make_upstream(self.root, "skills/swift-concurrency", ["1.0.0", "1.1.0"])
        md = self.root / "UPSTREAM.md"
        md.write_text(
            "# Upstream\n\n"
            "## SwiftUI\n\n"
            "- **Baseline tag:** `99.99.99` (`1111111`)\n\n"
            "### Deviations\n\n"
            "## Concurrency\n\n"
            "- **Baseline tag:** `1.0.0` (`0000000`)\n"
        )
        r = run(["concurrency"], UPSTREAM_DIFF_URL=str(repo), UPSTREAM_MD=str(md))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("baseline: 1.0.0 -> ref: 1.1.0", r.stdout)

    def test_wrong_section_baseline_is_a_clear_error(self):
        # Two real sections: the swiftui one names a tag the repo lacks, the
        # concurrency one names a tag it has. Asking for swiftui must read the
        # SwiftUI section and error on its missing 99.99.99 ref.
        repo = make_upstream(self.root, "skills/swift-concurrency", ["1.0.0"])
        md = self.root / "UPSTREAM.md"
        md.write_text(
            "# Upstream\n\n"
            "## SwiftUI\n\n"
            "- **Baseline tag:** `99.99.99` (`1111111`)\n\n"
            "### Deviations\n\n"
            "## Concurrency\n\n"
            "- **Baseline tag:** `1.0.0` (`0000000`)\n"
        )
        r = run(["swiftui"], UPSTREAM_DIFF_URL=str(repo), UPSTREAM_MD=str(md))
        self.assertEqual(r.returncode, 2)
        self.assertIn("99.99.99", r.stderr)

    def test_missing_section_is_a_clear_error(self):
        repo = make_upstream(self.root, "skills/swift-concurrency", ["1.0.0"])
        md = make_upstream_md(self.root, "Concurrency", "1.0.0")
        r = run(["swiftui"], UPSTREAM_DIFF_URL=str(repo), UPSTREAM_MD=str(md))
        self.assertEqual(r.returncode, 2)
        self.assertIn("no '## SwiftUI' section", r.stderr)

    def test_no_plain_tag_errors(self):
        # Only a pre-release tag exists, so the newest-plain-tag default fails;
        # the baseline names the pre-release explicitly. Ref resolution runs
        # after the baseline parse, so the error is the missing plain tag.
        repo = make_upstream(self.root, "skills/swift-concurrency", ["1.0.0-beta.1"])
        md = make_upstream_md(self.root, "Concurrency", "1.0.0-beta.1")
        r = run(["concurrency"], UPSTREAM_DIFF_URL=str(repo), UPSTREAM_MD=str(md))
        self.assertEqual(r.returncode, 2)
        self.assertIn("no plain X.Y.Z tag", r.stderr)

    def test_ref_equal_to_baseline_reports_no_changes(self):
        repo = make_upstream(self.root, "skills/swift-concurrency", ["1.0.0", "1.1.0"])
        md = make_upstream_md(self.root, "Concurrency", "1.1.0")
        r = run(["concurrency"], UPSTREAM_DIFF_URL=str(repo), UPSTREAM_MD=str(md))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no upstream changes", r.stdout)


if __name__ == "__main__":
    unittest.main()

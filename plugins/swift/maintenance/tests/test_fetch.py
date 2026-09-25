import io
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apicheck.fetch import (  # noqa: E402
    DEFAULT_MAX_AGE_DAYS,
    Fetcher,
    FetchError,
    NotFound,
    url_for,
)


class FakeOpener:
    """Stands in for urlopen: answers from a dict of url → bytes, or raises the given exception."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        answer = self.answers[url]
        if isinstance(answer, Exception):
            raise answer
        return io.BytesIO(answer)


def http_error(url, code):
    return urllib.error.HTTPError(url, code, "error", {}, None)


class FetcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "cache"
        self.url = url_for("index/swiftui")

    def tearDown(self):
        self.tmp.cleanup()

    def test_url_keeps_symbol_punctuation(self):
        self.assertEqual(
            url_for("documentation/swiftui/view/glasseffect(_:in:).json"),
            "https://developer.apple.com/tutorials/data/documentation/swiftui/view/glasseffect(_:in:).json",
        )
        self.assertTrue(
            url_for("documentation/swiftui/text/+(_:_:).json").endswith(
                "/text/+(_:_:).json"
            )
        )

    def test_second_fetch_comes_from_the_cache(self):
        opener = FakeOpener({self.url: b'{"a": 1}'})
        fetcher = Fetcher(self.cache, opener=opener)
        self.assertEqual(fetcher.index("swiftui"), {"a": 1})
        self.assertEqual(fetcher.index("swiftui"), {"a": 1})
        self.assertEqual(len(opener.calls), 1)

    def test_refresh_bypasses_the_cache(self):
        opener = FakeOpener({self.url: b'{"a": 1}'})
        Fetcher(self.cache, opener=opener).index("swiftui")
        Fetcher(self.cache, refresh=True, opener=opener).index("swiftui")
        self.assertEqual(len(opener.calls), 2)

    def test_404_raises_not_found_and_caches_nothing(self):
        opener = FakeOpener({self.url: http_error(self.url, 404)})
        with self.assertRaises(NotFound):
            Fetcher(self.cache, opener=opener).index("swiftui")
        self.assertFalse(self.cache.exists())

    def test_server_error_and_network_error_are_fetch_errors_not_404s(self):
        for failure in (
            http_error(self.url, 503),
            urllib.error.URLError("offline"),
            TimeoutError(),
        ):
            with self.subTest(failure=failure):
                with self.assertRaises(FetchError):
                    Fetcher(self.cache, opener=FakeOpener({self.url: failure})).index(
                        "swiftui"
                    )
        self.assertFalse(self.cache.exists())

    def test_non_json_answer_is_a_fetch_error(self):
        with self.assertRaises(FetchError):
            Fetcher(self.cache, opener=FakeOpener({self.url: b"<html>"})).index(
                "swiftui"
            )

    def test_corrupt_cache_file_names_the_fix(self):
        fetcher = Fetcher(self.cache, opener=FakeOpener({self.url: b'{"a": 1}'}))
        fetcher.index("swiftui")
        (cached,) = self.cache.glob("*.json")
        cached.write_text('{"a": ')
        with self.assertRaises(FetchError) as ctx:
            fetcher.index("swiftui")
        self.assertIn("--refresh", str(ctx.exception))

    def test_oldest_cache_age_is_none_before_any_fetch(self):
        fetcher = Fetcher(self.cache, opener=FakeOpener({}))
        self.assertIsNone(fetcher.oldest_cache_age_days())

    def test_freshly_fetched_entry_has_near_zero_age(self):
        opener = FakeOpener({self.url: b'{"a": 1}'})
        fetcher = Fetcher(self.cache, opener=opener)
        fetcher.index("swiftui")
        age = fetcher.oldest_cache_age_days()
        self.assertGreaterEqual(age, 0.0)
        self.assertLess(age, 0.001)  # well under a minute

    def test_reports_age_of_a_cache_hit(self):
        opener = FakeOpener({self.url: b'{"a": 1}'})
        Fetcher(self.cache, opener=opener).index("swiftui")
        (cached,) = self.cache.glob("*.json")
        five_days_ago = cached.stat().st_mtime - 5 * 86400
        os.utime(cached, (five_days_ago, five_days_ago))

        clock = [cached.stat().st_mtime + 5 * 86400]
        fetcher = Fetcher(self.cache, opener=FakeOpener({}), now=lambda: clock[0])
        fetcher.index("swiftui")
        self.assertAlmostEqual(fetcher.oldest_cache_age_days(), 5.0, places=6)

    def test_oldest_cache_age_is_the_max_across_entries_used(self):
        url2 = url_for("index/foundation")
        opener = FakeOpener({self.url: b'{"a": 1}', url2: b'{"b": 2}'})
        fetcher = Fetcher(self.cache, opener=opener)
        fetcher.index("swiftui")
        fetcher.index("foundation")
        cached_files = list(self.cache.glob("*.json"))
        self.assertEqual(len(cached_files), 2)
        older, newer = cached_files
        now = older.stat().st_mtime
        os.utime(older, (now - 10 * 86400, now - 10 * 86400))
        os.utime(newer, (now - 1 * 86400, now - 1 * 86400))

        fetcher2 = Fetcher(self.cache, opener=FakeOpener({}), now=lambda: now)
        fetcher2.index("swiftui")
        fetcher2.index("foundation")
        self.assertAlmostEqual(fetcher2.oldest_cache_age_days(), 10.0, places=6)

    def test_default_max_age_is_30_days(self):
        self.assertEqual(DEFAULT_MAX_AGE_DAYS, 30)


if __name__ == "__main__":
    unittest.main()

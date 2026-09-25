"""Fetch Apple documentation JSON through an on-disk cache. Network goes only to developer.apple.com."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://developer.apple.com/tutorials/data/"
_SAFE = "/():_.,-+~!*=<>&|^"

# How old a cache entry can get before check-apis warns that it might be
# stale and suggests --refresh (see cli.py).
DEFAULT_MAX_AGE_DAYS = 30


class NotFound(Exception):
    """Apple answered 404 for this documentation path."""


class FetchError(Exception):
    """A network failure, a non-404 HTTP error, a non-JSON answer or a corrupt cache file."""


def url_for(rel: str) -> str:
    return BASE + urllib.parse.quote(rel, safe=_SAFE)


def _urlopen(url: str):
    return urllib.request.urlopen(url, timeout=30)


class Fetcher:
    def __init__(
        self, cache_dir: Path, refresh: bool = False, opener=_urlopen, now=time.time
    ):
        self.cache_dir = cache_dir
        self.refresh = refresh
        self._open = opener
        self._now = now
        self._cache_ages_days: list[float] = []

    def index(self, framework: str) -> dict:
        return self._get(f"index/{framework}")

    def page(self, doc_path: str) -> dict:
        return self._get(f"documentation/{doc_path}.json")

    def oldest_cache_age_days(self) -> float | None:
        """Age in days of the stalest cache entry this run read or wrote, or None if none was used."""
        return max(self._cache_ages_days) if self._cache_ages_days else None

    def _note_cache_age(self, cached: Path) -> None:
        age_days = (self._now() - cached.stat().st_mtime) / 86400
        self._cache_ages_days.append(age_days)

    def _get(self, rel: str) -> dict:
        cached = self.cache_dir / (
            hashlib.sha256(rel.encode()).hexdigest()[:32] + ".json"
        )
        if cached.exists() and not self.refresh:
            try:
                data = json.loads(cached.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise FetchError(
                    f"corrupt cache file {cached} for {rel}; rerun with --refresh"
                ) from exc
            self._note_cache_age(cached)
            return data
        url = url_for(rel)
        try:
            with self._open(url) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NotFound(url) from exc
            raise FetchError(f"{url}: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise FetchError(f"{url}: {exc}") from exc
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise FetchError(f"{url}: answer is not JSON") from exc
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(".partial")
        partial.write_bytes(body)
        os.replace(partial, cached)
        self._note_cache_age(cached)
        return data

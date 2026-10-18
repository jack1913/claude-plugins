#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator names <candidate>...: screen candidate names against domain registries and package/handle namespaces.

SCREENING, NOT CLEARANCE. Three states only: REGISTERED (the source answered "exists"), NOT-FOUND (the source answered
"does not exist right now"; this says nothing about price, reserved or premium names, or trademarks) and UNKNOWN (the
answer could not be established: control failed, rate limit, network error, conflicting sources).

Method (standard library only):
  * domains: IANA RDAP bootstrap (cached 24 h in the data dir) -> the TLD's RDAP server; a TLD the bootstrap does not
    list goes to whois on port 43 at the server whois.iana.org names; a DNS NS lookup through the system resolver
    cross-checks every domain (a conflict makes the cell UNKNOWN).
  * software profile: npm, GitHub (gh api when authenticated, else HTTPS), Docker Hub orgs and users, PyPI, crates.io,
    Homebrew formulae and casks. consumer and personal profiles check domains only and list manual social-handle links.
  * every source (and every TLD) is first proven by a known-taken and a known-unregistered control; a failing control
    turns that source's results into UNKNOWN.
  * 0.3-1 s between calls to one host, one retry after a 429 (Retry-After honoured), one generic User-Agent.
  * raw responses are saved under research/names/raw/<date>/run-<n>/ (one folder per run, the memo's number; a run never
    reuses a folder) and can be replayed with --offline <run folder>; the replay reports the date the recordings carry.
    Personal data of third parties is cut before anything is stored (allow-lists per service, vcards and whois contacts removed).
  * trademark offices are never queried: owner-run search links are generated (WIPO's terms forbid automation).

Privacy: before any network call the run prints which services receive the candidate names and needs --yes.
Exit codes: 0 every cell established, 3 at least one cell UNKNOWN (not verified), 2 usage error.
"""
from __future__ import annotations

import datetime as _dt
import email.utils
import hashlib
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from _common import (EXIT_CANNOT, EXIT_PASS, EXIT_USAGE, USER_AGENT, Parser, Report, add_project_arg, confine,  # noqa: E402
                     data_dir, fail, find_project, main_guard, rel, today, write_bytes_if_changed)

REG, NF, UNK = "REGISTERED", "NOT-FOUND", "UNKNOWN"
BANNER = ("Screening, not clearance. NOT-FOUND means a source said the name does not exist right now. It says nothing "
          "about price, reserved or premium names, pending releases or trademarks. Recheck before you buy or file.")
BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"
BOOTSTRAP_TTL = 24 * 3600
IANA_WHOIS = "whois.iana.org"
TAKEN_LABELS = ("google", "wikipedia", "microsoft")  # domain controls, tried in order until one is registered
UNREG_LABEL = "bc-zz-control-x7q4k9v2m"  # nobody registers this; if someone ever does, the control fails and cells become UNKNOWN
RAW_LIMIT = 4096  # bytes of a response body kept in a raw file: enough as evidence, too little to hold a stranger's profile
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
# What a raw file keeps of a JSON body, per service: an allow-list, so a stranger's profile (names, locations, companies,
# gravatar hashes, package authors) never reaches disk. (prefix of the key, top-level fields kept, {object field: its fields kept}).
ERROR_KEEP = ("error", "errors", "message", "detail")
BODY_KEEP = [
    ("GET https://api.github.com/users/", ("login", "type", "created_at", "public_repos"), {}),
    ("GET https://hub.docker.com/v2/", ("orgname", "username", "type", "date_joined", "is_active", "badge") + ERROR_KEEP, {}),
    ("GET https://registry.npmjs.org/", ("name", "description", "dist-tags", "license") + ERROR_KEEP, {}),
    ("GET https://pypi.org/pypi/", ERROR_KEEP, {"info": ("name", "version", "summary", "license")}),
    ("GET https://crates.io/api/", ERROR_KEEP, {"crate": ("id", "name", "created_at", "updated_at", "max_version", "description")}),
    ("GET https://formulae.brew.sh/api/", ("name", "full_name", "token", "tap", "desc", "license", "homepage") + ERROR_KEEP, {}),
]
# whois: only these keys survive (registrant, admin, tech and registrar contact blocks carry names, phones and postal addresses).
# Lines that are not "key: value" survive only when they are an answer the replay needs (no match, a query limit).
WHOIS_KEEP = {"domain name", "domain", "registry domain id", "creation date", "created", "registered on", "registered", "updated date",
              "last modified", "last updated", "changed", "expiry date", "registry expiry date", "expiration date", "expires",
              "renewal date", "option created", "option expiration date", "registrar", "registrar iana id", "registrar url",
              "registrar whois server", "domain status", "status", "nserver", "nameservers", "name server", "name servers",
              "dnssec", "source", "whois", "refer", "tld"}
WHOIS_NS_KEYS = {"nserver", "nameservers", "name server", "name servers"}
MAX_RETRY_WAIT = 30.0
HTTP_TIMEOUT = 20
KEEP_HEADERS = ("content-type", "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "location")
LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
TLD_RE = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)*$")
PROFILES = ("software", "consumer", "personal")
SKIPPABLE = ("domains", "dns", "npm", "github", "docker", "pypi", "crates", "brew")

EU_MEMBERS = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU",
              "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}
REGION_TLD = {"GB": "co.uk", "UK": "co.uk", "EU": "eu"}  # everything else: the ISO code is the ccTLD
DEFAULT_TLDS = {"software": ["com", "dev", "app", "io", "ai"], "consumer": ["com"], "personal": ["com", "me"]}

# id, label, group, url template, known-taken name (controls use the same endpoint)
HTTP_SOURCES = [
    ("npm", "npm", "npm", "https://registry.npmjs.org/{n}", "react"),
    ("github", "GitHub user or org", "github", "https://api.github.com/users/{n}", "octocat"),
    ("docker-org", "Docker Hub org", "docker", "https://hub.docker.com/v2/orgs/{n}/", "grafana"),
    ("docker-user", "Docker Hub user", "docker", "https://hub.docker.com/v2/users/{n}/", "library"),
    ("pypi", "PyPI", "pypi", "https://pypi.org/pypi/{n}/json", "requests"),
    ("crates", "crates.io", "crates", "https://crates.io/api/v1/crates/{n}", "serde"),
    ("brew-formula", "Homebrew formula", "brew", "https://formulae.brew.sh/api/formula/{n}.json", "wget"),
    ("brew-cask", "Homebrew cask", "brew", "https://formulae.brew.sh/api/cask/{n}.json", "firefox"),
]
SERVICE_HOSTS = {"npm": "registry.npmjs.org", "github": "api.github.com", "docker": "hub.docker.com", "pypi": "pypi.org",
                 "crates": "crates.io", "brew": "formulae.brew.sh"}

# whois text (several registries, each seen in the wild). The registered test is strict (a creation date, registrar or
# name server line) so a legal footer that says "not found" cannot flip it; both are proven by the controls.
WHOIS_REGISTERED = re.compile(r"^\s*(registry domain id|creation date|created|registered on|registrar|nserver|name server)\s*:",
                              re.I | re.M)
WHOIS_NOT_FOUND = re.compile(r"(no match|not found|no data found|no entries found|no object found|nothing found|"
                             r"status:\s*(free|avail\w*)|no information avail\w*|is not registered)", re.I)
WHOIS_LIMIT = re.compile(r"(limit exceeded|too many (queries|requests)|quota exceeded|rate limit|query limit)", re.I)

MANUAL_SOCIAL = [
    ("Instagram", "https://www.instagram.com/{n}/"), ("TikTok", "https://www.tiktok.com/@{n}"),
    ("YouTube", "https://www.youtube.com/@{n}"), ("Facebook", "https://www.facebook.com/{n}"),
    ("LinkedIn", "https://www.linkedin.com/company/{n}/"), ("X", "https://x.com/{n}"),
]


# ---------------------------------------------------------------- responses and transports

@dataclass
class Resp:
    status: int  # HTTP status; 200 for a completed whois or DNS exchange; 0 = no answer
    headers: dict = field(default_factory=dict)
    body: str = ""
    error: str = ""
    via: str = "https"
    note: str = ""
    raw: str = ""  # project-relative path of the saved raw file


def retry_after_seconds(value: str | None, now: float) -> float | None:
    if value is None or not str(value).strip():
        return None
    v = str(value).strip()
    if re.fullmatch(r"\d+(\.\d+)?", v):
        return float(v)
    try:
        dt = email.utils.parsedate_to_datetime(v)
    except (TypeError, ValueError):
        return None
    return max(0.0, dt.timestamp() - now)


def _strip_vcards(node):
    """RDAP entities carry vcards (contact names, phones, postal addresses): keep only the version line."""
    if isinstance(node, dict):
        return {k: (["vcard", [["version", {}, "text", "4.0"]]] if k == "vcardArray" else _strip_vcards(v)) for k, v in node.items()}
    if isinstance(node, list):
        return [_strip_vcards(v) for v in node]
    return node


def minimise_json(key: str, text: str) -> str:
    try:
        doc = json.loads(text)
    except (ValueError, TypeError):
        # unparseable (cut at the fetch limit, or not JSON): nothing is stored past a vcard, or past 200 characters for a known service
        if any(key.startswith(pfx) for pfx, _f, _n in BODY_KEEP):
            return text[:200]
        i = text.find('"vcardArray"')
        return text if i < 0 else text[:i] + "[vcard cut]"
    for pfx, flat, nested in BODY_KEEP:
        if key.startswith(pfx):
            if not isinstance(doc, dict):
                return text[:200]
            out = {k: doc[k] for k in flat if k in doc}
            for k, keep in nested.items():
                if isinstance(doc.get(k), dict):
                    out[k] = {f: doc[k][f] for f in keep if f in doc[k]}
            return json.dumps(out, sort_keys=True, ensure_ascii=False)
    return json.dumps(_strip_vcards(doc), sort_keys=True, ensure_ascii=False)


def minimise_whois(text: str) -> str:
    out, in_ns = [], False
    for ln in text.splitlines():
        m = re.match(r"\s*([^:\s][^:]*?)\s*:", ln) if not ln[:1].isspace() else None
        if m:
            k = re.sub(r"\s+", " ", m.group(1).lower())
            in_ns = k in WHOIS_NS_KEYS
            if k in WHOIS_KEEP:
                out.append(ln.rstrip())
            continue
        if in_ns and re.fullmatch(r"\s+[A-Za-z0-9.-]+\.?\s*", ln):
            out.append(ln.rstrip())  # a name server list continued on the next lines
            continue
        in_ns = False
        if WHOIS_NOT_FOUND.search(ln) or WHOIS_LIMIT.search(ln):
            out.append(ln.rstrip())
    return "\n".join(out)


def _slug(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")[:60]


class Transport:
    """Shared retry and pacing logic. Subclasses supply _http_once, whois and ns."""

    def __init__(self, spacing: float = 0.5, sleep=time.sleep, clock=time.monotonic, wall=time.time):
        self.spacing, self._sleep, self._clock, self._wall = spacing, sleep, clock, wall
        self._last: dict[str, float] = {}

    def pace(self, host: str) -> None:
        now = self._clock()
        last = self._last.get(host)
        if last is not None and now - last < self.spacing:
            self._sleep(self.spacing - (now - last))
        self._last[host] = self._clock()

    def http(self, url: str, headers: dict | None = None) -> Resp:
        resp = self._http_once(url, headers)
        limited = resp.status == 429 or (resp.status == 403 and "retry-after" in resp.headers)
        if not limited:
            return resp
        wait = retry_after_seconds(resp.headers.get("retry-after"), self._wall())
        if wait is None:
            resp.note = f"rate-limited (HTTP {resp.status}) without Retry-After; not retried"
        elif wait > MAX_RETRY_WAIT:
            resp.note = f"rate-limited (HTTP {resp.status}), Retry-After {wait:g}s is over the {MAX_RETRY_WAIT:g}s cap; not retried"
        else:
            self._sleep(max(wait, self.spacing))
            again = self._http_once(url, headers)
            again.note = f"retried once after Retry-After {wait:g}s"
            return again
        return resp

    def _http_once(self, url: str, headers: dict | None) -> Resp:  # pragma: no cover - abstract
        raise NotImplementedError

    def whois(self, server: str, query: str) -> Resp:  # pragma: no cover - abstract
        raise NotImplementedError

    def ns(self, name: str) -> Resp:  # pragma: no cover - abstract
        raise NotImplementedError

    def bootstrap(self, tlds: list[str]) -> tuple[dict | None, str]:  # pragma: no cover - abstract
        raise NotImplementedError


class Live(Transport):
    def __init__(self, raw_dir: Path | None, project: Path, cache_dir: Path, *, use_gh: bool = True, **kw):
        super().__init__(**kw)
        self.raw_dir, self.project, self.cache_dir, self.use_gh = raw_dir, project, cache_dir, use_gh
        self._seq: dict[str, int] = {}
        self._gh_ready: bool | None = None

    # -- raw files (also the replay fixtures)
    @staticmethod
    def minimise(key: str, text: str, limit: int) -> str:
        """What a raw file keeps of a body. Registries and APIs return strangers' personal data (profile names, locations,
        authors, contact names, phones, postal addresses): JSON bodies of the known services are cut to an allow-list, RDAP
        vcards to their version line, whois answers to the allow-listed keys. Everything is cut at `limit` (the status, the first
        characters and the headers are what the replay and a reader need) and e-mail addresses are removed from every body."""
        if key.startswith("WHOIS "):
            text = minimise_whois(text)
        else:
            text = minimise_json(key, text)
        return EMAIL_RE.sub("[email removed]", text[:limit])

    def store(self, key: str, resp: Resp, body: str | None = None, limit: int = RAW_LIMIT) -> None:
        if self.raw_dir is None:
            return
        n = self._seq.get(key, 0)
        self._seq[key] = n + 1
        name = f"{_slug(key)}-{hashlib.sha256(key.encode()).hexdigest()[:10]}-{n}.json"
        doc = {"key": key, "seq": n, "status": resp.status, "headers": resp.headers, "body": self.minimise(key, resp.body if body is None else body, limit),
               "error": resp.error, "via": resp.via, "fetched": today()}
        path = self.raw_dir / name
        write_bytes_if_changed(path, (json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode())
        resp.raw = rel(self.project, path)

    # -- HTTP
    def _fetch(self, url: str, headers: dict) -> tuple[int, dict, str]:
        """One HTTPS GET. Returns (status, lower-cased headers, body); raises OSError-family on no answer."""
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rdap+json, application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
                return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read(262144).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read(262144).decode("utf-8", "replace")

    def gh_ready(self) -> bool:
        if self._gh_ready is None:
            ok = False
            if self.use_gh and shutil.which("gh"):
                try:
                    ok = subprocess.run(["gh", "auth", "status"], capture_output=True, timeout=30).returncode == 0
                except (OSError, subprocess.TimeoutExpired):
                    ok = False
            self._gh_ready = ok
        return self._gh_ready

    def _gh(self, url: str) -> Resp:
        path = url[len("https://api.github.com/"):]
        try:
            cp = subprocess.run(["gh", "api", "-i", path], capture_output=True, text=True, timeout=45)
        except (OSError, subprocess.TimeoutExpired) as e:
            return Resp(0, error=f"gh api failed ({type(e).__name__})", via="gh")
        m = re.match(r"HTTP/\S+\s+(\d{3})", cp.stdout)
        if not m:
            return Resp(0, error=f"gh api exited {cp.returncode} without an HTTP status", via="gh")
        parts = re.split(r"\r?\n\r?\n", cp.stdout, maxsplit=1)
        head, body = parts[0], (parts[1] if len(parts) > 1 else "")
        headers = {}
        for ln in head.splitlines()[1:]:
            k, _, v = ln.partition(":")
            headers[k.strip().lower()] = v.strip()
        return Resp(int(m.group(1)), headers, body, via="gh")

    def _http_once(self, url: str, headers: dict | None) -> Resp:
        host = re.match(r"https://([^/]+)", url).group(1)
        self.pace(host)
        if host == "api.github.com" and self.gh_ready():
            resp = self._gh(url)
        else:
            try:
                status, hdrs, body = self._fetch(url, headers or {})
                resp = Resp(status, hdrs, body)
            except (OSError, ValueError) as e:  # URLError, timeouts, TLS errors
                resp = Resp(0, error=f"{type(e).__name__}: {str(getattr(e, 'reason', e))[:120]}")
        resp.headers = {k: v for k, v in resp.headers.items() if k in KEEP_HEADERS}
        self.store(f"GET {url}", resp)
        return resp

    # -- whois (port 43)
    def whois(self, server: str, query: str) -> Resp:
        self.pace(server)
        key = f"WHOIS {server} {query}"
        try:
            with socket.create_connection((server, 43), timeout=15) as s:
                s.settimeout(15)
                s.sendall((query + "\r\n").encode("ascii"))
                chunks, size = [], 0
                while size < 262144:
                    c = s.recv(4096)
                    if not c:
                        break
                    chunks.append(c)
                    size += len(c)
            resp = Resp(200, {}, b"".join(chunks).decode("utf-8", "replace"), via="whois")
        except (OSError, UnicodeError) as e:
            resp = Resp(0, error=f"{type(e).__name__}: {str(e)[:120]}", via="whois")
        self.store(key, resp)
        return resp

    # -- DNS NS through the system resolver (no pacing: it is the local resolver, not a service we load)
    def ns(self, name: str) -> Resp:
        key = f"DNS NS {name}"
        try:
            resp = Resp(200, {}, json.dumps(dns_query_ns(name, system_resolvers()), sort_keys=True), via="dns")
        except (OSError, ValueError) as e:
            resp = Resp(0, error=f"{type(e).__name__}: {str(e)[:120]}", via="dns")
        self.store(key, resp)
        return resp

    # -- IANA RDAP bootstrap, cached 24 h
    def bootstrap(self, tlds: list[str]) -> tuple[dict | None, str]:
        cache = self.cache_dir / "iana-rdap-dns.json"
        doc = None
        try:
            c = json.loads(cache.read_text(encoding="utf-8"))
            if self._wall() - float(c["fetched_at"]) < BOOTSTRAP_TTL and isinstance(c["data"].get("services"), list):
                doc = c["data"]
        except (OSError, ValueError, KeyError, TypeError):
            doc = None
        if doc is None:
            resp = self._http_once_nostore(BOOTSTRAP_URL)
            if resp.status != 200:
                return None, f"IANA bootstrap download failed ({resp.error or 'HTTP ' + str(resp.status)})"
            try:
                doc = json.loads(resp.body)
                assert isinstance(doc["services"], list)
            except (ValueError, KeyError, AssertionError):
                return None, "IANA bootstrap download was not the expected JSON"
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"fetched_at": self._wall(), "source": BOOTSTRAP_URL, "data": doc}), encoding="utf-8")
        trimmed = trim_bootstrap(doc, tlds)
        self.store(f"GET {BOOTSTRAP_URL}", Resp(200, {}, json.dumps(trimmed, sort_keys=True)), limit=1 << 20)
        return doc, ""

    def _http_once_nostore(self, url: str) -> Resp:
        self.pace("data.iana.org")
        try:
            status, hdrs, body = self._fetch(url, {})
            return Resp(status, hdrs, body)
        except (OSError, ValueError) as e:
            return Resp(0, error=f"{type(e).__name__}: {str(getattr(e, 'reason', e))[:120]}")


class Replay(Transport):
    """Serves recorded responses (raw files from an earlier run or the test fixtures). Never sleeps, never touches the network."""

    def __init__(self, directory: Path, **kw):
        super().__init__(sleep=lambda s: None, **kw)
        self.dir = directory
        self.entries: dict[str, list[dict]] = {}
        files = sorted(directory.rglob("*.json"))
        if not files:
            fail(EXIT_USAGE, f"--offline {directory}: no recorded responses (*.json) found")
        runs = sorted({f.parent.name for f in files if f.parent.parent == directory and re.fullmatch(r"run-\d+", f.parent.name)})
        if len(runs) > 1:
            fail(EXIT_USAGE, f"--offline {directory}: holds several runs ({', '.join(runs)}); their answers would mix. Point --offline at one run folder.")
        self.fetched: set[str] = set()
        for f in files:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                key = d["key"]
            except (ValueError, KeyError, TypeError):
                fail(EXIT_USAGE, f"--offline: {f} is not a recorded response (needs a JSON object with a \"key\")")
            try:
                self.fetched.add(_dt.date.fromisoformat(str(d["fetched"])).isoformat())
            except (KeyError, ValueError):
                fail(EXIT_USAGE, f"--offline: {f} has no valid \"fetched\" date (YYYY-MM-DD). A replay reports the date the answers were "
                                 "recorded, so a recording without one cannot be replayed.")
            self.entries.setdefault(key, []).append(d)
        for lst in self.entries.values():
            lst.sort(key=lambda d: d.get("seq", 0))
        self._used: dict[str, int] = {}

    def _next(self, key: str) -> Resp:
        lst = self.entries.get(key)
        if not lst:
            return Resp(0, error=f"no recorded response for {key}", via="replay")
        i = self._used.get(key, 0)
        self._used[key] = i + 1
        d = lst[min(i, len(lst) - 1)]
        return Resp(int(d["status"]), dict(d.get("headers") or {}), d.get("body", ""), d.get("error", ""), d.get("via", "https"))

    def _http_once(self, url: str, headers: dict | None) -> Resp:
        return self._next(f"GET {url}")

    def whois(self, server: str, query: str) -> Resp:
        return self._next(f"WHOIS {server} {query}")

    def ns(self, name: str) -> Resp:
        return self._next(f"DNS NS {name}")

    def bootstrap(self, tlds: list[str]) -> tuple[dict | None, str]:
        r = self._next(f"GET {BOOTSTRAP_URL}")
        if r.status != 200:
            return None, f"no recorded IANA bootstrap ({r.error or 'HTTP ' + str(r.status)})"
        try:
            return json.loads(r.body), ""
        except ValueError:
            return None, "recorded IANA bootstrap is not JSON"


def trim_bootstrap(doc: dict, tlds: list[str]) -> dict:
    want = {t.rsplit(".", 1)[-1] for t in tlds}
    return {**{k: v for k, v in doc.items() if k != "services"},
            "services": [s for s in doc["services"] if want & set(s[0])], "trimmed_to": sorted(want)}


def bootstrap_base(doc: dict, tld: str) -> str | None:
    last = tld.rsplit(".", 1)[-1]
    for svc in doc.get("services", []):
        if last in svc[0]:
            urls = [u for u in svc[1] if u.startswith("https://")] or list(svc[1])
            if urls:
                return urls[0] if urls[0].endswith("/") else urls[0] + "/"
    return None


# ---------------------------------------------------------------- DNS (stdlib wire format)

def system_resolvers() -> list[str]:
    try:
        lines = Path("/etc/resolv.conf").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        raise OSError(f"cannot read the system resolver list: {e.strerror}") from None
    res = [p[1] for p in (ln.split() for ln in lines) if len(p) >= 2 and p[0] == "nameserver"]
    if not res:
        raise OSError("no nameserver in /etc/resolv.conf")
    return res


def build_ns_query(name: str, qid: int) -> bytes:
    q = b"".join(bytes([len(p)]) + p.encode("ascii") for p in name.rstrip(".").split(".")) + b"\x00"
    return struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + q + struct.pack(">HH", 2, 1)


def _name_at(buf: bytes, off: int) -> tuple[str, int]:
    labels, end, jumps = [], None, 0
    while True:
        if off >= len(buf):
            raise ValueError("DNS name runs past the packet")
        n = buf[off]
        if n == 0:
            off += 1
            break
        if n & 0xC0 == 0xC0:
            if off + 1 >= len(buf):
                raise ValueError("truncated DNS pointer")
            if end is None:
                end = off + 2
            off = ((n & 0x3F) << 8) | buf[off + 1]
            jumps += 1
            if jumps > 20:
                raise ValueError("DNS pointer loop")
            continue
        labels.append(buf[off + 1:off + 1 + n].decode("ascii", "replace"))
        off += 1 + n
    return ".".join(labels), (end if end is not None else off)


RCODES = {0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL", 3: "NXDOMAIN", 4: "NOTIMP", 5: "REFUSED"}


def parse_ns_response(buf: bytes, qid: int) -> dict:
    if len(buf) < 12:
        raise ValueError("short DNS answer")
    rid, flags, qd, an, ns_, _ar = struct.unpack(">HHHHHH", buf[:12])
    if rid != qid or not flags & 0x8000:
        raise ValueError("DNS answer does not match the query")
    off = 12
    for _ in range(qd):
        _n, off = _name_at(buf, off)
        off += 4
    answers, authority = [], []
    for i in range(an + ns_):
        _n, off = _name_at(buf, off)
        rtype, _cls, _ttl, rdlen = struct.unpack(">HHIH", buf[off:off + 10])
        off += 10
        if i < an:
            if rtype == 2:
                answers.append(_name_at(buf, off)[0].lower())
        else:
            authority.append(rtype)
        off += rdlen
    return {"rcode": RCODES.get(flags & 0xF, f"RCODE{flags & 0xF}"), "ns": sorted(answers), "authority": sorted(set(authority)),
            "truncated": bool(flags & 0x0200)}


def dns_query_ns(name: str, resolvers: list[str]) -> dict:
    last = "no resolver answered"
    for r in resolvers:
        try:
            infos = socket.getaddrinfo(r, 53, type=socket.SOCK_DGRAM)
            fam, _t, _p, _c, addr = infos[0]
            qid = int.from_bytes(os.urandom(2), "big")
            q = build_ns_query(name, qid)
            with socket.socket(fam, socket.SOCK_DGRAM) as s:
                s.settimeout(3)
                s.sendto(q, addr)
                out = parse_ns_response(s.recv(4096), qid)
            if out["truncated"]:
                with socket.socket(fam, socket.SOCK_STREAM) as s:
                    s.settimeout(5)
                    s.connect(addr)
                    s.sendall(struct.pack(">H", len(q)) + q)
                    ln = struct.unpack(">H", s.recv(2))[0]
                    data = b""
                    while len(data) < ln:
                        c = s.recv(ln - len(data))
                        if not c:
                            break
                        data += c
                out = parse_ns_response(data, qid)
            return out
        except (OSError, ValueError, struct.error) as e:
            last = f"{type(e).__name__}: {str(e)[:80]}"
    raise OSError(last)


def dns_state(resp: Resp) -> str:
    """NS (delegated), NXDOMAIN, NODATA or UNKNOWN."""
    if resp.status != 200:
        return "UNKNOWN"
    try:
        d = json.loads(resp.body)
    except ValueError:
        return "UNKNOWN"
    if d.get("rcode") == "NXDOMAIN":
        return "NXDOMAIN"
    if d.get("rcode") == "NOERROR":
        return "NS" if d.get("ns") else "NODATA"
    return "UNKNOWN"


# ---------------------------------------------------------------- interpreting answers

def interpret_http(resp: Resp, *, json_body: bool = False) -> tuple[str, str]:
    if resp.status == 0:
        return UNK, f"no answer: {resp.error}"
    extra = f"; {resp.note}" if resp.note else ""
    if resp.status == 200:
        if json_body and resp.body.lstrip()[:1] not in ("{", "["):  # bodies are stored truncated, so sniff instead of parsing
            return UNK, "HTTP 200 but the body is not JSON (a captive page or an error page?)" + extra
        return REG, "HTTP 200" + extra
    if resp.status == 404:
        return NF, "HTTP 404" + extra
    if resp.status in (403, 429):
        limited = resp.status == 429 or resp.headers.get("x-ratelimit-remaining") == "0" or "retry-after" in resp.headers
        return UNK, (f"rate-limited (HTTP {resp.status})" if limited else f"refused (HTTP {resp.status})") + extra
    return UNK, f"HTTP {resp.status}" + extra


def interpret_whois(resp: Resp) -> tuple[str, str]:
    if resp.status == 0:
        return UNK, f"no answer: {resp.error}"
    t = resp.body
    if WHOIS_REGISTERED.search(t):
        return REG, "whois record found"
    if WHOIS_NOT_FOUND.search(t):
        return NF, "whois reports no match"
    if WHOIS_LIMIT.search(t):
        return UNK, "whois server reports a query limit"
    return UNK, "whois answer not recognised"


# ---------------------------------------------------------------- the checker

@dataclass
class Cell:
    candidate: str
    source: str
    target: str
    state: str
    detail: str
    url: str = ""
    http: int = 0
    raw: list = field(default_factory=list)
    dns: str = ""


class Checker:
    def __init__(self, transport: Transport, tlds: list[str], skip: set[str]):
        self.t, self.tlds, self.skip = transport, tlds, skip
        self.doc: dict | None = None
        self.doc_err = ""
        self.controls: dict[str, dict] = {}
        self._tld_method: dict[str, tuple] = {}
        self._dns_ctl: dict | None = None

    # -- controls: a source is trusted only when both a known-taken and a known-unregistered name behave
    def run_controls(self, source: str, probe, taken: tuple) -> dict:
        if source in self.controls:
            return self.controls[source]
        rec = {"source": source, "taken": None, "unregistered": None, "ok": False, "why": ""}
        tried = []
        for lab in taken:
            st, det = probe(lab)
            tried.append(lab)
            rec["taken"] = {"name": lab, "state": st, "detail": det, "tried": list(tried)}
            if st == REG:
                break
        st2, det2 = probe(UNREG_LABEL)
        rec["unregistered"] = {"name": UNREG_LABEL, "state": st2, "detail": det2}
        why = []
        if rec["taken"]["state"] != REG:
            why.append(f"known-taken control returned {rec['taken']['state']} ({rec['taken']['detail']})")
        if st2 != NF:
            why.append(f"known-unregistered control returned {st2} ({det2})")
        rec["ok"], rec["why"] = not why, "; ".join(why)
        self.controls[source] = rec
        return rec

    # -- HTTP sources
    def _probe_http(self, url_tpl: str):
        def probe(name: str):
            r = self.t.http(url_tpl.format(n=name))
            return interpret_http(r, json_body=True)
        return probe

    def check_http(self, cand: str, src: tuple) -> Cell:
        sid, _label, _grp, tpl, taken = src
        url = tpl.format(n=cand)
        ctl = self.run_controls(sid, self._probe_http(tpl), (taken,))
        if not ctl["ok"]:
            return Cell(cand, sid, cand, UNK, "control failed: " + ctl["why"], url)
        r = self.t.http(url)
        st, det = interpret_http(r, json_body=True)
        return Cell(cand, sid, cand, st, det, url, r.status, [r.raw] if r.raw else [])

    # -- domains
    def load_bootstrap(self) -> None:
        if self.doc is None and not self.doc_err:
            self.doc, self.doc_err = self.t.bootstrap(self.tlds)

    def tld_method(self, tld: str) -> tuple:
        """('rdap', base) | ('whois', server) | ('none', reason)."""
        if tld in self._tld_method:
            return self._tld_method[tld]
        self.load_bootstrap()
        if self.doc is None:
            m = ("none", self.doc_err)
        else:
            base = bootstrap_base(self.doc, tld)
            m = ("rdap", base) if base else self.whois_method(tld, "not in the RDAP bootstrap")
        self._tld_method[tld] = m
        return m

    def whois_method(self, tld: str, why: str) -> tuple:
        last = tld.rsplit(".", 1)[-1]
        r = self.t.whois(IANA_WHOIS, last)
        srv = re.search(r"^\s*whois:\s*(\S+)", r.body, re.I | re.M) if r.status == 200 else None
        if srv:
            return ("whois", srv.group(1))
        return ("none", f".{last} is {why} and IANA names no whois server" + (f" ({r.error})" if r.error else ""))

    def _domain_probe(self, tld: str, method: tuple):
        def probe(label: str, resp_out: list | None = None):
            fqdn = f"{label}.{tld}"
            if method[0] == "rdap":
                r = self.t.http(f"{method[1]}domain/{fqdn}")
                st, det = interpret_http(r, json_body=True)
                det = ("RDAP " + det)
            else:
                r = self.t.whois(method[1], fqdn)
                st, det = interpret_whois(r)
            if resp_out is not None:
                resp_out.append(r)
            return st, det
        return probe

    def dns_controls_ok(self) -> tuple[bool, str]:
        if self._dns_ctl is None:
            def probe(label):
                st = dns_state(self.t.ns(f"{label}.com"))
                return (REG if st == "NS" else NF if st == "NXDOMAIN" else UNK), f"DNS {st}"
            rec = self.run_controls("dns", probe, TAKEN_LABELS)
            self._dns_ctl = rec
        return self._dns_ctl["ok"], self._dns_ctl["why"]

    def check_domain(self, cand: str, tld: str) -> Cell:
        fqdn = f"{cand}.{tld}"
        method = self.tld_method(tld)
        if method[0] == "none":
            return Cell(cand, f".{tld}", fqdn, UNK, method[1])
        probe = self._domain_probe(tld, method)
        sid = f".{tld}"
        ctl = self.run_controls(sid, lambda lab: probe(lab), TAKEN_LABELS)
        fell_back = ""
        if not ctl["ok"] and method[0] == "rdap" and any(ctl[k]["detail"].startswith("RDAP no answer") for k in ("taken", "unregistered")):
            # the RDAP server did not answer at all (for example a TLS chain Python cannot verify): use whois, and say so
            alt = self.whois_method(tld, "unreachable over RDAP")
            if alt[0] == "whois":
                method, fell_back = alt, " (the RDAP server did not answer, see the controls table; whois used)"
                probe = self._domain_probe(tld, method)
                sid = f".{tld} (whois)"
                ctl = self.run_controls(sid, lambda lab: probe(lab), TAKEN_LABELS)
        if not ctl["ok"]:
            return Cell(cand, f".{tld}", fqdn, UNK, f"control failed ({method[0]}): " + ctl["why"])
        out: list = []
        state, detail = probe(cand, out)
        detail += fell_back
        r = out[0]
        url = f"{method[1]}domain/{fqdn}" if method[0] == "rdap" else f"whois://{method[1]}/{fqdn}"
        cell = Cell(cand, f".{tld}", fqdn, state, detail, url, r.status, [r.raw] if r.raw else [])
        if "dns" in self.skip:
            return cell
        ok, why = self.dns_controls_ok()
        if not ok:
            cell.dns = "UNKNOWN"
            cell.detail += "; DNS cross-check not verified (control failed)"
            return cell
        nr = self.t.ns(fqdn)
        cell.dns = dns_state(nr)
        if nr.raw:
            cell.raw.append(nr.raw)
        if state == NF and cell.dns == "NS":
            cell.state, cell.detail = UNK, "registry says not-found but DNS delegates NS records (conflict); check by hand"
        elif state == NF and cell.dns == "NXDOMAIN":
            cell.detail += "; DNS NXDOMAIN agrees"
        elif state == UNK and cell.dns == "NS":
            cell.state, cell.detail = REG, f"inferred from DNS NS delegation (registry: {detail})"
        elif cell.dns in ("UNKNOWN", "NODATA"):
            cell.detail += f"; DNS cross-check inconclusive ({cell.dns})"
        else:
            cell.detail += f"; DNS {cell.dns}"
        return cell


# ---------------------------------------------------------------- plan, links, output

def region_tlds(region: str | None) -> list[str]:
    if not region:
        return []
    r = region.upper()
    out = [REGION_TLD.get(r, r.lower())]
    if r in EU_MEMBERS:
        out.append("eu")
    return out


def planned_sources(profile: str, skip: set[str]) -> list[tuple]:
    if profile != "software":
        return []
    return [s for s in HTTP_SOURCES if s[2] not in skip]


def disclosure(cands: list[str], tlds: list[str], profile: str, skip: set[str], use_gh: bool) -> list[str]:
    nm = ", ".join(cands)
    out = [f"PRIVACY: this run sends the candidate names ({nm}) to the services below. Nothing else leaves this machine; "
           "every request is a read-only lookup (nothing is registered, bought or created).",
           "  - data.iana.org: downloads the RDAP bootstrap list once per 24 h; receives no name"]
    if "domains" not in skip:
        t = " ".join("." + x for x in tlds)
        out += [f"  - the registry RDAP servers the bootstrap names for {t}: receive <name>.<tld>",
                f"  - {IANA_WHOIS} (receives the TLD only) and that TLD's own whois server (receives <name>.<tld>), for any TLD "
                "the bootstrap does not list"]
        if "dns" not in skip:
            out.append("  - the DNS resolver configured on this machine (and whatever it forwards to): NS lookup of <name>.<tld>")
    seen = []
    for _sid, _label, grp, _tpl, _t in planned_sources(profile, skip):
        if grp not in seen:
            seen.append(grp)
    for grp in seen:
        host = SERVICE_HOSTS[grp]
        extra = ""
        if grp == "github":
            extra = (" (through the gh CLI when it is logged in, which attaches your GitHub account to the request; "
                     "--no-gh forces anonymous HTTPS)") if use_gh else " (anonymous HTTPS, --no-gh)"
        out.append(f"  - {host}: receives <name>{extra}")
    out.append("  - Controls also send a few well-known names and one nonsense name to each of the same services.")
    out.append("  - Trademark offices are not contacted; owner-run links are listed in the report.")
    return out


def trademark_links(cands: list[str], region: str | None, classes: list[str]) -> list[dict]:
    r = (region or "").upper()
    offices = []
    if r and r not in ("EU", "EM"):
        offices.append(r if r != "UK" else "GB")
    offices += ["EM", "WO"]
    offices = list(dict.fromkeys(offices))
    cls = (" Nice classes to search: " + ", ".join(classes) + ".") if classes else ""
    out = []
    for c in cands:
        out.append({"candidate": c, "links": [
            {"office": f"EUIPO TMview ({'+'.join(offices)})", "kind": "deep link",
             "url": f"https://www.tmdn.org/tmview/#/tmview/results?page=1&pageSize=30&criteria=C&basicSearch={c}&fo=Y&offices={','.join(offices)}",
             "note": "Link format observed in a browser; open it yourself and confirm it loads." + cls},
            {"office": "EUIPO eSearch plus", "kind": "entry page", "url": "https://euipo.europa.eu/eSearch/",
             "note": f"Type the name yourself.{cls}"},
            {"office": "WIPO Global Brand Database", "kind": "manual only", "url": "https://branddb.wipo.int/",
             "note": "WIPO's terms forbid automated queries. brand-creator never calls it; search by hand."},
            {"office": "USPTO trademark search", "kind": "entry page", "url": "https://tmsearch.uspto.gov/",
             "note": "Text search is public; image search needs a USPTO.gov account (owner-run)."}]
              + ([{"office": "UPRP e-wyszukiwarka (Poland)", "kind": "entry page", "url": "https://ewyszukiwarka.pue.uprp.gov.pl/",
                   "note": "Public simple search; put multi-word names in quotes."}] if r == "PL" else [])
              + ([{"office": "UK IPO trade mark search", "kind": "entry page", "url": "https://www.gov.uk/search-for-trademark",
                   "note": "Owner-run."}] if r in ("GB", "UK") else [])
              + ([{"office": "National trademark office", "kind": "directory", "url": "https://www.wipo.int/directory/en/urls.jsp",
                   "note": f"Find the office for {r} in WIPO's directory of IP offices and search by hand."}]
                 if r and r not in ("PL", "GB", "UK", "EU", "EM") else [])})
    return out


def manual_links(cands: list[str]) -> list[dict]:
    return [{"candidate": c, "links": [{"service": s, "url": u.format(n=c)} for s, u in MANUAL_SOCIAL]} for c in cands]


def cell_text(c: Cell | None) -> str:
    return c.state if c else "-"


def render_markdown(meta: dict, cells: list[Cell], controls: list[dict], trademark: list[dict], manual: list[dict]) -> str:
    cols: list[str] = []
    for c in cells:
        if c.source not in cols:
            cols.append(c.source)
    L = [f"# Name screening {meta['date']}", "", f"> **{BANNER}**", "",
         f"Profile: {meta['profile']}. Region: {meta['region'] or 'not given'}. Checked: {meta['date']}"
         + (f" (recorded {meta['recorded']}, replayed {meta['replayed']}; the answers are as old as the recording)" if meta["mode"] != "live" else "")
         + f". Mode: {meta['mode']}. States: REGISTERED, NOT-FOUND, UNKNOWN (the source could not be established).", ""]
    L += ["| Candidate | " + " | ".join(cols) + " | Checked |", "|---|" + "---|" * (len(cols) + 1)]
    for cand in meta["candidates"]:
        row = {c.source: c for c in cells if c.candidate == cand}
        L.append(f"| {cand} | " + " | ".join(cell_text(row.get(s)) for s in cols) + f" | {meta['date']} |")
    unk = [c for c in cells if c.state == UNK]
    L += ["", "## UNKNOWN cells", ""]
    L += [f"- {c.candidate} / {c.source}: {c.detail}" for c in unk] or ["None."]
    L += ["", "## Per-cell detail", "", "| Candidate | Source | Target | State | Detail | Checked |", "|---|---|---|---|---|---|"]
    for c in cells:
        L.append(f"| {c.candidate} | {c.source} | {c.target} | {c.state} | {c.detail.replace('|', '/')} | {meta['date']} |")
    L += ["", "## Controls", "", "Each source is trusted only when a known-taken name is REGISTERED and a known-unregistered name is NOT-FOUND.", "",
          "| Source | Known-taken | Known-unregistered | Result |", "|---|---|---|---|"]
    for k in controls:
        L.append(f"| {k['source']} | {k['taken']['name']}: {k['taken']['state']} | {k['unregistered']['name']}: {k['unregistered']['state']} | "
                 f"{'passed' if k['ok'] else 'FAILED, source is UNKNOWN'} |")
    L += ["", "## Trademark search links (owner-run)", "",
          "Nothing here queries a trademark office. Open the links yourself, read the hits and record what you find by hand. "
          "A search with no hits is not clearance.", ""]
    for t in trademark:
        L.append(f"### {t['candidate']}")
        L += [f"- {x['office']} ({x['kind']}): {x['url']} . {x['note']}" for x in t["links"]]
        L.append("")
    if manual:
        L += ["## Social handles (manual)", "", "Open each link and look; nothing here calls these sites.", ""]
        for m in manual:
            L.append(f"### {m['candidate']}")
            L += [f"- {x['service']}: {x['url']}" for x in m["links"]]
            L.append("")
    L += ["## Reading this table", "",
          "- REGISTERED: the source answered that the name exists. The name is taken there.",
          "- NOT-FOUND: the source answered that the name does not exist right now. Reserved, premium, pending-delete and "
          "blocked names look the same. The owner confirms at a registrar; brand-creator never buys or registers anything.",
          "- UNKNOWN: not established (a control failed, a limit was hit, the network failed, or two sources disagree). Treat as not verified.",
          "- A package or handle that is NOT-FOUND may still be refused at publish time (registries block names close to existing or "
          "removed ones). GitHub's user lookup covers users and organisations, not repository names. npm scopes are an owner check.",
          "- Namespaces are only half of it: a name nobody holds in a namespace can still be an established product. Search "
          "repositories and the web for prior art before relying on any row.",
          f"- Every row was checked on {meta['date']}"
          + (f" (recorded; replayed {meta['replayed']})" if meta["mode"] != "live" else "") + ". Recheck close to the day you act.", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- CLI

def parse_args(argv: list[str]):
    ap = Parser(prog="brand-creator names", description=__doc__.split("\n\n")[0])
    ap.add_argument("candidates", nargs="+", help="candidate names: one token each, letters, digits and hyphens")
    add_project_arg(ap)
    ap.add_argument("--profile", choices=PROFILES, default="software",
                    help="software (domains and package/handle registries), consumer or personal (domains and manual social links)")
    ap.add_argument("--region", help="ISO country code of the audience (PL, DE, US, GB ...): picks the ccTLD and trademark offices")
    ap.add_argument("--tlds", help="comma-separated TLDs; replaces the profile and region defaults (e.g. com,dev,pl)")
    ap.add_argument("--classes", help="comma-separated Nice classes to mention beside the trademark links (e.g. 9,42)")
    ap.add_argument("--skip", help=f"comma-separated sources to leave out: {', '.join(SKIPPABLE)}")
    ap.add_argument("--spacing", type=float, default=0.5, help="seconds between calls to one host, 0.3 to 1 (default 0.5)")
    ap.add_argument("--no-gh", action="store_true", help="use anonymous HTTPS for GitHub even when gh is logged in")
    ap.add_argument("--yes", action="store_true", help="the owner agreed to send the names to the listed services")
    ap.add_argument("--plan", action="store_true", help="print which services would receive the names and exit 0 (no network)")
    ap.add_argument("--offline", metavar="DIR", help="replay recorded responses (one research/names/raw/<date>/run-<n> folder); the report carries the date of the recordings instead of the network")
    return ap.parse_args(argv)


def memo_path(project: Path, date: str, n: int) -> Path:
    return confine(project, f"research/names/{date}-check{'' if n == 1 else f'-{n}'}.md", what="memo")


def next_run(project: Path, date: str) -> int:
    """The first run number whose memo and raw folder are both unused: one run, one memo, one raw folder."""
    n = 1
    while memo_path(project, date, n).exists() or any(confine(project, f"research/names/raw/{date}/run-{n}", what="raw folder").glob("*")):
        n += 1
    return n


def normalise(cands: list[str]) -> list[str]:
    out = []
    for c in cands:
        n = c.strip().lower()
        if not LABEL_RE.match(n):
            fail(EXIT_USAGE, f"candidate {c!r} is not a single token of letters, digits and hyphens (1-63 characters, no leading or "
                             "trailing hyphen). Pass each name as its own argument; accents and spaces are not supported.")
        if n not in out:
            out.append(n)
    return out


def split_list(v: str | None, what: str, pattern: re.Pattern | None = None) -> list[str]:
    items = [x.strip().lower().lstrip(".") for x in (v or "").split(",") if x.strip()]
    for x in items:
        if pattern and not pattern.match(x):
            fail(EXIT_USAGE, f"bad {what}: {x!r}")
    return items


def main(argv: list[str] | None = None) -> int:
    a = parse_args(sys.argv[1:] if argv is None else argv)
    if not 0.3 <= a.spacing <= 1.0:
        fail(EXIT_USAGE, "--spacing must be between 0.3 and 1 second")
    cands = normalise(a.candidates)
    skip = set(split_list(a.skip, "--skip"))
    bad = skip - set(SKIPPABLE)
    if bad:
        fail(EXIT_USAGE, f"--skip: unknown source {sorted(bad)}; choose from {', '.join(SKIPPABLE)}")
    region = a.region.strip().upper() if a.region else None
    if region and not re.fullmatch(r"[A-Z]{2}", region):
        fail(EXIT_USAGE, "--region must be a two-letter country code such as PL, DE, US, GB")
    tlds = split_list(a.tlds, "--tlds", TLD_RE) or list(dict.fromkeys(DEFAULT_TLDS[a.profile] + region_tlds(region)))
    classes = split_list(a.classes, "--classes", re.compile(r"^\d{1,2}$"))
    project = find_project(a.project)
    now = today()

    lines = disclosure(cands, tlds, a.profile, skip, not a.no_gh)
    if not a.offline:
        print("\n".join(lines))
        if a.plan:
            return EXIT_PASS
        if not a.yes:
            fail(EXIT_USAGE, "nothing was sent. Ask the owner whether these names may go to the services above, then re-run with --yes "
                             "(or use --offline <dir> to replay recorded responses).")
    elif a.plan:
        print("--offline: replaying recorded responses; no network call and no name leaves this machine.")
        return EXIT_PASS
    else:
        print(f"--offline {a.offline}: replaying recorded responses; no network call and no name leaves this machine.")

    if a.offline:
        t: Transport = Replay(Path(a.offline).expanduser().resolve(), spacing=a.spacing)
        mode = "offline replay"
        recorded = sorted(t.fetched)
        date = recorded[0]  # the date on the recordings, never today's: a replay of old answers must not read as current
        n = next_run(project, date)
    else:
        date = now
        n = next_run(project, date)
        raw_dir = confine(project, f"research/names/raw/{date}/run-{n}", what="raw folder")
        raw_dir.mkdir(parents=True, exist_ok=False)
        cache = data_dir() / "cache"
        t = Live(raw_dir, project, cache, use_gh=not a.no_gh, spacing=a.spacing)
        mode = "live"
        recorded = [date]

    chk = Checker(t, tlds, skip)
    cells: list[Cell] = []
    for cand in cands:
        if "domains" not in skip:
            for tld in tlds:
                cells.append(chk.check_domain(cand, tld))
        for src in planned_sources(a.profile, skip):
            cells.append(chk.check_http(cand, src))

    controls = sorted(chk.controls.values(), key=lambda k: k["source"])
    trademark = trademark_links(cands, region, classes)
    manual = manual_links(cands) if a.profile != "software" else []
    meta = {"date": date, "profile": a.profile, "region": region, "candidates": cands, "mode": mode,
            "recorded": recorded[0] if len(recorded) == 1 else f"{recorded[0]} to {recorded[-1]}", "replayed": now}
    md_path = memo_path(project, date, n)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(meta, cells, controls, trademark, manual), encoding="utf-8")

    rep = Report("names", project, renderer="n/a (network screening)")
    for c in cells:
        rep.add(f"{c.candidate}:{c.source}", "skipped" if c.state == UNK else "info", c.target, state=c.state, candidate=c.candidate,
                source=c.source, detail=c.detail, url=c.url, http=c.http, dns=c.dns, raw=c.raw, checked=date)
    rep.extra.update({"banner": BANNER, "profile": a.profile, "region": region, "tlds": tlds, "candidates": cands, "mode": mode,
                      "skipped_sources": sorted(skip), "controls": controls, "trademark_links": trademark, "manual_links": manual,
                      "memo": rel(project, md_path), "checked": date,
                      **({"replayed": now, "recorded": meta["recorded"]} if a.offline else {})})
    rpath = rep.write()

    print(f"\nSCREENING, NOT CLEARANCE ({date}, {mode}{', replayed ' + now if a.offline else ''})")
    for cand in cands:
        print(f"{cand}")
        for c in (x for x in cells if x.candidate == cand):
            print(f"  {c.source:<14} {c.state:<10} {c.detail}")
    nunk = sum(1 for c in cells if c.state == UNK)
    print(f"\nnames: {len(cells)} cells, {nunk} UNKNOWN" + (" (not verified; do not read them as either answer)" if nunk else ""))
    print(f"memo: {md_path}\nreport: {rpath}")
    return EXIT_CANNOT if nunk else EXIT_PASS


if __name__ == "__main__":
    main_guard(main)

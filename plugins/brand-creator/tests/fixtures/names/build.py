"""Builds the recorded-response fixtures for `brand-creator names --offline`.

The bodies are minimised copies of the shapes the real services returned when the method was verified (RDAP domain
object, RDAP 404 error, whois text with its legal footer, the DNS NS answer as the checker stores it). The keys and
URLs are written out by hand on purpose: the tests must not derive their expectations from the code they test.

    python3 tests/fixtures/names/build.py      # rewrites software/, errors/ and ratelimit/ (a test checks they match)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAKEN, GONE = "granite", "zqxvkrmpl"           # neutral candidates: taken everywhere / taken nowhere
CTL = "bc-zz-control-x7q4k9v2m"                # the checker's known-unregistered control label
TLDS = ("com", "io")                           # com goes through RDAP, io through whois (not in the bootstrap)

# (source id, url template, known-taken control name)
HTTP = [
    ("npm", "https://registry.npmjs.org/{n}", "react"),
    ("github", "https://api.github.com/users/{n}", "octocat"),
    ("docker-org", "https://hub.docker.com/v2/orgs/{n}/", "grafana"),
    ("docker-user", "https://hub.docker.com/v2/users/{n}/", "library"),
    ("pypi", "https://pypi.org/pypi/{n}/json", "requests"),
    ("crates", "https://crates.io/api/v1/crates/{n}", "serde"),
    ("brew-formula", "https://formulae.brew.sh/api/formula/{n}.json", "wget"),
    ("brew-cask", "https://formulae.brew.sh/api/cask/{n}.json", "firefox"),
]
FOOTER = ("\n>>> Last update of WHOIS database: 2026-10-17T20:54:21Z <<<\n\nTerms of Use: Access to WHOIS information is provided "
          "to assist persons in determining the contents of a domain name registration record. You agree that you will not "
          "enable high volume, automated, electronic processes that send queries or data to the systems of the Registry "
          "Operator, and that your use is subject to quota and rate limit policies.\n")


def R(status: int, body: str = "{}", headers: dict | None = None, error: str = "", via: str = "https") -> dict:
    return {"status": status, "headers": headers or {}, "body": body, "error": error, "via": via}


def ok(body: str = "{}") -> dict:
    return R(200, body)


def gone(body: str = '{"error":"not found"}') -> dict:
    return R(404, body)


def whois_hit(fqdn: str) -> dict:
    return R(200, f"Domain Name: {fqdn}\nRegistry Domain ID: D1-EXAMPLE\nCreation Date: 2002-01-01T00:00:00Z\nName Server: NS1.EXAMPLE.NET\n" + FOOTER, via="whois")


def whois_miss() -> dict:
    return R(200, "Domain not found." + FOOTER, via="whois")


def dns_ns(*ns: str) -> dict:
    return R(200, json.dumps({"rcode": "NOERROR", "ns": sorted(ns), "authority": [], "truncated": False}, sort_keys=True), via="dns")


def dns_nx() -> dict:
    return R(200, json.dumps({"rcode": "NXDOMAIN", "ns": [], "authority": [6], "truncated": False}, sort_keys=True), via="dns")


def baseline() -> dict[str, list[dict]]:
    f: dict[str, list[dict]] = {}
    boot = {"description": "minimised copy of the IANA RDAP bootstrap shape", "publication": "2026-09-30T23:00:03Z", "version": "1.0",
            "services": [[["com", "net"], ["https://rdap.verisign.com/com/v1/"]], [["dev", "app"], ["https://pubapi.registry.google/rdap/"]]]}
    f["GET https://data.iana.org/rdap/dns.json"] = [ok(json.dumps(boot, sort_keys=True))]
    # .com over RDAP
    rd = "https://rdap.verisign.com/com/v1/domain/"
    f[f"GET {rd}google.com"] = [ok('{"objectClassName":"domain","ldhName":"GOOGLE.COM"}')]
    f[f"GET {rd}{CTL}.com"] = [gone('{"errorCode":404,"title":"Not Found"}')]
    f[f"GET {rd}{TAKEN}.com"] = [ok(f'{{"objectClassName":"domain","ldhName":"{TAKEN.upper()}.COM"}}')]
    f[f"GET {rd}{GONE}.com"] = [gone('{"errorCode":404,"title":"Not Found"}')]
    # .io over whois at the server IANA names
    f["WHOIS whois.iana.org io"] = [R(200, "domain:       IO\nwhois:        whois.nic.io\nstatus:       ACTIVE\nsource:       IANA\n", via="whois")]
    f["WHOIS whois.nic.io google.io"] = [whois_hit("google.io")]
    f[f"WHOIS whois.nic.io {CTL}.io"] = [whois_miss()]
    f[f"WHOIS whois.nic.io {TAKEN}.io"] = [whois_hit(f"{TAKEN}.io")]
    f[f"WHOIS whois.nic.io {GONE}.io"] = [whois_miss()]
    # DNS: resolver controls (com) and the cross-check of every domain
    f["DNS NS google.com"] = [dns_ns("ns1.google.com", "ns2.google.com")]
    f[f"DNS NS {CTL}.com"] = [dns_nx()]
    for t in TLDS:
        f[f"DNS NS {TAKEN}.{t}"] = [dns_ns("ns1.example.net")]
        f[f"DNS NS {GONE}.{t}"] = [dns_nx()]
    # package and handle sources
    for _sid, tpl, taken in HTTP:
        f[f"GET {tpl.format(n=taken)}"] = [ok()]
        f[f"GET {tpl.format(n=CTL)}"] = [gone()]
        f[f"GET {tpl.format(n=TAKEN)}"] = [ok()]
        f[f"GET {tpl.format(n=GONE)}"] = [gone()]
    return f


def errors() -> dict[str, list[dict]]:
    """The taken candidate hits server errors, timeouts and a broken resolver in every source."""
    f = baseline()
    f[f"GET https://rdap.verisign.com/com/v1/domain/{TAKEN}.com"] = [R(503, "<html>maintenance</html>")]
    f[f"WHOIS whois.nic.io {TAKEN}.io"] = [R(0, "", error="TimeoutError: timed out", via="whois")]
    for t in TLDS:
        f[f"DNS NS {TAKEN}.{t}"] = [R(200, json.dumps({"rcode": "SERVFAIL", "ns": [], "authority": [], "truncated": False}), via="dns")]
    for sid, tpl, _t in HTTP:
        f[f"GET {tpl.format(n=TAKEN)}"] = [R(0, "", error="URLError: timed out") if sid in ("npm", "pypi") else R(500, "<html>error</html>")]
    return f


def ratelimit() -> dict[str, list[dict]]:
    """The taken candidate is limited once and then answers (so it is retried); the other is limited twice; GitHub's limit has no Retry-After."""
    f = baseline()
    limited = R(429, "slow down", {"retry-after": "2"})
    f[f"GET https://rdap.verisign.com/com/v1/domain/{TAKEN}.com"] = [limited, ok(f'{{"objectClassName":"domain","ldhName":"{TAKEN.upper()}.COM"}}')]
    f[f"GET https://rdap.verisign.com/com/v1/domain/{GONE}.com"] = [limited, R(429, "slow down", {"retry-after": "2"})]
    for sid, tpl, _t in HTTP:
        if sid == "github":
            f[f"GET {tpl.format(n=TAKEN)}"] = [R(403, '{"message":"API rate limit exceeded"}', {"x-ratelimit-remaining": "0"})]
            continue
        f[f"GET {tpl.format(n=TAKEN)}"] = [limited, ok()]
        f[f"GET {tpl.format(n=GONE)}"] = [limited, R(429, "slow down", {"retry-after": "2"})]
    return f


def write(directory: Path, fixtures: dict[str, list[dict]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for i, key in enumerate(sorted(fixtures)):
        for seq, resp in enumerate(fixtures[key]):
            doc = {"key": key, "seq": seq, "fetched": "2026-10-17", **resp}
            (directory / f"{i:03d}-{seq}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def load(directory: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for f in sorted(directory.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        out.setdefault(d["key"], []).append({k: v for k, v in d.items() if k not in ("key", "seq", "fetched")})
    return out


SCENARIOS = {"software": baseline, "errors": errors, "ratelimit": ratelimit}

if __name__ == "__main__":
    for name, fn in SCENARIOS.items():
        d = HERE / name
        if d.exists() and any(d.iterdir()):
            sys.exit(f"{d} exists; move it aside first (this script never deletes)")
        write(d, fn())
        print(f"wrote {d} ({len(list(d.glob('*.json')))} files)")

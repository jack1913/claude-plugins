"""brand-creator names: replay from recorded fixtures, controls, rate limits, privacy gate, politeness.

Expectations are written out by hand or come from the recorded fixtures (see CONTRACT.md, "Testing"): nothing here asks
check_names for the answer it is being tested on. The default suite never touches the network.
"""
import calendar
import json
import re
import shutil
import socket
import sys
import urllib.request
from pathlib import Path

import pytest
from helpers import ROOT, bc

sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "tests" / "fixtures" / "names"))
import _common  # noqa: E402
import build as fxbuild  # noqa: E402
import check_names as cn  # noqa: E402

FX = ROOT / "tests" / "fixtures" / "names"
FORBIDDEN = re.compile(r"\b(available|free|clear)\b", re.I)
TAKEN, GONE, CTL = fxbuild.TAKEN, fxbuild.GONE, fxbuild.CTL
SOURCES = ["npm", "github", "docker-org", "docker-user", "pypi", "crates", "brew-formula", "brew-cask"]
WORDS = {"REGISTERED", "NOT-FOUND", "UNKNOWN"}


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "acme"
    p.mkdir()
    (p / "BRAND-STATE.md").write_text("---\nslug: acme\nname: Acme\ntier: standard\nphase: P2\n---\n", encoding="utf-8")
    return p


def run(proj, *extra, fixture="software", fx_dir=None, cands=(TAKEN, GONE), tlds="com,io"):
    d = fx_dir or FX / fixture
    return bc("names", *cands, "--tlds", tlds, "--offline", str(d), *extra, project=proj)


def report(proj):
    return json.loads((proj / "assets" / "_checks" / "names.json").read_text(encoding="utf-8"))


def cells(proj):
    return {r["id"]: r for r in report(proj)["results"]}


def mutated(tmp_path, scenario, changes: dict) -> Path:
    data = fxbuild.load(FX / scenario)
    for key, resps in changes.items():
        assert key in data, f"mutation did not apply: no recorded key {key!r}"
        assert data[key] != resps, f"mutation did not change {key!r}"
        data[key] = resps
    d = tmp_path / "fx"
    fxbuild.write(d, data)
    return d


# ---------------------------------------------------------------- replay: the states

def test_fixtures_on_disk_match_the_builder():
    for name, fn in fxbuild.SCENARIOS.items():
        assert fxbuild.load(FX / name) == json.loads(json.dumps(fn())), f"{name}: rerun python3 tests/fixtures/names/build.py"


def test_offline_replay_reports_taken_and_untaken_everywhere(proj):
    r = run(proj)
    assert r.returncode == 0, r.stdout + r.stderr
    c = cells(proj)
    for src in [".com", ".io", *SOURCES]:
        assert c[f"{TAKEN}:{src}"]["state"] == "REGISTERED", src
        assert c[f"{GONE}:{src}"]["state"] == "NOT-FOUND", src
    assert c[f"{TAKEN}:.com"]["dns"] == "NS" and c[f"{GONE}:.com"]["dns"] == "NXDOMAIN"
    rep = report(proj)
    assert rep["tool"] == "names" and rep["status"] == "pass" and len(rep["results"]) == 20
    assert all(x["checked"] == "2026-10-17" for x in rep["results"])
    assert all(k["ok"] for k in rep["controls"]) and {k["source"] for k in rep["controls"]} >= {".com", ".io", "dns", "npm", "github"}


def test_whois_hit_with_a_legal_footer_and_a_miss_with_the_same_footer_are_told_apart(proj):
    """Regression: the footer says 'automated ... quota ... rate limit' on both; neither may be read as a rate limit."""
    run(proj)
    c = cells(proj)
    assert c[f"{TAKEN}:.io"]["state"] == "REGISTERED" and c[f"{GONE}:.io"]["state"] == "NOT-FOUND"


def test_errors_scenario_is_unknown_never_guessed(proj):
    r = run(proj, fixture="errors")
    assert r.returncode == 3, r.stdout + r.stderr
    c = cells(proj)
    for src in [".com", ".io", *SOURCES]:
        assert c[f"{TAKEN}:{src}"]["state"] == "UNKNOWN", src
        assert c[f"{GONE}:{src}"]["state"] == "NOT-FOUND", src  # the untouched candidate is still answered
    assert report(proj)["status"] == "not-verified"
    assert c[f"{TAKEN}:npm"]["detail"].startswith("no answer")
    assert "HTTP 503" in c[f"{TAKEN}:.com"]["detail"]


def test_ratelimit_scenario(proj):
    r = run(proj, fixture="ratelimit")
    assert r.returncode == 3
    c = cells(proj)
    # limited once, then answered: retried and established
    for src in [".com", "npm", "docker-org", "docker-user", "pypi", "crates", "brew-formula", "brew-cask"]:
        assert c[f"{TAKEN}:{src}"]["state"] == "REGISTERED" and "retried once after Retry-After 2s" in c[f"{TAKEN}:{src}"]["detail"], src
        assert c[f"{GONE}:{src}"]["state"] == "UNKNOWN" and "rate-limited" in c[f"{GONE}:{src}"]["detail"], src
    # GitHub's 403 with no quota left and no Retry-After is not retried
    assert c[f"{TAKEN}:github"]["state"] == "UNKNOWN" and "rate-limited (HTTP 403)" in c[f"{TAKEN}:github"]["detail"]
    assert c[f"{GONE}:github"]["state"] == "NOT-FOUND"


# ---------------------------------------------------------------- controls

@pytest.mark.parametrize("source,key,resp", [
    ("npm", "GET https://registry.npmjs.org/" + CTL, fxbuild.ok()),                               # unregistered control wrongly 200
    ("pypi", "GET https://pypi.org/pypi/requests/json", fxbuild.gone()),                          # taken control wrongly 404
    ("crates", "GET https://crates.io/api/v1/crates/serde", fxbuild.R(500, "error")),             # taken control errors
    ("github", "GET https://api.github.com/users/octocat", fxbuild.R(403, "{}", {"x-ratelimit-remaining": "0"})),
])
def test_a_failing_control_turns_the_source_into_unknown(proj, tmp_path, source, key, resp):
    d = mutated(tmp_path, "software", {key: [resp]})
    r = run(proj, fx_dir=d)
    assert r.returncode == 3
    c = cells(proj)
    for cand in (TAKEN, GONE):
        assert c[f"{cand}:{source}"]["state"] == "UNKNOWN" and c[f"{cand}:{source}"]["detail"].startswith("control failed"), source
    others = [s for s in SOURCES if s != source]
    assert all(c[f"{cand}:{s}"]["state"] != "UNKNOWN" for cand in (TAKEN, GONE) for s in others)
    ctl = {k["source"]: k for k in report(proj)["controls"]}
    assert ctl[source]["ok"] is False and ctl[source]["why"]


def test_a_broken_tld_check_is_caught_by_its_control(proj, tmp_path):
    """The case that motivated controls: a whois server that answers 'not found' for a name everyone knows is taken."""
    data = fxbuild.load(FX / "software")
    for lab in ("google", "wikipedia", "microsoft"):  # every known-taken name the checker may try says NOT-FOUND
        data[f"WHOIS whois.nic.io {lab}.io"] = [fxbuild.whois_miss()]
    d = tmp_path / "fx"
    fxbuild.write(d, data)
    r = run(proj, fx_dir=d)
    assert r.returncode == 3
    c = cells(proj)
    assert c[f"{TAKEN}:.io"]["state"] == "UNKNOWN" and "known-taken control returned NOT-FOUND" in c[f"{TAKEN}:.io"]["detail"]
    assert {k["source"]: k["taken"]["tried"] for k in report(proj)["controls"]}[".io"] == ["google", "wikipedia", "microsoft"]
    assert c[f"{TAKEN}:.com"]["state"] == "REGISTERED"


def test_a_free_control_that_is_registered_voids_the_tld(proj, tmp_path):
    d = mutated(tmp_path, "software", {f"GET https://rdap.verisign.com/com/v1/domain/{CTL}.com": [fxbuild.ok('{"objectClassName":"domain"}')]})
    run(proj, fx_dir=d)
    c = cells(proj)
    assert c[f"{GONE}:.com"]["state"] == "UNKNOWN" and "known-unregistered control returned REGISTERED" in c[f"{GONE}:.com"]["detail"]


def test_a_captive_page_answering_200_everywhere_is_caught_by_the_controls(proj, tmp_path):
    html = fxbuild.R(200, "<html>sign in to the wifi</html>")
    changes = {f"GET https://registry.npmjs.org/{n}": [html] for n in ("react", CTL, TAKEN, GONE)}
    d = mutated(tmp_path, "software", changes)
    run(proj, fx_dir=d)
    c = cells(proj)
    assert c[f"{TAKEN}:npm"]["state"] == "UNKNOWN" and "not JSON" in c[f"{TAKEN}:npm"]["detail"]


def test_dns_conflict_and_inference(proj, tmp_path):
    # registry says NOT-FOUND but the name is delegated: conflict, UNKNOWN
    d = mutated(tmp_path, "software", {f"DNS NS {GONE}.com": [fxbuild.dns_ns("ns1.example.net")]})
    run(proj, fx_dir=d)
    c = cells(proj)[f"{GONE}:.com"]
    assert c["state"] == "UNKNOWN" and "conflict" in c["detail"] and c["dns"] == "NS"
    # registry error but the name is delegated: REGISTERED, inferred and labelled as such
    d2 = tmp_path / "fx2"
    d2.mkdir()
    base = fxbuild.load(FX / "software")
    base[f"GET https://rdap.verisign.com/com/v1/domain/{TAKEN}.com"] = [fxbuild.R(503, "maintenance")]
    fxbuild.write(d2, base)
    run(proj, fx_dir=d2)
    c = cells(proj)[f"{TAKEN}:.com"]
    assert c["state"] == "REGISTERED" and c["detail"].startswith("inferred from DNS NS delegation")


def test_failing_dns_controls_do_not_void_the_registry_answer(proj, tmp_path):
    d = mutated(tmp_path, "software", {f"DNS NS {CTL}.com": [fxbuild.dns_ns("hijack.example.net")]})
    run(proj, fx_dir=d)
    c = cells(proj)
    assert c[f"{GONE}:.com"]["state"] == "NOT-FOUND" and c[f"{GONE}:.com"]["dns"] == "UNKNOWN"
    assert "DNS cross-check not verified" in c[f"{GONE}:.com"]["detail"]
    assert {k["source"]: k["ok"] for k in report(proj)["controls"]}["dns"] is False


def test_rdap_that_does_not_answer_falls_back_to_whois_and_says_so(proj, tmp_path):
    """The .pl case seen live: the RDAP server's TLS chain cannot be verified, so every RDAP call errors."""
    data = fxbuild.load(FX / "software")
    boot = json.loads(data["GET https://data.iana.org/rdap/dns.json"][0]["body"])
    boot["services"].append([["pl"], ["https://rdap.dns.pl/"]])
    data["GET https://data.iana.org/rdap/dns.json"] = [fxbuild.ok(json.dumps(boot))]
    dead = fxbuild.R(0, "", error="URLError: [SSL: CERTIFICATE_VERIFY_FAILED]")
    for lab in ("google", "wikipedia", "microsoft", CTL, TAKEN, GONE):
        data[f"GET https://rdap.dns.pl/domain/{lab}.pl"] = [dead]
    data["WHOIS whois.iana.org pl"] = [fxbuild.R(200, "domain: PL\nwhois: whois.dns.pl\n", via="whois")]
    data["WHOIS whois.dns.pl google.pl"] = [fxbuild.R(200, "DOMAIN NAME: google.pl\ncreated: 2002.09.19 13:00:00\n", via="whois")]
    data[f"WHOIS whois.dns.pl {TAKEN}.pl"] = [fxbuild.R(200, f"DOMAIN NAME: {TAKEN}.pl\ncreated: 2010.01.01 13:00:00\n", via="whois")]
    data[f"WHOIS whois.dns.pl {GONE}.pl"] = [fxbuild.R(200, f"No information available about domain name {GONE}.pl in the Registry NASK database.\n", via="whois")]
    data[f"WHOIS whois.dns.pl {CTL}.pl"] = [fxbuild.R(200, "No information available about domain name x.pl in the Registry NASK database.\n", via="whois")]
    data[f"DNS NS {TAKEN}.pl"] = [fxbuild.dns_ns("ns1.example.net")]
    data[f"DNS NS {GONE}.pl"] = [fxbuild.dns_nx()]
    d = tmp_path / "fx"
    fxbuild.write(d, data)
    run(proj, fx_dir=d, tlds="pl")
    c = cells(proj)
    assert c[f"{TAKEN}:.pl"]["state"] == "REGISTERED" and "whois used" in c[f"{TAKEN}:.pl"]["detail"]
    assert c[f"{GONE}:.pl"]["state"] == "NOT-FOUND"


def test_missing_recording_is_unknown_with_the_key_named(proj, tmp_path):
    d = tmp_path / "fx"
    data = fxbuild.load(FX / "software")
    del data["GET https://pypi.org/pypi/requests/json"]
    fxbuild.write(d, data)
    run(proj, fx_dir=d)
    c = cells(proj)[f"{TAKEN}:pypi"]
    assert c["state"] == "UNKNOWN" and "no recorded response for GET https://pypi.org/pypi/requests/json" in c["detail"]


# ---------------------------------------------------------------- determinism and output

def test_offline_replay_is_deterministic(proj, tmp_path):
    run(proj)
    first = (proj / "assets" / "_checks" / "names.json").read_text(encoding="utf-8")
    md1 = (proj / "research" / "names" / "2026-10-17-check.md").read_text(encoding="utf-8")
    run(proj)
    assert (proj / "assets" / "_checks" / "names.json").read_text(encoding="utf-8") == first.replace("2026-10-17-check.md", "2026-10-17-check-2.md")
    md2 = (proj / "research" / "names" / "2026-10-17-check-2.md").read_text(encoding="utf-8")
    assert md1 == md2  # same bytes, and the first memo was not overwritten
    # and a different working directory or a freshly made project gives the same report
    other = tmp_path / "other"
    other.mkdir()
    (other / "BRAND-STATE.md").write_text((proj / "BRAND-STATE.md").read_text(encoding="utf-8"), encoding="utf-8")
    run(other)
    assert (other / "assets" / "_checks" / "names.json").read_text(encoding="utf-8") == first


def test_no_forbidden_words_in_any_output(proj, tmp_path):
    for scenario in ("software", "errors", "ratelimit"):
        r = run(proj, fixture=scenario)
        assert r.returncode in (0, 3)
        texts = [r.stdout, r.stderr, (proj / "assets" / "_checks" / "names.json").read_text(encoding="utf-8")]
        texts += [p.read_text(encoding="utf-8") for p in (proj / "research" / "names").glob("*-check*.md")]
        for t in texts:
            assert not FORBIDDEN.search(t), (scenario, FORBIDDEN.search(t).group(0))
    cons = bc("names", TAKEN, "--profile", "consumer", "--region", "PL", "--offline", str(FX / "software"), "--tlds", "com", project=proj)
    assert not FORBIDDEN.search(cons.stdout + cons.stderr)


def test_every_cell_uses_one_of_the_three_states_and_unknown_is_a_skip(proj):
    run(proj, fixture="errors")
    for r in report(proj)["results"]:
        assert r["state"] in WORDS
        assert (r["status"] == "skipped") == (r["state"] == "UNKNOWN")


def test_memo_has_the_banner_a_checked_date_per_row_and_the_controls(proj):
    run(proj)
    md = (proj / "research" / "names" / "2026-10-17-check.md").read_text(encoding="utf-8")
    assert md.splitlines()[0] == "# Name screening 2026-10-17"
    assert "Screening, not clearance." in md
    rows = [ln for ln in md.splitlines() if ln.startswith(f"| {TAKEN} |") or ln.startswith(f"| {GONE} |")]
    assert len(rows) == 2 + 20 and all(ln.rstrip().endswith("| 2026-10-17 |") for ln in rows)  # 2 summary rows + 20 detail rows, each dated
    assert "## Controls" in md and "## Trademark search links (owner-run)" in md and "recheck" in md.lower()


def test_report_follows_the_contract_shape(proj):
    run(proj)
    rep = report(proj)
    assert set(rep) >= {"tool", "version", "inputs_sha", "inputs", "renderer", "results", "status"}
    assert rep["version"] == json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
    assert all({"id", "status", "label"} <= set(r) for r in rep["results"])


# ---------------------------------------------------------------- profiles, tlds, trademark links

def test_consumer_profile_has_no_registries_and_lists_manual_handles(proj):
    r = bc("names", TAKEN, "--profile", "consumer", "--region", "PL", "--offline", str(FX / "software"), project=proj)
    srcs = {x["source"] for x in report(proj)["results"]}
    assert not srcs & set(SOURCES), srcs
    assert srcs == {".com", ".pl", ".eu"} or srcs <= {".com", ".pl", ".eu"}, srcs  # PL: country code and EU
    manual = report(proj)["manual_links"]
    assert [m["candidate"] for m in manual] == [TAKEN]
    assert {x["service"] for x in manual[0]["links"]} >= {"Instagram", "TikTok", "YouTube", "Facebook", "LinkedIn", "X"}
    assert f"https://www.instagram.com/{TAKEN}/" in {x["url"] for x in manual[0]["links"]}
    assert "Social handles (manual)" in (proj / "research" / "names" / "2026-10-17-check.md").read_text(encoding="utf-8")
    assert r.returncode in (0, 3)


def test_software_profile_has_no_manual_handles_and_personal_picks_com_and_me(proj):
    run(proj)
    assert report(proj)["manual_links"] == []
    bc("names", TAKEN, "--profile", "personal", "--offline", str(FX / "software"), project=proj)
    assert report(proj)["tlds"] == ["com", "me"] and report(proj)["manual_links"]


def test_tlds_come_from_profile_and_region(proj):
    def tlds(*a):
        bc("names", TAKEN, "--offline", str(FX / "software"), *a, project=proj)
        return report(proj)["tlds"]
    assert tlds() == ["com", "dev", "app", "io", "ai"]
    assert tlds("--region", "PL") == ["com", "dev", "app", "io", "ai", "pl", "eu"]
    assert tlds("--region", "US") == ["com", "dev", "app", "io", "ai", "us"]
    assert tlds("--region", "GB") == ["com", "dev", "app", "io", "ai", "co.uk"]
    assert tlds("--tlds", ".com,dev") == ["com", "dev"]


def test_trademark_links_are_owner_run_and_regional(proj):
    bc("names", TAKEN, "--region", "PL", "--classes", "9,42", "--tlds", "com", "--offline", str(FX / "software"), project=proj)
    links = report(proj)["trademark_links"][0]["links"]
    by = {x["office"]: x for x in links}
    tm = next(v for k, v in by.items() if k.startswith("EUIPO TMview"))
    assert tm["url"] == f"https://www.tmdn.org/tmview/#/tmview/results?page=1&pageSize=30&criteria=C&basicSearch={TAKEN}&fo=Y&offices=PL,EM,WO"
    assert "9, 42" in tm["note"]
    assert by["WIPO Global Brand Database"]["kind"] == "manual only" and "forbid" in by["WIPO Global Brand Database"]["note"]
    assert by["UPRP e-wyszukiwarka (Poland)"]["url"] == "https://ewyszukiwarka.pue.uprp.gov.pl/"
    assert "USPTO trademark search" in by and "EUIPO eSearch plus" in by
    bc("names", TAKEN, "--region", "DE", "--tlds", "com", "--offline", str(FX / "software"), project=proj)
    de = {x["office"]: x for x in report(proj)["trademark_links"][0]["links"]}
    assert "UPRP e-wyszukiwarka (Poland)" not in de and "National trademark office" in de


# ---------------------------------------------------------------- usage errors

def test_usage_errors(proj, tmp_path):
    assert bc("names", "two words", "--offline", str(FX / "software"), project=proj).returncode == 2
    assert bc("names", "-bad", "--offline", str(FX / "software"), project=proj).returncode == 2
    assert bc("names", "café", "--offline", str(FX / "software"), project=proj).returncode == 2
    assert bc("names", TAKEN, "--spacing", "0.1", "--offline", str(FX / "software"), project=proj).returncode == 2
    assert bc("names", TAKEN, "--spacing", "1.5", "--offline", str(FX / "software"), project=proj).returncode == 2
    assert bc("names", TAKEN, "--skip", "bogus", "--offline", str(FX / "software"), project=proj).returncode == 2
    assert bc("names", TAKEN, "--region", "Poland", "--offline", str(FX / "software"), project=proj).returncode == 2
    empty = tmp_path / "empty"
    empty.mkdir()
    r = bc("names", TAKEN, "--offline", str(empty), project=proj)
    assert r.returncode == 2 and "no recorded responses" in r.stderr
    r = bc("names", TAKEN, "--offline", str(FX / "software"), cwd=tmp_path)
    assert r.returncode == 2 and "no brand project found" in r.stderr
    r = bc("names", project=proj)
    assert r.returncode == 2


def test_candidates_are_lowercased_and_deduplicated(proj):
    bc("names", "Granite", "GRANITE", "granite", "--tlds", "com", "--offline", str(FX / "software"), project=proj)
    assert report(proj)["candidates"] == ["granite"]


# ---------------------------------------------------------------- privacy gate (in process, with every network door shut)

@pytest.fixture
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket.socket, "sendto", boom)
    monkeypatch.setattr(cn.subprocess, "run", boom)


def test_without_yes_nothing_is_sent_and_the_services_are_listed(proj, capsys, no_network, monkeypatch):
    monkeypatch.setenv("BRAND_CREATOR_DATA", str(proj / "data"))
    with pytest.raises(_common.CliError) as e:
        cn.main([TAKEN, "zqxvkrmpl", "--project", str(proj), "--region", "PL"])
    assert e.value.code == 2 and "--yes" in e.value.message
    out = capsys.readouterr().out
    assert out.startswith("PRIVACY")
    assert f"({TAKEN}, zqxvkrmpl)" in out
    for host in ("data.iana.org", "whois.iana.org", "registry.npmjs.org", "api.github.com", "hub.docker.com", "pypi.org", "crates.io",
                 "formulae.brew.sh", "DNS resolver"):
        assert host in out, host
    assert ".com .dev .app .io .ai .pl .eu" in out
    assert not (proj / "research").exists() and not (proj / "assets").exists()


def test_plan_exits_0_without_network(proj, capsys, no_network):
    assert cn.main([TAKEN, "--project", str(proj), "--plan", "--profile", "consumer"]) == 0
    out = capsys.readouterr().out
    assert "registry.npmjs.org" not in out and "hub.docker.com" not in out  # consumer: no registries
    assert "data.iana.org" in out and "(through the gh CLI" not in out


def test_skip_removes_a_service_from_the_plan_and_from_the_run(proj, capsys, no_network):
    cn.main([TAKEN, "--project", str(proj), "--plan", "--skip", "github,docker", "--no-gh"])
    out = capsys.readouterr().out
    assert "api.github.com" not in out and "hub.docker.com" not in out and "registry.npmjs.org" in out


def test_offline_makes_no_network_call(proj, capsys, no_network):
    rc = cn.main([TAKEN, GONE, "--project", str(proj), "--tlds", "com,io", "--offline", str(FX / "software")])
    assert rc == 0
    assert "no network call" in capsys.readouterr().out


# ---------------------------------------------------------------- live code paths with a fake network

class FakeNet:
    """Answers Live's HTTP, whois and DNS doors from a recorded fixture and logs everything that was sent."""

    def __init__(self, monkeypatch, data):
        self.data, self.used, self.http, self.whois, self.dns, self.fetches = data, {}, [], [], [], 0
        monkeypatch.setattr(cn.Live, "_fetch", self._fetch)
        monkeypatch.setattr(socket, "create_connection", self._conn)
        monkeypatch.setattr(cn, "system_resolvers", lambda: ["192.0.2.53"])
        monkeypatch.setattr(cn, "dns_query_ns", self._dns)
        monkeypatch.setattr(cn.time, "sleep", lambda s: None)
        real_init = cn.Live.__init__

        def no_spacing(live, *a, **kw):   # Transport's default `sleep` is time.sleep itself, bound when the class was defined: the patch above never reaches it
            kw.setdefault("sleep", lambda s: None)
            real_init(live, *a, **kw)
        monkeypatch.setattr(cn.Live, "__init__", no_spacing)
        monkeypatch.setattr(cn.Live, "gh_ready", lambda self: False)

    def _next(self, key):
        lst = self.data.get(key)
        if lst is None:
            raise OSError(f"fake network has no answer for {key}")
        i = self.used.get(key, 0)
        self.used[key] = i + 1
        return lst[min(i, len(lst) - 1)]

    def _fetch(self, url, headers):
        self.http.append(url)
        if url == cn.BOOTSTRAP_URL:
            self.fetches += 1
        d = self._next(f"GET {url}")
        if d["status"] == 0:
            raise OSError(d["error"])
        return d["status"], {k.lower(): v for k, v in d["headers"].items()}, d["body"]

    def _conn(self, addr, timeout=None):
        server, port = addr
        assert port == 43
        outer = self

        class S:
            def __enter__(s):
                return s

            def __exit__(s, *a):
                return False

            def settimeout(s, t):
                pass

            def sendall(s, b):
                s.q = b.decode().strip()
                outer.whois.append((server, s.q))
                s.out = outer._next(f"WHOIS {server} {s.q}")["body"].encode()

            def recv(s, n):
                chunk, s.out = s.out[:n], s.out[n:]
                return chunk
        return S()

    def _dns(self, name, resolvers):
        self.dns.append(name)
        return json.loads(self._next(f"DNS NS {name}")["body"])


def live(proj, monkeypatch, *args, data=None):
    net = FakeNet(monkeypatch, data or fxbuild.load(FX / "software"))
    monkeypatch.setenv("BRAND_CREATOR_DATA", str(proj / "data"))
    monkeypatch.setenv("BRAND_CREATOR_TODAY", "2026-10-17")
    rc = cn.main([TAKEN, GONE, "--project", str(proj), "--tlds", "com,io", "--yes", *args])
    return rc, net


def test_live_run_sends_only_candidates_and_controls_to_disclosed_hosts(proj, monkeypatch, capsys):
    rc, net = live(proj, monkeypatch)
    assert rc == 0
    disclosure = capsys.readouterr().out.split("SCREENING")[0]
    hosts = {re.match(r"https://([^/]+)", u).group(1) for u in net.http}
    rdap_hosts = {"rdap.verisign.com"}  # named by the bootstrap, disclosed by category
    for h in hosts - rdap_hosts:
        assert h in disclosure, h
    allowed = {TAKEN, GONE, CTL, "react", "octocat", "grafana", "library", "requests", "serde", "wget", "firefox", "google", "wikipedia", "microsoft"}
    for u in net.http[1:]:  # [0] is the bootstrap
        names = re.findall(r"(?:domain|users|orgs|crates|formula|cask|pypi|registry\.npmjs\.org)/([a-z0-9-]+)", u)
        assert names and all(n.split(".")[0] in allowed for n in names), u
    for server, q in net.whois:
        assert server in ("whois.iana.org", "whois.nic.io")
        assert q == "io" or q.split(".")[0] in allowed, q
    assert all(n.split(".")[0] in allowed for n in net.dns)
    assert not any("@" in u for u in net.http)


def test_live_raw_responses_are_saved_and_replay_to_the_same_report(proj, monkeypatch, tmp_path):
    rc, _net = live(proj, monkeypatch)
    live_report = report(proj)
    raw = proj / "research" / "names" / "raw" / "2026-10-17" / "run-1"
    files = sorted(raw.glob("*.json"))
    assert len(files) >= 48
    first = json.loads(files[0].read_text(encoding="utf-8"))
    assert {"key", "seq", "status", "headers", "body", "error", "via", "fetched"} <= set(first)
    # the IANA whois answer keeps only the lines the replay needs
    iana = json.loads(next(raw.glob("whois-whois-iana-org-io-*.json")).read_text(encoding="utf-8"))
    assert iana["body"].splitlines() == ["domain:       IO", "whois:        whois.nic.io", "status:       ACTIVE", "source:       IANA"]
    assert live_report["results"][0]["raw"] and all(p.startswith("research/names/raw/2026-10-17/run-1/") for r in live_report["results"] for p in r["raw"])
    # replay the saved folder in a second project
    other = tmp_path / "other"
    other.mkdir()
    (other / "BRAND-STATE.md").write_text((proj / "BRAND-STATE.md").read_text(encoding="utf-8"), encoding="utf-8")
    r = bc("names", TAKEN, GONE, "--tlds", "com,io", "--offline", str(raw), project=other)
    assert r.returncode == 0, r.stdout + r.stderr
    again = report(other)
    strip = lambda rep: [(x["id"], x["state"], x["dns"]) for x in rep["results"]]  # noqa: E731
    assert strip(again) == strip(live_report)


def test_raw_files_keep_no_stranger_profile_data_and_are_cut(proj, monkeypatch):
    at = chr(64)  # built at run time so this file holds no e-mail-looking text
    data = fxbuild.load(FX / "software")
    profile = json.dumps({"login": TAKEN, "type": "User", "name": "Some Person", "email": f"someone{at}example.test", "location": "Somewhere",
                          "created_at": "2011-01-01T00:00:00Z", "public_repos": 3})
    data[f"GET https://api.github.com/users/{TAKEN}"] = [fxbuild.ok(profile)]
    data[f"GET https://registry.npmjs.org/{TAKEN}"] = [fxbuild.ok('{"description":"contact a.person' + at + 'example.test ' + "x" * 20000 + '"}')]
    data[f"GET https://pypi.org/pypi/{TAKEN}/json"] = [fxbuild.ok('{"info":{"author_email":"maintainer' + at + 'example.test"}}')]
    live(proj, monkeypatch, data=data)
    raw = proj / "research" / "names" / "raw" / "2026-10-17" / "run-1"
    gh = json.loads(next(raw.glob(f"get-https-api-github-com-users-{TAKEN}-*.json")).read_text(encoding="utf-8"))
    assert json.loads(gh["body"]) == {"created_at": "2011-01-01T00:00:00Z", "login": TAKEN, "public_repos": 3, "type": "User"}
    everything = "".join(p.read_text(encoding="utf-8") for p in raw.glob("*.json"))
    assert "example.test" not in everything and "[email removed]" in everything
    npm = json.loads(next(raw.glob(f"get-https-registry-npmjs-org-{TAKEN}-*.json")).read_text(encoding="utf-8"))
    assert 4000 < len(npm["body"]) <= 4096  # cut at 4 KB (a few characters shorter once the address was replaced)
    assert cells(proj)[f"{TAKEN}:npm"]["state"] == "REGISTERED" and cells(proj)[f"{TAKEN}:github"]["state"] == "REGISTERED"


MINIMISE_CASES = {
    "docker": ("GET https://hub.docker.com/v2/users/x/",
               '{"id":"0a1b","uuid":"u","orgname":"x","username":"x","full_name":"Some Person","location":"Nowhere","company":"Some Co",'
               '"gravatar_url":"https://www.gravatar.com/avatar/7510e100f7ebeca4a0b8c3c617349295?s=80","gravatar_email":"","type":"User","date_joined":"2013-03-24T00:40:48Z"}',
               {"username": "x", "orgname": "x", "type": "User", "date_joined": "2013-03-24T00:40:48Z"},
               ("Some Person", "Nowhere", "Some Co", "gravatar", "7510e100")),
    "npm": ("GET https://registry.npmjs.org/x", '{"name":"x","author":{"name":"Some Person","url":"https://example.test/p"},"maintainers":[{"name":"Other Person"}],'
            '"dist-tags":{"latest":"1.0.0"}}', {"name": "x", "dist-tags": {"latest": "1.0.0"}}, ("Some Person", "Other Person")),
    "pypi": ("GET https://pypi.org/pypi/x/json", '{"info":{"name":"x","version":"1","author":"Some Person","maintainer":"Other Person","summary":"s"}}',
             {"info": {"name": "x", "version": "1", "summary": "s"}}, ("Some Person", "Other Person")),
    "crates": ("GET https://crates.io/api/v1/crates/x", '{"crate":{"id":"x","name":"x","max_version":"1.0.0","homepage":"https://example.test"},'
               '"versions":[{"published_by":{"name":"Some Person"}}]}', {"crate": {"id": "x", "name": "x", "max_version": "1.0.0"}}, ("Some Person", "published_by")),
}


@pytest.mark.parametrize("case", sorted(MINIMISE_CASES))
def test_json_bodies_of_known_services_are_cut_to_an_allow_list(case):
    key, body, want, gone = MINIMISE_CASES[case]
    out = cn.Live.minimise(key, body, cn.RAW_LIMIT)
    assert json.loads(out) == want
    assert not any(g in out for g in gone)


def test_error_bodies_keep_their_message():
    out = cn.Live.minimise("GET https://hub.docker.com/v2/orgs/x/", '{"message":"Not found","stack":"internal"}', cn.RAW_LIMIT)
    assert json.loads(out) == {"message": "Not found"}


def test_rdap_vcards_keep_only_their_version_line_and_the_rest_survives():
    body = json.dumps({"ldhName": "x.test", "status": ["active"], "entities": [
        {"roles": ["registrant"], "vcardArray": ["vcard", [["version", {}, "text", "4.0"], ["fn", {}, "text", "Some Person"],
                                                          ["tel", {"type": ["voice"]}, "uri", "tel:+1.5550100"],
                                                          ["adr", {}, "text", ["", "", "1 Example Street", "Town", "", "00-000", "Poland"]]]]},
        {"roles": ["registrar"], "entities": [{"roles": ["abuse"], "vcardArray": ["vcard", [["fn", {}, "text", "Other Person"]]]}]}],
        "events": [{"eventAction": "registration", "eventDate": "2002-09-19T00:00:00Z"}]})
    out = cn.Live.minimise("GET https://rdap.example.test/domain/x.test", body, cn.RAW_LIMIT)
    doc = json.loads(out)
    assert doc["ldhName"] == "x.test" and doc["events"][0]["eventDate"] == "2002-09-19T00:00:00Z" and doc["entities"][0]["roles"] == ["registrant"]
    assert doc["entities"][0]["vcardArray"] == ["vcard", [["version", {}, "text", "4.0"]]]
    assert not any(w in out for w in ("Some Person", "Other Person", "5550100", "Example Street", "00-000"))


def test_an_rdap_body_too_long_to_parse_is_cut_before_its_first_vcard():
    body = '{"ldhName":"x.test","entities":[{"vcardArray":["vcard",[["fn",{},"text","Some Person"' + "x" * 300
    out = cn.Live.minimise("GET https://rdap.example.test/domain/x.test", body, cn.RAW_LIMIT)
    assert "Some Person" not in out and out.startswith('{"ldhName":"x.test"')


WHOIS_PL = """DOMAIN NAME:                    x.pl
registrant type:                organization
nameservers:                    ns1.example.test.
                                ns2.example.test.
created:                        2002.09.19 13:00:00
last modified:                  2026.08.17 12:47:01
dnssec:                         Unsigned

REGISTRAR:
Some Registrar, Inc.
1 Example Street, Suite 3
00-000 Town
Tel: +1.5550100
https://registrar.example.test/

Registrant Name: Some Person
Registrant Phone: +48.5550100
WHOIS displays data with a delay not exceeding 15 minutes
"""


def test_whois_bodies_keep_dates_status_and_name_servers_but_no_contact_blocks():
    out = cn.Live.minimise("WHOIS whois.example.test x.pl", WHOIS_PL, cn.RAW_LIMIT)
    assert out.splitlines() == ["DOMAIN NAME:                    x.pl", "nameservers:                    ns1.example.test.",
                                "                                ns2.example.test.", "created:                        2002.09.19 13:00:00",
                                "last modified:                  2026.08.17 12:47:01", "dnssec:                         Unsigned", "REGISTRAR:"]
    assert cn.interpret_whois(cn.Resp(200, {}, out))[0] == "REGISTERED"  # still readable by the replay
    gone = cn.Live.minimise("WHOIS whois.example.test x.pl", "Registrant Name: Some Person\nNo match for domain \"X.PL\"\nTel: +1.5550100\n", cn.RAW_LIMIT)
    assert gone == 'No match for domain "X.PL"' and cn.interpret_whois(cn.Resp(200, {}, gone))[0] == "NOT-FOUND"


def test_every_recorded_live_body_in_a_run_survives_the_filters_for_replay(proj, monkeypatch):
    live(proj, monkeypatch)
    raw = proj / "research" / "names" / "raw" / "2026-10-17" / "run-1"
    live_report = report(proj)
    run(proj, fx_dir=raw)
    again = report(proj)
    assert [(x["id"], x["state"]) for x in again["results"]] == [(x["id"], x["state"]) for x in live_report["results"]]


# ---------------------------------------------------------------- one run, one folder; a replay keeps the recording's date

def test_a_second_live_run_the_same_day_gets_its_own_raw_folder_and_leaves_the_first_alone(proj, monkeypatch):
    live(proj, monkeypatch)
    base = proj / "research" / "names" / "raw" / "2026-10-17"
    first = {p.name: p.read_text(encoding="utf-8") for p in (base / "run-1").glob("*.json")}
    memo1 = (proj / "research" / "names" / "2026-10-17-check.md").read_text(encoding="utf-8")
    data = fxbuild.load(FX / "software")
    data[f"GET https://registry.npmjs.org/{TAKEN}"] = [fxbuild.ok('{"name":"changed"}')]
    live(proj, monkeypatch, data=data)
    assert sorted(p.name for p in base.iterdir()) == ["run-1", "run-2"]
    assert {p.name: p.read_text(encoding="utf-8") for p in (base / "run-1").glob("*.json")} == first, "run 1's evidence was rewritten"
    assert (proj / "research" / "names" / "2026-10-17-check.md").read_text(encoding="utf-8") == memo1
    assert report(proj)["memo"].endswith("2026-10-17-check-2.md") and all("/run-2/" in r for x in report(proj)["results"] for r in x["raw"])


def test_replaying_a_folder_that_holds_two_runs_is_refused(proj, monkeypatch):
    live(proj, monkeypatch)
    live(proj, monkeypatch)
    r = run(proj, fx_dir=proj / "research" / "names" / "raw" / "2026-10-17")
    assert r.returncode == 2 and "several runs (run-1, run-2)" in r.stdout + r.stderr


def test_an_old_replay_is_labelled_with_the_recording_date_not_today(proj, monkeypatch):
    live(proj, monkeypatch)  # records 2026-10-17
    raw = proj / "research" / "names" / "raw" / "2026-10-17" / "run-1"
    other = proj.parent / "later"
    other.mkdir()
    (other / "BRAND-STATE.md").write_text((proj / "BRAND-STATE.md").read_text(encoding="utf-8"), encoding="utf-8")
    r = bc("names", TAKEN, GONE, "--tlds", "com,io", "--offline", str(raw), project=other, env={"BRAND_CREATOR_TODAY": "2026-11-30"})
    assert r.returncode == 0, r.stdout + r.stderr
    rep = report(other)
    assert rep["checked"] == "2026-10-17" and rep["replayed"] == "2026-11-30" and rep["memo"] == "research/names/2026-10-17-check.md"
    assert all(x["checked"] == "2026-10-17" for x in rep["results"])
    md = (other / "research" / "names" / "2026-10-17-check.md").read_text(encoding="utf-8")
    assert "Checked: 2026-10-17 (recorded 2026-10-17, replayed 2026-11-30" in md and "2026-11-30-check" not in r.stdout
    assert "replayed 2026-11-30" in r.stdout


def test_a_recording_without_a_fetched_date_is_refused(proj, tmp_path):
    d = tmp_path / "nofetch"
    shutil.copytree(FX / "software", d)
    f = sorted(d.glob("*.json"))[0]
    doc = json.loads(f.read_text(encoding="utf-8"))
    del doc["fetched"]
    f.write_text(json.dumps(doc), encoding="utf-8")
    r = run(proj, fx_dir=d)
    assert r.returncode == 2 and "no valid \"fetched\" date" in r.stdout + r.stderr


def test_live_run_writes_nothing_outside_the_project_and_the_data_dir(proj, monkeypatch, tmp_path):
    before = {p for p in tmp_path.rglob("*")}
    live(proj, monkeypatch)
    new = {p for p in tmp_path.rglob("*")} - before
    assert all(proj in p.parents or p == proj for p in new), [p for p in new if proj not in p.parents]


# ---------------------------------------------------------------- bootstrap cache

def _live(tmp_path, proj, monkeypatch, now):
    fetched = []

    def fetch(self, url, headers):
        fetched.append(url)
        return 200, {}, json.dumps({"publication": "x", "services": [[["com"], ["https://rdap.example.test/com/"]]], "version": "1.0"})
    monkeypatch.setattr(cn.Live, "_fetch", fetch)
    t = cn.Live(None, proj, tmp_path / "cache", spacing=0.3, sleep=lambda s: None, wall=lambda: now[0])
    return t, fetched


def test_bootstrap_cache_is_used_for_24_hours_then_refetched(tmp_path, proj, monkeypatch):
    now = [1_000_000.0]
    t, fetched = _live(tmp_path, proj, monkeypatch, now)
    doc, err = t.bootstrap(["com"])
    assert err == "" and doc["services"][0][0] == ["com"] and len(fetched) == 1
    now[0] += 24 * 3600 - 1
    t.bootstrap(["com"])
    assert len(fetched) == 1, "still fresh one second before 24 h"
    now[0] += 2
    t.bootstrap(["com"])
    assert len(fetched) == 2, "expired after 24 h"
    now[0] += 60
    t.bootstrap(["com"])
    assert len(fetched) == 2, "the refetch renewed the cache"
    cached = json.loads((tmp_path / "cache" / "iana-rdap-dns.json").read_text(encoding="utf-8"))
    assert cached["fetched_at"] == now[0] - 60 and cached["source"] == "https://data.iana.org/rdap/dns.json"


def test_an_expired_cache_is_not_used_silently_when_the_download_fails(tmp_path, proj, monkeypatch):
    now = [1_000_000.0]
    t, fetched = _live(tmp_path, proj, monkeypatch, now)
    t.bootstrap(["com"])
    now[0] += 25 * 3600

    def down(self, url, headers):
        raise OSError("network down")
    monkeypatch.setattr(cn.Live, "_fetch", down)
    doc, err = t.bootstrap(["com"])
    assert doc is None and "download failed" in err and "network down" in err


def test_a_corrupt_cache_is_refetched(tmp_path, proj, monkeypatch):
    now = [1_000_000.0]
    t, fetched = _live(tmp_path, proj, monkeypatch, now)
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "iana-rdap-dns.json").write_text("{not json", encoding="utf-8")
    doc, err = t.bootstrap(["com"])
    assert doc and len(fetched) == 1


def test_bootstrap_failure_makes_every_domain_cell_unknown(proj, monkeypatch):
    data = fxbuild.load(FX / "software")
    data["GET https://data.iana.org/rdap/dns.json"] = [fxbuild.R(500, "oops")]
    rc, _ = live(proj, monkeypatch, data=data)
    assert rc == 3
    c = cells(proj)
    assert c[f"{TAKEN}:.com"]["state"] == "UNKNOWN" and "bootstrap" in c[f"{TAKEN}:.com"]["detail"]
    assert c[f"{TAKEN}:npm"]["state"] == "REGISTERED"


# ---------------------------------------------------------------- politeness: 429, spacing, user agent

def _fake_transport(proj, tmp_path, responses, now=None):
    sleeps, calls = [], []
    clock = [0.0]

    def sleep(s):
        sleeps.append(s)
        clock[0] += s
    t = cn.Live(None, proj, tmp_path / "c", spacing=0.5, sleep=sleep, clock=lambda: clock[0], wall=lambda: now if now is not None else 0.0)

    def fetch(self, url, headers):
        calls.append(url)
        return responses.pop(0)
    t._fetch = fetch.__get__(t)
    return t, sleeps, calls


def test_429_with_retry_after_waits_then_retries_once(proj, tmp_path):
    t, sleeps, calls = _fake_transport(proj, tmp_path, [(429, {"retry-after": "3"}, ""), (200, {}, "{}")])
    r = t.http("https://example.test/a")
    assert r.status == 200 and len(calls) == 2 and 3 in sleeps and "retried once after Retry-After 3s" in r.note


def test_429_twice_gives_up_after_one_retry(proj, tmp_path):
    t, sleeps, calls = _fake_transport(proj, tmp_path, [(429, {"retry-after": "1"}, ""), (429, {"retry-after": "1"}, ""), (200, {}, "{}")])
    r = t.http("https://example.test/a")
    assert r.status == 429 and len(calls) == 2
    assert cn.interpret_http(r)[0] == "UNKNOWN"


def test_retry_after_over_the_cap_or_missing_is_not_waited_for(proj, tmp_path):
    t, sleeps, calls = _fake_transport(proj, tmp_path, [(429, {"retry-after": "3600"}, "")])
    r = t.http("https://example.test/a")
    assert r.status == 429 and len(calls) == 1 and max(sleeps, default=0) < 1 and "over the 30s cap" in r.note
    t2, sleeps2, calls2 = _fake_transport(proj, tmp_path, [(429, {}, "")])
    r2 = t2.http("https://example.test/a")
    assert len(calls2) == 1 and "without Retry-After" in r2.note


def test_retry_after_as_an_http_date(proj, tmp_path):
    now = calendar.timegm((2026, 10, 17, 12, 0, 0))
    t, sleeps, calls = _fake_transport(proj, tmp_path, [(429, {"retry-after": "Sat, 17 Oct 2026 12:00:07 GMT"}, ""), (200, {}, "{}")], now=now)
    t.http("https://example.test/a")
    assert 7 in sleeps


def test_403_with_retry_after_is_treated_like_429(proj, tmp_path):
    t, sleeps, calls = _fake_transport(proj, tmp_path, [(403, {"retry-after": "2"}, ""), (200, {}, "{}")])
    assert t.http("https://api.example.test/x").status == 200 and len(calls) == 2


def test_spacing_between_calls_to_one_host(proj, tmp_path):
    t, sleeps, calls = _fake_transport(proj, tmp_path, [(200, {}, "{}")] * 4)
    t.http("https://a.example.test/1")
    t.http("https://b.example.test/1")  # another host: no wait
    assert sleeps == []
    t.http("https://a.example.test/2")  # same host straight away: waits the spacing
    assert sleeps and 0.3 <= sleeps[-1] <= 1.0


def test_user_agent_is_one_generic_constant_without_an_at_sign(monkeypatch, proj, tmp_path):
    assert "@" not in _common.USER_AGENT and _common.USER_AGENT.startswith("brand-creator/")
    seen = []

    class Resp:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return b"{}"

    def fake_urlopen(req, timeout=None):
        seen.append(req)
        return Resp()
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    t = cn.Live(None, proj, tmp_path / "c")
    t._fetch("https://crates.io/api/v1/crates/serde", {})
    assert len(seen) == 1
    ua = seen[0].get_header("User-agent")
    assert ua == _common.USER_AGENT and "@" not in ua


def test_no_script_hard_codes_a_user_agent():
    for p in sorted((ROOT / "scripts").rglob("*.py")):
        text = p.read_text(encoding="utf-8")
        for m in re.finditer(r"""['"]User-Agent['"]\s*:\s*(.{0,40})""", text, re.I):
            assert m.group(1).startswith("USER_AGENT"), f"{p.relative_to(ROOT)}: {m.group(0)}"
        if p.name != "_common.py":
            assert not re.search(r"brand-creator/\d+\.\d+", text), f"{p.relative_to(ROOT)} spells out a User-Agent version; use USER_AGENT"
    assert "@" not in _common.USER_AGENT


def test_gh_is_used_only_when_logged_in_and_not_with_no_gh(monkeypatch, proj, tmp_path):
    calls = []

    class CP:
        def __init__(self, rc, out=""):
            self.returncode, self.stdout, self.stderr = rc, out, ""

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if cmd[:3] == ["gh", "auth", "status"]:
            return CP(0)
        return CP(1, "HTTP/2.0 404 Not Found\r\nX-Ratelimit-Remaining: 4990\r\n\r\n{\"message\":\"Not Found\"}")
    monkeypatch.setattr(cn.subprocess, "run", fake_run)
    monkeypatch.setattr(cn.shutil, "which", lambda n: "/usr/bin/gh")
    t = cn.Live(None, proj, tmp_path / "c", spacing=0.3, sleep=lambda s: None)
    r = t._http_once("https://api.github.com/users/zzz", None)
    assert r.status == 404 and r.via == "gh" and r.headers == {"x-ratelimit-remaining": "4990"}
    assert ["gh", "api", "-i", "users/zzz"] in calls
    calls.clear()
    t2 = cn.Live(None, proj, tmp_path / "c", use_gh=False, spacing=0.3, sleep=lambda s: None)
    monkeypatch.setattr(cn.Live, "_fetch", lambda self, u, h: (200, {}, "{}"))
    r2 = t2._http_once("https://api.github.com/users/zzz", None)
    assert r2.via == "https" and calls == []


# ---------------------------------------------------------------- parsers against hand-written wire data

@pytest.mark.parametrize("text,state", [
    ("Domain Name: example.io\nRegistry Domain ID: D1\nCreation Date: 2002-01-01T00:00:00Z\n", "REGISTERED"),
    ("DOMAIN NAME: example.pl\ncreated: 2002.09.19 13:00:00\n", "REGISTERED"),
    ("domain: example.de\nnserver: ns1.example.net\nStatus: connect\n", "REGISTERED"),
    ("Domain not found.\n>>> Last update <<<\nautomated ... rate limit policies", "NOT-FOUND"),
    ("DOMAIN NOT FOUND\n", "NOT-FOUND"),
    ("Domain: example.eu\nStatus: AVAILABLE\n", "NOT-FOUND"),
    ("Domain: example.de\nStatus: free\n", "NOT-FOUND"),
    ('No match for "EXAMPLE.CO.UK".\n', "NOT-FOUND"),
    ("No information available about domain name example.pl in the Registry NASK database.\n", "NOT-FOUND"),
    ("Query limit exceeded. Try again later.\n", "UNKNOWN"),
    ("Welcome to the registry.\n", "UNKNOWN"),
    ("", "UNKNOWN"),
])
def test_whois_text_interpretation(text, state):
    assert cn.interpret_whois(cn.Resp(200, {}, text))[0] == state


def test_whois_connection_failure_is_unknown():
    assert cn.interpret_whois(cn.Resp(0, error="timed out"))[0] == "UNKNOWN"


def test_dns_query_bytes_match_the_wire_format():
    want = bytes.fromhex("1234" "0100" "0001" "0000" "0000" "0000" "06" + b"google".hex() + "03" + b"com".hex() + "00" "0002" "0001")
    assert cn.build_ns_query("google.com", 0x1234) == want
    assert cn.build_ns_query("google.com.", 0x1234) == want


GOOGLE_NS_ANSWER = bytes.fromhex(
    "1234" "8180" "0001" "0002" "0000" "0000"
    "06" + b"google".hex() + "03" + b"com".hex() + "00" "0002" "0001"
    "c00c" "0002" "0001" "00000e10" "0006" "03" + b"ns1".hex() + "c00c"      # ns1.google.com via a compression pointer
    "c00c" "0002" "0001" "00000e10" "0006" "03" + b"ns2".hex() + "c00c")


def test_dns_answer_with_compressed_names():
    out = cn.parse_ns_response(GOOGLE_NS_ANSWER, 0x1234)
    assert out["rcode"] == "NOERROR" and out["ns"] == ["ns1.google.com", "ns2.google.com"] and out["authority"] == []


def test_dns_nxdomain_with_an_soa_in_the_authority_section():
    pkt = bytes.fromhex(
        "1234" "8183" "0001" "0000" "0001" "0000"
        "03" + b"abc".hex() + "03" + b"com".hex() + "00" "0002" "0001"
        "c010" "0006" "0001" "00000384" "0000")  # name pointer into the question, type SOA, empty rdata
    out = cn.parse_ns_response(pkt, 0x1234)
    assert out["rcode"] == "NXDOMAIN" and out["ns"] == [] and out["authority"] == [6]


def test_dns_answer_for_another_query_is_refused():
    with pytest.raises(ValueError):
        cn.parse_ns_response(GOOGLE_NS_ANSWER, 0x9999)
    with pytest.raises(ValueError):
        cn.parse_ns_response(GOOGLE_NS_ANSWER[:8], 0x1234)
    loop = bytes.fromhex("1234" "8180" "0001" "0000" "0000" "0000" "c00c" "0002" "0001")  # pointer to itself
    with pytest.raises(ValueError):
        cn.parse_ns_response(loop, 0x1234)


def test_http_interpretation():
    I = cn.interpret_http  # noqa: E741
    R = cn.Resp
    assert I(R(200, {}, "{}"))[0] == "REGISTERED" and I(R(404))[0] == "NOT-FOUND"
    assert I(R(429))[0] == "UNKNOWN" and I(R(403, {"x-ratelimit-remaining": "0"}))[0] == "UNKNOWN"
    assert "rate-limited" in I(R(403, {"x-ratelimit-remaining": "0"}))[1] and "refused" in I(R(403))[1]
    assert I(R(500))[0] == "UNKNOWN" and I(R(0, error="boom"))[0] == "UNKNOWN"
    assert I(R(200, {}, "<html>"), json_body=True)[0] == "UNKNOWN"


def test_retry_after_parser():
    assert cn.retry_after_seconds("5", 0) == 5.0 and cn.retry_after_seconds("0", 0) == 0.0
    assert cn.retry_after_seconds(None, 0) is None and cn.retry_after_seconds("soon", 0) is None
    assert cn.retry_after_seconds("Sat, 17 Oct 2026 12:00:07 GMT", calendar.timegm((2026, 10, 17, 12, 0, 0))) == 7.0


# ---------------------------------------------------------------- wiring

def test_the_entry_point_dispatches_names_and_documents_it():
    r = bc("help")
    assert "names <candidate>..." in r.stdout
    assert bc("names", "--help").returncode == 0
    assert (ROOT / "scripts" / "check_names.py.lock").is_file()


def test_the_script_is_standard_library_only():
    head = (ROOT / "scripts" / "check_names.py").read_text(encoding="utf-8").split('"""')[0]
    assert "dependencies = []" in head


# ---------------------------------------------------------------- the one live smoke (manual)

@pytest.mark.requires_network
def test_live_smoke_two_neutral_candidates(proj, tmp_path):
    """Manual: BRAND_CREATOR_LIVE=1 pytest tests/test_names.py -k live_smoke. Sends two neutral words to the real services."""
    r = bc("names", "granite", "zqxvkrmpl", "--tlds", "com,dev,io", "--yes", project=proj, timeout=600)
    assert r.returncode in (0, 3), r.stdout + r.stderr
    c = cells(proj)
    assert c["granite:.com"]["state"] == "REGISTERED" and c["zqxvkrmpl:.com"]["state"] == "NOT-FOUND"
    assert {x["state"] for x in c.values()} <= WORDS
    assert not FORBIDDEN.search(r.stdout)
    assert list((proj / "research" / "names" / "raw").glob("*/*/*.json"))

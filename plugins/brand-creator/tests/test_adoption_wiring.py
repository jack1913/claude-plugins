"""adoption wiring: the links, form fields, handlers, test hooks, ids and scripts of a repository's source, recorded before and after a redesign
(read only, ripgrep). The record is adoption.json `wiring`; the cascade never searches it.

The target is tests/fixtures/target-site, a synthetic site. Expected values are written out by hand from its files, never taken from the module under
test. Reading rules not worth a fixture file are shown by example against wiring.scan_text; the extension list is checked against a hand-written list."""
import json
import os
import re
import shutil
import stat
from pathlib import Path

import pytest
from helpers import ROOT, bc, make_project, mutate_json, path_without

import adoptdata as ad
import wiring

pytestmark = pytest.mark.requires_rg
FIX = ROOT / "tests" / "fixtures" / "target-site"

# item -> the files that hold it, counted by hand in tests/fixtures/target-site (files in the order the scan reads them: sorted)
EXPECTED = {
    "field:address.street": ["src/Address.tsx"],
    "field:email": ["index.html", "src/Signup.vue"],
    "field:note": ["index.html"],
    "field:password": ["src/Signup.vue"],
    "field:plan": ["index.html"],
    "field:q": ["src/Header.jsx"],
    "handler:@submit.prevent=onSubmit": ["src/Signup.vue"],
    "handler:on:click={cancel}": ["src/Cancel.svelte"],
    "handler:onClick={() => onMenu({ open: true })}": ["src/Header.jsx"],
    "handler:onclick=track('signup')": ["index.html"],
    "handler:v-on:click=track": ["src/Signup.vue"],
    "hook:data-analytics-form=signup": ["index.html"],
    "hook:data-cy=email-input": ["index.html"],
    "hook:data-cy=site-header": ["src/Header.jsx"],
    "hook:data-gtm-event=signup-click": ["index.html"],
    "hook:data-qa=cancel-button": ["src/Cancel.svelte"],
    "hook:data-test=signup-form": ["src/Signup.vue"],
    "hook:data-testid=logo-link": ["index.html"],
    "hook:data-testid=nav-pricing": ["src/Header.jsx"],
    "hook:data-track-click=nav-products": ["index.html"],
    "id:email": ["index.html"],
    "id:item-static": ["src/Header.jsx"],
    "id:main": ["index.html"],
    "id:search-box": ["src/Header.jsx"],
    "id:signup-email": ["src/Signup.vue"],
    "id:signup-form": ["index.html"],
    "id:top": ["index.html"],
    "link:#main": ["index.html"],
    "link:/": ["index.html"],
    "link:/login": ["src/Signup.vue"],
    "link:/pricing": ["src/Header.jsx"],
    "link:/products?sort=new#list": ["index.html"],
    "link:/signup": ["index.html"],
    "link:/signup/express": ["index.html"],
    "link:{`/account/${user.id}`}": ["src/Header.jsx"],
    "script:https://analytics.example.com/tag.js": ["index.html"],
    "script:js/app.js": ["index.html"],
}


def tree(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns, p.read_bytes()) for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture
def site(tmp_path) -> Path:
    r = tmp_path / "site"
    shutil.copytree(FIX, r)
    (r / "ignored").mkdir()
    (r / "ignored" / "page.html").write_text('<a href="/ignored-only" data-testid="ignored-only">hidden by .gitignore</a>\n')   # made here: a fixture folder named in .gitignore would not be committed
    return r


@pytest.fixture
def proj(tmp_path):
    return make_project(tmp_path, tier="full")


def surveyed(proj, site, label="site"):
    r = bc("adoption", "survey", "--repo", f"{site}={label}", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    return r


def wire(proj, *args, label="site", env=None):
    return bc("adoption", "wiring", "--repo", label, *args, project=proj, env=env)


def load(proj) -> dict:
    return json.loads((proj / "adoption.json").read_text())


def record(proj, which="before", rid="r1") -> dict:
    return load(proj)["wiring"][rid][which]


# ---------------------------------------------------------------- the source is read, kind by kind

def test_the_wiring_of_a_site_is_read_from_its_source_with_every_kind(proj, site):
    surveyed(proj, site)
    md = (proj / "ADOPTION.md").read_bytes()
    r = wire(proj, "--before")
    assert r.returncode == 0, r.stdout + r.stderr
    rec = record(proj)
    assert rec["items"] == EXPECTED and list(rec["items"]) == sorted(EXPECTED)
    assert rec["date"] == "2026-10-17" and rec["files"] == 5 and isinstance(rec["head"], str)       # index.html, Address.tsx, Cancel.svelte, Header.jsx, Signup.vue
    rows = {x["id"]: x for x in json.loads((proj / "assets" / "_checks" / "adoption-wiring.json").read_text())["results"]}
    assert set(rows) == {"read-only:site", "wiring:site", "wiring:scope"} and rows["read-only:site"]["status"] == "pass"
    assert rows["wiring:site"]["status"] == "info" and rows["wiring:site"]["detail"] == "link 8, field 6, handler 5, hook 9, id 7, script 2 (37 items)"
    assert rows["wiring:scope"]["status"] == "info" and "5 source file(s) read; 3 more of the same kinds left out by the keep rules" in rows["wiring:scope"]["detail"]
    # what the rules leave out: a link element, base, a bare # and a comment; a meta, an anchor and a slot name; a script's body; an id with a space
    flat = json.dumps(rec["items"])
    for left_out in ("/css/site.css", "/app/", "link:#\"", "viewport", "legacy-anchor", "footer", "not-markup", "not-a-field", "commented-out", "note text", "id:note"):
        assert left_out not in flat, left_out
    assert "wiring" in load(proj) and (proj / "ADOPTION.md").read_bytes() == md             # the list renders the bytes it rendered before
    assert bc("adoption", "verify", project=proj).returncode == 0


def test_what_counts_as_wiring_is_decided_by_the_tag_the_attribute_and_the_value():
    def scan(text):
        return wiring.scan_text(text)[0]
    assert scan('<!-- <a href="/gone"> --><a href="/kept">x</a>') == ["link:/kept"]
    assert scan("<a href=/plain id=raw>") == []                                              # an unquoted value is not read
    assert scan('<link href="/a.css"><use href="#i"><image href="/i.png"><base href="/b/"><style href="/s"></style><script href="/s.js"></script>') == []
    assert scan('<Link href="/c">x</Link><a href="">e</a><a href="#">h</a><a href="#x">y</a>') == ["link:/c", "link:#x"]
    assert scan('<Link to="/t"><form action="/f"><button formAction="/g"><button formaction="/h">') == ["link:/t", "link:/f", "link:/g", "link:/h"]
    assert scan('<meta name="a"><a name="b"></a><iframe name="c"><param name="d"><slot name="e"><map name="f"><object name="g"><input name="ok"><Field name={"x"}>') == ["field:ok", 'field:{"x"}']
    assert scan('<b onClick={go} onclick="go()" @click.stop="x" v-on:input="y" on:change={z} onerror="" ondrag={} onchange="c()">') == [
        "handler:onClick={go}", "handler:onclick=go()", "handler:@click.stop=x", "handler:v-on:input=y", "handler:on:change={z}", "handler:onchange=c()"]
    assert scan('<p data-testid="a" data-test="b" data-cy="c" data-qa="d" data-track-x="e" data-analytics="f" data-event-name="g" data-gtm-id="h" '
                'data-testimonial="no" data-other="no">') == [
        "hook:data-testid=a", "hook:data-test=b", "hook:data-cy=c", "hook:data-qa=d", "hook:data-track-x=e", "hook:data-analytics=f",
        "hook:data-event-name=g", "hook:data-gtm-id=h"]
    assert scan('<p id="ok"><p id="a b"><p id="{{ x }}"><p id={dyn}><p id="">') == ["id:ok"]
    assert scan('<script src="./js/a.js?v=1"></script><script src="/b.js"></script><script src={url}></script><img src="/not.png">') == [
        "script:js/a.js", "script:/b.js", "script:{url}"]
    assert scan('<script>var s = \'<a href="/in-script" id="x">\';</script><style>a[href="/css"] {}</style><a href="/after">') == ["link:/after"]
    assert scan('<a href="/a\n     b"\n   id="multi"\n>') == ["link:/a b", "id:multi"]                  # white space squashed, a tag may span lines
    assert scan('<input <%= "checked" if x %> name="after-erb"><input <?php echo 1; ?> name="after-php">') == ["field:after-erb", "field:after-php"]
    assert scan('register("a"); {...register(\'b\', { required: true })}; sw.register("c"); registerUser("d"); register("")') == ["field:a", "field:b"]
    long = "/" + "x" * 200
    (item,) = scan(f'<a href="{long}">')
    assert item == "link:" + long[:120] and len(item) == len("link:") + 120


def test_braces_are_balanced_to_three_levels_and_a_deeper_value_is_counted_not_read():
    items, deep = wiring.scan_text('<a to={a({ b: { c: 1 } })} id="three">')
    assert items == ["link:{a({ b: { c: 1 } })}", "id:three"] and deep == 0
    items, deep = wiring.scan_text('<a to={a({ b: { c: { d: 1 } } })} id="after">')
    assert items == ["id:after"] and deep == 1                                                 # the value is not read, the next attribute still is


def test_a_file_is_read_for_wiring_by_exactly_the_listed_extensions(tmp_path):
    exts = ["html", "htm", "jsx", "tsx", "js", "ts", "mjs", "vue", "svelte", "astro", "erb", "ejs", "hbs", "handlebars", "njk", "liquid", "twig", "php", "mdx"]
    others = ["md", "css", "json", "txt", "py", "xml", "svg", "yaml"]
    repo = tmp_path / "exts"
    (repo / "pages").mkdir(parents=True)
    for e in exts + others:
        (repo / "pages" / f"p.{e}").write_text(f'<a href="/{e}">x</a>\n')
    proj = make_project(tmp_path, tier="full")
    assert bc("adoption", "survey", "--repo", f"{repo}=exts", project=proj).returncode == 0
    r = wire(proj, "--before", label="exts")
    assert r.returncode == 0, r.stderr
    got = {i: f for i, f in record(proj)["items"].items()}
    assert got == {f"link:/{e}": [f"pages/p.{e}"] for e in exts}


# ---------------------------------------------------------------- read only, proven

def test_the_wiring_scan_never_edits_the_repository_and_proves_it(proj, site, tmp_path):
    surveyed(proj, site)
    before = tree(site)
    r = wire(proj, "--before")
    assert r.returncode == 0 and "read-only:site" in r.stdout
    assert tree(site) == before                                                                 # bytes, sizes and modification times
    rep = json.loads((proj / "assets" / "_checks" / "adoption-wiring.json").read_text())
    ro = next(x for x in rep["results"] if x["id"] == "read-only:site")
    assert ro["status"] == "pass" and rep["status"] == "pass" and rep["tool"] == "adoption-wiring"
    assert not (site / "ADOPTION.md").exists() and not (site / "adoption.json").exists()
    # a repository that something else writes to during the scan fails the row, exits 1 and stores nothing: a ripgrep that edits index.html on its second run
    shim = tmp_path / "shim"
    shim.mkdir()
    counter = tmp_path / "calls"
    f = shim / "rg"
    f.write_text(f'#!/bin/bash\nn=$(cat "{counter}" 2>/dev/null || echo 0)\nn=$((n+1))\necho $n > "{counter}"\n'
                 f'if [ "$n" -ge 2 ]; then echo "<p>changed</p>" >> "{site}/index.html"; fi\nexec {shutil.which("rg")} "$@"\n')
    f.chmod(f.stat().st_mode | stat.S_IEXEC)
    assert "index.html" in f.read_text()
    again = load(proj)
    r = wire(proj, "--before", "--again", env={"PATH": f"{shim}:{os.environ['PATH']}"})
    assert r.returncode == 1, r.stdout + r.stderr
    rep = json.loads((proj / "assets" / "_checks" / "adoption-wiring.json").read_text())
    ro = next(x for x in rep["results"] if x["id"] == "read-only:site")
    assert ro["status"] == "fail" and "Nothing was stored" in ro["detail"] and rep["status"] == "fail"
    assert load(proj) == again                                                                  # the failed scan stored nothing


def test_generated_and_vendored_files_are_not_read_for_wiring(proj, site):
    for held in ("dist/bundle.js", "vendor/widget.js", "public/app.min.js", "ignored/page.html"):
        assert re.search(r'href="/[a-z]+-only"', (site / held).read_text()), held             # each would give a link and a hook if it were read
    surveyed(proj, site)
    assert wire(proj, "--before").returncode == 0
    flat = json.dumps(record(proj))
    for only in ("bundle-only", "vendor-only", "minified-only", "ignored-only"):
        assert only not in flat, only
    rows = {x["id"]: x for x in json.loads((proj / "assets" / "_checks" / "adoption-wiring.json").read_text())["results"]}
    assert "3 more of the same kinds left out by the keep rules" in rows["wiring:scope"]["detail"]      # dist/bundle.js, vendor/widget.js, public/app.min.js


# ---------------------------------------------------------------- the baseline

def test_a_before_record_is_kept_unless_asked_again(proj, site):
    surveyed(proj, site)
    assert wire(proj, "--before").returncode == 0
    first = record(proj)
    assert wire(proj, "--after").returncode == 0
    both = load(proj)["wiring"]["r1"]
    with (site / "index.html").open("a") as f:
        f.write('<a href="/added-later" data-testid="added-later">new</a>\n')
    r = wire(proj, "--before")
    assert r.returncode == 1 and "pass --again" in r.stderr and "baseline" in r.stderr
    assert load(proj)["wiring"]["r1"] == both                                                   # nothing changed, and no report says it did
    r = wire(proj, "--before", "--again")
    assert r.returncode == 0, r.stderr
    now = load(proj)["wiring"]["r1"]
    assert "link:/added-later" in now["before"]["items"] and "link:/added-later" not in first["items"]
    assert now["after"] == both["after"]                                                        # --again replaces the baseline and nothing else
    assert wire(proj, "--after", "--again").returncode == 2                                     # --again is for --before only


def test_after_needs_a_before(proj, site):
    surveyed(proj, site)
    r = wire(proj, "--after")
    assert r.returncode == 2 and "no before record for site" in r.stderr and "--before" in r.stderr
    assert load(proj)["wiring"] == {} and not (proj / "assets" / "_checks" / "adoption-wiring.json").exists()
    assert wire(proj, "--before").returncode == 0
    assert wire(proj, "--after").returncode == 0
    rec = load(proj)["wiring"]["r1"]
    assert rec["after"]["items"] == rec["before"]["items"] == EXPECTED                          # nothing changed between the two scans


def test_wiring_needs_a_surveyed_repository_and_one_of_before_or_after(proj, site, tmp_path):
    r = bc("adoption", "wiring", "--repo", "site", "--before", project=proj)
    assert r.returncode == 2 and "no adoption.json" in r.stderr                                 # nothing surveyed yet
    surveyed(proj, site)
    r = wire(proj, "--before", label="other")
    assert r.returncode == 2 and "not a surveyed repository" in r.stderr and "site" in r.stderr
    r = wire(proj)
    assert r.returncode == 2 and "one of the arguments --before --after is required" in r.stderr
    r = wire(proj, "--before", "--after")
    assert r.returncode == 2 and "not allowed with" in r.stderr
    assert bc("adoption", "wiring", "--before", project=proj).returncode == 2                 # --repo is required
    assert load(proj)["wiring"] == {}


def test_a_missing_ripgrep_is_exit_3_with_the_fix_and_stores_nothing_for_wiring(proj, site, tmp_path):
    surveyed(proj, site)
    r = wire(proj, "--before", env={"PATH": path_without(tmp_path, "rg")})
    assert r.returncode == 3 and "ripgrep" in r.stderr and "Install" in r.stderr
    assert load(proj)["wiring"] == {} and not (proj / "assets" / "_checks" / "adoption-wiring.json").exists()


# ---------------------------------------------------------------- the record in adoption.json

def test_the_wiring_record_is_not_searched_by_the_cascade(proj, site):
    surveyed(proj, site)
    assert wire(proj, "--before").returncode == 0
    assert "Header.jsx" in (proj / "adoption.json").read_text()                                 # the repository's file name is in the data: it is what was found
    r = bc("check", "--cascade", "Header.jsx", project=proj)
    cas = next(x for x in json.loads((proj / "assets" / "_checks" / "check.json").read_text())["results"] if x["id"] == "cascade:Header.jsx")
    assert cas["status"] == "pass" and cas["hits"] == [], cas
    assert ad.TARGET_KEYS.count("wiring") == 1
    assert r.returncode == 0, r.stdout + r.stderr


def test_an_adoption_json_from_before_wiring_still_verifies_and_takes_a_record(proj, site):
    surveyed(proj, site)
    doc = load(proj)
    assert doc.pop("wiring") == {}                                                              # a list written by an earlier version has no such key
    (proj / "adoption.json").write_bytes(ad.dumps(doc))
    assert bc("adoption", "verify", project=proj).returncode == 0
    assert wire(proj, "--before").returncode == 0
    assert set(load(proj)["wiring"]["r1"]) == {"before"} and bc("adoption", "verify", project=proj).returncode == 0


@pytest.mark.parametrize("how,needle", [("repo", "never surveyed"), ("items", "does not map to a list of strings"), ("noitems", "has no `items` object"),
                                          ("shape", "not an object keyed by repository id"), ("entry", "wiring of r1 is not an object")])
def test_verify_fails_a_wiring_record_of_an_unknown_repository_or_the_wrong_shape(proj, site, how, needle):
    surveyed(proj, site)
    assert wire(proj, "--before").returncode == 0

    def change(d):
        w = d["wiring"]
        if how == "repo":
            w["r9"] = w.pop("r1")
        elif how == "items":
            w["r1"]["before"]["items"]["link:/"] = "index.html"
        elif how == "noitems":
            del w["r1"]["before"]["items"]
        elif how == "entry":
            w["r1"] = []
        else:
            d["wiring"] = []
    mutate_json(proj / "adoption.json", change)
    r = bc("adoption", "verify", project=proj)
    assert r.returncode == 1 and needle in r.stderr, r.stderr
    assert bc("adoption", "status", project=proj).returncode == 1                                # nothing builds on it

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
from helpers import ROOT, bc, make_project, mutate, mutate_json, path_without, report

import adoptdata as ad
import wiring

pytestmark = pytest.mark.requires_rg
FIX = ROOT / "tests" / "fixtures" / "target-site"
GOLDEN = ROOT / "tests" / "fixtures" / "adoption-md" / "ADOPTION-before-wiring.txt"      # the ADOPTION.md the survey below rendered before it had a wiring section

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
    now, frame = (proj / "ADOPTION.md").read_text(), md.decode().index("## How this list is applied")
    assert "wiring" in load(proj) and "## Wiring kept" in now                                   # the list shows the record, and everything around the new section is as it was
    assert now.startswith(md.decode()[:frame]) and now.endswith(md.decode()[frame:])
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
    assert r.returncode == 2 and "one of the arguments --before --after --compare --drop is required" in r.stderr
    r = wire(proj, "--before", "--after")
    assert r.returncode == 2 and "not allowed with" in r.stderr
    for pair in (("--before", "--compare"), ("--after", "--drop", "link:/::x"), ("--compare", "--drop", "link:/::x")):
        r = wire(proj, *pair)
        assert r.returncode == 2 and "not allowed with" in r.stderr, pair
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
                                          ("shape", "not an object keyed by repository id"), ("entry", "wiring of r1 is not an object"),
                                          ("dropped", "`dropped` is not an object of item to reason"), ("noreason", "an empty reason")])
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
        elif how == "dropped":
            w["r1"]["dropped"] = ["link:/"]
        elif how == "noreason":
            w["r1"]["dropped"] = {"link:/": "  "}
        else:
            d["wiring"] = []
    mutate_json(proj / "adoption.json", change)
    r = bc("adoption", "verify", project=proj)
    assert r.returncode == 1 and needle in r.stderr, r.stderr
    assert bc("adoption", "status", project=proj).returncode == 1                                # nothing builds on it


# ---------------------------------------------------------------- compare, drop, the check row and ADOPTION.md

def edit(path: Path, old: str, new: str) -> None:
    """Change a file of the repository and prove the change applied (for the tests that must not call mutate())."""
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not found in {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def drops(proj, *pairs, label="site", env=None):
    args = []
    for pair in pairs:
        args += ["--drop", pair]
    return wire(proj, *args, label=label, env=env)


def record_entry(proj, rid="r1") -> dict:
    return load(proj)["wiring"][rid]


def check_row(proj, label="site") -> dict:
    return next(x for x in report(proj, "check")["results"] if x["id"] == f"adoption:wiring:{label}")


def wiring_section(md: str) -> list[str]:
    return md[md.index("## Wiring kept"):md.index("## How this list is applied")].rstrip("\n").split("\n")


# the whole form is one block in index.html: dropping it loses ten items (field:email stays, Signup.vue has it too)
FORM_LOST = ["field:note", "field:plan", "handler:onclick=track('signup')", "hook:data-analytics-form=signup", "hook:data-cy=email-input",
             "hook:data-gtm-event=signup-click", "id:email", "id:signup-form", "link:/signup", "link:/signup/express"]


def test_compare_lists_what_a_redesign_lost_and_fails_until_it_is_dropped_with_a_reason(proj, site):
    surveyed(proj, site)
    assert wire(proj, "--before").returncode == 0
    r = wire(proj, "--compare")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "against the before record of 2026-10-17 (37 items recorded, 37 found now)" in r.stdout
    assert "lost, not recorded as dropped: 0\n" in r.stdout and "dropped with a reason: 0\n" in r.stdout and "new items: 0\n" in r.stdout
    assert "wiring compare: PASS" in r.stdout
    # a redesign: the pricing link and its test hook are renamed, the plan select is gone
    mutate(site / "src" / "Header.jsx", 'to="/pricing" data-testid="nav-pricing"', 'to="/plans" data-testid="nav-plans"')
    mutate(site / "index.html", '<select name="plan"><option value="free">Free</option></select>', "")
    r = wire(proj, "--compare")
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stdout.splitlines()[1:6] == ["lost, not recorded as dropped: 3",
                                          "  field:plan (was in index.html)",
                                          "  hook:data-testid=nav-pricing (was in src/Header.jsx)",
                                          "  link:/pricing (was in src/Header.jsx)",
                                          "dropped with a reason: 0"], r.stdout
    assert "new items: 2\n" in r.stdout                                                          # hook:data-testid=nav-plans, link:/plans
    assert "wiring compare: FAIL. 3 item(s)" in r.stdout and '--drop "ITEM::REASON"' in r.stdout
    # one drop, with the owner's reason: two losses remain, and the drop is listed with its reason
    r = drops(proj, "link:/pricing::the pricing page moved to /plans")
    assert r.returncode == 0, r.stdout + r.stderr
    r = wire(proj, "--compare")
    assert r.returncode == 1
    lines = r.stdout.splitlines()
    assert lines[1:5] == ["lost, not recorded as dropped: 2", "  field:plan (was in index.html)", "  hook:data-testid=nav-pricing (was in src/Header.jsx)",
                          "dropped with a reason: 1"] and lines[5] == "  link:/pricing: the pricing page moved to /plans", r.stdout
    # both remaining losses dropped in one call: the comparison passes and still lists every reason
    assert drops(proj, "field:plan::the plan is chosen in the account now", "hook:data-testid=nav-pricing::the end-to-end test uses nav-plans").returncode == 0
    r = wire(proj, "--compare")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.splitlines()[1:8] == ["lost, not recorded as dropped: 0", "dropped with a reason: 3", "  field:plan: the plan is chosen in the account now",
                                          "  hook:data-testid=nav-pricing: the end-to-end test uses nav-plans", "  link:/pricing: the pricing page moved to /plans",
                                          "new items: 2", "wiring compare: PASS. Every item of the before record is still there or was dropped with a reason."], r.stdout


def test_compare_reads_the_repository_now_and_writes_nothing(proj, site, tmp_path):
    surveyed(proj, site)
    assert wire(proj, "--before").returncode == 0
    with (site / "index.html").open("a") as f:
        f.write('<a href="/added-later" data-testid="added-later">new</a>\n')
    held, mine = tree(site), tree(proj)
    r = wire(proj, "--compare")
    assert r.returncode == 0 and "new items: 2\n" in r.stdout and "(37 items recorded, 39 found now)" in r.stdout, r.stdout + r.stderr   # it read the site as it is now
    assert tree(site) == held and tree(proj) == mine                                            # no file of the repository or of the project changed: no record, no report, no ADOPTION.md
    # it proves its own read: a repository something else writes to while it is read gives exit 1 and no verdict about wiring
    shim = tmp_path / "shim"
    shim.mkdir()
    counter = tmp_path / "calls"
    f = shim / "rg"
    f.write_text(f'#!/bin/bash\nn=$(cat "{counter}" 2>/dev/null || echo 0)\nn=$((n+1))\necho $n > "{counter}"\n'
                 f'if [ "$n" -ge 2 ]; then echo "<p>changed</p>" >> "{site}/index.html"; fi\nexec {shutil.which("rg")} "$@"\n')
    f.chmod(f.stat().st_mode | stat.S_IEXEC)
    mine = tree(proj)
    r = wire(proj, "--compare", env={"PATH": f"{shim}:{os.environ['PATH']}"})
    assert r.returncode == 1 and "changed while it was read" in r.stderr and "wiring compare" not in r.stdout, r.stdout + r.stderr
    assert tree(proj) == mine
    # no ripgrep is exit 3 with the fix, a repository that was never surveyed or has no before record is exit 2
    r = wire(proj, "--compare", env={"PATH": path_without(tmp_path, "rg")})
    assert r.returncode == 3 and "ripgrep" in r.stderr and "Install" in r.stderr
    assert wire(proj, "--compare", label="other").returncode == 2
    fresh = make_project(tmp_path / "second", slug="second")
    surveyed(fresh, site)
    r = wire(fresh, "--compare")
    assert r.returncode == 2 and "no before record for site" in r.stderr and "--before" in r.stderr


def test_a_drop_needs_an_item_of_the_before_record_and_a_reason(proj, site, tmp_path):
    surveyed(proj, site)
    r = drops(proj, "link:/pricing::moved")
    assert r.returncode == 2 and "no before record for site" in r.stderr and load(proj)["wiring"] == {}
    with (site / "index.html").open("a") as f:
        f.write('<a href="/legacy::route">an item that holds the separator</a>\n')
    assert wire(proj, "--before").returncode == 0
    md = (proj / "ADOPTION.md").read_bytes()
    for bad, needle in (("link:/pricing", "needs ITEM::REASON"),                                   # no separator
                        ("link:/pricing::", "has no reason"), ("link:/pricing::   ", "has no reason"),
                        ("link:/nowhere::gone", "is not an item of the before record"),
                        ("::gone", "is not an item of the before record"), ("", "needs ITEM::REASON")):
        r = drops(proj, bad)
        assert r.returncode == 2 and needle in r.stderr, (bad, r.stderr)
        assert "dropped" not in record_entry(proj)
    r = drops(proj, "link:/pricing::moved to /plans", "link:/nowhere::gone")                     # one bad spec stores none
    assert r.returncode == 2 and "link:/nowhere" in r.stderr and "dropped" not in record_entry(proj)
    assert (proj / "ADOPTION.md").read_bytes() == md
    # a good drop is stored under the repository, sorted, with the owner's words; the list stays consistent
    r = drops(proj, "link:/pricing::moved to /plans", "id:main::the anchor is renamed  to   #content")
    assert r.returncode == 0, r.stdout + r.stderr
    assert record_entry(proj)["dropped"] == {"id:main": "the anchor is renamed to #content", "link:/pricing": "moved to /plans"}
    assert "id:main: dropped" in r.stdout and "link:/pricing: dropped" in r.stdout
    assert bc("adoption", "verify", project=proj).returncode == 0
    # the separator may be part of the item (the item is the first start that is in the record) and may be in the reason; a second drop replaces the reason
    r = drops(proj, "link:/legacy::route::the route has a new name, see ::redirects", "link:/pricing::replaced reason")
    assert r.returncode == 0, r.stdout + r.stderr
    assert record_entry(proj)["dropped"] == {"id:main": "the anchor is renamed to #content", "link:/legacy::route": "the route has a new name, see ::redirects",
                                              "link:/pricing": "replaced reason"}
    assert record_entry(proj)["before"] == load(proj)["wiring"]["r1"]["before"] and "after" not in record_entry(proj)       # nothing else changed
    # recording a drop reads no repository: it works without ripgrep, and a baseline asked for again keeps the drops
    r = drops(proj, "field:q::the search box is gone", env={"PATH": path_without(tmp_path, "rg")})
    assert r.returncode == 0 and "field:q" in record_entry(proj)["dropped"]
    assert wire(proj, "--before", "--again").returncode == 0 and "field:q" in record_entry(proj)["dropped"]
    assert wire(proj, "--compare", "--again").returncode == 2                                   # --again is for --before only


def test_check_fails_a_recorded_after_that_lost_wiring_nobody_dropped(proj, site):
    surveyed(proj, site)
    assert wire(proj, "--before").returncode == 0
    r = bc("check", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    row = check_row(proj)
    assert row["status"] == "info" and "record --after when the redesign is applied" in row["detail"]
    form = (site / "index.html").read_text()
    mutate(site / "index.html", form[form.index("<form"):form.index("</form>") + len("</form>")], "")        # the redesign loses the whole form
    assert wire(proj, "--after").returncode == 0
    r = bc("check", project=proj)
    row = check_row(proj)
    assert r.returncode == 1 and row["status"] == "fail", r.stdout
    assert row["detail"].startswith("10 item(s) of the before record are gone from the after record and nobody dropped them: " + ", ".join(FORM_LOST[:5]) + " and 5 more")
    assert next(x for x in report(proj, "check")["results"] if x["id"] == "adoption:data")["status"] == "pass"
    # five dropped, five left: all five are named and no "more"
    assert drops(proj, *[f"{i}::the form moved to the account page" for i in FORM_LOST[:5]]).returncode == 0
    r = bc("check", project=proj)
    row = check_row(proj)
    assert r.returncode == 1 and row["status"] == "fail" and ", ".join(FORM_LOST[5:]) in row["detail"] and "more" not in row["detail"]
    assert drops(proj, *[f"{i}::the form moved to the account page" for i in FORM_LOST[5:]]).returncode == 0
    r = bc("check", project=proj)
    row = check_row(proj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert row["status"] == "pass" and "10 dropped with a reason" in row["detail"]
    # a repository that keeps everything passes without any drop
    assert wire(proj, "--before", "--again").returncode == 0 and wire(proj, "--after").returncode == 0
    assert bc("check", project=proj).returncode == 0 and check_row(proj)["status"] == "pass"


def test_check_names_a_wiring_record_of_the_wrong_shape_once_and_does_not_crash(proj, site):
    surveyed(proj, site)
    assert wire(proj, "--before").returncode == 0
    mutate_json(proj / "adoption.json", lambda d: d["wiring"]["r1"].update(after={"items": {"link:/": "index.html"}}))
    r = bc("check", project=proj)
    rows = {x["id"]: x for x in report(proj, "check")["results"]}
    assert r.returncode == 1 and rows["adoption:data"]["status"] == "fail" and rows["adoption:data"]["detail"].count("does not map to a list of strings") == 1
    assert "adoption:wiring:site" not in rows and "Traceback" not in r.stderr


def test_adoption_md_shows_the_wiring_and_marks_its_lines_as_the_repository(proj, site):
    assert bc("adoption", "survey", "--repo", f"{site}=site", "--old-name", "Sample shop", project=proj).returncode == 0
    assert "## Wiring kept" not in (proj / "ADOPTION.md").read_text()
    assert wire(proj, "--before").returncode == 0
    md = (proj / "ADOPTION.md").read_text()
    counts = "link 8, field 6, handler 5, hook 9, id 7, script 2"
    assert wiring_section(md) == ["## Wiring kept", "", f"- `site`: before (2026-10-17) {counts}; no after record yet {ad.MARK}"]
    assert md.index("| # | Status |") < md.index("## Wiring kept") < md.index("## How this list is applied") < md.index("## Kept, not counted")
    assert "{{" not in md and "\n\n\n" not in md
    # the redesign: the pricing link and the plan select are gone, after is recorded
    edit(site / "src" / "Header.jsx", '<Link to="/pricing" data-testid="nav-pricing">Pricing</Link>', '<Link data-testid="nav-pricing">Pricing</Link>')
    edit(site / "index.html", '<select name="plan"><option value="free">Free</option></select>', "")
    assert wire(proj, "--after").returncode == 0
    md = (proj / "ADOPTION.md").read_text()
    assert wiring_section(md) == ["## Wiring kept", "",
                                  f"- `site`: before (2026-10-17) {counts}; after (2026-10-17) link 7, field 5, handler 5, hook 9, id 7, script 2 {ad.MARK}",
                                  f"  - `field:plan`: lost, not recorded {ad.MARK}",
                                  f"  - `link:/pricing`: lost, not recorded {ad.MARK}"]
    assert drops(proj, "link:/pricing::the pricing page moved to /plans", "field:plan::the plan is chosen in the account now").returncode == 0
    md = (proj / "ADOPTION.md").read_text()
    sec = wiring_section(md)
    assert sec[3:] == [f"  - `field:plan`: dropped, the plan is chosen in the account now {ad.MARK}",
                       f"  - `link:/pricing`: dropped, the pricing page moved to /plans {ad.MARK}"]
    assert all(ln.endswith(ad.MARK) for ln in sec[2:]), sec                                     # every line that holds the repository's values is a record, not a leftover
    assert bc("adoption", "verify", project=proj).returncode == 0
    # the cascade counts those lines as records: a leftover search for an item's value warns and names no file
    r = bc("check", "--cascade", "/pricing", "--cascade", "field:plan", project=proj)
    cas = {x["id"]: x for x in report(proj, "check")["results"] if x["id"].startswith("cascade:") and x["id"] != "cascade:scope"}
    assert r.returncode == 0 and set(cas) == {"cascade:/pricing", "cascade:field:plan"}, cas
    assert all(c["status"] == "warn" and c["hits"] == [] and c["recorded"] >= 1 for c in cas.values()), cas
    # two repositories: each has its own lines, in the order of the survey
    other = site.parent / "other"
    shutil.copytree(FIX, other)
    edit(other / "index.html", "Sample shop", "Other shop")
    surveyed(proj, other, label="other")
    assert bc("adoption", "wiring", "--repo", "other", "--before", project=proj).returncode == 0
    sec = wiring_section((proj / "ADOPTION.md").read_text())
    assert [ln for ln in sec if ln.startswith("- ")] == [f"- `site`: before (2026-10-17) {counts}; after (2026-10-17) link 7, field 5, handler 5, hook 9, id 7, script 2 {ad.MARK}",
                                                         f"- `other`: before (2026-10-17) {counts}; no after record yet {ad.MARK}"]


def test_adoption_md_of_a_list_without_wiring_is_the_bytes_it_was(proj, site):
    """The frame has a {{wiring}} line now. A list with no wiring record renders the bytes it rendered before (the file in tests/fixtures/adoption-md was
    written by the survey below, before the placeholder existed), whether adoption.json has an empty `wiring` or an older one has none."""
    (site / "public" / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>\n')
    (site / "manifest.json").write_text('{\n  "name": "Sample shop",\n  "theme_color": "#123456"\n}\n')
    (site / "README.md").write_text("# Sample shop\n\n![badge](https://img.shields.io/badge/build-passing-green)\n")
    (site / "src" / "colours.css").write_text("a { color: #123456; }\n")
    r = bc("adoption", "survey", "--repo", f"{site}=site", "--old-name", "Sample shop", "--old-colour", "#123456", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    r = bc("adoption", "add", "--repo", "site", "--file", "src/Header.jsx", "--find", "onClick", "--change", "Check the menu button still opens the menu.", "--lines", "8", project=proj)
    assert r.returncode == 0, r.stderr
    assert load(proj)["wiring"] == {} and (proj / "ADOPTION.md").read_bytes() == GOLDEN.read_bytes()
    doc = load(proj)
    del doc["wiring"]
    (proj / "adoption.json").write_bytes(ad.dumps(doc))
    assert bc("adoption", "render", project=proj).returncode == 0 and (proj / "ADOPTION.md").read_bytes() == GOLDEN.read_bytes()
    assert bc("adoption", "wiring", "--repo", "site", "--before", project=proj).returncode == 0
    assert (proj / "ADOPTION.md").read_bytes() != GOLDEN.read_bytes() and "## Wiring kept" in (proj / "ADOPTION.md").read_text()

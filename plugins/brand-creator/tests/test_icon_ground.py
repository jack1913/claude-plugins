"""The ground of the icons, the avatar and the social cards (qa/rules.json icons.ground, marks.<id>.ground, social.mode), and the accent line's
square ends when the brand's radius tokens are all 0.

A mark that carries its own dark ground (a light shape on a full-bleed dark square, made to be cropped by the phone) was shrunk onto the light
color.bg: a small dark tile on white. With icons.ground "drawing" the drawing fills the icon and its own ground is the ground every gate measures
against; with "dark" the dark color.bg and the dark artwork are used. The brand here is made up (Acme's tokens, a test mark)."""
import base64
import json
import re

import pytest
from helpers import bc, report

import _emit
import qa_rules
from _common import CliError
from pxio import read_png

GROUND = (10, 10, 15)   # the test mark's own ground, #0a0a0f
OWN = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" fill="#0a0a0f"/>'
       '<rect x="35" y="35" width="30" height="30" fill="#f5f5f0"/></svg>')
CORNER = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" fill="#0a0a0f"/>'
          '<rect x="10" y="10" width="80" height="80" fill="#f5f5f0"/></svg>')   # its light shape reaches past the maskable safe circle
INSET = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect x="10" y="10" width="80" height="80" fill="#0a0a0f"/>'
         '<rect x="35" y="35" width="30" height="30" fill="#f5f5f0"/></svg>')


def set_rules(p, **sections):
    f = p / qa_rules.RULES_FILE
    doc = json.loads(f.read_text()) if f.is_file() else {"schema": 1}
    doc.update(sections)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(doc))


def own_ground_mark(p, svg=OWN):
    """The mark and its small drawing become one that carries its own ground; it serves both grounds, so it has no -dark sibling."""
    for name in ("mark", "grid-mark"):
        (p / "assets/logo" / f"{name}.svg").write_text(svg)
        (p / "assets/logo" / f"{name}-dark.svg").unlink(missing_ok=True)


def corner(png: bytes) -> tuple:
    w, _h, px = read_png(png)
    return tuple(px[:3])


def light_side(png: bytes) -> int:
    """The width in px of the light shape on the dark ground."""
    w, h, px = read_png(png)
    xs = [i % w for i in range(w * h) if px[i * 4] > 128]
    return max(xs) - min(xs) + 1


def near(a, b, tol=3):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


# ---------------------------------------------------------------- the rules

@pytest.mark.parametrize("sections,ok", [
    ({"icons": {"ground": "light"}}, True), ({"icons": {"ground": "dark"}}, True), ({"icons": {"ground": "drawing"}}, True),
    ({"icons": {"ground": "black"}}, False), ({"icons": {"ground": 1}}, False), ({"icons": {"colour": "dark"}}, False),
    ({"social": {"mode": "dark"}}, True), ({"social": {"mode": "light"}}, True), ({"social": {"mode": "drawing"}}, False),
])
def test_the_rules_take_a_ground_for_the_icons_and_a_mode_for_the_cards_and_refuse_anything_else(tmp_path, sections, ok):
    set_rules(tmp_path, **sections)
    if ok:
        rules, _ = qa_rules.load(tmp_path)
        assert qa_rules.ground_for(rules, None) == sections.get("icons", {}).get("ground", "light")
        assert rules["social"]["mode"] == sections.get("social", {}).get("mode", "light")
    else:
        with pytest.raises(CliError) as e:
            qa_rules.load(tmp_path)
        assert e.value.code == 2


def test_the_default_ground_is_light_and_a_mark_may_name_its_own(tmp_path):
    rules, _ = qa_rules.load(tmp_path)
    assert qa_rules.ground_for(rules, None) == "light" and rules["social"]["mode"] == "light"
    bands = [{"name": "all", "drawing": "assets/logo/a.svg"}]
    set_rules(tmp_path, icons={"ground": "dark"}, marks={"a": {"bands": bands, "ground": "drawing"}, "b": {"bands": bands}})
    rules, _ = qa_rules.load(tmp_path)
    assert qa_rules.ground_for(rules, "a") == "drawing" and qa_rules.ground_for(rules, "b") == "dark"
    set_rules(tmp_path, marks={"a": {"bands": bands, "ground": "grey"}})
    with pytest.raises(CliError) as e:
        qa_rules.load(tmp_path)
    assert e.value.code == 2


@pytest.mark.parametrize("other,square", [
    ({"radius.sm": "0px", "radius.md": "0", "radius.lg": "0rem", "radius.pill": "0px"}, True),
    ({"radius.sm": "0px", "radius.md": "8px"}, False),
    ({"space.1": "4px"}, False),
    ({}, False),
])
def test_the_accent_line_is_square_when_every_radius_token_is_0(other, square):
    assert _emit.square_corners({"other": other}) is square
    assert _emit.rule_radius("1vh", [OWN], square=square) == ("0" if square else "1vh")


# ---------------------------------------------------------------- emit web

@pytest.mark.requires_setup
@pytest.mark.requires_resvg
def test_web_fills_the_touch_and_maskable_icons_with_a_drawing_that_carries_its_own_ground(acme):
    own_ground_mark(acme)
    set_rules(acme, icons={"ground": "drawing"})
    r = bc("emit", "web", project=acme)
    assert r.returncode == 0, r.stdout + r.stderr
    web = acme / "assets/web"
    for rel in ("apple-touch-icon.png", "icons/maskable-512.png"):
        assert near(corner((web / rel).read_bytes()), GROUND), rel        # the drawing's own ground to the edge, no light frame
    rows = {x["id"]: x for x in report(acme, "emit-web")["results"]}
    assert rows["check:maskable safe zone"]["status"] == "pass"         # the dark square is ground, not ink outside the circle
    assert rows["check:apple-touch opaque"]["status"] == "pass"
    mf = json.loads((web / "site.webmanifest").read_text())
    assert mf["theme_color"].lower() == mf["background_color"].lower() == "#0a0a0f"


@pytest.mark.requires_setup
@pytest.mark.requires_resvg
def test_web_shrinks_the_maskable_onto_the_drawings_own_ground_until_its_ink_is_inside_the_safe_circle(acme):
    own_ground_mark(acme, CORNER)
    set_rules(acme, icons={"ground": "drawing"})
    r = bc("emit", "web", project=acme)
    assert r.returncode == 0, r.stdout + r.stderr
    web = acme / "assets/web"
    mk = (web / "icons/maskable-512.png").read_bytes()
    assert near(corner(mk), GROUND)                                      # the drawing's own ground, not the light color.bg
    assert light_side(mk) < 0.8 * 512 - 4                                 # smaller than edge to edge (0.8 of the side)
    rows = {x["id"]: x for x in report(acme, "emit-web")["results"]}
    assert rows["check:maskable safe zone"]["status"] == "pass", rows["check:maskable safe zone"]
    at = (web / "apple-touch-icon.png").read_bytes()
    w, _h, _px = read_png(at)
    assert abs(light_side(at) - 0.8 * w) <= 2                             # the touch icon stays edge to edge


@pytest.mark.requires_setup
@pytest.mark.requires_resvg
def test_a_band_drawing_that_is_already_the_dark_file_serves_the_dark_ground_as_it_is(acme):
    assert bc("state", "--set", "tier=quick", project=acme).returncode == 0
    set_rules(acme, icons={"ground": "dark"}, bands=[{"name": "all", "drawing": "assets/logo/mark-dark.svg"}])
    for verb in ("web", "profiles"):
        r = bc("emit", verb, project=acme)
        assert r.returncode == 0, verb + r.stdout + r.stderr
        assert "mark-dark-dark.svg" not in r.stdout + r.stderr


@pytest.mark.requires_setup
@pytest.mark.requires_resvg
def test_web_refuses_the_drawing_ground_when_the_drawing_does_not_fill_its_canvas(acme):
    own_ground_mark(acme, INSET)
    set_rules(acme, icons={"ground": "drawing"})
    r = bc("emit", "web", project=acme)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "icons.ground" in r.stderr and "assets/logo/mark.svg" in r.stderr
    assert not (acme / "assets/web/apple-touch-icon.png").exists()


@pytest.mark.requires_setup
@pytest.mark.requires_resvg
def test_web_paints_the_dark_ground_when_the_rules_say_dark(acme):
    set_rules(acme, icons={"ground": "dark"})
    assert bc("emit", "web", project=acme).returncode == 0
    tokens = json.loads((acme / "assets/tokens/tokens.json").read_text())
    dark = tokens["modes"]["dark"]["color.bg"]["hex"].lower()
    want = tuple(int(dark[i:i + 2], 16) for i in (1, 3, 5))
    for rel in ("apple-touch-icon.png", "icons/maskable-512.png"):
        assert near(corner((acme / "assets/web" / rel).read_bytes()), want), rel
    mf = json.loads((acme / "assets/web/site.webmanifest").read_text())
    assert mf["background_color"].lower() == dark
    rows = {x["id"]: x for x in report(acme, "emit-web")["results"]}
    assert rows["check:maskable safe zone"]["status"] == "pass"


# ---------------------------------------------------------------- emit profiles

@pytest.mark.requires_setup
@pytest.mark.requires_resvg
def test_the_avatar_is_the_drawing_edge_to_edge_and_only_what_sits_on_its_ground_must_stay_in_the_circle(acme):
    assert bc("state", "--set", "tier=quick", project=acme).returncode == 0
    own_ground_mark(acme)
    set_rules(acme, icons={"ground": "drawing"})
    r = bc("emit", "profiles", project=acme)
    assert r.returncode == 0, r.stdout + r.stderr
    for n in (400, 800):
        png = (acme / f"assets/profiles/avatar-{n}.png").read_bytes()
        w, h, px = read_png(png)
        assert near(corner(png), GROUND)
        light = [(i % w, i // w) for i in range(w * h) if px[i * 4] > 128]
        side = max(x for x, _ in light) - min(x for x, _ in light) + 1
        assert abs(side - 0.3 * n) <= 2                                    # the drawing at full size: its light square is 30 % of the canvas
    rows = {x["id"]: x for x in report(acme, "emit-profiles")["results"]}
    assert rows["check:avatar-400 circle"]["status"] == rows["check:avatar-800 circle"]["status"] == "pass"


@pytest.mark.requires_setup
@pytest.mark.requires_resvg
def test_the_avatar_shrinks_a_drawing_whose_ink_reaches_past_the_circle_without_a_content_fraction(acme):
    assert bc("state", "--set", "tier=quick", project=acme).returncode == 0
    own_ground_mark(acme, CORNER)
    set_rules(acme, icons={"ground": "drawing"})
    r = bc("emit", "profiles", project=acme)
    assert r.returncode == 0, r.stdout + r.stderr
    for n in (400, 800):
        png = (acme / f"assets/profiles/avatar-{n}.png").read_bytes()
        assert near(corner(png), GROUND) and light_side(png) < 0.8 * n - 4
    rows = {x["id"]: x for x in report(acme, "emit-profiles")["results"]}
    assert rows["check:avatar-400 circle"]["status"] == rows["check:avatar-800 circle"]["status"] == "pass"


# ---------------------------------------------------------------- emit social

@pytest.mark.requires_setup
@pytest.mark.requires_resvg
def test_the_social_cards_take_the_dark_ground_when_the_rules_say_dark(acme):
    set_rules(acme, social={"mode": "dark"})
    r = bc("emit", "social", "--tagline", "Dependable small-batch tools", "--repo-images", "yes", project=acme)
    assert r.returncode == 0, r.stdout + r.stderr
    tokens = json.loads((acme / "assets/tokens/tokens.json").read_text())
    dark = tokens["modes"]["dark"]["color.bg"]["hex"].lower()
    for name in ("og", "github-social"):
        html = (acme / f"assets/social/_build/{name}.html").read_text()
        assert dark in html.lower(), name
    og = next((acme / "assets/social").glob("og-*.png"))
    want = tuple(int(dark[i:i + 2], 16) for i in (1, 3, 5))
    assert near(corner(og.read_bytes()), want)
    for name in ("og", "github-social"):                                  # the dark lettering, as the dark README header takes it
        html = re.sub(r"<!--.*?-->", "", (acme / f"assets/social/_build/{name}.html").read_text(), flags=re.S)
        m = re.search(r'src="data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)"', html)
        assert m and base64.b64decode(m.group(1)).decode("utf-8") == (acme / "assets/logo/wordmark-dark.svg").read_text(), name


@pytest.mark.requires_setup
@pytest.mark.requires_resvg
def test_the_card_accent_line_has_square_ends_when_the_brand_has_no_round_corners(acme):
    rule = re.compile(r"\.rule\{[^}]*?border-radius:([^;}]+)\}")
    run = ("emit", "social", "--tagline", "Dependable small-batch tools")
    assert bc(*run, project=acme).returncode == 0
    assert rule.search((acme / "assets/social/_build/og.html").read_text()).group(1) == "1vh"
    f = acme / "assets/tokens/tokens.json"
    doc = json.loads(f.read_text())
    doc["other"].update({k: "0px" for k in doc["other"] if k.startswith("radius.")} or {"radius.sm": "0px"})
    f.write_text(json.dumps(doc))
    assert bc(*run, project=acme).returncode == 0
    assert rule.search((acme / "assets/social/_build/og.html").read_text()).group(1) == "0"

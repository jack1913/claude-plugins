"""contrast --cvd: colour-vision-deficiency simulation (ColorAide: Brettel 1997, Vienot 1999) and CIEDE2000 distinctness over the
shared pair list (contrast pairs, touching pairs, `distinct` role-separation pairs).

Oracles: the known behaviour of red-green deficiencies (a red and a green of equal lightness collapse for deutan and protan viewers
and stay far apart for normal vision), black and white (never collapse), and the report's own normal-vision figure."""
import json

import pytest
from helpers import bc, failing, mutate_json, report

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_resvg]


def colour(L, C, H):
    return {"$value": {"colorSpace": "oklch", "components": [L, C, H], "alpha": 1, "hex": "#000000"}}  # hex is recomputed by --fix-hex


def add_roles(proj, pairs: dict[str, tuple], distinct: list[tuple[str, str]], rules=None):
    """Add primitives and semantic roles (same in light and dark), a distinct list, and rebuild the tokens."""
    def prim(d):
        for name, lch in pairs.values():
            d["color"][name] = colour(*lch)
    mutate_json(proj / "tokens/primitives.tokens.json", prim)
    for mode in ("light", "dark"):
        def sem(d, mode=mode):
            for role, (name, _lch) in pairs.items():
                d["color"][role] = {"$value": "{color.%s}" % name}
            if mode == "light":
                d["$extensions"]["brand-creator"]["distinct"] = [{"a": f"color.{a}", "b": f"color.{b}", "label": f"{a} and {b} stay distinct"} for a, b in distinct]
        mutate_json(proj / f"tokens/semantic.{mode}.tokens.json", sem)
    assert bc("tokens", "--fix-hex", project=proj).returncode == 0
    assert bc("tokens", project=proj).returncode == 0
    if rules:
        (proj / "qa").mkdir(exist_ok=True)
        (proj / "qa/rules.json").write_text(json.dumps(rules))


RED_GREEN = {"danger": ("red", (0.55, 0.17, 29)), "success": ("green", (0.55, 0.14, 142))}
BLUE_ORANGE = {"danger": ("orange", (0.72, 0.16, 60)), "success": ("blue", (0.45, 0.15, 255))}


def cvd(proj):
    return {r["id"]: r for r in report(proj, "contrast")["results"] if r.get("section") == "cvd"}


def test_the_acme_pairs_stay_distinguishable_and_every_method_is_named(acme):
    r = bc("contrast", "--cvd", project=acme)
    assert r.returncode == 0, r.stdout
    rows = cvd(acme)
    assert rows["cvd:light:color.text/color.bg"]["status"] == "pass"
    for row in rows.values():
        if row["id"] == "cvd:threshold":
            continue
        assert set(row["delta_e_simulated"]) == {"protan/brettel", "protan/vienot", "deutan/brettel", "deutan/vienot", "tritan/brettel"}
        assert row["delta_e_simulated"][f"{row['worst']['deficiency']}/{row['worst']['method']}"] == row["worst"]["delta_e"]
    text = rows["cvd:light:color.text/color.bg"]
    assert text["delta_e_normal"] > 80 and text["worst"]["delta_e"] > 80  # dark ink on paper never collapses
    assert "ColorAide" in report(acme, "contrast")["cvd"]["library"] and report(acme, "contrast")["cvd"]["metric"] == "CIEDE2000"
    one_per_pair = [k for k in rows if k.startswith("cvd:light:") and "color.accent/color.bg" in k]
    assert len(one_per_pair) == 1  # two contrast rules naming the same roles give one result, not a duplicate id


def test_the_threshold_is_a_labelled_proposal_until_the_owner_sets_it(acme):
    bc("contrast", "--cvd", project=acme)
    assert "a PROPOSAL" in cvd(acme)["cvd:threshold"]["detail"] and report(acme, "contrast")["cvd"]["threshold_delta_e"] == 10
    (acme / "qa/rules.json").write_text(json.dumps({"schema": 1, "cvd": {"min_delta_e": 20}}))
    bc("contrast", "--cvd", project=acme)
    assert "set by the project" in cvd(acme)["cvd:threshold"]["detail"] and report(acme, "contrast")["cvd"]["threshold_delta_e"] == 20


def test_red_and_green_of_equal_lightness_collapse_for_some_viewers_only(acme):
    add_roles(acme, RED_GREEN, [("danger", "success")])
    r = bc("contrast", "--cvd", project=acme)
    assert r.returncode == 1, r.stdout
    row = cvd(acme)["cvd:light:color.danger/color.success (distinct)"]
    assert row["status"] == "fail" and row["worst"]["deficiency"] in ("protan", "deutan") and row["worst"]["delta_e"] < 10
    assert row["delta_e_normal"] > 30  # normal vision tells them apart easily: the failure is specific to colour-vision deficiency
    assert row["delta_e_simulated"]["tritan/brettel"] > 10  # blue-yellow vision is unaffected
    assert "non-colour cue" in row["detail"]
    assert "cvd:dark:color.danger/color.success (distinct)" in failing(report(acme, "contrast"))


def test_blue_and_orange_survive_every_deficiency(acme):
    add_roles(acme, BLUE_ORANGE, [("danger", "success")])
    r = bc("contrast", "--cvd", project=acme)
    row = cvd(acme)["cvd:light:color.danger/color.success (distinct)"]
    assert r.returncode == 0, r.stdout
    assert row["status"] == "pass" and row["worst"]["delta_e"] >= 10 and row["delta_e_normal"] >= row["worst"]["delta_e"]


def test_an_owner_accepted_miss_is_a_warning_that_carries_its_reason(acme):
    add_roles(acme, RED_GREEN, [("danger", "success")])
    mutate_json(acme / "tokens/exceptions.json", lambda d: d["exceptions"].append(
        {"a": "color.danger", "b": "color.success", "mode": "*", "reason": "status uses an icon and a word as well, never colour alone"}))
    r = bc("contrast", "--cvd", project=acme)
    assert r.returncode == 0, r.stdout
    assert not [x for x in report(acme, "contrast")["results"] if x["id"].startswith("exception:")]  # used by the cvd check: not stale
    row = cvd(acme)["cvd:light:color.danger/color.success (distinct)"]
    assert row["status"] == "warn" and row["exception"].startswith("status uses an icon") and "EXCEPTION" in row["detail"]


def test_the_deficiency_list_and_threshold_come_from_the_project(acme):
    add_roles(acme, RED_GREEN, [("danger", "success")], rules={"schema": 1, "cvd": {"deficiencies": ["tritan"]}})
    r = bc("contrast", "--cvd", project=acme)
    row = cvd(acme)["cvd:light:color.danger/color.success (distinct)"]
    assert r.returncode == 0 and set(row["delta_e_simulated"]) == {"tritan/brettel"}  # tritan alone: red and green stay apart
    (acme / "qa/rules.json").write_text(json.dumps({"schema": 1, "cvd": {"min_delta_e": 95}}))
    assert bc("contrast", "--cvd", project=acme).returncode == 1  # an impossible bar fails ordinary pairs too
    (acme / "qa/rules.json").write_text(json.dumps({"schema": 1, "cvd": {"deficiencies": ["blue"]}}))
    r = bc("contrast", "--cvd", project=acme)
    assert r.returncode == 2 and "unknown" in r.stderr and "protan" in r.stderr


def test_without_the_flag_no_simulation_runs(acme):
    bc("contrast", project=acme)
    assert cvd(acme) == {} and "cvd" not in report(acme, "contrast")


def test_build_tokens_resolves_distinct_roles_and_refuses_unknown_ones(acme):
    add_roles(acme, BLUE_ORANGE, [("danger", "success")])
    tj = json.loads((acme / "assets/tokens/tokens.json").read_text())
    d = tj["distinct"][0]
    assert (d["a"], d["b"]) == ("color.danger", "color.success") and set(d["modes"]) == {"light", "dark"}
    assert d["modes"]["light"]["a_hex"] == tj["modes"]["light"]["color.danger"]["hex"]
    mutate_json(acme / "tokens/semantic.light.tokens.json",
                lambda doc: doc["$extensions"]["brand-creator"]["distinct"].append({"a": "color.danger", "b": "color.nope"}))
    r = bc("tokens", project=acme)
    assert r.returncode == 1 and "color.nope" in r.stdout

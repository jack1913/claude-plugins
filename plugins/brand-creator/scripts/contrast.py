#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = ["coloraide==8.13.1"]
# ///
"""brand-creator contrast: three clearly separated sections, read from the built tokens (assets/tokens/tokens.json).

  1. WCAG 2.2 AA, UI text and components: pass or fail (1.4.3 text 4.5, large text 3, 1.4.11 non-text 3).
  2. Brand rules for marks and lockups, labelled "brand rule (logos WCAG-exempt)": WCAG 2.2 exempts text that is part
     of a logo or brand name, so these targets are set by the owner (the `min` of each pair), not by WCAG.
  3. APCA Lc: an advisory column only (computed with colorjs.io by `brand-creator tokens`). It never gates and WCAG 3,
     which is a working draft, is never claimed.
  4. Touching pairs (brand rule): the logo SVGs (assets/logo/mark.svg and mark-dark.svg, plus lockup and wordmark when
     present; with several marks in qa/rules.json, every drawing each mark's bands name and its lockup and wordmark) are rasterised
     with resvg, every pair of flat colours that really touch each other, and every colour that
     touches the ground, is found in the pixels (not declared by hand), mapped to token roles and held to a target.

Pairs come from the tokens ($extensions["brand-creator"].pairs in semantic.light.tokens.json) and are evaluated in
every mode (light and dark). Touching-pair targets come from $extensions["brand-creator"].touching in the same file:
  {"default": 3.0, "ground": 3.0, "pairs": [{"a": "color.mark", "b": "color.accent", "min": 2.0, "label": "..."}]}
(first matching pair wins; "default" applies to any other touching pair, "ground" to a colour against the ground,
3 when unset). The accepted misses live in tokens/exceptions.json, one entry per pair with a reason:
  {"exceptions": [{"a": "color.mark", "b": "color.accent", "mode": "dark", "reason": "..."}]}
(a and b are token roles or #rrggbb; mode is light, dark or *). An exception turns a miss into a warning that carries
its reason; an exception that matches nothing, or a pair that passes anyway, is reported so the register stays honest.
  5. --cvd (colour-vision deficiency): the colours of every pair of the shared list (the contrast pairs, the touching
     pairs and $extensions["brand-creator"].distinct role-separation pairs) are simulated for protanopia, deuteranopia
     and tritanopia with ColorAide (MIT): Brettel 1997 and Vienot 1999 for protan and deutan, Brettel for tritan (Vienot's
     method covers the two red-green cases only). The simulated colours must stay at least cvd.min_delta_e apart in
     CIEDE2000 (qa/rules.json; the proposal is 10 and is printed as a proposal for the owner to set at G4).
  6. Text grounds (section `grounds`, warnings in this release, each saying it is a failure from the next one): every ground
     that carries text (`grounds` of tokens.json, from $extensions["brand-creator"].grounds) needs all five roles in light and
     dark (text, action, on-action, focus, border), with text at 4.5:1 on the ground, the action and the focus ring and the border
     at 3:1 against it, and the on-action text at 4.5:1 on the action. `grounds:named` warns until the owner has named the grounds
     (a date and their words); with --cvd the action and the focus ring must also stay the colour-vision distance (item 5) from
     the ground (`cvd:<mode>:grounds:<ground>:<role>`).
Exit 1 when any pair misses its target and is not excepted (the text-grounds rows never change the status or the exit code);
exit 3 when the logo SVG is missing (skip it explicitly with --skip-marks, which is printed).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "marklib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "booklib"))   # adapt reads bookdata
sys.path.insert(0, str(Path(__file__).resolve().parent / "adaptlib"))
import adapt  # noqa: E402  (grounds_of and owner_named: the shape of `grounds` and the owner's naming are adapt's, so that contrast and the adapters cannot disagree on one file)
import qa_rules  # noqa: E402
import svgtools  # noqa: E402
from _color import wcag_ratio  # noqa: E402
from _common import (EXIT_CANNOT, EXIT_USAGE, Parser, Report, add_project_arg, add_renderer_arg, confine, fail,  # noqa: E402
                     find_project, main_guard, rasterise_svg, rel)
from touching import analyse  # noqa: E402
from marks import load_exceptions, load_json, matches, names_of  # noqa: E402  (shared with logo-sheet)

WCAG = {
    "ui-text": (4.5, "WCAG 2.2 AA 1.4.3 (text)"),
    "ui-text-large": (3.0, "WCAG 2.2 AA 1.4.3 (large text)"),
    "ui-component": (3.0, "WCAG 2.2 AA 1.4.11 (non-text)"),
}
BRAND_LABEL = "brand rule (logos WCAG-exempt)"
TOUCH_LABEL = BRAND_LABEL + ": colours that touch in the artwork"
LOGO_NAMES = ("mark", "lockup", "wordmark")  # assets/logo/<name>.svg (light ground) and <name>-dark.svg (dark ground)
RASTER = 512
MARGIN = 8
DEFAULT_TOUCH_MIN = 3.0


def touching_config(tj: dict) -> dict:
    """Validated targets: {"default": float, "ground": float, "pairs": [{a, b, min, label}]}."""
    cfg = tj.get("touching") or {}
    if not isinstance(cfg, dict):
        fail(EXIT_USAGE, "tokens.json: touching must be an object")
    out = {"default": DEFAULT_TOUCH_MIN, "pairs": []}
    for k in ("default", "ground"):
        if cfg.get(k) is not None:
            if not isinstance(cfg[k], (int, float)) or isinstance(cfg[k], bool) or cfg[k] <= 0:
                fail(EXIT_USAGE, f"touching.{k} must be a number above 0, got {cfg[k]!r}")
            out[k] = float(cfg[k])
    out.setdefault("ground", out["default"])
    for i, pr in enumerate(cfg.get("pairs") or []):
        if not (isinstance(pr, dict) and isinstance(pr.get("a"), str) and isinstance(pr.get("b"), str)
                and isinstance(pr.get("min"), (int, float)) and not isinstance(pr.get("min"), bool) and pr["min"] > 0):
            fail(EXIT_USAGE, f"touching.pairs[{i}] needs a, b (token roles) and min (a number above 0)")
        out["pairs"].append({"a": pr["a"], "b": pr["b"], "min": float(pr["min"]), "label": pr.get("label")})
    return out


def logo_groups(project: Path, rules: dict) -> list[tuple[str, Path, Path | None]]:
    """The logo artwork whose touching colours are checked, each with its -dark.svg: assets/logo/mark.svg, lockup.svg and wordmark.svg;
    with several marks (qa/rules.json marks) every drawing each mark's bands name, and its <id>-lockup.svg and <id>-wordmark.svg."""
    if rules["marks"]:
        rels = list(dict.fromkeys(r for mid, m in rules["marks"].items()
                                  for r in [b["drawing"] for b in m["bands"]] + [f"assets/logo/{mid}-lockup.svg", f"assets/logo/{mid}-wordmark.svg"]))
    else:
        rels = [f"assets/logo/{name}.svg" for name in LOGO_NAMES]
    out = []
    for r in rels:
        light = confine(project, r, what="logo")
        if light.is_file():
            dark = confine(project, light.with_name(light.stem + "-dark.svg"), what="dark logo")
            out.append((light.stem, light, dark if dark.is_file() else None))
    return out


NOT_FLAT = ("linearGradient", "radialGradient", "pattern", "filter", "mask", "image")  # paint that is not a flat fill


def raster_pairs(svg_path: Path, renderer: str) -> dict:
    """analyse() of the rasterised SVG, or {"colours": {}, "unsupported": "<element>"} for artwork with non-flat paint
    (a gradient bands into false flat colours, so its pairs would be wrong rather than merely missing)."""
    try:
        text = svg_path.read_text(encoding="utf-8")
        root = svgtools.parse(text)
        for el in root.iter():
            local = el.tag.split("}")[-1]
            if local in NOT_FLAT:
                return {"colours": {}, "unsupported": f"<{local}>"}
        fitted = svgtools.fit(text, RASTER, RASTER, box=(RASTER - 2 * MARGIN, RASTER - 2 * MARGIN))
    except (OSError, svgtools.SvgError) as e:
        fail(EXIT_USAGE, f"{svg_path.name}: {e}")
    return analyse(rasterise_svg(fitted, RASTER, RASTER, renderer=renderer))


def _role(names: list[str]) -> str:
    return next((n for n in names if n.startswith("color.")), names[-1])


def check_touching(rep: Report, project: Path, tj: dict, exceptions: list[dict], renderer: str) -> bool:
    """True when the pairs were evaluated (the caller then lists stale exceptions); False when the check could not run."""
    cfg = touching_config(tj)
    try:
        ground_hex = {m: tj["modes"][m]["color.bg"]["hex"].lower() for m in ("light", "dark")}
    except KeyError:
        fail(EXIT_USAGE, "tokens.json has no color.bg in light and dark mode; the ground of the touching pairs cannot be named")
    rules, _rules_src = qa_rules.load(project)
    groups = logo_groups(project, rules)
    if rules["marks"] and not groups:
        rep.add("touching:marks", "skipped", TOUCH_LABEL, section="touching-pairs",
                detail="none of the drawings qa/rules.json marks names exists, so the pairs that touch in the artwork were NOT checked")
        return False
    if not rules["marks"] and not any(g[0] == "mark" for g in groups):
        rep.add("touching:mark.svg", "skipped", TOUCH_LABEL, section="touching-pairs",
                detail="assets/logo/mark.svg not found, so the pairs that touch in the artwork were NOT checked. Build the mark "
                       "first, or pass --skip-marks to leave this check out on purpose.")
        return False
    for name, light, dark in groups:
        runs = [("light", light, ["light"] if dark else ["light", "dark"])]
        if dark is not None:
            runs.append(("dark", dark, ["dark"]))
        else:
            rep.add(f"touching:{name}:dark-artwork", "info", TOUCH_LABEL, section="touching-pairs",
                    detail=f"no assets/logo/{name}-dark.svg: the light artwork is checked on the dark ground too")
        for art_mode, svg, ground_modes in runs:
            src = rel(project, svg)
            res = raster_pairs(svg, renderer)
            if not res["colours"]:
                why = f"uses {res['unsupported']}, which is not a flat fill" if res.get("unsupported") else "has no flat fills"
                rep.add(f"touching:{src}", "skipped", TOUCH_LABEL, section="touching-pairs",
                        detail=f"{src} {why}: the touching pairs of this artwork were NOT verified (gradients, patterns, "
                               f"filters, masks and images are not analysed; supply flat artwork)")
                continue
            for hexv in res["colours"]:
                if len(names_of(tj, art_mode, hexv)) == 1:
                    rep.add(f"touching:{src}:{hexv}:token", "warn", TOUCH_LABEL, section="touching-pairs",
                            detail=f"{hexv} in {src} is not a colour token in {art_mode} mode; no role can be named for it")
            work = [(a, b, c, art_mode, None) for (a, b), c in sorted(res["contacts"].items())]
            for gm in ground_modes:
                work += [(hexv, ground_hex[gm], c, gm, gm) for hexv, c in sorted(res["ground"].items())]
            for a, b, contact, mode, ground_mode in work:
                is_ground = ground_mode is not None
                na = names_of(tj, art_mode, a)
                nb = names_of(tj, mode, b) + ["ground"] if is_ground else names_of(tj, art_mode, b)
                minimum, label = (cfg["ground"] if is_ground else cfg["default"]), None
                for rule in cfg["pairs"]:
                    if matches(rule["a"], rule["b"], na, nb):
                        minimum, label = rule["min"], rule["label"]
                        break
                ratio = wcag_ratio(a, b)
                where = f"{src} on the {mode} ground" if is_ground else src
                rid = f"touch:{mode}:{name}:{a}|{'ground' if is_ground else b}"
                detail = (f"{_role(na)} ({a}) touches {'the ground, ' if is_ground else ''}{_role(nb)} ({b}): {ratio:.2f}:1 "
                          f"(need {minimum:g}:1), {contact} px of contact at {RASTER} px, in {where}")
                common = dict(section="touching-pairs", ratio=round(ratio, 2), required=minimum, fg=a, bg=b, contact_px=contact,
                              roles=[_role(na), _role(nb)], source=src, mode=mode, target_label=label)
                lab = TOUCH_LABEL + (f" ({label})" if label else "")
                hit = next((e for e in exceptions if e["mode"] in ("*", mode) and matches(e["a"], e["b"], na, nb)), None)
                if ratio >= minimum:
                    rep.add(rid, "pass", lab, detail=detail, **common)
                    if hit is not None:
                        hit["passed_anyway"] = True
                elif hit is not None:
                    hit["used"] = True
                    rep.add(rid, "warn", lab + ": accepted exception", detail=detail + f"  EXCEPTION: {hit['reason']}",
                            exception=hit["reason"], **common)
                else:
                    rep.add(rid, "fail", lab, detail=detail + "  (change the colours, set the target in touching.pairs, or record "
                                                              "an exception with a reason in tokens/exceptions.json)", **common)
    return True


def report_stale_exceptions(rep: Report, exceptions: list[dict], cvd: bool) -> None:
    """After every check that can use an exception (touching pairs, and the CVD pairs with --cvd): list the unused ones."""
    where = "touching or colour-vision pair" if cvd else "touching pair in the artwork"
    for e in exceptions:
        what = f"{e['a']} / {e['b']} ({e['mode']})"
        if not e["used"]:
            rep.add(f"exception:{what}", "warn", "exceptions register", section="touching-pairs",
                    detail=(f"{what} passes its target now: remove the exception" if e.get("passed_anyway")
                            else f"{what} matches no {where}: the exception is stale, remove it"))


# ---------------------------------------------------------------- text grounds
GROUND_ROLES = ("text", "action", "on-action", "focus", "border")
# role, what it is held against ("ground", or another role of the same ground), WCAG floor, WCAG criterion
GROUND_TARGETS = (
    ("text", "ground", 4.5, "WCAG 2.2 AA 1.4.3 (text)"),
    ("action", "ground", 3.0, "WCAG 2.2 AA 1.4.11 (non-text)"),
    ("on-action", "action", 4.5, "WCAG 2.2 AA 1.4.3 (text)"),
    ("focus", "ground", 3.0, "WCAG 2.2 AA 1.4.11 (non-text)"),
    ("border", "ground", 3.0, "WCAG 2.2 AA 1.4.11 (non-text)"),
)
GROUNDS_LABEL = "text grounds, complete roles"
NEXT_RELEASE = "this is a warning now and a failure from the next release"


def ground_entries(tj: dict) -> list[tuple[str, str, str, dict]]:
    """The grounds of tokens.json as (id, ground token, mode, {ground, text, action, on-action, focus, border -> hex or None}), light then dark of
    each ground. A ground named twice gets `#2`, `#3` after its id, so that no two rows share one. [] when tokens.json has no `grounds`. The shape is
    `adapt.grounds_of`'s, the one the adapters, the applied skill and the kit read: a block it refuses (an entry with no `roles` too) stops this run too (exit 2)."""
    out, count = [], {}
    for e in adapt.grounds_of(tj)[1]:
        count[e["ground"]] = n = count.get(e["ground"], 0) + 1
        gid = e["ground"] if n == 1 else f"{e['ground']}#{n}"
        out += [(gid, e["ground"], mode, e["modes"][mode]) for mode in ("light", "dark")]
    return out


def check_grounds(rep: Report, tj: dict) -> None:
    """Section `grounds`: `grounds:named`, then per ground and mode `grounds:<mode>:<ground>:roles` and one row per role that has what it is held
    against. Every row is a pass or a warning: the status and the exit code of the report do not change in this release."""
    g = tj.get("grounds")
    if g is None:
        rep.add("grounds:named", "warn", GROUNDS_LABEL, section="grounds",
                detail=f"tokens.json has no grounds: ask the owner which colours text sits on, record them in `grounds` with the date and their words, "
                       f"never guess; {NEXT_RELEASE}")
        return
    ground_entries(tj)                                    # the shape is checked once, whichever rows follow
    named = g["named_by_owner"].strip()
    if adapt.named_date(named) is None:
        rep.add("grounds:named", "warn", GROUNDS_LABEL, section="grounds", named_by_owner=False,
                detail=("grounds.named_by_owner is empty: " if not named else f"grounds.named_by_owner {named!r} does not start with a YYYY-MM-DD date: ")
                       + f"these grounds are a proposal, not named by the owner. Ask the owner which colours text sits on and record the date "
                         f"and their words; never guess; {NEXT_RELEASE}")
    elif not adapt.owner_named(named):
        rep.add("grounds:named", "warn", GROUNDS_LABEL, section="grounds", named_by_owner=False,
                detail=f"grounds.named_by_owner is only the date {named[:10]}: record the owner's words too; {NEXT_RELEASE}")
    elif not g["list"]:
        rep.add("grounds:named", "warn", GROUNDS_LABEL, section="grounds", named_by_owner=True,
                detail=f"the owner named the grounds ({named}) but grounds.list holds none: list each colour text sits on; {NEXT_RELEASE}")
    else:
        rep.add("grounds:named", "pass", GROUNDS_LABEL, section="grounds", named_by_owner=True, detail=f"named by the owner: {named}")
    for gid, name, mode, m in ground_entries(tj):
        missing = [r for r in ("ground",) + GROUND_ROLES if not m.get(r)]
        if missing:
            rep.add(f"grounds:{mode}:{gid}:roles", "warn", GROUNDS_LABEL, section="grounds", ground=name, mode=mode, missing=missing,
                    detail=f"{name} in {mode}: no colour for {', '.join(missing)}. A ground needs a text, action, on-action, focus and border colour: "
                           f"ask the owner, never guess; {NEXT_RELEASE}")
        else:
            rep.add(f"grounds:{mode}:{gid}:roles", "pass", GROUNDS_LABEL, section="grounds", ground=name, mode=mode, missing=[],
                    detail=f"{name} in {mode}: all five roles have a colour")
        for role, against, minimum, wcag in GROUND_TARGETS:
            fg, bg = m.get(role), m.get(against)
            if not (fg and bg):
                continue                                  # a missing role is said once, in the roles row
            ratio = wcag_ratio(fg, bg)
            ok = ratio >= minimum
            on = "the ground" if against == "ground" else "the action"
            rep.add(f"grounds:{mode}:{gid}:{role}", "pass" if ok else "warn", f"{GROUNDS_LABEL} ({wcag})", section="grounds", ground=name, mode=mode,
                    role=role, ratio=round(ratio, 2), required=minimum, fg=fg, bg=bg,
                    detail=f"{role} {fg} on {on} {bg} ({name}, {mode}): {ratio:.2f}:1 (need {minimum:g}:1)" + ("" if ok else f"; {NEXT_RELEASE}"))


CVD_METHODS = {"protan": ("brettel", "vienot"), "deutan": ("brettel", "vienot"), "tritan": ("brettel",)}
CVD_LABEL = "colour-vision simulation (ColorAide): simulated colours stay distinguishable (CIEDE2000)"


def cvd_pairs(tj: dict) -> list[dict]:
    """The shared pair list as {id, a, b, label, modes: {mode: (hex, hex)}}: contrast pairs, touching pairs, distinct pairs."""
    out, seen = [], set()
    for pr in tj["pairs"]:
        if (pr["fg"], pr["bg"]) in seen:  # one result per role pair, whatever number of rules (kinds) name it
            continue
        seen.add((pr["fg"], pr["bg"]))
        out.append({"id": f"{pr['fg']}/{pr['bg']}", "roles": (pr["fg"], pr["bg"]), "label": pr.get("label") or pr.get("kind") or "contrast pair",
                    "modes": {m: (v["fg_hex"], v["bg_hex"]) for m, v in pr["modes"].items()}})
    tchg = (tj.get("touching") or {}).get("pairs") or []
    for tp in tchg:
        modes = {}
        for m in ("light", "dark"):
            try:
                modes[m] = (tj["modes"][m][tp["a"]]["hex"], tj["modes"][m][tp["b"]]["hex"])
            except KeyError:
                break
        else:
            out.append({"id": f"{tp['a']}/{tp['b']} (touching)", "roles": (tp["a"], tp["b"]), "label": tp.get("label") or "touching pair", "modes": modes})
    for d in tj.get("distinct") or []:
        out.append({"id": f"{d['a']}/{d['b']} (distinct)", "roles": (d["a"], d["b"]), "label": d.get("label") or "roles that must stay distinguishable",
                    "modes": {m: (v["a_hex"], v["b_hex"]) for m, v in d["modes"].items()}})
    return out


def check_cvd(rep: Report, tj: dict, rules: dict, rules_src: str, exceptions: list[dict]) -> None:
    from coloraide import Color
    cfg = rules["cvd"]
    thr = float(cfg["min_delta_e"])
    kinds = [k for k in cfg["deficiencies"] if k in CVD_METHODS]
    unknown = [k for k in cfg["deficiencies"] if k not in CVD_METHODS]
    if unknown:
        fail(EXIT_USAGE, f"qa/rules.json cvd.deficiencies: unknown {unknown}; use protan, deutan, tritan")

    def sim(hexv: str, kind: str, method: str) -> Color:
        return Color(hexv).filter(kind, method=method).convert("srgb").fit()

    def measure(fg: str, bg: str) -> tuple[tuple, dict, float]:
        """(the lowest simulated distance as (delta_e, deficiency, method), every simulated distance by deficiency/method, the normal-vision distance)."""
        worst, by = None, {}
        for kind in kinds:
            for method in CVD_METHODS[kind]:
                de = sim(fg, kind, method).delta_e(sim(bg, kind, method), method="2000")
                by[f"{kind}/{method}"] = round(de, 1)
                if worst is None or de < worst[0]:
                    worst = (de, kind, method)
        return worst, by, Color(fg).delta_e(Color(bg), method="2000")

    rep.extra["cvd"] = {"threshold_delta_e": thr, "threshold_source": rules_src, "metric": "CIEDE2000",
                        "methods": {k: list(CVD_METHODS[k]) for k in kinds}, "library": "ColorAide (MIT)"}
    own = "cvd.min_delta_e" in rules["_from_file"]
    rep.add("cvd:threshold", "info", CVD_LABEL, section="cvd", detail=f"threshold {thr:g} CIEDE2000, "
            + ("set by the project in qa/rules.json" if own else "a PROPOSAL (no cvd.min_delta_e in qa/rules.json): the owner sets it at G4"))
    pairs = cvd_pairs(tj)
    for pr in pairs:
        for mode, (fg, bg) in pr["modes"].items():
            worst, by, normal = measure(fg, bg)
            ok = worst[0] >= thr
            hit = None
            if not ok:  # an owner-accepted miss of the same pair (tokens/exceptions.json) is a warning that carries its reason
                na, nb = names_of(tj, mode, fg.lower()), names_of(tj, mode, bg.lower())
                hit = next((e for e in exceptions if e["mode"] in ("*", mode) and matches(e["a"], e["b"], na, nb)), None)
            if hit is not None:
                hit["used"] = True
            detail = (f"{fg} / {bg}: lowest simulated distance {worst[0]:.1f} ({worst[1]}, {worst[2]}) vs threshold {thr:g}; normal vision {normal:.1f}")
            if not ok and hit is None:
                detail += "  these two collapse for some viewers: change one of them, add a non-colour cue, or set the threshold at G4"
            if hit is not None:
                detail += f"  EXCEPTION: {hit['reason']}"
            rep.add(f"cvd:{mode}:{pr['id']}", "pass" if ok else ("warn" if hit else "fail"), CVD_LABEL + (": accepted exception" if hit else ""),
                    detail=detail, section="cvd", pair=pr["id"], mode=mode, fg=fg, bg=bg, delta_e_normal=round(normal, 1), delta_e_simulated=by,
                    worst={"deficiency": worst[1], "method": worst[2], "delta_e": round(worst[0], 1)}, required=thr,
                    **({"exception": hit["reason"]} if hit else {}))
    for gid, name, mode, m in ground_entries(tj):         # the action and the focus ring against their ground: a warning in this release
        for role in ("action", "focus"):
            if not (m.get(role) and m.get("ground")):
                continue                                  # a missing role is said once, in the grounds:<mode>:<ground>:roles row
            fg, bg = m[role], m["ground"]
            worst, by, normal = measure(fg, bg)
            ok = worst[0] >= thr
            rep.add(f"cvd:{mode}:grounds:{gid}:{role}", "pass" if ok else "warn", f"{GROUNDS_LABEL}, {CVD_LABEL}", section="grounds", ground=name, mode=mode,
                    role=role, fg=fg, bg=bg, delta_e_normal=round(normal, 1), delta_e_simulated=by,
                    worst={"deficiency": worst[1], "method": worst[2], "delta_e": round(worst[0], 1)}, required=thr,
                    detail=f"{role} {fg} / ground {bg} ({name}, {mode}): lowest simulated distance {worst[0]:.1f} ({worst[1]}, {worst[2]}) vs threshold {thr:g}; "
                           f"normal vision {normal:.1f}" + ("" if ok else f"  the {role} collapses into its ground for some viewers: change one of them or "
                                                                          f"add a non-colour cue; {NEXT_RELEASE}"))


def main() -> int:
    ap = Parser(prog="brand-creator contrast", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    add_renderer_arg(ap)
    ap.add_argument("--tokens", help="built tokens.json (default: assets/tokens/tokens.json)")
    ap.add_argument("--exceptions", help="exceptions register inside the project (default: tokens/exceptions.json)")
    ap.add_argument("--cvd", action="store_true", help="also simulate colour-vision deficiencies (protan, deutan, tritan) and require the pairs to stay distinguishable")
    ap.add_argument("--skip-marks", action="store_true",
                    help="leave the touching-pair check out on purpose (no logo yet); the report says so")
    a = ap.parse_args()
    project = find_project(a.project)
    tok = confine(project, a.tokens or "assets/tokens/tokens.json", what="--tokens")
    if not tok.is_file():
        fail(EXIT_CANNOT, f"{tok.relative_to(project)} not found; run `brand-creator tokens` first")
    try:
        doc = json.loads(tok.read_text(encoding="utf-8"))
        pairs = doc["pairs"]
    except (ValueError, KeyError) as e:
        fail(EXIT_USAGE, f"{tok}: not a brand-creator tokens.json ({e})")
    if not pairs:
        fail(EXIT_CANNOT, "no contrast pairs defined: add $extensions[\"brand-creator\"].pairs to tokens/semantic.light.tokens.json")

    exc_path = confine(project, a.exceptions or "tokens/exceptions.json", what="--exceptions")
    exceptions = load_exceptions(exc_path)
    rules_file = project / qa_rules.RULES_FILE   # with several marks it names the drawings checked, so a change there makes the report stale
    inputs = [tok, exc_path] + [x for g in logo_groups(project, qa_rules.load(project)[0]) for x in g[1:] if x is not None] + ([rules_file] if rules_file.is_file() else [])
    rep = Report("contrast", project, inputs, renderer=a.renderer)
    rep.extra = {"notes": ["WCAG 2.2 UI pairs gate. Mark/lockup targets are owner-set brand rules: WCAG 2.2 exempts logo text.",
                           "Touching pairs are found in the pixels of the logo SVGs (resvg, 512 px) and held to touching targets; "
                           "accepted misses are in tokens/exceptions.json, each with a reason.",
                           "APCA Lc is advisory only. WCAG 3 is a working draft and is not claimed."]}
    for pr in pairs:
        kind = pr.get("kind")
        if kind in WCAG:
            default_min, label = WCAG[kind]
            minimum = float(pr.get("min") or default_min)
            if minimum < default_min:
                rep.add(f"{pr['fg']}/{pr['bg']}:min", "fail", label, detail=f"min {minimum} is below the WCAG 2.2 AA floor {default_min}; "
                                                                           f"relax brand rules, not WCAG pairs")
                continue
            section = "wcag-ui"
        elif kind == "brand-rule":
            if pr.get("min") is None:
                rep.add(f"{pr['fg']}/{pr['bg']}:min", "fail", BRAND_LABEL, detail="a brand-rule pair needs an explicit min")
                continue
            minimum, label, section = float(pr["min"]), pr.get("label") or BRAND_LABEL, "brand-rule"
            if BRAND_LABEL not in label:
                label = f"{BRAND_LABEL}: {label}"
        else:
            rep.add(f"{pr.get('fg')}/{pr.get('bg')}:kind", "fail", "unknown pair kind", detail=f"kind {kind!r}; use ui-text, ui-text-large, ui-component or brand-rule")
            continue
        for mode, m in pr["modes"].items():
            ratio = wcag_ratio(m["fg_hex"], m["bg_hex"])
            ok = ratio >= minimum
            lc = m.get("apca_lc")
            rep.add(f"{mode}:{pr['fg']}/{pr['bg']}", "pass" if ok else "fail", label,
                    section=section, ratio=round(ratio, 2), required=minimum, fg=m["fg_hex"], bg=m["bg_hex"],
                    apca_lc=lc, apca_advisory=True,
                    detail=f"{ratio:.2f}:1 (need {minimum:g}:1)  fg {m['fg_hex']} on {m['bg_hex']}"
                           + (f"  APCA Lc {lc} (advisory)" if lc is not None else "  APCA not computed"))
    check_grounds(rep, doc)
    if a.skip_marks:
        rep.add("touching:skipped-on-purpose", "info", TOUCH_LABEL, section="touching-pairs", detail="--skip-marks: the pairs that touch in the logo artwork were not checked")
        evaluated = False
    else:
        evaluated = check_touching(rep, project, doc, exceptions, a.renderer)
    if a.cvd:
        rules, rules_src = qa_rules.load(project)
        rep.inputs.append(project / qa_rules.RULES_FILE)
        check_cvd(rep, doc, rules, rules_src, exceptions)
        # an exception may be meant for a colour-vision pair, so stale ones are listed only after both checks ran
    if evaluated:
        report_stale_exceptions(rep, exceptions, a.cvd)
    return rep.finish()


main_guard(main)

#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator emit profiles: the circle-safe avatar, the profile banners and the Instagram feed and story images.

Writes under assets/profiles/ (override with --out-dir) and records every file in assets/manifest.json.
  avatar-<px>.png                  the profile photo at each size of the profile-avatar row (400 and 800): an opaque square with the mark centred, no alpha channel.
                                   Most networks show it in a circle, so the gate is the circle: the mark's ink must stay inside the row's safe circle
                                   (a share of the radius). By default the mark is as large as fits (up to --content-fraction); a value you set is held to the same gate
  linkedin-banner-<w>x<h>.png, x-header-..., youtube-banner-..., facebook-cover-..., instagram-feed-..., instagram-story-...
                                   one image per platform at its row's size, from templates/profile/banner.html (or --template): the brand's drawn lettering (the
                                   lockup alone, or the wordmark next to the mark: --logo-svg, else assets/logo/lockup.svg, else wordmark.svg) and one line of real
                                   copy with --tagline, laid out inside the row's safe rectangle, on the light ground, 24-bit PNG. With no lockup or wordmark, or
                                   with --name, the name is live text in the system font, and the report says so
  _proof/<name>.png                the same image with the safe areas drawn on it (the platform's circle crop, the safe circle or rectangle, the areas outside in red).
                                   A proof for you to look at: never shipped, not in the manifest, and written even when a gate fails so you can see why
Gate: before anything is shipped, the ink of every image must lie inside its safe area (the circle for the avatar, the rectangle for a banner). A mark or a name
that does not fit exits 1 and writes no image. Every size and safe area comes from platform-specs.json; every row here is status U, so each file carries the label
"UNVERIFIED, recheck" until a person has read the platform's page and the row says so. Standard and Full tier write everything; the Quick tier
writes the circle-safe avatars only (400 and 800), because every business that is on a network needs that one picture, and skips the banners (an info row says so). Needs gate G3 and `brand-creator setup` (Chromium
renders the banners). Idempotent: a second run writes nothing.
"""
import html
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import svgtools  # noqa: E402
from _color import parse_hex  # noqa: E402
from _common import EXIT_FAIL, EXIT_USAGE, confine, fail, main_guard, plugin_root, read_state, write_bytes_if_changed  # noqa: E402
from _emit import add_logo_arg, art_img, card_lettering_setup, fill_template, fit_art, render_card  # noqa: E402
from px_lib import from_png  # noqa: E402
from pxio import png_color_type, png_size  # noqa: E402
from tierb import INK_TOLERANCE_PX, PROFILE_BANNERS, TierBEmit, fit_share, ink_bbox_on, ink_far  # noqa: E402

AVATAR_MAX_CONTENT = 0.7     # the largest share of the avatar the mark's box fills when the safe circle would allow more
ROW_MARK_SHARE = 0.7         # a wide safe rectangle: the mark's side as a share of its height
COLUMN_MARK_SHARE = 0.5      # a tall one: the mark's side as a share of its width ...
COLUMN_MARK_HEIGHT = 0.35    # ... and at most this share of its height
LOCKUP_ROW = 0.92, 0.36      # a drawn lockup in a wide safe rectangle: at most this share of its width and of its height
LOCKUP_COLUMN = 0.8          # ... in a tall one: at most this share of its width (and COLUMN_MARK_HEIGHT of its height)
WORDMARK_SHARE = 0.75        # a drawn wordmark's height as a share of the name's type size (the caps of live text are about that tall)
GAP_SHARE = 0.06             # the gap between the mark and the name, as a share of the safe rectangle's shorter side
TITLE_ROW, TITLE_COLUMN = 0.2, 0.1   # the name's size as a share of the safe rectangle's height (wide) or width (tall)
SUB_SHARE = 0.45             # the tagline's size as a share of the name's
RULE_SHARE = 0.08            # the accent rule's thickness as a share of the name's size
WIDE_RATIO = 1.5             # a safe rectangle at least this much wider than tall is laid out as a row
PROOF_STROKE = "crimson"
PROOF_SHADE = "rgba(255,0,0,0.2)"
PROOF_CROP = "royalblue"
PROOF_FONT_MIN, PROOF_FONT_DIV = 14, 28   # the proof label: at least this many px, else this fraction of the image's shorter side


def proof_overlay(w: int, h: int, s: dict) -> str:
    """HTML for the proof image: the areas outside the safe rectangle shaded, the rectangle dashed and labelled. Nothing of it is in the shipped file."""
    x, y, sw, sh = s["x"], s["y"], s["width"], s["height"]
    box = lambda l, t, ww, hh, extra="": f'<div style="position:absolute;left:{l:g}px;top:{t:g}px;width:{ww:g}px;height:{hh:g}px;{extra}"></div>'  # noqa: E731
    shade = f"background:{PROOF_SHADE}"
    parts = [box(0, 0, w, y, shade), box(0, y + sh, w, h - y - sh, shade), box(0, y, x, sh, shade), box(x + sw, y, w - x - sw, sh, shade),
             box(x, y, sw, sh, f"box-sizing:border-box;border:{max(2, round(min(w, h) / 200))}px dashed {PROOF_STROKE}")]
    label = f'safe area {sw:g} x {sh:g} px'
    parts.append(f'<div style="position:absolute;left:{x + 6:g}px;top:{y + 6:g}px;font:600 {max(PROOF_FONT_MIN, round(min(w, h) / PROOF_FONT_DIV))}px sans-serif;color:{PROOF_STROKE};'
                 f'background:#fff;padding:2px 6px">{label}</div>')
    return '<div style="position:absolute;left:0;top:0;width:100%;height:100%">' + "".join(parts) + "</div>"


def main() -> int:
    def args(ap) -> None:
        ap.add_argument("--content-fraction", type=float, help="share of the avatar the mark's box fills (default: the largest that fits the safe circle, "
                                                               f"up to {AVATAR_MAX_CONTENT:g}; a value you set is held to the same gate)")
        ap.add_argument("--template", help="banner template (default: templates/profile/banner.html in the plugin)")
        add_logo_arg(ap, cards=True)
        ap.add_argument("--tagline", default="", help="one line on the banners (must be a value in FACTS.md)")

    e = TierBEmit.begin("profiles", __doc__, add_args=args)
    a, rep = e.a, e.rep
    if a.tagline:
        e.require_fact(a.tagline, what="--tagline")
    if a.content_fraction is not None and not (0 < a.content_fraction <= 1):
        fail(EXIT_USAGE, f"--content-fraction {a.content_fraction:g} is outside 0 to 1")
    av = e.sizes("profile-avatar")
    ground = e.colour("light", "color.bg")
    ground_rgb = parse_hex(ground)
    out = e.out
    proofs: dict[str, bytes] = {}      # written first, even when a gate fails below: the proof shows why
    shipped: list[tuple] = []          # (rel, data, row, slot, size_px, drawing, note, extra)
    failures: list[str] = []

    # ---- avatar: the mark inside the circle, at every size
    biggest = max(av["px"])
    full = e.png(svgtools.tile(e.drawing(biggest).svg, biggest, biggest, content=1.0), biggest, biggest)
    far_full = ink_far(full)
    if not far_full:
        fail(EXIT_FAIL, "the mark has no ink: there is nothing to put in an avatar")
    limit_top = av["safe_circle"] * biggest / 2
    auto = a.content_fraction is None
    content = fit_share(limit_top, far_full, AVATAR_MAX_CONTENT) if auto else a.content_fraction
    if content <= 0:
        fail(EXIT_FAIL, f"the mark does not fit the avatar's safe circle even at the smallest size (its ink reaches {far_full:.0f} px from the centre of a {biggest} px "
                        f"canvas at a box of 1.0, the limit is {limit_top:.0f} px). Nothing is written. Redraw the mark with a rounder silhouette")
    rep.add("note:avatar content", "info", "the mark's box in the avatar", detail=f"{content:g} of the canvas ({'the largest that fits the safe circle' if auto else '--content-fraction'})")
    for n in av["px"]:
        d, raw = e.tile_png(n, content=content, ground=True, flat=True)
        try:
            rgb = from_png(raw).png_rgb()
        except ValueError as err:
            fail(EXIT_FAIL, f"the avatar at {n} px has transparent pixels ({err})")
        radius = av["safe_circle"] * n / 2
        far = ink_far(rgb, ground=ground_rgb)
        ok = far <= radius + INK_TOLERANCE_PX
        rep.add(f"check:avatar-{n} circle", "pass" if ok else "fail", f"the mark stays inside {av['safe_circle']:g} of the avatar's circle at {n} px",
                detail=f"farthest ink pixel {far:.0f} px from the centre, limit {radius:.0f}" + ("" if ok else "; lower --content-fraction"))
        if not ok:
            failures.append(f"avatar-{n}: ink {far:.0f} px from the centre, limit {radius:.0f}")
        svg = svgtools.tile(d.svg, n, n, bg=ground, content=content)
        stroke = max(2, round(n / 200))
        marks = (f'<circle cx="{n / 2:g}" cy="{n / 2:g}" r="{n / 2 - stroke / 2:g}" fill="none" stroke="{PROOF_CROP}" stroke-width="{stroke}"/>'
                 f'<circle cx="{n / 2:g}" cy="{n / 2:g}" r="{radius:g}" fill="none" stroke="{PROOF_STROKE}" stroke-width="{stroke}" stroke-dasharray="{stroke * 4} {stroke * 3}"/>')
        head, _close, tail = svg.rpartition("</svg>")    # the wrapper's closing tag is the last one: the mark's own nested <svg> closes before it
        proofs[f"avatar-{n}"] = e.png(head + marks + "</svg>" + tail, n, n, bg=ground)
        shipped.append((f"avatar-{n}.png", rgb, "profile-avatar", "profile-avatar", n, d,
                        f"profile photo, {n} px square, opaque; shown in a circle: the mark is {content:g} of the canvas and inside {av['safe_circle']:g} of the circle's radius",
                        {"safe_radius_px": round(radius, 2)}))

    # ---- banners: the mark and the name inside each platform's safe rectangle (none in the Quick tier, so nothing of theirs is read there)
    fg = e.colour("light", "color.text")
    muted, accent = e.modes["light"].get("color.muted", fg), e.modes["light"].get("color.accent", fg)
    quick = str(read_state(e.project).get("tier") or "") == "quick"
    if quick:
        rep.add("note:banners", "info", "no banners in the Quick tier", detail="the Quick tier writes the circle-safe avatar only; raise the tier with the owner's agreement "
                                                                           "(brand-creator state --set tier=standard) for the LinkedIn, X, YouTube, Facebook and Instagram images")
    else:
        tpl_path = Path(a.template).expanduser().resolve() if a.template else plugin_root() / "templates" / "profile" / "banner.html"
        if not tpl_path.is_file():
            fail(EXIT_USAGE, f"banner template not found: {tpl_path}")
        template = tpl_path.read_text(encoding="utf-8")
        e.add_input(tpl_path)
        found, layout = card_lettering_setup(rep, e.project, a, template, tpl_path.name)
    for fname, row_id in ({} if quick else PROFILE_BANNERS).items():
        sz = e.sizes(row_id)
        w, h, s = sz["width"], sz["height"], sz["safe"]
        sw, sh = s["width"], s["height"]
        wide = sw >= sh * WIDE_RATIO
        short = min(sw, sh)
        mark_px = round(sh * ROW_MARK_SHARE) if wide else round(min(sw * COLUMN_MARK_SHARE, sh * COLUMN_MARK_HEIGHT))
        title_px = round(sh * TITLE_ROW) if wide else round(sw * TITLE_COLUMN)
        d = e.drawing(mark_px)
        if layout == "lockup":
            art_w, art_h = fit_art(found[0], sw * LOCKUP_ROW[0], sh * LOCKUP_ROW[1]) if wide else fit_art(found[0], sw * LOCKUP_COLUMN, sh * COLUMN_MARK_HEIGHT)
        elif layout == "wordmark":
            art_w, art_h = fit_art(found[0], (sw - mark_px - round(short * GAP_SHARE)) if wide else sw, title_px * WORDMARK_SHARE)
        lettering = art_img(found[0], art_w, art_h, e.brand) if layout != "type" else f"<h1>{html.escape(e.brand)}</h1>"
        mark_html = d.svg.split("?>", 1)[-1].strip() if d.svg.lstrip().startswith("<?xml") else d.svg
        values = {"width": w, "height": h, "bg": ground, "fg": fg, "muted": muted, "accent": accent, "name": e.brand, "tagline": a.tagline,
                  "layout": layout, "lettering": lettering, "mark": "" if layout == "lockup" else mark_html,
                  "safe_x": f"{s['x']:g}", "safe_y": f"{s['y']:g}", "safe_w": sw, "safe_h": sh,
                  "direction": "row" if wide else "column", "align": "left" if wide else "center", "items": "flex-start" if wide else "center",
                  "gap": round(short * GAP_SHARE), "mark_px": mark_px, "title_px": title_px, "sub_px": round(title_px * SUB_SHARE),
                  "rule_w": title_px * 2, "rule_h": max(2, round(title_px * RULE_SHARE))}
        pngs = {}
        for variant, proof in (("", ""), ("-proof", proof_overlay(w, h, s))):
            src_rel = f"{out}/_build/{fname}{variant}.html"
            src = confine(e.project, src_rel, what="card source")
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text(fill_template(template, {**{k: str(v) for k, v in values.items()}, "proof": proof}, raw=("mark", "lettering", "proof")),
                           encoding="utf-8")
            render_card(e.project, src_rel, w, h, f"{out}/_build/{fname}{variant}.png", "light")
            pngs[variant] = confine(e.project, f"{out}/_build/{fname}{variant}.png", what="card").read_bytes()
        proofs[fname] = pngs["-proof"]
        try:
            rgb = from_png(pngs[""]).png_rgb()
        except ValueError as err:
            fail(EXIT_FAIL, f"the {fname} image has transparent pixels ({err}); the template must paint a ground over the whole card")
        got = png_size(rgb)
        rep.add(f"check:{fname} size", "pass" if got == (w, h) else "fail", "PNG size equals the spec row", detail=f"{got[0]}x{got[1]}, wanted {w}x{h}")
        if got != (w, h):
            failures.append(f"{fname}: {got[0]}x{got[1]}, wanted {w}x{h}")
        bb = ink_bbox_on(rgb, ground_rgb)
        inside = bb is not None and bb[0] >= s["x"] - INK_TOLERANCE_PX and bb[1] >= s["y"] - INK_TOLERANCE_PX \
            and bb[2] <= s["x"] + sw + INK_TOLERANCE_PX and bb[3] <= s["y"] + sh + INK_TOLERANCE_PX
        rep.add(f"check:{fname} safe area", "pass" if inside else "fail", f"everything drawn on the {fname} stays inside its safe rectangle",
                detail=f"ink box {bb}, safe rectangle x {s['x']:g} to {s['x'] + sw:g}, y {s['y']:g} to {s['y'] + sh:g}" + ("" if inside else "; see the proof image; a shorter name or a smaller template fixes it"))
        if not inside:
            failures.append(f"{fname}: ink box {bb} is not inside the safe rectangle")
        what = {"lockup": "the drawn lockup", "wordmark": "the mark and the drawn wordmark", "type": "the mark and the name as text"}[layout]
        shipped.append((f"{fname}-{w}x{h}.png", rgb, row_id, f"profile-{fname}", (w, h), d,
                        what + (" and one line of real copy" if a.tagline else "") + f" inside the {sw:g} x {sh:g} px safe rectangle, light ground, 24-bit PNG",
                        {"safe": {"x": s["x"], "y": s["y"], "width": sw, "height": sh}}))

    # ---- proofs first (never shipped), then the gate, then the files
    for name, data in proofs.items():
        write_bytes_if_changed(confine(e.project, f"{out}/_proof/{name}.png", what="proof image"), data)
    rep.add("proofs", "info", "safe-area proof images written (never shipped, not in the manifest)", detail=f"{out}/_proof/ ({len(proofs)} PNG files)")
    if failures:
        fail(EXIT_FAIL, "an image does not fit its safe area: " + "; ".join(failures[:4]) + f". Nothing is written; look at {out}/_proof/")
    for rel_name, data, row_id, slot, size_px, d, note, extra in shipped:
        e.slot(f"{out}/{rel_name}", data, [row_id], slot=slot, size_px=size_px, drawing=d, resampled_by="OURS" if slot == "profile-avatar" else "PAGE", note=note, **extra)
    return e.finish()


main_guard(main)

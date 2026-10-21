#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator emit social: Open Graph card, GitHub social preview, README header (light and dark).

Every image is a designed card: an HTML page (templates/card.html, or --template) filled from the built tokens, the
mark and the brand's drawn lettering (the lockup alone, or the wordmark next to the mark: --logo-svg, else assets/logo/lockup.svg,
else wordmark.svg; the dark README header takes <name>-dark.svg next to it), rendered to PNG by the single Chromium driver (render.mjs
card). With no lockup or wordmark, or with --name, the name is live text in the system font, and the report says so. Sizes come from
platform-specs.json only.
  assets/social/og-<w>x<h>-<hash>.png   a new URL whenever the bytes change (platforms cache by URL)
  assets/social/github-social-<w>x<h>.png                only when INVENTORY.md or brief/BRIEF.md lists a code repository (or --repo-images yes)
  assets/social/readme-header-light.png, readme-header-dark.png   the same condition; otherwise an info row says why they were skipped
  assets/social/og-meta.html            only with --site-url (og:image must be an absolute URL)
  assets/social/posts/                  only with --posts (Standard tier): a 4:5 carousel (cover, one slide per fact, closing), a 1:1 post and an
                                        educational 4:5 post of numbered points, from templates/social/ (or --post-template-dir). Every word on
                                        a post is the value or label of a FACTS.md row chosen with --post-fact (repeatable); nothing is invented.
                                        When brief/BRIEF.md marks a regulated profession, the post pages carry data-regulated-checklist and
                                        posts/PRE-PUBLICATION.md lists the checklist the owner ticks before anything is published.
Intermediate HTML and PNGs live in assets/social/_build/. Needs gate G3 and `brand-creator setup`.
"""
import base64
import hashlib
import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import qa_rules  # noqa: E402
import specs  # noqa: E402
from _common import EXIT_FAIL, EXIT_USAGE, Parser, Report, confine, fail, find_project, main_guard, plugin_root, read_state, today  # noqa: E402
from _emit import (add_common_args, add_logo_arg, art_img, card_lettering, card_lettering_setup, card_mark_size, dark_sibling,  # noqa: E402
                   facts as facts_of, fill_template, fit_art, lettering_art, lettering_files, mark_accent, mark_tagline,
                   load_mark, load_tokens, need_colors, regulated_profession, render_card, lists_repository, require_gate,
                   require_tier)
from manifest import Manifest  # noqa: E402
from pxio import png_size  # noqa: E402

NOTE_MAX = 110   # characters of a post's text kept in its manifest note
EDU_MAX_POINTS = 4   # numbered points an educational post can hold and stay readable
# the side-by-side image (templates/lineup.html), as shares of the card's height h unless named otherwise
LINEUP_ROW = 0.86        # the row of marks: at most this share of the card's width
LINEUP_GAP_X = 0.04      # between two cells, as a share of the card's width; every mark has a cell of the same width
LINEUP_MARK = 0.42       # a mark's box: at most this, and at most LINEUP_CELL of its cell's width
LINEUP_CELL = 0.8
LINEUP_CAPTION = 0.10    # the drawn wordmark (or the typed name) under each mark: at most this tall, one height for all
LINEUP_TITLE = 0.11      # the brand's name typed above, or its drawn lettering up to LINEUP_TITLE_ART of the width and height
LINEUP_TITLE_ART = 0.6, 0.14


fill = fill_template


def lineup_members(project: Path, a, rules: dict, rep: Report) -> list[dict]:
    """Every mark of qa/rules.json marks for the side-by-side image: its main drawing and dark one, and its drawn wordmark
    (<id>-wordmark.svg) and dark one when they exist; a warning names each mark whose name is typed instead."""
    members = []
    for m in rules["marks"].values():
        light, dark, paths = load_mark(project, a, m)
        rep.inputs += [q for q in paths if q not in rep.inputs]
        wm_rel = lettering_files(m["id"])[1]
        wm = lettering_art(project, wm_rel, rep.inputs) if confine(project, wm_rel, what="wordmark").is_file() else None
        if wm is None:
            rep.add(f"note:lineup {m['id']}", "warn", "a name typed in the system font",
                    detail=f"no {wm_rel}: {m['name']} is typed under its mark; draw the wordmark (outlined, P6) for the brand's own lettering")
        members.append({"id": m["id"], "name": m["name"], "light": light, "dark": dark, "wordmark": wm[0] if wm else None,
                        "wordmark_dark": dark_sibling(project, wm_rel, rep.inputs) if wm else None})
    return members


def lineup_values(members: list[dict], layout: str, art: str | None, name: str, mode: str, w: int, h: int) -> dict:
    """The values of templates/lineup.html at w x h: each mark (its dark drawing on a dark card when it has one) as an image in its cell,
    the wordmarks under them at one height, and the brand's lettering or typed name above. Pixel art is set at a whole-number scale."""
    n = len(members)
    gap_x = round(w * LINEUP_GAP_X)
    cell_w = (w * LINEUP_ROW - (n - 1) * gap_x) / n
    box = min(h * LINEUP_MARK, cell_w * LINEUP_CELL)
    words = [m["wordmark_dark"] if mode == "dark" and m["wordmark_dark"] else m["wordmark"] for m in members]
    cap = min([fit_art(x, cell_w, h * LINEUP_CAPTION)[1] for x in words if x] or [round(h * LINEUP_CAPTION)])
    figs = []
    for m, word in zip(members, words):
        drawing = m["dark"] if mode == "dark" and m["dark"] else m["light"]
        mw, mh = fit_art(drawing, box, box)
        data = base64.b64encode(drawing.encode("utf-8")).decode("ascii")
        caption = art_img(word, *fit_art(word, cell_w, cap), m["name"]) if word else html.escape(m["name"])
        figs.append(f'<figure><img class="m" alt="{html.escape(m["name"])} mark" width="{mw}" height="{mh}" src="data:image/svg+xml;base64,{data}">'
                    f"<figcaption>{caption}</figcaption></figure>")
    title = (art_img(art, *fit_art(art, w * LINEUP_TITLE_ART[0], h * LINEUP_TITLE_ART[1]), name) if layout != "type" and art
             else f"<h1>{html.escape(name)}</h1>")
    title_px = round(h * LINEUP_TITLE)
    return {"lettering": title, "marks": "".join(figs), "gap": round(h * 0.06), "gap_x": gap_x, "cell_w": int(cell_w), "caption_gap": round(h * 0.03), "caption_h": cap,
            "caption_px": round(cap * 0.8), "title_px": title_px, "sub_px": round(h * 0.045), "rule_w": title_px * 2, "rule_h": max(2, round(h * 0.012))}


def main() -> int:
    ap = Parser(prog="brand-creator emit social", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_common_args(ap)
    ap.add_argument("--template", help="card template (default: templates/card.html in the plugin; for the side-by-side image of a project with "
                                        "several marks, templates/lineup.html)")
    add_logo_arg(ap, cards=True)
    ap.add_argument("--name", help="name on the card, set as text (default: the drawn lockup or wordmark, else the name in BRAND-STATE.md as text)")
    ap.add_argument("--tagline", default="", help="one line under the name (must be a fact from FACTS.md)")
    ap.add_argument("--site-url", help="absolute site URL; writes og-meta.html with absolute og:image")
    ap.add_argument("--out-dir", help="folder inside the project (default assets/social; with --mark, assets/social/<mark>)")
    ap.add_argument("--repo-images", choices=("auto", "yes", "no"), default="auto",
                    help="the GitHub social preview and the README headers: auto (default) writes them only when INVENTORY.md or the brief lists a code repository; yes or no forces it")
    ap.add_argument("--posts", action="store_true", help="also write the post templates (Standard tier): carousel, square and educational posts")
    ap.add_argument("--post-fact", action="append", default=[], metavar="LABEL", help="a FACTS.md label whose value is a post's text (repeatable; needed with --posts)")
    ap.add_argument("--post-template-dir", help="folder with your copies of the post templates (default: templates/social in the plugin)")
    a = ap.parse_args()
    project = find_project(a.project)
    require_gate(project, "G3", for_what="emit social")
    if a.posts:
        require_tier(project, ("standard", "full"), what="social posts")
        if not a.post_fact:
            fail(EXIT_USAGE, "--posts needs at least one --post-fact LABEL (a FACTS.md row): the posts take their words from FACTS.md and nowhere else. "
                             f"Available labels: {', '.join(sorted(facts_of(project))) or 'none yet'}")
        lang = str(read_state(project).data().get("content_languages") or "").split(",")[0].strip()
        if not lang:
            fail(EXIT_USAGE, "content_languages is not set in BRAND-STATE.md; it is never defaulted from the chat language. Set it: "
                             "brand-creator state --set content_languages=en")
    st = read_state(project).data()
    rules, _rules_src = qa_rules.load(project)
    mark = qa_rules.select_mark(a, rules, required=False)
    mid = mark["id"] if mark else None
    lineup = bool(rules["marks"]) and mark is None   # several marks and no --mark: the images show every mark side by side
    if lineup and a.posts:
        fail(EXIT_USAGE, "a post shows one mark: pass --mark <id> with --posts")
    name = a.name or (mark["name"] if mark else str(st.get("name") or st.get("slug")))
    light, dark, paths = (None, None, []) if lineup else load_mark(project, a, mark)
    modes, tokens_path = load_tokens(project, a)
    tpl_path = Path(a.template).expanduser().resolve() if a.template else plugin_root() / "templates" / ("lineup.html" if lineup else "card.html")
    if not tpl_path.is_file():
        fail(EXIT_USAGE, f"card template not found: {tpl_path}")
    template = tpl_path.read_text(encoding="utf-8")
    out = (a.out_dir or (f"assets/social/{mid}" if mid else "assets/social")).strip("/")
    og, gh, rh = specs.sizes("open-graph"), specs.sizes("github-social"), specs.sizes("readme-header")

    rep = Report("emit-social" + (f"/{mid}" if mid else ""), project, paths + [tokens_path], renderer=a.renderer)
    rep.inputs += [q for q in (project / qa_rules.RULES_FILE,) if q.is_file()]
    mf = Manifest(project)
    of_mark = {"mark": mid} if mid else {}            # every row of a --mark run names its mark
    tagline = mark_tagline(project, mark, a.tagline, rep.inputs)
    found, layout = card_lettering_setup(rep, project, a, template, tpl_path.name, mid)
    members = lineup_members(project, a, rules, rep) if lineup else []

    def render(variant: str, mode: str, w: int, h: int, values: dict, raw: tuple) -> bytes:
        bg, fg = need_colors(modes, mode, "color.bg", "color.text")
        values = {"width": w, "height": h, "bg": bg, "fg": fg, "muted": modes[mode].get("color.muted", fg), "accent": mark_accent(modes, mode, mark, fg),
                  "name": name, "tagline": tagline, **values}
        src_rel = f"{out}/_build/{variant}.html"
        png_rel = f"{out}/_build/{variant}.png"
        src = confine(project, src_rel, what="card source")
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(fill(template, {k: str(v) for k, v in values.items()}, raw=raw), encoding="utf-8")
        render_card(project, src_rel, w, h, png_rel, mode)
        data = confine(project, png_rel, what="card").read_bytes()
        got = png_size(data)
        rep.add(f"check:{variant} size", "pass" if got == (w, h) else "fail", "PNG size equals the spec row", detail=f"{got[0]}x{got[1]}, wanted {w}x{h}")
        return data

    def card(variant: str, mode: str, w: int, h: int, mark_svg: str | None, art: str | None) -> bytes:
        if lineup:
            return render(variant, mode, w, h, lineup_values(members, layout, art, name, mode, w, h), ("lettering", "marks"))
        values = {"layout": layout, "lettering": card_lettering(layout, art, name, w, h), "mark_size": card_mark_size(mark_svg, h),
                  "mark": "" if layout == "lockup" else re.sub(r"^\s*<\?xml[^>]*>\s*", "", mark_svg)}
        return render(variant, mode, w, h, values, ("mark", "lettering"))

    # Open Graph: new URL per change
    art = found[0] if found else None
    d = card("og", "light", og["width"], og["height"], light, art)
    h8 = hashlib.sha256(d).hexdigest()[:8]
    og_rel = f"og-{og['width']}x{og['height']}-{h8}.png"
    changed = mf.put(f"{out}/{og_rel}", d, emitter="social", specs=["open-graph"], width=og["width"], height=og["height"], **of_mark)
    rep.add(f"file:{og_rel}", "pass", "written" if changed else "unchanged", bytes=len(d))
    stale_og = sorted(p.name for p in (project / out).glob("og-*.png") if p.name != og_rel)
    if stale_og:
        rep.add("note:old og images", "warn", "superseded Open Graph files", detail=f"{', '.join(stale_og)} are no longer referenced; move them to removed-<date>/")

    repo_reason = lists_repository(project) if a.repo_images == "auto" else ("--repo-images yes" if a.repo_images == "yes" else None)
    repo_images = repo_reason is not None
    rep.inputs += [q for q in (project / "INVENTORY.md", project / "brief" / "BRIEF.md") if q.is_file() and q not in rep.inputs]
    if not repo_images:
        rep.add("note:repo-images", "info", "no GitHub social preview or README headers",
                detail="no code repository is listed in the brief or the inventory, so the 1280 x 640 GitHub preview and the README headers are skipped; "
                       "add the repository to the brief, or pass --repo-images yes")
    else:
        # GitHub social preview
        d = card("github-social", "light", gh["width"], gh["height"], light, art)
        gh_rel = f"github-social-{gh['width']}x{gh['height']}.png"
        changed = mf.put(f"{out}/{gh_rel}", d, emitter="social", specs=["github-social"], width=gh["width"], height=gh["height"], **of_mark)
        rep.add(f"file:{gh_rel}", "pass", "written" if changed else "unchanged", bytes=len(d))

        # README header, light and dark
        art_dark = dark_sibling(project, found[1], rep.inputs) if layout != "type" else None
        for mode, mark_art, lettering_svg in (("light", light, art), ("dark", dark or light, art_dark or art)):
            d = card(f"readme-header-{mode}", mode, rh["width"], rh["height"], mark_art, lettering_svg)
            rel_name = f"readme-header-{mode}.png"
            changed = mf.put(f"{out}/{rel_name}", d, emitter="social", specs=["readme-header"], width=rh["width"], height=rh["height"], **of_mark)
            rep.add(f"file:{rel_name}", "pass", "written" if changed else "unchanged", bytes=len(d))
        if dark is None and layout != "lockup" and not lineup:   # a lockup card draws no separate mark; the side-by-side image checks each mark
            rep.add("note:readme-header-dark", "warn", "no dark artwork", detail="the dark README header reuses the light mark artwork")
        for m in members:   # the side-by-side image: each mark and wordmark on the dark header
            if m["dark"] is None:
                rep.add(f"note:readme-header-dark {m['id']}", "warn", "no dark artwork",
                        detail=f"the dark README header shows {m['id']}'s light drawing: draw the -dark.svg next to its main drawing")
            if m["wordmark"] and m["wordmark_dark"] is None:
                rep.add(f"note:readme-header-dark {m['id']} lettering", "warn", "no dark lettering",
                        detail=f"no {Path(lettering_files(m['id'])[1]).stem}-dark.svg: the dark README header reuses {m['id']}'s light wordmark")
        if layout != "type" and art_dark is None:
            dark_name = str(Path(found[1]).with_name(Path(found[1]).stem + "-dark.svg"))
            rep.add("note:readme-header-dark lettering", "warn", "no dark lettering", detail=f"no {dark_name}: the dark README header reuses the light {layout}")

    used_rows = ["open-graph"] + (["github-social", "readme-header"] if repo_images else [])
    if a.posts:
        used_rows += ["social-post-4x5", "social-post-1x1"]
        rep.inputs.append(project / "FACTS.md")
        fx = facts_of(project)
        picked = []
        for lab in a.post_fact:
            if lab.strip().lower() not in fx:
                fail(EXIT_FAIL, f"--post-fact {lab!r} is not a label in FACTS.md (available: {', '.join(sorted(fx))}). Add the row with its source first")
            picked.append((lab.strip().lower(), fx[lab.strip().lower()]))
        edu_max = EDU_MAX_POINTS
        if len(picked) > edu_max:
            fail(EXIT_USAGE, f"an educational post holds at most {edu_max} numbered points; pass at most {edu_max} --post-fact labels")
        p4, p1 = specs.sizes("social-post-4x5"), specs.sizes("social-post-1x1")
        tdir = Path(a.post_template_dir).expanduser().resolve() if a.post_template_dir else plugin_root() / "templates" / "social"
        if not tdir.is_dir():
            fail(EXIT_USAGE, f"--post-template-dir not found: {tdir}")
        prof, answered = regulated_profession(project)
        if prof:
            rep.add("note:regulated", "warn", "regulated profession: the pre-publication checklist applies",
                    detail=f"brief/BRIEF.md names {prof!r}: the posts carry data-regulated-checklist and {out}/posts/PRE-PUBLICATION.md lists what the owner ticks first")
        elif not answered:
            rep.add("note:regulated", "warn", "the brief does not say whether the profession is regulated",
                    detail="brief/BRIEF.md has no answered 'Regulated profession' line: answer it before posting (a regulated profession needs the pre-publication checklist)")
        reg_attr = f' data-regulated-checklist="skills/brand-creator/references/regulated-industries.md#typical-guardrails" data-regulated-profession="{html.escape(prof, quote=True)}"' if prof else ""
        bg, fg = need_colors(modes, "light", "color.bg", "color.text")
        muted, accent = modes["light"].get("color.muted", fg), mark_accent(modes, "light", mark, fg)
        mark_art = re.sub(r"^\s*<\?xml[^>]*>\s*", "", light)

        def post(kind: str, tpl_name: str, size: dict, name_: str, **vals) -> str:
            tp = tdir / f"{tpl_name}.html"
            if not tp.is_file():
                fail(EXIT_USAGE, f"post template not found: {tp}")
            values = {"lang": lang, "width": size["width"], "height": size["height"], "bg": bg, "fg": fg, "muted": muted, "accent": accent, "name": name,
                      "mark": mark_art, "kicker": "", "headline": "", "counter": "", "points_block": "", "regulated_attr": reg_attr}
            values.update(vals)
            src_rel = f"{out}/_build/posts/{name_}.html"
            src = confine(project, src_rel, what="post source")
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text(fill(tp.read_text(encoding="utf-8"), {k: str(v) for k, v in values.items()}, raw=("mark", "points_block", "regulated_attr")), encoding="utf-8")
            png_rel = f"{out}/_build/posts/{name_}.png"
            render_card(project, src_rel, size["width"], size["height"], png_rel, "light")
            data = confine(project, png_rel, what="post").read_bytes()
            got = png_size(data)
            rep.add(f"check:post {name_} size", "pass" if got == (size["width"], size["height"]) else "fail", "PNG size equals the spec row",
                    detail=f"{got[0]}x{got[1]}, wanted {size['width']}x{size['height']}")
            row = "social-post-1x1" if size is p1 else "social-post-4x5"
            changed = mf.put(f"{out}/posts/{name_}.png", data, emitter="social", specs=[row], width=size["width"], height=size["height"], kind=kind,
                             note=vals.get("headline", "")[:NOTE_MAX], **of_mark)
            rep.add(f"file:posts/{name_}.png", "pass", "written" if changed else "unchanged", bytes=len(data))
            texts[name_] = vals.get("headline", "") if not vals.get("points_block") else "; ".join(f"{l}: {v}" for l, v in picked)
            return name_

        written, texts = [], {}
        total = len(picked) + 2
        written.append(post("carousel", "post-4x5", p4, "carousel-4x5-01", headline=name, counter=f"01 / {total:02d}"))
        for i, (lab, val) in enumerate(picked, start=2):
            written.append(post("carousel", "post-4x5", p4, f"carousel-4x5-{i:02d}", headline=val, kicker=lab, counter=f"{i:02d} / {total:02d}"))
        written.append(post("carousel", "post-4x5", p4, f"carousel-4x5-{total:02d}", headline=name, counter=f"{total:02d} / {total:02d}"))
        lab0, val0 = picked[0]
        written.append(post("square", "post-1x1", p1, "post-1x1", headline=val0, kicker=lab0))
        pts = "".join(f'<li><span class="n">{i}</span><div><div class="lab">{html.escape(lab)}</div><div class="val">{html.escape(val)}</div></div></li>'
                      for i, (lab, val) in enumerate(picked, start=1))
        written.append(post("educational", "post-educational", p4, "educational-4x5", headline=name, points_block=pts))
        rep.extra["posts"] = written
        if prof:
            lines = [f"# Pre-publication checklist: social posts", "",
                     f"The brief names a regulated profession ({prof}). These posts are drafts: nothing is posted until the owner has ticked every line. "
                     "The lines are generic guardrails (skills/brand-creator/references/regulated-industries.md, section Typical guardrails); confirm each "
                     "for your profession and country, and use the dated rules table in brief/BRIEF.md.", "",
                     "- [ ] the text is informative; promotional communication is labelled as such",
                     "- [ ] no comparative or evaluative claim (best, leading, number one) and no claim about competitors",
                     "- [ ] no client testimonial, or only with consent and where the rules allow it",
                     "- [ ] no pressure, no guarantee of outcome, no fee-based referral",
                     "- [ ] the formal name or designation the regulator requires is used, consistently",
                     "- [ ] every mandatory disclosure this surface needs (registration number, supervising body, insurance) is present",
                     "- [ ] each claim is a FACTS.md row the owner confirmed", "", "## Posts", ""]
            lines += [f"- {n}.png: {texts[n]}" for n in written]
            changed = mf.put(f"{out}/posts/PRE-PUBLICATION.md", ("\n".join(lines) + "\n").encode(), emitter="social", specs=["social-post-4x5"],
                             note="regulated profession: the owner ticks it before posting", **of_mark)
            rep.add("file:posts/PRE-PUBLICATION.md", "pass", "written" if changed else "unchanged")

    if a.site_url:
        if not re.match(r"^https?://", a.site_url):
            fail(EXIT_USAGE, "--site-url must be an absolute http(s) URL")
        base = a.site_url.rstrip("/")
        meta = "\n".join([
            "<!-- Generated by brand-creator emit social. Paste into <head>. The file name changes whenever the image changes. -->",
            f'<meta property="og:image" content="{base}/{og_rel}">',
            f'<meta property="og:image:width" content="{og["width"]}">',
            f'<meta property="og:image:height" content="{og["height"]}">',
            f'<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:image" content="{base}/{og_rel}">', ""])
        changed = mf.put(f"{out}/og-meta.html", meta.encode(), emitter="social", specs=["open-graph"], **of_mark)
        rep.add("file:og-meta.html", "pass", "written" if changed else "unchanged")
    else:
        rep.add("note:og-meta", "info", "no --site-url", detail="og:image needs an absolute URL; re-run with --site-url to write og-meta.html")

    stamped, warns = specs.stamp(used_rows, today())
    mf.stamp_specs(stamped)
    retired = mf.retire_unwritten("social", out, keep=lambda p: re.fullmatch(r"og-\d+x\d+-[0-9a-f]{8}\.png", Path(p).name) is not None
                                  or (not a.posts and p.startswith(f"{out}/posts/")), mark=mid)
    for p in retired:
        rep.add(f"retired:{p}", "warn", "slot no longer emitted",
                detail=f"an earlier run wrote {p} but this run did not: the file was moved to removed-{today()}/ and its manifest row dropped")
    mf.save()
    for wmsg in warns:
        rep.add("spec", "warn", "platform spec", detail=wmsg)
    rep.extra.update({"out_dir": out, "changed": mf.changed, "unchanged": mf.unchanged, "specs": stamped, "template": str(tpl_path.name), "retired": retired})
    print(f"emit social: {len(mf.changed)} written, {len(mf.unchanged)} unchanged ({out}/)")
    return rep.finish()


main_guard(main)

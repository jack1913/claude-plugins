#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator emit developer: the brand where developers meet it.

Writes under assets/developer/ (override with --out-dir) and records every file in assets/manifest.json.
  email/<slug>-email-logo.png, @2x, @3x   the logo art, transparent, 24 px high at 1x (email-logo spec row; --height overrides)
  nuget/<slug>-nuget-<px>.png             package-registry icon (NuGet-style), opaque ground, the nuget-icon spec row, size limit checked
  avatar/<slug>-avatar-<px>.png           organisation avatar, opaque ground (github-org-avatar spec row)
  cli/identity.txt, identity.plain.txt    the name (and --tagline, which must be a FACTS.md value) for a terminal: a brand colour is written as
                                          24-bit only when it reaches the cli-identity contrast on a white AND a black ground, otherwise the
                                          named ANSI colour nearest in hue is used (the user's terminal theme decides how that looks)
The registry icon and the avatar are shrunk by the host from one large file: pass --master-band NAME with --exemption TEXT to draw them
from a coarse-grid band instead of the one the size picks (the rule is in qa/rules.json). Needs gate G3. Idempotent.
"""
import colorsys
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import svgtools  # noqa: E402
from _color import parse_hex, wcag_ratio  # noqa: E402
from _common import EXIT_USAGE, fail, main_guard  # noqa: E402
from _emit import Emit, add_logo_arg  # noqa: E402

CONTENT = 0.62  # share of an opaque tile the mark fills
ANSI_BY_HUE = ("red", "yellow", "green", "cyan", "blue", "magenta")          # the six named colours, one per sixth of the hue circle
ANSI_INDEX = {"red": 1, "green": 2, "yellow": 3, "blue": 4, "magenta": 5, "cyan": 6}   # SGR 3<index> is the foreground colour
NOTE_MAX = 110   # characters of the reason kept in a manifest note
GREY_BELOW = 0.12  # HSL saturation under which a colour has no hue worth naming


def ansi_for(hex_: str) -> tuple[str, str] | None:
    r, g, b = (c / 255 for c in parse_hex(hex_))
    h, _l, s = colorsys.rgb_to_hls(r, g, b)
    if s < GREY_BELOW:
        return None
    name = ANSI_BY_HUE[round(h * len(ANSI_BY_HUE)) % len(ANSI_BY_HUE)]
    return f"3{ANSI_INDEX[name]}", name


def cli_colour(e: Emit, role: str, grounds: dict, need: float) -> tuple[str, str]:
    """-> (escape sequence, a one-line reason) for one brand role."""
    tried = []
    for mode in ("light", "dark"):
        hx = e.modes[mode].get(role)
        if hx is None:
            continue
        ratios = {g: wcag_ratio(parse_hex(hx), parse_hex(c)) for g, c in grounds.items()}
        tried.append(f"{mode} {hx}: " + ", ".join(f"{r:.2f}:1 on {g}" for g, r in ratios.items()))
        if all(r >= need for r in ratios.values()):
            r, g_, b = parse_hex(hx)
            return f"\x1b[38;2;{r};{g_};{b}m", f"24-bit {hx} ({mode} value) reaches {need:g}:1 on both grounds"
    named = ansi_for(e.modes["light"].get(role) or e.modes["dark"][role])
    why = "; ".join(tried) + f"; below {need:g}:1 on a ground"
    if named is None:
        return "", f"no 24-bit value reaches {need:g}:1 on both grounds and the colour has no hue to name, so the terminal's own text colour is used ({why})"
    return f"\x1b[{named[0]}m", f"ANSI {named[0]} ({named[1]}) instead of 24-bit: {why}"


def main() -> int:
    def args(ap):
        add_logo_arg(ap)
        ap.add_argument("--height", type=int, help="display height of the e-mail logo in px at 1x (default: the email-logo spec row)")
        ap.add_argument("--tagline", default="", help="a line under the name in identity.txt; must be a value in FACTS.md")
        ap.add_argument("--content-fraction", type=float, default=CONTENT, help=f"share of the registry icon and avatar the mark fills (default {CONTENT}); the downscale gate measures the result")
        ap.add_argument("--master-band", help="band for the registry icon and the avatar (default: the band the file's size picks)")
        ap.add_argument("--exemption", help="one line: why --master-band differs from the picker")

    e = Emit.begin("developer", __doc__, add_args=args)
    em, ng, av, cli = e.sizes("email-logo"), e.sizes("nuget-icon"), e.sizes("github-org-avatar"), e.sizes("cli-identity")
    if e.a.exemption and not e.a.master_band:
        fail(EXIT_USAGE, "--exemption needs --master-band")
    for n in (ng["px"], av["px"]):
        e.check_master_band(n, e.a.master_band, e.a.exemption)
    tagline = e.require_fact(e.a.tagline, what="--tagline") if e.a.tagline else ""
    ground = e.colour("light", "color.bg")
    art, art_src = e.logo_art()
    vb = svgtools.viewbox(svgtools.parse(art))
    e.rep.add("note:logo art", "info", "logo art used for the e-mail logo", detail=art_src)

    h1 = e.a.height or em["display_height"]
    for sc in em["scales"]:
        h = h1 * sc
        w = round(h * vb[2] / vb[3])
        d = None
        svg = art
        if art_src == "the mark":
            d = e.drawing(max(w, h))
            svg = d.svg
        suffix = "" if sc == 1 else f"@{sc}x"
        e.slot(f"{e.out}/email/{e.slug}-email-logo{suffix}.png", e.png(svgtools.fit(svg, w, h), w, h), ["email-logo"], slot="email-logo",
               size_px=(w, h), drawing=d, note=f"shown {h1} px high, @{sc}x, transparent")

    for key, spec, row, folder, label in (("px", ng, "nuget-icon", "nuget", "nuget"), ("px", av, "github-org-avatar", "avatar", "avatar")):
        n = spec[key]
        d = e.drawing(n, band=e.a.master_band)
        data = e.png(svgtools.tile(d.svg, n, n, bg=ground, content=e.a.content_fraction), n, n, bg=ground)
        e.slot(f"{e.out}/{folder}/{e.slug}-{label}-{n}.png", data, [row], slot=f"developer-{label}", size_px=n, drawing=d,
               exemption=e.a.exemption, resampled_by="SYS", qa=["downscale"],
               note="one large file the host shrinks; opaque ground" + (f"; drawn from band {d.band}" if d.band else ""))
        if label == "nuget":
            size = len(data)
            e.rep.add("check:nuget icon size", "pass" if size <= spec["max_bytes"] else "fail", "the icon file is within the registry's size limit",
                      detail=f"{size} bytes, limit {spec['max_bytes']}")

    # CLI identity text
    grounds = cli["grounds"]
    lines, plain = [], []
    name_role = "color.accent" if "color.accent" in e.modes["light"] else "color.text"
    seq, why = cli_colour(e, name_role, grounds, cli["min_contrast"])
    e.rep.add(f"cli:{name_role}", "info", "terminal colour chosen by contrast", detail=why)
    lines.append(f"\x1b[1m{seq}{e.brand}\x1b[0m")
    plain.append(e.brand)
    if tagline:
        lines.append(tagline)
        plain.append(tagline)
    e.put(f"{e.out}/cli/identity.txt", ("\n".join(lines) + "\n").encode(), ["cli-identity"], slot="cli-identity", resampled_by="PAGE",
          note="ANSI colour; " + why[:NOTE_MAX])
    e.put(f"{e.out}/cli/identity.plain.txt", ("\n".join(plain) + "\n").encode(), ["cli-identity"], slot="cli-identity-plain", resampled_by="PAGE",
          note="no escape codes (NO_COLOR, pipes, logs)")
    return e.finish()


main_guard(main)

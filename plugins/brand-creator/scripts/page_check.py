#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator page-check: measure one rendered page against the brand.

    brand-creator page-check <page.html> [--project DIR] [--widths 360,390,...] [--schemes light,dark]
    brand-creator page-check --from DIR <page.html> [--project DIR] ...
    brand-creator page-check --url http://localhost:<port>/<path> [--project DIR] ...

The page is a page of the project, a page of a built site anywhere (--from DIR: the folder is copied into the data folder's scratch area and the copy is
served, so the site is only read), or a page already served on this machine (--url: localhost, 127.0.0.1 or [::1] only; a remote page is refused).
It is opened in Chromium at each width (default 360, 390, 768, 1024, 1440 and 1920 css px; qa/rules.json `page.widths` or --widths override) in each colour
scheme, with every request to another origin aborted. The browser only measures (`render.mjs page-measure`); the judging is here and in
scripts/pagelib/pagecheck.py, against the built tokens and the `page` block of qa/rules.json. The report is assets/_checks/page-check/<slug>-<hash6>.json,
one per page. The rows are `page:target` and, per view, `page:load:<width>-<scheme>` (the page and console errors, failed requests and requests to another origin).
Per colour scheme it also reports `page:colours:<scheme>` (every colour the page paints is a semantic colour of that theme) and `page:pairs:<scheme>` (every text colour on its
ground is a declared pair, or is measured against WCAG), `page:motion` (every duration and easing is a motion token) and `page:claims` (outside a `data-sample`, every number and
status word is backed by FACTS.md); `page:samples` lists the labelled samples, and the report holds the same list as `samples`.
`page:words` warns, never fails, for each word the brand forbids (the Forbidden bullets of brief/BRIEF.md and research/cliches.md; the book check also adds the book's own `lint.forbidden`, the page check does not) that the text of the page holds; info when none is listed.
`page:mark-file`, `page:mark-band` and `page:mark-clear-space` judge the brand mark (`data-brand-mark`, an image named `logo`, `mark` or `wordmark`, alone or followed by `-`, `_` or `@` and more (`mark` and `wordmark` only for an `.svg` file), or an image byte for byte like a logo file): it is a logo file of
the project, the drawing its size calls for, and has its clear space.
Each entry of qa/rules.json `page.rules` is a brand rule of the owner's and gives `page:rule:<id>` (one mark per screen, a button says at most three words, the words around an accent): it fails once
the "(rule)" line it is tied to (`g4`) is recorded at G4, and before that only warns.
Generic tells (skills/brand-creator/references/page-tells.json) give `tell:<id>`, a warning that names where the pattern is (an eyebrow over a heading, an arrow glued to a label, a run of middle
dots, a stock label on the hero's second action, too much text in the hero, a mock-up built of styled boxes, three equal tiles in a row); a tell the owner adopts as a rule of kind `tell` is judged by its
`page:rule:<id>` row instead. `note:stock-anatomy` is an info row for a page in the stock order. `tell:stray-box` looks for what no other check does: a box left outside its place once the animations that end have ended, still shown
outside its parent's box or off the screen (each width is measured again in a window 1300 px high for it alone); a page with an animation that never ends or follows a scroll or view timeline is NOT verified for it.
Over all views it reports `page:fonts` (every text is set in a family a `font.*` token names, and the browser drew it in that face) and `page:display-size` (no text in the
`font.display` face is under `page.display_min_px`).

Exit 0 pass (warnings allowed), 1 a row failed, 2 usage error (no target, two targets, a page that does not exist, a remote URL, a bad width or scheme, a
--from folder of more than 5000 files or 200 MB, a bad qa/rules.json page block, a `tell` rule that names no tell), 3 cannot run (no built tokens, no node, Chromium missing or no view measured).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
sys.path.insert(0, str(HERE / "pagelib"))
import pagecheck as pc  # noqa: E402
import qa_rules  # noqa: E402
from _common import (EXIT_CANNOT, EXIT_USAGE, Parser, Report, add_project_arg, fail, find_project, main_guard, plugin_root, run,  # noqa: E402
                     scratch_dir, which_or_cannot)

RUN_TIMEOUT_S = 900   # six widths in two schemes, each loaded and settled


def measure(project: Path, root: Path | None, target: pc.Target, widths: list[int], schemes: list[str], node: str, colours: list[str] = (), page_rules: list[dict] = ()) -> tuple[dict, Path]:
    """Write the request, run `render.mjs page-measure` and read what it measured. -> (measures, path of the measures file). `colours` are the modern colour values
    of the project's tokens (tokens.css) the browser is asked to render, so the judge knows what a role looks like on a page, not only its hex. `page_rules` are the brand's own
    rules (qa/rules.json page.rules): the selectors they name and the rules measured in the page's text go in the request."""
    selectors, asks = pc.rule_request(list(page_rules))
    work = scratch_dir(project, pc.report_tool(target.ident))
    request, out = work / "request.json", work / "measures.json"
    out.unlink(missing_ok=True)   # a failed run must never be judged on the measurements of an earlier one
    request.write_text(json.dumps({"schema": 1, "root": str(root) if root else None, "page": target.page if root else None, "url": target.url,
                                   "widths": widths, "schemes": schemes, "selectors": selectors, "rules": asks, "colours": list(colours), "dsf": 1, "stray_min_px": pc.stray_min_px()}, indent=2) + "\n", encoding="utf-8")
    cp = run([node, str(plugin_root() / "scripts" / "render.mjs"), "page-measure", "--request", str(request), "--out", str(out), "--project", str(project)],
             timeout=RUN_TIMEOUT_S, check=False)
    message = cp.stderr.decode("utf-8", "replace").strip().removeprefix("error: ")
    if cp.returncode == EXIT_USAGE:
        fail(EXIT_USAGE, message or "render.mjs page-measure refused the request")
    if cp.returncode != 0:
        fail(EXIT_CANNOT, message or f"render.mjs page-measure exited {cp.returncode}")
    try:
        return json.loads(out.read_text(encoding="utf-8")), out
    except (OSError, ValueError) as e:
        fail(EXIT_CANNOT, f"render.mjs page-measure wrote no measurements ({e})")


def main() -> int:
    ap = Parser(prog="brand-creator page-check", description=__doc__.split("\n\n")[0],
                epilog="exit codes: 0 pass (warnings allowed), 1 a row failed, 2 usage error, 3 cannot run")
    ap.add_argument("page", nargs="?", help="a page of the project (a path inside it); with --from, the page inside DIR")
    ap.add_argument("--from", dest="from_dir", metavar="DIR", help="a built site anywhere: copied into the data folder's scratch area and served from the copy (read only)")
    ap.add_argument("--url", help="a page already served on this machine (http or https on localhost, 127.0.0.1 or [::1]); a remote URL is refused")
    ap.add_argument("--widths", help="css px widths to render at, comma separated, each a whole number from 200 to 4000 "
                                     "(default: qa/rules.json page.widths, else 360,390,768,1024,1440,1920)")
    ap.add_argument("--schemes", help="colour schemes to render, comma separated (default: light,dark)")
    add_project_arg(ap)
    a = ap.parse_args()

    project = find_project(a.project)
    rules, _ = qa_rules.load(project)
    widths = pc.parse_widths(a.widths) if a.widths is not None else rules["page"]["widths"]   # an empty --widths is a usage error, not the default
    schemes = pc.parse_schemes(a.schemes) if a.schemes is not None else list(pc.SCHEMES)
    pc.check_tell_rules(rules["page"]["rules"])   # exit 2 for a rule that names no generic tell, before anything is opened
    target = pc.resolve_target(project, a.page, a.from_dir, a.url)
    tokens = pc.load_tokens(project)   # exit 3: nothing to judge against
    modern = pc.load_modern(project)   # exit 3 likewise: what the browser paints for a token comes from tokens.css
    node = which_or_cannot("node", "Install Node 22 or newer. Run: brand-creator prereq --for quick")

    rep = Report(pc.report_tool(target.ident), project, pc.base_inputs(project, target), renderer="chromium")
    root = project if target.kind == "project" else pc.stage_from_copy(project, target) if target.kind == "from" else None
    measures, measures_path = measure(project, root, target, widths, schemes, node, sorted(set(modern.values())), rules["page"]["rules"])
    pc.judge(rep, measures, pc.Ctx(project, target, widths, schemes, rules, tokens, modern), measures_path)
    return rep.finish()


if __name__ == "__main__":
    main_guard(main)

#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator collapse: after a decision, take the choice scaffolding out of the book sources and the tokens.

While a choice is open, the book and the tokens may carry the options:
  book/chapters/*.md   `::: variant GROUP NAME` ... `:::` (one block per option) and `::: switcher GROUP` ... `:::` (the control that picks)
  a hand-authored book elements with data-variant="GROUP:NAME" and data-switcher="GROUP"
  tokens/*.tokens.json a token with $extensions["brand-creator"].variant = "GROUP:NAME"
`collapse --group GROUP --keep NAME` removes every option that lost (and every switcher), unwraps the one that won (its fence or
data-variant goes, its content stays), and drops the `variant` mark from the winning tokens. Every file it changes is first copied to
removed-<date>/<path> (never deleted); the decision is recorded under `## Collapsed` in BRAND-STATE.md, and under `## Edition log` when a
book file changed. Without --apply it only prints the plan. --list shows the groups found. An approved edition needs --new-edition.
A generated book.html is derived: rebuild it with `brand-creator book`; tokens are rebuilt with `brand-creator tokens`.
"""
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "booklib"))
import bookdata  # noqa: E402
import htmlscan  # noqa: E402
from _common import (EXIT_FAIL, EXIT_USAGE, Parser, add_project_arg, confine, fail, find_project, main_guard, read_state, rel,  # noqa: E402
                     today, write_bytes_if_changed)

FENCE = re.compile(r"^\s*:::\s*(variant|switcher)\s+(.*?)\s*$")


def md_collapse(text: str, group: str, keep: str | None):
    """-> (new text, removed variants, removed switchers, found list). keep None = only list what is there."""
    out, stack, rv, rs, found = [], [], 0, 0, []
    for ln in text.split("\n"):
        m = FENCE.match(ln)
        if m:
            kind, parts = m.group(1), m.group(2).split()
            g = parts[0] if parts else ""
            name = parts[1] if kind == "variant" and len(parts) > 1 else ""
            found.append((g, name or "(switcher)"))
            if g == group and keep is not None:
                act = "keep" if (kind == "variant" and name == keep) else "drop"
                stack.append((True, act))
                if act == "drop":
                    rv += kind == "variant"
                    rs += kind == "switcher"
                continue
            stack.append((False, "other"))
            if not any(a == "drop" for _, a in stack[:-1]):
                out.append(ln)
            continue
        if ln.strip() == ":::" and stack:
            target, act = stack.pop()
            if not target and not any(a == "drop" for _, a in stack) and act != "drop":
                out.append(ln)
            continue
        if not any(a == "drop" for _, a in stack):
            out.append(ln)
    return "\n".join(out), rv, rs, found


def html_collapse(text: str, group: str, keep: str | None):
    spans, strips, found = [], [], []
    for t in htmlscan.tags(text):
        if t.closing:
            continue
        a = t.attrs
        v, s = a.get("data-variant"), a.get("data-switcher")
        if v:
            g, _, n = v.partition(":")
            found.append((g, n))
            if g == group and keep is not None:
                if n == keep:
                    strips.append(t)
                else:
                    spans.append((t.start, htmlscan.element_end(text, t), "variant"))
        if s:
            found.append((s, "(switcher)"))
            if s == group and keep is not None:
                spans.append((t.start, htmlscan.element_end(text, t), "switcher"))
    spans.sort()
    top = []
    for sp in spans:
        if not top or sp[0] >= top[-1][1]:
            top.append(sp)
    edits = [(s, e, "") for s, e, _ in top]
    for t in strips:
        if not any(s <= t.start < e for s, e, _ in top):
            new_tag = re.sub(r"\s+data-variant\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", text[t.start:t.end], count=1)
            edits.append((t.start, t.end, new_tag))
    for s, e, rep in sorted(edits, reverse=True):
        if rep == "":
            while e < len(text) and text[e] == "\n" and (s == 0 or text[s - 1] == "\n"):
                e += 1
        text = text[:s] + rep + text[e:]
    return text, sum(1 for *_, k in top if k == "variant"), sum(1 for *_, k in top if k == "switcher"), found


def tokens_collapse(doc, group: str, keep: str | None):
    """-> (removed count, found list); mutates doc."""
    removed, found = 0, []

    def walk(node):
        nonlocal removed
        for k in list(node):
            if k.startswith("$"):
                continue
            v = node[k]
            if not isinstance(v, dict):
                continue
            if "$value" in v:
                ext = v.get("$extensions", {}).get("brand-creator", {}) if isinstance(v.get("$extensions"), dict) else {}
                var = ext.get("variant") if isinstance(ext, dict) else None
                if var:
                    g, _, n = str(var).partition(":")
                    found.append((g, n))
                    if g == group and keep is not None:
                        if n == keep:
                            del ext["variant"]
                            if not ext:
                                del v["$extensions"]["brand-creator"]
                            if not v["$extensions"]:
                                del v["$extensions"]
                        else:
                            del node[k]
                            removed += 1
            else:
                walk(v)
                if not any(not x.startswith("$") for x in v) and keep is not None and any(g == group for g, _ in found):
                    del node[k]
    walk(doc)
    return removed, found


def main() -> int:
    ap = Parser(prog="brand-creator collapse", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--group", help="the choice that was decided")
    ap.add_argument("--keep", help="the option that won")
    ap.add_argument("--list", action="store_true", help="list the groups and options found, change nothing")
    ap.add_argument("--apply", action="store_true", help="write the changes (without it, only the plan is printed)")
    ap.add_argument("--new-edition", action="store_true", help="open the next edition (needed when the current one is approved)")
    a = ap.parse_args()
    project = find_project(a.project)
    cfg, _ = bookdata.load_config(project)
    st = read_state(project)
    mark_source = str(st.get("mark_source", ""))
    files = []
    for p in sorted((project / "book" / "chapters").glob("*.md")) if (project / "book" / "chapters").is_dir() else []:
        files.append((p, "md"))
    book = project / cfg["output"]
    if book.is_file() and mark_source == "authored-vector":
        files.append((book, "html"))
    for p in sorted((project / "tokens").glob("*.tokens.json")) if (project / "tokens").is_dir() else []:
        files.append((p, "tokens"))
    if a.list or not (a.group and a.keep):
        if not a.list:
            fail(EXIT_USAGE, "give --group and --keep (or --list to see what is open)")
        seen: dict[tuple, list[str]] = {}
        for p, kind in files:
            if kind == "md":
                found = md_collapse(p.read_text(encoding="utf-8"), "\0", None)[3]
            elif kind == "html":
                found = html_collapse(p.read_text(encoding="utf-8"), "\0", None)[3]
            else:
                found = tokens_collapse(json.loads(p.read_text(encoding="utf-8")), "\0", None)[1]
            for g, n in found:
                seen.setdefault((g, n), []).append(rel(project, p))
        if not seen:
            print("no open choices: no variant or switcher in book/chapters, the book or the tokens")
        for (g, n), where in sorted(seen.items()):
            print(f"{g}: {n}  ({', '.join(sorted(set(where)))})")
        return 0
    group, keep = a.group, a.keep
    plan, total_v, total_s, total_t, kept_found = [], 0, 0, 0, False
    all_found = []
    for p, kind in files:
        text = p.read_text(encoding="utf-8")
        if kind == "md":
            new, rv, rs, found = md_collapse(text, group, keep)
            n_changed = rv + rs
        elif kind == "html":
            new, rv, rs, found = html_collapse(text, group, keep)
            n_changed = rv + rs
        else:
            doc = json.loads(text)
            rt, found = tokens_collapse(doc, group, keep)
            new, rv, rs = json.dumps(doc, indent=2, ensure_ascii=False) + "\n", 0, 0
            n_changed = rt
            total_t += rt
        all_found += found
        kept_found = kept_found or any(g == group and n == keep for g, n in found)
        total_v += rv
        total_s += rs
        if new != text:
            plan.append((p, kind, new, rv, rs, n_changed))
    if not any(g == group for g, _ in all_found):
        fail(EXIT_USAGE, f"no choice named {group!r} is open in the book sources or the tokens (--list shows what is)")
    if not kept_found:
        names = sorted({n for g, n in all_found if g == group and n != "(switcher)"})
        fail(EXIT_USAGE, f"--keep {keep!r} is not an option of {group!r} (options: {', '.join(names) or 'none'}); nothing was changed")
    for p, kind, _new, rv, rs, n in plan:
        what = f"{rv} variant block(s), {rs} switcher(s)" if kind != "tokens" else f"{n} token(s)"
        print(f"{'would change' if not a.apply else 'changing'} {rel(project, p)}: remove {what}; keep {group}:{keep}")
    if not plan:
        print(f"nothing to change: {group}:{keep} is already the only option left")
        return 0
    if not a.apply:
        print("nothing was written; re-run with --apply to make these changes (a dated copy of each file goes to removed-<date>/)")
        return 0
    book_changed = any(k in ("md", "html") for _, k, *_ in plan)
    ed = str(st.get("edition", "") or "").strip()
    approved = bool(str(st.get("gates.G5", "") or "").strip()) and str(st.get("approved_edition", "") or "").strip() == ed and ed != ""
    if book_changed and approved and not a.new_edition:
        fail(EXIT_FAIL, f"edition {ed} was approved (G5); collapse changes the book, so open the next edition with --new-edition (it needs a new G5 approval)")
    n = 1
    dest_root = project / f"removed-{today()}"
    while dest_root.exists():
        n += 1
        dest_root = project / f"removed-{today()}-{n}"
    for p, *_ in plan:
        d = confine(project, dest_root / rel(project, p), what="backup")
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, d)
    for p, kind, new, *_ in plan:
        write_bytes_if_changed(p, new.encode("utf-8"))
    if book_changed and a.new_edition and ed:
        st.set("edition", int(ed) + 1)
        ed = str(int(ed) + 1)
        bookdata.append_to_section(st, "Edition log", f"- {today()} edition {ed}: opened (edition {int(ed) - 1} stays as approved)")
    names = ", ".join(rel(project, p) for p, *_ in plan)
    bookdata.append_to_section(st, "Collapsed", f"- {today()}: {group} decided, kept {keep}; removed {total_v} variant block(s), {total_s} switcher(s) and "
                                                f"{total_t} token(s) from {names}; copies in {dest_root.name}/")
    if book_changed and ed:
        bookdata.append_to_section(st, "Edition log", f"- {today()} edition {ed}: collapsed {group} to {keep}")
    st.save()
    print(f"copies of the changed files are in {dest_root.name}/; recorded under ## Collapsed in BRAND-STATE.md")
    if any(k == "tokens" for _, k, *_ in plan):
        print("next: brand-creator tokens (rebuild the token outputs), then brand-creator contrast")
    if mark_source != "authored-vector":
        print("next: brand-creator book (the generated book follows its chapter files)")
    return 0


main_guard(main)

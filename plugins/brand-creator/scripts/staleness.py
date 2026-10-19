#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator staleness: is a generated pack older than what it was built from?

tools/inputs.json records, at the moment a pack is built, the sha256 of every upstream input (token sources, mark
artwork, rules), the plugin version, the sha256 of the emitter code that wrote the pack, and optional needle sentences
that must still be present in sibling documents (a README or a book that quotes a number). `staleness` compares that
record with the files as they are now:

  staleness --write [--input GLOB]... [--needle FILE::SENTENCE]...   record the current state (after the chain has run)
  staleness [--check]                                                flag every difference (exit 1) or say all current

Inputs default to tokens/*.json, assets/logo/*.svg, assets/logo/*.png, qa/*.json, FACTS.md, INVENTORY.md and tray/*.json, plus BRAND.md and DESIGN.md once they
exist (`brand-creator adapters`); --input adds globs (kept in the file). A new file matching a glob that was not recorded is stale too. Emitter code hashes cover scripts/emitters/*.py,
platform-specs.json, print-regions.json and scripts/lib/*.py of the plugin, so an update of the plugin that changes an emitter makes the pack
stale until it is rebuilt. `check` runs the same comparison whenever tools/inputs.json exists.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
from _common import EXIT_USAGE, Parser, add_project_arg, confine, fail, find_project, main_guard, rel  # noqa: E402
from stale import DEFAULT_GLOBS, INPUTS_FILE, check_project, needle_present, record  # noqa: E402

ADAPTER_FILES = ("BRAND.md", "DESIGN.md")


def main() -> int:
    ap = Parser(prog="brand-creator staleness", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--write", action="store_true", help="record the current state in tools/inputs.json")
    ap.add_argument("--check", action="store_true", help="compare (the default)")
    ap.add_argument("--input", action="append", default=[], metavar="GLOB", help="extra input glob relative to the project (with --write)")
    ap.add_argument("--needle", action="append", default=[], metavar="FILE::SENTENCE", help="a sentence that must stay in a sibling document (with --write)")
    a = ap.parse_args()
    project = find_project(a.project)
    f = confine(project, INPUTS_FILE, what="inputs.json")
    if a.write and a.check:
        fail(EXIT_USAGE, "--write and --check are alternatives")
    if a.write:
        old = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
        adapters = [g for g in ADAPTER_FILES if (project / g).is_file()]   # generated views of the brand: once they exist they are inputs of the pack
        globs = list(dict.fromkeys((old.get("globs") or DEFAULT_GLOBS) + adapters + a.input))
        needles = list(old.get("needles", []))
        for n in a.needle:
            file, sep, text = n.partition("::")
            if not sep or not file.strip() or not text.strip():
                fail(EXIT_USAGE, f"--needle needs FILE::SENTENCE, got {n!r}")
            ok, why = needle_present(project, file.strip(), text)
            if not ok:
                fail(EXIT_USAGE, f"needle not found now ({why or 'the sentence is not in the file'}): {n}")
            needles.append({"file": file.strip(), "text": text.strip()})
        doc = record(project, globs, needles)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"recorded {len(doc['inputs'])} input(s), {len(doc['emitters'])} emitter file(s), {len(needles)} needle(s), plugin {doc['plugin_version']} -> {rel(project, f)}")
        return 0
    if not f.is_file():
        fail(EXIT_USAGE, f"{INPUTS_FILE} not found: build the pack, then run `brand-creator staleness --write`")
    try:
        json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        fail(EXIT_USAGE, f"{INPUTS_FILE} is not valid JSON: {e}")
    rep = check_project(project)
    rep.inputs = [f]
    return rep.finish()


main_guard(main)

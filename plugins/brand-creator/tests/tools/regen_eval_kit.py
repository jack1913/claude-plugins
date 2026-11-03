"""Test helper: rebuild the committed snapshot of the Acme brand kit that the kit-test-hero eval starts from (evals/_shared/acme-kit/).

  BRAND_CREATOR_DATA=<set-up data dir> uv run --no-project --with-requirements tests/requirements.txt python tests/tools/regen_eval_kit.py [--into DIR]

Run it from the plugin folder, by hand, when tests/test_kit.py::test_the_eval_kit_snapshot_is_what_kit_build_writes_for_acme fails (the tokens builder or the
applied-skill text changed). It needs a data directory where `brand-creator setup --yes` ran. It builds the golden Acme pack in a scratch folder, runs
`kit build --yes`, fills the owner files with the text the kit tests use (`test_kit.fill_owned`), builds again so that kit.json records them, and copies the
kit folder (.claude/skills/acme-brand/) over DIR (default: evals/_shared/acme-kit/). The tools write their scratch output into a data directory of this
run's own, never into the one you give.
Exits 1 with a message when a step fails, and leaves DIR as it was.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS))

from helpers import FIXTURES, ROOT, bc, data_dir, install_fixture, make_project, own_data  # noqa: E402

SNAPSHOT = ROOT / "evals" / "_shared" / "acme-kit"


def run(*args: str, project: Path) -> None:
    r = bc(*args, project=project)
    if r.returncode != 0:
        sys.exit(f"regen_eval_kit: `brand-creator {' '.join(args)}` exited {r.returncode}\n{r.stdout}{r.stderr}")


def acme_kit(tmp: Path) -> Path:
    """The kit folder of the golden Acme pack, made in `tmp`: the project of tests/conftest.py (`golden`) with the setup of tests/test_kit.py (`pack`), the kit
    built, the owner files filled and the kit built again (version 1.2)."""
    from test_kit import fill_owned, kit_json, kit_of          # the tests' own helpers: one text for "filled", one place that says where the kit is
    p = make_project(tmp)
    install_fixture(p)
    run("state", "--record", "G3", "approved r1 (test)", project=p)
    run("tokens", project=p)
    shutil.copy2(FIXTURES / "FACTS.md", p / "FACTS.md")
    for kv in ("content_languages=en", "edition=1"):
        run("state", "--set", kv, project=p)
    run("state", "--record", "G5", "approved (test)", project=p)
    run("kit", "build", "--yes", project=p)
    fill_owned(kit_of(p))
    run("kit", "build", "--yes", project=p)
    if kit_json(p)["version"] != "1.2":
        sys.exit(f"regen_eval_kit: the kit is at version {kit_json(p)['version']}, expected 1.2 (a build, the owner files filled, a second build)")
    return kit_of(p)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--into", type=Path, default=SNAPSHOT, help="the folder to rebuild (default: evals/_shared/acme-kit)")
    into = ap.parse_args().into
    given = data_dir()
    if given is None:
        sys.exit("regen_eval_kit: BRAND_CREATOR_DATA must name a data directory where `brand-creator setup --yes` ran")
    with tempfile.TemporaryDirectory(prefix="regen-eval-kit-") as td:
        tmp = Path(td)
        (tmp / "data").mkdir()
        os.environ["BRAND_CREATOR_DATA"] = str(own_data(given, tmp / "data"))      # scratch output stays in this run's folder
        (tmp / "work").mkdir()
        kit = acme_kit(tmp / "work")
        staged = tmp / "staged"
        shutil.copytree(kit, staged, symlinks=False)
        if into.exists():
            shutil.rmtree(into)
        into.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged, into, symlinks=False)
    n = sum(1 for f in into.rglob("*") if f.is_file())
    print(f"regen_eval_kit: wrote {n} files to {into}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

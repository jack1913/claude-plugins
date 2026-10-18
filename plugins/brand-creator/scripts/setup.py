#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator setup [--yes]: install what the render and token scripts need, into the data directory.

Shows what it will download and roughly how big it is, then asks (interactive) or needs --yes (non-interactive):
  1. Node packages from scripts/package.json + package-lock.json  -> <data>/node_modules   (npm ci)
  2. Chrome Headless Shell for the pinned Playwright build         -> reuses an existing matching build in
     PLAYWRIGHT_BROWSERS_PATH or the default Playwright cache; otherwise installs it into <data>/browsers
  3. uv script environments for the locked Python scripts          -> uv's cache (warmed so later runs are instant; a few
     scripts pull small PyPI packages: fonttools, skia-pathops, brotli, ColorAide, Pillow)
Nothing is written under the plugin root. Re-runnable: finished steps are skipped (--force redoes them).
No SessionStart auto-install: this runs only when you ask for it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prereq  # noqa: E402  (bootstrap sibling, standard library only)

ROOT = HERE.parent
NODE_MB = 90
CHROMIUM_DOWNLOAD_MB, CHROMIUM_DISK_MB = 110, 190


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def default_browsers_path() -> Path:
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    if env and env != "0":
        return Path(env).expanduser()
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    if system == "Windows":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "ms-playwright"
    return Path.home() / ".cache" / "ms-playwright"


def find_chromium(rev: str, data: Path) -> Path | None:
    """A directory that already holds the pinned headless shell build (marker file present)."""
    for base in (default_browsers_path(), data / "browsers"):
        d = base / f"chromium_headless_shell-{rev}"
        if (d / "INSTALLATION_COMPLETE").is_file():
            return base
    return None


def python_scripts_with_locks() -> list[Path]:
    return sorted(p for p in HERE.rglob("*.py") if (p.parent / (p.name + ".lock")).is_file())


def run(cmd, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, **kw)


def main() -> int:
    ap = argparse.ArgumentParser(prog="brand-creator setup", description=__doc__.split("\n\n")[0])
    ap.add_argument("--yes", action="store_true", help="proceed without asking (required when not interactive)")
    ap.add_argument("--plan", action="store_true", help="only show what would be downloaded")
    ap.add_argument("--force", action="store_true", help="redo steps that look finished")
    ap.add_argument("--data", default=os.environ.get("BRAND_CREATOR_DATA"))
    a = ap.parse_args()
    if not a.data:
        print("error: no data directory: pass --data <dir> or set BRAND_CREATOR_DATA", file=sys.stderr)
        return 2
    data = Path(a.data).expanduser().resolve()

    missing = [i for i in (prereq.chk_python(), prereq.chk_uv(), prereq.chk_node(), prereq.chk_npm()) if i["status"] == "MISSING"]
    if missing:
        for i in missing:
            print(f"MISSING {i['id']}: blocks {i['blocks']}; install: {i['install']}", file=sys.stderr)
        print("error: cannot run setup until the items above are installed (brand-creator prereq --for quick)", file=sys.stderr)
        return 3

    lock = ROOT / "scripts" / "package-lock.json"
    pkg = ROOT / "scripts" / "package.json"
    lock_sha = sha(lock) + ":" + sha(pkg)
    state_file = data / "setup.json"
    prev = json.loads(state_file.read_text()) if state_file.is_file() else {}
    node_done = (data / "node_modules" / "playwright-core").is_dir() and prev.get("lock_sha") == lock_sha and not a.force
    rev = prereq.PINNED_CHROMIUM_REVISION
    existing = find_chromium(rev, data)
    pyscripts = python_scripts_with_locks()

    print("brand-creator setup will:")
    print(f"  1. npm ci into {data / 'node_modules'}: playwright-core, style-dictionary, culori, colorjs.io, @google/design.md "
          f"(pinned by package-lock.json), about {NODE_MB} MB on disk" + ("   [already done, skipped]" if node_done else ""))
    if existing:
        print(f"  2. Chrome Headless Shell build {rev}: found in {existing}, reused (no download)")
    else:
        print(f"  2. Chrome Headless Shell build {rev}: not found; download about {CHROMIUM_DOWNLOAD_MB} MB "
              f"(about {CHROMIUM_DISK_MB} MB on disk) into {data / 'browsers'}")
    print(f"  3. warm {len(pyscripts)} locked Python scripts with uv (a few MB of uv cache; fonttools, skia-pathops, brotli, "
          f"ColorAide and Pillow are downloaded from PyPI for the scripts that need them)")
    print("  Sizes are approximate. Nothing is written under the plugin folder. Re-run any time; finished steps are skipped.")
    if a.plan:
        return 0
    if not a.yes:
        if sys.stdin.isatty():
            if input("Proceed? [y/N] ").strip().lower() not in ("y", "yes"):
                print("cancelled; nothing was changed.")
                return 1
        else:
            print("error: this downloads software; re-run with --yes to confirm (or with --plan to only look).", file=sys.stderr)
            return 2

    data.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)

    # 1. node packages
    if not node_done:
        for f in (pkg, lock):
            shutil.copy2(f, data / f.name)
        print("[1/3] npm ci ...", flush=True)
        cp = run(["npm", "ci", "--no-audit", "--no-fund", "--ignore-scripts"], cwd=data, env=env)
        if cp.returncode != 0:
            print("error: npm ci failed (see output above). Fix the network or npm problem and re-run setup.", file=sys.stderr)
            return 3
    else:
        print("[1/3] node packages already installed, skipped")
    browsers_json = data / "node_modules" / "playwright-core" / "browsers.json"
    got = next((b["revision"] for b in json.loads(browsers_json.read_text())["browsers"] if b["name"] == "chromium-headless-shell"), None)
    if got != rev:
        print(f"error: playwright-core wants Chromium build {got} but setup pins {rev}. "
              f"Update PINNED_CHROMIUM_REVISION in scripts/prereq.py together with scripts/package.json.", file=sys.stderr)
        return 3

    # 2. chromium
    base = find_chromium(rev, data)
    if base is None and a.force:
        base = None
    if base is None:
        print(f"[2/3] installing Chrome Headless Shell {rev} into {data / 'browsers'} ...", flush=True)
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(data / "browsers")
        cli = data / "node_modules" / "playwright-core" / "cli.js"
        cp = run(["node", str(cli), "install", "chromium-headless-shell"], env=env)
        if cp.returncode != 0:
            print("error: the Chromium download failed (see output above). Check the network and re-run setup.", file=sys.stderr)
            return 3
        base = find_chromium(rev, data)
        if base is None:
            print("error: Chromium install finished but the build was not found afterwards.", file=sys.stderr)
            return 3
    else:
        print(f"[2/3] reusing Chrome Headless Shell {rev} in {base}")

    state = {"setup_version": 1, "lock_sha": lock_sha, "playwright_core": json.loads(pkg.read_text())["dependencies"]["playwright-core"],
             "chromium_revision": rev, "browsers_path": str(base)}
    state_file.write_text(json.dumps(state, indent=2) + "\n")

    # 3. uv script environments
    print("[3/3] warming locked Python scripts ...", flush=True)
    bad = []
    for p in pyscripts:
        cp = run(["uv", "run", "--script", "--locked", "--quiet", str(p), "--help"], capture_output=True, text=True,
                 env={**env, "BRAND_CREATOR_DATA": str(data), "PYTHONDONTWRITEBYTECODE": "1"})
        if cp.returncode != 0:
            bad.append(f"{p.relative_to(ROOT)}: {cp.stderr.strip()[:200]}")
    if bad:
        print("error: these scripts did not start:\n  " + "\n  ".join(bad), file=sys.stderr)
        return 3

    # self-test of the browser path
    cp = run(["node", str(HERE / "render.mjs"), "selftest"], capture_output=True, text=True,
             env={**env, "BRAND_CREATOR_DATA": str(data)})
    sys.stdout.write(cp.stdout)
    if cp.returncode != 0:
        sys.stderr.write(cp.stderr)
        print("error: Chromium self-test failed; see the message above.", file=sys.stderr)
        return 3
    print(f"setup complete. Data directory: {data}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

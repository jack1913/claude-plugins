#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator prereq --for quick|standard|full|apple|print|names|adoption

Reports, for the scope you asked about: OK / MISSING / WARN, what each missing item blocks, and the install
command for this OS. Exit 0 when nothing blocks, exit 3 when something does (message names the fix).
Bootstrap script: standard library only, runs with plain python3 so it works before uv or Node exist.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

# The stated minimum Claude Code version = the highest row of the README feature table (userConfig `options`).
MIN_CLAUDE = "2.1.271"
MIN_PYTHON = (3, 10)
MIN_NODE = 22
TESTED_XCODE_BUILD = "27A5194q"  # Xcode 27.0 beta, the build the Apple emitters were tested against
APPLE_SDKS = ("macosx", "iphoneos", "watchos", "appletvos", "xros")
PINNED_CHROMIUM_REVISION = "1228"  # playwright-core 1.61.1 (scripts/package.json)

OS = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(platform.system(), "other")

INSTALL = {
    "uv": {"macos": "brew install uv", "linux": "curl -LsSf https://astral.sh/uv/install.sh | sh  (or your package manager)",
           "windows": "winget install astral-sh.uv"},
    "python": {"macos": "brew install python@3.12", "linux": "apt install python3 (3.10 or newer)",
               "windows": "winget install Python.Python.3.12"},
    "node": {"macos": "brew install node", "linux": "install Node 22+ (https://nodejs.org or nvm/mise)",
             "windows": "winget install OpenJS.NodeJS"},
    "resvg": {"macos": "brew install resvg", "linux": "cargo install resvg  (or your package manager)",
              "windows": "winget install resvg  (or cargo install resvg)"},
    "gs": {"macos": "brew install ghostscript", "linux": "apt install ghostscript", "windows": "winget install ArtifexSoftware.GhostScript"},
    "pdfinfo": {"macos": "brew install poppler", "linux": "apt install poppler-utils", "windows": "scoop install poppler"},
    "magick": {"macos": "brew install imagemagick", "linux": "apt install imagemagick", "windows": "winget install ImageMagick.ImageMagick"},
    "claude": {"macos": "npm install -g @anthropic-ai/claude-code  (or claude update)", "linux": "claude update", "windows": "claude update"},
    "xcode": {"macos": "install Xcode from the App Store or developer.apple.com, then: sudo xcode-select -s /Applications/Xcode.app",
              "linux": "not available: Apple emitters need macOS and Xcode (no cross-platform fallback)",
              "windows": "not available: Apple emitters need macOS and Xcode (no cross-platform fallback)"},
    "rg": {"macos": "brew install ripgrep", "linux": "apt install ripgrep", "windows": "winget install BurntSushi.ripgrep.MSVC"},
    "gh": {"macos": "brew install gh", "linux": "apt install gh", "windows": "winget install GitHub.cli"},
    "dig": {"macos": "preinstalled", "linux": "apt install dnsutils", "windows": "not needed"},
}


def run_out(cmd: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return cp.returncode, (cp.stdout + cp.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


def vparse(s: str) -> tuple[int, ...]:
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", s or "")
    return tuple(int(x) for x in m.groups(default="0")) if m else ()


def item(id_, status, version="", blocks="", fix="", note=""):
    return {"id": id_, "status": status, "version": version, "blocks": blocks, "install": fix, "note": note}


def hint(key: str) -> str:
    return INSTALL.get(key, {}).get(OS, "")


# ----------------------------------------------------------------- individual checks

def chk_python():
    v = sys.version_info
    ok = (v.major, v.minor) >= MIN_PYTHON
    return item("python3", "OK" if ok else "MISSING", f"{v.major}.{v.minor}.{v.micro}",
                "every brand-creator script", hint("python"), "" if ok else f"need Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer")


def chk_uv():
    p = shutil.which("uv")
    if not p:
        return item("uv", "MISSING", "", "all locked Python scripts (new, state, freeze, contrast, board-lint, check, logo-sheet, emit)", hint("uv"))
    rc, out = run_out([p, "--version"])
    return item("uv", "OK", out.split()[1] if out.startswith("uv ") else out)


def chk_node():
    p = shutil.which("node")
    if not p:
        return item("node", "MISSING", "", "render (shot, card), tokens, setup of Chromium", hint("node"))
    rc, out = run_out([p, "--version"])
    ok = vparse(out) and vparse(out)[0] >= MIN_NODE
    return item("node", "OK" if ok else "MISSING", out, "render (shot, card), tokens", hint("node"),
                "" if ok else f"need Node {MIN_NODE} or newer")


def chk_npm():
    p = shutil.which("npm")
    if not p:
        return item("npm", "MISSING", "", "setup (npm ci of the Node dependencies)", hint("node"))
    rc, out = run_out([p, "--version"])
    if rc != 0 or not vparse(out):   # a broken npm must not read as OK with its error text as the version
        return item("npm", "MISSING", "", "setup (npm ci of the Node dependencies)", hint("node"),
                    f"{p} did not report a version (exit {rc}): {out.splitlines()[0][:100] if out else 'no output'}")
    return item("npm", "OK", out)


def chk_resvg():
    p = shutil.which("resvg")
    if not p:
        return item("resvg", "MISSING", "", "logo sheet, web and social emitters (SVG rasteriser)", hint("resvg"),
                    "--renderer=pillow cannot rasterise SVG, so there is no fallback for SVG input")
    rc, out = run_out([p, "--version"])
    return item("resvg", "OK", out.replace("resvg", "").strip())


def chk_chromium(data: str | None):
    if not data:
        return item("chromium", "WARN", "", "", "", "pass --data <dir> to check the setup state")
    f = Path(data) / "setup.json"
    if not f.is_file():
        return item("chromium", "MISSING", "", "shot, card, social images (Chromium driver)", "brand-creator --data <dir> setup --yes")
    try:
        st = json.loads(f.read_text())
    except ValueError:
        return item("chromium", "MISSING", "", "shot, card, social images", "brand-creator --data <dir> setup --yes", "setup.json is unreadable")
    return item("chromium", "OK", f"build {st.get('chromium_revision', '?')}", note=f"in {st.get('browsers_path', '?')}")


def chk_claude():
    p = shutil.which("claude")
    if not p:
        return item("claude", "WARN", "", "", hint("claude"), f"claude is not on PATH in this shell; the plugin needs Claude Code {MIN_CLAUDE} or newer")
    rc, out = run_out([p, "--version"])
    v = vparse(out)
    if not v:
        return item("claude", "WARN", out[:40], note="could not read the version")
    ok = v >= vparse(MIN_CLAUDE)
    return item("claude", "OK" if ok else "MISSING", ".".join(map(str, v)),
                "" if ok else "loading the plugin (userConfig options need Claude Code " + MIN_CLAUDE + "+)",
                "" if ok else hint("claude"), "" if ok else f"installed {'.'.join(map(str, v))} is below the minimum {MIN_CLAUDE}")


def chk_tool(name: str, blocks: str, version_args=("--version",), key: str | None = None, optional=False):
    p = shutil.which(name)
    if not p:
        return item(name, "WARN" if optional else "MISSING", "", blocks, hint(key or name))
    if version_args is None:
        return item(name, "OK")
    rc, out = run_out([p, *version_args])
    first = out.splitlines()[0] if out else ""
    return item(name, "OK", first[:40])


def chk_downscale():
    """The system downscaler the downscale check uses by default. Where there is none (off macOS, or sips is not on PATH) an explicit opt-in is
    needed; this row is the one place prereq asks for it, so the owner is asked once, not once per line."""
    if OS == "macos" and shutil.which("sips"):
        return chk_tool("sips", "downscale check (the real system downscale; --renderer=resvg|pillow is the explicit alternative)", None, optional=True)
    why = "sips exists on macOS only" if OS != "macos" else "sips is not on this PATH"
    return item("sips", "WARN", "", "downscale check without an opt-in", "",
                f"{why}: the downscale check needs your explicit --renderer=resvg|pillow choice (resvg for an SVG source, pillow for a PNG source), "
                "recorded in BRAND-STATE.md (renderer: <name> (opted in <date>)) and printed on every report. Nothing falls back silently.")


def chk_apple():
    if OS != "macos":
        return [item("xcode", "MISSING", "", "Apple emitters (app icons, colorsets, DMG art): macOS and Xcode only, no fallback",
                     hint("xcode"), "exit 3 by design off macOS")]
    out = []
    xcrun = shutil.which("xcrun")
    if not xcrun:
        return [item("xcrun", "MISSING", "", "all Apple emitters", hint("xcode"))]
    rc, ver = run_out(["xcodebuild", "-version"])
    build = (re.search(r"Build version (\S+)", ver) or [None, ""])[1] if rc == 0 else ""
    if rc != 0:
        out.append(item("xcodebuild", "MISSING", "", "all Apple emitters", hint("xcode"), ver[:120]))
    else:
        same = build == TESTED_XCODE_BUILD
        out.append(item("xcodebuild", "OK" if same else "WARN", ver.splitlines()[0] + f" ({build})",
                        note="" if same else f"tested against build {TESTED_XCODE_BUILD}; actool behaviour can change per Xcode release, "
                                            f"treat a failed compile as a hard error"))
    for tool in ("actool", "iconutil", "assetutil", "sips"):
        if tool == "assetutil":
            rc, p = run_out([xcrun, "--find", "assetutil"])
            out.append(item("assetutil", "OK" if rc == 0 else "MISSING", "", "" if rc == 0 else "Assets.car comparison in verify-idempotent", hint("xcode")))
        elif tool == "actool":
            rc, p = run_out([xcrun, "--find", "actool"])
            out.append(item("actool", "OK" if rc == 0 else "MISSING", "", "" if rc == 0 else ".icon compile and Assets.car", hint("xcode")))
        else:
            out.append(chk_tool(tool, "icns/downscale checks", None))
    for sdk in APPLE_SDKS:
        rc, p = run_out([xcrun, "--sdk", sdk, "--show-sdk-path"])
        out.append(item(f"sdk:{sdk}", "OK" if rc == 0 else "MISSING", "", "" if rc == 0 else f"{sdk} emitters",
                        f"xcodebuild -downloadPlatform {sdk}" if rc != 0 else ""))
    return out


GROUPS = {
    "quick": "base+render",
    "standard": "base+render+print",
    "full": "base+render+print+apple+adoption",
    "apple": "base+apple",
    "print": "base+print",
    "names": "base+names",
    "adoption": "base+adoption",
}


def collect(group: str, data: str | None) -> list[dict]:
    parts = GROUPS[group].split("+")
    items = [chk_python(), chk_uv(), chk_claude()]
    if "render" in parts:
        items += [chk_node(), chk_npm(), chk_resvg(), chk_chromium(data), chk_downscale()]
    if "print" in parts:
        items += [chk_tool("gs", "print PDFs (outlines the text; a PDF/X-4 candidate with --icc)", ("--version",), "gs"),
                  chk_tool("pdfinfo", "print-check (reads MediaBox, TrimBox and BleedBox back) and book-pdf", ("-v",), "pdfinfo"),
                  chk_tool("pdftoppm", "print-check (rasterises the page to look at the bleed)", ("-v",), "pdfinfo"),
                  chk_tool("magick", "NSIS bitmap and raster conversions", ("-version",), "magick", optional=True)]
    if "adoption" in parts:
        items += [chk_tool("rg", "adoption survey (reads the product repositories for brand slots, read only)", ("--version",), "rg")]
    if "apple" in parts:
        items += chk_apple()
    seen = set()
    items = [i for i in items if not (i["id"] in seen or seen.add(i["id"]))]  # one row per tool even when two scopes both list it
    if "names" in parts:
        items += [chk_tool("gh", "authenticated GitHub name checks (HTTPS is used otherwise)", ("--version",), "gh", optional=True)]
    return items


def main() -> int:
    ap = argparse.ArgumentParser(prog="brand-creator prereq", description=__doc__.split("\n\n")[0])
    ap.add_argument("--for", dest="group", required=True, choices=sorted(GROUPS), help="scope to check")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--data", default=os.environ.get("BRAND_CREATOR_DATA"))
    a = ap.parse_args()
    items = collect(a.group, a.data)
    blockers = [i for i in items if i["status"] == "MISSING"]
    if a.json:
        print(json.dumps({"for": a.group, "os": OS, "items": items, "blocked": bool(blockers)}, indent=2))
        return 3 if blockers else 0
    print(f"brand-creator prereq --for {a.group}   (os: {OS}, minimum Claude Code: {MIN_CLAUDE})")
    for i in items:
        line = f"{i['status']:<8} {i['id']:<12} {i['version']}"
        print(line.rstrip())
        if i["status"] != "OK":
            if i["blocks"]:
                print(f"           blocks:  {i['blocks']}")
            if i["install"]:
                print(f"           install: {i['install']}")
            if i["note"]:
                print(f"           note:    {i['note']}")
    if OS != "macos" and a.group == "apple":   # the quick, standard and full scopes carry the renderer question in their sips row (asked once)
        print("note: off macOS the downscale check has no sips; it needs the explicit opt-in --renderer=resvg, which is then "
              "recorded in BRAND-STATE.md (renderer: resvg (opted in <date>)) and printed on every report.")
    if blockers:
        print(f"\nBLOCKED: {len(blockers)} item(s) missing for '{a.group}': " + ", ".join(i["id"] for i in blockers), file=sys.stderr)
        return 3
    print("\nnothing blocks this scope.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

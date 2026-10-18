"""assets/manifest.json: every artefact an emitter wrote, with its hash, and the spec rows it used.

put() writes a file only when its bytes changed (put-on-byte-change), so a rebuild never touches an unchanged
artefact. `brand-creator check` gates only the artefacts listed here.

A row may also carry (all optional, documented in scripts/CONTRACT.md):
  slot          the surface the file serves
  inv           its INVENTORY.md slot id (optional)
  size          "WxH" in px
  resampled_by  OURS (our own master at the exact pixels) | SYS (a system downscale of one master) | PAGE (drawn by the page)
  note          one line
  band, exemption  the size band whose drawing the file uses (put_slot() records it; see below)
  qa            the QA gates the file needs, from: downscale, states, motion, family, fonts, idempotent, staleness; `check`
                requires a current passing report for each (so a pack that needs a downscale proof cannot skip it)
  downscale_source  with qa "downscale": the project path of the master the downscale gate must have measured (the report
                for that source, assets/_checks/downscale/<slug>.json, must be current and passing)
  layer_bands   for a multi-layer file (.ico): {"<px>": band} of each layer's drawing; checked against the band rule

Size bands: qa/rules.json lists bands ({name, max_px, drawing}); pick_band() is the ONE function that picks the drawing for
a body size. put_slot() records the band a slot used. A slot that uses a different band than the picker names is off the
rule and needs a one-line exemption (a rule gets revisited, an exemption is a decision someone made).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from _common import (EXIT_FAIL, EXIT_USAGE, confine, fail, plugin_version, rel, sha256_bytes, sha256_file,  # noqa: E402
                     today, write_bytes_if_changed)
import qa_rules  # noqa: E402

MANIFEST = "assets/manifest.json"


class Manifest:
    def __init__(self, project: Path):
        self.project = project
        self.path = confine(project, MANIFEST, what="manifest")
        doc = json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else {}
        self.artefacts: dict[str, dict] = {a["path"]: a for a in doc.get("artefacts", [])}
        self.specs: dict[str, dict] = doc.get("specs", {})
        self.changed: list[str] = []
        self.unchanged: list[str] = []

    def put(self, relpath: str, data: bytes, *, emitter: str, specs: list[str], **extra) -> bool:
        target = confine(self.project, relpath, what="artefact")
        did = write_bytes_if_changed(target, data)
        (self.changed if did else self.unchanged).append(relpath)
        self.artefacts[relpath] = {"path": relpath, "sha256": sha256_bytes(data), "bytes": len(data), "emitter": emitter,
                                   "specs": sorted(specs), **extra}
        return did

    def put_slot(self, relpath: str, data: bytes, *, emitter: str, specs: list[str], slot: str, size_px: int | tuple[int, int],
                 band: str | None = None, exemption: str | None = None, resampled_by: str = "OURS", note: str = "",
                 qa: list[str] | None = None, inv: str | None = None, **extra) -> bool:
        """put() for a slot with a size: records the slot, size, who made the pixels and the band used.

        `size_px` is the side of a square or (width, height); the band follows the longer side. `inv` is the INVENTORY.md slot id.
        With bands defined in qa/rules.json the band defaults to the picker's; naming another band needs `exemption`."""
        w, h = (size_px, size_px) if isinstance(size_px, int) else size_px
        size_px = max(w, h)
        rules, _src = qa_rules.load(self.project)
        picked = qa_rules.pick_band(rules["bands"], size_px)
        used = band or (picked["name"] if picked else None)
        if picked and used != picked["name"] and not (exemption and exemption.strip()):
            fail(EXIT_FAIL, f"slot {slot} at {size_px} px uses band {used!r} but the band rule picks {picked['name']!r}; "
                            f"an off-rule slot needs a stated exemption (one line, why this slot differs)")
        if band and not picked:
            fail(EXIT_USAGE, f"slot {slot}: band {band!r} was named but qa/rules.json defines no bands")
        if band and picked and not any(b["name"] == band for b in rules["bands"]):
            fail(EXIT_USAGE, f"slot {slot}: unknown band {band!r} (defined: {', '.join(b['name'] for b in rules['bands'])})")
        row = {"slot": slot, "size": f"{w}x{h}", "resampled_by": resampled_by, "note": note}
        if inv:
            row["inv"] = inv
        if used:
            row["band"] = used
        if exemption and exemption.strip() and picked and used != picked["name"]:
            row["exemption"] = exemption.strip()
        if qa:
            row["qa"] = sorted(qa)
            if "downscale" in qa:
                row["downscale_source"] = extra.pop("downscale_source", relpath)   # the file the downscale gate must have measured
        return self.put(relpath, data, emitter=emitter, specs=specs, **row, **extra)

    def retire_unwritten(self, emitter: str, out: str, keep=None) -> list[str]:
        """Rows of `emitter` under `out/` that this run did not write describe slots that no longer exist (a removed tray state, a
        dropped target, a superseded fingerprinted name). Their files are MOVED (never deleted) to removed-<date>/<path> inside
        the project and the rows are dropped; returns the retired paths. `keep(path)` true spares a row (social keeps superseded Open
        Graph files: their URLs may still be in cached link previews, and the emitter warns about them instead)."""
        written = set(self.changed) | set(self.unchanged)
        self.retired_to = {}   # path -> removed-<date>[-n] folder it went to (for the report text)
        prefix = out.strip("/") + "/"
        gone = sorted(p for p, a in self.artefacts.items() if a.get("emitter") == emitter and p.startswith(prefix) and p not in written
                      and not (keep and keep(p)))
        for p in gone:
            src = confine(self.project, p, what="retired artefact")
            if src.is_file():
                dest = confine(self.project, f"removed-{today()}/{p}", what="removed folder")
                n = 1
                while dest.exists():
                    n += 1
                    dest = confine(self.project, f"removed-{today()}-{n}/{p}", what="removed folder")
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                self.retired_to[p] = f"removed-{today()}" + (f"-{n}" if n > 1 else "")
            del self.artefacts[p]
        return gone

    def stamp_specs(self, stamped: dict) -> None:
        self.specs.update(stamped)

    def save(self) -> bool:
        doc = {"generator": "brand-creator", "version": plugin_version(),
               "artefacts": [self.artefacts[k] for k in sorted(self.artefacts)],
               "specs": {k: self.specs[k] for k in sorted(self.specs)}}
        return write_bytes_if_changed(self.path, (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode())


def load_artefacts(project: Path) -> list[dict]:
    p = project / MANIFEST
    return json.loads(p.read_text(encoding="utf-8")).get("artefacts", []) if p.is_file() else []


def verify(project: Path) -> list[str]:
    """Problems with the artefacts listed in manifest.json (missing or changed since they were emitted)."""
    out = []
    for a in load_artefacts(project):
        f = project / a["path"]
        if not f.is_file():
            out.append(f"missing: {a['path']}")
        elif sha256_file(f) != a["sha256"]:
            out.append(f"changed since emitted: {a['path']} (re-run the emitter or update the source)")
    return out


def band_problems(project: Path) -> list[str]:
    """Slots that sit off the band rule without an exemption, or name a band the rules no longer define."""
    rules, _src = qa_rules.load(project)
    bands = rules["bands"]
    out = []
    for a in load_artefacts(project):
        if "band" not in a:
            continue
        m = a.get("size", "").split("x")
        if not (len(m) == 2 and m[0].isdigit()):
            out.append(f"{a['path']}: has a band but no usable size {a.get('size')!r}")
            continue
        if not bands:
            out.append(f"{a['path']}: records band {a['band']!r} but qa/rules.json defines no bands now")
            continue
        picked = qa_rules.pick_band(bands, max(int(m[0]), int(m[1])))
        if a["band"] != picked["name"] and not a.get("exemption"):
            out.append(f"{a['path']} ({a.get('slot', '?')}, {a['size']}): band {a['band']!r}, the rule picks {picked['name']!r}, and there is no exemption")
        elif a["band"] not in {b["name"] for b in bands}:
            out.append(f"{a['path']}: band {a['band']!r} is not defined in qa/rules.json")
    return out + layer_band_problems(project)


def layer_band_problems(project: Path) -> list[str]:
    """Layers of a multi-layer file (.ico) whose drawing is off the band rule for the layer's own size, with no exemption."""
    rules, _src = qa_rules.load(project)
    bands = rules["bands"]
    names = {b["name"] for b in bands}
    out = []
    for a in load_artefacts(project):
        if "layer_bands" not in a:
            continue
        for px, used in sorted(a["layer_bands"].items(), key=lambda kv: int(kv[0])):
            if not bands:
                if used is not None:
                    out.append(f"{a['path']}: layer {px} records band {used!r} but qa/rules.json defines no bands now")
                continue
            picked = qa_rules.pick_band(bands, int(px))["name"]
            if used not in names:
                out.append(f"{a['path']}: layer {px} uses band {used!r}, which is not defined in qa/rules.json")
            elif used != picked and not a.get("exemption"):
                out.append(f"{a['path']} layer {px} px: drawn from band {used!r}, the rule picks {picked!r}, and there is no exemption")
    return out

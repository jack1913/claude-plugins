# P8 Asset packs (pointer: the brand-assets skill is the single source)

- **When:** after G3 (every emitter refuses without it); packs follow INVENTORY.md, or the brief's required surfaces when `inventory: none`.
- **How:** read and follow [the brand-assets skill](../../../brand-assets/SKILL.md) fully, project entry; this file holds no method of its own.
- **Inputs:** approved mark SVGs (`assets/logo/`), built tokens, `qa/rules.json` size bands (G4; with several marks, `marks` and each mark's bands), INVENTORY.md slots and deployment targets, FACTS.md (every word an emitter copies), `tray/tray.json`.
- **Outputs:** `assets/<target>/` laid out as the target repo's paths (with several marks, `assets/<target>/<id>/` per mark), `assets/manifest.json`, `assets/_checks/emit-<target>.json` (or `emit-<target>/<id>.json`), `tools/finish.sh` (the chain), `tools/inputs.json`.
- **Gate:** G3 before any emit; `check` exit 0 before G5. Apple packs run only on macOS with Xcode (exit 3 elsewhere, no fallback).

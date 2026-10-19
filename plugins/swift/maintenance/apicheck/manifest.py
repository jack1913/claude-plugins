"""Load maintenance/apis.json: frameworks to index, APIs with recorded claims, names to ignore."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .apple import PLATFORMS

_TOP_KEYS = {"frameworks", "apis", "ignore"}
_API_KEYS = {"name", "path", "claims", "table"}


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class ApiEntry:
    name: str  # as the skills write it, e.g. "glassEffect(_:in:)"
    path: str  # Apple doc path below /documentation/, e.g. "swiftui/view/glasseffect(_:in:)"
    claims: dict  # e.g. {"visionOS": False, "iOS": "26.0", "deprecated": False}
    table: bool  # include in platform-availability.md


@dataclass(frozen=True)
class Manifest:
    frameworks: tuple[str, ...]
    apis: tuple[ApiEntry, ...]
    ignore: dict[str, str]  # name → reason


def _valid_claim(key: str, value) -> bool:
    if key in ("deprecated", "beta"):
        return isinstance(value, bool)
    return key in PLATFORMS and isinstance(value, (bool, str))


def load_manifest(path: Path) -> Manifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"{path}: manifest root must be a JSON object")
    unknown = set(data) - _TOP_KEYS
    if unknown:
        raise ManifestError(f"{path}: unknown keys {sorted(unknown)}")
    frameworks = data.get("frameworks")
    if (
        not isinstance(frameworks, list)
        or not frameworks
        or not all(isinstance(f, str) for f in frameworks)
    ):
        raise ManifestError(
            f"{path}: 'frameworks' must be a non-empty list of Apple framework slugs"
        )

    apis_data = data.get("apis", [])
    if not isinstance(apis_data, list):
        raise ManifestError(f"{path}: 'apis' must be a list of API entries")
    apis, seen = [], set()
    for i, raw in enumerate(apis_data):
        where = f"{path}: apis[{i}]"
        if (
            not isinstance(raw, dict)
            or set(raw) - _API_KEYS
            or not {"name", "path"} <= set(raw)
        ):
            raise ManifestError(
                f"{where}: needs 'name' and 'path'; allowed keys are {sorted(_API_KEYS)}"
            )
        if not isinstance(raw["name"], str):
            raise ManifestError(f"{where}: 'name' must be a string")
        if not isinstance(raw["path"], str):
            raise ManifestError(f"{where}: 'path' must be a string")
        if raw["name"] in seen:
            raise ManifestError(f"{where}: duplicate name {raw['name']!r}")
        seen.add(raw["name"])
        if raw["path"].startswith("/") or raw["path"].endswith(".json"):
            raise ManifestError(
                f"{where}: path is relative to /documentation/ without .json, e.g. swiftui/view/glasseffect(_:in:)"
            )
        if "claims" in raw and not isinstance(raw["claims"], dict):
            raise ManifestError(f"{where}: 'claims' must be an object")
        if "table" in raw and not isinstance(raw["table"], bool):
            raise ManifestError(f"{where}: 'table' must be true or false")
        claims = raw.get("claims", {})
        for key, value in claims.items():
            if not _valid_claim(key, value):
                raise ManifestError(
                    f"{where}: bad claim {key!r}: {value!r} (deprecated/beta take true/false; "
                    f'platforms {", ".join(PLATFORMS)} take true/false or an introduced version like "26.0")'
                )
        apis.append(
            ApiEntry(
                raw["name"], raw["path"], dict(claims), bool(raw.get("table", False))
            )
        )

    ignore_data = data.get("ignore", {})
    if not isinstance(ignore_data, dict):
        raise ManifestError(
            f"{path}: 'ignore' must be an object mapping a reason to a list of names"
        )
    ignore: dict[str, str] = {}
    for reason, names in ignore_data.items():
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            raise ManifestError(
                f"{path}: 'ignore' entry {reason!r} must be a list of name strings"
            )
        for name in names:
            if name in ignore:
                raise ManifestError(f"{path}: {name!r} is ignored twice")
            ignore[name] = reason
    return Manifest(tuple(frameworks), tuple(apis), ignore)

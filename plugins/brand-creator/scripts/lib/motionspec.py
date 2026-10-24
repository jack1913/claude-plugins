"""motion/motion.json: the machine-readable motion spec, the one source the adapters and the brand book read.

load(project) -> the validated document, or None when the file is absent. Anything wrong is exit 2 naming the field path and what is wrong, never
a guess. The references to duration and curve tokens are looked up in the built tokens (assets/tokens/tokens.json); when those are not built that is
exit 3 naming `brand-creator tokens`. The schema is in scripts/CONTRACT.md ("Motion spec"). Standard library only; no clock and no random numbers.

decision(project) and status_lines(project, decision) are the owner's answer as `motion` and `state` print it: on, off (nothing moves) or not decided. The answer is read from the document
alone, without looking its tokens up (the motion round comes before the tokens are built): whether they are built is the spec row of `check`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from _common import EXIT_CANNOT, EXIT_USAGE, CliError, fail, gate_recorded, read_state

FILE = "motion/motion.json"
TOKENS = "assets/tokens/tokens.json"
# what Standard and Full say while motion is not decided (the line of `motion` and `state`, the rows of `check`, the finish chain): one sentence, one place
DECIDE = 'run the motion round, or record nothing moves with `brand-creator motion --off "<the owner\'s reason>"`'
KEYS = {"": ("schema", "motion", "reason", "signature", "parts", "timeline", "rules"), "signature": ("name", "description", "where"),
        "part": ("id", "description"), "step": ("part", "property", "start", "duration", "easing", "note")}
ID = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
REF = re.compile(r"\{([^{}\s]+)\}")
TERM = r"\{([^{}\s]+)\}(?:\s*\*\s*(\d+(?:\.\d+)?))?"   # a duration reference, or one times a number of 0 or more
START = re.compile(rf"{TERM}(?:\s*\+\s*{TERM})*")             # a term, or a sum of them: "{motion.base} + {motion.stagger} * 2"
KIND = {"duration": "duration", "curve": "cubicBezier"}   # what a reference must name, in the words of the DTCG type


def one_line(t) -> str:
    return re.sub(r"\s+", " ", str(t)).strip()


def check(doc) -> tuple[list[str], list[tuple[str, str, str]]]:
    """-> (what is wrong with the document itself, and the token references it holds as (field path, token path, "duration" or "curve"))."""
    bad: list[str] = []
    refs: list[tuple[str, str, str]] = []
    if not isinstance(doc, dict):
        return ["the document must be a JSON object"], refs

    def text(v) -> bool:
        return isinstance(v, str) and v.strip() != ""

    def unknown(obj: dict, group: str, at: str) -> None:
        for k in obj:
            if k not in KEYS[group]:
                bad.append(f'{at + "." if at else ""}{k}: unknown key (allowed: {", ".join(KEYS[group])})')

    unknown(doc, "", "")
    schema = doc.get("schema")
    if type(schema) is not int or schema != 1:
        bad.append(f"schema: must be 1 (the only schema this version reads), got {json.dumps(schema)}" if "schema" in doc else "schema: required, 1")
    mode = doc.get("motion")
    if mode not in ("on", "off"):
        bad.append(f'motion: must be "on" or "off", got {json.dumps(mode)}' if "motion" in doc else 'motion: required, "on" or "off" (the owner\'s answer on motion)')
    if "reason" in doc and not text(doc["reason"]):
        bad.append("reason: must be a non-empty string")
    if mode == "off":
        if "reason" not in doc:
            bad.append('reason: required with motion "off": why nothing moves, in the owner\'s words')
        bad += [f'{k}: not allowed with motion "off" (nothing moves)' for k in ("signature", "parts", "timeline") if k in doc]
    elif mode == "on":
        if "reason" in doc:
            bad.append('reason: only with motion "off"')
        if "signature" not in doc:
            bad.append('signature: required with motion "on": the move that is the brand\'s own')
    if "signature" in doc:
        sig = doc["signature"]
        if not isinstance(sig, dict):
            bad.append("signature: must be an object {name, description, where}")
        else:
            unknown(sig, "signature", "signature")
            bad += [f"signature.{k}: required, a non-empty string" for k in ("name", "description") if not text(sig.get(k))]
            where = sig.get("where")
            if not (isinstance(where, list) and where and all(text(w) for w in where)):
                bad.append("signature.where: required, a non-empty list of the places the move shows (strings)")
    ids: list[str] = []
    if "parts" in doc:
        parts = doc["parts"]
        if not isinstance(parts, list):
            bad.append("parts: must be a list of {id, description}")
        else:
            for i, part in enumerate(parts):
                at = f"parts[{i}]"
                if not isinstance(part, dict):
                    bad.append(f"{at}: must be an object {{id, description}}")
                    continue
                unknown(part, "part", at)
                pid = part.get("id")
                if not (isinstance(pid, str) and ID.fullmatch(pid)):
                    bad.append(f"{at}.id: must be lower case words joined by hyphens (a-z, 0-9, -), got {json.dumps(pid)}")
                elif pid in ids:
                    bad.append(f'{at}.id: "{pid}" is used twice')
                else:
                    ids.append(pid)
                if not text(part.get("description")):
                    bad.append(f"{at}.description: required, a non-empty string")
    if "timeline" in doc:
        timeline = doc["timeline"]
        if not isinstance(timeline, list):
            bad.append("timeline: must be a list of steps")
        else:
            for i, step in enumerate(timeline):
                at = f"timeline[{i}]"
                if not isinstance(step, dict):
                    bad.append(f"{at}: must be an object {{part, property, start, duration, easing}}")
                    continue
                unknown(step, "step", at)
                part = step.get("part")
                if not text(part):
                    bad.append(f"{at}.part: required, the id of a part")
                elif part not in ids:
                    bad.append(f'{at}.part: "{part}" is not a part id ({", ".join(ids) if ids else "no part is defined"})')
                if not text(step.get("property")):
                    bad.append(f"{at}.property: required, what moves (for example transform)")
                start = step.get("start")
                if isinstance(start, str) and START.fullmatch(start.strip()):
                    refs += [(f"{at}.start", m.group(1), "duration") for m in re.finditer(TERM, start)]   # every part of a sum is a duration token
                elif start != "0":
                    bad.append(f'{at}.start: must be "0", a duration reference such as "{{motion.stagger}}", a reference times a number such as "{{motion.stagger}} * 2", '
                               f'or a sum of them such as "{{motion.base}} + {{motion.stagger}} * 2", got {json.dumps(start)}')
                for key, kind, example in (("duration", "duration", "{motion.base}"), ("easing", "curve", "{easing.standard}")):
                    v = step.get(key)
                    m = REF.fullmatch(v) if isinstance(v, str) else None
                    if m:
                        refs.append((f"{at}.{key}", m.group(1), kind))
                    else:
                        bad.append(f'{at}.{key}: must be a reference to a {KIND[kind]} token such as "{example}", got {json.dumps(v)}')
                if "note" in step and not text(step["note"]):
                    bad.append(f"{at}.note: when present, a non-empty string")
    if "rules" in doc:
        rules = doc["rules"]
        if not isinstance(rules, list):
            bad.append("rules: must be a list of strings")
        else:
            bad += [f"rules[{i}]: must be a non-empty string" for i, r in enumerate(rules) if not text(r)]
    return bad, refs


def built_tokens(project: Path) -> dict | None:
    """The built tokens as the motion spec needs them: the duration and cubicBezier token paths (assets/tokens/tokens.json `motion`) and every token path; None when not built."""
    f = project / TOKENS
    if not f.is_file():
        return None
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
        motion = doc.get("motion") or {}
        out = {"duration": set(motion.get("durations_ms") or {}), "curve": set(motion.get("curves") or {}), "motion_section": "motion" in doc,
               "every": set(doc.get("primitives", {})) | set(doc.get("other", {})) | set(doc["modes"]["light"])}
    except (OSError, ValueError, AttributeError, KeyError, TypeError) as e:
        fail(EXIT_CANNOT, f"{TOKENS} cannot be read ({type(e).__name__}: {e}); run `brand-creator tokens`")
    out["every"] |= out["duration"] | out["curve"]
    return out


def ref_problems(refs: list[tuple[str, str, str]], built: dict) -> list[str]:
    bad = []
    for at, ref, kind in refs:
        if ref in built[kind]:
            continue
        have = ", ".join(sorted(built[kind])) or "none"
        hint = "" if built["motion_section"] else "; the built tokens have no motion section: run `brand-creator tokens` if they were built before the sources had a duration or a curve"
        bad.append(f"{at}: " + (f"{{{ref}}} is not a {KIND[kind]} token" if ref in built["every"] else f"no token named {ref}") + f" ({KIND[kind]} tokens: {have}{hint})")
    return bad


def load(project: Path, *, tokens: bool = True) -> dict | None:
    """The validated motion spec of a project, or None when motion/motion.json does not exist. tokens=False checks the document itself and leaves its references unresolved."""
    f = project / FILE
    if not f.is_file():
        return None
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        fail(EXIT_USAGE, f"{FILE}: cannot be read as JSON ({e})")
    bad, refs = check(doc)
    if refs and tokens:
        try:
            built = built_tokens(project)
        except CliError:
            if not bad:
                raise
            built = None   # a document that is wrong in itself is exit 2 whatever state the tokens are in
        if built is not None:
            bad += ref_problems(refs, built)
        elif not bad:
            fail(EXIT_CANNOT, f"{FILE} refers to {len(refs)} duration or curve token(s) and {TOKENS} is not built: run `brand-creator tokens`")
    if bad:
        fail(EXIT_USAGE, f"{FILE}: " + "; ".join(bad[:8]) + (f"; and {len(bad) - 8} more" if len(bad) > 8 else ""))
    return doc


def summary(doc: dict) -> str:
    """One line for a report row."""
    if doc["motion"] == "off":
        return f"motion off: {one_line(doc['reason'])}"
    return (f"motion on: signature {doc['signature']['name']!r}, {len(doc.get('parts', []))} part(s), {len(doc.get('timeline', []))} timeline step(s), "
            f"{len(doc.get('rules', []))} rule(s)")


def decision(project: Path) -> dict:
    """The owner's answer on motion, from the one record of it: {"motion": "on", "signature": name}, {"motion": "off", "reason": text} or {"motion": "undecided"} when
    there is no motion/motion.json. A file that is not valid in itself is load()'s exit 2, never read as an answer; the tokens it names are not looked up."""
    doc = load(project, tokens=False)
    if doc is None:
        return {"motion": "undecided"}
    return {"motion": "off", "reason": doc["reason"]} if doc["motion"] == "off" else {"motion": "on", "signature": doc["signature"]["name"]}


def due_before_g4(project: Path) -> bool:
    """Standard and Full decide motion before G4, from the moment G3 is recorded; Quick decides it at G4, and only when something moves."""
    return str(read_state(project).get("tier", "") or "").strip().lower() in ("standard", "full") and bool(gate_recorded(project, "G3"))


def status_lines(project: Path, d: dict) -> list[str]:
    """The line `motion` and `state` print for a decision (as decision() returns it); while it is open in Standard and Full after G3, a second line says it is due."""
    if d["motion"] == "on":
        return [f"motion: on (signature: {one_line(d['signature'])})"]
    if d["motion"] == "off":
        return [f"motion: off (nothing moves: {one_line(d['reason'])})"]
    return ["motion: not decided", *([f"due before G4: {DECIDE}"] if due_before_g4(project) else [])]

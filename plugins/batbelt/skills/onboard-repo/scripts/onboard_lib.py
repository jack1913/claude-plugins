"""Deterministic helpers for the onboard-repo skill (stdlib only).

The LLM-driven skill (SKILL.md) orchestrates detection and stamping; the
mechanically-exact parts -- two-region preservation on --sync, predecessor
detection, and the docs-IA helpers (ToC renumbering, markdown-link rewriting,
move-manifest read/write) -- live here as PURE FUNCTIONS so they can be
unit-tested directly (design spec Section 9). Nothing here reads global state or
the network.
"""

import copy
import json
import pathlib
import posixpath
import re
import xml.etree.ElementTree as _ET

# The grounding gates and the markdown primitives they need live in check.py --
# the file onboard-repo stamps into a maintained repo on its own (ADR-0008). Imported
# back here so the onboarding helpers below keep working and so callers that reach for
# `onboard_lib.check_instructions` still find it. One implementation, two names.
from check import (  # noqa: F401  (re-exported for callers of this module)
    GROUNDING_WINDOW,
    _split_fences,
    canonicalize_output,
    check_instructions,
    heading_slugs,
    heading_texts,
    illustrative_line_numbers,
    iter_citations,
    iter_count_claims,
    iter_fenced_blocks,
    iter_frontmatter_problems,
    iter_markdown_links,
    iter_path_globs,
    iter_script_citations,
    output_subsequence_ok,
    redact_output,
    split_frontmatter,
    table_cell_errors,
)

# Bump when the stamped template layout changes; recorded in the provenance header.
TEMPLATE_VERSION = 3

BEGIN = "<!-- BEGIN REPO SPECIFICS (preserved on --sync) -->"
END = "<!-- END REPO SPECIFICS -->"


class MarkerError(ValueError):
    """Raised when the REPO SPECIFICS markers are missing, duplicated, reversed,
    or otherwise malformed. --sync MUST fail closed on this: back up and refuse
    to write, never guess where the preserved region ends (spec Section 4.3)."""


def parse_regions(text):
    """Split a stamped file into (before, inner, after) around the single
    REPO SPECIFICS block, where
        before + BEGIN + inner + END + after == text.
    Raises MarkerError unless exactly one well-formed BEGIN..END pair exists."""
    begins = [m.start() for m in re.finditer(re.escape(BEGIN), text)]
    ends = [m.start() for m in re.finditer(re.escape(END), text)]
    if len(begins) != 1 or len(ends) != 1:
        raise MarkerError(
            "expected exactly one REPO SPECIFICS block, found "
            "%d BEGIN / %d END marker(s)" % (len(begins), len(ends))
        )
    b, e = begins[0], ends[0]
    if b >= e:
        raise MarkerError("END marker appears before BEGIN marker")
    before = text[:b]
    inner = text[b + len(BEGIN) : e]
    after = text[e + len(END) :]
    return before, inner, after


def preserve_repo_specifics(old_text, new_template_text):
    """Return the new template with the OLD file's REPO SPECIFICS block carried
    forward verbatim (template region from new, specifics from old). Fail-closed
    (MarkerError) if either side lacks exactly one well-formed block."""
    _, old_inner, _ = parse_regions(old_text)  # what to preserve
    new_before, _new_inner, new_after = parse_regions(new_template_text)  # where it goes
    return new_before + BEGIN + old_inner + END + new_after


# An ordered-list item: "N." or "N)" style (review M2).
_OL_ITEM_RE = re.compile(r"^(\s*)\d+([.)])(\s+)", re.MULTILINE)
# The ToC total. Each cue is FULLY delimited so a look-alike prose range does not
# match (review C1): bold on BOTH sides ("**1 → N**"), the literal "(read 1 → N)",
# or the MD029 "1→N reading order" comment. A bare "(1 to 5)" / "steps 1 to 7." /
# unrelated "**1 → 5**" table cell is left alone. Seed ships digit totals so this is
# not inert on a fresh scaffold.
_TOTAL_RE = re.compile(
    r"(\*\*1\s*(?:→|->|to)\s*)\d+(?=\*\*)"  # **1 → N**
    r"|(\(read\s+1\s*(?:→|->|to)\s*)\d+(?=\))"  # (read 1 → N)
    r"|(\b1\s*(?:→|->|to)\s*)\d+(?=\s*reading order)"  # 1→N reading order
)


def renumber_toc(text):
    """Reflow a manual ToC: renumber ordered-list items to a continuous 1..N in
    document order, and rewrite the hardcoded '1 → N' / '1 -> N' / '1 to N' ToC
    total to match N. Ordered-list lines and totals inside fenced code blocks are
    left untouched (not renumbered, not counted). Idempotent. No-op when the text
    has no ordered-list items outside code fences (spec Section 3, review I-1/I-2)."""
    # A leading BOM (U+FEFF) is NOT matched by `\s`, so a "﻿1. …" first line
    # would push `^\s*\d+` off the first item and offset the count (review S3-m).
    # Strip it up front and re-prepend on return so numbering sees a true line start.
    bom = ""
    if text[:1] == "﻿":
        bom, text = text[0], text[1:]
    n = 0

    def _item(m):
        nonlocal n
        n += 1
        return "%s%d%s%s" % (m.group(1), n, m.group(2), m.group(3))

    def _total(m):
        # exactly one of the three alternation groups matched; keep its lead text.
        lead = m.group(1) or m.group(2) or m.group(3)
        return "%s%d" % (lead, n)

    parts = []
    for seg, is_fence in _split_fences(text):
        parts.append(seg if is_fence else _OL_ITEM_RE.sub(_item, seg))
    if n == 0:
        return bom + text
    # Rewrite the anchored total only in prose segments (never inside a fence).
    out = []
    for seg, is_fence in _split_fences("".join(parts)):
        out.append(seg if is_fence else _TOTAL_RE.sub(_total, seg))
    return bom + "".join(out)


def rewrite_markdown_links(text, moves):
    """Rewrite markdown inline-link, image, and reference-definition TARGETS from
    old->new per `moves` (a dict of repo-relative path strings). Only real link
    targets are touched: `](old)`, `![](old)`, and `]: old` reference defs. A bare
    occurrence of the path in code or prose is left untouched -- adoption must not
    corrupt code that merely contains a matching substring (spec Section 3, 4.3)."""
    if not moves:
        return text
    # ONE simultaneous pass over an alternation of all olds, so no rule's output can
    # feed another: moves like {"a.md": "b.md", "b.md": "c.md"} must rewrite a.md->b.md
    # (NOT chain a.md->c.md) (review S3-m). Longest-first so a longer key wins over a
    # shorter prefix; the lookahead still guards prefix collisions (e.g. old.md.bak).
    alt = "(?:" + "|".join(re.escape(o) for o in sorted(moves, key=len, reverse=True)) + ")"

    def _sub(m):
        return m.group(1) + moves[m.group(2)]

    # inline link / image target:  ](old) / ](<old>) / ](old "title") / ](old#a) / ](old?v=1)
    out = re.sub(r"(\]\(\s*<?)(" + alt + r")(?=[)>\s#?])", _sub, text)
    # reference definition:  ]: old   ->   ]: new   (line-anchored, ws/EOL after)
    out = re.sub(r"(?m)^(\s*\[[^\]]+\]:\s*<?)(" + alt + r")(?=[>\s]|$)", _sub, out)
    return out


def write_move_manifest(pairs, dirs_created):
    """Serialize an adoption move record to JSON text: {'moves': [[old,new],...],
    'dirs_created': [...]}. Written to a known path by the adoption step so manual
    rollback and --rollback-ia can reverse the moves precisely (spec 4.3/4.6)."""
    return json.dumps({"moves": pairs, "dirs_created": dirs_created}, indent=2)


def read_move_manifest(text):
    """Parse a move manifest back to (moves, dirs_created)."""
    data = json.loads(text)
    return data["moves"], data["dirs_created"]


# ---- Run state (a long onboarding survives compaction and session loss) -----
#
# A brownfield onboarding is a MULTI-HOUR run, and the facts it depends on -- the
# confirmed detection, the confirmed move plan, which surfaces are already authored --
# lived only in the model's context. Context compaction or a dropped session therefore
# lost every operator confirmation, and the run restarted from detection.
#
# RUN_SCHEMA is the durable record. It is deliberately a DUMB document: this module
# validates its shape and applies one transition at a time, and never decides what the
# next phase should be. Phase order is the skill's business (SKILL.md), not the
# helper's -- encoding it here would mean two sources of truth for the flow.
RUN_SCHEMA = 1

# The phases a run moves through, in SKILL.md order. Recorded (not enforced) so
# `run-status` can report "phase 4 of 8" without the skill re-deriving it.
RUN_PHASES = (
    "detect",
    "plan",
    "stamp",
    "agent-config",
    "copilot",
    "scaffold",
    "adopt",
    "author",
    "review",
    "done",
)

# A surface/page is in exactly one of these states. `parked` is the load-bearing
# addition: the pre-existing design gave up on the whole RUN when a page would not
# converge, which is precisely the wrong granularity for a 3-4h pass -- one stubborn
# page must not discard six hours of good work. A parked page carries its reason and
# is re-flagged by --check, so parking is durable and visible, never a silent skip.
RUN_ITEM_STATES = ("pending", "in-progress", "done", "parked")


class RunStateError(ValueError):
    """Raised when a run record is malformed or a transition is not applicable.
    Callers fail closed: a run record that does not parse must never be silently
    replaced with a fresh one, because that discards the operator's confirmations
    (the same fail-closed rule --sync applies to REPO SPECIFICS markers)."""


def new_run(stamp, repo_root, mode="default"):
    """Build a fresh run record. `stamp` is the caller's timestamp (this module
    never reads a clock, so the record stays reproducible and testable)."""
    if not stamp:
        raise RunStateError("stamp is required")
    return {
        "schema": RUN_SCHEMA,
        "stamp": stamp,
        "repo_root": repo_root,
        "mode": mode,
        "phase": RUN_PHASES[0],
        "phases_done": [],
        "confirmed": {},
        "items": [],
        "log": [],
    }


def read_run(text):
    """Parse and VALIDATE a run record. Unknown schema is an error, not a
    best-effort read: a newer record read by an older helper would silently drop
    the fields it does not know, and those fields are operator confirmations."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise RunStateError("run record is not valid JSON: %s" % exc)
    if not isinstance(data, dict):
        raise RunStateError("run record must be a JSON object")
    schema = data.get("schema")
    if schema != RUN_SCHEMA:
        raise RunStateError(
            "unsupported run schema %r (this helper writes v%d)" % (schema, RUN_SCHEMA)
        )
    for key, typ in (("items", list), ("confirmed", dict), ("log", list), ("phases_done", list)):
        if not isinstance(data.get(key), typ):
            raise RunStateError("run record field %r must be a %s" % (key, typ.__name__))
    for it in data["items"]:
        if not isinstance(it, dict) or not it.get("key"):
            raise RunStateError("every run item needs a 'key'")
        if it.get("state") not in RUN_ITEM_STATES:
            raise RunStateError(
                "run item %r has state %r; expected one of %s"
                % (it.get("key"), it.get("state"), ", ".join(RUN_ITEM_STATES))
            )
    return data


def write_run(run):
    """Serialize a run record to JSON text (sorted keys: a stable byte layout keeps
    a `diff` between two run states readable for the operator)."""
    return json.dumps(run, indent=2, sort_keys=True) + "\n"


def run_add_items(run, keys, kind, state="pending"):
    """Register work items (surfaces, pages) idempotently. Re-registering an
    existing key is a NO-OP that preserves its current state -- so re-running
    detection after a compaction cannot reset a page that is already done."""
    if state not in RUN_ITEM_STATES:
        raise RunStateError("bad state %r" % state)
    have = {it["key"] for it in run["items"]}
    for k in keys:
        if k in have:
            continue
        run["items"].append({"key": k, "kind": kind, "state": state, "rounds": 0, "note": ""})
        have.add(k)
    return run


def run_mark(run, key, state, note="", rounds=None):
    """Apply one item transition. An unknown key is an ERROR: it means the caller
    and the record disagree about what work exists, and inventing the item here
    would paper over exactly the drift this record exists to detect."""
    if state not in RUN_ITEM_STATES:
        raise RunStateError("bad state %r" % state)
    for it in run["items"]:
        if it["key"] == key:
            it["state"] = state
            if note:
                it["note"] = note
            if rounds is not None:
                it["rounds"] = rounds
            return run
    raise RunStateError("no such run item: %r" % key)


def run_set_phase(run, phase, confirmed=None):
    """Advance the recorded phase and merge in any operator confirmations.
    `confirmed` is the durable half of the run: the detection the operator
    approved, the move plan they approved. Merged (not replaced) so one phase
    cannot drop another's confirmations."""
    if phase not in RUN_PHASES:
        raise RunStateError("unknown phase %r; expected one of %s" % (phase, ", ".join(RUN_PHASES)))
    if run.get("phase") and run["phase"] not in run["phases_done"]:
        run["phases_done"].append(run["phase"])
    run["phase"] = phase
    if confirmed:
        if not isinstance(confirmed, dict):
            raise RunStateError("confirmed must be a JSON object")
        run["confirmed"].update(confirmed)
    return run


def run_log(run, message):
    """Append a progress line. The §3.7 loop is required to log what changed and
    why each round; putting that in the record rather than the transcript is what
    makes it survive compaction."""
    run["log"].append(message)
    return run


def run_summary(run):
    """Human-readable status: phase position plus a per-state item tally, with
    every parked item named. Parked items are spelled out rather than counted
    because a park is a deferred decision the operator still owes an answer to."""
    lines = []
    phase = run.get("phase", "?")
    pos = (RUN_PHASES.index(phase) + 1) if phase in RUN_PHASES else 0
    lines.append("stamp:  %s" % run.get("stamp", "?"))
    lines.append("mode:   %s" % run.get("mode", "?"))
    lines.append("phase:  %s (%d of %d)" % (phase, pos, len(RUN_PHASES)))
    if run.get("confirmed"):
        lines.append("confirmed: " + ", ".join(sorted(run["confirmed"])))
    tally = {s: 0 for s in RUN_ITEM_STATES}
    for it in run["items"]:
        tally[it["state"]] += 1
    lines.append(
        "items:  " + ", ".join("%d %s" % (tally[s], s) for s in RUN_ITEM_STATES if tally[s])
        if run["items"]
        else "items:  none registered"
    )
    for it in run["items"]:
        if it["state"] == "parked":
            lines.append("  PARKED %s: %s" % (it["key"], it.get("note") or "(no reason recorded)"))
    for it in run["items"]:
        if it["state"] == "in-progress":
            lines.append("  IN-PROGRESS %s (rounds: %d)" % (it["key"], it.get("rounds", 0)))
    return "\n".join(lines) + "\n"


def run_next(run, kind=None):
    """The next actionable item key, or None. Resume is a QUERY on the record, not
    a guess: an interrupted in-progress item is returned before any pending one,
    so a run that died mid-page picks that page back up instead of skipping it."""
    for want in ("in-progress", "pending"):
        for it in run["items"]:
            if it["state"] == want and (kind is None or it.get("kind") == kind):
                return it["key"]
    return None


# Every skill this repo stamps. Must equal the set of templates/<name>/SKILL.md on
# disk -- find_predecessors skips these, so a name missing here makes onboarding report
# an already-stamped canonical skill as a PREDECESSOR TO RETIRE. `update-rules` was
# missing for exactly that reason: ADR-0007 added the template and not this line, and
# nothing compared the two. test_dogfood.py now does.
CANONICAL = frozenset({"changelog-release", "update-docs", "update-deps", "update-rules"})

# STRONG signals name the actual work; WEAK signals are terse words that recur
# incidentally ("changelog", "readme"). A body qualifies only with >=1 strong
# signal OR >=2 weak ones -- so a single incidental mention is not a candidate
# (spec Section 7.1: "content actually matches changelog/docs-sync WORK").
_CL_STRONG = (
    "keep a changelog",
    "changelog.md",
    "update the changelog",
    "[unreleased]",
    "conventional commit",
    "bump the version",
    "version bump",
    "semver",
    "release notes",
)
_CL_WEAK = ("changelog", "change log")
_DOCS_STRONG = (
    "docs/",
    "doc drift",
    "diataxis",
    "diátaxis",
    "update the docs",
    "update the readme",
    "keep the readme",
    "keep docs in sync",
    "docs in sync",
    "readme.md",
)
_DOCS_WEAK = ("readme", "documentation")
_DEPS_STRONG = (
    "tier model",
    "tier-based",
    "dependency update",
    "dependencies update",
    "bundlednativemodules",
    "cargo update",
    "--precise",
    "directory.packages.props",
    "verify_fast",
    "verify_full",
    "resolve tier",
    "dotnet restore",
    "expo install --fix",
)
_DEPS_WEAK = ("dependency", "dependencies")


def _score(low, strong, weak):
    s = sum(1 for k in strong if k in low)
    w = sum(1 for k in weak if k in low)
    return (s * 2 + w) if (s >= 1 or w >= 2) else 0


def classify_artifact(text):
    """Classify a skill/command body by CONTENT (never by name). Returns
    'changelog', 'docs', 'deps', or None when no surface matches actual work.
    Highest score wins; ties resolve deps > docs > changelog (a deps command
    that incidentally mentions docs terms is still deps)."""
    low = text.lower()
    cl = _score(low, _CL_STRONG, _CL_WEAK)
    dc = _score(low, _DOCS_STRONG, _DOCS_WEAK)
    dp = _score(low, _DEPS_STRONG, _DEPS_WEAK)
    if cl == 0 and dc == 0 and dp == 0:
        return None
    # max() returns the FIRST maximal element on ties, so tuple order encodes
    # the tie-break: deps before docs before changelog.
    return max(("deps", dp), ("docs", dc), ("changelog", cl), key=lambda kv: kv[1])[0]


_PROVENANCE_RE = re.compile(r"(stamped by onboard-repo v)\d+( from claude-configs on )[^.]*(\.)")


def restamp_provenance(text, version, date):
    """Set the provenance header's version and date. Used on --sync so the merged
    file records the sync's version/date rather than the template's `<date>`
    placeholder. No-op if no provenance header is present."""
    return _PROVENANCE_RE.sub(
        lambda m: "%s%s%s%s%s" % (m.group(1), version, m.group(2), date, m.group(3)), text, count=1
    )


def find_predecessors(claude_dir):
    """Scan .claude/skills/*/SKILL.md and .claude/commands/*.md for artifacts
    whose CONTENT matches changelog or docs-sync work, excluding our canonical
    skills. Returns [{path, name, kind, excerpt}] sorted by path."""
    claude_dir = pathlib.Path(claude_dir)
    candidates = []
    skills_root = claude_dir / "skills"
    if skills_root.is_dir():
        for d in sorted(skills_root.iterdir()):
            sk = d / "SKILL.md"
            if d.is_dir() and sk.is_file():
                candidates.append((d.name, sk))
    cmds_root = claude_dir / "commands"
    if cmds_root.is_dir():
        # rglob: Claude Code commands can be namespaced in subdirs
        # (commands/release/changelog.md -> /release:changelog).
        for f in sorted(cmds_root.rglob("*.md")):
            if f.is_file():  # skip a broken symlink or a directory named *.md
                candidates.append((f.stem, f))

    found = []
    for name, path in candidates:
        # Exclude only canonical SKILLS (always skills/<name>/SKILL.md), never a
        # same-named legacy command (commands/<name>.md) — that must still surface
        # for retirement. path.name == "SKILL.md" is the canonical-skill signal.
        if name in CANONICAL and path.name == "SKILL.md":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # unreadable/broken entry never aborts the whole scan
        kind = classify_artifact(text)
        if kind is None:
            continue
        excerpt = "\n".join(text.strip().splitlines()[:5])
        found.append({"path": str(path), "name": name, "kind": kind, "excerpt": excerpt})
    found.sort(key=lambda d: d["path"])
    return found


# inline link/image target: `](target)` where target is either an <angle> form
# (which may contain spaces) or a bare no-space form. Mirrors _INLINE_LINK_RE so a
# spaced `<my file.md>` is captured whole and re-emitted in <...> form (review S2-M2).
_REBASE_INLINE_RE = re.compile(r"(\]\(\s*)(?:<([^>]*)>|([^)>\s]+))(\s*(?:\"[^\"]*\")?\s*\))")
_REBASE_REFDEF_RE = re.compile(r"(?m)^(\s*\[[^\]]+\]:\s*<?)([^>\s]+)(>?\s*$)")


def _is_relative_target(target):
    if target.startswith("#"):
        return False
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:", target):  # http:, mailto:, etc.
        return False
    return not target.startswith("/")  # absolute path


def rebase_relative_links(text, page_old, page_new, moves):
    """Rewrite a moved page's OUTBOUND relative links so they resolve from the new
    location. For each relative, non-anchor target, in this exact order (spec 4.1):
    split path#anchor; tgt_old = normpath(join(dirname(page_old), path));
    loc = moves.get(tgt_old, tgt_old); relpath(loc, dirname(page_new)); reattach
    anchor. posixpath throughout. Fenced links untouched. Apply AFTER
    rewrite_markdown_links (order verified load-bearing, spec 4.4)."""

    def rebase_one(target):
        if not _is_relative_target(target):
            return target
        path, sep, frag = target.partition("#")
        if path == "":
            return target
        tgt_old = posixpath.normpath(posixpath.join(posixpath.dirname(page_old), path))
        loc = moves.get(tgt_old, tgt_old)
        # moves values are contractually repo-relative; an absolute loc would make
        # posixpath.relpath consult os.getcwd() (impure/cwd-dependent), so refuse it
        # and leave the link untouched rather than emit a cwd-dependent path.
        if posixpath.isabs(loc):
            return target
        new = posixpath.relpath(loc, posixpath.dirname(page_new))
        return new + (sep + frag if sep else "")

    def rebase_inline(m):
        if m.group(2) is not None:  # <angle> target (may contain spaces)
            return m.group(1) + "<" + rebase_one(m.group(2)) + ">" + m.group(4)
        return m.group(1) + rebase_one(m.group(3)) + m.group(4)

    out = []
    for seg, is_fence in _split_fences(text):
        if is_fence:
            out.append(seg)
            continue
        seg = _REBASE_INLINE_RE.sub(rebase_inline, seg)
        seg = _REBASE_REFDEF_RE.sub(lambda m: m.group(1) + rebase_one(m.group(2)) + m.group(3), seg)
        out.append(seg)
    return "".join(out)


def _non_fence_word_count(text):
    n = 0
    for seg, is_fence in _split_fences(text):
        if not is_fence:
            n += len(seg.split())
    return n


def shrink_violations(old_text, new_text, cleared_finding):
    """Guard a loop rewrite (spec 4.1). warn: an ATX heading in old_text is gone
    from new_text. error: non-fence word count cut by > 25% UNLESS cleared_finding
    (a rewrite that clears >=1 gate/reviewer finding may legitimately shrink, e.g.
    deleting a fabricated paragraph). Pure."""
    out = []
    old_h = set(heading_slugs(old_text))
    new_h = set(heading_slugs(new_text))
    for slug in sorted(old_h - new_h):
        out.append(("warn", "heading dropped: %s" % slug))
    ow = _non_fence_word_count(old_text)
    nw = _non_fence_word_count(new_text)
    if ow > 0 and nw < ow * 0.75 and not cleared_finding:
        out.append(
            (
                "error",
                "non-fence word count cut %d%% (%d -> %d)"
                % (round((ow - nw) * 100.0 / ow), ow, nw),
            )
        )
    return out


_CARGO_WS_RE = re.compile(r"^\s*\[workspace\]\s*$", re.MULTILINE)
_CARGO_MEMBERS_RE = re.compile(r"^\s*members\s*=\s*\[(.*?)\]", re.MULTILINE | re.DOTALL)


def cargo_workspace_members(cargo_toml_text):
    """members = [...] globs under [workspace]; [] when not a workspace root."""
    if not _CARGO_WS_RE.search(cargo_toml_text):
        return []
    m = _CARGO_MEMBERS_RE.search(cargo_toml_text)
    if not m:
        return []
    return [s.strip().strip('"').strip("'") for s in m.group(1).split(",") if s.strip()]


def cargo_dep_kinds(cargo_toml_text):
    """Classify each dependency in [dependencies]/[dev-dependencies]/
    [build-dependencies]/[workspace.dependencies] as registry/exact/git/path.
    Section-scoped (no tomllib) so [package] metadata (authors, license, ...)
    is never misclassified as a dependency; defaults to registry."""
    dep_sections = {
        "dependencies",
        "dev-dependencies",
        "build-dependencies",
        "workspace.dependencies",
    }
    kinds = {}
    section = None
    for line in cargo_toml_text.splitlines():
        header = re.match(r"^\s*\[([^\]]+)\]\s*$", line)
        if header:
            section = header.group(1).strip()
            continue
        if section not in dep_sections:
            continue
        m = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*=\s*(.+?)\s*$", line)
        if not m:
            continue
        name, rest = m.group(1), m.group(2).strip()
        if rest.startswith("{"):
            if "git" in rest:
                kinds[name] = "git"
            elif "path" in rest:
                kinds[name] = "path"
            else:
                kinds[name] = "registry"
        else:
            ver = rest.strip('"').strip("'")
            kinds[name] = "exact" if ver.startswith("=") else "registry"
    return kinds


def package_json_deps(pkg_json_text):
    """Merge dependencies + devDependencies -> {name: spec}."""
    data = json.loads(pkg_json_text)
    out = {}
    out.update(data.get("dependencies", {}) or {})
    out.update(data.get("devDependencies", {}) or {})
    return out


def package_resolved_pins(resolved_json_text):
    """Package.resolved v3 -> [{name, version, branch, revision}] (branch/
    revision None when absent). branch/revision pins -> swift SKIP."""
    data = json.loads(resolved_json_text)
    out = []
    for pin in data.get("pins", []):
        state = pin.get("state", {}) or {}
        out.append(
            {
                "name": pin.get("identity"),
                "version": state.get("version"),
                "branch": state.get("branch"),
                "revision": state.get("revision"),
            }
        )
    return out


def directory_packages_props_versions(props_xml_text):
    """Central Package Management: <PackageVersion Include Version/> -> {name: ver}."""
    try:
        root = _ET.fromstring(props_xml_text)
    except _ET.ParseError:
        return {}
    return {
        pv.get("Include"): pv.get("Version")
        for pv in root.iter("PackageVersion")
        if pv.get("Include")
    }


# --- Project agent configuration (.claude/settings.json, .gitignore) ----------
#
# These provision the TARGET repo's own agent config, which is committed. They
# are unrelated to the installer's global ~/.claude/settings.json machinery in
# lib/merge_settings.py: that file is the operator's, this one is the repo's.

# Claude Code auto-allows a fixed set of read-only Bash commands in every mode,
# INCLUDING read-only forms of git, so an allow entry for one of these is dead
# weight. The set is not configurable and is not published as a list, so treat it
# as a version-sensitive assumption (recorded in ADR-0002), not a guarantee.
BUILTIN_READONLY_BASH = (
    "ls",
    "cat",
    "echo",
    "pwd",
    "head",
    "tail",
    "grep",
    "find",
    "wc",
    "which",
    "diff",
    "stat",
    "du",
    "cd",
)
BUILTIN_READONLY_GIT = (
    "git log",
    "git show",
    "git diff",
    "git status",
    "git blame",
    "git ls-files",
    "git ls-tree",
    "git rev-parse",
    "git describe",
    "git branch",
    "git tag",
    "git cat-file",
    "git shortlog",
)

_RULE_RE = re.compile(r"^(?P<tool>[A-Za-z]+)\((?P<body>.*)\)$", re.DOTALL)


def _is_builtin_readonly_bash(body):
    """True when a Bash(...) rule body names something Claude Code already allows
    unprompted, which makes an explicit allow entry redundant."""
    cmd = body.strip()
    for suffix in (":*", "*"):
        if cmd.endswith(suffix):
            cmd = cmd[: -len(suffix)]
    cmd = cmd.strip().rstrip(":").strip()
    if not cmd:
        return False
    if cmd in BUILTIN_READONLY_BASH:
        return True
    return any(cmd == g or cmd.startswith(g + " ") for g in BUILTIN_READONLY_GIT)


def pair_shell_rules(rules, drop_builtin_bash=False):
    """Mirror every shell rule across Bash and PowerShell, preserving order.

    Permission rules are matched PER TOOL, so `Bash(git reset:*)` does not block
    `PowerShell(git reset ...)`. Any ask/deny present in one form must be present
    in the other or the guard has a hole -- that is what drop_builtin_bash=False
    (the default, used for ask and deny) guarantees.

    With drop_builtin_bash=True (used for allow lists) a Bash rule duplicating the
    built-in read-only set is dropped as dead weight, while its PowerShell twin is
    KEPT: the PowerShell tool has no equivalent carve-out and genuinely needs it.

    Non-shell rules (Read/Edit/WebFetch/mcp__*) pass through untouched.
    """
    out, seen = [], set()

    def _emit(rule):
        if rule not in seen:
            seen.add(rule)
            out.append(rule)

    for rule in rules:
        m = _RULE_RE.match(rule.strip())
        if not m or m.group("tool") not in ("Bash", "PowerShell"):
            _emit(rule.strip())
            continue
        body = m.group("body")
        if not (drop_builtin_bash and _is_builtin_readonly_bash(body)):
            _emit("Bash(" + body + ")")
        _emit("PowerShell(" + body + ")")
    return out


# Commands each ecosystem needs in order to build and test without prompting.
_ECOSYSTEM_ALLOW = {
    "dotnet": (
        "dotnet build:*",
        "dotnet test:*",
        "dotnet restore:*",
        "dotnet clean:*",
    ),
    # `npm ci` installs exactly what the lockfile pins; `npm install <pkg>` / `npm i` / `npm add` change the dependency
    # set and rewrite package-lock.json, so they sit in ask with `uv add` and `composer require`.
    "js": ("npm run:*", "npm test:*", "npm ci:*"),
    # `vendor/bin/pint` is the FORMATTER: allowed only in its check form, because the
    # bare command REWRITES source. That is the same read-only rule the update-deps
    # template states for every ecosystem ("use `pint --test`, never `pint`") -- granting
    # the rewriting form unprompted would let a verify gate destroy baseline purity.
    # `cargo fmt:*` predates this list and is left as-is rather than changed here.
    "php": (
        "composer install:*",
        "composer dump-autoload:*",
        "composer validate:*",
        "php artisan test:*",
        "vendor/bin/pest:*",
        "vendor/bin/phpunit:*",
        "vendor/bin/pint --test:*",
        "vendor/bin/phpstan:*",
        "vendor/bin/psalm:*",
    ),
    # Bare `uv run:*` is deliberately absent: unlike `npm run <script>`, which is bounded
    # by package.json, `uv run <anything>` executes an arbitrary command and would be a
    # blanket shell grant. The bounded forms are listed instead, so the common test and
    # lint loops never prompt while `uv run rm -rf …` still does.
    #
    # `ruff format` appears only as `--check`, for the same reason as `pint --test` above.
    # The rest run repo-controlled code (pytest imports conftest.py, `uv sync` runs the
    # build backend) -- that is the model every ecosystem here already assumes, since
    # `npm install` runs postinstall and `cargo build` runs build.rs. The line drawn is
    # source-REWRITING, not code execution.
    "python": (
        "uv sync:*",
        "uv run pytest:*",
        "uv run ruff:*",
        "uv run mypy:*",
        "pytest:*",
        "ruff check:*",
        "ruff format --check:*",
        "mypy:*",
        "pip list:*",
        "pip show:*",
    ),
    "rust": ("cargo build:*", "cargo test:*", "cargo check:*", "cargo fmt:*"),
    "swift": ("swift build:*", "swift test:*"),
}

# Ecosystem commands that mutate a lockfile, a schema or the dependency tree.
#
# `npx:*` is NOT here any more. It used to be the one js ask rule, and it was the
# wrong tier for the wrong reason: `npx` is how every Node toolchain runs (`tsc`,
# `vitest`, `markdownlint-cli2`, `prettier`), so the rule fired on the hot path of
# every js repo -- and under auto mode an `ask` rule is a HUMAN-ONLY prompt the
# classifier cannot clear (`classifierApprovable: false`). The maintainer clicked
# through it on every lint run for weeks. What the rule guarded -- `npx <package>`
# fetching and executing an arbitrary registry package -- is real, but it is a
# supply-chain posture some repos want and most do not, so it is OPT-IN
# (`plan_project_permissions(ask_npx=True)`, `settings-plan --ask-npx`), asked
# once at onboarding with the cost stated. Rules that stay here fire on a
# deliberate, occasional action (adding a dependency, running a migration), which
# is exactly when a prompt is cheap and a mistake is expensive.
_NPX_ASK = "npx:*"
_ECOSYSTEM_ASK = {
    # `dotnet ef` covers `database update` / `database drop` / `migrations remove`, the same tier as `php artisan migrate`.
    "dotnet": ("dotnet add:*", "dotnet remove:*", "dotnet ef:*"),
    "js": ("npm install:*", "npm i:*", "npm add:*", "npm uninstall:*"),
    "php": (
        "composer update:*",
        "composer require:*",
        "composer remove:*",
        "php artisan migrate:*",
        "php artisan db:*",
    ),
    "python": (
        "uv add:*",
        "uv remove:*",
        "uv lock:*",
        "pip install:*",
        "pip uninstall:*",
        "poetry add:*",
        "poetry remove:*",
        "poetry update:*",
        # Schema migrations, the same reason `php artisan migrate` is here.
        "alembic upgrade:*",
        "alembic downgrade:*",
        "python manage.py migrate:*",
    ),
    "rust": ("cargo add:*", "cargo remove:*"),
    "swift": (),
}

# Credential-shaped paths an agent should not touch unprompted. The per-ecosystem
# entries are additive, not replacements.
#
# ONE glob, not an enumeration. The list this replaced spelled out .env.dev /
# .env.prod / .env.staging / .env.qa / ... and STILL missed .env.uat, .env.preview
# and .env.e2e -- environment names are an open set, so enumerating them leaks by
# construction. `.env*` covers plain `.env` as well (verified with `git
# check-ignore`, gitignore being the syntax Read/Edit rules use), and picks up
# `.envrc` for direnv users as a bonus.
#
# `**/*.env` -- the `config/prod.env` shape taken by docker's `env_file:` and
# GitLab's `dotenv:` reports -- was weighed and dropped. `.env*` already covers
# plain `.env`, so it would only have added the `foo.env` spelling.
#
# `**/.ssh/**` and `**/.aws/**` are deliberately absent. A relative glob anchors
# under the project, so those only ever matched a `.ssh` directory INSIDE the repo;
# the real ones are the user's own `~/.ssh/**` rule, which a shared project file
# has no business restating.
_SECRET_GLOBS = ("**/.env*",)
_ECOSYSTEM_SECRET_GLOBS = {
    "dotnet": ("**/appsettings*.json",),
    "js": ("**/.npmrc",),
    "php": ("**/auth.json",),
    # .pypirc holds PyPI upload tokens; pip.conf / uv.toml can carry an index URL with
    # embedded credentials for a private registry.
    "python": ("**/.pypirc", "**/pip.conf", "**/uv.toml"),
    "rust": ("**/.cargo/credentials*",),
    "swift": (),
}

# Mutating git that should never run unprompted, regardless of ecosystem.
_BASELINE_DENY = ("git reset:*", "git restore:*")
_BASELINE_ASK = ("git rm:*",)  # extended below
# Only the forms that cannot lose work or redirect a push: `git stash drop|clear|pop`, `git worktree remove`,
# `git remote set-url|remove` and `git switch --discard-changes|-f` fall through to the normal prompt (or ask, below).
_BASELINE_ALLOW = (
    "git fetch:*",
    "git switch:*",
    "git stash push:*",
    "git stash list:*",
    "git stash show:*",
    "git worktree add:*",
    "git worktree list:*",
    "git remote -v",
    "git remote show:*",
    "git remote get-url:*",
    "mkdir:*",
)
# `git switch` refuses to drop uncommitted changes unless forced; the forced forms ask. A prefix rule only sees the flag
# when it comes first (`git switch -f main`), which is how the forms are written in practice.
_BASELINE_ASK_EXTRA = ("git switch --discard-changes:*", "git switch -f:*", "git switch --force:*")


# One line per ask/deny rule body: why it is in that tier. `explain_permissions`
# renders these beside the plan so the operator confirms an informed choice, and
# a test pins that every rule the planner can emit has an entry -- a new rule
# without a reason is a rule nobody can defend at the prompt.
_RULE_REASONS = {
    "git reset:*": "rewrites branch history or the index; the git verb that loses work silently",
    "git restore:*": "overwrites working-tree files from the index or a commit; edits are gone",
    "git rm:*": "stages a deletion; a wrong path removes a tracked file from the next commit",
    "dotnet add:*": "changes the project's dependency set and lockfile",
    "dotnet remove:*": "changes the project's dependency set and lockfile",
    "dotnet ef:*": "can update or drop the database and remove migrations",
    "npm install:*": "adds or changes dependencies and rewrites package-lock.json (npm ci installs the lockfile as is)",
    "npm i:*": "short for npm install: adds or changes dependencies and rewrites package-lock.json",
    "npm add:*": "adds a dependency and rewrites package-lock.json",
    "npm uninstall:*": "drops a dependency and rewrites package-lock.json",
    "git switch --discard-changes:*": "switches branch by throwing away uncommitted changes",
    "git switch -f:*": "switches branch by throwing away uncommitted changes",
    "git switch --force:*": "switches branch by throwing away uncommitted changes",
    "composer update:*": "rewrites composer.lock across the dependency tree",
    "composer require:*": "adds a dependency and rewrites composer.lock",
    "composer remove:*": "drops a dependency and rewrites composer.lock",
    "php artisan migrate:*": "alters the database schema",
    "php artisan db:*": "seeds, wipes or otherwise mutates the database",
    "uv add:*": "adds a dependency and rewrites the lockfile",
    "uv remove:*": "drops a dependency and rewrites the lockfile",
    "uv lock:*": "rewrites uv.lock",
    "pip install:*": "installs into the active environment; can pull arbitrary packages",
    "pip uninstall:*": "removes packages from the active environment",
    "poetry add:*": "adds a dependency and rewrites poetry.lock",
    "poetry remove:*": "drops a dependency and rewrites poetry.lock",
    "poetry update:*": "rewrites poetry.lock across the dependency tree",
    "alembic upgrade:*": "alters the database schema",
    "alembic downgrade:*": "reverts database schema migrations",
    "python manage.py migrate:*": "alters the database schema",
    "cargo add:*": "adds a dependency and rewrites Cargo.lock",
    "cargo remove:*": "drops a dependency and rewrites Cargo.lock",
    _NPX_ASK: "runs an arbitrary registry package (opt-in: fires on every tsc/vitest/lint run)",
}
_SECRET_REASON = "credential path; ask not deny, so .env.example stays readable (ADR-0009)"

# What an `ask` rule costs. Stated once, rendered with every plan: the operator is
# choosing prompts, not just protection.
ASK_COST = (
    "An `ask` rule is a human-only prompt: it fires in every permission mode, and "
    "under auto mode the classifier cannot clear it -- you click, or the turn stops. "
    "Every rule below trades a prompt for a guard; keep the ones whose action is rare "
    "and expensive to get wrong."
)


def plan_project_permissions(ecosystems, ask_npx=False):
    """Build a proposed project .claude/settings.json permissions block.

    `ecosystems` is the list of names from `deps-detect` (js / php / rust / dotnet /
    swift). An unknown name contributes nothing rather than raising, so a newly
    supported ecosystem degrades to the baseline instead of breaking onboarding.
    `ask_npx` adds the opt-in `npx:*` ask rule when js is among the ecosystems
    (see the note above `_ECOSYSTEM_ASK`).

    Returns the dict to be MERGED into (never written over) an existing file.
    """
    names = [e for e in dict.fromkeys(ecosystems or ()) if e in _ECOSYSTEM_ALLOW]

    allow = list(_BASELINE_ALLOW)
    for name in names:
        allow.extend(_ECOSYSTEM_ALLOW[name])

    ask = list(_BASELINE_ASK) + list(_BASELINE_ASK_EXTRA)
    for name in names:
        ask.extend(_ECOSYSTEM_ASK.get(name, ()))
    if ask_npx and "js" in names:
        ask.append(_NPX_ASK)

    secret_globs = list(_SECRET_GLOBS)
    for name in names:
        secret_globs.extend(_ECOSYSTEM_SECRET_GLOBS.get(name, ()))

    # Credential globs land in ASK, never DENY, and the two decisions are coupled.
    # gitignore patterns carry no negation -- "a deny rule can't carry allowlist
    # exceptions" (the permissions doc) -- so a single wildcard in `deny` could never
    # spare `.env.example`, the committed template an agent legitimately reads to
    # document setup. Enumerating was the old way to spare it; `ask` is the cheaper
    # one. It also stops a SHARED project file silently overriding a choice the user
    # made for themselves: deny outranks ask across settings scopes, so a project
    # deny converts their global "ask me" into "never", with no prompt to override.
    ask_rules = pair_shell_rules(["Bash(%s)" % r for r in ask])
    for glob in secret_globs:
        ask_rules.append("Read(%s)" % glob)
        ask_rules.append("Edit(%s)" % glob)

    return {
        "permissions": {
            "allow": pair_shell_rules(["Bash(%s)" % r for r in allow], drop_builtin_bash=True),
            "ask": ask_rules,
            "deny": pair_shell_rules(["Bash(%s)" % r for r in _BASELINE_DENY]),
        }
    }


def explain_permissions(plan):
    """Render the ask and deny tiers of a `plan_project_permissions` result as
    text: the cost statement, then one line per rule body (the Bash/PowerShell
    twins collapsed) with the tier and the reason from `_RULE_REASONS`. Allow
    rules are not explained -- they remove prompts, they never add one."""
    perms = plan["permissions"]
    lines = [ASK_COST, ""]
    for tier in ("deny", "ask"):
        seen = []
        for rule in perms.get(tier, ()):
            m = _RULE_RE.match(rule)
            body = m.group("body") if m and m.group("tool") in ("Bash", "PowerShell") else rule
            if body in seen:
                continue
            seen.append(body)
            if m and m.group("tool") in ("Read", "Edit"):
                reason = _SECRET_REASON
            else:
                reason = _RULE_REASONS.get(body, "(no reason recorded)")
            lines.append("%-5s %-28s %s" % (tier, body, reason))
    return "\n".join(lines) + "\n"


# --- ADR-0017: an onboarded plan is audited and migrated, not just printed ------
#
# On Claude Code 2.1.259 a path-less `rg`, `grep -r`, `git`, `cp` or `mv` was
# treated as a READ OF THE DIRECTORY it would scan, and that directory checked
# against every `Read()` deny rule's static prefix -- everything before the rule's
# first glob segment. A rule anchored inside the repo (`**/x`, `x`, `./x`, `/x`)
# has its prefix in the working directory, so every such command became a
# human-only prompt the auto-mode classifier could not clear. A `//`-anchored rule
# has the prefix `/`, which is inside no working directory; a `~`-anchored one is
# outside the repo too. The pre-ADR-0009 planner emitted the inside-repo shape
# for every credential path, and nothing revisited an onboarded file afterwards.
#
# 2.1.260 reverted that directory check, so the prompt storm is gone. Re-anchoring
# stands on the coverage argument below, which never depended on it.
#
# `//**/<path>` matches the same files under this repo AND anywhere else: a strict
# superset, so re-anchoring never leaves a file less protected. Tier is kept --
# a repo owner's deny stays a deny; moving credential paths to `ask` (ADR-0009)
# is a policy change the operator makes by re-running settings-plan, never a
# side effect of the migration.

# Home-directory globs in PROJECT scope anchor under the repo and so match only a
# `.ssh` directory inside it: zero coverage, and a guard trigger until re-anchored.
_HOME_DIR_GLOBS = ("**/.ssh/**", "**/.aws/**", "**/.gnupg/**", "**/.kube/**")
# The allow-tier shapes test_payload.py refuses in the shipped payload: a blanket
# grant, a wildcarded interpreter, a command wrapper, an argument-pinned fetcher.
_WRAPPERS = ("xargs", "env", "nice", "nohup", "time", "timeout", "sudo", "watch")
_FETCHERS = ("curl", "wget", "iwr", "irm", "Invoke-WebRequest", "Invoke-RestMethod")
_WILDCARD_INTERPRETER = re.compile(
    r"^(python[0-9.]*|node|npx|sh|bash|zsh|pwsh|powershell|perl|ruby|php)\*$"
)


def _anchored_outside_repo(body):
    return body.startswith("//") or body.startswith("~")


def _reanchor(body):
    """`**/x`, `x`, `./x` and `/x` all become `//**/x`."""
    b = body
    if b.startswith("./"):
        b = b[2:]
    elif b.startswith("/"):
        b = b[1:]
    if b.startswith("**/"):
        b = b[3:]
    return "//**/" + b


def _is_broad_allow(rule):
    m = _RULE_RE.match(rule.strip())
    if not m or m.group("tool") not in ("Bash", "PowerShell"):
        return False
    body = m.group("body").strip()
    if body in ("*", ":*"):
        return True
    if _WILDCARD_INTERPRETER.match(body):
        return True
    head = body.split(":*")[0].rstrip("*").strip()
    first = head.split(" ", 1)[0] if head else ""
    if first in _WRAPPERS:
        return True
    if first in _FETCHERS and head != first:
        return True
    return False


def audit_project_permissions(settings):
    """Report what is wrong with an existing project permissions block.

    guard_triggers   -- deny `Read()` rules anchored inside the repo (every
                        path-less rg/grep -r prompts a human while they exist)
    dead_home_denies -- `**/.ssh/**`-style globs that cover nothing in project scope
    broad_allows     -- allow entries the shipped payload's own tests refuse
    Never writes. An absent permissions block audits clean.
    """
    perm = (settings or {}).get("permissions") or {}
    deny = perm.get("deny") or []
    allow = perm.get("allow") or []
    triggers, dead = [], []
    for rule in deny:
        m = _RULE_RE.match(rule.strip())
        if not m or m.group("tool") not in ("Read", "Edit"):
            continue
        body = m.group("body").strip()
        if m.group("tool") == "Read" and not _anchored_outside_repo(body):
            triggers.append(rule)
        if body in _HOME_DIR_GLOBS:
            dead.append(rule)
    return {
        "guard_triggers": triggers,
        "dead_home_denies": dead,
        "broad_allows": [r for r in allow if _is_broad_allow(r)],
    }


def migrate_project_permissions(settings):
    """Re-anchor every inside-repo deny `Read()`/`Edit()` rule at `//**/`.

    Returns (new_settings, actions) with one {tier, from, to} per rewritten
    rule. Order is kept, a rewrite that lands on a rule already present is
    dropped rather than duplicated, and the ask/allow tiers and every other key
    are untouched. Pure and idempotent.
    """
    settings = copy.deepcopy(settings or {})
    perm = settings.get("permissions") or {}
    deny = perm.get("deny") or []
    if not deny:
        return settings, []
    out, seen, actions = [], set(), []
    for rule in deny:
        new = rule
        m = _RULE_RE.match(rule.strip())
        if m and m.group("tool") in ("Read", "Edit"):
            body = m.group("body").strip()
            if not _anchored_outside_repo(body):
                new = "%s(%s)" % (m.group("tool"), _reanchor(body))
                actions.append({"tier": "deny", "from": rule, "to": new})
        if new not in seen:
            seen.add(new)
            out.append(new)
    perm["deny"] = out
    return settings, actions


def ensure_gitignore_lines(text, lines):
    """Append each missing line to a .gitignore body, idempotently.

    Compares on stripped content so a trailing-newline difference cannot produce
    a duplicate entry. Unchanged input returns unchanged output, so the caller can
    skip the write entirely.
    """
    existing = {ln.strip() for ln in (text or "").splitlines() if ln.strip()}
    missing = [ln for ln in lines if ln.strip() not in existing]
    if not missing:
        return text
    out = text or ""
    if out and not out.endswith("\n"):
        out += "\n"
    return out + "\n".join(missing) + "\n"


# --- migrating GitHub Copilot instruction files -------------------------------
# A repo arriving from Copilot already has human-written, codebase-grounded
# instruction files. Porting them is a mechanical frontmatter transform, which is a
# different act from AUTHORING rules (ADR-0002) -- the content and its grounding
# already exist and are not being invented here.
#
# Two traps, both observed on a real migration:
#
#  1. Copilot quotes its `description:`; a naive port that drops the quotes turns a
#     valid document into one YAML rejects, and the rule then silently never loads.
#     These converters re-quote unconditionally rather than copying the source form.
#  2. `${input:Name}` has explicit delimiters. Claude's `$name` does not, so
#     `${input:Name}Props` becomes `$NameProps` -- a different, undeclared variable.
#     The converter refuses to make that substitution silently.

_APPLY_TO_RE = re.compile(r"^applyTo:\s*(.+?)\s*$", re.MULTILINE)
_INPUT_RE = re.compile(r"\$\{input:([A-Za-z_][A-Za-z0-9_]*)(?::[^}]*)?\}")


def _yaml_quote(value):
    """Always double-quote a scalar. Cheaper than deciding when it is safe, and the
    failure it prevents (an unquoted colon-space) is silent."""
    return '"%s"' % value.strip().strip("\"'").replace("\\", "\\\\").replace('"', '\\"')


def convert_copilot_instruction(text):
    """(new_text, notes) porting one `*.instructions.md` to a Claude rule.

    `applyTo: "a,b"` becomes a `paths:` block sequence -- Copilot's comma-joined
    string and Claude's list are the same information in two shapes. Every other
    frontmatter key is preserved, with scalars re-quoted.
    """
    notes = []
    fm, _ = split_frontmatter(text)
    if fm is None:
        return text, ["no frontmatter -- nothing to convert"]
    m = _APPLY_TO_RE.search(fm)
    if not m:
        return text, ["no applyTo: -- not a Copilot instruction file"]
    globs = [g.strip().strip("\"'") for g in m.group(1).strip("\"'").split(",") if g.strip()]
    if not globs:
        notes.append("applyTo: was empty -- the ported rule would load every session")
    out = ["paths:"]
    for g in globs:
        out.append("  - " + _yaml_quote(g))
    for line in fm.split("\n"):
        if _APPLY_TO_RE.match(line) or not line.strip():
            continue
        kv = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*)$", line)
        if kv and kv.group(2).strip():
            out.append("%s: %s" % (kv.group(1), _yaml_quote(kv.group(2))))
        else:
            out.append(line)
    body = text[len("---\n") + len(fm) :]
    body = body[body.index("\n---") + len("\n---") :] if "\n---" in body else body
    notes.append("applyTo -> paths (%d glob%s)" % (len(globs), "" if len(globs) == 1 else "s"))
    return "---\n" + "\n".join(out) + "\n---" + body, notes


def convert_copilot_prompt(text):
    """(new_text, arg_names, notes) porting one `*.prompt.md` to a Claude skill.

    `${input:Name}` becomes `$Name` and Name is collected for `arguments:`. A
    placeholder followed immediately by an identifier character is left ALONE and
    reported: `${input:Name}Props` cannot become `$NameProps` without silently
    renaming the variable, and a template that looks converted but is not is worse
    than one that is obviously untouched.
    """
    notes, args, out, i = [], [], [], 0
    for m in _INPUT_RE.finditer(text):
        name = m.group(1)
        tail = text[m.end() : m.end() + 1]
        out.append(text[i : m.start()])
        if tail and (tail.isalnum() or tail == "_"):
            out.append(m.group(0))
            notes.append(
                "line %d: ${input:%s} is followed by %r -- $%s%s would read as a "
                "different variable; rename the placeholder or add a separator"
                % (text.count("\n", 0, m.start()) + 1, name, tail, name, tail)
            )
        else:
            out.append("$" + name)
            if name not in args:
                args.append(name)
        i = m.end()
    out.append(text[i:])
    converted = "".join(out)
    if args:
        notes.append("${input:...} -> $name for: " + ", ".join(args))
    return converted, args, notes

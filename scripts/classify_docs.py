#!/usr/bin/env python3
"""Classify docs/ entries as active or historical provenance (docs/archive/).

Selection logic for the physical split described in docs/MODULE_MAP.md.  The unit of
movement is a top-level entry of docs/ (a file or a whole directory).  An entry is
historical when its name matches a historical pattern, and it is NOT protected:

* protected name: owner decision / ADR / freeze / OWNER_DECISIONS documents (a file whose
  name matches keeps its whole entry in place; so do owner_decision_* and
  architecture_freeze* entries);
* protected location: docs/claude/ (state and playbook), docs/archive/ itself;
* core documents and every tracked file outside docs/ (src, scripts, tests, .github,
  config, qualification, evidence, .claude, root files, SHA256SUMS manifests) must
  not reference any file of the entry, by full docs/ path or by entry name.

Modes: default prints the plan; --json prints it as JSON; --links lists broken relative
links in docs/; --apply performs the git mv and link rewrite; --check exits 1 when a
historical entry is still outside docs/archive/ or when code references anything
inside docs/archive/.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = "docs"
ARCHIVE = "docs/archive"

# Core documents whose references keep an entry active (besides every non-docs file).
CORE_DOCS = (
    "docs/README.md",
    "docs/PROJECT_MISSION.md",
    "docs/CURRENT_EXECUTION_AUTHORITY.md",
    "docs/MODULE_MAP.md",
)
KEEP_TREES = ("docs/claude/", "docs/foundry-execution/", "docs/architecture/", ARCHIVE + "/")

PROTECTED_NAME = re.compile(
    r"owner_decision|owner-decision|OWNER_DECISIONS|(^|[_/\-.])adr([_\-./0-9]|$)|freeze",
    re.IGNORECASE,
)
PROTECTED_ENTRY = re.compile(r"owner_decision|OWNER_DECISIONS|architecture_freeze", re.IGNORECASE)
# Historical patterns per docs/MODULE_MAP.md "Docs: current vs historical".
HISTORICAL_NAME = re.compile(
    r"""^(
        workstream_.*
      | .*_2026\d{4}(_.*)?      # dated closures / packets
      | .*_2026\d{4}\.md
      | .*_erratum_.*
      | J_P\d.*
      | phase.*
      | NEXT_STEP_HANDOFF_.*
      | PROJECT_UPDATE_.*
      | roadmap
      | af0.* | af456_.*
      | forge_.* | xmage_.*
      | ci479_.* | pr\d.* | b8_takeover_.* | oc572_.*
      | project_integrity_.* | project_hygiene_.* | project_integration_hygiene_.*
      | test_signal_integrity_.*
      | COORDINATOR_EXECUTION_AUTHORITY_.*
    )$""",
    re.VERBOSE | re.IGNORECASE,
)
WORD = re.compile(r"[A-Za-z0-9_.\-]+")
DOC_PATH = re.compile(r"docs/[A-Za-z0-9_./\-]+")
TEXT_LIMIT = 8_000_000
DOC_REF = re.compile(r"docs/archive/")


def _git_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    ).stdout.decode()
    return [f for f in out.split("\0") if f]


def _read(path: str) -> str:
    p = ROOT / path
    try:
        if p.stat().st_size > TEXT_LIMIT:
            return ""
        return p.read_bytes().decode("utf-8", "ignore")
    except OSError:
        return ""


def referencer_files(files: list[str]) -> list[str]:
    refs = []
    for f in files:
        if f.startswith(DOCS + "/"):
            if f in CORE_DOCS or f.startswith(("docs/claude/",)):
                refs.append(f)
        else:
            refs.append(f)
    return refs


def entries(files: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in files:
        parts = f.split("/")
        if parts[0] != DOCS or len(parts) < 2 or parts[1] == "archive":
            continue
        out.setdefault(parts[1], []).append(f)
    return out


def classify(files: list[str] | None = None) -> dict[str, object]:
    files = files if files is not None else _git_files()
    ents = entries(files)
    words: set[str] = set()
    paths: set[str] = set()
    for f in referencer_files(files):
        text = _read(f)
        words.update(WORD.findall(text))
        paths.update(p.rstrip(".") for p in DOC_PATH.findall(text))
    historical: list[str] = []
    kept: dict[str, str] = {}
    for name in sorted(ents):
        members = ents[name]
        if f"docs/{name}/".startswith(KEEP_TREES) or f"docs/{name}" in CORE_DOCS:
            kept[name] = "active tree"
        elif not HISTORICAL_NAME.match(name):
            kept[name] = "not historical by name"
        elif PROTECTED_ENTRY.search(name) or any(
            PROTECTED_NAME.search(m.rsplit("/", 1)[1]) for m in members
        ):
            kept[name] = "owner decision / ADR / freeze"
        else:
            stem = name
            hit = None
            if stem in words:
                hit = f"referenced by name {stem}"
            else:
                for m in members:
                    if m in paths:
                        hit = f"referenced path {m}"
                        break
            if hit:
                kept[name] = hit
            else:
                historical.append(name)
    return {
        "historical": historical,
        "kept_historical_named": {k: v for k, v in kept.items() if HISTORICAL_NAME.match(k)},
        "entries": ents,
    }


def check(files: list[str] | None = None) -> list[str]:
    files = files if files is not None else _git_files()
    problems: list[str] = []
    plan = classify(files)
    for name in plan["historical"]:  # type: ignore[union-attr]
        problems.append(f"historical doc outside archive: docs/{name}")
    for f in referencer_files(files):
        if f.startswith(ARCHIVE + "/"):
            continue
        if DOC_REF.search(_read(f)) and f not in _ARCHIVE_POINTERS:
            problems.append(f"code references docs/archive/: {f}")
    return problems


# Files that legitimately point at the archive as a location (navigation, not content).
_ARCHIVE_POINTERS = {
    "docs/README.md",
    "docs/MODULE_MAP.md",
    "scripts/classify_docs.py",
    "tests/unit/test_docs_archive.py",
}


LINK = re.compile(r"(\]\(|^\[[^\]]+\]:\s*)(<?)([^)\s>]+)", re.MULTILINE)


def _split_target(t: str) -> tuple[str, str] | None:
    if re.match(r"^([a-z][a-z0-9+.-]*:|#|/)", t, re.IGNORECASE):
        return None
    for i, ch in enumerate(t):
        if ch in "#?":
            return t[:i], t[i:]
    return t, ""


def iter_links(rel: str, text: str):
    """Yield (match, path_part, suffix) for relative markdown links."""
    for m in LINK.finditer(text):
        sp = _split_target(m.group(3))
        if sp and sp[0]:
            yield m, sp[0], sp[1]


def broken_links(files: list[str]) -> list[str]:
    out = []
    for f in files:
        if not (f.startswith("docs/") and f.endswith(".md")) or not (ROOT / f).exists():
            continue
        base = (ROOT / f).parent
        for _m, path, _s in iter_links(f, _read(f)):
            if not (base / path).resolve().exists():
                out.append(f"{f} -> {path}")
    return out


def apply_moves(names: list[str]) -> None:
    """git mv entries into docs/archive/ and rewrite relative links that crossed."""
    import os

    files = _git_files()
    moved = {n: f"{ARCHIVE}/{n}" for n in names}

    def new_of(rel: str) -> str:
        parts = rel.split("/")
        if parts[0] == DOCS and len(parts) > 1 and parts[1] in moved:
            return "/".join([ARCHIVE, *parts[1:]])
        return rel

    docs_md = [f for f in files if f.startswith("docs/") and f.endswith(".md")]
    edits: dict[str, str] = {}
    for f in docs_md:
        text = _read(f)
        old_base = (ROOT / f).parent
        new_f = new_of(f)

        def repl(
            m: re.Match[str], f: str = f, new_f: str = new_f, old_base: Path = old_base
        ) -> str:
            sp = _split_target(m.group(3))
            if not sp or not sp[0]:
                return m.group(0)
            target = (old_base / sp[0]).resolve()
            if not target.exists():
                return m.group(0)  # already broken: leave untouched
            rel_t = target.relative_to(ROOT).as_posix()
            new_t = new_of(rel_t)
            if new_t == rel_t and new_f == f:
                return m.group(0)
            new_rel = os.path.relpath(ROOT / new_t, (ROOT / new_f).parent)
            if sp[0].endswith("/") and not new_rel.endswith("/"):
                new_rel += "/"
            return m.group(1) + m.group(2) + new_rel + sp[1]

        new_text = LINK.sub(repl, text)  # type: ignore[arg-type]
        if new_text != text:
            edits[f] = new_text
    (ROOT / ARCHIVE).mkdir(parents=True, exist_ok=True)
    for n, dest in moved.items():
        subprocess.run(["git", "mv", f"docs/{n}", dest], cwd=ROOT, check=True)
    for f, text in edits.items():
        (ROOT / new_of(f)).write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--links", action="store_true", help="list broken relative links in docs/")
    ap.add_argument("--apply", action="store_true", help="git mv historical entries and fix links")
    ns = ap.parse_args(argv)
    if ns.check:
        problems = check()
        for p in problems:
            print(p)
        print(f"classify_docs --check: {'FAIL' if problems else 'OK'} ({len(problems)} problems)")
        return 1 if problems else 0
    if ns.links:
        for b in broken_links(_git_files()):
            print(b)
        return 0
    plan = classify()
    if ns.apply:
        apply_moves(list(plan["historical"]))  # type: ignore[arg-type]
        return 0
    summary = {
        "historical": plan["historical"],
        "kept_historical_named": plan["kept_historical_named"],
    }
    if ns.json:
        print(json.dumps(summary, indent=2))
    else:
        for n in plan["historical"]:  # type: ignore[union-attr]
            print(n)
    return 0


if __name__ == "__main__":
    sys.exit(main())

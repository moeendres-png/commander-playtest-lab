#!/usr/bin/env python3
"""Classify docs/ entries: current, kept because anchored, or archivable by topic.

The unit of movement is a top-level entry of docs/ (a file or a whole directory), plus the
nested unit ``claude/handoffs``.  An entry belongs to an archive topic (TOPICS) when it
describes something that was removed or finished.  Topic membership is a reviewed decision
of the owner of the documentation, kept in TOPICS; an entry without topic is current.

An entry with a topic still stays in place (class ``keep-anchored``) when one of three
anchors holds:

1. a test, script, workflow, source, configuration or ``.claude`` file reads it, by full
   docs/ path, by its entry name, or by a basename that is unique in the tree;
2. a machine-read record under qualification/ or candidate-qualification/ (JSON, YAML,
   TOML, hash manifest) names it; a mention in prose there is NOT an anchor;
3. a staying entry document (README.md, AGENTS.md, CLAUDE.md, docs/STUDIO_*.md,
   docs/OWNER_*.md, docs/CURRENT_EXECUTION_AUTHORITY.md, docs/CI_WHICH_CHECK_RUNS_WHEN.md,
   docs/claude/*.md, docs/README.md, data/**/README.md, .claude/**/*.md) links it.
   A history pointer in such a document is updated when the target moves.

Owner-decision / ADR / freeze documents, docs/archive/ and the current-handoff tree are never
moved.  This script and its test do not count as referencers.

Modes: default prints the plan; --json prints it as JSON; --inventory FILE writes a TSV of
every document under docs/; --links lists broken relative links in docs/; --apply performs
the git mv into docs/archive/<topic>/ and rewrites links in documents that stay; --check
exits 1 when an archivable entry is still outside docs/archive/ or when code references
anything inside docs/archive/.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = "docs"
ARCHIVE = "docs/archive"


# topic -> (what the topic holds, entry names).  An entry is a top-level name under docs/
# or the nested unit "claude/handoffs".  Each topic gets a README.md in docs/archive/<topic>/.
TOPICS: dict[str, tuple[str, tuple[str, ...]]] = {
    "opencode-foundry": (
        "Execution-authority documents of the removed OpenCode/Foundry tooling",
        (
            "COORDINATOR_EXECUTION_AUTHORITY_2026-09-27.md",
            "OPENAI_COORDINATOR_EXECUTION_AUTHORITY_2026-09-10.md",
        ),
    ),
    "tool-service-mcp": (
        "Usage of the removed tool service and its MCP/API servers",
        ("archetype_package_extraction.md",),
    ),
    "deck-optimizer-j-phases": (
        "The removed deck optimizer (whole_deck, optimization), its decision-quality policy "
        "records and the J-phase roadmap",
        (
            "optimizer-v2",
            "decision-quality",
            "decision_quality",
            "roadmap",
            "END_TO_END_WORKFLOW_EFFICIENCY.md",
            "NEXT_STEP_HANDOFF_J_P6_TO_FINAL.md",
        ),
    ),
    "mulligan-lab": ("The removed mulligan lab", ("mulligan_lab",)),
    "meta-store-primer": (
        "The removed meta knowledge base and primer compiler",
        ("meta", "META_KB_REFRESH_REPORT.md", "primer_to_pilot_compiler.md"),
    ),
    "structural-simulator": (
        "The removed structural simulator layer (counterfactual replay, diagnostics, structural "
        "estimates and their limits)",
        (
            "counterfactual",
            "diagnostics",
            "MODELING_IMPROVEMENT_REPORT.md",
            "PILOT_GOLDEN_SCENARIOS.md",
            "CARD_COVERAGE_CURRENT.md",
            "known_limitations.md",
            "validation_levels.md",
        ),
    ),
    "rogshai-campaigns": (
        "RogShai-only consolidation records (the optimisation campaigns are gone; RogShai "
        "regression data stays under data/)",
        ("FINAL_CONSOLIDATION_MANIFEST.json",),
    ),
    "audits-and-hygiene": (
        "Dated project audits, integrity and hygiene sweeps and status reports",
        (
            "AUDIT_POINT_E_BUG_REMEDIATION.md",
            "LIMITATION_REMEDIATION_REPORT.md",
            "POST_CLEANUP_INVENTORY.md",
            "POST_H_TECHNICAL_CONSOLIDATION.md",
            "PROJECT_STRUCTURE_FINAL_AUDIT.md",
            "TIME_BOMB_AUDIT_2026-10-30.md",
            "STATIC_ANALYSIS_2026-10-18.md",
            "1.20",
            "project_integrity_20260928",
            "project_integration_hygiene_20260927",
            "efficiency",
        ),
    ),
    "handoffs-and-reviews": (
        "Session handoffs, independent reviews and integration dispositions",
        (
            "claude/handoffs",
            "claude_independent_review_20260929",
            "muse_final_integration_20260928",
            "reconciliation",
        ),
    ),
    "prefreeze-campaigns": (
        "Finished pre-freeze evidence campaigns of the sealed qualification epoch",
        ("af07_actual_card_campaign_20261001",),
    ),
    "superseded": (
        "Guidance replaced by a later document or decision",
        (
            "PROJECT_UPDATE_CURRENT_STATE.md",
            "external_runtime_setup.md",
            "rules-engine-bridge-protocol.md",
        ),
    ),
}
TOPIC_OF = {name: topic for topic, (_d, names) in TOPICS.items() for name in names}
NESTED_UNITS = ("claude/handoffs",)

PROTECTED_NAME = re.compile(
    r"owner_decision|owner-decision|OWNER_DECISIONS|(^|[_/\-.])adr([_\-./0-9]|$)|freeze",
    re.IGNORECASE,
)
PROTECTED_ENTRY = re.compile(r"owner_decision|OWNER_DECISIONS|architecture_freeze", re.IGNORECASE)

# Staying entry documents (anchor 3); paths are repository-relative globs.
ENTRY_DOC_GLOBS = (
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/README.md",
    "docs/STUDIO_*.md",
    "docs/OWNER_*.md",
    "docs/CURRENT_EXECUTION_AUTHORITY.md",
    "docs/CI_WHICH_CHECK_RUNS_WHEN.md",
    "docs/claude/*.md",
    "docs/claude/state/*.md",
    "data/*/README.md",
    ".claude/**/*.md",
    ".github/*.md",
    ".clinerules/*.md",
)
# Records under these trees count as anchors only when machine-read.
SEALED_TREES = ("qualification/", "candidate-qualification/")
MACHINE_SUFFIXES = (".json", ".jsonl", ".yml", ".yaml", ".toml", ".sha256", ".txt")
# Never referencers: this tool and its test, and trees whose content is never read.
NOT_REFERENCERS = ("scripts/classify_docs.py", "tests/unit/test_docs_archive.py")
# data/collections is never read; the others are historical records, not readers.
SKIP_TREES = ("data/collections/", "research/", "handoffs/", "artifacts/")
# "docs/<name>" or pathlib style ("docs" / "<name>"): the second path component.
DOC_CHILD = re.compile(r"""docs["']?\s*[/,]\s*["']?([A-Za-z0-9_.\-]+)""")
WORD = re.compile(r"[A-Za-z0-9_.\-]+")
DOC_PATH = re.compile(r"docs/[A-Za-z0-9_./\-]+")
TEXT_LIMIT = 8_000_000
DOC_REF = re.compile(r"docs/archive/")
ARCHIVED_PATH = re.compile(r"docs/archive/[A-Za-z0-9_./\-]*")


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


def _is_entry_doc(f: str) -> bool:
    return any(fnmatch.fnmatchcase(f, g) for g in ENTRY_DOC_GLOBS)


def referencer_files(files: list[str]) -> list[str]:
    """Files whose references anchor a document (see the module docstring)."""
    refs = []
    for f in files:
        if f in NOT_REFERENCERS or f.startswith(SKIP_TREES) or f.startswith(ARCHIVE + "/"):
            continue
        if f.startswith(DOCS + "/"):
            if _is_entry_doc(f):
                refs.append(f)
        elif f.startswith(SEALED_TREES):
            if f.endswith(MACHINE_SUFFIXES) or "SHA256" in f:
                refs.append(f)
        elif not f.endswith(".md") or _is_entry_doc(f):
            refs.append(f)
    return refs


def entry_of(path: str) -> str | None:
    parts = path.split("/")
    if parts[0] != DOCS or len(parts) < 2 or parts[1] == "archive":
        return None
    for nested in NESTED_UNITS:
        if path.startswith(f"{DOCS}/{nested}/"):
            return nested
    return parts[1]


def entries(files: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in files:
        name = entry_of(f)
        if name is not None:
            out.setdefault(name, []).append(f)
    return out


def _anchors(files: list[str]) -> tuple[set[str], set[str], dict[str, int]]:
    words: set[str] = set()
    paths: set[str] = set()
    for f in referencer_files(files):
        text = ARCHIVED_PATH.sub(" ", _read(f))  # a pointer into the archive anchors nothing
        words.update(WORD.findall(text))
        paths.update(p.rstrip(".") for p in DOC_PATH.findall(text))
        paths.update(f"{DOCS}/{c}" for c in DOC_CHILD.findall(text))
    counts: dict[str, int] = {}
    for f in files:
        base = f.rsplit("/", 1)[-1]
        counts[base] = counts.get(base, 0) + 1
    return words, paths, counts


def _anchor_of(
    name: str, members: list[str], words: set[str], paths: set[str], counts
) -> str | None:
    if f"{DOCS}/{name}" in paths:
        return f"referenced path docs/{name}"
    for m in members:
        if m in paths:
            return f"referenced path {m}"
        base = m.rsplit("/", 1)[-1]
        if base != "README.md" and counts.get(base) == 1 and base in words:
            return f"referenced basename {base}"
    return None


def classify(files: list[str] | None = None) -> dict[str, object]:
    files = files if files is not None else _git_files()
    ents = entries(files)
    words, paths, counts = _anchors(files)
    archive: dict[str, str] = {}  # entry -> topic
    kept: dict[str, str] = {}  # entry -> reason (entries with a topic that stay)
    current: list[str] = []
    for name in sorted(ents):
        members = ents[name]
        topic = TOPIC_OF.get(name)
        if topic is None:
            current.append(name)
        elif PROTECTED_ENTRY.search(name) or any(
            PROTECTED_NAME.search(m.rsplit("/", 1)[1]) for m in members
        ):
            kept[name] = "owner decision / ADR / freeze"
        else:
            hit = _anchor_of(name, members, words, paths, counts)
            if hit:
                kept[name] = hit
            else:
                archive[name] = topic
    return {"archive": archive, "kept_anchored": kept, "current": current, "entries": ents}


def check(files: list[str] | None = None) -> list[str]:
    files = files if files is not None else _git_files()
    problems: list[str] = []
    plan = classify(files)
    for name, topic in plan["archive"].items():  # type: ignore[union-attr]
        problems.append(f"archivable doc outside archive: docs/{name} (topic {topic})")
    for f in referencer_files(files):
        if DOC_REF.search(_read(f)) and f not in _ARCHIVE_POINTERS:
            problems.append(f"code references docs/archive/: {f}")
    return problems


# Files that legitimately point at the archive as a location (navigation, not content).
_ARCHIVE_POINTERS = {
    ".gitattributes",  # byte-identity (-text) rules for archived sealed records
    "README.md",
    "docs/README.md",
    "data/provenance/claims.json",  # provenance claims cite archived reports by location
    "data/provenance/provenance_graph.json",
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


def apply_moves(plan: dict[str, str]) -> None:
    """git mv entries (name -> topic) into docs/archive/<topic>/ and fix links elsewhere.

    Moved documents are never edited (their bytes are history); relative links are rewritten
    only in documents that stay.
    """
    import os

    files = _git_files()
    moved = {n: f"{ARCHIVE}/{t}/{n}" for n, t in plan.items()}

    def new_of(rel: str) -> str:
        name = entry_of(rel)
        if name in moved:
            return moved[name] + rel[len(f"{DOCS}/{name}") :]
        return rel

    stay_md = [
        f
        for f in files
        if f.endswith(".md")
        and (f.startswith("docs/") or f == "README.md")
        and not f.startswith(ARCHIVE + "/")
        and new_of(f) == f
    ]
    edits: dict[str, str] = {}
    for f in stay_md:
        text = _read(f)
        base = (ROOT / f).parent

        def repl(m: re.Match[str], f: str = f, base: Path = base) -> str:
            sp = _split_target(m.group(3))
            if not sp or not sp[0]:
                return m.group(0)
            target = (base / sp[0]).resolve()
            if not target.exists():
                return m.group(0)
            rel_t = target.relative_to(ROOT).as_posix()
            new_t = new_of(rel_t)
            if new_t == rel_t:
                return m.group(0)
            new_rel = os.path.relpath(ROOT / new_t, base)
            if sp[0].endswith("/") and not new_rel.endswith("/"):
                new_rel += "/"
            return m.group(1) + m.group(2) + new_rel + sp[1]

        new_text = LINK.sub(repl, text)  # type: ignore[arg-type]
        if new_text != text:
            edits[f] = new_text
    for n, dest in moved.items():
        (ROOT / dest).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "mv", f"docs/{n}", dest], cwd=ROOT, check=True)
    for f, text in edits.items():
        (ROOT / f).write_text(text, encoding="utf-8")


def _last_modified() -> dict[str, str]:
    out = subprocess.run(
        ["git", "log", "--format=@%cs", "--name-only", "--", DOCS],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    seen: dict[str, str] = {}
    day = ""
    for line in out.splitlines():
        if line.startswith("@"):
            day = line[1:]
        elif line and line not in seen:
            seen[line] = day
    return seen


def inventory(path: str) -> int:
    """Write a TSV with one row per document under docs/ (archive excluded)."""
    files = _git_files()
    plan = classify(files)
    words, paths, counts = _anchors(files)
    modified = _last_modified()
    ents: dict[str, list[str]] = plan["entries"]  # type: ignore[assignment]
    rows = ["path\tlines\tlast_modified\tclass\tdescribes\tanchor\tdecision"]
    for name in sorted(ents):
        topic = TOPIC_OF.get(name)
        if name in plan["archive"]:  # type: ignore[operator]
            cls, decision = "archive", f"ARCHIVE({topic})"
        elif name in plan["kept_anchored"]:  # type: ignore[operator]
            cls, decision = "keep-anchored", "KEEP-ANCHORED"
        else:
            cls, decision = "current", "KEEP"
        describes = TOPICS[topic][0] if topic else "current"
        for m in ents[name]:
            text = _read(m)
            anchor = _anchor_of(name, [m], words, paths, counts) or ""
            rows.append(
                "\t".join(
                    [
                        m,
                        str(text.count("\n")),
                        modified.get(m, ""),
                        cls,
                        describes,
                        anchor or "",
                        decision,
                    ]
                )
            )
    Path(path).write_text("\n".join(rows) + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--links", action="store_true", help="list broken relative links in docs/")
    ap.add_argument("--apply", action="store_true", help="git mv archivable entries, fix links")
    ap.add_argument("--inventory", metavar="FILE", help="write the per-document TSV")
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
    if ns.inventory:
        return inventory(ns.inventory)
    plan = classify()
    if ns.apply:
        apply_moves(dict(plan["archive"]))  # type: ignore[arg-type]
        return 0
    summary = {"archive": plan["archive"], "kept_anchored": plan["kept_anchored"]}
    if ns.json:
        print(json.dumps(summary, indent=2))
    else:
        for n, t in plan["archive"].items():  # type: ignore[union-attr]
            print(f"{t}\t{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

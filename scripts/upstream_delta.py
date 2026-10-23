#!/usr/bin/env python3
"""Upstream delta check: what magefree/mage gained since the fork's last upstream merge.

Reads a checkout that holds both the fork pin and the upstream branch (``git fetch upstream``
in the fork checkout) and answers four questions without building anything:

1. Which upstream commits does the pin lack, split by what they touch (engine core, card
   classes, set registrations, tests, data, CI)?
2. Which card classes did they add or change, and which card names are those?
3. Which of those names are in the precon decks (named) or in the owner collection
   (counted only)? Which precon cards the engine still lacks are implemented upstream now?
4. Does a merge of upstream into the pin conflict (``git merge-tree``, no working tree)?
5. Do the new upstream lines add RNG calls or unordered collections (the determinism hazards
   behind earlier pod hash splits), and in which cards?
6. Did upstream change or remove a core method signature, and does a file the fork changed
   still call it (the silent compile break of a fork test after a merge)?

It measures; it never decides. A repin needs the Owner's go and a requalification
(``docs/claude/REPIN_RUNBOOK.md``); the report gives the numbers that go into that decision.

Usage:
    python3 scripts/upstream_delta.py --fork-checkout ~/mage [--upstream-ref upstream/master]
        [--pin <commit>] [--import-report imports.json] [--pull-requests-json prs.json]
        [--out report.json] [--markdown report.md]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).parent.parent
PRECON_DIR = REPO / "data" / "decks" / "precons"
COLLECTION_FILE = REPO / "data" / "collections" / "owner_collection_2026-10-12.txt"
RULES_ENGINES = REPO / "config" / "rules_engines.json"

CARD_DIR = "Mage.Sets/src/mage/cards/"
SET_DIR = "Mage.Sets/src/mage/sets/"
ENGINE_PREFIXES = ("Mage/src/main/", "Mage.Server/", "Mage.Server.Plugins/", "Mage.Common/")
KIND_ORDER = ("engine", "card", "set", "test", "verify", "data", "ci", "other")
ENGINE_COMMIT_LIST_LIMIT = 40
CORE_DIR = "Mage/src/main/"
SCAN_PATHS = (CORE_DIR, CARD_DIR)
LAB_BRIDGE_SRC = REPO / "engine-bridge" / "src"
CALLER_LIST_LIMIT = 8
RELEASE_VERSION_FLOOR = (1, 4, 62)
MAX_WEEKS_WITHOUT_UPSTREAM_MERGE = 6
UNBLOCKED_DECKS_THRESHOLD = 2
# Files that hold the engine's hot paths (copy, playable calculation, combat, effect layers).
HOT_FILES = (
    "Combat.java",
    "CombatGroup.java",
    "ContinuousEffects.java",
    "GameState.java",
    "GameImpl.java",
    "PlayerImpl.java",
)
HAZARD_PATTERNS = {
    "rng": re.compile(r"RandomUtil|new Random|Math\.random|Collections\.shuffle"),
    "unordered": re.compile(r"new HashSet|new HashMap|toSet\(\)"),
}

_RECORD = "\x1e"
_FIELD = "\x1f"
_SET_CARD_INFO = re.compile(
    r'SetCardInfo\("((?:[^"\\]|\\.)*)",\s*[^,]+,\s*Rarity\.\w+,\s*mage\.cards\.\w+\.(\w+)\.class'
)
_CARD_CLASS = re.compile(r"^Mage\.Sets/src/mage/cards/([a-z0-9])/(\w+)\.java$")
_MODIFIERS = r"(?:(?:public|protected|private|static|final|abstract|default|synchronized)\s+)"
_DECLARATION = re.compile(
    rf"^(?P<indent>\s*)(?:@\w+(?:\([^)]*\))?\s+)*(?P<mods>{_MODIFIERS}+)?"
    r"(?:<[^>]+>\s+)?(?:(?P<type>[\w<>\[\],.? ]+?)\s+)?(?P<name>\w+)\s*\((?P<params>[^)]*)\)"
    r"(?P<tail>\s*(?:throws [\w., ]+)?\s*[{;]?)\s*$"
)
_NOT_A_DECLARATION = ("return", "throw", "new", "else", "if", "for", "while", "switch", "case")


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", "-C", str(repo), *args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


def classify_path(path: str) -> str:
    if path.startswith(CARD_DIR):
        return "card"
    if path.startswith(SET_DIR):
        return "set"
    if path.startswith("Mage.Tests/"):
        return "test"
    if path.startswith("Mage.Verify/"):
        return "verify"
    if path.startswith("Utils/") or path.endswith("mtg-cards-data.txt"):
        return "data"
    if path.startswith(".github/"):
        return "ci"
    if path.startswith(ENGINE_PREFIXES):
        return "engine"
    return "other"


def commit_kinds(files: list[str]) -> list[str]:
    kinds = {classify_path(path) for path in files}
    return [kind for kind in KIND_ORDER if kind in kinds]


def parse_log(text: str) -> list[dict[str, Any]]:
    """Parse ``git log --name-only`` output written with the record and field separators."""
    commits: list[dict[str, Any]] = []
    for record in text.split(_RECORD):
        if not record.strip():
            continue
        head, _, tail = record.partition("\n")
        sha, date, author, subject = [*head.split(_FIELD), "", "", "", ""][:4]
        files = [line for line in tail.splitlines() if line.strip()]
        commits.append(
            {
                "sha": sha,
                "date": date,
                "author": author,
                "subject": subject,
                "files": files,
                "kinds": commit_kinds(files),
            }
        )
    return commits


def commits_between(repo: Path, base: str, upstream: str) -> list[dict[str, Any]]:
    fmt = f"{_RECORD}%H{_FIELD}%cs{_FIELD}%an{_FIELD}%s"
    out = git(repo, "log", "--no-merges", "--name-only", f"--format={fmt}", f"{base}..{upstream}")
    return parse_log(out.stdout)


def card_class_changes(repo: Path, base: str, upstream: str) -> dict[str, str]:
    """Card class name -> ``added`` / ``modified`` / ``deleted`` between the two trees."""
    out = git(repo, "diff", "--name-status", "--no-renames", base, upstream, "--", CARD_DIR)
    changes: dict[str, str] = {}
    labels = {"A": "added", "M": "modified", "D": "deleted"}
    for line in out.stdout.splitlines():
        status, _, path = line.partition("\t")
        match = _CARD_CLASS.match(path)
        if match and status[:1] in labels:
            changes[match.group(2)] = labels[status[:1]]
    return changes


def registrations(text: str) -> Iterator[tuple[str, str]]:
    """``(card name, class)`` of each live ``SetCardInfo`` line; a commented-out one (the set
    keeps those for cards it does not implement yet) is not a registration."""
    for line in text.splitlines():
        if line.lstrip().startswith("//"):
            continue
        for card, cls in _SET_CARD_INFO.findall(line):
            yield card.replace('\\"', '"'), cls


def card_names_for_classes(repo: Path, ref: str, classes: list[str]) -> dict[str, str]:
    """Class name -> card name, from the ``SetCardInfo`` registrations at ``ref``."""
    if not classes:
        return {}
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        handle.write("".join(f".{name}.class\n" for name in sorted(classes)))
        patterns = handle.name
    try:
        out = git(repo, "grep", "-h", "-F", "-f", patterns, ref, "--", SET_DIR, check=False)
    finally:
        Path(patterns).unlink(missing_ok=True)
    wanted = set(classes)
    names: dict[str, str] = {}
    for card, cls in registrations(out.stdout):
        if cls in wanted:
            names.setdefault(cls, card)
    return names


def fold(name: str) -> str:
    """Accent-free form: the engine registers ``Lothlorien Blade`` where Scryfall says ``Lothlórien``."""
    decomposed = unicodedata.normalize("NFKD", name)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def registered_names(repo: Path, ref: str, cards: list[str]) -> set[str]:
    """The subset of ``cards`` that has a ``SetCardInfo`` registration at ``ref`` (one pass).

    Names are compared without accents, and a split or double-faced name matches by its
    front face on either side.
    """
    if not cards:
        return set()
    out = git(repo, "grep", "-h", "-F", 'SetCardInfo("', ref, "--", SET_DIR, check=False)
    found: set[str] = set()
    for name, _cls in registrations(out.stdout):
        found |= {fold(name), fold(front_face(name))}
    return {card for card in cards if fold(card) in found or fold(front_face(card)) in found}


def front_face(name: str) -> str:
    return name.split(" // ")[0].strip()


def deck_cards(deck_dir: Path) -> dict[str, list[str]]:
    """Front-face card name -> decks (file stems) that hold it."""
    held: dict[str, list[str]] = {}
    for path in sorted(deck_dir.glob("*.json")):
        deck = json.loads(path.read_text(encoding="utf-8"))
        names = {entry.get("oracle_name") or entry.get("name") for entry in deck.get("cards", [])}
        names |= set(deck.get("commander", {}).get("commanders", []))
        for name in names:
            if name:
                held.setdefault(front_face(name), []).append(path.stem)
    return held


def collection_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        front_face(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    }


def missing_precon_names(report: dict[str, Any]) -> dict[str, list[str]]:
    """Card the engine lacks -> decks that need it, from a ``measure_precon_imports`` report."""
    missing: dict[str, list[str]] = {}
    for row in report.get("results", []):
        for entry in row.get("missing_cards", []):
            missing.setdefault(entry["card"], []).append(row["deck"])
    return missing


def merge_conflicts(repo: Path, pin: str, upstream: str) -> dict[str, Any]:
    """Dry-run of ``git merge upstream`` into ``pin`` (object database only)."""
    out = git(repo, "merge-tree", "--write-tree", "--name-only", pin, upstream, check=False)
    lines = out.stdout.splitlines()
    if out.returncode == 0:
        return {"status": "CLEAN", "conflicted_files": []}
    if out.returncode != 1 or not lines:
        return {
            "status": "UNKNOWN",
            "error": (out.stderr or out.stdout)[:300],
            "conflicted_files": [],
        }
    files: list[str] = []
    for line in lines[1:]:
        if not line.strip():
            break
        files.append(line.strip())
    return {"status": "CONFLICTS", "conflicted_files": files}


def _parameter_types(params: str) -> str:
    """``Game game, Map<A, B> m`` -> ``Game,Map<A,B>``: types only, so a parameter rename is not a change."""
    parts: list[str] = []
    depth = 0
    current = ""
    for char in params:
        depth += (char == "<") - (char == ">")
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    parts.append(current)
    types = []
    for part in parts:
        part = re.sub(r"@\w+(?:\([^)]*\))?\s*", "", part).replace("final ", "").strip()
        if part:
            types.append(re.sub(r"\s+", "", re.sub(r"\s+\w+$", "", part)))
    return ",".join(types)


def parse_declaration(line: str) -> tuple[str, str] | None:
    """``(name, parameter types)`` when a single diff line looks like a member declaration.

    A heuristic on one line: a declaration with a modifier, or a typed one at member
    indentation that ends in ``{`` or ``;`` (interface methods). A parameter list that runs over
    several lines is not seen.
    """
    match = _DECLARATION.match(line)
    if match is None:
        return None
    name = match.group("name")
    declared_type = match.group("type")
    if (declared_type or name).split()[0] in _NOT_A_DECLARATION:
        return None
    if not match.group("mods"):
        member_level = match.group("indent") in ("    ", "\t")
        ends_declaration = match.group("tail").strip()[-1:] in ("{", ";")
        if not (declared_type and member_level and ends_declaration):
            return None
    return name, _parameter_types(match.group("params"))


def scan_diff(repo: Path, base: str, upstream: str) -> dict[str, list[dict[str, Any]]]:
    """Added hazard lines (core and cards) and changed or removed core signatures."""
    out = git(repo, "diff", "-U0", "--no-renames", base, upstream, "--", *SCAN_PATHS)
    hazards: list[dict[str, Any]] = []
    removed: dict[str, list[tuple[str, str]]] = {}
    added: dict[str, list[tuple[str, str]]] = {}
    current = ""
    in_hunk = False
    for line in out.stdout.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
        elif line.startswith("@@"):
            in_hunk = True
        elif not in_hunk:
            # ``--- a/X`` names a deleted file too; ``+++ /dev/null`` must not overwrite it.
            if line.startswith(("--- a/", "+++ b/")):
                current = line[6:]
        elif line[:1] in ("+", "-"):
            text = line[1:]
            is_core = current.startswith(CORE_DIR)
            if line[0] == "+":
                for category, pattern in HAZARD_PATTERNS.items():
                    if pattern.search(text):
                        hazards.append(
                            {"file": current, "category": category, "line": text.strip()[:160]}
                        )
            declaration = parse_declaration(text) if is_core else None
            if declaration:
                (added if line[0] == "+" else removed).setdefault(current, []).append(declaration)

    signatures: list[dict[str, Any]] = []
    for path, olds in sorted(removed.items()):
        news = added.get(path, [])
        by_name: dict[str, set[str]] = {}
        for name, params in news:
            by_name.setdefault(name, set()).add(params)
        for name, params in dict.fromkeys(olds):
            if (name, params) in news:
                continue
            signatures.append(
                {
                    "file": path,
                    "name": name,
                    "kind": "changed" if name in by_name else "removed",
                    "old_parameters": params,
                    "new_parameters": sorted(by_name.get(name, ())),
                }
            )
    return {"hazards": hazards, "signature_changes": signatures}


def changed_files(repo: Path, left: str, right: str) -> set[str]:
    out = git(repo, "diff", "--name-only", "--no-renames", left, right)
    return {line for line in out.stdout.splitlines() if line.strip()}


def fork_callers(
    repo: Path,
    pin: str,
    fork_files: set[str],
    signatures: list[dict[str, Any]],
    lab_sources: Path | None = None,
) -> None:
    """Add ``fork_callers`` to each signature: files the fork changed (and the lab bridge)
    that still mention the method name, i.e. that may no longer compile after a merge."""
    lab_texts: dict[str, str] = {}
    if lab_sources is not None and lab_sources.is_dir():
        for path in sorted(lab_sources.rglob("*.java")):
            label = f"{lab_sources.parent.name}/{path.relative_to(lab_sources.parent)}"
            lab_texts[label] = path.read_text(encoding="utf-8", errors="replace")
    cache: dict[str, set[str]] = {}
    for sig in signatures:
        name = sig["name"]
        if name not in cache:
            out = git(repo, "grep", "-l", "-F", "-e", f"{name}(", pin, "--", "*.java", check=False)
            cache[name] = {line.partition(":")[2] for line in out.stdout.splitlines()}
        callers = sorted((cache[name] & fork_files) - {sig["file"]})
        callers += [label for label, text in lab_texts.items() if f"{name}(" in text]
        sig["fork_callers"] = callers


def pom_version(repo: Path, ref: str) -> tuple[int, ...]:
    out = git(repo, "show", f"{ref}:pom.xml", check=False)
    match = re.search(r"<version>(\d+(?:\.\d+)*)", out.stdout)
    return tuple(int(part) for part in match.group(1).split(".")) if match else ()


def evaluate_triggers(
    repo: Path,
    upstream: str,
    base: str,
    report: dict[str, Any],
    missing: dict[str, list[str]],
    gained: set[str],
    today: date,
) -> dict[str, dict[str, str]]:
    """The roadmap's repin triggers T1-T6 as far as a script can read them.

    ``MET`` and ``NOT_MET`` are measured; ``REVIEW`` means the listed items need a human read;
    ``OWNER`` is not in the repository (T4, the fork's own need). A repin still needs the
    Owner's go whatever this says.
    """
    engine = report["engine_commits"]
    decks_with_gaps = {deck for decks in missing.values() for deck in decks}
    unblocked = sorted(
        deck
        for deck in decks_with_gaps
        if all(card in gained for card, decks in missing.items() if deck in decks)
    )
    core_conflicts = [f for f in report["merge"]["conflicted_files"] if f.startswith(CORE_DIR)]
    hot = sorted(
        {
            path.rsplit("/", 1)[-1]
            for commit in engine
            for path in commit["files"]
            if path.rsplit("/", 1)[-1] in HOT_FILES
        }
    )
    version = pom_version(repo, upstream)
    base_date = date.fromisoformat(git(repo, "show", "-s", "--format=%cs", base).stdout.strip())
    weeks = (today - base_date).days // 7
    precon_card_hits = len(report["changed_cards_in_precons"])
    return {
        "T1 rule fix touching the lab": {
            "status": "REVIEW" if engine else "NOT_MET",
            "detail": f"{len(engine)} engine commits, {precon_card_hits} changed card classes "
            "are in precon decks; read the commits against the deck lists",
        },
        "T2 release 1.4.63 or POM above 1.4.62": {
            "status": "MET" if version > RELEASE_VERSION_FLOOR else "NOT_MET",
            "detail": f"upstream POM {'.'.join(map(str, version)) or 'unreadable'}",
        },
        f"T3 at least {UNBLOCKED_DECKS_THRESHOLD} blocked decks become importable": {
            "status": "MET" if len(unblocked) >= UNBLOCKED_DECKS_THRESHOLD else "NOT_MET",
            "detail": f"{len(decks_with_gaps)} decks lack a card at the pin, "
            f"{len(unblocked)} would be complete with upstream's registrations",
        },
        "T4 the fork's own need": {
            "status": "OWNER",
            "detail": "fork patch backlog or an engine bug only the fork can fix; not in the repo",
        },
        "T5 conflict pressure on core": {
            "status": "MET" if core_conflicts else ("REVIEW" if hot else "NOT_MET"),
            "detail": f"{len(core_conflicts)} core conflict files; hot files changed upstream: "
            f"{', '.join(hot) or 'none'}",
        },
        f"T6 more than {MAX_WEEKS_WITHOUT_UPSTREAM_MERGE} weeks since the last merge": {
            "status": "MET" if weeks > MAX_WEEKS_WITHOUT_UPSTREAM_MERGE else "NOT_MET",
            "detail": f"merge base {base_date.isoformat()}, {weeks} weeks before {today.isoformat()}",
        },
    }


def pin_from_config() -> str:
    data = json.loads(RULES_ENGINES.read_text(encoding="utf-8"))
    return str(data["primary_engine"]["commit"])


def build_report(
    repo: Path,
    pin: str,
    upstream_ref: str,
    precon_dir: Path = PRECON_DIR,
    collection_file: Path = COLLECTION_FILE,
    import_report: dict[str, Any] | None = None,
    pull_requests: dict[str, dict[str, Any]] | None = None,
    lab_sources: Path | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    pin_full = git(repo, "rev-parse", "--verify", f"{pin}^{{commit}}").stdout.strip()
    upstream_full = git(repo, "rev-parse", "--verify", f"{upstream_ref}^{{commit}}").stdout.strip()
    base = git(repo, "merge-base", pin_full, upstream_full).stdout.strip()
    commits = commits_between(repo, base, upstream_full)

    kinds: Counter[str] = Counter()
    for commit in commits:
        for kind in commit["kinds"]:
            kinds[kind] += 1

    changes = card_class_changes(repo, base, upstream_full)
    names = card_names_for_classes(
        repo, upstream_full, [c for c, s in changes.items() if s != "deleted"]
    )
    held = deck_cards(precon_dir)
    owned = collection_names(collection_file)

    changed_cards = []
    in_collection = 0  # a count only: which cards the Owner holds never goes into a report
    for cls, status in sorted(changes.items()):
        name = names.get(cls)
        in_collection += bool(name and front_face(name) in owned)
        changed_cards.append(
            {
                "class": cls,
                "status": status,
                "name": name,
                "precon_decks": held.get(front_face(name), []) if name else [],
            }
        )

    scan = scan_diff(repo, base, upstream_full)
    by_class = {c["class"]: c for c in changed_cards}
    for hazard in scan["hazards"]:
        match = _CARD_CLASS.match(hazard["file"])
        card = by_class.get(match.group(2)) if match else None
        hazard["card"] = card["name"] if card else None
        hazard["precon_decks"] = card["precon_decks"] if card else []
    signatures = scan["signature_changes"]
    fork_callers(repo, pin_full, changed_files(repo, base, pin_full), signatures, lab_sources)

    # Cards the pin lacks: the importer's own list when given, else every precon card
    # without a registration at the pin (no JVM needed).
    if import_report is not None:
        missing = missing_precon_names(import_report)
        pin_has = registered_names(repo, pin_full, list(missing))
    else:
        pin_has = registered_names(repo, pin_full, list(held))
        missing = {card: decks for card, decks in held.items() if card not in pin_has}
    upstream_has = registered_names(repo, upstream_full, list(missing))
    gained = {card for card in missing if card in upstream_has and card not in pin_has}
    now_implemented = [
        {"name": card, "decks": decks} for card, decks in sorted(missing.items()) if card in gained
    ]

    engine_commits = [c for c in commits if "engine" in c["kinds"]]
    report = {
        "pin": pin_full,
        "upstream_ref": upstream_ref,
        "upstream_head": upstream_full,
        "merge_base": base,
        "commits_total": len(commits),
        "commits_by_kind": {kind: kinds[kind] for kind in KIND_ORDER if kinds[kind]},
        "engine_commits": [
            {k: c[k] for k in ("sha", "date", "subject", "files")} for c in engine_commits
        ],
        "card_classes": {
            "added": sum(1 for c in changed_cards if c["status"] == "added"),
            "modified": sum(1 for c in changed_cards if c["status"] == "modified"),
            "deleted": sum(1 for c in changed_cards if c["status"] == "deleted"),
            "name_unresolved": sum(
                1 for c in changed_cards if c["status"] != "deleted" and not c["name"]
            ),
        },
        "changed_cards": changed_cards,
        "changed_cards_in_precons": [c for c in changed_cards if c["precon_decks"]],
        "changed_cards_in_collection": in_collection,
        "hazards": scan["hazards"],
        "hazards_in_precons": [h for h in scan["hazards"] if h["precon_decks"]],
        "signature_changes": signatures,
        "signature_changes_with_fork_callers": [s for s in signatures if s["fork_callers"]],
        "missing_precon_cards_source": "import report" if import_report else "registry at the pin",
        "missing_precon_cards_total": len(missing),
        "missing_precon_cards_now_implemented": now_implemented,
        "missing_precon_cards_with_pull_request": [
            {"name": card, "decks": decks, "pull_request": (pull_requests or {})[card]}
            for card, decks in sorted(missing.items())
            if card in (pull_requests or {})
        ],
        "merge": merge_conflicts(repo, pin_full, upstream_full),
        "commits": [
            {k: c[k] for k in ("sha", "date", "author", "subject", "kinds")} for c in commits
        ],
    }
    report["triggers"] = evaluate_triggers(
        repo, upstream_full, base, report, missing, gained, today or date.today()
    )
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"Upstream `{report['upstream_ref']}` at `{report['upstream_head'][:8]}`, pin `{report['pin'][:8]}`, "
        f"merge base `{report['merge_base'][:8]}`: {report['commits_total']} commits the pin lacks.",
        "",
        "| Touches | Commits |",
        "|---|---:|",
    ]
    lines += [f"| {kind} | {count} |" for kind, count in report["commits_by_kind"].items()]
    classes = report["card_classes"]
    lines += [
        "",
        f"Card classes: {classes['added']} added, {classes['modified']} modified, "
        f"{classes['deleted']} deleted ({classes['name_unresolved']} without a registered name). "
        f"In precon decks: {len(report['changed_cards_in_precons'])}; "
        f"in the owner collection: {report['changed_cards_in_collection']} (count only).",
        f"Merge into the pin: **{report['merge']['status']}**"
        + (
            f" ({len(report['merge']['conflicted_files'])} files)"
            if report["merge"]["conflicted_files"]
            else ""
        ),
    ]
    lines += ["", "| Repin trigger | Status | Detail |", "|---|---|---|"]
    lines += [
        f"| {name} | {row['status']} | {row['detail']} |"
        for name, row in report["triggers"].items()
    ]
    hazards = report["hazards"]
    by_category = Counter(h["category"] for h in hazards)
    lines += [
        "",
        f"Determinism hazards in new upstream lines: {by_category['rng']} RNG, "
        f"{by_category['unordered']} unordered collection; cards among them in precon decks: "
        f"{len({h['card'] for h in report['hazards_in_precons']})}.",
    ]
    for hazard in hazards:
        marker = f" [precon: {', '.join(hazard['precon_decks'])}]" if hazard["precon_decks"] else ""
        lines.append(f"- {hazard['category']} `{hazard['file'].rsplit('/', 1)[-1]}`{marker}")
    signatures = report["signature_changes"]
    hitting = report["signature_changes_with_fork_callers"]
    lines += [
        "",
        f"Core signatures changed or removed upstream: {len(signatures)}; "
        f"still called from files the fork changed or the lab bridge: {len(hitting)}.",
    ]
    for sig in signatures:
        callers = sig["fork_callers"]
        shown = ", ".join(c.rsplit("/", 1)[-1] for c in callers[:CALLER_LIST_LIMIT])
        more = f" (+{len(callers) - CALLER_LIST_LIMIT})" if len(callers) > CALLER_LIST_LIMIT else ""
        now = " / ".join(f"({params})" for params in sig["new_parameters"])
        lines.append(
            f"- {sig['kind']} `{sig['name']}({sig['old_parameters']})`"
            + (f" to `{now}`" if now else "")
            + f" in `{sig['file'].rsplit('/', 1)[-1]}`"
            + (f"; name also used in {shown}{more}" if callers else "")
        )
    implemented = report["missing_precon_cards_now_implemented"]
    if implemented is not None:
        lines += [
            "",
            f"Precon cards the engine lacks: {report['missing_precon_cards_total']}; "
            f"upstream now implements {len(implemented)}; "
            f"{len(report['missing_precon_cards_with_pull_request'])} have an upstream PR on record.",
        ]
        lines += [f"- {item['name']} ({', '.join(item['decks'])})" for item in implemented]
    if report["engine_commits"]:
        lines += ["", "Engine-core commits:"]
        for commit in report["engine_commits"][:ENGINE_COMMIT_LIST_LIMIT]:
            lines.append(f"- `{commit['sha'][:10]}` {commit['date']} {commit['subject']}")
    precon_hits = report["changed_cards_in_precons"]
    if precon_hits:
        lines += ["", "Changed card classes that are in precon decks:"]
        for card in precon_hits:
            lines.append(f"- {card['name']} ({card['status']}): {', '.join(card['precon_decks'])}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fork-checkout", type=Path, required=True)
    parser.add_argument("--upstream-ref", default="upstream/master")
    parser.add_argument("--pin", default=None, help="default: primary_engine.commit of the config")
    parser.add_argument("--import-report", type=Path, default=None)
    parser.add_argument(
        "--pull-requests-json",
        type=Path,
        default=None,
        help='{"<card>": {"number": N, "state": "open"}}: upstream PR status per missing card',
    )
    parser.add_argument("--precon-dir", type=Path, default=PRECON_DIR)
    parser.add_argument("--collection-file", type=Path, default=COLLECTION_FILE)
    parser.add_argument("--lab-sources", type=Path, default=LAB_BRIDGE_SRC)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--markdown", type=Path, default=None)
    args = parser.parse_args()

    report_in = (
        json.loads(args.import_report.read_text(encoding="utf-8")) if args.import_report else None
    )
    pull_requests = (
        json.loads(args.pull_requests_json.read_text(encoding="utf-8"))
        if args.pull_requests_json
        else None
    )
    try:
        report = build_report(
            args.fork_checkout,
            args.pin or pin_from_config(),
            args.upstream_ref,
            precon_dir=args.precon_dir,
            collection_file=args.collection_file,
            import_report=report_in,
            pull_requests=pull_requests,
            lab_sources=args.lab_sources,
        )
    except subprocess.CalledProcessError as exc:
        print(f"git failed: {exc.stderr.strip()[:300]}", file=sys.stderr)
        return 2
    text = render_markdown(report)
    print(text)
    if args.out:
        args.out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if args.markdown:
        args.markdown.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

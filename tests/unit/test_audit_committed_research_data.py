"""Unit tests for the committed research data consistency audit."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest
from scripts.audit_committed_research_data import main, run_audit

MAX_RESEARCH_FILE_BYTES = 3 * 1024 * 1024  # 3 MiB ceiling (blocks 4 MB+ dumps under data/research/)
_BYTECODE_SUFFIXES = frozenset({".pyc", ".pyo"})
_MODEL_VENDOR_RE = re.compile(
    r"(?<![A-Za-z0-9])("
    r"claude|sonnet|haiku|anthropic|"
    r"opus[\s_-]?(?:[0-9][0-9a-z.]*|rater|review|stufe|modell|model)|"
    r"(?:rater|model|modell|stufe|tier|review)[^\n]{0,24}(?<![A-Za-z0-9])opus|"
    r"openai|gpt[\s_-]?[0-9][0-9a-z.]*|chatgpt|"
    r"o[134](?:-(?:mini|pro|preview))?|"
    r"gemini|deepseek|llama[\s_-]?[0-9][0-9a-z.]*|mistral|qwen|grok|copilot|codex"
    r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def _is_bytecode_cache(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix in _BYTECODE_SUFFIXES


def _iter_committed_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*"))
        if not _is_bytecode_cache(path) and (path.is_file() or path.is_symlink())
    ]


def _oversized_research_files(
    root: Path, limit_bytes: int = MAX_RESEARCH_FILE_BYTES
) -> list[tuple[str, int]]:
    hits: list[tuple[str, int]] = []
    for path in _iter_committed_files(root):
        if path.is_symlink():
            hits.append((path.relative_to(root).as_posix(), -1))
            continue
        size = path.stat().st_size
        if size > limit_bytes:
            hits.append((path.relative_to(root).as_posix(), size))
    return hits


def _find_model_vendor_mentions(paths: list[Path]) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for path in sorted(paths):
        if _is_bytecode_cache(path):
            continue
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in _MODEL_VENDOR_RE.finditer(line):
                hits.append((path.as_posix(), line_no, match.group(0)))
    return hits


def test_card_global_signals_csv_has_no_price_columns() -> None:
    csv_path = Path("data/research/deckbuilder_1655/card_global_signals.csv")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    assert fieldnames == [
        "card_name",
        "card_slug",
        "fetch_status",
        "num_decks",
        "potential_decks",
        "inclusion_share",
        "salt",
        "rarity",
        "source_file",
    ]
    assert all("price" not in col.lower() for col in fieldnames)
    assert len(rows) == 1655


def test_run_audit_against_repo() -> None:
    repo_root = Path(".")
    rows, markdown_text = run_audit(repo_root)

    assert len(rows) == 9
    results_by_check = {r.check_name: r for r in rows}

    # 1.1 Parseability
    assert results_by_check["1.1 Parsebarkeit der 5 Datendateien"].result == "OK"
    assert results_by_check["1.1 Parsebarkeit der 5 Datendateien"].count == 0

    # 2.1 Gap matrix vs PCK (gap closed by the full public catalog, Refs #1227)
    r21 = results_by_check["2.1 Gap-Matrix-Karten ohne Eintrag in pilot_card_knowledge"]
    assert r21.result == "OK"
    assert r21.count == 0

    # 2.2 Inclusion CSV vs Gap Matrix
    r22 = results_by_check[
        "2.2 Inclusion-CSV-Karten ohne Gap-Matrix-Eintrag (Universum vs. Chulane-Pool)"
    ]
    assert r22.result == "ABWEICHUNG"
    assert r22.count == 6084
    assert "- **Betroffene Karten (6084, alphabetisch sortiert):**" in markdown_text

    # Count emitted card list entries directly between 2.2 heading and 2.3 heading
    sec22_start = markdown_text.index("### 2.2 Inclusion-CSV-Karten ohne Gap-Matrix-Eintrag")
    sec23_start = markdown_text.index("### 2.3 Dubletten je Datei")
    sec22_block = markdown_text[sec22_start:sec23_start]
    emitted_names = [
        line.removeprefix("  * `").removesuffix("`")
        for line in sec22_block.splitlines()
        if line.startswith("  * `")
    ]
    assert len(emitted_names) == 6084
    assert len(set(emitted_names)) == 6084
    assert emitted_names == sorted(emitted_names)

    # 2.3 Duplicates
    assert results_by_check["2.3 Dubletten je Datei"].result == "OK"
    assert results_by_check["2.3 Dubletten je Datei"].count == 0

    # 3.1 Constant cohort denominators
    assert results_by_check["3.1 Inclusion-CSV: Kohorten-Nenner konstant"].result == "OK"
    assert results_by_check["3.1 Inclusion-CSV: Kohorten-Nenner konstant"].count == 0

    # 3.2 Value ranges
    r32 = results_by_check[
        "3.2 Inclusion-CSV: Wertebereiche (0 <= decks <= universe_decks; 0.0 <= share <= 1.0)"
    ]
    assert r32.result == "OK"
    assert r32.count == 0

    # 3.3 Empty fields
    assert results_by_check["3.3 Inclusion-CSV: Leere Pflichtfelder"].result == "OK"
    assert results_by_check["3.3 Inclusion-CSV: Leere Pflichtfelder"].count == 0

    # 3.4 Summary counts
    assert results_by_check["3.4 Gap-Matrix: summary_counts Nachrechnung"].result == "OK"
    assert results_by_check["3.4 Gap-Matrix: summary_counts Nachrechnung"].count == 0

    # 4.1 Game Changer vs Banned
    r41 = results_by_check["4.1 commander_flags.json: Game Changer vs. Banned Überschneidung"]
    assert r41.result == "OK"
    assert r41.count == 0

    # Markdown checks
    assert "# Daten-Konsistenz-Audit der committed Research- und Kartendaten" in markdown_text
    assert (
        "| 2.1 Gap-Matrix-Karten ohne Eintrag in pilot_card_knowledge | OK | 0 |" in markdown_text
    )
    assert "Gesamt-Tabelle aller Prüfungen" in markdown_text


def test_main_cli_execution(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_file = tmp_path / "test_audit.md"
    ret = main(["--repo-root", ".", "--out", str(out_file)])
    assert ret == 0
    assert out_file.is_file()
    captured = capsys.readouterr().out
    assert "Wrote audit report to" in captured


def test_committed_research_data_files_stay_within_size_limit() -> None:
    """#1745 (#1768 P3-2): no single file under ``data/research/`` may exceed 3 MiB."""
    root = Path("data/research")
    files = _iter_committed_files(root)
    assert len(files) >= 10
    assert _oversized_research_files(root) == []


def test_oversized_research_file_is_caught_by_size_guard(tmp_path: Path) -> None:
    """Negative control: a 4 MiB file under ``data/research/`` is flagged; ``__pycache__`` ignored."""
    root = tmp_path / "data" / "research"
    pycache = root / "__pycache__"
    pycache.mkdir(parents=True)
    (root / "ok.json").write_bytes(b"{}\n")
    big_size = 4 * 1024 * 1024
    (pycache / "mod.cpython-312.pyc").write_bytes(b"\xcb\x0d\x0d\x0a" + b"\xff" * big_size)
    (root / "too_large.bin").write_bytes(b"x" * big_size)
    assert _oversized_research_files(root) == [("too_large.bin", big_size)]


def test_rating_v3_plan_and_scripts_contain_no_model_or_vendor_names() -> None:
    """#1745 (#1768 P3-2, AGENTS.md §12): rating-v3 plan, reports and scripts stay neutral."""
    v3_docs = sorted(Path("docs/analysis-reports").glob("rating_v3_*.md"))
    v3_scripts = sorted(Path("scripts/analysis").glob("rating_v3_*.py"))
    v3_data_dirs = sorted(
        path for path in Path("data/research").glob("chulane_rubric_v3_*") if path.is_dir()
    )
    v3_data_files = [
        path for directory in v3_data_dirs for path in _iter_committed_files(directory)
    ]
    assert len(v3_docs) >= 1
    assert len(v3_scripts) >= 1
    assert len(v3_data_files) >= 1
    assert _find_model_vendor_mentions([*v3_docs, *v3_scripts, *v3_data_files]) == []


def test_model_vendor_guard_catches_leaks_and_ignores_bytecode_and_mtg_opus(tmp_path: Path) -> None:
    """Negative control: model/rater/snake_case leaks are caught; bytecode and MTG Opus pass."""
    sample = tmp_path / "plan.md"
    sample.write_text(
        "Rater A = Opus\n"
        "Rater B = GPT 4 / o4-mini\n"
        "claude_sonnet = 'bad'\n"
        "Version: Opus 4.5 and GPT-4o\n"
        "Ability word: Opus — whenever you cast an instant or sorcery spell.\n",
        encoding="utf-8",
    )
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    pyc = pycache / "extract_facts_v2.cpython-312.pyc"
    pyc.write_bytes(b"\xcb\x0d\x0d\x0a\x00\x00\x00\x00\xff\xfe")

    hits = _find_model_vendor_mentions([sample, pyc])
    assert [(line_no, token.lower()) for _path, line_no, token in hits] == [
        (1, "rater a = opus"),
        (2, "gpt 4"),
        (2, "o4-mini"),
        (3, "claude"),
        (3, "sonnet"),
        (4, "opus 4.5"),
        (4, "gpt-4o"),
    ]

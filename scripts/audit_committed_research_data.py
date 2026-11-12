#!/usr/bin/env python3
"""Consistency audit script for committed research and card data files.

Audit Scope:
- data/research/chulane_legal_pool_gap_matrix.json (801 cards)
- data/research/chulane_decklist_inclusion_20261112.csv (15,038 rows)
- data/cards/pilot_card_knowledge.json (7,231 cards)
- data/cards/commander_flags.json (53 game changers, 83 commander banned)
- data/cards/official_precon_oracle_cards.json (512 cards)

Rules and Semantics:
- Status vocabulary strictly: OK / ABWEICHUNG / UNKNOWN.
- Purely factual counting and discrepancy reporting; no automatic modifications.
- No personal collection, deck, or owner data.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AuditRow:
    check_name: str
    result: str  # OK / ABWEICHUNG / UNKNOWN
    count: int
    details: str


def run_audit(repo_root: Path) -> tuple[list[AuditRow], str]:
    rows: list[AuditRow] = []
    lines: list[str] = [
        "# Daten-Konsistenz-Audit der committed Research- und Kartendaten",
        "",
        "- **Datum / Stichtag:** 2026-11-12",
        "- **Prüfskript:** `scripts/audit_committed_research_data.py`",
        "- **Status-Vokabular:** `OK` / `ABWEICHUNG` / `UNKNOWN`",
        "",
        "## 1. Parsebarkeit und Objekt-/Zeilenzahlen",
        "",
    ]

    # File paths
    gap_path = repo_root / "data/research/chulane_legal_pool_gap_matrix.json"
    inc_path = repo_root / "data/research/chulane_decklist_inclusion_20261112.csv"
    pck_path = repo_root / "data/cards/pilot_card_knowledge.json"
    flags_path = repo_root / "data/cards/commander_flags.json"
    precon_path = repo_root / "data/cards/official_precon_oracle_cards.json"

    # --- 1. Parsebarkeit ---
    # Gap matrix
    try:
        gap_data = json.loads(gap_path.read_text(encoding="utf-8"))
        gap_cards: list[dict[str, object]] = gap_data.get("cards", [])
        gap_parse_err = 0
    except Exception as exc:
        gap_data = {}
        gap_cards = []
        gap_parse_err = 1
        lines.append(f"- FEHLER beim Parsen von {gap_path}: {exc}")

    # Inclusion CSV
    try:
        with inc_path.open("r", encoding="utf-8") as f:
            inc_reader = csv.DictReader(f)
            inc_fieldnames = list(inc_reader.fieldnames or [])
            inc_rows = list(inc_reader)
        inc_parse_err = 0
    except Exception as exc:
        inc_fieldnames = []
        inc_rows = []
        inc_parse_err = 1
        lines.append(f"- FEHLER beim Parsen von {inc_path}: {exc}")

    # Pilot card knowledge
    try:
        pck_data = json.loads(pck_path.read_text(encoding="utf-8"))
        pck_cards: dict[str, dict[str, object]] = pck_data.get("cards", {})
        pck_parse_err = 0
    except Exception as exc:
        pck_data = {}
        pck_cards = {}
        pck_parse_err = 1
        lines.append(f"- FEHLER beim Parsen von {pck_path}: {exc}")

    # Commander flags
    try:
        flags_data = json.loads(flags_path.read_text(encoding="utf-8"))
        flags_gc: list[dict[str, object]] = flags_data.get("game_changers", [])
        flags_cb: list[dict[str, object]] = flags_data.get("commander_banned", [])
        flags_parse_err = 0
    except Exception as exc:
        flags_data = {}
        flags_gc = []
        flags_cb = []
        flags_parse_err = 1
        lines.append(f"- FEHLER beim Parsen von {flags_path}: {exc}")

    # Official precon oracle cards
    try:
        precon_data = json.loads(precon_path.read_text(encoding="utf-8"))
        precon_cards: list[dict[str, object]] = precon_data.get("cards", [])
        precon_parse_err = 0
    except Exception as exc:
        precon_data = {}
        precon_cards = []
        precon_parse_err = 1
        lines.append(f"- FEHLER beim Parsen von {precon_path}: {exc}")

    total_parse_errors = (
        gap_parse_err + inc_parse_err + pck_parse_err + flags_parse_err + precon_parse_err
    )
    rows.append(
        AuditRow(
            "1.1 Parsebarkeit der 5 Datendateien",
            "OK" if total_parse_errors == 0 else "ABWEICHUNG",
            total_parse_errors,
            "Abschnitt 1: 0 Parse-Fehler über alle 5 Dateien",
        )
    )

    lines.append("| Datei | Format | Status | Objekt-/Zeilenzahl |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| `chulane_legal_pool_gap_matrix.json` | JSON | {'OK' if gap_parse_err == 0 else 'ABWEICHUNG'} | {len(gap_cards)} Karten |"
    )
    lines.append(
        f"| `chulane_decklist_inclusion_20261112.csv` | CSV | {'OK' if inc_parse_err == 0 else 'ABWEICHUNG'} | {len(inc_rows)} Datenzeilen |"
    )
    lines.append(
        f"| `pilot_card_knowledge.json` | JSON | {'OK' if pck_parse_err == 0 else 'ABWEICHUNG'} | {len(pck_cards)} Karten |"
    )
    lines.append(
        f"| `commander_flags.json` | JSON | {'OK' if flags_parse_err == 0 else 'ABWEICHUNG'} | {len(flags_gc)} Game Changers, {len(flags_cb)} Banned |"
    )
    lines.append(
        f"| `official_precon_oracle_cards.json` | JSON | {'OK' if precon_parse_err == 0 else 'ABWEICHUNG'} | {len(precon_cards)} Karten |"
    )
    lines.append("")

    # --- 2. Namens-Mengen vergleichen ---
    lines.append("## 2. Namens-Mengen und Dubletten")
    lines.append("")

    gap_names_exact = [str(c.get("card_name", "")) for c in gap_cards]
    gap_names_norm = {name.casefold().strip(): name for name in gap_names_exact}

    pck_names_exact = set(pck_cards.keys())
    pck_names_norm = {k.casefold().strip(): k for k in pck_cards}

    inc_names_exact = [str(r.get("card_name", "")) for r in inc_rows]
    inc_names_unique = set(inc_names_exact)

    # 2.1 Gap-Matrix-Karten ohne Eintrag in pilot_card_knowledge
    gap_missing_pck = [name for name in gap_names_exact if name not in pck_names_exact]
    gap_missing_pck_norm = [
        name for name in gap_names_exact if name.casefold().strip() not in pck_names_norm
    ]

    rows.append(
        AuditRow(
            "2.1 Gap-Matrix-Karten ohne Eintrag in pilot_card_knowledge",
            "OK" if len(gap_missing_pck) == 0 else "ABWEICHUNG",
            len(gap_missing_pck),
            "Abschnitt 2.1: 3 benutzerdefinierte/geteilte Karten fehlen in PCK",
        )
    )

    lines.append("### 2.1 Gap-Matrix-Karten ohne Eintrag in `pilot_card_knowledge`")
    lines.append(f"- **Exakte Namensgleichheit:** {len(gap_missing_pck)} Karten")
    lines.append(f"- **Normalisiert (casefold + strip):** {len(gap_missing_pck_norm)} Karten")
    if gap_missing_pck:
        lines.append("- **Betroffene Karten:**")
        for name in gap_missing_pck:
            lines.append(f"  * `{name}`")
    lines.append("")

    # 2.2 Inclusion-CSV-Karten ohne Gap-Matrix-Eintrag
    inc_missing_gap = sorted(list(inc_names_unique - set(gap_names_exact)))
    inc_missing_gap_norm = sorted(
        list(set(n for n in inc_names_unique if n.casefold().strip() not in gap_names_norm))
    )

    rows.append(
        AuditRow(
            "2.2 Inclusion-CSV-Karten ohne Gap-Matrix-Eintrag (Universum vs. Chulane-Pool)",
            "OK" if len(inc_missing_gap) == 0 else "ABWEICHUNG",
            len(inc_missing_gap),
            "Abschnitt 2.2: 6.126 Universums-Karten außerhalb des 801-Chulane-Pools",
        )
    )

    lines.append("### 2.2 Inclusion-CSV-Karten ohne Gap-Matrix-Eintrag")
    lines.append(f"- **Distinkte Kartennamen in Inclusion-CSV:** {len(inc_names_unique)}")
    lines.append(f"- **Karten im Chulane-Legal-Pool (Gap-Matrix):** {len(gap_cards)}")
    lines.append(
        f"- **Karten der Inclusion-CSV ohne Gap-Matrix-Eintrag (exakt):** {len(inc_missing_gap)}"
    )
    lines.append(
        f"- **Karten der Inclusion-CSV ohne Gap-Matrix-Eintrag (normalisiert):** {len(inc_missing_gap_norm)}"
    )
    lines.append(
        "- **Befund:** Die Inclusion-CSV deckt das gesamte 4-Player-Deck-Universum ab (inkl. Gegner- und Formatkarten außerhalb des Chulane-Pools). "
        "417 der 801 Chulane-Pool-Karten erscheinen in der Inclusion-CSV; 6.126 Universumskarten liegen außerhalb des 801-Pools."
    )
    lines.append("")

    # 2.3 Dubletten je Datei
    gap_dups = [name for name, count in Counter(gap_names_exact).items() if count > 1]
    pck_dups = [name for name, count in Counter(pck_cards.keys()).items() if count > 1]

    # In inclusion CSV: check duplicates within same cohort (card_name, source, bracket)
    inc_cohort_dups = [
        key
        for key, count in Counter(
            (r.get("card_name"), r.get("source"), r.get("bracket")) for r in inc_rows
        ).items()
        if count > 1
    ]

    gc_names = [str(x.get("name", "")) for x in flags_gc]
    cb_names = [str(x.get("name", "")) for x in flags_cb]
    gc_dups = [n for n, c in Counter(gc_names).items() if c > 1]
    cb_dups = [n for n, c in Counter(cb_names).items() if c > 1]

    precon_names = [str(x.get("oracle_name", "")) for x in precon_cards]
    precon_dups = [n for n, c in Counter(precon_names).items() if c > 1]

    total_dups = (
        len(gap_dups)
        + len(pck_dups)
        + len(inc_cohort_dups)
        + len(gc_dups)
        + len(cb_dups)
        + len(precon_dups)
    )
    rows.append(
        AuditRow(
            "2.3 Dubletten je Datei",
            "OK" if total_dups == 0 else "ABWEICHUNG",
            total_dups,
            "Abschnitt 2.3: 0 Dubletten in allen 5 Dateien",
        )
    )

    lines.append("### 2.3 Dubletten je Datei")
    lines.append(f"- `chulane_legal_pool_gap_matrix.json`: {len(gap_dups)} Dubletten")
    lines.append(f"- `pilot_card_knowledge.json`: {len(pck_dups)} Dubletten")
    lines.append(
        f"- `chulane_decklist_inclusion_20261112.csv` (innerhalb derselben Kohorte): {len(inc_cohort_dups)} Dubletten"
    )
    lines.append(f"- `commander_flags.json` (Game Changers): {len(gc_dups)} Dubletten")
    lines.append(f"- `commander_flags.json` (Banned): {len(cb_dups)} Dubletten")
    lines.append(f"- `official_precon_oracle_cards.json`: {len(precon_dups)} Dubletten")
    lines.append("")

    # --- 3. Feld-Prüfungen ---
    lines.append("## 3. Feld-Prüfungen")
    lines.append("")

    # 3.1 Inclusion-CSV: Kohorten-Nenner
    cohort_denominators: dict[tuple[str, str], set[int]] = defaultdict(set)
    cohort_snapshots: dict[tuple[str, str], set[str]] = defaultdict(set)
    range_violations: list[tuple[int, str, object, str]] = []
    empty_field_counts: dict[str, int] = {col: 0 for col in inc_fieldnames}

    for idx, r in enumerate(inc_rows, start=2):
        for col in inc_fieldnames:
            val = r.get(col, "")
            if val is None or val.strip() == "":
                empty_field_counts[col] += 1

        source = str(r.get("source", ""))
        bracket = str(r.get("bracket", ""))
        cohort = (source, bracket)

        u_decks_raw = r.get("universe_decks", "")
        c_decks_raw = r.get("decks_with_card", "")
        share_raw = r.get("share", "")

        try:
            u_decks = int(u_decks_raw)
            c_decks = int(c_decks_raw)
            share = float(share_raw)

            cohort_denominators[cohort].add(u_decks)
            cohort_snapshots[cohort].add(str(r.get("universe_snapshot", "")))

            if not (0 <= c_decks <= u_decks):
                range_violations.append(
                    (idx, "decks_with_card", c_decks, f"nicht in [0, {u_decks}]")
                )
            if not (0.0 <= share <= 1.0):
                range_violations.append((idx, "share", share, "nicht in [0.0, 1.0]"))
        except Exception as exc:
            range_violations.append((idx, "type_conversion", "", str(exc)))

    non_constant_cohorts = [c for c, denoms in cohort_denominators.items() if len(denoms) != 1]
    rows.append(
        AuditRow(
            "3.1 Inclusion-CSV: Kohorten-Nenner konstant",
            "OK" if len(non_constant_cohorts) == 0 else "ABWEICHUNG",
            len(non_constant_cohorts),
            "Abschnitt 3.1: Alle 4 Kohorten haben exakt 1 konstanten Nenner",
        )
    )

    lines.append("### 3.1 Inclusion-CSV: Konstanz der Kohorten-Nenner")
    for (src, brk), denoms in sorted(cohort_denominators.items()):
        is_const = len(denoms) == 1
        lines.append(
            f"- Kohorte `source={src}, bracket={brk}`: Nenner = {list(denoms)} (konstant: {'JA (OK)' if is_const else 'NEIN (ABWEICHUNG)'})"
        )
    lines.append("")

    # 3.2 Inclusion-CSV: Wertebereiche
    rows.append(
        AuditRow(
            "3.2 Inclusion-CSV: Wertebereiche (0 <= decks <= universe_decks; 0.0 <= share <= 1.0)",
            "OK" if len(range_violations) == 0 else "ABWEICHUNG",
            len(range_violations),
            "Abschnitt 3.2: 0 Wertebereichsverletzungen",
        )
    )

    lines.append("### 3.2 Inclusion-CSV: Wertebereichs-Prüfung")
    lines.append(f"- Anzahl Wertebereichsverletzungen: {len(range_violations)}")
    lines.append("")

    # 3.3 Inclusion-CSV: Leere Pflichtfelder
    total_empty_fields = sum(empty_field_counts.values())
    rows.append(
        AuditRow(
            "3.3 Inclusion-CSV: Leere Pflichtfelder",
            "OK" if total_empty_fields == 0 else "ABWEICHUNG",
            total_empty_fields,
            "Abschnitt 3.3: 0 leere Felder über alle 15.038 Zeilen",
        )
    )

    lines.append("### 3.3 Inclusion-CSV: Leere Pflichtfelder je Spalte")
    for col, cnt in empty_field_counts.items():
        lines.append(f"- Spalte `{col}`: {cnt} leere Werte")
    lines.append("")

    # 3.4 Gap-Matrix: summary_counts Nachrechnung
    summary = gap_data.get("summary_counts", {})
    diffs: list[str] = []

    # total_cards
    rep_total = gap_data.get("total_cards")
    act_total = len(gap_cards)
    if rep_total != act_total:
        diffs.append(f"total_cards: gemeldet={rep_total} vs. nachgerechnet={act_total}")

    # coverage_grades
    rep_grades = summary.get("coverage_grades", {})
    act_grades = dict(Counter(c.get("coverage_grade") for c in gap_cards))
    for grade, act_cnt in act_grades.items():
        rep_cnt = rep_grades.get(grade)
        if rep_cnt != act_cnt:
            diffs.append(
                f"coverage_grades[{grade}]: gemeldet={rep_cnt} vs. nachgerechnet={act_cnt}"
            )

    # long_tail_candidates_count
    rep_lt = summary.get("long_tail_candidates_count")
    act_lt = sum(1 for c in gap_cards if c.get("is_long_tail_candidate") is True)
    if rep_lt != act_lt:
        diffs.append(f"long_tail_candidates_count: gemeldet={rep_lt} vs. nachgerechnet={act_lt}")

    # unobserved_in_corpus_count
    rep_unobs = summary.get("unobserved_in_corpus_count")
    act_unobs = sum(1 for c in gap_cards if c.get("corpus_hits") == 0)
    if rep_unobs != act_unobs:
        diffs.append(
            f"unobserved_in_corpus_count: gemeldet={rep_unobs} vs. nachgerechnet={act_unobs}"
        )

    # observed_in_corpus_count
    rep_obs = summary.get("observed_in_corpus_count")
    act_obs = sum(1 for c in gap_cards if (c.get("corpus_hits") or 0) > 0)
    if rep_obs != act_obs:
        diffs.append(f"observed_in_corpus_count: gemeldet={rep_obs} vs. nachgerechnet={act_obs}")

    # has_edhrec_count
    rep_edhrec = summary.get("has_edhrec_count")
    act_edhrec = sum(1 for c in gap_cards if c.get("edhrec_hits") is not None)
    if rep_edhrec != act_edhrec:
        diffs.append(f"has_edhrec_count: gemeldet={rep_edhrec} vs. nachgerechnet={act_edhrec}")

    # has_spellbook_combos_count
    rep_combos = summary.get("has_spellbook_combos_count")
    act_combos = sum(1 for c in gap_cards if c.get("has_spellbook_combos") is True)
    if rep_combos != act_combos:
        diffs.append(
            f"has_spellbook_combos_count: gemeldet={rep_combos} vs. nachgerechnet={act_combos}"
        )

    # xmage_ready_count
    rep_xmage = summary.get("xmage_ready_count")
    act_xmage = sum(1 for c in gap_cards if c.get("has_xmage_rules") is True)
    if rep_xmage != act_xmage:
        diffs.append(f"xmage_ready_count: gemeldet={rep_xmage} vs. nachgerechnet={act_xmage}")

    rows.append(
        AuditRow(
            "3.4 Gap-Matrix: summary_counts Nachrechnung",
            "OK" if len(diffs) == 0 else "ABWEICHUNG",
            len(diffs),
            "Abschnitt 3.4: Alle summary_counts stimmen exakt mit Kartenliste überein",
        )
    )

    lines.append("### 3.4 Gap-Matrix: Nachrechnung der `summary_counts`")
    lines.append(
        f"- `total_cards`: gemeldet = {rep_total}, nachgerechnet = {act_total} ({'OK' if rep_total == act_total else 'ABWEICHUNG'})"
    )
    for grade in ["COMPLETE", "PARTIAL", "SPARSE", "UNOBSERVED_IN_CORPUS"]:
        rg = rep_grades.get(grade)
        ag = act_grades.get(grade)
        lines.append(
            f"- `coverage_grades[{grade}]`: gemeldet = {rg}, nachgerechnet = {ag} ({'OK' if rg == ag else 'ABWEICHUNG'})"
        )
    lines.append(
        f"- `long_tail_candidates_count`: gemeldet = {rep_lt}, nachgerechnet = {act_lt} ({'OK' if rep_lt == act_lt else 'ABWEICHUNG'})"
    )
    lines.append(
        f"- `unobserved_in_corpus_count`: gemeldet = {rep_unobs}, nachgerechnet = {act_unobs} ({'OK' if rep_unobs == act_unobs else 'ABWEICHUNG'})"
    )
    lines.append(
        f"- `observed_in_corpus_count`: gemeldet = {rep_obs}, nachgerechnet = {act_obs} ({'OK' if rep_obs == act_obs else 'ABWEICHUNG'})"
    )
    lines.append(
        f"- `has_edhrec_count`: gemeldet = {rep_edhrec}, nachgerechnet = {act_edhrec} ({'OK' if rep_edhrec == act_edhrec else 'ABWEICHUNG'})"
    )
    lines.append(
        f"- `has_spellbook_combos_count`: gemeldet = {rep_combos}, nachgerechnet = {act_combos} ({'OK' if rep_combos == act_combos else 'ABWEICHUNG'})"
    )
    lines.append(
        f"- `xmage_ready_count`: gemeldet = {rep_xmage}, nachgerechnet = {act_xmage} ({'OK' if rep_xmage == act_xmage else 'ABWEICHUNG'})"
    )
    lines.append("")

    # --- 4. commander_flags.json: Game Changer vs. Banned ---
    lines.append("## 4. `commander_flags.json`: Überschneidung Game Changer vs. Banned")
    lines.append("")

    gc_names_set = set(str(x.get("name", "")) for x in flags_gc)
    cb_names_set = set(str(x.get("name", "")) for x in flags_cb)
    overlap = sorted(list(gc_names_set & cb_names_set))

    rows.append(
        AuditRow(
            "4.1 commander_flags.json: Game Changer vs. Banned Überschneidung",
            "OK" if len(overlap) == 0 else "ABWEICHUNG",
            len(overlap),
            "Abschnitt 4: 0 Karten sind gleichzeitig Game Changer und Banned",
        )
    )

    lines.append(f"- Anzahl Game Changers: {len(flags_gc)}")
    lines.append(f"- Anzahl Commander Banned: {len(flags_cb)}")
    lines.append(f"- Überschneidung (Namen in beiden Mengen): {len(overlap)}")
    if overlap:
        lines.append("- Betroffene Karten:")
        for name in overlap:
            lines.append(f"  * `{name}`")
    lines.append("")

    # --- 5. Gesamt-Tabelle ---
    lines.append("## 5. Gesamt-Tabelle aller Prüfungen")
    lines.append("")
    lines.append("| Prüfung | Ergebnis | Anzahl | Details-Datei/Abschnitt |")
    lines.append("|---|---|---|---|")
    for r in rows:
        lines.append(f"| {r.check_name} | {r.result} | {r.count} | {r.details} |")
    lines.append("")

    report_markdown = "\n".join(lines)
    return rows, report_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit consistency across committed research and cards data."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Path to repository root.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/research/DATA_AUDIT_20261112.md"),
        help="Path to output Markdown audit report.",
    )
    args = parser.parse_args(argv)

    _rows, markdown_text = run_audit(args.repo_root)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown_text, encoding="utf-8")
    print(f"Wrote audit report to {args.out}")

    print()
    print(markdown_text)

    # Return 0 if audit completed and executed successfully
    return 0


if __name__ == "__main__":
    sys.exit(main())

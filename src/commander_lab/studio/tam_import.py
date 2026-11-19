"""TAM data importers: TAM_91, TAM_CHANDRA_381 (separated cohorts) and EDHREC-78 views.

Reads locally downloaded Google Drive CSV exports (UTF-8 with optional BOM) into the Studio
SQLite store without ever mixing cohorts or commanders. Every import is transactional,
idempotent, records exact SHA-256 provenance in ``source`` and binds written decks and
observation cohorts to ``Tam, the Possibility`` via ``commander_binding``.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from .catalog import refresh_corpus_stats
from .field_read import (
    CARD_NAME_ALIASES,
    EDHREC_DECK_COUNT_ALIASES,
    EDHREC_INCLUSION_PCT_ALIASES,
    EDHREC_POTENTIAL_DECKS_ALIASES,
    EDHREC_SYNERGY_ALIASES,
    FallbackTracker,
    read_field,
    read_str,
    record_store_fallbacks,
)
from .store import (
    BOUND_ELSEWHERE,
    DataClass,
    StudioStore,
    rebuild_corpus_deck_role,
    sha256_file,
)

TAM_COMMANDER_NAME = "Tam, the Possibility"
TAM_IDENTITY = frozenset({"W", "U", "B", "R", "G"})

COHORT_TAM_91 = "tam:active_91"
COHORT_TAM_381_B2_4 = "tam:curated_b2_4"
COHORT_TAM_381_UNBRACKETED = "tam:curated_unbracketed"

OBSERVED_THEME_DATA_CLASS = "OBSERVED_THEME"
_EDHREC_VIEW_COHORT_PREFIX = "tam:edhrec_view:"

_VIEW_ALIASES: tuple[str, ...] = ("view", "theme", "rubrik")
_DENOMINATOR_ALIASES: tuple[str, ...] = (
    "denominator",
    "deck_denominator",
    *EDHREC_POTENTIAL_DECKS_ALIASES,
)
_URL_ALIASES: tuple[str, ...] = ("source_url", "url")
_SNAPSHOT_ALIASES: tuple[str, ...] = ("snapshot_utc", "snapshot_date", "retrieved_at")

_MergedCardRows = dict[tuple[str, str, str], tuple[str | None, int, str]]


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _snapshot_from_name(path: Path) -> str | None:
    for candidate in (path.name, path.parent.name):
        match = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", candidate)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


def _max_date(rows: list[dict[str, str]], column: str = "date") -> str | None:
    dates = [
        val[:10] for row in rows if (val := (row.get(column) or "").strip()) and len(val) >= 10
    ]
    return max(dates) if dates else None


def _normalize_section(raw: str | None) -> str:
    cleaned = (raw or "").strip().lower()
    if cleaned in {"", "main", "mainboard"}:
        return "main"
    return cleaned


def _is_true_flag(raw: str | None) -> bool:
    return (raw or "").strip().upper() == "TRUE"


def _parse_int(raw: str | None) -> int | None:
    text = (raw or "").strip()
    if not text:
        return None
    return int(float(text))


def _parse_float(raw: str | None) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    return float(text)


@contextmanager
def _bound_import(store: StudioStore, commander_name: str) -> Iterator[None]:
    """Ensure ``store.importing_for(commander_name)`` is active without nesting triggers."""
    target = commander_name.strip()
    if not target:
        raise ValueError("a commander name is required")
    existing = store.connection.execute(
        "SELECT 1 FROM sqlite_temp_master WHERE type = 'table' AND name = 'import_commander'"
    ).fetchone()
    if existing is not None:
        row = store.connection.execute("SELECT name FROM import_commander").fetchone()
        active = str(row[0]) if row is not None else ""
        if active != target:
            raise ValueError(BOUND_ELSEWHERE)
        yield
        return
    with store.importing_for(target):
        yield


def _collect_mainboard_rows(
    rows: list[dict[str, str]], allowed_decks: set[str]
) -> tuple[_MergedCardRows, int]:
    merged: _MergedCardRows = {}
    skipped = 0
    for row in rows:
        deck_id = (row.get("deck_id") or "").strip()
        if deck_id not in allowed_decks:
            skipped += 1
            continue
        card_name = (row.get("canonical_name") or "").strip() or (
            row.get("raw_card_name") or ""
        ).strip()
        if not card_name:
            raise ValueError(f"mainboard row for deck {deck_id!r} has no card name")
        section = _normalize_section(row.get("section"))
        quantity = int((row.get("quantity") or "1").strip() or "1")
        oracle_id = (row.get("oracle_id") or "").strip() or None
        status = (row.get("normalization_status") or "").strip() or "normalized"
        key = (deck_id, card_name, section)
        previous = merged.get(key)
        merged[key] = (
            oracle_id or (previous[0] if previous else None),
            quantity + (previous[1] if previous else 0),
            status,
        )
    return merged, skipped


def _collect_commander_rows(
    rows: list[dict[str, str]], allowed_decks: set[str]
) -> tuple[_MergedCardRows, int]:
    merged: _MergedCardRows = {}
    skipped = 0
    for row in rows:
        deck_id = (row.get("deck_id") or "").strip()
        if deck_id not in allowed_decks:
            skipped += 1
            continue
        commander_name = (row.get("commander_name") or "").strip()
        if not commander_name:
            raise ValueError(f"commander row for deck {deck_id!r} has no commander_name")
        quantity = int((row.get("quantity") or "1").strip() or "1")
        oracle_id = (row.get("oracle_id") or "").strip() or None
        status = (
            (row.get("verification_status") or "").strip()
            or (row.get("source_level") or "").strip()
            or "commander"
        )
        key = (deck_id, commander_name, "commander")
        previous = merged.get(key)
        merged[key] = (
            oracle_id or (previous[0] if previous else None),
            quantity + (previous[1] if previous else 0),
            status,
        )
    return merged, skipped


def _merge_card_maps(primary: _MergedCardRows, secondary: _MergedCardRows) -> _MergedCardRows:
    combined = dict(primary)
    for key, (oracle_id, qty, status) in secondary.items():
        previous = combined.get(key)
        if previous is None:
            combined[key] = (oracle_id, qty, status)
        else:
            combined[key] = (oracle_id or previous[0], previous[1] + qty, status)
    return combined


def _source_entry(path: Path, digest: str, source_id: str) -> dict[str, str]:
    return {"file": path.name, "sha256": digest, "source_id": source_id}


def import_tam_91(
    store: StudioStore,
    register_csv: str | Path,
    mainboard_csv: str | Path,
    commander_csv: str | Path,
    *,
    commander_name: str = TAM_COMMANDER_NAME,
) -> dict[str, object]:
    """Import the ``TAM_91`` cohort (``tam:active_91``) from its three Drive CSV files.

    Idempotent and transactional: re-importing replaces the decks in ``register_csv`` and their
    card/cohort rows without duplicating rows or touching other commanders or cohorts.
    """
    register_path = Path(register_csv)
    mainboard_path = Path(mainboard_csv)
    commander_path = Path(commander_csv)

    register_rows = _csv_rows(register_path)
    mainboard_rows = _csv_rows(mainboard_path)
    commander_rows = _csv_rows(commander_path)

    deck_ids: list[str] = []
    seen_decks: set[str] = set()
    for row in register_rows:
        deck_id = (row.get("deck_id") or "").strip()
        if not deck_id:
            raise ValueError(f"{register_path.name}: row without deck_id")
        if deck_id not in seen_decks:
            seen_decks.add(deck_id)
            deck_ids.append(deck_id)

    main_merged, skipped_main = _collect_mainboard_rows(mainboard_rows, seen_decks)
    cmd_merged, skipped_cmd = _collect_commander_rows(commander_rows, seen_decks)
    all_cards = _merge_card_maps(main_merged, cmd_merged)

    reg_sha = sha256_file(register_path)
    main_sha = sha256_file(mainboard_path)
    cmd_sha = sha256_file(commander_path)
    reg_snap = _max_date(register_rows) or _snapshot_from_name(register_path)

    duplicates_marked = 0
    with _bound_import(store, commander_name), store.connection as db:
        reg_source_id = store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE,
            title=register_path.name,
            sha256=reg_sha,
            snapshot_date=reg_snap,
        )
        main_source_id = store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE,
            title=mainboard_path.name,
            sha256=main_sha,
            snapshot_date=_snapshot_from_name(mainboard_path) or reg_snap,
        )
        cmd_source_id = store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE,
            title=commander_path.name,
            sha256=cmd_sha,
            snapshot_date=_snapshot_from_name(commander_path) or reg_snap,
        )
        for row in register_rows:
            deck_id = (row.get("deck_id") or "").strip()
            dup_of = (row.get("exact_duplicate_of") or "").strip() or None
            if dup_of is not None:
                duplicates_marked += 1
            db.execute(
                "INSERT OR REPLACE INTO corpus_deck(deck_id, cohort, url, platform, "
                "play_group, deck_date, tags, fingerprint, duplicate_of, legality_audit, "
                "source_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    deck_id,
                    COHORT_TAM_91,
                    (row.get("original_url") or "").strip(),
                    (row.get("source_platform") or "").strip(),
                    (row.get("group") or "").strip(),
                    (row.get("date") or "").strip() or None,
                    (row.get("source_archetype_tags") or "").strip(),
                    (row.get("fingerprint_scryfall_oracle") or "").strip(),
                    dup_of,
                    (row.get("current_legality_name_audit") or "").strip(),
                    reg_source_id,
                ),
            )
        db.executemany(
            "DELETE FROM corpus_deck_card WHERE deck_id = ?",
            [(d,) for d in deck_ids],
        )
        db.executemany(
            "INSERT INTO corpus_deck_card(deck_id, card_name, section, oracle_id, quantity, "
            "normalization_status) VALUES (?, ?, ?, ?, ?, ?)",
            [(*key, *val) for key, val in all_cards.items()],
        )
        db.executemany(
            "DELETE FROM corpus_cohort WHERE deck_id = ?",
            [(d,) for d in deck_ids],
        )
        db.executemany(
            "INSERT INTO corpus_cohort(cohort, deck_id) VALUES (?, ?)",
            [(COHORT_TAM_91, d) for d in deck_ids],
        )
        if store.count("card_role") > 0:
            rebuild_corpus_deck_role(db)

    if store.count("scryfall_card") > 0:
        refresh_corpus_stats(store)

    total = len(register_rows)
    imported = len(deck_ids)
    return {
        "commander": commander_name,
        "cohort": COHORT_TAM_91,
        "decks_imported": imported,
        "decks_total": total,
        "decks_ratio": f"{imported}/{total}",
        "duplicates_marked": duplicates_marked,
        "mainboard_rows": len(main_merged),
        "commander_rows": len(cmd_merged),
        "mainboard_rows_without_registered_deck": skipped_main,
        "commander_rows_without_registered_deck": skipped_cmd,
        "sources": {
            "register": _source_entry(register_path, reg_sha, reg_source_id),
            "mainboard": _source_entry(mainboard_path, main_sha, main_source_id),
            "commander": _source_entry(commander_path, cmd_sha, cmd_source_id),
        },
    }


def import_tam_381(
    store: StudioStore,
    register_csv: str | Path,
    eligibility_csv: str | Path,
    mainboard_csv: str | Path,
    commander_csv: str | Path,
    *,
    commander_name: str = TAM_COMMANDER_NAME,
) -> dict[str, object]:
    """Import ``TAM_CHANDRA_381`` split strictly by eligibility into separate cohorts.

    - ``paper_legal_snapshot_2026_11_09 != "TRUE"`` (or missing eligibility row) is rejected
      and counted in ``rejected_not_paper_legal``.
    - Paper-legal with ``verified_bracket_2_4 == "TRUE"`` enters ``tam:curated_b2_4``.
    - Paper-legal with ``verified_bracket_2_4 != "TRUE"`` enters ``tam:curated_unbracketed``
      (never silently classified as Bracket 2-4).
    - When ``legacy91_cardset_overlap == "TRUE"`` and ``legacy91_deck_id`` is non-empty,
      ``duplicate_of`` is set to ``legacy91_deck_id`` and counted in ``overlaps_with_tam91``.
    """
    register_path = Path(register_csv)
    eligibility_path = Path(eligibility_csv)
    mainboard_path = Path(mainboard_csv)
    commander_path = Path(commander_csv)

    register_rows = _csv_rows(register_path)
    eligibility_rows = _csv_rows(eligibility_path)
    mainboard_rows = _csv_rows(mainboard_path)
    commander_rows = _csv_rows(commander_path)

    elig_by_deck: dict[str, dict[str, str]] = {}
    for erow in eligibility_rows:
        deck_id = (erow.get("deck_id") or "").strip()
        if deck_id:
            elig_by_deck[deck_id] = erow

    accepted_rows: list[tuple[dict[str, str], str, str | None]] = []
    b2_4_ids: list[str] = []
    unbracketed_ids: list[str] = []
    rejected_not_paper_legal = 0
    overlaps_with_tam91 = 0

    for row in register_rows:
        deck_id = (row.get("deck_id") or "").strip()
        if not deck_id:
            raise ValueError(f"{register_path.name}: row without deck_id")
        elig = elig_by_deck.get(deck_id)
        if elig is None or not _is_true_flag(elig.get("paper_legal_snapshot_2026_11_09")):
            rejected_not_paper_legal += 1
            continue
        if _is_true_flag(elig.get("verified_bracket_2_4")):
            cohort = COHORT_TAM_381_B2_4
            b2_4_ids.append(deck_id)
        else:
            cohort = COHORT_TAM_381_UNBRACKETED
            unbracketed_ids.append(deck_id)

        dup_of = (row.get("exact_duplicate_of") or "").strip() or None
        legacy_overlap = _is_true_flag(elig.get("legacy91_cardset_overlap"))
        legacy_deck_id = (elig.get("legacy91_deck_id") or "").strip()
        if legacy_overlap and legacy_deck_id:
            dup_of = legacy_deck_id
            overlaps_with_tam91 += 1
        accepted_rows.append((row, cohort, dup_of))

    accepted_id_set = {(r.get("deck_id") or "").strip() for r, _, _ in accepted_rows}
    accepted_id_list = sorted(accepted_id_set)

    main_merged, skipped_main = _collect_mainboard_rows(mainboard_rows, accepted_id_set)
    cmd_merged, skipped_cmd = _collect_commander_rows(commander_rows, accepted_id_set)
    all_cards = _merge_card_maps(main_merged, cmd_merged)

    reg_sha = sha256_file(register_path)
    elig_sha = sha256_file(eligibility_path)
    main_sha = sha256_file(mainboard_path)
    cmd_sha = sha256_file(commander_path)
    reg_snap = (
        _max_date(eligibility_rows, "snapshot_captured_utc")
        or _max_date(register_rows)
        or _snapshot_from_name(register_path)
    )

    with _bound_import(store, commander_name), store.connection as db:
        reg_source_id = store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE,
            title=register_path.name,
            sha256=reg_sha,
            snapshot_date=reg_snap,
        )
        elig_source_id = store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE,
            title=eligibility_path.name,
            sha256=elig_sha,
            snapshot_date=reg_snap,
        )
        main_source_id = store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE,
            title=mainboard_path.name,
            sha256=main_sha,
            snapshot_date=_snapshot_from_name(mainboard_path) or reg_snap,
        )
        cmd_source_id = store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE,
            title=commander_path.name,
            sha256=cmd_sha,
            snapshot_date=_snapshot_from_name(commander_path) or reg_snap,
        )

        for row, cohort, dup_of in accepted_rows:
            deck_id = (row.get("deck_id") or "").strip()
            db.execute(
                "INSERT OR REPLACE INTO corpus_deck(deck_id, cohort, url, platform, "
                "play_group, deck_date, tags, fingerprint, duplicate_of, legality_audit, "
                "source_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    deck_id,
                    cohort,
                    (row.get("original_url") or "").strip(),
                    (row.get("source_platform") or "").strip(),
                    (row.get("group") or "").strip(),
                    (row.get("date") or "").strip() or None,
                    (row.get("source_archetype_tags") or "").strip(),
                    (row.get("fingerprint_scryfall_oracle") or "").strip(),
                    dup_of,
                    (row.get("current_legality_name_audit") or "").strip(),
                    reg_source_id,
                ),
            )

        db.executemany(
            "DELETE FROM corpus_deck_card WHERE deck_id = ?",
            [(d,) for d in accepted_id_list],
        )
        db.executemany(
            "INSERT INTO corpus_deck_card(deck_id, card_name, section, oracle_id, quantity, "
            "normalization_status) VALUES (?, ?, ?, ?, ?, ?)",
            [(*key, *val) for key, val in all_cards.items()],
        )
        db.executemany(
            "DELETE FROM corpus_cohort WHERE deck_id = ?",
            [(d,) for d in accepted_id_list],
        )
        db.executemany(
            "INSERT INTO corpus_cohort(cohort, deck_id) VALUES (?, ?)",
            [(cohort, (row.get("deck_id") or "").strip()) for row, cohort, _ in accepted_rows],
        )
        if store.count("card_role") > 0:
            rebuild_corpus_deck_role(db)

    if store.count("scryfall_card") > 0:
        refresh_corpus_stats(store)

    total = len(register_rows)
    imported = len(accepted_rows)
    return {
        "commander": commander_name,
        "decks_total": total,
        "decks_imported": imported,
        "decks_imported_ratio": f"{imported}/{total}",
        "cohorts": {
            COHORT_TAM_381_B2_4: {
                "count": len(b2_4_ids),
                "denominator": total,
                "ratio": f"{len(b2_4_ids)}/{total}",
            },
            COHORT_TAM_381_UNBRACKETED: {
                "count": len(unbracketed_ids),
                "denominator": total,
                "ratio": f"{len(unbracketed_ids)}/{total}",
            },
        },
        "rejected_not_paper_legal": rejected_not_paper_legal,
        "rejected_not_paper_legal_ratio": f"{rejected_not_paper_legal}/{total}",
        "overlaps_with_tam91": overlaps_with_tam91,
        "overlaps_with_tam91_ratio": f"{overlaps_with_tam91}/{imported}",
        "mainboard_rows": len(main_merged),
        "commander_rows": len(cmd_merged),
        "mainboard_rows_without_registered_deck": skipped_main,
        "commander_rows_without_registered_deck": skipped_cmd,
        "sources": {
            "register": _source_entry(register_path, reg_sha, reg_source_id),
            "eligibility": _source_entry(eligibility_path, elig_sha, elig_source_id),
            "mainboard": _source_entry(mainboard_path, main_sha, main_source_id),
            "commander": _source_entry(commander_path, cmd_sha, cmd_source_id),
        },
    }


def _read_edhrec_view_meta(rows: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    meta: dict[str, dict[str, object]] = {}
    for row in rows:
        view = (row.get("view") or "").strip()
        if not view:
            continue
        meta[view] = {
            "n_cardrecs": _parse_int(row.get("n_cardrecs")),
            "deck_denominator": _parse_int(row.get("deck_denominator")),
            "source_url": (row.get("source_url") or "").strip() or None,
        }
    return meta


def _parse_synergy_value(row: Mapping[str, str], tracker: FallbackTracker) -> float | None:
    raw_val, used_alias = read_field(
        row, EDHREC_SYNERGY_ALIASES, tracker=tracker, canonical_name="synergy"
    )
    if raw_val is None:
        return None
    val = _parse_float(str(raw_val))
    if val is None:
        return None
    if used_alias in {"synergy", "synergy_score"} and abs(val) <= 1.0:
        return round(val * 100.0, 2)
    return val


def import_tam_edhrec_views(
    store: StudioStore,
    sources_csv: str | Path,
    cardrecs_csv: str | Path,
    *,
    commander_name: str = TAM_COMMANDER_NAME,
) -> dict[str, object]:
    """Import ``EDHREC_78`` theme cardrecs as ``OBSERVED_THEME`` observations per view.

    Each view stays in its own cohort ``tam:edhrec_view:<view>`` with its own denominator
    (never summed across views, never imported as decklists) and is bound to ``commander_name``
    in ``commander_binding(kind='observation_cohort')``.
    """
    sources_path = Path(sources_csv)
    cardrecs_path = Path(cardrecs_csv)

    source_rows = _csv_rows(sources_path)
    cardrec_rows = _csv_rows(cardrecs_path)
    view_meta = _read_edhrec_view_meta(source_rows)

    sources_sha = sha256_file(sources_path)
    cardrecs_sha = sha256_file(cardrecs_path)
    default_snap = _snapshot_from_name(cardrecs_path) or _snapshot_from_name(sources_path)

    tracker = FallbackTracker()
    prepared: list[
        tuple[
            str,  # view
            str,  # cohort
            str,  # card_name
            str,  # metric
            float | None,  # value
            int | None,  # numerator
            int | None,  # denominator
            str | None,  # url
            str | None,  # snapshot
        ]
    ] = []
    seen_keys: set[tuple[str, str, str]] = set()
    views_seen: set[str] = set()
    view_cardrecs: dict[str, int] = {}
    view_denominators: dict[str, int | None] = {}
    dropped = 0
    rows_read = 0

    for row in cardrec_rows:
        view = read_str(row, _VIEW_ALIASES, tracker=tracker, canonical_name="view")
        card_name = read_str(row, CARD_NAME_ALIASES, tracker=tracker, canonical_name="card_name")
        if not view and not card_name:
            continue
        if not view or not card_name:
            raise ValueError(
                f"{cardrecs_path.name}: row missing view or card_name "
                f"(view={view!r}, card_name={card_name!r})"
            )
        rows_read += 1
        views_seen.add(view)
        view_cardrecs[view] = view_cardrecs.get(view, 0) + 1
        cohort = f"{_EDHREC_VIEW_COHORT_PREFIX}{view}"

        raw_num = read_str(
            row, EDHREC_DECK_COUNT_ALIASES, tracker=tracker, canonical_name="num_decks"
        )
        raw_den = read_str(row, _DENOMINATOR_ALIASES, tracker=tracker, canonical_name="denominator")
        raw_inc_pct = read_str(
            row, EDHREC_INCLUSION_PCT_ALIASES, tracker=tracker, canonical_name="inclusion_pct"
        )

        meta_entry = view_meta.get(view, {})
        meta_den = meta_entry.get("deck_denominator")
        numerator = _parse_int(raw_num)
        denominator = _parse_int(raw_den)
        if denominator is None and isinstance(meta_den, int):
            denominator = meta_den
        if view not in view_denominators or view_denominators[view] is None:
            view_denominators[view] = denominator

        inclusion_pct = _parse_float(raw_inc_pct)
        if (
            inclusion_pct is None
            and numerator is not None
            and denominator is not None
            and denominator > 0
        ):
            inclusion_pct = round((numerator * 100.0) / denominator, 4)

        url = read_str(row, _URL_ALIASES) or (
            str(meta_entry["source_url"]) if meta_entry.get("source_url") else None
        )
        snapshot = read_str(row, _SNAPSHOT_ALIASES) or default_snap

        inc_key = (cohort, card_name, "inclusion_pct")
        if inc_key in seen_keys:
            dropped += 1
        else:
            seen_keys.add(inc_key)
            prepared.append(
                (
                    view,
                    cohort,
                    card_name,
                    "inclusion_pct",
                    inclusion_pct,
                    numerator,
                    denominator,
                    url,
                    snapshot,
                )
            )

        synergy_val = _parse_synergy_value(row, tracker)
        if synergy_val is not None:
            syn_key = (cohort, card_name, "synergy_pct")
            if syn_key in seen_keys:
                dropped += 1
            else:
                seen_keys.add(syn_key)
                prepared.append(
                    (
                        view,
                        cohort,
                        card_name,
                        "synergy_pct",
                        synergy_val,
                        None,
                        denominator,
                        url,
                        snapshot,
                    )
                )

    with _bound_import(store, commander_name), store.connection as db:
        sources_source_id = store.register_source(
            data_class=DataClass.ORIGINAL_SOURCE,
            title=sources_path.name,
            sha256=sources_sha,
            snapshot_date=_snapshot_from_name(sources_path) or default_snap,
        )
        cardrecs_source_id = store.register_source(
            data_class=DataClass.ORIGINAL_SOURCE,
            title=cardrecs_path.name,
            sha256=cardrecs_sha,
            snapshot_date=default_snap,
        )
        db.execute("DELETE FROM observation WHERE source_id = ?", (cardrecs_source_id,))
        for view in sorted(views_seen):
            cohort = f"{_EDHREC_VIEW_COHORT_PREFIX}{view}"
            db.execute(
                "DELETE FROM observation WHERE cohort = ? AND data_class = ?",
                (cohort, OBSERVED_THEME_DATA_CLASS),
            )
        for (
            _view,
            cohort,
            card_name,
            metric,
            value,
            numerator,
            denominator,
            url,
            snapshot,
        ) in prepared:
            card_id = store.card_id_by_oracle_or_name(None, card_name)
            db.execute(
                "INSERT INTO observation(card_id, card_name, cohort, metric, value, "
                "numerator, denominator, data_class, url, snapshot, source_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    card_id,
                    card_name,
                    cohort,
                    metric,
                    value,
                    numerator,
                    denominator,
                    OBSERVED_THEME_DATA_CLASS,
                    url,
                    snapshot,
                    cardrecs_source_id,
                ),
            )
        fallbacks = tracker.to_dict()
        if fallbacks:
            record_store_fallbacks(store, fallbacks)

    views_summary: dict[str, dict[str, object]] = {}
    for view in sorted(views_seen):
        meta_entry = view_meta.get(view, {})
        views_summary[view] = {
            "cohort": f"{_EDHREC_VIEW_COHORT_PREFIX}{view}",
            "cardrecs": view_cardrecs.get(view, 0),
            "denominator": view_denominators.get(view),
            "source_url": meta_entry.get("source_url"),
        }

    result: dict[str, object] = {
        "commander": commander_name,
        "data_class": OBSERVED_THEME_DATA_CLASS,
        "views_in_sources": len(view_meta),
        "views_imported": len(views_seen),
        "views_ratio": f"{len(views_seen)}/{len(view_meta)}",
        "cardrecs_rows": rows_read,
        "observations_written": len(prepared),
        "duplicate_observations_dropped": dropped,
        "views": views_summary,
        "sources": {
            "sources_csv": _source_entry(sources_path, sources_sha, sources_source_id),
            "cardrecs_csv": _source_entry(cardrecs_path, cardrecs_sha, cardrecs_source_id),
        },
    }
    if fallbacks:
        result["fallbacks_used"] = fallbacks
    return result

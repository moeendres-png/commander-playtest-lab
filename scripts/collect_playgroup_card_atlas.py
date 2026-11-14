"""Collect Playgroup.gg Card Atlas statistics for collection/deck cards (#1192).

Fetches publicly available card statistics from Playgroup.gg:
- Respects CC BY 4.0 license and attribution requirements.
- Uses a generic client User-Agent without any owner or repository reference.
- Enforces conservative rate-limiting (~1 request/second) with caching and resumption.
- Prioritizes 801 Chulane-legal cards, followed by remaining 613 cards.
- Exports structured TSV and JSON conforming to STUDIO_PLAYGROUP_ATLAS_SCHEMA.md.

Mandatory disclosure:
    Live-Korrelation (Playgroup.gg), keine kausale Kartenstärke.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

# Add src to sys.path if run directly
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from commander_lab.storage.atomic import atomic_write_text  # noqa: E402
from commander_lab.studio.playgroup_parser import (  # noqa: E402
    PLAYGROUP_ATTRIBUTION,
    PLAYGROUP_DISCLOSURE,
    PLAYGROUP_LICENSE,
    PlaygroupCardRecord,
    parse_playgroup_card_html,
    to_playgroup_slug,
)

logger = logging.getLogger("collect_playgroup")

DEFAULT_USER_AGENT = "card-statistics-research/1.0"
MAX_RETRY_AFTER_SECONDS = 60.0
PLAYGROUP_BASE_URL = "https://playgroup.gg/cards"


def _dedupe_targets(cards: list[dict[str, object]]) -> list[dict[str, object]]:
    """Drop repeated card names, keeping the first occurrence."""
    seen: set[str] = set()
    unique: list[dict[str, object]] = []
    for card in cards:
        key = str(card["card_name"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(card)
    return unique


def load_target_cards(
    *,
    store_path: Path | None = None,
    crosswalk_path: Path | None = None,
    coverage_matrix_path: Path | None = None,
    pool_gap_matrix_path: Path | None = None,
    explicit_names: Sequence[str] | None = None,
) -> list[dict[str, object]]:
    """Load target cards to query from public datasets (corpus, matrix, or card file)."""
    cards: list[dict[str, object]] = []

    # Load pool card names for prioritization if pool gap matrix exists
    pool_card_names: set[str] = set()
    if pool_gap_matrix_path and pool_gap_matrix_path.exists():
        try:
            with pool_gap_matrix_path.open("r", encoding="utf-8") as f:
                pool_data = json.load(f)
                pool_card_names = {c["card_name"] for c in pool_data.get("cards", [])}
        except Exception as e:
            logger.warning("Failed to load pool gap matrix %s: %s", pool_gap_matrix_path, e)

    if explicit_names:
        # Check if single argument is an existing text or csv file
        if len(explicit_names) == 1 and Path(explicit_names[0]).is_file():
            p = Path(explicit_names[0])
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    clean = line.strip()
                    if clean and not clean.startswith("#"):
                        cards.append(
                            {
                                "card_name": clean,
                                "oracle_id": "",
                                "card_id": "",
                                "slug": to_playgroup_slug(clean),
                                "is_pool": clean in pool_card_names,
                            }
                        )
        else:
            for name in explicit_names:
                clean = name.strip()
                if clean:
                    cards.append(
                        {
                            "card_name": clean,
                            "oracle_id": "",
                            "card_id": "",
                            "slug": to_playgroup_slug(clean),
                            "is_pool": clean in pool_card_names,
                        }
                    )
        # Enrich explicit names with metadata from snapshot if available
        playgroup_dir = _REPO_ROOT / "data" / "research" / "playgroup"
        if playgroup_dir.exists():
            snapshot_cards: dict[str, dict[str, object]] = {}
            for jf in sorted(playgroup_dir.glob("playgroup_card_atlas_*.jsonl")):
                try:
                    with jf.open("r", encoding="utf-8") as handle:
                        for line in handle:
                            if line.strip():
                                rec_d = json.loads(line)
                                c_name = rec_d.get("card_name")
                                if c_name:
                                    snapshot_cards[str(c_name)] = rec_d
                except Exception:
                    pass
            for c in cards:
                c_name = str(c["card_name"])
                if c_name in snapshot_cards:
                    snap = snapshot_cards[c_name]
                    if not c.get("oracle_id") and snap.get("oracle_id"):
                        c["oracle_id"] = snap["oracle_id"]
                    if not c.get("card_id") and snap.get("card_id"):
                        c["card_id"] = snap["card_id"]

        cards = _dedupe_targets(cards)
        pool_cards = sorted([c for c in cards if c["is_pool"]], key=lambda c: str(c["card_name"]))
        rest_cards = sorted(
            [c for c in cards if not c["is_pool"]], key=lambda c: str(c["card_name"])
        )
        return pool_cards + rest_cards

    if coverage_matrix_path and coverage_matrix_path.exists():
        with coverage_matrix_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                name = row.get("card_name") or row.get("oracle_name") or row.get("name") or ""
                if not name:
                    continue
                cards.append(
                    {
                        "card_name": name,
                        "oracle_id": row.get("oracle_id") or "",
                        "card_id": row.get("card_id") or "",
                        "slug": to_playgroup_slug(name),
                        "is_pool": name in pool_card_names,
                    }
                )

        # Resolve oracle_ids from store if missing
        if store_path and store_path.exists():
            conn = sqlite3.connect(store_path)
            conn.row_factory = sqlite3.Row
            try:
                table_check = [
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('scryfall_card', 'card')"
                    ).fetchall()
                ]
                cur = conn.cursor()
                for c in cards:
                    if not c["oracle_id"]:
                        c_name = str(c["card_name"])
                        if "scryfall_card" in table_check:
                            row_scry = cur.execute(
                                "SELECT oracle_id FROM scryfall_card WHERE front_name = ? OR name = ?",
                                (c_name, c_name),
                            ).fetchone()
                            if row_scry and row_scry[0]:
                                c["oracle_id"] = str(row_scry[0])
                        if not c["oracle_id"] and "card" in table_check:
                            row_card = cur.execute(
                                "SELECT oracle_id FROM card WHERE oracle_name = ?", (c_name,)
                            ).fetchone()
                            if row_card and row_card[0]:
                                c["oracle_id"] = str(row_card[0])
            finally:
                conn.close()

        cards = _dedupe_targets(cards)
        pool_cards = sorted([c for c in cards if c["is_pool"]], key=lambda c: str(c["card_name"]))
        rest_cards = sorted(
            [c for c in cards if not c["is_pool"]], key=lambda c: str(c["card_name"])
        )
        return pool_cards + rest_cards

    if crosswalk_path and crosswalk_path.exists():
        with crosswalk_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                name = row.get("oracle_name") or row.get("name") or row.get("card_name") or ""
                if not name:
                    continue
                cards.append(
                    {
                        "card_name": name,
                        "oracle_id": row.get("oracle_id") or "",
                        "card_id": row.get("card_id") or "",
                        "slug": to_playgroup_slug(name),
                        "is_pool": name in pool_card_names,
                    }
                )
        cards = _dedupe_targets(cards)
        pool_cards = sorted([c for c in cards if c["is_pool"]], key=lambda c: str(c["card_name"]))
        rest_cards = sorted(
            [c for c in cards if not c["is_pool"]], key=lambda c: str(c["card_name"])
        )
        return pool_cards + rest_cards

    if store_path and store_path.exists():
        conn = sqlite3.connect(store_path)
        conn.row_factory = sqlite3.Row
        try:
            # Query public corpus decks; if absent fallback to scryfall_card
            table_check = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('corpus_deck_card', 'scryfall_card')"
                ).fetchall()
            ]
            if "corpus_deck_card" in table_check:
                for row in conn.execute(
                    """
                    SELECT DISTINCT card_name, oracle_id
                    FROM corpus_deck_card
                    WHERE card_name IS NOT NULL AND card_name != ''
                    ORDER BY card_name ASC
                    """
                ):
                    name = str(row["card_name"])
                    cards.append(
                        {
                            "card_name": name,
                            "oracle_id": str(row["oracle_id"]) if row["oracle_id"] else "",
                            "card_id": "",
                            "slug": to_playgroup_slug(name),
                            "is_pool": name in pool_card_names,
                        }
                    )
            elif "scryfall_card" in table_check:
                for row in conn.execute(
                    """
                    SELECT DISTINCT name AS card_name, oracle_id
                    FROM scryfall_card
                    WHERE name IS NOT NULL AND name != ''
                    ORDER BY name ASC
                    """
                ):
                    name = str(row["card_name"])
                    cards.append(
                        {
                            "card_name": name,
                            "oracle_id": str(row["oracle_id"]) if row["oracle_id"] else "",
                            "card_id": "",
                            "slug": to_playgroup_slug(name),
                            "is_pool": name in pool_card_names,
                        }
                    )
        finally:
            conn.close()
        cards = _dedupe_targets(cards)
        pool_cards = sorted([c for c in cards if c["is_pool"]], key=lambda c: str(c["card_name"]))
        rest_cards = sorted(
            [c for c in cards if not c["is_pool"]], key=lambda c: str(c["card_name"])
        )
        return pool_cards + rest_cards

    raise ValueError(
        "No valid public source specified for target cards (corpus, crosswalk, or explicit)"
    )


TTL_404_SECONDS = 7 * 86400  # 7 days expiration for 404 cache


def capped_retry_after(value: str | None, default: float = 10.0) -> float:
    """Parse a Retry-After header value and cap it at MAX_RETRY_AFTER_SECONDS."""
    wait = float(value) if value is not None and value.isdigit() else default
    return min(wait, MAX_RETRY_AFTER_SECONDS)


def is_404_marker_valid(marker: Path, *, now: float | None = None) -> bool:
    """A 404 marker is valid only while 0 <= age < TTL; future mtimes count as expired."""
    try:
        age = (time.time() if now is None else now) - marker.stat().st_mtime
    except OSError:
        return False
    return 0 <= age < TTL_404_SECONDS


def fetch_card_html(
    slug: str,
    *,
    cache_dir: Path,
    user_agent: str = DEFAULT_USER_AGENT,
    delay: float = 1.0,
    offline_only: bool = False,
    refresh: bool = False,
) -> tuple[str | None, int, str]:
    """Fetch card HTML from cache or live server.

    Returns: (html_content_or_none, http_status, error_message)
    """
    cache_file = cache_dir / f"{slug}.html"
    if not refresh and cache_file.exists():
        try:
            cached = cache_file.read_text(encoding="utf-8")
            if cached:
                return cached, 200, ""
            cache_file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning("Failed to read cache file %s: %s", cache_file, e)

    cache_404 = cache_dir / f"{slug}.404"
    if not refresh and cache_404.exists():
        if is_404_marker_valid(cache_404):
            return None, 404, "Cached HTTP 404: Not Found"
        cache_404.unlink(missing_ok=True)

    if offline_only:
        # Uncached in offline mode is UNKNOWN (status 0), not NOT_FOUND
        return None, 0, "Offline only: not in cache"

    url = f"{PLAYGROUP_BASE_URL}/{slug}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        },
    )

    try:
        time.sleep(delay)
        with urllib.request.urlopen(req, timeout=20) as response:
            status = response.status
            content = response.read().decode("utf-8", errors="replace")
            if not content.strip():
                return None, 0, "Empty HTTP 200 response (not cached)"
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(cache_file, content)
            return content, status, ""
    except urllib.error.HTTPError as e:
        if e.code == 404:
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / f"{slug}.404").touch()
            return None, 404, "HTTP 404: Not Found"
        if e.code in (403, 429):
            wait_time = capped_retry_after(e.headers.get("Retry-After") if e.headers else None)
            logger.error(
                "HTTP %d Rate limited/blocked (Retry-After %.0f s, capped). Run aborts.",
                e.code,
                wait_time,
            )
            return None, e.code, f"HTTP {e.code}: blocked (retry after {wait_time:.0f} s)"
        return None, e.code, str(e)
    except Exception as e:
        return None, 0, str(e)


def run_collection(
    targets: list[dict[str, object]],
    *,
    out_dir: Path,
    cache_dir: Path,
    user_agent: str = DEFAULT_USER_AGENT,
    delay: float = 1.1,
    offline_only: bool = False,
    limit: int | None = None,
    refresh: bool = False,
    out_jsonl: Path | None = None,
) -> dict[str, object]:
    """Run collection and export structured records."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    items_to_process = targets[:limit] if limit else targets
    records: list[PlaygroupCardRecord] = []

    # Disjoint top-level status counts: AVAILABLE, NOT_FOUND, BLOCKED, UNKNOWN
    total_status_counts: dict[str, int] = {
        "AVAILABLE": 0,
        "NOT_FOUND": 0,
        "BLOCKED": 0,
        "UNKNOWN": 0,
    }
    pool_status_counts: dict[str, int] = {
        "AVAILABLE": 0,
        "NOT_FOUND": 0,
        "BLOCKED": 0,
        "UNKNOWN": 0,
    }
    rest_status_counts: dict[str, int] = {
        "AVAILABLE": 0,
        "NOT_FOUND": 0,
        "BLOCKED": 0,
        "UNKNOWN": 0,
    }

    # Detailed substatus counts: OK, PARTIAL, NO_DATA, NOT_FOUND, BLOCKED, UNKNOWN
    total_substatus_counts: dict[str, int] = {
        "OK": 0,
        "PARTIAL": 0,
        "NO_DATA": 0,
        "NOT_FOUND": 0,
        "BLOCKED": 0,
        "UNKNOWN": 0,
    }
    pool_substatus_counts: dict[str, int] = {
        "OK": 0,
        "PARTIAL": 0,
        "NO_DATA": 0,
        "NOT_FOUND": 0,
        "BLOCKED": 0,
        "UNKNOWN": 0,
    }
    rest_substatus_counts: dict[str, int] = {
        "OK": 0,
        "PARTIAL": 0,
        "NO_DATA": 0,
        "NOT_FOUND": 0,
        "BLOCKED": 0,
        "UNKNOWN": 0,
    }

    cache_hits = 0
    network_requests = 0

    for idx, card in enumerate(items_to_process, 1):
        name = str(card["card_name"])
        slug = str(card["slug"])
        oracle_id = str(card.get("oracle_id") or "")
        card_id = str(card.get("card_id") or "")
        is_pool = bool(card.get("is_pool", False))

        # Check if already in cache before calling fetch
        cache_file = cache_dir / f"{slug}.html"
        cache_404 = cache_dir / f"{slug}.404"
        is_cached = not refresh and (
            (cache_file.exists() and cache_file.stat().st_size > 0)
            or is_404_marker_valid(cache_404)
        )
        if is_cached:
            cache_hits += 1
        elif not offline_only:
            network_requests += 1

        logger.info(
            "[%d/%d] (Pool: %s, Cached: %s) Processing %s (%s)...",
            idx,
            len(items_to_process),
            is_pool,
            is_cached,
            name,
            slug,
        )

        now_utc_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        html, status, err = fetch_card_html(
            slug,
            cache_dir=cache_dir,
            user_agent=user_agent,
            delay=delay,
            offline_only=offline_only,
            refresh=refresh,
        )

        if html:
            rec = parse_playgroup_card_html(
                html,
                slug=slug,
                card_id=card_id or None,
                oracle_id=oracle_id or None,
                retrieved_at_utc=now_utc_str,
            )
            if name:
                rec = replace(rec, card_name=name)
            records.append(rec)
            top_status = "AVAILABLE"
            sub_status = rec.fetch_status  # "OK", "PARTIAL", or "NO_DATA"
        else:
            if status == 404:
                top_status = "NOT_FOUND"
                sub_status = "NOT_FOUND"
            elif status in (403, 429):
                top_status = "BLOCKED"
                sub_status = "BLOCKED"
            else:
                top_status = "UNKNOWN"
                sub_status = "UNKNOWN"

            warning = f"HTTP {status}: {err}" if err else f"HTTP {status}"
            rec = PlaygroupCardRecord(
                card_name=name,
                slug=slug,
                card_id=card_id or None,
                oracle_id=oracle_id or None,
                fetch_status=sub_status,
                quality_warnings=(warning,),
                retrieved_at_utc=now_utc_str,
            )
            records.append(rec)

        total_status_counts[top_status] += 1
        total_substatus_counts[sub_status] += 1
        if is_pool:
            pool_status_counts[top_status] += 1
            pool_substatus_counts[sub_status] += 1
        else:
            rest_status_counts[top_status] += 1
            rest_substatus_counts[sub_status] += 1

        if top_status == "BLOCKED":
            logger.error(
                "HTTP %d received for %s (%s). Aborting loop to avoid further blocked requests.",
                status,
                name,
                slug,
            )
            for remaining in items_to_process[idx:]:
                rem_name = str(remaining["card_name"])
                rem_slug = str(remaining["slug"])
                rem_is_pool = bool(remaining.get("is_pool", False))
                records.append(
                    PlaygroupCardRecord(
                        card_name=rem_name,
                        slug=rem_slug,
                        card_id=str(remaining.get("card_id") or "") or None,
                        oracle_id=str(remaining.get("oracle_id") or "") or None,
                        fetch_status="BLOCKED",
                        quality_warnings=("Aborted due to preceding BLOCKED status",),
                    )
                )
                total_status_counts["BLOCKED"] += 1
                total_substatus_counts["BLOCKED"] += 1
                if rem_is_pool:
                    pool_status_counts["BLOCKED"] += 1
                    pool_substatus_counts["BLOCKED"] += 1
                else:
                    rest_status_counts["BLOCKED"] += 1
                    rest_substatus_counts["BLOCKED"] += 1
            break

    # Export JSON
    json_path = out_dir / "playgroup_card_atlas.json"
    json_payload = {
        "schema_version": "1.1.0",
        "license": PLAYGROUP_LICENSE,
        "attribution": PLAYGROUP_ATTRIBUTION,
        "disclosure": PLAYGROUP_DISCLOSURE,
        "total_cards": len(records),
        "cache_hits": cache_hits,
        "network_requests": network_requests,
        "total_status_counts": total_status_counts,
        "pool_status_counts": pool_status_counts,
        "rest_status_counts": rest_status_counts,
        "total_substatus_counts": total_substatus_counts,
        "pool_substatus_counts": pool_substatus_counts,
        "rest_substatus_counts": rest_substatus_counts,
        "status_counts": total_substatus_counts,  # Backwards compatibility with 1.0 schema
        "cards": [r.to_dict() for r in records],
    }
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    blocked = total_status_counts["BLOCKED"] > 0

    # Export TSV (main table)
    tsv_path = out_dir / "playgroup_card_atlas.tsv"
    fieldnames = [
        "card_id",
        "oracle_id",
        "card_name",
        "slug",
        "format_mode",
        "card_type",
        "set_name",
        "live_inclusion_pct",
        "deck_inclusion_pct",
        "times_brought",
        "decks_running",
        "unique_players",
        "median_cast_turn",
        "drawn_to_played_pct",
        "first_cast_n",
        "turn_1_pct",
        "turn_2_pct",
        "turn_3_pct",
        "turn_4_pct",
        "turn_5_pct",
        "turn_6_to_9_pct",
        "turn_10_plus_pct",
        "p25_cast_turn",
        "p75_cast_turn",
        "max_cast_turn",
        "on_curve_pct",
        "on_curve_count",
        "on_curve_denominator",
        "on_curve_turn",
        "cast_same_turn_as_drawn_pct",
        "turns_in_hand",
        "funnel_brought_n",
        "funnel_players_n",
        "ever_drawn_n",
        "reached_battlefield_n",
        "still_on_board_at_end_n",
        "battlefield_survival_pct",
        "winrate_when_cast_pct",
        "winrate_when_cast_n",
        "winrate_when_in_library_pct",
        "winrate_when_in_library_n",
        "winrate_when_in_hand_pct",
        "winrate_when_in_hand_n",
        "observed_winrate_gap_pp",
        "ci_95_lower_pp",
        "ci_95_upper_pp",
        "conservative_ranking_indicator",
        "final_zones_instances_n",
        "fetch_status",
        "quality_warnings",
        "insufficient_sample",
        "retrieved_at_utc",
    ]

    with tsv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        for r in records:
            d = asdict(r)
            d["quality_warnings"] = json.dumps(list(r.quality_warnings), ensure_ascii=False)
            d["insufficient_sample"] = 1 if r.insufficient_sample else 0
            writer.writerow(d)

    # Export Top Commanders TSV
    cmd_tsv_path = out_dir / "playgroup_top_commanders.tsv"
    with cmd_tsv_path.open("w", encoding="utf-8", newline="") as handle:
        cmd_writer = csv.DictWriter(
            handle,
            fieldnames=[
                "oracle_id",
                "card_name",
                "rank",
                "commander_name",
                "commander_slug",
                "color_identity",
                "decks_count",
            ],
            delimiter="\t",
        )
        cmd_writer.writeheader()
        for r in records:
            for tc in r.top_commanders:
                cmd_writer.writerow(
                    {
                        "oracle_id": r.oracle_id or "",
                        "card_name": r.card_name,
                        "rank": tc.rank,
                        "commander_name": tc.commander_name,
                        "commander_slug": tc.commander_slug,
                        "color_identity": tc.color_identity,
                        "decks_count": tc.decks_count,
                    }
                )

    # Export Final Zones TSV
    zone_tsv_path = out_dir / "playgroup_final_zones.tsv"
    with zone_tsv_path.open("w", encoding="utf-8", newline="") as handle:
        zone_writer = csv.DictWriter(
            handle,
            fieldnames=["oracle_id", "card_name", "zone_name", "pct", "instances_n"],
            delimiter="\t",
        )
        zone_writer.writeheader()
        for r in records:
            for z in r.final_zones:
                zone_writer.writerow(
                    {
                        "oracle_id": r.oracle_id or "",
                        "card_name": r.card_name,
                        "zone_name": z.zone_name,
                        "pct": z.pct,
                        "instances_n": z.instances_n or "",
                    }
                )

    # Export JSONL (one JSON object per line conforming to schema)
    jsonl_path = out_jsonl or (out_dir / "playgroup_card_atlas.jsonl")
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for r in records:
            handle.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")

    summary = {
        "total_cards": len(records),
        "cache_hits": cache_hits,
        "network_requests": network_requests,
        "total_status_counts": total_status_counts,
        "pool_status_counts": pool_status_counts,
        "rest_status_counts": rest_status_counts,
        "total_substatus_counts": total_substatus_counts,
        "pool_substatus_counts": pool_substatus_counts,
        "rest_substatus_counts": rest_substatus_counts,
        "status_counts": total_substatus_counts,
        "blocked": blocked,
        "json_path": str(json_path),
        "tsv_path": str(tsv_path),
        "jsonl_path": str(jsonl_path),
    }
    logger.info("Collection complete. %s", summary)
    return summary


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", help="Path to Studio SQLite database")
    parser.add_argument("--crosswalk", help="Path to Scryfall/Oracle crosswalk CSV")
    parser.add_argument("--coverage-matrix", help="Path to coverage matrix CSV (1655 cards)")
    parser.add_argument(
        "--pool-gap-matrix", help="Path to Chulane pool gap matrix JSON (927 cards)"
    )
    parser.add_argument("--cards", nargs="+", help="Explicit card names to query")
    parser.add_argument("--out-dir", default="data/research/playgroup", help="Output directory")
    parser.add_argument("--out-jsonl", help="Path to write JSONL export")
    parser.add_argument("--cache-dir", default=".cache/playgroup_cards", help="Cache directory")
    parser.add_argument(
        "--delay", type=float, default=1.1, help="Delay between HTTP requests in seconds"
    )
    parser.add_argument(
        "--offline-only", action="store_true", help="Only read from cache, no network requests"
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Bypass cache and re-fetch from network"
    )
    parser.add_argument("--limit", type=_positive_int, help="Limit number of cards processed")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent string")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    store_path = Path(args.store) if args.store else None
    if not store_path and not args.crosswalk and not args.cards and not args.coverage_matrix:
        default_studio = Path.home() / ".local/share/commander-studio/studio.sqlite3"
        if default_studio.exists():
            store_path = default_studio

    coverage_path = Path(args.coverage_matrix) if args.coverage_matrix else None
    if not coverage_path and not args.crosswalk and not args.cards:
        default_cov = Path("data/research/deckbuilder_1655/coverage_matrix_1655.csv")
        if default_cov.exists():
            coverage_path = default_cov

    pool_path = Path(args.pool_gap_matrix) if args.pool_gap_matrix else None
    if not pool_path:
        default_pool = Path("data/research/chulane_legal_pool_gap_matrix.json")
        if default_pool.exists():
            pool_path = default_pool

    targets = load_target_cards(
        store_path=store_path,
        crosswalk_path=Path(args.crosswalk) if args.crosswalk else None,
        coverage_matrix_path=coverage_path,
        pool_gap_matrix_path=pool_path,
        explicit_names=args.cards,
    )

    logger.info("Loaded %d target cards.", len(targets))
    summary = run_collection(
        targets,
        out_dir=Path(args.out_dir),
        cache_dir=Path(args.cache_dir),
        user_agent=args.user_agent,
        delay=args.delay,
        offline_only=args.offline_only,
        limit=args.limit,
        refresh=args.refresh,
        out_jsonl=Path(args.out_jsonl) if args.out_jsonl else None,
    )
    if summary["blocked"]:
        logger.error("Run ended BLOCKED (HTTP 403/429).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

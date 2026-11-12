"""Collect Playgroup.gg Card Atlas statistics for collection/deck cards (#1192).

Fetches publicly available card statistics from Playgroup.gg:
- Respects CC BY 4.0 license and attribution requirements.
- Uses descriptive identifying User-Agent: CommanderLabResearch/1.0 (+https://github.com/moeendres-png/commander-playtest-lab).
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
from dataclasses import asdict
from pathlib import Path

# Add src to sys.path if run directly
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from commander_lab.studio.playgroup_parser import (  # noqa: E402
    PLAYGROUP_ATTRIBUTION,
    PLAYGROUP_DISCLOSURE,
    PLAYGROUP_LICENSE,
    PlaygroupCardRecord,
    parse_playgroup_card_html,
    to_playgroup_slug,
)

logger = logging.getLogger("collect_playgroup")

DEFAULT_USER_AGENT = (
    "CommanderLabResearch/1.0 (+https://github.com/moeendres-png/commander-playtest-lab)"
)
PLAYGROUP_BASE_URL = "https://playgroup.gg/cards"


def load_target_cards(
    *,
    store_path: Path | None = None,
    crosswalk_path: Path | None = None,
    explicit_names: Sequence[str] | None = None,
) -> list[dict[str, object]]:
    """Load target cards to query, prioritizing Chulane-legal cards."""
    cards: list[dict[str, object]] = []

    if explicit_names:
        for name in explicit_names:
            clean = name.strip()
            if clean:
                cards.append(
                    {
                        "card_name": clean,
                        "oracle_id": "",
                        "card_id": "",
                        "commander_legal": 1,
                        "slug": to_playgroup_slug(clean),
                    }
                )
        return cards

    if crosswalk_path and crosswalk_path.exists():
        with crosswalk_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                name = row.get("oracle_name") or row.get("name") or ""
                if not name:
                    continue
                cards.append(
                    {
                        "card_name": name,
                        "oracle_id": row.get("oracle_id") or "",
                        "card_id": row.get("card_id") or "",
                        "commander_legal": int(row.get("commander_legal") or 0),
                        "slug": to_playgroup_slug(name),
                    }
                )
        cards.sort(
            key=lambda c: (
                -int(c["commander_legal"]),  # type: ignore[arg-type]
                str(c["card_name"]),
            )
        )
        return cards

    if store_path and store_path.exists():
        conn = sqlite3.connect(store_path)
        conn.row_factory = sqlite3.Row
        try:
            for row in conn.execute(
                """
                SELECT card_id, oracle_id, oracle_name, commander_legal,
                       CASE
                           WHEN color_identity NOT LIKE '%B%' AND color_identity NOT LIKE '%R%' AND commander_legal = 1 THEN 1
                           ELSE 0
                       END AS is_chulane_legal
                FROM card_fact
                ORDER BY is_chulane_legal DESC, commander_legal DESC, oracle_name ASC
                """
            ):
                name = str(row["oracle_name"])
                cards.append(
                    {
                        "card_name": name,
                        "oracle_id": str(row["oracle_id"]) if row["oracle_id"] else "",
                        "card_id": str(row["card_id"]) if row["card_id"] else "",
                        "commander_legal": int(row["commander_legal"] or 0),
                        "is_chulane_legal": int(row["is_chulane_legal"] or 0),
                        "slug": to_playgroup_slug(name),
                    }
                )
        finally:
            conn.close()
        return cards

    raise ValueError("No valid source specified for target cards (store, crosswalk, or explicit)")


def fetch_card_html(
    slug: str,
    *,
    cache_dir: Path,
    user_agent: str = DEFAULT_USER_AGENT,
    delay: float = 1.0,
    offline_only: bool = False,
) -> tuple[str | None, int, str]:
    """Fetch card HTML from cache or live server.

    Returns: (html_content_or_none, http_status, error_message)
    """
    cache_file = cache_dir / f"{slug}.html"
    if cache_file.exists():
        try:
            return cache_file.read_text(encoding="utf-8"), 200, ""
        except Exception as e:
            logger.warning("Failed to read cache file %s: %s", cache_file, e)

    cache_404 = cache_dir / f"{slug}.404"
    if cache_404.exists():
        return None, 404, "Cached HTTP 404: Not Found"

    if offline_only:
        return None, 404, "Offline only: not in cache"

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
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(content, encoding="utf-8")
            return content, status, ""
    except urllib.error.HTTPError as e:
        if e.code == 404:
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / f"{slug}.404").touch()
            return None, 404, "HTTP 404: Not Found"
        if e.code in (403, 429):
            retry_after = e.headers.get("Retry-After", "10")
            wait_time = float(retry_after) if retry_after.isdigit() else 10.0
            logger.warning("HTTP %d Rate limited/blocked. Waiting %s seconds...", e.code, wait_time)
            time.sleep(wait_time)
            # Retry once
            try:
                with urllib.request.urlopen(req, timeout=20) as retry_resp:
                    content = retry_resp.read().decode("utf-8", errors="replace")
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_file.write_text(content, encoding="utf-8")
                    return content, retry_resp.status, ""
            except Exception as retry_err:
                return None, e.code, str(retry_err)
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
) -> dict[str, object]:
    """Run collection and export structured records."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    items_to_process = targets[:limit] if limit else targets
    records: list[PlaygroupCardRecord] = []
    status_counts: dict[str, int] = {}

    for idx, card in enumerate(items_to_process, 1):
        name = str(card["card_name"])
        slug = str(card["slug"])
        oracle_id = str(card.get("oracle_id") or "")
        card_id = str(card.get("card_id") or "")
        is_chulane = card.get("is_chulane_legal", 0)

        logger.info(
            "[%d/%d] (Chulane: %s) Processing %s (%s)...",
            idx,
            len(items_to_process),
            is_chulane,
            name,
            slug,
        )

        html, status, err = fetch_card_html(
            slug,
            cache_dir=cache_dir,
            user_agent=user_agent,
            delay=delay,
            offline_only=offline_only,
        )

        if html:
            rec = parse_playgroup_card_html(
                html,
                slug=slug,
                card_id=card_id or None,
                oracle_id=oracle_id or None,
            )
            records.append(rec)
            status_counts[rec.fetch_status] = status_counts.get(rec.fetch_status, 0) + 1
        else:
            if status == 404:
                fetch_status = "NOT_FOUND"
            elif status in (403, 429):
                fetch_status = "BLOCKED"
            else:
                fetch_status = "UNKNOWN"
            warning = f"HTTP {status}: {err}" if err else f"HTTP {status}"
            rec = PlaygroupCardRecord(
                card_name=name,
                slug=slug,
                card_id=card_id or None,
                oracle_id=oracle_id or None,
                fetch_status=fetch_status,
                quality_warnings=(warning,),
            )
            records.append(rec)
            status_counts[fetch_status] = status_counts.get(fetch_status, 0) + 1

    # Export JSON
    json_path = out_dir / "playgroup_card_atlas.json"
    json_payload = {
        "schema_version": "1.0.0",
        "license": PLAYGROUP_LICENSE,
        "attribution": PLAYGROUP_ATTRIBUTION,
        "disclosure": PLAYGROUP_DISCLOSURE,
        "total_cards": len(records),
        "status_counts": status_counts,
        "cards": [r.to_dict() for r in records],
    }
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

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

    summary = {
        "total_cards": len(records),
        "status_counts": status_counts,
        "json_path": str(json_path),
        "tsv_path": str(tsv_path),
    }
    logger.info("Collection complete. %s", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", help="Path to Studio SQLite database")
    parser.add_argument("--crosswalk", help="Path to Scryfall/Oracle crosswalk CSV")
    parser.add_argument("--cards", nargs="+", help="Explicit card names to query")
    parser.add_argument("--out-dir", default="data/research/playgroup", help="Output directory")
    parser.add_argument("--cache-dir", default=".cache/playgroup_cards", help="Cache directory")
    parser.add_argument(
        "--delay", type=float, default=1.1, help="Delay between HTTP requests in seconds"
    )
    parser.add_argument(
        "--offline-only", action="store_true", help="Only read from cache, no network requests"
    )
    parser.add_argument("--limit", type=int, help="Limit number of cards processed")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent string")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    store_path = Path(args.store) if args.store else None
    if not store_path and not args.crosswalk and not args.cards:
        # Check standard studio location
        default_studio = Path.home() / ".local/share/commander-studio/studio.sqlite3"
        if default_studio.exists():
            store_path = default_studio

    targets = load_target_cards(
        store_path=store_path,
        crosswalk_path=Path(args.crosswalk) if args.crosswalk else None,
        explicit_names=args.cards,
    )

    logger.info("Loaded %d target cards.", len(targets))
    run_collection(
        targets,
        out_dir=Path(args.out_dir),
        cache_dir=Path(args.cache_dir),
        user_agent=args.user_agent,
        delay=args.delay,
        offline_only=args.offline_only,
        limit=args.limit,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

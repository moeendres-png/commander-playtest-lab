"""Collect Playgroup.gg Card Atlas statistics for a PUBLIC card list (#1192).

Fetches publicly available card statistics from Playgroup.gg:
- Targets come only from --cards FILE (public card names); no collection, deck or
  store data decides what is requested (AGENTS.md section 12).
- Respects CC BY 4.0 license and attribution requirements.
- Generic User-Agent without owner handle or URL.
- Conservative rate-limiting (~1 request/second) with caching and resumption.
- Stops with status BLOCKED (exit code 3) on HTTP 403/429 after the single retry.
- Exports structured TSV and JSON conforming to STUDIO_PLAYGROUP_ATLAS_SCHEMA.md.

Mandatory disclosure:
    Live-Korrelation (Playgroup.gg), keine kausale Kartenstärke.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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

DEFAULT_USER_AGENT = "commander-studio-research/1.0"
DEFAULT_RETRY_404_AFTER_DAYS = 30.0
NOT_COLLECTED_STATUS = -1
BLOCKING_STATUSES = (403, 429)
PLAYGROUP_BASE_URL = "https://playgroup.gg/cards"


def load_target_cards(cards_file: Path) -> list[dict[str, str]]:
    """Read request targets from a PUBLIC card list (AGENTS.md section 12).

    The file holds one card name per line, or is a CSV whose header has a
    ``card_name`` column. Order is file order, deduplicated casefolded. No store,
    collection or deck data is ever consulted to decide what is requested.
    """
    lines = cards_file.read_text(encoding="utf-8-sig").splitlines()
    names: list[str] = []
    header = next(csv.reader(lines[:1]), []) if lines else []
    if "card_name" in [h.strip() for h in header]:
        for row in csv.DictReader(lines):
            names.append((row.get("card_name") or "").strip())
    else:
        names = [line.strip() for line in lines]
    targets: list[dict[str, str]] = []
    seen: set[str] = set()
    for name in names:
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        targets.append({"card_name": name, "slug": to_playgroup_slug(name)})
    return targets


def _read_404_marker(marker: Path) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(marker.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)


def fetch_card_html(
    slug: str,
    *,
    cache_dir: Path,
    user_agent: str = DEFAULT_USER_AGENT,
    delay: float = 1.0,
    offline_only: bool = False,
    retry_404_after_days: float = DEFAULT_RETRY_404_AFTER_DAYS,
    opener: Callable[..., AbstractContextManager[Any]] = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
    now: datetime | None = None,
) -> tuple[str | None, int, str]:
    """Fetch card HTML from cache or live server.

    Returns: (html_content_or_none, http_status, error_message). Status
    ``NOT_COLLECTED_STATUS`` means nothing was requested (offline cache miss).
    """
    current = now or datetime.now(UTC)
    cache_file = cache_dir / f"{slug}.html"
    if cache_file.exists():
        try:
            return cache_file.read_text(encoding="utf-8"), 200, ""
        except OSError as e:
            logger.warning("Failed to read cache file %s: %s", cache_file, e)

    cache_404 = cache_dir / f"{slug}.404"
    if cache_404.exists():
        stamp = _read_404_marker(cache_404)
        if stamp is not None and current - stamp < timedelta(days=retry_404_after_days):
            return None, 404, "Cached HTTP 404: Not Found"
        # expired or unreadable (legacy empty marker): ask again

    if offline_only:
        return None, NOT_COLLECTED_STATUS, "Offline only: not in cache, not collected"

    url = f"{PLAYGROUP_BASE_URL}/{slug}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        },
    )

    def store(content: str) -> None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(content, encoding="utf-8")

    try:
        sleep(delay)
        with opener(req, timeout=20) as response:
            content = response.read().decode("utf-8", errors="replace")
            store(content)
            return content, int(response.status), ""
    except urllib.error.HTTPError as e:
        if e.code == 404:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_404.write_text(current.astimezone(UTC).isoformat() + "\n", encoding="utf-8")
            return None, 404, "HTTP 404: Not Found"
        if e.code in (403, 429):
            retry_after = e.headers.get("Retry-After", "10") if e.headers else "10"
            wait_time = float(retry_after) if retry_after.isdigit() else 10.0
            logger.warning("HTTP %d Rate limited/blocked. Waiting %s seconds...", e.code, wait_time)
            sleep(wait_time)
            try:  # retry once
                with opener(req, timeout=20) as retry_resp:
                    content = retry_resp.read().decode("utf-8", errors="replace")
                    store(content)
                    return content, int(retry_resp.status), ""
            except urllib.error.HTTPError as retry_err:
                return None, retry_err.code, str(retry_err)
            except Exception as retry_err:
                return None, e.code, str(retry_err)
        return None, e.code, str(e)
    except Exception as e:
        return None, 0, str(e)


def run_collection(
    targets: Sequence[dict[str, str]],
    *,
    out_dir: Path,
    cache_dir: Path,
    user_agent: str = DEFAULT_USER_AGENT,
    delay: float = 1.1,
    offline_only: bool = False,
    limit: int | None = None,
    retry_404_after_days: float = DEFAULT_RETRY_404_AFTER_DAYS,
    fetch: Callable[..., tuple[str | None, int, str]] = fetch_card_html,
) -> dict[str, object]:
    """Run collection and export structured records."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    items_to_process = targets[:limit] if limit else targets
    records: list[PlaygroupCardRecord] = []
    status_counts: dict[str, int] = {}
    run_status = "COMPLETE"

    for idx, card in enumerate(items_to_process, 1):
        name = str(card["card_name"])
        slug = str(card["slug"])
        oracle_id = ""
        card_id = ""

        logger.info("[%d/%d] Processing %s (%s)...", idx, len(items_to_process), name, slug)

        html, status, err = fetch(
            slug,
            cache_dir=cache_dir,
            user_agent=user_agent,
            delay=delay,
            offline_only=offline_only,
            retry_404_after_days=retry_404_after_days,
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
            elif status in BLOCKING_STATUSES:
                fetch_status = "BLOCKED"
            elif status == NOT_COLLECTED_STATUS:
                fetch_status = "NOT_COLLECTED"
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
            if fetch_status == "BLOCKED":
                run_status = "BLOCKED"
                logger.error("Blocked by source (HTTP %d); aborting. Cache is resumable.", status)
                break

    # Export JSON
    json_path = out_dir / "playgroup_card_atlas.json"
    json_payload = {
        "schema_version": "1.0.0",
        "license": PLAYGROUP_LICENSE,
        "attribution": PLAYGROUP_ATTRIBUTION,
        "disclosure": PLAYGROUP_DISCLOSURE,
        "total_cards": len(records),
        "status_counts": status_counts,
        "run_status": run_status,
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
        "status": run_status,
        "total_cards": len(records),
        "status_counts": status_counts,
        "json_path": str(json_path),
        "tsv_path": str(tsv_path),
    }
    logger.info("Collection complete. %s", summary)
    return summary


def exit_code_for(summary: dict[str, object]) -> int:
    """Non-zero when the run was aborted because the source blocked us."""
    return 3 if summary.get("status") == "BLOCKED" else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cards",
        required=True,
        help="Public card list: one name per line, or CSV with a card_name column",
    )
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
    parser.add_argument(
        "--retry-404-after-days",
        type=float,
        default=DEFAULT_RETRY_404_AFTER_DAYS,
        help="Days after which a cached HTTP 404 is requested again (default 30)",
    )

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    targets = load_target_cards(Path(args.cards))
    logger.info("Loaded %d target cards.", len(targets))
    summary = run_collection(
        targets,
        out_dir=Path(args.out_dir),
        cache_dir=Path(args.cache_dir),
        user_agent=args.user_agent,
        delay=args.delay,
        offline_only=args.offline_only,
        limit=args.limit,
        retry_404_after_days=args.retry_404_after_days,
    )
    return exit_code_for(summary)


if __name__ == "__main__":
    sys.exit(main())

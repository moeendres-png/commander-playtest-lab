#!/usr/bin/env python3
"""Fetch full EDHTop16 card play rates for Chulane, Teller of Tales.

Fetches the complete published list of tournament staples for Chulane, Teller of Tales
from EDHTop16's persisted GraphQL API for the 1-year window.

References:
    GitHub Issue #1232: EDHTop16 — Vollauszug Chulane (1-Jahres-Fenster)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

GRAPHQL_ENDPOINT = "https://edhtop16.com/api/graphql"
PASTORIA_ID_STAPLES = "3979f7397ed9d69dbf496964ee5d235b"  # staples_CommanderStaplesQuery
PASTORIA_ID_STATS = "365ea6c7d469ca7dc4420af2a9ac0e94"  # page_CommanderStatsQuery

COMMANDER_NAME = "Chulane, Teller of Tales"
WINDOW = "ONE_YEAR"

CSV_COLUMNS: tuple[str, ...] = (
    "commander",
    "card_name",
    "play_rate",
    "conversion_rate",
    "entries_n",
    "window",
    "source_url",
    "fetched_at_utc",
)


def fetch_graphql(
    query_id: str,
    variables: dict[str, str | int | None],
    *,
    timeout: float = 15.0,
) -> dict[str, object]:
    """Execute a persisted GraphQL query on EDHTop16 with rate limiting."""
    payload = json.dumps(
        {
            "variables": variables,
            "extensions": {"pastoria-id": query_id},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        GRAPHQL_ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "commander-playtest-lab-research/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        parsed: dict[str, object] = json.loads(body)
        return parsed


def fetch_chulane_staples() -> list[dict[str, object]]:
    """Fetch the complete list of staple cards for Chulane."""
    res = fetch_graphql(
        PASTORIA_ID_STAPLES,
        {"commander": COMMANDER_NAME, "staplesSortBy": "MOST_PLAYED"},
    )
    data = res.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected response structure: {res}")
    cmd_data = data.get("commander")
    if not isinstance(cmd_data, dict):
        raise ValueError(f"Commander not found in response: {res}")
    staples = cmd_data.get("staples")
    if not isinstance(staples, list):
        raise ValueError(f"Staples list missing: {res}")
    result: list[dict[str, object]] = []
    for item in staples:
        if isinstance(item, dict):
            result.append(item)
    return result


def fetch_chulane_sample_size() -> int:
    """Fetch the total tournament entries count for Chulane in the 1-year window."""
    res = fetch_graphql(
        PASTORIA_ID_STATS,
        {"commander": COMMANDER_NAME, "minEventSize": 0, "timePeriod": WINDOW},
    )
    data = res.get("data")
    if not isinstance(data, dict):
        return 0
    cmd_data = data.get("commander")
    if not isinstance(cmd_data, dict):
        return 0
    stats = cmd_data.get("stats")
    if not isinstance(stats, dict):
        return 0
    count = stats.get("count")
    if isinstance(count, int):
        return count
    return 0


def generate_chulane_full_rows(
    *,
    delay_seconds: float = 1.2,
) -> list[dict[str, str]]:
    """Fetch and construct standardized research rows for Chulane."""
    fetched_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    staples = fetch_chulane_staples()
    time.sleep(delay_seconds)
    entries_n = fetch_chulane_sample_size()

    encoded_cmd = urllib.parse.quote(COMMANDER_NAME)
    source_url = f"https://edhtop16.com/commander/{encoded_cmd}?tab=staples"

    rows: list[dict[str, str]] = []
    for s in staples:
        name = str(s.get("name", ""))
        raw_rate = s.get("playRateLastYear")
        play_rate_str = f"{float(raw_rate):.6f}" if isinstance(raw_rate, (int, float)) else ""

        row: dict[str, str] = {
            "commander": COMMANDER_NAME,
            "card_name": name,
            "play_rate": play_rate_str,
            "conversion_rate": "",  # Not published per card by source
            "entries_n": str(entries_n) if entries_n > 0 else "0",
            "window": WINDOW,
            "source_url": source_url,
            "fetched_at_utc": fetched_at,
        }
        rows.append(row)

    return rows


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    """Write research rows to CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/research/edhtop16_chulane_full_20261112.csv"),
        help="Path to output CSV file",
    )
    args = parser.parse_args()

    print(f"Fetching full EDHTop16 staples for {COMMANDER_NAME}...")
    rows = generate_chulane_full_rows()
    write_csv(rows, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

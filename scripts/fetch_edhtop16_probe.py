#!/usr/bin/env python3
"""Fetch EDHTop16 card play rate probe for sample commanders.

This script fetches published card play rates from EDHTop16's persisted GraphQL
API for sample commanders (Chulane, Kinnan, Tymna), formats the data into a
standardized research CSV, and validates data integrity.

References:
    GitHub Issue #1225: EDHTop16 probe & verification
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

# Persisted query hashes discovered from EDHTop16 frontend client bundles
GRAPHQL_ENDPOINT = "https://edhtop16.com/api/graphql"
PASTORIA_ID_STAPLES = "3979f7397ed9d69dbf496964ee5d235b"  # staples_CommanderStaplesQuery
PASTORIA_ID_STATS = "365ea6c7d469ca7dc4420af2a9ac0e94"  # page_CommanderStatsQuery

TARGET_COMMANDERS: tuple[str, ...] = (
    "Chulane, Teller of Tales",
    "Kinnan, Bonder Prodigy",
    "Tymna the Weaver",
)

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


def fetch_commander_staples(commander: str) -> list[dict[str, object]]:
    """Fetch the list of staple cards with playRateLastYear for a commander."""
    res = fetch_graphql(
        PASTORIA_ID_STAPLES,
        {"commander": commander, "staplesSortBy": "MOST_PLAYED"},
    )
    data = res.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected response structure for {commander}: {res}")
    cmd_data = data.get("commander")
    if not isinstance(cmd_data, dict):
        raise ValueError(f"Commander not found in response for {commander}: {res}")
    staples = cmd_data.get("staples")
    if not isinstance(staples, list):
        raise ValueError(f"Staples list missing for {commander}: {res}")
    result: list[dict[str, object]] = []
    for item in staples:
        if isinstance(item, dict):
            result.append(item)
    return result


def fetch_commander_sample_size(commander: str) -> int:
    """Fetch the total tournament entries count for the 1-year window."""
    res = fetch_graphql(
        PASTORIA_ID_STATS,
        {"commander": commander, "minEventSize": 0, "timePeriod": "ONE_YEAR"},
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


def generate_probe_rows(
    commanders: tuple[str, ...] = TARGET_COMMANDERS,
    *,
    delay_seconds: float = 1.2,
) -> list[dict[str, str]]:
    """Fetch and construct standardized probe rows for the given commanders."""
    rows: list[dict[str, str]] = []
    fetched_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    for idx, cmd in enumerate(commanders):
        if idx > 0 and delay_seconds > 0:
            time.sleep(delay_seconds)

        staples = fetch_commander_staples(cmd)
        time.sleep(delay_seconds)
        entries_n = fetch_commander_sample_size(cmd)

        encoded_cmd = urllib.parse.quote(cmd)
        source_url = f"https://edhtop16.com/commander/{encoded_cmd}?tab=staples"

        for s in staples:
            name = str(s.get("name", ""))
            raw_rate = s.get("playRateLastYear")
            play_rate_str = f"{float(raw_rate):.6f}" if isinstance(raw_rate, (int, float)) else ""

            row: dict[str, str] = {
                "commander": cmd,
                "card_name": name,
                "play_rate": play_rate_str,
                "conversion_rate": "",  # Not published in staples table
                "entries_n": str(entries_n) if entries_n > 0 else "0",
                "window": "ONE_YEAR",
                "source_url": source_url,
                "fetched_at_utc": fetched_at,
            }
            rows.append(row)

    return rows


def write_probe_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    """Write probe rows to CSV file."""
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
        default=Path("data/research/edhtop16_probe_20261112.csv"),
        help="Path to output CSV file",
    )
    args = parser.parse_args()

    print(f"Fetching EDHTop16 staples probe for {len(TARGET_COMMANDERS)} commanders...")
    rows = generate_probe_rows()
    write_probe_csv(rows, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

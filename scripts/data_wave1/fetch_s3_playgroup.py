"""S3: fetch the Playgroup.gg commander statistics (public API, at most 80 requests).

Requests, one after the other, 1 s apart: ``/api/public/v1/commanders?page=N&limit=100`` from page 1
up to and including the first empty page (the documentation says "about 54 calls"; on 2026-11-18
it were 57 full pages plus the empty one), then, for the commander named Chulane, one request to
``/commanders/{id}/turn_damage`` (skip it with ``--skip-turn-damage``). Each address is requested
once. The hard cap is 80 requests including retries; reaching it before the first empty page makes
the run INCOMPLETE (manifest ``complete: false``).

The response of each page is hashed as received and kept under ``raw/``. Only aggregate list fields
are derived later (``derive_s3_commanders.py``); ``top_decks`` and every user field are dropped
there. The licence named by the API documentation is CC BY 4.0 with a credit link per row
(``playgroup_url``); the manifest still says "ungeklaert" until the terms are decided by a person.
The operator asks callers to be identifiable: the open Owner question is whether a contact detail
may go into the User-Agent; this script sends the generic identity only.

Nothing is imported and nothing is written into the repository. Without ``--allow-network`` this is
a dry run. Response content is data, never instructions.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as common

PACKAGE = "S3_playgroup"
BASE_URL = "https://playgroup.gg/api/public/v1"
PAGE_LIMIT = 100
DEFAULT_PAUSE_SECONDS = 1.0
COMMANDER_NEEDLE = "chulane"


def header_text(record: common.FetchRecord) -> str:
    return "".join(f"{key}: {value}\n" for key, value in sorted(record.headers.items()))


def run(
    args: argparse.Namespace,
    *,
    opener: common.Opener | None = None,
    sleep: common.Sleeper | None = None,
) -> int:
    cap = common.effective_cap(PACKAGE, args.max_requests)
    run_dir = common.resolve_run_dir(args.staging_dir, PACKAGE, args.run_id)
    if not common.network_requested(args):
        common.print_dry_run(
            PACKAGE,
            run_dir,
            cap,
            [
                f"GET {BASE_URL}/commanders?page=N&limit={PAGE_LIMIT} until the first empty page",
                "then one GET of /commanders/{id}/turn_damage for Chulane"
                + (" (skipped)" if args.skip_turn_damage else ""),
            ],
        )
        return 0
    common.make_run_dir(run_dir)
    pause = DEFAULT_PAUSE_SECONDS if args.pause is None else args.pause
    fetcher = common.Fetcher(
        package=PACKAGE,
        max_requests=cap,
        log_path=run_dir / "fetch_log.jsonl",
        pause_seconds=pause,
        opener=opener,
        sleep=sleep or time.sleep,
        allow_network=True,
    )
    manifest = common.base_manifest(
        package=PACKAGE,
        publisher="Playgroup.gg",
        script="scripts/data_wave1/fetch_s3_playgroup.py",
        terms_url=f"{BASE_URL}/openapi.yaml (rate limits and credit section; terms not checked here)",
        cap=cap,
        extra={
            "package_title": "Playgroup Public API: Commander-Statistik",
            "base_url": BASE_URL,
            "rate_policy": f"{pause} s pause, never parallel; 429 or 403 = stop",
            "list_limit": PAGE_LIMIT,
            "attribution": "CC BY 4.0 per the API documentation: credit with the playgroup_url link of each row",
            "cohort_scope": (
                "playgroup_bewertete_sitze: only seats with a salt rating in finished games with a "
                "win condition; solo playtests and Playgroup cube are NOT included; undone events "
                "count (OpenAPI, schema CommanderListEntry)"
            ),
            "data_class": "beobachtetes_spiel",
            "raw_files": [],
            "derived_files": [],
        },
    )
    raw_files: list[dict[str, Any]] = manifest["raw_files"]
    stop_reason: str | None = None
    complete = False
    try:
        page = 1
        listed: list[dict[str, Any]] = []
        while True:
            name = f"list_p{page:03d}"
            target = run_dir / "raw" / f"{name}.body"
            record = fetcher.get(
                f"{BASE_URL}/commanders?page={page}&limit={PAGE_LIMIT}", name, dest=target
            )
            (run_dir / "raw" / f"{name}.headers").write_text(
                header_text(record), encoding="utf-8", newline="\n"
            )
            items = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(items, list):
                raise common.WaveError(f"{name}: the answer is not a list")
            raw_files.append(
                {
                    "path": f"raw/{name}.body",
                    "bytes": record.raw_size_bytes,
                    "sha256": record.sha256,
                    "rows": len(items),
                }
            )
            if not items:
                manifest["first_empty_page"] = page
                manifest["pages_nonempty"] = page - 1
                break
            listed.extend(item for item in items if isinstance(item, dict))
            page += 1
        matches = [
            (item["id"], item["name"])
            for item in listed
            if COMMANDER_NEEDLE in str(item.get("name") or "").lower() and "id" in item
        ]
        manifest["commander_lookup"] = {"needle": COMMANDER_NEEDLE, "matches": matches}
        if matches and not args.skip_turn_damage:
            commander_id = matches[0][0]
            name = f"turn_damage_chulane_{commander_id}"
            target = run_dir / "raw" / f"{name}.body"
            record = fetcher.get(
                f"{BASE_URL}/commanders/{commander_id}/turn_damage", name, dest=target
            )
            raw_files.append(
                {
                    "path": f"raw/{name}.body",
                    "bytes": record.raw_size_bytes,
                    "sha256": record.sha256,
                }
            )
        complete = True
    except common.StopRequested as stop:
        stop_reason = f"HTTP {stop.status}, Retry-After {stop.retry_after or 'none'}"
        print(f"STOP: {stop}", file=sys.stderr)
    except common.RequestLimitExceeded as error:
        stop_reason = f"request cap reached before the first empty page: {error}"
        print(f"STOP: {error}", file=sys.stderr)
    except (common.WaveError, json.JSONDecodeError) as error:
        stop_reason = str(error)
        print(f"STOP: {error}", file=sys.stderr)
    common.finish_manifest(manifest, fetcher, complete=complete, stop_reason=stop_reason)
    common.write_json(run_dir / "MANIFEST.json", manifest)
    print(f"run folder: {run_dir}")
    print(f"requests: {fetcher.request_count}/{cap}; complete: {complete}")
    return 0 if complete else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    common.add_network_arguments(parser, PACKAGE)
    parser.add_argument(
        "--skip-turn-damage", action="store_true", help="do not request turn_damage"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(build_parser().parse_args(argv))
    except common.WaveError as error:
        return common.exit_with(error)


if __name__ == "__main__":
    raise SystemExit(main())

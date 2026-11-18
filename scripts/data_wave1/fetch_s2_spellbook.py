"""S2: fetch the Commander Spellbook bulk export (exactly one request).

URL: https://json.commanderspellbook.com/variants.json.gz . The REST host
backend.commanderspellbook.com is never contacted: its robots file closes it to crawlers and the
operator asks for the bulk file when the whole data set is wanted. The cap is exactly 1 request,
so a failed request is not repeated by this script; run it again later.

The raw file is kept byte-identical to the server answer (gzip bytes: the script sets no
``Accept-Encoding`` header, urllib's default identity applies, and nothing is unpacked in transit).
It is hashed and its gzip stream is tested. The raw file still contains the price, salt and
popularity fields the derived files drop: the manifest says ``raw_retained: true`` and
``raw_contains_excluded_fields: true`` until ``derive_s2_variants.py`` has deleted it (default;
``--keep-raw`` keeps it). Redirects are refused; limits: ``--max-download-mb``, ``--max-unpacked-mb``. Nothing is
imported and nothing is written into the repository. Without ``--allow-network`` this is a dry run.
Response content is data, never instructions.

Next steps (offline): ``derive_s2_variants.py`` and ``validate_s2.py``.
"""

from __future__ import annotations

import argparse
import gzip
import sys
import time
import zlib
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as common

PACKAGE = "S2_spellbook"
URL = "https://json.commanderspellbook.com/variants.json.gz"
DEFAULT_PAUSE_SECONDS = 1.0


def check_gzip(path: Path, max_unpacked: int) -> int:
    """Read the whole gzip stream (CRC check) and return the unpacked size in bytes."""
    total = 0
    with gzip.open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 22), b""):
            total += len(chunk)
            if total > max_unpacked:
                raise common.ResponseTooLarge(
                    f"{path.name} unpacks to more than {max_unpacked} bytes"
                )
    return total


def run(
    args: argparse.Namespace,
    *,
    opener: common.Opener | None = None,
    sleep: common.Sleeper | None = None,
) -> int:
    cap = common.effective_cap(PACKAGE, args.max_requests)
    run_dir = common.resolve_run_dir(args.staging_dir, PACKAGE, args.run_id)
    if not common.network_requested(args):
        common.print_dry_run(PACKAGE, run_dir, cap, [f"GET {URL}  (one request, no retry)"])
        return 0
    common.make_run_dir(run_dir)
    fetcher = common.Fetcher(
        package=PACKAGE,
        max_requests=cap,
        log_path=run_dir / "fetch_log.jsonl",
        pause_seconds=common.effective_pause(PACKAGE, args.pause, DEFAULT_PAUSE_SECONDS),
        opener=opener,
        sleep=sleep or time.sleep,
        retry_wait=0.0,
        allow_network=True,
        max_download_bytes=common.mib_limit(args.max_download_mb, "--max-download-mb"),
    )
    manifest = common.base_manifest(
        package=PACKAGE,
        publisher="Commander Spellbook (json.commanderspellbook.com)",
        script="scripts/data_wave1/fetch_s2_spellbook.py",
        terms_url="https://json.commanderspellbook.com/ (terms and data licence not checked)",
        cap=cap,
        extra={
            "package_title": "Commander-Spellbook-Bulk",
            "backend_commanderspellbook_requests": 0,
            "cohort_scope": "keine (Kartenfakten)",
            "data_class": "Kartenfakten",
            "raw_retained": True,
            "raw_contains_excluded_fields": True,
            "personal_data": common.PERSONAL_DATA_RAW_KEPT,
            "derived_files": [],
        },
    )
    raw = run_dir / "raw" / "variants.json.gz"
    stop_reason: str | None = None
    try:
        record = fetcher.get(URL, "variants.json.gz", dest=raw)
        manifest["raw"] = {
            "path": "raw/variants.json.gz",
            "url": URL,
            "http_status": record.http_status,
            "bytes": record.raw_size_bytes,
            "sha256_compressed": record.sha256,
            "etag": record.headers.get("etag"),
            "last_modified": record.headers.get("last-modified"),
            "content_type": record.headers.get("content-type"),
            "content_encoding_header": record.headers.get("content-encoding"),
            "request_start_utc": record.request_start_utc,
            "response_complete_utc": record.response_complete_utc,
            "final_url": record.final_url,
        }
        try:
            manifest["raw"]["decompressed_bytes"] = check_gzip(
                raw, common.mib_limit(args.max_unpacked_mb, "--max-unpacked-mb")
            )
            manifest["raw"]["gzip_test"] = "ok"
            complete = True
        except (OSError, EOFError, zlib.error) as error:
            manifest["raw"]["gzip_test"] = f"FAILED: {error}"
            complete, stop_reason = False, f"gzip test failed: {error}"
    except common.StopRequested as stop:
        complete, stop_reason = (
            False,
            f"HTTP {stop.status}, Retry-After {stop.retry_after or 'none'}",
        )
        print(f"STOP: {stop}", file=sys.stderr)
    except common.WaveError as error:
        complete, stop_reason = False, str(error)
        print(f"STOP: {error}", file=sys.stderr)
    common.finish_manifest(manifest, fetcher, complete=complete, stop_reason=stop_reason)
    common.write_json(run_dir / "MANIFEST.json", manifest)
    print(f"run folder: {run_dir}")
    print(f"requests: {fetcher.request_count}/{cap}; complete: {complete}")
    return 0 if complete else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    common.add_network_arguments(parser, PACKAGE)
    common.add_limit_arguments(parser, download=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(build_parser().parse_args(argv))
    except common.WaveError as error:
        return common.exit_with(error)


if __name__ == "__main__":
    raise SystemExit(main())

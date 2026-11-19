#!/usr/bin/env python3
"""Capture new Chulane EDHREC public JSON with immutable request/response evidence.

Never backfill a C079 historical timestamp. New observations only, review-only.
No packages, no personal inventory and no secrets.

FAIL-CLOSED: EDHREC's Terms of Service (effective 2024-08-06) prohibit automated queries and
scripts (register status ``prohibited``), and the Owner decision #1557 point 1 allows no new
automated retrieval without the operator's written permission. A live capture therefore runs
only when the environment variable ``EDHREC_WRITTEN_PERMISSION_REF`` names that written
permission (a reference, not a secret). Without it the script exits non-zero with an
explanation and never opens a network connection. ``--dry-run`` stays network-free.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_USER_AGENT = "mtg-json-archive-tool/1.0"
UA = DEFAULT_USER_AGENT
PERMISSION_ENV = "EDHREC_WRITTEN_PERMISSION_REF"
ALLOW = re.compile(
    r"^https://json\.edhrec\.com/pages/commanders/chulane-teller-of-tales(?:/[a-z0-9-]+)?\.json$"
)


class PermissionRequired(RuntimeError):
    """A live EDHREC capture was requested without a reference to written permission."""


def require_written_permission(environ: Mapping[str, str] | None = None) -> str:
    """The reference to the operator's written permission, or PermissionRequired.

    Called before any request is built, so a missing permission never reaches the network.
    """
    source = os.environ if environ is None else environ
    ref = source.get(PERMISSION_ENV, "").strip()
    if not ref:
        raise PermissionRequired(
            "EDHREC capture refused: EDHREC's Terms of Service (2024-08-06) prohibit automated "
            "queries and Owner decision #1557 point 1 allows no new automated retrieval without "
            f"the operator's written permission. Set {PERMISSION_ENV} to a reference to that "
            "permission to run a live capture. No network access was attempted."
        )
    return ref


def utc() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".tmp")
    with pending.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, path)


def read_urls(path: Path) -> list[str]:
    urls = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not urls or len(set(urls)) != len(urls):
        raise ValueError("No URL or duplicate URLs")
    if any(not ALLOW.fullmatch(url) for url in urls):
        raise ValueError("Only 20 public Chulane EDHREC JSON URLs allowed")
    return urls


def capture_one(
    url: str,
    *,
    opener=urllib.request.urlopen,
    sleep=time.sleep,
    user_agent: str = DEFAULT_USER_AGENT,
):
    if not ALLOW.fullmatch(url):
        raise ValueError("External URL is not authorized")
    permission_ref = require_written_permission()
    began = utc()
    request = urllib.request.Request(
        url, headers={"User-Agent": user_agent, "Accept": "application/json"}
    )
    attempts = 0
    while True:
        try:
            with opener(request, timeout=35) as response:
                if getattr(response, "status", None) != 200:
                    raise RuntimeError("Unexpected HTTP status")
                headers = response.headers
                body = response.read(4_000_001)
                if len(body) > 4_000_000:
                    raise ValueError("Response too large")
            finished = utc()
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempts < 2:
                raw = exc.headers.get("Retry-After", "") if exc.headers else ""
                sleep(min(int(raw) if raw.isdigit() else 3 * (attempts + 1), 30))
                attempts += 1
                continue
            raise RuntimeError(f"HTTP {exc.code}, no capture") from exc
    try:
        obj = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Non-JSON response") from exc
    if not isinstance(obj, dict) or not isinstance(obj.get("container"), dict):
        raise ValueError("Missing EDHREC response container")
    j = obj["container"].get("json_dict")
    if not isinstance(j, dict) or not isinstance(j.get("cardlists"), list):
        raise ValueError("Missing EDHREC cardlists")
    digest = hashlib.sha256(body).hexdigest()
    eid = (
        "EDHREC_NEW_"
        + hashlib.sha256((url + "\n" + began + "\n" + digest).encode()).hexdigest()[:24]
    )
    meta = {
        "event_id": eid,
        "url": url,
        "http_status": 200,
        "request_start_utc": began,
        "response_complete_utc": finished,
        "response_http_date_header_NOT_ORIGIN_TIME": headers.get("Date"),
        "response_etag": headers.get("ETag"),
        "response_last_modified": headers.get("Last-Modified"),
        "response_cache_control": headers.get("Cache-Control"),
        "raw_response_sha256": digest,
        "raw_size_bytes": len(body),
        "cardlists": len(j["cardlists"]),
        "written_permission_ref": permission_ref,
        "provenance_class": "NEW_HTTP_CAPTURE_ONLY",
        "historical_C079_timestamp_backfilled": False,
        "automatic_import": False,
    }
    return meta, body


def capture(
    urls: list[str],
    output: Path,
    *,
    opener=urllib.request.urlopen,
    sleep=time.sleep,
    delay=1.5,
    user_agent: str = DEFAULT_USER_AGENT,
):
    require_written_permission()
    records = []
    for index, url in enumerate(urls):
        if index:
            sleep(delay)
        try:
            meta, body = capture_one(url, opener=opener, sleep=sleep, user_agent=user_agent)
        except Exception as ex:
            failure = {
                "status": "CAPTURE_BLOCKED_NO_HISTORICAL_PROOF",
                "url": url,
                "time_utc": utc(),
                "completed": len(records),
                "error": type(ex).__name__,
                "message": str(ex),
                "automatic_import": False,
            }
            atomic(output / "capture_failure.json", (json.dumps(failure, indent=2) + "\n").encode())
            raise
        name = meta["event_id"]
        p = Path("raw") / f"{name}.json"
        q = Path("observations") / f"{name}.json"
        atomic(output / p, body)
        atomic(output / q, (json.dumps(meta, indent=2) + "\n").encode())
        records.append(
            {
                "event_id": name,
                "url": url,
                "raw": str(p),
                "metadata": str(q),
                "sha256": meta["raw_response_sha256"],
                "observed_utc": meta["response_complete_utc"],
            }
        )
        atomic(
            output / "manifest.json",
            (
                json.dumps(
                    {
                        "dataset": "new observations, never replace historical C079",
                        "records": records,
                        "automatic_import": False,
                    },
                    indent=2,
                )
                + "\n"
            ).encode(),
        )
    return records


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urls", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--pause", type=float, default=1.5)
    parser.add_argument("--dry-run", action="store_true")
    opts = parser.parse_args(argv)
    if not opts.dry_run:
        try:
            require_written_permission()
        except PermissionRequired as refusal:
            print(str(refusal), file=sys.stderr)
            return 2
    targets = read_urls(opts.urls)
    if not 1 <= opts.limit <= 20 or opts.pause < 1.2:
        raise ValueError("Source count and pause constraints")
    targets = targets[: opts.limit]
    if opts.dry_run:
        print(
            json.dumps(
                {
                    "source_count": len(targets),
                    "urls": targets,
                    "historical_timestamp_changes": 0,
                    "automatic_import": False,
                },
                indent=2,
            )
        )
    else:
        results = capture(targets, opts.out, delay=opts.pause)
        print(
            json.dumps(
                {
                    "new_sources": len(results),
                    "historical_timestamp_changes": 0,
                    "status": "REVIEW_ONLY",
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

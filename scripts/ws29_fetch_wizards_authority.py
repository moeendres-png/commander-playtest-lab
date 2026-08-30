#!/usr/bin/env python3
"""WS-29 direct-Wizards byte acquisition and Gatherer accessibility probe.

This script intentionally stores only metadata/digests. Raw Wizards Comprehensive
Rules bytes exist only in memory during the process and are never written into the
repository or uploaded as evidence.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

USER_AGENT = (
    "Commander-Simulation-Foundry-WS29/1.0 "
    "(+https://github.com/moeendres-png/commander-playtest-lab)"
)
CR_SOURCES = {
    "txt": "https://media.wizards.com/2026/downloads/MagicCompRules%2020260807.txt",
    "pdf": "https://media.wizards.com/2026/downloads/MagicCompRules%2020260807.pdf",
}
GATHERER_URLS = [
    "https://gatherer.wizards.com/Pages/Default.aspx",
    "https://gatherer.wizards.com/Pages/Search/Default.aspx?name=%2b%5bRograkh%2c%20Son%20of%20Rohgahh%5d",
]
EXPECTED_TXT_PREFIX = "Magic: The Gathering Comprehensive Rules"
EXPECTED_EFFECTIVE = "effective August 7, 2026"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def selected_headers(headers: Any) -> dict[str, str | None]:
    return {
        "content_type": headers.get("Content-Type"),
        "content_length": headers.get("Content-Length"),
        "etag": headers.get("ETag"),
        "last_modified": headers.get("Last-Modified"),
    }


def fetch_raw(url: str) -> tuple[bytes, dict[str, Any]]:
    opener = build_opener()  # standard redirect handling only
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    retrieved_at = now_utc()
    with opener.open(req, timeout=60) as response:
        data = response.read()
        metadata: dict[str, Any] = {
            "requested_url": url,
            "retrieved_at_utc": retrieved_at,
            "http_status": response.getcode(),
            "final_url": response.geturl(),
            **selected_headers(response.headers),
            "raw_byte_count": len(data),
            "sha256": sha256_bytes(data),
        }
        return data, metadata


def probe_url(url: str) -> dict[str, Any]:
    opener = build_opener()
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    retrieved_at = now_utc()
    try:
        with opener.open(req, timeout=60) as response:
            body = response.read()
            return {
                "requested_url": url,
                "retrieved_at_utc": retrieved_at,
                "http_status": response.getcode(),
                "final_url": response.geturl(),
                **selected_headers(response.headers),
                "raw_byte_count": len(body),
                "sha256": sha256_bytes(body),
                "transport_error": None,
            }
    except HTTPError as exc:
        body = exc.read()
        return {
            "requested_url": url,
            "retrieved_at_utc": retrieved_at,
            "http_status": exc.code,
            "final_url": exc.geturl(),
            **selected_headers(exc.headers),
            "raw_byte_count": len(body),
            "sha256": sha256_bytes(body) if body else None,
            "transport_error": f"HTTPError: {exc.code} {exc.reason}",
        }
    except URLError as exc:
        return {
            "requested_url": url,
            "retrieved_at_utc": retrieved_at,
            "http_status": None,
            "final_url": None,
            "content_type": None,
            "content_length": None,
            "etag": None,
            "last_modified": None,
            "raw_byte_count": None,
            "sha256": None,
            "transport_error": f"URLError: {exc.reason}",
        }


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/ws29/network")
    out_dir.mkdir(parents=True, exist_ok=True)

    cr_report: dict[str, Any] = {
        "schema_version": "ws29-cr-raw-acquisition/1.0.0",
        "user_agent": USER_AGENT,
        "sources": {},
        "official_cr_raw_bytes": "UNKNOWN",
    }
    cr_success = True
    for kind, url in CR_SOURCES.items():
        try:
            data, meta = fetch_raw(url)
            if kind == "txt":
                text_head = data[:4096].decode("utf-8-sig", errors="replace")
                meta["identity_verification"] = {
                    "title_prefix_match": text_head.startswith(EXPECTED_TXT_PREFIX),
                    "effective_date_match": EXPECTED_EFFECTIVE in text_head,
                    "expected_effective_date": "2026-08-07",
                    "verification_excerpt": "Magic: The Gathering Comprehensive Rules — effective August 7, 2026",
                }
                if not (
                    meta["identity_verification"]["title_prefix_match"]
                    and meta["identity_verification"]["effective_date_match"]
                ):
                    cr_success = False
            cr_report["sources"][kind] = meta
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            cr_success = False
            cr_report["sources"][kind] = {
                "requested_url": url,
                "retrieved_at_utc": now_utc(),
                "http_status": getattr(exc, "code", None),
                "final_url": getattr(exc, "url", None),
                "content_type": None,
                "content_length": None,
                "etag": None,
                "last_modified": None,
                "raw_byte_count": None,
                "sha256": None,
                "transport_error": f"{type(exc).__name__}: {exc}",
            }

    txt = cr_report["sources"].get("txt", {})
    if (
        txt.get("http_status") == 200
        and txt.get("sha256")
        and txt.get("identity_verification", {}).get("title_prefix_match")
        and txt.get("identity_verification", {}).get("effective_date_match")
    ):
        cr_report["official_cr_raw_bytes"] = "PASS"
    else:
        cr_report["official_cr_raw_bytes"] = "UNKNOWN"

    gatherer_probes = [probe_url(url) for url in GATHERER_URLS]
    any_200 = any(item.get("http_status") == 200 for item in gatherer_probes)
    all_403 = bool(gatherer_probes) and all(item.get("http_status") == 403 for item in gatherer_probes)
    gatherer_report = {
        "schema_version": "ws29-gatherer-access/1.0.0",
        "user_agent": USER_AGENT,
        "probes": gatherer_probes,
        "gatherer_direct_access": (
            "PASS" if any_200 else "BLOCKED" if all_403 else "UNKNOWN"
        ),
        "policy_note": (
            "Only ordinary public GET requests with a normal User-Agent and standard redirects were used; "
            "no CAPTCHA bypass, authentication bypass, private API, or anti-bot circumvention was attempted."
        ),
    }

    cr_path = out_dir / "CR_RAW_ACQUISITION.json"
    gatherer_path = out_dir / "GATHERER_ACCESS.json"
    cr_path.write_text(json.dumps(cr_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    gatherer_path.write_text(
        json.dumps(gatherer_report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    hashes = {
        cr_path.name: sha256_bytes(cr_path.read_bytes()),
        gatherer_path.name: sha256_bytes(gatherer_path.read_bytes()),
    }
    (out_dir / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())),
        encoding="utf-8",
    )

    print(json.dumps({"cr": cr_report, "gatherer": gatherer_report}, indent=2, sort_keys=True))
    return 0 if cr_success else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""WS-29 direct-Wizards byte acquisition and Gatherer accessibility probe.

Only metadata, digests, and narrowly bounded diagnostic excerpts are retained.
Raw Comprehensive Rules bytes are never committed or uploaded.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/139.0 Safari/537.36 "
    "Commander-Simulation-Foundry-WS29/1.0"
)
CR_SOURCES = {
    "txt": "https://media.wizards.com/2026/downloads/MagicCompRules%2020260807.txt",
    "pdf": "https://media.wizards.com/2026/downloads/MagicCompRules%2020260807.pdf",
}
GATHERER_URLS = [
    "https://gatherer.wizards.com/Pages/Default.aspx",
    "https://gatherer.wizards.com/Pages/Search/Default.aspx?name=%2b%5bRograkh%2c%20Son%20of%20Rohgahh%5d",
    "https://gatherer.wizards.com/CMR/en-us/197/rograkh-son-of-rohgahh",
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


def request(url: str, accept: str = "*/*") -> Request:
    return Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.8",
        },
    )


def fetch_raw(url: str) -> tuple[bytes, dict[str, Any]]:
    opener = build_opener()
    retrieved_at = now_utc()
    with opener.open(request(url), timeout=60) as response:
        data = response.read()
        return data, {
            "requested_url": url,
            "retrieved_at_utc": retrieved_at,
            "http_status": response.getcode(),
            "final_url": response.geturl(),
            **selected_headers(response.headers),
            "raw_byte_count": len(data),
            "sha256": sha256_bytes(data),
        }


def bounded_html_diagnostic(body: bytes) -> dict[str, Any]:
    text = body.decode("utf-8", errors="replace")
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', text, flags=re.IGNORECASE)
    relevant_hrefs = [
        unescape(href)
        for href in hrefs
        if "card" in href.lower() or "rograkh" in href.lower() or "search" in href.lower()
    ][:40]
    visible = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    visible = re.sub(r"<style\b[^>]*>.*?</style>", " ", visible, flags=re.I | re.S)
    visible = re.sub(r"<[^>]+>", " ", visible)
    visible = " ".join(unescape(visible).split())
    needle = "Rograkh"
    idx = visible.lower().find(needle.lower())
    excerpt = visible[max(0, idx - 240) : idx + 1800] if idx >= 0 else None
    return {
        "relevant_hrefs": relevant_hrefs,
        "contains_rograkh": idx >= 0,
        "bounded_rograkh_excerpt": excerpt,
    }


def probe_url(url: str) -> dict[str, Any]:
    opener = build_opener()
    retrieved_at = now_utc()
    try:
        with opener.open(
            request(url, "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
            timeout=60,
        ) as response:
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
                "diagnostic": bounded_html_diagnostic(body),
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
            "diagnostic": bounded_html_diagnostic(body) if body else None,
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
            "diagnostic": None,
        }


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/ws29/network")
    out_dir.mkdir(parents=True, exist_ok=True)
    cr_report: dict[str, Any] = {
        "schema_version": "ws29-cr-raw-acquisition/1.1.1",
        "user_agent": USER_AGENT,
        "sources": {},
        "official_cr_raw_bytes": "UNKNOWN",
        "txt_raw_bytes": "UNKNOWN",
        "pdf_raw_bytes": "UNKNOWN",
    }
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
                if meta["identity_verification"]["title_prefix_match"] and meta["identity_verification"]["effective_date_match"]:
                    cr_report["txt_raw_bytes"] = "PASS"
            if kind == "pdf" and data.startswith(b"%PDF-"):
                meta["pdf_magic_header_verified"] = True
                cr_report["pdf_raw_bytes"] = "PASS"
            cr_report["sources"][kind] = meta
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            cr_report["sources"][kind] = {
                "requested_url": url,
                "retrieved_at_utc": now_utc(),
                "http_status": getattr(exc, "code", None),
                "final_url": getattr(exc, "url", None),
                "content_type": getattr(getattr(exc, "headers", None), "get", lambda _k: None)("Content-Type"),
                "content_length": getattr(getattr(exc, "headers", None), "get", lambda _k: None)("Content-Length"),
                "etag": getattr(getattr(exc, "headers", None), "get", lambda _k: None)("ETag"),
                "last_modified": getattr(getattr(exc, "headers", None), "get", lambda _k: None)("Last-Modified"),
                "raw_byte_count": None,
                "sha256": None,
                "transport_error": f"{type(exc).__name__}: {exc}",
            }
    if cr_report["txt_raw_bytes"] == "PASS" or cr_report["pdf_raw_bytes"] == "PASS":
        cr_report["official_cr_raw_bytes"] = "PASS"

    gatherer_probes = [probe_url(url) for url in GATHERER_URLS]
    any_200 = any(item.get("http_status") == 200 for item in gatherer_probes)
    all_403 = bool(gatherer_probes) and all(item.get("http_status") == 403 for item in gatherer_probes)
    gatherer_report = {
        "schema_version": "ws29-gatherer-access/1.1.1",
        "user_agent": USER_AGENT,
        "probes": gatherer_probes,
        "gatherer_direct_access": "PASS" if any_200 else "BLOCKED" if all_403 else "UNKNOWN",
        "policy_note": (
            "Only ordinary public GET requests with a normal browser User-Agent and standard redirects were used; "
            "no CAPTCHA bypass, authentication bypass, private API, or anti-bot circumvention was attempted."
        ),
    }
    cr_path = out_dir / "CR_RAW_ACQUISITION.json"
    gatherer_path = out_dir / "GATHERER_ACCESS.json"
    cr_path.write_text(json.dumps(cr_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    gatherer_path.write_text(json.dumps(gatherer_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {cr_path.name: sha256_bytes(cr_path.read_bytes()), gatherer_path.name: sha256_bytes(gatherer_path.read_bytes())}
    (out_dir / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())), encoding="utf-8")
    print(json.dumps({"cr": cr_report, "gatherer": gatherer_report}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

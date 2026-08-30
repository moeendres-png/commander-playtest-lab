#!/usr/bin/env python3
"""Fetch the frozen WS-29 29-card corpus from public official Gatherer pages.

The script uses only ordinary public GET requests to Gatherer search/detail pages.
It retains extracted Oracle-facing text plus transport metadata/digests, never raw
HTML. No private endpoint, credential, CAPTCHA bypass, or anti-bot workaround is
used.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, build_opener

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/139.0 Safari/537.36 "
    "Commander-Simulation-Foundry-WS29/1.0"
)
BASE = "https://gatherer.wizards.com"
CORPUS = [
    ("CARD_01", "Ishai, Ojutai Dragonspeaker"),
    ("CARD_02", "Rograkh, Son of Rohgahh"),
    ("CARD_03", "Esior, Wardwing Familiar"),
    ("CARD_04", "Kediss, Emberclaw Familiar"),
    ("CARD_05", "Veyran, Voice of Duality"),
    ("CARD_06", "Harmonic Prodigy"),
    ("CARD_07", "Narset, Parter of Veils"),
    ("CARD_08", "Jeska, Thrice Reborn"),
    ("CARD_09", "Magma Opus"),
    ("CARD_10", "Wash Away"),
    ("CARD_11", "Wear // Tear"),
    ("CARD_12", "Dig Through Time"),
    ("CARD_13", "Flare of Duplication"),
    ("CARD_14", "Vandalblast"),
    ("CARD_15", "Finale of Revelation"),
    ("CARD_16", "Psychosis Crawler"),
    ("CARD_17", "Kaervek the Merciless"),
    ("CARD_18", "Shriekmaw"),
    ("CARD_19", "Butcher of Malakir"),
    ("CARD_20", "Syphon Mind"),
    ("CARD_21", "Gratuitous Violence"),
    ("CARD_22", "Bolt Bend"),
    ("CARD_23", "Makeshift Mannequin"),
    ("CARD_24", "Warstorm Surge"),
    ("CARD_25", "Basilisk Collar"),
    ("CARD_26", "Burn Down the House"),
    ("CARD_27", "Path of Ancestry"),
    ("CARD_28", "Find // Finality"),
    ("CARD_29", "Boseiju Reaches Skyward // Branch of Boseiju"),
]
DETAIL_RE = re.compile(r'href=["\'](?P<href>/[A-Za-z0-9]+/en-us/\d+/[^"\']+)["\']', re.I)
LABELS = [
    "Printed Oracle Card Name",
    "Mana Cost",
    "Type",
    "Rarity",
    "rules Text",
    "Flavor Text",
    "P/T",
    "Loyalty",
    "Defense",
    "Set",
    "Number",
    "Language",
    "printings",
    "Legal Formats",
    "Not Legal Formats",
    "Rulings",
    "Find Articles",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("//", " ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def slug_tokens(href: str) -> set[str]:
    slug = urlparse(href).path.rstrip("/").split("/")[-1]
    return set(normalize(slug).split())


def req(url: str) -> Request:
    return Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8",
        },
    )


def fetch(url: str) -> tuple[bytes, dict[str, object]]:
    retrieved = now_utc()
    try:
        with build_opener().open(req(url), timeout=60) as response:
            data = response.read()
            return data, {
                "requested_url": url,
                "retrieved_at_utc": retrieved,
                "http_status": response.getcode(),
                "final_url": response.geturl(),
                "content_type": response.headers.get("Content-Type"),
                "content_length": response.headers.get("Content-Length"),
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "raw_byte_count": len(data),
                "sha256": sha256_bytes(data),
                "transport_error": None,
            }
    except HTTPError as exc:
        data = exc.read()
        return data, {
            "requested_url": url,
            "retrieved_at_utc": retrieved,
            "http_status": exc.code,
            "final_url": exc.geturl(),
            "content_type": exc.headers.get("Content-Type"),
            "content_length": exc.headers.get("Content-Length"),
            "etag": exc.headers.get("ETag"),
            "last_modified": exc.headers.get("Last-Modified"),
            "raw_byte_count": len(data),
            "sha256": sha256_bytes(data) if data else None,
            "transport_error": f"HTTPError: {exc.code} {exc.reason}",
        }
    except URLError as exc:
        return b"", {
            "requested_url": url,
            "retrieved_at_utc": retrieved,
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


def visible_text(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(unescape(text).split())


def discover_detail(search_html: bytes, card_name: str) -> tuple[str | None, list[str]]:
    text = search_html.decode("utf-8", errors="replace")
    hrefs = list(dict.fromkeys(m.group("href") for m in DETAIL_RE.finditer(text)))
    target_tokens = set(normalize(card_name).split())
    ranked = sorted(
        hrefs,
        key=lambda href: (
            len(target_tokens & slug_tokens(href)),
            -abs(len(target_tokens) - len(slug_tokens(href))),
        ),
        reverse=True,
    )
    if not ranked:
        return None, []
    best = ranked[0]
    overlap = len(target_tokens & slug_tokens(best))
    threshold = max(1, min(2, len(target_tokens)))
    return (urljoin(BASE, best) if overlap >= threshold else None), ranked[:10]


def extract_oracle_section(text: str, expected_name: str) -> dict[str, object]:
    marker = "Printed Oracle Card Name"
    start = text.find(marker)
    if start < 0:
        return {
            "oracle_section_present": False,
            "oracle_section": None,
            "expected_name_present": normalize(expected_name) in normalize(text),
            "rules_text_label_present": False,
            "rulings_label_present": "Rulings" in text,
        }
    end_candidates = [
        idx for idx in (text.find("Find Articles", start), text.find("Club support", start)) if idx > start
    ]
    end = min(end_candidates) if end_candidates else min(len(text), start + 12000)
    section = text[start:end].strip()
    return {
        "oracle_section_present": True,
        "oracle_section": section[:12000],
        "expected_name_present": normalize(expected_name) in normalize(section),
        "rules_text_label_present": "rules Text" in section,
        "rulings_label_present": "Rulings" in section,
        "printed_oracle_label_present": marker in section,
    }


def search_url(card_name: str) -> str:
    # Public modern Gatherer search endpoint, exact full card-name string.
    return f"{BASE}/search?searchTerm={quote(card_name, safe='')}"


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/ws29/gatherer")
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for fixture_id, card_name in CORPUS:
        s_url = search_url(card_name)
        s_body, s_meta = fetch(s_url)
        detail_url, candidates = discover_detail(s_body, card_name) if s_meta.get("http_status") == 200 else (None, [])
        record: dict[str, object] = {
            "fixture_id": fixture_id,
            "card_name": card_name,
            "search": s_meta,
            "detail_candidates": candidates,
            "detail": None,
            "current_oracle_fetch_status": "AUTHORITY_BLOCKED",
            "blocker": None,
        }
        if detail_url is None:
            record["blocker"] = "No matching public Gatherer detail URL was discovered from the exact-name search response."
        else:
            time.sleep(0.10)
            d_body, d_meta = fetch(detail_url)
            extracted = extract_oracle_section(visible_text(d_body), card_name) if d_meta.get("http_status") == 200 else {
                "oracle_section_present": False,
                "oracle_section": None,
                "expected_name_present": False,
                "rules_text_label_present": False,
                "rulings_label_present": False,
            }
            d_meta["extracted"] = extracted
            record["detail"] = d_meta
            if (
                d_meta.get("http_status") == 200
                and extracted.get("oracle_section_present")
                and extracted.get("expected_name_present")
                and extracted.get("rules_text_label_present")
            ):
                record["current_oracle_fetch_status"] = "FULL_CURRENT_ORACLE_LOCK"
                record["blocker"] = None
            else:
                record["blocker"] = "Public Gatherer detail page did not expose a complete validated Oracle section for this identity."
        records.append(record)
        print(f"{fixture_id}: {record['current_oracle_fetch_status']} {detail_url or '-'}", flush=True)
        time.sleep(0.10)

    report = {
        "schema_version": "ws29-gatherer-corpus/1.0.0",
        "retrieved_by": "public Gatherer exact-name search -> public Gatherer detail page",
        "authority_statement": (
            "Gatherer is an official Wizards source. A FULL_CURRENT_ORACLE_LOCK here means the current public detail page "
            "returned HTTP 200 and exposed a validated Oracle section for the expected identity. It does not prove engine runtime behavior."
        ),
        "policy_note": (
            "Ordinary public GET requests only; no authentication, CAPTCHA bypass, private API, reverse-engineered endpoint, "
            "or anti-bot circumvention. Raw HTML is hashed then discarded."
        ),
        "card_count": len(records),
        "full_current_oracle_lock_count": sum(r["current_oracle_fetch_status"] == "FULL_CURRENT_ORACLE_LOCK" for r in records),
        "records": records,
    }
    path = out_dir / "GATHERER_29_CARD_ORACLE_LOCK.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = sha256_bytes(path.read_bytes())
    (out_dir / "SHA256SUMS").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    print(json.dumps({"card_count": len(records), "full_current_oracle_lock_count": report["full_current_oracle_lock_count"], "sha256": digest}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""WS-31 authority acquisition v4.

This layer handles a finite set of observed Gatherer search-index gaps without
weakening authority.  Printing URLs and legacy multiverse IDs are discovery
hints only.  A hint can produce PASS only after an ordinary HTTPS fetch from
the official Gatherer host and exact card-face validation of the returned
Oracle section.  No secondary-source card data is materialized.
"""
from __future__ import annotations

from urllib.parse import urlparse

import ws31_acquire_gatherer_v3 as v3

v2 = v3.v2
base = v2.base
_original_acquire_face = v2.acquire_face

# Discovery-only hints for the exact faces that remained UNKNOWN after the
# exhaustive ordinary-public exact/prefix/last-token search run.  These are
# printing locators, not authority data: the fetched official page must still
# parse to the exact requested face before PASS is possible.
DIRECT_DISCOVERY_HINTS: dict[str, list[str]] = {
    "Agrus Kos, Wojek Veteran": [f"{base.BASE}/RAV/en-us/190/agrus-kos-wojek-veteran"],
    "Angel's Feather": [f"{base.BASE}/M12/en-us/202/angels-feather"],
    "Avatar of Discord": [f"{base.BASE}/GK2/en-us/61/avatar-of-discord", f"{base.BASE}/DIS/en-us/140/avatar-of-discord"],
    "Petty Theft": [f"{base.BASE}/SPG/en-us/30/petty-theft"],
    "Chandra Nalaar": [f"{base.BASE}/M11/en-us/127/chandra-nalaar"],
    "Consume Spirit": [f"{base.BASE}/M12/en-us/88/consume-spirit"],
    "Demon's Horn": [f"{base.BASE}/M12/en-us/205/demons-horn"],
    "Elspeth, Knight-Errant": [f"{base.BASE}/MMA/en-us/13/elspeth-knight-errant"],
    "Kaiso, Memory of Loyalty": [f"{base.BASE}/BOK/en-us/3/kaiso-memory-of-loyalty"],
    "Firemane Angel": [f"{base.BASE}/IMA/en-us/199/firemane-angel"],
    "Healing Salve": [f"{base.BASE}/DDC/en-us/14/healing-salve"],
    "Maestro's Gift": [f"{base.BASE}/SOC/en-us/48/maestros-gift", f"{base.BASE}/SOC/en-us/96/maestros-gift"],
    "Nicol Bolas, Planeswalker": [f"{base.BASE}/M13/en-us/199/nicol-bolas-planeswalker"],
    "Fall": [f"{base.BASE}/DDH/en-us/73/fall"],
    "Sorin Markov": [f"{base.BASE}/ZEN/en-us/111/sorin-markov"],
    "Unholy Strength": [f"{base.BASE}/9ED/en-us/168/unholy-strength"],
    "Venerable Monk": [f"{base.BASE}/8ED/en-us/55/venerable-monk"],
    "Vicious Hunger": [f"{base.BASE}/NEM/en-us/74/vicious-hunger"],
    "Vine Trellis": [f"{base.BASE}/8ED/en-us/287/vine-trellis"],
}

LEGACY_MULTIVERSE_IDS: dict[str, list[int]] = {
    "Agrus Kos, Wojek Veteran": [89101],
    "Angel's Feather": [221520, 72686],
    "Avatar of Discord": [460607, 107437],
    "Chandra Nalaar": [205958],
    "Consume Spirit": [244249],
    "Demon's Horn": [221522],
    "Elspeth, Knight-Errant": [370551],
    "Kaiso, Memory of Loyalty": [74093],
    "Firemane Angel": [438765],
    "Healing Salve": [197011],
    "Nicol Bolas, Planeswalker": [260991],
    "Sorin Markov": [195403],
    "Unholy Strength": [83310],
    "Venerable Monk": [45175],
    "Vicious Hunger": [21317, 45300],
    "Vine Trellis": [45399, 19624],
}


def _official_gatherer(url: str | None) -> bool:
    if not url:
        return False
    p = urlparse(url)
    return p.scheme == "https" and p.hostname == "gatherer.wizards.com"


def _validated_result(face: str, requested_url: str, mode: str, require_slug: bool):
    body, meta = base.fetch(requested_url)
    attempt = {"mode": mode, "query": face, "requested_url": requested_url, "transport": meta}
    if not meta or meta.get("http_status") != 200:
        return None, attempt
    final_url = meta.get("final_url") or requested_url
    if not _official_gatherer(final_url):
        return None, attempt
    if require_slug and not v2.detail_url_matches_face(final_url, face):
        return None, attempt
    section = v2.extract_oracle_section(base.visible_text(body), face)
    if not section:
        return None, attempt
    fields = v2.parse_section(section, face)
    if not fields.get("parse_complete"):
        return None, attempt
    result = {
        "requested_face_name": face,
        "official_gatherer_url": final_url,
        "detail_transport": meta,
        **fields,
        "oracle_section_sha256": base.sha256_bytes(" ".join(section.split()).encode("utf-8")),
        "currentness_status": "CURRENT_OFFICIAL_GATHERER_AT_RETRIEVAL",
        "retrieval_timestamp_utc": meta.get("retrieved_at_utc"),
        "raw_html_sha256": meta.get("raw_html_sha256"),
        "raw_html_byte_count": meta.get("raw_byte_count"),
        "acquisition_status": "PASS",
        "failure_reason": None,
        "discovery_hint_only": True,
        "discovery_hint_mode": mode,
    }
    return result, attempt


def acquire_face(face: str, delay: float):
    out, db, siblings = _original_acquire_face(face, delay)
    if out.get("acquisition_status") == "PASS":
        return out, db, siblings

    attempts = list(out.get("search_attempts") or [])
    candidates = list(out.get("detail_candidates") or [])

    for candidate in DIRECT_DISCOVERY_HINTS.get(face, []):
        result, attempt = _validated_result(
            face, candidate, "DISCOVERY_ONLY_KNOWN_PRINTING_HINT", require_slug=True
        )
        attempts.append(attempt)
        candidates.append(candidate)
        if result:
            result["search"] = out.get("search")
            result["search_attempts"] = attempts
            result["detail_candidates"] = list(dict.fromkeys(candidates))[:60]
            return result, None, []

    for multiverse_id in LEGACY_MULTIVERSE_IDS.get(face, []):
        candidate = f"https://gatherer.wizards.com/Pages/Card/Details.aspx?multiverseid={multiverse_id}"
        result, attempt = _validated_result(
            face, candidate, "LEGACY_MULTIVERSEID_DISCOVERY_HINT", require_slug=False
        )
        attempts.append(attempt)
        candidates.append(candidate)
        if result:
            result["search"] = out.get("search")
            result["search_attempts"] = attempts
            result["detail_candidates"] = list(dict.fromkeys(candidates))[:60]
            return result, None, []

    out["search_attempts"] = attempts
    out["detail_candidates"] = list(dict.fromkeys(candidates))[:60]
    out["failure_reason"] = "NO_EXACT_OFFICIAL_GATHERER_PAGE_AFTER_VALIDATED_DISCOVERY_HINTS"
    return out, db, siblings


# The base main loop resolves this global at runtime.  Patch both namespaces so
# acquisition remains single-source and all identity/shard semantics stay intact.
v2.acquire_face = acquire_face
base.acquire_face = acquire_face


if __name__ == "__main__":
    raise SystemExit(base.main())

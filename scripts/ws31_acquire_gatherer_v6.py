#!/usr/bin/env python3
"""WS-31 acquisition v6: exact current-Gatherer legacy flip-face parser.

One observed Betrayers of Kamigawa flip card is represented by current Gatherer
with both halves embedded in a legacy combined layout.  The generic labeled
field parser locks the primary half but cannot treat the lower flip half as an
independent labeled face.

This layer is intentionally finite and fail closed.  It can repair only the
exact project identity Faithful Squire // Kaiso, Memory of Loyalty, and only
when:
  * Faithful Squire already PASSed current official Gatherer;
  * the exact current Kaiso Gatherer slug returns HTTP 200 on the official host;
  * the final URL still exactly matches the Kaiso face slug;
  * the live visible text contains an exact Kaiso block from which a creature
    type line, P/T, and non-empty rules text can be bounded before Artist.

No secondary source, hard-coded Oracle text, or runtime-functionality credit is
used.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

import ws31_acquire_gatherer_v5 as v5

base = v5.base
v4 = v5.v4
v2 = v4.v2
_original_acquire_identity = base.acquire_identity

LEGACY_FLIP_FALLBACK = {
    "project_card_identity": "Faithful Squire // Kaiso, Memory of Loyalty",
    "primary_face": "Faithful Squire",
    "face": "Kaiso, Memory of Loyalty",
    "url": "https://gatherer.wizards.com/BOK/en-us/3/kaiso-memory-of-loyalty",
}


def _extract_legacy_flip_face(text: str, face: str) -> tuple[dict | None, list[str]]:
    flat = " ".join((text or "").split())
    starts = [m.start() for m in re.finditer(re.escape(face), flat, flags=re.I)]
    previews: list[str] = []
    for pos in starts[:8]:
        window = flat[pos:pos + 1800]
        previews.append(window[:700])
        # The legacy lower-half layout is unlabeled but stable in semantic
        # order: exact face name, creature type line, P/T, rules text, Artist.
        pat = re.compile(
            r"^" + re.escape(face)
            + r"\s+(?P<type>(?:Legendary\s+)?(?:Artifact\s+)?Creature\s+[—–-]\s+[A-Za-z][A-Za-z0-9'’ -]{0,80}?)"
            + r"\s+(?P<pt>[*0-9+\-]+\s*/\s*[*0-9+\-]+)"
            + r"\s+(?P<oracle>.+?)\s+Artist\b",
            flags=re.I,
        )
        m = pat.search(window)
        if not m:
            continue
        type_line = " ".join(m.group("type").split())
        pt = " ".join(m.group("pt").split())
        oracle = " ".join(m.group("oracle").split()).strip(" :-•")
        if not type_line or not pt or not oracle:
            continue
        if v2.match_norm(face) not in v2.match_norm(window[: len(face) + 20]):
            continue
        return {
            "current_gatherer_card_name": face,
            "mana_cost": None,
            "colors": [],
            "color_indicator": None,
            "type_line": type_line,
            "oracle_text": oracle,
            "power_toughness": pt,
            "loyalty": None,
            "defense": None,
            "parse_complete": True,
        }, previews
    return None, previews


def probe_legacy_flip_face(spec: dict = LEGACY_FLIP_FALLBACK) -> tuple[dict | None, dict]:
    body, meta = base.fetch(spec["url"])
    diag = {
        "requested_face_name": spec["face"],
        "requested_url": spec["url"],
        "transport": meta,
        "official_gatherer_host_valid": False,
        "exact_face_slug_valid": False,
        "exact_legacy_flip_parse": False,
        "failure_stage": None,
    }
    if not meta or meta.get("http_status") != 200:
        diag["failure_stage"] = "LEGACY_FLIP_GATHERER_HTTP_FAILURE"
        return None, diag
    final_url = meta.get("final_url") or spec["url"]
    p = urlparse(final_url)
    diag["official_gatherer_host_valid"] = p.scheme == "https" and p.hostname == "gatherer.wizards.com"
    diag["exact_face_slug_valid"] = v2.detail_url_matches_face(final_url, spec["face"])
    if not diag["official_gatherer_host_valid"] or not diag["exact_face_slug_valid"]:
        diag["failure_stage"] = "LEGACY_FLIP_FINAL_URL_NOT_EXACT_CURRENT_GATHERER_FACE"
        return None, diag
    visible = base.visible_text(body)
    parsed, previews = _extract_legacy_flip_face(visible, spec["face"])
    diag["visible_text_sha256"] = base.sha256_bytes(visible.encode("utf-8"))
    diag["visible_text_byte_count"] = len(visible.encode("utf-8"))
    diag["exact_legacy_flip_parse"] = bool(parsed)
    if not parsed:
        # Small bounded diagnostics make layout drift debuggable without
        # retaining the raw official page as a repository artifact.
        diag["bounded_context_previews"] = previews
        diag["failure_stage"] = "EXACT_LEGACY_FLIP_FACE_PARSE_FAILED"
        return None, diag
    return parsed, diag


def _legacy_flip_face_result(identity_record: dict, spec: dict = LEGACY_FLIP_FALLBACK) -> tuple[dict | None, dict]:
    primary = next(
        (f for f in identity_record.get("faces", [])
         if f.get("requested_face_name") == spec["primary_face"] and f.get("acquisition_status") == "PASS"),
        None,
    )
    if not primary or not primary.get("official_gatherer_url"):
        return None, {"requested_face_name": spec["face"], "failure_stage": "PRIMARY_CURRENT_GATHERER_PASS_MISSING"}
    if urlparse(primary["official_gatherer_url"]).hostname != "gatherer.wizards.com":
        return None, {"requested_face_name": spec["face"], "failure_stage": "PRIMARY_GATHERER_HOST_INVALID"}

    parsed, diag = probe_legacy_flip_face(spec)
    if not parsed:
        return None, diag
    meta = diag["transport"]
    evidence_fragment = " | ".join([
        spec["primary_face"], spec["face"], parsed["type_line"], parsed["power_toughness"], parsed["oracle_text"]
    ])
    return {
        "requested_face_name": spec["face"],
        "search": None,
        "search_attempts": [{"mode": "CURRENT_GATHERER_EXACT_LEGACY_FLIP_FACE", "query": spec["face"], "transport": meta}],
        "detail_candidates": [spec["url"]],
        "official_gatherer_url": meta.get("final_url") or spec["url"],
        **parsed,
        "set_or_printing_used": primary.get("set_or_printing_used"),
        "collector_number": primary.get("collector_number"),
        "official_rulings": primary.get("official_rulings") or [],
        "oracle_section_sha256": base.sha256_bytes(evidence_fragment.encode("utf-8")),
        "currentness_status": "CURRENT_OFFICIAL_GATHERER_AT_RETRIEVAL",
        "retrieval_timestamp_utc": meta.get("retrieved_at_utc"),
        "raw_html_sha256": meta.get("raw_html_sha256"),
        "raw_html_byte_count": meta.get("raw_byte_count"),
        "acquisition_status": "PASS",
        "failure_reason": None,
        "authority_role": "CURRENT_OFFICIAL_GATHERER_EXACT_LEGACY_FLIP_FACE",
        "legacy_flip_probe": diag,
    }, diag


def acquire_identity(rec, delay):
    out = _original_acquire_identity(rec, delay)
    spec = LEGACY_FLIP_FALLBACK
    if rec.get("project_card_identity") != spec["project_card_identity"] or out.get("acquisition_status") == "PASS":
        return out
    replacement, diag = _legacy_flip_face_result(out, spec)
    out["legacy_flip_fallback_attempt"] = diag
    if not replacement:
        return out
    faces = list(out.get("faces") or [])
    replaced = False
    for i, face in enumerate(faces):
        if face.get("requested_face_name") == spec["face"] and face.get("acquisition_status") != "PASS":
            faces[i] = replacement
            replaced = True
            break
    if not replaced:
        out["legacy_flip_fallback_attempt"]["failure_stage"] = "TARGET_UNKNOWN_FACE_RECORD_NOT_FOUND"
        return out
    out["faces"] = faces
    if faces and all(f.get("acquisition_status") == "PASS" for f in faces):
        out["acquisition_status"] = "PASS"
        out["terminal"] = True
        out["authority_scope"] = "OFFICIAL_GATHERER_IDENTITY_AND_ORACLE_ONLY_NO_RUNTIME_CREDIT"
        alltxt = " ".join((f.get("oracle_text") or "") for f in faces)
        type_line = " // ".join(f.get("type_line") or "" for f in faces)
        out["special_structure_hints"] = base.structure_hints(alltxt, type_line, len(faces))
    return out


base.acquire_identity = acquire_identity

if __name__ == "__main__":
    raise SystemExit(base.main())

#!/usr/bin/env python3
"""WS-31 acquisition v5: official shared-card alternative-face authority.

Current Gatherer represents two observed alternative spell faces on the same
card page as the primary face rather than through separately addressable face
URLs.  The frozen WS-31 authority policy permits official Wizards release
notes/rulings, with older notes supplemental only.

A fallback can PASS only when the primary face already PASSed current Gatherer
and the official Wizards release-notes page is fetched and exactly validates
the alternative face.  Failures retain diagnostic transport/parse evidence and
remain UNKNOWN.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

import ws31_acquire_gatherer_v4 as v4

base = v4.base
_original_acquire_identity = base.acquire_identity

OFFICIAL_RELEASE_NOTE_FALLBACKS = {
    "Brazen Borrower // Petty Theft": {
        "primary_face": "Brazen Borrower",
        "face": "Petty Theft",
        "url": "https://magic.wizards.com/en/news/feature/outlaws-of-thunder-junction-release-notes",
        "mana_cost": "{1}{U}",
        "type_line": "Instant — Adventure",
        "section_anchor": "Brazen Borrower",
        "ruling_anchor": "Brazen Borrower is a creature card in every zone except the stack",
        "authority_role": "OLDER_OFFICIAL_RELEASE_NOTES_SUPPLEMENTAL_TO_CURRENT_GATHERER_SHARED_CARD",
    },
    "Inspired Skypainter // Maestro's Gift": {
        "primary_face": "Inspired Skypainter",
        "face": "Maestro's Gift",
        "url": "https://magic.wizards.com/en/news/feature/secrets-of-strixhaven-release-notes",
        "mana_cost": "{3}{U}{R}",
        "type_line": "Sorcery",
        "section_anchor": "Inspired Skypainter",
        "ruling_anchor": "The token created by Maestro's Gift copies exactly what was printed on the original creature",
        "authority_role": "CURRENT_OFFICIAL_RELEASE_NOTES_WITH_CURRENT_GATHERER_SHARED_CARD",
    },
}


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").replace("’", "'")
    return " ".join(value.split()).casefold()


def _official_release_notes(url: str | None) -> bool:
    if not url:
        return False
    p = urlparse(url)
    return (
        p.scheme == "https"
        and p.hostname == "magic.wizards.com"
        and (p.path.endswith("-release-notes") or "/release-notes" in p.path)
    )


def _extract_release_note_face(text: str, spec: dict) -> dict | None:
    flat = " ".join((text or "").split())
    low = _fold(flat)
    section_anchor = _fold(spec["section_anchor"])
    face_anchor = _fold(f'{spec["face"]} {spec["mana_cost"]} {spec["type_line"]}')
    ruling_anchor = _fold(spec["ruling_anchor"])
    section_pos = low.find(section_anchor)
    if section_pos < 0:
        return None
    face_pos = low.find(face_anchor, section_pos)
    if face_pos < 0:
        return None
    ruling_pos = low.find(ruling_anchor, face_pos)
    if ruling_pos < 0 or ruling_pos - face_pos > 2500:
        return None
    literal_header = f'{spec["face"]} {spec["mana_cost"]} {spec["type_line"]}'
    start = flat.find(literal_header)
    if start < 0:
        alt_header = literal_header.replace("'", "’")
        start = flat.find(alt_header)
        if start < 0:
            return None
        literal_header = alt_header
    start += len(literal_header)
    end = flat.find(spec["ruling_anchor"], start)
    if end < 0:
        end = flat.find(spec["ruling_anchor"].replace("'", "’"), start)
    if end < 0 or end - start > 2200:
        return None
    oracle = flat[start:end].strip(" :-•")
    if not oracle or spec["face"].casefold() in oracle[:30].casefold():
        return None
    if "Card-Specific Notes" in oracle or "CARD-SPECIFIC NOTES" in oracle:
        return None
    return {"oracle_text": oracle}


def probe_release_note(spec: dict) -> tuple[dict | None, dict]:
    body, meta = base.fetch(spec["url"])
    diag = {
        "requested_face_name": spec["face"],
        "requested_url": spec["url"],
        "transport": meta,
        "official_release_notes_host_path_valid": False,
        "exact_face_parse": False,
        "failure_stage": None,
    }
    if not meta or meta.get("http_status") != 200:
        diag["failure_stage"] = "RELEASE_NOTES_HTTP_FAILURE"
        return None, diag
    final_url = meta.get("final_url") or spec["url"]
    diag["official_release_notes_host_path_valid"] = _official_release_notes(final_url)
    if not diag["official_release_notes_host_path_valid"]:
        diag["failure_stage"] = "RELEASE_NOTES_FINAL_URL_NOT_CANONICAL_WIZARDS"
        return None, diag
    text = base.visible_text(body)
    parsed = _extract_release_note_face(text, spec)
    diag["visible_text_sha256"] = base.sha256_bytes(text.encode("utf-8"))
    diag["visible_text_byte_count"] = len(text.encode("utf-8"))
    diag["exact_face_parse"] = bool(parsed)
    if not parsed:
        diag["failure_stage"] = "EXACT_RELEASE_NOTE_FACE_PARSE_FAILED"
        return None, diag
    return parsed, diag


def _release_note_face_result(identity_record: dict, spec: dict) -> tuple[dict | None, dict]:
    primary = next(
        (f for f in identity_record.get("faces", [])
         if f.get("requested_face_name") == spec["primary_face"] and f.get("acquisition_status") == "PASS"),
        None,
    )
    if not primary or not primary.get("official_gatherer_url"):
        return None, {"requested_face_name": spec["face"], "failure_stage": "PRIMARY_CURRENT_GATHERER_PASS_MISSING"}
    if urlparse(primary["official_gatherer_url"]).hostname != "gatherer.wizards.com":
        return None, {"requested_face_name": spec["face"], "failure_stage": "PRIMARY_GATHERER_HOST_INVALID"}

    parsed, diag = probe_release_note(spec)
    if not parsed:
        return None, diag
    meta = diag["transport"]
    colors = sorted(set(x.upper() for x in re.findall(r"\{([WUBRG])\}", spec["mana_cost"], flags=re.I)))
    evidence_fragment = " | ".join([
        spec["primary_face"], spec["face"], spec["mana_cost"], spec["type_line"], parsed["oracle_text"]
    ])
    return {
        "requested_face_name": spec["face"],
        "search": None,
        "search_attempts": [{"mode": "OFFICIAL_WIZARDS_RELEASE_NOTES_SHARED_CARD_FALLBACK", "query": spec["face"], "transport": meta}],
        "detail_candidates": [primary["official_gatherer_url"], meta.get("final_url") or spec["url"]],
        "official_gatherer_url": primary["official_gatherer_url"],
        "official_release_notes_url": meta.get("final_url") or spec["url"],
        "shared_primary_gatherer_representation": True,
        "shared_primary_face": spec["primary_face"],
        "current_gatherer_card_name": spec["face"],
        "mana_cost": spec["mana_cost"],
        "colors": colors,
        "color_indicator": None,
        "type_line": spec["type_line"],
        "oracle_text": parsed["oracle_text"],
        "power_toughness": None,
        "loyalty": None,
        "defense": None,
        "set_or_printing_used": primary.get("set_or_printing_used"),
        "collector_number": primary.get("collector_number"),
        "official_rulings": primary.get("official_rulings") or [],
        "parse_complete": True,
        "authority_evidence_fragment_sha256": base.sha256_bytes(evidence_fragment.encode("utf-8")),
        "release_notes_raw_html_sha256": meta.get("raw_html_sha256"),
        "release_notes_raw_byte_count": meta.get("raw_byte_count"),
        "currentness_status": spec["authority_role"],
        "retrieval_timestamp_utc": meta.get("retrieved_at_utc"),
        "raw_html_sha256": meta.get("raw_html_sha256"),
        "raw_html_byte_count": meta.get("raw_byte_count"),
        "acquisition_status": "PASS",
        "failure_reason": None,
        "authority_role": spec["authority_role"],
        "release_note_probe": diag,
    }, diag


def acquire_identity(rec, delay):
    out = _original_acquire_identity(rec, delay)
    spec = OFFICIAL_RELEASE_NOTE_FALLBACKS.get(rec.get("project_card_identity"))
    if not spec or out.get("acquisition_status") == "PASS":
        return out
    replacement, diag = _release_note_face_result(out, spec)
    out["official_release_note_fallback_attempt"] = diag
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
        out["official_release_note_fallback_attempt"]["failure_stage"] = "TARGET_UNKNOWN_FACE_RECORD_NOT_FOUND"
        return out
    out["faces"] = faces
    statuses = [f.get("acquisition_status") for f in faces]
    if faces and all(s == "PASS" for s in statuses):
        out["acquisition_status"] = "PASS"
        out["terminal"] = True
        out["authority_scope"] = "OFFICIAL_GATHERER_PLUS_OFFICIAL_WIZARDS_RELEASE_NOTES_IDENTITY_AND_ORACLE_ONLY_NO_RUNTIME_CREDIT"
        alltxt = " ".join((f.get("oracle_text") or "") for f in faces)
        type_line = " // ".join(f.get("type_line") or "" for f in faces)
        out["special_structure_hints"] = base.structure_hints(alltxt, type_line, len(faces))
    return out


base.acquire_identity = acquire_identity

if __name__ == "__main__":
    raise SystemExit(base.main())

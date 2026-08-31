#!/usr/bin/env python3
"""WS-31 acquisition v6: exact current-Gatherer legacy flip-face reconciliation.

Current Gatherer exposes Faithful Squire / Kaiso, Memory of Loyalty as two
public BOK #3 URLs with complementary legacy layouts: the exact Kaiso URL
establishes the reverse-face identity/printing/P-T, while the exact Faithful
Squire URL embeds the Kaiso type and rules text in the combined flip-card
rules block.  This layer reconciles only those two current official pages.

PASS is possible only for the exact project identity and only when both URLs
return HTTP 200 on gatherer.wizards.com, both final slugs exactly match their
requested faces, the reverse page identifies Kaiso and its P/T/printing, the
primary page yields a bounded exact Kaiso type/P-T/rules block, and both P/T
values agree.  No secondary source or hard-coded Oracle text is used.
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
    "primary_url": "https://gatherer.wizards.com/BOK/en-us/3/faithful-squire",
    "face": "Kaiso, Memory of Loyalty",
    "url": "https://gatherer.wizards.com/BOK/en-us/3/kaiso-memory-of-loyalty",
}


def _extract_legacy_flip_face(text: str, face: str) -> tuple[dict | None, list[str]]:
    """Extract an unlabeled embedded lower-half rules block from current Gatherer."""
    flat = " ".join((text or "").split())
    starts = [m.start() for m in re.finditer(re.escape(face), flat, flags=re.I)]
    previews: list[str] = []
    for pos in starts[:12]:
        window = flat[pos:pos + 2200]
        previews.append(window[:800])
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
        return {
            "current_gatherer_card_name": face,
            "type_line": type_line,
            "oracle_text": oracle,
            "power_toughness": pt,
            "loyalty": None,
            "defense": None,
            "parse_complete": True,
        }, previews
    return None, previews


def _extract_reverse_identity_fields(text: str, face: str) -> dict | None:
    """Read only labeled fields actually present on the exact reverse-face URL."""
    flat = " ".join((text or "").split())
    marker = "Printed Oracle Card Name"
    start = flat.casefold().find(marker.casefold())
    if start < 0:
        return None
    section = flat[start:]
    name = base.val_between(section, base.LABELS, ["Alternative Name", "Mana Cost", "Color Indicator", "Type", "Rarity", "rules Text"])
    if not name or v2.match_norm(name) != v2.match_norm(face):
        return None
    mana = base.val_between(section, ["Mana Cost"], ["Color Indicator", "Type", "Rarity", "rules Text"])
    pt = base.val_between(section, ["P/T"], ["Loyalty", "Defense", "Set ", "Language", "printings"])
    set_text = base.val_between(section, ["Set "], ["Number", "Language", "printings"])
    collector = base.val_between(section, ["Number"], ["Language", "printings"])
    if not pt or not set_text or not collector:
        return None
    return {
        "current_gatherer_card_name": name,
        "mana_cost": mana,
        "power_toughness": " ".join(pt.split()),
        "set_or_printing_used": set_text,
        "collector_number": collector,
    }


def _exact_current_gatherer_fetch(url: str, face: str) -> tuple[bytes | None, dict | None, str | None]:
    body, meta = base.fetch(url)
    if not meta or meta.get("http_status") != 200:
        return None, meta, "HTTP_FAILURE"
    final_url = meta.get("final_url") or url
    p = urlparse(final_url)
    if p.scheme != "https" or p.hostname != "gatherer.wizards.com":
        return None, meta, "HOST_FAILURE"
    if not v2.detail_url_matches_face(final_url, face):
        return None, meta, "EXACT_SLUG_FAILURE"
    return body, meta, None


def probe_legacy_flip_face(spec: dict = LEGACY_FLIP_FALLBACK) -> tuple[dict | None, dict]:
    diag = {
        "requested_face_name": spec["face"],
        "reverse_requested_url": spec["url"],
        "primary_requested_url": spec["primary_url"],
        "failure_stage": None,
    }

    reverse_body, reverse_meta, err = _exact_current_gatherer_fetch(spec["url"], spec["face"])
    diag["reverse_transport"] = reverse_meta
    if err:
        diag["failure_stage"] = f"REVERSE_{err}"
        return None, diag
    reverse_visible = base.visible_text(reverse_body)
    reverse_fields = _extract_reverse_identity_fields(reverse_visible, spec["face"])
    diag["reverse_visible_text_sha256"] = base.sha256_bytes(reverse_visible.encode("utf-8"))
    diag["reverse_identity_fields_valid"] = bool(reverse_fields)
    if not reverse_fields:
        diag["failure_stage"] = "REVERSE_LABELED_IDENTITY_FIELDS_INVALID"
        return None, diag

    primary_body, primary_meta, err = _exact_current_gatherer_fetch(spec["primary_url"], spec["primary_face"])
    diag["primary_transport"] = primary_meta
    if err:
        diag["failure_stage"] = f"PRIMARY_{err}"
        return None, diag
    primary_visible = base.visible_text(primary_body)
    embedded, previews = _extract_legacy_flip_face(primary_visible, spec["face"])
    diag["primary_visible_text_sha256"] = base.sha256_bytes(primary_visible.encode("utf-8"))
    diag["embedded_flip_rules_valid"] = bool(embedded)
    if not embedded:
        diag["bounded_primary_context_previews"] = previews
        diag["failure_stage"] = "PRIMARY_EMBEDDED_FLIP_RULES_INVALID"
        return None, diag

    reverse_pt = re.sub(r"\s+", "", reverse_fields["power_toughness"])
    embedded_pt = re.sub(r"\s+", "", embedded["power_toughness"])
    diag["power_toughness_agrees"] = reverse_pt == embedded_pt
    if not diag["power_toughness_agrees"]:
        diag["failure_stage"] = "REVERSE_PRIMARY_PT_MISMATCH"
        return None, diag

    # Both pages are the same BOK collector-number printing.  Require those
    # exact public URL path components in addition to the parsed reverse fields.
    diag["same_printing_path"] = (
        urlparse(reverse_meta.get("final_url") or spec["url"]).path.split("/")[:4]
        == urlparse(primary_meta.get("final_url") or spec["primary_url"]).path.split("/")[:4]
    )
    if not diag["same_printing_path"]:
        diag["failure_stage"] = "CURRENT_GATHERER_PRINTING_PATH_MISMATCH"
        return None, diag

    parsed = {
        **embedded,
        "mana_cost": reverse_fields.get("mana_cost"),
        "colors": [],
        "color_indicator": None,
        "set_or_printing_used": reverse_fields["set_or_printing_used"],
        "collector_number": reverse_fields["collector_number"],
    }
    return parsed, diag


def _legacy_flip_face_result(identity_record: dict, spec: dict = LEGACY_FLIP_FALLBACK) -> tuple[dict | None, dict]:
    primary = next(
        (f for f in identity_record.get("faces", [])
         if f.get("requested_face_name") == spec["primary_face"] and f.get("acquisition_status") == "PASS"),
        None,
    )
    if not primary or not primary.get("official_gatherer_url"):
        return None, {"requested_face_name": spec["face"], "failure_stage": "PRIMARY_CURRENT_GATHERER_PASS_MISSING"}
    if v2.match_norm(urlparse(primary["official_gatherer_url"]).path.rstrip("/").split("/")[-1].replace("-", " ")) != v2.match_norm(spec["primary_face"]):
        return None, {"requested_face_name": spec["face"], "failure_stage": "PRIMARY_LOCKED_FACE_SLUG_MISMATCH"}

    parsed, diag = probe_legacy_flip_face(spec)
    if not parsed:
        return None, diag
    reverse_meta = diag["reverse_transport"]
    primary_meta = diag["primary_transport"]
    evidence_fragment = " | ".join([
        spec["primary_face"], spec["face"], parsed["type_line"], parsed["power_toughness"], parsed["oracle_text"]
    ])
    return {
        "requested_face_name": spec["face"],
        "search": None,
        "search_attempts": [
            {"mode": "CURRENT_GATHERER_EXACT_LEGACY_FLIP_REVERSE", "query": spec["face"], "transport": reverse_meta},
            {"mode": "CURRENT_GATHERER_EXACT_LEGACY_FLIP_PRIMARY_EMBEDDED_RULES", "query": spec["primary_face"], "transport": primary_meta},
        ],
        "detail_candidates": [spec["url"], spec["primary_url"]],
        "official_gatherer_url": reverse_meta.get("final_url") or spec["url"],
        **parsed,
        "official_rulings": primary.get("official_rulings") or [],
        "oracle_section_sha256": base.sha256_bytes(evidence_fragment.encode("utf-8")),
        "currentness_status": "CURRENT_OFFICIAL_GATHERER_AT_RETRIEVAL",
        "retrieval_timestamp_utc": max(
            x for x in [reverse_meta.get("retrieved_at_utc"), primary_meta.get("retrieved_at_utc")] if x
        ),
        "raw_html_sha256": reverse_meta.get("raw_html_sha256"),
        "raw_html_byte_count": reverse_meta.get("raw_byte_count"),
        "primary_raw_html_sha256": primary_meta.get("raw_html_sha256"),
        "primary_raw_html_byte_count": primary_meta.get("raw_byte_count"),
        "acquisition_status": "PASS",
        "failure_reason": None,
        "authority_role": "CURRENT_OFFICIAL_GATHERER_RECONCILED_LEGACY_FLIP_FACE",
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

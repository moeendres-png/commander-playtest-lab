#!/usr/bin/env python3
"""WS-31 Gatherer acquisition hardening after full-domain diagnostic run.

This wrapper preserves the WS-31 transport/checkpoint/output contract while
removing heuristic authority matching. Detail URLs are accepted only when the
URL slug is an exact card-face name after punctuation/diacritic folding, and
vanilla/basic-land pages with no Rules Text label are valid empty Oracle text.
"""
from __future__ import annotations

import re
import time
import unicodedata
from urllib.parse import urljoin

import ws31_acquire_gatherer as base


def match_norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().replace("’", "").replace("'", "")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def query_variants(face: str) -> list[str]:
    folded = match_norm(face)
    vals = [face, folded]
    if "," in face:
        vals.append(face.replace(",", ""))
    if "'" in face or "’" in face:
        vals.append(face.replace("'", "").replace("’", ""))
    if "-" in face:
        vals.append(face.replace("-", " "))
    out = []
    for value in vals:
        value = " ".join(value.split())
        if value and value not in out:
            out.append(value)
    return out


def exact_detail_from_search(html: bytes, face: str):
    hrefs = list(dict.fromkeys(
        m.group("href") for m in base.DETAIL_RE.finditer(html.decode("utf-8", errors="replace"))
    ))
    target = match_norm(face)
    exact = [href for href in hrefs if match_norm(base.slug_norm(href)) == target]
    return (urljoin(base.BASE, exact[0]) if exact else None), hrefs[:20]


def extract_oracle_section(text: str, face: str):
    low = text.casefold()
    starts = [low.find(label.casefold()) for label in base.LABELS if low.find(label.casefold()) >= 0]
    if not starts:
        return None
    start = min(starts)
    ends = [i for marker in ("Find Articles", "Club Support") if (i := low.find(marker.casefold(), start)) > start]
    end = min(ends) if ends else min(len(text), start + 50000)
    section = text[start:end].strip()
    if match_norm(face) not in match_norm(section):
        return None
    if " type " not in f" {section.casefold()} " and "rarity" not in section.casefold():
        return None
    return section


def parse_section(section: str, expected_face: str):
    name = base.val_between(section, base.LABELS, ["Alternative Name", "Mana Cost", "Color Indicator", "Type", "Rarity", "rules Text"])
    mana = base.val_between(section, ["Mana Cost"], ["Color Indicator", "Type", "Rarity", "rules Text"])
    color_indicator = base.val_between(section, ["Color Indicator"], ["Type", "Rarity", "rules Text"])
    type_line = base.val_between(section, ["Type"], ["Rarity", "rules Text"])
    has_rules_label = "rules text" in section.casefold()
    oracle = base.val_between(section, ["rules Text"], ["Flavor Text", "Artist", "P/T", "Loyalty", "Defense", "Set "]) if has_rules_label else ""
    if has_rules_label and oracle is None:
        oracle = ""
    pt = base.val_between(section, ["P/T"], ["Loyalty", "Defense", "Set ", "Language", "printings"])
    loyalty = base.val_between(section, ["Loyalty"], ["Defense", "Set ", "Language", "printings"])
    defense = base.val_between(section, ["Defense"], ["Set ", "Language", "printings"])
    set_text = base.val_between(section, ["Set "], ["Number", "Language", "printings"])
    collector = base.val_between(section, ["Number"], ["Language", "printings"])
    rulings = []
    rp = section.casefold().find("rulings")
    if rp >= 0:
        tail = section[rp + len("rulings"):]
        for m in re.finditer(r"\(\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})\s*\)\s*(.*?)(?=\(\s*[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}\s*\)|$)", tail, re.S):
            rulings.append({"date": m.group(1), "text": " ".join(m.group(2).split())})
    syms = re.findall(r"\{([WUBRGC])\}", mana or "", re.I)
    colors = sorted(set(x.upper() for x in syms if x.upper() in "WUBRG"))
    if color_indicator:
        for word, color in [("white", "W"), ("blue", "U"), ("black", "B"), ("red", "R"), ("green", "G")]:
            if word in color_indicator.casefold():
                colors = sorted(set(colors + [color]))
    complete = bool(name and match_norm(name) == match_norm(expected_face) and type_line and oracle is not None)
    return {
        "current_gatherer_card_name": name,
        "mana_cost": mana,
        "colors": colors,
        "color_indicator": color_indicator,
        "type_line": type_line,
        "oracle_text": oracle,
        "power_toughness": pt,
        "loyalty": loyalty,
        "defense": defense,
        "set_or_printing_used": set_text,
        "collector_number": collector,
        "official_rulings": rulings,
        "parse_complete": complete,
    }


def acquire_face(face: str, delay: float):
    searches = []
    detail = None
    candidates = []
    for query in query_variants(face):
        body, meta = base.fetch(base.search_url(query))
        searches.append({"query": query, "transport": meta})
        if meta and meta.get("http_status") == 200:
            detail, found = exact_detail_from_search(body, face)
            candidates.extend(found)
            if detail:
                break
        time.sleep(delay)
    out = {
        "requested_face_name": face,
        "search": searches[0]["transport"] if searches else None,
        "search_attempts": searches,
        "detail_candidates": list(dict.fromkeys(candidates))[:30],
        "official_gatherer_url": detail,
        "acquisition_status": "UNKNOWN",
        "failure_reason": None,
    }
    if not detail:
        out["failure_reason"] = "NO_EXACT_PUBLIC_GATHERER_DETAIL_URL"
        return out, None, []
    time.sleep(delay)
    db, dm = base.fetch(detail)
    out["detail_transport"] = dm
    if not dm or dm.get("http_status") != 200:
        out["failure_reason"] = "GATHERER_DETAIL_HTTP_FAILURE"
        return out, db, []
    section = extract_oracle_section(base.visible_text(db), face)
    if not section:
        out["failure_reason"] = "VALIDATED_ORACLE_SECTION_NOT_FOUND"
        return out, db, []
    fields = parse_section(section, face)
    out.update(fields)
    out["oracle_section_sha256"] = base.sha256_bytes(" ".join(section.split()).encode("utf-8"))
    out["currentness_status"] = "CURRENT_OFFICIAL_GATHERER_AT_RETRIEVAL"
    out["retrieval_timestamp_utc"] = dm.get("retrieved_at_utc")
    out["raw_html_sha256"] = dm.get("raw_html_sha256")
    out["raw_html_byte_count"] = dm.get("raw_byte_count")
    if fields["parse_complete"]:
        out["acquisition_status"] = "PASS"
    else:
        out["failure_reason"] = "OFFICIAL_PAGE_PRESENT_BUT_REQUIRED_FIELDS_INCOMPLETE"
    return out, db, []


base.extract_oracle_section = extract_oracle_section
base.parse_section = parse_section
base.acquire_face = acquire_face
base.same_printing_siblings = lambda _html, _detail_url: []


if __name__ == "__main__":
    raise SystemExit(base.main())

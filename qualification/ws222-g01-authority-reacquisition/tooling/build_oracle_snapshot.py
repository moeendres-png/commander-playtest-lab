#!/usr/bin/env python3
"""WS222 Oracle field snapshot builder (offline, deterministic).

Reads artifacts/oracle/ORACLE_ACQUISITION_RECEIPT.json + pages/*.html,
extracts the authoritative official fields per denominator identity into a
canonical JSON snapshot with its own SHA-256. Authority remains the official
page bytes; the snapshot is a deterministic projection for machine use and
repeatability comparison (page shells carry rotating nonces/promos, so live
re-fetch byte equality is NOT claimed; field equality is).

Extracted per identity: canonical URL, page SHA, main printing identity
(resourceId, multiverseId, setCode, setName, cardNumber), per-face Oracle
function (oracleName, oracleManaText, oracleTypeLine, oracleText full,
power/toughness), Commander legality, rulings list, related printings count.
"""

import hashlib
import json
import os
import re
import sys


def _unescape(s: str) -> str:
    # Flight data escapes (deterministic, ASCII-only handling so non-ASCII
    # Oracle characters such as U+2212 loyalty minus pass through untouched;
    # a blanket unicode_escape decode would mojibake them -- WS222 finding).
    s = s.replace('\\\\"', '"').replace('\\"', '"')
    s = s.replace("\\\\n", "\n").replace("\\n", "\n")
    s = s.replace("\\\\t", "\t").replace("\\t", "\t")
    s = s.replace("\\\\/", "/").replace("\\/", "/")
    s = re.sub(r"\\\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
    s = s.replace("\\\\", "\\")
    return s


def parse_page(text: str) -> dict:
    names = sorted(set(re.findall(r'oracleName\\?\"?:\\?\"([^"\\]+)', text)))
    if not names:
        raise RuntimeError("no oracleName markers")
    main = re.search(
        r'\\"card\\?\":\{\\"resourceId\\?\":\\?\"([0-9A-F]{32})\\?\",\\"multiverseId\\?\":(\d+)',
        text,
    )
    setm = re.search(
        r'\\"setCode\\?\":\\?\"([A-Z0-9]+)\\?\",\\"setName\\?\":\\?\"(.*?)\\?\",\\"artistName',
        text,
    )
    numm = re.search(r'\\"cardNumber\\?\":\\?\"([^"\\]+)', text)
    # full oracleText values (escaped; repeats across related printings).
    # Terminator must be a known following oracle* field key: a bare "oracle"
    # terminator over-matches into i18n/UI string tables (WS222 finding).
    raw_texts = re.findall(
        r"oracleText\\?\"?:\\?\"(.*?)\\?\",\\?\"oracle(Toughness|Type|Types|ManaText|Subtype|Subtypes|Supertypes|Power|Name)",
        text,
    )
    texts = []
    for rt, _k in raw_texts:
        t = _unescape(rt)
        if t not in texts:
            texts.append(t)
    raw_mana = re.findall(r'oracleManaText\\?\"?:\\?\"([^"\\]*)', text)
    mana = sorted(set(_unescape(m) for m in raw_mana))
    raw_type = re.findall(r'oracleTypeLine\\?\"?:\\?\"([^"\\]*)', text)
    types = sorted(set(_unescape(x) for x in raw_type))
    # rulings: pairs (date, statement)
    raw_rul = re.findall(
        r'rulingDate\\?\"?:\\?\"([^"\\]+)\\?\",\\"rulingStatement\\?\":\\?\"(.*?)\\?\"\}',
        text,
    )
    rulings = [{"date": d, "statement": _unescape(s)} for d, s in raw_rul]
    # dedupe rulings preserving order
    seen, uniq = set(), []
    for r in rulings:
        k = (r["date"], r["statement"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    # Commander legality from main block region (first formatLegalities)
    cmd = None
    fm = re.search(r"formatLegalities\\?\":\[(.*?)\]", text, re.S)
    if fm:
        pairs = re.findall(
            r'formatName\\?\"?:\\?\"([^"\\]+)\\?\",\\"legality\\?\":\\?\"([^"\\]+)', fm.group(1)
        )
        leg = {a: b for a, b in pairs}
        cmd = leg.get("Commander")
    return {
        "oracle_names_observed": names,
        "main_resource_id": main.group(1) if main else None,
        "main_multiverse_id": main.group(2) if main else None,
        "set_code": setm.group(1) if setm else None,
        "set_name": _unescape(setm.group(2)) if setm else None,
        "card_number": numm.group(1) if numm else None,
        "oracle_texts_distinct": texts,
        "oracle_mana_texts": mana,
        "oracle_type_lines": types,
        "commander_legality": cmd,
        "rulings": uniq,
    }


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--oracle-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    with open(
        os.path.join(args.oracle_dir, "ORACLE_ACQUISITION_RECEIPT.json"), encoding="utf-8"
    ) as f:
        receipt = json.load(f)
    snap_records = []
    for rec in receipt["records"]:
        page_path = os.path.join(args.oracle_dir, rec["page_file"])
        with open(page_path, "rb") as f:
            data = f.read()
        sha = hashlib.sha256(data).hexdigest()
        if sha != rec["page_sha256"]:
            print(f"BYTE_MISMATCH {rec['denominator_identity']}", file=sys.stderr)
            return 1
        fields = parse_page(data.decode("utf-8", errors="replace"))
        snap_records.append(
            {
                "denominator_identity": rec["denominator_identity"],
                "face": rec.get("face", "front"),
                "official_canonical_url": rec["official_canonical_url"],
                "page_file": rec["page_file"],
                "page_sha256": sha,
                "bridge": rec["bridge"],
                "official_fields": fields,
                "retrieved_at": rec["retrieved_at"],
            }
        )
    snap = {
        "schema_version": "ws222-oracle-field-snapshot/1.0.0",
        "authority": "Wizards Gatherer (official card database); snapshot is a deterministic projection of official page bytes",
        "denominator_count": len({r["denominator_identity"] for r in snap_records}),
        "page_count": len(snap_records),
        "records": sorted(snap_records, key=lambda r: (r["denominator_identity"], r["face"])),
    }
    blob = json.dumps(snap, indent=2, sort_keys=True, ensure_ascii=False)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(blob + "\n")
    print(
        json.dumps(
            {
                "records": len(snap_records),
                "snapshot_sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
                "out": args.out,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

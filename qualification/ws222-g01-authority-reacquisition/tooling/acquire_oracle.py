#!/usr/bin/env python3
"""WS222 bounded official Gatherer Oracle capture (Model B).

Authority: https://gatherer.wizards.com per-card pages (official card
database). Secondary bridge (api.scryfall.com) is DISCOVERY ONLY: it supplies
a pointer (related_uris.gatherer multiverseid) which the official redirect
chain then resolves to the canonical Gatherer 2.0 URL. Authority bytes are
always the official page bytes; secondary text is never written as authority.

Allowlist: gatherer.wizards.com (authority), api.scryfall.com (discovery
pointer only). No credentials. Redirect chain recorded. Atomic writes.
SHA-256 over exact page bytes. Sanity fails closed on homepage fallback
(search miss), missing oracleName markers, or name mismatch. Verify mode +
offline verify from captured bytes.

Usage:
  acquire_oracle.py --names-file <json list> --out-dir <dir> [--delay 1.5]
  acquire_oracle.py --out-dir <dir> --verify-only
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import UTC

AUTHORITY_HOST = "gatherer.wizards.com"
BRIDGE_HOST = "api.scryfall.com"
UA = "Commander-Simulator-Next WS222 bounded Oracle capture (contact: project)"


def _host(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower()


def _fetch(url: str, allowed: set, accept: str = "text/html", timeout: int = 60):
    if _host(url) not in allowed:
        raise RuntimeError(f"host not allowed: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return {
            "status": r.status,
            "final_url": r.geturl(),
            "headers": dict(r.headers.items()),
            "bytes": r.read(),
        }


def _atomic_write(path: str, data: bytes) -> None:
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-oracle-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass


def _slug(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def bridge_pointer(name: str) -> dict:
    """Discovery only: Scryfall named -> related_uris.gatherer (old URL).

    Fallback (deterministic): if the default printing carries no Gatherer
    pointer (newer printings sometimes lack one), follow prints_search_uri in
    returned order and take the first printing that does. The pointer is only
    an official-URL resolver; authority bytes are always Gatherer's.
    """
    url = "https://api.scryfall.com/cards/named?exact=" + urllib.parse.quote(name)
    res = _fetch(url, {BRIDGE_HOST}, "application/json")
    if res["status"] != 200:
        raise RuntimeError(f"bridge status {res['status']} for {name}")
    doc = json.loads(res["bytes"].decode("utf-8"))
    gatherer = (doc.get("related_uris") or {}).get("gatherer")
    used = {
        "scryfall_set": doc.get("set"),
        "scryfall_collector_number": doc.get("collector_number"),
    }
    fallback_used = False
    if not gatherer:
        prints_uri = doc.get("prints_search_uri")
        if not prints_uri:
            raise RuntimeError(f"bridge returned no gatherer pointer for {name}")
        if _host(prints_uri) != BRIDGE_HOST:
            raise RuntimeError("bridge prints host unexpected")
        pres = _fetch(prints_uri, {BRIDGE_HOST}, "application/json")
        prints = json.loads(pres["bytes"].decode("utf-8")).get("data", [])
        for p in prints:
            g = (p.get("related_uris") or {}).get("gatherer")
            if g:
                gatherer = g
                used = {
                    "scryfall_set": p.get("set"),
                    "scryfall_collector_number": p.get("collector_number"),
                }
                fallback_used = True
                break
    if not gatherer:
        raise RuntimeError(f"bridge returned no gatherer pointer for {name}")
    faces = [f.get("name") for f in (doc.get("card_faces") or []) if f.get("name")]
    return {
        "scryfall_set": used["scryfall_set"],
        "scryfall_collector_number": used["scryfall_collector_number"],
        "gatherer_pointer": gatherer,
        "scryfall_faces": faces,
        "bridge_fallback_to_older_printing": fallback_used,
    }


def extract_official_fields(page_text: str) -> dict:
    """Extract official Oracle fields from Gatherer 2.0 flight data.

    Returns per-face records keyed by oracleName with oracleText,
    oracleManaText, oracleTypeLine, resourceId, multiverseId context.
    Raises on missing markers (fail closed).
    """
    names = re.findall(r'oracleName\\?\"?:\\?\"([^"\\]+)', page_text)
    if not names:
        raise RuntimeError("no oracleName markers in official page")
    # resourceIds and multiverseIds in order (composite back-face ids are 64-hex)
    rids = re.findall(r"resourceId\\?\"?:\\?\"([0-9A-F]{32,64})", page_text)
    mids = re.findall(r"multiverseId\\?\"?:(\d+)", page_text)
    # main card block: "card":{"resourceId":"...","multiverseId":N,...
    main = re.search(
        r'\\"card\\?\":\{\\"resourceId\\?\":\\?\"([0-9A-F]{32})\\?\",\\"multiverseId\\?\":(\d+)',
        page_text,
    )
    # per-face oracleText occurrences (escaped). Terminator must be a known
    # following oracle* field key; a bare "oracle" terminator over-matches
    # into i18n/UI string tables (WS222 finding: polluted extraction).
    texts = re.findall(
        r"oracleText\\?\"?:\\?\"(.*?)\\?\",\\?\"oracle(Toughness|Type|Types|ManaText|Subtype|Subtypes|Supertypes|Power|Name)",
        page_text,
    )
    texts = [v for v, _k in texts]
    # MDFC back-face linkage (compositeCard): front page carries the back
    # face's printing identity but not its Oracle text; the back face has its
    # own canonical slug URL under the same set+number.
    mdfc = []
    for m in re.finditer(
        r'\\"compositeCard\\?\":\{\\"cardNumber\\?\":\\?\"([^"\\]+)\\?\",\\"compositeType\\?\":\\?\"Doublefaced\\?\",\\"instanceName\\?\":\\?\"([^"\\]+)\\?\",\\"languageCode\\?\":\\?\"en-us\\?\",\\"oracleName\\?\":\\?\"([^"\\]+)\\?\",\\"resourceId\\?\":\\?\"([0-9A-F]{32,64})\\?\",\\"setCode\\?\":\\?\"([A-Z0-9]+)',
        page_text,
    ):
        mdfc.append(
            {
                "card_number": m.group(1),
                "instance_name": m.group(2),
                "oracle_name": m.group(3),
                "resource_id": m.group(4),
                "set_code": m.group(5),
            }
        )
    # dedupe preserving order
    seen, uniq_mdfc = set(), []
    for e in mdfc:
        k = (e["oracle_name"], e["resource_id"])
        if k not in seen:
            seen.add(k)
            uniq_mdfc.append(e)
    return {
        "oracle_names_observed": sorted(set(names)),
        "resource_ids_observed": sorted(set(rids)),
        "multiverse_ids_observed": sorted(set(mids)),
        "main_resource_id": main.group(1) if main else None,
        "main_multiverse_id": main.group(2) if main else None,
        "oracle_text_samples": [t[:400] for t in texts[:6]],
        "oracle_text_occurrences": len(texts),
        "mdfc_back_faces": uniq_mdfc,
    }


def capture_one(name: str, out_dir: str, delay: float = 1.5) -> dict:
    from datetime import datetime

    retrieved_at = datetime.now(UTC).isoformat()
    ptr = bridge_pointer(name)
    time.sleep(delay)
    # Official resolution: old multiverseid URL -> canonical 2.0 URL.
    official = _fetch(ptr["gatherer_pointer"], {AUTHORITY_HOST})
    if official["status"] != 200:
        raise RuntimeError(f"official status {official['status']} for {name}")
    final = official["final_url"]
    data = official["bytes"]
    text = data.decode("utf-8", errors="replace")
    # fail closed on homepage fallback (search miss renders homepage shell)
    if final.rstrip("/") == "https://gatherer.wizards.com":
        raise RuntimeError(f"official resolution fell back to homepage for {name}")
    if len(data) < 50_000:
        raise RuntimeError(f"official page suspiciously small for {name}: {len(data)}")
    fields = extract_official_fields(text)
    # name match: expected front-face (or full "A // B") must appear among
    # observed oracle names; split/MDFC pages expose per-face names.
    fronts = [name] + [p.strip() for p in name.split("//")]
    if not any(f in fields["oracle_names_observed"] for f in fronts):
        raise RuntimeError(
            f"oracleName mismatch for {name}: observed {fields['oracle_names_observed'][:8]}"
        )
    sha = hashlib.sha256(data).hexdigest()
    safe = _slug(name)
    page_file = f"gatherer_{safe}.html"
    _atomic_write(os.path.join(out_dir, "pages", page_file), data)
    record = {
        "denominator_identity": name,
        "face": "front",
        "bridge": {"role": "discovery_pointer_only", **ptr},
        "official_request_url": ptr["gatherer_pointer"],
        "official_canonical_url": final,
        "page_file": f"pages/{page_file}",
        "page_size": len(data),
        "page_sha256": sha,
        "page_content_type": official["headers"].get("Content-Type"),
        "official_fields": fields,
        "retrieved_at": retrieved_at,
    }
    return record


def acquire(names: list, out_dir: str, delay: float = 1.5) -> dict:
    from datetime import datetime

    os.makedirs(os.path.join(out_dir, "pages"), exist_ok=True)
    records = []
    for n in names:
        rec = capture_one(n, out_dir, delay=delay)
        records.append(rec)
        print(f"CAPTURED {n} -> {rec['official_canonical_url']} {rec['page_sha256'][:12]}")
        time.sleep(delay)
    receipt = {
        "schema_version": "ws222-oracle-receipt/1.0.0",
        "model": "B_bounded_official_gatherer_capture",
        "authority_host": AUTHORITY_HOST,
        "bridge_host": BRIDGE_HOST,
        "bridge_role": "discovery_pointer_only_never_authority",
        "denominator_count": len(records),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "records": records,
    }
    with open(os.path.join(out_dir, "ORACLE_ACQUISITION_RECEIPT.json"), "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, sort_keys=True)
        f.write("\n")
    return receipt


def verify(out_dir: str, names: list | None = None) -> dict:
    receipt_path = os.path.join(out_dir, "ORACLE_ACQUISITION_RECEIPT.json")
    with open(receipt_path, encoding="utf-8") as f:
        receipt = json.load(f)
    results = []
    ok_all = True
    for rec in receipt["records"]:
        p = os.path.join(out_dir, rec["page_file"])
        with open(p, "rb") as f:
            data = f.read()
        sha = hashlib.sha256(data).hexdigest()
        text = data.decode("utf-8", errors="replace")
        try:
            fields = extract_official_fields(text)
            match = sha == rec["page_sha256"]
        except Exception as e:
            fields = {"error": repr(e)}
            match = False
        ok = match and fields.get("oracle_names_observed")
        ok_all = ok_all and bool(ok)
        results.append(
            {
                "denominator_identity": rec["denominator_identity"],
                "expected_sha256": rec["page_sha256"],
                "actual_sha256": sha,
                "match": match,
                "canonical_url": rec["official_canonical_url"],
            }
        )
    return {"count": len(results), "all_match": ok_all, "results": results}


def ensure_back_faces(out_dir: str, delay: float = 1.5) -> dict:
    """Capture MDFC back faces for records whose front page advertises a
    Doublefaced compositeCard. Offline-safe for records without one. Updates
    the receipt in place (existing records' bytes/pins untouched)."""
    from datetime import datetime

    receipt_path = os.path.join(out_dir, "ORACLE_ACQUISITION_RECEIPT.json")
    with open(receipt_path, encoding="utf-8") as f:
        receipt = json.load(f)
    have = {(r["denominator_identity"], r.get("face", "front")) for r in receipt["records"]}
    added = []
    for rec in list(receipt["records"]):
        if rec.get("face", "front") != "front":
            continue
        with open(os.path.join(out_dir, rec["page_file"]), encoding="utf-8", errors="replace") as f:
            text = f.read()
        backs = extract_official_fields(text).get("mdfc_back_faces", [])
        for b in backs:
            if (rec["denominator_identity"], "back:" + b["oracle_name"]) in have:
                continue
            set_code = b["set_code"]
            number = b["card_number"]
            back_slug = _slug(b["oracle_name"])
            url = f"https://gatherer.wizards.com/{set_code}/en-us/{number}/{back_slug}"
            time.sleep(delay)
            official = _fetch(url, {AUTHORITY_HOST})
            if official["status"] != 200:
                raise RuntimeError(f"back-face status {official['status']} for {b['oracle_name']}")
            final = official["final_url"]
            data = official["bytes"]
            btext = data.decode("utf-8", errors="replace")
            if final.rstrip("/") == "https://gatherer.wizards.com":
                raise RuntimeError(f"back-face fell back to homepage for {b['oracle_name']}")
            bfields = extract_official_fields(btext)
            if b["oracle_name"] not in bfields["oracle_names_observed"]:
                raise RuntimeError(f"back-face name mismatch for {b['oracle_name']}")
            sha = hashlib.sha256(data).hexdigest()
            page_file = f"gatherer_{_slug(rec['denominator_identity'])}__back-{back_slug}.html"
            _atomic_write(os.path.join(out_dir, "pages", page_file), data)
            new_rec = {
                "denominator_identity": rec["denominator_identity"],
                "face": "back:" + b["oracle_name"],
                "bridge": {
                    "role": "derived_from_official_front_page_compositeCard",
                    "front_canonical_url": rec["official_canonical_url"],
                },
                "official_request_url": url,
                "official_canonical_url": final,
                "page_file": f"pages/{page_file}",
                "page_size": len(data),
                "page_sha256": sha,
                "page_content_type": official["headers"].get("Content-Type"),
                "official_fields": bfields,
                "retrieved_at": datetime.now(UTC).isoformat(),
            }
            receipt["records"].append(new_rec)
            added.append(new_rec["official_canonical_url"])
            time.sleep(delay)
    receipt["retrieved_at"] = datetime.now(UTC).isoformat()
    with open(receipt_path, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, sort_keys=True)
        f.write("\n")
    return {"added": added}


def _load_names(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--names-file", default=None)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--ensure-back-faces", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.verify_only:
            res = verify(args.out_dir)
            print(json.dumps(res, indent=2, sort_keys=True))
            return 0 if res["all_match"] else 1
        if args.ensure_back_faces:
            res = ensure_back_faces(args.out_dir, delay=args.delay)
            print(json.dumps(res, indent=2, sort_keys=True))
            v = verify(args.out_dir)
            if not v["all_match"]:
                print("VERIFY_MISMATCH", file=sys.stderr)
                return 1
            print("VERIFY_PASS")
            return 0
        if not args.names_file:
            print("names-file required for acquisition", file=sys.stderr)
            return 2
        names = _load_names(args.names_file)
        receipt = acquire(names, args.out_dir, delay=args.delay)
        print(json.dumps({"denominator_count": receipt["denominator_count"]}, indent=2))
        v = verify(args.out_dir)
        if not v["all_match"]:
            print("VERIFY_MISMATCH", file=sys.stderr)
            return 1
        print("VERIFY_PASS")
        return 0
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

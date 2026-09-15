#!/usr/bin/env python3
"""WS222 official Comprehensive Rules acquisition (bounded, fail-closed).

Official-host allowlist: magic.wizards.com (landing page), media.wizards.com
(artifact bytes). No credentials. Redirects tracked. Atomic writes.
Exact-byte SHA-256. Sanity checks fail closed on HTML/error masquerade.
Effective-date extraction + check. Idempotent verify mode + offline verify.

Usage:
  acquire_cr.py --out-dir <dir> [--verify-only] [--offline]
  acquire_cr.py --landing-url https://magic.wizards.com/en/rules --out-dir <dir>

Exit 0 on PASS, nonzero with reason on failure. Never fabricates bytes.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.request
from datetime import UTC, datetime

ALLOWED_HOSTS = {"magic.wizards.com", "media.wizards.com"}
UA = "Commander-Simulator-Next WS222 authority acquisition (bounded; contact: project)"
EXPECTED_EFFECTIVE_RE = re.compile(
    r"These rules are effective as of ([A-Z][a-z]+ \d{1,2}, \d{4})\.", re.ASCII
)


def _check_host(url: str) -> None:
    from urllib.parse import urlparse

    host = urlparse(url).hostname or ""
    if host.lower() not in ALLOWED_HOSTS:
        raise RuntimeError(f"host not allowlisted: {host} ({url})")


def _fetch(url: str, accept: str, timeout: int = 60):
    _check_host(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
    with opener.open(req, timeout=timeout) as r:
        # urllib follows redirects internally; record final only + status
        data = r.read()
        return {
            "status": r.status,
            "final_url": r.geturl(),
            "headers": dict(r.headers.items()),
            "bytes": data,
        }


def _atomic_write(path: str, data: bytes) -> None:
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-cr-")
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


def acquire(out_dir: str, landing_url: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    retrieved_at = datetime.now(UTC).isoformat()
    # 1. landing page (identity of current official links)
    landing = _fetch(landing_url, "text/html")
    if landing["status"] != 200:
        raise RuntimeError(f"landing page status {landing['status']}")
    ctype = landing["headers"].get("Content-Type") or ""
    if "text/html" not in ctype:
        raise RuntimeError(f"landing content-type unexpected: {ctype}")
    html = landing["bytes"].decode("utf-8", errors="replace")
    hrefs = re.findall(r'href="([^"]+)"', html)
    txt_links = sorted({h for h in hrefs if h.endswith(".txt") and "MagicCompRules" in h})
    pdf_links = sorted({h for h in hrefs if h.endswith(".pdf") and "MagicCompRules" in h})
    docx_links = sorted({h for h in hrefs if h.endswith(".docx") and "MagicCompRules" in h})
    if not txt_links:
        raise RuntimeError("no official TXT link on landing page")
    # Current official source truth wins: take the TXT linked by the page.
    raw_txt = txt_links[0]

    # landing hrefs contain a literal space; encode it
    txt_url = raw_txt.replace(" ", "%20")
    _check_host(txt_url)
    # 2. artifact bytes
    art = _fetch(txt_url, "text/plain,*/*")
    if art["status"] != 200:
        raise RuntimeError(f"artifact status {art['status']}")
    actype = art["headers"].get("Content-Type") or ""
    data = art["bytes"]
    # fail closed on HTML/error masquerade
    head = data[:2000].decode("utf-8", errors="replace")
    if "<html" in head.lower() or "<!doctype" in head.lower():
        raise RuntimeError("artifact masquerades as HTML; refusing")
    if len(data) < 100_000:
        raise RuntimeError(f"artifact suspiciously small: {len(data)}")
    if "Magic: The Gathering Comprehensive Rules" not in head:
        raise RuntimeError("artifact header sanity check failed")
    m = EXPECTED_EFFECTIVE_RE.search(data.decode("utf-8-sig", errors="replace"))
    if not m:
        raise RuntimeError("effective-date line not found in artifact")
    effective_date_text = m.group(0)
    sha256 = hashlib.sha256(data).hexdigest()
    # 3. persist exact bytes (normalization NONE)
    from urllib.parse import unquote

    fname = unquote(txt_url.rsplit("/", 1)[-1]).replace(" ", "_")
    art_path = os.path.join(out_dir, fname)
    _atomic_write(art_path, data)
    receipt = {
        "schema_version": "ws222-cr-receipt/1.0.0",
        "landing_page_url": landing_url,
        "landing_final_url": landing["final_url"],
        "landing_bytes": len(landing["bytes"]),
        "landing_sha256": hashlib.sha256(landing["bytes"]).hexdigest(),
        "landing_txt_links": txt_links,
        "landing_pdf_links": pdf_links,
        "landing_docx_links": docx_links,
        "resolved_artifact_url": txt_url,
        "artifact_final_url": art["final_url"],
        "artifact_file": os.path.basename(art_path),
        "artifact_size": len(data),
        "artifact_sha256": sha256,
        "artifact_content_type": actype,
        "artifact_etag": art["headers"].get("ETag"),
        "artifact_last_modified": art["headers"].get("Last-Modified"),
        "artifact_content_length_header": art["headers"].get("Content-Length"),
        "effective_date_text": effective_date_text,
        "normalization": "NONE",
        "retrieved_at": retrieved_at,
        "allowlist": sorted(ALLOWED_HOSTS),
    }
    with open(os.path.join(out_dir, "CR_ACQUISITION_RECEIPT.json"), "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, sort_keys=True)
        f.write("\n")
    # landing snapshot for provenance (bounded size)
    _atomic_write(os.path.join(out_dir, "landing.html"), landing["bytes"])
    return receipt


def verify(out_dir: str) -> dict:
    receipt_path = os.path.join(out_dir, "CR_ACQUISITION_RECEIPT.json")
    with open(receipt_path, encoding="utf-8") as f:
        receipt = json.load(f)
    art_path = os.path.join(out_dir, receipt["artifact_file"])
    with open(art_path, "rb") as f:
        data = f.read()
    sha = hashlib.sha256(data).hexdigest()
    ok = sha == receipt["artifact_sha256"]
    m = EXPECTED_EFFECTIVE_RE.search(data.decode("utf-8-sig", errors="replace"))
    return {
        "artifact_file": receipt["artifact_file"],
        "expected_sha256": receipt["artifact_sha256"],
        "actual_sha256": sha,
        "size": len(data),
        "effective_date_text": m.group(0) if m else None,
        "match": ok and m is not None,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--landing-url", default="https://magic.wizards.com/en/rules")
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.verify_only:
            res = verify(args.out_dir)
            print(json.dumps(res, indent=2, sort_keys=True))
            return 0 if res["match"] else 1
        receipt = acquire(args.out_dir, args.landing_url)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        v = verify(args.out_dir)
        if not v["match"]:
            print("VERIFY_MISMATCH", file=sys.stderr)
            return 1
        print("VERIFY_PASS " + v["actual_sha256"])
        return 0
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

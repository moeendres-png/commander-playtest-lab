#!/usr/bin/env python3
"""WS222 Commander B&R authority capture (bounded, official only).

Allowlist: magic.wizards.com. Captures the official B&R list page bytes +
the latest Commander B&R announcement bytes, extracts the Commander banned
list, writes a machine-readable receipt. No credentials. Fail closed.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import UTC, datetime

ALLOWED = {"magic.wizards.com"}
UA = "Commander-Simulator-Next WS222 B&R capture (bounded; contact: project)"
LIST_URL = "https://magic.wizards.com/en/banned-restricted-list"
CMDR_ANN_URL = "https://magic.wizards.com/en/news/announcements/commander-banned-and-restricted-february-9-2026"


def _fetch(url: str):
    from urllib.parse import urlparse

    if (urlparse(url).hostname or "").lower() not in ALLOWED:
        raise RuntimeError(f"host not allowed: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return {
            "status": r.status,
            "final_url": r.geturl(),
            "headers": dict(r.headers.items()),
            "bytes": r.read(),
        }


def _atomic(path: str, data: bytes) -> None:
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    import tempfile as tf

    fd, tmp = tf.mkstemp(dir=d, prefix=".tmp-ban-")
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


def _commander_list(page_text: str) -> list:
    i = page_text.find("Commander Banned Cards")
    if i < 0:
        raise RuntimeError("Commander section not found")
    # next section header after Commander
    j = page_text.find("<h3>", i + 10)
    seg = page_text[i : j if j > 0 else i + 20000]
    items = re.findall(r"<li>(.*?)</li>", seg, re.S)
    clean = []
    for it in items:
        it = re.sub(r"<[^>]+>", "", it)
        it = it.replace("&amp;", "&").strip()
        it = re.sub(r"\s+", " ", it)
        if it:
            clean.append(it)
    if not clean:
        raise RuntimeError("empty Commander list extraction")
    return clean


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)
    try:
        os.makedirs(args.out_dir, exist_ok=True)
        retrieved_at = datetime.now(UTC).isoformat()
        b = _fetch(LIST_URL)
        if b["status"] != 200:
            raise RuntimeError("B&R list status")
        a = _fetch(CMDR_ANN_URL)
        if a["status"] != 200:
            raise RuntimeError("announcement status")
        bt = b["bytes"].decode("utf-8", errors="replace")
        at = a["bytes"].decode("utf-8", errors="replace")
        cmd_list = _commander_list(bt)
        m_ann = re.search(r"Announcement Date</strong>:\s*([^<]+)</p>", at)
        m_eff = re.search(r"Effective date</strong>:\s*([^<]+)</p>", at)
        _atomic(os.path.join(args.out_dir, "banned-restricted-list.html"), b["bytes"])
        _atomic(
            os.path.join(args.out_dir, "commander-ban-announcement-2026-02-09.html"), a["bytes"]
        )
        receipt = {
            "schema_version": "ws222-ban-receipt/1.0.0",
            "list_url": LIST_URL,
            "list_final_url": b["final_url"],
            "list_bytes": len(b["bytes"]),
            "list_sha256": hashlib.sha256(b["bytes"]).hexdigest(),
            "announcement_url": CMDR_ANN_URL,
            "announcement_final_url": a["final_url"],
            "announcement_bytes": len(a["bytes"]),
            "announcement_sha256": hashlib.sha256(a["bytes"]).hexdigest(),
            "announcement_date": m_ann.group(1).strip() if m_ann else None,
            "announcement_effective_date": m_eff.group(1).strip() if m_eff else None,
            "commander_banned_entries": cmd_list,
            "commander_banned_named_count": sum(
                1
                for e in cmd_list
                if not e.startswith(("25 cards", "9 cards", "Cards whose", "Lutri"))
            ),
            "retrieved_at": retrieved_at,
        }
        if not receipt["announcement_date"] or not receipt["announcement_effective_date"]:
            raise RuntimeError("announcement dates not extracted")
        with open(
            os.path.join(args.out_dir, "BAN_ACQUISITION_RECEIPT.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(receipt, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

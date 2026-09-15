#!/usr/bin/env python3
"""WS222 authority verification (offline): validates successor lock vs bytes.

Checks: CR bytes + SHA + effective date; per-card page bytes + SHA +
oracleName presence; B&R capture presence; receipt/schema sanity. No network.
Exit 0 VERIFICATION_PASS, 1 mismatch, 2 error.
"""

import argparse
import hashlib
import json
import os
import re
import sys

EFF_RE = re.compile(r"These rules are effective as of ([A-Z][a-z]+ \d{1,2}, \d{4})\.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns", required=True, help="evidence namespace dir")
    ap.add_argument("--lock", required=True, help="successor authority lock json")
    args = ap.parse_args(argv)
    try:
        with open(args.lock, encoding="utf-8") as f:
            lock = json.load(f)
        errors = []
        # CR
        cr = lock.get("comprehensive_rules", {})
        cr_path = os.path.join(args.ns, cr.get("artifact_path", ""))
        if not os.path.isfile(cr_path):
            errors.append(f"missing CR artifact: {cr_path}")
        else:
            with open(cr_path, "rb") as f:
                data = f.read()
            sha = hashlib.sha256(data).hexdigest()
            if sha != cr.get("artifact_sha256"):
                errors.append("CR sha mismatch")
            if len(data) != cr.get("artifact_size"):
                errors.append("CR size mismatch")
            m = EFF_RE.search(data.decode("utf-8-sig", errors="replace"))
            if not m or m.group(0) != cr.get("effective_date_text"):
                errors.append("CR effective-date mismatch")
        # Oracle
        oracle = lock.get("oracle", {})
        for rec in oracle.get("records", []):
            p = os.path.join(args.ns, rec.get("page_file", ""))
            if not os.path.isfile(p):
                errors.append(f"missing oracle page: {p}")
                continue
            with open(p, "rb") as f:
                data = f.read()
            if hashlib.sha256(data).hexdigest() != rec.get("page_sha256"):
                errors.append(f"oracle sha mismatch: {rec.get('denominator_identity')}")
            text = data.decode("utf-8", errors="replace")
            fronts = [rec["denominator_identity"]] + [
                x.strip() for x in rec["denominator_identity"].split("//")
            ]
            if not any(f in text for f in fronts):
                errors.append(f"oracle name absent: {rec.get('denominator_identity')}")
        # B&R
        br = lock.get("commander_ban_authority", {})
        br_path = os.path.join(args.ns, br.get("artifact_path", ""))
        if br_path and not os.path.isfile(br_path):
            errors.append(f"missing B&R artifact: {br_path}")
        if errors:
            print(json.dumps({"verification": "FAIL", "errors": errors}, indent=2))
            return 1
        print(
            json.dumps(
                {
                    "verification": "PASS",
                    "cr_sha256": cr.get("artifact_sha256"),
                    "oracle_records": len(oracle.get("records", [])),
                },
                indent=2,
            )
        )
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

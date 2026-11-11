"""Network-free proof tests for the public EDHREC capture lane."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

script = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "studio_edhrec_provenance"
    / "capture_public_chulane.py"
)
spec = importlib.util.spec_from_file_location("capture_public", script)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

URL = "https://json.edhrec.com/pages/commanders/chulane-teller-of-tales/big-mana.json"
BODY = b'{"container":{"json_dict":{"cardlists":[]}}}'


class Fake(io.BytesIO):
    def __init__(self, body: bytes = BODY):
        super().__init__(body)
        self.status = 200
        self.headers = {"Date": "Wed, 11 Nov 2026 12:00:00 GMT", "ETag": '"test"'}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class SourceTest(unittest.TestCase):
    def test_allowlist_and_duplicate_sources(self):
        with self.assertRaises(ValueError):
            mod.capture_one("https://other.example.org/secret", opener=lambda *args, **kw: Fake())
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "sources.txt"
            p.write_text(URL + "\n" + URL + "\n")
            with self.assertRaises(ValueError):
                mod.read_urls(p)

    def test_http_success_creates_distinct_nonhistorical_proof(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root)
            got = mod.capture(
                [URL], out, opener=lambda *args, **kw: Fake(), sleep=lambda seconds: None
            )
            self.assertEqual(1, len(got))
            metadata = json.loads((out / got[0]["metadata"]).read_text())
            raw = (out / got[0]["raw"]).read_bytes()
            self.assertEqual(BODY, raw)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), metadata["raw_response_sha256"])
            self.assertFalse(metadata["historical_C079_timestamp_backfilled"])
            self.assertFalse(metadata["automatic_import"])
            self.assertEqual(200, metadata["http_status"])
            self.assertEqual("REVIEW_ONLY", "REVIEW_ONLY")
            self.assertEqual(1, len(json.loads((out / "manifest.json").read_text())["records"]))

    def test_http_403_fails_closed_with_no_fake_snapshot(self):
        def forbidden(*args, **kw):
            raise urllib.error.HTTPError(URL, 403, "Denied", {}, None)

        with tempfile.TemporaryDirectory() as root:
            out = Path(root)
            with self.assertRaises(RuntimeError):
                mod.capture([URL], out, opener=forbidden, sleep=lambda seconds: None)
            self.assertFalse((out / "manifest.json").exists())
            self.assertEqual([], list((out / "raw").glob("*.json")))
            self.assertEqual(
                "CAPTURE_BLOCKED_NO_HISTORICAL_PROOF",
                json.loads((out / "capture_failure.json").read_text())["status"],
            )

    def test_non_edhrec_json_cannot_be_source_evidence(self):
        with self.assertRaises(ValueError):
            mod.capture_one(URL, opener=lambda *args, **kw: Fake(b"{}"))


if __name__ == "__main__":
    unittest.main()

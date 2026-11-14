"""Reassemble the cProfile ``*.pstats`` files stored as gzip + Base64 parts here.

Each original ``*.pstats`` file was gzipped and the gzip bytes were split
into raw chunks of 79,998 bytes (a multiple of 3, so no Base64 padding lands
mid-stream); every chunk is stored Base64-encoded as ``<name>.gz.b64.pNNN``.
``MANIFEST.json`` records the original size and SHA-256, the gzip SHA-256
and the part list per file. This script decodes the parts in order, verifies
the gzip hash, gunzips and verifies size and SHA-256 of the result.

Usage: python3 reassemble_pstats.py [--data-dir DIR] [--out-dir DIR]
Defaults: data directory = this script's directory, output = data directory.
"""

import argparse
import base64
import gzip
import hashlib
import json
import sys
from pathlib import Path


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reassemble(entry: dict[str, object], data_dir: Path, out_dir: Path) -> Path:
    parts = entry["parts"]
    assert isinstance(parts, list)
    gz = b"".join(base64.b64decode((data_dir / str(p)).read_text().strip()) for p in parts)
    if sha256_hex(gz) != entry["gzip_sha256"]:
        raise SystemExit(f"gzip SHA-256 mismatch for {entry['original_file']}")
    raw = gzip.decompress(gz)
    if len(raw) != entry["original_size"]:
        raise SystemExit(f"size mismatch for {entry['original_file']}: {len(raw)}")
    if sha256_hex(raw) != entry["original_sha256"]:
        raise SystemExit(f"SHA-256 mismatch for {entry['original_file']}")
    out = out_dir / str(entry["original_file"])
    out.write_bytes(raw)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).parent)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()
    data_dir = args.data_dir
    out_dir = args.out_dir if args.out_dir is not None else data_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((data_dir / "MANIFEST.json").read_text())
    for entry in manifest["files"]:
        out = reassemble(entry, data_dir, out_dir)
        print(f"OK {out} ({entry['original_size']} bytes, sha256 {entry['original_sha256']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

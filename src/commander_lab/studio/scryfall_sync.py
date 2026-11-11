"""Download only public Scryfall Default Cards bulk metadata/data to the local data folder."""
from __future__ import annotations

import gzip
import hashlib
import json

import ijson
import os
import time
import urllib.request
from pathlib import Path

from .store import studio_data_dir

BULK_METADATA = "https://api.scryfall.com/bulk-data/default-cards"
_AGENT = "MTGCollectionDeckbuilder/0.1 (local Commander card facts; no collection upload)"


def sync_scryfall(folder: str | Path | None = None) -> dict[str, str]:
    data = Path(folder).expanduser().resolve() if folder else studio_data_dir()
    dest = data / "public" / "default-cards.jsonl.gz"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(
        urllib.request.Request(BULK_METADATA, headers={
            "User-Agent": _AGENT, "Accept": "application/json"
        }), timeout=30
    ) as response:
        metadata = json.load(response)
    url = metadata["download_uri"]
    if not str(url).startswith("https://"):
        raise ValueError("Scryfall returned non-HTTPS download_uri")
    sha = hashlib.sha256()
    temp = dest.with_suffix(".download")
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": _AGENT}), timeout=60
        ) as response, temp.open("wb") as f:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                sha.update(chunk)
                f.write(chunk)
        # Official Scryfall bulk payload is a JSON array, not JSONL. Stream
        # conversion (bounded memory) preserves each public object as a JSONL row.
        converted = dest.with_suffix(".part")
        try:
            with temp.open("rb") as source:
                source_stream = gzip.GzipFile(fileobj=source) if source.read(2) == b"\x1f\x8b" else source
                source.seek(0)
                with gzip.open(converted, "wt", encoding="utf-8") as target:
                    for item in ijson.items(source_stream, "item"):
                        target.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
            os.replace(converted, dest)
        finally:
            converted.unlink(missing_ok=True)
        chosen = dest
        stamp = {"source": BULK_METADATA, "updated_at": metadata.get("updated_at"),
                 "sha256": sha.hexdigest(), "path": str(chosen), "fetched_at": time.time()}
        (dest.parent / "scryfall-source.json").write_text(
            json.dumps(stamp, indent=2), encoding="utf-8"
        )
        return {k: str(v) for k, v in stamp.items()}
    finally:
        temp.unlink(missing_ok=True)

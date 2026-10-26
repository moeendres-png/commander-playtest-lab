"""Scheiben eines Full-Dumps mergen (record --all je 6 Seeds).

Jede Scheibe ist ein gueltiges Corpus-File (Header + Zeilen). Der Merge
haengt die Zeilen an und rechnet den Header neu (games_decisions,
Klassen, Seeds, jar_sha256 aus der ersten Scheibe). Zeilen tragen ihren
Seed, daher ist der Merge verlustfrei und reihenfolgentreu je Seed.

Verwendung: python3 merge_dumps.py OUT.gz IN1.gz IN2.gz ...
"""

from __future__ import annotations

import gzip
import json
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    out_path, in_paths = Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]]
    header: dict | None = None
    rows: list[dict] = []
    for path in in_paths:
        lines = [json.loads(line) for line in gzip.open(path, "rt", encoding="utf-8") if line.strip()]
        head, body = lines[0], lines[1:]
        if header is None:
            header = dict(head)
        assert head["corpus_version"] == header["corpus_version"]
        assert head["jar_sha256"] == header["jar_sha256"], f"anderes JAR in {path}"
        rows.extend(body)
    assert header is not None
    header["seeds"] = sorted({int(r["seed"]) for r in rows})
    header["games_decisions"] = len(rows)
    header["classes"] = dict(sorted(Counter(r["class"] for r in rows).items()))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as handle, gzip.GzipFile(
        filename="", mode="wb", fileobj=handle, mtime=0
    ) as raw:
        for item in (header, *rows):
            raw.write((json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n").encode())
    print(json.dumps(header, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

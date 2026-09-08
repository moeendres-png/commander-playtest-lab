"""WS-49 G49-13 support: static fallback-pattern inventory probe.

Mechanical reporter only. It scans the WS-49 adapter scripts and the
engine-bridge Java sources for textual markers that *may* indicate
unsupported fallback/pilot-randomness paths, and emits a deterministic JSON
inventory for authoritative (Work/Terra) adjudication.

This probe grants no gate, decides no semantics, and never fails the tree:
exit status is 0 whenever the inventory itself was produced. Every match is
a candidate for human review, not a verdict.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA = "commander-lab.ws49-fallback-zero-static-inventory/1.0.0"

CATEGORIES: dict[str, list[str]] = {
    # Explicit fallback vocabulary in provider/bridge/adapter code.
    "FALLBACK_MENTION": [r"\bfallback\b", r"\bFallback\b", r"\bFALLBACK\b"],
    # Pilot-side randomness markers (Rules randomness must stay engine-side).
    "PILOT_RANDOMNESS": [
        r"\bnew\s+Random\s*\(",
        r"\bMath\s*\.\s*random\s*\(",
        r"\bSecureRandom\b",
        r"\brandom\s*\.\s*(choice|randint|random|shuffle)\s*\(",
        r"\bnumpy\b.*\brandom\b",
    ],
    # Unfinished-work markers in the decision path.
    "UNRESOLVED_MARKER": [r"\bTODO\b", r"\bFIXME\b", r"\bHACK\b", r"\bXXX\b"],
    # Silent-skip / swallowing markers worth a human look.
    "SILENT_SKIP": [r"catch\s*\([^)]*\)\s*\{\s*\}", r"except\s+[^:]+:\s*pass\b"],
}

SCAN_GLOBS = ["*.py", "*.java"]


def _git_head(repo_root: Path) -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def iter_files(root: Path):
    for pattern in SCAN_GLOBS:
        yield from sorted(root.rglob(pattern))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo_root: Path = args.repo_root.resolve()
    scan_roots = [
        repo_root / "candidate-qualification" / "ws49-xmage-v1.0.5",
        repo_root / "engine-bridge" / "src",
    ]
    for root in scan_roots:
        if not root.is_dir():
            print(f"ERROR: scan root missing: {root}", file=sys.stderr)
            return 2

    compiled = {name: [re.compile(p) for p in patterns] for name, patterns in CATEGORIES.items()}
    matches: list[dict[str, str | int]] = []
    files_scanned = 0
    for root in scan_roots:
        for path in iter_files(root):
            if path.name == Path(__file__).name:
                continue
            files_scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="strict")
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                for category, regexes in compiled.items():
                    if any(r.search(line) for r in regexes):
                        matches.append(
                            {
                                "category": category,
                                "file": str(path.relative_to(repo_root)),
                                "line": lineno,
                                "snippet": line.strip()[:220],
                            }
                        )

    matches.sort(key=lambda m: (str(m["category"]), str(m["file"]), int(m["line"])))
    inventory = {
        "schema": SCHEMA,
        "repo_head": _git_head(repo_root),
        "scan_roots": [str(r.relative_to(repo_root)) for r in scan_roots],
        "files_scanned": files_scanned,
        "match_count": len(matches),
        "matches": matches,
        "note": (
            "Reporter only. Each match requires authoritative human "
            "adjudication; presence of a marker is not proof of a "
            "fallback path and absence is not proof of fallback-zero."
        ),
    }
    args.output.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    by_category: dict[str, int] = {}
    for m in matches:
        by_category[str(m["category"])] = by_category.get(str(m["category"]), 0) + 1
    print(
        f"files={files_scanned} matches={len(matches)} "
        f"categories={json.dumps(by_category, sort_keys=True)}"
    )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

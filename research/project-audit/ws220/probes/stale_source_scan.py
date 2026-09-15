"""WS220 probe P-SRC-01: stale-source-truth scan.

Deterministic, stdlib-only. Scans the tree for:
  1. CURRENT/FINAL/LATEST filename traps (AGENTS.md s3: names prove nothing).
  2. Live 4P-only scope claims that contradict the 2-5P mission + WS215 code.
  3. Citations of superseded engine pins outside provenance contexts.
  4. References to qualification/aggregate/* (stale WS17-era rollup layer).

Emits machine-readable JSON to stdout. Exit 0 always (observation, not gate).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

TRAP_NAME = re.compile(r"(CURRENT|FINAL|LATEST)", re.IGNORECASE)
FOUR_P_ONLY = re.compile(
    r"(4P-only|4-player only|four-player only|exactly-?4P|player_count\s*=\s*4"
    r"|pod_sizes\s*==\s*\(\s*4|3P/5P out of scope)",
    re.IGNORECASE,
)
SUPERSEDED_PINS = {
    "cfc36f445f917f101fa2ed588770e043f53bc44c": "WS213-predecessor XMage pin (superseded by db134b97)",
    "77d7646d": "WS206-era XMage pin (superseded)",
    "06d166b": "J-P3 frozen XMage pin (provenance only)",
    "a37a865a": "Forge forge-2.0.14 pin: still live as secondary per manifest :47-58; J-P3-era, verify before reuse",
}
AGGREGATE_REFS = re.compile(
    r"(qualification/aggregate/|PRODUCTION_ADMISSION|GATE_RESULTS\.json"
    r"|CROSS_CANDIDATE_EVIDENCE_MATRIX|BASELINE_COMMON_RESULTS)"
)

SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache"}
SKIP_SUFFIX = {".pyc", ".pyo"}
# This audit's own namespace must never pollute results.
SKIP_PREFIXES = ("research/project-audit/ws220",)
# Seal slot/artifact files inherit their seal's own source lock; a superseded
# pin there is provenance, not a live claim. Only surface them separately.
SEAL_DIRS = (
    "qualification/ws203-", "qualification/ws204-", "qualification/ws205-",
    "qualification/ws206-", "qualification/ws207-", "qualification/ws208-",
    "qualification/ws211-", "qualification/ws212-", "qualification/ws213-",
    "qualification/ws214-", "qualification/ws215-", "qualification/ws79-",
    "qualification/ws80-", "qualification/ws88-", "qualification/ws90-",
    "qualification/ws92-", "qualification/WS17",
)


def iter_files():
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(ROOT))
        if rel.startswith(SKIP_PREFIXES):
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix in SKIP_SUFFIX:
            continue
        yield p, rel


def in_seal_dir(rel: str) -> bool:
    return rel.startswith(SEAL_DIRS)


def main() -> int:
    name_traps = []
    four_p_claims = []
    pin_cites = []
    aggregate_cites = []
    pin_live: dict[str, list[int]] = {}
    pin_provenance: dict[str, list[int]] = {}
    for p, rel in iter_files():
        if TRAP_NAME.search(p.name):
            name_traps.append(rel)
        try:
            text = p.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        seal = in_seal_dir(rel)
        for i, line in enumerate(text.splitlines(), 1):
            if FOUR_P_ONLY.search(line):
                four_p_claims.append({"file": rel, "line": i, "text": line.strip()[:200]})
            for pin, note in SUPERSEDED_PINS.items():
                if pin in line:
                    entry = {"file": rel, "line": i, "pin": pin[:12], "note": note}
                    pin_cites.append(entry)
                    bucket = pin_provenance if seal else pin_live
                    bucket.setdefault(rel, []).append(i)
            if AGGREGATE_REFS.search(line):
                aggregate_cites.append({"file": rel, "line": i, "text": line.strip()[:160]})
    print(
        json.dumps(
            {
                "probe": "P-SRC-01",
                "name_traps": sorted(set(name_traps)),
                "name_trap_count": len(set(name_traps)),
                "four_p_claims": four_p_claims,
                "four_p_claim_files": sorted({c["file"] for c in four_p_claims}),
                "superseded_pin_citations_total": len(pin_cites),
                "superseded_pin_live_files": {k: v for k, v in sorted(pin_live.items())},
                "superseded_pin_provenance_files": len(pin_provenance),
                "aggregate_layer_citations": aggregate_cites,
                "aggregate_citing_files": sorted({c["file"] for c in aggregate_cites}),
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

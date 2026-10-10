#!/usr/bin/env python3
"""Derive XMage ``missing_required_capabilities`` in config/rules_engines.json from evidence.

#662 / SLOT-06 ruling §(b)2: the list is computed from the newest sealed epoch bound
to the current XMage pin, by the same freeze-record assembler that judges Freeze
eligibility. It is never edited by hand. ``--check`` fails when the file differs from
the derivation; ``--write`` rewrites only the two derived fields.

    scripts/derive_rules_engines_capabilities.py --check [--epoch DIR]
    scripts/derive_rules_engines_capabilities.py --write [--epoch DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary.freeze_record import (  # noqa: E402
    SEAL_MANIFEST,
    assemble_freeze_record,
)

CONFIG = REPO_ROOT / "config" / "rules_engines.json"
EPOCHS = REPO_ROOT / "qualification" / "current-boundary-epochs"


def newest_epoch_for_pin(pin: str) -> Path:
    """The newest sealed epoch whose PB-03 runtime ledger is bound to ``pin``.

    Selection uses the runtime ledger's candidate commit, which PB-03 writes for
    every run, never AF01's reported commit: a newer epoch whose AF01 failed is
    still the newest evidence and is judged (not-eligible), not skipped in favour
    of an older one. Directories without a seal manifest are not epochs.
    """
    candidates: list[tuple[str, Path]] = []
    for epoch in sorted(EPOCHS.iterdir()):
        identity = epoch / "EPOCH_IDENTITY.json"
        runtime = epoch / "PB03_RUNTIME_EXECUTION.json"
        if not (epoch / SEAL_MANIFEST).is_file() or not identity.is_file() or not runtime.is_file():
            continue
        created = json.loads(identity.read_text(encoding="utf-8")).get("created_utc")
        bound = json.loads(runtime.read_text(encoding="utf-8")).get("candidate_commit")
        if bound == pin and isinstance(created, str):
            candidates.append((created, epoch))
    if not candidates:
        raise SystemExit(f"no sealed epoch is bound to the XMage pin {pin}")
    return max(candidates)[1]


def derive(epoch: Path | None = None) -> tuple[Path, list[str]]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    pin = config["primary_engine"]["commit"]
    chosen = epoch or newest_epoch_for_pin(pin)
    result = assemble_freeze_record(chosen, repo_root=REPO_ROOT, expected_pin=pin)
    return chosen, list(result.record["truthful_capabilities"]["missing_required_capabilities"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    parser.add_argument("--epoch", type=Path)
    args = parser.parse_args(argv)

    epoch, missing = derive(args.epoch)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    current = (
        config["primary_engine"].get("missing_required_capabilities"),
        config["current_runtime"].get("required_missing_capabilities"),
    )
    rel = epoch.relative_to(REPO_ROOT) if epoch.is_absolute() else epoch
    if args.check:
        if current != (missing, missing):
            print(
                f"config/rules_engines.json is not derived from {rel}: "
                f"file={list(current)} derived={missing}",
                file=sys.stderr,
            )
            return 1
        print(f"rules_engines.json missing capabilities match {rel}: {missing}")
        return 0
    config["primary_engine"]["missing_required_capabilities"] = missing
    config["current_runtime"]["required_missing_capabilities"] = missing
    CONFIG.write_text(json.dumps(config, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote missing capabilities derived from {rel}: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

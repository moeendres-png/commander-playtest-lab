#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "vendor/engine-source/xmage")
patterns = {
    "new_random": re.compile(r"\bnew\s+Random\s*\("),
    "thread_local_random": re.compile(r"\bThreadLocalRandom\b"),
    "math_random": re.compile(r"\bMath\.random\s*\("),
    "secure_random": re.compile(r"\bSecureRandom\b"),
    "collections_shuffle": re.compile(r"\bCollections\.shuffle\s*\("),
}

findings: list[dict[str, object]] = []
for path in sorted(root.rglob("*.java")):
    rel = path.relative_to(root).as_posix()
    if "/target/" in f"/{rel}/":
        continue
    text = path.read_text(errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        for kind, rx in patterns.items():
            if rx.search(line):
                findings.append(
                    {
                        "kind": kind,
                        "path": rel,
                        "line": lineno,
                        "text": line.strip()[:300],
                    }
                )


def classify(item: dict[str, object]) -> str:
    rel = str(item["path"])
    text = str(item["text"])
    kind = str(item["kind"])

    if rel == "Mage/src/main/java/mage/util/RandomUtil.java":
        return "RULES_RNG_AUTHORITY"
    if rel == "Mage/src/main/java/mage/players/PlayerImpl.java":
        return "RULES_RNG_DELEGATED" if "RandomUtil.getRandom()" in text else "UNCONTROLLED_RULES_RNG"
    if rel.startswith("Mage.Sets/src/mage/cards/"):
        return "RULES_RNG_DELEGATED" if "RandomUtil.getRandom()" in text else "UNCONTROLLED_RULES_RNG"
    if rel == "Mage/src/main/java/mage/game/match/MatchImpl.java":
        return "MATCH_SETUP_RNG_DELEGATED" if "RandomUtil.getRandom()" in text else "UNCONTROLLED_MATCH_RNG"
    if rel == "Mage/src/main/java/mage/cards/repository/TokenRepository.java":
        return "PRESENTATION_RNG_ID_DERIVED"
    if rel == "Mage/src/main/java/mage/collation/Rotater.java":
        return "PRE_GAME_COLLATION_RNG"
    if rel == "Mage/src/main/java/mage/game/draft/RandomBoosterDraft.java":
        return "PRE_GAME_DRAFT_RNG"
    if rel == "Mage/src/main/java/mage/game/jumpstart/JumpstartPoolGenerator.java":
        return "PRE_GAME_DECK_GENERATION_RNG"
    if rel == "Mage/src/main/java/mage/game/tournament/pairing/SwissPairingMinimalWeightMatching.java":
        return "TOURNAMENT_PAIRING_RNG"
    if rel == "Mage.Server/src/main/java/mage/server/MageServerImpl.java":
        return "SERVER_SECURITY_RNG"
    if rel.startswith("Mage.Common/src/main/java/mage/utils/testers/"):
        return "TEST_UI_RNG"
    if any(part in rel for part in ("Mage.Tests/", "Mage.Client/", "Mage.Server.Plugins/", "Mage.Plugins/")):
        return "NON_QUALIFIED_SURFACE"
    if kind == "collections_shuffle" and "RandomUtil.getRandom()" in text:
        return "NON_RULES_RNG_DELEGATED"
    return "REQUIRES_REACHABILITY_REVIEW"

classified = [{**item, "classification": classify(item)} for item in findings]
counts: dict[str, int] = {}
for item in classified:
    key = f"{item['classification']}:{item['kind']}"
    counts[key] = counts.get(key, 0) + 1

blocking = [
    item
    for item in classified
    if item["classification"] in {
        "UNCONTROLLED_RULES_RNG",
        "UNCONTROLLED_MATCH_RNG",
        "REQUIRES_REACHABILITY_REVIEW",
    }
]
out = {
    "schema_version": "ws26-xmage-rng-census/1.1.0",
    "root": str(root),
    "findings": classified,
    "counts": counts,
    "rules_rng_authority": "mage.util.RandomUtil",
    "pilot_rng_mixed": False,
    "blocking_findings": blocking,
    "gate_pass": not blocking,
}
Path("qualification/evidence/ws26-xmage").mkdir(parents=True, exist_ok=True)
Path("qualification/evidence/ws26-xmage/XMAGE_RNG_CENSUS.json").write_text(
    json.dumps(out, indent=2, sort_keys=True) + "\n"
)
print(json.dumps({"counts": counts, "blocking": len(blocking), "gate_pass": not blocking}, sort_keys=True))
if blocking:
    raise SystemExit(2)

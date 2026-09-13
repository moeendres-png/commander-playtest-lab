#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
EVIDENCE_DIR = Path("qualification/evidence/ws26-xmage")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require_head(root: Path) -> None:
    observed = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if observed != XMAGE_COMMIT:
        raise RuntimeError(f"XMAGE_SOURCE_LOCK_MISMATCH: expected {XMAGE_COMMIT}, observed {observed}")


def transform_file(
    root: Path,
    relative: str,
    replacements: list[tuple[str, str, int]],
) -> dict[str, object]:
    path = root / relative
    before = path.read_text(encoding="utf-8")
    text = before
    applied: list[dict[str, object]] = []
    for index, (old, new, expected_count) in enumerate(replacements, 1):
        observed_count = text.count(old)
        if observed_count != expected_count:
            raise RuntimeError(
                f"XMAGE_TRANSFORM_PRECONDITION_FAILED: {relative} replacement {index} "
                f"expected_count={expected_count} observed_count={observed_count}"
            )
        text = text.replace(old, new)
        applied.append(
            {
                "replacement": index,
                "expected_count": expected_count,
                "observed_count": observed_count,
                "old_sha256": sha256_text(old),
                "new_sha256": sha256_text(new),
            }
        )
    if text == before:
        raise RuntimeError(f"XMAGE_TRANSFORM_NO_CHANGE: {relative}")
    path.write_text(text, encoding="utf-8")
    return {
        "path": relative,
        "before_sha256": sha256_text(before),
        "after_sha256": sha256_text(text),
        "replacements": applied,
    }


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "vendor/engine-source/xmage")
    require_head(root)

    random_imports_old = """import java.awt.*;\nimport java.util.Collection;\nimport java.util.Random;\nimport java.util.Set;\nimport java.util.UUID;\n"""
    random_imports_new = """import java.awt.*;\nimport java.util.ArrayList;\nimport java.util.Collection;\nimport java.util.Collections;\nimport java.util.List;\nimport java.util.Random;\nimport java.util.Set;\nimport java.util.UUID;\n"""
    random_decl_old = "    private static final Random random = new Random(); // thread safe with seed support\n"
    random_decl_new = """    /**
     * WS-26 qualification instrumentation. Recording happens at Random.next(bits)
     * so callers using getRandom(), Collections.shuffle(..., Random), nextInt,
     * nextBoolean and nextDouble all traverse the same attributable Rules RNG.
     */
    private static final class RecordingRandom extends Random {
        private final List<String> tape = new ArrayList<>();
        private boolean recording;
        private long drawIndex;

        @Override
        protected synchronized int next(int bits) {
            int value = super.next(bits);
            if (recording) {
                drawIndex++;
                tape.add(drawIndex + ":next_bits:" + bits + ":" + value);
            }
            return value;
        }

        synchronized void beginTape() {
            tape.clear();
            drawIndex = 0L;
            recording = true;
        }

        synchronized List<String> snapshotTape() {
            return Collections.unmodifiableList(new ArrayList<>(tape));
        }
    }

    private static final RecordingRandom random = new RecordingRandom(); // thread safe with seed support
"""
    seed_old = """    public static void setSeed(long newSeed) {
        random.setSeed(newSeed);
    }

    public static <T> T randomFromCollection(Collection<T> collection) {
"""
    seed_new = """    public static void setSeed(long newSeed) {
        random.setSeed(newSeed);
    }

    public static void beginRulesRngTape() {
        random.beginTape();
    }

    public static List<String> getRulesRngTape() {
        return random.snapshotTape();
    }

    public static <T> T randomFromCollection(Collection<T> collection) {
"""

    results = [
        transform_file(
            root,
            "Mage/src/main/java/mage/util/RandomUtil.java",
            [
                (random_imports_old, random_imports_new, 1),
                (random_decl_old, random_decl_new, 1),
                (seed_old, seed_new, 1),
            ],
        ),
        transform_file(
            root,
            "Mage/src/main/java/mage/players/PlayerImpl.java",
            [
                (
                    "Collections.shuffle(ids);",
                    "Collections.shuffle(ids, mage.util.RandomUtil.getRandom());",
                    2,
                )
            ],
        ),
        transform_file(
            root,
            "Mage.Sets/src/mage/cards/e/ExposeTheCulprit.java",
            [
                (
                    "Collections.shuffle(cardsToCloak);",
                    "Collections.shuffle(cardsToCloak, mage.util.RandomUtil.getRandom());",
                    1,
                )
            ],
        ),
        transform_file(
            root,
            "Mage.Sets/src/mage/cards/g/GhastlyConscription.java",
            [
                (
                    "Collections.shuffle(cardsToManifest);",
                    "Collections.shuffle(cardsToManifest, mage.util.RandomUtil.getRandom());",
                    1,
                )
            ],
        ),
        transform_file(
            root,
            "Mage.Sets/src/mage/cards/j/JalumGrifter.java",
            [
                (
                    "Collections.shuffle(shellGamePile);",
                    "Collections.shuffle(shellGamePile, mage.util.RandomUtil.getRandom());",
                    1,
                )
            ],
        ),
        transform_file(
            root,
            "Mage.Sets/src/mage/cards/j/JeskaiInfiltrator.java",
            [
                (
                    "Collections.shuffle(cardsToManifest);",
                    "Collections.shuffle(cardsToManifest, mage.util.RandomUtil.getRandom());",
                    1,
                )
            ],
        ),
        transform_file(
            root,
            "Mage.Sets/src/mage/cards/v/VialSmasherTheFierce.java",
            [
                (
                    "Collections.shuffle(opponents);",
                    "Collections.shuffle(opponents, mage.util.RandomUtil.getRandom());",
                    1,
                )
            ],
        ),
    ]

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": "ws26-xmage-source-transform/1.0.0",
        "xmage_commit": XMAGE_COMMIT,
        "fail_closed_preconditions": True,
        "files": results,
    }
    (EVIDENCE_DIR / "XMAGE_SOURCE_TRANSFORM.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"transformed_files": len(results), "xmage_commit": XMAGE_COMMIT}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

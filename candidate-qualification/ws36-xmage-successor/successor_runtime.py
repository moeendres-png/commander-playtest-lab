"""WS-36 v1.0.2 runtime-only adapters.

This module translates successor metadata into provider run metadata without
mutating or reinterpreting the immutable WS-32 record.  In v1.0.2 Rules RNG is
bound by ``rules_randomness.seed_binding == SCENARIO_SEED``; the numerical seed
is therefore an execution input, not a frozen record field.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def scenario_seed(record: dict[str, Any]) -> int:
    randomness = record.get("rules_randomness")
    if not isinstance(randomness, dict):
        raise ValueError("RULES_RANDOMNESS_SCHEMA_MISSING")
    if randomness.get("seed_binding") != "SCENARIO_SEED":
        raise ValueError(
            "UNSUPPORTED_RULES_RNG_SEED_BINDING:"
            + str(randomness.get("seed_binding"))
        )
    digest = record.get("materialization_digest")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("MATERIALIZATION_DIGEST_INVALID_FOR_SCENARIO_SEED")
    # Positive signed Java long, deterministic for the immutable record.
    return int(digest[:16], 16) & 0x7FFF_FFFF_FFFF_FFFF


def v101_compat_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return a private compatibility copy for old scenario builders only.

    The historical v1.0.1 helper reads ``rules_seed``.  WS-36 does not add that
    field to the canonical record; it injects the explicit scenario run input
    into a deep copy consumed only by the provider-side builder.
    """
    copied = deepcopy(record)
    randomness = copied.setdefault("rules_randomness", {})
    randomness["rules_seed"] = scenario_seed(record)
    return copied

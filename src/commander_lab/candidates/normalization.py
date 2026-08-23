from __future__ import annotations

import hashlib
import json

from .models import DeckCandidate, DeckCandidateSet


def canonical_deck_payload(candidate: DeckCandidate) -> dict[str, object]:
    return {
        "commanders": sorted(candidate.commander_names, key=str.casefold),
        "mainboard": [
            {"oracle_name": name, "quantity": quantity}
            for name, quantity in sorted(candidate.mainboard.items(), key=lambda item: item[0].casefold())
        ],
    }


def canonical_deck_hash(candidate: DeckCandidate) -> str:
    encoded = json.dumps(
        canonical_deck_payload(candidate),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_candidate(candidate: DeckCandidate) -> DeckCandidate:
    digest = canonical_deck_hash(candidate)
    if candidate.deck_hash is not None and candidate.deck_hash != digest:
        raise ValueError(
            f"candidate {candidate.candidate_id} supplied deck_hash does not match canonical deck identity"
        )
    return candidate.model_copy(update={"deck_hash": digest})


def normalize_candidate_set(candidate_set: DeckCandidateSet) -> DeckCandidateSet:
    normalized = tuple(normalize_candidate(candidate) for candidate in candidate_set.candidates)
    return candidate_set.model_copy(
        update={"candidate_count": len(normalized), "candidates": normalized}
    )


__all__ = [
    "canonical_deck_hash",
    "canonical_deck_payload",
    "normalize_candidate",
    "normalize_candidate_set",
]

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class DecisionContextError(ValueError):
    """Raised when deck/candidate decision context is missing or contradictory."""


class CandidateAvailability(StrEnum):
    """Availability/provenance state for a deck-improvement candidate."""

    PHYSICAL_OWNED = "physical_owned"
    PHYSICAL_RESERVED = "physical_reserved"
    PHYSICAL_FREE = "physical_free"
    OPPONENT_CARD = "opponent_card"
    HYPOTHETICAL_TEST = "hypothetical_test"
    PURCHASE_CANDIDATE = "purchase_candidate"
    UNKNOWN = "unknown"


_DECISION_EVIDENCE_CLASSES = frozenset(
    {
        "structural_model_estimates",
        "tactical_oracle",
        "external_rules_engine",
        "real_observation",
        "synthetic_assumption",
    }
)
_NONPHYSICAL_AVAILABILITY = frozenset(
    {
        CandidateAvailability.HYPOTHETICAL_TEST,
        CandidateAvailability.PURCHASE_CANDIDATE,
        CandidateAvailability.OPPONENT_CARD,
        CandidateAvailability.UNKNOWN,
    }
)
_SIMULATABLE_AVAILABILITY = frozenset(
    {
        CandidateAvailability.PHYSICAL_FREE,
        CandidateAvailability.HYPOTHETICAL_TEST,
    }
)


def _sha256_bytes(payload: bytes) -> str:
    normalized = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise DecisionContextError(f"required decision-context input is missing: {path}")
    return _sha256_bytes(path.read_bytes())


def _sha256_json(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise DecisionContextError(f"required decision-context input is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DecisionContextError(f"invalid decision-context JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise DecisionContextError(f"decision-context JSON must be an object: {path}")
    return payload


def _stable_id(prefix: str, *parts: str) -> str:
    label = "/".join(parts)
    slug = re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-")[:48]
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}/{slug}-{digest}"


@dataclass(frozen=True, slots=True)
class CandidateProvenance:
    candidate_id: str
    oracle_name: str
    availability: CandidateAvailability
    allowed_deck_ids: tuple[str, ...]
    source_id: str
    source_hash: str
    quantity: int = 0
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.oracle_name or not self.source_id:
            raise DecisionContextError("candidate provenance requires stable ids and oracle name")
        if len(self.source_hash) != 64:
            raise DecisionContextError(f"invalid candidate source hash: {self.candidate_id}")
        if self.quantity < 0:
            raise DecisionContextError(f"negative candidate quantity: {self.candidate_id}")
        if len(self.allowed_deck_ids) != len(set(self.allowed_deck_ids)):
            raise DecisionContextError(f"duplicate allowed deck id: {self.candidate_id}")
        if self.availability is CandidateAvailability.PHYSICAL_FREE and self.quantity <= 0:
            raise DecisionContextError(
                f"free physical candidate has no available copy: {self.candidate_id}"
            )
        if self.availability in _NONPHYSICAL_AVAILABILITY and self.quantity != 0:
            raise DecisionContextError(
                f"non-physical candidate must not advertise physical quantity: {self.candidate_id}"
            )

    @property
    def simulatable_for_improvement(self) -> bool:
        return self.availability in _SIMULATABLE_AVAILABILITY

    @property
    def physically_available(self) -> bool:
        return self.availability is CandidateAvailability.PHYSICAL_FREE and self.quantity > 0

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["availability"] = self.availability.value
        payload["physically_available"] = self.physically_available
        payload["simulatable_for_improvement"] = self.simulatable_for_improvement
        return payload


@dataclass(frozen=True, slots=True)
class TestCandidateSpec:
    oracle_name: str
    allowed_deck_ids: tuple[str, ...]
    source_id: str
    source_hash: str
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.oracle_name or not self.allowed_deck_ids or not self.source_id:
            raise DecisionContextError(
                "test candidate requires oracle name, deck ids and source id"
            )
        if len(self.source_hash) != 64:
            raise DecisionContextError(f"invalid test-candidate source hash: {self.oracle_name}")


@dataclass(frozen=True, slots=True)
class DeckDecisionContext:
    deck_id: str
    deck_hash: str
    commander_names: tuple[str, ...]
    inventory_hash: str
    allocation_hash: str
    candidate_scope_hash: str
    opponent_context_hash: str

    def __post_init__(self) -> None:
        if not self.deck_id or not self.commander_names:
            raise DecisionContextError("deck context requires deck id and commander identity")
        for field_name in (
            "deck_hash",
            "inventory_hash",
            "allocation_hash",
            "candidate_scope_hash",
            "opponent_context_hash",
        ):
            if len(str(getattr(self, field_name))) != 64:
                raise DecisionContextError(f"invalid {field_name} for {self.deck_id}")

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DecisionRunContext:
    deck_id: str
    deck_hash: str
    variant_id: str
    candidate_provenance: tuple[CandidateProvenance, ...]
    opponent_ids: tuple[str, ...]
    pilot_ids: tuple[str, ...]
    pod_size: int
    seed: int
    evidence_class: str
    context_snapshot_hash: str
    run_identity_hash: str

    def as_dict(self) -> dict[str, object]:
        candidate_rows = [item.as_dict() for item in self.candidate_provenance]
        return {
            "deck_id": self.deck_id,
            "deck_hash": self.deck_hash,
            "variant_id": self.variant_id,
            "candidate_provenance": candidate_rows,
            "opponent_ids": list(self.opponent_ids),
            "pilot_ids": list(self.pilot_ids),
            "pod_size": self.pod_size,
            "seed": self.seed,
            "evidence_class": self.evidence_class,
            "context_snapshot_hash": self.context_snapshot_hash,
            "run_identity_hash": self.run_identity_hash,
        }


class DecisionContextRegistry:
    """Immutable deck-scoped context registry for decision-support workflows.

    The registry never reserves cards, mutates canonical data, or converts hypothetical test
    candidates into physical inventory. Callers select the own ``deck_id`` explicitly.
    """

    def __init__(
        self,
        decks: Iterable[DeckDecisionContext],
        candidates: Iterable[CandidateProvenance],
    ) -> None:
        deck_rows = tuple(decks)
        candidate_rows = tuple(candidates)
        self._decks = {row.deck_id: row for row in deck_rows}
        self._candidates = {row.candidate_id: row for row in candidate_rows}
        if len(self._decks) != len(deck_rows):
            raise DecisionContextError("duplicate deck id in decision context")
        if len(self._candidates) != len(candidate_rows):
            raise DecisionContextError("duplicate candidate id in decision context")
        unknown = sorted(
            {
                deck_id
                for row in candidate_rows
                for deck_id in row.allowed_deck_ids
                if deck_id not in self._decks
            }
        )
        if unknown:
            raise DecisionContextError(f"candidate references unknown own deck ids: {unknown}")

    @property
    def deck_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._decks))

    @property
    def snapshot_hash(self) -> str:
        deck_rows = [self._decks[key].as_dict() for key in sorted(self._decks)]
        candidate_rows = [self._candidates[key].as_dict() for key in sorted(self._candidates)]
        return _sha256_json({"decks": deck_rows, "candidates": candidate_rows})

    def deck(self, deck_id: str) -> DeckDecisionContext:
        try:
            return self._decks[deck_id]
        except KeyError as exc:
            raise DecisionContextError(f"unknown own deck id: {deck_id}") from exc

    def candidates_for_deck(
        self,
        deck_id: str,
        *,
        include_hypothetical_tests: bool = True,
    ) -> tuple[CandidateProvenance, ...]:
        self.deck(deck_id)
        allowed_states = {CandidateAvailability.PHYSICAL_FREE}
        if include_hypothetical_tests:
            allowed_states.add(CandidateAvailability.HYPOTHETICAL_TEST)
        ordered = sorted(self._candidates.values(), key=lambda value: value.candidate_id)
        return tuple(
            row
            for row in ordered
            if deck_id in row.allowed_deck_ids
            and row.availability in allowed_states
            and row.simulatable_for_improvement
        )

    def build_run_context(
        self,
        *,
        deck_id: str,
        variant_id: str,
        candidate_ids: Iterable[str],
        opponent_ids: Iterable[str],
        pilot_ids: Iterable[str],
        pod_size: int,
        seed: int,
        evidence_class: str,
    ) -> DecisionRunContext:
        deck = self.deck(deck_id)
        if not variant_id:
            raise DecisionContextError("variant id is required")
        if evidence_class not in _DECISION_EVIDENCE_CLASSES:
            raise DecisionContextError(f"unsupported evidence class: {evidence_class}")
        if not 2 <= pod_size <= 10:
            raise DecisionContextError("pod size must be between 2 and 10")
        if seed < 0:
            raise DecisionContextError("seed must be non-negative")

        selected: list[CandidateProvenance] = []
        for candidate_id in candidate_ids:
            try:
                candidate = self._candidates[str(candidate_id)]
            except KeyError as exc:
                raise DecisionContextError(f"unknown candidate id: {candidate_id}") from exc
            if deck_id not in candidate.allowed_deck_ids:
                raise DecisionContextError(
                    f"candidate {candidate.candidate_id} is not scoped to deck {deck_id}"
                )
            if not candidate.simulatable_for_improvement:
                raise DecisionContextError(
                    f"candidate {candidate.candidate_id} is not eligible for improvement simulation"
                )
            selected.append(candidate)

        opponents = tuple(str(value) for value in opponent_ids)
        pilots = tuple(str(value) for value in pilot_ids)
        payload = {
            "registry_snapshot_hash": self.snapshot_hash,
            "deck": deck.as_dict(),
            "variant_id": variant_id,
            "candidates": [row.as_dict() for row in selected],
            "opponent_ids": list(opponents),
            "pilot_ids": list(pilots),
            "pod_size": pod_size,
            "seed": seed,
            "evidence_class": evidence_class,
        }
        return DecisionRunContext(
            deck_id=deck_id,
            deck_hash=deck.deck_hash,
            variant_id=variant_id,
            candidate_provenance=tuple(selected),
            opponent_ids=opponents,
            pilot_ids=pilots,
            pod_size=pod_size,
            seed=seed,
            evidence_class=evidence_class,
            context_snapshot_hash=self.snapshot_hash,
            run_identity_hash=_sha256_json(payload),
        )


def load_decision_context_registry(
    root: str | Path,
    *,
    test_candidates: Iterable[TestCandidateSpec] = (),
) -> DecisionContextRegistry:
    """Load live own-deck decision context without encoding a specific deck identity.

    Explicit test candidates are caller-provided and remain ``hypothetical_test``. Loading the
    context never writes them to inventory or allocation files.
    """

    root_path = Path(root).resolve()
    scope_path = root_path / "data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json"
    manifest_path = root_path / "data/decks/manifest.json"
    inventory_path = root_path / "data/canonical_import/2026-08-07/inventory_snapshot.json"
    allocation_path = root_path / "data/collections/current_deck_allocations.json"
    candidate_path = root_path / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json"
    opponent_path = root_path / "data/collections/current/POD_SCENARIOS_CURRENT.json"

    scope = _load_json(scope_path)
    manifest = _load_json(manifest_path)
    candidate_scope = _load_json(candidate_path)
    active_raw = scope.get("active_own_decks")
    if not isinstance(active_raw, list) or not active_raw:
        raise DecisionContextError("current scope contains no active own deck")
    active = tuple(str(value) for value in active_raw)
    if len(active) != len(set(active)):
        raise DecisionContextError("current scope contains duplicate active own deck ids")

    manifest_decks = manifest.get("decks")
    if not isinstance(manifest_decks, dict):
        raise DecisionContextError("deck manifest has no decks mapping")
    eligible_by_deck = candidate_scope.get("eligible_by_deck")
    if not isinstance(eligible_by_deck, dict):
        raise DecisionContextError("candidate scope has no eligible_by_deck mapping")

    inventory_hash = _sha256_file(inventory_path)
    allocation_hash = _sha256_file(allocation_path)
    candidate_scope_hash = _sha256_file(candidate_path)
    opponent_context_hash = _sha256_file(opponent_path)

    decks: list[DeckDecisionContext] = []
    candidates: list[CandidateProvenance] = []
    for deck_id in active:
        raw_deck = manifest_decks.get(deck_id)
        if not isinstance(raw_deck, dict):
            raise DecisionContextError(f"active own deck is missing from manifest: {deck_id}")
        deck_hash = raw_deck.get("deck_hash")
        commanders = raw_deck.get("commanders")
        if not isinstance(deck_hash, str) or len(deck_hash) != 64:
            raise DecisionContextError(f"invalid deck hash for {deck_id}")
        if not isinstance(commanders, list) or not commanders:
            raise DecisionContextError(f"missing commander identity for {deck_id}")
        decks.append(
            DeckDecisionContext(
                deck_id=deck_id,
                deck_hash=deck_hash,
                commander_names=tuple(str(value) for value in commanders),
                inventory_hash=inventory_hash,
                allocation_hash=allocation_hash,
                candidate_scope_hash=candidate_scope_hash,
                opponent_context_hash=opponent_context_hash,
            )
        )
        raw_rows = eligible_by_deck.get(deck_id, {})
        if not isinstance(raw_rows, dict):
            raise DecisionContextError(f"candidate eligibility is invalid for {deck_id}")
        for oracle_name, raw_spec in raw_rows.items():
            if not isinstance(raw_spec, dict) or raw_spec.get("commander_legal") is not True:
                continue
            quantity = int(raw_spec.get("physical_available_quantity", 0))
            if quantity <= 0:
                continue
            source_id = f"repo:{candidate_path.relative_to(root_path).as_posix()}:{deck_id}"
            candidates.append(
                CandidateProvenance(
                    candidate_id=_stable_id("physical", deck_id, str(oracle_name)),
                    oracle_name=str(oracle_name),
                    availability=CandidateAvailability.PHYSICAL_FREE,
                    allowed_deck_ids=(deck_id,),
                    source_id=source_id,
                    source_hash=candidate_scope_hash,
                    quantity=quantity,
                    notes="Free physical candidate from current deck-scoped eligibility.",
                )
            )

    active_set = set(active)
    for spec in test_candidates:
        unknown = sorted(set(spec.allowed_deck_ids) - active_set)
        if unknown:
            raise DecisionContextError(
                f"test candidate {spec.oracle_name} references inactive/unknown decks: {unknown}"
            )
        candidates.append(
            CandidateProvenance(
                candidate_id=_stable_id("test", spec.source_id, spec.oracle_name),
                oracle_name=spec.oracle_name,
                availability=CandidateAvailability.HYPOTHETICAL_TEST,
                allowed_deck_ids=tuple(spec.allowed_deck_ids),
                source_id=spec.source_id,
                source_hash=spec.source_hash,
                notes=spec.notes,
            )
        )

    return DecisionContextRegistry(decks, candidates)


__all__ = [
    "CandidateAvailability",
    "CandidateProvenance",
    "DecisionContextError",
    "DecisionContextRegistry",
    "DecisionRunContext",
    "DeckDecisionContext",
    "TestCandidateSpec",
    "load_decision_context_registry",
]

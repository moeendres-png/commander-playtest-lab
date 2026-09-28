"""PB-03: admit a frozen mid-game obligation from the engine's OWN manifest.

Background
----------
Thirty of the effective FULL107 denominator rows require a frozen mid-game
starting state. Until now the reason those rows were blocked was a **Lab
projection**: ``materialization.requires_starting_state`` named the mechanism,
and the runner then asserted that the mechanism was unreachable because the
bridge reported ``starting_state_injection_supported=false``. A bare boolean
cannot support that conclusion, because it does not say *which* dimensions the
engine can actually restore.

The bridge now publishes an itemised manifest
(``full_game_lane.state_restoration_dimensions``, schema
``native-state-restoration-dimensions-1.1.0``) naming 11 supported and 11
unsupported dimensions. This module consumes that live manifest so a row's
blockage rests on the engine's own words rather than on Lab inference.

Two hard rules govern this module
---------------------------------
1. **The manifest decides ADMISSIBILITY only. It never decides an outcome.**
   A dimension being supported says the engine *can* restore it. It says
   nothing about whether the obligation holds. Only execution may set PASS or
   FAIL, and this module never emits either.

2. **Fail closed on anything unrecognised.** If the manifest is absent,
   malformed, carries an unexpected schema, or a mechanism family has no
   declared dimension requirement, the family is ``NOT_DECLARED`` and the
   obligation is not admitted. Guessing a mapping would silently re-create the
   very projection PB-03 removed.

``TRANSPORT_SEAM_AVAILABLE`` records a second, independent fact: no protocol
message exposes the restoration path to the qualification lane. The native
restoration harness is reached only from Lab-owned in-process Java harnesses.
So an engine-supported dimension is *not* yet executable here, and this module
says so rather than letting ``admissible`` be misread as ``executable``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

RESTORATION_MANIFEST_SCHEMA = "native-state-restoration-dimensions-1.1.0"

# No protocol verb reaches the native restoration path. The restoration harness
# is driven only from Lab-owned in-process Java harnesses; the JSONL lanes
# expose no apply/restore/inject message. Admissibility therefore cannot by
# itself make a row executable, and this flag is carried into every reason the
# runner writes so a reader cannot mistake "the engine could do it" for "this
# run did it".
TRANSPORT_SEAM_AVAILABLE = False

DimensionState = Literal["SUPPORTED", "UNSUPPORTED", "NOT_DECLARED"]


@dataclass(frozen=True)
class DimensionRequirement:
    """One engine dimension a mechanism family needs to be constructed.

    ``marker`` is a verbatim prefix of the engine's own manifest entry. It is
    matched, not assumed: if the engine's wording moves, the family degrades to
    ``NOT_DECLARED`` and the obligation is not admitted.
    """

    key: str
    marker: str
    why: str


# Mechanism family (from materialization.MID_GAME_MECHANISM_FAMILIES) -> the
# engine dimensions that family needs. Every entry is anchored to engine text.
#
# multiplayer_lifecycle is deliberately ABSENT. The manifest covers position
# restoration (cards, damage, zones, turn-1 timing); it says nothing about
# player elimination or multiplayer cleanup, so there is no honest mapping and
# the family fails closed rather than being waved through.
MECHANISM_DIMENSION_REQUIREMENTS: dict[str, tuple[DimensionRequirement, ...]] = {
    "live_priority_ring": (
        DimensionRequirement(
            key="turn1_temporal_targets",
            marker="qualified turn-1 temporal targets",
            why="a live priority ring is reached by progressing to a qualified turn-1 step",
        ),
    ),
    "combat_declaration": (
        DimensionRequirement(
            key="turn1_temporal_targets",
            marker="qualified turn-1 temporal targets",
            why=(
                "declare attackers, declare blockers and combat damage are named turn-1 "
                "temporal targets"
            ),
        ),
    ),
    "commander_damage_accounting": (
        DimensionRequirement(
            key="commander_damage_matrices",
            marker="commander damage matrices through exact live CommanderInfoWatcher bindings",
            why="commander damage state is restored through the native damage-matrix bindings",
        ),
    ),
    "zone_manipulation": (
        DimensionRequirement(
            key="card_placement",
            marker="battlefield/graveyard/exile placement of real cards",
            why="zone manipulation needs real cards placed in the target zone",
        ),
    ),
    "stack_response": (
        DimensionRequirement(
            key="stack_spells",
            marker="stack spells (casting requires real costs/timing: executor scope)",
            why="a stack response needs real spells already cast on the stack",
        ),
    ),
    "turn_transition": (
        DimensionRequirement(
            key="out_of_allow_list_temporal",
            marker="temporal points outside the qualified RG-03 turn-1 checkpoint allow-list",
            why="an extra or non-first turn is a temporal point outside the turn-1 allow-list",
        ),
    ),
}


@dataclass(frozen=True)
class RestorationManifest:
    """The live manifest as published by the candidate bridge."""

    schema_version: str
    starting_state_injection_supported: bool
    supported: tuple[str, ...]
    unsupported: tuple[str, ...]

    def locate(self, marker: str) -> tuple[DimensionState, str]:
        """Find ``marker`` in exactly one list, or fail closed."""
        hit_supported = next((s for s in self.supported if s.startswith(marker)), None)
        if hit_supported is not None:
            return "SUPPORTED", hit_supported
        hit_unsupported = next((s for s in self.unsupported if s.startswith(marker)), None)
        if hit_unsupported is not None:
            return "UNSUPPORTED", hit_unsupported
        return "NOT_DECLARED", ""


@dataclass(frozen=True)
class FamilyVerdict:
    family: str
    state: DimensionState
    dimension_keys: tuple[str, ...]
    engine_text: tuple[str, ...]
    detail: str

    @property
    def admissible(self) -> bool:
        return self.state == "SUPPORTED"


@dataclass(frozen=True)
class AdmissionVerdict:
    fixture_id: str
    requires_starting_state: bool
    admitted: bool
    families: tuple[FamilyVerdict, ...]
    reason: str


class ManifestUnavailableError(RuntimeError):
    """Raised when no usable engine manifest was supplied. Never guessed around."""


def parse_manifest(capability_payload: dict[str, Any] | None) -> RestorationManifest:
    """Parse ``full_game_lane.state_restoration_dimensions`` from a live payload.

    Raises :class:`ManifestUnavailableError` rather than defaulting: an absent or
    malformed manifest must not silently degrade into "no dimensions supported",
    which would look like an engine incapability that was never observed.
    """
    payload = capability_payload or {}
    lane = payload.get("full_game_lane")
    raw = None
    if isinstance(lane, dict) and isinstance(lane.get("state_restoration_dimensions"), dict):
        raw = lane["state_restoration_dimensions"]
    elif isinstance(payload.get("state_restoration_dimensions"), dict):
        # Compatibility lane: the manifest is a harness property, not a lane
        # property, so both transports publish it.
        raw = payload["state_restoration_dimensions"]
    if not isinstance(raw, dict):
        raise ManifestUnavailableError(
            "candidate bridge published no state_restoration_dimensions on either the "
            "full_game_lane or the top-level capability payload"
        )
    schema = str(raw.get("schema_version", ""))
    if schema != RESTORATION_MANIFEST_SCHEMA:
        raise ManifestUnavailableError(
            f"unexpected restoration manifest schema {schema!r}; "
            f"expected {RESTORATION_MANIFEST_SCHEMA!r}"
        )
    supported = raw.get("supported_dimensions")
    unsupported = raw.get("unsupported_dimensions")
    if not isinstance(supported, list) or not isinstance(unsupported, list):
        raise ManifestUnavailableError(
            "restoration manifest must carry supported_dimensions and unsupported_dimensions lists"
        )
    return RestorationManifest(
        schema_version=schema,
        starting_state_injection_supported=bool(raw.get("starting_state_injection_supported")),
        supported=tuple(str(item) for item in supported),
        unsupported=tuple(str(item) for item in unsupported),
    )


def classify_family(manifest: RestorationManifest, family: str) -> FamilyVerdict:
    """Classify one mechanism family against the engine's own manifest."""
    requirements = MECHANISM_DIMENSION_REQUIREMENTS.get(family)
    if not requirements:
        # Fail closed. This is the PB-03 rule: a family with no declared
        # mapping is not admitted, and the reason says so instead of guessing.
        return FamilyVerdict(
            family=family,
            state="NOT_DECLARED",
            dimension_keys=(),
            engine_text=(),
            detail=(
                f"mechanism family {family!r} has no declared engine-dimension requirement, so "
                "its admissibility is unknown and it is not admitted. The engine manifest "
                f"declares {len(manifest.supported)} supported and {len(manifest.unsupported)} "
                "unsupported dimensions, none of which this module claims to cover for this "
                "family."
            ),
        )

    keys: list[str] = []
    texts: list[str] = []
    worst: DimensionState = "SUPPORTED"
    for requirement in requirements:
        state, text = manifest.locate(requirement.marker)
        keys.append(requirement.key)
        if state == "NOT_DECLARED":
            return FamilyVerdict(
                family=family,
                state="NOT_DECLARED",
                dimension_keys=tuple(keys),
                engine_text=(),
                detail=(
                    f"the engine manifest declares no dimension beginning "
                    f"{requirement.marker!r} for {family} ({requirement.why}), so the engine's "
                    "position on this mechanism is unknown and it is not admitted. Engine wording "
                    "may have moved; the mapping is matched, never assumed."
                ),
            )
        texts.append(text)
        if state == "UNSUPPORTED" and worst == "SUPPORTED":
            worst = "UNSUPPORTED"
    if worst == "UNSUPPORTED":
        detail = (
            f"the engine itself declares the required dimension unsupported: "
            f"{'; '.join(texts)}. This is an engine-declared limitation, not a Lab projection."
        )
    else:
        detail = (
            "every dimension this family needs is declared supported by the engine manifest: "
            f"{'; '.join(texts)}."
        )
    return FamilyVerdict(
        family=family,
        state=worst,
        dimension_keys=tuple(keys),
        engine_text=tuple(texts),
        detail=detail,
    )


def admit(
    manifest: RestorationManifest,
    record: dict[str, Any],
    *,
    families: tuple[str, ...],
) -> AdmissionVerdict:
    """Decide whether a frozen mid-game obligation may be attempted.

    Admission is a *permission to attempt*, never a result. Callers must still
    execute the row to learn its outcome; this function never returns PASS.
    """
    fixture_id = str(record.get("fixture_id", ""))
    if not families:
        return AdmissionVerdict(
            fixture_id=fixture_id,
            requires_starting_state=False,
            admitted=False,
            families=(),
            reason="every required event is reachable from a fresh game start",
        )
    verdicts = tuple(classify_family(manifest, family) for family in sorted(set(families)))
    admitted = all(verdict.admissible for verdict in verdicts)
    if admitted and not TRANSPORT_SEAM_AVAILABLE:
        reason = (
            "every dimension this obligation needs is declared SUPPORTED by the engine's own "
            "restoration manifest, so the mechanism is not an engine limitation; but the "
            "qualification lane exposes no protocol message that reaches the native restoration "
            "path, so this run cannot construct the position. The blocker is a Lab transport "
            "seam, and it is not executed here."
        )
    elif admitted:
        reason = "every required dimension is declared supported; the obligation may be attempted"
    else:
        reason = " ".join(verdict.detail for verdict in verdicts)
    return AdmissionVerdict(
        fixture_id=fixture_id,
        requires_starting_state=True,
        admitted=admitted,
        families=verdicts,
        reason=reason,
    )

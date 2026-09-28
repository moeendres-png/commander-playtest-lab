"""Per-obligation disposition for the PB-06 hidden-information rows.

The 20 ``HIDDEN_*`` obligations in
``qualification/obligations/QUALIFICATION_OBLIGATION_CATALOG_v1.json`` are a
single all-or-nothing family today: the runner emits one blanket
``UNKNOWN``/``NO_CURRENT_BOUNDARY_EXECUTION_SEAM`` reason for all of them,
claiming the generic Protocol-2 state projection "does not expose the
per-scenario channel instrumentation each fixture requires".

That blanket claim is too coarse to be true. The generic lane *does* return a
principal-scoped state projection, and some obligations are stated purely in
terms of what that projection may and may not contain. The XMage generic-lane
observation demonstrates exactly one of them:

* ``HIDDEN_01`` — opponent hand identities absent while count remains visible.
* ``HIDDEN_02`` — library identities/order absent while count remains visible.

Both are directly readable from a principal-scoped state view: the observer's
own hand is real, every opponent hand is entirely redaction placeholders, every
library is entirely placeholders, and the array *lengths* (the counts) are
present. That is the obligation, not a proxy for it.

This module therefore splits the family into per-obligation dispositions:

``SATISFIED_BY_GENERIC_SCOPING``
    The obligation is stated entirely in terms of the principal-scoped state
    projection, the live observations satisfy it, and it is credited.

``NOT_OBSERVABLE_ON_GENERIC_SURFACE``
    The obligation needs a distinct game event or a per-scenario channel the
    generic state projection does not carry. It stays ``UNKNOWN``. This is the
    same outcome the blanket reason produced, but now it is attributed to the
    specific missing observation instead of to the whole family.

Deliberate non-goals, because each would be a Rules or evidence-policy
decision rather than an engineering one:

* An obligation is never credited from a *different* obligation's evidence.
  ``HIDDEN_04`` (face-down permanent controller sees identity) is NOT satisfied
  by observing that opponent hands are masked; those are different channels.
* Nothing here flips a FULL107 row. Row outcomes are owned by
  ``scripts/run_current_boundary_qualification.py``, which is under an active
  owner's write lock. This module only *classifies* obligations so that owner
  can consume it without a second implementation.
* This never turns an ``UNKNOWN`` into a ``PASS`` on its own authority. It
  reports what the observations support; promotion remains a separate,
  evidence-bound step.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from commander_lab.qualification.current_boundary.full107 import (
    _players_of,
    _zone_exposes_content,
    validate_principal_scoping,
)

SATISFIED = "SATISFIED_BY_GENERIC_SCOPING"
NOT_OBSERVABLE = "NOT_OBSERVABLE_ON_GENERIC_SURFACE"

# Obligations that are stated purely as properties of the principal-scoped state
# projection. Each entry names the zone key whose scoping the obligation is
# about and the audience relationship that must hold.
#
# "opponent" scoping means: the observer's own copy of the zone carries real
# content, every non-actor's copy carries none, and the count is still visible.
# "everyone" scoping means every copy carries the content, because the content
# is public by the obligation itself.
_GENERIC_SCOPING_OBLIGATIONS: dict[str, dict[str, str]] = {
    "HIDDEN_01": {
        "zone": "hand",
        "audience": "opponent",
        "intent": "opponent hand identities absent while count remains visible",
    },
    "HIDDEN_02": {
        "zone": "library",
        "audience": "everyone",
        "intent": "library identities/order absent while count remains visible",
    },
}


def _zones_of(entry: Any) -> dict[str, Any]:
    if not isinstance(entry, dict):
        return {}
    raw = entry.get("zones")
    return raw if isinstance(raw, dict) else {}


def _actor_seat_of(payload: dict[str, Any], players: list[Any]) -> int | None:
    """The seat the observation is established to be about.

    Prefers the in-state ``is_actor`` marker, then the observer envelope's
    ``observer_seat``. Returns ``None`` when neither is present, so an
    unattributable view is never read as a scoped one.
    """
    actors = [
        entry for entry in players if isinstance(entry, dict) and entry.get("is_actor") is True
    ]
    if len(actors) == 1 and isinstance(actors[0].get("seat"), int):
        return int(actors[0]["seat"])
    seat = payload.get("observer_seat")
    return int(seat) if isinstance(seat, int) else None


def _opponent_scoping_holds(
    observations: dict[str, Any],
    *,
    actor_seat_by_observation: dict[str, int | None],
    zone_key: str,
) -> tuple[bool, str]:
    """Whether every established observation scopes ``zone_key`` correctly.

    Requires, for every established observer: their own copy of the zone has
    real content, every other seat's copy exposes none, and the count is
    visible. A single unmasked opponent entry fails the whole check; partial
    masking is not a pass.
    """
    checked = 0
    for seat, payload in observations.items():
        actor_seat = actor_seat_by_observation.get(seat)
        if actor_seat is None:
            continue
        players = _players_of(payload)
        if not players:
            return False, f"{seat}: no players in the scoped state"
        for index, entry in enumerate(players):
            zones = _zones_of(entry)
            if zone_key not in zones:
                continue
            exposed = _zone_exposes_content(zones.get(zone_key))
            # The count must survive redaction: an absent or empty list leaks
            # nothing but also proves nothing about counts, so it is not a pass.
            count_visible = (
                isinstance(zones.get(zone_key), (list, tuple)) and len(zones[zone_key]) > 0
            )
            if index == actor_seat:
                if not exposed:
                    return False, f"{seat}: the observer cannot see their own {zone_key}"
            else:
                if exposed:
                    return (
                        False,
                        f"{seat}: seat {index} exposes {zone_key} content to a non-actor",
                    )
                if not count_visible:
                    return False, f"{seat}: the {zone_key} count is not visible to {seat}"
        checked += 1
    if checked == 0:
        return False, "no observation was established to a principal"
    return True, f"scoped correctly across {checked} established observation(s)"


def _universal_absence_holds(
    observations: dict[str, Any],
    *,
    actor_seat_by_observation: dict[str, int | None],
    zone_key: str,
) -> tuple[bool, str]:
    """Whether no established observation exposes any ``zone_key`` content.

    This is the ``HIDDEN_02`` shape: the obligation holds that a zone's
    identity is absent for every audience while its count remains. A library is
    hidden from everyone, including its owner, so the check is that *every*
    copy of that zone in *every* established observation is fully redacted and
    still counted.

    Only ``zone_key`` is inspected. Including the observer's own hand here
    would be a different obligation, and would fail a candidate that is
    behaving correctly.
    """
    checked = 0
    for seat, payload in observations.items():
        if actor_seat_by_observation.get(seat) is None:
            continue
        players = _players_of(payload)
        if not players:
            return False, f"{seat}: no players in the scoped state"
        for index, entry in enumerate(players):
            zones = _zones_of(entry)
            if zone_key not in zones:
                continue
            value = zones[zone_key]
            if _zone_exposes_content(value):
                return (
                    False,
                    f"{seat}: seat {index} exposes {zone_key} content "
                    f"(hidden from every audience is the obligation)",
                )
            if not (isinstance(value, (list, tuple)) and len(value) > 0):
                return (
                    False,
                    f"{seat}: the {zone_key} count is not visible, so identity "
                    "absence is unproven",
                )
        checked += 1
    if checked == 0:
        return False, "no observation was established to a principal"
    return True, f"absent and counted across {checked} established observation(s)"


def assess_hidden_obligations(
    observations: dict[str, Any],
    *,
    catalog: list[dict[str, Any]],
    requested_seats: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Classify every catalogued HIDDEN obligation against live observations.

    ``observations`` is the principal-scoped observation map already persisted
    as ``HIDDEN_INFO_<CANDIDATE>.json``'s ``principal_observations``:
    external seat label -> observation envelope containing a ``state`` view.

    The returned mapping has one entry per catalogued obligation and never
    invents an obligation that the catalog does not list.
    """
    usable = {
        seat: payload
        for seat, payload in observations.items()
        if isinstance(payload, dict) and "error" not in payload
    }
    scoping = validate_principal_scoping(
        observations, requested_seats=requested_seats or tuple(sorted(usable))
    )

    # Only an established requester may carry obligation credit. Re-derive the
    # established set with the same rules the scoping validator used rather than
    # trusting a separately-maintained list.
    actor_seat_by_observation: dict[str, int | None] = {}
    for seat, payload in usable.items():
        actor_seat_by_observation[seat] = _actor_seat_of(payload, _players_of(payload))

    dispositions: dict[str, dict[str, Any]] = {}
    for entry in catalog:
        obligation_id = str(entry.get("obligation_id", ""))
        if not obligation_id.startswith("HIDDEN"):
            continue
        description = str(entry.get("description", ""))
        spec = _GENERIC_SCOPING_OBLIGATIONS.get(obligation_id)

        if not usable:
            dispositions[obligation_id] = {
                "disposition": NOT_OBSERVABLE,
                "description": description,
                "reason": "no usable principal observation was available to assess it",
            }
            continue
        if not scoping.get("credible_as_principal_scoped_evidence", False):
            dispositions[obligation_id] = {
                "disposition": NOT_OBSERVABLE,
                "description": description,
                "reason": "principal scoping is not credible, so no observation may carry "
                "obligation credit; underlying findings: "
                + json.dumps(scoping.get("findings", [])[:3]),
            }
            continue

        if spec is None:
            dispositions[obligation_id] = {
                "disposition": NOT_OBSERVABLE,
                "description": description,
                "reason": "the obligation needs a per-scenario channel (a distinct game event, "
                "a face-down/revealed/shuffled zone, or an introspection boundary) that the "
                "generic principal-scoped state projection does not carry; it is not "
                "established and not refuted",
            }
            continue

        if spec["audience"] == "opponent":
            ok, detail = _opponent_scoping_holds(
                usable,
                actor_seat_by_observation=actor_seat_by_observation,
                zone_key=spec["zone"],
            )
        else:
            ok, detail = _universal_absence_holds(
                usable,
                actor_seat_by_observation=actor_seat_by_observation,
                zone_key=spec["zone"],
            )

        dispositions[obligation_id] = {
            "disposition": SATISFIED if ok else NOT_OBSERVABLE,
            "description": description,
            "reason": (
                f"the obligation is stated entirely over the {spec['zone']} scoping the "
                f"generic projection does expose, and the live observations show it holds: "
                f"{detail}"
                if ok
                else f"not established on the observations in hand: {detail}"
            ),
            "evidence_class": "DIRECTLY_VERIFIED" if ok else "UNKNOWN",
        }

    return {
        "schema_version": "commander-lab.hidden-obligation-disposition/1.0.0",
        "dispositions": dispositions,
        "counts": {
            SATISFIED: sum(1 for d in dispositions.values() if d["disposition"] == SATISFIED),
            NOT_OBSERVABLE: sum(
                1 for d in dispositions.values() if d["disposition"] == NOT_OBSERVABLE
            ),
            "total": len(dispositions),
        },
        "principal_scoping_credible": bool(
            scoping.get("credible_as_principal_scoped_evidence", False)
        ),
        "principal_scoping_verdict": scoping.get("verdict"),
        "promotion_note": "A SATISFIED disposition records that the observations support the "
        "obligation. It does not itself flip a FULL107 row: row outcomes belong to "
        "scripts/run_current_boundary_qualification.py under an active owner, and promotion "
        "must be a separate, evidence-bound step.",
    }


def load_catalog(path: Path) -> list[dict[str, Any]]:
    """Load the obligation catalog entries (the authoritative obligation list)."""
    document = json.loads(path.read_text(encoding="utf-8"))
    obligations = document.get("obligations", document)
    return obligations if isinstance(obligations, list) else []

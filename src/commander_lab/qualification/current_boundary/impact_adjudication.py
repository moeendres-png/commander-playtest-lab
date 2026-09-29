"""Impact adjudication for evidence produced under the XMage shuffle defect.

PR #293 (merged to ``main`` as ``adee8b16``) removed
``XmageBridgePlayer.shuffleLibrary``, which was overridden as a no-op. On the
XMage generic lane that meant:

* CR 103.3 opening shuffles never happened, and neither did mulligan shuffles
  nor any "search ... then shuffle";
* every library stayed in decklist order, so a principal who knew the decklist
  knew every library order and every opening hand;
* the engine's ``SHUFFLE_LIBRARY`` replacement check and ``LIBRARY_SHUFFLED``
  event were suppressed.

The committed current-boundary XMage column was produced on that lane. PR #293's
own handoff records that and asks for adjudication rather than deciding it. This
module performs that adjudication for the findings *this* workstream derived from
that column.

The adjudication rule is deliberately narrow. A finding is impacted only when its
obligation depends on the behaviour the defect corrupted -- that is, on library
order, opening-hand contents, or shuffle events. Findings about channels the
defect did not touch are left alone. Marking everything impacted would be as
dishonest as marking nothing.

Consequences the adjudication does not draw on its own authority:

* It never flips a gate verdict and never rewrites a disposition. It records that
  an existing disposition can no longer be cited for the current bridge.
* It does not requalify anything. Requalification needs the current-boundary
  runner, which is under another active writer, so the requirement is recorded
  and handed over rather than raced.
"""

from __future__ import annotations

from typing import Any

IMPACTED = "IMPACTED_REQUALIFICATION_REQUIRED"
UNAFFECTED = "UNAFFECTED_BY_THE_DEFECT"

# Findings this workstream derived from the XMage column, and whether the
# obligation each rests on depends on the corrupted behaviour.
#
# ``hidden_01`` and ``hidden_02`` are impacted for the same reason the defect is
# a hidden-information leak at all: the obligation is that hand and library
# *identity and order* are not disclosed, and the defect made both derivable
# from the decklist. A principal who knows a decklist read both off the ordering,
# which is precisely the disclosure the obligations exist to forbid. The
# projection did mask the arrays; the lane still failed the obligation.
#
# ``pb08_seed`` is impacted because the same change flipped the lane from
# ``seed_supported: false`` to an acknowledged, engine-readback-verified Rules
# seed, so the recorded precondition is a statement about the old bridge.
#
# ``af11_technical_facts`` is unaffected: process topology, adapter identity and
# licence metadata do not depend on library order or RNG. Re-deriving it would
# add nothing.
_KNOWN_FINDINGS: dict[str, dict[str, Any]] = {
    "xmage_hidden_01": {
        "description": "opponent hand identities absent while count remains visible",
        "depends_on_corrupted_behaviour": True,
        "channel": "hand identity and opening-hand derivation",
    },
    "xmage_hidden_02": {
        "description": "library identities/order absent while count remains visible",
        "depends_on_corrupted_behaviour": True,
        "channel": "library order",
    },
    "xmage_pb08_seed_precondition": {
        "description": "Rules RNG seed control on the generic lane",
        "depends_on_corrupted_behaviour": True,
        "channel": "Rules randomness binding",
    },
    "af11_technical_facts": {
        "description": "interop and licence topology",
        "depends_on_corrupted_behaviour": False,
        "channel": "process/adapter topology, not game state",
    },
}


def adjudicate_xmage_shuffle_impact(
    *, defect_change: dict[str, Any], findings: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Classify this workstream's XMage findings against the shuffle defect.

    ``defect_change`` identifies the change that removed the no-op, so the
    adjudication is bound to a specific revision rather than to prose.
    """
    findings = findings if findings is not None else _KNOWN_FINDINGS
    dispositions: dict[str, dict[str, Any]] = {}
    for finding_id, finding in sorted(findings.items()):
        impacted = bool(finding.get("depends_on_corrupted_behaviour"))
        dispositions[finding_id] = {
            "disposition": IMPACTED if impacted else UNAFFECTED,
            "description": finding.get("description"),
            "channel": finding.get("channel"),
            "reason": (
                "the obligation depends on library order, opening-hand contents or shuffle "
                "events, which the removed shuffleLibrary no-op corrupted: every library stayed "
                "in decklist order and every opening hand was derivable from it, so the "
                "observation cannot be cited for the current bridge"
                if impacted
                else "the obligation does not depend on library order, opening hands or shuffle "
                "events, so the defect does not bear on it"
            ),
        }

    return {
        "schema_version": "commander-lab.impact-adjudication/1.0.0",
        "candidate": "xmage",
        "defect": {
            "summary": (
                "XmageBridgePlayer.shuffleLibrary was a no-op, silently skipping CR 103.3 "
                "opening shuffles, mulligan shuffles and search-then-shuffle effects, leaving "
                "every library in decklist order and suppressing SHUFFLE_LIBRARY replacements "
                "and LIBRARY_SHUFFLED events"
            ),
            "repaired_by": defect_change.get("head"),
            "repaired_in": defect_change.get("contained_in") or [],
            "source": defect_change.get("source"),
            "impact_scope_statement": (
                "PR #293's handoff states that any generic-lane observation depending on library "
                "order, opening hands or shuffle events was produced under this defect, "
                "explicitly including the committed current-boundary XMage column, and asks for "
                "adjudication rather than deciding it"
            ),
        },
        "dispositions": dispositions,
        "counts": {
            IMPACTED: sum(1 for d in dispositions.values() if d["disposition"] == IMPACTED),
            UNAFFECTED: sum(1 for d in dispositions.values() if d["disposition"] == UNAFFECTED),
            "total": len(dispositions),
        },
        "consequences": {
            "gate_verdicts_changed": False,
            "dispositions_rewritten": False,
            "requalification_required": [
                finding_id for finding_id, d in dispositions.items() if d["disposition"] == IMPACTED
            ],
            "why_not_requalified_here": (
                "requalification needs scripts/run_current_boundary_qualification.py, which is "
                "under PR #284's active writer lock; the requirement is recorded and handed over "
                "rather than raced"
            ),
        },
        "what_this_does_not_say": [
            "that the repaired bridge now satisfies any impacted obligation, which only a fresh "
            "run at the repaired revision can establish",
            "that the pre-repair run was fabricated, which it was not: it faithfully reports the "
            "lane that existed",
            "that any gate verdict moves, in either direction",
        ],
    }


def default_defect_change() -> dict[str, Any]:
    """The recorded identity of the repair, so the adjudication is bound to it."""
    return {
        "head": "938719d0",
        "contained_in": [],
        "source": (
            "commander-playtest-lab PR #293, MERGED to main as adee8b16: deleted the "
            "XmageBridgePlayer.shuffleLibrary no-op in favour of PlayerImpl.shuffleLibrary"
        ),
    }

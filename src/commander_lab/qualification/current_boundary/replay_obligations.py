"""Per-obligation disposition for the PB-08 replay and RNG rows.

The five ``REPLAY_*``/``RNG_*`` obligations were recorded as one undifferentiated
``UNKNOWN`` family. They are not one thing, and the run's own evidence already
separates them:

* ``RNG_RULES_TAPE`` is about the Rules Core acknowledging a seed. That is
  observable in the create-game response, and the two candidates differ: Forge
  acknowledges the requested seed, XMage does not.
* The four ``REPLAY_*`` obligations all require a semantic replay export seam.
  Both candidates currently refuse it and fail closed, each with its own error
  code. A refusal is a real observation, and it is evidence that the seam is
  absent -- it is not evidence that replay works.

This module records that split, and it records *why* each unestablished
obligation is unestablished, so the gap is attributed to a named missing seam
rather than to the family. It deliberately does not:

* treat a fail-closed refusal as a pass. An unsupported message is an absent
  capability, never a satisfied obligation;
* treat an acknowledged seed as a completed ``RulesRngTape``. Acknowledgement is
  the precondition for the tape obligation, not the obligation itself, so the
  obligation stays unestablished while the acknowledgement is recorded as a
  fact;
* infer replay from a second run agreeing. A same-seed twin is a different
  obligation from a semantic export, and only the export seam is checked here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ACKNOWLEDGED = "SEED_ACKNOWLEDGED_CAPABILITY_OBSERVED"
UNACKNOWLEDGED = "NOT_OBSERVABLE_ON_CURRENT_SURFACE"

# Which replay obligations need the semantic export seam, and how each one's
# absence is detected. The probe is the same fail-closed refusal both
# candidates currently return; recognising it is what lets the reason name the
# missing seam instead of the whole family.
_REPLAY_EXPORT_OBLIGATIONS: tuple[str, ...] = (
    "REPLAY_DECISION_TAPE",
    "REPLAY_EVENT_TAPE",
    "REPLAY_CLEAN_PROCESS",
    "REPLAY_STATE_HASHES",
)

# Any of these codes means the engine refused the export rather than performing
# it. Treating one of them as success would invert the meaning of the evidence.
_REFUSAL_CODES: frozenset[str] = frozenset(
    {
        "unsupported_message",
        "unknown_message",
        "unsupported",
        "not_supported",
        "unsupported_capability",
    }
)


def _refused(payload: Any) -> tuple[bool, str]:
    """Whether a semantic-replay response is a refusal, and the engine's reason.

    Returns ``(refused, detail)``. A response that actually carries replay
    content is not a refusal, and the caller must not credit it here either,
    because this module only reports seam availability.
    """
    if payload is None:
        return True, "no semantic replay response was produced"
    if isinstance(payload, dict):
        errors = payload.get("error")
        if isinstance(errors, list) and errors:
            codes = [str(e.get("code")) for e in errors if isinstance(e, dict)]
            messages = [str(e.get("message")) for e in errors if isinstance(e, dict)]
            recognised = sorted({c for c in codes if c in _REFUSAL_CODES})
            if recognised:
                return (
                    True,
                    f"engine refused the export ({', '.join(recognised)}): {'; '.join(messages)}",
                )
            return True, f"engine returned an error instead of a replay: {'; '.join(messages)}"
        # A payload carrying replay content is still not credited here: proving a
        # tape is correct is a separate obligation from proving the seam exists.
        return True, "a replay payload was returned but this module reports seam availability only"
    return True, "semantic replay response had an unexpected shape"


def assess_replay_obligations(
    artifact: dict[str, Any], *, catalog: list[dict[str, Any]]
) -> dict[str, Any]:
    """Classify the replay/RNG obligations against one candidate's run."""
    binding = artifact.get("rules_rng_binding") or {}
    controlled = bool(binding.get("controlled"))
    acknowledged = binding.get("acknowledged_seed")
    requested = binding.get("requested_seed")
    classification = str(binding.get("classification") or "UNCLASSIFIED")

    refused, detail = _refused(artifact.get("semantic_replay"))

    dispositions: dict[str, dict[str, Any]] = {}
    for entry in catalog:
        obligation_id = str(entry.get("obligation_id", ""))
        if not obligation_id.startswith(("REPLAY_", "RNG_")):
            continue
        description = str(entry.get("description", ""))

        if obligation_id == "RNG_RULES_TAPE":
            if controlled and acknowledged == requested:
                dispositions[obligation_id] = {
                    "disposition": ACKNOWLEDGED,
                    "description": description,
                    "reason": (
                        f"the engine acknowledged the requested seed {acknowledged!r} in the "
                        f"create-game response, so seed control is a precondition this candidate "
                        "meets; the RulesRngTape itself is a separate obligation and is not "
                        "established by the acknowledgement alone"
                    ),
                    "evidence_class": "DIRECTLY_VERIFIED",
                }
            else:
                dispositions[obligation_id] = {
                    "disposition": UNACKNOWLEDGED,
                    "description": description,
                    "reason": (
                        f"the engine did not acknowledge the requested seed {requested!r} "
                        f"(classification {classification}); without an acknowledged root seed no "
                        "RulesRngTape can be bound to the engine's randomness, so this candidate "
                        "cannot demonstrate the obligation on this surface"
                    ),
                    "evidence_class": "DIRECTLY_VERIFIED",
                }
            continue

        if obligation_id in _REPLAY_EXPORT_OBLIGATIONS:
            dispositions[obligation_id] = {
                "disposition": UNACKNOWLEDGED,
                "description": description,
                "reason": (
                    f"this obligation needs the semantic replay export seam, which the engine "
                    f"refused rather than served: {detail}. A fail-closed refusal is an absent "
                    "capability, never a satisfied obligation"
                ),
                "evidence_class": "DIRECTLY_VERIFIED",
            }
            continue

        dispositions[obligation_id] = {
            "disposition": UNACKNOWLEDGED,
            "description": description,
            "reason": "no observation in this run bears on this obligation",
            "evidence_class": "UNKNOWN",
        }

    return {
        "schema_version": "commander-lab.replay-obligation-disposition/1.0.0",
        "dispositions": dispositions,
        "counts": {
            ACKNOWLEDGED: sum(1 for d in dispositions.values() if d["disposition"] == ACKNOWLEDGED),
            UNACKNOWLEDGED: sum(
                1 for d in dispositions.values() if d["disposition"] == UNACKNOWLEDGED
            ),
            "total": len(dispositions),
        },
        "seed_binding": {
            "requested_seed": requested,
            "acknowledged_seed": acknowledged,
            "classification": classification,
            "controlled": controlled,
        },
        "replay_export_seam": {"refused": refused, "detail": detail},
        "promotion_note": (
            "A disposition here reports what the run observed about the seed acknowledgement and "
            "the replay export seam. It never turns a fail-closed refusal into a pass, and it does "
            "not itself flip a FULL107 row: row outcomes belong to "
            "scripts/run_current_boundary_qualification.py under an active owner."
        ),
    }


def load_catalog(path: Path) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    obligations = document.get("obligations", document)
    return obligations if isinstance(obligations, list) else []

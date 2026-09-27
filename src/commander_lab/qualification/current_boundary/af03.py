"""AF03 RULES_AUTHORITY probe: prove the engine, not the harness, owns legality.

AF03 was previously a hard-coded ``"verdict": "PASS"`` in the assembler with an
evidence list describing deck imports that were never performed, and no AF03
artifact existed at all. Every claim in that list was therefore
``CODE_DERIVED`` at best and read as runtime evidence.

This module runs the negative probes for real against a live bridge and derives
the verdict from the responses. Rules authority is the qualified engine's alone:
the harness constructs deliberately illegal decks and requires the engine to
refuse them. A probe that the engine does not refuse is a FAIL, because it means
the boundary accepted something the Rules forbid. A probe that could not be run
is UNKNOWN, never PASS.
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from typing import Any

from .bridge_launcher import BridgeProcess

# Each probe mutates one aspect of an otherwise legal Commander deck. The
# mutation is named so the evidence says which authority was exercised.
ILLEGAL_DECK_PROBES: tuple[tuple[str, str, str], ...] = (
    (
        "unknown_card_name",
        "deck_import_rejects_unknown_card",
        "a mainboard entry naming a card neither candidate knows",
    ),
    (
        "commander_not_in_pool",
        "deck_import_rejects_non_commander",
        "the commander is a real card but is not a legal Commander",
    ),
    (
        "colour_identity_violation",
        "deck_import_rejects_colour_identity_violation",
        "the deck's colour identity does not match the commander's, which CR "
        "2.3 and the Commander format require",
    ),
    (
        "mainboard_short_of_one_hundred",
        "deck_import_rejects_wrong_deck_size",
        "a Commander deck with fewer than 100 cards in the mainboard",
    ),
    (
        "empty_mainboard",
        "deck_import_rejects_empty_mainboard",
        "a Commander deck with an empty mainboard",
    ),
)


def _mutate(base: dict[str, Any], probe: str) -> dict[str, Any]:
    """Return a copy of ``base`` made illegal in exactly one documented way."""
    deck = copy.deepcopy(base)
    if probe == "unknown_card_name":
        deck["mainboard"] = [*deck["mainboard"][:-1], "Definitely Not A Real Card Name"]
    elif probe == "commander_not_in_pool":
        deck["commander_names"] = ["Hill Giant"]
    elif probe == "colour_identity_violation":
        # Isamaru is {W}{W}; replacing the monobound with black permanents
        # makes the deck violate the commander's colour identity.
        deck["mainboard"] = ["Black Lotus"] * len(deck["mainboard"])
    elif probe == "mainboard_short_of_one_hundred":
        deck["mainboard"] = deck["mainboard"][:50]
    elif probe == "empty_mainboard":
        deck["mainboard"] = []
    else:  # pragma: no cover - the table is closed
        raise ValueError(f"unknown probe {probe!r}")
    # Each probe is a distinct deck, not the control deck wearing a mutation.
    # Sharing the control's deck_id would let a provider answer from a cache or
    # deduplicate the import, and the probe would prove nothing.
    deck["deck_id"] = f"af03-probe-{probe}"
    deck["deck_hash"] = hashlib.sha256(
        "|".join([*deck.get("commander_names", []), *deck.get("mainboard", [])]).encode("utf-8")
    ).hexdigest()
    return deck


def _accepted(response: dict[str, Any]) -> bool:
    """True when the engine accepted the deck. Acceptance is the failure mode."""
    return response.get("success") is True


@dataclass
class AF03Probe:
    probe: str
    invariant: str
    obligation: str
    response: dict[str, Any] = field(default_factory=dict)
    verdict: str = "UNKNOWN"
    detail: str = ""

    def to_document(self) -> dict[str, Any]:
        return {
            "probe": self.probe,
            "invariant": self.invariant,
            "obligation": self.obligation,
            "verdict": self.verdict,
            "detail": self.detail,
            "engine_response": self.response,
        }


@dataclass
class AF03Report:
    candidate: str
    probes: list[AF03Probe] = field(default_factory=list)
    legal_control_response: dict[str, Any] = field(default_factory=dict)

    @property
    def verdict(self) -> str:
        if not self.probes:
            return "UNKNOWN"
        if any(probe.verdict == "FAIL" for probe in self.probes):
            return "FAIL"
        if any(probe.verdict == "UNKNOWN" for probe in self.probes):
            return "UNKNOWN"
        return "PASS"

    @property
    def failed(self) -> list[AF03Probe]:
        return [probe for probe in self.probes if probe.verdict != "PASS"]

    def to_document(self) -> dict[str, Any]:
        return {
            "gate": "AF03",
            "name": "RULES_AUTHORITY",
            "candidate": self.candidate,
            "verdict": self.verdict,
            "authority": "ENGINE_ONLY",
            "harness_role": "constructs deliberately illegal decks and requires refusal",
            "probes": [probe.to_document() for probe in self.probes],
            "legal_control": {
                "purpose": "an unmodified legal deck must import, so a refusal is "
                "evidence about the mutation and not about the deck format",
                "response": self.legal_control_response,
            },
            "nonblocking_limitations": [
                "proves the engine refuses these specific illegality classes at the "
                "import boundary; it is not an exhaustive proof of deck legality",
            ],
        }


def run_af03(
    proc: BridgeProcess,
    *,
    candidate: str,
    legal_deck: dict[str, Any],
) -> AF03Report:
    """Run the AF03 negative deck-import probes against a live bridge.

    A legal control import runs first. Without it, a provider that refused every
    deck would score a perfect AF03 while being unable to play Commander at all.
    """
    report = AF03Report(candidate=candidate)

    control = proc.request("import_deck", {"deck": legal_deck})
    report.legal_control_response = control
    if not _accepted(control):
        for probe_name, invariant, obligation in ILLEGAL_DECK_PROBES:
            report.probes.append(
                AF03Probe(
                    probe_name,
                    invariant,
                    obligation,
                    response={"skipped": "the legal control deck did not import"},
                    verdict="UNKNOWN",
                    detail="the unmodified legal deck was refused, so these refusals "
                    "would prove nothing about deck legality",
                )
            )
        return report

    for probe_name, invariant, obligation in ILLEGAL_DECK_PROBES:
        illegal = _mutate(legal_deck, probe_name)
        try:
            response = proc.request("import_deck", {"deck": illegal})
        except Exception as exc:  # a transport error is not a legality verdict
            report.probes.append(
                AF03Probe(
                    probe_name,
                    invariant,
                    obligation,
                    response={"error": str(exc)},
                    verdict="UNKNOWN",
                    detail="the probe could not be delivered, so refusal is unproven",
                )
            )
            continue
        if _accepted(response):
            verdict = "FAIL"
            detail = "the engine ACCEPTED a deck made illegal by this mutation, so the boundary did not enforce the Rules"
        elif response.get("success") is False or "error" in response or "status" in response:
            verdict = "PASS"
            detail = "the engine refused the mutated deck at the import boundary"
        else:
            verdict = "UNKNOWN"
            detail = f"unrecognised refusal shape: {response!r}"
        report.probes.append(
            AF03Probe(probe_name, invariant, obligation, response, verdict, detail)
        )

    return report

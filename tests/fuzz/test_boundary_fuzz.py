"""Boundary fuzzing for the two untrusted-input surfaces.

Both tests are deliberately explicit about what they do and do not establish, because
the file previously was not.

``test_protocol_json_fuzz_is_deterministically_rejected`` fuzzed raw garbage and
**asserted nothing**. Measured: of its 128 seeds, **zero** produce parseable JSON, so
``EngineProtocolRequest.model_validate`` was never called even once -- while the name
claimed a property about deterministic rejection. A green run therefore said nothing
about the validator. The near-miss corpus below is what actually exercises it, and it
counts what it exercises so the same vacuity cannot return unnoticed.

``test_plaintext_importer_fuzz_never_executes_or_hangs`` did have a real implicit
assertion (an unsuppressed exception fails the test), but its name claimed two
properties it never checked: that garbage "never executes", and that the call cannot
hang. Neither is established here; both would need machinery this file does not have.
The count assertions make the real invariant visible instead of leaving a reader to
infer it.
"""

from __future__ import annotations

import copy
import json
import random
import string
from pathlib import Path

import pytest
from pydantic import ValidationError

from commander_lab.cards.catalog import CardCatalog
from commander_lab.importers import DeckImportOptions, PlaintextDeckImporter
from commander_lab.models import EngineProtocolRequest

GARBAGE_SEEDS = 128
IMPORT_SEEDS = 64


def _garbage(seed: int, length: int) -> str:
    rng = random.Random(seed)
    alphabet = string.printable + "Ω🕷️’\x00"
    return "".join(rng.choice(alphabet) for _ in range(length))


def _valid_request_payload() -> dict:
    """Minimal payload that validates, asserted as valid below rather than assumed."""
    return {"request_id": "r-1", "message_type": "start_engine"}


def _near_miss_mutations() -> list[tuple[str, dict]]:
    """Structurally plausible requests carrying exactly one defect each."""

    def mutant(label: str, apply) -> tuple[str, dict]:
        payload = copy.deepcopy(_valid_request_payload())
        apply(payload)
        return label, payload

    return [
        mutant("request_id removed", lambda p: p.pop("request_id")),
        mutant("message_type removed", lambda p: p.pop("message_type")),
        mutant("request_id is null", lambda p: p.update(request_id=None)),
        mutant("request_id is an int", lambda p: p.update(request_id=123)),
        mutant("message_type is unknown", lambda p: p.update(message_type="not_a_message_type")),
        mutant("message_type is null", lambda p: p.update(message_type=None)),
        mutant("message_type is an int", lambda p: p.update(message_type=123)),
        mutant("protocol_version is a list", lambda p: p.update(protocol_version=["2.0.0"])),
        mutant("payload is a string", lambda p: p.update(payload="not-an-object")),
        mutant("params is a number", lambda p: p.update(params=5)),
        mutant("game_id is a number", lambda p: p.update(game_id=7)),
        mutant("unknown extra key", lambda p: p.update(unexpected_key="x")),
    ]


def test_the_baseline_payload_validates() -> None:
    """Guard for the corpus: only meaningful if the unmutated payload is accepted."""
    EngineProtocolRequest.model_validate(_valid_request_payload())


def test_protocol_rejects_every_near_miss_mutation() -> None:
    """Fail closed on inputs that look like requests but are not."""
    mutants = _near_miss_mutations()
    assert len(mutants) >= 10, "corpus shrank; the validator would be under-exercised"
    for label, payload in mutants:
        try:
            EngineProtocolRequest.model_validate(payload)
        except ValidationError:
            continue
        pytest.fail(f"{label}: the validator accepted a payload it must refuse")


def test_protocol_validation_is_stable_and_does_not_mutate_its_input() -> None:
    """The property the previous test name claimed, now checked in a falsifiable way.

    Two real invariants, either of which can genuinely break:

    * the validator must not mutate the caller's payload -- a validator that pops keys or
      normalises in place would corrupt a caller that reuses the dict;
    * the same payload must produce the same outcome twice.

    A bare "validate twice and compare" would essentially never fail and would itself be a
    weak guarantee, so the payload snapshot is the part doing the work.
    """

    def outcome(payload: dict) -> str:
        try:
            EngineProtocolRequest.model_validate(payload)
            return "accepted"
        except ValidationError as exc:
            return f"rejected:{len(exc.errors())}:{sorted(e['type'] for e in exc.errors())}"

    for label, payload in _near_miss_mutations():
        snapshot = copy.deepcopy(payload)
        first = outcome(payload)
        assert payload == snapshot, f"{label}: validation mutated the caller's payload"
        second = outcome(payload)
        assert first == second, f"{label}: {first!r} then {second!r}"


def test_garbage_text_never_becomes_a_protocol_request() -> None:
    """Guards the outer layer: arbitrary bytes must never become a request object.

    Honest scope, measured rather than assumed: with this generator **none** of the
    seeds produces parseable JSON, so ``model_validate`` is not reached here. That is
    precisely why the near-miss corpus above exists. The final assertion pins that
    measurement, so if the generator starts producing dicts, the reader is told to
    re-derive the corpus instead of silently getting more coverage than the docstring
    describes -- or less.
    """
    parsed = 0
    for seed in range(GARBAGE_SEEDS):
        raw = _garbage(seed, seed % 500)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        parsed += 1
        with pytest.raises(ValidationError):
            EngineProtocolRequest.model_validate(value)
    assert parsed == 0, (
        f"the garbage generator now yields {parsed} parseable dict(s). That is a change in a "
        "test fixture, not a product regression: re-derive the near-miss corpus and re-check "
        "the scope note in this docstring, which currently says this path is never reached."
    )


def test_plaintext_importer_rejects_garbage_without_unexpected_errors(
    repo_root: Path, tmp_path: Path
) -> None:
    """Garbage must be refused, and only with the documented exception types.

    Previously named ``..._never_executes_or_hangs``, which claimed two properties this
    test does not check. What it does check is now explicit: every seed is either
    refused with a documented exception type or would be counted as accepted, and
    acceptance is asserted to be zero. An unexpected exception type still fails the
    test, as before, but no longer as the only thing holding it up.
    """
    catalog = CardCatalog.from_json(repo_root / "data/cards/oracle_subset.json")
    importer = PlaintextDeckImporter(catalog)
    options = DeckImportOptions(
        deck_id="fuzz", name="Fuzz", commander_names=("Korvold, Fae-Cursed King",)
    )

    accepted = 0
    rejected = 0
    for seed in range(IMPORT_SEEDS):
        path = tmp_path / f"deck-{seed}.txt"
        path.write_text(_garbage(seed, seed % 300), encoding="utf-8", errors="ignore")
        try:
            importer.import_file(path, options)
        except (ValueError, ValidationError, UnicodeError):
            rejected += 1
        else:
            accepted += 1

    assert rejected + accepted == IMPORT_SEEDS, "a seed was neither accepted nor refused"
    assert accepted == 0, (
        f"{accepted} of {IMPORT_SEEDS} garbage inputs were accepted as decks. The importer is "
        "expected to fail closed on unparseable text; if that changed deliberately, this "
        "assertion is the one to revisit, not the exception clause above."
    )

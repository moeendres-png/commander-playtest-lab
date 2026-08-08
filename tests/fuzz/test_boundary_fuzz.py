from __future__ import annotations

import contextlib
import json
import random
import string
from pathlib import Path

from pydantic import ValidationError

from commander_lab.cards.catalog import CardCatalog
from commander_lab.importers import DeckImportOptions, PlaintextDeckImporter
from commander_lab.models import EngineProtocolRequest


def _garbage(seed: int, length: int) -> str:
    rng = random.Random(seed)
    alphabet = string.printable + "Ω🕷️\u2019\x00"
    return "".join(rng.choice(alphabet) for _ in range(length))


def test_plaintext_importer_fuzz_never_executes_or_hangs(repo_root: Path, tmp_path: Path) -> None:
    catalog = CardCatalog.from_json(repo_root / "data/cards/oracle_subset.json")
    importer = PlaintextDeckImporter(catalog)
    options = DeckImportOptions(
        deck_id="fuzz", name="Fuzz", commander_names=("Korvold, Fae-Cursed King",)
    )
    for seed in range(64):
        path = tmp_path / f"deck-{seed}.txt"
        path.write_text(_garbage(seed, seed % 300), encoding="utf-8", errors="ignore")
        with contextlib.suppress(ValueError, ValidationError, UnicodeError):
            importer.import_file(path, options)


def test_protocol_json_fuzz_is_deterministically_rejected() -> None:
    for seed in range(128):
        raw = _garbage(seed, seed % 500)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            with contextlib.suppress(ValidationError):
                EngineProtocolRequest.model_validate(value)

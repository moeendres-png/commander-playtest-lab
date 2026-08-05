from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _variant_hash(root: Path, hash_seed: str) -> str:
    code = r'''
from commander_lab.engine.structural import load_project_structural_decks
from commander_lab.tools.candidates import load_candidate_profiles
from commander_lab.optimization.experiments import variant_deck
root = r"ROOT"
decks = load_project_structural_decks(root, include_current_opponents=True)
candidates = load_candidate_profiles(root)
baseline = decks["korvold/current"]
card = candidates["korvold/idol-of-oblivion"].card
variant = variant_deck(
    baseline,
    variant_id="cross-process-test",
    removals=("Scouring Swarm",),
    additions=(card,),
)
print(variant.deck_hash)
'''.replace("ROOT", str(root))
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONPATH"] = str(root / "src")
    return subprocess.check_output([sys.executable, "-c", code], env=env, text=True).strip()


def test_variant_hash_is_independent_of_python_hash_seed() -> None:
    root = Path.cwd()
    assert _variant_hash(root, "1") == _variant_hash(root, "987654")

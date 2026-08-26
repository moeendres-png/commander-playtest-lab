from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

from commander_lab.engine.structural import load_project_structural_decks

EXPECTED_IDS = [
    "N017", "N018", "N019", "N020", "N021", "N022", "N023", "N024",
    "N025", "N026", "N027", "N028", "C016", "C004", "C030", "C017",
    "C029", "C011", "C020", "C043",
]
EXPECTED_COMMANDERS = {"Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run(*args: str) -> None:
    subprocess.run(list(args), check=True)


def add_schedule(old: set[int], sources: list[dict], path: Path, label: str, basis: str) -> None:
    obj = load_json(path)
    before = len(old)
    old.update(int(row["master_seed"]) for row in obj.get("schedule", []))
    old.update(int(value) for value in obj.get("master_seeds", []))
    sources.append({"source": label, "new_unique_seeds": len(old) - before, "basis": basis})


def validate_candidates(campaign: Path, output: Path) -> dict:
    payload = load_json(campaign / "input/CANDIDATES_20.json")
    ids = [str(row["candidate_id"]) for row in payload["candidates"]]
    assert ids == EXPECTED_IDS
    assert len(ids) == len(set(ids)) == 20
    assert all(len(row["mainboard"]) == 98 for row in payload["candidates"])
    assert all(set(row["commander_names"]) == EXPECTED_COMMANDERS for row in payload["candidates"])
    (output / "CANDIDATES_20.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def validate_schedule(campaign: Path, output: Path) -> None:
    run(
        sys.executable,
        str(campaign / "scripts/generate_arch_frontier_schedule.py"),
        "--output",
        str(output / "SEED_SCHEDULE.json"),
        "--audit-output",
        str(output / "BALANCE_AUDIT.json"),
    )
    audit = load_json(output / "BALANCE_AUDIT.json")
    assert audit["status"] == "PASS"
    assert audit["scenario_count"] == 2048
    assert audit["candidate_count"] == 20
    assert audit["target_game_count"] == 40960
    assert audit["candidate_seat_each"] == 512
    assert audit["starting_player_seat_each"] == 512
    assert audit["candidate_by_starting_seat_cell_each"] == 128
    assert set(audit["opponent_appearances_per_candidate"].values()) == {768}
    assert audit["triplet_type_count"] == 56
    assert (audit["triplet_multiplicity_min"], audit["triplet_multiplicity_max"]) == (36, 37)
    assert audit["pair_type_count"] == 28
    assert (audit["pair_multiplicity_min"], audit["pair_multiplicity_max"]) == (219, 220)
    for counts in audit["physical_seat_counts"].values():
        assert set(counts.values()) == {192}
    for counts in audit["relative_position_counts"].values():
        assert set(counts.values()) == {256}


def validate_seed_disjointness(root: Path, output: Path) -> None:
    ext2 = Path("/tmp/generate_ext2.py")
    real8 = Path("/tmp/generate_real8.py")
    morcant = Path("/tmp/generate_morcant.py")
    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/moeendres-png/commander-playtest-lab/"
        "runs/rogshai-48-structural-12opp-20260825/scripts/generate_structural_ext2_schedule.py",
        ext2,
    )
    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/moeendres-png/commander-playtest-lab/"
        "runs/rogshai-48-structural-12opp-20260825/scripts/generate_structural_real_current_8_schedule.py",
        real8,
    )
    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/moeendres-png/commander-playtest-lab/"
        "runs/rogshai-morcant-balanced-post-seatfix-20260825/scripts/generate_morcant_balanced_schedule.py",
        morcant,
    )

    frozen = load_json(
        root / "artifacts/rogshai-postfix-opponent-balance-2026-08-25/input/PRIOR_ACTUAL_BROAD_R1_SEEDS.json"
    )
    old: set[int] = set()
    sources: list[dict] = []
    for source in frozen["sources"]:
        before = len(old)
        old.update(int(value) for value in source["master_seeds"])
        sources.append(
            {"source": source["campaign"], "new_unique_seeds": len(old) - before, "basis": source["evidence"]}
        )

    for block in range(9, 17):
        path = Path(f"/tmp/ext2-{block}.json")
        run(sys.executable, str(ext2), "--block", str(block), "--output", str(path))
        add_schedule(old, sources, path, f"12opp-R2-block-{block}", "regenerated frozen design")
    for block in range(1, 9):
        path = Path(f"/tmp/real8-{block}.json")
        run(sys.executable, str(real8), "--block", str(block), "--output", str(path))
        add_schedule(old, sources, path, f"real-current-8-block-{block}", "regenerated frozen design")

    run(sys.executable, str(morcant), "--output", "/tmp/morcant.json", "--audit-output", "/tmp/morcant-audit.json")
    add_schedule(old, sources, Path("/tmp/morcant.json"), "morcant-sensitivity-design", "regenerated frozen design")

    prior_generators = [
        ("generate_rogshai_postfix_balance_schedule.py", "/tmp/postfix.json", "/tmp/postfix-audit.json", "postfix-opponent-balance-7680-v3"),
        ("generate_rogshai_near_neighbor_schedule.py", "/tmp/near.json", "/tmp/near-audit.json", "postfix-near-neighbor-5120"),
        ("generate_rogshai_postfix_eightopp_equalize_schedule.py", "/tmp/eightopp.json", "/tmp/eightopp-audit.json", "postfix-eightopp-equalize-15360"),
    ]
    for script, path, audit, label in prior_generators:
        run(sys.executable, str(root / "scripts" / script), "--output", path, "--audit-output", audit)
        add_schedule(old, sources, Path(path), label, "completed post-fix campaign design")

    new_obj = load_json(output / "SEED_SCHEDULE.json")
    new = {int(row["master_seed"]) for row in new_obj["schedule"]}
    overlap = sorted(new & old)
    assert len(new) == 2048
    assert not overlap, overlap[:20]
    report = {
        "schema_version": "rogshai-architecture-frontier-seed-disjointness-1.0.0",
        "status": "PASS",
        "new_seed_count": 2048,
        "prior_unique_seed_count_checked": len(old),
        "overlap_count": 0,
        "replacement_seeds_allowed": False,
        "sources": sources,
    }
    (output / "SEED_DISJOINTNESS_AUDIT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def validate_materialization(root: Path, campaign: Path, output: Path, payload: dict) -> None:
    runner_path = campaign / "scripts/run_arch_frontier_block.py"
    spec = importlib.util.spec_from_file_location("arch_frontier_runner", runner_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    candidates = module.materialize_candidates(root, payload)
    assert len(candidates) == 20
    assert len({deck.deck_hash for deck in candidates.values()}) == 20
    project_decks = load_project_structural_decks(root, include_current_opponents=True)
    for key, deck_id in module.OPPONENT_IDS.items():
        assert deck_id in project_decks, (key, deck_id)
        assert len(project_decks[deck_id].cards) == 100
    assert module.OPPONENT_EVIDENCE_CLASSES["cosmic"] == "partially_observed_synthetic_completion_public_deck_proxy"
    assert module.OPPONENT_EVIDENCE_CLASSES["morcant"] == "partially_observed_synthetic_completion_pool_constrained"
    report = {
        "status": "PASS",
        "candidate_count": 20,
        "unique_candidate_hashes": 20,
        "pre_gameplay_elimination": 0,
        "opponents": module.OPPONENT_IDS,
        "opponent_evidence_classes": module.OPPONENT_EVIDENCE_CLASSES,
    }
    (output / "PRE_GAMEPLAY_VALIDATION.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    campaign = Path(args.campaign).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    payload = validate_candidates(campaign, output)
    validate_schedule(campaign, output)
    validate_seed_disjointness(root, output)
    validate_materialization(root, campaign, output, payload)
    print("ARCH_FRONTIER_PREFLIGHT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""WS205 qualification orchestrator: decks, prefs, isolated-JVM runs, adjudication.

Mutation surface: qualification/ws205-xmage-ws90-first-wave/** only.
Drives the WS204 generic legalActionsPayload/submitAction boundary through
fresh JVMs (one per game). No production bridge mutation. No engine repin.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

WS205_ROOT = Path(__file__).resolve().parent
REPO_ROOT = WS205_ROOT.parent.parent
PACK_PATH = (
    REPO_ROOT
    / "qualification/ws90-rqc3-corrected-first-wave-reissue"
    / "FIRST_WAVE_EXECUTION_PACK_CORRECTED.json"
)
ENGINE_PIN = "cfc36f445f917f101fa2ed588770e043f53bc44c"
CANDIDATE_HEAD = "5994019b4da59e27a388eec47e6805404bd98df9"
POLICY_VERSION = "ws205-pilot-v1"
BUDGET = 500

SLOT_ORDER = [
    "RQ-C3-A03",
    "RQ-C3-A04",
    "RQ-C3-B01",
    "RQ-C3-C01",
    "RQ-C3-C03",
    "RQ-C3-D06",
    "RQ-C3-E01",
    "RQ-C3-E02",
    "RQ-C3-F01",
    "RQ-C3-G02",
    "RQ-C3-G03",
    "RQ-C3-G04",
    "RQ-C3-H01",
    "RQ-C3-I01",
    "RQ-C3-J02",
]
SEEDS = {slot: 9101 + index for index, slot in enumerate(SLOT_ORDER)}
SEEDS["RQ-C3-H01-CLONE_FIRST"] = 9213
SEEDS["RQ-C3-H01-NO_HUMILITY"] = 9313

KENRITH = "Kenrith, the Returned King"
GHALTA = "Ghalta, Stampede Tyrant"


def basics_fill(have: list[str], basics: list[str], total: int = 99) -> list[str]:
    out = list(have)
    i = 0
    while len(out) < total:
        out.append(basics[i % len(basics)])
        i += 1
    return out


def seat_spec(deck_id: str, cards: list[str], basics: list[str], commanders: list[str]) -> dict:
    return {
        "deck_id": deck_id,
        "deck_hash": deck_id,
        "mainboard": basics_fill(cards, basics),
        "commanders": commanders,
    }


def build_decks(slot: str, subcase: str = "") -> dict:
    """Crafted Commander decks per slot. Scenario cards + basic filler."""
    U = ["Island"]
    W = ["Plains"]
    G = ["Forest"]
    R = ["Mountain"]
    B = ["Swamp"]
    K = [KENRITH]
    tag = slot if not subcase else f"{slot}-{subcase}"
    if slot == "RQ-C3-A03":
        return {
            "seat0": seat_spec(f"ws205-{tag}-p0", ["Drudge Skeletons"], B, K),
            "seat1": seat_spec(f"ws205-{tag}-p1", ["Lightning Bolt"], R, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", [], G, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", [], W, K),
        }
    if slot == "RQ-C3-A04":
        return {
            "seat0": seat_spec(
                f"ws205-{tag}-p0", ["Doubling Season", "Hardened Scales", "Stonecoil Serpent"], G, K
            ),
            "seat1": seat_spec(f"ws205-{tag}-p1", [], R, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", [], W, K),
        }
    if slot == "RQ-C3-B01":
        # NOTE: pack neutral state wants 2x Soul Warden on P0 and 1x elsewhere,
        # but Commander singleton legality permits only 1 copy per deck. Decks
        # stay singleton-legal; the assembly gap is recorded as evidence.
        return {
            "seat0": seat_spec(f"ws205-{tag}-p0", ["Soul Warden", "Llanowar Elves"], G, K),
            "seat1": seat_spec(f"ws205-{tag}-p1", ["Soul Warden"], G + W, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", ["Soul Warden"], G + W, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", ["Soul Warden"], G + W, K),
        }
    if slot == "RQ-C3-C01":
        return {
            "seat0": seat_spec(f"ws205-{tag}-p0", ["Force of Will", "Turn to Frog"], U, K),
            "seat1": seat_spec(f"ws205-{tag}-p1", ["Llanowar Elves"], G, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", [], R, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", [], B, K),
        }
    if slot == "RQ-C3-C03":
        return {
            "seat0": seat_spec(f"ws205-{tag}-p0", ["Fireball"], R, K),
            "seat1": seat_spec(f"ws205-{tag}-p1", [], G, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", [], W, K),
        }
    if slot == "RQ-C3-D06":
        return {
            "seat0": seat_spec(f"ws205-{tag}-p0", ["Casualties of War"], B + G, K),
            "seat1": seat_spec(f"ws205-{tag}-p1", ["Ornithopter", "Runeclaw Bear"], G, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", [], R, K),
        }
    if slot == "RQ-C3-E01":
        # NOTE: pack neutral state wants 2x Runeclaw Bear on P1; Commander
        # singleton legality permits only 1 copy per deck. Deck stays legal;
        # the assembly gap is recorded as evidence.
        return {
            "seat0": seat_spec(f"ws205-{tag}-p0", ["Propaganda"], U, K),
            "seat1": seat_spec(f"ws205-{tag}-p1", ["Runeclaw Bear"], G, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", [], R, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", [], W, K),
        }
    if slot == "RQ-C3-E02":
        return {
            "seat0": seat_spec(f"ws205-{tag}-p0", ["Runeclaw Bear", "Llanowar Elves"], G, K),
            "seat1": seat_spec(f"ws205-{tag}-p1", ["Carnage Tyrant"], G, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", [], R, K),
        }
    if slot == "RQ-C3-F01":
        return {
            "seat0": seat_spec(f"ws205-{tag}-p0", ["Rampant Growth"], G, K),
            "seat1": seat_spec(f"ws205-{tag}-p1", [], R, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", [], W, K),
        }
    if slot == "RQ-C3-G02":
        return {
            "seat0": seat_spec(f"ws205-{tag}-p0", [], G, [GHALTA]),
            "seat1": seat_spec(f"ws205-{tag}-p1", ["Murder"], B, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", [], R, K),
        }
    if slot == "RQ-C3-G03":
        return {
            "seat0": seat_spec(f"ws205-{tag}-p0", [], G, [GHALTA]),
            "seat1": seat_spec(f"ws205-{tag}-p1", [], R, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", [], W, K),
        }
    if slot == "RQ-C3-G04":
        return {
            "seat0": seat_spec(f"ws205-{tag}-p0", ["Runeclaw Bear", "Control Magic"], G + U, K),
            "seat1": seat_spec(f"ws205-{tag}-p1", [], R, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", [], B, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", [], W, K),
        }
    if slot == "RQ-C3-H01":
        if subcase == "CLONE_FIRST":
            return {
                "seat0": seat_spec(f"ws205-{tag}-p0", ["Clone"], U, K),
                "seat1": seat_spec(f"ws205-{tag}-p1", ["Runeclaw Bear"], G, K),
                "seat2": seat_spec(f"ws205-{tag}-p2", ["Humility", "Disenchant"], W, K),
                "seat3": seat_spec(f"ws205-{tag}-p3", [], R, K),
            }
        if subcase == "NO_HUMILITY":
            return {
                "seat0": seat_spec(f"ws205-{tag}-p0", ["Clone"], U, K),
                "seat1": seat_spec(f"ws205-{tag}-p1", ["Runeclaw Bear"], G, K),
                "seat2": seat_spec(f"ws205-{tag}-p2", [], W, K),
                "seat3": seat_spec(f"ws205-{tag}-p3", [], R, K),
            }
        return {
            "seat0": seat_spec(f"ws205-{tag}-p0", ["Clone"], U, K),
            "seat1": seat_spec(f"ws205-{tag}-p1", ["Runeclaw Bear"], G, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", ["Humility", "Disenchant"], W, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", [], R, K),
        }
    if slot == "RQ-C3-I01":
        return {
            "seat0": seat_spec(f"ws205-{tag}-p0", ["Runeclaw Bear", "Momentary Blink"], G + W, K),
            "seat1": seat_spec(f"ws205-{tag}-p1", ["Pacifism"], W, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", [], R, K),
        }
    if slot == "RQ-C3-J02":
        return {
            "seat0": seat_spec(f"ws205-{tag}-p0", ["Delina, Wild Mage", "Runeclaw Bear"], R + G, K),
            "seat1": seat_spec(f"ws205-{tag}-p1", [], U, K),
            "seat2": seat_spec(f"ws205-{tag}-p2", [], W, K),
            "seat3": seat_spec(f"ws205-{tag}-p3", [], B, K),
        }
    raise ValueError(f"unknown slot {slot}")


def build_prefs(slot: str, subcase: str = "") -> dict:
    """Wish-lists: desired semantic labels matched ONLY against offered options."""
    base = {"play_land_max": 12, "neutral_play_land": "true"}
    if slot == "RQ-C3-A03":
        base.update(
            {
                "priority": {"1": ["Lightning Bolt"], "0": ["Regenerate", "Drudge Skeletons"]},
                "target": {"1": ["Drudge Skeletons"]},
            }
        )
    elif slot == "RQ-C3-A04":
        base.update(
            {
                "priority": {"0": ["Stonecoil Serpent", "Doubling Season", "Hardened Scales"]},
                "numeric": {"0": 2},
            }
        )
    elif slot == "RQ-C3-B01":
        base.update(
            {
                "priority": {
                    "0": ["Llanowar Elves", "Soul Warden"],
                    "1": ["Soul Warden"],
                    "2": ["Soul Warden"],
                    "3": ["Soul Warden"],
                },
            }
        )
    elif slot == "RQ-C3-C01":
        base.update(
            {
                "priority": {"1": ["Llanowar Elves"], "0": ["Force of Will"]},
                "choice": {"0": ["Turn to Frog", "Force of Will"]},
                "choose_object": {"0": ["Turn to Frog"]},
                "target": {"0": ["Llanowar Elves"]},
            }
        )
    elif slot == "RQ-C3-C03":
        base.update(
            {
                "priority": {"0": ["Fireball"]},
                "numeric": {"0": 4},
            }
        )
    elif slot == "RQ-C3-D06":
        base.update(
            {
                "priority": {"0": ["Casualties of War"]},
                "mode": {"0": ["Creature", "Land", "Artifact"]},
                "target": {"0": ["Runeclaw Bear", "Ornithopter", "Forest", "Swamp"]},
            }
        )
    elif slot == "RQ-C3-E01":
        base.update(
            {
                "priority": {"0": ["Propaganda"], "1": ["Runeclaw Bear"]},
                "declare_attacker": {"1": ["Runeclaw Bear"]},
            }
        )
    elif slot == "RQ-C3-E02":
        base.update(
            {
                "priority": {"1": ["Carnage Tyrant"], "0": ["Runeclaw Bear", "Llanowar Elves"]},
                "declare_attacker": {"1": ["Carnage Tyrant"]},
                "declare_blocker": {"0": ["Runeclaw Bear", "Llanowar Elves"]},
            }
        )
    elif slot == "RQ-C3-F01":
        base.update(
            {
                "priority": {"0": ["Rampant Growth"]},
                "choose_object": {"0": ["Forest"]},
                "choice": {"0": ["Forest"]},
            }
        )
    elif slot == "RQ-C3-G02":
        base.update(
            {
                "priority": {"0": ["Ghalta"], "1": ["Murder"]},
                "target": {"1": ["Ghalta"]},
            }
        )
    elif slot == "RQ-C3-G03":
        base.update(
            {
                "priority": {"0": ["Ghalta"]},
                "declare_attacker": {"0": ["Ghalta"]},
            }
        )
    elif slot == "RQ-C3-G04":
        base.update(
            {
                "priority": {"0": ["Runeclaw Bear", "Control Magic"]},
                "target": {"0": ["Runeclaw Bear"]},
            }
        )
    elif slot == "RQ-C3-H01":
        if subcase == "NO_HUMILITY":
            base.update(
                {
                    "priority": {"0": ["Clone"], "1": ["Runeclaw Bear"]},
                    "choice": {"0": ["Runeclaw Bear"]},
                }
            )
        elif subcase == "CLONE_FIRST":
            base.update(
                {
                    "priority": {
                        "0": ["Clone"],
                        "1": ["Runeclaw Bear"],
                        "2": ["Humility", "Disenchant"],
                    },
                    "choice": {"0": ["Runeclaw Bear"]},
                    "target": {"2": ["Humility"]},
                }
            )
        else:
            base.update(
                {
                    "priority": {
                        "2": ["Humility", "Disenchant"],
                        "0": ["Clone"],
                        "1": ["Runeclaw Bear"],
                    },
                    "choice": {"0": ["Runeclaw Bear"]},
                    "target": {"2": ["Humility"]},
                }
            )
    elif slot == "RQ-C3-I01":
        base.update(
            {
                "priority": {"0": ["Runeclaw Bear", "Momentary Blink"], "1": ["Pacifism"]},
                "target": {"0": ["Runeclaw Bear"], "1": ["Runeclaw Bear"]},
            }
        )
    elif slot == "RQ-C3-J02":
        base.update(
            {
                "priority": {"0": ["Delina", "Runeclaw Bear"]},
                "declare_attacker": {"0": ["Delina"]},
                "target": {"0": ["Runeclaw Bear"]},
            }
        )
    # Casts/activations may surface as `choice`-class frames (cast_ability) or
    # as priority-frame actions. Mirror every priority wish name into the
    # choice-class wish list (priority names first, deduplicated) so cast
    # wishes hit regardless of surfacing class. Matching stays offered-only.
    if "priority" in base:
        choice = base.setdefault("choice", {})
        for seat, names in base["priority"].items():
            merged = list(names)
            for existing in choice.get(seat, []):
                if existing not in merged:
                    merged.append(existing)
            choice[seat] = merged
    return base


SETUPS = {
    "RQ-C3-A03": "NATURAL_GAME_START",
    "RQ-C3-A04": "NATURAL_GAME_START",
    "RQ-C3-B01": "NATURAL_GAME_START",
    "RQ-C3-C01": "NATURAL_GAME_START",
    "RQ-C3-C03": "NATURAL_GAME_START",
    "RQ-C3-D06": "NATURAL_GAME_START",
    "RQ-C3-E01": "PRE_STEP_NATIVE_PROGRESSION",
    "RQ-C3-E02": "PRE_STEP_NATIVE_PROGRESSION",
    "RQ-C3-F01": "NATURAL_GAME_START",
    "RQ-C3-G02": "NATURAL_GAME_START",
    "RQ-C3-G03": "PRE_DECISION_CONSTRUCTION",
    "RQ-C3-G04": "NATURAL_GAME_START",
    "RQ-C3-H01": "NATURAL_GAME_START",
    "RQ-C3-I01": "NATURAL_GAME_START",
    "RQ-C3-J02": "PRE_STEP_NATIVE_PROGRESSION",
}

PACK_AUTHORITY = (
    "FIRST_WAVE_EXECUTION_PACK_CORRECTED.json blob 5852965e59412399a947c626d4f7d428be8ef337"
)


def java_classpath() -> str:
    cp = Path("/tmp/opencode/ws205-cp.txt").read_text().strip()
    return f"/tmp/opencode/ws205-driver-classes:engine-bridge/target/classes:{cp}"


def run_jvm(args: list[str], timeout_s: int = 1500) -> subprocess.CompletedProcess:
    cmd = ["java", "-cp", java_classpath(), "org.commanderlab.xmage.Ws205FirstWaveDriver", *args]
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout_s, cwd=str(REPO_ROOT)
    )


_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_HEX_RE = re.compile(r"\b[0-9a-fA-F]{16,}\b")
_WS205_DEC_RE = re.compile(r"ws205-[a-z\-]+")
_XMAGE_DEC_RE = re.compile(r"[0-9a-f]{4,}-[0-9a-f\-]{8,}")


def normalize_label(text: str) -> str:
    text = _UUID_RE.sub("<uuid>", text)
    text = _HEX_RE.sub("<hex>", text)
    return text


def semantic_transcript(evidence: dict) -> list[dict]:
    """Rules-relevant projection: no process-local identity, no private state."""
    out = []
    for row in evidence.get("decision_stream", []):
        # NOTE: selection_basis (neutral/wish/twin_stream) is pilot-role
        # metadata, not Rules semantics; it is excluded from the semantic
        # projection. Twin stream-following is verified separately by
        # stream_entries_followed + stream_diverged in twin.record.json.
        entry = {
            "offset": row.get("offset"),
            "class": row.get("class"),
            "actor_seat": row.get("actor_seat"),
            "offered_count": row.get("offered_count"),
            "offered_types": row.get("offered_types"),
            "selected_label": normalize_label(str(row.get("selected_label", ""))),
            "label_ambiguous": bool(row.get("label_ambiguous", False)),
        }
        if row.get("numeric_choice") is not None:
            entry["numeric_choice"] = row.get("numeric_choice")
        out.append(entry)
    assertion = evidence.get("assertion_state", {})
    if isinstance(assertion, dict) and "battlefield" in assertion:
        board = []
        for perm in assertion["battlefield"]:
            if not isinstance(perm, dict) or "name" not in perm:
                continue
            board.append(
                {
                    "name": perm.get("name"),
                    "controller_seat": perm.get("controller_seat"),
                    "power": perm.get("power"),
                    "toughness": perm.get("toughness"),
                    "is_copy": perm.get("is_copy"),
                    "ability_count": perm.get("abilities"),
                }
            )
        board.sort(key=lambda r: (str(r["name"]), str(r["controller_seat"])))
        out.append({"terminal_board": board})
        seats = []
        for seat in assertion.get("seats", []):
            grave = (
                sorted(seat.get("graveyard", []))
                if isinstance(seat.get("graveyard", []), list)
                else []
            )
            seats.append(
                {
                    "seat": seat.get("seat"),
                    "life": seat.get("life"),
                    "hand_size": seat.get("hand_size"),
                    "library_size": seat.get("library_size"),
                    "graveyard": grave,
                }
            )
        out.append({"terminal_seats": seats})
    return out


def transcript_hash(transcript: list[dict]) -> str:
    canonical = json.dumps(transcript, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def main(argv: list[str]) -> int:
    only = [a.split("=", 1)[1] for a in argv if a.startswith("--only=")]
    wanted = set(only[0].split(",")) if only else set(SLOT_ORDER)
    pack = json.loads(PACK_PATH.read_text())
    scenarios = {s["rqc3_scenario_id"]: s for s in pack["scenarios"]}
    for slot in SLOT_ORDER:
        if slot not in wanted:
            continue
        subcases = ["HUMILITY_FIRST", "CLONE_FIRST", "NO_HUMILITY"] if slot == "RQ-C3-H01" else [""]
        for subcase in subcases:
            run_construction(slot, subcase, scenarios[slot])
    return 0


def run_construction(slot: str, subcase: str, scenario: dict) -> None:
    key = slot if not subcase else f"{slot}-{subcase}"
    seed = SEEDS[key]
    slot_dir = WS205_ROOT / "slots" / key
    slot_dir.mkdir(parents=True, exist_ok=True)
    decks = build_decks(slot, subcase)
    prefs = build_prefs(slot, subcase)
    decks_path = slot_dir / "decks.json"
    prefs_path = slot_dir / "prefs.json"
    decks_path.write_text(json.dumps(decks, indent=1, sort_keys=True))
    prefs_with_meta = dict(prefs)
    prefs_with_meta["_meta"] = {
        "decision_policy_version": POLICY_VERSION,
        "slot": slot,
        "subcase": subcase,
        "seed": seed,
    }
    prefs_path.write_text(json.dumps(prefs_with_meta, indent=1, sort_keys=True))
    primary_out = slot_dir / "primary.json"
    print(f"[WS205] {key}: primary run seed={seed}", flush=True)
    result = run_jvm(
        [
            "--mode=run",
            f"--slot={slot}",
            f"--case={subcase}",
            f"--decks={decks_path}",
            f"--prefs={prefs_path}",
            f"--seed={seed}",
            f"--budget={BUDGET}",
            f"--out={primary_out}",
            f"--head={CANDIDATE_HEAD}",
            f"--setup={SETUPS[slot]}",
            f"--authority-hash={PACK_AUTHORITY}",
        ]
    )
    (slot_dir / "primary.stdout.txt").write_text(result.stdout[-8000:])
    (slot_dir / "primary.stderr.txt").write_text(result.stderr[-4000:])
    if not primary_out.exists():
        (slot_dir / "primary.failed.txt").write_text(
            f"rc={result.returncode}\n{result.stderr[-4000:]}"
        )
        print(f"[WS205] {key}: PRIMARY JVM FAILED rc={result.returncode}", flush=True)
        return
    evidence = json.loads(primary_out.read_text())
    transcript = semantic_transcript(evidence)
    (slot_dir / "primary.semantic.json").write_text(
        json.dumps(transcript, indent=1, sort_keys=True)
    )
    thash = transcript_hash(transcript)
    (slot_dir / "primary.semantic.sha256").write_text(thash + "\n")
    # Twin gate: fresh JVM, same seed/decks/scenario/stream.
    twin_out = slot_dir / "twin.json"
    stream_path = slot_dir / "primary.stream.json"
    stream_path.write_text(
        json.dumps({"decision_stream": evidence.get("decision_stream", [])}, indent=1)
    )
    print(f"[WS205] {key}: twin run seed={seed}", flush=True)
    twin = run_jvm(
        [
            "--mode=twin",
            f"--slot={slot}",
            f"--case={subcase}",
            f"--decks={decks_path}",
            f"--prefs={prefs_path}",
            f"--seed={seed}",
            f"--budget={BUDGET}",
            f"--out={twin_out}",
            f"--stream={stream_path}",
            f"--head={CANDIDATE_HEAD}",
            f"--setup={SETUPS[slot]}",
            f"--authority-hash={PACK_AUTHORITY}",
        ]
    )
    (slot_dir / "twin.stdout.txt").write_text(twin.stdout[-8000:])
    (slot_dir / "twin.stderr.txt").write_text(twin.stderr[-4000:])
    twin_evidence = json.loads(twin_out.read_text()) if twin_out.exists() else None
    if twin_evidence is None:
        print(f"[WS205] {key}: TWIN JVM FAILED rc={twin.returncode}", flush=True)
        twin_record = {
            "semantic_replay_match": False,
            "reason": "twin_jvm_failed",
            "semantic_transcript_hash": None,
            "twin_semantic_transcript_hash": None,
        }
    else:
        twin_transcript = semantic_transcript(twin_evidence)
        (slot_dir / "twin.semantic.json").write_text(
            json.dumps(twin_transcript, indent=1, sort_keys=True)
        )
        twin_hash = transcript_hash(twin_transcript)
        (slot_dir / "twin.semantic.sha256").write_text(twin_hash + "\n")
        diverged = bool(twin_evidence.get("stream_diverged", False))
        match = (not diverged) and (twin_hash == thash)
        twin_record = {
            "semantic_replay_match": bool(match),
            "stream_diverged": diverged,
            "stream_divergence_detail": twin_evidence.get("stream_divergence_detail", ""),
            "stream_entries_followed": len(twin_evidence.get("decision_stream", [])),
            "primary_entries": len(evidence.get("decision_stream", [])),
            "semantic_transcript_hash": thash,
            "twin_semantic_transcript_hash": twin_hash,
        }
        print(
            f"[WS205] {key}: twin match={match} "
            f"answered={evidence.get('decisions_answered')}/"
            f"{twin_evidence.get('decisions_answered')} "
            f"stopped={evidence.get('stopped_by')}/"
            f"{twin_evidence.get('stopped_by')}",
            flush=True,
        )
    (slot_dir / "twin.record.json").write_text(json.dumps(twin_record, indent=1, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

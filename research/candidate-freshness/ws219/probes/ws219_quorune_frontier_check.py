"""WS219 bounded probe: Quorune frozen-29 frontier census (read-only).

Reads /home/moeen/code/ws219-ref-quorune-64ef6569/coverage/card-unlock-frontier.json.gz
without modifying the reference root. Reports per-card oracle_ir_status /
card_program_status / trust_basis / blockers. No behavior credit claimed.
"""
import gzip
import json
import pathlib

REF = pathlib.Path("/home/moeen/code/ws219-ref-quorune-64ef6569")
FRONTIER = REF / "coverage" / "card-unlock-frontier.json.gz"

FROZEN_29 = [
    "Ishai, Ojutai Dragonspeaker",
    "Rograkh, Son of Rohgahh",
    "Esior, Wardwing Familiar",
    "Kediss, Emberclaw Familiar",
    "Veyran, Voice of Duality",
    "Harmonic Prodigy",
    "Narset, Parter of Veils",
    "Jeska, Thrice Reborn",
    "Magma Opus",
    "Wash Away",
    "Wear // Tear",
    "Dig Through Time",
    "Flare of Duplication",
    "Vandalblast",
    "Finale of Revelation",
    "Psychosis Crawler",
    "Kaervek the Merciless",
    "Shriekmaw",
    "Butcher of Malakir",
    "Syphon Mind",
    "Gratuitous Violence",
    "Bolt Bend",
    "Makeshift Mannequin",
    "Warstorm Surge",
    "Basilisk Collar",
    "Burn Down the House",
    "Path of Ancestry",
    "Find // Finality",
    "Boseiju Reaches Skyward // Branch of Boseiju",
]


def main() -> None:
    assert REF.exists(), f"reference root missing: {REF}"
    assert FRONTIER.exists(), f"frontier missing: {FRONTIER}"
    with gzip.open(FRONTIER, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    # Frontier shape varies; normalize to list of records with name-like keys.
    if isinstance(data, dict):
        records = data.get("cards") or data.get("records") or data.get("frontier") or []
        if not records and any("oracle" in k.lower() for k in data.keys()):
            records = [data]
    else:
        records = data
    by_name = {}
    for rec in records if isinstance(records, list) else []:
        if not isinstance(rec, dict):
            continue
        for key in ("name", "card_name", "oracle_name", "identity"):
            if key in rec and isinstance(rec[key], str):
                by_name[rec[key].strip().lower()] = rec
                break
    print(f"frontier_records={len(by_name)} frontier_file={FRONTIER}")
    missing = []
    for name in FROZEN_29:
        rec = by_name.get(name.lower())
        if rec is None:
            # fallback: substring match on front face (for split/MDFC)
            front = name.split("//")[0].strip().lower()
            rec = by_name.get(front)
        if rec is None:
            missing.append(name)
            print(f"MISSING_RECORD | {name}")
        else:
            status = {k: rec.get(k) for k in (
                "oracle_ir_status", "card_program_status", "trust_basis",
                "exact_spans", "residuals", "minimum_known_blocker_set", "blockers",
            ) if k in rec}
            print(f"RECORD | {name} | {json.dumps(status, sort_keys=True)[:600]}")
    print(f"matched={len(FROZEN_29) - len(missing)} missing_records={len(missing)}")
    if missing:
        print("missing_list=" + json.dumps(missing))


if __name__ == "__main__":
    main()

"""WS222 authority validation (offline, deterministic, no network).

Validates the sealed WS222 package: successor lock integrity, CR byte-exact
artifact, Oracle page pins + field snapshot, B&R capture + deck legality,
and no-secondary-promotion flags. Live acquisition/repeatability evidence is
recorded in the sealed receipts and docs, not re-fetched here.
"""

import hashlib
import json
import re
from pathlib import Path

NS = Path(__file__).resolve().parents[2] / "qualification" / "ws222-g01-authority-reacquisition"
LOCK = NS / "AUTHORITY_LOCK_v2.json"
EFF_RE = re.compile(r"These rules are effective as of ([A-Z][a-z]+ \d{1,2}, \d{4})\.")

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


def _load_lock():
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    assert lock["lock_id"] == "AUTHORITY_LOCK_v2"
    assert lock["supersedes"] == "AUTHORITY_LOCK_v1"
    assert lock["secondary_sources_promoted"] is False
    return lock


def test_successor_lock_present_and_scoped():
    lock = _load_lock()
    assert lock["capture_date"] == "2026-09-15"
    assert lock["comprehensive_rules"]["status"] == "BYTE_EXACT_CAPTURED"
    assert lock["oracle"]["status"] == "BOUNDED_OFFICIAL_CAPTURE"
    assert lock["oracle"]["secondary_sources_promoted"] is False
    assert lock["commander_ban_authority"]["announcement_effective_date"] == "February 9, 2026"
    assert lock["deck_provenance"]["status"] == "CARRIED_FORWARD_UNCHANGED"
    assert lock["refresh_procedure"] and lock["known_limitations"]


def test_cr_byte_exact_and_effective_date():
    lock = _load_lock()
    cr = lock["comprehensive_rules"]
    data = (NS / cr["artifact_path"]).read_bytes()
    assert len(data) == cr["artifact_size"] == 977822
    assert hashlib.sha256(data).hexdigest() == cr["artifact_sha256"]
    assert cr["normalization"] == "NONE"
    m = EFF_RE.search(data.decode("utf-8-sig", errors="replace"))
    assert m and m.group(0) == cr["effective_date_text"]
    assert cr["effective_date"] == "2026-08-07"
    receipt = json.loads(
        (NS / "artifacts/cr/CR_ACQUISITION_RECEIPT.json").read_text(encoding="utf-8")
    )
    assert receipt["artifact_sha256"] == cr["artifact_sha256"]
    assert "20260819" in receipt["resolved_artifact_url"]


def test_oracle_denominator_complete_and_pinned():
    lock = _load_lock()
    recs = lock["oracle"]["records"]
    assert len(recs) == 30  # 29 front + 1 MDFC back
    by_ident = {}
    for r in recs:
        p = NS / r["page_file"]
        data = p.read_bytes()
        assert hashlib.sha256(data).hexdigest() == r["page_sha256"], r["page_file"]
        text = data.decode("utf-8", errors="replace")
        fronts = [r["denominator_identity"]] + [
            x.strip() for x in r["denominator_identity"].split("//")
        ]
        assert any(f in text for f in fronts), r["denominator_identity"]
        by_ident.setdefault(r["denominator_identity"], []).append(r.get("face", "front"))
    assert sorted(by_ident) == sorted(FROZEN_29)
    assert sorted(by_ident["Boseiju Reaches Skyward // Branch of Boseiju"]) == [
        "back:Branch of Boseiju",
        "front",
    ]
    snap_path = NS / lock["oracle"]["field_snapshot_path"]
    assert (
        hashlib.sha256(snap_path.read_bytes()).hexdigest()
        == lock["oracle"]["field_snapshot_sha256"]
    )
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    assert snap["page_count"] == 30
    for entry in snap["records"]:
        assert entry["official_fields"]["commander_legality"] == "Legal"
        assert entry["official_fields"]["oracle_texts_distinct"]


def test_ban_capture_and_deck_legality():
    lock = _load_lock()
    ban = lock["commander_ban_authority"]
    assert (
        hashlib.sha256((NS / ban["artifact_path"]).read_bytes()).hexdigest()
        == ban["artifact_sha256"]
    )
    assert ban["commander_banned_named_count"] == 42
    assert lock["oracle"]["rulings_total"] == sum(
        len(e["official_fields"]["rulings"])
        for e in json.loads(
            (NS / lock["oracle"]["field_snapshot_path"]).read_text(encoding="utf-8")
        )["records"]
    )
    assert ban["deck_legality"] == {
        "frozen_29_banned_hits": 0,
        "rogshai_87_banned_hits": 0,
        "kaervek_77_banned_hits": 0,
    }
    # independently re-check deck lists against the captured ban entries
    ban_receipt = json.loads(
        (NS / "artifacts/ban/BAN_ACQUISITION_RECEIPT.json").read_text(encoding="utf-8")
    )
    named = {
        e
        for e in ban_receipt["commander_banned_entries"]
        if not e.startswith(("25 cards", "9 cards", "Cards whose", "Lutri"))
    }
    domain = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "qualification/manifests/ACTUAL_CARD_DOMAIN_v1.json"
        ).read_text(encoding="utf-8")
    )
    for key in ("current_rogshai_unique_identity_list", "current_kaervek_unique_identity_list"):
        for ident in domain[key]:
            assert ident not in named, ident
            for face in [x.strip() for x in ident.split("//")]:
                assert face not in named, face


def test_historical_lock_untouched_and_no_promotion():
    v1 = json.loads(
        (
            Path(__file__).resolve().parents[2] / "qualification/manifests/AUTHORITY_LOCK_v1.json"
        ).read_text(encoding="utf-8")
    )
    assert v1["comprehensive_rules"]["original_sha256"] is None
    assert v1["oracle"]["status"] == "UNKNOWN"
    subset = json.loads(
        (Path(__file__).resolve().parents[2] / "data/cards/oracle_subset.json").read_text(
            encoding="utf-8"
        )
    )
    assert subset["authoritative_oracle_snapshot"] is False

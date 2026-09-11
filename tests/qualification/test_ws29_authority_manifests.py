from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WS29 = ROOT / "qualification" / "ws29"

EXPECTED_SHA256 = {
    "CARD_AUTHORITY_LEDGER.json": "a810c9262597db5a1162c6fd8240bd154938e98efe58b0e0cddb29541344e3c4",
    "PROVIDER_NEUTRAL_EXPECTED_SEMANTICS.json": "bde2177e91fe9ed0e0399e1637d3b47226c402bfe2c0350cf6bccf87f19c5201",
    "WS29_SOURCE_LOCK.json": "c4306b9bdd16b81100a13e0ff49691bbe43418ac54f4d666a223c52c32bbc910",
    "UNRESOLVED_AUTHORITY_REGISTER.json": "6765db1613c5f30e27c84998f39fafb30db3645c0cc5fc8e896f5cc20d0e89d9",
}

CARD_NAMES = [
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
EXPECTED_IDS = [f"CARD_{i:02d}" for i in range(1, 30)]


def load(name: str) -> dict:
    path = WS29 / name
    if not path.is_file():
        raise AssertionError(f"required WS-29 manifest missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestWS29FrozenAuthorityManifests(unittest.TestCase):
    def test_exact_frozen_file_hashes(self) -> None:
        for name, expected in EXPECTED_SHA256.items():
            path = WS29 / name
            self.assertTrue(path.is_file(), f"missing frozen artifact: {path}")
            self.assertEqual(sha256(path), expected, f"frozen WS-29 artifact drifted: {name}")

    def test_ledger_is_exact_29_card_current_official_oracle_lock(self) -> None:
        ledger = load("CARD_AUTHORITY_LEDGER.json")
        self.assertEqual(ledger["schema_version"], "ws29-card-authority-ledger/1.0.0")
        self.assertEqual(ledger["corpus_count"], 29)
        self.assertTrue(ledger["authority_policy"]["direct_official_required"])
        self.assertFalse(ledger["authority_policy"]["engine_behavior_authoritative"])
        self.assertFalse(ledger["authority_policy"]["secondary_sources_authoritative"])

        records = ledger["records"]
        self.assertEqual([r["fixture_id"] for r in records], EXPECTED_IDS)
        self.assertEqual([r["card_identity"] for r in records], CARD_NAMES)

        for record in records:
            self.assertEqual(record["player_count"], 4)
            self.assertEqual(record["primary_authority_class"], "FULL_CURRENT_ORACLE_LOCK")
            self.assertIn("DISCRIMINATOR_AUTHORITY_PASS", record["authority_classifications"])
            self.assertFalse(record["authority_blocked"])
            self.assertFalse(record["currentness_unproven"])
            self.assertFalse(record["printed_text_only"])
            self.assertTrue(record["faces"])
            self.assertIn("not upgraded by authority closure", record["runtime_status_note"])
            for face in record["faces"]:
                self.assertEqual(face["http_status"], 200)
                self.assertTrue(face["official_gatherer_url"].startswith("https://gatherer.wizards.com/"))
                self.assertEqual(len(face["raw_html_sha256"]), 64)
                self.assertGreater(face["raw_html_byte_count"], 0)
                self.assertTrue(face["retrieved_at_utc"].endswith("Z"))

    def test_expected_semantics_match_denominator_and_remain_provider_neutral(self) -> None:
        semantics = load("PROVIDER_NEUTRAL_EXPECTED_SEMANTICS.json")
        self.assertEqual(semantics["schema_version"], "ws29-provider-neutral-expected-semantics/1.0.0")
        self.assertEqual(semantics["fixture_count"], 29)
        self.assertIn("Exactly 4 players", semantics["scope"])

        records = semantics["records"]
        self.assertEqual([r["fixture_id"] for r in records], EXPECTED_IDS)
        self.assertEqual([r["card_identity"] for r in records], CARD_NAMES)
        for record in records:
            self.assertEqual(record["player_count"], 4)
            self.assertEqual(record["authority_classification"], "FULL_CURRENT_ORACLE_LOCK")
            self.assertEqual(record["discriminator_authority"], "DISCRIMINATOR_AUTHORITY_PASS")
            self.assertTrue(record["runtime_independent"])
            self.assertTrue(record["initial_semantic_state"])
            self.assertTrue(record["required_decisions"])
            self.assertTrue(record["legal_result_constraints"])
            self.assertTrue(record["expected_events"])
            self.assertTrue(record["expected_terminal_postconditions"])
            self.assertTrue(record["cr_rule_references"])
            self.assertTrue(record["official_card_authority_sources"])
            for source in record["official_card_authority_sources"]:
                self.assertTrue(source["url"].startswith("https://gatherer.wizards.com/"))
                self.assertEqual(len(source["raw_html_sha256"]), 64)
                self.assertTrue(source["retrieved_at_utc"].endswith("Z"))

    def test_cross_manifest_identity_and_authority_agree(self) -> None:
        ledger = load("CARD_AUTHORITY_LEDGER.json")
        semantics = load("PROVIDER_NEUTRAL_EXPECTED_SEMANTICS.json")
        ledger_map = {r["fixture_id"]: r for r in ledger["records"]}
        semantics_map = {r["fixture_id"]: r for r in semantics["records"]}
        self.assertEqual(set(ledger_map), set(EXPECTED_IDS))
        self.assertEqual(set(semantics_map), set(EXPECTED_IDS))
        for fixture_id in EXPECTED_IDS:
            self.assertEqual(ledger_map[fixture_id]["card_identity"], semantics_map[fixture_id]["card_identity"])
            self.assertEqual(ledger_map[fixture_id]["primary_authority_class"], semantics_map[fixture_id]["authority_classification"])

    def test_source_lock_preserves_raw_byte_and_access_truth(self) -> None:
        source = load("WS29_SOURCE_LOCK.json")
        self.assertEqual(source["schema_version"], "ws29-source-lock/1.0.0")
        self.assertEqual(source["canonical_main"]["commit"], "c83e52ae79ff2242578757c0f517badbb1a2621c")
        self.assertEqual(source["canonical_main"]["tree"], "551c0d55a171508618d2b7d29e0f49b19893f886")
        cr = source["cr_raw_acquisition"]
        self.assertEqual(cr["official_cr_raw_bytes"], "PASS")
        self.assertEqual(cr["pdf_raw_bytes"], "PASS")
        self.assertEqual(cr["txt_raw_bytes"], "UNKNOWN")
        self.assertEqual(cr["sources"]["pdf"]["http_status"], 200)
        self.assertEqual(cr["sources"]["pdf"]["raw_byte_count"], 2524708)
        self.assertEqual(cr["sources"]["pdf"]["sha256"], "9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c")
        self.assertEqual(cr["sources"]["txt"]["http_status"], 404)
        self.assertIsNone(cr["sources"]["txt"]["sha256"])
        self.assertEqual(source["gatherer_access"]["status"], "PASS")
        self.assertEqual(source["gatherer_corpus_manifest"]["full_current_oracle_lock_count"], 29)
        self.assertEqual(source["gatherer_corpus_manifest"]["manifest_sha256"], "f75e1c322a15d94fb89f1409cd42ea9e2095cc25810d845bcf8518d4d5634b10")
        self.assertEqual(source["work_branch"], "ws29/canonical-authority-closure")

    def test_unresolved_register_has_no_card_authority_blockers(self) -> None:
        unresolved = load("UNRESOLVED_AUTHORITY_REGISTER.json")
        self.assertEqual(unresolved["schema_version"], "ws29-unresolved-authority-register/1.0.0")
        self.assertEqual(unresolved["card_authority_blockers"], [])

        forge = unresolved["forge_runtime_ready_delta"]
        self.assertEqual(forge["still_authority_blocked"], [])
        self.assertEqual(forge["runtime_pass_unchanged"], ["CARD_02"])
        self.assertEqual(set(forge["newly_authority_ready"]), set(EXPECTED_IDS) - {"CARD_02"})

        xmage = unresolved["xmage_authority_delta"]
        self.assertEqual(xmage["runtime_pass_unchanged"], ["CARD_02", "CARD_04", "CARD_24"])
        self.assertEqual(xmage["authority_supported_runtime_passes"], ["CARD_02", "CARD_04", "CARD_24"])
        self.assertEqual(set(xmage["remaining_runtime_unexecuted_or_unsupported"]), set(EXPECTED_IDS) - {"CARD_02", "CARD_04", "CARD_24"})

        unknowns = {entry["id"]: entry["status"] for entry in unresolved["non_card_unknowns"]}
        self.assertEqual(unknowns, {"CR_TXT_RAW_BYTES": "UNKNOWN", "WS27_INPUT": "INPUT_UNAVAILABLE"})


if __name__ == "__main__":
    unittest.main(verbosity=2)

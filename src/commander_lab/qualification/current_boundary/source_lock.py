"""Current-boundary identity constants and receipts (WSR22).

Every identity here is a fixed, contract-bound value. Nothing in this module
may be repinned inside WSR22: provider repinning belongs to a later
Architecture Freeze decision.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CURRENT_QUALIFICATION_BOUNDARY = "commander-lab.pre-freeze-qualification/2.0.0"
CURRENT_TRANSPORT_PROTOCOL = "2.0.0"
SUPERSEDED_RULES_SERVICE_BOUNDARY = "commander-lab.rules-service/1.1.0"

# Official current Comprehensive Rules (direct Wizards capture, see
# qualification/final-current-boundary-20260927/CURRENT_RULES_AUTHORITY.json).
CURRENT_RULES_AUTHORITY_EFFECTIVE_DATE = "2026-09-25"
CURRENT_RULES_TXT_SHA256 = "8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca"
CURRENT_RULES_TXT_URL = "https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt"

FULL107_FROZEN_SOURCE = "5a2e4f462fd45bba25f2271153212aab9faf09f5"
FULL107_SUCCESSOR_CONTRACT = "1.0.6-successor"
FULL107_MATERIALIZATION_SCHEMA = "commander-lab.semantic-fixture-materialization/1.0.6-successor"

XMAGE_CANDIDATE_COMMIT = "b19596980f2734496ea1896504253e1bdd2756dd"
XMAGE_LAB_RUNTIME_AUTHORITY = "593326713faeddb8c90df2fdc5e5bafbe1fccf1b"
XMAGE_PROVIDER = "xmage"
XMAGE_LICENSE = "MIT"

FORGE_CANDIDATE_COMMIT = "ef958ee91ac6c9ce0152189f2654bf6e05abf273"
FORGE_CANDIDATE_TREE = "fc3387bf37aab19d780b2939a235309ed32b0492"
FORGE_WSR20_EVIDENCE_TIP = "18bba95a4528f6ab5910633f1f87f603b8c4ddf8"
FORGE_PROVIDER = "forge"

# PB-09 identity distinction. These are three different things and must never be
# conflated, reported under one name, or compared as if one implied another.
#
#   FORGE_CANDIDATE_COMMIT        the Commander-Lab fork, and the engine that
#                                 actually executes. Lab-modified code.
#   FORGE_UPSTREAM_BASELINE_COMMIT pristine upstream Forge, the fork's ancestor.
#                                 Ancestry is NOT identity, and this baseline is
#                                 NOT verified pristine: no exact pristine
#                                 upstream checkout with proven provenance has
#                                 been established, so upstream behaviour remains
#                                 UNKNOWN and must not be described as observed.
#   FORGE_WSR20_EVIDENCE_TIP      the WSR20/WSR24 descendant of the fork. This is
#                                 what the bound native suites execute at, and
#                                 it is neither of the two above. A descendant is
#                                 a different tree and may carry Rules-Core
#                                 changes, so a suite executed here cannot be
#                                 attributed to FORGE_CANDIDATE_COMMIT.
FORGE_FORK_REPOSITORY = "https://github.com/moeendres-png/forge.git"
FORGE_UPSTREAM_REPOSITORY = "https://github.com/Card-Forge/forge.git"
FORGE_UPSTREAM_BASELINE_COMMIT = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"
FORGE_UPSTREAM_BASELINE_VERIFIED_PRISTINE = False
FORGE_BRIDGE_SOURCE_COMMIT = "4753bb7c72ea60d653121e0bab989077b4009f9c"
FORGE_LICENSE = "GPL-3.0"

# Contract blob paths inside the Lab repository.
CONTRACT_PATHS = {
    "current_pre_freeze_contract": "qualification/CURRENT_PRE_FREEZE_CONTRACT.json",
    "full107_successor_contract": "qualification/pre-freeze-successor/"
    "FULL107_SUCCESSOR_CONTRACT_v1_0_6.json",
    "materialization_schema": "qualification/pre-freeze-successor/"
    "SEMANTIC_FIXTURE_SCHEMA_v1_0_6_SUCCESSOR.json",
    "af01_boundary": "qualification/pre-freeze-successor/AF01_QUALIFICATION_BOUNDARY_V2.json",
    "freeze_gate_catalog": "qualification/pre-freeze-successor/"
    "architecture_freeze_gate_catalog_v2.json",
    "freeze_result_schema": "qualification/pre-freeze-successor/"
    "architecture_freeze_contract_v2.schema.json",
    "rules_authority_receipt": "qualification/pre-freeze-successor/CURRENT_RULES_AUTHORITY.json",
    "transport_schema": "schemas/engine_adapter_protocol.schema.json",
    "frozen_materialization_v1_0_5": "qualification/ws47/"
    "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json",
    "denominator_107": "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json",
    "engine_pin_manifest": "config/rules_engines.json",
}

REQUIRED_HANDSHAKE_MESSAGES = ("start_engine", "get_provider_version", "get_capabilities")


def repo_root() -> Path:
    """Repository root for the running Lab checkout."""
    return Path(__file__).resolve().parents[4]


def contract_blob_digest(root: Path, relative: str) -> str:
    """SHA-256 of a contract blob, used to bind evidence to exact bytes."""
    return hashlib.sha256((root / relative).read_bytes()).hexdigest()


def boundary_receipt(root: Path | None = None) -> dict[str, Any]:
    """Machine-readable identity receipt bound to the current boundary."""
    resolved_root = root or repo_root()
    blobs = {
        name: {
            "path": relative,
            "sha256": contract_blob_digest(resolved_root, relative),
        }
        for name, relative in CONTRACT_PATHS.items()
    }
    return {
        "schema_version": "commander-lab.current-boundary-receipt/1.0.0",
        "qualification_boundary": CURRENT_QUALIFICATION_BOUNDARY,
        "transport_protocol": CURRENT_TRANSPORT_PROTOCOL,
        "superseded_rules_service_boundary": SUPERSEDED_RULES_SERVICE_BOUNDARY,
        "full107_frozen_source": FULL107_FROZEN_SOURCE,
        "full107_successor_contract": FULL107_SUCCESSOR_CONTRACT,
        "full107_materialization_schema": FULL107_MATERIALIZATION_SCHEMA,
        "rules_authority": {
            "effective_date": CURRENT_RULES_AUTHORITY_EFFECTIVE_DATE,
            "official_txt_url": CURRENT_RULES_TXT_URL,
            "official_txt_sha256": CURRENT_RULES_TXT_SHA256,
            "applicable_rule": "103.8a",
            "capture_classification": "DIRECTLY_VERIFIED_OFFICIAL",
        },
        "candidates": {
            XMAGE_PROVIDER: {
                "candidate_commit": XMAGE_CANDIDATE_COMMIT,
                "lab_runtime_authority": XMAGE_LAB_RUNTIME_AUTHORITY,
                "license": XMAGE_LICENSE,
                "substitution_forbidden": "current Mage master is NOT the qualified identity",
            },
            FORGE_PROVIDER: {
                "candidate_commit": FORGE_CANDIDATE_COMMIT,
                # PB-09. The three Forge identities are reported under distinct
                # names so no consumer can read one as another.
                "engine_identity_pb09": {
                    "executing_engine": {
                        "role": "THE ENGINE THAT ACTUALLY RUNS. Lab-modified code.",
                        "repository": FORGE_FORK_REPOSITORY,
                        "commit": FORGE_CANDIDATE_COMMIT,
                        "tree": FORGE_CANDIDATE_TREE,
                        "is_pristine_upstream": False,
                    },
                    "upstream_baseline": {
                        "role": "ANCESTRY ONLY. Not the engine under test, and not "
                        "verified pristine.",
                        "repository": FORGE_UPSTREAM_REPOSITORY,
                        "commit": FORGE_UPSTREAM_BASELINE_COMMIT,
                        "verified_pristine": FORGE_UPSTREAM_BASELINE_VERIFIED_PRISTINE,
                        "upstream_behaviour_observed": False,
                        "note": "no exact pristine upstream checkout with proven "
                        "provenance has been established, so upstream behaviour is "
                        "UNKNOWN and must never be described as observed",
                    },
                    "wsr20_evidence_tip": {
                        "role": "WHAT THE BOUND NATIVE SUITES EXECUTE AT. Neither the "
                        "fork head nor the upstream baseline.",
                        "commit": FORGE_WSR20_EVIDENCE_TIP,
                        "is_candidate_head": False,
                        "note": "a suite executed at this descendant must not be "
                        "attributed to candidate_commit; verify_candidate_identity "
                        "fails closed on the divergence",
                    },
                    "bridge_source_commit": {
                        "role": "the bridge inside the fork, distinct from the engine commit",
                        "commit": FORGE_BRIDGE_SOURCE_COMMIT,
                    },
                },
                "candidate_tree": FORGE_CANDIDATE_TREE,
                "wsr20_evidence_tip": FORGE_WSR20_EVIDENCE_TIP,
                "license": FORGE_LICENSE,
                "substitution_forbidden": "WSR20 is tests/evidence only; not a Rules-Core version",
            },
        },
        "contract_blobs": blobs,
    }


def load_contract(root: Path | None = None) -> dict[str, Any]:
    """Load the current pre-Freeze contract document."""
    resolved_root = root or repo_root()
    path = resolved_root / CONTRACT_PATHS["current_pre_freeze_contract"]
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document

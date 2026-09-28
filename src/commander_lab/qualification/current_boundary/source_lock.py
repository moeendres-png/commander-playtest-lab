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

# The Forge candidate under test is the PINNED UPSTREAM Rules Core, materialized
# by the pinned additive bridge. This is the "pinned upstream" PB-09 resolution
# being EVIDENCED, not selected: the Coordinator still owns candidate identity,
# and nothing here repins config/rules_engines.json, which already names this
# commit as secondary_engine.commit.
#
# The Commander-Lab fork is retained below under an explicitly non-candidate
# name so no result can be reported against it by accident, and so the existing
# fork evidence keeps its own honest provenance.
FORGE_CANDIDATE_COMMIT = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"
FORGE_CANDIDATE_TREE = "4471ff068dd23127fc5878bdffa0c0e6de8e6c28"
FORGE_COLUMN_SCOPE = "pinned_upstream"
FORGE_FORK_HEAD_COMMIT = "ef958ee91ac6c9ce0152189f2654bf6e05abf273"
FORGE_FORK_HEAD_TREE = "fc3387bf37aab19d780b2939a235309ed32b0492"
FORGE_WSR20_EVIDENCE_TIP = "18bba95a4528f6ab5910633f1f87f603b8c4ddf8"
FORGE_PROVIDER = "forge"

# PB-09 identity distinction. These are three different things and must never be
# conflated, reported under one name, or compared as if one implied another.
#
#   FORGE_CANDIDATE_COMMIT        the PINNED UPSTREAM Rules Core, and the engine
#                                 this column executes. It is materialized by
#                                 FORGE_BRIDGE_SOURCE_COMMIT, whose diff against
#                                 the pin is confined to forge-protocol2-bridge/**
#                                 and pom.xml, so the Rules Core executes
#                                 unmodified. Upstream behaviour is now observed.
#   FORGE_FORK_HEAD_COMMIT        the Commander-Lab fork that produced all
#                                 earlier Forge evidence. NOT a candidate: it is
#                                 Lab-modified Rules Core. No result may be
#                                 reported against it here.
#   FORGE_UPSTREAM_BASELINE_COMMIT the same upstream pin, kept under its
#                                 historical name for receipts that reference it.
#                                 Ancestry is NOT identity and a descendant is a
#                                 different tree.
#   FORGE_WSR20_EVIDENCE_TIP      the WSR20/WSR24 descendant of the fork. This is
#                                 what the fork's bound native suites executed
#                                 at, and it is not the candidate either. A suite
#                                 executed at a descendant cannot be attributed
#                                 to the candidate without a module-tree proof.
FORGE_FORK_REPOSITORY = "https://github.com/moeendres-png/forge.git"
FORGE_UPSTREAM_REPOSITORY = "https://github.com/Card-Forge/forge.git"
FORGE_UPSTREAM_BASELINE_COMMIT = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"
FORGE_UPSTREAM_BASELINE_VERIFIED_PRISTINE = True
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
                "column_scope": FORGE_COLUMN_SCOPE,
                "engine_identity_pb09": {
                    "executing_engine": {
                        "role": "THE PINNED UPSTREAM RULES CORE THAT ACTUALLY RUNS, "
                        "materialized by the additive bridge below.",
                        "repository": FORGE_UPSTREAM_REPOSITORY,
                        "commit": FORGE_CANDIDATE_COMMIT,
                        "tree": FORGE_CANDIDATE_TREE,
                        "is_pristine_upstream": True,
                    },
                    "fork_head": {
                        "role": "THE COMMANDER-LAB FORK. NOT a candidate: it is "
                        "Lab-modified Rules Core. Every earlier Forge result was "
                        "produced here and none of it may be reported against the "
                        "pinned candidate.",
                        "repository": FORGE_FORK_REPOSITORY,
                        "commit": FORGE_FORK_HEAD_COMMIT,
                        "tree": FORGE_FORK_HEAD_TREE,
                        "is_pristine_upstream": False,
                    },
                    "upstream_baseline": {
                        "role": "the same upstream pin under its historical name, "
                        "kept so receipts that reference it stay resolvable.",
                        "repository": FORGE_UPSTREAM_REPOSITORY,
                        "commit": FORGE_UPSTREAM_BASELINE_COMMIT,
                        "verified_pristine": FORGE_UPSTREAM_BASELINE_VERIFIED_PRISTINE,
                        "upstream_behaviour_observed": True,
                        "note": "upstream behaviour was UNKNOWN until the pinned "
                        "candidate was built and executed at this identity; the "
                        "historical fork result is NOT an upstream result and must "
                        "never be presented as one",
                    },
                    "wsr20_evidence_tip": {
                        "role": "WHERE THE FORK'S BOUND NATIVE SUITES EXECUTED. "
                        "Neither the fork head nor the pinned candidate.",
                        "commit": FORGE_WSR20_EVIDENCE_TIP,
                        "is_candidate_head": False,
                        "note": "a suite executed at this descendant must not be "
                        "attributed to candidate_commit; verify_candidate_identity "
                        "and engine_tree_equivalence both fail closed on the divergence",
                    },
                    "bridge_source_commit": {
                        "role": "the additive Protocol-2 bridge that materializes the "
                        "pinned Rules Core, distinct from the engine commit; its diff "
                        "against the pin is confined to forge-protocol2-bridge/** and "
                        "pom.xml, so the Rules Core executes unmodified",
                        "commit": FORGE_BRIDGE_SOURCE_COMMIT,
                        "rules_core_base_commit": FORGE_CANDIDATE_COMMIT,
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

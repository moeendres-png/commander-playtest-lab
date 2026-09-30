"""Current-boundary identity constants and receipts (WSR22).

Every identity here is current-boundary authority. Sealed historical evidence
is never rewritten, but current candidate identities may advance only through
an explicit owner/coordinator adjudication. R-1 (2026-09-30) admits the
Commander-Lab-maintained Forge fork for exact-source qualification; this does
not select a Production Provider or claim Architecture Freeze.
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

FORGE_CANDIDATE_COMMIT = "e22c424adde043e23892e4bb59aaeb4d2fb089d9"
FORGE_CANDIDATE_TREE = "6c49f100fe61d1b2a71dd46a7347a2ff0f0da4ea"
FORGE_WSR20_EVIDENCE_TIP = "18bba95a4528f6ab5910633f1f87f603b8c4ddf8"
FORGE_QUALIFICATION_LINEAGE_BASE_COMMIT = "ef958ee91ac6c9ce0152189f2654bf6e05abf273"
FORGE_PROVIDER = "forge"

# R-1 / PB-09 current identity distinction. The current exact-source candidate
# is the maintained fork successor. ef958ee9 is retained as its admitted
# Rules-Core lineage base; pristine upstream remains reference-only; the WSR20
# execution tip remains historical evidence. None of those historical identities
# receives current credit merely because R-1 changed candidate authority.
FORGE_FORK_REPOSITORY = "https://github.com/moeendres-png/forge.git"
FORGE_UPSTREAM_REPOSITORY = "https://github.com/Card-Forge/forge.git"
FORGE_UPSTREAM_BASELINE_COMMIT = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"
FORGE_UPSTREAM_BASELINE_VERIFIED_PRISTINE = False
FORGE_BRIDGE_SOURCE_COMMIT = FORGE_CANDIDATE_COMMIT

# The bridge/provider role remains separately named even when it co-resides at
# the same exact source commit as the maintained-fork candidate. PR #13 is a
# bridge-only successor of the accepted #11 head and closes the bounded AF01
# unsupported-decision-class residual. Same-SHA role binding is intentional and
# does not collapse Rules authority into the bridge.
FORGE_BRIDGE_EVIDENCE_COMMIT = FORGE_CANDIDATE_COMMIT
FORGE_BRIDGE_EVIDENCE_TREE = FORGE_CANDIDATE_TREE
FORGE_BRIDGE_EVIDENCE_PR = 13
FORGE_BRIDGE_EVIDENCE_IS_DRAFT = False

# PB-05 provenance fields the bridge now emits. They are consumed fail-closed:
# no verified=true means no AF00/PB-05 credit, and a dirty or unknown build
# source means no current evidence at all.
FORGE_PB05_PROVENANCE_FIELDS = (
    "engine_build_commit",
    "engine_build_tree",
    "engine_build_dirty",
    "engine_build_source",
    "engine_commit_verified",
)
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
                    "pb09_status": "RESOLVED_BY_OWNER_R1_2026_09_30_FOR_CURRENT_QUALIFICATION_AUTHORITY",
                    "qualification_lineage_base": {
                        "role": "R-1 Rules-Core lineage base; ancestor only, not the current exact-source candidate.",
                        "repository": FORGE_FORK_REPOSITORY,
                        "commit": FORGE_QUALIFICATION_LINEAGE_BASE_COMMIT,
                        "is_current_candidate": False,
                    },
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
                        "role": "HISTORICAL WSR20/WSR24 native-suite execution identity. "
                        "Supporting evidence only; not current Final-Gate credit.",
                        "commit": FORGE_WSR20_EVIDENCE_TIP,
                        "is_candidate_head": False,
                        "note": "R-4 forbids carried-forward historical execution from "
                        "standing in for fresh direct current-candidate execution.",
                    },
                    "bridge_evidence_head": {
                        "role": "CURRENT BRIDGE/PROVIDER SOURCE ROLE. Bound explicitly "
                        "even though it shares the exact source commit with the unified "
                        "maintained-fork candidate. Forge PR #13 is bridge-only and is "
                        "not a forge/master merge authorization.",
                        "repository": FORGE_FORK_REPOSITORY,
                        "commit": FORGE_BRIDGE_EVIDENCE_COMMIT,
                        "tree": FORGE_BRIDGE_EVIDENCE_TREE,
                        "pull_request": FORGE_BRIDGE_EVIDENCE_PR,
                        "is_draft": FORGE_BRIDGE_EVIDENCE_IS_DRAFT,
                        "changes_rules_core": False,
                    },
                    "bridge_source_commit": {
                        "role": "current bridge/materialization source role; same exact "
                        "source commit as the unified candidate by R-1 design",
                        "commit": FORGE_BRIDGE_SOURCE_COMMIT,
                    },
                    "pb05_provenance_consumed": list(FORGE_PB05_PROVENANCE_FIELDS),
                    "pb05_credit_rule": "no engine_commit_verified=true means no AF00 or "
                    "PB-05 credit; a dirty or unknown build source means no current evidence",
                },
                "candidate_tree": FORGE_CANDIDATE_TREE,
                "wsr20_evidence_tip": FORGE_WSR20_EVIDENCE_TIP,
                "license": FORGE_LICENSE,
                "substitution_forbidden": "historical WSR20/upstream identities are not substitutes for the current exact-source candidate",
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

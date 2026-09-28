"""Current-boundary qualification orchestration (candidate-neutral).

WSR22 — FINAL-CURRENT-BOUNDARY-FREEZE-QUALIFICATION-20260927.

This package is the smallest Lab-owned orchestration required to execute the
effective FULL107 provider denominator against BOTH candidate Rules engines
under the current pre-Freeze qualification boundary
``commander-lab.pre-freeze-qualification/2.0.0``.

It is deliberately NOT a second Rules engine. It may only:

* materialize canonical fixture inputs from the effective contract;
* launch the exact pinned engine/provider builds as external processes;
* supply externally discretionary decisions among engine-offered options;
* bind supported Rules RNG seeds;
* observe principal-scoped outputs;
* collect semantic events;
* classify runtime evidence.

It must never reconstruct legality, calculate Rules outcomes, fabricate
options, inject expected outcomes, choose Rules randomness, patch engine state
to force parity, or default a decision. Unsupported production-reachable
paths fail closed.
"""

from __future__ import annotations

from .af01 import AF01_INVARIANTS, run_af01
from .af03 import AF03Report, run_af03
from .bridge_launcher import (
    BridgeLaunchError,
    BridgeProcess,
    CandidateId,
    build_launch_plan,
    launch,
)
from .full107 import (
    NEGATIVE_ROWS,
    OUTCOMES,
    PILOT_ROWS,
    REPLAY_ROWS,
    RowResult,
    cardinality_row,
    export_replay,
    non_executed_row,
    observe_principal_state,
    run_cardinality,
    start2_row,
    summarize,
    validate_principal_scoping,
)
from .game_driver import (
    DECISION_IDENTITY_SHAPES,
    build_deck,
    drive_commander_game,
)
from .materialization import (
    EffectiveMaterialization,
    load_effective_materialization,
)
from .source_lock import (
    CURRENT_QUALIFICATION_BOUNDARY,
    CURRENT_RULES_AUTHORITY_EFFECTIVE_DATE,
    CURRENT_TRANSPORT_PROTOCOL,
    FORGE_CANDIDATE_COMMIT,
    FORGE_CANDIDATE_TREE,
    FORGE_WSR20_EVIDENCE_TIP,
    FULL107_FROZEN_SOURCE,
    XMAGE_CANDIDATE_COMMIT,
    XMAGE_LAB_RUNTIME_AUTHORITY,
    boundary_receipt,
)

__all__ = [
    "AF01_INVARIANTS",
    "CURRENT_QUALIFICATION_BOUNDARY",
    "CURRENT_RULES_AUTHORITY_EFFECTIVE_DATE",
    "CURRENT_TRANSPORT_PROTOCOL",
    "DECISION_IDENTITY_SHAPES",
    "FORGE_CANDIDATE_COMMIT",
    "FORGE_CANDIDATE_TREE",
    "FORGE_WSR20_EVIDENCE_TIP",
    "FULL107_FROZEN_SOURCE",
    "NEGATIVE_ROWS",
    "OUTCOMES",
    "PILOT_ROWS",
    "REPLAY_ROWS",
    "XMAGE_CANDIDATE_COMMIT",
    "XMAGE_LAB_RUNTIME_AUTHORITY",
    "AF03Report",
    "BridgeLaunchError",
    "BridgeProcess",
    "CandidateId",
    "EffectiveMaterialization",
    "RowResult",
    "boundary_receipt",
    "build_deck",
    "build_launch_plan",
    "cardinality_row",
    "drive_commander_game",
    "export_replay",
    "launch",
    "load_effective_materialization",
    "non_executed_row",
    "observe_principal_state",
    "run_af01",
    "run_af03",
    "run_cardinality",
    "start2_row",
    "summarize",
    "validate_principal_scoping",
]

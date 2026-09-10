"""Q6 actual-card scaffolding pipeline (mechanical preparation only).

This package automates qualification *preparation* (intake, parsing,
capability clustering, valueless skeleton generation, review queues,
manifests). It is structurally incapable of awarding card behavior PASS,
qualification credit, or coverage promotion: the schemas defined here
contain no behavior-credit fields, and :mod:`gate` rejects any input or
output that attempts to carry them.

Evidence class of everything produced here: SYNTHETIC (tooling output),
never behavior evidence. Authoritative behavior truth comes only from the
Rules Core plus official Magic rules/Oracle/rulings via runtime
qualification, which this package never performs.

Clean-room provenance: the Forge card-script parser in
:mod:`forge_parser` is a project-authored reimplementation ported from the
D3 clean-room prototype ``d3q6-cleanroom-0.1.0``
(``research/d3-q6-import-automation/forge_script_parser.py`` at
``moeendres-png/mage@a766f900``), itself written from the public Forge
wiki format description plus observed corpus files. No Forge GPL, Manabrew
AGPL, or third-party implementation code is copied, linked, or embedded.
"""

from __future__ import annotations

Q6_SCAFFOLDING_VERSION = "q6-scaffolding-0.1.0"

SCHEMA_INTAKE_RECORD_V1 = "q6.intake-record.v1"
SCHEMA_PARSE_RESULT_V1 = "q6.parse-result.v1"
SCHEMA_CLASSIFICATION_V1 = "q6.classification.v1"
SCHEMA_SCENARIO_SKELETON_V1 = "q6.scenario-skeleton.v1"
SCHEMA_QUEUE_ITEM_V1 = "q6.queue-item.v1"
SCHEMA_MANIFEST_V1 = "q6.campaign-manifest.v1"

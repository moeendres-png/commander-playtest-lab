# WS221 Evidence Vocabulary Inventory (pre-repair, independently re-inspected)

Four live vocabularies plus free prose, exactly as WS220 reported:

1. Doctrine policy (docs/EVIDENCE_INDEX_REQUIREMENTS.md §2, 7 terms):
   DIRECTLY_VERIFIED, CODE_DERIVED, TECHNICALLY_CONFORMANT,
   EXTERNALLY_RULE_VALIDATED, MODELED, SYNTHETIC, UNKNOWN.
2. Machine schema enum (candidate_result_v1 + normalized_evidence_v1, 5 terms):
   RUNTIME_VERIFIED, DIRECT_CODE_FAIL, CODE_DERIVED, SOURCE_DERIVED, NOT_RUN.
   Gap: UNKNOWN and the other policy terms are not representable.
3. Failure classifications (candidate_result_v1, 9 terms): DIRECT_RULES_FAIL,
   DIRECT_PILOT_BOUNDARY_FAIL, DIRECT_CARD_COVERAGE_FAIL,
   PROTOCOL_ADAPTER_MISSING, QUALIFICATION_INFRASTRUCTURE_MISSING,
   AUTHORITY_BLOCKED, RUNTIME_NOT_RUN, RUNTIME_PASS, REMEDIATION_REQUIRED.
4. Harness-synthesised row values: evidence_class default-fill
   (`harness.py` pre-fix lines 111–114: missing class defaulted to
   RUNTIME_VERIFIED for PASS/FAIL rows) and classification RUNTIME_PASS for any
   PASS verdict regardless of evidence strength — the active silent-upgrade path.
5. Free prose in sealed VALIDATION.json (ws80, ws88, ws90 evidence_class) and
   evidence_classification UNKNOWN/CODE_DERIVED/MODELED/DIRECTLY_VERIFIED in
   ws205_adjudicate.py / ws207_setup.py (policy-axis terms, controlled).
6. Separate non-evidence axes that must never merge into Axis 1:
   pin-consumer dispositions, risk-matrix classes, ws79 ledger dispositions,
   retention anchor types, Structural decision-bundle tags
   (structural_model_estimates et al.), full-game conformance tags
   (technical_conformance_only).

Machine-readable note: exact pre-repair enums are quoted in the schemas at the
audit base; the coercion lines are preserved in git history (harness.py pre-WS221).

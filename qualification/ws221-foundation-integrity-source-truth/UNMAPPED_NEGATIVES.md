# WS221 Unmapped Negatives

Deliberate injections, all proven rejected (tests/qualification/test_ws221_evidence_vocab.py):

- PASS verdict with missing evidence_class → UNKNOWN / UNKNOWN / RUNTIME_NOT_RUN.
- PASS verdict with free-prose evidence_class (ws88-style) → rejected, reason recorded.
- PASS verdict with CODE_DERIVED → UNKNOWN verdict, CODE_DERIVED preserved, no upgrade.
- require_evidence_class: None, "", lowercase, "PASSED", non-strings → UnmappedEvidenceTerm.
- map_legacy_evidence_class: brand-new term → UnmappedEvidenceTerm.
- Schema validation: free-prose evidence_class rejected; controlled UNKNOWN/DIRECTLY_VERIFIED/TECHNICALLY_CONFORMANT/MODELED/SYNTHETIC accepted.
- Rejected rows block production admission (aggregate FAIL).

# WS221 Legacy Mapping (evidence-legacy-map-v1)

Authority: qualification/evidence/evidence_legacy_map_v1.json, read-time
adaptor `map_legacy_evidence_class` in evidence_vocab_v1.py. Sealed artifacts
are never rewritten.

| Seal term | Disposition | Mapping |
|---|---|---|
| ws88 "RUNTIME_VERIFIED unless a gate cites a sealed historical frame" | LEGACY_EXPLICITLY_MAPPED | RUNTIME_VERIFIED + qualifier preserved |
| ws90 per-aspect breakdown (CODE_DERIVED / TECHNICALLY_CONFORMANT / DIRECTLY_VERIFIED / NOT_RUN) | LEGACY_EXPLICITLY_MAPPED | aspect map; behavior consumers take NOT_RUN |
| ws80 "CODE_DERIVED unless noted as RUNTIME_VERIFIED …" | LEGACY_EXPLICITLY_MAPPED | default CODE_DERIVED; RUNTIME_VERIFIED only for seal-named gates |
| ws205/ws207 evidence_classification UNKNOWN/CODE_DERIVED/MODELED/DIRECTLY_VERIFIED | CURRENT_NATIVE | policy-axis terms inside the controlled enum |
| WS17 candidate reports (NOT_RUN/CODE_DERIVED/RUNTIME_VERIFIED) | CURRENT_NATIVE | validate against updated schemas |
| Any other term at a machine join | INVALID_UNMAPPED | rejected (UnmappedEvidenceTerm → UNKNOWN row) |
| Pin-consumer / risk-matrix / ws79-ledger / retention / Structural tags | HISTORICAL_NOT_CONSUMED (by Axis 1) | separate axes; never fed to require_evidence_class |

Production-relevant current readers: harness.py execute() (understands the
mapping exactly: native terms pass, legacy prose is rejected at the join and
must arrive via the explicit adaptor), schema validators (accept the 11-term
enum, reject prose). Proven in tests/qualification/test_ws221_evidence_vocab.py.

# WS221 Controlled Vocabulary Design (evidence-vocab-v1)

Authority: qualification/evidence_vocab_v1.py (VOCAB_VERSION evidence-vocab-v1).

Four axes, never one enum:

- Axis 1 EVIDENCE_CLASS (11 controlled terms): RUNTIME_VERIFIED,
  DIRECT_CODE_FAIL, CODE_DERIVED, SOURCE_DERIVED, NOT_RUN (machine-native) +
  DIRECTLY_VERIFIED, TECHNICALLY_CONFORMANT, EXTERNALLY_RULE_VALIDATED,
  MODELED, SYNTHETIC, UNKNOWN (doctrine-native). CODE_DERIVED is shared;
  NOT_RUN (runtime not executed) and UNKNOWN (not established) stay distinct;
  both fail closed.
- Axis 2 VERDICT: unchanged 7-term WS17 enum.
- Axis 3 FAILURE_CLASSIFICATION: unchanged 9-term WS17 enum.
- Axis 4 OMISSION_REASON: unchanged 5-term WS17 enum.

Invariants enforced in code (`require_evidence_class`,
`is_satisfying_evidence`): UNKNOWN != PASS; CODE_DERIVED != RUNTIME_VERIFIED;
construction/import/readback caps at CODE_DERIVED/SOURCE_DERIVED, never
RUNTIME_VERIFIED. The only credit-granting pair is PASS + RUNTIME_VERIFIED.

Schemas candidate_result_v1 / normalized_evidence_v1 adopt the Axis-1 enum
(verdict/classification/omission enums untouched): no semantic flattening,
UNKNOWN becomes representable, free prose stays schema-rejected.

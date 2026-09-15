# WS221 Harness Strictness (reject, never coerce)

Repair: qualification/harness.py execute().

Pre-repair coercion (removed): missing provider evidence_class defaulted to
RUNTIME_VERIFIED for PASS/FAIL verdicts; any PASS verdict was classified
RUNTIME_PASS regardless of evidence strength.

Post-repair machine-join rules:

1. Missing / non-string / unmapped evidence_class → row rejected: verdict
   UNKNOWN, evidence_class UNKNOWN, classification RUNTIME_NOT_RUN, reason
   records the rejected term. The provider's claimed verdict is not honored.
2. Verdict PASS with evidence_class != RUNTIME_VERIFIED → row demoted to
   UNKNOWN (weak claim preserved in evidence_class for diagnosis), never
   upgraded to RUNTIME_VERIFIED / RUNTIME_PASS.
3. Classification RUNTIME_PASS is emitted only for PASS + RUNTIME_VERIFIED.
4. normalize_missing (no provider configured) still emits NOT_RUN / NOT_RUN /
   PROTOCOL_ADAPTER_MISSING — native controlled terms, fail closed, block
   admission via aggregate().

Forbidden paths confirmed absent: no PASS→RUNTIME_VERIFIED default, no missing
upgrade, no strongest-class mapping of unknown terms, no free-prose acceptance
at the join.

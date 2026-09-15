# WS220 Evidence-Model Audit

Questions: are evidence standards strong enough? unnecessarily expensive
anywhere? where can green create false confidence?

## Verdict: STANDARDS STRONG IN DESIGN, LEAKING AT THE JOINTS

Strengths (real): fail-closed defaults everywhere; UNKNOWN discipline mostly
honored in seals; twin controls with honest PARTIALs; zero behavior credit
claimed where unearned (WS205/207 credit 0; WS213 +1 with pointer); FULL107
correctly withheld; impact-selected suite scoping in WS213/215 seals.

Joints leaking (all P1):
1. F-EVID-03 — four vocabularies; `harness.py` coerces missing
   `evidence_class` to RUNTIME_VERIFIED for PASS rows. Machine joining today
   would upgrade weak evidence silently.
2. F-EVID-01 — stale WS17 rollup vs live seals; CI pins the stale shape.
3. F-EVID-04a — retention prose without machine predicates; two sentences
   literally inaccurate (pin-unchanged / byte-identical).
4. F-EVID-04b — retention unscoped for N≠4.
5. F-QUAL-02 — authority anchor UNKNOWN; G01 FAIL; admission ungrounded.
6. F-CI-02 — integrity gate RED on the WS215 line.

Expensive anywhere? No — the opposite risk profile: the project withholds
expensive runs correctly (FULL107 NOT_RUN, scoped suites). The waste is
repetition of low-information neutral runs (16/17 zero-offer games re-driven
3–4×) and 6.6M-line evidence bulk that no human reviews while the integrity
layer disagreeing with it (RED gate) goes unanswered.

False-confidence ranking: harness coercion (silent upgrade) > stale rollup
(wrong picture) > prose retention (rot over time) > RED gate (ignored red).
Fix in that order (S1, S2, S8, S4).

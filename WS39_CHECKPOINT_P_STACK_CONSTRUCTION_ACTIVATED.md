# WS39 CHECKPOINT P — STACK CONSTRUCTION ACTIVATED / FOUR NATIVE FAILURES

## Status

Persistent resumable WS-39 checkpoint after the first exact full-107 construction run with `stack_state` and `zone:stack` enabled.

This checkpoint grants **construction evidence only**. It grants no successor behavior runtime credit, imports no historical PASS, and does not claim AF07 or Architecture Freeze.

## Source Lock

- Commander Lab branch: `ws39/xmage-engine-remediation-requalification`
- Provider commit: `2a25528a0c2cf640991e28a02692fda4a217500d`
- Provider tree: `aeac38e589c949fbf720371aa5a89030de12acca`
- XMage commit: `7bde812727817723616c575759f39bfc4cda4607`
- XMage tree: `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`
- WS32 freeze commit: `038d0f38635eecee4e331c99af41f148de267a26`
- WS32 freeze tree: `0d160128119f2bad30b220a17c43419b50b7edbe`
- Exact WS39 denominator: 107 records.

## Exact Runtime Evidence

- Workflow: `WS39 Full107 Native Construction Probe`
- Run: `33794109615`
- Job: `100777526648`
- Job conclusion: `SUCCESS`
- Native `CommanderPlaysCountStateRestoreTest`: PASS
- Exact XMage build: PASS
- Qualification bridge build: PASS
- Runtime classpath materialization: PASS
- Full-107 native construction probe: PASS as an evidence-producing fail-closed census
- Evidence seal: PASS
- Artifact upload: PASS

Artifact:

- id: `9908948532`
- name: `ws39-full107-construction-2a25528a0c2cf640991e28a02692fda4a217500d`
- GitHub artifact digest: `sha256:c9c52c7120ed7447eda95ea52f63d7c1dd608e2a9533bf3bff1e86cf8ca53e7b`
- independently downloaded ZIP SHA256: `c9c52c7120ed7447eda95ea52f63d7c1dd608e2a9533bf3bff1e86cf8ca53e7b`
- `WS39_FULL107_CONSTRUCTION_PROBE.json` SHA256: `fef78df6af00454a8490dbee8635a80c8cf11048649aff11e565ec6d4e220d91`
- all 10 entries in artifact `SHA256SUMS`: independently verified, zero mismatch after restoring the archived path prefix.

## Fresh Construction Result

- `NATIVE_SETUP_PASS_NO_RUNTIME_CREDIT`: **49**
- `DEFERRED_TO_FRESH_NATURAL_EXECUTOR`: **7**
- `FAIL_CLOSED_UNSUPPORTED_NATIVE_DIMENSION`: **47**
- `FAIL_CLOSED_NATIVE_CONSTRUCTION`: **4**
- total: **107**
- `historical_pass_imported=false`
- `runtime_credit_granted=false`

Compared with Checkpoint O / the last successful pre-stack census (`39 / 7 / 61 / 0`), enabling stack construction converts ten previously unsupported records into native setup PASS and exposes four concrete native construction failures. No failure is hidden or reclassified as PASS.

## Four Concrete Native Construction Failures

1. `PILOT_CHOICE`
   - record digest: `f255fb5e8aaa115c659442bd60d617a8ba5128b2df945e3b013c5c6c3a2f90ba`
   - requested-state digest: `4c1c8ab42c351281cd9f0d34a770ea65eaff7ab8c909ad57b989671842456044`
   - error: `NATIVE_VALIDATION_FAILED: stack target group cardinality obj:utopia`

2. `PILOT_REPLACEMENT_EFFECT`
   - record digest: `294d304eb6fd307ae0899f9e9805d03ef3addf34e489ceae19f021770c6b9074`
   - requested-state digest: `415d143b6caf8725211c75001cee234bc1871af98e50abd840db5bb1aa411ed3`
   - error: `NATIVE_VALIDATION_FAILED: stale semantic id obj:P1-commander`

3. `MICRO_PRIORITY`
   - record digest: `6ea3fff3fbf3cde65b87662bb2612c8a22264fd36060213a9622ed3a9d262ee3`
   - requested-state digest: `a031bd468065626232a04fec05470e7aef28deb933933cec9c9b7a288b7b73ae`
   - error: `NATIVE_VALIDATION_FAILED: stale semantic id obj:P2-bears`

4. `MICRO_STACK`
   - record digest: `00fc1c6c04b498cce5f8aacb976276648d91f69ff1c0fe7d764bf90d99889fec`
   - requested-state digest: `a031bd468065626232a04fec05470e7aef28deb933933cec9c9b7a288b7b73ae`
   - error: `NATIVE_VALIDATION_FAILED: stale semantic id obj:P2-bears`

## Interpretation

- The stack overlay is now genuinely exercised against the frozen v1.0.2 denominator.
- Ten stack-bearing records construct and validate natively that were previously blocked only by capability declaration.
- Four stack-bearing records expose bounded setup/readback defects and remain fail-closed.
- The remaining 47 records are still blocked by other explicitly unsupported native snapshot dimensions.
- Construction equality remains necessary but insufficient for successor behavior PASS.

## Exact Next Action

1. Audit only the four fresh native construction failures against the exact frozen requested states and current `apply_ws39_stack_state_overlay.py` implementation.
2. Repair stale semantic-id handling and the `obj:utopia` target-group cardinality path using XMage-native identities/targets; do not weaken native validation and do not invent harness legality.
3. Re-run the exact Full-107 construction workflow.
4. Persist the resulting census before touching any further setup family.
5. Continue until all 107 records are either fresh native-construction-ready or correctly delegated to a fresh natural-start executor, then execute the complete fresh 107/107 behavior qualification.

No merge is authorized.

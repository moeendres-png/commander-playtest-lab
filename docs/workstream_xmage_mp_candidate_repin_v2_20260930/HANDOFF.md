# Handoff: XMage multiplayer-candidate repin v2 (2026-09-30)

## Source Lock
- **Lab:** base `main` at the branch point of `claude/xmage-mp-candidate-repin-v2-20260930`.
- **XMage:** prior pin `f79e4168`, new pin `9375f35ac7c9a540ebcb8b262b8645b8c6b1b326` (tree `0fb7c2f9`), on branch `claude/xmage-mp-candidate-20260929` (moeendres-png/mage#24).

## Work completed
- **Candidate** = `f79e4168` plus:
  - mage#26 (F-22/F-23, merge `23b996a5`);
  - mage#27/#28 (F-28/F-29, merge `2dc89b3c`);
  - the F-34 donor `2786665809` (merge `9375f35a`).
- **Lab repin:**
  - `config/rules_engines.json` pin, archive and authority note;
  - 19 active literal consumers: workflows, provider, bridge tests, scripts, unit pin tests;
  - successor lock v2 and guard `tests/qualification/test_xmage_mp_candidate_repin_v2_20260930.py`;
  - the v1 guard's current-pin checks marked superseded;
  - fingerprint extended;
  - F-22/F-23/F-28/F-29 regressions enabled (the F-22/F-23 ones ported from #360);
  - SHA256 manifests regenerated.
- **Not repinned:**
  - the WSR22 `source_lock.py` (b19596980f27);
  - the v1 successor lock (f79e4168);
  - Java test comments that name `f79e4168` as historical provenance.

## Tests / evidence
- **Native:** full `Mage.Tests` on `9375f35a`, 7020 / 0 / 0 / 125 (DIRECTLY_VERIFIED).
- **Lab bridge suite:** see the successor lock `lab_runtime_qualification.bridge_suite` (DIRECTLY_VERIFIED, isolated Maven repo).
- **Exact-head CI:** this PR.

## Remaining blockers / next
- Close or re-scope the draft Lab PR #360 (its content is carried here). That is its owner's call.
- A successor FULL107 current-boundary run on the new pin (a Coordinator gate).
- The consolidated engine CI with a required `engine-gate` job (see `docs/ci_efficiency_20260930/README.md`).

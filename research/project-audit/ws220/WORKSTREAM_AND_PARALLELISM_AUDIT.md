# WS220 Workstream & Parallelism Audit

Question: is workstream sizing/parallelism/integration optimal?

## Verdict: CORRECT SERIALITY IN THE XMAGE CHAIN, FRAGMENTATION ELSEWHERE

Facts: XMage WS203→215 strictly serial (justified — each consumes the prior
lane; WS207∥WS208 parallelism correctly exploited). Foundry WS196→200
strictly serial over disjoint surfaces (unjustified — contract coordination
would have sufficed). WS197 proves parallel branching from main works.
Micros (WS196/204/208: 1 unique commit each) pay full ceremony for tiny
surfaces (~10h wall for ~5k Foundry lines across 4 streams).

Integration risks (F-WS-01 P2, F-WS-02 P3): 18-deep + 9-deep unmerged stacks;
WS208 consumed conceptually without ancestry or verification trace; RED gate
grows rebase burden; POST_LOCK_DRIFT from WS218/219 possible.

Better default sizing model (for S14):
- Integrate-or-extend: a stream that only consumes a prior tip without
  changing its surface extends the prior stream (checkpoint commit) instead
  of chartering a successor — unless parallel ownership is needed.
- Minimum viable stream ≈ one behavior claim + its seal (WS204-scale is the
  floor; WS196-scale ceremony for 1 commit is overhead).
- Parallel by default for disjoint surfaces (WS197 pattern); serial only for
  lane-consumption (WS203→205 pattern).
- Ancestry-or-traceability: consumed findings get a verification pointer.
- Merge train: unmerged depth capped (e.g. advisory cap ~8) with manifest
  refresh at each merge (kills F-CI-02 class defects at birth).

Terminal handoffs unlock next work well (successor specs S1-S4 →
S-SETUP/S-PILOT/S-MECH → handoff Exact Next Actions). The failure is not
handoff quality but merge cadence.

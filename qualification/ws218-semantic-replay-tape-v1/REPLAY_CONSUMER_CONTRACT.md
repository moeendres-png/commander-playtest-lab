# WS218 REPLAY_CONSUMER_CONTRACT

First-class fresh-process consumer (`semantic_replay/consumer.py::
replay_tape`): parse/validate → lock verify (refuse-before-execution) →
fresh JVM → exact-manifest construction → pre-randomness seed bind → native
start → initial verify → per-step await native decision, verify
actor/class/revision/observation/legal-set/RNG-before, resolve recorded
prints to EXACTLY ONE native option each (0→MISSING, >1→AMBIGUOUS), submit
CURRENT native ids + recorded numeric, verify RNG-after/event/post →
terminal verify (no extra decisions; seat-mapped five-field outcomes
equal). Concede steps via native offer/execute for the exact principal.
No fuzzy match, skip, missing-decision injection, filtering, or second
legality engine (consumer imports no pilot/policy; recorder-only policy
use). 14-step algorithm implemented exactly.

Machine companion: `REPLAY_CONSUMER_CONTRACT.json`.

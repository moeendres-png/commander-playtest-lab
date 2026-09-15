# WS229 HIDDEN_INFO_IMPACT (regression GREEN)

## Claim

No hidden-information leakage introduced: numeric descriptors carry only
ints; joint legs carry min/max ints + engine prompt strings (no
identities); no UUID traverses the new paths.

## Evidence (DIRECTLY_VERIFIED)

- `XmageFullGameHiddenInformationTest` (live full-game hidden-info suite):
  1/1 PASS on the WS229 tree with joint-capable drivers.
- `XmageFullGameNameCanaryTest` (UUID + name-canary guarantees): 4/4
  PASS on the WS229 tree.
- Python `test_ws224_name_canary.py`: green in the impact sweep.
- Actor-safe identities: untouched (redactor, stable ids, label
  tiebreaks all unchanged; priority/mana views use raw offered ids as
  before, no new identity joins).
- Transcript additions (`forced_move`, `numeric_choices`) carry labels
  and ints only; `semantic_transcript` mapping ignores unknown keys
  safely (reads via .get with None defaults).

## UUID/name-canary guarantees

Preserved: no per-process engine UUID enters pilot views, descriptors,
tape fields, logs, or evidence (pending-frame captures in
LIVE_FRAME_CAPTURES.json carry per-run random ids REDACTED to stable
shape; only decision_class/context/counts are recorded).

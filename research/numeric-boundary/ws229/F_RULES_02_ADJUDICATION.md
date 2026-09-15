# WS229 F-RULES-02 Adjudication (CLOSED by this workstream)

## Defect (WS220 P1, reproduced WS228)

`_decide_numeric` collapsed span>16 domains to {min,mid,max} before pilot
ranking (first and only narrowing point, full_game.py:750-754).

## Disposition

REMOVED. The enumeration/collapse hunk is deleted; the scalar descriptor
path offers the full authoritative interval at every span. No bounded-set
alternative was needed: the range-native design is O(1) at any span, so
no performance justification for narrowing exists either.

## Proof

- R4 entry premise confirmed the hunk present on the base; post-repair
  grep shows no `midpoint`, no `maximum - minimum <= 16` branch, no
  `numeric:{value}` view construction on the numeric path.
- Descriptor exactness + interior submissions at span>16 executed
  (POSITIVE_MATRIX_RESULTS P-A1/P-A2; ANNOUNCE_X_LIVE/AMOUNT_LIVE).
- Boundary 16/17 behavior retired: both spans now expose the full domain
  (P-B1).
- Full unit + JVM suites green with no narrowing-shaped assertions left
  (the one matrix row pinning the old scalar multi shape was migrated to
  the joint contract as a documented contract change, not a weakening).

## Credit

Per-class behavior credit only for rows with live observation (see
POSITIVE_MATRIX_RESULTS evidence classes); nothing is promoted by fiat.

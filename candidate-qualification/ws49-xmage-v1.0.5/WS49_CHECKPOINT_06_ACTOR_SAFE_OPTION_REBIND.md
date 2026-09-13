# WS-49 CHECKPOINT 06 — ACTOR-SAFE OPTION REBIND REMEDIATION

Status: **PERSISTED / NO PASS CREDIT GRANTED**

## Exact failure evidence

- provider head: `4ef534e113d635c857186f4df481712963daac91`
- workflow run: `34278951702`
- job: `102238785059`
- outcome: failure; `100/107` native setup-ready and `7/107` fail-closed

The exact seven NATURAL_GAME_START fixtures reached the first native
starting-player offer.  Submission then failed closed with:

`COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER: missing native binding for obj-...`

XMage build and the bridge build both completed successfully.  The failure
was a bridge identity-transport defect, not a Rules result.

## Root cause and bounded remediation

`XmageFullGameDecisionController` correctly created a native-to-semantic
binding, but the subsequent actor-safe identity projection replaced the
semantic option ID with a viewer-scoped opaque handle.  The controller kept
the pre-projection binding, so a legal offered opaque handle could not be
submitted back to its native XMage UUID.

`XmageDecisionOptionIdentity.rebindAfterOutboundProjection` now composes the
validated pre-projection binding with the final actor-safe option frame.  It
requires unchanged option cardinality, a nonblank ID at each corresponding
position, and no post-projection identity collision.  Otherwise it fails
closed.  No hidden identity crosses the external boundary, and this applies
generically to all decision classes rather than special-casing starting
player selection.

Focused local evidence:

- `mvn test -Dtest=XmageDecisionOptionIdentityTest`
- `4/4` PASS, including actor-safe opaque rebind and collision fail-closed
  regressions.

## Next automatic action

Push the focused bridge remediation and run a new exact-head Full107 sequence.
G49-07 remains `NOT_CLOSED`; G49-08 through G49-14 remain `NOT_RUN`.

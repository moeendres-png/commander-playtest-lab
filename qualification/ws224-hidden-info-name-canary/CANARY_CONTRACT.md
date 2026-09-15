# WS224 CANARY_CONTRACT — second negative dimension (name canaries supplement the UUID oracle)

The existing UUID oracle (`XmageFullGameHiddenInformationTest` + WS215
`HIDDEN_INFO_CARDINALITY` 9985 frames / 0 violations) is RETAINED UNCHANGED.
This contract adds the WS220-mandated name dimension. Both must be green.

## Design constraints (from the workstream objective)

- Unmistakable, test-only, never in production/user decklists as canaries.
- Located only in hidden hand/library while tested; never passed to outsiders.
- Never used as a gameplay heuristic (all live answers remain neutral:
  keep/pass/hold/minimum, identical to the UUID-oracle discipline).
- Prefer actual-card identities where infrastructure requires real cards.
- Real card names DO appear legitimately in public output (battlefield,
  graveyard, command, stack, own hand, entitled grants/choices), so the oracle
  uses a test-only sentinel WRAPPER: the per-frame hidden-EXCLUSIVE name set
  (below), never a fake production card. No Rules outcome is altered.

## Oracle A — live-engine hidden-exclusive names (Java, fresh game per count)

For each pending decision with actor A in an N-player game (N = 2, 3, 4, 5):

1. Test-only peeking (reflection, never pilot input) reads every other
   principal O != A: `O.hand[].name`, `O.library[].name`.
2. Build the PUBLIC name set P for this frame: all names in every seat's
   `battlefield`/`graveyard`/`command`, the `stack`, `commander_status`,
   the ACTOR's own `hand` names (actor-entitled), and — only while the D2
   window is live for (A <- O) — O's `granted_library` names.
3. Canary set C(A, frame) = (hidden names of all O) minus P. Only names in C
   are asserted. Rationale: a name simultaneously public (e.g. a second
   Plains on the battlefield) proves nothing; a name that is NOWHERE public
   yet appears in A's pilot-visible serialization is an unambiguous leak.
   Frames with empty C are recorded as vacuous-pass (no signal), never as
   proof; per-pair proof requires at least one non-empty C scan.
4. Assert NO element of C appears as a substring in:
   - `pilot_state` serialization (S01),
   - the full pending-decision serialization incl. `legal_options` labels +
     metadata + `context` + `source_object` (S02/S03/S04),
   - `legalActionsPayload` actions serialization (S02/S03/S04/S09),
   - the controller transcript slice serialized so far (S05/S06/S12),
   - the whole `pendingDecisionPayload` + `legalActionsPayload` (S09 container).
5. UUID oracle runs on the SAME frames (existing assertions kept verbatim in
   the original test; the canary test additionally asserts UUID absence over
   its own frames so each canary run proves UUID absence AND name absence).
6. Coverage: the actor rotates naturally as the engine offers decisions.
   Record per ordered pair (A -> O) every frame where O contributed >= 1 name
   to C and the scan passed. PASS requires every ordered pair (N*(N-1) pairs:
   2, 6, 12, 20) to have >= 1 non-vacuous pass. At 5P this proves P1 vs
   P2/P3/P4/P5 AND every other actor, not just P1.
7. Grant rule: any non-empty `granted_library` observed outside a
   `choose_object` library frame FAILS the run (window violation), independent
   of names.
8. Error probes (attacker-inducible, per count, after the scan loop):
   `wrong actor` (valid shape, swapped actor), `stale decision` (replayed
   prior decision_id), `unknown action` (ghost option id), `illegal target`
   (ghost UUID target). Each must REJECT without advancing AND its
   error-message text must contain no element of the CURRENT frame's full
   hidden-name set (strict superset of C: all opponent hand/library names,
   public or not — errors have no entitlement to any of them).

Decks: N copies of the pinned `rogshai_current.json` runtime deck (same deck
the UUID oracle uses), seed `10704L`, starting seat 0, life 40, up to 120
engine steps / 60 scanned frames per count (same budget as the UUID oracle).

## Oracle B — synthetic sentinel canaries (Python, no JVM)

Unmistakable test-only sentinels (never real cards, never in any deck):

- `WS224_CANARY_ALPHA_SENTINEL` (opponent seat 2)
- `WS224_CANARY_BETA_SENTINEL` (opponent seat 3)
- `WS224_CANARY_GAMMA_SENTINEL` (opponent seat 4)
- `WS224_CANARY_DELTA_SENTINEL` (opponent seat 5)

Planted ONLY in simulated hidden stores / adversarial redactor outputs that
production code must drop; never fed to pilots as heuristics; never written
to production decks. Assertions:

- `canonical_actor_view` drops opponent `hand` even when adversarially present;
  digests (`principal_observation_digest`, `public_state_digest`,
  `internal_checkpoint_digest`, `legal_set_digest`) never contain sentinels
  while still containing actor-public names (no global scrub).
- `option_fingerprint` generic fallback excludes UUID-like keys; target joins
  resolve via public projections only.
- `ExternalPilotDecisionPolicy._pilot_state` exposes no opponent names
  (`hand_names`/`battlefield_names` actor-only; opponents counts-only).
- `semantic_transcript` (prompt/labels) carries no sentinels for public-only
  transcripts; full-transcript scanner flags sentinel presence (detector works).
- Every `DivergenceClass` message template + all `FullGameProtocolError` /
  `FullGameConformanceError` structural messages contain no sentinel surface
  (attacker-inducible errors echo structure/seats/counts, never hidden names).
- Sealed WS218 tapes: structural scan (no UUIDs, no hand/mana/granted arrays
  in steps) + `selected_labels` entitlement note; manifest decklists classified
  EXPECTED_PRIVILEGED (reconstruction necessity, never pilot-served mid-game).

## Replay rule

Semantic fingerprints, checkpoints, event digests and replay failures must not
require raw opponent-private names in pilot-visible output. Privileged evidence
may hash private semantics (digests) but must not store unnecessary raw hidden
values. The WS218 tape contract is UNCHANGED (no repair required: scans prove
the contract already satisfies the rule; `selected_labels` carry only
actor-entitled chosen text).

## Historical rule

66 committed `primary.json` artifacts scanned READ-ONLY; findings classified
NO_PRIVATE_NAME_MATCH / EXPECTED_PRIVILEGED_ARTIFACT / POTENTIAL_LEAK_ARTIFACT /
CONFIRMED_PILOT_VISIBLE_LEAK / UNKNOWN. NOTHING rewritten. Privileged-but-
unsafe sharing gets quarantine/advisory disposition, never history falsification.

## No-behavior-credit rule

Zero actual-card behavior credit. All live answers neutral; no Rules semantic
touched in production files. `BEHAVIOR_CREDIT_CHANGE = 0`.

# WS222 COORDINATOR_GATE (informational — G01 needs NO waiver)

`AUTHORITY_GATE_REQUIRED = NO` for G01 closure: every canonical G01 authority
requirement is satisfied by sealed official evidence above, with no waiver.
`WAIVER_GRANTED = NO` (WS222 cannot grant one).

## Decisions owned by the Coordinator (not blocking WS222 completion)

1. **Bounded-scope acceptance.** WS222 closes G01 on the canonical required
   domain (29-card denominator + Commander/B&R + deck legality). If the project
   wants a broader pinned corpus (1385/1338/795 or whole-catalog), choose:
   (a) extend Model B per-card with the same tooling; (b) Model C (official
   per-card proof + versioned secondary bulk transport, authority/transport
   separated); or (c) a bounded policy exception with explicit scope/risks
   (Model D — Coordinator-only; WS222 documents it but does not approve it).
2. **Rollup integration.** Migrate `GATE_RESULTS.json` G01 FAIL → PASS (scoped)
   and fixture `authority_refs` v1 → v2 via the S2 rollup track; WS222 does not
   touch aggregates/manifests outside its namespace. Re-run
   `tests/qualification/test_ws17_qualification.py` hash manifests accordingly
   (note pre-existing F-CI-02 RED on `test_ws207_seed_binding.py`, out of
   WS222 scope).
3. **FULL107/retention interplay.** None: WS222 neither needs nor changes it.
4. **POST_LOCK_DRIFT.** If WS221 changed evidence enums mid-run, WS222 used
   only its source-lock vocabulary; report drift at integration.

## Proposed waiver scope (only if the Coordinator prefers bulk without capture)

Not requested. If ever invoked, the waiver would need explicit bounds (card
universe, expiry, refresh duty, risk acceptance for unpinned Oracle function)
— none granted here.

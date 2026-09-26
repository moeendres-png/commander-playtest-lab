# WS88 Pin Migration: `77d7646d` -> `cfc36f44`

Old runtime pin: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`
New integrated candidate: `cfc36f445f917f101fa2ed588770e043f53bc44c`
(new tree `e51ba998d35decff087b5bebfdc001e62e8d33e4`; 17 commits ahead, 0 behind;
remote branch `ws85/xmage-cr61412-future-state-hardening-20260913` head matches.)

## Changed (coherent production migration)

1. `config/rules_engines.json` — `primary_engine.commit` plus `source_archive`
   URL changed atomically; `known_stale_pointers` gained a WS88 addendum
   (Dockerfiles pin-free since WS-A1D; canonical xmage pin now `cfc36f…`).
2. `engine-bridge/.../XmageProvider.java` (`ENGINE_COMMIT`) and
   `.../Phase6DifferentialAdapter.java` (`BACKEND_VERSION`, `provider_commit`) —
   bridge rebuilt from `cfc36f`-resolved `org.mage:1.4.61` so the compiled
   self-report matches authority.
3. `engine-bridge/.../JsonlBridgeTest.java` — expected `engine_commit` updated.
4. `scripts/bootstrap_engine_linux.sh` / `bootstrap_engine_windows.ps1` —
   `COMMANDER_LAB_XMAGE_COMMIT` defaults updated; override mechanism unchanged.
5. `scripts/run_external_full_game_conformance.py` — `XMAGE_COMMIT` updated.
6. `tests/unit/test_xmage_full_game.py`,
   `test_xmage_compatibility_provider.py`, `test_ws_a1r_pin_authority.py`,
   `test_ws_a1d_docker_pin_authority.py` (`CANONICAL_XMAGE_PIN`) — expected
   constants updated; pin-agnostic negative-control logic untouched.
7. `.github/workflows/external-engine-integration.yml` (2 literals),
   `xmage-full-game-conformance.yml`, `exact-main-recovery.yml`
   (`xmage_pinned_commit` provenance literal) — CI inputs updated.
8. `docs/architecture/xmage-full-game-external-pilots.md`,
   `XMAGE_FULL_GAME_CLOSEOUT.md` — living pointers updated (no runtime effect).
9. `docs/RETENTION_AND_LIFECYCLE_POLICY.md` — WS88 resolution appended to the
   `PIN_DIVERGENCE_DOCKERFILES` gate entry; historical-fact sentences preserved.

## Docker pin-divergence gate (resolved, TD-WS88-01)

`docker/xmage/Dockerfile` carries zero SHA literals and refuses to build without
manifest-resolved args; it follows the repin automatically via
wrapper -> resolver -> build-arg -> provenance -> entrypoint-gate. Zero
Dockerfile/Compose changes. `phase85.py` stays frozen provenance.

## Deliberately unchanged (sealed historical evidence)

- Entire `qualification/ws80-xmage-callback-reachability/` package (its
  `verify.py:77` old-pin assertion fails closed on the new pin — correct
  sealed-frame behavior, superseded not patched).
- `qualification/WS17_SOURCE_LOCK.json`,
  `qualification/evidence/candidates/xmage.json` (sealed; no in-place edits).
- `docs/B4F_XMAGE_FIDELITY_CLOSEOUT.md`, `docs/xmage/BRIDGE_ARCHITECTURE_B0.md`,
  `docs/WS_A1D_PIN_CONSUMER_AUDIT.md`, Appendix G facts.
- Tracked `.foundry/WORKSTREAM_STATE.yaml` (stale WS-A1D-H4 artifact; TD-WS88-05).

No historical PASS is imported: every current claim rests on fresh `cfc36f` runs.
`HISTORICAL_EVIDENCE_REWRITTEN=NO`. `PRODUCTION_PIN_CONSUMERS_COHERENT=PASS`.

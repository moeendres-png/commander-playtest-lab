# WS213 ENGINE_REPIN_PROOF

Claim: the Lab production XMage dependency is EXACTLY WS212
`db134b9737e951367d65ef5806ad986319cc73ab`
(tree `4c7cae47f355ab41739b489af383ab54bf49e908`).
WS214 (`c044d40f6`) was never used as the pin.

1. Reference identity (DIRECTLY_VERIFIED, read-only roots):
   - `git rev-parse HEAD` in `ws212-xmage-rules-rng-seed-authority` =
     `db134b9737e951367d65ef5806ad986319cc73ab`, clean tree.
   - `git rev-parse HEAD^{tree}` = `4c7cae47f355ab41739b489af383ab54bf49e908`.
   - WS214 root HEAD = `c044d40f62015dc7936ef09e8460b2ae2cd60d2f` (untouched).
2. Lineage (DIRECTLY_VERIFIED): `cfc36f44` is the direct parent of WS206
   `97c2b27e5e`; then `b82226f36`, `a9b9a407`, WS211 `2b3f0f76`, WS212
   `db134b97`. Five-commit fast-forward; production delta is exactly
   `Game.java` (+`canConcede`), `GameImpl.java` (+`canConcede` impl,
   concede stale guard), `CombatGroup.java` (+160/−13 CR510 validation),
   plus tests/research (`git diff --stat cfc36f44..db134b97`: 51 files).
3. Materialization (DIRECTLY_VERIFIED): source copied (no `.git`) from the
   read-only root to `/tmp/opencode/mage-db134b97` with a SHA-256 manifest
   (93,093 files); copy integrity PASS on all three production files;
   `mvn -B -ntp -DskipTests clean install` → BUILD SUCCESS (39,231 files
   compiled, 40 modules, 0 errors; log in run dir). An earlier incremental
   build was discarded after stale-`target/` reuse was detected; the clean
   build is the authority.
4. Artifact correspondence (DIRECTLY_VERIFIED): freshly installed
   `org.mage:mage:1.4.61` (`~/.m2`, rebuilt 2026-09-14) contains
   `Game.canConcede`, the `WS54: game init requires an explicit Rules seed`
   gate, the concede stale guard, and both CombatGroup seams
   (`requestLegalTrampleBlockerAssignment`,
   `requestLegalFreeBlockerAssignment`); `mage-game-commanderfreeforall`
   and `mage-deck-constructed` refreshed in the same build.
5. Lab consumers (CODE_DERIVED + runtime): `config/rules_engines.json`
   commit/archive/note, `XmageProvider.ENGINE_COMMIT`,
   `Phase6DifferentialAdapter` backend/provider strings, bootstrap scripts,
   `run_external_full_game_conformance.py`, three workflows, pilots doc,
   `JsonlBridgeTest` live-commit assertion, both census `engine_commit`
   fields, and all Python pin tests now resolve `db134b97`
   (bridge battery + 75-test Python subset green post-change).

Machine companion: `ENGINE_REPIN_PROOF.json`.

# WS-A1D Pin Consumer Audit (Phase A) and Historical Evidence Impact (Phase B)

Status: audit record for `WS-A1D — Docker Pin Authority & Runtime Requalification`.
Source lock: `audit_base_sha dd3be6026515e40f4b18a6121058877f5cab5725`
(`origin/main` verified at the locked base; no drift at audit time).
Canonical authority: `config/rules_engines.json`
(xmage `77d7646da6958fdf8125ee7c8f4aabd130d21d4c` from
`https://github.com/moeendres-png/mage.git`;
forge `a37a865a53280dd8ad6fad3384d69611e8c5a42f`, `forge-2.0.14`;
protocol `2.0.0`; `NO_PROVIDER_READY` / selected `false` / provider `null`).

Immutable evidence record: exact SHAs below are provenance, not new authority.

## Phase A — consumer classification

### CURRENT_AUTHORITY

- `config/rules_engines.json` — sole machine-readable pin authority (pins,
  repositories, protocol `2.0.0`, provider truth, `authority_note`).

### LIVE_CONSUMER (authority-driven, correct)

- `scripts/run_external_b4f_provider_pin_validation.py` — reads the manifest;
  fail-closes when `XMAGE_COMMIT` env, live-provider `engine_commit`, or
  protocol differ from the pin.
- `scripts/run_external_b4f_capability_closeout.py` — reads the manifest;
  fail-closes on env/replay/live-provider/descriptor pin mismatch.
- `scripts/bootstrap_engine_linux.sh` (plus `bootstrap_engine_macos.sh`
  delegate and `bootstrap_engine_windows.ps1`) — direct-source builds already
  carry the canonical fork URL + commit (xmage) and canonical forge commit.
  NOTE: literals duplicate authority without mechanical enforcement (design
  input for Phase C; forge values are not env-overridable while xmage values
  are — minor asymmetry, out of Docker scope).
- `.github/workflows/external-engine-integration.yml` — checks out
  `moeendres-png/mage` at `XMAGE_COMMIT` (default canonical, 40-hex validated);
  literal default duplicates the pin without enforcement (noted, not changed:
  CI input surface, direct-source path, no Docker involvement).
- `.github/workflows/xmage-full-game-conformance.yml` — same checkout pattern
  at the canonical default (same note as above).
- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageProvider.java` —
  bridge self-identity (`ENGINE_COMMIT` canonical, `PROTOCOL_VERSION 2.0.0`);
  compiled into the bridge built from pinned source. Self-report, not authority.
- `src/commander_lab/models/engine_runtime.py` — `ENGINE_PROTOCOL_VERSION =
  "2.0.0"` code default, matching the manifest.
- `src/commander_lab/engine/rules/bridge.py`,
  `src/commander_lab/engine/process_manager.py`,
  `src/commander_lab/engine/rules/full_game.py`,
  `src/commander_lab/engine/rules/protocol.py`,
  `scripts/tactical_rules_bridge.py` — consume the `ENGINE_PROTOCOL_VERSION`
  constant and hard-fail handshake mismatches. Correct.
- `src/commander_lab/technical_truth.py` — reads the manifest for truth
  payloads (`commit`, `decision_source`).
- `.env.example` — `ENGINE_PROTOCOL_VERSION=2.0.0`, matching the manifest.
- `tests/contract/test_phase1213_provider_surface.py`,
  `tests/contract/test_phase85_protocol.py`,
  `tests/unit/test_external_engine_foundation.py` — pin protocol `2.0.0`
  behaviorally. TEST_FIXTURE, correct.
- `tests/unit/test_xmage_compatibility_provider.py`,
  `tests/unit/test_xmage_full_game.py`,
  `scripts/run_external_full_game_conformance.py` — canonical `XMAGE_COMMIT`
  literal as expected-value fixture. TEST_FIXTURE, correct.
- `tests/unit/test_ws_a1r_pin_authority.py` — stale-SHA negative controls plus
  manifest-truth assertions. TEST_FIXTURE, correct; stale SHAs remain stale
  after WS-A1D.

### STALE_LIVE_POINTER (WS-A1D repair surface)

- `docker/xmage/Dockerfile` — default `06d166b098ad36b277edef01116472203d5a047e`
  cloned from upstream `https://github.com/magefree/mage.git`. Wrong commit
  AND wrong repository versus manifest authority.
- `docker/forge/Dockerfile` — default
  `852066bf4f761b302ed17cb011999d8a8fe08ad6` (`forge-2.0.13`) versus canonical
  `a37a865a…` (`forge-2.0.14`).
- `docker-compose.engine.yml` — passes no `ENGINE_COMMIT` build args (so
  defaults win) and sets `ENGINE_PROTOCOL_VERSION: "1.0.0"` for both providers
  versus canonical `2.0.0`.
- `.devcontainer/devcontainer.json` — builds `../docker/xmage/Dockerfile` and
  sets `ENGINE_PROTOCOL_VERSION: "1.0.0"`. Second live protocol consumer found
  during audit (not named in the contract's minimum list).

### Competing restatement (doc hygiene surface)

- `integrations/xmage/README.md` — restates the canonical commit literal in
  prose (lines 8-11) while also citing the manifest as capability truth (line
  91). Per the WS-A1R documentation rule (human-readable pin statements must
  cite the manifest and must not restate commits), the literal is a competing
  pin statement. `integrations/forge/README.md` already conforms (defers, no
  duplicate). Minimal fix in scope for Phase F/G.
- `docs/engine_setup.md` — cites the manifest (WS-A1R test enforced); Docker
  section documents the Compose path; states Dockerfiles were
  prepared-but-not-executed in Phase 8.5.

### HISTORICAL_PROVENANCE / GENERATED_OUTPUT (do not touch)

- `src/commander_lab/engine/rules/phase85.py` (`installed_or_pinned` template
  literals `06d166b0…` / `852066bf…`, `executed: false`) — historical
  Phase-8.5 preparation template. Still exercised by
  `tests/integration/test_phase85_validation.py`,
  `tests/contract/test_phase86_phase85_claims.py`, and
  `.github/workflows/windows-runtime.yml`, but its output is a provenance
  record of what Phase 8.5 prepared, marked not-executed. Disposition:
  HISTORICAL_PROVENANCE template; mechanical replacement would rewrite
  provenance. Left untouched.
- `docs/J_P3_*` (contract, runbooks, spike reports, raw-evidence manifests,
  provider decision/matrix), `docs/archive/legacy_phase_artifacts/PHASE85_*`,
  `artifacts/**`, `qualification/**`, `docs/B4F_XMAGE_FIDELITY_CLOSEOUT.md`,
  `XMAGE_FULL_GAME_CLOSEOUT.md`, `docs/NEXT_STEP_HANDOFF_*`,
  `docs/xmage/BRIDGE_ARCHITECTURE_B0.md`,
  `docs/architecture/xmage-full-game-external-pilots.md` — immutable historical
  records; old SHAs stay as provenance.

### Live gate ledger (update on resolution)

- `docs/RETENTION_AND_LIFECYCLE_POLICY.md` Appendix G, lines 161-168 —
  records `PIN_DIVERGENCE_DOCKERFILES` facts (stale defaults, no build-arg
  override). Facts change on WS-A1D resolution; the ledger entry is updated in
  Phase F/J to record the resolution, not deleted.

### No UNKNOWN remains

Every material occurrence of the four SHAs, `ENGINE_COMMIT`,
`ENGINE_PROTOCOL_VERSION`, Compose references, and Dockerfile references found
by global search is classified above. No workflow under `.github/workflows/`
references Docker at all (verified by search).

## Phase B — historical evidence impact

- Phase 8.5 family (`artifacts/engine_setup/phase85_*`, `PHASE85_REPORT`,
  bootstrap-files tests): HISTORICAL_ONLY. `docs/engine_setup.md` records
  Dockerfiles prepared-but-not-executed (no Docker in the Phase-8.5 build
  container); validation output marks scenarios `manual_review_required` and
  pinned entries `executed: false`. The re-pin cannot invalidate evidence that
  never consumed the Docker path.
- B3/B4/B4F regression chain, External XMage Integration, full-game
  conformance: UNAFFECTED. All consume direct vendor-source builds
  (`vendor/engine-source/xmage` from the fork at the canonical commit via CI
  checkout or bootstrap scripts) plus the bridge self-report check; no Docker
  involvement; no container identity recorded in artifacts (verified by
  search: no `container`/`image_id` keys in engine-setup artifacts).
- Forge spike evidence (`PARTIAL`): UNAFFECTED. Runbooks show no Docker
  involvement; status is preserved as-is.
- Release artifacts workflow: UNAFFECTED. Reads `config/rules_engines.json`
  directly as the truth source; no Docker-default consumption.
- `test_phase85_bootstrap_files.py` (existence/parse checks): UNAFFECTED by
  content changes provided all listed files remain and shell stays parseable.
- `test_ws_a1r_pin_authority.py`: UNAFFECTED. The manifest is untouched and
  the stale SHAs remain stale; assertions keep passing.
- No qualification evidence known to have executed the stale Docker path was
  found; therefore no blanket invalidation. Requalification is targeted at the
  Docker path itself (Phase I), not at re-running B3/B4 semantics.

## Phases C–E — adjudications (appended during implementation)

### Phase D — XMage repository adjudication

- Canonical commit `77d7646d…` was directly observed in the manifest-authoritative
  fork `moeendres-png/mage` (commit page: "feat: implement Ashling the Limitless",
  parent `b1ef0dc`, forked from `magefree/mage`; fork-local card implementation
  plus regression test). The Docker path therefore clones the fork.
- The same SHA also resolves under the `magefree/mage` path in the web UI
  (shared object store), so upstream unreachability is NOT claimed; the fork is
  required by authority and by fork-only compatibility content regardless.
- Forge canonical commit `a37a865a…` was directly observed in `Card-Forge/forge`
  ("[maven-release-plugin] prepare release forge-2.0.14"), matching the Dockerfile's
  existing clone source; only the commit default was stale there.

### Phase E — protocol drift adjudication: SAME-SCOPE CORRECTION

- `ENGINE_PROTOCOL_VERSION` flows from the environment (default `2.0.0`) into
  `EngineRuntimeConfig.protocol_version`, into `JsonLineBridgeClient`, which stamps
  every request and hard-fails on any response mismatch
  (`src/commander_lab/engine/rules/bridge.py`). Both real bridges speak `2.0.0`
  (`XmageProvider.PROTOCOL_VERSION`, `scripts/tactical_rules_bridge.py`).
- Compose's and devcontainer's `"1.0.0"` therefore described no implemented
  dialect: any container started with it would fail the handshake against a real
  `2.0.0` bridge. No adapter, schema or fixture migration is required; nothing in
  the repository speaks `1.0.0` as a bridge protocol. Disposition: correct both
  live values to `2.0.0` with regression tests enforcing equality with the manifest.
  (Unrelated `1.0.0` schema/report versions elsewhere are not bridge protocol.)

### Phase C — pin-authority design (as implemented)

- `scripts/docker_resolve_engine_pin.py`: manifest-aware resolver (stdlib only).
  Maps `xmage → primary_engine`, `forge → secondary_engine`; validates https
  repository shape, provider-token cross-wire guard, 40-hex commit, non-empty
  release and protocol. Any failure exits non-zero with a stderr diagnostic.
- `scripts/docker_build_engine.sh <xmage|forge> [compose args…]`: the single
  supported build path; exports resolver output as provider-prefixed variables
  and execs `docker compose --profile <provider>`.
- Dockerfiles declare `ARG ENGINE_REPOSITORY / ENGINE_COMMIT /
  ENGINE_PROTOCOL_VERSION` with no defaults; re-validate shape/commit/provider
  match (including per-file cross-provider refusal); verify checked-out HEAD;
  write `/opt/engine-provenance.json`.
- `docker-compose.engine.yml` interpolates wrapper-exported variables with `:?`
  (fail closed without the wrapper); runtime `ENGINE_PROTOCOL_VERSION` is the
  literal `2.0.0`, mechanically enforced against the manifest by tests (same
  precedent as `.env.example`). `.devcontainer/devcontainer.json` likewise carries
  literal `2.0.0` under test enforcement (no interpolation path exists there).
- `scripts/verify_container_provenance.py` + entrypoint gate: a started container
  with both a provenance record and a mounted manifest refuses a stale or
  cross-wired image (exit 3). Records without authority, or authority without a
  record, warn and proceed; the bridge handshake still applies.
- No second volatile pin file was created. Literal `2.0.0` copies in Compose /
  devcontainer / `.env.example` are runtime-contract values enforced by tests,
  justified per surface above; no commit SHA is duplicated anywhere outside the
  manifest, provenance records and immutable history.

## Phase H/I status pointer

- Docker client is absent on the WS-A1D execution host: no image was constructed
  there (NOT_RUN, not PASS). Dockerfile guard logic was executed directly under
  `bash` (missing/stale-shape/cross-wire/canonical matrices) and the RUN bodies
  pass `bash -n`; Compose YAML and devcontainer/manifest JSON parse.
- Targeted requalification executed: new WS-A1D suite plus pin, technical-truth,
  bootstrap, protocol-contract, foundation, compatibility-provider and Phase-8.5
  suites green. B3/B4/external-engine suites are NOT_RUN locally (no vendor
  source or bridge build present) and were adjudicated UNAFFECTED; they remain
  owned by CI on the direct-source path.

# Identity Reconciliation — FINAL-PROVIDER-CDQ-20260927 (Gate A)

Gate A passes only if every source identity below is bound separately with no
ambiguity. No identities are collapsed. Stale historical pointers are
preserved as provenance, never rewritten.

Classification legend:

- CURRENT — the identity this workstream executes against / freezes
- HISTORICAL — superseded pointer retained for provenance only
- EVIDENCE_ONLY — tests/evidence tip; never a Rules-Core version
- ENGINE_CODE — the engine bytes whose Rules semantics are judged
- LAB_INTEGRATION — Lab-side runtime/evidence binding of an engine
- PRE_SELECTION_MANIFEST — the checked-in manifest pointer, frozen here

## 1. Commander-Lab execution source lock — CURRENT / LAB_INTEGRATION

- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `wsr21/final-provider-cdq-20260927` (sole-writer worktree:
  `/home/moeen/code/wsr21-final-provider-cdq`; verified clean + up-to-date
  with `origin/wsr21/final-provider-cdq-20260927`)
- HEAD: `58e8fca430651207a87a8f3e9f41d8c6527dd4cd`
- Tree: `4cf4f3d23da9b6a7bb010178b6efcc2b2c853ba2`
- Role: the ONLY mutation surface of this workstream (comparison harnesses,
  qualification tests, evidence normalization, packets, docs, observation-only
  adapters). PR #253 publisher hardening is included (launch gate PASS:
  CI `36310680744`, Production Qualification `36310680885`, Exact Main
  Recovery `36310680895`, Windows Runtime Hygiene `36310680966`, Release
  Artifacts `36310680812`).
- This workstream's own evidence lineage is recorded per-milestone in this
  directory; local checkpoint commits only (no push/merge/rebase without the
  configured approval gate).

## 2. Immutable FULL107 denominator — CURRENT (frozen)

- Frozen source: `5a2e4f462fd45bba25f2271153212aab9faf09f5`
  (`origin/ws47/successor-contract-v1.0.5-freeze`; locally resolves in Lab
  clone; 107 items; bytes immutable)
- Materialization: `commander-lab.semantic-fixture-materialization/1.0.5`
  (135 records; denominator is the 107-item subset with
  `denominator_decreased_to_bypass_blocker: false`)
- Machine sources: `qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json`,
  `qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json`,
  `qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json` (135-item manifest)
- No alteration, deletion, split, combination, or threshold redefinition was
  performed or is permitted.

## 3. Historical FULL107 mapping provenance — HISTORICAL (preserved)

- `docs/workstream_full107_definition_20260921/FULL107_IDENTITY_BINDING.json`:
  binds frozen source `5a2e4f46…` to lineage base
  `069762bc074efa78153931ba637f392766d2cb44` and to then-current engine
  pointers `db134b9737e951367d65ef5806ad986319cc73ab` (XMage, HISTORICAL —
  superseded by the cumulative M1–M4 candidate below) and `a37a865a…`
  (Forge Rules-Core, still the manifest pointer — see §8).
- `docs/workstream_full107_definition_20260921/FULL107_MAPPING.json`:
  CURRENT mapping content (107 rows: DIRECT 15 / SUPPORTING 13 /
  NOT_RUN_BLOCKED 25 / UNKNOWN 54), already including the three reconciled
  residual promotions (SPLIT, PARTNER-DMG, START-3). Its per-row `pointer` /
  `reason` fields are provenance for Gate B, re-adjudicated row-by-row in
  `XMAGE_FULL107_REFRESH.json`.
- `docs/workstream_full107_fixture_identity_20260922/FIXTURE_IDENTITY_REGISTER.json`:
  20 adjudicated fixture→verdict bindings (DIRECT requires EXACT), enforced by
  `tests/unit/test_full107_direct_correspondence.py` (10/10 guard).
- Old per-fixture UNKNOWN / NOT_RUN_BLOCKED values are NOT treated as current
  truth where later L1→L7 evidence exactly satisfies the obligation — but no
  promotion is granted without exact matching (Gate B).

## 4. XMage engine candidate pin — ENGINE_CODE (contract-claimed)

- Repository: `moeendres-png/mage`
- Pin: `b19596980f2734496ea1896504253e1bdd2756dd` — cumulative qualified
  M1–M4 residual candidate (RG-02 commander-damage restore, RG-07 exact-N
  target offering, RG-08 replacement timing, RG-06A ordered-library/face-down
  state-load remediation).
- Status: VERIFIED via read-only reference `mage-rg-candidate-build` (resolves
  to `RG-06A: persist hidden-state restore qualification handoff`).
  Corroborated by `config/rules_engines.json` (`primary_engine.commit`), the
  L1 handoff (single-candidate consumption + requalification), and the
  cumulative campaign handoff (pin held constant across L1→L7).
- Mage master is explicitly NOT the candidate (materially diverged, not
  qualified for this decision). No substitution, rebase, repin, or migration
  performed.

## 5. XMage reconciled Lab runtime authority — LAB_INTEGRATION (verified)

- Commit: `593326713faeddb8c90df2fdc5e5bafbe1fccf1b`
  (`L7: prevalidation atomicity battery`; locally resolves in Lab clone).
- Content: final L6 test contract + L7 implementation + FULL107
  requalification + prevalidation atomicity battery; no production Rules
  change in reconciliation. Merge `f133fe9d96c5e61842c866f3338de06a764a97b6`
  (PR #249) introduced zero content delta (merge tree byte-identical to
  qualified PR-head tree).
- Evidence (all terminal SUCCESS on the exact authority head):
  CI `36252815364`, External XMage Integration `36252815268`, XMage Full Game
  Conformance `36252815281`, XMage Real 4P Technical Smoke `36252815303`,
  H4 Docker Materialization `36252815304`, Production Qualification
  `36252815322`. Results: Python 1548/7, mypy 0/261, bridge 298/0/0/1 skip,
  4P seeded semantic replay 4476 decisions match, bounded 2P/3P/5P/6P PASS, 7P
  FAIL_CLOSED.
- Historical L-layer heads (`cc9bd438`, `1efab77b`, `ab4c0c25`, `8dd283fe`,
  `4117aff0`, `a7de8603`) and their workflow runs are supporting/provenance
  only; they do not qualify the reconciled semantics. Docs-only successors
  (`20bf2cd2`, `5a5a5523`) are documentation heads, not runtime authorities.
- Distinction preserved: engine candidate pin (§4) ≠ Lab runtime authority
  (§5) ≠ historical FULL107 mapping pointers (§3).

## 6. Forge production-code candidate — ENGINE_CODE (contract-claimed)

- Repository: `moeendres-png/forge`
- Commit: `ef958ee91ac6c9ce0152189f2654bf6e05abf273`
- Tree: `fc3387bf37aab19d780b2939a235309ed32b0492`
- Status: VERIFIED via read-only reference worktree
  `/home/moeen/code/ws-forge-full107-cdq-20260926` (`git show` resolves with
  byte-exact tree `fc3387bf…`, matching the WSR20 audit base). No
  production-code edit, merge, repin, or Rules-semantic change performed here.

## 7. Forge WSR20 evidence tip — EVIDENCE_ONLY (contract-claimed, packet absent locally)

- Commit: `18bba95a4528f6ab5910633f1f87f603b8c4ddf8`
- Tree: `56209bb72b84fc845ad00433b4471e723ecc8a01`
- Role: tests/evidence ONLY. Production-code delta WSR20↔§6 is contract-
  recorded as NONE. Must NOT be merged into Forge master and must NOT be
  treated as a new Rules-Core version.
- Contract-claimed contents (`forge-protocol2-bridge/wsr20-full107/`):
  `FULL107_FORGE_MAPPING.json` (claimed disposition DIRECTLY_VERIFIED 84 /
  TECHNICALLY_CONFORMANT 17 / UNKNOWN 3 / NOT_RUN_BLOCKED 3 / FAIL 0),
  `COMMON_FIXTURE_SUCCESSOR_PACKET.json` (101 common fixtures),
  `EXECUTION_RESULTS.json`, `HIDDEN_INFO_RESULTS.json`, `RNG_REPLAY_RESULTS.json`,
  `MULTIPLAYER_RESULTS.json`, `VALIDATION.md`, `FINAL_HANDOFF.md`.
- Local truth: the packet is VENDORED into this workstream as
  `docs/final_provider_adjudication_20260927/wsr20-ingest/` (8 byte copies
  with provenance: source tip, sizes, hashes). Forge mapping counts verified
  from ingested bytes (84 / 17 / 3 / 3, FAIL 0, 107 rows over exactly the Lab
  denominator ids; successor packet 101 fixtures). Gate C is rebuilt from the
  actual successor packet; every prior UNKNOWN_PENDING verdict is
  re-adjudicated per row (prior verdict preserved in
  `packet_verdict_superseded`).

## 8. Lab Forge pre-selection manifest — PRE_SELECTION_MANIFEST (frozen here)

- File: `config/rules_engines.json` (sole machine-readable authority for
  current engine pins; intentionally NOT repinned in this workstream —
  repinning belongs to the later Freeze decision).
- Records older Forge pre-selection identities: Rules-Core
  `a37a865a53280dd8ad6fad3384d69611e8c5a42f`, historical bridge
  materialization `4753bb7c72ea60d653121e0bab989077b4009f9c`.
- These manifest pointers are NOT the Forge production candidate (§6) and NOT
  the WSR20 evidence tip (§7). The manifest's own authority note (§116,
  Appendix G PIN_DIVERGENCE) already marks docker/phase85 pointers as stale
  provenance; since WS-A1D both Dockerfiles resolve identity from this
  manifest at build time (pin-free by design).

## Gate A verdict

PASS: all 8 identities bound separately with explicit CURRENT / HISTORICAL /
EVIDENCE_ONLY / ENGINE_CODE / LAB_INTEGRATION / PRE_SELECTION_MANIFEST
classification; Lab-side facts verified in-clone; Forge/Mage bytes verified
via Coordinator-authorized read-only references; WSR20 packet vendored with
provenance and verified counts. No source identity is ambiguous. Seam
blocking assessments (§8 of the continuation: 5 still-unknown, MULL-2
bounded-non-blocking) are recorded in `COMMON_FIXTURE_NORMALIZATION.json`
(`excluded_seams`), not papered over.

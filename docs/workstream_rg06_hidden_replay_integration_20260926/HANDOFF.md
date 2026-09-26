# L7 — RG-06 Hidden-State and Replay Integration

## Terminal Handoff

**Disposition:** COMPLETE / PASS

**Branch:** `sol/rg06-hidden-replay-integration-20260924`

**Exact predecessor L6:** `060869e5ee60b4a504c317f24786b715ddd66c0d`

**Runtime-qualified L7 head:** `a7de8603535bb5d3656df576ef5c8f8190f144f1`

**Mage pin:** `b19596980f2734496ea1896504253e1bdd2756dd`

**Draft PR:** #248, stacked on `sol/rg05-causal-elimination-20260924`

**WORKTREE:** NOT_AVAILABLE_IN_CONNECTOR_EXECUTION

**ARCHITECTURE_FREEZE:** NOT CLAIMED

**PRODUCTION_PROVIDER:** NOT SELECTED

## Objective / Work Completed

Integrated the already qualified Mage RG-06A hidden-state load APIs into a bounded, lossless Commander-Lab surface and hardened replay/privacy semantics without adding a second hidden-information permission model.

- Added `XmageHiddenStateRestoration`.
- Exact library restoration accepts only a complete top-to-bottom identity sequence covering the entire live native library.
- Identity sequences are deterministically bound to the existing native card UUID multiset; incomplete/foreign/mismatched requests fail before mutation.
- Face-down restoration requires an explicit semantic object id plus explicit native `FaceDownType`.
- Old frozen records containing only partial library positions or `face_down=true` with no native subtype remain fail closed and are not silently upgraded.
- Mutation delegates only to Mage:
  - `Library.restoreOrderForGameLoad(...)`
  - `BecomesFaceDownCreatureEffect.restoreFaceDownStateForGameLoad(...)`
- Lab permits at most one face-down object in one atomic hidden-state request so a later incompatible hidden object cannot leave a partially mutated request.
- The principal-scoped redactor stores only restored hidden identity metadata; authorization is re-derived dynamically from the live native controller relationship.
- Public projections never include restored private face-down identity.
- Decision requests now carry separate:
  - `public_state_reference = public-view:<hash>`
  - `private_actor_state_reference = actor-view:<hash>`
- Exportable transcript events retain the public state reference but omit the private actor-state reference, preventing transcript hashes from becoming hidden-state oracles.
- A historical two-argument internal `publicPermanent(Permanent, Game)` redactor seam was restored as a public-only overload for existing WS92 reflection qualification; it delegates with no viewer and cannot reveal `private_identity`.

## Reuse Classification

### Ordered library

`ENGINE_NATIVE_REUSE / WRAP`.

L7 does not reorder a Java collection directly. It validates a lossless Lab request and calls the Mage RG-06A native library load seam.

### Face-down state

`ENGINE_NATIVE_REUSE / WRAP`.

L7 does not model Morph/Manifest/Cloak/Disguise itself. It binds one requested live permanent to an explicit native face-down type and delegates to Mage RG-06A.

### Hidden-information authorization

`REUSE_AS_IS + bounded metadata registration`.

The existing `XmageFullGameStateRedactor` remains the sole principal-scoped observation boundary. The added map stores restored identity metadata only; it does not grant permission. Permission remains dynamically determined from native live controller state.

### Replay/state references

`EXTRACT_AND_GENERALIZE`.

Existing state hashing is retained, but public and actor-private hashes are now separated so the exportable transcript does not expose a private-view oracle.

## Changed Files vs L6

Exact compare `060869e5ee60b4a504c317f24786b715ddd66c0d..a7de8603535bb5d3656df576ef5c8f8190f144f1`:

- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameDecisionController.java`
- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameStateRedactor.java`
- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageHiddenStateRestoration.java`
- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java`
- `engine-bridge/src/test/java/org/commanderlab/xmage/XmageHiddenReplayIntegrationTest.java`

L7 runtime head is 7 commits ahead / 0 behind exact L6 predecessor.

## Runtime Qualification

All five required workflows on exact runtime head
`a7de8603535bb5d3656df576ef5c8f8190f144f1` completed SUCCESS:

- CI `36244387854`
- External XMage Integration `36244387873`
- XMage Full Game Conformance `36244387786`
- XMage Real 4P Technical Smoke `36244387825`
- H4 Docker Materialization `36244387833`

### CI

- Python: **1548 passed, 7 skipped, 1 warning**
- mypy: **no issues in 261 source files**
- security job: PASS
- CI artifact: `10906583687`
- security artifact: `10907106377`

### External XMage Integration

Bridge Maven suite:

- **291 tests**
- **0 failures**
- **0 errors**
- **1 intentional skip**
- `BUILD SUCCESS`

Key cumulative classes on the same exact source:

- `XmageHiddenReplayIntegrationTest`: **8/8 PASS**
- `Ws92D1D2D3ProjectionTest`: **3/3 PASS**
- `XmageCausalEliminationReconstructionTest`: **18/18 PASS**
- `XmageControlDivergenceReconstructionTest`: **7/7 PASS**
- `XmageCausalStackMechanicsTest`: **7/7 PASS**
- `XmageCausalStackReconstructionTest`: **5/5 PASS**
- `XmageTemporalProgressionDriverTest`: **7/7 PASS**
- `XmageTemporalAdvancedProgressionTest`: **6/6 PASS**
- `XmageCommanderDamageRestorationTest`: **8/8 PASS**
- `XmageNativeStateRestorationTest`: **20/20 PASS**

Provider-bound Phase-6 differential battery: 2 passed / 1 configured-backend skip.

Artifacts:
- B4-F: `10907350659`
- B4-D: `10907415425`

### Full Game Conformance

- bridge Maven suite 291/0/0/1: PASS
- seeded 4P game-over/replay: PASS
- decisions: **4476**
- `semantic_replay_match=true`
- `raw_result_match=false` (not claimed)
- bounded 2P: PASS, 25 decisions
- bounded 3P: PASS, 25 decisions
- bounded 5P: PASS, 45 decisions
- bounded 6P: PASS, 55 decisions
- 7P: **FAIL_CLOSED** at the supported-cardinality table
- full-game artifact: `10907370530`

### Real 4P Technical Smoke

PASS on the same L7 runtime source.

Artifact: `10906378618`.

### H4 Docker Materialization

- preflight: PASS
- Forge lane: PASS
- XMage direct-source build/bridge verification/image/provenance/handshake/negative controls: PASS
- XMage artifact: `10906534059`
- Forge artifact: `10907027320`

H4 success remains technical materialization evidence only and does not select a production provider.

## L7 Semantic / Privacy Gates

PASS:

1. exact complete library order restoration;
2. incomplete library order fails before mutation;
3. native face-down rejection cannot partially apply a prepared library reorder;
4. restored face-down private identity is visible only to the currently entitled controller;
5. opponent principal view does not expose restored hidden identity;
6. global public view does not expose restored hidden identity;
7. public replay-state hash is unchanged by hidden library order changes that are not public;
8. non-entitled opponent actor-state hash is unchanged by the other player's hidden library reorder;
9. exportable transcript contains no `private_actor_state_reference`;
10. public transcript does not contain the restored hidden card identity;
11. old partial-library frozen records remain fail closed;
12. old untyped face-down frozen records remain fail closed;
13. explicit hidden-state JSON requires a lossless face-down type;
14. fresh same-seed sessions reproduce the same public semantic hidden-state result without public hidden-card hashes;
15. historical public-board reflection contract remains public-only after the compatibility overload.

## Initial Failure / Remediation

The first L7 runtime attempt compiled general CI and executed all 8 new L7 tests successfully, but all XMage-specific integration lanes failed because a retained WS92 regression accesses the private helper
`publicPermanent(Permanent, Game)` via reflection.

L7 had internally extended that helper to include a viewer parameter.

Remediation:

- restored the historical two-argument internal seam;
- it delegates to the new three-argument implementation with `viewer=null`;
- therefore it remains strictly public-only and cannot return `private_identity`;
- no privacy rule or observation permission was weakened.

The second exact-head run passed all five workflows.

## Evidence Classification

- branch ancestry/source lock: DIRECTLY_VERIFIED
- exact workflow/runtime evidence: DIRECTLY_VERIFIED
- hidden-state load behavior: DIRECTLY_VERIFIED + TECHNICALLY_CONFORMANT
- principal/public projection separation: DIRECTLY_VERIFIED
- transcript private-hash removal: DIRECTLY_VERIFIED + CODE_DERIVED
- delegation to Mage state-load APIs/no second Rules Core: CODE_DERIVED + runtime tests
- old ambiguous frozen records fail closed: DIRECTLY_VERIFIED
- same-seed public semantic replay: DIRECTLY_VERIFIED

## PASS / FAIL / UNKNOWN

### PASS

`RG06_HIDDEN_STATE_REPLAY_INTEGRATION = PASS`

`RESIDUAL_L1_TO_L7_CUMULATIVE_RUNTIME = PASS`

### FAIL

None in bounded L7 scope.

### UNKNOWN / intentionally unsupported

- Multiple face-down restorations in one atomic Lab hidden-state request remain unsupported; request fails closed.
- Mixed Manifest/Cloak plus underlying Morph/Megamorph/Disguise remains the pre-existing native Mage bounded gap documented by RG-06A; L7 does not override it.
- Historical frozen records that do not losslessly encode full library order or native face-down subtype remain unsupported.
- L6 poison-counter and empty-library causal reconstruction remain UNKNOWN and are not promoted by L7.

## Remaining Blockers

None for the commissioned L1→L7 residual closure campaign.

The remaining UNKNOWN items above are explicit future capability scopes, not hidden blockers to the bounded campaign.

## Outputs

- Draft stacked PR #248
- `XmageHiddenStateRestoration`
- hardened principal/public projection and replay-reference separation
- L7 runtime/adversarial regression suite
- this terminal handoff

## Dependencies Unblocked

- The cumulative Commander-Lab residual lineage L1→L7 is now source-bound and runtime-qualified.
- Coordinator may perform final stacked-candidate adjudication.
- No stacked PR in this L1→L7 campaign is authorized for direct merge to `main` by this workstream.

## Exact Next Action

Coordinator reads the terminal L7 branch head containing this handoff, records it as the cumulative residual-closure candidate, and adjudicates integration strategy for the stacked PR chain. Any integration must preserve linear ancestry and rerun the appropriate main/post-merge gates.

Do not claim Architecture Freeze or Production Provider selection from this campaign alone.

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`

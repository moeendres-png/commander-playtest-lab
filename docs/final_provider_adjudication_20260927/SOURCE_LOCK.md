# Source Lock — FINAL-PROVIDER-CDQ-20260927

Verified at session start 2026-09-27 in worktree
`/home/moeen/code/wsr21-final-provider-cdq`.

## Commander-Lab (locally verified)

| Fact | Value | How verified |
|---|---|---|
| Branch | `wsr21/final-provider-cdq-20260927` | `git branch --show-current` + `git status` (`## wsr21/final-provider-cdq-20260927...origin/wsr21/final-provider-cdq-20260927`, clean) |
| HEAD | `58e8fca430651207a87a8f3e9f41d8c6527dd4cd` | `git rev-parse HEAD`; `git log --oneline -3` top = `58e8fca4 Merge PR #253: restore effective push-target hardening` |
| Tree | `4cf4f3d23da9b6a7bb010178b6efcc2b2c853ba2` | `git rev-parse HEAD^{tree}` — byte-matches dispatch tree |
| Dispatch HEAD match | YES | HEAD equals canonical main `58e8fca4…` |
| Dispatch tree match | YES | tree equals `4cf4f3d2…` |
| Remote branch position | `origin/wsr21/final-provider-cdq-20260927 == 58e8fca4` | `git status` reports up-to-date with origin; `git for-each-ref` lists `wsr21/final-provider-cdq-20260927 58e8fca4` and `origin/wsr21/final-provider-cdq-20260927 58e8fca4` |
| Working tree | clean | `git status`: nothing to commit |

No SOURCE_DRIFT: branch, HEAD, tree, and remote position all match dispatch.
No rebase of the evidence contract performed.

## Launch gate (remotely verified, exact main)

All on exact HEAD `58e8fca4`, terminal SUCCESS (via `gh run view`):

| Workflow | Run ID | Conclusion |
|---|---|---|
| CI | `36310680744` | success |
| Production Qualification | `36310680885` | success |
| Exact Main Recovery | `36310680895` | success |
| Windows Runtime Hygiene | `36310680966` | success |
| Release Artifacts | `36310680812` | success |

Launch gate: PASS.

## FULL107 denominator (locally verified)

| Fact | Value | How verified |
|---|---|---|
| Frozen source commit | `5a2e4f462fd45bba25f2271153212aab9faf09f5` | `git show --no-patch` resolves in Lab clone (`ws47: persist terminal self-contained handoff`); cited by `FULL107_IDENTITY_BINDING.json`, `FULL107_MAPPING.json`, generator, `SOURCE_LOCK.json` |
| Denominator count | 107 | `qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json` (`provider_denominator_count: 107`, 107 fixture_ids, `denominator_decreased_to_bypass_blocker: false`) |
| Materialization | `commander-lab.semantic-fixture-materialization/1.0.5`, 135 records | `SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json` (`record_count: 135`); `COMMON_FIXTURE_MANIFEST_v1.json` (135 fixtures) |
| Current mapping | 107 entries: DIRECT 15 / SUPPORTING 13 / NOT_RUN_BLOCKED 25 / UNKNOWN 54 | `docs/workstream_full107_definition_20260921/FULL107_MAPPING.json` (parsed locally) |
| Fixture identity register | 20 adjudicated verdicts, DIRECT-requires-EXACT rule | `docs/workstream_full107_fixture_identity_20260922/FIXTURE_IDENTITY_REGISTER.json` + `tests/unit/test_full107_direct_correspondence.py` |

Frozen bytes treated as immutable. No fixture meaning altered.

## XMage identities (mixed verification)

| Identity | Value | Verification |
|---|---|---|
| Engine candidate pin | `b19596980f2734496ea1896504253e1bdd2756dd` (moeendres-png/mage) | CONTRACT_CLAIMED. Not locally re-verified: no Mage reference root declared for this run; Mage master divergence warning from contract honored (no substitution, no repin, no migration). Corroborated in-repo by `config/rules_engines.json` (`primary_engine.commit`), residual campaign handoff (Mage pin throughout), and reconciled runtime docs. |
| Reconciled Lab runtime authority | `593326713faeddb8c90df2fdc5e5bafbe1fccf1b` | LOCALLY_VERIFIED: `git show --no-patch` resolves (`L7: prevalidation atomicity battery`); recorded 3× in `docs/residual_closure_campaign_20260926/HANDOFF.md`; 6 exact-head workflows SUCCESS (CI `36252815364`, External `36252815268`, Conformance `36252815281`, Smoke `36252815303`, H4 `36252815304`, Production Qualification `36252815322`); post-merge push on `f133fe9d…` all SUCCESS. |

## Forge identities (contract-claimed, not locally re-verified)

| Identity | Value | Verification |
|---|---|---|
| Production-code candidate | `ef958ee91ac6c9ce0152189f2654bf6e05abf273` (moeendres-png/forge), tree `fc3387bf37aab19d780b2939a235309ed32b0492` | CONTRACT_CLAIMED. No Forge reference root declared; not locally re-verified here. No merge, no repin, no Rules-semantic edit performed. |
| WSR20 evidence tip | `18bba95a4528f6ab5910633f1f87f603b8c4ddf8`, tree `56209bb72b84fc845ad00433b4471e723ecc8a01` | CONTRACT_CLAIMED. WSR20 packet (`forge-protocol2-bridge/wsr20-full107/` with `FULL107_FORGE_MAPPING.json`, `COMMON_FIXTURE_SUCCESSOR_PACKET.json`, `EXECUTION_RESULTS.json`, `HIDDEN_INFO_RESULTS.json`, `RNG_REPLAY_RESULTS.json`, `MULTIPLAYER_RESULTS.json`, `VALIDATION.md`, `FINAL_HANDOFF.md`) is ABSENT from Lab source truth in this worktree (glob+grep negative; see Gate C). Production-code delta WSR20↔candidate is contract-recorded as NONE; WSR20 is tests/evidence only and must not be merged into Forge master nor treated as a new Rules-Core version. |
| Lab pre-selection manifest (current, frozen for this workstream) | Rules-Core `a37a865a53280dd8ad6fad3384d69611e8c5a42f`, bridge materialization `4753bb7c72ea60d653121e0bab989077b4009f9c` | LOCALLY_VERIFIED in `config/rules_engines.json` (secondary_engine.commit + bridge_source). NOT repinned here; repinning belongs to the later Freeze decision. |

## Provenance preservation

Historical identity files may contain stale candidate identities (e.g.
`FULL107_IDENTITY_BINDING.json` records `db134b9737e951367d65ef5806ad986319cc73ab`
and `a37a865a…`). Those are preserved as provenance and never silently
rewritten. Gate A binds each identity separately with CURRENT / HISTORICAL /
EVIDENCE_ONLY / ENGINE_CODE / LAB_INTEGRATION / PRE_SELECTION_MANIFEST labels.

## Impact adjudication (fetch policy)

Only Commander-Lab history was fetched/inspected in this worktree
(`git fetch` scope = Lab remotes). Fresh fetches of the separate Forge/Mage
repositories were not achievable from this worktree (no declared reference
roots; sibling-worktree probing prohibited). This is recorded as a bounded
verification gap, not a drift: all Lab-side source-lock facts verify exactly,
and no Lab main/branch advancement occurred during the session opening.

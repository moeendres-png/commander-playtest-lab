# WS-39 TERMINAL BLOCKER EVIDENCE — REFRESHED AFTER STACK IDENTITY REQUALIFICATION

## Classification

`WS39-TERMINAL-BLOCKER-IMMUTABLE-WS32-PILOT-CHOICE-AURA-TARGET`

This is the terminal fail-closed stop-condition evidence for WS-39. It does **not** grant XMage successor-provider PASS, AF credit, AF07, or Architecture Freeze.

A prior revision of this file listed three immutable stack-contract blockers. That prior classification is superseded. Fresh bounded alias remediation and exact rerun proved `PILOT_REPLACEMENT_EFFECT`, `MICRO_PRIORITY`, and `MICRO_STACK` natively constructible. The sole remaining terminal blocker is `PILOT_CHOICE`.

WS-39 is explicitly prohibited from modifying WS-32. Exact runtime plus current primary rules authority proves that the immutable WS-32 v1.0.2 requested state for `PILOT_CHOICE` cannot simultaneously satisfy Magic Rules correctness and the frozen requested-state equality/digest gate.

---

## Source Lock

### Immutable WS-32

- schema: `commander-lab.semantic-fixture-materialization/1.0.2`
- freeze commit: `038d0f38635eecee4e331c99af41f148de267a26`
- freeze tree: `0d160128119f2bad30b220a17c43419b50b7edbe`
- canonical bundle digest: `ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23`
- materialization SHA256: `0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261`
- authority lock Comprehensive Rules effective date: `2026-08-07`
- authority lock CR PDF SHA256: `9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c`
- exact XMage denominator: 107 records.

### XMage

- repo/branch: `moeendres-png/mage` / `foundry/ws39-commander-history-state-restore`
- exact engine commit: `7bde812727817723616c575759f39bfc4cda4607`
- exact engine tree: `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`
- exact card source: `Mage.Sets/src/mage/cards/u/UtopiaSprawl.java`
- that source adds one `TargetPermanent` filtered to Forest to Utopia Sprawl's spell ability, an `AttachEffect`, and the corresponding `EnchantAbility`.

### Current primary Magic authority

The current Wizards Rules page resolves its Comprehensive Rules PDF to:

`https://media.wizards.com/2026/downloads/MagicCompRules%2020260807.pdf`

The PDF states it is effective August 7, 2026. Relevant rules:

- CR 303.4a: an Aura spell requires a target defined by its enchant ability.
- CR 115.1b: Aura spells are always targeted, and the target is chosen as the spell is cast.
- CR 601.2c: the caster announces an appropriate object/player for each target the spell requires.

This is the same effective-date authority domain frozen by WS-32.

---

## Fresh exact construction evidence after bounded alias remediation

### Runtime identity

- provider runtime head: `f326efc841c8ad81d1c5c60aefc3913cb3f33651`
- provider runtime tree: `ee130a07efc3982b731347d1b77700328cd9f25d`
- workflow: `WS39 Full107 Native Construction Probe`
- run: `33798418779`
- job: `100791627620`
- job conclusion: `SUCCESS`
- artifact id: `9910486727`
- artifact name: `ws39-full107-construction-f326efc841c8ad81d1c5c60aefc3913cb3f33651`
- artifact digest / independently downloaded ZIP SHA256: `3ca60c2b796da66b5839cda49f5ae4b9c6af1214bd533b3a318db889f0e0c572`
- `WS39_FULL107_CONSTRUCTION_PROBE.json` SHA256: `560087d5cffc2c7d903d293c545d929bb621fd4d5087872f2125af220dcb329e`
- `SHA256SUMS` SHA256: `88e3ca96c5b2c844246ef39d5c941069ca5319ee44064aec5e9d9127dcc1b9ae`
- all 10 internally sealed files independently rehashed: PASS.

### Fresh census

- 52 `NATIVE_SETUP_PASS_NO_RUNTIME_CREDIT`
- 7 `DEFERRED_TO_FRESH_NATURAL_EXECUTOR`
- 47 `FAIL_CLOSED_UNSUPPORTED_NATIVE_DIMENSION`
- 1 `FAIL_CLOSED_NATIVE_CONSTRUCTION`
- total 107
- `historical_pass_imported=false`
- `runtime_credit_granted=false`.

The three previously ambiguous identity failures are now closed:

- `PILOT_REPLACEMENT_EFFECT`: native setup PASS via unique frozen `card_lineage_id` alias.
- `MICRO_PRIORITY`: native setup PASS via unique case-insensitive semantic-id alias.
- `MICRO_STACK`: native setup PASS via unique case-insensitive semantic-id alias.

Those records are **not** terminal blockers.

---

## Sole terminal blocker — `PILOT_CHOICE`

### Frozen identity

- fixture family: `pilot_boundary`
- materialization digest: `f255fb5e8aaa115c659442bd60d617a8ba5128b2df945e3b013c5c6c3a2f90ba`
- requested-state digest: `4c1c8ab42c351281cd9f0d34a770ea65eaff7ab8c909ad57b989671842456044`
- execution entry: `NATIVE_STATE_LOAD`.

### Frozen requested stack state

The semantic object `obj:utopia` is `Utopia Sprawl` in zone `stack`. Its sole frozen `stack_state` row requires:

- `source_semantic_id = obj:utopia`
- `controller = P1`
- `cast_complete = true`
- `costs_paid = true`
- `targets = []`
- `modes = []`.

The same frozen record contains `obj:forest` as a Forest permanent on P1's battlefield. Its frozen native procedure requires `NATIVE_RESOLVE_TOP_OF_STACK` for `obj:utopia` with `attached_to = obj:forest`.

### Frozen construction gate

The same record requires:

- `construction_validation.required = true`
- `credit_condition = REQUESTED_STATE_DIGEST_EQUALS_CONSTRUCTED_STATE_DIGEST`
- `provider_must_emit_normalized_constructed_state = true`
- requested-vs-normalized-native-constructed-state equality
- `silent_setup_correction` forbidden.

Its normalization explicitly retains stack source/controller/targets/modes/order as semantic identity. Provider-local object IDs may be normalized away; semantic targets may not.

### Fresh runtime failure

The exact post-alias rerun leaves only this record as native construction failure:

`NATIVE_VALIDATION_FAILED: stack target group cardinality obj:utopia`

- `behavior_runtime_executed=false`
- `runtime_credit=NONE`.

This is not a generic stack implementation failure: 52 denominator records now pass native setup construction, including the three remediated stack identity records.

### Digest proof

Using the exact frozen `commander-lab.requested-state-digest/1.0.0` projection and canonical JSON algorithm from `scripts/ws32_lint_semantic_v1_0_2.py`:

- frozen record with `targets=[]` reproduces exact requested-state digest
  `4c1c8ab42c351281cd9f0d34a770ea65eaff7ab8c909ad57b989671842456044`;
- changing only `PILOT_CHOICE.stack_state[0].targets` to the required legal Forest target `["obj:forest"]` produces
  `ef1df9ac28c80dc6c13d1d8922967a9078c52a9085aa9f03a219931be2944108`.

Therefore the minimum Rules-correct correction necessarily changes the frozen requested-state digest.

### Unsatisfiability proof

No in-scope provider implementation can satisfy both sides:

1. **Preserve frozen state exactly:** create a fully cast, fully paid Utopia Sprawl Aura spell on the stack with zero targets. This violates CR 303.4a / 115.1b / 601.2c and disagrees with the exact XMage card implementation's required Forest target.
2. **Construct the Rules-correct native spell:** choose `obj:forest` as Utopia Sprawl's target. This changes the requested state and its digest from `4c1c8ab4...` to `ef1df9ac...`, violating the immutable WS-32 construction equality gate.
3. **Construct the legal target but hide it from normalized readback:** this falsifies requested-vs-native construction evidence and is equivalent to the explicitly forbidden silent setup correction.

There is no fourth provider-side path that preserves both Rules correctness and exact frozen semantic-state equality.

**Verdict:** `IMMUTABLE_CONTRACT_UNSATISFIABLE`.

---

## Stop condition

WS-39's required terminal success criterion is a fresh exact 107/107 successor-provider result on the immutable WS-32 v1.0.2 denominator. One mandatory denominator record is now proven unsatisfiable under that immutable source lock.

WS-39 is explicitly prohibited from modifying WS-32. Continuing unrelated native setup or transaction implementation cannot make 107/107 reachable and would consume work against a source lock that must be superseded.

Therefore the correct WS-39 terminal outcome is:

- `TASK_COMPLETE = NO`
- `WS39_STATUS = BLOCKED`
- `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`.

This is an upstream immutable-contract blocker, not an XMage Rules-Core qualification failure.

No AF07 claim. No Architecture Freeze claim. No merge.

## Required upstream repair outside WS-39

Create and freeze a new provider-neutral successor contract version that:

1. changes `PILOT_CHOICE.stack_state[0].targets` from `[]` to the legal Forest semantic target `["obj:forest"]` (or otherwise represents an equivalent Rules-legal cast state without changing the underlying obligation);
2. recomputes `requested_state_digest`, record materialization digest, bundle digest, and all dependent frozen checksums;
3. strengthens semantic linting so fully cast Aura spells cannot freeze a zero-target stack state;
4. freezes a new immutable source lock;
5. resumes XMage successor qualification against that new source lock, reusing WS-39's engine remediation and bounded qualification overlays only after revalidation.

Do not retroactively edit WS-32 v1.0.2 inside WS-39.

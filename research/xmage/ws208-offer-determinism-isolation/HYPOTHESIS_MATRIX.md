# WS208 Hypothesis Matrix — XMage Offer Enumeration Nondeterminism Isolation

Status: PRE-IMPLEMENTATION adjudication record (XHIGH read-first).
Source Lock: audit base `1dee8b77`, XMage pin `cfc36f44`, WS205 immutable evidence authority.
Classification of this file: CODE_DERIVED (static analysis) + WS205-record-derived observations.
Nothing here is promoted to root cause without fresh-JVM reproducer evidence.

## WS205 record facts (derived from sealed WS205 evidence, not reinterpreted)

1. Six FALSE constructions: A03, B01, D06, E02, H01-HUMILITY_FIRST, I01.
2. All six: identical prefix (offset, class, actor_seat, selected_label) up to the
   first differing entry; divergence is ALWAYS `offered_count` differing by
   exactly 1 `activated_ability` at a `priority` frame; the selected label at
   the divergent frame is IDENTICAL on both sides (`label_ambiguous=true`,
   i.e. duplicate same-name options exist — multiple same-name basics in hand).
3. Only H01-HUMILITY_FIRST has `stream_diverged=true` (Clone-cast label absent
   at offset 411 in twin); the other five ran the full 500-decision budget with
   identical selection histories and equal terminal boards.
4. First-divergence offsets: A03@47, B01@377, D06@14, E02@80, H01@14, I01@14.
   Three of six diverge at offset 14 (early land-drop turns).
5. TRUE controls (A04, C01, F01, ...): 502-entry semantic transcripts identical.
6. Twin matching is order-independent (exact-label scan) and the semantic
   normalizer sorts `offered_types` as a multiset — so pure ORDER differences
   cannot explain any FALSE. All six FALSEs are SET-membership divergences in
   the projected offer stream. Sorting is NOT a legitimate fix.

## Bridge surface audit (CODE_DERIVED)

- `XmageFullGamePlayer.priority()`: options = pass + `getPlayable(game,false)`
  (NATIVE engine enumeration), sorted by `abilitySortKey` (sourceId:originalId
  UUID strings — deterministic within a run, distinct across JVMs; affects
  ORDER only, never membership). No dedup, no filtering, 1:1 option construction.
- `XmageFullGameActionProjection.project()`: strictly one action per
  `legal_options` entry, no filtering, no dedup. Membership-preserving.
- `toDecisionResponse` / `DecisionController.submit()`: membership validation
  only (reject unknown), no requested-option filtering. `REQUESTED_OPTION_FILTERING=ABSENT` stands.
- `decision_id` = SHA-256(gameId, offset, actorId, class): gameId/actorId are
  per-JVM random UUIDs, so ids differ across JVMs by design; twin matching and
  the semantic transcript never depend on them. `STABLE_ID_DETERMINISM`: stable
  by construction (hash, not identityHashCode/index), process-local inputs
  correctly excluded from semantics.
- `HashMap` in `choose()` (2 sites): lookup-only (`byOption.get(selected)`),
  iteration never drives the offered set. Classification: ORDER_IRRELEVANT.
- `HashSet` uses (projection + controller): duplicate/contains checks with
  deterministic semantics. Classification: ORDER_IRRELEVANT.
- `System.nanoTime`: timeout deadlines only. Classification: NOT_RELEVANT.
- `XmageDeckImporter` `UUID.randomUUID()`: deck-handle identity only
  (process-local, never semantic). Classification: NOT_RELEVANT.
- `smallestAction` / `smallestNonCancelManaAction` compare `action_id` strings
  (embed per-JVM decision UUIDs): order among DUPLICATE-label options can vary
  across JVMs. Effect is selection-among-semantically-fungible-duplicates only
  (same label recorded); cannot change offered SETs. Not a FALSE cause; noted
  as second-order nondeterminism with no semantic effect on basics.
- `chooseReplacementEffect` iterates engine-supplied `effectsMap.entrySet()`:
  if the engine passes a HashMap, ORDER may vary across JVMs; SET is preserved
  and twin matching is order-independent. Classification: POTENTIAL_NONDETERMINISM
  (order only), NOT_RELEVANT to the observed SET divergences.

## Hypotheses

### H1 — Engine game state already differs before enumeration (layer A). Prior: HIGH.
Same-seed runs produce different hands/library order (e.g. unseeded RNG in the
shuffle/draw path, RNG-consumption order perturbed by per-JVM UUID-keyed
HashMap iteration, or threading). Predicts: diagnostic hand multisets and/or
library fingerprints differ at or before the first offer divergence. A ±1
duplicate basic-land `PlayLandAbility` is exactly what a 1-card hand difference
produces. Concrete sub-mechanism H1a: per-JVM random card UUIDs change
`HashMap<UUID,…>` iteration order inside the engine; any order-dependent RNG
consumption (shuffle, random discard, "random element" picks) then diverges.

### H2 — Native `getPlayable` membership nondeterminism on identical state (layer B). Prior: MEDIUM.
Engine enumeration itself returns different sets from identical state
(HashMap-iteration with early exit, conditional RNG/time dependence in
`canPlay` paths). Predicts: diagnostic hands + library + battlefield identical,
native offered SETs differ. Requires engine-bytecode/call-chain evidence.

### H3 — Bridge projection drops/duplicates an option (layers D/E/F). Prior: LOW.
Code review shows 1:1 membership-preserving projection with unique option ids;
no dedup/filter path exists. Predicts: native SETs identical, projected differ.
Kept for reproducer-side falsification (reproducer captures both layers).

### H4 — Order-only divergence (layers C/F-order). Prior: NONE as FALSE cause (excluded).
Proven excluded by multiset normalization + order-independent twin matching +
identical selected labels. Kept only to record the mandatory set-vs-order
distinction: sorting is NOT a fix for these FALSEs.

### H5 — Normalizer false mismatch (layer G). Prior: LOW.
Python normalizer is deterministic over recorded fields (sorted histograms,
sorted boards/graveyards, regex redaction that can only MERGE labels, never
split them). It cannot manufacture a count difference. Reproducer captures
projected labels directly, bypassing the normalizer, which falsifies H5 if
projected SETs already differ.

### H6 — Other source (layer H). Prior: LOW.
Starting-seat rule `floorMod(seed,4)` is deterministic; London-mulligan always
kept; no pilot RNG (bridge full-game path uses no `Random`). Any H6 mechanism
must still manifest as state inequality (→H1) or enumeration inequality (→H2)
in the layered capture, so H6 collapses into the A/B decision.

## Decisive experiment

Bounded exact-prefix replay harness (`trace-primary` wish-policy re-runs in
N fresh JVMs + offline pairwise diff), capturing per decision:
state semantic fingerprint (turn/phase/step, active player, life, battlefield,
stack, mana, commander state, diagnostic hand name-multisets + library sizes —
diagnostics-only, never pilot input), native pre-projection option SET+order
(`pending.decision.legal_options`), projected SET+order (`actions`), stable ids.
Decision rule:
- hands/library differ at/before first offer divergence → H1 (layer A).
- hands equal, native SETs differ → H2 (layer B).
- native equal, projected differ → H3 (bridge D/E/F).
- projected equal, transcript differs → H5 (G).
Start: H01-HUMILITY_FIRST (explicit missing cast offer), then representative
FALSE pairs + TRUE controls. Record actual JVM counts; no count-as-proof.

# SLOT-06 ruling: truthful XMage capabilities on the production lane

Status: **COORDINATOR RULING** (AGENTS.md §8, Owner delegation). Refs #662, #255.
Date: 2026-10-09. Source lock: `main@727d7ee` (sealed epoch
`qualification/current-boundary-epochs/c124150d77ab-d303b2ca5f32`, #661).

This ruling decides what each flag means and what proves it. It does not flip any flag,
does not grant any gate, and does not claim Freeze.
`ARCHITECTURE_FREEZE = NOT_CLAIMED`; `provider_decision = NO_PROVIDER_READY`.

## Fresh facts this ruling rests on

1. One build artifact carries three JSONL lanes, chosen by `Main` argument:
   `full-game` (`XmageFullGameJsonlBridge`), `midgame` (`XmageMidgameJsonlBridge`), and
   the compatibility lane (`JsonlBridge`) for every other argument shape. `phase6` is a
   separate file mode. Because the artifact is shared, an artifact identity binds no
   evidence to one particular lane.
2. `architecture_freeze_contract_v2` holds **one** candidate, **one** source lock and
   **one** `truthful_capabilities` object with `reported_by_provider: true`.
3. The full-game lane (`XmageFullGameJsonlBridge.capabilitiesPayload`) reports five of the
   eleven `REQUIRED_CAPABILITIES` as `false`, not three:
   `legal_actions_supported`, `action_submission_supported`, `event_log_supported`,
   `replay_supported`, `game_shutdown_supported`.
   It serves neither `export_event_log`, `export_replay` nor `shutdown_game`
   (they answer `unsupported_message`).
4. The compatibility lane reports `event_log_supported` and `game_shutdown_supported` as
   `true`, but `legal_actions_supported`, `action_submission_supported` and
   `replay_supported` as `false`. AF01 in the sealed epoch ran on this lane.
5. AF04 in the sealed epoch exercised only `MULLIGAN` and `PRIORITY` frames.
6. AF09 PASS rests on the midgame clean-process twin (5/5). The epoch also records
   `export_replay` refused with `unsupported_message`, as an absent capability.
7. The in-epoch receipts (`receipts/native-xmage-{mechanism,direct}.json`,
   `executed_classes`) executed twelve `XmageFullGame*` classes, among them
   `XmageFullGameHiddenInformationTest`. **Not** executed in the epoch:
   - `XmageFullGameReplayTwinTest`;
   - `XmageFullGamePlayerBoundaryTest`;
   - `XmageFullGameActionProjectionTest`;
   - `XmageFullGameGenericActionSubmissionTest`.
   They appear only as source digests in `NATIVE_SUITE_RECEIPTS.json`, which makes them
   `CODE_DERIVED`, not runtime evidence of the epoch. They count only after they run
   in-epoch.
8. When a decision has no `legal_options` and no numeric context,
   `XmageFullGameActionProjection.project` returns an empty list
   (`XmageFullGameActionProjection.java:108-111`). `XmageFullGameSession` still reports
   `complete: true` (`XmageFullGameSession.java:382`).
9. When a cast or activation is cancelled or cannot be completed (payment cancelled, no
   legal target, no viable mode), `XmageFullGamePlayer` calls `pass(game)`
   (`XmageFullGamePlayer.java:398-428`). That means the lane passes priority for the
   player. Under the Comprehensive Rules (handling illegal actions; 601.2), the action is
   reversed and the player keeps priority. A forced pass breaks the rule that the Lab
   never chooses for a player.

## (a) Does a decision-scoped API satisfy the flags?

**Yes, under the definitions below. Not yet proven.**

`docs/engine_adapter_protocol.md` names `get_legal_actions` and `submit_action` as
required messages, requires `engine_capabilities` to report *actual observed*
capabilities, and requires illegal actions to fail without mutation. It does not require
a decision-free enumeration point. XMage is engine-driven: a legal action only exists
while the engine waits on a player, and priority is itself such a wait. A free-standing,
decision-free enumeration would have to be built by the adapter. That would be adapter
legality reconstruction, which AF01 and AF04 forbid.

`legal_actions_supported = true` requires all of:
- **L1.** For every production-reachable decision class: while a decision is pending,
  `get_legal_actions` returns that decision's complete engine-offered option set. It is
  set-equal to the native options and bound to the decision identity and revision.
  Numeric and selection-cardinality bounds (min/max) are exact. The test computes "native
  options" itself from the engine API (`possibleTargets`, playable abilities, `Choice`
  keys, modes, triggers and so on). It never takes them from the bridge's own
  `pending.legal_options`, because that would make the oracle circular.
- **L2.** While no decision is pending, it answers an explicit no-decision status and
  fabricates no actions.
- **L3.** A pending decision of a class that cannot be projected fails closed with a typed
  error. It never returns an empty or partial list, and never takes a default. Fact 8 is
  exactly this defect. It must be fixed, and a red control must fail on the old path.
- **L4.** The inventory is derived mechanically from:
  - every discretionary `Player` callback that `XmageFullGamePlayer` overrides;
  - the audited parent delegations;
  - every `decision_class` value the lane can emit.
  A class marked unreachable needs a code-derived reason. It is not claimed as
  exercised. A test fails as soon as an emitted `decision_class` has neither a matrix row
  nor an unreachability entry.

`action_submission_supported = true` requires all of:
- **S1.** Every projected action of every class in the matrix is submitted and accepted
  by the engine, and the routed native response contains only the selected option.
- **S2.** A stale decision or offset, a wrong actor, an option that was not offered, an
  out-of-bounds value and a malformed proposal each fail with a typed error. The
  engine-side state digest (`XmageFullGameSession` status payload) and the event offset
  are unchanged afterwards.
- **S3.** If an action is cancelled, or cannot be completed after it was proposed, it is
  reversed according to the CR, and the same player gets a new priority frame. When the
  engine cannot reverse it, the lane fails closed. It never forces a pass (fact 9).

**Required proof (test matrix, production lane, real engine).** The minimum matrix is
below. The binding list is the mechanical L4 inventory:
- priority, cast-ability choice (`chooseAbilityForCast`/`chooseLandOrSpellAbility`);
- target (`choose`/`chooseTarget`, including card selection from a zone with
  `Cards, TargetCard`) and target amount (`chooseTargetAmount`);
- mode, announceX, amount (`getAmount`), multi-amount
  (`getMultiAmountWithIndividualConstraints`);
- chooseUse, choice (`choose(Outcome, Choice)`), pile, replacement effect;
- attackers, blockers, trigger order;
- mulligan, London bottom and bottom order (`putCardsOnBottomOfLibrary`);
- playMana including cancelling a payment, the starting-player prompt, concede;
- chooseRingBearer;
- cancel and rewind (S3).
- Each class must show L1 and S1.
- `chooseRingBearer` and `getMultiAmount` are the two audited parent delegations. They
  count only if the test shows that the delegation reaches an externally answered
  callback. Otherwise L3 applies, and the flag stays `false` until the callback is
  overridden.
- Red controls:
  - a stubbed unprojectable class fails closed;
  - the empty-projection path from fact 8 fails;
  - a forced pass after a cancel fails;
  - a capability payload that reports a flag `true` while its matrix entry is missing
    fails the capability-truth test.
- **Executed proof only.** `capabilitiesPayload` is a static constant, so a flag value
  alone proves nothing. A required capability counts as `true` in the Freeze record only
  if the same epoch has an executed receipt of its proof test (class plus source
  digest). Without one, the assembler lists it as missing.

## (b) Which lane decides the Freeze record?

**The production lane is the full-game lane (`Main full-game`).** It is the only lane
with all of: external pilots for every seat, an explicit Rules seed bound before start,
concede, and a whole-game lifecycle up to TERMINAL. It is the P4 product path.
Compatibility and midgame remain qualification lanes.

Binding rules for the Freeze record:
1. **Capabilities.** `truthful_capabilities.capabilities` is exactly the full-game lane's
   `get_capabilities` payload from the epoch run, read from the AF01 transcript. Lanes are
   never merged and never combined into a union: a union would be inferred, not reported.
2. **Missing capabilities.** `missing_required_capabilities` is computed as
   `[c for c in REQUIRED_CAPABILITIES if capabilities[c] is not True]`. The same function
   writes `config/rules_engines.json` (`primary_engine.missing_required_capabilities` and
   `current_runtime.required_missing_capabilities`). A check mode fails CI on any
   difference.

   *Amendment 2026-10-10 (Coordinator ruling, #662 step 4).* The two fields describe
   different things and are derived separately, both from the same sealed epoch and
   never by hand:
   - `primary_engine.missing_required_capabilities` is the engine's truth on the
     production lane, computed as above;
   - `current_runtime.required_missing_capabilities` is the truth of the runtime the
     application launches (`production_bridge`, today the B4-D compatibility bridge).
     It is computed the same way from that runtime's own AF01 in the epoch (lane
     `compatibility`, verdict PASS, engine commit equal to the pin). It fails closed to
     every required capability when that evidence is absent or does not match.

   They diverged for the first time with epoch `85dbcb1ac475-9824c55d5ef2`, and H4
   (`engine-verify` must be degraded while the launched runtime lacks a capability)
   caught it. Moving the application to the full-game lane is a production integration
   step.
3. **Lane-surface gates** need a production-lane component from the same epoch, because
   each lane has its own player callbacks, its own seed binding, its own JSONL loop and
   its own observation filter:
   - AF01: the 20 v2 invariants on the full-game lane.
   - AF02: 2P to 5P lifecycle on the full-game lane (`XmageFullGamePlayerCountTest`).
   - AF03: seed binding and legality authority on the full-game lane
     (`XmageFullGameRulesSeedBindingTest`; in the compatibility-lane transcript
     `rules_seed_binding` is `null`).
   - AF04: the matrix above.
   - AF05: `XmageFullGameHiddenInformationTest` plus the redaction test from (c) R4.
   - AF08: the WS05 obligations that depend on the lane surface, run on the full-game
     lane. The lane reports `commander_damage_visible`/`commander_tax_visible` as
     `false`, so AF08 must name which obligations are proven on that lane.
   - AF09: the replay surface under (c).
   - AF10: run reliability on the full-game JSONL loop.
   - AF11: process topology of the full-game lane.
   Sibling-lane evidence stays as supporting evidence. It never stands in for the
   production-lane component.
4. **Rules-Core gates** (only AF00, AF06, AF07) may come from sibling lanes only if all of
   these hold:
   - same epoch;
   - same build artifact SHA-256;
   - same XMage pin;
   - a recorded argument that the lane's player callbacks do not affect the gate's subject
     (card and rule behaviour of the Rules Core).
   The artifact identity alone binds nothing (fact 1). The record names the lane of each
   gate's evidence.
5. **Label adjudication.** The sealed epoch calls midgame the "production midgame lane"
   (AF09). This ruling replaces that label. AF05 and AF09 of the sealed epoch remain
   valid for that epoch. The next epoch needs an impact adjudication under AGENTS.md §4
   against rule 3.

## (c) What satisfies `replay_supported`?

**`export_replay` on the production lane, verified by a clean-process replay.** Accepting
the AF09 twins as sufficient is **rejected**.

Why:
- `export_replay` is a required protocol message, and the flag reports a provider
  surface.
- The twins are harness machinery. A consumer of the bridge cannot obtain a tape from
  it, and the epoch already records the refused export as an absent capability.
- AGENTS.md §5 defines replay as deterministic semantic replay from recorded seeds plus
  authoritative Decision Options. That is exactly what an export has to carry.

`replay_supported = true` requires all of:
- **R1.** `export_replay` returns a versioned document with:
  - the protocol version and the bridge and engine identity;
  - the bound Rules seed;
  - the deck identities (digests) and the seating;
  - the ordered decision record: identity, class, actor, digest of the offered option
    set, and the chosen options by semantic key.
- **R2.** A replay verifier, a separate fresh JVM process, takes only the export. For
  every frame, the offered-set digest must match. The final semantic state digest must be
  equal. It may reuse the `XmageFullGameReplayTwinTest` machinery.
- **R3.** Red controls fail closed:
  - when the engine asks for a frame that is not in the tape, the verifier reports a
    divergence and never takes a default;
  - a tampered choice, a tampered seed or a truncated record is reported as a divergence
    at the first differing frame, never as PASS;
  - an export taken before game start is refused.
- **R4.** Privacy. The export carries hidden information, because the seed fixes every
  library order. The same is true of divergence reports and of offered-set digests,
  which can be brute-forced over a known decklist. All three are artifacts for the
  orchestration principal only:
  - they are never part of a pilot observation and never go to a pilot channel;
  - they never appear in logs, errors or committed evidence without redaction.
  The same applies to `get_legal_actions`: it takes no principal today and returns the
  whole pending decision. Either the request must be bound to a principal and checked,
  or a named test must prove the orchestrator-side redaction before anything is passed
  on to a pilot. Tests enforce both.

The AF09 twins remain valid AF09 evidence, and R2 may build on them. The flag goes `true`
only when R1 to R4 hold.

## `event_log_supported` and `game_shutdown_supported`

These two follow the same rule on the production lane:
- `export_event_log` must return a monotonic, principal-safe public event log;
- `shutdown_game` must end the game, release its resources and refuse later decisions
  with a typed error.

Each surface gets its own test and a red control. The compatibility lane's `true` values
are never carried over.

## Execution order

1. Bridge work on the full-game lane:
   - the decision-class matrix (L1–L4, S1–S2);
   - `export_event_log` and `shutdown_game`;
   - `export_replay` plus the verifier (R1–R4).
   Each flag goes `true` only in the commit that adds its passing proof.
2. AF01 on the full-game lane (all 20 invariants), plus the production-lane components
   of AF02/AF03/AF05/AF08/AF10/AF11 from rule (b)3. The AF04 production-lane component
   is the matrix.
3. A freeze-record assembler that follows (b), and `rules_engines.json` derived by it,
   with a check mode in CI.
4. PB-03 on `main`, seal with `seal.py`, then `check_freeze_eligibility` on the record.
5. Only if eligible: fill in the Freeze ADR template as a decision document for the
   Owner. The Freeze itself remains the Owner's decision.

## Non-claims

- No flag is `true` because of this ruling.
- No gate verdict changes.
- The D17 in-JVM residual risk stays not accepted.
- `UNKNOWN`, `PARTIAL`, `NOT_RUN` and `SKIPPED` are never PASS.

## Review

A fresh-context adversarial review (evidence-reviewer) of the first draft found three P1
and six P2 problems. They are fixed in this text:
- fact 7 was false;
- the lane-binding rule bound nothing, and its gate classification was too wide;
- the matrix was incomplete;
- proof from code alone was enough to set a flag;
- the L1 oracle was circular;
- the empty projection reported `complete: true`;
- a cancelled action forced a pass;
- the AF09 lane label was unadjudicated;
- R4 had privacy gaps.

The Coordinator verified facts 7, 8 and 9 itself against the receipts and the source.

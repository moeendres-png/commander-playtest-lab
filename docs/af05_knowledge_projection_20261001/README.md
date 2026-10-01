# AF05-KNOWLEDGE-PROJECTION-20261001 (#441 residual, Claude lane)

Milestone M1 of AF05 HIDDEN_INFORMATION on the XMage mid-game lane. Reserved on
#441 (comments 5931834370 and 5932387228). Branch `claude/optimistic-bohr-6asye6`.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`

## Source lock

| Role | Identity |
|---|---|
| Lab base | `main` `4e41bde6fd4f27dc448ae8c44f7af9212e3198fe` (tree `09e139d4`) |
| XMage candidate | `37e4df6c914f1e189e24f0ef59fa91734c922436` (unchanged) |
| Forge | not touched; Forge HIDDEN rows are milestone M3 |
| Effective contract | `commander-lab.full107/1.0.8-successor` (this change; was 1.0.7) |

## Scope

The six HIDDEN rows whose obligation is a knowledge boundary at a constructed
checkpoint (empty decision script):

| Row | Viewer obligation (the record's own sentence) |
|---|---|
| HIDDEN_01 | opponent hand identities absent while count remains visible |
| HIDDEN_02 | library identities/order absent while count remains visible |
| HIDDEN_03 | face-up exile identities public |
| HIDDEN_04 | face-down permanent controller sees identity while opponents do not |
| HIDDEN_19 | pilot code cannot access omniscient raw engine APIs |
| HIDDEN_HONEYCARD_SENTINEL | unique forbidden sentinels scanned across every channel |

HIDDEN_05–18 need event-driven script errata of their own (milestone M2). They
are untouched by this change and still fail closed on the lossless lane.

## What changed

### 1. SLOT-04 fixture errata, versioned as contract 1.0.8

#255 comment 5925956587 makes L7 lossless construction binding. A partial
library request and an untyped `face_down=true` must fail closed, and the old
HIDDEN fixtures are to be corrected and versioned. Every 1.0.5 HIDDEN record has
both an untyped face-down object and a partial library (one P2 library card at
position 0, nothing else), so no lossless construction of the predecessor exists.

`FULL107_SUCCESSOR_CONTRACT_v1_0_8.json` re-applies the nine 1.0.7 overlays
byte for byte, and adds `LOSSLESS_HIDDEN_STATE_MATERIALIZATION_ERRATUM_SLOT04`
for the six rows. The erratum adds:
- `face_down_type: MANIFESTED` on `obj:facedown`. Grizzly Bears has no morph,
  megamorph or disguise, so manifest and cloak are its only face-down routes.
  Cloak adds ward {2}, which the obligation does not describe.
- A complete `deck_state`: the base's own 99-Mountain template convention, the
  complete P2 checkpoint library (`obj:hidden-lib-0` on top, then 92 template
  cards), and exact checkpoint hands. P1 holds 7 + 1, because rule 103.8a skips
  the first draw only in a two-player game.

The obligation keys are untouched, so every obligation digest equals the
predecessor's. Requested-state digests are recomputed by the canonical resolver,
and lineage is kept under `historical_digests`. The 1.0.8 schema types
`face_down_type` and the `deck_state` entries. The resolver now reads the
materialization identity from the contract (`effective_materialization_version`)
instead of a literal.

Rule numbers other than 103.8a are cited by name. The official text could not
be re-fetched from this session, because the network policy denies the host.

### 2. Lossless construction and projection on the mid-game lane (Lab adapter)

- `XmageLosslessHiddenPlan` parses the lossless declarations and fails closed on
  any partial, untyped, MANUAL or inconsistent request, with codes only.
  - Before game start it turns the face-down object face down through the L7
    validation and native game-load primitive.
  - After the opening hands it places and orders the complete libraries through
    the native API.
  - It verifies every declaration engine-direct.
- `get_midgame_projection` is the actor-entitled knowledge projection
  (`XmageFullGameStateRedactor.actorView`) for one named principal.
  - It adds an engine-derived seat-to-label bijection.
  - There is no unscoped variant: an absent, wildcard or unknown requester fails
    closed.
  - Capabilities declare every observation's scope and no omniscient or raw
    object-graph API.
- `complete_midgame_arrival` reports `lossless_hidden_checks` as counts per kind,
  never by name.

### 3. Verifier, receipts and runner wiring

`src/commander_lab/qualification/current_boundary/knowledge_projection.py` reads
what each principal may know from the record and what it was shown from the
engine:
- **Construction:** EXACT, with the exact lossless check counts the record
  requires.
- **Binding:** each projection is bound to its requester.
- **Row focus:** the record's own obligation, compared against values the record
  requests.
- **Forbidden-identity and honey-sentinel scan:** covers every document the
  viewer receives (frames, legal actions, scoped observations, the public event
  tape, refusals) plus the process log. It requires channel coverage and two
  positive controls. A frame belongs to the actor it names, whichever response
  carries it. This is how the production full-game driver routes frames.
- **HIDDEN_19:** ten omniscient-access attempts must be refused with a typed code,
  and every frame must embed only its actor's view.

Outcomes:
- A **demonstrated leak** or a **denied entitlement** is a FAIL. The assembler
  records it on the row, and AF05 then derives FAIL rather than UNKNOWN.
- Anything unmeasured stays **UNVERIFIED** and earns nothing.
- A verified row persists a runner-bound positive receipt
  (`midgame-lane:knowledge-projection#<row>`), which the assembler promotes
  under R-4.

## Findings

1. **Fixed: face-down identity exposed through the mulligans.** The face-down
   permanent used to turn face down only at the first priority. Every opponent's
   mulligan frame named it face up. It now turns face down before game start.
   `XmageMidgameKnowledgeProjectionTest.noOpponentFrameEverNamesTheFaceDownPermanent`
   fails on the old ordering (verified locally) and passes now.
2. **Fixed: lossless check names.** Naming the checked object
   (`library_object:obj:hidden-lib-0`) in an observation a non-entitled requester
   receives would tell it that P2's library holds a requested card. The lane
   reports counts per kind instead.
3. **Not a defect: next-actor frames in submission responses.** A submission's
   response carries the next pending frame, which may be another principal's.
   The production full-game driver routes it by the frame's own seat, never to
   the submitter. The verifier addresses every frame to the actor it names and
   checks that each frame embeds only that actor's view.
4. **Observation only:** `get_legal_actions.outcomes` names every player's native
   id while projections mask non-viewer ids. These are engine-local handles, with
   no card identity and no HIDDEN obligation.

## Validation (local, `37e4df6c`)

- End to end on the lane: 6/6 rows verified. There were 0 occurrences of any
  forbidden identity or sentinel in the viewer's channels, and for HIDDEN_04 none
  in P2/P3/P4's channels either.
  - Coverage: 11 prompts and contexts, 52 options and labels, 24 state documents,
    7 events, 113 transcript documents, 216 log bytes.
  - This is development validation, not evidence. Credit comes only from the
    PB-03 run's receipts.
- Java: `XmageMidgameKnowledgeProjectionTest` 5/5. Its fail-before was shown by
  reverting the face-down ordering.
- Python: `test_knowledge_projection.py` 26/26. It kills three mutants (blind
  scan, everyone entitled, per-response addressing).
  - Contract tests cover the errata digest chain, lineage, schema mutations, and
    HIDDEN_05–18 left untouched.
  - The AF05 gate test shows a failed HIDDEN row now fails the gate.

## Remaining

- **M2:** HIDDEN_05–18, which are event-driven (invalidation on zone change,
  shuffle, look and reveal audiences, temporary permissions, controlled-player
  decisions, replay knowledge). Each needs a scripted real-card erratum before
  it can execute.
- **M3:** Forge HIDDEN rows, which need a Forge mid-game construction lane.
- **AF05** stays UNKNOWN until all twenty rows PASS. M1 can lift at most six.

## M2 batch 1: HIDDEN_07 and HIDDEN_08 (contract 1.0.9)

Every HIDDEN_05–18 record has the M1 static base and an empty decision script,
but its obligation names an event. A versioned scenario erratum adds the objects
that cause that event and a decision script that selects only engine offers.
The obligation, the viewer state and the lossless base state stay unchanged
(`HIDDEN_EVENT_SCENARIO_ERRATUM_SLOT04`).

| Row | Obligation | Event route |
|---|---|---|
| HIDDEN_07 | reveal reaches exactly legal audience | P1 casts Telepathy (Island pays). Its opponents play with their hands revealed, so P2's hand card reaches every principal's `revealed` log. |
| HIDDEN_08 | look reaches only specified audience | P1 activates Orcish Spy (`{T}`: look at the top three cards of target player's library), targeting P2. Only P1's `looked_at` log names `obj:hidden-lib-0`; P2 (the owner), P3 and P4 receive it nowhere. |

Verifier additions:
- A small script runner answers the record's script from engine offers only.
- The record's temporary permissions apply only to documents after the event.
  The same identity in a frame the viewer received earlier is still a leak.
- An event that never completed leaves the row UNVERIFIED, never FAIL.

A measured limit for later rows: a range-of-influence static (Telepathy) cannot
be *placed* before game start. XMage raises `IllegalStateException` in
`hasPlayerInRange`, so scenarios that need one have to cast it.

Local end to end on `37e4df6c`: 8/8 rows verified (six M1 rows plus HIDDEN_07
and HIDDEN_08). Credit only through the PB-03 receipts.

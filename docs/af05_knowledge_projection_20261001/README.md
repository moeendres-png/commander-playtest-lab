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

## M2 batch 2: HIDDEN_09, HIDDEN_14 and HIDDEN_18 (contract 1.0.10)

Contract 1.0.10 carries the seventeen 1.0.9 overlays byte for byte and adds the
same `HIDDEN_EVENT_SCENARIO_ERRATUM_SLOT04` class for three more rows.

| Row | Obligation | Event route |
|---|---|---|
| HIDDEN_09 | hidden-zone search inspection does not leak | P2 activates **Planar Portal** (`{6}, {T}`: search your library for a card, put it into your hand, then shuffle), paid by six P2 Islands, and chooses `obj:hidden-lib-0`. |
| HIDDEN_14 | target option metadata does not leak | P2 activates **Mastery of the Unseen** (`{3}{W}`: manifest the top card of your library), so `obj:hidden-lib-0` becomes a face-down 2/2 that P1 may not identify. P1 activates **Prodigal Pyromancer** (`{T}`: 1 damage to any target) and targets it. |
| HIDDEN_18 | transcripts omit actor-private state | P1 activates **Orcish Spy** targeting P2. P1 now privately knows `obj:hidden-lib-0`, the record's `known_object_identities`. |

Planar Portal was chosen because the search reveals nothing. A spell tutor
would make its own card public on the stack, and Mystical-style tutors reveal
the found card.

Verifier additions:
- **Search inspection.** The searcher and zone come from the record's own search
  permission. The searcher's own frame must offer every card of that library
  (93 of 93 at the checkpoint), including the requested identity. No other
  principal may receive any library offer or any identity it is not entitled
  to. If the searcher's frames carry no options, nothing was measured, so the
  row is UNVERIFIED rather than denied.
- **Library-object selector.** The lane reports no native id for a hidden
  library card. The script's `semantic_object` selector therefore matches a
  library object by the record's checkpoint position and identity, which the
  engine's offer to the searcher carries. Zero or several matches fail closed.
- **Hidden target.** The hidden target is the face-down permanent that the viewer
  does not control, as the viewer's own projection shows it. The script selects
  it with `semantic_face_down_permanent`, which resolves through the acting
  principal's own projection and nothing else. Every offer of it must carry an
  empty label and name and no denied token.
- **Script timing.** A scripted priority action now waits for an empty stack. A
  script declares events, never responses. Without this, P1 activated Prodigal
  Pyromancer while P2's manifest was still on the stack.
- **Transcript privacy.** The viewer's `known_object_identities` entitle it only
  after the scripted event, like temporary permissions. Before the event the
  same identity is a leak.
  - The look must reach the viewer.
  - Every public document (event tape, status and refusal envelopes) and the
    process log may carry no identity that any principal is denied.
  - Every other principal's channels are scanned.

### Finding: the public event tape named a face-down permanent's requested object

The first local run of HIDDEN_14 failed with `FAIL_DEMONSTRATED_LEAK`. The public
`get_midgame_events` tape carried `target_object: obj:hidden-lib-0` on the
`DAMAGED_PERMANENT` event for P2's manifested permanent, and every principal
receives that tape. `XmagePublicEventWatcher` treated every event other than a
zone change as public, so the bridge resolved the face-down target to the
semantic object the record requested, and the record binds that object to the
hidden identity. The card name itself was already withheld.

Fixed in the Lab adapter: the watcher marks the target and source of every
event other than a zone change as hidden while the object is a face-down
permanent or sits in a hidden zone, and the bridge then names neither its
semantic object nor its card. A public source is still named.
`XmageMidgameKnowledgeProjectionTest.thePublicEventTapeNeverResolvesAFaceDownPermanentToItsRequestedObject`
damages P1's own face-down permanent. It fails without the fix and passes with
it.

HIDDEN_11 (shuffle invalidates order knowledge) is executable with Orcish Spy
followed by a shuffle. After the shuffle, though, XMage keeps the viewer's
`looked_at` entry and its pre-shuffle card order as a turn-stamped history.
No current-state field (`granted_library`, `library_top_revealed`) ever
carried the order. Whether such a retained history entry is "pre-shuffle order
retained after shuffle" is a Coordinator adjudication, so the row is not built
yet.

Local end to end on `37e4df6c`: 11/11 rows verified (the six M1 rows,
HIDDEN_07, 08, 09, 14 and 18). In
HIDDEN_09, P1, P3 and P4 received no library offer. In HIDDEN_18 there were 120
public documents with 0 occurrences of any denied identity. Credit comes only
from the PB-03 receipts.

## M2 batch 3: HIDDEN_17 (contract 1.0.11)

Contract 1.0.11 carries the twenty 1.0.10 overlays byte for byte and adds the
same erratum class for HIDDEN_17.

| Row | Obligation | Event route |
|---|---|---|
| HIDDEN_17 | copy/face-down interactions hide original identity | P2 activates **Mastery of the Unseen**, so `obj:hidden-lib-0` becomes a face-down 2/2. P1 casts **Phantasmal Image** (two Islands), answers its "use" prompt yes, and copies that face-down permanent. |

Verifier additions:
- **Boolean selector:** a yes/no frame is answered only by the engine's own
  boolean offer whose value is the script's.
- **Copy of a hidden permanent:**
  - P1's copy choice must offer the hidden permanent with an empty label and
    name.
  - P1's resulting copy must be a face-up, nameless 2/2 with no private
    identity, as the copiable values of a face-down permanent are only its
    face-down characteristics.
  - Every principal other than P1 and the face-down permanent's controller is
    scanned.
- **Scripted casts become public:** a card that the record's own script casts
  is on the stack, a public zone (CR 601.2a), so every principal may know it
  after the event. Before the event it is still its owner's alone. The first
  local run showed why: P3 and P4 received "Phantasmal Image" once it was cast.
  Nothing else becomes public with it, and a test covers both directions.

Local end to end on `37e4df6c`: 12/12 rows verified.

## M2 batch 4: HIDDEN_10 (scry) and HIDDEN_13 (piles), contract 1.0.15

Both records come from the 1.0.5 base. Each declares an obligation, but its decision script is empty, so no event ever causes the obligated state. The erratum class is `HIDDEN_EVENT_SCENARIO_ERRATUM_SLOT04`. It sits on the lossless base and leaves the obligation unchanged. Both rows are in the provider denominator, so the unchanged-row count drops from 86 to 84. The denominator itself is unchanged.

| Row | Scenario | Verifier |
|---|---|---|
| HIDDEN_10 | <ul><li>P1 casts Magma Jet at P2 and scries 2.</li><li>The top of P1's library is requested as complete runs: Counterspell, then Brainstorm, then 91 template Mountains.</li><li>P1 keeps both cards on top: an empty selection on the engine's scry frame, which its own minimum of zero allows.</li><li>P1 orders them so Counterspell stays on top.</li></ul> | `scry_knowledge` |
| HIDDEN_13 | <ul><li>P1 casts Fact or Fiction. It reveals P1's top five cards (Counterspell, Brainstorm, Ponder, Preordain, Opt) to every player.</li><li>P2 splits them into piles.</li><li>P1 chooses pile 1.</li><li>The erratum declares the cast's legal reveal of the five cards as reveal permissions.</li></ul> | `pile_metadata` |

**`scry_knowledge`**
- The range comes from the record's own `known_library_ranges`.
- The range's cards entitle its viewer, and nobody else, only after the event (`known_range_objects`, `forbidden_tokens(after_event=True)`).
- The viewer's own frame must offer exactly the range's cards.
- The cards must return to the library: the engine reports two library-to-library moves.
- Every other principal receives no library offer and no range identity.
- Frames without options count as unmeasured, never as denied.

**`pile_metadata`**
- The reveal is checked as a reveal audience: every principal's reveal log names the five cards.
- Every principal's pile frames (P2's split, P1's choice) are scanned for identities, semantic ids and sentinels that principal is not entitled to after the event.
- At least two pile frames must have reached the table.

**Lane executor additions** (`knowledge_projection.run_script`)
- An empty selection is accepted only where the engine frame's minimum is zero.
- A set of library objects (a pile split) is matched by checkpoint position and identity, each fail-closed, within the frame's own bounds.
- `pile_label` selects the pile the record names by its engine label. A positional selector is barred by the schema.

**Finding: the projection keeps no state memory of a scry.** After the scry, P1's current-state projection carries no granted library entry and no `looked_at` entry. P1's knowledge is evidenced by the frames P1 received during the event.
- This is the same history-versus-state question as HIDDEN_11 (#441): a projection serves current state, and knowledge lives in what the viewer was shown.
- The verifier asserts what was shown and to whom. It does not claim that the projection remembers the range.

**Result.** The local run on this tree verifies 14 of 14 rows: the 12 earlier HIDDEN rows plus HIDDEN_10 and HIDDEN_13, each with its honey scan and controls. The unit controls cover:
- a range offered to P2 (leak);
- the wrong range shown to P1 (not verified);
- a private identity in a pile label (leak);
- piles that never reached the table (unmeasured);
- the pile selector.

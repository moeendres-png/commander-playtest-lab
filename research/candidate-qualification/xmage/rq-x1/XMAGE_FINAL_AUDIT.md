# RQ-X1 — Final Audit (XMAGE ARCHITECTURE-REVERSER READ-ONLY AUDIT)

Branch: `research/xmage-architecture-reverser-audit-20260910`
HEAD: `c162871ba416c338d37f83a44fbd5b054e79ca0e`
XMage pin: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c` / tree `f0a028b…`
(tree `f0a028b265f9c008ea0aedc4cec6b8f14500b69f`), checkout `/tmp/rq-xmage-src`
(read-only, verified clean post-audit).
Method: six parallel source-exploration passes + worker DIRECTLY_VERIFIED
spot-checks (source lock, counts, RNG body, license, stateId absence, key
signatures). No builds, no runs, no mutations, no mirror. All semantics
CODE_DERIVED; all runtime UNKNOWN.

## Objective verdict (the four primary questions)

**1. Can XMage expose authoritative legal decisions cleanly enough for an
external Commander Simulator pilot? — YES, at source level (CODE_DERIVED).**
The `Player` interface (1281 lines) + `HumanPlayer` (2960 lines) implement a
uniform ENGINE-builds-set → wire-carries-set → client-echoes-member →
server-revalidates loop for every decision kind. GUI/AI contribute ZERO
legality (selection-only, proven branch by branch). A UUID-echoing adapter
needs NO legality reconstruction. Caveats: no global legal-action
enumeration API; GUI preferences live inside the `HumanPlayer` path; runtime
confirmation needs M-1.

**2. Can Selection → Native Object → Execution bind without heuristic
reconstruction? — YES, natively (CODE_DERIVED).** Random-v4 UUIDs per
object/ability/effect/mode/player/game/token-instance; UUID sets/maps on the
wire verbatim; `map.get/contains/id.equals` consumption (×5
`possibleTargets.contains`, DIRECTLY_VERIFIED); `MageObjectReference` id+zcc
with null-on-mismatch; `stillLegal`/ZCC re-gating at resolution. Label
matching neither suffices nor is needed. WS48 lesson satisfied at source.
Caveats: `Choice` strings are key-based (bounded); NO request/state identity
and NO stale rejection exist (`stateId|requestId` zero hits,
DIRECTLY_VERIFIED) — staleness envelopes are adapter work; runtime proof
needs M-2.

**3. Is principal-scoped hidden information structurally/projectably safe? —
PROJECTABLY YES, STRUCTURALLY NO (CODE_DERIVED, safety UNKNOWN).** Protection
is SERVER_REDACTED per-viewer projection (N `GameView`s from `game.copy()`;
own-hand-only `myHand`, DIRECTLY_VERIFIED; counts-only library; face-down /
foretell / hidden-exile / look-at / search redaction with in-process test
pins). It is NOT structural (engine `choose*` sees full `Game`) and NOT
proven: hidden-card UUIDs + set/card numbers travel on the wire, logs are
single-broadcast strings gated only at construction, no no-leakage suite
exists. Server-side ⇒ safe MUST NOT be assumed. Needs M-3.

**4. Can Rules RNG + Semantic Replay satisfy project requirements without a
second Rules engine? — NO (CODE_DERIVED, decisive at source level).** Global
static `Random` shared by Rules+AI+setup+UI (DIRECTLY_VERIFIED body); unseeded
no-arg shuffles in Rules paths; per-call SecureRandom; iteration-order draws;
variable consumption; no per-game stream/seed/serialization/reset. Replay is
an outdated self-declared-unused snapshot-stepper ("TODO: delete" /
"not working correctly yet", DIRECTLY_VERIFIED); no journal, no reexecution.
`SEED_SUPPORTED = FALSE` and `REPLAY_SUPPORTED = FALSE` CONFIRMED as engine
facts. No second engine is needed for DECISIONS (R-1/R-2), but determinism/
replay would require ENGINE MODIFICATION (Rules-authority-boundary change) —
or an explicit mission-tolerance authority decision. Quantification needs M-4/M-5.

## Secondary objective: Deep Research correction

The Deep Research report itself was not found in-repo (searched
`deep|research` filenames + `deep research` content: only
`artifacts/audit/web_research.md`; no `GLOBAL_*_SUPPORTED` strings anywhere
— the eight historical statements survive only in this task brief). Claim-
level diffing is therefore at statement level: as PROVIDER-support statements
all eight survive uncontradicted; as ENGINE-capability claims, four are
REJECTED (mulligan, targets, modes, trigger-order — engine HAS them
natively), two are RESTRUCTURED (global legal actions / global submission —
per-dialog native equivalents exist; unified global forms absent), two are
CONFIRMED (seed, replay — engine LACKS them). License premise corrected:
MIT, not GPL (DIRECTLY_VERIFIED), clearance still required.

## Decision surface (42/42 located, zero UNKNOWN)

Full matrix in `XMAGE_DECISION_SURFACE.md`: all 42 kinds NATIVE_EXPLICIT
(targets/modes/cast/activate/X/amounts/colors/types/names/ordering/attackers/
blockers/damage/division/discard/sacrifice/search/hidden-choice/reveal/scry/
surveil/piles/voting/secrets/simultaneous/may/replacement/copy/commander-
replacement/concession/…), four with NATIVE_BUT_GUI_COUPLED (pass-skips,
grave-order, trigger auto-order, replacement auto-pick — preferences inside
path, legality unaffected). Zero INDEX_BASED on the wire; zero
SEMANTIC_ID_AVAILABLE (no second id to trust); ADAPTER_REQUIRED only for the
non-rules identity envelope.

## Action-identity gap (in `XMAGE_SELECTION_NATIVE_EXECUTION.md` §5)

NATIVE: game/session id, principal, native object/action identity, selected
option, Rules events, post-state identity. DERIVABLE_WITHOUT_RULES_LOGIC:
engine build id, decision context (partial). ADAPTER_REQUIRED_NON_RULES:
state revision, option-set identity, stale rejection, execution ack, RNG
effects. WOULD_REQUIRE_LEGALITY_RECONSTRUCTION: none on the native path.
ABSENT: global enumeration, unified submission, seed, replay.

## Multiplayer/Commander relevance (architecture only)

Variable counts (FFA 3–10, DIRECTLY_VERIFIED; Duel fixed 2); dynamic seats;
`sessionId→userId→playerId` three-namespace identity with in-memory join maps;
APNAP trigger loop; per-defender combat decisions; `leave()` 800.4a cleanup;
no `stateId`/revision (turnNum/stepNum only); starting-player choose() +
APNAP London mulligan. Eight seam weaknesses recorded (no external decision
handle; GUI prefs in path; first-option fallbacks; stale `getNumPlayers()`;
no revision; controller-hijack/projection coupling; destructive leave;
RNG/timer outside core).

## Test corpus (DIRECTLY_VERIFIED counts)

1957 `*Test.java` (Mage.Tests) / 1977 repo-wide; 6851 strict `@Test`
(+135 outside ⇒ ~6986); cards 1817 files/~6109 tests (~89%); commander 33/81;
multiplayer 18/69; dedicated view tests 1 file/1 test; dedicated RNG tests 3
files/38 tests; no decision-API unit suite; no `CardTestBase` at pin (harness
is `MageTestPlayerBase` + `CardTestPlayerAPIImpl` + 4727-line `TestPlayer`).
Reuse: DIRECT_REUSE none; strict-queue discipline REFERENCE_ONLY; skeletons
CLEAN_ROOM_PORT; card/multiplayer cases REFERENCE_ONLY; AI-assisted
UNSUITABLE; everything LEGAL_REVIEW_REQUIRED.

## Architecture reversers (net)

FOR XMage: R-1 engine legal sets on wire (HIGH) · R-2 UUID+ZCC binding (HIGH) ·
R-3 server-redacted views (MEDIUM) · R-4 variable counts (MEDIUM) · R-5 corpus
methodology (LOW-MEDIUM) · R-6 provider-history downgrade (MEDIUM).
AGAINST: C-1 no identity/stale/ack (HIGH) · C-2 global RNG (VERY HIGH) ·
C-3 no replay (HIGH) · C-4 GUI-path/projection/leave/UUID costs (MEDIUM) ·
C-5 no global enumeration (MEDIUM-HIGH).
NET: for a dialog-echoing pilot without engine determinism needs, the seam is
genuinely good; for the mission's reproducibility/replay needs, C-2/C-3 are
structural and unfixable without engine modification. Lead-reversal condition
is strategic (Coordinator authority), not hidden-evidence-shaped.

## Runtime mirror value

`XMAGE_RUNTIME_MIRROR_VALUE = MEDIUM` (rationale + 5-probe stop-early spec
M-1…M-5, ~5–7 days, in `XMAGE_RUNTIME_MIRROR_SPEC.md`). NOT executed, NOT
authorized — needs a new workstream contract + explicit user approval.

## PASS / FAIL / UNKNOWN

`XMAGE_ARCHITECTURE_AUDIT_COMPLETE` — the read-only audit is finished; all
twelve outputs persisted; no source/authority blocker encountered. (Ordinary
complexity was not a blocker; no user questions were asked.)
This is NOT a qualification PASS, NOT provider selection, NOT Architecture
Freeze:
`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.

## Remaining blockers / exact next action

Blockers: none for RQ-X1 (complete). Mirror execution blocked on
Coordinator/user authorization + new contract (AUTHORITY_GATE, not technical).
Next action: Coordinator reviews the twelve RQ-X1 files; decides
WORK_NECESSITY for the M-1…M-5 mirror (exceptional path only); adjudicates
the mission-tolerance question on C-2/C-3 (seed/replay without engine
changes) before any provider-direction use of R-1…R-6.

## Outputs (all under `research/candidate-qualification/xmage/rq-x1/`)

1. `XMAGE_SOURCE_LOCK.md` — lock + license correction + classification discipline
2. `XMAGE_DECISION_SEAM.md` — lifecycle, prompts, options, AI/GUI/adapters
3. `XMAGE_SELECTION_NATIVE_EXECUTION.md` — binding + identity gap analysis
4. `XMAGE_DECISION_SURFACE.md` — 42-kind matrix + historical adjudication
5. `XMAGE_HIDDEN_INFO.md` — projection paths + per-category verdicts
6. `XMAGE_RULES_RNG.md` — inventory + verdicts + R-A…R-D design
7. `XMAGE_REPLAY.md` — candidate classification + journal spec note
8. `XMAGE_TEST_CORPUS.md` — counts + harness + reuse table
9. `XMAGE_ARCHITECTURE_REVERSERS.md` — R-1…R-6 / C-1…C-5 + net
10. `XMAGE_RUNTIME_MIRROR_SPEC.md` — MEDIUM + M-1…M-5 (design only)
11. `XMAGE_UNKNOWN_LEDGER.md` — U-1…U-13 + promotion rules
12. `XMAGE_FINAL_AUDIT.md` — this file

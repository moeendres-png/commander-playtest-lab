# Engine strategy reassessment and execution — #665

Status: independent Codex assessment on the source lock in SOURCE_LOCK.json.
Recommendation: **Option D, XMage as the sole Rules authority in each production
game, with Forge retained as an optional bounded reference.** This supplements
the Owner-accepted #647 ADR; it does not replace it, select a new provider,
release a runtime, change qualification policy or claim Freeze.

## Fresh source truth and authority

GitHub was re-read on 2026-10-09; Lab main remains
9bd7cbad30d65f379cedfbaa63dedf81c2fd9061 / tree
89e33bf342b111fadd79047d49278e32cb11484b, after #664.
The JSON source lock records full default-head/tree and distinct qualified
core/bridge pins for all three repositories. A default branch head is not the
qualified engine pin. In particular Forge's actual bridge tree is
b5c19c19de37ca7976059e1a9fd6295a30534c06, verified through Git data.

At inventory: no open PR in the three repositories; Lab issues #255, #441,
#634, #654 and #662 open. No open mage/Forge issues. Local worktrees were
inventoried; only codex/engine-strategy-reassessment-20261009 is writable.
Other local worktrees retain their evidence/history. Claude's dispatched
#662 branches are active work even before they have PRs.

The newest direct Owner request outranks historical summaries. Actual executor
here is Codex; no Claude or Foundry identity/certificate is claimed.
Canonical policy read: AGENTS.md, docs/PROJECT_MISSION.md,
docs/CURRENT_EXECUTION_AUTHORITY.md, config/rules_engines.json,
CURRENT_PRE_FREEZE_CONTRACT.json, R-1…R-4 and SLOT06_RULING.md.

Owner receipts on #255:
- [6080484727](https://github.com/moeendres-png/commander-playtest-lab/issues/255#issuecomment-6080484727):
  conditional XMage selection, Option D and no Forge source port.
- [6084402560](https://github.com/moeendres-png/commander-playtest-lab/issues/255#issuecomment-6084402560):
  selection effective after sealed epoch 8398b69bc6a9-8a004769ee19.
- Runtime manifest remains NO_PROVIDER_READY; release readiness and Freeze
  are distinct. Architecture Freeze NOT_CLAIMED; production repository NOT_CREATED.
  Stable generic policy pointers still say NOT_SELECTED: use the newer explicit
  Owner receipts for strategic selection, without editing runtime admission.

R-1: the admitted Lab Forge fork is the candidate; pristine upstream is a
different reference identity and inherits no evidence.
R-2: provider decision-identity translation is allowed only with offering-frame
byte/type provenance; it never reconstructs legality.
R-3: all 20 AF01 invariants on one designated lane/run, never a capability union.
The newer accepted SLOT-06 ruling designates Main full-game for production.
R-4: direct execution of the exact FULL107 obligation, not adjacent mechanism
equivalence/import/construction. R-5 is a historical finding, not a new ruling.

Reference disposition freshly checked: #592 CLOSED/not_planned (not COMPLETE);
#626 and #646 CLOSED/completed; #645/#647/#658/#659/#661/#663/#664 merged/closed.
#634's remaining probe helpers are still owned and open. #441's old body/old
counts are not current source truth. #650/#651/#653 are complete, not reopened.

## Evidence and gap classification

Contract is 1.0.31, denominator 107. Sealed canonical epoch
c124150d77ab-d303b2ca5f32 records XMage 107/107 and AF00–AF11 PASS.
Its AF01 is compatibility-lane evidence; AF09 twins do not implement export_replay.
SLOT-06 identifies five false full-game required flags:
legal_actions_supported, action_submission_supported, event_log_supported,
replay_supported, game_shutdown_supported. Those are CODE_DERIVED missing
surfaces, not fresh runtime capability evidence. The manifest's shorter list
describes the older B4D lane and is not a truthful full-game missing list.
Claude B owns the evidence-derived repair.

The sealed Forge snapshot records 20 PASS / 33 BLOCKED / 54 UNKNOWN and six
AF PASS. After M15, fresh required packets can show NOT_RUN_REFERENCE_ONLY and
explicit carry-forward refusals with different non-PASS counts. They cannot be
compared as new Forge execution or used to downgrade preserved old evidence.

| Finding | Classification | Consequence |
| --- | --- | --- |
| XMage empty projection marked complete | Bridge/adapter correctness defect | A1 must fail closed and prove native set equality |
| Cancelled cast/activation forces priority pass | Bridge/player Rules deviation | A1 must use native rollback/re-offer; no Lab default |
| Full-game export/event/shutdown absent | Product/adapter gap | A2 implements and qualifies provider surfaces |
| Old AF01/receipts omit production components | Qualification/lane evidence gap | B binds same-epoch execution and derives readiness |
| #634 residual synthetic probe commands | Harness/helper causal-credit gap | Claude-owned remediation; no card/Rules-Core blame |
| Diagnostic tokens/public_message/type names leak | Lab error boundary defect | #665 repairs shared Python boundary and its direct sinks |
| Forge 87 older non-PASS rows | Mixed fixture/Lab/adapter/missing evidence | Does not establish worse internal Rules correctness |
| 32k/34k implementation files or parsed cards | Static breadth only | No arbitrary-card behavior or interaction completeness proof |
| Full terminal 4P + separate 127-step tape check | Bounded technical runtime evidence | Not replay of every terminal-game decision |

No current comparative semantic superiority is proven. The old comparison
marked every row NON_COMPARABLE. Historical reported gap grouping
55 fixture-not-rerun / 23 Lab / 5 adapter / 4 other is provenance, not a fresh
census under the current production-lane contract.

Actual hosted post-#653 main evidence on d3a12cf245b3f3d036d565190887053ebaa20f34:
fullgame run 37979448725 succeeds, native tests 985 pass / 1 skip,
a 4432-decision natural 4P terminal game, and a separate 127-step semantic
tape verification; 2/3/5/6P are bounded smokes, 7P fails closed.
Real 4P smoke uses four existing 100-card deck inputs but does not prove
their complete terminal games, every interaction or deck-comparison validity.
These are not production-lane proofs for all five missing flags.

## Independent comparison: eighteen dimensions

A is XMage-only without maintaining a reference. D is A plus selected,
explicitly budgeted external reference cases. The production path is identical.

| Dimension | A / D: XMage production | B: Forge production | C: two production engines |
| --- | --- | --- | --- |
| 1 Rules correctness | Strong bounded Lab evidence; A1 exposes a real bridge deviation | Core superiority UNKNOWN; older bounded evidence | Agreement detects discrepancies, proves neither correct |
| 2 Real card/mechanic coverage | Actual-card campaign; arbitrary combinations UNKNOWN | Scripts are breadth, behavior parity UNKNOWN | Each needs independent card qualification |
| 3 Core architecture | Engine-native Java state/events/abilities; callback audit required | Different Java/script/controller model; no proven fatal deficit | Two independent internal models to maintain |
| 4 Multiplayer/Commander | Terminal technical 4P; per-count and lane proof still needed | Scenario evidence; external product lifecycle absent in Lab | Separate complete lifecycles, no mixed authority |
| 5 Legal actions/pilot separation | Native callbacks exist; empty/cancel issues block truthful flags | Scenario API; full-game external driver work remains | Must prove completeness separately for both |
| 6 Hidden information | Principal redactor plus tests; error leaks repaired here | Production-lane isolation unqualified | Twice the observation/error boundaries |
| 7 RNG/replay | Explicit seed, twins/tape; provider export not yet qualified | Provider product export/replay UNKNOWN | Separate semantic representations and verifiers |
| 8 Isolation/batch | Existing full-game/batch path; scale and clean isolation need studies | External scenario process; product batch integration absent | Two execution/isolation/recovery surfaces |
| 9 Extensibility/maintenance | One production fork; bounded reference upkeep under D | One fork plus new integration; GPL constraints | Two production forks and interfaces |
| 10 Gap repair effort | Native matrix/surfaces + evidence critical path is concrete | Additional product-driver work; total effort UNKNOWN | Both critical paths plus integration/comparison maintenance |
| 11 Decks/pilots/analysis | Real deck loader/pilot bindings/batch exist | No equivalent complete Lab product lane shown | Provider-specific integration/regression work |
| 12 Technical debt | Callback/projection and qualification-lane debt explicit | Controller/adapter debt not fully inventoried | Cross-engine abstractions add debt unless materially useful |
| 13 Licensing/distribution | MIT engine; Lab proprietary; no source transfer | GPL-3.0 topology/distribution review required | GPL boundary remains, including packaging/upstream obligations |
| 14 Qualification/CI | XMage required; D reference only on demand | Full fresh current-contract qualification necessary | Each must meet same standards; shared checks need not double |
| 15 Total product cost | Lowest evidenced integration distance; reference cost bounded | Could win if unmeasured architectural advantage dominates | Higher obligations without demonstrated product value |
| 16 Reproducible real terminal 4P | Existing lane; five surfaces and same-lane qualification next | Product lane plus equivalent proof needed | Time to first product need not wait for both, but parity costs remain |
| 17 Meaningful deck comparison | Still UNKNOWN: pilots, complete games, sampling/uncertainty | Same study requirements plus integration | Cross-backend disagreement complicates statistics/attribution |
| 18 Production performance | Thousands-game throughput/memory/error rates UNKNOWN | Not measured under same decks/pilots/workload | No comparable throughput advantage established |

C is **not intrinsically prohibited** by one authoritative Rules Core per game:
two isolated backend runs could each have a single authority. The older ADR's
categorical mission-conflict claim is too broad. Reject C on demonstrated
additional production qualification/maintenance obligations without a measured
need (resilience, user engine choice or superior coverage), not that assertion.

B is not disproven by a small PASS count. It is presently less attractive because
it lacks the Lab's complete external product lane and associated proofs.
“Strictly longer” is not a measured theorem; unknown Forge quality/performance
could reverse the result. No such advantage is demonstrated at the locked pins.

E: current [phase-rs/phase](https://github.com/phase-rs/phase), default main
1477564533eef445a21294e3e5bb235e6ee05a68 / tree
cca9f323581c22488f72eac476e079bea7c3e51c, was screened afresh.
Its README reports Rust/native/WASM, multiplayer and MIT/Apache licences,
but also thousands of unimplemented cards. Its repository now has
fixtures/adapter-contract, including waiting_for_priority and game_action:
the old “no external interface described” screen is too absolute.
Fixture existence is not independent external-agent conformance, complete
Commander behavior, process-isolated replay or a Lab qualification receipt.
Do not migrate on catalogue counts or README architecture claims. Revisit if
an exact-pin executable probe proves complete 4P external decisions, principal
isolation, explicit seed and clean-process replay, plus difficult actual-card
negative controls. This is a bounded screen, not a claim that no other simulator
could ever be superior.

E across the same dimensions (external screen, not Lab qualification):

| Dimensions | E evidence / unresolved requirement |
| --- | --- |
| 1 correctness; 2 real coverage | README admits unimplemented cards; independent comprehensive behavior proof UNKNOWN |
| 3 architecture; 9 extensibility; 12 debt | Rust/native/WASM and functional architecture reported; maintenance advantage UNKNOWN |
| 4 multiplayer/Commander; 5 external legality | Multiplayer and adapter fixtures present; complete authoritative Commander/external-choice conformance UNKNOWN |
| 6 hidden information; 7 RNG/replay; 8 isolation/batch | Multiplayer privacy reported; principal/error isolation, explicit Rules seed and fresh-process batch replay unqualified |
| 10 gap repair; 11 deck/pilot/analysis integration | Card contribution/deck builder reported; Lab adapter/pilot/study integration effort UNKNOWN |
| 13 licence; 14 qualification/CI | MIT/Apache reported; exact proposed distribution and all Lab gates still need validation |
| 15 total cost; 16 reproducible real 4P; 17 deck comparison | No comparable measured engineering cost, qualified complete 4P run or controlled study |
| 18 performance | No same-workload production benchmark; Rust/WASM is not a throughput proof |

## Costs, uncertainty and sensitivity

No implementation-hour estimate is measured for A–E. No invented person-days,
throughput, probabilities or weights are used. Track qualified outcomes per
actual recorded engineering time when comparable logs become available;
the current resource-normalized productivity metric is UNKNOWN.

Lifetime model (MODELED, units can be recorded engineer-hours + runner-seconds,
kept separate unless an explicit conversion rate is adopted):
T = initial integration + defect repair + qualification/requalification
  + reviews/merge coordination + fork/upstream/card maintenance + CI.
Let X be remaining XMage product work, F analogous Forge work, R bounded
reference maintenance, and J dual-backend coordination. Then:
A = X; D = X + R; B = F; C = X + F + J minus proven shared work.
These are accounting variables, not numeric forecasts or proof of dominance.
R is not zero. Existing infrastructure lowers setup cost but reference pin
maintenance, fixtures and adjudication still consume resources.

Freshly inspected raw GitHub job metadata for historical PB03 run 37914716200:
job 113768076991 lasted 3002 s; Forge checkout 33 s and build 132 s.
Those two serial steps alone were 165 s (5.5% of that old job).
The old ADR additionally reports 50 s Forge FULL107 + 220 s scenario work,
giving ~435 s (~14.5%). The latter breakdown is historical reported measurement,
not newly isolated here. M15 already removed obligatory Forge execution.
A seven-minute saving on every current job or a causal current speedup is
not proven; cache, source and runner workloads differ.

Sensitivity:
- D beats A only when avoided debugging/review time or decision quality exceeds R.
  Run a reference case only with a named unresolved semantic question, official
  rule obligation, pinned identity, time budget and stop condition. If it adds
  no decision value, stop that case; no permanent parity target.
- B beats D if Forge's future repair/integration/maintenance savings exceed its
  additional external product-lane qualification and distribution costs.
  Require actual reproducible counterexamples/benchmarks before switching.
- C needs incremental value greater than F + J after shared work; independent
  official, actual-card, metamorphic, negative-control and replay tests reduce
  demand for parity, but do **not** fully replace independent implementation
  error detection. Agreement can preserve a shared wrong interpretation.
- Production throughput must be measured on the same real decks, pilots,
  hardware, seeds and terminal criterion. Old 25-second fixture games cannot
  support a games/hour or thousands-game completion forecast.
- Do not optimize parallel phases/shared builds until correctness and evidence
  contracts stabilize and provenance-bound paired measurements justify complexity.

## Forge reference and independent implementation protocol

A Behavior: observe a separately pinned Forge run; record the exact situation,
choices/result and oracle uncertainty. Decide the rule from current official
CR, Oracle and rulings, not Forge agreement. A divergent result is a discovery
signal, not automatically a validated Rules defect.
B Ideas: record general architectural concepts without copying implementation
structure or protected expression.
C Independent XMage implementation: derive a rule specification and positive/
negative scenarios from official sources. Implement with XMage-native events,
abilities, stack, object identity, replacement/continuous effects and rollback;
add systemic tests rather than card-name exceptions. Record sources/authorship
and any reference observations. Rewriting viewed GPL code is not automatically
independent; a doubtful provenance stops transfer and needs review.
D Direct port: forbidden under the existing Owner decision. Technical adaptation
between Forge script/controller and XMage object/event models is nontrivial;
matching functionality does not make implementations interchangeable.

[MIT](https://opensource.org/license/mit) permits reuse subject to its notice;
[GPLv3](https://www.gnu.org/licenses/gpl-3.0.html) governs modified/combined-work
conveyance and corresponding source. The [FSF FAQ](https://www.gnu.org/licenses/gpl-faq.en.html)
distinguishes well-separated programs from effectively combined programs.
A process boundary alone does not establish legal clearance. AF11's admitted
single-XMage topology is not approval for Forge linking or code transfer.
The proprietary Lab and distribution boundary still require the exact proposed
combination/licence review before any port. No Forge source was used in this patch.
Official rule starting points: [Wizards rules](https://magic.wizards.com/en/rules)
and [Oracle/rulings](https://gatherer.wizards.com/); canonical authority receipt
locks effective 2026-09-25. No Rules corpus is repinned by this assessment.

## Actual implementation and impact

Reuse classification: EXTRACT_AND_GENERALIZE the existing exact-public-reason
discipline in semantic_replay/divergence.py at the existing shared
failure_privacy boundary. No new Rules, observation or replay system.
Raw bridge/pilot text is no authority for public codes, class names or messages.

Implemented:
- Exact audited code vocabulary; unknown tokens cannot consume the code budget.
- Fixed standard exception classification; never read an arbitrary public_message.
- FullGame public exceptions redact dynamic text/code and suppress raw context;
  protocol conversions no longer chain raw validation/engine/pilot exceptions.
- Public runner/request/decision boundaries also redact otherwise unhandled
  engine numeric-conversion/pilot errors, retaining standard failure families.
  Exception formatting itself is guarded; a failing __str__ cannot leak its
  own exception or prevent a classified batch/smoke failure record.
- Rebuild exact public errors at the boundary too: pilot-added exception notes
  cannot enter a public traceback; standard reason/code and memory-local
  diagnostic channels are retained without copying traceback metadata.
- Actor-scope violations expose only validated integer seats or “invalid”.
- Real smoke persists safe classification and rethrows a redacted failure.
- Interrupted-session adversarial review additionally found spoofed str-subclass
  codes, unsafe formatting/type hooks and message-derived numeric audit data.
  Exact primitive codes, builtin text normalization, actual type ancestry and
  formatter-only failure containment close those routes. Conformance subclasses
  retain their failure family; the actor-audit public reason is static. Genuine
  operation interrupts remain interrupts. Recovery controls discriminate the
  old candidate (10 FAIL / 2 PASS), then pass after repair.
- Further independent review reproduced exact-exception dictionary lookup hooks.
  Builtin item enumeration with exact string keys now preserves intended local
  metadata without invoking subclass lookup or hostile-key equality. Three
  discriminating controls fail on the prior candidate and pass after repair.
- Final security adjudication found an inherited offline dictionary disclosure:
  native cast/land-or-spell failures can identify a still-private card by its
  name and three hexadecimal ID characters. An unkeyed diagnostic hash exposes
  this low-entropy value even without publishing its text. The shared digest
  now uses HMAC-SHA-256 with a random memory-only 256-bit process key, rotated
  after fork; entropy failure has no unkeyed fallback. The legacy
  `diagnostics sha256:` marker and 16-hex token width remain compatible.
  All full-game and replay diagnostic consumers receive the keyed token.
  Correlation is stable only within the originating process, not across
  independent processes or after exit using saved raw logs alone. This
  protects exported-record readers against offline enumeration; arbitrary
  code with access to the Python process/key is outside this boundary.
  This cryptographic privacy entropy never participates in Rules RNG,
  legal options, pilot selection or canonical semantic replay hashes.
- Fullgame/smoke push + scope filters include this dependency and new tests;
  their focused tests execute negative and legitimate privacy controls.

Success semantics, native rules/options, pilot choices, decks, seeds, pins,
capability flags, contracts and denominators are unchanged. Failures remain
failures. Unknown native error codes retain generic failure classification and
digest; exposing a new code requires explicit vocabulary review. Human
diagnostic suffixes and arbitrary subclass names are deliberately no longer
a public API. Raw transport diagnostics remain memory-local; not a pilot log.

Qualification impact: adapter error representation and CI triggering change.
Required quality/security/infrastructure retained. Triggered exact-head XMage
PB03, fullgame, real-4P smoke, metamorphic and applicable replay tests must
execute; no new FULL107 credit, no blanket historical PASS transfer. PB03
under the existing producer still does not settle SLOT-06 eligibility.
No optional Forge run needed: its code/pin/behavior is unchanged and the Owner
already authorised reference-only status. No sealed bundle modified.

## Workstream reconciliation and shortest qualified roadmap

| Priority / dependency | Owner / surface | Completion criterion / stop condition |
| --- | --- | --- |
| Rules-default correction + decision completeness | Claude #662 A1, Java | Native per-class matrix/inventory, invalid/stale nonmutation, cancel rollback, principal-bound options; flags only with executed proof |
| Event log, clean shutdown, export + fresh verifier | Claude #662 A2, Java | Typed lifecycle failures, 2P/4P fresh JVM replay, tamper/truncate/missing-frame controls, orchestration-only hidden tape |
| Same-lane readiness and derived manifest | Claude #662 B, Python qualification/config | AF01 production transcript, required production components, schema-valid computed record; absent receipt never true |
| Remaining causal harness helper defaults | Claude #634 | Declared-engine choice causality; targeted obligations and erratum/requalification if needed |
| Shared Python error privacy + reassessment | Codex #665 | Discriminating controls, independent review, affected exact-head CI and normal merge receipt |
| Native routing diagnostic | #654, unclaimed implementation | Preserve failed native evidence; do not fake model identity or block unrelated authorised work |
| New sealed current production epoch | Claude coordinator #441/#255 after A1/A2/B | Execute exact integrated sources once, seal, validate identity/production-lane readiness; no digest-only proof |
| Provider release / Freeze | Owner, decision after eligibility | Explicit exact-epoch Owner decision; otherwise no new production repo |
| Real terminal 2–5P and desired 6P | Post-gate assigned product lane | Per-count outcomes, legal external choices, complete tape/fresh replay, privacy and commander lifecycle; no cap-reached PASS |
| Reliable real-deck batch/study | Post-gate assigned product lane | Isolated per-game identity/failure/recovery, terminal game replay, representative mechanic coverage, fixed study design/uncertainty |

Existing efficiency measures: M1–M4/M7 done; M5 static registry preflight
implemented via #645, M8 step B merged but #634 residual helpers remain;
M6 superseded by M15; M9 parallel phases and M11 shared builds deferred;
M10/M12 no safe worthwhile reduction established. M14/#646 and M16 merged;
M17/#650–#653 completed. Do not rewrite Claude's stale efficiency status file
or restart those tasks. M15/#659 already implements the justified Forge
consolidation; this campaign preserves it.

Integrate A1/A2 with explicit conflict adjudication at shared Java flags/session,
then B against the final actual payload. #665 is disjoint Python diagnostic work,
but target drift must be rechecked before its own merge. After all relevant
sources are integrated, one fresh production-bound qualification epoch avoids
repeating expensive runs on intermediate untruthful capability states.

Execution update (#662 comment 6088767140): OpenCode Go monthly quota blocked
all dispatched batches before any implementation; Claude Coordinator now owns
their direct implementation in order B, A1, A2, then #634 B2. A paid quota
change remains Owner-reserved and is unnecessary for the disjoint #665 patch.

Final Owner template is concrete but **not yet eligible for signature**:
“On exact sealed epoch E, validated production-lane freeze record R and artifact
identities H, approve Architecture Freeze for already-selected XMage Option D
and authorise production repository creation under the recorded topology.”
Alternative: withhold until any listed gate/required capability is qualified.
Current E/R/H satisfying SLOT-06 are absent, so do not ask for or record a
premature Freeze. No second provider-selection request is needed.


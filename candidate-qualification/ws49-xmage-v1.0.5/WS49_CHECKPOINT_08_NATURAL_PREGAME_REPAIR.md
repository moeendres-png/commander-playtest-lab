# WS-49 CHECKPOINT 08 — NATURAL PREGAME ROOT CAUSE AND SYSTEMIC REPAIR

Status: **PERSISTED / NO PASS CREDIT GRANTED**

## Source basis (unchanged, verified live 2026-09-09)

- WS49 branch: `ws49/xmage-v1.0.5-successor-qualification`
- Pre-repair tip: `6c8c92d8f0930067300bc9412021add484650077`
  / tree `a82e94059ce38e7f5a1df0203042a307312d8664`
- Remote tip re-verified equal to the known tip before mutation; no
  concurrent worker advanced the branch. Draft PR #164 remains the
  qualification PR.
- main advanced `b483263e -> c27ad16f` (PR #171, OpenCode CLI v1.18.29 lane
  pin, `.github/workflows/opencode.yml` only). Impact-adjudicated as
  execution/CI infrastructure only. NOT merged or rebased into WS49: the
  WS49 base (`c83e52ae`) predates both mains and no technical necessity
  exists.
- WS-47 immutable lock unchanged: freeze `192e2b77...`, tree `f596c54d...`,
  namespace tree `12af7369...`, materialization SHA-256 `0e47b792...`,
  bundle digest `631da205...`, denominator 107.
- XMage baseline unchanged and re-verified: `0c1f455ea8c8fa48ab9d638ad5068ec242800428`
  / tree `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`; local engine worktree
  HEAD and tree match exactly.

## Failure matrix at pre-repair tip (evidence: CI run 34284488333 + PR sync)

| gate | status | first causal failure | evidence class |
|---|---|---|---|
| Full107 construction (push 34284488333) | 104/107, 3 FAIL_CLOSED | runner-side pregame expectation + unhandled London bottoming (this checkpoint) | DIRECTLY_VERIFIED (artifact `WS49_FULL107_CONSTRUCTION_PROBE.json`) |
| Bootstrap/impact (push 34284488343) | PASS | — | DIRECTLY_VERIFIED |
| CI quality (job 102256786345) | 44 ruff errors; 3 in WS49 files, 41 inherited (ws34/finalist/ws26/ws46 files absent from current main) | inherited lint debt; WS49-owned trio repaired here | DIRECTLY_VERIFIED (job log) |
| Full Game Conformance (run 34284492564) | FAIL `same-seed semantic full-game replay diverged` (passed at prior sync 34282291030) | suspect regression from `8de1964d..6c8c92d8` OR flake; downstream of pregame path, re-triage after construction closes | DIRECTLY_VERIFIED (job log), root cause UNKNOWN |
| WS42 census, MICRO_STACK, Finalist XMage, WS39 engine, WS-26 viability | FAIL at both recent syncs | presumed downstream of shared pregame/provider path; NOT independently root-caused yet | UNKNOWN (not re-triaged until construction closes) |
| WS18/WS22/WS34/external/core/handoff/windows/production | PASS | — | DIRECTLY_VERIFIED |

Downstream failures sharing one upstream construction/runtime defect are not
counted as independent root causes. `UNKNOWN` is not PASS.

## Exact failing rows (artifact 34284488333, DIRECTLY_VERIFIED)

- `PILOT_MULLIGAN`: `WS49_NATURAL_OPENING_HAND_MISMATCH:P1:actual=7:expected=6`
- `WS05-CMD-MULL-4`: `WS49_NATURAL_OPENING_HAND_MISMATCH:P1:actual=7:expected=6`
- `WS05-CMD-MULL-2`: `WS49_NATURAL_UNSUPPORTED_PREGAME_DECISION` on a native
  `target` decision (`discard`, `a card (1 more) to put on the bottom of
  your library`, 7 options, actor P1)

## Root cause (both runner-side; engine and contract exonerated)

RC1 — wrong opening-hand expectation (CODE_DERIVED + contract-bound):
`XmageWs26QualificationSession.java:89` grants the London free mulligan iff
`playerCount >= 3` (`MulliganType.LONDON.getMulligan(playerCount >= 3 ? 1 : 0)`).
XMage `LondonMulligan` then draws 7 with no bottom prompt for the free
mulligan and prompts per-card bottoming only for non-free ones. The immutable
contract independently encodes the same rule: `WS05-CMD-MULL-4` (4P, P1
mulligans once) models `expected_bottom_count=0`, while `WS05-CMD-MULL-2`
(2P, same plan) models `expected_bottom_count=1`. The probe instead expected
`7 - mulligan_count` for every player, manufacturing both hand mismatches.
Native hands of 7 for the 4P rows are engine-correct free-mulligan results.

RC2 — unhandled London-bottoming decision (DIRECTLY_VERIFIED via local
native transcript): after P1's non-free mulligan in the 2P row, XMage
natively prompts `target` bottom selection. The probe treated every
non-`mulligan`/`priority` class as unsupported and failed closed instead of
completing pregame.

Local native transcripts further verified (DIRECTLY_VERIFIED, exact-head
bridge + instrumented exact-baseline engine): starting-player offer,
per-actor mulligan rounds keyed by native seat, then either direct priority
(4P rows) or exactly one 7-option bottom prompt (2P row).

## Bounded systemic repair (no fixture/card-name hacks)

In `candidate-qualification/ws49-xmage-v1.0.5/run_full107_construction_probe_v105.py`:

1. New `target` handler for native London-bottom prompts: strict signature
   check (`targeted`, `discard`, bottom-of-library description, required,
   sourceless, exact min==max>=1); each bottom must be covered by a taken
   mulligan of the same actor; selection allowed ONLY across
   proven-semantically-identical actor-safe options
   (`option_type`+`label`+`metadata.name` equal, non-blank), otherwise
   `WS49_NATURAL_BOTTOM_OPTIONS_DIVERGE` fail-closed. No positional, UUID,
   random, default, AI, or GUI selection exists. The choice is recorded with
   an identical-option neutrality proof.
2. Empirical opening-hand expectation: `expected_hand = 7 - bottoms_submitted`
   from the runner's own native submission log — no mirrored freeness
   prediction. Where the immutable procedure models
   `NATIVE_COMPLETE_LONDON_MULLIGAN_BOTTOMING`, total submissions must equal
   `expected_bottom_count` exactly (fail-closed both directions).
3. Old-format records without a bottoming step (PILOT_MULLIGAN) verify from
   the submission log plus the fully consumed plan and native prompt
   observations.
4. Added `native_mulligans_taken`, `native_london_bottoms_submitted`, and
   `contract_london_bottom_total` to the pregame evidence payload (additive).

Also repaired the 3 WS49-owned ruff errors (SIM102 nested-if collapse,
I001 import-block format, B905 explicit `strict=True` over two provably
length-2 sequences). The 41 inherited errors in files absent from current
main remain untouched as out-of-scope debt.

The repair does NOT modify WS-47, XMage, Magic legality, fallback behavior,
or any expected semantics; unsupported paths still fail closed.

## Local validation (DIRECTLY_VERIFIED, exact locks)

- Exact-baseline engine worktree + RNG-instrumented build installed;
  exact-head bridge rebuilt (`mvn verify`: 62/62 PASS); WS49 ruff clean;
  `py_compile` PASS.
- Repaired `probe_record_v105` executed natively for all 7
  NATURAL_GAME_START fixtures: 7/7
  `NATIVE_SETUP_PASS_AWAITING_INDEPENDENT_NORMALIZATION`.
  - `WS05-CMD-MULL-2`: P1 6/93 after 1 neutrality-proven bottom
    (common label `Mountain`, 7 options, 1 distinct identity);
    submissions total 1 == contract 1.
  - `WS05-CMD-MULL-4`: all 7/92, submissions 0 == contract 0.
  - `PILOT_MULLIGAN`: all 7/92, submissions 0 (no contract step).
  - `PLAYER_COUNT_2P/3P/4P/5P`: PASS, no regression.
- Full 107-row CI adjudication is still required; no construction credit is
  claimed here (`G49-07 = NOT_CLOSED`).

## Next automatic action

Push this repair, obtain the fresh exact-head Full107 CI sequence
(run 34284488333 is superseded and must not be reused), adjudicate 107/107
from the new artifact, then re-triage the downstream gates (Full Game
Conformance divergence first) from fresh evidence only.

# WSR24 Self-Review (adversarial, 2026-09-27)

Method: each attack below was executed against the committed WSR24 artifacts
(machine JSON validated by `tests/qualification/test_wsr24_freeze_readiness.py`;
prose scanned by grep). Findings marked FIXED were repaired and re-validated;
findings marked ACCEPTED are Khonest limitations recorded, not hidden.

## Attack 1 — Implicit provider preference

Probed for recommending/preferring/scoring language (case-insensitive scan for
`recommend xmage/forge`, `prefer`, `winner is`, `score =`, `ranking:`).
Result: no hits. Both DAGs carry "CONDITIONAL, NOT selected" + "no
recommendation". Both readiness packets carry "no score, no tier, no
recommendation… one half of a symmetric pair". The PASS asymmetry (79 vs 30)
is explicitly classified as evidence-build asymmetry (PB-03), never as
capability. ACCEPTED as clean.

## Attack 2 — Rankings disguised as prose

Checked: row-count differences (33 vs 7+2 BLOCKED rows; 19 vs 8 hidden rows)
are presented as remediation-sizing facts with per-row lists, never as
quality judgments. SLOT-01 lists both options with symmetric consequence
statements. ACCEPTED as clean.

## Attack 3 — Stale source identity

Cross-checked every pinned SHA in SOURCE_LOCK.json and WSR22_EVIDENCE_INGEST
provenance against fresh `git rev-parse` / `git hash-object` output at review
time: audit base `b786fbf2`, WSR24 HEAD lineage, PR #269 head `208341c6`,
engine pins `b1959698` / `ef958ee9`, protocol blob `ea8651f7` all confirmed.
The FULL107-contract blob drift (267909c4 at WSR22 vs 23d9ec53 current) is
recorded with its metadata-only delta, not silently unified. ACCEPTED as clean.

## Attack 4 — Stale WSR22 counts

Recomputed from the WSR22 branch objects (not from memory): XMage
30/0/44/33, Forge 79/0/21/7, comparison 25/82, blockers 0/4/4 — all match the
ingest, and the validator test recomputes the sums to 107. ACCEPTED as clean.

## Attack 5 — Missing AF gate

Validator asserts the catalog is exactly AF00–AF11, both readiness packets
hold 12 gates with exact id sets, and the binding map covers all 12 exactly
once. The schema's per-gate `contains` clauses are structurally verified.
ACCEPTED as clean.

## Attack 6 — Missing required capability

The 11 schema-required capabilities are extracted from the schema's own
`then` conditional (test asserts each name + `const:true` present) and mirrored
in `freeze_readiness.REQUIRED_CAPABILITIES`. Both packets' preventers name the
actually-missing flags, verified lane by lane against AF01 artifacts.
ACCEPTED as clean.

## Attack 7 — Invalid freeze_eligible claim

Every `freeze_eligible=true` string in the packet was inspected: all occur in
rule statements ("ONLY IF…"), falsifiers ("invalid … validating"), or the
post-Freeze step-13 standing record — never as a claim about current
evidence. Both packets record `freeze_eligible:false`. The `find_banned`
pattern plus the literal `"freeze_eligible": true` absence test enforce this
in CI. ACCEPTED as clean.

## Attack 8 — Second Rules Engine design

The production contract §1–2 and the slice contract §4 place all legality
inside the Rules Core; the adapter is translation-only and the pilot is
strategy-only. The SLOT-03 shim is explicitly provenance-bound (submitted
identity must byte-match the offering frame) with a falsifier for breach.
No test-helper, pilot, or adapter legality exists in the WSR24 module (pure
structural checks, no card semantics). ACCEPTED as clean.

## Attack 9 — Legality in adapter/pilot; hidden fallback

Scanned the production/slice contracts for fallback-shaped language: every
hit is a prohibition (N1–N8) or a fail-closed requirement, never a
mechanism. Default-choice, silent-skip, internal-AI, GUI, and injection
fallbacks are each named as forbidden with a CI test. ACCEPTED as clean.

## Attack 10 — Hidden-information contract completeness

AF05 rows are enumerated per candidate (19 XMage / 8 Forge incl. sentinel);
honeycard negatives are required in the contract, the slice, and the DAGs;
SLOT-04 forces the Coordinator to scope channels rather than letting WSR24
narrow them. The five historical Forge seams must be "freshly classified,
not dismissed". ACCEPTED as clean.

## Attack 11 — Rules RNG ownership; replay without clean process

RNG ownership is engine-only in the ADR template (§19), the production
contract (N6), and the slice (§2.6); the harness-RNG falsifier is shared with
the impact template. Clean-process twins are required per fixture (PB-08),
never assumed from single-process export; SLOT-09 governs timing.
ACCEPTED as clean.

## Attack 12 — Unsupported paths without fail-closed behavior

The ADR template forces explicit SUPPORTED/UNSUPPORTED lists with per-path
fail-closed behavior; the bootstrap plan and slice require typed failures
with evidence bundles. No path is left implicit. ACCEPTED as clean.

## Attack 13 — Production Repository creation before Freeze

No repository was created (verify: `git status` shows only Lab-branch files;
no new remotes). The contract header and step-0 precondition forbid creation
before SLOT-10. ACCEPTED as clean.

## Attack 14 — Historical PASS silently promoted

Promotions are bounded (25 ≤ 30, 74 ≤ 79) with byte-identity provenance
cited; evidence_class is FRESH_CURRENT_BOUNDARY_EXECUTION; the impact
template §2/§4 + validators forbid reassurance reruns AND silent carry-forward
alike. ACCEPTED as clean.

## Attack 15 — Performance overriding correctness

Performance appears exactly once: bootstrap step 17, explicitly last, gated
on invariants staying green. The slice contract §6 excludes optimization.
ACCEPTED as clean.

## Defects found and fixed during this review

1. FORGE AF10 entry drafted with a placeholder evidence pointer — replaced
   with the authoritative AF10 evidence before commit.
2. `validate_readiness_packet` read a `verdict` key the packets never had
   (packets use `current_verdict`) — module fixed, tests caught it, 32 green.
3. DAG symmetry test split headers on the wrong delimiter — test fixed to
   normalize candidate tokens.
4. ADR CLAIMED-absence test collided with the legitimate checklist fill-task
   — test narrowed to "only occurrence is the checkbox line".
5. XMage AF11 cited Forge-side PB-05 — removed; XMage AF11 rests on PB-02.
6. Typo "rimiento" in the XMage DAG header comment — fixed.

## Residual limitations (accepted, recorded)

- JSON artifacts are single-line (machine-first); reviewers should use
  `python -m json.tool` for reading. Validity is CI-enforced.
- `tests/contract` collection fails in this environment (`typer` absent) —
  pre-existing, unrelated to WSR24 (no WSR24 import touches it); recorded in
  VALIDATION.md.

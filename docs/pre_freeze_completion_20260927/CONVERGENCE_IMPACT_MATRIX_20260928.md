# Controlled Convergence — Impact Matrix & Adjudication (Muse XHIGH)

Convergence merge: `muse-xhigh/full-completion cb185e58` =
independent baseline `164f166b` + canonical `origin/main 933d5df5`
(PR #278 successor + PR #279 provider readiness).
Independent history preserved; no rebase; no wholesale ours/theirs.

`SB_INDEPENDENT_BASELINE` = `164f166b`. Everything after is
`CONVERGED_SHARED_PROJECT_WORK`.

## 1. PB-03 adjudication: BOTH_VALID_DIFFERENT_SCOPE, executions added

- Main RESOLVED the classification half (mechanism families from required
  events + per-candidate capability attribution; prefix hardcode gone).
- This lane independently reached the same classification (dimension tiers
  + admission table) AND executed rows main leaves BLOCKED: 9 Tier-1
  obligation executions (PASS) + 3 Tier-1 characterizations + 8 Wave-2a
  duality characterizations, all with fresh runtime evidence.
- No contradiction: main claims no executions for these rows. The converged
  column carries main's classification for unexecuted rows and this lane's
  executions where they exist (via positive fixture receipts, §4).
- The 11 modeled-projection rows from WSR25 remain projections on both sides.

## 2. PB-05 adjudication: DIFFERENT_CANDIDATE_SCOPE

- Main RESOLVED PB-05 for the fork lane (Forge PR #4 `d5bd22d1`, present in
  this lane's forge repo; build-derived commit/tree/dirty/source/verified;
  Forge AF00 PASS on that lane).
- This lane's pristine run (`a37a865a` + `4753bb7c`) still binds via
  `env:FORGE_ENGINE_SHA`: PB-05 stays OPEN on the pristine lane by design
  (the pristine bridge predates the provenance repair).
- No contradiction: different artifacts, different verdicts, both recorded
  without collapsing Forge identities.

## 3. PB-09 adjudication: OPEN — RESERVED (Coordinator), technically advanced

- The Coordinator question (upstream `a37a865a` vs fork `ef958ee9`) is
  untouched by this lane.
- New technical facts for the packet: pristine upstream materialized
  (`4753bb7c`, zero Rules-Core drift vs `a37a865a`), launched, handshake
  binds `engine_commit=a37a865a`, real 4P lifecycle PASS. Pristine bridge
  lane limits (measured, not asserted): exactly-4-players
  (`PLAYER_COUNT_UNSUPPORTED` elsewhere), no seed (`SEED_UNSUPPORTED`),
  no partner. These are bridge-version facts at the pin, not engine claims.

## 4. PB-10 vs main's receipt gate: CONVERGENT

- Main independently retired the same name-mention promotion defect (citing
  HIDDEN_02 explicitly) via persisted positive receipts. This lane's four
  demotions (LIB-YES, OWNED-3, HIDDEN_02, ELIM-4) match main's column
  exactly (all four non-PASS on main). Two mechanisms, one verdict.
- Converged rule: credit requires a positive fixture receipt; this lane
  authors receipts for its executed rows (§4) instead of a parallel map.

## 5. Convergence impact matrix (main changes vs independent baseline)

| Change | Class | Disposition |
|---|---|---|
| Pins (`rules_engines.json` commits) | NO_SEMANTIC_IMPACT | verified identical (xmage `b1959698`, forge `a37a865a`/`4753bb7c`) |
| Receipt 1.3.0 shape (both claim 2026-09-25/`8d860e45`) | EVIDENCE_ONLY | main's shape adopted; 09-28 live reverify preserved in state/packet |
| Assembler receipt gate + `receipts.py` + `run_native_suite` receipts | HARNESS_ONLY | adopted; my positive-map layer retired in favor of authoring receipts |
| Mechanism classifier + per-candidate attribution (runner) | HARNESS_ONLY | adopted; my forge-UNKNOWN branch + env overrides retained |
| Seed observed-binding (no asserted `engine_owned`) + capability-gated send | BRIDGE_SEMANTIC_IMPACT (harness) + EVIDENCE_ONLY | adopted; my CAPABILITY_ABSENT mapping retained |
| START-2/cardinality observed-state + all-or-nothing | HARNESS_ONLY | adopted; my capability branch retained |
| `validate_principal_scoping` + actor-safe identity + redactor repair | BRIDGE_SEMANTIC_IMPACT | adopted; triggers requalification of hidden-info-adjacent evidence (§6) |
| XMage generic-lane leak finding (AF05 FAIL, demonstrated) | RULES-adjacent EVIDENCE_ONLY | accepted as trusted input; my native tests use full-game lane + engine-direct readback (unaffected path, re-verified by rerun) |
| Forge AF03 FAIL (commander legality gap) | EVIDENCE_ONLY | accepted as trusted input; not re-proven here |
| Forge seed PARTIAL (fork lane, state-bound) | EVIDENCE_ONLY | accepted; distinct scope from pristine `SEED_UNSUPPORTED` |
| Corpus 12/29, CARD_02 UNKNOWN (PB-07 open) | EVIDENCE_ONLY | accepted; no corpus work in this lane yet |
| Forge PR #4 provenance (PB-05 RESOLVED fork lane) | PIN/IDENTITY_IMPACT | accepted; object present locally; pristine lane stays env-bound |
| PB-09 fork-vs-upstream question | UNKNOWN (reserved) | untouched; technical facts added only |
| Donor evidence re-run 4/44/59 | EVIDENCE_ONLY | supersedes my transplant copy; my recompute re-targeted ( §7) |
| `mid_game_mechanisms` + `lifecycle.py` + `semantic.py` + `af03.py` | HARNESS_ONLY | adopted |

## 6. Requalification owed by the merge (bridge bytes changed)

- Full `engine-bridge` `mvn verify` (ActorSafeIdentity, Session, Redactor,
  GameManager changed): all 330+17+8+8 native tests re-run. My Tier-1/2
  executions must re-pass on the rebuilt bridge or be re-tiered honestly.
- Python suite on the merged tree (imports, receipts, runner, assembler).
- Hidden-info-adjacent claims re-examined against the leak finding (my tests
  use full-game lane + engine-direct paths; the generic-lane defect does not
  touch them, proven by rerun, not by assertion).
- Unaffected retained evidence: donor transplant history, WSR22 impact
  adjudication, PB-03/PB-09/PB-10 analysis docs, pristine worktree build,
  4P pristine lifecycle (bridge-unchanged on Forge side; Lab runner changes
  adjudicated non-impacting for that column).

## 7. Re-targeted recompute

My Wave-1 recompute transformed donor rows; main superseded the donor column
(4/44/59). The recompute script is re-targeted at main's column: Tier-1/2
executions re-apply as positive fixture receipts (canonical mechanism);
demotions are already convergent (no-ops); Tier-2/3 admissions annotate with
dimension specificity where main's reasons are mechanism-only.

## 8. Remaining Coordinator gates (unchanged authority)

`PRODUCTION_PROVIDER = NOT SELECTED`. `ARCHITECTURE_FREEZE = NOT CLAIMED`.
Next gate remains `COORDINATOR_PROVIDER_SELECTION_REQUIRED` once the converged
column is decision-grade.

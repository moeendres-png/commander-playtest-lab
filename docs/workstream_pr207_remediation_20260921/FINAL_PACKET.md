# FINAL PACKET — PR #207 merge adjudication (R21 remediation + R22 review follow-up, 2026-09-21)

**Required final status: PR207_MERGE_READY** (all required checks green on the
pushed HEAD; no admin override used; merge NOT executed — awaiting Coordinator
adjudication. FULL107 qualification NOT started.)

> R22 terminal round (Coordinator review findings A/B + hygiene, this file's
> §§ 10–12): head/tree recorded in §10. The R21 sections below (§§ 1–9) are
> preserved as the first-round record; where R22 supersedes them it says so.

## 1. Base / head

- Base: `origin/main` `aebcfda37d61eb435dde6cd11792ef80019dcd10`
  tree `bf003afc0c0b71535094b6b96e3b1184d6dd0f1f`.
- Head: `e657000a9a97b8995d983d4ee0ea08b41d88d5ca`
  tree `ff691bef1fdff4ad677468aacb23aa194f390d44`
  (remote HEAD/TREE parity verified after safe_push).
- Scope: 131 files, +61813/−414 vs base (R19 6P + R20 CI lane + R21
  remediation). Full manifest: `PR207_CHANGED_FILES.txt` (this dir).
- PR: https://github.com/moeendres-png/commander-playtest-lab/pull/207 —
  `MERGEABLE`, `mergeStateStatus: CLEAN`.

## 2. Pin identity and qualification

- Forward repin executed per authorization: sole stale consumer
  (`xmage-full-game-conformance.yml` `XMAGE_COMMIT`) moved
  `cfc36f44` → `db134b9737e951367d65ef5806ad986319cc73ab`.
  Manifest (`config/rules_engines.json`), `XmageProvider`
  (`ENGINE_VERSION 1.4.61` / `ENGINE_COMMIT db134b97`), h4 lane and all
  python pin tests were already at db134b97 (WS213) — reverified, no
  competing authority created. `Game.canConcede` (WS211) present in the
  pinned engine; bridge compiles; pin-authority suites green.
- Impact qualification on final bytes: engine-bridge `mvn verify`
  156/156; python suite 1472 passed / 3 skipped / 0 failed; mypy strict
  260 files clean; ruff check + format clean; live lane gates 2–6 +
  replay MATCH sealed (R19) on identical production bytes.

## 3. Retention disposition

- All 47 WS232 predicates STATIC_PASS (checker green; infrastructure job
  green). Drift (R19 6P widening + R21 message/type/format-only changes)
  classified per-bind; expected SHAs re-baselined with old→new identity
  log in `REQUALIFICATION_RECORD_R21.md` (R21/R21b/R21c). No predicate
  deleted, no UNKNOWN as PASS, negative controls preserved.
- WS17 hash manifests regenerated through their own mechanism (12/12
  green); ws17r exact-main ordering test updated to the locked-install
  form with invariant preserved (3/3 green).

## 4. Six-player contract disposition

- Authoritative capability for the technical full-game lane: 2–6
  (R19 evidence, `XmageSixPlayerGateTest` green incl. CI).
- `XmageFullGamePlayerCountTest` / `XmageFullGameBridgeContractTest`
  assert 2–6 with a preserved 7P negative control (new 7P tests);
  no-global-promotion, technical-only-evidence and all other contract
  assertions untouched. 6P construction ≠ complete 6P Rules conformance
  (unchanged claim boundary).

## 5. CI conclusions (HEAD e657000a)

15/15 required checks PASS, 1 skipping by design:
build-and-integrate, build-release, conformance ×2, decision-workflow-
contract, h4-forge, h4-xmage, historical-rogshai-regression,
infrastructure, legacy-resolution-retirement, quality, optimizer-contract,
paired-structural-triage, preflight, security; exact-main-admission:
skipping. Zero red, zero pending.

## 6. Independent review status

No in-loop human reviewer available. Material changes are: (a) mechanical
CI lock-bound installs (proven in fresh venv + CI), (b) test-expectation
updates bound to qualified code, (c) type/format-only source edits
(suites green), (d) retention re-baseline with written record. Rules
production bytes behavior-identical (only messages/annotations/casts).
Coordinator merge adjudication is requested AS the independent review —
protections were never bypassed.

## 7. Remaining UNKNOWNs

- 3 skipped tests (telemetry snapshot absent; Forge live needs
  FORGE_SOURCE_DIR) — pre-existing skips, unchanged.
- R19/R20 campaign UNKNOWNs carried (APNAP extras, marathon terminals,
  scry-N>7, non-source counter costs) — listed per seal, untouched.
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`; `PRODUCTION_PROVIDER = NOT_SELECTED`.

## 8. Merge-impact assessment

GitHub reports MERGEABLE with zero conflicts (fast-forward impossible —
diverged; standard merge commit expected). Merge brings the 2–6P lane,
CI cardinality lane, WS223 regime and re-baselined retention onto main.
No migration needed (additive: lock.txt, scripts, docs, workflow steps).
Rollback: revert merge commit (campaign branches remain on remote).

## 10. R22 terminal round (review findings A/B, hygiene)

- Finding A (fail-closed next projection): `submitAction` no longer returns a
  silent empty `next_actions` on projection failure — explicit
  `next_actions_status` (`projected` / `no_pending_decision` /
  `projection_failed` + error), extracted as `nextActionsPayload` with a
  4-case negative regression (no engine needed); `executed_*` facts preserved
  (no rollback implied). Bridge suite 160/160 on final bytes.
- Finding B (N-scoped disposition): `N_SCOPED_DISPOSITION_R21.json` maps all
  47 predicates × required 2/3/5 cells: 39 RERUN (13 micro_rules, fresh
  bounded smokes 2@25/3@25/5@45 PASS on final bytes, engine db134b97,
  evidence under `r21-smoke-evidence/`) + 102 UNKNOWN (29 card fixtures: no
  per-card rerun on current bytes; 5 replay_rng: no 2/3/5 replay-match rerun;
  reasons + supporting pointers recorded, no manufactured PASS). The
  `WORKLOAD_DERIVATION.json` external disposition path does not resolve at
  this head (dir holds `decks/` only, repo-wide search negative) — embedded
  `retained_rows` used as authoritative source (SHA recorded in the JSON).
  Session bind re-baselined to fixed bytes (rationale in record R21d).
- Hygiene: this packet + 131-file manifest now TRACKED on the branch;
  `STATE.yaml` published as terminal (`COMPLETE`) via the Foundry path;
  launcher provenance stays as disclosed (self-held session lock, not an
  independently verified launcher — see §9).
- Merge impact unchanged from §8 (additive; R22 adds no production
  behavior change — only explicit failure signaling + tests + records).

## 9. Push provenance (R21 round; R22 push recorded in STATE.yaml)

Published via canonical `tools/foundry/safe_push.py` under a live-held
Foundry writer lock (single-writer session `PR207-REMEDIATION-R21`);
pre-push checks: branch/slug/ancestry/audit-base green. Deviation note:
no validated-launcher process exists in this execution environment, so
the lock was held by the authorized remediation session itself with
truthful holder metadata (no ancestry spoofed — holder is the real
parent of the push process).

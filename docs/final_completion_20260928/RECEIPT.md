# Final-completion evidence receipt — Space Bunny MAX, 2026-09-28

Machine-readable companions: `RECEIPT.json` (this directory) and
`EVIDENCE_SUMMARY.json`. `artifacts/xmage-full-game/EVIDENCE_RECEIPT_20260928.json`
covers the cardinality, conformance and hidden-information artifacts.

**Raw artifacts are not committed.** The per-decision engine transcripts are
8–15 MB each (~57 MB total). They are deterministic outputs of the recorded
commands and seeds, so this directory keeps compact summaries carrying every
evidentiary field, plus each raw file's exact `sha256` in
`EVIDENCE_SUMMARY.json#/raw_artifacts_sha256`, so a regenerated artifact can be
verified byte-for-byte.

`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.

## Source lock

| Field | Value |
|---|---|
| Repository / branch | `moeendres-png/commander-playtest-lab` / `sbmax/full-completion` |
| Lab HEAD at evidence capture | `c4224fd4d73a5d3ad20173a9bab1cc527b4ffbdb` |
| XMage pin (`config/rules_engines.json`) | `b19596980f2734496ea1896504253e1bdd2756dd` |
| Engine artifact sha256 (`org.mage:mage:1.4.61`) | `bccb4031a586feb3e6636f1c7f11f3bbd3f35deb6ef4361daa005b7ad4695961` |
| Bridge artifact sha256 | `be972d604b7663318c10734dd4f739771de6c0f7578c586d8dd518ad44ffd6c5` |
| Bridge classpath manifest sha256 | recorded in `artifacts/xmage-full-game/EVIDENCE_RECEIPT_20260928.json` |
| Transport / decision protocol | `2.0.0` / `xmage-external-decision-protocol-1.0.0` |
| Lane | `xmage_full_game_external_pilots` |
| Evidence class | `technical_conformance_only` |

### Why artifact hashes are recorded and not just a version

The pre-existing local `org.mage:mage:1.4.61` artifact hashed
`1c347a65bc257b3c1488d680bdccf98f3b68f4e2827628c0386884f08d83cfa1` and was **not**
built from the pin. After rebuilding from a `git archive` of the exact pinned tree,
all 34 `org.mage` artifact hashes changed, to `bccb4031…` for the engine jar. A
matching version string is not identity; this is the same reasoning error
`docs/pre_freeze_completion_20260927/PB09_FORGE_CANDIDATE_IDENTITY.md` documents
for Forge, found independently for XMage. CI is unaffected: it checks out the pin
and verifies HEAD before every build.

The pin is also **not** an ancestor of `origin/master` nor of the campaign `mage`
worktree HEAD; it exists only on `origin/sol/rg06-hidden-state-restore-20260924`
and `origin/sol/rg06b-restored-morph-ability-suppression-20260926`. Building from
the worktree would have built the wrong engine while appearing to build the pin.

## What was executed

All items are `DIRECTLY_VERIFIED` runtime against the pinned engine, on a real
external process, with Lab external pilots as the only discretionary decision
authority. No tactical, structural, engine-AI, random or default fallback was
available or used.

### 1. Real-deck 4P terminal game — `terminal_single_20260923.json`

Four real 100-card Commander decks, seed `20260923`, external-pilot decisions only.

- `terminal: true`, `decision_count: 10826`, `winner_seats: [2]`
- 10 observed decision classes: `choice`, `choose_object`, `choose_use`,
  `declare_attacker`, `mana_payment`, `mode`, `mulligan`, `priority`, `target`,
  `target_amount`
- `hidden_information_actor_scoped: true`, `fallback_used: false`,
  `consumed_gameplay_evidence: false`, `holdout_consumed: false`

This reproduces the historical WSR23 real-deck record exactly (10826 decisions,
winner seat 2), now at the current pin.

### 2. Clean-process semantic replay twin — `replay_twin_20260923.json`

Two fresh processes, same seed.

- `semantic_replay_match: true`
- `raw_result_match: false` — expected; the raw payload embeds per-process
  identities that the semantic normalizer strips
- `bit_exact_replay_validated: false` — bit-exactness is **not** claimed

### 3. Process-isolated multi-seed batch — six `*.json` batch records

Six fresh processes, one game per process, no shared game state.

| Seed case | Status | Terminal | Decisions | Winner |
|---|---|---|---|---|
| 20260923 | completed | true | 10826 | 2 |
| 20260924 | completed | true | 10546 | 4 |
| 20260925 | completed | true | 5896 | 3 |
| 20260926 | completed | true | 8213 | 1 |
| 20260927 | completed | true | 6481 | 1 |
| 20260928 | completed | true | 13883 | 2 |

6/6 completed, 6/6 terminal, zero failures, winners spanning all four seats. This
is the process-isolation and multi-seed evidence; a failure or corrupt game
cannot silently contaminate a sibling, because each game owns its process.

### 4. Player-count conformance (recorded under `artifacts/xmage-full-game/`)

| Count | Status | Decisions | Decision classes |
|---|---|---|---|
| 2P | PASS | 12484 | 8 |
| 3P | PASS | 2071 | 8 |
| 4P | PASS | 4476 | 8 |
| 5P | PASS | 5953 | 8 |
| 6P | PASS (bounded) | 7284 | 8, first `declare_blocker` observed on this lineage, terminal |
| 7P | `FAIL_CLOSED` | — | unsupported player count refused |

2–5P conformance is established independently per count. 6P is bounded, not the
primary benchmark. 7P fails closed rather than degrading.

## Impact adjudication of this campaign's own production-path changes

The engine working-directory change is on a production-reachable path, so it was
adjudicated rather than assumed.

Pre-change and post-change code were both run at seed `20260923` and produced the
**identical** semantic transcript
`3de9c52095cbfd091ff445bb17ee9b39e65a2cf66678194ebb624e026e559c4d` over 10826
decisions. `raw_result_sha256` differs, as expected, because raw embeds
per-process identities. The change relocates engine runtime state only; it is
semantically neutral.

## Explicitly not claimed

- `PRODUCTION_PROVIDER` selection and `ARCHITECTURE_FREEZE` — Coordinator decisions.
- Bit-exact replay.
- Any `AF06`/`AF07`/`AF08`/`AF09` verdict: **no 107-row execution has been run on
  this lineage**, so nothing has been recomputed. The WSR22 107x2 results are not
  inherited; they were produced at a different HEAD before these changes.
- `legal_actions_supported` and `action_submission_supported` remain `false`.
  Decision-scoped enumeration is proven, and the payload says so honestly
  (`decision_scoped`, `global_capability_promoted: false`); a globally free-standing
  legal-action API does not exist and is not claimed.
- Any card-mechanism coverage claim beyond the 10 decision classes observed.

## Reproduction

```
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements/lock.txt
.venv/bin/pip install -e . --no-deps --no-build-isolation

# Build the engine from the EXACT pinned tree, never from a worktree checkout.
git -C <mage-clone> archive b19596980f2734496ea1896504253e1bdd2756dd \
  | tar -x -C <engine-build-dir>
cd <engine-build-dir> && MAVEN_OPTS=-Djava.io.tmpdir=<writable> mvn -DskipTests install

cd engine-bridge
MAVEN_OPTS=-Djava.io.tmpdir=<writable> mvn -B -ntp verify
MAVEN_OPTS=-Djava.io.tmpdir=<writable> mvn -B -ntp -DskipTests package

cd .. && export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -jar $PWD/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar full-game"
.venv/bin/python scripts/run_real_deck_gate.py single --seed 20260923 --out terminal.json
.venv/bin/python scripts/run_real_deck_gate.py replay --seed 20260923 --out replay.json
.venv/bin/python scripts/run_real_deck_gate.py batch --base-seed 20260923 --count 6 --out-dir batch/
for pc in 2 3 4 5 6; do .venv/bin/python scripts/run_external_full_game_conformance.py --player-count $pc; done
.venv/bin/python scripts/run_external_full_game_conformance.py --player-count 7 --expect-fail-closed
```

Environment notes for a sandboxed runner:

- `python -m pytest -q` requires a **clean tracked tree**;
  `src/commander_lab/tools/service.py` rejects canonical inputs when
  `tracked_worktree_dirty`, producing roughly 52 unrelated failures otherwise.
- `/tmp` may be read-only. Maven's JVM and surefire's forked JVM each need their
  own writable `java.io.tmpdir`; `MAVEN_OPTS` reaches only the Maven JVM, so
  `mvn verify` additionally needs `-DargLine=-Djava.io.tmpdir=<writable>`.
- **Never rebuild the bridge jar while an evidence run is in flight.** Replacing it
  underneath a running game produced a real `java.lang.NoClassDefFoundError`, which
  the batch runner then misclassified as a Rules conformance failure. Both problems
  are now handled, but the operational rule stands.

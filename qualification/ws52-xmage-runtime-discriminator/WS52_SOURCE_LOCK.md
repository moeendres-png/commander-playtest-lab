# WS52 — Source Lock (DIRECTLY_VERIFIED)

Status: `WS52_SOURCE_LOCK_VERIFIED` — no `AUTHORITY_GATE: ENGINE_PIN_CHANGE`.

Verification performed 2026-09-10 (UTC) by direct `git rev-parse` in the
WS52 worktree and read-only `git` plumbing in `/tmp/rq-xmage-src`.
No engine source was modified. No lock was mutated.

## 1. CPL candidate lineage (this worktree)

| Field | Value |
|---|---|
| Repository | `moeendres-png/commander-playtest-lab` |
| Worktree | `/home/moeen/code/ws52-xmage-runtime-discriminator` |
| Branch | `ws52/xmage-runtime-architecture-discriminator-20260910` |
| HEAD commit | `7c3e3d2af474cbf9cdda6f9dd694f68e5cdb2c10` |
| HEAD tree | `8dfc4bcbe65f1b3f43ef9805a6363343d137414b` |
| Working tree at WS52 start | clean |

HEAD and TREE match the contracted WS52 starting lock exactly.

## 2. Writer state

| Field | Value |
|---|---|
| `WS52_WRITER_COUNT` | `1` (exactly one live `opencode` process with this worktree as CWD, pid 175145; no other writer) |
| flock holder file | absent (`writer_lock.py check` reports `held: false`, `holder: null`) — the launcher Python process already exited, so no kernel flock is currently held; single-writer holds operationally by the scan (exactly one CWD occupant) and this session never bypasses the lock |
| Push protection | `GIT_CONFIG_VALUE_0=file:///dev/null/ws52-xmage-push-disabled`; remote push NOT authorized from OpenCode in this workstream |

## 3. XMage engine identities (discrepancy recorded, resolved without mutation)

Two XMage pins appear in the input evidence:

| Identity | Commit | Tree | Authority |
|---|---|---|---|
| RQ-X1 audit pin | `77d7646da6958fdf8125ee7c8f4aabd130d21d4c` | `f0a028b265f9c008ea0aedc4cec6b8f14500b69f` | RQ-X1 read-only audit + B4 bridge lineage (`config/rules_engines.json`) |
| WS49 candidate pin | `0c1f455ea8c8fa48ab9d638ad5068ec242800428` | `fdb8bf56a8bd8199a4ef372e468d93d6550b0649` | `candidate-qualification/ws49-xmage-v1.0.5/WS49_SOURCE_LOCK.json` + `successor_contract_v105.py` (`XMAGE_COMMIT`/`XMAGE_TREE`) |

Both commit/tree pairs were freshly re-verified by direct
`git -C /tmp/rq-xmage-src rev-parse <commit>^{tree}`:

- `77d7646d^{tree}` = `f0a028b265f9c008ea0aedc4cec6b8f14500b69f` (matches RQ-X1 lock)
- `0c1f455e^{tree}` = `fdb8bf56a8bd8199a4ef372e468d93d6550b0649` (matches WS49 lock)

Relationship (DIRECTLY_VERIFIED):

- `77d7646d` is an ancestor of `0c1f455e`
  (`merge-base --is-ancestor` = yes).
- The complete delta `77d7646d..0c1f455e` is exactly 6 files, all
  WS39/WS42 commander-history/state-restore work:
  `.github/workflows/ws39-retained-base.yml`,
  `Mage.Tests/.../CommanderPlaysCountStateRestoreTest.java`,
  `Mage/.../CommanderInfoWatcher.java`,
  `Mage/.../CommanderPlaysCountState.java`,
  `Mage/.../CommanderPlaysCountWatcher.java`,
  `foundry/ws39/README.md`.
- No decision-seam, RNG, hidden-information, replay, or identity
  file differs between the pins.

Authoritative ruling for WS52 (no mutation of either side):

- The WS49 candidate pin `0c1f455e` is authoritative for the
  candidate line under test. WS52 runtime evidence targets it.
- The RQ-X1 pin `77d7646d` remains the authoritative source of the
  read-only audit hypotheses. Because the delta touches none of the
  decision/RNG/hidden-info surfaces, RQ-X1 hypotheses transfer as
  CODE_DERIVED inputs (see `WS52_RQ_X1_TRANSFER.md`), re-verified at
  runtime where decision-critical.
- Neither lock is changed. No upgrade to XMage master.
  `AUTHORITY_GATE: ENGINE_PIN_CHANGE` is NOT triggered.

## 4. Execution policy (not candidate evidence)

Control plane `project/opencode-muse-cross-repo-hardening-v2-20260910`
terminal commit `ec68024593904b648fd03d2fb518bee94cfa4d3b`
(verified present in `/home/moeen/code/opencode-muse-cross-repo-hardening-v2`).
Execution policy only.

## 5. WS52 runtime build identity (to be sealed after build)

- Engine source export: `git archive 0c1f455e` from `/tmp/rq-xmage-src`
  into `/tmp/ws52-xmage-build` (pristine export, no `.git`, zero
  mutation risk to the RQ-X1 checkout).
- Engine build: `mvn -DskipTests install` of the required reactor
  modules (see build log `/tmp/ws52-engine-build.log`).
- Bridge: `engine-bridge` at WS52 HEAD + WS52-owned test surfaces only.
- Full build/runtime fingerprints are sealed in `WS52_EVIDENCE_SEAL.json`
  after the discriminator runs.

# MUSE LOCAL EXECUTION-READINESS SUPPORT HANDOFF — WS-49

Status: **SUPPORT LANE / NO GATE CREDIT CLAIMED**

This file is maintained by the parallel Muse support lane. It is a resume
pointer, not Source Authority. The authoritative WS-49 branch is
`ws49/xmage-v1.0.5-successor-qualification` (Draft PR #164); this lane never
writes to it.

## Source locks (freshly verified)

- Commander Lab authoritative WS-49 remote head observed:
  `47fb5aa6ac0362494d7e021b73ba1c405f8ca645`
  (`ws49: checkpoint construction remediation before fresh full107`)
- Muse support branch: `muse/ws49-xmage-local-execution-readiness`
  based on the exact remote head above (no divergence at creation).
- XMage fork: `moeendres-png/mage`
  branch `foundry/ws39-commander-history-state-restore`
  commit `0c1f455ea8c8fa48ab9d638ad5068ec242800428`
  tree `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`
  (commit + tree both reverified locally after checkout).
- WS-47 immutables unchanged and untouched (see WS49_SOURCE_LOCK.json).
- Java: `17.0.20` (`/usr/lib/jvm/java-17-openjdk-amd64`), Maven `3.9.12`.
- Isolated Maven repository: `/home/moeen/.m2-ws49-isolated`
  (outside both checkouts; default `~/.m2` was not used or trusted).
- Engine source checkout: `<support-worktree>/vendor/engine-source/xmage`
  (untracked build input, same relative layout as CI; never committed).

## Provisioning status: PASS (local execution readiness only)

Reproduced CI's exact provisioning (`ws49-xmage-v105-construction.yml`):

1. `git clone --depth 100 --branch foundry/ws39-commander-history-state-restore
   https://github.com/moeendres-png/mage.git vendor/engine-source/xmage`
2. `git checkout --detach 0c1f455e...` + commit/tree verification.
3. `JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 mvn -B -ntp -DskipTests
   -Dmaven.repo.local=/home/moeen/.m2-ws49-isolated install`
   in `vendor/engine-source/xmage` → **40/40 modules BUILD SUCCESS**.
   All three required artifacts installed:
   `org.mage:mage:1.4.61`,
   `org.mage:mage-deck-constructed:1.4.61`,
   `org.mage:mage-game-commanderfreeforall:1.4.61`.
4. `JAVA_HOME=... mvn -B -ntp -Dmaven.repo.local=/home/moeen/.m2-ws49-isolated
   verify` in `engine-bridge` → **BUILD SUCCESS, 60/60 tests PASS**,
   matching the CI result cited in WS49_CHECKPOINT_04.

No arbitrary engine version was substituted. Dependency resolution alone is
not claimed as qualification; bridge tests are local readiness evidence only.

## Reproducible local sequence (canonical script + WS-49 pins)

The canonical `scripts/bootstrap_engine_linux.sh` was kept and extended
additively (no default changed):

- new optional `COMMANDER_LAB_XMAGE_TREE` fail-closed tree verification
  (exit 4 on mismatch; no-op when unset, so historical callers unaffected).

WS-49 local provisioning via the canonical script:

```bash
ENGINE_PROVIDER=xmage \
ENGINE_SOURCE_PATH=<worktree>/vendor/engine-source/xmage \
COMMANDER_LAB_XMAGE_COMMIT=0c1f455ea8c8fa48ab9d638ad5068ec242800428 \
COMMANDER_LAB_XMAGE_TREE=fdb8bf56a8bd8199a4ef372e468d93d6550b0649 \
bash scripts/bootstrap_engine_linux.sh
```

then build/test with the isolated repository:

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
mvn -B -ntp -DskipTests -Dmaven.repo.local=/home/moeen/.m2-ws49-isolated install  # in vendor/engine-source/xmage
mvn -B -ntp -Dmaven.repo.local=/home/moeen/.m2-ws49-isolated verify               # in engine-bridge
```

Full command logs: `/home/moeen/ws49-muse-logs/`
(`xmage-install-02.log` = 40/40 BUILD SUCCESS;
`bridge-verify-01.log` = 60/60 PASS).

## Files changed on the support branch

- `scripts/bootstrap_engine_linux.sh` — additive `COMMANDER_LAB_XMAGE_TREE`
  fail-closed verification only (syntax-checked with `bash -n`; wrong-tree
  exits 4, correct/unset exits 0, tested against the real checkout).
- this handoff file.

Suitable for Terra review/cherry-pick: yes, both are isolated support
artifacts; neither touches semantics, providers, or immutable material.

## Authority questions (none blocking local readiness)

- None for provisioning. Any G49-08..G49-14 semantic question arising in
  Phase E will be recorded here as AUTHORITY_REQUIRED; no gate PASS will be
  claimed from this lane.

## Exact next action

Continue Phase E mechanical support (G49-08..G49-14 inventories/probes);
push the support branch only after configured approval, never merge it.

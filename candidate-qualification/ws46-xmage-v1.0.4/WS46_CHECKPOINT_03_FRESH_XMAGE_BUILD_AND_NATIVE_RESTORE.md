# WS-46 CHECKPOINT 03 — FRESH XMAGE BUILD + NATIVE RESTORE RUNTIME

## Status

`PASS`

This checkpoint closes WS-46 Phase 2. It grants **only** fresh XMage source/build/native-restore credit. It does not grant construction, behavior, AF04/05/06/08/09, provider qualification, AF07, or Architecture Freeze.

## Commander Lab execution source

- repository: `moeendres-png/commander-playtest-lab`
- branch: `ws46/xmage-v1.0.4-successor-qualification`
- execution commit: `e79283df3c9f0530cf0fb0115ca42f2d668da977`
- execution tree: `9d9dc2b1e13ea0b88f8edbe9566172ec250fec13`
- workflow: `.github/workflows/ws46-xmage-v104-build-restore.yml`

## Exact XMage source lock

Fresh checkout/build/runtime used exactly:

- repository: `moeendres-png/mage`
- branch provenance: `foundry/ws39-commander-history-state-restore`
- commit: `0c1f455ea8c8fa48ab9d638ad5068ec242800428`
- tree: `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`

The workflow verified commit and tree before runtime and verified the checkout was unmodified before the fresh build.

## Fresh build/runtime evidence

GitHub Actions:

- run: `34165017452`
- job: `101874241201`
- job name: `build-and-native-restore`
- conclusion: `success`
- fresh build step: `success`
- native cast-history + commander-damage restore runtime step: `success`
- exact test-execution proof step: `success`

Artifact:

- artifact id: `10033919163`
- name: `ws46-xmage-v104-build-restore-e79283df3c9f0530cf0fb0115ca42f2d668da977`
- digest: `sha256:d7d4c4e8822340f7856025bcd070e898f85deae5000a01702f71930af94c613c`

## Native restore proof

The exact candidate source was checked for both native state-restoration APIs before build:

- Commander cast-history restore: `CommanderPlaysCountWatcher.restoreStateForGameLoad`
- Commander damage restore: `CommanderInfoWatcher.restoreDamageStateForGameLoad`

Runtime then executed and proved exact successful Surefire results for:

- `org.mage.test.cards.commander.CommanderPlaysCountStateRestoreTest`: exactly `7` tests
- `org.mage.test.cards.commander.CommanderDamageStateRestoreTest`: exactly `2` tests
- total: `9`
- failures: `0`
- errors: `0`
- skipped: `0`

The Commander-damage test was installed only as a WS46 test overlay after the unmodified exact candidate completed its fresh build; the workflow asserts the overlay is the only XMage working-tree addition before test execution.

## Gate result

- Reconciliation v1.0.4: `PASS` (Checkpoint 02)
- Fresh exact XMage build/source lock: `PASS`
- Native Commander cast-history restore runtime: `PASS`
- Native Commander-damage restore runtime: `PASS`
- Construction: `0/107` fresh v1.0.4 credit
- Behavior: `0/107` fresh v1.0.4 credit
- `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

Historical v1.0.3 runtime credit remains exactly zero.

## Next exact action

Materialize and execute a fresh WS46 v1.0.4 construction qualification from record 1 through the complete immutable 107-record provider denominator, using native XMage state/readback and no request echo, heuristic legality, silent fallback, or historical PASS import.

# WS56 — Source Lock (DIRECTLY_VERIFIED)

Status: `WS56_SOURCE_LOCK_VERIFIED` — successor pin consumed exactly; no upgrade to master.

Verification performed 2026-09-11 (UTC) by direct `git rev-parse` in the WS56 worktree
and read-only plumbing in `/tmp/ws56-mage-successor-src` (detached HEAD, clean).
No XMage source was modified. No lock was mutated beyond the authorized successor pin.

## 1. CPL candidate lineage (this worktree)

| Field | Value |
|---|---|
| Repository | `moeendres-png/commander-playtest-lab` |
| Worktree | `/home/moeen/code/ws56-xmage-successor-requalification` |
| Branch | `ws56/xmage-successor-requalification-20260911` |
| HEAD commit | `7023cbdf533df82d59a50a83d16baf816edb7307` |
| HEAD tree | `e4122b510e7bb3018f72ef74ce4e8ffdc8ac9076` |
| Working tree at WS56 start | clean except `candidate-qualification/ws56-xmage-successor-requalification/WORKSTREAM_STATE.yaml` placeholder (untracked) |

HEAD and TREE match the contracted WS56 CPL source lock exactly (WS52 terminal).

## 2. XMage engine pins (old → successor)

| Identity | Commit | Tree | Authority |
|---|---|---|---|
| Old engine pin (WS52/WS49 candidate) | `0c1f455ea8c8fa48ab9d638ad5068ec242800428` | `fdb8bf56a8bd8199a4ef372e468d93d6550b0649` | WS52 source lock + WS49 `WS49_SOURCE_LOCK.json` |
| New successor pin (WS54 terminal, authorized experimental) | `7135d5e85ddb4c8aa4b49b4192ca51947c822704` | `ea193e0d04493d53d962ed13ebd3b5d2f68838c7` | WS56 contract; WS54 terminal `XMAGE_RNG_REEXECUTION_REMEDIATION_PASS` |

Verification (DIRECTLY_VERIFIED):

- `git rev-parse 0c1f455e^{tree}` in `/tmp/ws56-mage-successor-src` = `fdb8bf56a8bd8199a4ef372e468d93d6550b0649` (matches old lock).
- `git rev-parse 7135d5e^{tree}` = `ea193e0d04493d53d962ed13ebd3b5d2f68838c7` (matches successor lock).
- `git rev-parse HEAD` in `/tmp/ws56-mage-successor-src` = `7135d5e85ddb4c8aa4b49b4192ca51947c822704`.
- `git status --short --branch` in successor checkout = `## HEAD (no branch)`, clean (read-only).
- `merge-base --is-ancestor 0c1f455e 7135d5e` = yes (exit 0). Successor is a descendant of old pin.
- `git diff --name-only 0c1f455e..7135d5e` = 114 files (WS54 remediation: `GameRandom`, `Game`/`GameImpl` RNG authority, `Library.shuffle(Random)`, `Deck` LinkedHashSet, `PlayerImpl` game-scoped shuffle, target determinism, 51 card files, `SimulatedPlayerMCTS` non-Rules, plus WS54 tests/evidence).
- No upgrade to XMage master. No other pin consumed. XMage source is READ-ONLY in WS56.

## 3. WS54 terminal verdict consumed (not re-executed in WS56 Phase A)

- `XMAGE_RNG_REEXECUTION_REMEDIATION_PASS` (WS54 Final Report, `research/ws54-xmage-successor-requalification/` in successor worktree `/home/moeen/code/ws54-xmage-rng-reexecution-remediation-engine`).
- WS54 scope: per-game `GameRandom` authority, deterministic setup order, full call-site closure (UNKNOWN 0), cross-game isolation, non-Rules perturbation isolation, fresh-process reexecution at unit + game levels, 7/7 negatives.
- WS56 must requalify WS54's repair *through the actual CPL integration* (Phase B M5), not by assumption.

## 4. Writer / push policy

- Single writer: WS56 worktree branch `ws56/xmage-successor-requalification-20260911`.
- Push protection: `origin` push URL is `file:///dev/null/ws56-xmage-push-disabled`; remote push NOT authorized. No push, merge, rebase, squash in WS56.
- Local checkpoint commits only, after materially validated milestones.

## 5. RQ-C3 boundary

- RQ-C3 Rules authority is ready. WS56 does NOT execute the RQ-C3 First Wave.
- WS56 determines whether the successor architecture may enter that later candidate-neutral stage.

## 6. Credit / freeze (unchanged, repeated)

- `BEHAVIOR_CREDIT = 0/107`
- `FULL107 = NOT_RUN`
- `ARCHITECTURE_FREEZE = NOT CLAIMED`
- `PRODUCTION_PROVIDER = NOT SELECTED`

## Evidence class

All lock facts above are `DIRECTLY_VERIFIED`. Historical verdicts cited are `CODE_DERIVED` inputs until WS56 runtime requalification.

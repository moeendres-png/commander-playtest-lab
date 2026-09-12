# WS74 — Source Lock (DIRECTLY_VERIFIED)

Status: `WS74_SOURCE_LOCK_VERIFIED` — all pins consumed exactly; no upgrades.

## 1. CPL workstream lineage (this worktree)

| Field | Value |
|---|---|
| Repository | `moeendres-png/commander-playtest-lab` |
| Worktree | `/home/moeen/code/ws74-xmage-full107-construction-normalization` |
| Branch | `ws74/xmage-full107-construction-normalization-20260912` |
| Audit base (WS73 terminal) | `96db95dbc3a63d2a10d86e04c65443da617d4437` |
| Audit base tree | `07906c475a48bd6ed2bdd8c4422d488853d01c81` |

## 2. Full107 contract authority (WS47)

| Field | Value |
|---|---|
| WS47 commit | `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8` |
| Materialization | `qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json`, sha256 `0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3`, 135 records |
| Denominator | `qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json`, 107 IDs + 28 excluded (`CARD_01,CARD_03..CARD_29`) |
| Schema | `commander-lab.semantic-fixture-materialization/1.0.5` |
| Canonical bundle | `631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01` |

## 3. XMage engine pin (accepted successor, read-only)

| Field | Value |
|---|---|
| Repository | `moeendres-png/mage` |
| Checkout | `/tmp/ws56-mage-successor-src` (pre-existing WS56/WS72 checkout; no new clone) |
| Commit | `7135d5e85ddb4c8aa4b49b4192ca51947c822704` |
| Tree | `ea193e0d04493d53d962ed13ebd3b5d2f68838c7` |
| Remote | `https://github.com/moeendres-png/mage.git` |
| Tracked modifications | none (build `target/` outputs ignored, documented in receipt) |
| Old pin (absent) | `0c1f455ea8c8fa48ab9d638ad5068ec242800428` — successor descends from it; no 0c1f455e artifacts on the staging classpath; only `1.4.61` in the local Maven repository |

## 4. Bridge/provider lineage (CPL-owned, reused read-only)

- WS56 successor requalification terminal: `1dc43619eff5b71cf20405c5c8da83493ff52732db` (111/111 green at `7135d5e`).
- WS60 RQ-C3 First Wave terminal: `731891ec5ed8e7611fc9a636bab5fc3c400108eb` (14/15 PASS, filed 14/107 historical).
- Staging lane: `XmageGameManager` + `XmageBridgePlayer` (external-control) + `XmageActionExecutor.passPriority` (startup passes only), `XmageDeckImporter`. No bridge, provider, or engine source edits in WS74.

## 5. Writer / push policy

- Single writer: this worktree branch. Ownership: `candidate-qualification/ws74-xmage-full107-construction-normalization/` only.
- No XMage source edits. No shared provider semantic edits. No CPL files outside the owned directory.
- Remote persistence via `safe_push` only (dry-run first), with `--expected-audit-base-ref ws73/full107-contract-reconciliation-20260912`. Ordinary push, force, `--no-verify`, and writer-lock deletion are forbidden.

## 6. Credit / freeze (unchanged, repeated)

- `XMAGE_FULL107_BEHAVIOR_CREDIT=0/107`
- `FULL107_BEHAVIOR=NOT_RUN`
- `ARCHITECTURE_FREEZE=NOT_CLAIMED`
- `PRODUCTION_PROVIDER=NOT_SELECTED`
- RQ-C3 14/15 remains separate historical behavior evidence.

## Evidence class

All lock facts above are `DIRECTLY_VERIFIED`. Historical verdicts cited are inputs, not WS74 evidence.

# Muse unique value — final integration assessment

## Executive result

The Muse history contains real unique engineering value, but most of it is either already canonical or tied to older qualification/provider architectures.

The surviving unique value is concentrated in XMage PB-03 native-restoration tests.

No whole Muse branch should be merged.

## 1. Unique engineering that already survived into canonical project code

### Cross-repository Foundry hardening

`project/opencode-muse-cross-repo-hardening-v2-20260910@ec68024593904b648fd03d2fb518bee94cfa4d3b` is an ancestor of current main.

Disposition: **already canonical**.

### Governance / routing mechanisms

Several files from `governance/space-bunny-max-muse-xhigh-successor-20260927` are byte-identical on main, and the rest have later versions implementing the current authority model:
- Space Bunny MAX default/preferred;
- Muse XHIGH explicit alternate;
- no active Muse HIGH lane;
- normal owned-branch Git/GitHub authority;
- no mandatory `safe_push` ancestry gate.

Disposition: **already canonical or superseded by later stronger versions**.

### Privacy principle

Muse's project-data/private-data distinction survives in current `AGENTS.md`:
project technical data is permitted; unrelated private data and raw secrets are not.

The old Muse-HIGH-primary execution implementation did not survive and should not.

## 2. Unique Muse code ported during final salvage

### PB-03 dimension-admission discriminator

`XmagePb03DimensionAdmissionTest.java`

This is the cleanest immediately reusable Muse artifact.

It:
- reads the frozen PB-03 records;
- proves which records the native restoration seam can parse;
- pins exact fail-closed unsupported dimensions;
- does not turn construction into behavior credit.

It is ported onto `sol/muse-final-salvage-20260929`.

## 3. Unique Muse code already integration-ready on PR #284

### Tier-1 actual behavior

`XmagePb03Tier1RowsTest.java`

Contains genuine engine runtime coverage for combat, continuous effects, modes, prevention, replacement, costs, SBAs, triggers and multiplayer combat/blocking.

This is valuable.

Its current positive-credit path is not merge-admissible until the shared mana helper stops selecting an arbitrary sorted first source/pool offer.

### Tier-2 command-zone

`XmagePb03Tier2CmdZoneTest.java`

Contains genuine command-zone replacement characterization across graveyard/exile/hand/library yes/no paths.

Current #284 correctly does not auto-promote it to FULL107 PASS.

### Tier-2 control / turn

`XmagePb03Tier2ControlTurnTest.java`

Contains high-value genuine Control Magic owner/controller divergence and actual Time Warp/Nexus extra-turn ordering.

Its current credit depends on the shared mana helper and therefore remains gated.

### Tier-2 stack

`XmagePb03Tier2StackTest.java`

Contains high-value stack/priority/mana/copy/zone-change/multiplayer-priority tests.

Its `firstPoolSpend()` helper currently chooses sorted element zero and must be hardened before affected positive credit.

The Rules-RNG test is correctly fail-closed: it observes the real Heads/Tails choice and does not choose without a script.

## 4. Muse ideas independently solved better

### PB-10 source-name false credit

Muse independently found the defect, but the current receipt model is stronger:
positive credit now requires exact runtime receipts and a positive behavior assertion.

The old Muse assembler patch is not needed.

### WS49 source identity

Muse added an optional expected Git tree check.

Current exact Git commit verification already binds the tree, while current provider handshake/source-lock/receipt machinery additionally binds the actual runtime candidate. The Muse change did not protect the offline declared-source path.

No port.

### WS49 fallback-zero inventory

The static inventory was useful as review evidence but intentionally always returned zero.

Current runtime-negative tests and Meta Qualification are stronger.

No port.

### R11 replay/paired cumulative work

The historical local commit was never published and cannot be reconstructed byte-for-byte.

Later canonical work independently provides replay-tape v1, hidden-state semantic replay and cumulative L1→L7 runtime evidence.

No attempt is made to pretend the old commit itself was merged.

## 5. Muse code rejected

### WS48 old behavior driver

Rejected for current production/evidence use because:
- it is tied to obsolete Forge v1.0.5 overlay/pin assumptions;
- the behavior driver contains unscripted sorted-first option selection;
- one fresh-run negative-cause path also picks the first sorted payment option;
- current Forge dual-identity/provider evidence and runtime negative controls are stronger.

Historical design/postcondition ideas remain useful provenance.

### Old Muse-HIGH-primary execution policy

Rejected because current direct authority requires Space Bunny MAX default and Muse XHIGH-only.

## 6. Muse evidence retained only as provenance

### Generated PB-03 Wave results

Useful for discovering tests and mechanisms, but not current PASS credit.

### Pristine Forge PB-09 experiment

Useful as control/attribution context, but its engine identity was operator-supplied while PB-05 was open.

No provider capability credit.

## 7. Local-only / unavailable work

Historical Muse R11:
- reported `7ad4e944...`;
- no GitHub object or exact published descendant was found;
- exact bytes therefore remain `UNRECOVERABLE_LOCAL_ONLY`.

The intended replay capability has later canonical replacements.

## 8. Remaining integration dependency

There is no unidentified Muse asset left.

The only remaining useful code is known and already located:
the PB-03 Tier-1/Tier-2 test family on PR #284.

Before its behavior PASS credit is accepted:
1. remove/semantically justify arbitrary first mana-source/pool selection;
2. run exact current-head Maven tests;
3. derive fixture credit only from exact passing Surefire testcase receipts;
4. re-adjudicate against whatever PB-03/current-boundary implementation wins the active Space Bunny integration.

That is an engineering gate, not an inventory unknown.

## Final answer to “did we forget good Muse work?”

No.

Every discovered Muse branch and the 12-commit current donor have a terminal disposition.

The remaining high-value Muse PB-03 tests are explicitly preserved and integration-ready; they are not being discarded. Their behavior credit is intentionally blocked until the identified discretion issue is removed.

`MUSE_INVENTORY_COMPLETE = YES`

`MUSE_UNIQUE_CODE_ADJUDICATED = YES`

`MUSE_UNRESOLVED_UNKNOWN = NO`

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`

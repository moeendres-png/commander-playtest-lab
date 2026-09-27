# WSR20 Final Handoff — Forge FULL107 Common-Denominator Qualification

## Source Lock

- Execution repo `moeendres-png/forge`, branch
  `wsr20/forge-full107-common-denominator-20260926`, worktree
  `/home/moeen/code/ws-forge-full107-cdq-20260926` (sole writer).
- Audit base (verified, no drift at any stage): master ==
  `ef958ee91ac6c9ce0152189f2654bf6e05abf273`, tree
  `fc3387bf37aab19d780b2939a235309ed32b0492`.
- Content tip: `088c1a39a05f7809784dedddc760ac442304b0d1` (31 tests + mapping +
  packet + results + audit). Production-code delta vs audit base: NONE.
- Lab read-only authority: main `fa315da3`, merge `f133fe9d`, XMage runtime
  `59332671`, XMage pin `b1959698`, denominator `ws47 freeze @5a2e4f46`
  (107 items, materialization 1.0.5). Lab Forge pin `a37a865a` (ancestor of
  candidate ✓) with bridge source `4753bb7c`; provider decision
  NO_PROVIDER_READY (unchanged).
- Gate 0: five identities distinguished; historical binding (db134b97)
  preserved, not rewritten; no ranking.

## Work Completed

1. Gate 0 identity/provenance reconciliation (IDENTITY_ADJUDICATION.md).
2. Reuse-first adjudication: R9–R19 seals EXACT_REUSE (re-verified 213/213);
   wsc2 packet 23 PASS + 7 FAIL_CLOSED rows adopted (provisional XMage column
   replaced with canonical 15/13/54/25); wsc2a real-deck evidence adopted
   supporting (zero production delta); R19 FULL107=NOT_RUN preserved.
3. Missing execution: 31 new `WsR20Full107DenominatorTest` tests, 31/31 green:
   tax ladder {W}+{2}+{4}, 21-lethal/split/control damage, 8 zone branches,
   partner zone/tax, Rograkh first-cast, first-turn draw skip/grant, elim
   stack/ring/turn/owned/control, Fog prevention, Control-Magic revert,
   Crawler continuity, Humility/Anthem layers, Bolt/Growth stack, Surge
   exactness, face-up exile, Thoughtseize audience, generic scry, Time Walk
   extra turn, coin-flip call framing, 2/2 trade.
4. 107-item mapping (84 DIRECTLY_VERIFIED / 17 TECHNICALLY_CONFORMANT /
   3 NOT_RUN_BLOCKED / 3 UNKNOWN), machine-reconciled.
5. Common-fixture successor packet: 101 fixtures with Forge/XMage evidence
   pointers, seed/tape/observation slots, non-comparable fields, and
   UNKNOWN_PENDING_RULES_ADJUDICATION verdicts (no winner labels).
6. Coordinator amendment: full read-only inventory (9 repos, ~220 worktrees)
   + safe_push special search + impact adjudication (INTEGRATION_AUDIT.md);
   WSR20 resumed without restart; no duplication (wsc2/wsc2a adopted).

## New Findings

- Commander tax formula (count*2) verified exact to {4}/count-3 live.
- Commander-damage attribution/21-loss/ring-cleanup verified, including
  cross-control identity persistence and split non-pooling.
- Zone-replacement branches all 8 green (incl. library-bottom via Condemn).
- London-tuck ship path fails LOUDLY by design (no quiet mis-tuck possible).
- Engine offers unexecutable casts in rare illegal states but refuses
  execution (applied≠executed) — harness now asserts both.
- Bridge frame order varies (target↔mana); harness settles both directions.
- Lone legal targets resolve forced with no frame (correct, G02-documented).
- No newer publisher remediation exists: main deleted (not moved) the #206
  hardening; strongest candidate remains #206 @80abaae6 (separate track).

## Changes

- ADD `forge-protocol2-bridge/src/test/java/forge/bridge/WsR20Full107DenominatorTest.java` (31 tests).
- ADD `forge-protocol2-bridge/wsr20-full107/` (13 deliverables).
- MODIFY nothing else. No production code, no workflows, no fixtures.

## Tests / Evidence

- JDK 21: 213/213 (existing) + 31/31 (R20) + 243/243 (full bridge) green,
  BUILD SUCCESS all modules.
- JDK 17 lane: full bridge run per CI matrix (log bridge-jdk17.log).
- No weakening/deletion/relaxation of any existing test (diff-verified).
- wsc2a real-deck evidence reused (4 decks, 240 decisions, twins, hidden-info).

## PASS / FAIL / UNKNOWN

- FULL107 Forge disposition: DIRECTLY_VERIFIED 84 / TECHNICALLY_CONFORMANT 17
  / NOT_RUN_BLOCKED 3 / UNKNOWN 3 (= 107).
- Actual-card direct count: 84 (every behavioral DIRECT is actual-card runtime).
- Player matrix: 2/3/4/5P DIRECT; 6P bounded support (extra-denominator);
  7P FAIL_CLOSED.
- Hidden-info: 13 DIRECT, 2 TC, 2 BLOCKED, 3 UNKNOWN (no leaks anywhere proven).
- RNG/replay: tapes + clean-process + hashes DIRECT; flip-call framed;
  predetermined-HEADS residual named.
- Forbidden-fallback audit: 7/7 families fail-closed green.
- Successor packet: 101 fixtures sealed.
- FAIL: none. All UNKNOWN/BLOCKED cells explicit with seam + next action.

## Remaining Blockers

- Technical: none (stop condition A met: all 107 explicit, claims evidenced,
  packet sealed).
- Publication: WSR20 remote push needs fresh fetch + ownership recheck at
  push time (publisher path noted unresolved Lab-side; Forge branch push is
  standard fast-forward, no bypass).

## Outputs

`forge-protocol2-bridge/wsr20-full107/`: WORKSTREAM_CONTRACT.md,
SOURCE_LOCK.md, IDENTITY_ADJUDICATION.md, FULL107_DEFINITION_BINDING.json,
FULL107_FORGE_MAPPING.json, EVIDENCE_REUSE_ADJUDICATION.md,
EXECUTION_RESULTS.json, HIDDEN_INFO_RESULTS.json, RNG_REPLAY_RESULTS.json,
MULTIPLAYER_RESULTS.json, COMMON_FIXTURE_SUCCESSOR_PACKET.json,
VALIDATION.md, INTEGRATION_AUDIT.md, FINAL_HANDOFF.md (this file).

## Dependencies Unblocked

- Lab-owned XMage-vs-Forge comparison can proceed on the 101-fixture packet
  (same-deck same-seed reruns + independent Rules adjudication).
- Coordinator publisher track can proceed on #206/b048d682 (separate).

## Exact Next Action

1. Verify JDK-17 lane green, commit VALIDATION.md + FINAL_HANDOFF.md (seal),
   fresh-fetch + ownership recheck, fast-forward push wsr20 branch.
2. Coordinator: run Lab-owned cross-engine adjudication from the packet;
   integrate publisher remediation separately. Do NOT merge Forge master
   from this workstream.

## Local / Remote Integration Audit (amendment section)

Condensed table (see INTEGRATION_AUDIT.md for full detail):

Repo | Worktree | Branch | HEAD | Dirty | Remote | PR | Unique local work | Classification | WSR20 relevance | Next action
forge | ws-forge-full107-cdq-20260926 | wsr20/... | 088c1a39 | clean | Y+2 | - | this workstream | INCOMPLETE→COMPLETE (local) | self | push after recheck
forge | ws-c2-... | wsc2/... | b24ce365 | clean | N | - | denominator packet | HISTORICAL_KEEP/REUSED | A adopted | keep
forge | ws-forge-real-deck-... | wsc2a/... | 4c427063 | clean | N | - | real-deck e2e | HISTORICAL_KEEP/REUSED | A adopted | keep
forge | forge | master | 8a41f4a1 | clean | Y b94 | - | local drift | SOURCE_DRIFT(local) | none | do not touch
cpl | ws-csn-r9-... | wsr9/ws241 | 80abaae6 | clean | N(=PR) | #206 OPEN | PR bytes | REINTEGRATE_ON_CURRENT_BASE | B separate | Coordinator (no merge as-is)
cpl | (cpl/r10 branch) | cpl/r10-... | b048d682 | clean | N | - | R7 stack + safe_push | REVALIDATE_THEN_PUBLISH | B separate | revalidate+publish
cpl | muse-ws48 | muse/ws48 | 895eca21 | 1? | Y a57/b18 | - | probe tooling | RELEVANT-SEPARATE | B | none
others | (dirty foreign worktrees) | * | * | dirty | * | - | others' work | DIRTY_RECOVERY_REQUIRED | none | do not touch

PUBLISHER_STRONGEST_CANDIDATE = ws241/safe-push-effective-target-20260916 @
80abaae66065c25b507e1d0eb49c838764fa61db (PR #206 head; no stronger newer
local remediation exists; main lacks the hardening).

UNPUBLISHED_VALIDATED_WORK = 6 items: cpl/r10 b048d682; forge wsc2 b24ce365;
forge wsc2a 4c427063+8f0e2b23; cpl muse-ws48 895eca21; cpl camp/rg-closure
ca8950e5; forge wsr20 this workstream.

DIRTY_RECOVERY_ITEMS = 5 material (xmage-ws49-baseline 7M; ws50 51U;
ws49-canonical 1M; ws-l6-rg05 1M+1U; main Datenpaket U) + ~15 trivial.
All foreign: untouched.

REMOTE_PRS_TO_CLOSE_AS_SUPERSEDED = none directed.

REMOTE_PRS_REQUIRING_REINTEGRATION = PR #206 (stale; do NOT merge as-is).

WSR20_REUSED_EXISTING_WORK = R9–R19 seals; wsc2 23+7 rows; wsc2a evidence;
WS233/WS227/R15/R16/WS202/216/217 suites.

WSR20_DUPLICATE_WORK_AVOIDED = packet rebuild; real-deck re-execution;
XMage regeneration; publisher remediation.

ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED

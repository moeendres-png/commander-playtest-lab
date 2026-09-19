# Root Cause — Prepare DFC absence on pinned xmage-1.4.61

Verdict: `ENGINE_PIN_GAP` (pinned artifact predates card implementation).
No ENGINE semantic defect is claimed (unimplemented ≠ misimplemented);
no HARNESS/ADAPTER/FIXTURE defect found.

## Evidence

1. DIRECTLY_VERIFIED: 9/9 Prepare-creature DFCs resolve NULL on pinned
   xmage-1.4.61 in both `//` and front-face forms, while the DFC control
   (`Delver of Secrets // Insectile Aberration` → ISD 51) resolves —
   the lookup shape is sound.
2. CODE_DERIVED (reference source only, `moeendres-png/mage` worktree
   `/home/moeen/code/mage-d3q6`, read-only, NOT the pinned artifact):
   `Mage.Sets/src/mage/cards/b/BlazingFiresinger.java` exists as a
   `PrepareCard` with `EntersPreparedAbility`, introduced by commit
   `ba3a30bcc8 [SOS] Implement Blazing Firesinger`. The pinned Maven
   artifact (`~/.m2/repository/org/mage/mage/1.4.61`, also versioned
   `1.4.61` in mage-d3q6's pom) predates these SOS DFC implementations.
3. DIRECTLY_VERIFIED: unknown Prepare names fail closed at import
   (`UNKNOWN_CARD_NAME`, zero stored decks, zero games).

## Repair boundary

Engine repin (to an SOS-DFC-complete xmage version) plus full
requalification is owned by the engine workstream, not this one. This
workstream's repair surface (owned Lab tests + evidence) is complete:
fail-closed gates + confusion guards + honest NOT_RUN matrix.

## Intermediate diagnostic (HARNESS_SEQUENCING, repaired test-only)

First gate run showed `XMAGE_CARD_REPOSITORY_PREINITIALIZED_UNVERIFIED` /
`POISONED` because the test called `CardScanner.scan()` directly before the
importer's verified init — the importer's fail-closed B2 gate working as
designed. Repaired by ordering: verified importer warmup first, direct reads
after. No production change; 8/8 green after.

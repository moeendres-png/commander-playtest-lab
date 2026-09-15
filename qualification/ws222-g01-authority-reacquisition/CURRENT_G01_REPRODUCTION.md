# WS222 CURRENT_G01_REPRODUCTION

Independent reproduction of WS220 F-QUAL-02 on WS222 source lock
(HEAD `1a6ffcda`, tree `6bc707b3`). All reads DIRECTLY_VERIFIED in this
worktree; no WS220 prose trusted without re-read.

## Reproduction steps (rerunnable)

1. `qualification/manifests/AUTHORITY_LOCK_v1.json` full read:
   - `comprehensive_rules.status = AUTHORITY_IDENTIFIED_BYTES_UNAVAILABLE`
   - `original_sha256 = null`, `original_bytes_preserved = false`,
     `normalized_text_sha256 = null`
   - failure: official media URL reachable via browser/web extraction, but
     two raw-file download paths FAILED; no bytes fabricated (honest null).
   - `oracle.status = UNKNOWN`, `authoritative_oracle = UNKNOWN`; secondary
     sources explicitly not promoted (`secondary_sources_promoted = false`).
2. `qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json` machine read:
   135 fixtures; distinct `authority_refs` sets = exactly
   `{('AUTHORITY_LOCK_v1',)}` → 135/135 cite the gapped lock.
   - 29 fixtures carry non-null `card_identity` = the frozen 29-card corpus
     (CARD_01..CARD_29); remaining 106 are card-agnostic (player_count,
     multiplayer_commander, pilot_boundary(+negative), hidden_information,
     replay_rng, micro_rules).
3. `qualification/aggregate/GATE_RESULTS.json`: `G01 = FAIL`, `G13 = FAIL`
   (infrastructure materialization is not admission).
4. `data/cards/oracle_subset.json`: `authoritative_oracle_snapshot = false`,
   195 local-project cards, 17 of the frozen 29 absent → secondary cannot
   cover the denominator (correspondence only, never authority).
5. `data/cards/README.md`: subset is "a local project dataset, not a complete
   MTG Oracle database"; `project_inferred` entries must be replaced when a
   version-pinned authoritative snapshot is added.

## Verdict

`F-QUAL-02 REPRODUCED = PASS` (the blocker is real and current):
no byte-exact CR artifact, no authoritative Oracle basis, every behavior row
ungrounded at admission. Repair must satisfy S3 hard gates without promoting
secondary sources, without browser-text-as-bytes, and without waiver by
silence.

Machine companion: `CURRENT_G01_REPRODUCTION.json`.
Evidence class: DIRECTLY_VERIFIED (reads + counts executed in-worktree).

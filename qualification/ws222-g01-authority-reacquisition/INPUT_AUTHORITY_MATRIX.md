# WS222 INPUT_AUTHORITY_MATRIX

WS220 primary inputs consumed for WS222 (F-QUAL-02 + S3). Classification:
DIRECTLY_VERIFIED = read/executed in this worktree; CODE_DERIVED = source
facts derived from repository files.

| # | Input | Location | Finding (WS222 read) |
|---|-------|----------|----------------------|
| 1 | F-QUAL-02 | `research/project-audit/ws220/FINDINGS.json` | P1 EVIDENCE_RISK: no sealed domain-freshness artifact; CR bytes unavailable (sha null), Oracle UNKNOWN; all 135 fixtures cite the lock as `authority_ref`; aggregate G01=FAIL unreconciled; seals never assert freshness. Desired: byte-exact CR + authoritative Oracle (or Coordinator-scoped waiver) + sealed G01. |
| 2 | S3 | `research/project-audit/ws220/SUCCESSOR_PROPOSALS.json` | Objective: re-acquire byte-exact CR + authoritative Oracle (or ratified bounded waiver). Hard gates: successor lock sealed with non-null CR sha + authoritative Oracle (or ratified waiver); G01 verdict sealed. Forbidden: promoting secondary sources, browser-text as byte-exact, waiver by silence. Mutation surface: `qualification/manifests/AUTHORITY_LOCK_*.json` + acquisition tooling, no engine/pilot code. |
| 3 | Qualification audit | `research/project-audit/ws220/QUALIFICATION_AUDIT.md` | AF00–AF11 cover the right risks but standing is uncomputable; G01/G13/G14/G15 have no AF home; 29-card corpus has blind spots and no sampling rationale (F-CARD-01). WS222 does not change AF scope; it grounds G01. |
| 4 | Source-truth map | `research/project-audit/ws220/SOURCE_TRUTH_MAP.md/.json` + probe | Living authority: `config/rules_engines.json` pins, `docs/PROJECT_MISSION.md`, lane code, per-workstream seals (scoped). Filename traps noted. WS222 cites only verified paths. |
| 5 | WS220 handoff | `research/project-audit/ws220/FINAL_HANDOFF.md` | Audit COMPLETE (semantic); G01 re-acquisition flagged as possibly genuinely unobtainable upstream → Coordinator decision (waiver bounds or acquisition path). WS222 tests that hypothesis with bounded official-mechanism exploration. |

Machine companion: `INPUT_AUTHORITY_MATRIX.json`.

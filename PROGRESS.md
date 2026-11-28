# PROGRESS — thread "Restliche offene Pakete abschließen" (2026-11-27)

Branch: `claude/project-thread-gj8qzc` (agent defs + this file). Per-package branches below.

## Plan
1. Close #1864 #1865 #1868 #1745 after verifying on main.
2. PR #1888 (pool default): review, fix lint + tests 3/4, merge (owner handover in brief).
3. #1586 per-game progress. 4. #1856 draws in store (Option B). 5. #1703 schema-22 steps.
6. #1612 D-0/D-1/D-3 (plan on issue first). 7. #1662 acceptance list.
8. Owner templates: #1528 #1524 #1369 #1093/#1628 #1533. Closing summary on #1167.

## Decisions
- gh CLI token invalid in this container; GitHub via MCP tools only.
- #1888 belongs to a Gemini session (claim 19:27); owner brief explicitly hands it to this thread.

## Done
- 1: #1864 #1865 #1868 #1745 verified on 3495bc48 and closed.
- 2: PR #1888 review FAIL (5/6-seat default refused) -> fixed 8fd05cb9, delta PASS_WITH_NOTES, merged 33ea5f27. #1652, #1586 closed.
- 4/5: #1856 waits on Schema-22 cut; owner template on #1703 (rec. B: 22a migration machinery + draw columns, split = 23).
- 6: #1612 D-0/D-3/D-2 done; D-1 P2 by #1891 (other session); P3 re-warm + acceptance tests PR #1892 merged c513c209; #1612 closed (real-store timing UNKNOWN).
- 7: #1662 Part 2 gaps (3-step speed, single pass element) on feat/play-v1-pass-element-1662.
- #1524: audit package PR #1890 (review FAIL -> fixed -> PASS) merged 40ca4519; owner go for the 240-game run still pending.
- 7: PR #1893 (single pass element, 3-step speed, hold-to-confirm on click) reviewed; merge pending CI on bf096114.

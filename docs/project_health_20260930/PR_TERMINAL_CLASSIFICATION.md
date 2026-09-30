# Terminal PR classification (2026-09-30)

Every open PR in the three repositories was classified as one of `HISTORICAL`, `SUPERSEDED`, `DONOR_EVIDENCE`, `ACTIVE_DEPENDENCY` or `CLOSE`.

- **Closed PRs:** each carries a comment with the measurement behind its class.
- **Branches:** none was deleted, and every PR ref stays reachable.
- **Undo:** reopening a PR restores it unchanged.
- **Measurement:** ancestry and `git cherry` on a full (unshallowed) clone. Superseded content was checked against the named successor, not against name similarity.

## commander-playtest-lab

| PR | Class | Basis |
|---|---|---|
| #408 (issue) | closed, resolved | #411 (`8e07c9de`) delivered the producer, loader and wiring. Documented run: FULL107 XMage 5 → 14 PASS |
| #285 | DONOR_EVIDENCE | The head `b4ea7751` is a destructive tree collapse (2,096 files deleted). The real work at `4a56d179` is an ancestor on `sbmax/full-completion` |
| #287 | DONOR_EVIDENCE | Audit docs only. Its Forge question is forge#9, which is contained in forge#11 |
| #164, #163 | SUPERSEDED | v1.0.5 provider qualifications, replaced by v1.0.6 plus the current boundary. `ws47/…` is untouched |
| #158, #144, #142 | HISTORICAL | Completed contract lineage: v1.0.4 freeze, v1.0.0 freeze, CR/29-card authority |
| #153, #148, #147, #146, #143, #141, #140 | SUPERSEDED | Old pins or contracts. Each has a successor on `main` (cast-history restoration, midgame lane, WSR20/22 comparison) |
| #152, #137, #136, #135 | HISTORICAL | Completed workstreams on older pins. phase.rs is no longer a candidate |
| #128, #126, #122 | HISTORICAL | Pre-Simulator-Next lines (deckstrength gate, Structural seat audit, optimizer validation trigger) |
| #297, #299 | ACTIVE_DEPENDENCY → DONOR_EVIDENCE | Inputs to PB-09. They close once R-1 (`docs/coordinator_adjudication_20260930/`) is signed |

## forge

| PR | Class | Basis |
|---|---|---|
| #4, #5, #6, #9 | SUPERSEDED | Each head is an ancestor of the #11 head `bb0a740d` |
| #8 | SUPERSEDED | Targets `master`, which is never merged. The same question is answered by #9 inside #11. 3 donor commits remain on the branch |
| #10 | SUPERSEDED | #7 + #9 on an older base, unified by #11 |
| #11 | ACTIVE_DEPENDENCY | Forge candidate integration. Its admission is Coordinator R-1 |

## mage

| PR | Class | Basis |
|---|---|---|
| #11, #13, #14, #15 | SUPERSEDED | Each head is an ancestor of the candidate pin `9375f35a` |
| #12 | HISTORICAL | Routing/dispatch packets. Not in the pin |
| #16 | ACTIVE_DEPENDENCY | Carries the pin `9375f35a` plus 1 commit |

## Still open in the Lab after this pass

- **#297 and #299:** open until PB-09 is signed.
- **Live work:** PRs of the active lanes.

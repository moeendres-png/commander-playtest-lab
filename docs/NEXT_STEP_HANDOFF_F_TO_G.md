# NEXT STEP HANDOFF — F TO G

Date: 2026-08-08
Status: `PENDING_F_FINAL_CI_AND_MERGE`

## F result

Point F performed organizational cleanup only. No decklist, inventory quantity, allocation, opponent content, or simulation semantics were changed.

### Completed cleanup

- Audit E was completed before F and merged to `main` as `ae7be044fb9edc86ed353422dbc4e16766261ad2`.
- GitHub branch cleanup deleted 24 branches proven fully contained in `main`.
- 14 branches with exclusive commits were retained fail-closed.
- The stale/mixed Drive `00_LATEST` was archived under `99_Historical`; F did not invent a replacement release pointer.
- One proven-empty duplicate Drive folder `17_Mulligan_Lab` was permanently deleted.
- Obsolete/superseded 1.13.3 sync phases, old pretest/audit folders, stale canonical-entry material, and old repair/intermediate material were moved to historical areas rather than destroyed.
- `artifacts/audit/DELETION_LOG.json` and `docs/POST_CLEANUP_INVENTORY.md` record the cleanup evidence.

## Activation condition for G

G becomes authoritative only after this F evidence PR has:

1. public GitHub CI/quality/security = SUCCESS;
2. Release Artifacts = SUCCESS, including full tests, clean-tree assertion and recovery roundtrip;
3. Windows Runtime Hygiene = SUCCESS;
4. the F evidence PR is merged;
5. `main` ancestry is verified;
6. Drive receives the final F evidence with the exact merge commit;
7. this handoff is amended to `F_COMPLETE=true` and `G_READY=true`.

## G scope after activation

Point G should then work from the exact merged F `main` commit and focus on modeling quality rather than further general cleanup:

- high-impact Structural card-profile coverage, starting with Kaervek and relevant opponent cards;
- structural modeling gaps that materially affect deckbuilding decisions;
- opponent uncertainty without inventing observed data;
- meta knowledge refresh with provenance;
- adversarial pilot decision/golden scenarios for Korvold and RogShai.

## Carry-forward boundaries

- Structural Simulator remains structural evidence, not empirical win rate.
- Tactical Oracle is not an external rules engine.
- Real XMage/Forge validation remains pending.
- Real-playtest calibration remains inactive project scope.
- The 14 retained exclusive-commit branches are not current software truth; `main` remains authoritative.
- Do not modify canonical decklists or inventory/allocation in G without an explicit user decision.

F_COMPLETE: false
G_READY: false

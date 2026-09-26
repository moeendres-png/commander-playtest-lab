# NEXT STEP HANDOFF — F TO G

Date: 2026-08-08
Status: `AUTHORITATIVE_AFTER_SCOPE_CORRECTION_MERGE`

## F result

Point F is complete. It performed organizational cleanup only. No decklist, inventory quantity, allocation, opponent content, or simulation semantics were changed.

### Verified cleanup

- Audit E was completed first and merged to `main` as `ae7be044fb9edc86ed353422dbc4e16766261ad2`.
- GitHub branch cleanup deleted 24 branches only after proving each branch tip was already contained in `main`.
- 14 branches with exclusive commits were retained fail-closed for later semantic/historical review.
- The stale/mixed Drive `00_LATEST` was removed from the active surface and archived under `99_Historical`; F did not invent a replacement release pointer.
- One proven-empty duplicate Drive folder `17_Mulligan_Lab` was permanently deleted; the populated folder remains.
- Obsolete/superseded 1.13.3 sync phases, the old 1.13.4 pretest release folder, the superseded 2026-08-06 system audit, stale canonical-entry material, the historical external-engine-fix note, and old repair/intermediate folders were archived rather than destroyed.
- Key deleted branch names were searched in current repository content; no active code/document references were found for the checked canonical/release/data-sync branch names.
- `artifacts/audit/DELETION_LOG.json` and `docs/POST_CLEANUP_INVENTORY.md` contain the machine-readable and human-readable cleanup evidence.

### F verification

The F evidence head `5041aa0e51283c042e435306f0499d710761cdf5` passed all required public GitHub gates before merge:

- CI / quality / security: `SUCCESS`;
- Release Artifacts: `SUCCESS`, including full tests, clean-tree assertion, build, SHA-256 checks and recovery roundtrip;
- Windows Runtime Hygiene: `SUCCESS`.

The F evidence PR was merged as `80e894875497d088d3c48caf23b88a5c3b226c0d`.
The F closeout PR was merged as `618280095165e81eae8045945b05530491f2576e` after the same green gates.
Post-merge cleanup helper commits produced zero net file changes and removed their temporary workflow/branch; pre-correction `main` was `4f2ca55a917be9fccb79f6058a250886a9005cb6`, with final push CI and Windows Runtime Hygiene green.

## G scope

The authoritative G scope is the user-approved modeling-quality scope from the D–I sequence. G should focus on improving the parts of the Commander Playtest Lab that most affect deckbuilding decisions, without silently changing canonical decklists or inventory.

G should address, in priority order:

1. high-impact Structural card-profile coverage, beginning with Kaervek and relevant opponent cards;
2. structural model gaps that materially affect Commander deckbuilding decisions;
3. opponent uncertainty while strictly preserving `verified`, `observed`, `reported`, `synthetic`, and `unknown` evidence boundaries;
4. current meta/research knowledge refresh with provenance and without treating research/model estimates as empirical local win rates;
5. adversarial pilot/golden scenarios for Korvold and RogShai that test protection timing, wipe timing, stack interaction, engine-vs-threat decisions, finisher windows, rebuild, pod size, seat effects, and archenemy states.

G may make focused repository/code/test changes when required to complete those modeling-quality tasks, using the normal small-branch → tests → PR → CI → merge process.

## Carry-forward boundaries

- Structural Simulator remains structural evidence, not empirical win rate.
- Tactical Oracle is not an external rules engine.
- Real XMage/Forge validation remains pending for the later external-engine phase.
- Real-playtest calibration remains inactive project scope.
- The retained exclusive-commit branches are not current software truth; `main` remains authoritative.
- Strict-quality branches remain review candidates until useful exclusive typing work is adopted or rejected.
- Do not modify canonical Korvold, RogShai, Kaervek decklists, inventory quantities, or cross-deck allocations without explicit user instruction.

The earlier repository-only statement that G was restricted to Google Drive had no verified supporting direct-user instruction in the current project context and is superseded by this corrected handoff.

F_COMPLETE: true
G_READY: true

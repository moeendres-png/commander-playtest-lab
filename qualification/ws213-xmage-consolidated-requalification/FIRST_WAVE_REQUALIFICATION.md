# WS213 FIRST_WAVE_REQUALIFICATION

Matrix: 12 constructions (A03, B01, C01, C03, D06, E02, F01, G04, H01×3,
I01) × behavior primary+twin (500), setup primary+twin for the 7 qualified
(500), opening-hand twin probes, 3 different-seed controls, E02 combat-scan
ladder (6×500 + 3×3000 + 2×6000 + 2×6000-twins). All fresh JVMs. Raw runs
under `runs/` + `runs/MATRIX.json`.

Per-slot (behavior run; setup twins all TRUE; hidden-info 0 violations and
explicit binding everywhere):

| Slot | Outcome |
|------|---------|
| A03 | 500/500 budget; Bolt cast+resolved natively but P1 at 37 (objective needs life unchanged) → mechanism only, credit 0 |
| B01 | 500/500 budget; Wardens unassembled in budget → UNKNOWN, credit 0 |
| C01 | Twin-identical native activation failure at offset 175 (FoW underfunded by policy; pre-existing path) → credit 0 |
| C03 | Twin-identical native activation failure at offset 245 (Fireball underfunded); all 122 decision rows identical → credit 0 |
| D06 | 500/500 budget; Casualties uncast → UNKNOWN, credit 0 |
| E02 | Trample/double-block runtime proven (see COMBAT_E02); exact 2/1/4 unmet → credit 0 |
| F01 | Growth resolved (grave + library drop) but tapped-Forest unprovable from assertion → credit 0 (conservative) |
| G04 | Concede mechanism proven seat 3 (see CONCESSION_G04); Control-Magic setup unassembled → credit 0 |
| H01-HF | Humility + 1/1 Bear assembled; Clone never cast → credit 0 |
| H01-CF | Bear copy established (is_copy) but Humility never entered → credit 0 |
| H01-NH | **PASS (+1)**: copy choice offered+taken (choose_use Yes + choose_object Bear), terminal Bear-copy 2/2, twin-identical, see ledger |
| I01 | Bear/Blink unassembled → UNKNOWN, credit 0 |

A04/E01/G02/G03/J02 unattempted (no qualified setup, no pin-removed
blocker; recorded, not chased).

Machine companion: `FIRST_WAVE_REQUALIFICATION.json`.

# #1591: PLAY `skipForcedDecisions` — Echt-Engine-Abnahme und 3-Seed-Identitätsprobe (2026-11-24)

Refs #1591, #1558, #1623, #1792.

Alle Zahlen: lokale Messung am Owner-PC (`SIMULATED_RESULT`, kein CI-Beleg, keine Qualifikation,
Zustand `BRIDGE_AHEAD_OF_QUALIFICATION`, `covered_by_sealed_epoch: false`).
Lab-Stand: `main` `62f388d6a`, Bridge-JAR SHA-256: `c9bd21c9c9484c97d6a91e7510458a6b2c56bef25c642bf745bedcb23ab9ce76`,
Engine-Pin: `f4d12f6e8066203fba7aa38bd35ea3358117393d` (XMage 1.4.62), Java 21, Linux, 16 Kerne.

Tisch: Mensch an Sitz `0` (`precon/2026/lorehold_spirit`, deterministisches Testskript
`_scripted_human_answer` aus `tests/unit/test_human_seat_play_1169.py`) gegen Engine-KI an Sitz `1`
(`precon/2024/animated_army`), ausschließlich über die PLAY-Routen (`/api/games`, `/api/play/{id}`,
`/api/play/{id}/decision`), KI-Pause `0 ms`.

## 1. Echt-Engine-Test des Mensch-Sitzes mit Schalter

`pytest -v -rs tests/unit/test_human_seat_play_1169.py -k test_real_engine_human_seat_plays_a_game_to_its_end_through_the_play_routes`
mit `COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -Xmx3g -jar <jar> full-game"` (Studio ergänzt
`-Dcommanderlab.fullGame.skipForcedDecisions=true` über `interactive_bridge_command`): **1 passed in 38,44 s**.

## 2. Identitätsprobe (`skipForcedDecisions=false` gegen `true`, 3 Seeds, volle 64-Hex-Hashes + Frame-Folge)

| Seed | Schalter | Sieger | `decision_count` | Frames | `forced_decisions_skipped` | Live `forced_passes_answered_by_engine` (max / Proben) | Antworten Mensch | `semantic_transcript_sha256` | Dauer |
|---|---|---|---|---|---|---|---|---|---|
| 11 | aus | [1] | 899 | 899 | 0 | 0 / 0 | 357 | `d2314ebea1faabd55775b0abc1a6c707760939047ccf970e688b4dcd1dafa7b5` | 62,35 s |
| 11 | an | [1] | 899 | 617 | 282 | 282 / 507 | 357 | `d2314ebea1faabd55775b0abc1a6c707760939047ccf970e688b4dcd1dafa7b5` | 45,09 s |
| 12 | aus | [1] | 576 | 576 | 0 | 0 / 0 | 199 | `a588f7fe6ff1b9d574b724efdfa2bf30c357fd2a3f094ae11cf11d1d95cdb9ae` | 54,21 s |
| 12 | an | [1] | 576 | 530 | 46 | 46 / 361 | 199 | `a588f7fe6ff1b9d574b724efdfa2bf30c357fd2a3f094ae11cf11d1d95cdb9ae` | 41,93 s |
| 13 | aus | [1] | 428 | 428 | 0 | 0 / 0 | 158 | `d11acbd8d80ec36b629acdc434a1c4bf0b3f57bd63a4dd7cf8fc3f37c5abb434` | 34,53 s |
| 13 | an | [1] | 428 | 369 | 59 | 59 / 275 | 158 | `d11acbd8d80ec36b629acdc434a1c4bf0b3f57bd63a4dd7cf8fc3f37c5abb434` | 28,65 s |

## 3. Geprüfte Invarianten (`3/3` Seeds erfüllt)

- **Sieger, Entscheidungszahl, voller 64-Hex-`semantic_transcript_sha256`:** auf `3/3` Seeds identisch.
- **Mensch-Frames (`seat == 0`):** auf `3/3` Seeds nach Anzahl und `(turn, step, decision_class, chosen_labels)` exakt identisch (`357`, `199`, `158`).
- **Frame-für-Frame-Teilfolge:** auf `3/3` Seeds ist die Frame-Folge mit Schalter eine exakte geordnete Teilfolge der Folge ohne Schalter (`617 + 282 = 899`, `530 + 46 = 576`, `369 + 59 = 428`).
- **Ausgelassene Frames:** `100 %` der ausgelassenen Frames (`282/282`, `46/46`, `59/59`) sind ausschließlich KI-Prioritätspässe auf Sitz `1` (`[1, "priority", []]`); kein einziger Frame des Mensch-Sitzes wurde übersprungen.
- **Live-Zählung (#1792):** `forced_passes_answered_by_engine` wächst bereits während der laufenden Partie und erreicht im letzten Live-Snapshot exakt `forced_decisions_skipped` (`282`, `46`, `59`).

## Grenzen / `UNKNOWN`
- Gemessen auf 2-Sitz-Precon-Tisch bei KI-Pause `0 ms`; 4–6-Sitz-Tische und positive KI-Pause wurden in dieser Probe nicht separat gemessen (`UNKNOWN`).

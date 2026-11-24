# #1660 (S1): Echt-Engine-Probe `N = 20` (`1` gegen `4` Worker) und Bugfix Determinismus-Wächter (2026-11-24)

Refs #1660, #1656, #1720, #1721, #1754, #1785, #1803.

Alle Zahlen: lokale Messung am Owner-PC (`SIMULATED_RESULT`, kein CI-Beleg, keine Qualifikation,
Zustand `BRIDGE_AHEAD_OF_QUALIFICATION`, `covered_by_sealed_epoch: false`).
Lab-Stand: `main` `62f388d6a` plus PR #1803 (`a1ecebb32`), Bridge-JAR SHA-256:
`c9bd21c9c9484c97d6a91e7510458a6b2c56bef25c642bf745bedcb23ab9ce76`,
Engine-Pin: `f4d12f6e8066203fba7aa38bd35ea3358117393d` (XMage 1.4.62), Java 21, Linux, 16 Kerne.
Start-Last vor dem Lauf: `1-min-loadavg = 0,44` (`< 2`).

## 1. Gefundener und behobener S1-Defekt (PR #1803)

Beim ersten Echt-Engine-Lauf (`N = 20`) auf unverändertem `main` (`62f388d6a`) meldete
`series_guard` für beide Arme `unguarded: 20` bei `finished: 20`: `close_recorded_game` in
`src/commander_lab/studio/play.py` schrieb `semantic_transcript_sha256` zwar in den Log-Abschluss
(`closing`), gab das Feld aber nicht im zurückgegebenen `GameSummary`-Dict zurück, sodass
`SeriesRecord.record` im Pool-Pfad stets `None` ins Journal schrieb.
PR #1803 (`a1ecebb32`) ergänzt das Feld in `close_recorded_game` samt Unit-Test
(`test_close_recorded_game_propagates_semantic_transcript_hash_for_series_guard`, `149 passed`).

## 2. Echt-Engine-Probe `N = 20` (`1` Worker gegen `4` Worker, nach PR #1803)

- **Tisch:** 2 Sitze (`precon/2026/lorehold_spirit`, `precon/2024/animated_army`), `seat_styles = [0.25, 0.75]` (`!= 0.5`),
  `table_hash = e67bf3670f87db6cc353cc7f8c1e798ea8fe95ed090530607d0326c09f935c6f`, `skipForcedDecisions = true`,
  `games_per_jvm = 20`, Seeds `1–20`.
- **Pfad:** `plan_task` → `SeriesRecord.open` (`manifest.json`, `journal.jsonl`) → `GamePool.run(..., record=record)` → `series_guard` / `series_violation`.

| Kennzahl | Arm `1` Worker | Arm `4` Worker (`private_card_repository=True`) | Vergleich |
|---|---:|---:|---|
| Gestartet / beendet / fehlgeschlagen | 20 / 20 / 0 | 20 / 20 / 0 | `20/20` beendet |
| `game_key` identisch | — | — | **`20/20`** |
| Voller 64-Hex-`semantic_transcript_sha256` identisch | — | — | **`20/20`** |
| Sieger & Entscheidungszahl identisch | — | — | **`20/20`** |
| `series_guard.finished` / `unguarded` | 20 / **0** | 20 / **0** | alle 20 Partien bewacht |
| `series_violation` | `None` | `None` | `0` Verletzungen |
| Gesamtdauer | 103,19 s | 70,36 s | 1,47× schneller |

Stichprobe voller 64-Hex-Transkript-Hashes (identisch zwischen `1W` und `4W`):
- Seed `1`: Sieger `[0]`, `680` Entscheidungen, `game_key = 6b7dad5b982dd476…`, `semantic_transcript_sha256 = 9153ae7ba543a45eb431c206015476f178eef09a4a8bfedbd6190f1f1af73a48`
- Seed `2`: Sieger `[0]`, `1010` Entscheidungen, `game_key = f9191d404fc3bc14…`, `semantic_transcript_sha256 = 520cb3323fe650f252e3f310b9863499c6447e5cccd51465cf0715850e3b4e80`
- Seed `3`: Sieger `[0]`, `697` Entscheidungen, `game_key = 10fb082791da3aa9…`, `semantic_transcript_sha256 = b60f04ad12353cbf13c0af7f6739b79259635bfaf05144ad8f233cdb628c5d37`
- Seed `20`: Sieger `[0]`, `755` Entscheidungen, `game_key = 7b0722f94518db36…`, `semantic_transcript_sha256 = 9b326e943ababa9e1518c98b73cb617f48502b726b61529a27ed2aa2b63b09d3`

## Grenzen / `UNKNOWN`
- Gemessen auf 2-Sitz-Precon-Tisch unter Linux (`COMMANDER_LAB_STUDIO_SERIES_POOL` bleibt unverändert AUS). Natives Windows-`taskkill /T /F` bleibt `UNKNOWN`.

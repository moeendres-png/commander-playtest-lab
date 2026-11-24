# #1593 & #1578 (P-C): Echte Browser-Vorher/Nachher-Messung im PLAY-Modus (2026-11-24)

Refs #1593, #1578, #1558, #1634, #1644, #1655, #1789.

## Messaufbau

- **Browser:** Google Chrome `157.0.8103.80` (echter Browser, headless via DevTools Protocol gegen echten lokalen Studio-HTTP-Server auf isoliertem temporären Datenordner; keine Store-Kopie oder Rohdaten im Repository).
- **Engine:** echte XMage-Bridge (Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d`, XMage 1.4.62, Java 21, `skipForcedDecisions=true`, `BRIDGE_AHEAD_OF_QUALIFICATION`, `covered_by_sealed_epoch: false`).
  - Vorher-Stände (`b9d9cadf9`, `63b6fff8e`): Bridge-JAR `f0894620ee7c2b21e07e9f80c2fdbb23f6cd0155a1a739898485dd2f28271737` (6-Sitz-Handshake).
  - Nachher-Stand (`main` `62f388d6a`): Bridge-JAR `c9bd21c9c9484c97d6a91e7510458a6b2c56bef25c642bf745bedcb23ab9ce76` (8-Sitz-Handshake).
- **Tisch & Partie:** Mensch an Sitz `0` (`precon/2026/lorehold_spirit`) gegen Engine-KI an Sitz `1` (`precon/2024/animated_army`), Seed `11`, echte Seite `partie.html?game=<id>`. Jeder Lauf ist eine interaktive Partie mit einem Menschen (kein Simulationsergebnis).
- **Instrumentierung:** exakt das `window.__rt` / `window.__summary()`-Skript aus `docs/analysis-reports/play_polling_1578_20261124.md`, ergänzt um einen `MutationObserver` auf `#human-decision` für die Browser-Anzeigelatenz von `POST /decision` bis zur nächsten gerenderten Entscheidung.

## 1. #1578 P-C: Vorspulen (Vorher `63b6fff8e` gegen Nachher `main` `62f388d6a`)

Gleiche Partie (Seed `11`, `ai_delay_ms = 0`), „Vorspulen bis zu meiner nächsten Entscheidung“ (`#ff-btn`) aktiv, `45` menschliche Antworten (`POST /decision`):

| Kennzahl | Vorher (`63b6fff8e`, vor #1644/#1655) | Nachher (`main` `62f388d6a`) | Veränderung |
|---|---:|---:|---:|
| `posts` (`POST /decision`) | 45 | 45 | gleich |
| `state_gets` (`GET /api/play/{id}`) | 104 | 30 | **−71,2 %** |
| `held` (Long-Poll mit `wait_ms=`) | 36 | 22 | −38,9 % |
| `plain` (ungehaltene State-GETs) | 68 | 8 | **−88,2 %** |
| `plain` je `POST` | 1,51 | 0,18 | **−88,2 %** |
| `gap_ms_median` (Abstand zw. POSTs, n = 44) | 90 ms | 84 ms | −6,7 % |
| `post_ms_median` | 30 ms | 41 ms | +11 ms (enthält nun geschwärzten Stand) |

Lesart: `POST /decision` liefert den neuen Stand direkt zurück, sodass die Seite den bisherigen zweiten GET (`plain` je `POST`: `1,51 → 0,18`) einspart; die leichte Zunahme von `post_ms_median` (`30 → 41 ms`) ist das Einbetten des Standes in der POST-Antwort und wird durch den Wegfall der zusätzlichen GET-Roundtrips mehr als ausgeglichen (`gap_ms_median` `90 → 84 ms`, Gesamt-GETs `104 → 30`).

## 2. #1593: Long-Poll statt festem Abfragetakt (Vorher `b9d9cadf9` gegen Nachher `main` `62f388d6a`)

Gleiche Partie (Seed `11`), normaler interaktiver Betrieb ohne Vorspulen (`45` Antworten bei `ai_delay_ms = 0`; zusätzlich `35` Antworten bei `ai_delay_ms = 50`):

| Messung | Stand | `posts` | `state_gets` | `held` | `plain` | `gap_ms_p95` | `answer→render` p95 (n) |
|---|---|---:|---:|---:|---:|---:|---:|
| `ai_delay_ms = 0` | Vorher (`b9d9cadf9`, vor #1634) | 45 | 55 | 0 | 55 | 493 ms | 1724 ms (13) |
| `ai_delay_ms = 0` | Nachher (`main` `62f388d6a`) | 45 | **12** | **11** | **1** | **415 ms** | **1632 ms** (13) |
| `ai_delay_ms = 50` | Vorher (`b9d9cadf9`, vor #1634) | 35 | 44 | 0 | 44 | 591 ms | 1829 ms (12) |
| `ai_delay_ms = 50` | Nachher (`main` `62f388d6a`) | 35 | **10** | **9** | **1** | 673 ms | **1709 ms** (12) |

Lesart: Im normalen PLAY-Betrieb entfallen durch Long-Poll (`since`/`wait_ms` + `revision`) und die eingebettete POST-Antwort **77–78 %** aller State-GETs (`55 → 12` bzw. `44 → 10`) und **98 %** der ungehaltenen Polls (`55 → 1`, `44 → 1`); die p95-Zeit von der Antwort bis zur Anzeige der nächsten Entscheidung sinkt in beiden Läufen (`1724 → 1632 ms` bzw. `1829 → 1709 ms`). Kein Frame-Verlust bei Verbindungsabbruch ist durch die Unit-/Node-Tests aus #1634 (`test_human_seat_play_1169.py`) abgedeckt.

## Grenzen / `UNKNOWN`
- Gemessen an einem 2-Sitz-Precon-Tisch (Seed `11`, 1 Tab); Verhalten bei ~40 gleichzeitig offenen Tabs (Threadpool-Last) sowie 4–6-Sitz-Tische bleiben `UNKNOWN`.

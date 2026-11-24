# Q1-c (`#1666`): Echt-Engine-Serienbeleg für Reifegrad- und Evidenz-Anzeige (Verlauf, Diff, Kürzen/Tauschen)

- **Datum:** 2026-11-24 · **Refs:** `#1666`, `#1656`, `#1612`
- **Einordnung:** `SIMULATED_RESULT` (lokale Owner-PC-Echt-Engine-Messung unter Linux/WSL2 in einem temporären Studio-Store außerhalb des Repositories, Rohlogs nach dem Lauf entfernt, **kein Qualifikationsbeleg**; `AGENTS.md` §4).
- **Basisstand & Engine-Pin:** `main` @ `62f388d6a037e63c3eaad5975ab932448e6c1de0`, Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`config/rules_engines.json`), gemeldeter `bridge_jar_sha256` der Serie `ec53219322a25d0d7433e972051731d48115bcb4a9329b0a75713aeb3d10b938`, Bridge-Zustand `BRIDGE_AHEAD_OF_QUALIFICATION` (`covered_by_sealed_epoch: false`).
- **Pilot-Fingerabdruck:** `fp:51818f6859adb2aef8d79f879934f1e7efe6564a0be8fad1d2c896f0242b4a9f`.
- **Hinweis zu Mutation N6:** Die in `#1666` Kommentar 8 genannte Folge-Schärfung (`texts[2]` exakt `n/N 4 / 4 Paare (abgeschlossen / geplant)` je Serie) ist bereits über PR `#1776` auf `main` (`tests/unit/test_studio_maturity.py:848-886`) umgesetzt.

## 1. Fragestellung (offener Restpunkt aus `#1666` Kommentar 8)

Nach Paket 1 (`#1717`), Paket 2 (`#1729`) und der N6-Schärfung (`#1776`) blieb `#1666` ausschließlich offen, um einen Befund aus einer **echten gespeicherten Paar-Serie** über den vollständigen Studio-Weg (`POST /api/experiments` → echte XMage-Partien → `GET /api/decks/{id}/series` → Rendering durch `src/commander_lab/studio/static/deckseries.js`) sichtbar zu belegen.

## 2. Durchgeführte Echt-Engine-Serie (`n/N = 4/4` Paare, `8/8` Partien, `SIMULATED_RESULT`)

- **Deck & Stände:** `chulane-probe` aus `data/decks/deckbau/chulane_current.json`:
  - Basis (`main`): `chulane-probe@301251e2a48b5128`
  - Variante (`var-land-swap`, 1-Karten-Tausch `-1 Forest / +1 Island`): `chulane-probe@ff567869ff630f47` (`slot_alignment_state: "aligned"`, `swapped_slots: 1`)
- **Tisch (`table_size = 4`):** `precon/2026/lorehold_spirit`, `precon/2024/animated_army`, `precon/2022/token_triumph`, Zweck `confirmation`, `budget_pairs = 4`, `look_every_pairs = 4`, `first_seed = 2100`.
- **Serien-Ergebnis (`paired-1795548699-1-26bc8326`):**
  - `status`: `completed` (`abgeschlossen`), `counts_as_result: true`, `stop_reason: "BUDGET_EXHAUSTED"`
  - `pairs_completed / pairs_planned`: `4 / 4`, `pairs_censored: 0`, `games_completed: 8` (`tested_seats: [0, 1, 2, 3]`)
  - `table_size: 4`, `table_size_check: "consistent"`, `table_size_source: "aus Plan und gespielten Partien"`
  - `difference_pp: 0.0`, `decision_ci_pp: null` (bei `4` Paaren ohne trennbare Differenz bleibt das Intervall ehrlich `null`)

## 3. Reifegrad-Auswertung (`reifegrad`) und gerenderte UI-Texte (`static/deckseries.js`)

Die echte API-Antwort `GET /api/decks/chulane-probe/series` liefert für `paired-1795548699-1-26bc8326` unter `reifegrad.befunde`:

- **R0-Bedingungen:** `Serie zählt als Ergebnis` = `bestanden`, `Tischgröße an den gespielten Partien belegt` = `bestanden`, `Ergebnis auswertbar` = `nicht erfüllt` (`nicht auswertbar (nachweisbare Differenz unbekannt)` — fail-closed, weil `decision_ci_pp` bei `4` Paaren `null` ist).
- **R1-Bedingungen:** `Bestätigung mit intaktem Plan` = `bestanden`, `frische Seeds (disjunkt von jeder Erkundung des Decks)` = `bestanden`, `Holm angewandt` = `bestanden` (`holm_p = 1.0`, `niveau = 0.05`).
- **R2/R3-Bedingungen:** alle `nicht erfasst (UNKNOWN)` (`reifegrad.luecken`: Kontrollen, Karten-Kompetenzprüfung, Pilot-Audit und Owner-Annahme sind im Studio noch nicht erfasst; eigene Folgepakete nach Owner-Antwort 3a).
- **Stand-Bezug & Empfehlungsfähigkeit:** `stand.bezug = "aktuell"` (`Befund zum aktuellen Stand`), `empfehlungsfaehig = false` (`Reifegrad unter R2; Pilot-Fingerabdruck nicht aktuell oder unbekannt`), `data_class = "SIMULATED_RESULT"`.

Rendering derselben echten API-Antwort mit `src/commander_lab/studio/static/deckseries.js` (über `node`):

1. **Verlauf (`deckSeriesEvidence`):**
   `kein Reifegrad (Beleg fehlt)Ergebnis (simuliert): nicht auswertbar (nachweisbare Differenz unbekannt) · n/N 4 / 4 Paare (abgeschlossen / geplant) · Tisch mit 4 Sitzen (Zufallsbasis 1/4)Befund zum aktuellen Standnicht empfehlungsfähig: Reifegrad unter R2; Pilot-Fingerabdruck nicht aktuell oder unbekanntHolm-Familie: 1 Bestätigung(en) mit derselben Basis und demselben Tisch; eine spätere Bestätigung derselben Familie kann dieses Ergebnis zurückhalten`
2. **Diff (`deckSeriesDiffEvidence` für Basis ↔ Variante):**
   `Simulation zu diesem Vergleich (SIMULIERT)SIMULATED_RESULT: gespeicherte Serie genau dieser beiden Stände, nicht Teil der Tierliste und nie mit anderen Zahlen summiert.Serie vom 2026-11-24 19:31 · Tisch table · Tisch mit 4 Sitzen: A = Vergleichsbasis, B = geöffneter StandStand-Bezug des Befunds darunter: gemessen an main bzw. dessen direktem Vorgänger, unabhängig davon, welcher Stand geöffnet ist.kein Reifegrad (Beleg fehlt)Ergebnis (simuliert): nicht auswertbar (nachweisbare Differenz unbekannt) · n/N 4 / 4 Paare (abgeschlossen / geplant) · Tisch mit 4 Sitzen (Zufallsbasis 1/4)Befund zum aktuellen Standnicht empfehlungsfähig: Reifegrad unter R2; Pilot-Fingerabdruck nicht aktuell oder unbekanntHolm-Familie: 1 Bestätigung(en) mit derselben Basis und demselben Tisch; eine spätere Bestätigung derselben Familie kann dieses Ergebnis zurückhalten`
3. **Kürzen/Tauschen (`deckSeriesCardEvidence`):**
   `kein Befund (keine Serie je Karte gespeichert; unbekannt, nicht 0)` (wie in `deckseries.js:241-245` spezifiziert: Simulation ist je Paar gespeicherter Stände, nie je Einzelkarte).

## 4. Grenzen und `UNKNOWN` / `NOT_RUN`

- **Stichprobe:** `N = 4` Paare (`8` Partien), ein fester 4-Sitz-Tisch, 1-Karten-Landtausch an Chulane; durch `N = 4` und `difference_pp = 0,0` bleibt `Ergebnis auswertbar` ehrlich `false` (ein echter R1-Befund erfordert eine größere Serie mit nachweisbarer Differenz `y_pp`).
- **R2/R3:** Im Studio produktiv weiter unerreichbar (höchstens R1), bis Kontrollen, Karten-Kompetenzprüfung, Pilot-Audit und Owner-Annahme erfasst werden (eigene Pakete).
- **Browser / Windows:** Rendering wurde per `node` gegen `static/deckseries.js` geprüft; echter Browser-Klicklauf und natives Windows sind `NOT_RUN` / `UNKNOWN`.

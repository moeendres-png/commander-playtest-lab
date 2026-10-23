# Issue #978 — Precon-Varianten: Import + Pod-Sweep (Mess-Lane Muse, 2026-10-23)

**Ergebnis: 9/9 Varianten importieren, 8/8 Pods durchgespielt, 0 Fehler.** Die neun
Ersatzkarten-Decks sind am beauftragten Stand nicht nur importierbar, sondern in
echten 4er-Spielen spielbar. Keine Siegquoten in diesem Bericht (Test-Decks, keine
gedruckten Precons; Mandat der Issue).

## Source Lock und Integrität

- Lab `b9936e94` (Worktree, detached), Pin aus `config/rules_engines.json` an diesem
  Commit: **v12 `4da83f6267907798e5527c3e5f8a0bd3579ff993`**.
- Bridge-JAR lokal aus dem Fork am Pin gebaut (Fork-Module installiert, Bridge im
  Lab-Worktree gepackt; kein Bridge-Code geändert): sha256
  `f27e6546e7a204c99129bb2fcab9872ed6ca420ae6287206d7e4f26921975b97`.
- Varianten-Dateien (sha256, erste 16): blast_from_the_past `817dd6840ca96653`,
  masters_of_evil `0792f7574a97af24`, paradox_power `41a3acf621d15fb2`,
  timey_wimey `7d71fa20a9357a00`, blame_game `d6aa7649a6e81081`,
  revenant_recon `0311b4d9052be0ae`, tricky_terrain `4d9b6c9deb98c850`,
  tricky_terrain_collector_s_edition `7854667e62ffcb92`,
  odds_and_ends `e816516bb5d63b25`.
- Generator-Abgleich: `python scripts/build_precon_variants.py --check` → Exit 0
  (keine Ausgabe, keine Abweichung) am Lock.

## Import

`measure_precon_imports.py --deck-dir data/decks/precon_variants` → **9/9 OK**
(`import_variants.json` in diesem Ordner; je Deck eine Handle-Zeile, Status OK).

## Negativ-Kontrolle (Abnahme)

Kopie von `2024_blame_game` außerhalb des Repos, „Sol Ring" durch
„Definitely Not A Real Card Zzz" ersetzt; Importlauf darüber → **0/1 OK** mit
`UNKNOWN_CARD_NAME: Definitely Not A Real Card Zzz` (`import_negctl.json`).
Das Werkzeug meldet den Fehlschlag laut, wie gefordert.

## Pod-Sweep

Pool: die 9 Varianten + 7 Originale aus `data/decks/precons/` (2017_vampiric_bloodlust,
2019_primal_genesis, 2020_symbiotic_swarm, 2021_lorehold_legacies,
2021_prismari_performance, 2022_bedecked_brokers, 2022_maestros_massacre) = 16 Decks.
Zwei Läufe à 4 Pods (`precon_pod_sweep.py`, Plan-Seeds 1 und 2, Game-Seed 1,
`--games-per-jvm 4`, workers 2). Jede Variante sitzt in **genau 2 Pods** (aus den
Ergebniszeilen verifiziert). Wall-Zeiten sind Chunk-Mittel (Batching), wie im Skript
dokumentiert.

| Lauf | Pod | Status | Entscheidungen | Decks |
|---|---|---|---|---|
| 1 | pod-000 | ok | 2557 | symbiotic_swarm, **timey_wimey**, vampiric_bloodlust, **tricky_terrain_ce** |
| 1 | pod-001 | ok | 3232 | maestros_massacre, bedecked_brokers, lorehold_legacies, **masters_of_evil** |
| 1 | pod-002 | ok | 3123 | **blast_from_the_past**, **blame_game**, **odds_and_ends**, primal_genesis |
| 1 | pod-003 | ok | 2248 | **revenant_recon**, **tricky_terrain**, **paradox_power**, prismari_performance |
| 2 | pod-000 | ok | 3127 | **revenant_recon**, **blame_game**, **blast_from_the_past**, **tricky_terrain** |
| 2 | pod-001 | ok | 2272 | maestros_massacre, vampiric_bloodlust, **masters_of_evil**, lorehold_legacies |
| 2 | pod-002 | ok | 1662 | **paradox_power**, prismari_performance, **timey_wimey**, symbiotic_swarm |
| 2 | pod-003 | ok | 2473 | bedecked_brokers, **tricky_terrain_ce**, **odds_and_ends**, primal_genesis |

Summe: **8/8 Pods ok, 0 fehlgeschlagen, keine Fehlerfamilien** (`families: {}` in
beiden Läufen). Damit gibt es **keine Fehlerursachen und keine Folge-Issues** aus
dieser Messung. Semantische Pod-Hashes stehen in `sweep_plan1.json` /
`sweep_plan2.json` (dieser Ordner). Ein Pod = ein Spiel überstanden, keine
Passquote (Lesart wie in docs/PRECON_VALIDATION.md).

## Tests

`python -m pytest tests/unit/test_precon_variants.py tests/unit/test_measure_precon_imports.py tests/unit/test_precon_pod_sweep.py -q`
→ **50 passed** (0,83 s, am Lock).

## Kontext (nicht Teil der Messung)

- #982 (auf main nach dem Lock gemerged) hat dieselben neun Decks dort in
  `precon-synthetic/` umbenannt (deck_id/Name/Notizen; Karteninhalt identisch) —
  die Zahlen oben beschreiben den Lock/v12-Stand wie beauftragt.
- #988 hat die vier Commander-unbekannten Proxies entfernt; Pool auf main jetzt
  186 echt + 9 SYNTHETIC. Diese vier Decks haben keine Variante und berühren
  diese Messung nicht.
- Pin v13 (`90f5c4d3`, zehn Fork-Karten, versiegelt per #987) existiert; er ist
  Kontext, nicht Messstand.

Evidenzklasse aller Zahlen: `LOCAL_OBSERVED` (ein Lauf je Plan-Seed auf dieser Box).

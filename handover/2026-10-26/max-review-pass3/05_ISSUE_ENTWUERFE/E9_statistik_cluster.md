# Issue-Entwurf E9: Cluster-robuste Vergleichs-Intervalle + Teststärke-Tabelle

## Objective
Vergleiche ehrlicher machen: Seed-Rotationen teilen einen Shuffle, also sind Paare nicht unabhängig — Intervalle müssen das als Cluster abbilden, und jede Win-Rate braucht eine Teststärke-Angabe.

Source lock: Lab-main `6fb26071ba66176335ddc65d352797721212c51d` (Merge #1026, 2026-10-26), Engine-Pin v13 `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e`, Bridge-Jar Pass 3 sha256 `ab179c88b75e51a86a7bba22806280773a8417e89b4c4f87db6a6d75a5f3a39b` (Tests 1081/0/0/1, ReplayExport ohne Einzelnachweis — siehe Pass-3-Befund B-03).

## Read first
- `src/commander_lab/engine/rules/full_game_pilot/full_game_comparison.py:515-519` (im Code dokumentiert: Rotationen teilen Shuffle, Intervalle zu schmal, Sign-Test unberührt)
- Pass-3-Befund B-09; Pass C Feld 4 (36-Seed-Anker: Entscheidungen/Spiel 1.656–4.955, Median 2.767)
- Pass D §3 (CRN/Control Variates/sequentielle Designs — Pilotstudie nötig, keine Zahl versprochen)

## Items
1. Vergleichs-Auswertung: Seed als Cluster behandeln (Cluster-Bootstrap oder Mixed-Effects — Methode im PR begründen, nicht raten) und die Intervalle neu berechnen.
2. Re-Analyse eines bestehenden Vergleichs (z. B. #1027 oder #1008, Daten aus dem PR) mit alter und neuer Methode — zeigen, ob sich ein Urteil ändert (wenn nicht: trotzdem dokumentieren, das ist ein gutes Ergebnis).
3. Teststärke-Tabelle: Für typische Effektgrößen (Win-Rate-Differenz 5 % / 10 % / 20 %) die benötigte Spielzahl bei gepaarten Spielen angeben (Formel + Anker aus 36-Seed-Streuung), als Tabelle in die Vergleichs-Doku.
4. Sequentielle Stopp-Regel (optional, nur mit vorab festgelegter Regel): Erst 10 Seeds (Signatur), dann nur bei knappem Ergebnis weitere Seeds — Regel VOR der Messung festlegen, sonst p-Hacking.

## Acceptance (mit Wrong-Reason-Kontrolle)
- Re-Analyse dokumentiert (alt vs. neu, Urteil geändert ja/nein); Tabelle in der Doku.
- Wrong-Reason-Kontrolle: Die neue Methode muss auf synthetischen Daten mit bekannter Cluster-Struktur die wahre Streuung wiedergeben (sonst ist sie nur eine andere, falsche Methode).
- Test command: Re-Analyse-Skript + Unit-Tests für die Cluster-Rechnung.
- Stop condition: Methode + Tabelle in der Doku, keine neuen Spiele nötig für dieses Issue (Re-Analyse reicht).

Rules footer: XMage ist die einzige Rules Engine (Legality, Kosten, Mana, Stack, Priority, Targets, Combat, Trigger, Replacement/Prevention, Layers/SBA, Zonen, Copy/Control, Commander-/Multiplayer-Regeln, Rules-RNG). Keine zweite/versteckte Rules Engine, keine erfundenen legalen Aktionen, keine heuristische Legalität, keine First-/Random-/Default-Fallbacks, keine stillen Skips, keine Outcome-Injection. Observations und legale Optionen strikt principal-scoped. Nicht unterstützte produktions-erreichbare Pfade fail closed. Keine Sammlungsdaten (`data/collections`, `data/coverage_decks/collection`) lesen oder zitieren. Kein neues `Any` (Baseline 2189, `object` nehmen). Kein Force-Push, kein Rebase, kein Push auf main. `ci-definition-integrity-shadow` ist rot by design; erforderlich sind quality, security, infrastructure auf dem aktuellen Head-SHA. Refs #NEU (Nummer bei Anlage vergeben).


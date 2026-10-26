# Issue-Entwurf E7: Mana-Budget-Residual (Self-Tap/Sacrifice um 1) schließen

## Objective
Den im Code vermerkten Residualfehler schließen: Self-Tap-/Sacrifice-Fähigkeiten überschätzen das verfügbare Mana um 1 — zuerst zählen, dann fixen, dann messen.

Source lock: Lab-main `6fb26071ba66176335ddc65d352797721212c51d` (Merge #1026, 2026-10-26), Engine-Pin v13 `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e`, Bridge-Jar Pass 3 sha256 `ab179c88b75e51a86a7bba22806280773a8417e89b4c4f87db6a6d75a5f3a39b` (Tests 1081/0/0/1, ReplayExport ohne Einzelnachweis — siehe Pass-3-Befund B-03).

## Read first
- `src/commander_lab/engine/rules/full_game_pilot/payment.py:1456-1478` (`_mana_budget`/`_available_mana`), `:1516-1535` (Residual-Vermerk)
- `payment_plan.py` (419 Z., nur {T}/Sacrifice-Self, kein Convoke/Delve/Improvise/Assist, DFS-Cap 20.000)
- Pass-3-Befund B-07

## Items
1. Zählung: In echten Spielen (24+ Seeds, gleiche Pods wie #1027-Messung, falls verfügbar) loggen, wie oft das Budget um 1 überschätzt wird und ob daraus eine abgebrochene Zahlung oder eine falsche Aktion folgt.
2. Fix: Budget um die Self-Kosten korrigieren (nur die belegte Stelle, keine neue Kosten-Logik für Convoke/Delve — das ist ein eigenes Issue).
3. Vergleich: gepaart, ≥10 Seeds, Metriken: abgebrochene Zahlungen, Mana-Float-Fehler, Entscheidungen (keine Win-Rate ohne Teststärke).
4. Tests: Unit-Test für den Self-Tap-Fall (vorher rot, nachher grün) + Regression: bisher korrekte Zahlungen bleiben korrekt.

## Acceptance (mit Wrong-Reason-Kontrolle)
- Zählung dokumentiert; Fix-Test rot vor, grün nach dem Fix.
- Wrong-Reason-Kontrolle: Ein Spiel, in dem KEINE Self-Tap-Fähigkeit vorkommt, muss bit-identisch bleiben (sonst hat der Fix mehr geändert).
- Test command: neue Unit-Tests + gepaarter Vergleich (Seeds, Befehl, JSON).
- Stop condition: Fix gemessen, keine Convoke-/Delve-Logik in diesem Issue.

Rules footer: XMage ist die einzige Rules Engine (Legality, Kosten, Mana, Stack, Priority, Targets, Combat, Trigger, Replacement/Prevention, Layers/SBA, Zonen, Copy/Control, Commander-/Multiplayer-Regeln, Rules-RNG). Keine zweite/versteckte Rules Engine, keine erfundenen legalen Aktionen, keine heuristische Legalität, keine First-/Random-/Default-Fallbacks, keine stillen Skips, keine Outcome-Injection. Observations und legale Optionen strikt principal-scoped. Nicht unterstützte produktions-erreichbare Pfade fail closed. Keine Sammlungsdaten (`data/collections`, `data/coverage_decks/collection`) lesen oder zitieren. Kein neues `Any` (Baseline 2189, `object` nehmen). Kein Force-Push, kein Rebase, kein Push auf main. `ci-definition-integrity-shadow` ist rot by design; erforderlich sind quality, security, infrastructure auf dem aktuellen Head-SHA. Refs #NEU (Nummer bei Anlage vergeben).


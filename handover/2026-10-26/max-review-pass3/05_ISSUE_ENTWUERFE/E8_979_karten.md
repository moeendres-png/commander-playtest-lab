# Issue-Entwurf E8: #979 — 31 engine-unbekannte Precon-Karten als Printed implementieren (Fork, in Paketen)

## Objective
Den größten offenen Coverage-Posten (#979, Follow-up zu #920) schließen: 31 Precon-Karten, die die Engine heute nicht kennt, als Printed im Fork implementieren — in Paketen nach Häufigkeit im 173er-Pool, jedes Paket mit einem echten Spiel, in dem die Karte gezogen wird.

Source lock: Lab-main `6fb26071ba66176335ddc65d352797721212c51d` (Merge #1026, 2026-10-26), Engine-Pin v13 `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e`, Bridge-Jar Pass 3 sha256 `ab179c88b75e51a86a7bba22806280773a8417e89b4c4f87db6a6d75a5f3a39b` (Tests 1081/0/0/1, ReplayExport ohne Einzelnachweis — siehe Pass-3-Befund B-03).

## Read first
- Offenes Issue #979 (31 Karten, Liste dort — hier NICHT neu raten, die Liste aus #979 übernehmen)
- Fork-Stand Pass 3: Pin v13, Diff fab0f23b→HEAD (620 Dateien, überwiegend neue Karten) als Muster, wie Karten-Pakete aussehen
- Repin-Runbook `docs/claude/REPIN_RUNBOOK.md` (96 Z.)

## Items
1. Die 31 Karten nach Vorkommen in den 173 Precons sortieren (Häufigkeit zählen, nicht alphabetisch) und in Pakete (z. B. 5–8 Karten) schneiden.
2. Pro Paket: Fork-Implementierung + Unit-/Engine-Tests + ein echtes Spiel, in dem jede Karte des Pakets mindestens einmal gezogen/gespielt wird (sonst ist "implementiert" nur Parsing).
3. Nach allen Paketen: Repin (mit Hans-Go), PB-03-Qualifizierung + Seal (Claude-Thread, nicht Muse).
4. SYNTHETIC-Proxies für die implementierten Karten entfernen (Pool-Zahlen neu belegen), sobald die Karten im Pin sind — nicht vorher.

## Acceptance (mit Wrong-Reason-Kontrolle)
- Pro Paket: Tests grün + Spiel-Nachweis je Karte (Seed, Spiel-JSON).
- Wrong-Reason-Kontrolle: Ein Paket, dessen Karten in keinem Spiel gezogen wurden, gilt als NICHT abgeschlossen, auch wenn alle Tests grün sind (Parsing ≠ Funktion).
- Test command: Fork-Tests + Repin-Runbook-Schritte (genauer Befehl im PR).
- Stop condition: Alle 31 Karten im Pin + Seal, oder ehrlicher Zwischenstand pro Paket (kein Teil-Paket als "fertig" melden). Fork-Push/Repin/Seal nur mit Hans-Go.

Rules footer: XMage ist die einzige Rules Engine (Legality, Kosten, Mana, Stack, Priority, Targets, Combat, Trigger, Replacement/Prevention, Layers/SBA, Zonen, Copy/Control, Commander-/Multiplayer-Regeln, Rules-RNG). Keine zweite/versteckte Rules Engine, keine erfundenen legalen Aktionen, keine heuristische Legalität, keine First-/Random-/Default-Fallbacks, keine stillen Skips, keine Outcome-Injection. Observations und legale Optionen strikt principal-scoped. Nicht unterstützte produktions-erreichbare Pfade fail closed. Keine Sammlungsdaten (`data/collections`, `data/coverage_decks/collection`) lesen oder zitieren. Kein neues `Any` (Baseline 2189, `object` nehmen). Kein Force-Push, kein Rebase, kein Push auf main. `ci-definition-integrity-shadow` ist rot by design; erforderlich sind quality, security, infrastructure auf dem aktuellen Head-SHA. Refs #NEU (Nummer bei Anlage vergeben).


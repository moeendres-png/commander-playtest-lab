# Issue-Entwurf E1: 36-Seed-Referenz am HEAD neu erzeugen + automatische Invalidierung

## Objective
Eine aktuelle, am HEAD gültige 36-Seed-Referenz ersetzen die stale Referenz für `b528082d5`, und jede Pilot-/Bridge-Änderung invalidiert sie automatisch (CI-Warnung), statt dass sie still weiter als Vergleichsbasis dient.

Source lock: Lab-main `6fb26071ba66176335ddc65d352797721212c51d` (Merge #1026, 2026-10-26), Engine-Pin v13 `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e`, Bridge-Jar Pass 3 sha256 `ab179c88b75e51a86a7bba22806280773a8417e89b4c4f87db6a6d75a5f3a39b` (Tests 1081/0/0/1, ReplayExport ohne Einzelnachweis — siehe Pass-3-Befund B-03).

## Read first
- `docs/performance/REFERENCE_36_SEEDS_2026-10-26.md` (66 Z., inkl. ihrer eigenen Gültigkeitsregel)
- `scripts/benchmark_xmage_full_games.py run --jar JAR --out OUT --seeds 1-36 --workers 4 --games-per-jvm 9 --fast`
- Pass-3-Befund B-01 (Diff `b528082d5..6fb26071`: payment.py +65, priority.py +9, choices.py +1 = #1027)

## Items
1. 36-Seed-Lauf am HEAD mit Pass-3-Jar (oder frisch gebautem Jar vom HEAD), Twin-Lauf, beide JSONs unter `docs/performance/measurements-2026-10-26/`-Nachfolger ablegen (neues Verzeichnis, alte Dateien NICHT überschreiben).
2. Neue Referenz-Datei schreiben: Stand, Pin, Jar-sha256, Twin-Ergebnis (identical X/36, Hash + Winner), Sieger nach Sitz, Entscheidungen/Spiel (Min/Median/Max), und die ausdrückliche Regel, dass sie nur für genau diesen Stand gilt.
3. CI-/Guard-Check: Ein Test oder Workflow-Schritt, der warnt/failt, wenn sich Pilot- oder Bridge-Code seit dem Referenz-Commit geändert hat, ohne dass die Referenz erneuert wurde (Warnung reicht, Fail nur mit Hans-Go — sonst blockiert jeder Pilot-PR).
4. Alte Referenz NICHT löschen oder überschreiben (Historie bleibt lesbar).

## Acceptance (mit Wrong-Reason-Kontrolle)
- Neue Referenz existiert, Twin 36/36 dokumentiert (Hash + Winner), oder die Abweichung ist als solche dokumentiert und erklärt (kein Schönrechnen).
- Wrong-Reason-Kontrolle: Der Guard muss auf dem alten Stand (`b528082d5` + alte Referenz) GRÜN sein und am HEAD mit alter Referenz ROT/Warnung zeigen — sonst prüft er nichts.
- Test command: `scripts/benchmark_xmage_full_games.py run --jar <HEAD-Jar> --out <neu> --seeds 1-36 --workers 4 --games-per-jvm 9 --fast` (zweimal, Twin) + Guard-Test.
- Stop condition: Referenz-Datei + Guard grün auf dem HEAD; keine Pilot-Änderung in diesem Issue.

Rules footer: XMage ist die einzige Rules Engine (Legality, Kosten, Mana, Stack, Priority, Targets, Combat, Trigger, Replacement/Prevention, Layers/SBA, Zonen, Copy/Control, Commander-/Multiplayer-Regeln, Rules-RNG). Keine zweite/versteckte Rules Engine, keine erfundenen legalen Aktionen, keine heuristische Legalität, keine First-/Random-/Default-Fallbacks, keine stillen Skips, keine Outcome-Injection. Observations und legale Optionen strikt principal-scoped. Nicht unterstützte produktions-erreichbare Pfade fail closed. Keine Sammlungsdaten (`data/collections`, `data/coverage_decks/collection`) lesen oder zitieren. Kein neues `Any` (Baseline 2189, `object` nehmen). Kein Force-Push, kein Rebase, kein Push auf main. `ci-definition-integrity-shadow` ist rot by design; erforderlich sind quality, security, infrastructure auf dem aktuellen Head-SHA. Refs #NEU (Nummer bei Anlage vergeben).


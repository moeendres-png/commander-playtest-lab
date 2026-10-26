# Issue-Entwurf E4: Mulligan-Modell auf den 173er-Pool neu fitten

## Objective
Das Opening-Hand-Modell (heute auf 195 Decks gefittet) auf den aktuellen Pool (173 = 164 + 9 SYNTHETIC) neu fitten und messen, ob sich Keep-Raten und frühe Spielstärke ändern — oder ob das Modell am Limit ist.

Source lock: Lab-main `6fb26071ba66176335ddc65d352797721212c51d` (Merge #1026, 2026-10-26), Engine-Pin v13 `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e`, Bridge-Jar Pass 3 sha256 `ab179c88b75e51a86a7bba22806280773a8417e89b4c4f87db6a6d75a5f3a39b` (Tests 1081/0/0/1, ReplayExport ohne Einzelnachweis — siehe Pass-3-Befund B-03).

## Read first
- `src/commander_lab/agents/pilots.py:314-454` (Modell, Kommentar Z. 320: 58.500 Hände, 195 Decks, R² 0,33)
- `git log -- src/commander_lab/agents/pilots.py` (letzte Mulligan-Änderung #1002, danach nur #1013 Guides)
- Pass-3-Befund B-02; `mulligan/`-Verzeichnis (3 Dateien, 1.343 Z.)

## Items
1. Fit-Daten für den 173er-Pool erzeugen (gleiche Methode wie bisher: seeded Hände, Holdout-Anteil dokumentieren) — neue Daten, alte Fit-Kommentare NICHT überschreiben, sondern ersetzen mit Datums-/Pool-Angabe.
2. Neues Modell (gleiche Features, neue Koeffizienten) als Pilot-Änderung einbauen, hinter keinem Flag versteckt (sonst ist es toter Code — siehe B-11-Lektion).
3. Vergleich: ≥10 Seeds, gepaart, gleiche Pods, Metriken: Keep-Rate je Handtyp, Mulligan-Anzahl, frühe Entscheidungen (keine Win-Rate als Hauptmetrik — 10 Seeds tragen keine Win-Rate, siehe Pass C Feld 4).
4. Wenn R² nach dem Refit nicht besser wird oder die Keep-Raten sich nicht bewegen: Ergebnis ehrlich als "Modell am Limit, Refit bringt nichts" dokumentieren und das Issue mit "kein weiterer Refit, Modell ersetzen" schließen — das ist ein gutes Ergebnis, kein Fehlschlag.

## Acceptance (mit Wrong-Reason-Kontrolle)
- Fit mit Pool-Angabe + R² dokumentiert; Vergleich auf ≥10 Seeds mit Signatur (kein Win-Rate-Claim ohne Teststärke).
- Wrong-Reason-Kontrolle: Der Vergleich muss auf dem ALTEN Modell (195er-Fit) reproduzierbar die ALTEN Keep-Raten zeigen — sonst misst der Vergleich etwas anderes als den Fit.
- Test command: Fit-Skript (im PR benannt) + gepaarter Vergleich (Seeds, Befehl, JSON im PR).
- Stop condition: Refit gemessen und dokumentiert, egal ob er hilft oder nicht; keine cEDH-Anpassung.

Rules footer: XMage ist die einzige Rules Engine (Legality, Kosten, Mana, Stack, Priority, Targets, Combat, Trigger, Replacement/Prevention, Layers/SBA, Zonen, Copy/Control, Commander-/Multiplayer-Regeln, Rules-RNG). Keine zweite/versteckte Rules Engine, keine erfundenen legalen Aktionen, keine heuristische Legalität, keine First-/Random-/Default-Fallbacks, keine stillen Skips, keine Outcome-Injection. Observations und legale Optionen strikt principal-scoped. Nicht unterstützte produktions-erreichbare Pfade fail closed. Keine Sammlungsdaten (`data/collections`, `data/coverage_decks/collection`) lesen oder zitieren. Kein neues `Any` (Baseline 2189, `object` nehmen). Kein Force-Push, kein Rebase, kein Push auf main. `ci-definition-integrity-shadow` ist rot by design; erforderlich sind quality, security, infrastructure auf dem aktuellen Head-SHA. Refs #NEU (Nummer bei Anlage vergeben).


# Issue-Entwurf E3: Kartenkatalog fail closed statt leer

## Objective
Ein unlesbarer/korrupter Kartenkatalog darf nicht still zu einem leeren Katalog (und damit zu namensbasiertem, schlechterem Pilot-Verhalten) führen — er muss laut abbrechen oder ein Startup-Gate muss ihn stoppen.

Source lock: Lab-main `6fb26071ba66176335ddc65d352797721212c51d` (Merge #1026, 2026-10-26), Engine-Pin v13 `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e`, Bridge-Jar Pass 3 sha256 `ab179c88b75e51a86a7bba22806280773a8417e89b4c4f87db6a6d75a5f3a39b` (Tests 1081/0/0/1, ReplayExport ohne Einzelnachweis — siehe Pass-3-Befund B-03).

## Read first
- `src/commander_lab/agents/card_knowledge.py:105-106, 218-219` (OSError/ValueError → `{}`)
- Pass-3-Befund B-12; `notes_pilot_rest.md` §4/§11 (Katalog wird zur Entscheidungszeit gelesen, dann `lru_cache`)

## Items
1. Katalog-Laden: Bei OSError/ValueError NICHT still `{}` zurückgeben, sondern einen benannten Fehler werfen (Fail closed) — oder, falls ein Fallback bewusst gewollt ist, ihn laut loggen und in einem Startup-Gate sichtbar machen (Entscheidung im PR dokumentieren, nicht still).
2. Startup-Gate: Kataloggröße gegen Pool-Größe prüfen (Vorschlag: < 50 % der Pool-Karten mit Eintrag = Abbruch; Schwelle im PR begründen, nicht raten).
3. Tests: korrupte JSON → Fehler (nicht leer); leere Datei → Fehler; gültiger Katalog → wie bisher.
4. Smoke: 1-Spiel-Smoke mit gültigem Katalog grün (kein Spiel-Verhalten geändert, nur der Fehlerpfad).

## Acceptance (mit Wrong-Reason-Kontrolle)
- Korrupt-Test rot vor dem Fix, grün nach dem Fix (gegen Pre-Fix-Stand verifiziert).
- Wrong-Reason-Kontrolle: Ein Smoke mit ABSICHTLICH korruptem Katalog muss jetzt abbrechen (nicht "grün, aber schlechter spielen") — sonst ist das Gate kein Gate.
- Test command: neue Unit-Tests + Smoke (absoluter Jar-Pfad, siehe Befund B-05).
- Stop condition: Fehlerpfad fail closed, gültiger Pfad unverändert.

Rules footer: XMage ist die einzige Rules Engine (Legality, Kosten, Mana, Stack, Priority, Targets, Combat, Trigger, Replacement/Prevention, Layers/SBA, Zonen, Copy/Control, Commander-/Multiplayer-Regeln, Rules-RNG). Keine zweite/versteckte Rules Engine, keine erfundenen legalen Aktionen, keine heuristische Legalität, keine First-/Random-/Default-Fallbacks, keine stillen Skips, keine Outcome-Injection. Observations und legale Optionen strikt principal-scoped. Nicht unterstützte produktions-erreichbare Pfade fail closed. Keine Sammlungsdaten (`data/collections`, `data/coverage_decks/collection`) lesen oder zitieren. Kein neues `Any` (Baseline 2189, `object` nehmen). Kein Force-Push, kein Rebase, kein Push auf main. `ci-definition-integrity-shadow` ist rot by design; erforderlich sind quality, security, infrastructure auf dem aktuellen Head-SHA. Refs #NEU (Nummer bei Anlage vergeben).


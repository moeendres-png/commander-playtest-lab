# Issue-Entwurf E5: Deck-Hash verifizieren + Duplikat-/Farb-Gate vor dem Bridge-Import

## Objective
Ein Deck mit falschem Hash, Duplikaten oder falscher Commander-Farbe soll VOR dem Bridge-Import fail closed abgelehnt werden, statt sich auf den (in Pass 3 ungelesenen) XMage-Validator zu verlassen.

Source lock: Lab-main `6fb26071ba66176335ddc65d352797721212c51d` (Merge #1026, 2026-10-26), Engine-Pin v13 `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e`, Bridge-Jar Pass 3 sha256 `ab179c88b75e51a86a7bba22806280773a8417e89b4c4f87db6a6d75a5f3a39b` (Tests 1081/0/0/1, ReplayExport ohne Einzelnachweis — siehe Pass-3-Befund B-03).

## Read first
- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageDeckImporter.java` (504 Z., vollständig in Pass 3 gelesen: Hash nur non-blank, keine Duplikat-/Banned-/Farb-Prüfung, 13 Fehlercodes)
- Pass-3-Befund B-04

## Items
1. Python-Gate (Lab-Seite, KEINE Rules-Engine — das ist Deck-Konstruktion, keine Spiel-Legalität; die Abgrenzung im PR ausdrücklich begründen, sonst verstößt das gegen "XMage = einzige Rules Engine"): Hash über Deck-Inhalt neu berechnen und gegen `deck_hash` prüfen; Duplikate im Mainboard zählen; Commander-Farbidentität gegen Mainboard prüfen.
2. Gate in den Import-Pfad einhängen (vor `import_deck`), mit eigenem Fehlercode (nicht einen Bridge-Code wiederverwenden).
3. Tests: falscher Hash → Ablehnung; Duplikat → Ablehnung; falsche Farbe → Ablehnung; gültiges Deck → unverändert importiert (Smoke grün).
4. Separat (Lese-Issue, optional im selben PR als Doku, nicht als Code): XMage-`Commander`-Validator lesen und dokumentieren, welche Checks er tatsächlich macht — schließt die Pass-3-Lücke, ohne Engine-Code zu ändern.

## Acceptance (mit Wrong-Reason-Kontrolle)
- Alle drei Ablehnungs-Tests rot vor, grün nach dem Gate.
- Wrong-Reason-Kontrolle: Ein Deck, das NUR durch den Hash falsch ist (sonst gültig), muss abgelehnt werden — sonst prüft das Gate nur die anderen Checks.
- Test command: neue Unit-Tests + 1-Spiel-Smoke (absoluter Jar-Pfad).
- Stop condition: Gate grün, kein Bridge-/Engine-Code geändert, keine Sammlungsdaten berührt.

Rules footer: XMage ist die einzige Rules Engine (Legality, Kosten, Mana, Stack, Priority, Targets, Combat, Trigger, Replacement/Prevention, Layers/SBA, Zonen, Copy/Control, Commander-/Multiplayer-Regeln, Rules-RNG). Keine zweite/versteckte Rules Engine, keine erfundenen legalen Aktionen, keine heuristische Legalität, keine First-/Random-/Default-Fallbacks, keine stillen Skips, keine Outcome-Injection. Observations und legale Optionen strikt principal-scoped. Nicht unterstützte produktions-erreichbare Pfade fail closed. Keine Sammlungsdaten (`data/collections`, `data/coverage_decks/collection`) lesen oder zitieren. Kein neues `Any` (Baseline 2189, `object` nehmen). Kein Force-Push, kein Rebase, kein Push auf main. `ci-definition-integrity-shadow` ist rot by design; erforderlich sind quality, security, infrastructure auf dem aktuellen Head-SHA. Refs #NEU (Nummer bei Anlage vergeben).


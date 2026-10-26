# Issue-Entwurf E6: Commander-Schaden und -Tax für den Piloten sichtbar machen (Messung zuerst)

## Objective
Zuerst messen, ob die unsichtbare Commander-Regel (Schaden/Tax) überhaupt Entscheidungen ändert — erst dann (falls ja) die Sichtbarkeit in der Bridge umsetzen.

Source lock: Lab-main `6fb26071ba66176335ddc65d352797721212c51d` (Merge #1026, 2026-10-26), Engine-Pin v13 `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e`, Bridge-Jar Pass 3 sha256 `ab179c88b75e51a86a7bba22806280773a8417e89b4c4f87db6a6d75a5f3a39b` (Tests 1081/0/0/1, ReplayExport ohne Einzelnachweis — siehe Pass-3-Befund B-03).

## Read first
- `notes_bridge.md` (`commander_damage_visible`/`commander_tax_visible` = false in beiden Lanes)
- Pass-3-Befund B-10
- Bridge-Dateien: `XmageFullGamePlayer.java`, `XmageFullGameSession.java` (abschnittsweise in Pass 3 gelesen — hier vollständig für die betroffenen Stellen lesen)

## Items
1. Messung (kein Bridge-Code): In echten Spielen (≥10 Seeds) zählen, in wie vielen Entscheidungen Commander-Schaden (nahe 21) oder Tax (≥1) die beste Aktion ändern würde, wenn der Pilot sie sehen könnte — per Replay/Analyse, nicht per Raten. Wenn die Zahl 0 ist: Issue als "kein Hebel" schließen, kein Bridge-Code.
2. Nur wenn die Messung > 0 zeigt: Bridge-Änderung (Sichtbarkeits-Flags + Pilot-Sicht), mit Requalifizierung durch einen Claude-Thread (Muse startet KEINE engine-bridge-Änderung selbst).
3. Danach: gepaarter Vergleich ≥10 Seeds, Signatur: Entscheidungen, bei denen Commander-Schaden/Tax den Ausschlag gibt; Win-Rate nur mit Teststärke.
4. Principal-Scoping prüfen: Die Sicht darf nur den eigenen Commander bzw. die für den Entscheider sichtbaren Informationen zeigen — keine Hidden-Information-Leckage (Audit aus `full_game.py` Hidden-Information-Audit beachten).

## Acceptance (mit Wrong-Reason-Kontrolle)
- Messung dokumentiert (Zahl der betroffenen Entscheidungen, Seeds, Befehl); bei 0: Issue geschlossen ohne Code — das zählt als Erfolg.
- Bei Umsetzung: Requalifizierung durch Claude-Thread belegt, Vergleich grün, kein Hidden-Info-Leck.
- Wrong-Reason-Kontrolle: Der Vergleich muss zeigen, dass sich NUR Commander-bezogene Entscheidungen ändern (sonst hat die Bridge-Änderung mehr geändert als die Sicht).
- Test command: Mess-Skript + (bei Umsetzung) Bridge-Tests + gepaarter Vergleich.
- Stop condition: Messung steht; Umsetzung nur mit Claude-Requalifizierung.

Rules footer: XMage ist die einzige Rules Engine (Legality, Kosten, Mana, Stack, Priority, Targets, Combat, Trigger, Replacement/Prevention, Layers/SBA, Zonen, Copy/Control, Commander-/Multiplayer-Regeln, Rules-RNG). Keine zweite/versteckte Rules Engine, keine erfundenen legalen Aktionen, keine heuristische Legalität, keine First-/Random-/Default-Fallbacks, keine stillen Skips, keine Outcome-Injection. Observations und legale Optionen strikt principal-scoped. Nicht unterstützte produktions-erreichbare Pfade fail closed. Keine Sammlungsdaten (`data/collections`, `data/coverage_decks/collection`) lesen oder zitieren. Kein neues `Any` (Baseline 2189, `object` nehmen). Kein Force-Push, kein Rebase, kein Push auf main. `ci-definition-integrity-shadow` ist rot by design; erforderlich sind quality, security, infrastructure auf dem aktuellen Head-SHA. Refs #NEU (Nummer bei Anlage vergeben).


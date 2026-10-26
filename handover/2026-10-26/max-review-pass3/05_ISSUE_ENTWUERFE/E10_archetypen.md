# Issue-Entwurf E10: Graveyard-/Artifact-Archetypen — echte Deltas oder zusammenlegen

## Objective
Drei Archetypen, ein Verhalten, beenden: GraveyardPilot und ArtifactPilot sind heute identisch mit EnginePilot (nur Name anders).

Source lock: Lab-main `6fb26071ba66176335ddc65d352797721212c51d` (Merge #1026, 2026-10-26), Engine-Pin v13 `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e`, Bridge-Jar Pass 3 sha256 `ab179c88b75e51a86a7bba22806280773a8417e89b4c4f87db6a6d75a5f3a39b` (Tests 1081/0/0/1, ReplayExport ohne Einzelnachweis — siehe Pass-3-Befund B-03).

## Read first
- `src/commander_lab/agents/pilots.py:1650-1667` (EnginePilot mit Deltas, Graveyard/Artifact ohne Override)
- Pass-3-Befund B-13; `live_routing.py` (Archetypen: aggro, control, engine, graveyard, artifact)

## Items
1. Entscheiden (im PR begründet, nicht geraten): Entweder echte Deltas — Graveyard: Friedhof als Ressource werten (z. B. Friedhofsgröße, Reanimation-Ziele); Artifact: Artefakt-Synergie werten — oder die beiden Archetypen auf EnginePilot zusammenlegen (Routing + Docs anpassen).
2. Bei Deltas: gepaarter Vergleich ≥10 Seeds, Graveyard-Deck vs. Engine-Deck (bzw. Artifact-Deck vs. Engine-Deck), Signatur: Entscheidungen, die sich durch das Delta ändern (keine Win-Rate ohne Teststärke).
3. Bei Zusammenlegen: Tests, die beweisen, dass Routing + Docs keine toten Archetypen mehr anbieten.
4. NICHT in diesem Issue: neue Archetypen erfinden.

## Acceptance (mit Wrong-Reason-Kontrolle)
- Deltas: Vergleich zeigt geänderte Entscheidungen, die zum Archetyp passen (Graveyard-Entscheidungen ändern sich bei Friedhofs-Decks, nicht bei allen Decks) — sonst ist das Delta Rauschen.
- Zusammenlegen: Kein Code/Doku-Pfad bietet Graveyard/Artifact mehr als eigenes Verhalten an.
- Test command: betroffene Unit-Tests + (bei Deltas) gepaarter Vergleich.
- Stop condition: Ein Verhalten pro Archetyp (echt oder zusammengelegt), dokumentiert.

Rules footer: XMage ist die einzige Rules Engine (Legality, Kosten, Mana, Stack, Priority, Targets, Combat, Trigger, Replacement/Prevention, Layers/SBA, Zonen, Copy/Control, Commander-/Multiplayer-Regeln, Rules-RNG). Keine zweite/versteckte Rules Engine, keine erfundenen legalen Aktionen, keine heuristische Legalität, keine First-/Random-/Default-Fallbacks, keine stillen Skips, keine Outcome-Injection. Observations und legale Optionen strikt principal-scoped. Nicht unterstützte produktions-erreichbare Pfade fail closed. Keine Sammlungsdaten (`data/collections`, `data/coverage_decks/collection`) lesen oder zitieren. Kein neues `Any` (Baseline 2189, `object` nehmen). Kein Force-Push, kein Rebase, kein Push auf main. `ci-definition-integrity-shadow` ist rot by design; erforderlich sind quality, security, infrastructure auf dem aktuellen Head-SHA. Refs #NEU (Nummer bei Anlage vergeben).


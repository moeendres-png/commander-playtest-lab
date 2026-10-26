# Issue-Entwurf E2: Korvold-Piloten als retired markieren, Legacy-Pfad in Tests verbieten

## Objective
Beenden, dass 6 Korvold-Pilot-Klassen (~530 Zeilen) in Tests über den Legacy-Pfad grün aussehen, obwohl sie in keinem Live-Spiel je laufen.

Source lock: Lab-main `6fb26071ba66176335ddc65d352797721212c51d` (Merge #1026, 2026-10-26), Engine-Pin v13 `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e`, Bridge-Jar Pass 3 sha256 `ab179c88b75e51a86a7bba22806280773a8417e89b4c4f87db6a6d75a5f3a39b` (Tests 1081/0/0/1, ReplayExport ohne Einzelnachweis — siehe Pass-3-Befund B-03).

## Read first
- `src/commander_lab/agents/live_routing.py` (Retired-Set, `_validate_family`, `build_pilot`)
- `src/commander_lab/agents/__init__.py:2` (exportiert Live-Routing)
- `src/commander_lab/agents/pilots.py:919-1448` (KorvoldPilot + 5 Varianten)
- Pass-3-Befund B-11 (direkt verifiziert; Korrektur: 6, nicht 7 Klassen)

## Items
1. In `pilots.py` jede Korvold-Klasse als retired dokumentieren (Docstring: "Live-Routing lehnt diese Klasse ab, nur Legacy/Ensemble-Pfad").
2. Einen Test schreiben, der beweist: `commander_lab.agents.build_pilot` mit Korvold-Name → ValueError; `auto` + Korvold-Strategie → GenericCommanderPilot (nicht Korvold).
3. Einen Hygiene-Test (oder Ratchet), der `pilots.build_pilot` in Produktionspfaden verbietet, außer den beiden belegten Ausnahmen (`ensemble.py`, `tools/service_knowledge.py`, dort mit Kommentar warum).
4. NICHT in diesem Issue: Klassen löschen (das braucht Hans-/Claude-Go, weil der Name in Docs/Handoffs steht) — Löschen ist ein Folge-Issue, wenn dieses hier grün ist.

## Acceptance (mit Wrong-Reason-Kontrolle)
- Routing-Test grün; Hygiene-Test grün.
- Wrong-Reason-Kontrolle: Der neue Test muss auf einem Stand, auf dem Live-Routing Korvold zuließe (z. B. Retired-Set temporär geleert, nur lokal, nicht committet), ROT werden — sonst prüft er die falsche Stelle.
- Test command: betroffene Unit-Tests + `ruff check` + `ruff format --check` auf geänderten Dateien.
- Stop condition: Tests grün, keine Spiel-Änderung, keine Klasse gelöscht.

Rules footer: XMage ist die einzige Rules Engine (Legality, Kosten, Mana, Stack, Priority, Targets, Combat, Trigger, Replacement/Prevention, Layers/SBA, Zonen, Copy/Control, Commander-/Multiplayer-Regeln, Rules-RNG). Keine zweite/versteckte Rules Engine, keine erfundenen legalen Aktionen, keine heuristische Legalität, keine First-/Random-/Default-Fallbacks, keine stillen Skips, keine Outcome-Injection. Observations und legale Optionen strikt principal-scoped. Nicht unterstützte produktions-erreichbare Pfade fail closed. Keine Sammlungsdaten (`data/collections`, `data/coverage_decks/collection`) lesen oder zitieren. Kein neues `Any` (Baseline 2189, `object` nehmen). Kein Force-Push, kein Rebase, kein Push auf main. `ci-definition-integrity-shadow` ist rot by design; erforderlich sind quality, security, infrastructure auf dem aktuellen Head-SHA. Refs #NEU (Nummer bei Anlage vergeben).


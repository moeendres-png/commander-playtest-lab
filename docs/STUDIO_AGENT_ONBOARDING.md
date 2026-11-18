# Commander Studio: Einstieg für einen weiteren Agenten

Diese Seite wiederholt keine Regel, sie sagt, wo die Regeln stehen und wie man hier anfängt. Bei
Widerspruch gilt `AGENTS.md`, dann `docs/STUDIO_SCOPE.md`. Grundlage: Owner-Aussage vom 2026-11-18,
die Dateien so anzupassen, dass ein weiterer Agent weiß, wie abgearbeitet wird
(`docs/OWNER_DECISIONS_STUDIO_20261118.md`, Abschnitt 1).

## 1. In dieser Reihenfolge lesen

1. `AGENTS.md` (ganz).
2. `docs/STUDIO_SCOPE.md`, darin „Feste Regeln“, „Phasenplan S0 bis S6“ und „Abarbeitung (für
   alle Agents)“.
3. `docs/OWNER_DECISIONS_STUDIO_20261118.md`, dann `docs/OWNER_DECISIONS_STUDIO_20261112.md`.
4. Das eigene Issue und die Claim-Tabelle im Übersichts-Issue #1167.

## 2. Anfangen

- Stand holen und einen eigenen Branch von `origin/main` anlegen. Nie auf `main` schreiben, nie
  Force-Push (`AGENTS.md` §10).
- Vor dem Start die Claim-Tabelle in #1167 und die offenen PRs und Branches prüfen (keine
  Doppelarbeit), dann claimen: Kommentar im Issue und Zeile in der Claim-Tabelle (Fläche, Branch,
  Stand). Claimen gilt für jeden Agenten, auch Lead und Coordinator (Owner, 2026-11-18). Freigeben
  bei Merge, Übergabe oder Abbruch. Bei einem Claim ohne gepushten Meilenstein darf jeder im Issue
  nachfragen; sind danach 24 Stunden ohne Antwort oder Push vergangen, verfällt er und darf
  übernommen werden. Der aktive Branch eines anderen Agenten bleibt ohne Übergabe unberührt.
  Einzelheiten und Verfallsfrist sind Ausgestaltung des Leads (`AGENTS.md` §8, §11).
- Ein Paket = ein Issue bzw. ein Branch = ein PR. Commits und PR-Texte sagen `Refs #N`, nie
  `Closes #N`.

## 3. Flächen

Eine Fläche hat einen Halter; wer sie hält, steht in der Claim-Tabelle in #1167. Dateien außerhalb
der eigenen Fläche sind nur lesbar. Pfade unter `studio/` meinen `src/commander_lab/studio/`.

| Fläche | Dateien |
|---|---|
| PLAY-Seite | `studio/static/partie.js`, `partie.html`, `partie.css`, `boardclick.js`, `vorspulen.js`; `tests/unit/test_human_seat_play_1169.py`; `tests/fixtures/boardclick_payloads.json` |
| PLAY-Server | `studio/play.py`, `studio/games.py`, Partie-Teil von `studio/launch.py` |
| SIMULATE-Kern | `studio/paired_series.py`, `paired_comparison.py`, `play_batch.py`, `simulations.py`, `deck_series.py`; `studio/static/paired.js`, `deckseries.js` und ihre Tests. Pakete hier laufen nacheinander, nie zwei offene PRs auf `paired_series.py`. |
| SIMULATE-Auswertung | `studio/card_outcomes.py`, `castability.py` und neue Auswertungs-Dateien |
| BUILD-Tierliste | `studio/strength*.py`, `overall_rating.py`, `card_understanding.py`, `tiers.py`, `tier_snapshot.py`, `ranking_check.py`; `studio/static/tierliste.*` |
| BUILD-Deckbauer | übrige Deckbau-Module unter `studio/`; `studio/static/app.js`, `decks.js`, `cutlab.js`, `search.js` |
| Betrieb | `studio/doctor.py`; `scripts/studio_start.*`, `scripts/provision_engine_bridge.py`; `docs/STUDIO_OWNER_PC_SETUP.md` |
| Gate-Werkzeuge und CI | `scripts/benchmark_xmage_full_games.py`, `scripts/check_studio_series_identity.py`, `.github/workflows/**` (MATERIAL; Pflicht-Checks und Gate-Definitionen ändert nur der Owner, `AGENTS.md` §10) |
| Bridge | `engine-bridge/**` (Studio-Bridge-Gate, `AGENTS.md` §10) |
| Governance | `AGENTS.md`, `CLAUDE.md`, `docs/STUDIO_SCOPE.md`, `docs/OWNER_DECISIONS_*`, `.claude/**`, `.github/copilot-instructions.md`, `.github/pull_request_template.md` |

**Kollisionsdateien** (mehrere Flächen wollen hinein): `studio/web.py`, `studio/static/app.js`,
`studio/static/partie.js`, `studio/static/tierliste.js`, `studio/__main__.py`, `studio/launch.py`,
`studio/static/index.html`, `tests/unit/test_studio_static_guards.py`, `docs/README.md`. Dort gilt:

1. Neue Funktion in neuer Datei; in die Kollisionsdatei kommt nur die Einhängung (eine Route, ein
   `<script>`-Eintrag, ein Aufruf, ein Unterbefehl). Muster: `studio/static/deckseries.js` mit dem
   Platzhalter `deck-series-slot` in `app.js`.
2. Vorher in #1167 Datei und Funktionsbereich nennen. Der frühere Kommentar hat Vorrang; der
   spätere mergt `main` in seinen Branch.
3. Nichts umformatieren, verschieben oder umbenennen.

## 4. Nie ohne ausdrückliches Owner-Go

Engine-Fork und Pin · `qualification/` · `pyproject.toml`, `requirements/lock.txt` · neue
Abhängigkeit · 5 und 6 Sitze freigeben · Sichtbarkeit, #1108 · Bezahldienste · Gewicht
`simulation` anheben. Vollständige Liste: `AGENTS.md` §8.

`AGENTS.md` und `CLAUDE.md` ändern Lead oder Coordinator nach `AGENTS.md` §8.
`docs/STUDIO_SCOPE.md` und `docs/OWNER_DECISIONS_*` ändern sich inhaltlich nur auf
Owner-Anweisung oder nach Owner-Freigabe einer vorgelegten Option; andere legen Option und
Empfehlung vor (`docs/STUDIO_SCOPE.md`, Abarbeitung Punkt 5). Bei Unsicherheit wird mit dem Owner
geplant.

## 5. Prüfen vor dem Push

- Testumgebung außerhalb des Arbeitsbaums anlegen: `.claude/skills/lab-ops/SKILL.md`, Abschnitt
  „Local test environment“.
- Schmal testen, ohne `--shards`: `python -m pytest -q tests/unit -k "<modul>"`.
- Vor dem PR einmal breit, mit Pfaden statt `-k` (`--shards` nimmt kein `-k` an,
  `tests/pytest_shards.py`):
  `python -m pytest -q --shards=4 tests/unit/test_studio_*.py tests/unit/test_human_seat_play_1169.py`,
  dazu `ruff check .`, `ruff format --check .`, `mypy src/commander_lab` und für geänderte
  Seiten-Skripte `node --check <datei>`.
- Reine Doku: `python scripts/classify_docs.py --check` und `--links`; neue Datei unter `docs/` in
  `docs/README.md` eintragen.

## 6. Review und Merge

- MATERIAL (Liste in `AGENTS.md` §10; dazu Texte der Oberfläche über Ratings oder
  Simulationsergebnisse, `docs/STUDIO_SCOPE.md` Abarbeitung Punkt 4): zuerst ein Review aus
  frischem Kontext mit PASS als PR-Kommentar. Der Kommentar nennt die prüfende Sitzung neutral
  (ohne Personennamen), die exakte Head-SHA, die ausgeführten Befehle und das Urteil. Gemergt wird
  genau diese SHA. Arbeiten zwei Agenten parallel, prüft eine Sitzung des jeweils anderen Agenten;
  der Autor mergt frühestens nach diesem Kommentar (Kreuz-Review, `AGENTS.md` §10).
- Pflicht-Checks `quality`, `security`, `infrastructure` grün auf dem exakten Head.
- Wer selbst mergen darf, steht in `AGENTS.md` §6, §10 und §11. Nicht bestellte externe Agenten
  mergen nicht selbst; Lead oder Owner prüfen und mergen.

## 7. Fallen

- `ci-definition-integrity-shadow` ist rot, wenn ein PR Workflows, Prüf-Konfiguration oder
  bestehende Tests anders als durch Hinzufügen ändert (`scripts/verify_required_check_definitions.py`).
  Das ist absichtlich, kein Gate und wird nie abgeschwächt: nicht „reparieren“, im PR erklären.
- Eine Änderung unter `.github/` (auch Markdown) verlässt den schnellen Doku-Pfad der CI
  (`scripts/ci_change_scope.py`, `NON_DOCS_ROOTS`); dann läuft die volle Test-Matrix.
- GitHub antwortet mit 429: ein Versuch, dann aufhören und es im Issue vermerken. Kein enges
  Polling; Warten läuft als Hintergrund-Schleife. GraphQL ist nicht verfügbar; REST benutzen.
- Plattenplatz: Ein voller Checkout belegt mehrere hundert MB (`qualification/` und `data/` sind
  die größten Verzeichnisse). Arbeitsbäume fremder Sitzungen nie löschen; bei Platzmangel einen
  Sparse-Checkout ohne die nicht gebrauchten Verzeichnisse anlegen und Tests, die sie brauchen,
  erst nach vollem Checkout als Beleg werten.
- `scripts/regenerate_hash_manifests.py` hat keinen Prüfmodus: Jeder Aufruf schreibt die
  Manifeste neu. Das ist außerhalb der in `AGENTS.md` §8 genannten Fälle Owner-vorbehalten. Geprüft
  wird über `tests/qualification/test_ws17_qualification.py`.
- Seiten-Skripte: kein `innerHTML`, kein `style=`, kein `.toFixed(`
  (`tests/unit/test_studio_static_guards.py`). Kein `assert` in `src/`
  (`tests/unit/test_no_runtime_asserts_in_src.py`).
- Der Echt-Engine-Test des Mensch-Sitzes überspringt ohne Engine. Übersprungen ist nicht
  bestanden: als `NOT_RUN` melden.
- Neue Repository-Inhalte nennen kein KI-Modell und keinen Anbieter (`AGENTS.md` §12).
- Ergebnisse aus Simulation heißen `SIMULATED_RESULT` und stehen nicht auf der Tierliste, bevor
  G-SIM erfüllt und vom Owner bestätigt ist.
- Jede Zahl mit n/N und Herkunft. Was nicht belegt ist, heißt `UNKNOWN`, nie PASS.

## 8. Übergabe

Nach jedem Meilenstein committen und pushen (`AGENTS.md` §14). Am Ende ein Kommentar im Issue:
Head-SHA, was getan ist, Tests mit Ergebnis, PASS/FAIL/UNKNOWN, was offen ist, nächster Schritt.
Punkte, die eine echte Engine oder den Owner-PC brauchen, werden als solche ausgewiesen.

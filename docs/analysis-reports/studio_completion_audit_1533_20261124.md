# `#1533`: Vorbereitendes Abschluss-Audit – Bridge-Zustandsanzeige und Tabelle der 6 Abschlusskriterien

- **Datum:** 2026-11-24 · **Refs:** `#1533`, `#1167`, `#1661`, `#1662`, `#1528`, `#1703`
- **Owner-Entscheid (`#1533` Kommentar 1 & Option `6A`, 2026-11-24):**
  - Frage (a) Siegel (`a1`): Über eine finale Qualifikations-Epoche wird erst nach dem Windows-PC-Test entschieden; bis dahin bleibt alles ehrlich als `BRIDGE_AHEAD_OF_QUALIFICATION` / „vor Qualifikation“ ausgewiesen.
  - Frage (b) Release (`b1`): Weiter `gh` + Workflow-Artefakt (`release-artifacts.yml`).
  - Option `6A`: Vorbereitendes Audit und Kriterien-Tabelle jetzt vorziehen; `#1533` bleibt bis zur vollständigen Owner-Abnahme und „Einrichtung von null“ offen.
- **Basisstand & Engine-Pin:** `main` @ `aa7a4b57e21d8c350ae4b75f5bf504f935881f19`, Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`config/rules_engines.json`).
- **Einordnung:** `CODE_DERIVED` (Code- und Doku-Audit auf `origin/main`; Qualifikations-Dispatch-Lauf und Windows-Einrichtung „von null“ sind `NOT_RUN`).

## 1. Audit der Qualifikationsanzeige in Oberfläche und Backend (`CODE_DERIVED`)

Geprüft wurde jede Stelle unter `src/commander_lab/studio/`, die Qualifikationszustand oder Epochen-Abdeckung ausgibt. Keine Stelle stellt einen Lauf auf einer neueren Bridge als von der versiegelten Epoche abgedeckt dar:

| Datei & Zeilen | Was geprüft wurde | Befund |
|---|---|---|
| `src/commander_lab/studio/deck_series.py:218-219, 290-291` | Extrahiert `bridge_qualification_states` und `covered_by_sealed_epoch` (`bool(...) if res else None`) | ehrlich, kein Default `True` |
| `src/commander_lab/studio/maturity.py:14, 591` | R3-Bedingung verlangt explizit `covered_by_sealed_epoch is True` oder Owner-Annahme | ehrlich, fail-closed |
| `src/commander_lab/studio/static/ui.js:270-279` | Status-Badge für `BRIDGE_AHEAD_OF_QUALIFICATION` mit Rohcode, Grund und versiegelter Epoche im Tooltip | ehrlich ausgewiesen |
| `src/commander_lab/studio/static/app.js:74, 1692-1693, 1716-1718, 1779-1785, 1806, 1813` | Monitor-Pille („Bridge: Engine-Stand noch nicht qualifiziert · nicht durch versiegelte Epoche abgedeckt“), Serien-Tabelle und Fußnote | ehrlich ausgewiesen |
| `src/commander_lab/studio/static/paired.js:403-408, 452` | Paar-Serien-Ansicht zeigt `BRIDGE_AHEAD_OF_QUALIFICATION`-Warnpille und Epochenlabel (`versiegelt` nur bei `covered_by_sealed_epoch`) | ehrlich ausgewiesen |
| `src/commander_lab/studio/static/deckseries.js:147, 155` | Deck-Verlauf zeigt `Bridge-JAR`, `Qualifizierung` und explizit `· nicht versiegelt` bei `covered_by_sealed_epoch === false` | ehrlich ausgewiesen |
| `src/commander_lab/studio/static/kartenauswertung.js:26, 372-375` | Kartenauswertung beschriftet `BRIDGE_AHEAD_OF_QUALIFICATION (Bridge neuer als Qualifizierung)` und `ja` / `nein` / `unbekannt` | ehrlich ausgewiesen |
| `src/commander_lab/studio/static/partie.js:1137-1143, 1545, 1762` | Partie-Banner zeigt `BRIDGE_AHEAD_OF_QUALIFICATION · Bridge-JAR … (nicht durch versiegelte Epoche abgedeckt)` | ehrlich ausgewiesen |

## 2. Tabelle der 6 Abschlusskriterien (`docs/OWNER_DECISIONS_STUDIO_20261118.md` §6.6, SR25–SR30)

| # | Abschlusskriterium (SR25–SR30) | Stand (2026-11-24) | Beleg / was noch offen ist |
|---|---|---|---|
| **1 (SR25, PLAY)** | AK-1 bis AK-8 erfüllt und vom Owner bestätigt | **`UNKNOWN` / offen (`needs:owner`)** | Technik auf `main` (inkl. 5/6-Sitze-Freigabe `#1743`, Kohorte `PLAYED_GAME` `#1722`, Ehrlichkeitspille `#1735`, Real-Browser-Bericht `#1804`); es fehlt die erste vollständige **Owner-PLAY-Partie** (`#1661` Abnahme (e) + `#1662` AK-8). |
| **2 (SR26, SIMULATE)** | Eine vom Owner gestellte Chulane-Frage mit Serienplan, Ergebnis, Intervall, nachweisbarer Differenz und Gültigkeitsblock im Deck-Verlauf sichtbar | **`NOT_RUN` / in Arbeit** | Serienplan für `#1528` (Achse `36 / 38 / 40` + Kontrollen) liegt vor; Gültigkeitsblock & Reifegrad auf `main` (`#1790`, `#1801`); der große Nachtlauf am Owner-PC (`#1528`) ist noch `NOT_RUN` (wartet auf `#1589`). |
| **3 (SR27, BUILD)** | Deck geht ohne Handarbeit aus dem Deckbauer in Partie und Serie; Tierliste (`#1369`) vom Owner abgenommen; Gesamtrating entfernt | **teilweise belegt / Tierliste-Abnahme `UNKNOWN`** | Gesamtrating & `simulation`-Gewicht entfernt (`#1684`, `#1686`, `#1691`, `#1696`, `#1701`); B2-Roundtrip & „Als Variante testen“ auf `main` (`#1685`, `#1726`, `#1788`, `#1799`); explizite finale Tierlisten-Abnahme durch den Owner: `UNKNOWN`. |
| **4 (SR28, Regeln)** | `simulation`-Komponente entfernt (durch Test gesichert); 5/6 Sitze gesperrt oder vom Owner freigegeben; keine Zahl ohne `n/N` | **erfüllt (`CODE_DERIVED` / getestet)** | `simulation`-Gewicht entfernt & getestet (`#1686`/`#1696`); 5/6 Sitze durch Owner-Entscheid E16 freigegeben (`#1743`, 7/8 für SIMULATE nach E18 `#1762`); Zahlen-Vertrag B3 (`#1674`) und Reifegrad Q1-c (`#1717`/`#1729`/`#1776`/`#1801`) auf `main`. |
| **5 (SR29, Doku)** | Charta v2, Register (`OWNER_DECISIONS_STUDIO_20261118.md`), keine offenen Widersprüche | **erfüllt (`CODE_DERIVED`)** | `docs/STUDIO_CHARTA_V2.md`, `docs/OWNER_DECISIONS_STUDIO_20261118.md` (SR1–SR39) und Archivierung von Scope/Plan/Roadmap gemergt (`#1697`, `#1724`, `#1741`); `classify_docs.py --check` grün. |
| **6 (SR30, Betrieb)** | Einrichtung am Owner-PC aus dem Release-Paket von null nachvollzogen; Bridge-Zustand ehrlich ausgewiesen | **teilweise (`Bridge` belegt, Einrichtung von null `NOT_RUN`)** | Bridge-Zustand in allen 8 geprüften Studio-Dateien (Abschnitt 1) ehrlich als `BRIDGE_AHEAD_OF_QUALIFICATION` ausgewiesen; Ein-Klick-Starter `#1766` auf `main`. **Offen (`NOT_RUN`):** frischer Durchlauf „Einrichtung von null“ aus dem `release-artifacts.yml`-Paket mit ausgefülltem `docs/STUDIO_ABNAHME_PROTOKOLL.md` sowie Qualifikations-Dispatch-Messlauf (`NOT_SEALED`-Aufwand). |

## 3. Grenzen und offene Akzeptanzpunkte für den späteren Abschluss von `#1533`

- **Weiter `NOT_RUN` / `UNKNOWN`:**
  1. Qualifikations-Workflow-Lauf per Dispatch auf dem Abschluss-Stand (Laufzeit und `NOT_SEALED`-Bericht).
  2. Einrichtung von null aus dem Release-Artefakt am Windows-PC des Owners (mit 1 Partie + 1 Serie + ausgefülltem Abnahme-Protokoll).
  3. Finale Owner-Entscheidung zu Frage (a) (neue Epoche versiegeln oder dauerhaft `BRIDGE_AHEAD_OF_QUALIFICATION` nach dem Windows-PC-Test).
- **`qualification/**`, Engine-Pin, Fork und Pflicht-Checks wurden nicht berührt.**

# Open-Source-Recherche in vier Lanes (Deckbau, PLAY, SIMULATE, Querschnitt) — 2026-11-17

**Auftrag:** Nur Recherche, kein Bau. Welche Projekte, Methoden und Muster können dem Commander
Studio auf den drei Ebenen Deckbau, PLAY und SIMULATE helfen — und was davon ist unter den
Studio-Regeln tatsächlich einpflegbar?

**Methode/Ehrlichkeit:** Vier Web-Recherche-Läufe (Haiku-Modell) mit Seitenabruf von GitHub-/Doku-Seiten.
Sterne, Lizenz und Aktivität stammen aus den abgerufenen Seiten; **„unbekannt“ heißt nicht belegt.**
Viele Aktivitätsdaten fehlen, mehrere Seiten waren nicht abrufbar (Scryfall-Richtlinien: HTTP 403).
**Nichts davon wurde im Studio ausgeführt oder gegen unseren Code geprüft.** Lizenzaussagen sind
keine Rechtsberatung; vor jeder Code-Übernahme ist die LICENSE-Datei des Projekts selbst zu prüfen.

**Rahmen, der die Auswahl bestimmt:**
- `pyproject.toml` ist hash-gebunden und bleibt unverändert: **keine neuen Python-Abhängigkeiten**
  ohne Owner-Entscheid. Code-Übernahme ist daher nur als kleiner eigener Nachbau der Methode realistisch.
- AGPL/GPL-Projekte dienen **nur als Ideenquelle**, nie als Codequelle.
- Studio-Regeln: jede Zahl mit Nenner und Herkunft, unbekannt statt 0, keine Preise/Werte, keine
  Gesamtnote, kein Urteil „besser/schlechter“ ohne Intervall-Aussage, keine Simulation in der Tierliste.
- Datenquellen: kein automatisierter Abruf ohne geklärte Nutzungsbedingungen (Live-Collector ist ein
  Owner-Gate, #1192). Hier wurde **nichts abgerufen**.

## 1. Deckbau

| Projekt / Methode | Lizenz (belegt?) | Nutzen für uns | Bewertung |
|---|---|---|---|
| Karsten-Methode (hypergeometrisch, Farbquellen je Zug) | Methode öffentlich; kommerzielle Rechner ohne offene Quelle widersprechen sich bei der Zielschwelle | Kern der Manabasis-Analyse | **Haben wir** (`castability.py`, #1422/#1460) |
| mtgoncurve/landlord (Rust) | MIT, 36 Sterne, archiviert seit 2025-12 | unabhängige Gegenprobe für Mulligan-/Starthand-Werte | Idee: Testorakel gegen eigene Zahlen; Methodik nicht im Detail geprüft |
| MTGJSON | Code MIT (FAQ); Rechte an den Kartendaten unklar | lokale Stammdaten (Rollen, Farbidentität), keine Preise | Datenquelle erst nach Klärung der Daten-Rechte; wir haben Scryfall-Fakten im Store |
| Commander Spellbook (Backend) | Code MIT; Lizenz der Kombodaten und API-ToS nicht belegt | etabliertes Kombo-Schema | Datenmodell als Idee; Daten nicht spiegeln, bevor die Lizenz geklärt ist |
| mtg_parser (PyPI) | EUPL-1.2 | MTGO/Arena-Text-Import | nur Referenz (Format-Parsing); wir haben `decks.py`-Parser; kein URL-Scraping |
| Scryfall Tagger (`otag:`) | Scryfall-Terms nicht geprüft | Funktions-Labels mit Herkunft | **Haben wir** (Rollen aus otags, #1413) |
| Jaccard-Ähnlichkeit je Kohorte | Formel | n/N je Kohorte | **Haben wir** (`similar_decks.py`) |
| Deck-Diff / Versionsverlauf | — | — | **Haben wir** (#1423, Verlauf, Serien im Verlauf #1461); Recherche fand keinen besseren Kandidaten |

Verworfen: kommerzielle Karsten-Rechner (keine offene Quelle), Preis-/Budget-Tools, Lernprojekte.
**Fazit Deckbau:** Der Deckbuilder deckt die recherchierten Methoden bereits ab. Offen bleiben nur zwei
Ideen: (a) landlord-Werte als einmalige externe Gegenprobe der Starthand-Zahlen (Test, keine Abhängigkeit);
(b) Spellbook-Datenmodell erst nach geklärter Datenlizenz.

## 2. PLAY (Bedienmuster)

| Projekt | Lizenz | Muster zum Abschauen | Einordnung |
|---|---|---|---|
| phase.rs (React-Client) | MIT/Apache-2.0 | Battlefield, Stack, Zielwahl-Overlays, Mana-Bezahlung | Code übernehmbar, Rust/WASM-Engine irrelevant |
| Ironsmith | AGPL-3.0 (+ BSL-Datei ungeprüft) | Zielwahl mit Zielpfeil, Stack-Schiene, Tastatur, Inspektor | **nur Ideen** |
| Manabrew | AGPL-3.0-or-later | Browser-Client mit austauschbarer Engine | nur Ideen |
| Forge / Cockatrice / Magarena | GPL | Spielverlauf-UI, Zonen, Touch-Bedienung | nur Ideen |
| XMage | MIT | unsere Engine; Swing-Client mit Ziel-/Kampf-UI | Referenz |

**Muster, die sich für das Anklicken auf dem Brett eignen** (Owner-Wunsch 2026-11-17: „wie ein fertiges
Kartenspiel“): (1) legale Ziele hervorheben, Klick wählt, Bestätigen/Überspringen als Knöpfe; (2) Zielpfeil
als **SVG-Overlay** während der Wahl (ohne `innerHTML`/Inline-Style); (3) Stack-Schiene, neueste oben, Klick
zeigt die Ziele; (4) Tastatur: Pfeile zwischen Karten, Enter wählt, Esc bricht ab; (5) Hover-/Klick-Inspektor
mit Regeltext. **Randbedingung aus den Scryfall-Bildregeln (aus Spiegeln, nicht verifiziert):** Kartenbilder
nicht verzerren oder per CSS-Filter entsättigen/abdunkeln und Copyright-Zeile nicht verdecken → nicht legale
Karten über ein **Overlay** dämpfen, nicht über einen Filter auf dem Bild.
Stand im Repo: Ein Klick-Ausbau liegt unfertig auf dem Branch `play/board-click`; die Bridge liefert die
Objekt-IDs bereits (`metadata.object_id`, `source_object_id`, `attacker_id`, `blocker_id`, `defender_id`),
es ist reine Frontend-Arbeit (siehe Kommentar auf #1167).

## 3. SIMULATE (Statistik, Versuchsplanung)

| Quelle | Lizenz | Kern | Einordnung |
|---|---|---|---|
| Brown/Cai/DasGupta (Binomial-Intervalle) | Paper | Wilson/Jeffreys/Agresti-Coull statt Wald; Clopper-Pearson konservativ | **Haben wir** (Wilson); Methode bestätigt |
| statsmodels | BSD-3 | `proportion_confint`, `multipletests` (Holm, BH) | nur Referenz für Golden-Value-Tests, keine Abhängigkeit |
| Fishtest-Mathematik (pentanomial, GSPRT) | Doku | Paar-Ergebnisse als Einheit, SPRT-Stopp | passt zu unseren Paar-Serien; 2-Spieler-Methode, Übertragung auf 4 Sitze nicht gegeben |
| Always-valid Inference (Johari/Pekelis/Walsh) | Paper | CI bleibt bei datenabhängigem Stopp gültig | Idee für das laufende Intervall der Paar-Serie; Unabhängigkeit der Partien prüfen |
| OpenSkill (openskill.py) | MIT, 380 Sterne | Plackett-Luce-Wertung für 3+ Plätze | nur als Zusatzmetrik mit Unsicherheit denkbar; modelliert Sitz-/Seed-Effekte nicht; **nie in die Tierliste** |
| mtg-replay-notation | MIT, Community-Format | deterministische Replays aus Seed + Event-Log | Idee: Herkunftsfeld je `SIMULATED_RESULT` (Seed, Sitz-Mapping, Log-Hash) |
| mage-go `oracle-replay` | Lizenz unbekannt | prüft XMage-JSONL gegen Zustand je Priority-Punkt | Idee: Stichprobe als Replay-Treue-Prüfung |
| Forge (CLI-Simulation) | GPL-3.0 | KI-gegen-KI | höchstens Cross-Check-Stichprobe, kein Code |

**Nicht im Web belegt** (vor jeder Einpflege Lehrbuch/Primärquelle prüfen): Sitzrotation/Positionseffekte,
McNemar, gepaarter BCa-Bootstrap, Permutationstest, Power-Planung, Control-Variates, O'Brien-Fleming-/
alpha-spending-Grenzen. Holm/BH sind über statsmodels belegt: **Mehrfachvergleichs-Korrektur** wäre
relevant, sobald viele Karten-Vergleiche gleichzeitig ausgewertet werden (Newcombe-Differenz je Karte).

## 4. Querschnitt (Qualität, Daten)

| Werkzeug | Lizenz | Nutzen | Einordnung |
|---|---|---|---|
| Playwright `toHaveScreenshot` | n/a | Pixelvergleich mit Baselines, 3 Viewports | würde die manuellen 1080p-Sichtläufe automatisieren; CI hat heute keine Playwright-Suite → Owner-Entscheid (Abhängigkeit, Laufzeit, Baseline-Pflege) |
| `@axe-core/playwright` | MPL-2.0, ~737 Sterne | Barrierefreiheits-Prüfung als CI-Fail | gleiche Abhängigkeitsfrage; MPL-2.0 vor Einsatz prüfen |
| Lighthouse CI | unbekannt | Web-Vitals-Budgets | zu schwer für den Nutzen, Flakiness |
| pytest-recording (VCR.py) | MIT | Datenquellen-Tests ohne Netz | erst sinnvoll, wenn Abrufe erlaubt sind |
| Hypothesis / scipy.stats.hypergeom | unbekannt / n.b. | Invarianten und Referenzwerte für Wahrscheinlichkeitscode | Idee; Abhängigkeiten nur in Tests, trotzdem Owner-Frage wegen `pyproject.toml` |
| mutmut / cosmic-ray | unbekannt / MIT | Mutation-Testing nächtlich | optional, Laufzeit |
| pandera / Great Expectations | unbekannt / Apache-2.0 | Datenvalidierung | überdimensioniert, nicht empfohlen |

**Datenquellen (Nutzungsbedingungen für automatisierten Abruf):** Scryfall: unklar (ToS-Volltext nicht
abrufbar; unverifiziert 2 Anfragen/s bei Suche, Cache und User-Agent verlangt); MTGJSON: Code MIT, Rechte
an Kartendaten unklar; Commander Spellbook, EDHREC, Moxfield, Archidekt: **keine Bedingungen gefunden →
unklar**; EDHTop16/TopDeck: nicht recherchiert. **Folge: nichts automatisiert abrufen**, bis die Bedingungen
geklärt sind (deckt sich mit dem Owner-Gate zum Live-Collector).

## 5. Was daraus folgt

- **Deckbau (Owner-Zuständigkeit dieser Session):** nichts Neues zu übernehmen; die Recherche bestätigt die
  umgesetzten Methoden. Optional: landlord-Werte als einmalige Gegenprobe der Starthand-Tabelle.
- **PLAY (Gemini aktiv):** Ideen 1–5 oben für das Anklicken/Zielpfeil/Stack-Schiene/Tastatur; Bildabdunkelung nur
  per Overlay. Kein Code aus AGPL/GPL-Projekten.
- **SIMULATE (Gemini aktiv):** Kandidaten für die Paar-Serie: pentanomiale Auswertung, always-valid Intervall,
  Mehrfachvergleichs-Korrektur (Holm) bei vielen Karten-Vergleichen, Herkunftsfeld je Ergebnis.
- **Owner-Fragen:** (1) Dürfen Test-Abhängigkeiten (Playwright/axe, Hypothesis) in `pyproject.toml`/CI
  aufgenommen werden? (2) Soll jemand die Nutzungsbedingungen von Scryfall, EDHREC, Spellbook, Moxfield
  prüfen (Mensch, nicht automatisiert)?

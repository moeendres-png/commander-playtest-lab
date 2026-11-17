# Vergleichs-Recherche: Open-Source-Projekte vs. CPL-Deckbuilder (Studio-BUILD) — 2026-11-16

**Auftrag:** Nur Recherche, kein Bau. Wie die Schwester-Recherche für
Deckbuild Studio (DBS, gleicher Autorenkreis, 2026-11-16),
aber für den Deckbuilder im Repo `commander-playtest-lab` (Studio-Bereich
BUILD): Was kann sich der CPL-Deckbuilder an Features, Architektur,
Datenmodell und Code-Organisation von Open-Source-Projekten abschauen —
und was verbietet das CPL-Mandat?

**Methode/Ehrlichkeit:** Die 10 DBS-Projekte (Abschnitt A) wurden aus der
DBS-Recherche übernommen und **nicht** neu verifiziert; geprüft wurde nur
ihre Übertragbarkeit auf CPL. Die 7 neuen Projekte (Abschnitt B) wurden am
2026-11-16 per Repo-Seitenabruf geprüft (Beschreibung, Lizenz-Erkennung,
Commit-Zahl, Erstell-Datum, README). Sterne = Stand zum Abruf, als
Größenordnung zu lesen. Leistungszahlen aus READMEs sind **Eigenangaben
der Projekte**, keine Nachmessung.

**CPL-Maßstab (kurz):** Repo-Regeln `AGENTS.md` §1/§2: nur objektive Daten
mit Provenienz; jede Zahl mit Zähler und Nenner; Kohorten werden nie
addiert; Quelldaten sind an einen Commander gebunden; kein geratenes Tier;
Owner-Markierungen/Favoriten zählen nie als Bewertung;
**Simulationsergebnisse fließen nicht in die Tierliste** (Gewicht
`simulation` bleibt 0); die Rules-Autorität ist allein XMage — kein zweites
Regelwerk, auch kein „Spielzeug-Goldfish", erzeugt CPL-Evidenz.
Deckbuilder heute: Inclusion-Engine über dem lokalen Korpus (10.551 Decks,
davon 10.150 kanonisch, Tier-Universum 10.128; Kohorten nach Bracket und
Variante getrennt), Tierliste v3 als empirischer Index (Signale u. a.
`corpus_tuned`, `corpus_log_lift`, `corpus_bracket_slope`, `tournament`),
`land_advisor`, Sub-Archetyp-Tags (landfall / blink_bounce / big_mana /
clue_artifact / cedh_combo), Rollen-Claims, Spellbook-Combo-Signale,
EDHREC-/TopDeck-Daten im Store. Andock-Issues: **#1404** (Deckbau-Produkt-
prüfung, Kern-Issue, offen), #1323 (Deck-Browser — **geschlossen/erledigt**),
#1382 (Web-Bilder — **geschlossen/erledigt**), #1363 (Tierliste-Umbrella —
**geschlossen**), #1261 (Daten für objektivere Kartenbewertung, offen).
#1210 (Ernte aller Commander) ist Owner-gesperrt und wird hier nur als
Kontext genannt.

## Übersicht

| # | Projekt | Stack | Lizenz | Sterne | Aktivität (Beleg) | Herkunft |
|---|---|---|---|---|---|---|
| 1 | [CubeCobra](https://github.com/dekkerglen/CubeCobra) | Node/Express, DynamoDB/S3, React/TS | Apache-2.0 erkannt, README sagt ISC | ~268 | 8.149 Commits, seit 2019 | DBS-Übertragung |
| 2 | [Commander Spellbook Backend](https://github.com/SpaceCowMedia/commander-spellbook-backend) | Python/Django, PostgreSQL, React | MIT | ~38 | 3.625 Commits, 474 Releases, seit 2022 | DBS-Übertragung |
| 3 | [CardForge](https://github.com/urza-lab/cardforge) | FastAPI, React/TS, Postgres, Docker | GPL-3.0 | 0 | 43 Commits, seit Aug 2026 | DBS-Übertragung |
| 4 | [Cockatrice](https://github.com/Cockatrice/Cockatrice) | C++/Qt, CMake | GPL-2.0 | ~1.849 | 6.740 Commits, 53 Releases, seit 2011 | DBS-Übertragung |
| 5 | [MTGJSON](https://github.com/mtgjson/mtgjson) | Python (Pydantic/Polars) | MIT | ~485 | 1.759 Commits, tägliche Rebuilds, seit 2018 | DBS-Übertragung |
| 6 | [ManaTuner](https://github.com/gbordes77/manatuner) | React/TS-SPA, clientseitig | unklar (NOASSERTION) | ~3 | 374 Commits, Live v2.7.9, seit Jun 2025 | DBS-Übertragung |
| 7 | [mtg-commander-analyzer-mcp](https://github.com/kscius/mtg-commander-analyzer-mcp) | TypeScript, SQLite, MCP-Server | MIT | ~1 | 198 Commits, v0.7.0, seit Dez 2025 | DBS-Übertragung |
| 8 | [SparkRoot](https://github.com/gurleyryan/sparkroot) | Next.js/React, FastAPI, Supabase | BUSL-1.1 (kein OSI-OS) | 0 | 321 Commits, seit Jul 2025 | DBS-Übertragung |
| 9 | [commander-pod-deck-generation](https://github.com/virtu333/commander-pod-deck-generation) | Python-CLI | keine Lizenzdatei | 0 | 8 Commits, seit Mär 2026 | DBS-Übertragung |
| 10 | [Scrython](https://github.com/NandaScott/Scrython) | Python-Bibliothek | MIT | ~168 | 416 Commits, 15 Releases, seit 2018 | DBS-Übertragung |
| 11 | [commander-builder](https://github.com/LlamaAdam/commander-builder) | Python, SQLite, Web-UI | MIT | 1 | 582 Commits, 1 Release, seit Apr 2026 | **neu** |
| 12 | [MTG-Deck-Builder-MCP](https://github.com/Harshal12355/MTG-Deck-Builder-MCP) | Python (MCP-Server) | MIT | 1 | 35 Commits, seit Sep 2026 | **neu** |
| 13 | [mtg-deck-optimizer](https://github.com/OlliTapio/mtg-deck-optimizer) | Python-Skripte | **keine Lizenz erkannt** | 0 | 98 Commits, seit Mär 2026 | **neu** |
| 14 | [mtg_deck_builder](https://github.com/CathGrvt/mtg_deck_builder) | Python, Streamlit, GCP | MIT | 1 | 64 Commits, seit Dez 2025 (Fork) | **neu** |
| 15 | [bracket / MTG Analyzer](https://github.com/capywitch/bracket) | Python 3.11+, SQLite, FastAPI-Seed | MIT laut README, GitHub: NOASSERTION | 0 | 97 Commits, seit Sep 2026 | **neu** |
| 16 | [edhtop16](https://github.com/EDH-Top-16/edhtop16) | TypeScript, Next.js/Relay, MongoDB→SQLite | nicht festgestellt | nicht belastbar abgerufen | Website-Code zum cEDH-Turnierdienst | **neu, teilverifiziert** |
| 17 | [transmute](https://github.com/oflannabhra/transmute) | Python-CLI/Bibliothek | MIT | 2 | 43 Commits, 1 Release, seit Jul 2021 | **neu** |

---

## A. Übertragung der 10 DBS-Projekte auf den CPL-Deckbuilder

Pro Projekt nur das CPL-Urteil; die Projektbeschreibungen stehen in der
DBS-Recherche.

**1. CubeCobra** — *Teilweise übertragbar.* Die eine Filter-Syntax, die
Liste **und** alle Analyse-Ansichten steuert, passt direkt auf den
Deck-Browser (#1323, erledigt) und die Kartenfenster in #1404: Filtern im
Browser sollte Kookkurrenz- und Kohorten-Ansichten auf dieselbe Teilmenge
umrechnen statt je eigene Filter zu pflegen. Gespeicherte Analyse-Läufe
mit Delta zum Vorlauf sind das Muster für den Änderungs-Vergleich in
#1404. Nicht übertragbar: Draft-Simulation/Playtest und Elo/Power-Level
(Simulation bzw. Modell-Score; CPL zählt Kohorten). **Andockpunkt: #1404.**

**2. Commander Spellbook Backend** — *Stark übertragbar, CPL nutzt die
Daten schon.* Das Feature/Tag-Modell (Tags = benannte Feature-Mengen,
`is:infinite` ↔ Feature) ist die Blaupause, CPLs Sub-Archetyp-Tags und
Combo-Signale aus hartcodierten Listen in pflegbare Feature-Mengen zu
überführen — dieselbe Denkfigur wie DBS #142, hier für Tags wie
`cedh_combo`. Neu für CPL aus der Spellbook-Welt: das **Bracket-Tag je
Combo** (`bracketTag` im API-Payload) ist ein Quelldatum mit Provenienz
und kann als Boden-Signal in der Combo-Bewertung geprüft werden (vgl.
Projekt 15). Nicht übertragbar: der Bracket-Schätz-Endpunkt als
Deck-Urteil. **Andockpunkt: #1363-Nachfolge / #1404 (D9 Combo-Handlungswert).**

**3. CardForge** — *Ideen übertragbar (GPL, kein Code).* Drei Muster für
CPL: (a) Import als Preview/Confirm/Abort mit Fehlerbericht je Zeile plus
verbindlichem Format-Dokument — für den fehlenden Listen-Import in #1404
(D5: kein „Neues Deck", keine Liste einfügen); (b) Daten-Frische als
Anzeige (Alter jeder Quelle im Status) — CPLs Store mischt EDHREC-,
TopDeck- und Korpus-Stände, deren Alter heute nirgends in der BUILD-Sicht
steht; (c) die Ehrlichkeits-Beschriftung abgeleiteter Aggregate
(„computed, not an actual decklist") für CPLs Konsens-/Durchschnitts-
Ansichten. Nicht übertragbar: Preis-/Kauf-Kern („collection leverage",
Budget-Filter, Shopping-Listen) — #1404 verbietet Preise und Zukauf
ausdrücklich. **Andockpunkt: #1404 (D5, Frische-Anzeige neu).**

**4. Cockatrice** — *Schwach übertragbar.* Das Zonen-Modell (Tokens als
eigene Zone/Sicht, aus den Erzeugern abgeleitet) passt zur Token-Sicht im
Deckbau; die UI-freien Bibliotheken (Decklisten-Modell und Filter ohne
UI) bestätigen CPLs Trennung Store/Engine vs. Web-Schicht. Der
Spiel-Client ist für BUILD irrelevant; anders als in DBS ist Spiel-Code
in CPL nicht verboten, gehört aber zur XMage-Lane, nicht in den
Deckbuilder. **Andockpunkt: #1404 (Token-Sicht, klein).**

**5. MTGJSON** — *Stark übertragbar (Pipeline/Tests, MIT).* Provider-
Muster mit Identifiers-Submodell (alle Fremd-IDs an einer Stelle) ist
CPLs Join-Disziplin für Scryfall-/EDHREC-/TopDeck-IDs; das
`Meta.json`-Frische-Pollen und vor allem die **VCR-Cassettes** (HTTP-
Antworten aufgezeichnet, CI offline) sind die Antwort auf CPLs
Sync-Flakiness: Ernte-/Import-Tests (EDHREC, TopDeck, Archidekt) würden
deterministisch statt live laufen. Nicht übertragbar: Preis-Aggregation
als Datenfeld. **Andockpunkt: neu (Test-Organisation), #1261 (Datenwege).**

**6. ManaTuner** — *Methodik übertragbar, Lizenz vorher klären.*
Castability je Karte × Zug (T1–T7, exakt hypergeometrisch) und bedingte
Quellen (Cavern-Regel) plus Ramp-Typen jenseits von Ländern sind die
inhaltliche Erweiterung für CPLs `land_advisor` — der in #1404 (D1)
gerade an einem Kohorten-Filter (`mainboard` statt `main`) scheitert;
nach dem Bugfix ist die kartenfeine Rechnung der natürliche Ausbau.
Nicht übertragbar: Monte-Carlo-Mulligan, „optimale Länderzahl" als
Empfehlungs-Urteil, Mana-Health-Score. CPL zeigt Wahrscheinlichkeiten
mit Nenner, keine Note. **Andockpunkt: #1404 (land_advisor).**

**7. mtg-commander-analyzer-mcp (kscius)** — *Teilweise übertragbar
(MIT).* Regelwerk als versionierte Daten-Dateien (Bracket-Regeln,
Templates, Banlist als Textdatei) passt zu CPLs Kohorten-Definitionen:
Bracket-/Kohorten-Regelstände sollten als datierte Daten mit Quelle im
Repo liegen statt als Code-Konstanten. Die Kategorie-Korridore
(Anzahl gegen min/max, Status „within") sind das deskriptive Muster für
#1261 Punkt 4 (Rang in der Funktion). `evaluate_card_swap` ist ein
Verwandter des Tausch-Helfers in #1404. Nicht übertragbar: `synergyScore`
und Quality-Gate (Urteile), EDHREC-Autofill ohne lokale Kohortenbindung.
**Andockpunkt: #1404, #1261.**

**8. SparkRoot** — *Nur Ideen (BUSL).* „House Rules" als benannte,
gespeicherte Regel-Sets sind für CPL als **benannte Kohorten-/Filter-
Profile** denkbar (z. B. ein gespeichertes BUILD-Profil „nur Bracket 4+5,
ohne unclassified"), solange sie nur filtern und nie bewerten. Nicht
übertragbar: Salt-Score, Deck-Generierung mit Qualitätsurteil,
Preis-Roadmap. **Andockpunkt: #1404 (D6: Universum/Profile im Deckbauer).**

**9. commander-pod-deck-generation (virtu333)** — *Nur Einzelmuster
(keine Lizenz).* Der `load-bulk-data`-Schritt (Scryfall-Bulk einmal
laden, danach lokal auflösen) ist CPLs bestehende Praxis und bestätigt
sie; der Multi-Format-Export in einem Lauf (`--format` mehrfach) ist das
Muster für CPLs Deck-Export (Moxfield/Archidekt/Text aus einer Quelle).
Die Bracket-Kategorien-Liste (Game Changer, Infinite Combos, MLD,
Extrazüge) ist als **Zähl-Kategorien** übernehmbar, ihre Verdichtung zu
einer Bracket-Zahl nicht. **Andockpunkt: #1404 (Export), #1363-Nachfolge.**

**10. Scrython** — *Übertragbar (MIT).* Gestaffeltes Rate-Limiting als
zentrale Client-Policy je Endpunkt-Klasse + TTL-Cache + Bulk-first ist
die Vorlage für CPLs Scryfall-/EDHREC-Zugriffe in den Ernte-Skripten —
eine Client-Schicht statt verstreuter `sleep`-Aufrufe (vgl. auch die
Client-Konventionen bei Projekt 11). **Andockpunkt: neu (Sync-Schicht).**

---

## B. Neue Projekte (für CPL recherchiert und verifiziert)

### 11. commander-builder (LlamaAdam) — der inhaltlich nächste Verwandte

Python, SQLite, lokale Web-UI; „closed-loop deck improvement": LLM
schlägt Tausche vor, eine Forge-Simulation entscheidet empirisch, ein
SQLite-Wissenslog akkumuliert Iterationen. MIT — **Code kopierbar.**
582 Commits, 1 Release, seit April 2026, aktiv.

**Für CPL abschauenswert (Daten-/Analytik-Teile):**
- **Vier-Quellen-Korpus mit Haus-Client-Konventionen:** EDHREC-JSON-,
  Archidekt-, Moxfield- und **edhtop16-GraphQL-Client** teilen sich ein
  Muster: injizierbare `fetch_json`-Naht (testbar ohne Netz), Disk-Cache
  mit 24-h-TTL, **no-cache-on-empty** (die Quelle antwortet bei
  unbekanntem Commander mit HTTP 200 plus GraphQL-`errors` — ein 200er
  ist kein Erfolg) und ausd
...[truncated 15865 chars]rücklicher Kennzeichnung
  „exploratory, NOT a validated predictor" für die Turnierquelle. Das ist
  exakt die Härtung, die CPLs Ernten (EDHREC/TopDeck/Archidekt) brauchen.
- **edhtop16 als vierte Korpus-Quelle:** Der GraphQL-Endpunkt liefert je
  Commander Statistiken (`count`, `conversionRate`, `winRate`), komplette
  Sieger-Listen und **`cardWinrateStats`** — Conversion/Win-Rate **mit
  und ohne** eine Karte. Das ist die Datenform, die #1261 Punkt 1
  (Turnier-Conversion je Karte als Signal `tournament_conversion`)
  verlangt; CPLs heutiges `tournament`-Signal kommt aus EDHTop16/
  TopDeck, aber ohne diese Mit/Ohne-Gegenüberstellung je Karte.
- **„Lift picks":** Kandidaten und stärkste Paare werden per
  **Kookkurrenz-Lift über dem eigenen geernteten Korpus** gereiht —
  dieselbe Größe wie CPLs `corpus_log_lift`, dort aber zusätzlich als
  Deckbau-Anzeige („pairs well with your deck") aufbereitet. Beleg, dass
  sich der Lift aus dem Store direkt in die BUILD-Ansicht holen lässt.
- **Rollen-Zielkorridore:** `staples.ROLE_TARGETS` + `role_target_report()`
  speisen die Deck-Health-Kacheln — deskriptive Soll-Korridore je Rolle
  statt einer Note; Muster für #1261 Punkt 4 (Rang in der Funktion).
- **Versionierung:** Snapshot-Befehle frieren Deck-Versionen ein,
  `commander-history`/`revert` machen Änderungen nachvollziehbar —
  Vorläufer eines Deck-Diffs (vgl. Projekte 12/15).

**Nicht übernehmen:** der Forge-Simulations-Verdict-Loop selbst (fremde
Engine als Qualitätsbeweis — CPLs Rules-Autorität ist XMage, und
Simulation fließt nicht in die Tierliste), Health-Grade A–F und der
0–100-Health-Score als Budget-Automatik (verdichtete Urteile),
„cheaper-printing savings" (Preise), LLM-Kurator als Entscheider.

**Architektur:** Python-Paket `src/commander_builder`, ~30 CLI-Befehle
hinter einer gemeinsamen Front-Door, SQLite-Wissenslog, pre-commit wie
CI. **Lizenz: MIT.**

### 12. MTG-Deck-Builder-MCP (Harshal12355) — Deck-Diff und Universal-Parser

Python-MCP-Server mit 28 Tools über Scryfall, Spellbook, EDHREC und
Archidekt; dazu eine Referenz-Bibliothek kuratierter Decks. MIT —
**Code kopierbar.** Jung (35 Commits, seit Sep 2026), aber mit Testsuite
und CI-Badge.

**Für CPL abschauenswert:**
- **`compare_decks`:** zwei Listen in einem Batch vergleichen —
  `cards_added`, `cards_removed`, `similarity_pct` und exakte Vorher/
  Nachher-Deltas je Kennzahl. Das ist die Form, die CPLs Änderungs-
  Vergleich (#1404) braucht — **abzüglich** der Score-Deltas (Bracket,
  Power Score), die CPL nicht übernehmen darf; Zähl-Deltas (Kurve,
  Rollen, Farben, Länder) sind dagegen reine Fakten.
- **Universal Decklist Parser:** ein Parser für Moxfield (inkl.
  Druckangaben, Foils, `#tags`, Commander-Block), Arena, Archidekt
  (`[Category]`), MTGO, Deckstats (`*CMDR*`) und Klartext; Alternativ-
  Namen (Secret Lair / Universes Beyond) werden automatisch auf die
  Oracle-Karte aufgelöst. Direkt relevant für #1404 D5 (Liste einfügen).
- **`archidekt_popular_cards`:** Inclusion-% über einer Stichprobe der
  Top-N-Decks eines Commanders (Bracket-Filter möglich), optional nur
  Karten, die noch nicht im eigenen Deck sind — dieselbe Anzeige-Logik
  wie CPLs „ähnliche Quelldecks" in #1404, dort gegen den lokalen
  Korpus zu rechnen statt gegen Live-Archidekt.
- **`analyze_mana_base`:** Karsten-Rechnung als exakte Hypergeometrie —
  Quellen-Bedarf je Farbe zu 90 %, Cast-Raten Zug 1–8, Defizite je Farbe
  (Ergänzung zu Projekt 6 für den `land_advisor`); `search_lands`
  katalogisiert 24 Land-Zyklen mit Speed-Klassen (untapped/conditional/
  tapped) — ein Land-Zyklen-Katalog als Daten, nicht als Code-Listen.
- **`find_tokens`:** alle Tokens eines Decks inkl. Zähl-Empfehlung aus
  Batch-Erzeugung, wiederholbaren Triggern und Verdopplern — die
  Ableitungs-Logik hinter Cockatrice' Token-Zone (Projekt 4).

**Nicht übernehmen:** Power Score 0–10, 3-School-Score, Mana Base Grade
S–D (Noten), Preis-Tools und Budget-Cut-Vorschläge, der Monte-Carlo-
Goldfish als „Beweis" (CPL-Goldfish-Fragen gehören zur XMage-Lane).

**Architektur:** ein Tool = eine klar benannte Fähigkeit mit
strukturierter Rückgabe; Referenz-Bibliothek als versionierte Daten
mit Provenienz je Deck (Autor, Erfassungszeit). **Lizenz: MIT.**

### 13. mtg-deck-optimizer (OlliTapio) — Synergie als belegte Paar-Bewertung

Flache Python-Skript-Sammlung (Archidekt-Pull, Deck-Analyse, Synergie,
Combos, Tausche) mit Tests je Kernmodul. **Keine Lizenz im Repo erkannt
→ nur Ideen, kein Code.** 98 Commits, seit März 2026.

**Für CPL abschauenswert:**
- **`synergy.py` — produces/cares-about:** Jede Karte wird aus Keywords,
  Typen und Triggern mit Tags versehen, **was sie erzeugt** und **was
  sie braucht**; ein Paar punktet nur, wenn Erzeuger und Payoff beide
  vorhanden sind (zehn Karten ohne Payoff = 0). Commander-Paare zählen
  doppelt, Spellbook-Combos geben einen Paar-Bonus. Entscheidend ist die
  Hausregel dahinter: **„The model never judges synergy unaided"** —
  jedes Score-Ergebnis trägt den Kartentext als Beleg. Das ist CPLs
  Evidenz-Semantik (§4) als Produktregel und ein Gegenentwurf zu CPLs
  heutiger Alternativen-Sortierung in #1404 D3, die Synergie gar nicht
  kennt: Eine **erklärbare Paar-Sicht** (welche Karten im Deck füttern
  einander, mit Beleg) wäre ein gezähltes, prüfbares Signal — kein
  Urteil.
- **`otag_fetcher.py`:** Scryfalls Community-Funktions-Tags („otags")
  werden je Karte geholt und lokal gecacht. Das ist exakt die
  Quellen-Art, die #1261 Punkt 4 für die Rollen-Lücke verlangt
  („nur aus Quell-Tags oder regelabgeleiteten Merkmalen, nie von einem
  Agenten vergeben").
- **`combos.py`:** Spellbook-Treffer und Near-Misses werden **gegen das
  Deck-Bracket geprüft** — Muster, Combo-Anzeigen (#1404 D9) mit
  Kohorten-Kontext statt nackter Trefferlisten zu zeigen.

**Nicht übernehmen:** der eigene Spiel-Simulator/Autopilot (zweite
Rules-Engine — in CPL verboten), `price_check.py`.

**Architektur:** bewusst flach (ein Skript = ein Werkzeug, Tests daneben);
für CPL nur als Methodik-Lektüre, nicht als Bauform. **Lizenz: keine
erkannt.**

### 14. mtg_deck_builder (CathGrvt) — Cluster- und Embedding-Methodik

Python/Streamlit, Fork mit produktionsartigem Agenten- und Eval-Überbau.
MIT — **Code kopierbar.** 64 Commits, seit Dez 2025.

**Für CPL abschauenswert (nur Methodik):**
- **`deck_corpus_builder` + `train_deck_generator`:** Deck-Vektoren
  werden per (MiniBatch-)KMeans zu Archetyp-ähnlichen Clustern
  gruppiert; Oracle-Texte werden per TF-IDF + SVD zu dichten
  Karten-Vektoren verdichtet. Das ist die einzige gefundene
  Open-Source-Referenz für **datengetriebene Sub-Archetypen** — als
  **Gegenprobe** zu CPLs regelbasierten Sub-Archetyp-Tags (#1368-Linie)
  interessant: Stimmen Cluster und Tag-Mengen überein, und wo nicht,
  warum? Das Projekt benennt seine Grenze selbst: Cluster sind **nicht
  automatisch beschriftet und nicht strategisch validiert** — für CPL
  heißt das: Cluster dürfen Analyse-Hypothesen sein, nie Tier- oder
  Tag-Wahrheit; Beschriftung nur über gezählte Evidenz.
- **Eval-Harness mit Fehler-Taxonomie** (`retrieval_miss`,
  `bad_citation`, `hallucinated_claim`, `off_topic_claim`) plus
  Benchmark-Snapshots und Trace-Logs je Lauf: ein Muster, wie CPL
  künftige Analyse-Features mit einem festen Fall-Korpus gegen
  Regressionen prüft, statt nur Unit-Tests zu zählen.

**Nicht übernehmen:** LLM-Reranking und Deck-Generierung als
Produktversprechen, GCP-/Agenten-Überbau (für CPLs lokale
SQLite-Architektur überdimensioniert).

**Architektur:** Korpus-Bau, Analyse und Generator teilen sich eine
`DeckSpec`-Schnittstelle; UI ist austauschbar. **Lizenz: MIT.**

### 15. bracket / „MTG Analyzer" (capywitch) — Bracket-Methodik und Deck-Diff

Lokales Einzelplatz-Werkzeug: Python-Engine (UI-frei) hinter einer
Service-Fassade (`AnalyzerService`), CLI `mtg`, dünner FastAPI-Seed.
README sagt MIT, GitHub erkennt „Other/NOASSERTION", eine LICENSE-Datei
liegt bei — **vor Code-Übernahme LICENSE direkt lesen.** 97 Commits,
seit Sep 2026.

**Für CPL abschauenswert:**
- **Bracket-Signale als getrennte, benannte Bausteine:** Die Game-
  Changer-Liste wird als **externe, versionierte Daten** behandelt
  (Scryfall-`game_changer`-Flag statt Handliste), und das **Combo-
  Bracket-Tag von Commander Spellbook** speist das Combo-Signal als
  **Boden (floor), nicht als Decke**; fehlt ein Tag, greift eine lokale
  Heuristik statt einer erfundenen Zahl. Für CPL ist das die Methodik,
  mit der sich die **Kohorten-Zuordnung** eigener Decks prüfen lässt
  (deklariertes Bracket gegen gezählte Signale) — nicht als Anzeige-
  Urteil, sondern als Datenqualitäts-Abgleich.
- **`mtg deck diff <a> <b>`:** Decklisten-Vergleich als einfacher,
  benannter Befehl — neben Projekt 12 der zweite Beleg, dass „Diff"
  als eigenes Werkzeug (nicht als UI-Nebenprodukt) die richtige Form
  für #1404s Änderungs-Vergleich ist.
- **Goldfish-Mathematik mit `scipy.stats.hypergeom`** (exakt statt
  Stichprobe) und ein **Matchlog** realer Spielergebnisse als eigener
  Datenbestand — Letzteres ist konzeptionell CPLs Playgroup-Denken
  (#1261 Punkt 3: beobachtete Korrelation, als solche beschriftet).

**Nicht übernehmen:** das heuristische Battle-/Matchup-Modell mit
Power-Level-Ranking über Deck-Pools (Sim-Urteil), Budget-Shopping-
Listen, EDHREC-„blended" Empfehlungen mit Budgetdeckel.

**Architektur:** Engine strikt UI-frei, alle Orchestrierung hinter der
Service-Fassade; Datenbestand regenerierbar und gitignored, nur
synthetische Fixtures im Repo. **Lizenz: MIT laut README (s. o.).**

### 16. edhtop16 (EDH-Top-16) — die Quelle hinter CPLs Turnier-Signal

Website-Code des cEDH-Turnierdienstes EDHTop16 (Next.js/Relay,
TopDeck.gg-API als Quelle). **Nur teilweise verifiziert:** Die
Repo-Seite lieferte beim Abruf nur die README-Kurzbeschreibung;
Stack- und Modellangaben stammen aus den im Repo-Umfeld einsehbaren
Architektur-Notizen (MongoDB-Datenlager → generierte lokale SQLite,
Kysely-Migrationen, Commander-Normalisierung über Scryfall-Oracle-IDs,
DecklistItem als Many-to-many zwischen Entry und Karte). Lizenz und
Commit-Zahlen wurden **nicht** festgestellt — vor jeder Code-Übernahme
neu prüfen; hier zählt die Datenarchitektur, nicht der Code.

**Für CPL abschauenswert:**
- **Zweistufige Datenhaltung:** rohes Turnier-Datenlager (MongoDB)
  getrennt von der generierten, normalisierten Auswertungs-DB
  (SQLite) — dieselbe Trennung, die CPL zwischen Ernte-Rohdaten und
  Store pflegt; die nächtliche Regeneration der Auswertungs-DB aus
  dem Lager ist das Vorbild für einen wiederholbaren Turnier-Import
  statt inkrementeller Handpflege.
- **Commander-Normalisierung über Oracle-IDs** statt Namen — CPLs
  eigene Lektion aus der Fingerprint-Normalisierung (#1394) wird hier
  von der Quelle selbst bestätigt.
- Die öffentliche GraphQL-Sicht (`cardWinrateStats`, vgl. Projekt 11)
  zeigt, dass die Mit/Ohne-Conversion je Karte **quellseitig existiert**
  und nicht aus Rohlisten nachgerechnet werden muss.

**Andockpunkt: #1261 Punkt 1.**

### 17. transmute (oflannabhra) — Format-Registry für Listen-Formate

Python-CLI/Bibliothek zur Konvertierung von Sammlungs-CSVs zwischen
16 Formaten (u. a. Archidekt, Moxfield, ManaBox, Deckstats, MTGO).
MIT — **Code kopierbar.** 43 Commits, 1 Release, seit 2021.

**Für CPL abschauenswert:**
- **`FormatRegistry`-Muster:** Je Format ein Handler mit `read`/
  `write`, dazu **Auto-Erkennung des Eingabeformats aus den
  CSV-Headern** — die Bauform für CPLs Listen-Import/-Export (#1404
  D5), damit neue Formate als Daten + Handler dazukommen statt als
  Parser-Sonderfälle.
- **Verlust-Ehrlichkeit als Dokumentation:** Jedes Format hat eine
  Spezifikation mit Beispiel **und** einer Limitations-Tabelle (was
  bei der Konvertierung verloren geht, z. B. Set-Namen vs. -Codes,
  Pflicht-Scryfall-IDs). Für CPL heißt das: Import zeigt vor dem
  Bestätigen, welche Angaben der Quelle nicht übernommen werden —
  dieselbe Ehrlichkeitslinie wie CardForges Import-Bericht (Projekt 3).

**Nicht übernehmen:** Preis-Spalten mehrerer Formate (beim Import
ignorieren, nicht in den Store übernehmen).

**Architektur:** `src/transmute`-Paket, pytest + ruff, PyPI-Paket
(`transmute-mtg`). **Lizenz: MIT.**

---

## Mandats-Filter: NICHT übernehmbar (CPL)

| Was | Herkunft | Warum nicht |
|---|---|---|
| Simulations-Verdicts als Deck-Qualität | commander-builder (Forge-Loop), capywitch (Battle-Modell), Harshal (Monte-Carlo-Goldfish) | CPLs Rules-Autorität ist allein XMage; Simulationsergebnisse fließen nicht in die Tierliste (Gewicht 0, #1261 Owner-Entscheid) und sind keine BUILD-Evidenz. |
| Verdichtete Noten/Scores | commander-builder (Health-Grade A–F, 0–100), Harshal (Power Score, Mana Base Grade, 3-School), kscius (Synergy-Score/Quality-Gate), CubeCobra (Elo/Power-Level) | Verdichtung von Heuristiken zu einer Note = geratenes Tier. CPL zeigt gezählte Signale mit Nenner. |
| Bracket-**Zahl** als Deck-Ergebnis | commander-builder, capywitch, Harshal (Schätzungen), virtu333 (Ziel-Bracket) | WotC-Brackets enthalten Intent-Anteile. CPL nutzt Brackets als Quell-Kohorten; eine geschätzte Zahl als Anzeige wäre ein Urteil. (Methodik zur Kohorten-QA: s. Projekt 15.) |
| Preise, Kauf-/Budget-Features | commander-builder (cheaper printing), Harshal (Preis-Tools), CardForge (collection leverage), transmute (Preis-Spalten), capywitch (Shopping-Listen) | #1404-Regeln: keine Preise, kein Zukauf; Karten außerhalb der Sammlung nur hinter Schalter. |
| ML-Scores als Ranking | CathGrvt (Cluster/Reranking), CubeCobra (Smart Search) | CPL-Rankings sind gezählte Kohorten-Werte (Inclusion/Lift). Cluster nur als Analyse-Gegenprobe, nie als Tier/Tag. |
| Zweite Rules Engine / Spielzeug-Simulator | OlliTapio (Autopilot-Sim), Cockatrice-Spielteil für BUILD | AGENTS.md §2: keine zweite Rules Engine, keine heuristische Legalität. |
| Rollen/Tags von einem Agenten vergeben | (Anti-Muster, in #1261 ausgeschlossen) | Rollen nur aus Quell-Tags (z. B. otags, Projekt 13) oder regelabgeleiteten Merkmalen, mit Abdeckung je Rolle. |

## Priorisierte Abschauen-Liste

| # | Punkt | Herkunft | Nutzen für CPL | Aufwand | Issue-Bezug |
|---|---|---|---|---|---|
| 1 | Turnier-Conversion je Karte (mit/ohne Karte) als Signal `tournament_conversion` | commander-builder (edhtop16-Client), edhtop16 | Schließt #1261s größten Daten-Gewinn (Prio 1.1) mit vorhandener Quellen-API statt Rohlisten-Nachrechnung | M | #1261 (läuft über #1258) |
| 2 | Alternativen/Tausch-Helfer nach gezählter Inclusion/Lift des eigenen Korpus sortieren statt nach Rolle/Name | commander-builder (Lift picks), Harshal (`archidekt_popular_cards`) | Behebt #1404 D3 direkt; nutzt vorhandene Signale (`corpus_log_lift`), keine neue Datenquelle | S–M | #1404 (Ergänzung) |
| 3 | Kookkurrenz-Anzeige mit Stichproben-Ehrlichkeit (n/N, Gruppen < 30 kennzeichnen, nie „100 %" ohne Nenner) | #1323-Methodik, commander-builder (Paar-Lift) | Behebt #1404 D4; überträgt die erledigte Browser-Methodik ins Kartenfenster | S | #1404 (Ergänzung) |
| 4 | Deck-Diff/Versionsvergleich als eigene Ansicht: added/removed + Zähl-Deltas (Kurve, Rollen, Länder), ohne Score-Deltas | Harshal (`compare_decks`), capywitch (`deck diff`), commander-builder (Snapshots) | Änderungs-Wirkung wird sichtbar; Grundlage für Verlaufs-Denken statt Momentaufnahme | M | neu (Refs #1404) |
| 5 | Rollen-Lücke aus Scryfall-otags schließen + Rang-in-der-Funktion-Korridore | OlliTapio (`otag_fetcher`), commander-builder (ROLE_TARGETS), kscius (Korridore) | #1261 Prio 2.4: faire Vergleichsgruppen; Abdeckung je Rolle mit Nenner statt verzerrter Vergleiche (#1404 D2) | M | #1261 (Unter-Issue) |
| 6 | Listen-Import als Preview/Confirm mit Fehlerbericht je Zeile; Universal-Parser + Format-Registry | CardForge, Harshal (Parser), transmute (Registry) | Behebt #1404 D5 (kein Liste-Einfügen/Neues Deck); Formate werden erweiterbare Daten | M | #1404 (Ergänzung) |
| 7 | Manabasis-Methodik: Castability je Karte × Zug + bedingte Quellen + Land-Zyklen-Katalog | ManaTuner, Harshal (`analyze_mana_base`, `search_lands`) | `land_advisor` wird nach dem D1-Bugfix von Aggregaten zu kartenfeinen Aussagen mit Nenner | M | #1404 (Ergänzung) |
| 8 | Client-Konventionen für alle Quellen: injizierbare Fetch-Naht, TTL-Cache, no-cache-on-empty, VCR-Fixtures in CI | commander-builder, MTGJSON, Scrython | Ernten werden testbar und deterministisch; stille Fehler (200 + errors) fallen auf statt Daten zu verfälschen | M | neu (Daten-Pipeline) |
| 9 | Kohorten-/Bracket-Regelstände als versionierte Daten-Dateien mit Quelle + Stand; Combo-`bracketTag` als Boden-Signal prüfen | kscius, capywitch/Spellbook | Regeländerungen (WotC Okt 2025) werden nachvollziehbar; Combo-Signal gewinnt ein Quelldatum | S | #1363-Nachfolge, #1404 D9 |
| 10 | Cluster-Gegenprobe zu den Sub-Archetyp-Tags (KMeans auf Deck-Vektoren, TF-IDF/SVD auf Oracle-Texten) | CathGrvt | Prüft die regelbasierten Tags (#1368) datengetrieben, ohne sie zu ersetzen; Abweichungen werden erklärungsbedürftige Funde | M–L | neu (Analyse) |

## Nicht verifiziert / verworfen

- **MythGauntlet / mythforgemtg** (onemorethan0): misst Brackets per
  Spiel-Simulation mit Konfidenzintervall; der Kern liegt nach eigener
  Status-Doku in einem privaten Repo — nicht prüfbar und methodisch
  das Gegenteil der CPL-Linie (Sim-Verdict). Nicht aufgenommen.
- **alxhghs/mtg-deck-analyzer:** In einem Blogbeitrag verlinkt, das
  Repo antwortete beim Abruf mit 404 — nicht aufgenommen.
- **Kahno/cedh_database_analysis:** alter HTML-Scraper für die cEDH-
  Decklist Database (Plattform-Parser u. a. gegen eine alte
  Moxfield-API) — als Bauform überholt; die Plattform-Erkennung als
  Idee ist in Projekt 17 aufgegangen. Nicht aufgenommen.
- **AI-Skill-/Prompt-Repos** aus der Suche (u. a. P47Phoenix
  mtg-commander-Skill, reakaleek- und artemlitch-Skill-Sammlungen):
  keine eigene Engine/Codebasis — wie in der DBS-Recherche verworfen.
  Ausnahme der Form halber: OlliTapio (Projekt 13) führt echte,
  getestete Python-Werkzeuge und wurde deshalb aufgenommen.
- **DylnMtthws/deck-lab, ByronWilliamsCPA/MTG_AI:** nur Planungs-/
  Gerüst-Stand bzw. RAG-Kritik-Assistent im Aufbau — keine tragfähige
  Referenz. Nicht aufgenommen.
- **EDH-Top-16-Detaildaten:** Lizenz, Sterne und Commit-Zahl des
  Website-Repos konnten beim Abruf nicht festgestellt werden
  (Repo-Seite lieferte nur die Kurzbeschreibung) — Projekt 16 ist
  deshalb als teilverifiziert markiert; seine Datenarchitektur ist
  zusätzlich über den Client von Projekt 11 belegt.
- **Lizenz-Diskrepanzen** (capywitch: MIT laut README vs. NOASSERTION;
  CubeCobra/ManaTuner aus der DBS-Recherche) ließen sich per
  Seitenabruf nicht auflösen — vor jeder Code-Übernahme die
  LICENSE-Datei im Repo direkt lesen. Bei OlliTapio fehlt eine
  erkannte Lizenz ganz; bei den GPL-Projekten (CardForge, Cockatrice)
  und SparkRoot (BUSL) ist Code-Übernahme unabhängig davon
  ausgeschlossen — dort zählen nur die Ideen.

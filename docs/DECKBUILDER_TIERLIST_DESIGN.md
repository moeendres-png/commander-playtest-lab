# Design: Tierlist-Umbau und Deck-Universum-Einstellungen im CPL-Studio-Deckbuilder

**Stand:** Design-Dokument, keine Implementierung. Alle Aussagen sind Mechanik-, Schema- oder
Quellen-Fakten aus dem CPL-Repo (`src/commander_lab/studio/`, gelesen auf dem aktuellen
Arbeitsstand) oder als `UNKNOWN` markiert (Abschnitt 6).
**Regeln dieses Dokuments:** Es enthält ausschließlich objektive Daten und Mechaniken. Es
bewertet keine Karte. Es legt keine Schwellenwerte fest: Jeder Schwellenwert ist ein
Parameter, dessen Wert der Owner setzt (Abschnitt 3.4). `UNKNOWN` ist nie `0` und nie ein
bestandenes Kriterium (Repo-Regel, AGENTS.md §4).

---

## 0. Ist-Befund (verifiziert per Code-Durchsicht)

- **Es gibt im CPL-Studio kein Tier-System.** Weder `store.py`, `builder.py`, `roles.py`,
  `data_report.py`, `queries.py`, `importers.py`, `web.py` noch das Frontend
  (`static/index.html`, `static/app.js`) enthalten eine Tier-Funktion oder Tier-Anzeige.
  Der „Umbau" ist daher: Einführung von Tiers als parametrisierte, reine Funktion über den
  bereits vorhandenen Datenstrukturen — kein Ersatz einer vorhandenen Tier-Logik.
- **Vorhandene Bausteine, auf denen der Entwurf aufsetzt:**
  - `observation` (Tabelle): jede externe Kennzahl liegt als Zeile mit `metric`, `cohort`,
    `value`, `numerator`, `denominator`, `data_class`, `url`, `snapshot`, `source_id`.
  - `corpus_deck` / `corpus_deck_card` / `corpus_cohort`: lokal gespeicherte Roh-Decklisten
    (Hub-Korpus: 975 deduplizierte Chulane-Decks, Quelle `active_drive:chulane-corpus-975`,
    VERIFIED). Zählungen daraus sind jederzeit lokal nachrechenbar.
  - Kohorten-Mechanik existiert: `builder.cohort_sizes()` (Gruppen: `all`, je `play_group`,
    je benannte Kohorte), `builder._corpus_hits()`, `queries.corpus_inclusion()`
    (Zähler/Nenner je Karte, optional `play_group`-Filter; Nenner 0 ⇒ Anteil `None` =
    unbekannt, nicht null).
  - `pool_cards()` zeigt je Karte heute genau **eine** EDHREC-Beobachtung: die mit dem
    größten Nenner (`ORDER BY denominator DESC`, erste je `card_id`). Diese implizite
    Auswahl ist der Punkt, den das Universum-Modell (Abschnitt 2) durch eine ausdrückliche
    Owner-Auswahl ersetzt.
  - Datenklassen (`store.DataClass`): `ORIGINAL_SOURCE`, `NORMALIZED_SOURCE`,
    `DERIVED_DESCRIPTIVE`, `HEURISTIC_MODEL`, `SIMULATED_RESULT`, `UNKNOWN`. Jede Zahl im
    Studio trägt eine davon; Tiers erben die Klasse ihrer Rechenvorschrift (Abschnitt 3.2).
  - Provenienz: `source` (SHA-256, `snapshot_date`, `imported_at`) und
    `source_capture_event` (Rohantwort-SHA-256, HTTP-Status, Zeitpunkte) existieren.
  - Schema-Version des Stores: 7. Alle bisherigen Schema-Schritte ergänzen nur Tabellen
    und Views (Kommentar in `store._prepare`); additive Tabellen sind der Migrationsweg.
  - Existierende Konstanten (Code-Fakten, **keine** Empfehlungen dieses Dokuments):
    `SMALL_DENOMINATOR = 30` in `builder.py` und `data_report.py` (Markierung „kleiner
    Nenner" im Datenbericht), `SCRYFALL_STALE_AFTER_DAYS = 30` in `data_report.py`.

---

## 1. Signal-Inventar

Jedes Signal mit: Quelle, exaktem Feld / Datenherkunft im Store, Einheit, Stichprobe,
Aktualisierungsweg, Datenklasse. Signale sind in vier Gruppen getrennt: **(A) Zähl-Signale
aus Decklisten**, **(B) Fakten-Felder**, **(C) simulierte Werte**, **(D) Marker ohne
Stärke-Aussage** und **(E) harte Kennzeichnungen**. Nur Gruppen A–C sind als Eingaben der
Tier-Funktion zulässig (C nur per Owner-Schalter, Abschnitt 3.4); D ist Anzeige-only,
E ist Filter/Flag, nie Punktwert.

### 1.A Zähl-Signale aus Decklisten (Evidence-Layer `OBSERVED_DECK`)

| # | Signal | Quelle | Feld / Herkunft im Store | Einheit | Stichprobe | Aktualisierung |
|---|--------|--------|--------------------------|---------|------------|----------------|
| A1 | Korpus-Inclusion | lokales Korpus (`corpus_deck_card` ⨝ `corpus_deck`) | Zähler = `COUNT(DISTINCT deck_id)` mit `section != 'sideboard'` und `duplicate_of IS NULL`; Nenner = Universumsgröße &#124;U&#124; | Zähler / Nenner (Anteil abgeleitet) | &#124;U&#124;, aktuell 975 im Hub-Korpus (`all`) | Neuimport des Korpus (`import_hub_corpus`, `import_corpus_cards`, `import-cohort`); danach jederzeit per SQL nachrechenbar, `DERIVED_DESCRIPTIVE` |
| A2 | EDHREC-Inclusion (Commander-/Theme-Seite) | EDHREC JSON (`edhrec:chulane`, VERIFIED) | `observation.metric = 'inclusion_pct'`, `numerator = cardviews.num_decks`, `denominator = cardviews.potential_decks`, `value = numerator/denominator × 100`; `cohort = 'edhrec:<theme>'` bzw. `'edhrec_snapshot_<datum>:<slug>'` | Zähler / Nenner (Quelle), Prozentwert | `denominator` der Quelle je Seite | `import-edhrec-manifest` (mit `source_capture_event`, Roh-SHA-256), `import_edhrec_table`, `import_edhrec_cardrecs_csv`; idempotent je `source_id` |
| A3 | EDHREC-Inclusion (Bracket-Kohorten, historisch) | EDHREC-Delta-Dateien | `observation.cohort ∈ {'edhrec:core_b2_563_index', 'edhrec:core_b2_634_hist', 'edhrec:upgraded_b3_593_hist'}`; `numerator = decks_with_card*` | Zähler; **Nenner teilweise fehlend** (`eligible_decks_per_card` ist dort `None`/NOT_LISTED) | je Datei unterschiedlich | Einmal-Importe (`_import_one_edhrec_delta_file`); Importer-Regel: Kohortengröße wird **nie** als Karten-Nenner eingesetzt — fehlender Nenner ⇒ Inclusion `UNKNOWN` |
| A4 | EDHREC-Lift | EDHREC JSON | `observation.metric = 'lift'`, `value` aus `cardviews.lift`; `numerator`/`denominator` = `NULL` | Verhältniswert der Quelle (ohne Zähler) | nicht als Zähler verfügbar | wie A2 |
| A5 | EDHREC-Synergy | EDHREC JSON | `observation.metric = 'synergy_pct'`, `value = cardviews.synergy × 100` (Importer-Konvention); Zähler `NULL` | Prozentwert der Quelle (ohne Zähler) | nicht als Zähler verfügbar | wie A2 |
| A6 | Co-Occurrence | lokales Korpus | `builder.card_cooccurrence()`: `both_hits` (Decks mit beiden Karten) / `card_decks` (Decks mit der Ausgangskarte), je Kohorte | Zähler / Nenner | `card_decks` | reine Ableitung aus A1-Daten, `DERIVED_DESCRIPTIVE` |
| A7 | Neutral-Board-Zählungen | Hub-Batch-Dateien | `neutral_board_row`: Treffer je Sektion (`MAYBEBOARD`, `CUTS`, `SIDEBOARD`) / Anzahl Batch-Quellen je Sektion | Zähler / Nenner | Batch-Quellen je Sektion | Hub-Import; **wird nie mit Mainboard-Frequenzen vermischt** (bestehende Regel in `builder.card_neutral_boards`) |
| A8 | Rollen-Zugehörigkeit | Scryfall Tagger (Claims) + Oracle-Text-Prüfung | `card_role_claim` (mit `role_origin ∈ {SCRYFALL_TAGGER_ORIGINAL, CROSSWALK_NORMALIZED, ORACLE_TEXT_REVIEW, LEGACY_UNSPECIFIED}`, `scope_key`, Original-Tag) → abgeleitet `card_role`; Zählung je Deck in `corpus_deck_role` | Mitgliedschaft (ja/nein) je Rolle (17 Rollen, `roles.ROLES`) | — (Klassifikation, keine Stichprobe) | `fetch-roles` (öffentliche Scryfall-Suche, nur Farbidentität als Anfrage) + `import-roles`; Claims-Modell mit `FULL_SNAPSHOT`/`PARTIAL_INCREMENTAL` |
| A9 | Deck-Form-Verteilungen | lokales Korpus | `corpus_deck_stat` (Länder, Kreaturen, Ø-Manawert Nichtland) und `builder.cohort_shapes()`: Median, p25, p75 je Kohorte | Verteilungs-Kennwerte je Deckmenge | Decks mit `resolved = cards` (unvollständig aufgelöste Decks werden gezählt und ausgeschlossen) | Ableitung aus Korpus; Perzentil-Mechanik `builder._percentile` (lineare Interpolation) existiert |

Quellen-Fakt zur Einordnung von A4 (steht so im Register `sources.py`): „Lift is relative
deck co-occurrence, NOT winrate lift." — A4/A5 sind Mitauftretens-Werte der Quelle, keine
Spielergebnis-Werte.

**Verteilung der EDHREC-Decks des Commanders nach Bracket** (von EDHREC publizierte
`bracket_counts` für Chulane, Kontext-Fakt): `{"1": 45, "2": 558, "3": 755, "4": 695,
"5": 233}`, Summe 2.286. Das ist ein Verteilungs-Fakt über das EDHREC-Deck-Universum,
kein Karten-Signal. Ob die Summe distinkte Decks zählt, ist eine offene Faktenfrage
(Abschnitt 6, U7).

### 1.B Fakten-Felder (Evidence-Layer `FACT` / `DERIVED_MECHANICAL`)

| # | Feld | Quelle | Herkunft im Store 
...[truncated 25977 chars]Einheit | Aktualisierung |
|---|---|---|---|---|---|
| B1 | Kartenfakten (Manawert, Typzeile, Farbidentität, Keywords, `produced_mana`, `released_at`) | Scryfall Bulk (`scryfall:bulk-oracle`, VERIFIED) | `scryfall_card`-Spalten; Zugriff über View `card_fact` | Feldwerte je `oracle_id` | Bulk-Import `import-scryfall`; Stand über `source.snapshot_date`, Bericht meldet Alter (`stale` ab 30 Tagen, Code-Konstante) |
| B2 | `edhrec_rank` | Scryfall (Feld des Bulk-Datensatzes) | `scryfall_card.edhrec_rank` | Rangzahl der Quelle (Rekurrenz über alle Commander-Decks bei EDHREC, Definition der Quelle) | wie B1 |
| B3 | XMage-Regelunterstützung | XMage, gepinnter Pin (`xmage:card-facts`, VERIFIED) | `builder.sim_readiness_status()` gegen Repo-Kartenfakten + Pilot-Katalog | Status je Karte (`OK` / `READY` / `UNKNOWN`) | Repo-Datei `data/cards/xmage_card_facts.json`, Pin in `config/rules_engines.json`; laut Register 7.231 Karten, Pool 801/801 `OK` |
| B4 | Combo-Teilnahme | Commander Spellbook (`spellbook:variants-api`, VERIFIED) | `sources.load_spellbook_combo_cards()` liest `data/meta/spellbook_combos.json` (Kartenmenge je Commander) | Mitgliedschaft (ja/nein); Varianten-Details liegen nur in der Quelldatei | Datei-Stand des Combo-Katalogs; Register-Regel: redundante Varianten sind keine unabhängigen Belege |

### 1.C Simulierte Werte (Evidence-Layer `SIMULATED_RESULT`) — getrennt zu führen

| # | Signal | Herkunft im Store | Einheit | Stichprobe |
|---|--------|-------------------|---------|------------|
| C1 | Cast-Gelegenheiten je Karte | `simulation_card`: `games_offered`, `games_cast_after_offer`, `games_rotted`, `offered_castable`, `cast_count`, `mean_first_cast_round` | Zähler je Lauf | `games_completed` des Laufs |
| C2 | Laufergebnis | `simulation_run`: `win_rate`, `wins_fractional`, `mean_rounds`, `games_planned/completed/failed`, dazu `engine_pin`, `pilot_policy`, `seeds`, `pod` | Anteile/Zähler je Lauf | Spiele des Laufs |

C-Werte stammen aus lokalen XMage-Spielen gegen die im Lauf gespeicherten Pods und
Pilot-Policies (keine Beobachtung fremder Decks). Ob sie in eine Tier-Berechnung
eingehen, ist ein Owner-Schalter (Parameter `simulation_einbeziehen`, Abschnitt 3.4);
die Anzeige kennzeichnet sie immer mit ihrer Datenklasse `SIMULATED_RESULT` und der
`run_id`.

### 1.D Marker ohne Stärke-Aussage — Anzeige-only, nie Tier-Eingabe

| # | Marker | Sachverhalt |
|---|--------|-------------|
| D1 | Salt-Score (EDHREC) | EDHREC publiziert auf Kartenseiten einen Salt-Wert (Quellen-Fakt aus dem übergeordneten Datenplan). Die CPL-Importer lesen aus EDHREC-JSONs ausschließlich `num_decks`, `potential_decks`, `lift`, `synergy` — ein Salt-Feld wird lokal **nicht** gespeichert. Lokaler Bestand: **nicht vorhanden**. Vorgesehene Ablage bei Beschaffung: `observation.metric = 'salt'`, `ORIGINAL_SOURCE`, ohne Zähler/Nenner. Keine Tier-Eingabe (Mechanik-Regel 3.3). |
| D2 | Preis | `scryfall_card` enthält **keine** Preisfelder (Schema geprüft). Scryfall-Preise sind druckbezogen (je Druck, nicht je `oracle_id`); ein „Preis je Karte" braucht eine Festlegung (z. B. günstigster Druck), die im aktuellen Import nicht existiert. Lokaler Bestand: **nicht vorhanden**, Beschaffungsweg offene Faktenfrage (Abschnitt 6, U4). Keine Tier-Eingabe. |
| D3 | Owner-Marken | `card_mark` (`favorite`, `excluded`, `note`) ist die persönliche Markierungsebene des Owners. Sie wirkt als Anzeige/Filter (z. B. `excluded` blendet Vorschläge aus — bestehendes Verhalten von `pool_cards`), ist aber **keine** Eingabe der Tier-Funktion (Mechanik-Regel 3.3). |

### 1.E Harte Kennzeichnungen — Flags/Filter, nie Punktwerte

| # | Kennzeichnung | Herkunft | Mechanik |
|---|---------------|----------|----------|
| E1 | Commander-Legalität / Banned | `scryfall_card.commander_legality` (String, u. a. `legal`/`banned`); abgeleitet `card_fact.commander_legal` (0/1) | `legal_pool()` und `pool_cards()` filtern auf `commander_legal = 1`: nicht legale Karten sind im Pool gar nicht enthalten. Das Legalitäts-Feld wird als Fakt angezeigt; es gibt keine Punkte. |
| E2 | Game Changer | `scryfall_card.game_changer` (1 / 0 / `NULL` = unbekannt) | Boolean-Flag in der Kartenanzeige (`pool_cards` liefert `game_changer` je Karte bereits mit). `NULL` bleibt „unbekannt", wird nicht zu 0. Keine Punkte, kein Tier-Einfluss. |

---

## 2. Deck-Universum-Modell

### 2.1 Zwei Universum-Typen (Mechanik-Unterscheidung)

- **Listen-Universum:** eine Teilmenge der lokal gespeicherten Roh-Decklisten
  (`corpus_deck`-Zeilen). Inclusion ist daraus vollständig und jederzeit **nachrechenbar**.
- **Aggregat-Universum:** eine Auswahl bereits aggregierter Quell-Kohorten in
  `observation` (EDHREC-Seiten/-Snapshots). EDHREC liefert keine Roh-Decklisten; Inclusion
  ist dort nur als gespeicherter Zähler/Nenner der Quelle verfügbar und **nicht** aus
  Listen nachrechenbar. Beide Typen werden im Profil und in jeder Anzeige als solche
  gekennzeichnet; Werte beider Typen werden nie in einer Zahl vermischt.

### 2.2 Filterdimensionen (Listen-Universum)

Jede Dimension ist ein Filter über vorhandenen Spalten/Tabellen; nicht gesetzte
Dimensionen filtern nicht.

| Dimension | Feld / Tabelle | Sachverhalt |
|---|---|---|
| Herkunft/Quelle | `corpus_deck.source_id` → `source` (`title`, `data_class`, `snapshot_date`, `imported_at`); `corpus_deck.platform` | Wählbar je Importquelle/Batch |
| Spielgruppe | `corpus_deck.play_group` | Werte aus dem Bestand, z. B. `community`, `turnier_cedh`, `unklassifiziert` (Fallback des Hub-Imports) |
| Benannte Kohorte | `corpus_cohort` (`cohort`, `deck_id`) | Deck kann in mehreren Kohorten sein; `cohort_sizes()`/`_corpus_hits()` behandeln benannte Kohorten bereits generisch |
| Bracket 1–5 | **keine Spalte in `corpus_deck`** | Die Hub-Katalog-CSV trägt `bracket_user_set` je Deck; der Importer nutzt es heute nur als Ausschluss (verifizierte Bracket-1-Decks bleiben draußen). Zwei mechanische Wege: (a) beim Import zusätzlich Kohorten-Zeilen `bracket:<n>` in `corpus_cohort` schreiben — **keine Schemaänderung**, nutzt die vorhandene Kohorten-Mechanik; (b) neue Spalte `corpus_deck.bracket INTEGER NULL` mit Herkunft über `source_id`, falls Bracket als Deck-Attribut mit eigener Provenienz geführt werden soll. Weg (a) ist der schemafreie; die Entscheidung ist Implementierungsdetail von Paket D1 |
| Thema/Archetyp | `corpus_deck.tags` (TEXT); EDHREC-seitig: Theme-Seiten als `observation.cohort = 'edhrec:<theme>'` | Nur soweit die Quelle es liefert. Das Tag-Format ist nicht typisiert (der Datenbericht zählt nur `tags_missing`) ⇒ Themen-Filter über Korpus-Tags ist eine offene Faktenfrage (U5). EDHREC-Themes sind dagegen als Kohorten bereits real |
| Zeitraum | `corpus_deck.deck_date` | Filter `deck_date BETWEEN von AND bis`. Decks ohne Datum (`deck_date IS NULL`/leer; der Datenbericht zählt sie als `date_unknown`) fallen aus datumsgefilterten Universen heraus und werden in der Universums-Beschreibung als eigene Zahl ausgewiesen („davon ohne Datum: n, nicht enthalten") |
| Commander | kein Feld in `corpus_deck` | Zugehörigkeit ist heute nur über Herkunft/Kohorte gegeben (Hub-Korpus = Chulane-Decks). Ein Commander-Filter über mehrere Korpus-Quellen ist ohne neues Feld nur über Kohorten abbildbar (U6) |
| Legalitäts-Audit | `corpus_deck.legality_audit` | Filter auf Audit-Status ist als Dimension vorgesehen; die Wertemenge steht im Bestand |
| Duplikate | `corpus_deck.duplicate_of` | Feststehende Regel aller heutigen Zählungen: nur `duplicate_of IS NULL` zählt. Inhaltliche Duplikate des Katalogs (994 Quellen → 975 Unikate) zeigen auf ihren Repräsentanten |
| Sektionen | `corpus_deck_card.section` | Es zählt nur das Mainboard (`section != 'sideboard'`); Neutral-Boards (A7) zählen nie in Inclusion |
| Mindest-Stichprobe (Universum) | &#124;U&#124; ≥ Parameter `min_stichprobe_universum` | Unterschreitung ⇒ keine Berechnung, Status „Universum unter Mindestgröße" statt Zahlen (Anschluss an `corpus_inclusion`: Nenner 0 ⇒ Anteil `None`) |

### 2.3 Profile

- **Neue Tabelle `universe_profile`** (`profile_id TEXT PRIMARY KEY`, `name TEXT`,
  `universe_type TEXT` ∈ {`LIST`, `AGGREGATE`}, `definition_json TEXT`, `created_at TEXT`,
  `updated_at TEXT`). `definition_json` enthält ausschließlich die Dimensionen aus 2.2
  (Listen-Typ) bzw. eine Liste von `observation.cohort` + Snapshot-Auswahl (Aggregat-Typ).
- **Standard-Profil „alle Decks"** ist fest verdrahtet (nicht löschbar): leere
  Filtermenge, entspricht dem heutigen `ALL_DECKS`-Verhalten von `builder`/`queries`.
- Profile liegen im Store (nicht nur im Browser), damit sie rechnerübergreifend und in
  Berichten referenzierbar sind — wie alle übrigen Arbeitszustände (`card_mark`,
  `deck_draft`) auch.
- **Snapshot/Reproduzierbarkeit:** Bei jeder Berechnung wird eine Zeile in der neuen
  Tabelle `universe_snapshot` festgehalten: `snapshot_id` (Hash über Profil-Definition,
  sortierte `deck_id`-Liste des aufgelösten Universums, je beteiligter Quelle
  `source_id` + `snapshot_date`/`imported_at`, Store-Schema-Version), `profile_id`,
  `universe_size`, `resolved_at`. Optional materialisiert `universe_snapshot_deck`
  (`snapshot_id`, `deck_id`) die Mitgliedschaft, damit eine historische Berechnung exakt
  nachvollzogen werden kann, auch wenn der Korpus später wächst.

### 2.4 Inclusion-Definition (reine Zählung)

Für ein Listen-Universum U und eine Karte k:

```
zaehler_U(k)  = |{ d ∈ U : k steht im Mainboard von d }|      (COUNT(DISTINCT deck_id))
inclusion_U(k) = zaehler_U(k) / |U|                            (|U| > 0; sonst UNKNOWN)
```

- Zähler und Nenner werden **immer gemeinsam** gespeichert und angezeigt
  (Repo-Konvention, `builder.py`: „A figure about source decks always comes with its
  denominator").
- Für ein Aggregat-Universum gilt `inclusion(k) = observation.numerator /
  observation.denominator` der gewählten Kohorte. Fehlt der Nenner (Fall A3), ist die
  Inclusion dieser Karte in diesem Universum `UNKNOWN` — sie wird nicht durch die
  Kohorten-Deckzahl ersetzt (bestehende Importer-Regel).
- Abwesenheit ist typabhängig: Im Listen-Universum ist „nicht enthalten" der definierte
  Zähler 0. Im Aggregat-Universum ist „nicht gelistet" **kein** 0-Wert: EDHREC lässt den
  Long-Tail (< 1 %) auf Commander-Seiten aus (Register-Fakt), Abwesenheit dort heißt
  `UNKNOWN`.
- Keine Schema-Neuerfindung über die zwei Tabellen in 2.3 hinaus: Mitgliedschaft,
  Zählung und Kohorten laufen über `corpus_deck`, `corpus_deck_card`, `corpus_cohort`;
  Aggregate bleiben in `observation`; Provenienz in `source`/`source_capture_event`.
  Eine Ergebnis-Ablage (Cache) ist optional und in Abschnitt 3.5 als ableitbare,
  jederzeit löschbare Tabelle spezifiziert.

---

## 3. Tier-Mechanik

### 3.1 Grundform

Ein Tier ist das Ergebnis einer reinen Funktion

```
tier(karte, universum_snapshot, parametersatz) → (tier | U, aufschluesselung)
```

ohne Seiteneffekte und ohne Zugriff auf Daten außerhalb der genannten Eingaben.
Gleiche Eingaben (Snapshot-ID + Parameter-Hash) ergeben immer dasselbe Ergebnis; das
macht jeden Tier-Wert reproduzierbar und in Tests festnagelbar.

### 3.2 Eingaben und Datenklasse

- Zulässige Eingaben: Signale der Gruppen A und B (Abschnitt 1) sowie — nur bei
  gesetztem Parameter `simulation_einbeziehen` — Gruppe C.
- Die Datenklasse des Ergebnisses folgt der Rechenvorschrift: reine Zählung/Perzentile
  über gespeicherten Beobachtungen ⇒ `DERIVED_DESCRIPTIVE`. Sobald der Owner Gewichte
  über mehrere Signale legt (`aggregationsmodus = gewichtet`), ist das Ergebnis ein
  Modell und wird als `HEURISTIC_MODEL` gekennzeichnet — die Klasse steht in jeder
  Aufschlüsselung, sie wird nicht versteckt.
- Rangbildung: Perzentil des Primärsignal-Werts innerhalb der Vergleichsmenge (alle
  Pool-Karten mit definiertem Wert im gewählten Universum). Die Perzentil-Mechanik
  (lineare Interpolation über der sortierten Werteliste) existiert als
  `builder._percentile` und wird wiederverwendet.

### 3.3 Feste Mechanik-Regeln (keine Parameter)

1. Marker (Abschnitt 1.D) und harte Kennzeichnungen (1.E) sind keine Eingaben der
   Tier-Funktion. `card_mark` wird von der Tier-Funktion nicht gelesen.
2. Fehlender Nenner ⇒ kein Wert (nie Ersatznennner, nie 0).
3. Tier-Zustand `U` ist ein eigener Zustand neben den Tiers, kein unterster Tier.
4. Jede Anzeige eines Tier-/Inclusion-Werts zeigt Universum (Profil + Snapshot-ID +
   Größe) und Zeitpunkt der Datenstände mit an (Abschnitt 4.3).

### 3.4 Parameter (alle Werte setzt der Owner)

Gespeichert als benannte Parametersätze in der neuen Tabelle `tier_parameter_set`
(`parameter_set_id`, `name`, `definition_json`, `created_at`, `updated_at`); ein Hash
der Definition (`parameter_hash`) geht in jede Berechnung ein.

| Parameter | Typ | Wirkung |
|---|---|---|
| `primaersignal` | Enum: `corpus_inclusion` \| `edhrec_inclusion` \| `getrennt` | Bestimmt, aus welchem Zähl-Signal (A1 bzw. A2/A3) die Rangbildung erfolgt. `getrennt` = je Quelle ein eigener Tier, nebeneinander angezeigt, keine Vermischung |
| `aggregationsmodus` | Enum: `eins` \| `gewichtet` | `eins`: nur das Primärsignal zählt. `gewichtet`: mehrere Signale gehen mit `gewichte` ein; Ergebnis-Datenklasse wird `HEURISTIC_MODEL` |
| `gewichte` | Map: Signal-ID → Zahl ≥ 0 | Nur bei `aggregationsmodus = gewichtet`; Gewichte der nicht genannten Signale = 0 |
| `grenz_modus` | Enum: `perzentil` \| `anteil` | Ob Tier-Grenzen als Perzentile der Vergleichsmenge oder als Inclusion-Anteile (0–1) gelesen werden |
| `tier_grenzen` | Liste von Zahlen (Länge = Tier-Anzahl − 1), streng fallend | Grenzen zwischen den Tiers im gewählten Modus. Tier-Namen/Anzahl folgen aus der Listenlänge; die oberste Grenze trennt zum höchsten Tier |
| `min_stichprobe_karte` | Integer ≥ 0 | Karten, deren Signal-Nenner (Listen-Universum: &#124;U&#124;; Aggregat: `observation.denominator`) kleiner ist, erhalten `U` mit Grund `SAMPLE_BELOW_MIN` |
| `min_stichprobe_universum` | Integer ≥ 0 | Universen unter dieser Größe werden nicht berechnet (Status statt Zahlen) |
| `fehlende_signale` | Enum: `strikt` \| `ignorieren` | `strikt`: fehlt ein für die Rechenvorschrift nötiges Signal, erhält die Karte `U` (`NO_OBSERVATION`/`DENOMINATOR_MISSING`). `ignorieren`: gerechnet wird mit den definierten Signalen; die Aufschlüsselung listet die fehlenden ausdrücklich |
| `simulation_einbeziehen` | Bool | Ob Gruppe C (C1) als Signal zugelassen ist; Anzeige der `run_id` ist dann Pflichtbestandteil der Aufschlüsselung |
| `duplikate_zaehlen` | Bool (Bestands-Mechanik: `false`) | `false`: nur `duplicate_of IS NULL` (heutige Regel). `true`: Duplikate zählen als eigene Decks — ändert Zähler und Nenner und wird im Snapshot vermerkt |
| `vergleichsmenge` | Enum: `pool` \| `universum_beobachtet` | Ob Perzentile über allen Pool-Karten mit definiertem Wert oder nur über den im Universum beobachteten Karten gebildet werden |

### 3.5 Zustand `U` und Grund-Codes

`U` („ungenügende Daten") wird mit genau einem Grund-Code geführt:

| Code | Auslöser (mechanisch) |
|---|---|
| `NO_OBSERVATION` | Karte hat im gewählten Universum keine Beobachtung (Aggregat) bzw. ist in der Vergleichsmenge nicht vertreten |
| `DENOMINATOR_MISSING` | Beobachtung vorhanden, aber Nenner fehlt (Fall A3) |
| `SAMPLE_BELOW_MIN` | Nenner < `min_stichprobe_karte` |
| `UNIVERSE_TOO_SMALL` | &#124;U&#124; < `min_stichprobe_universum` (gilt für alle Karten des Laufs) |
| `SOURCE_STATUS_REVIEW` | Das verwendete Signal stammt aus einer Quelle mit Register-Status `REVIEW` und der Parametersatz verlangt VERIFIED-Quellen (Verknüpfung zum Quellen-Register in `sources.py`) |

### 3.6 Aufschlüsselung je Karte (Anzeige-Spezifikation)

Jeder Tier-Wert wird mit dieser Struktur ausgeliefert (API-Feld
`tier_breakdown` an Karten-Detail und Pool-Zeilen):

```
{
  "tier": "…" | "U",
  "u_reason": <Code aus 3.5> | null,
  "data_class": "DERIVED_DESCRIPTIVE" | "HEURISTIC_MODEL",
  "universe": {
    "profile_id": "…", "profile_name": "…", "universe_type": "LIST" | "AGGREGATE",
    "snapshot_id": "…", "universe_size": <int>,
    "filter": { …gesetzte Dimensionen aus 2.2… }
  },
  "parameter_set_id": "…", "parameter_hash": "…",
  "computed_at": "<UTC>",
  "signals": [
    { "signal_id": "A1", "source_id": "active_drive:chulane-corpus-975",
      "cohort": "all", "numerator": <int|null>, "denominator": <int|null>,
      "value": <float|null>, "data_class": "…",
      "snapshot": "<Quellen-Snapshot/imported_at>", "percentile": <float|null> }
  ]
}
```

Fehlende Signale erscheinen in `signals` mit `value: null` und dem passenden
`u_reason`-Bezug — sie werden nicht weggelassen, damit „nicht gemessen" von „0"
unterscheidbar bleibt (vgl. `data_report.NOT_MEASURED`-Prinzip).

Ergebnis-Cache (optional): Tabelle `tier_result` (`snapshot_id`, `parameter_set_id`,
`card_id`, `tier`, `u_reason`, `breakdown_json`, `computed_at`). Der Cache ist eine
reine Ableitung: Löschen und Neuberechnen aus Snapshot + Parametersatz muss identische
Zeilen ergeben (Test in Paket R3).

---

## 4. Einstellungs-Oberflächen

### 4.1 Bestehende Oberflächen (Ist)

- Web-UI (`static/index.html`/`app.js`): Pool-Ansicht mit Filtern (Suche, Farbe, Typ,
  Rolle), Auswahl „Vergleichsgruppe" (`<select id="cohort">`) und „Sortierung";
  Karten-Detail; Deck-/Varianten-Ansichten; Partie-Ansicht (gehört zu PLAY, nicht zum
  Deckbuilder).
- API (`web.py`): `GET /api/pool?commander=…`, `GET /api/cohorts`,
  `GET /api/cards/{card_id}?cohort=…`, `GET /api/status`, dazu Deck-/Draft-/Mark-Endpunkte.
- CLI (`__main__.py`): u. a. `pool`, `inclusion <karte> [--group]`, `check`, `export`,
  die Import-Befehle und `import-edhrec-manifest`.

### 4.2 Wo welche Einstellung wirkt (Design)

| Oberfläche | Einstellung | Wirkung dort |
|---|---|---|
| Kopfzeile aller Deckbuilder-Ansichten | **Aktives Universum-Profil** (Auswahl aus `universe_profile` + Standard „alle Decks") | Steuert alle Inclusion-/Tier-Werte der Ansicht; ersetzt mechanisch die heutige implizite Auswahl (breiteste EDHREC-Kohorte in `pool_cards`, `cohort`-Parameter der API wird zu `profile_id`) |
| Kopfzeile, zweite Auswahl | **Aktiver Parametersatz** (`tier_parameter_set`) | Steuert Tier-Berechnung und `U`-Verhalten aller Ansichten |
| Pool-Ansicht | Tier-Spalte + Sortierung „Tier", Filter „nur Tier X / nur U" | Zeigt je Karte Tier oder `U`+Grund-Code; die vorhandenen Spalten (Korpus-Treffer je Kohorte, EDHREC-Wert) bleiben und zeigen weiterhin Zähler/Nenner des aktiven Universums |
| Pool-Ansicht, Profil-Editor | Profile anlegen/ändern/löschen (Dimensionen aus 2.2 als Formular) | Schreibt `universe_profile`; jede Änderung erzeugt bei der nächsten Berechnung einen neuen Snapshot (neue Snapshot-ID) |
| Karten-Detail (`/api/cards/{id}`) | `tier_breakdown` (Struktur 3.6) + Inclusion im aktiven Universum | Zeigt zusätzlich die Werte aller gespeicherten Profile auf Wunsch (Vergleichsansicht der Universen, strikt getrennt ausgewiesen) |
| Deck-Ansicht (Variante/Diff) | Anzeige des aktiven Universums unverändert global | Diffs/Form-Werte (`deck_shape`, `diff_lists`) sind universumsunabhängig (sie zählen die Liste selbst); Tier-Werte einzelner Karten in der Liste folgen dem globalen Profil |
| CLI | `inclusion <karte> --profile <id>` (Erweiterung des bestehenden `--group`); neuer Befehl `tiers --profile <id> --parameter-set <id>` | Gleiche Rechenkerne wie die API, keine zweite Implementierung |
| Berichte | `data_report`-Erweiterung (Paket B1) | Zählungen je Profil/Tier (Abschnitt 5) |

### 4.3 Sichtbarkeit und Persistenz

- **Pflichtanzeige:** Jede Ansicht, die Inclusion- oder Tier-Werte zeigt, zeigt in der
  Kopfzeile: Profilname, Universum-Typ, Universumsgröße &#124;U&#124;, Snapshot-ID
  (kurz), Parametersatz-Name. Ein Wert ohne diese Angaben wird nicht gerendert.
- **Persistenz der Definitionen:** Profile und Parametersätze liegen im Store
  (`universe_profile`, `tier_parameter_set`) — sie sind damit Teil des Datenordners,
  tauchen in Backups auf und sind in Berichten referenzierbar.
- **Persistenz der Auswahl:** Welches Profil/Parametersatz gerade aktiv ist, ist ein
  UI-Zustand je Ansicht und darf im Browser (localStorage) liegen; er verändert keine
  Definition und keine Berechnung.
- **Reproduzierbarkeit:** Ein Tier-Wert ist vollständig beschrieben durch
  (`snapshot_id`, `parameter_hash`, Code-Stand). Datenstände der Quellen stehen in
  `source.snapshot_date`/`imported_at` bzw. `source_capture_event`; wächst der Korpus,
  ändert sich die Snapshot-ID, und alte Werte bleiben über
  `universe_snapshot`/`universe_snapshot_deck` nachvollziehbar.

---

## 5. Umsetzungsreihenfolge (Arbeitspakete)

Reihenfolge ergibt sich aus den Abhängigkeiten; jedes Paket hat eine messbare Abnahme
(Zählung oder Test). „Tests grün" heißt immer: bestehende Studio-Tests plus die im Paket
genannten neuen Tests.

### Datenhaltung (D)

| Paket | Inhalt | Abhängt von | Messbare Abnahme |
|---|---|---|---|
| D1 | Bracket-Herkunft der Korpus-Decks speichern: Hub-Import schreibt zusätzlich `bracket:<n>`-Zeilen in `corpus_cohort` aus der Katalog-Spalte `bracket_user_set` (Weg 2.2a). Decks ohne Bracket-Angabe erhalten keine Zeile und werden gezählt | — | Zählung je Bracket im Store = Zählung je `bracket_user_set` in der Katalog-CSV (Differenz 0); Anzahl Decks ohne Bracket-Angabe steht im Import-Ergebnis; `role_fingerprint`-Prinzip: Fingerprints anderer Bereiche unverändert |
| D2 | Tabellen `universe_profile`, `universe_snapshot`, optional `universe_snapshot_deck`; Schema-Version 7 → 8 (additiv) | — | Migrationstest auf einer Kopie einer echten DB (Zeilen aller Bestandstabellen unverändert, Zählvergleich vorher/nachher); Store-Tests grün |
| D3 | EDHREC-Aggregat-Universen für Bracket 3 und 4 beschaffen — **erst nach Klärung von U2** (Abschnitt 6). Falls Aggregat-Ansichten existieren: Import als eigene `observation`-Kohorten mit `source_capture_event` | U2 | Je Kohorte: Anzahl Karten mit Zähler **und** Nenner, Anzahl Karten mit Zähler ohne Nenner (werden `UNKNOWN` geführt), beides im Datenbericht; keine Nenner-Ersetzung (Test gegen die A3-Importer-Regel) |
| D4 | Salt-Marker beschaffen, **falls** die abgerufenen EDHREC-Rohdaten das Feld enthalten (Klärung U3): Import als `observation.metric = 'salt'` | U3 | Anzahl Pool-Karten mit Salt-Wert / 801 im Datenbericht; Karten ohne Wert als unbekannt gezählt, nicht als 0 |
| D5 | Preis-Marker | U4 | Kein Bau vor Klärung von U4 (welches Produkt/Feld, welche Druck-Festlegung). Abnahme wird erst nach der Klärung formuliert |

### Rechenkern (R) — reine Funktionen, keine UI

| Paket | Inhalt | Abhängt von | Messbare Abnahme |
|---|---|---|---|
| R1 | Universum-Auflösung: Profil-Definition → (`deck_id`-Menge bzw. Kohorten-Auswahl, Snapshot-ID, &#124;U&#124;) inkl. Snapshot-Persistenz aus D2 | D2 (D1 für Bracket-Filter) | Fixture-Tests: Standard-Profil „alle Decks" liefert exakt die heutige `ALL_DECKS`-Menge; jede Einzeldimension (play_group, Kohorte, Bracket, Zeitraum) an einem Fixture-Korpus mit bekannter Mitgliedschaft; Decks ohne Datum werden im Datums-Filter gezählt ausgeschlossen |
| R2 | Inclusion über Universum (Formel 2.4) für Listen- und Aggregat-Universen | R1 | Nachrechnungs-Test: Für `play_group`-Profile stimmen Zähler/Nenner mit `queries.corpus_inclusion()` überein (alle Pool-Karten, Differenz 0); Aggregat-Fall A3 (fehlender Nenner) ergibt `UNKNOWN`, nicht 0 |
| R3 | Tier-Funktion (Abschnitt 3) inkl. `U`-Grund-Codes, Aufschlüsselungs-Struktur 3.6, optionalem `tier_result`-Cache | R2 | Fixture-Tests mit bekannten Zählern → bekannte Tiers in beiden Grenz-Modi; jeder Grund-Code aus 3.5 durch mindestens einen Testfall ausgelöst; Cache-Test: Löschen + Neuberechnen ergibt identische Zeilen; Determinismus-Test: gleiche Snapshot-ID + gleicher Parameter-Hash ⇒ identisches Ergebnis |

### UI / Einstellungen (U)

| Paket | Inhalt | Abhängt von | Messbare Abnahme |
|---|---|---|---|
| U1 | Profil- und Parametersatz-Verwaltung (API + Editor-Formular), Standard-Profil „alle Decks" nicht löschbar | D2, R1 | API-Tests: Anlegen/Ändern/Löschen; ungültige Definitionen (unbekannte Dimension, leere Grenzen-Liste) werden abgelehnt (HTTP-Fehler statt stiller Übernahme) |
| U2 | Pool-Ansicht: Profil-/Parametersatz-Auswahl in der Kopfzeile, Pflichtanzeige (4.3), Tier-Spalte, Sortierung und Filter nach Tier/`U` | R3, U1 | Manuelle + API-Abnahme: Wechsel des Profils ändert die angezeigten Zähler auf die Werte des neuen Snapshots (Vergleich gegen CLI-Ausgabe desselben Profils, Differenz 0); keine Ansicht zeigt Tier-Werte ohne Snapshot-ID |
| U3 | Karten-Detail: `tier_breakdown`-Anzeige inkl. fehlender Signale und `U`-Grund | R3 | API-Test: Antwort enthält alle Felder aus 3.6; eine Karte ohne Beobachtung zeigt `U` + Grund statt eines Werts |

### Berichte (B)

| Paket | Inhalt | Abhängt von | Messbare Abnahme |
|---|---|---|---|
| B1 | `data_report`-Erweiterung: Universen (Größe je gespeichertem Profil, davon ohne Datum/Duplikate ausgeschlossen), Tier-Verteilung als reine Zählung (je Tier, je `U`-Grund), Salt-/Preis-Abdeckung aus D4/D5 als „vorhanden / von 801" bzw. `NOT_MEASURED` | R3 (D4 für Marker-Zahlen) | Berichts-Test: Summen der Tier-Zählung = Pool-Größe (801) für das Standard-Profil; Bericht bleibt counts-only (keine Kartennamen, keine Deck-Adressen — bestehendes Prinzip von `data_report`) |
| B2 | Export-Kopfzeile: Deck-Export vermerkt Profil, Snapshot-ID und Parameter-Hash der Ansicht, aus der exportiert wurde | U2 | Export-Test: Kopfzeile enthält die drei Angaben; der exportierte Karteninhalt ist unverändert (Diff gegen Export ohne Kopfzeile nur in der Kopfzeile) |

---

## 6. Offene Faktenfragen (UNKNOWN-Liste)

Keine der folgenden Fragen wird in diesem Dokument vermutend beantwortet. Jede ist mit
dem Prüfweg notiert, der sie in einen Fakt überführt; Pakete, die davon abhängen, sind
genannt.

| # | Offene Frage | Warum offen / Prüfweg | Blockiert |
|---|---|---|---|
| U1 | Welche Felder publiziert Playgroup.gg tatsächlich (Commander-Profil Chulane, ID 2143, und Card Atlas) — insbesondere: gibt es Archetyp-/Matchup-Felder in einem öffentlichen JSON? | Im CPL-Store liegt **kein** Playgroup-Wert (`playgroup_observed_games` wird im Code mit „Documented blockade / no public export" auf `None` gesetzt); das Register führt beide Playgroup-Quellen als `REVIEW` mit `has_exact_numerator_denominator = False` und erlaubter Abrufart `MANUAL_INSPECTION_ONLY`. Prüfweg: manuelle Inspektion der öffentlichen JSON-Antwort, Feldliste als Fakt festhalten | jedes Playgroup-Signal; ggf. Themen-Dimension für Playgroup-Daten |
| U2 | Stellt EDHREC bracket-gefilterte Decklisten (v. a. Bracket 3 und 4) in maschinenlesbarer Form bereit — mit welchen Feldern (Deck-Adressen, Datum, Bracket-Zuordnung), in welcher Menge und zu welchen Nutzungsbedingungen? | Lokal belegt sind nur Aggregat-Kohorten: Commander-Seite (alle Brackets gemischt), Theme-Seiten und die historischen Delta-Kohorten `core_b2`/`upgraded_b3` mit teilweise fehlenden Nennern. Eine offizielle Bracket-3/4-Listen- oder Aggregat-Sicht ist im Repo nicht verzeichnet. Prüfweg: EDHREC-Seiten/JSONs für Bracket-Ansichten inspizieren, Felder und Zähler dokumentieren, Lizenz-/Rate-Bedingungen aus der Quelle übernehmen | D3 |
| U3 | Enthalten die lokal abgerufenen EDHREC-Rohantworten (Commander-/Kartenseiten) ein Salt-Feld, und unter welchem Feldnamen? | Die Importer lesen nur `num_decks`, `potential_decks`, `lift`, `synergy`; die Rohantworten sind per `source_capture_event` (SHA-256) referenziert, aber ihr Feldumfang ist nicht inventarisiert. Prüfweg: eine gespeicherte Rohantwort gegen die Feldliste prüfen | D4 |
| U4 | Welches Scryfall-Produkt führt druckbezogene Preise (EUR/USD), und wie ist „der Preis einer Karte" (welcher Druck) für eine Marker-Anzeige festzulegen? | `scryfall_card` (Bulk `oracle_cards`) hat keine Preisfelder; Preise hängen am Druck, nicht an der `oracle_id`. Prüfweg: Scryfall-Bulk-Produkte/Feldlisten prüfen, Druck-Festlegung als Owner-Entscheidung dokumentieren | D5 |
| U5 | Welches Format/Schema hat `corpus_deck.tags` konkret, und lassen sich daraus Themen/Archetypen als Filter ableiten? | Die Spalte ist untypisiertes TEXT; `data_report` zählt nur fehlende Tags (`''`, `'[]'`, `'{}'`, `'null'`). Prüfweg: Tag-Werte des Bestands inventarisieren (Häufigkeiten der vorkommenden Werte, counts-only) | Themen-Dimension für Listen-Universen (2.2) |
| U6 | Sind alle `corpus_deck`-Zeilen Chulane-Decks, oder enthalten andere Importquellen fremde Commander — und woran ist die Commander-Zugehörigkeit eines Decks festzumachen? | `corpus_deck` hat keine Commander-Spalte; für das Hub-Korpus gilt Chulane per Herkunft (Register). Für übrige Quellen (`import_corpus_register`, `import-cohort`) ist das nicht verzeichnet. Prüfweg: Herkunft je `source_id` inventarisieren; ggf. Commander als Kohorten-Konvention festlegen | Commander-Dimension (2.2) bei mehreren Korpus-Quellen |
| U7 | Was genau zählen die EDHREC-`bracket_counts` für Chulane (`{"1": 45, "2": 558, "3": 755, "4": 695, "5": 233}`, Summe 2.286): distinkte Decks, Deck-Bracket-Zuordnungen, welcher Zeitraum? | Die Zahlen sind ein Kontext-Fakt der Quelle; ihre Semantik ist lokal nicht verifiziert und sie weichen vom lokalen Korpus-Nenner (975) ab — die Universen sind also verschiedene Mengen. Prüfweg: EDHREC-Dokumentation/Seitenbeschriftung zur Bracket-Zählung prüfen und als Quellen-Fakt ins Register übernehmen | Interpretation der Verteilung in 1.A; Abgleich mit D3-Kohorten |
| U8 | Wie groß ist die tatsächliche Stichprobe der Playgroup-Chulane-Daten je Karte (Spiele je Karte, nicht nur gesamt)? | Das Register nennt ~2.094 aufgezeichnete Spiele gesamt (manuelle Inspektion) und vermerkt kleine Stichproben (n < 30) für Nicht-Stapel — exakte Zähler/Nenner je Karte existieren nicht (`has_exact_numerator_denominator = False`). Prüfweg: nur über U1 (Feld-/Exportklärung) lösbar, sonst bleibt der Wert `UNKNOWN` | jedes Playgroup-Signal |
| U9 | Dürfen EDHREC-Hauptseite, Theme-Seiten und Budget-Subansichten als getrennte Aggregat-Universen nebeneinander geführt werden, ohne Doppelzählung zu suggerieren? | Das Register vermerkt für `edhrec:chulane` ausdrücklich: Subansichten überlappen mit der Hauptseite und dürfen nie über Kohorten summiert werden. Ob die getrennte Führung als Auswahl (statt Summe) ausreicht, ist eine Darstellungs-/Semantikfrage an den Owner, keine Datenfrage. Prüfweg: Owner-Festlegung, im Profil-Formular als Hinweis zu verankern | Profil-Design für Aggregat-Universen (2.1) |
| U10 | Welche `legality_audit`-Werte kommen in `corpus_deck` tatsächlich vor? | Die Spalte existiert und wird vom Hub-Import gesetzt; eine Werteliste ist nirgends dokumentiert. Prüfweg: `GROUP BY`-Inventar der Spalte (counts-only) | Legalitäts-Dimension (2.2) |

---

## Anhang: Zuordnung zu den Quelldateien

| Design-Teil | Bestehende Struktur |
|---|---|
| Signal-Ablage A2–A5 | `observation` + Importer in `importers.py` (`import_edhrec_table`, `import_edhrec_cardrecs_csv`, Delta-Importe, `import_edhrec_manifest`) |
| Zählung A1/A6/A9 | `builder.cohort_sizes`, `builder._corpus_hits`, `builder.card_cooccurrence`, `builder.cohort_shapes`, `queries.corpus_inclusion` |
| Rollen A8 | `card_role_claim` / `card_role` / `corpus_deck_role`, `roles.py` (Claims, Origins, Scopes) |
| Fakten B1–B3, Flags E1/E2 | `scryfall_card`, View `card_fact`, `builder.sim_readiness_status` |
| Simulation C | `simulation_run` / `simulation_card`, `builder.card_simulations` |
| Marker D3 | `card_mark`, `builder.set_mark` |
| Quellen-Status (3.5, `SOURCE_STATUS_REVIEW`) | `sources.QUALIFIED_SOURCES` (`status`, `status_rationale`, `has_exact_numerator_denominator`) |
| Berichte | `data_report.data_report` (counts-only, `NOT_MEASURED`-Liste, `SMALL_DENOMINATOR`) |
| Neue Tabellen (2.3, 3.4, 3.6) | `universe_profile`, `universe_snapshot`, optional `universe_snapshot_deck`, `tier_parameter_set`, optional `tier_result` — additiv zu Schema-Version 7 |

# Studio Playgroup.gg Card Atlas Schema (Version 1.0.0)

**Gegenstand**: Maschinenlesbares Datenschema und Qualitätsregeln für die Erfassung, Normalisierung und Integration von Playgroup.gg Card-Atlas-Telemetriedaten in das Commander Studio (Issue #1192).

> [!IMPORTANT]
> **Pflicht-Hinweis zur Kausalität:**
> Alle Playgroup.gg-Statistiken sind **`OBSERVED_GAME`**-Evidenz (reale beobachtete Live-Partien auf Playgroup Live). Sie spiegeln Korrelationen wider und sind **kein kausaler Kartenstärke-Score**. Teure Finisher werden typischerweise erst in Partien gewirkt, die der Pilot ohnehin lange überlebt hat (Survivorship-Bias). 

---

## 1. Lizenz, Attribution und Zugriffsbedingungen

- **Lizenz:** Creative Commons Attribution 4.0 International ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)).
- **Urheber:** Arcane Digital B.V. / Playgroup.gg.
- **Attribution:** „Playgroup.gg, CC BY 4.0, URL: `https://playgroup.gg/cards/<slug>`“.
- **Zugriffsbedingungen (Stand 2026-11-11):**
  - Identifizierender User-Agent erforderlich (z. B. `CommanderLabResearch/1.0 (+https://github.com/moeendres-png/commander-playtest-lab)`).
  - Offiziell dokumentierte Rate-Limits: 400 Anfragen / Minute mit User-Agent, 10 ohne.
  - Im Commander Lab gilt ein konservatives Drosselungslimit von maximal ca. **1 Anfrage / Sekunde** mit lokalem Caching, Retry-After-Beachtung und Wiederaufnahme.
  - Kein Auth-Bypass, keine bezahlten Zugänge, kein aggressives Crawling.

---

## 2. Tabellen- und Datensatzstruktur

### Tabelle 1: `playgroup_card_atlas` (Haupttabelle, 1 Zeile je Karte und Modus)

| Spalte | Datentyp | Einheit / Format | Nullable | Beschreibung |
|---|---|---|---|---|
| `card_id` | TEXT | `card:project:<UUID>` | Nein | Eindeutige interne Studio-Karten-ID |
| `oracle_id` | TEXT | UUID (Scryfall) | Nein | Scryfall Oracle-ID |
| `format_mode` | TEXT | `'multiplayer'` / `'1v1'` | Nein | Spielmodus (Standard: `'multiplayer'`) |
| `slug` | TEXT | Slug (`koma-cosmos-serpent`) | Nein | Playgroup.gg URL-Slug |
| `card_name` | TEXT | Text | Nein | Offizieller Oracle-Kartenname |
| `card_type` | TEXT | Text | Ja | Typenzeile aus der Quelle |
| `set_name` | TEXT | Text | Ja | Set-Name der dargestellten Druckversion |
| `live_inclusion_pct` | REAL | Prozent (0–100) | Ja | Live Inclusion Rate im gewählten Modus |
| `deck_inclusion_pct` | REAL | Prozent (0–100) | Ja | Deck Inclusion Rate (sofern getrennt angegeben) |
| `times_brought` | INTEGER | Anzahl | Ja | Anzahl Male, die die Karte mitgebracht wurde |
| `decks_running` | INTEGER | Anzahl | Ja | Anzahl Decks, die die Karte führen |
| `unique_players` | INTEGER | Anzahl | Ja | Einzigartige Spieler im Funnel |
| `median_cast_turn` | REAL | Runde (z. B. `6.0`) | Ja | Medianer Cast-Turn aus der Kopfzeile |
| `drawn_to_played_pct`| REAL | Prozent (0–100) | Ja | Konvertierungsrate: Gezogen $\rightarrow$ Gewirkt |
| `first_cast_n` | INTEGER | Anzahl | Ja | Stichprobengröße der Erst-Wirkungen ($n$) |
| `turn_1_pct` | REAL | Prozent (0–100) | Ja | Anteil Erst-Wirkung in Runde 1 |
| `turn_2_pct` | REAL | Prozent (0–100) | Ja | Anteil Erst-Wirkung in Runde 2 |
| `turn_3_pct` | REAL | Prozent (0–100) | Ja | Anteil Erst-Wirkung in Runde 3 |
| `turn_4_pct` | REAL | Prozent (0–100) | Ja | Anteil Erst-Wirkung in Runde 4 |
| `turn_5_pct` | REAL | Prozent (0–100) | Ja | Anteil Erst-Wirkung in Runde 5 |
| `turn_6_to_9_pct` | REAL | Prozent (0–100) | Ja | Anteil Erst-Wirkung in Runden 6–9 |
| `turn_10_plus_pct` | REAL | Prozent (0–100) | Ja | Anteil Erst-Wirkung in Runde 10+ |
| `p25_cast_turn` | REAL | Runde | Ja | 25. Perzentil des Cast-Turns |
| `p75_cast_turn` | REAL | Runde | Ja | 75. Perzentil des Cast-Turns |
| `max_cast_turn` | REAL | Runde | Ja | Maximal beobachteter Cast-Turn |
| `on_curve_pct` | REAL | Prozent (0–100) | Ja | Veröffentlichter On-Curve-Prozentsatz |
| `on_curve_count` | INTEGER | Anzahl | Ja | Zähler der On-Curve-Wirkungen |
| `on_curve_denominator` | INTEGER | Anzahl | Ja | Nenner der On-Curve-Wirkungen |
| `on_curve_turn` | TEXT | z. B. `'T7'` | Ja | Definierte Kurven-Runde der Karte |
| `cast_same_turn_as_drawn_pct` | REAL | Prozent (0–100) | Ja | Am Zieh-Zug direkt gewirkt |
| `turns_in_hand` | REAL | Runden | Ja | Durchschnittliche Verweildauer auf der Hand |
| `funnel_brought_n` | INTEGER | Anzahl | Ja | Funnel: Brought to game |
| `funnel_players_n` | INTEGER | Anzahl | Ja | Funnel: Beteiligte Spieler |
| `ever_drawn_n` | INTEGER | Anzahl | Ja | Funnel: Mindestens einmal gezogen |
| `reached_battlefield_n`| INTEGER | Anzahl | Ja | Funnel: Aufs Schlachtfeld gelangt |
| `still_on_board_at_end_n` | INTEGER | Anzahl | Ja | Funnel: Bei Spielende noch im Spiel |
| `battlefield_survival_pct` | REAL | Prozent (0–100) | Ja | Verbleib-Quote bei Spielende |
| `winrate_when_cast_pct` | REAL | Prozent (0–100) | Ja | Siegrate, wenn gewirkt |
| `winrate_when_cast_n` | INTEGER | Anzahl | Ja | Stichprobe für Winrate when cast |
| `winrate_when_in_library_pct` | REAL | Prozent (0–100) | Ja | Siegrate, wenn in Bibliothek verblieben |
| `winrate_when_in_library_n` | INTEGER | Anzahl | Ja | Stichprobe für Library-Verbleib |
| `winrate_when_in_hand_pct` | REAL | Prozent (0–100) | Ja | Siegrate, wenn gezogen aber auf Hand |
| `winrate_when_in_hand_n` | INTEGER | Anzahl | Ja | Stichprobe für Hand-Verbleib |
| `observed_winrate_gap_pp` | REAL | Prozentpunkte (pp) | Ja | Beobachteter Abstand (Cast vs Library) |
| `ci_95_lower_pp` | REAL | Prozentpunkte (pp) | Ja | Untere 95-%-Konfidenzintervallgrenze |
| `ci_95_upper_pp` | REAL | Prozentpunkte (pp) | Ja | Obere 95-%-Konfidenzintervallgrenze |
| `conservative_ranking_indicator` | TEXT | Text (z. B. `'≥ +7.6pp'`) | Ja | Konservativer Schätzer (CI-Untergrenze) |
| `final_zones_instances_n` | INTEGER | Anzahl | Ja | Instanzen der Endzonen-Erhebung |
| `fetch_status` | TEXT | Status | Nein | `'OK'`, `'PARTIAL'`, `'NO_DATA'`, `'NOT_FOUND'`, `'FETCH_ERROR'`, `'PARSE_ERROR'`, `'RATE_LIMITED'` |
| `quality_warnings` | TEXT | JSON Array | Nein | Liste erkannter Quell- und Rechenanomalien |
| `insufficient_sample`| INTEGER | 0 oder 1 | Nein | 1 wenn $n < 30$ |
| `retrieved_at_utc` | TEXT | ISO-8601 UTC | Ja | Abrufzeitstempel |
| `source_id` | TEXT | Ref `source.source_id` | Ja | Zugeordnete Quellen-ID |

---

### Tabelle 2: `playgroup_top_commander` (1:N Relation)

| Spalte | Datentyp | Beschreibung |
|---|---|---|
| `oracle_id` | TEXT | Scryfall Oracle-ID der Karte |
| `format_mode` | TEXT | `'multiplayer'` / `'1v1'` |
| `rank` | INTEGER | Rang 1..10 |
| `commander_name` | TEXT | Name des gespielten Commanders |
| `commander_slug` | TEXT | Playgroup-Slug des Commanders |
| `color_identity` | TEXT | Farbidentität (z. B. `'GU'`, `'WUBRG'`) |
| `decks_count` | INTEGER | Anzahl getrackter Decks mit diesem Commander |

---

### Tabelle 3: `playgroup_final_zone` (1:N Relation)

| Spalte | Datentyp | Beschreibung |
|---|---|---|
| `oracle_id` | TEXT | Scryfall Oracle-ID der Karte |
| `format_mode` | TEXT | `'multiplayer'` / `'1v1'` |
| `zone_name` | TEXT | Name der Zone (`'Library'`, `'Battlefield'`, `'Graveyard'`, `'Exile'`) |
| `pct` | REAL | Prozentualer Anteil (0–100) |
| `instances_n` | INTEGER | Gesamtzahl der Instanzen |

---

## 3. Qualitätsregeln & Fehlerbehandlung

1. **Keine erfundenen Zahlen:** Fehlende Felder bleiben `NULL` (None), niemals `0` oder `0.0`.
2. **Klassifikation des Fetch-Status:**
   - `OK`: Erfolgreich abgerufen mit $n \ge 30$ Erst-Wirkungen (`first_cast_n >= 30`).
   - `PARTIAL`: Karte auf Playgroup gelistet, aber unzureichende Daten ($n < 30$ oder $< 100$ Spiele, z. B. Esperzoa). Gilt als `UNRATED`, nicht als D-Tier.
   - `NO_DATA`: Karte gelistet, jedoch keine Spieltelemetrie vorhanden.
   - `NOT_FOUND`: HTTP 404 (Karte nicht in der Playgroup-Datenbank).
   - `FETCH_ERROR`: Netzwerk- oder Serverfehler (HTTP 5xx, Timeout).
   - `RATE_LIMITED`: HTTP 429 erhalten.
   - `PARSE_ERROR`: HTML-Format wich unerwartet ab.
3. **Dokumentierte Quell-Anomalien (QA-Warnungen):**
   - **Brought-Mismatch**: Wenn `times_brought != funnel_brought_n` (z. B. Koma, World-Eater: 817 vs. 821; Sol Ring: 131.091 vs. 131.212). Beide Rohwerte werden unverändert gespeichert und im `quality_warnings`-Feld protokolliert.
   - **On-Curve-Rechenfehler**: Wenn der verlinkte Text `(count / denominator)` rechnerisch um $> 2.0$ Prozentpunkte vom angezeigten `on_curve_pct` abweicht (z. B. Koma, World-Eater: Anzeige 53 %, real $25 / 157 = 15.9 \%$; Koma, Cosmos Serpent: Anzeige 68 %, real $51 / 320 = 15.9 \%$). Der angezeigte Originalwert bleibt erhalten, die Abweichung wird protokolliert.
   - **Endzonen-Summe**: Die Zonenwerte müssen sich nicht auf 100 % summieren (Karten können unaufgelöst bleiben oder sich in Sonderzonen wie Hand/Kommandozone befinden). Keine künstliche Normalisierung auf 100 %.

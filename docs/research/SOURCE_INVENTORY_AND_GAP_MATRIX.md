# Commander Studio BUILD: Quelleninventar, Datenlückenmatrix & Beispielreport (P0 Deliverables 1, 2 & 3)

**Datum:** 2026-11-11  
**Autorität & Bindung:** Issue [#1185](https://github.com/moeendres-png/commander-playtest-lab/issues/1185), [`docs/PROJECT_MISSION.md`](../PROJECT_MISSION.md), [`docs/OWNER_DECISION_STUDIO_BUILD_PLAY_SIMULATE_20261110.md`](../OWNER_DECISION_STUDIO_BUILD_PLAY_SIMULATE_20261110.md), `AGENTS.md` §2 (Rules Authority), §3 (Source Truth), §12 (Privacy).  
**Status:** `P0_DELIVERABLES_COMPLETED` (Maschinenlesbares Quellenregister, 801-Karten-Lückenmatrix, Beispielreport & CLI-Integration).  
**Maschinenlesbare Artefakte:**
- Quellenregister (9 Quellen): [`data/provenance/source_inventory.json`](../../data/provenance/source_inventory.json)
- Lückenmatrix (801 Chulane-Poolkarten): [`data/research/chulane_legal_pool_gap_matrix.json`](../../data/research/chulane_legal_pool_gap_matrix.json)

---

## 1. Auftrag und Methodik

Die Bewertung von Karten im Commander Studio BUILD erfordert eine **evidenzbasierte, reproduzierbare Datengrundlage**. Das Ziel ist die Vermeidung zirkulärer Popularitäts-Heuristiken (wo eine Karte nur deshalb als stark eingestuft wird, weil viele Spieler sie ins Deck kopieren) und die Aufdeckung von Synergien im **Long Tail** (Karten mit 0–4 Decktreffern, die aufgrund spezifischer Mechaniken wie Bounce, ETB, Landfall oder Mana-Dork-Eigenschaften hervorragend mit Chulane harmonieren).

### Grundsätze der Quellenqualifizierung
1. **Keine erfundene Spielstärke / Keine Schein-Scores:**  
   Fehlende Daten bleiben explizit `UNKNOWN` oder `NULL`. Ein Zähler von 0 Treffern in einem Korpus bedeutet ausschließlich **„im Korpus nicht beobachtet“**, niemals $0\,\%$ Spielstärke oder automatisches D-Tier.
2. **Strikte Trennung von Evidenzschichten:**
   - `FACT` / `DERIVED_MECHANICAL`: Objektive Eigenschaften (Oracle-Text, CMC, Typ, Farbidentität, XMage-Regeln).
   - `OBSERVED_DECK`: Deckbau-Popularität und relatives Vorkommen (z. B. EDHREC Lift, Korpuspräsenz). **Kein Winrate-Beweis!**
   - `OBSERVED_GAME`: Echte Partien (Siege, Cast-Turn, Hand-Age, Pilotenanzahl). Beobachtete Zusammenhänge sind **nicht kausal**.
   - `COMBO_VERIFIED`: Nachprüfbare Regelfolgen und Komboschritte (Commander Spellbook).
   - `SIMULATED_RESULT`: Deterministische XMage-4P-Simulationen (eigene Messung mit Pin, Seed, Policy).
   - `MODELED` / `EXTERNAL_OPINION`: Heuristiken oder Meinungs-Tierlisten (stets separat ausgewiesen).
3. **Datenschutz & Kostenfreiheit ($0\text{ €}$):**  
   Keine kostenpflichtigen APIs. Keine Weitergabe von privaten Sammlungs- oder Deckbeständen nach außen (`AGENTS.md` §12). Lokale Berechnungen und Scryfall/Spellbook-Abfragen erfolgen höflich gedrosselt und ToS-konform.

---

## 2. Qualifizierung der 7 priorisierten Quellen

Die Qualifizierung erfolgt in der vom Owner verbindlich festgelegten Reihenfolge (Priorität 1 bis 7):

### Priorität 1: Scryfall Bulk-Manifest & API-Abrufregeln
- **Quellen-ID:** `scryfall:bulk-oracle`
- **Direkte URL:** [`https://api.scryfall.com/bulk-data`](https://api.scryfall.com/bulk-data)
- **Referenz-Dokumentation:** [`https://scryfall.com/docs/api`](https://scryfall.com/docs/api), [`https://scryfall.com/docs/faqs/i-m-having-trouble-accessing-the-scryfall-api-or-i-m-blocked-17`](https://scryfall.com/docs/faqs/i-m-having-trouble-accessing-the-scryfall-api-or-i-m-blocked-17)
- **Herausgeber:** Scryfall, LLC
- **Datenstand / Snapshot:** `scryfall-oracle-cards-20261110`, Abruf: `2026-11-10T00:00:00Z`
- **Schema & Identifikator:** JSON Bulk (`oracle_cards`); Primärschlüssel: kanonische `oracle_id`.
- **Abdeckung:** $100\,\%$ aller Magic-Karten. Exakt **801 von 801** Chulane-Poolkarten im Studio-Store verifiziert.
- **Evidenzschicht:** `FACT` und `DERIVED_MECHANICAL`.
- **Zähler / Nenner:** Exakte Zahlenwerte für Manawert (CMC), Farben, Stärke/Widerstand, Loyalität.
- **Doppelzählungs-Risiko:** Ausgeschlossen; alle Drucke/Reprints werden deterministisch auf die eine `oracle_id` normalisiert.
- **Lizenz & Abrufmethode:** Freie Nutzung für persönliche/unkommerzielle Projekte unter der *Wizards Fan Content Policy*. Abruf via Bulk-Manifest mit bedingtem GET (ETag), **keine** Einzelabfragen-Schleifen; API-Aufrufe mit 50–100 ms Drosselung.
- **Reproduzierbarkeit:** `DETERMINISTIC_OFFLINE_SNAPSHOT` (gespeichert in `studio.sqlite3`, Tabelle `scryfall_card`).
- **Bias & Grenzen:** Fakten und Regeln, **keinerlei Spielstärke-Aussage**. Community-Rollen (Tagger) sind subjektiv und müssen als solche gekennzeichnet bleiben.
- **Status:** **`VERIFIED`**

---

### Priorität 2: Playgroup.gg Card Atlas & Methodik
- **Quellen-ID:** `playgroup:card-atlas`
- **Direkte URL:** [`https://playgroup.gg/cards`](https://playgroup.gg/cards)
- **Referenz-Dokumentation:** [`https://playgroup.gg/about`](https://playgroup.gg/about), [`https://playgroup.gg/research`](https://playgroup.gg/research), [`https://playgroup.gg/api-docs/index.html`](https://playgroup.gg/api-docs/index.html)
- **Herausgeber:** Playgroup.gg
- **Datenstand:** Laufender Aggregationsbestand aus Playgroup-Live-Sitzungen (2024–2026).
- **Schema & Identifikator:** HTML / Web-Applikation; Identifikation via Kartennamen / Slug.
- **Abdeckung:** Nur Karten, die in digital protokollierten Playgroup-Live-Partien tatsächlich gewirkt wurden. Der Long-Tail selten gespielter Karten fehlt vollständig.
- **Evidenzschicht:** `OBSERVED_GAME`.
- **Zähler / Nenner:** Teils unvollständig oder gerundet; Web-Ansichten zeigen oft aggregierte Prozentwerte ohne getrennte Subkohorten-Nenner.
- **Doppelzählungs-Risiko:** Hoch; lokale Spielrunden spielen wiederholt gegeneinander, was zu starker Häufung bestimmter Karten und Decktypen führt.
- **Lizenz & Abrufmethode:** Aggregierte Statistiken stehen unter CC BY 4.0; Roh-Events und Code sind proprietär. **Keine unauthentifizierte Bulk-Download-API vorhanden.** Automatisiertes Scraping hinter Auth ist laut ToS untersagt.
- **Reproduzierbarkeit:** `DYNAMIC_EPHEMERAL_WEB`.
- **Bias & Grenzen:** 
  - Beobachtete Korrelation ist **kein kausaler Wirksamkeitsbeweis**.
  - **Survivorship-Bias:** Metriken wie `Drawn -> Played` erfassen nur Karten, die der Spieler in einem noch handlungsfähigen Spielzustand gezogen hat.
  - Pilot- und Spielgruppen-Konzentration.
- **Status:** **`REVIEW`** (Dokumentierte Blockade für automatischen Bulk-Abzug; Methodik dient als Konzeptreferenz).

---

### Priorität 3: Playgroup.gg Chulane-spezifische Auswertung
- **Quellen-ID:** `playgroup:chulane`
- **Direkte URL:** [`https://playgroup.gg/commanders/2143-chulane-teller-of-tales`](https://playgroup.gg/commanders/2143-chulane-teller-of-tales)
- **Referenz-Dokumentation:** [`https://playgroup.gg/about`](https://playgroup.gg/about)
- **Herausgeber:** Playgroup.gg
- **Datenstand:** 2.094 dokumentierte Chulane-Spiele (Audit-Stand: November 2026).
- **Schema & Identifikator:** HTML / Web-Ansicht; Identifikation via Slug `2143-chulane-teller-of-tales`.
- **Abdeckung:** Auf Chulane fokussierte Teilmenge der beobachteten Partien; Long-Tail unvollständig.
- **Evidenzschicht:** `OBSERVED_GAME`.
- **Zähler / Nenner:** Veröffentlichte Top-Line-Werte: 36 % Winrate (770 Siege, 1.304 Niederlagen; Nenner unvollständig ausgewiesen).
- **Doppelzählungs-Risiko:** Wiederholte Partien desselben Decks in einer festen Runde.
- **Lizenz & Abrufmethode:** CC BY 4.0 für aggregierte Werte; kein programmatischer Bulk-Export. Nur manuelle Kontrollstichproben.
- **Reproduzierbarkeit:** `DYNAMIC_EPHEMERAL_WEB`.
- **Bias & Grenzen:**
  - **Extremer Sitzpositions-Bias:** Sitz 1 zeigt $45{,}33\,\%$ Winrate ($n = 674$), Sitz 5 nur $16{,}28\,\%$ ($n = 43$).
  - **Archetyp-Verzerrung:** Das Playgroup-Chulane-Sample ist extrem Landfall-lastig; creature-bounce/Kombi-Strategien sind unterrepräsentiert.
  - Kleine Fallzahlen bei Nischenkarten ($n < 30$).
- **Status:** **`REVIEW`** (Gaps transparent offenlegen; Kennzahlen nur manuell als Kontext einordnen).

---

### Priorität 4: EDHREC Chulane, Lift-Definition & Anleitung
- **Quellen-ID:** `edhrec:chulane`
- **Direkte URL:** [`https://edhrec.com/commanders/chulane-teller-of-tales`](https://edhrec.com/commanders/chulane-teller-of-tales)
- **Referenz-Dokumentation:** [`https://edhrec.com/articles/changelog-replacing-synergy-with-lift-on-edhrecs-card-pages`](https://edhrec.com/articles/changelog-replacing-synergy-with-lift-on-edhrecs-card-pages), [`https://edhrec.com/guides/how-to-use-edhrec`](https://edhrec.com/guides/how-to-use-edhrec)
- **Herausgeber:** EDHREC (Space Cow Media / MTGGoldfish)
- **Datenstand / Snapshots:** 
  - 20 frische HTTP200-Snapshots vom **2026-11-11T12:54–12:55 UTC** (Run #43024442970, Refs #1186, PR #1184).
  - 1.304 historische Zeilen verbleiben mit `retrieved_at_utc = NULL` (keine unbewiesene Rückdatierung!).
- **Schema & Identifikator:** JSON (EDHREC Web-API); `sanitized` Name $\rightarrow$ erfordert Abgleich mit `oracle_id`.
- **Abdeckung:** Beliebteste ~1.300 Karten für Chulane; Karten mit $< 1\,\%$ Inclusion fehlen komplett.
- **Evidenzschicht:** `OBSERVED_DECK`.
- **Zähler / Nenner:** Exakte Zähler `num_decks` und `potential_decks` (wo in API vorhanden; sonst `NULL`).
- **Doppelzählungs-Risiko:** Hoch bei Aggregation über Themen (z. B. *Landfall*, *Blink*, *Budget* überschneiden sich mit der Hauptseite).
- **Lizenz & Abrufmethode:** Freie Webreferenzierung; Drosselung und Einhaltung von `robots.txt` zwingend; Caching mit Zeitstempel.
- **Reproduzierbarkeit:** `REPRODUCIBLE_API` für versionierte HTTP-Snapshots.
- **Bias & Grenzen:**
  - **Deckbau-Popularität $\neq$ Spielstärke oder Gewinnrate!**
  - **Lift ist relatives Deckvorkommen**, absolut **KEIN** Winrate-Lift!
  - Precon- und Content-Creator-Echo-Chamber (weit verbreitete Listen verzerren die Zähler).
- **Status:** **`VERIFIED`** (für die 20 versionierten Snapshots) / **`REVIEW`** (für historische Altdaten ohne Zeitstempel).

---

### Priorität 5: Commander Spellbook Combo-Suche & Backend-API
- **Quellen-ID:** `spellbook:variants-api`
- **Direkte URL:** [`https://backend.commanderspellbook.com/variants/`](https://backend.commanderspellbook.com/variants/)
- **Referenz-Dokumentation:** [`https://commanderspellbook.com/`](https://commanderspellbook.com/), [`https://spacecowmedia.github.io/commander-spellbook-backend/index.html`](https://spacecowmedia.github.io/commander-spellbook-backend/index.html)
- **Herausgeber:** Commander Spellbook (Space Cow Media / Community)
- **Datenstand:** Kontinuierlich gepflegter, auditierter Kombo-Datenbestand.
- **Schema & Identifikator:** JSON REST API; Identifikation via `oracle_name` und `variant_id`.
- **Abdeckung:** Alle regelkonformen Kombos innerhalb der WUG-Farbidentität.
- **Evidenzschicht:** `COMBO_VERIFIED`.
- **Zähler / Nenner:** Diskrete Varianten-ID, genaue Anzahl beteiligter Teile und Schritte.
- **Doppelzählungs-Risiko:** Gering auf Kombo-Ebene; funktionale Klone (z. B. Shrieking Drake vs. Man-o'-War) bilden separate Varianten.
- **Lizenz & Abrufmethode:** **Open Source (MIT License & CC BY 4.0)**; uneingeschränkt frei nutzbar via REST-API. Adapter in [`src/commander_lab/commander_spellbook.py`](../../src/commander_lab/commander_spellbook.py) bereits implementiert.
- **Reproduzierbarkeit:** `REPRODUCIBLE_API`.
- **Bias & Grenzen:**
  - Die bloße Existenz einer Kombo ist **kein Beleg für Konsistenz, Spielstärke oder Siegquote**.
  - 4+-Karten-Kombos ohne Tutoren sind in der Praxis oft inert.
- **Status:** **`VERIFIED`**

---

### Priorität 6: ACTIVE-Drive Curated Chulane 99-Card Deck-Korpus
- **Quellen-ID:** `active_drive:chulane-corpus-975`
- **Direkte URL:** `local:data/hub/03_MAINBOARD_99_COMPACT_*.jsonl`
- **Referenz-Dokumentation:** [`docs/STUDIO_DECKBUILDER.md`](../STUDIO_DECKBUILDER.md)
- **Herausgeber:** Commander Studio ACTIVE Archive / Owner
- **Datenstand:** Stand 2026-11-10; 994 registrierte Quellen, **975 einzigartige Deckkompositionen**.
- **Schema & Identifikator:** JSONL / CSV; Primärschlüssel `deck_id`, referenziert über `oracle_id`.
- **Abdeckung:** 975 vollständige 99-Karten-Chulane-Decks. **429** der 801 Poolkarten sind beobachtet, **372** haben 0 Treffer.
- **Evidenzschicht:** `OBSERVED_DECK`.
- **Zähler / Nenner:** Exakt $x$ Treffer von $N = 975$ deduplizierten Decks.
- **Doppelzählungs-Risiko:** Vollständig gelöst; die 19 Dubletten sind im 975er-Nenner bereinigt.
- **Lizenz & Abrufmethode:** Lokale Projektdaten; verbleiben lokal auf dem Rechner (`AGENTS.md` §12).
- **Reproduzierbarkeit:** `DETERMINISTIC_OFFLINE_SNAPSHOT` (in `studio.sqlite3`).
- **Bias & Grenzen:**
  - Spiegelt historische Vorlieben und gesammelte Webquellen wider.
  - **Nullfall-Vorsicht:** 372 unbeobachtete Karten dürfen niemals automatisch als ungeeignet abgewertet werden.
- **Status:** **`VERIFIED`**

---

### Priorität 7: Öffentliche cEDH- / Turnier-Decklisten
- **Quellen-ID:** `tournament:cedh-meta`
- **Direkte URL:** [`https://edhtop16.com/commander/Chulane,%20Teller%20of%20Tales`](https://edhtop16.com/commander/Chulane,%20Teller%20of%20Tales)
- **Referenz-Dokumentation:** [`https://mtgtop8.com/`](https://mtgtop8.com/), [`https://topdeck.gg/`](https://topdeck.gg/)
- **Herausgeber:** EDHTop16 / TopDeck.gg
- **Datenstand:** Turnier-Meta 2023–2026.
- **Schema & Identifikator:** JSON API / Web; Card Name.
- **Abdeckung:** Stark selektiv; nur Top-16-Turnier-Decks.
- **Evidenzschicht:** `OBSERVED_TOURNAMENT` / `EXTERNAL_OPINION`.
- **Zähler / Nenner:** Turnierplatzierungen, oft ohne exakten Pool-Nenner.
- **Doppelzählungs-Risiko:** Wiederholte Starts desselben Piloten mit identischer Liste bei mehreren Turnieren.
- **Lizenz & Abrufmethode:** ToS-Prüfung erforderlich; keine automatisierte Massenausleitung ohne API-Vereinbarung.
- **Reproduzierbarkeit:** `DYNAMIC_EPHEMERAL_WEB`.
- **Bias & Grenzen:**
  - **Extremer Selektions-Bias:** cEDH optimiert auf Turn-2/3-Siege, Fast-Mana (Mana Crypt, Mox Diamond, Lotus Petal) und Free-Counterspells. Dies ist für Casual- oder Focused-Commander ungeeignet.
  - Sehr kleine Fallzahl für Chulane im aktuellen cEDH-Meta.
- **Status:** **`REVIEW`**

---

### Priorität 8: XMage Engine Card Facts & Rules Readiness
- **Quellen-ID:** `xmage:card-facts`
- **Direkte URL:** `local:data/cards/xmage_card_facts.json`
- **Referenz-Dokumentation:** [`https://github.com/magefree/mage`](https://github.com/magefree/mage), [`src/commander_lab/deck_readiness.py`](../../src/commander_lab/deck_readiness.py)
- **Herausgeber:** XMage Project / Commander Lab
- **Datenstand / Snapshot:** `xmage-card-facts-v1`, Stand: `2026-11-10T00:00:00Z`
- **Schema & Identifikator:** JSON (`xmage_card_facts.json`); Primärschlüssel: normalisierter `engine_name` / `oracle_name`.
- **Abdeckung:** 7.231 im gepinnten Rules Core implementierte Karten. Exakt **801 von 801** Chulane-Poolkarten sind verifiziert und regeltechnisch lauffähig (`sim_status: OK`).
- **Evidenzschicht:** `DERIVED_MECHANICAL`.
- **Zähler / Nenner:** Deterministische Indikatoren (`implemented`, `playable`, `sim_status`).
- **Doppelzählungs-Risiko:** Ausgeschlossen; deterministische Namensabbildung.
- **Lizenz & Abrufmethode:** Open Source (GPLv3); lokales Repository-Asset.
- **Reproduzierbarkeit:** `DETERMINISTIC_OFFLINE_SNAPSHOT`.
- **Bias & Grenzen:**
  - Regeln-Verfügbarkeit $\neq$ Spielstärke: Eine lauffähige Karte ist nicht automatisch gut.
  - Karten ohne externe Entscheidungsunterstützung scheitern fail-closed.
- **Status:** **`VERIFIED`**

---

### Priorität 9: Scryfall Tagger Community-Rollen
- **Quellen-ID:** `scryfall:tagger`
- **Direkte URL:** [`https://tagger.scryfall.com/`](https://tagger.scryfall.com/)
- **Referenz-Dokumentation:** [`https://scryfall.com/docs/tagger-tags`](https://scryfall.com/docs/tagger-tags), [`src/commander_lab/studio/roles.py`](../../src/commander_lab/studio/roles.py)
- **Herausgeber:** Scryfall Community / Tagger Project
- **Datenstand:** Kontinuierlich gepflegter Community-Tag-Katalog (2024–2026).
- **Schema & Identifikator:** Web / CSV / Tag-Taxonomie; Identifikation via `oracle_id` und Kartennamen.
- **Abdeckung:** Funktionale Rollen (Ramp, Draw, Removal, Bounce, Tutor, Combo-Piece).
- **Evidenzschicht:** `EXTERNAL_OPINION`.
- **Zähler / Nenner:** Qualitative Tags ohne standardisierten Nenner.
- **Doppelzählungs-Risiko:** Mehrfache überlappende Tags für dieselbe Funktion (z. B. `bounce-creature` und `bounce-permanent`).
- **Lizenz & Abrufmethode:** Wizards Fan Content Policy; unkommerzielle Zitation, manuelle Prüfung oder Scryfall-Bulk-Export.
- **Reproduzierbarkeit:** `DYNAMIC_EPHEMERAL_WEB`.
- **Bias & Grenzen:** Subjektive Zuordnung durch Community-Nutzer; Vollständigkeit bei neuen Sets verzögert.
- **Status:** **`REVIEW`**

---

## 3. Deliverable 2: 801-Karten-Lückenmatrix & Long-Tail-Analyse

Die vollständige Lückenmatrix für den gesamten legalen Chulane-Pool ($N = 801$ Karten) wurde berechnet und in [`data/research/chulane_legal_pool_gap_matrix.json`](../../data/research/chulane_legal_pool_gap_matrix.json) hinterlegt.

### Methodik der Lückenberechnung

Für jede der 801 Poolkarten wird die Evidenzabdeckung und das Research-Potential objektiv bewertet:

1. **Evidenzabdeckung ($\text{Coverage} \in [0.0, 1.0]$):**
   - Scryfall-Fakten (`oracle_id`, Typ, CMC, Farben): $+0{,}20$
   - XMage-Regeln verifiziert (`sim_status: OK`): $+0{,}20$
   - Korpus-Beobachtung:
     - $\ge 5$ Treffer: $+0{,}30$
     - $1\text{--}4$ Treffer: $(\text{hits} / 5) \times 0{,}30$
     - $0$ Treffer: $+0{,}00$
   - EDHREC-Verankerung (Inclusion-Beobachtung vorhanden): $+0{,}20$
   - Spellbook-Kombobeteiligung: $+0{,}10$
2. **Deck-Relevanz ($\text{Relevance} \in [0.0, 1.0]$):**
   - Basisrelevanz (format-legale Karte im Studio-Store): $+0{,}15$
   - Kreaturen:
     - Manawert $\le 3$ (optimaler Chulane-Cast-Trigger): $+0{,}35$
     - Manawert $> 3$: $+0{,}15$
   - Funktionale Synergien (Bounce, Recast, Ramp, Draw, Mana-Dork, Landfall): $+0{,}30$
   - Sonstige funktionale Rollen: $+0{,}15$
   - Spellbook-Kombostück: $+0{,}20$
3. **Research-Prioritäts-Score:**
   $$\text{Research-Priorität} = (1 - \text{Coverage}) \times \text{Relevance}$$
   Karten mit hoher mechanischer Relevanz, aber bisher fehlender Korpus-Evidenz, erhalten den höchsten Score und stehen an erster Stelle für gezielte Simulationen oder vertiefte Recherchen.

### Klassifikation der Evidenzabdeckung (Coverage Grades)

| Evidenzgrad | Kriterien | Anzahl Karten | Anteil |
| :--- | :--- | :---: | :---: |
| **`COMPLETE`** | Scryfall Fakten + XMage Regeln + Korpus $\ge 5$ + EDHREC Daten | **219** | 27,3 % |
| **`SPARSE`** | Korpus beobachtet, aber dünn ($1 \le \text{hits} \le 4$) | **202** | 25,2 % |
| **`PARTIAL`** | Korpus $\ge 5$, aber EDHREC fehlt (z. B. Nischen-Staples) | **8** | 1,0 % |
| **`UNOBSERVED_IN_CORPUS`** | Im 975-Deck-Korpus bisher nicht beobachtet ($0$ Treffer) | **372** | 46,4 % |
| **Gesamt** | **Format-legaler Chulane-Pool im StudioStore** | **801** | **100,0 %** |

> [!IMPORTANT]
> **Striktes Evidenzprinzip zu `UNOBSERVED_IN_CORPUS` (372 Karten):**
> 0 Korpustreffer bedeutet ausschließlich **fehlende Beobachtung im kuratierten Korpus**, niemals Spielstärke 0 oder D-Tier! Karten wie z. B. `Esperzoa`, `Gleaming Barrier`, `Hydro-Channeler` oder `Faerie Artisans` besitzen starke mechanische Synergien und erhalten daher höchste Priorität für weitere Untersuchungen.

### Long-Tail-Kandidaten (413 von 801 Karten)

Exakt **413 Karten (51,6 % des Pools)** wurden als **Long-Tail-Kandidaten** identifiziert:
- **Kriterium:** $0 \le \text{Korpustreffer} \le 4$ **UND** (Kreatur mit $\text{MV} \le 3$ ODER Synergie-Rolle Bounce/Recast/Ramp/Draw/Landfall ODER Spellbook-Kombostück).
- **Höchste Research-Priorität (Score 0,48):**
  - `Esperzoa` (MV 3, Artifact Creature, Upkeep-Bounce)
  - `Gleaming Barrier` (MV 2, Creature, Mana/Treasure Death-Trigger)
  - `Hydro-Channeler` (MV 3, Creature, Bounce/Draw Spells)
  - `Cephalid Facetaker` (MV 3, Creature, Copy/ETB)
  - `Combat Courier` (MV 2, Artifact Creature, Draw/Recast)
  - `Faerie Artisans` (MV 3, Creature, Token-ETB-Abundance)

---

---

## 4. Deliverable 3: Beispielreport für vorhandene, schwache und unbekannte Beobachtungen

Gemäß den P0-Abnahmekriterien aus Issue #1185 wurde ein strukturierter Beispielreport implementiert (`generate_gap_example_report` und CLI-Befehl `python -m commander_lab.studio sources --example-report`). Er demonstriert die Repräsentanz der vier Evidenzklassen im legalen Pool:

### 1. `COMPLETE` (Vollständige Evidenz)
- **Beispiel 1: `Aether Adept`**
  - Manawert: 3, Typ: `Creature — Human Wizard`, Rollen: `bounce`
  - Korpus: 6 / 975 Treffer ($0{,}6\,\%$)
  - EDHREC: Vorhanden, Inclusion: $100{,}0\,\%$ (breiteste Ansicht, kein Lift)
  - Research-Score: $0{,}08$ (gut belegt, geringer Forschungsbedarf)
- **Beispiel 2: `Aftermath Analyst`**
  - Manawert: 2, Typ: `Creature — Elf Detective`, Rollen: `ramp`, `landfall`
  - Korpus: 6 / 975 Treffer
  - EDHREC: Vorhanden, Inclusion: $5{,}56\,\%$ (breiteste Ansicht, kein Lift)
  - Research-Score: $0{,}08$

### 2. `SPARSE` (Schwache Evidenz / 1–4 Korpustreffer)
- **Beispiel 1: `Felidar Cub`**
  - Manawert: 2, Typ: `Creature — Cat Beast`, Rollen: `removal`
  - Korpus: 1 / 975 Treffer
  - EDHREC: Fehlend
  - Research-Score: $0{,}351$ (Long-Tail-Kandidat)
- **Beispiel 2: `Groundskeeper`**
  - Manawert: 1, Typ: `Creature — Human Druid`, Rollen: `card_advantage`, `recursion`
  - Korpus: 1 / 975 Treffer
  - EDHREC: Fehlend
  - Research-Score: $0{,}351$ (Long-Tail-Kandidat)

### 3. `PARTIAL` (Partielle Evidenz / $\ge 5$ Korpustreffer, aber fehlendes EDHREC)
- **Beispiel 1: `Fleetfoot Panther`**
  - Manawert: 3, Typ: `Creature — Cat`, Flash, Self-Bounce (`roles: ['bounce']`)
  - Korpus: 16 / 975 Treffer ($1{,}64\,\%$)
  - EDHREC: Fehlend im Chulane-Schnitt (keine Inclusion-Beobachtung)
  - Research-Score: $0{,}24$
- **Beispiel 2: `Walking Atlas`**
  - Manawert: 2, Typ: `Artifact Creature — Construct`, Land-Drop-Tap (`roles: ['ramp']`)
  - Korpus: 8 / 975 Treffer
  - EDHREC: Fehlend
  - Research-Score: $0{,}24$

### 4. `UNOBSERVED_IN_CORPUS` (Unbekannt / 0 Korpustreffer)
- **Beispiel 1: `Esperzoa`**
  - Manawert: 3, Typ: `Artifact Creature — Jellyfish`
  - Upkeep-Trigger: Lässt Artefakte auf die Hand zurückspringen (potentieller Mana-/ETB-Recast für 0–2 Mana)
  - Korpus: **0 / 975 Treffer**
  - Research-Score: **$0{,}48$ (Spitzen-Research-Priorität)**
  - Einordnung: *Missing observation* – extrem starke mechanische Synergie, die im Standard-Korpus komplett übersehen wird!
- **Beispiel 2: `Gleaming Barrier`**
  - Manawert: 2, Typ: `Artifact Creature — Wall`
  - Death-Trigger erzeugt Treasure-Token
  - Korpus: **0 / 975 Treffer**
  - Research-Score: **$0{,}48$**

---

## 5. Software-Architektur und Schnittstellen

1. **CLI-Befehle:**
   - **Quellenregister:**
     ```bash
     python -m commander_lab.studio sources
     python -m commander_lab.studio sources --verified-only
     ```
   - **801-Karten-Lückenmatrix berechnen und exportieren:**
     ```bash
     python -m commander_lab.studio sources --gap-report
     python -m commander_lab.studio sources --gap-report --gap-out custom_matrix.json
     ```
   - **Beispielreport erzeugen:**
     ```bash
     python -m commander_lab.studio sources --example-report
     ```
2. **Datenablage:**
   - [`data/provenance/source_inventory.json`](../../data/provenance/source_inventory.json): Versioniertes Quellenregister (9 Quellen: 5 `VERIFIED`, 4 `REVIEW`).
   - [`data/research/chulane_legal_pool_gap_matrix.json`](../../data/research/chulane_legal_pool_gap_matrix.json): Vollständige Matrix für alle 801 legalen Poolkarten mit `research_priority_score`, `coverage_grade` und Long-Tail-Kennzeichnung.
3. **Unit-Tests:**
   - [`tests/unit/test_studio_sources.py`](../../tests/unit/test_studio_sources.py): 12 Tests, $100\,\%$ Test-Hygiene, 0 `Any`-Verletzungen, vollständige CLI-Abdeckung.

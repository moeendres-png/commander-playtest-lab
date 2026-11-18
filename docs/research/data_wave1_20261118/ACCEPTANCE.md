> Herkunft: Abnahmebericht der Datensammlung Welle 1 vom 2026-11-18, Wortlaut unverändert bis auf
> Namen der prüfenden Sitzung und Arbeitsverzeichnis-Pfade. Die Auflagen sind seit der
> Wiederholbarkeits-Änderung in `scripts/data_wave1/` umgesetzt; wie jede Auflage behoben wurde,
> steht in `README.md` (Abschnitt „Abnahme-Auflagen und ihre Behebung“). Die Zahlen sind Zahlen
> vom 2026-11-18; die Quellen ändern sich täglich.

# Abnahme Datensammlung Welle 1 (unabhängige Prüfsitzung, 2026-11-18)

Grundlage: `data_plan.md` Abschnitt D, `data_frame.md`. Alles selbst nachgerechnet (Prüfskripte der Prüfsitzung, nicht im Repository;
Python `-I`, DB `mode=ro&immutable=1`).
Kein Abruf von Datenquellen; einziger Web-Zugriff: Lesen der Playgroup-OpenAPI-Doku.
Repo: `git status --porcelain` = 0 Zeilen, HEAD `dced77b8…` (vor und nach der Prüfung).

| Paket | Urteil |
|---|---|
| S1 Scryfall | **ABGENOMMEN MIT AUFLAGEN** |
| S2 Spellbook | **ABGENOMMEN MIT AUFLAGEN** |
| S3 Playgroup | **ABGENOMMEN MIT AUFLAGEN** (Daten sauber; Bedeutung/Kohorte im Manifest falsch beschrieben) |

---

## S1 Scryfall-Bulk-Bündel (`staging/S1_scryfall/20261118T221408Z`)

**Log/Regeln.** 5 Anfragen (Limit 5), alle 200, kein 429/403, kein Retry, Abstände ≥ 5 s,
User-Agent `mtg-deck-tool/1.0 (local research script)` (generisch). Nur die 5 geplanten Adressen.

**Hashes/Zeilen (selbst gerechnet).** Alle 12 Einträge in `derived_files` stimmen in Bytes und
SHA-256. Zeilen: oracle_cards 39.356, rulings 80.928, oracle_tags 4.606, default_cards 120.210,
Teilmenge 1.655. Rohdaten: Index-Datei SHA-256 `1d05b132…` stimmt (und der ETag ist dessen
32-Zeichen-Präfix). Die vier `.gz` wurden planmäßig nicht behalten, ihr SHA-256 ist daher
**nicht nachprüfbar**; indirekt belegt: `content-length` der Header = `compressed_size` im Index
= `raw_size_bytes` im Manifest (4/4).

**Verbotene Felder.** Rekursive Schlüsselzählung über alle vier Dateien
(`prices`, `purchase_uris`, `salt`, `user`, `owner`, `pilot`, `top_decks`): 0.

**Validierungszahlen.**
- oracle_cards 39.356 (≥ 35.361), Sammlung 1.655/1.655 enthalten; Teilmenge = exakt die 1.655 IDs der Tabelle `card`.
- Rulings 80.928; 952 Sammlungskarten mit Ruling; 3.264 gegen Store 3.259 (Netto +5; 3 Karten
  mit anderer Anzahl: +1, +1, +3; mengenmäßig 7 neue Texte, 2 Store-Texte nicht mehr vorhanden).
- Tags 4.606; 1.629/1.655 getaggt (26 ohne Tag).
- Default Cards 120.210; 1.646/1.650 Set-/Nummer-Paare genau ein Druck, 4 ohne, 0 mehrfach.
  Die 4 ohne Treffer tragen keine Scryfall-Setcodes, sondern Fremdcodes der Sammlungsquelle:
  `xcmr/456` Wear // Tear → Scryfall `cmr/456`; `xdmc/68` Tor Wauki the Younger → `dmc/68`;
  `xmh2/381` Blacksmith's Skill → `mh2/381` (x-Präfix = „Extras“-Untersets); `sch/189`
  Lavinia, Azorius Renegade → `prna/189` (Store-Championship-Promo). Alle vier per
  Code-Zuordnung lösbar, kein Datenmangel.
- Stichprobe 10 Zufallskarten (Seed 20261118) gegen `card`: 0 Abweichungen in Name, Kosten,
  Manawert, Typzeile, Text, Farbidentität. Gesamte Sammlung gegen `scryfall_card`: 0 echte
  Textabweichungen (40× nur `''` gegen NULL).

**Ehrlichkeit.**
- `s1_validate.py` in der abgelegten Fassung vergleicht (Set, Nummer, **Sprache**) und ergäbe
  417/1.650, nicht 1.646. Die gemeldete Zahl 1.646 ist richtig (von mir ohne Sprache
  nachgerechnet), aber **nicht mit dem abgelegten Skript reproduzierbar**.
- Mit Sprache: 417 Treffer; alle 148 deutschen Drucke fehlen im Default-Bulk (bestätigt den
  offenen Punkt des Plans). 1.087 Drucke haben `lang` NULL.
- Manifest offen und ehrlich benannt: `source_id` nicht geprüft, `terms_checked_utc` null,
  `license_status` unverified.

**Auflagen.**
1. Manifest ergänzen: je Datei `updated_at` und `download_uri` aus dem Index, `rows_in/rows_out`,
   `dropped_fields`, `data_class`; `source_id` aus dem Register; Bedingungen prüfen
   (`terms_checked_utc`).
2. `derived/collection_subset_*.jsonl` fehlt für Rulings (3.264 Zeilen), Tags und Default Cards
   (Plan verlangt die Teilmengen); offline nachziehen.
3. `s1_validate.py` auf den tatsächlich gerechneten Stand bringen (Sprache ignorieren, 4 Fehlpaare ausgeben).

**Import in DB-KOPIE (vorhandene Importer, kein Schema):** nicht MATERIAL, solange Kopie.
- `import-scryfall derived/oracle_cards.jsonl` → prüfen: 1.655/1.655 verknüpft; Zuwachs gegen
  35.361 erklären (3.995 neue IDs, davon 2.411 art_series, 940 token …).
- `import-rulings <Teilmenge>`: der Importer filtert **nicht** auf die Sammlung und ersetzt nur
  Dateien gleichen Namens. Deshalb die Teilmenge als `card_rulings_1655.jsonl` (3.264 Zeilen)
  übergeben, nicht `rulings.jsonl` (sonst 80.928 Zeilen und eine zweite Quelle). Erwartung:
  3.264 Rulings, 952 Karten.
- Tags: `scripts/import_scryfall_oracle_tags.py --bulk-file derived/oracle_tags.jsonl --store <Kopie> --audit-only`,
  dann mit `--out-roles`; nie `--download`. Wächter: Claims je Scope vorher/nachher
  (heute `SCRYFALL_TAGGER_ORIGINAL/WUG` 17.048).
- Drucke: `import-printings <Arbeitsmappe> --bulk derived/default_cards.jsonl` (braucht die
  Sammlungsdatei des Owners); vorher die 4 Fremdcodes zuordnen. Deutsche Drucke: Entscheidung
  `all_cards` (408 MB) oder 148 Einzelabrufe bleibt Owner-/Planfrage.

---

## S2 Commander-Spellbook-Bulk (`staging/S2_spellbook/20261118T221408Z`)

**Log/Regeln.** 1 Anfrage (Limit 1), 200, kein 429/403, generischer User-Agent, kein
`backend.commanderspellbook.com`.

**Hashes/Zeilen.** Roh `variants.json.gz` SHA-256 `fcaab1e1…` = Manifest; MD5 = ETag des
Servers (`69d9da3c…`) → Rohdatei ist byte-identisch zur Serverantwort. `variants_wug.jsonl`:
31.544 Zeilen, SHA-256 `d97d74f5…` = Manifest. Aus der Rohdatei neu abgeleitet: dieselben
31.544 IDs.

**Zahlen.** Varianten 123.315, commander-legal 121.792 (Plausibilität 15.11.: 123.118/121.593);
Status OK 122.972 / E 343; WUG 31.544, davon legal 31.041, legal+OK 30.941. Verbotene Schlüssel
in der Ableitung (price, purchase, salt, popularity, variantCount, user, owner, author): 0.

**„Nur 4 von 31.544“ – kein Matching-Fehler, die Zahl ist echt.**
- Abgleich läuft über `uses[].card.oracleId` gegen `card.oracle_id` (1.655, keine NULL; die
  ID-Datei im Staging ist identisch zur DB). Gegenprobe über Kartennamen: dieselben 182 Karten,
  0 Unterschiede in beide Richtungen.
- Ursache: Die WUG-Varianten nutzen 3.645 verschiedene Karten; **nur 182 (5,0 %)** liegen in der
  Sammlung. Variantengrößen (alle WUG): 1 Karte 5 · 2 Karten 1.929 · 3 Karten 16.211 · 4 Karten
  11.161 · 5 Karten 2.237 · 8 Karten 1. Bei 3–4 Pflichtkarten je Variante ist Vollabdeckung selten.
- Überdeckung (legal + Status OK, N = 30.941): fehlende Karten 0 → 4 · 1 → 226 · 2 → 3.623 ·
  3 → 16.205 · ≥ 4 → 10.883. Mindestens 1 Sammlungskarte: 4.495 (14,5 %). Mittlerer
  Sammlungsanteil je Variante 4,5 %, Median 0.
- **Sinnzahl für den Builder:** vollständig baubar **4**, bis auf 1 Karte **226** (zusammen 230;
  207 der 226 ohne zusätzliche Schablonen-Anforderung `requires`). Mit Chulane als Karte:
  56 Varianten, davon 3 vollständig, 17 mit 1 fehlenden Karte. Die 226 „fast“-Varianten hängen
  an 123 verschiedenen fehlenden Karten.
- Hinweis: 256 `uses` verlangen `mustBeCommander`; für Chulane-Decks müssen Varianten mit
  fremdem Pflicht-Commander ausgeschlossen werden (im Repo-Stand: 249).

**„12 abweichende Kartenmengen“ – Fehler im Prüfskript, nicht in den Daten.**
`s2_check.py`/`s2_check_all.py` lesen die ID mit `(\d+-\d+-\d+)` und schneiden damit alle IDs
mit ≥ 4 Segmenten ab (in der Referenz 6.544 von 16.571 Einträgen). Dadurch 13.144 statt 16.565
Schlüssel, falsche Zusammenführungen und 12 Scheinabweichungen. Mit vollständiger ID:
16.565 Referenz-IDs, 16.562 im Bulk (3 IDs `215-527-…` gibt es dort nicht mehr), 16.560 in WUG,
**16.559 gleich, 1 abweichend** (`3314-4377-5238`: handgepflegter Chulane-Eintrag, der die dritte
Karte als `any_of` führt – gewollt). Bonus-Plausibilität: Die Referenz nennt für den Abruf vom
15.11. `fetched 31.544`, `not_commander_legal 503`, `status_not_ok 100` – identisch zum Bulk.
Auch „Stichprobe 10: 1 in Referenz“ ist deshalb wertlos.

**Alias- und bracketTag-Entscheidung.**
- `of`/`includes` wurden als `alias_of`/`alias_includes` abgelegt: **falsch benannt**. Das sind
  die erzeugenden bzw. enthaltenen Kombo-Datensätze (Zahl-IDs), keine Aliase. Die echte
  Alias-Tabelle steht auf oberster Ebene der Rohdatei (`aliases`, 6.397 Einträge alte ID →
  `variant`, 119 mit Ziel) und **fehlt in der Ableitung** (Plan verlangt sie). Der Sammler hat die
  Unklarheit im Manifest als offenen Punkt genannt – ehrlich, aber zu korrigieren.
- `bracket_tag` roh behalten: vertretbar. Werte E 23.210 · S 3.940 · R 2.722 · P 592 · B 503 ·
  O 463 · C 114. Belegt ist nur: B ⇔ nicht commander-legal (503/503). Die übrigen Buchstaben
  sind im Paket nicht erklärt; es ist eine Schätzung der Quelle je Kombo, **kein erklärtes
  Deck-Bracket** → nie mit der Bracket-Kohorte der Decks mischen, bis die Legende belegt ist.
- `cards_all_in_collection` in einer Kartenfakten-Datei mischt Sammlungsbezug hinein;
  `legalities_commander` doppelt `commander_legal`. Beim Import weglassen.

**Ehrlichkeit.** Manifest: `terms_url` null, Lizenz „nicht belegt“ (ehrlich, aber offen);
`request_start_utc` nur im Log; `publisher` „laut Plan“.

**Auflagen.**
1. Ableitung offline neu schreiben (Rohdatei liegt vor, keine neue Anfrage): `aliases`-Tabelle
   dazu, `alias_of/alias_includes` → `of_ids/includes_ids`, Sammlungsfeld und Dublette raus.
2. Prüfskripte auf volle ID (`[\d-]+`) korrigieren; Vergleichszahl 16.559/16.560 ins Manifest.
3. Bedingungen/Lizenz und `source_id` klären; Legende zu `bracketTag` aus der Quelldoku belegen.
4. Überdeckungszahlen (4 / 226 / 4.495) statt der bloßen „4“ in den Bericht.

**Import.** Es gibt **keinen** Importer für Varianten; `data/meta/spellbook_combos.json` wird
als Repo-Datei gelesen (`builder.py`, `evidence.py`, `universe_view.py`, `sources.py`), die
Tabelle `commander_combo` (97 Zeilen) hat ein anderes Schema. Aufnahme = neue Tabelle/neuer
Importer oder Änderung einer Repo-Datei → **MATERIAL** (Schema/Importer, Review nötig). Bis
dahin nur als Staging-Referenz nutzbar.

---

## S3 Playgroup Public API (`staging/S3_playgroup/20261118T221456Z`)

**Log/Regeln.** 59 Anfragen (Limit 80; 57 volle Seiten, Seite 58 leer, 1× turn_damage), alle
200, kein 429/403, kein Retry, jede Adresse genau einmal, Mindestabstand 1,0 s, generischer
User-Agent. Die Doku sagt „about 54 calls“; tatsächlich 58 – unkritisch.

**Hashes/Zeilen.** 59/59 Rohantworten: SHA-256 = Log = Manifest (ETag = Präfix des Hashes).
Ableitungen 3/3 Hash gleich. 5.609 Zeilen roh und abgeleitet, 0 doppelte IDs, Chulane ID 2143
vorhanden. Verbotene Schlüssel 0; `top_decks` kommt in der Liste nicht vor; `average_salt_rating`,
`average_fun_rating`, Bild-/Scryfall-Felder entfernt. `pilot_count` ist eine Zählung, keine Person.

**Siege > Spiele: 29 Zeilen bestätigt** (12 mit 0 Spielen; größter Überschuss 7). Alle 29 haben
≤ 9 Spiele. Die Siegarten summieren sich in 5.609/5.609 Zeilen exakt zu `game_win_count`.

**Was die Listenfelder bedeuten (OpenAPI, Schema `CommanderListEntry`).**
- Grundgesamtheit: „from finished games with a win condition and seats with a salt rating. Solo
  playtests and Playgroup Cube games are not counted. Undone events are counted.“
- `game_played_count`: „Rated seats played with this commander. Two decks of this commander in
  one game count twice.“ `game_win_count`: „Rated seats won.“ `pilot_count`: „Distinct owners of
  an unarchived deck with this commander.“ `average_round_amount`: Runden je Spiel, je Spiel einmal.
- Einzelendpunkt `/commanders/{id}` (Schema `CommanderStats`): `games_count`, `games_won`,
  `games_lost`, `decks_count` **ohne Beschreibung**; liefert zusätzlich `average_wins_by_turn`
  („Average turn number when winning“), `top_decks` und Graphen.
- Die Doku sagt nichts dazu, wie Liste und Einzelendpunkt zusammenhängen.

**Die 91 Abweichungen sind deshalb kein Fehler, sondern zwei Zählweisen.** Liste = nur
**bewertete Sitze** (Sitz mit Salt-Bewertung, Spiel mit Siegbedingung); CSV (Einzelendpunkt,
Abruf 11./12.11.) = alle Spiele nach nicht dokumentierter Regel. Über die 107 IDs: 44.603 gegen
87.129, Liste in 91 Fällen kleiner, in 0 größer, Verhältnis im Median 0,54. Chulane: Liste
1.111 Sitze / 449 Siege (40,4 %) / 678 Piloten; CSV 2.110 Spiele / 782 Siege (37 %). Die
Verletzung Siege > Spiele ist mit der Doku **nicht erklärbar** (beide Felder heißen „rated
seats“) → Quellfehler bei Kleinstzahlen, dokumentieren, nicht korrigieren.

**Ehrlichkeit – ein falscher Satz im Manifest.** `cohort_scope`: „alle Commander,
Solo-Playtests und Cube laut API-Beschreibung“. Die Doku sagt das Gegenteil (nicht gezählt). Die
Feldnamen `games_count`/`games_won` der Ableitung verdecken, dass es Sitze sind, und laden zur
Verwechslung mit dem CSV ein. `repo_commit` „nicht ermittelt“; `source_id` nicht vergeben.

**Genügt die Listenzählung für B5?**
- **Ja für den Gültigkeitsblock von SIMULATE**, wenn als das benannt, was sie ist: Chulane
  n = 1.111 bewertete Sitze, mittlere Spiellänge 8,82 Runden, Siegart-Anteile (z. B. Kampf
  276/449, Kombo 66/449), Mulligans 0,55 je Sitz. Definierte Nenner, täglich neu gebaut.
  Regeln: nur Zeilen mit n ≥ 30 **und** Siege ≤ Spiele verwenden (2.151 Zeilen; schließt alle
  29 Verletzer aus); Auswahlverzerrung nennen (nur bewertete Sitze; Quote liegt höher als im
  Einzelendpunkt); nie mit den CSV-Zahlen verrechnen (zwei Kohorten).
- **Nein für die Sitz-/Zugkurve.** `turn_damage` ist der Mittelwert **je Einzelereignis** je
  Runde, kein Rundenwert, ohne n, mit Selbstschaden und rückgängig gemachten Ereignissen;
  Chulane hat Ausreißer (Runde 9: 3.761.289,99; Heilung Runde 7: 3.594,08). Als Kurve
  unbrauchbar; höchstens als „vorhanden, nicht belastbar“ führen. Der „Siegzug“
  (`average_wins_by_turn`) steht nur im Einzelendpunkt.
- **Empfehlung:** Welle 1 mit der Liste abschließen. Der Einzelendpunkt ist nur nötig, wenn der
  Builder den Siegzug oder die 107er-Vergleichsbasis aktuell braucht: dann 1 Anfrage (Chulane)
  bzw. ≤ 107 Anfragen bei 1/s (laut Doku erlaubt: „Walking … every commander once is fine“),
  `top_decks` und alles zu Nutzern beim Schreiben entfernen. Das ist ein neuer Live-Abruf →
  **Owner-Frage** (Gate #1192), dazu O4 (Kontakt im User-Agent: Playgroup bittet darum).

**Auflagen.**
1. Manifest: `cohort_scope` berichtigen („bewertete Sitze; ohne Solo-Playtests und Cube“).
2. Ableitung offline neu schreiben: Felder als `rated_seats_played`/`rated_seats_won` (oder
   Quellnamen), Kennzeichen `wins_gt_games` je Zeile, Platzhalter ID −2 („Guest Commander“)
   markieren; `turn_damage` mit Warnhinweis „Mittel je Ereignis, kein n“.
3. Nennungspflicht (CC BY 4.0, Link auf `playgroup_url`) in jede Anzeige übernehmen.

**Import.** `import-playgroup-atlas` liest den **Karten**atlas, nicht die Commander-Statistik;
`playgroup_commander_stats.csv` hat heute keinen Leser. Aufnahme = neue Tabelle/Importer →
**MATERIAL**. S3b (927 Kartenseiten) kann aus Sicht dieser Abnahme starten, sobald Auflage 1
erledigt ist; es bleibt ein Live-Abruf unter Gate #1192.

---

## Gemeinsame Punkte

- Kein Paket hat ins Repo geschrieben oder importiert; alle drei melden `automatic_import: false`.
- In allen drei Manifesten fehlt die `source_id` des Registers; Bedingungen sind nur bei S3 geprüft.
- Reihenfolge der nächsten Schritte: (1) Auflagen offline nachziehen (keine neue Anfrage nötig),
  (2) S1 in DB-Kopie importieren mit Zählwächtern, (3) S2/S3 als MATERIAL-Vorhaben (Schema +
  Importer) über Issue/Review, (4) Owner-Fragen: deutsche Drucke, Einzelendpunkt Playgroup, O4.

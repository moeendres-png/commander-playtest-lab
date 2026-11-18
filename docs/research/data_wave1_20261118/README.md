# Datensammlung Welle 1 (2026-11-18): Ergebnis, Wiederholbarkeit, offene Punkte

Zu den Issues #1554 (Scryfall-Bulk, S1), #1555 (Commander-Spellbook-Bulk, S2) und #1556
(Playgroup-Commander-Statistik, S3). Die Daten selbst stehen **nicht** im Repository (groß, die
Lizenz ist je Quelle ungeklärt, und der Studio-Store liegt am Owner-PC). Das Repository enthält, was
nötig ist, um die Sammlung dort zu wiederholen und nachzuvollziehen.

| Datei | Inhalt |
|---|---|
| `README.md` | Diese Seite: Ergebnis, Zahlen mit Herkunft, Auflagen und Behebung, Grenzen, Owner-Fragen |
| `RUNBOOK.md` | Schritt für Schritt am Owner-PC (Windows und WSL/Linux): Sammeln, Ableiten, Import in eine Kopie, Wächter, Verbote |
| `ACCEPTANCE.md` | Abnahmebericht der unabhängigen Prüfsitzung vom 2026-11-18 (Wortlaut, ohne Arbeitsverzeichnis-Pfade) |
| `PLAN.md` | Abschnitte C (Lückenliste, Zugangsstatus der Quellen) und D (Sammlungsplan) des Datenplans |
| `manifests/` | Die drei Provenienz-Manifeste des Laufs (`S1_scryfall`, `S2_spellbook`, `S3_playgroup`), nur Pfade bereinigt, ohne Rohdaten |
| `../../../scripts/data_wave1/` | Die wiederholbaren Skripte (reines Python 3, nur Standardbibliothek) |
| `../../../tests/unit/test_data_wave1_scripts.py` | Offline-Tests der Skripte (kein Netz, eingebettete Mini-Fixtures), auch gegen feindliche Antworten (Kennungen, Umleitungen, Größen) |

## 1. Ergebnis

Alle drei Pakete wurden am 2026-11-18 als Hilfs-Agent-Lauf gesammelt und von einer unabhängigen
Prüfsitzung **abgenommen mit Auflagen** (`ACCEPTANCE.md`). Anfragen: S1 5 von höchstens 5,
S2 1 von 1, S3 59 von höchstens 80; alle HTTP 200, kein 429 oder 403, keine Wiederholung, generische
Kennung `mtg-deck-tool/1.0 (local research script)`. Kein Paket hat ins Repository geschrieben oder
importiert; alle Manifeste sagen `automatic_import: false`. `personal_data: none` gilt für die
abgeleiteten Dateien. Die Rohdaten des Laufs (S2 `variants.json.gz`, S3 Rohseiten) enthalten Felder,
die die Regeln ausschließen (Preise, Salt-Werte, `top_decks`, Eigner-Namen); die Manifeste dieses
Laufs (`manifests/`) tragen `personal_data: none` und S2 `raw_retained: true`, ohne diesen Zusatz zu
nennen. Seither gilt: die Skripte löschen die Rohdaten nach dem Ableiten (Standard) und vermerken in
den Manifesten `raw_retained` und `raw_contains_excluded_fields`; `--keep-raw` hält sie.

Danach wurde S1 offline in eine Kopie der Studio-DB (Stand 2026-11-16) importiert: `import-scryfall`,
`import-rulings` (nur die Teilmenge), Tags nur als Audit. Wächter vorher und nachher: `integrity_check`
ok, `foreign_key_check` 0 Zeilen, Schema und Karten-Oracle-ID-Zuordnung unverändert; geändert nur
`scryfall_card`, `scryfall_card_token`, `scryfall_token`, `card_ruling`, `card_ruling_source`,
`source`; die übrigen 40 von 44 Tabellen unverändert.

Wiederholbar gemacht (diese Änderung): die Hilfsskripte des Laufs lagen in einem flüchtigen
Arbeitsverzeichnis. Ihre Logik und die berichtigten Prüfungen sind nach `scripts/data_wave1/`
übernommen; der Ablauf steht im `RUNBOOK.md`.

## 2. Zahlen mit Herkunft

Alle Zahlen sind Stand 2026-11-18 und ändern sich mit der Quelle. Herkunft: Manifeste
(`manifests/`), `ACCEPTANCE.md` (von der Prüfsitzung selbst nachgerechnet) und die Prüfausgaben der
Skripte.

**S1 Scryfall (Bulk-Index vom 2026-11-18, 22:01 bis 22:06 UTC)**

| Zahl | Wert | Herkunft |
|---|---|---|
| Zeilen `oracle_cards` · `rulings` · `oracle_tags` · `default_cards` | 39.356 · 80.928 · 4.606 · 120.210 | Manifest, von der Prüfung nachgezählt |
| Sammlungs-Oracle-IDs in `oracle_cards` | 1.655/1.655 | Manifest, Prüfung |
| Teilmenge `oracle_cards` · `card_rulings_1655` · Default-Cards der Sammlung | 1.655 · 3.264 · 16.614 Zeilen | Manifest; 17 Zeilen nur über `card_faces` getroffen |
| Sammlungskarten mit Ruling | 952/1.655 (Store vorher 3.259 Rulings, jetzt 3.264, netto +5) | Prüfung |
| Sammlungskarten mit Tag | 1.629/1.655 (26 ohne Tag) | Prüfung |
| (Set, Nummer) der Sammlung mit genau einem Druck, ohne Sprache | 1.646/1.650 (0 mehrfach, 4 ohne) | Prüfung; `validate_s1.py` reproduziert die Zahl |
| dasselbe mit Sprache (nur Information) | 417/1.650; alle 148 deutschen Drucke fehlen im Default-Bulk; 1.087 Drucke mit `lang` NULL | Prüfung |
| Preis- und Personenfelder in den abgeleiteten Dateien | 0 (rekursive Schlüsselzählung) | Prüfung |
| Roh-Hashes der vier `.gz` | **nicht nachprüfbar** (nicht behalten); indirekt: `content-length` = `compressed_size` im Index = Manifest, 4/4 | Prüfung |
| Import in die Kopie | `oracle_cards` 35.420 (vorher 35.361), 1.020 Tokens, 4.250 Karte-Token-Verknüpfungen, 1.655/1.655 verknüpft, 1 Faktenabweichung (Farbidentität einer Karte); Rulings 3.264, 952 Karten; Tag-Audit 4.606 Tags, Negativ-Vokabular bestanden | Ausgaben des Importlaufs |

**S2 Commander Spellbook (Datei vom 2026-11-18, `timestamp` 22:13:17 UTC, Version 7.4.4)**

| Zahl | Wert | Herkunft |
|---|---|---|
| Rohdatei | 32.664.289 Bytes, entpackt 743.920.732; SHA-256 stimmt mit dem Manifest, MD5 mit dem ETag des Servers | Manifest, Prüfung |
| Varianten gesamt · commander-legal | 123.315 · 121.792 | Manifest |
| Status OK · E | 122.972 · 343 | Manifest |
| WUG-Varianten · davon commander-legal · legal und Status OK (N) | 31.544 · 31.041 · 30.941 | Manifest, Prüfung |
| Aliastabelle · davon mit Ziel | 6.397 · 119 | Manifest |
| Überdeckung in N: vollständig baubar · bis auf 1 Karte · mindestens 1 Sammlungskarte | 4 · 226 · 4.495 (14,5 %) | `validate_s2.py`, Prüfung |
| Fehlende Karten in N: 0 · 1 · 2 · 3 · 4 oder mehr | 4 · 226 · 3.623 · 16.205 · 10.883 | Prüfung |
| verschiedene Karten in N · davon in der Sammlung | 3.614 · 181 | Manifest |
| mit Chulane in N | 56: 3 vollständig, 17 mit 1 fehlenden, 36 mit 2 oder mehr | Manifest, Prüfung |
| Vergleich mit `data/meta/spellbook_combos.json` (volle ID) | 16.565 IDs, 16.560 in WUG, 16.559 gleich, 1 abweichend (handgepflegter Eintrag, gewollt) | Prüfung, `validate_s2.py` |

Die Zahl „nur 4 von 31.544“ ist echt und kein Zuordnungsfehler: die WUG-Varianten brauchen meist 3
bis 4 Karten und nur 181 der 3.614 verwendeten Karten liegen in der Sammlung. Sinnzahl für den
Builder: 4 vollständig baubar, 226 bis auf eine Karte.

**S3 Playgroup (Commander-Liste, Abruf 2026-11-18, 22:14 bis 22:16 UTC)**

| Zahl | Wert | Herkunft |
|---|---|---|
| Anfragen · Seiten | 59 (57 volle Seiten, Seite 58 leer, 1 `turn_damage`) | Manifest, Prüfung |
| Commander-Zeilen · doppelte IDs | 5.609 · 0 | Manifest, Prüfung |
| Chulane | 1.111 bewertete Sitze, 449 Siege (40,4 %), 678 Piloten | Prüfung |
| Zeilen mit Siegen > Sitzen | 29/5.609 (12 mit 0 Sitzen, größter Überschuss 7, alle mit höchstens 9 Sitzen) | Prüfung |
| nutzbar (Sitze ≥ 30 und Siege ≤ Sitze) | 2.151/5.609 | Prüfung |
| Siegarten summieren sich je Zeile zu den Siegen | 5.609/5.609 | Prüfung |
| gegen `playgroup_commander_stats.csv` (107 IDs): Liste kleiner · gleich · größer | 91 · 16 · 0; Summe 44.603 gegen 87.129 | Prüfung |

Die 91 Abweichungen sind keine Fehler, sondern zwei Zählweisen: die Liste zählt nur **bewertete
Sitze** (Sitz mit Salt-Bewertung in beendeten Spielen mit Siegbedingung; ohne Solo-Playtests und
Cube), die CSV stammt aus dem Einzelendpunkt. Die Felder heißen darum `rated_seats_played` und
`rated_seats_won`. Beide Quellen werden nie verrechnet.

**Reproduktion durch die neuen Skripte (offline gegen den Staging-Stand des Laufs):**

| Prüfung | Ergebnis |
|---|---|
| Sammlungs-ID-Export aus der Store-Kopie, gleicher SHA-256 wie die Datei des Laufs | 1/1 |
| S1-Teilmengen (`oracle_cards`, `card_rulings_1655`, Tag- und Default-Cards-Teilmenge), byte-gleich | 4/4 |
| S1 Schreibweg (Entpacken, Preisfelder entfernen, kompakt schreiben) auf die vier Dateien angewandt, byte-gleich | 4/4 |
| S2 `variants_wug.jsonl` (31.544 Zeilen) und `aliases.jsonl` (6.397), byte-gleich aus der Rohdatei | 2/2 |
| S3 `playgroup_commanders.jsonl` (5.609 Zeilen), byte-gleich aus den 58 Seiten; `chulane_turn_damage.json` gleich bis auf den Schlusszeilenumbruch | 2/2 |
| `validate_s1.py` (1.646/1.650, 4 Fehlpaare, 4/4 Zuordnungen), `validate_s2.py` (Überdeckung, 16.559/16.560), `validate_s3.py` (29, 2.151, 91/16/0) | gleiche Zahlen wie die Abnahme |
| `db_guard.py` auf die Kopie vom 2026-11-16: Digest je Tabelle wie der Wächter des Laufs | 44/44 |

Nicht reproduziert: der Netzabruf selbst. Die neuen Sammelskripte wurden nicht gegen die echten
Server gefahren (kein Netz in dieser Aufgabe); sie sind mit einem nachgebildeten Opener getestet
(`tests/unit/test_data_wave1_scripts.py`). Der erste echte Lauf am Owner-PC ist ihre Bewährung:
**UNKNOWN**, bis das Runbook dort einmal durchgelaufen ist.

## 3. Abnahme-Auflagen und wie sie behoben wurden

| Auflage der Abnahme | Behebung | Stand |
|---|---|---|
| S1-1 Manifest je Datei ergänzen (`updated_at`, `download_uri`, `rows_in/out`, `dropped_fields`, `data_class`) | `fetch_s1_scryfall.py` schreibt sie ins Manifest | erledigt |
| S1-1 `source_id` aus dem Register, Bedingungen prüfen (`terms_checked_utc`) | Manifest sagt ehrlich `source_id`/`license_status` „ungeklaert“, `terms_checked_utc: null`; die Zuordnung zum Register und die Prüfung macht eine Person | **offen** (Owner-Frage 4) |
| S1-2 Teilmengen für Rulings, Tags, Default Cards | `derive_s1_subsets.py` (`card_rulings_1655.jsonl` 3.264 Zeilen, Tag-Teilmenge, Default-Cards-Teilmenge 16.614) | erledigt |
| S1-3 `s1_validate.py` auf den gerechneten Stand bringen (Sprache ignorieren, 4 Fehlpaare ausgeben) | `validate_s1.py`: Vergleich ohne Sprache, Fehlpaare einzeln, Zuordnung `set_code_mapping.json`; Zahl mit Sprache nur als Information | erledigt |
| S2-1 Ableitung neu: echte Aliastabelle, `of`/`includes` richtig benennen, Sammlungsfeld und Dublette raus | `derive_s2_variants.py` (`aliases.jsonl`, `generates`, `includes_combos`) | erledigt |
| S2-2 Prüfskripte auf die volle ID (`[\d-]+`) | `validate_s2.py` (16.559/16.560 statt 12 Scheinabweichungen) | erledigt |
| S2-3 Bedingungen, Lizenz, `source_id`, Legende zu `bracketTag` | `bracket_tag` roh behalten und im Manifest als „kein erklärtes Deck-Bracket“ vermerkt; Bedingungen/Lizenz weiter ungeklärt | **offen** (Owner-Frage 4) |
| S2-4 Überdeckungszahlen statt der bloßen „4“ | `validate_s2.py` (`variants_wug_coverage_counts.json`: 4 / 226 / 4.495) | erledigt |
| S3-1 `cohort_scope` berichtigen | `fetch_s3_playgroup.py` schreibt „bewertete Sitze; ohne Solo-Playtests und Cube“ | erledigt |
| S3-2 Ableitung neu: `rated_seats_*`, `wins_exceed_games`, Platzhalter, `turn_damage` mit Warnhinweis | `derive_s3_commanders.py` | erledigt |
| S3-3 Nennungspflicht (CC BY 4.0, Link auf `playgroup_url`) in jede Anzeige | `playgroup_url` bleibt in jeder Zeile und im Manifest; die Anzeige in der Oberfläche gibt es noch nicht | **offen** (mit dem Importer, Abschnitt 5) |

Härtung nach Review: Kennungen aus Antworten (Commander-ID) gehen nur als einfache positive Ganzzahl in
Adresse und Dateiname, Zielpfade werden auf den Lauf-Ordner begrenzt; Umleitungen werden nicht
befolgt und die liefernde Adresse (`final_url`) steht im Manifest; Rohdaten werden nach dem Ableiten
gelöscht (Standard); Antwort- und Entpackgröße sind begrenzt; `--pause` hat eine Untergrenze; ein
fehlender `turn_damage`-Wert ist `null`, nicht 0; `--out` von `export_collection_ids.py` und
`db_guard.py` darf nicht im Repository liegen.

Weitere Regeln des Plans, die jetzt im Code stehen (und getestet sind): Netz nur mit
`--allow-network`; Anfragelimit je Paket (S1 5, S2 1, S3 80), Wiederholungen zählen mit; Stopp bei
429 oder 403 mit `Retry-After` im Log; höchstens eine Wiederholung nach 60 s; nie parallel; nur
`https`; Download-Adressen aus dem Scryfall-Index nur unter `data.scryfall.io`; Preis- und
Personenfelder werden beim Schreiben entfernt; Staging nie im Repository.

## 4. Grenzen und UNKNOWN

- **Netzlauf der neuen Skripte: UNKNOWN** (siehe oben). Erst der Lauf am Owner-PC zeigt, ob etwa
  eine Firmen-Proxy-Konfiguration oder die Server-Antworten den Skripten Probleme machen.
- **Windows: NOT_RUN.** Nichts wurde unter Windows ausgeführt: weder die Skripte noch die
  PowerShell-Befehle des Runbooks, noch der SQLite-Dateipfad (`Path.as_uri()`) oder die Auflösung von
  `%LOCALAPPDATA%`. Getestet ist die Pfadlogik für Windows nur mit nachgebildeten Umgebungswerten.
  Der Lauf unter Linux wurde gegen den Staging-Stand des Laufs vom 2026-11-18 geprüft (Abschnitt 2).
- **Zahlen driften.** Alle drei Quellen werden täglich neu gebaut. Das `RUNBOOK.md` trennt harte
  Prüfungen von Referenzwerten.
- **Roh-Hashes der vier Scryfall-Dateien** sind für den Lauf vom 2026-11-18 nicht nachprüfbar. Die
  neuen Skripte halten die Dateien auf Wunsch (`--keep-raw`), im Standard nicht.
- **Store des Owners:** der Import wurde nur an einer Kopie vom 2026-11-16 geprüft. Ob die
  Produktiv-DB gleich aussieht: **UNKNOWN**.
- **Lizenzen und Nutzungsbedingungen:** je Quelle ungeklärt (Abschnitt 5, Frage 4). Die Manifeste
  führen `license_status: ungeklaert` und `terms_checked_utc: null`; das gilt auch für S3, dessen
  OpenAPI-Dokumentation CC BY 4.0 nennt (keine rechtliche Prüfung).
- **S2 und S3 haben keinen Importer.** `data/meta/spellbook_combos.json` wird als Repo-Datei gelesen
  (`builder.py`, `evidence.py`, `universe_view.py`, `sources.py`), die Tabelle `commander_combo` hat
  ein anderes Schema; `import-playgroup-atlas` liest den Kartenatlas, nicht die Commander-Statistik.
  Beides bleibt Staging-Referenz, bis ein Importer da ist (Schema- und Importer-Änderung, MATERIAL).
- **`bracket_tag` (S2)** ist die Schätzung der Quelle je Kombo, belegt ist nur „B genau dann, wenn
  nicht commander-legal“ (503/503); nicht mit dem Bracket der Decks mischen.
- **`turn_damage` (S3)** ist ein Mittel je Einzelereignis je Runde, ohne n, mit Selbstschaden und
  rückgängig gemachten Ereignissen (Ausreißer in Runde 9 und 7); als Kurve unbrauchbar. Der Siegzug
  steht nur im Einzelendpunkt (nicht in diesem Paket).
- **Siege > Sitze** in 29 Zeilen sind ein Quellfehler bei Kleinstzahlen, dokumentiert und gekennzeichnet,
  nicht korrigiert. Nur Zeilen mit mindestens 30 Sitzen und Siegen höchstens Sitzen verwenden.
- **Pflicht-Commander in Varianten:** 256 Verwendungen verlangen `mustBeCommander`; für Chulane-Decks sind
  Varianten mit fremdem Pflicht-Commander auszuschließen.

## 5. Offene Owner-Fragen

1. **Deutsche Drucke (148).** Der Default-Bulk enthält sie nicht (Trockenlauf der Auflösung: 1.499 von
   1.650 aufgelöst, 147 mehrdeutig auf Deutsch, 4 nicht gefunden; mit den vier Fremdcodes 1.502 und
   148 mehrdeutig). Optionen: `all_cards` laden (rund 389 bis 408 MB laut Scryfall-Seite), 148
   Einzelabrufe `/cards/{set}/{nummer}/de` mit 1 pro Sekunde (Plan), oder Verzicht (Bild des
   englischen Drucks). Dazu die Zuordnung der vier Fremdcodes (`xcmr`, `xdmc`, `xmh2`, `sch`) in
   `set_code_mapping.json`. `import-printings` braucht die Arbeitsmappe des Owners.
2. **Playgroup-Einzelendpunkt `/commanders/{id}`.** Er liefert den Siegzug (`average_wins_by_turn`) und
   die 107er-Vergleichsbasis: 1 Anfrage für Chulane oder bis zu 107 Anfragen bei 1 pro Sekunde, `top_decks`
   und alles zu Nutzern würden beim Schreiben entfernt. Neuer Live-Abruf unter Gate #1192.
3. **Kontaktangabe im User-Agent.** Playgroup bittet Aufrufer, erkennbar zu sein; die Leitplanke
   verlangt eine generische Kennung. Vorschlag: ohne Kontakt (so laufen die Skripte).
4. **Lizenzen und Nutzungsbedingungen je Quelle.** Scryfall: kostenlos für Software und Forschung,
   Preise entfernen (geschieht), nicht als Trainingsmaterial verwenden; die `robots.txt` von
   `data.scryfall.io` trägt ein Content-Signal (`ai-train=no, use=reference`): soll der Owner die
   vier Dateien lieber selbst laden (Plan O6)? Commander Spellbook: Bulk erlaubt, die Datenlizenz ist auf
   den gelesenen Seiten nicht belegt, Nennung wird erbeten. Playgroup: CC BY 4.0 laut OpenAPI mit
   Nennung per Link. Und die Zuordnung zu Einträgen des Quellenregisters (`source_id`).
5. **Importer für S2 und S3.** Neue Tabellen oder ein Importer sind MATERIAL (Review nötig). Frage:
   Priorität, und ob Spellbook-Varianten und Playgroup-Referenzwerte in die Studio-DB sollen oder als
   Datei neben ihr gelesen werden.
6. **S3b** (927 Kartenseiten des Playgroup-Atlas, Live-Abruf unter Gate #1192) ist nach Abnahme von S3
   möglich; die Fragen O1 bis O6 des Plans (EDHREC, Archidekt, TopDeck-Schlüssel, Preis-Skript)
   bleiben unberührt (`PLAN.md`).

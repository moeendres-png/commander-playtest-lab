# Commander Studio: objektiver TAM-/Chulane-Quellenkatalog (2026-11-11)

**Status:** Metadaten- und Prüfnachweis für Agents; **kein importierbarer Deckkorpus**. [Aufgaben-Issue #1187](https://github.com/moeendres-png/commander-playtest-lab/issues/1187).

## Autorität und Zugang

- `main` ist der maßgebliche **Code**-Stand; der persönliche Kartenbestand, die einzelnen Decklisten und die historischen Originalantworten verbleiben außerhalb dieses **öffentlichen** Repositorys auf berechtigtem [Google Drive](https://drive.google.com/drive/folders/1muyGu8uQNLGvc_LBdkdRyhF406O2WWAC) beziehungsweise im lokalen Owner-Datenordner.
- **Maschinenlesbarer Einstieg:** [`data/provenance/commander_studio_drive_sources_20261111.json`](../../data/provenance/commander_studio_drive_sources_20261111.json). Alle 16 referenzierten Dateien sind dort mit `drive_url`, Quellmanifest, SHA-256-Angabe des jeweiligen Manifests, erwarteter Zeilenanzahl, Rolle und Importstatus verzeichnet.
- Die SHA-256-Werte im GitHub-Index sind **aus den bestehenden Drive-Manifesten übernommen**; sie wurden für diesen Commit **nicht erneut byteweise berechnet**. Vor lokalen Importen Originaldateien herunterladen und ihre Hashes gegen die Quelle prüfen.
- Ein Zugriff auf den Drive-Link setzt die jeweiligen Drive-Berechtigungen voraus. Das Manifest ersetzt keine Kopie und erweitert keine Freigaben.

## Kohorten (streng getrennt)

| Datensatz | Umfang | Befund/Evidenz | Status |
|---|---:|---|---|
| Chulane V010 | 994 Quelldecks, 87.156 Mainboard-CSV-Zeilen, 98.406 Kartenexemplare | Zahlen aus dem bestehenden Drive-Importmanifest; 994 × 99; ein historischer Oracle-Namensfall offen; 975 eindeutige Deckinhalte laut Audit | separater Chulane-Korpus |
| TAM 91 | 91 × (99+1), 8.488 Mainboard-Zeilen, 9.009 Exemplare, 91 Commander | **CSV-Inhalte in dieser Sitzung erneut gezählt:** 91 Decks mit je 99 Mainboard-Kopien; 0 leere Oracle-IDs; 91/91 strukturelle QA | `ACTIVE` **nur im Drive-Quellvertrag**, nicht als Live-Import auf Owner-Rechner bestätigt |
| TAM/Chandra 381 | 381 × (99+1), 35.728 Mainboard-Zeilen, 37.719 Exemplare, 381 Commander | **CSV-Inhalte erneut gezählt:** 381 Decks mit je 99 Mainboard-Kopien und einem Commander; 0 leere Oracle-IDs | `REVIEW`, **automatic_import=false** |
| TAM EDHREC | 78 Themenansichten, 16.023 CardRec-Zeilen | historischer Quellenvertrag; getrennte Nenner pro Thema | `OBSERVATION`, kein Deckkorpus |
| Chulane EDHREC | 1.379 historische Quellzeilen | bestehendes Drive-Manifest, fehlende Snapshotzeiten bleiben UNKNOWN | `OBSERVATION`, kein Deckkorpus |

**Weitere Gate-Fakten:**
- TAM 91: 70 `SOURCE_BACKED_70` und 21 `USER_PASTED_TEXT_NO_MOXFIELD_URL`; im aktuellen Register **91/91 `original_url` leer**. „Source-backed“ ist eine Archivklassifikation, **kein in dieser Runde unabhängig nachgewiesener Original-Weblink**.
- TAM/Chandra 381: Source-Eligibility klassifiziert **187** als Bracket 2–4 **und** papierlegal, **193** mit Bracket UNKNOWN sowie **1** mit Papierlegalitäts-Review. Die Quellmetadaten zeigen **8** Deckset-Überschneidungen zu TAM 91, darunter **3** der 187; daher **184** potenziell neue qualifizierte Kandidaten. Die Bracket- und Legalitätsklassifikation wurde **nicht gegen einen Live-Dienst erneut bestätigt**.
- Der 381er-Review-Bestand **darf nicht** stillschweigend in die 91er-ACTIVE-Kohorte gelangen.
- Weder strukturelle QA noch Scryfall-Snapshot beweisen einen erfolgreichen XMage-Regeltest, eine Spielsimulation oder eine aktuelle Online-Legalitätsprüfung.
- Öffentliche Quellenansichten, historische Decklisten und persönliche Besitzdaten haben **verschiedene Nenner**. Nie zum globalen `all`-Zähler verschmelzen.

## Reproduzierbarer Agentenablauf

1. Aus dem JSON-Index genau die benötigte Kohorte und Dateien anhand von `dataset`, `role` und `drive_url` auswählen. **Nicht** die gesamte historische Drive-Ordnerstruktur rekursiv importieren.
2. Die Dateien über den authentifizierten Drive-Zugang lokal beziehen, Rohbytes mit den *manifest-deklarierten* SHA-256-Werten abgleichen und anschließend mit CSV-Header, Anzahl, eindeutiger `deck_id`, `oracle_id`, Summen und 99+1 prüfen. Nicht übereinstimmende Dateien als `REVIEW` isolieren, keine stillen Reparaturen.
3. In separater SQLite-Testdatenbank TAM 91 und Chulane 994 importieren; source cohort/commander sind bei jeder Card-Inclusion-Query zwingende Filter. Quoten immer als `included_decks / eligible_decks` ausweisen. Im lokalen Owner-Datenbestand **keine** Änderungen ohne eigene Freigabe.
4. **PR #1183** prüft deckweise überlappende CSV-Teile; bis der Importfix auf dem geprüften Stand verfügbar ist, keine Mehrteildateien mit möglicherweise gleichen IDs unkontrolliert importieren.
5. TAM 381 gesondert auf Bracket-Originalbeleg, Oracle-Legalität, Deckhash, Überlappungen und Snapshot-Zeit prüfen. **Unbekannte Brackets bleiben unbekannt.** Keinen LIVE-Import durchführen.
6. EDHREC-Importadapter (`count`, `denominator`, `source_view`, `captured_at`) getrennt behandeln; pro Thema/Snapshot nie Nenner addieren. Aktuelle historische Zeitprobleme: **PR #1184**.
7. Ergebnis als Zahlen, Fehlertypen, Source IDs/Hashes und Testbelege dokumentieren. Keine subjektiven Tierlisten, Planeswalker-Synergiegewichte, künstlichen Rollenfit-Scores oder ungeprüften Siegraten.

## Schutzgrenzen

Das Repository ist öffentlich. **Keine persönlichen Sammlungs- und Deckexports, Mengen, Notizen, Besitzerverknüpfungen, vollständigen Rohdecks oder Drive-Berechtigungsänderungen hier einchecken.** Diese Grenze folgt dem bisherigen Studio-Owner-Vertrag und `AGENTS.md` §12. Vollständige Daten verbleiben im Drive als zugriffskontrollierte Originale; dieser Index macht sie für berechtigte Agents auffindbar, ohne sie global zu veröffentlichen.

Siehe außerdem [#1176](https://github.com/moeendres-png/commander-playtest-lab/issues/1176), [#1182](https://github.com/moeendres-png/commander-playtest-lab/issues/1182), [PR #1183](https://github.com/moeendres-png/commander-playtest-lab/pull/1183) und [PR #1184](https://github.com/moeendres-png/commander-playtest-lab/pull/1184).

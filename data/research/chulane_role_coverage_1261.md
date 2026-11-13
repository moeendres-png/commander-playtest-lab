# Rollen-Abdeckung Chulane-Pool — #1261 Punkt 2.4, Teilpaket Daten

Messung vom 2026-11-13. Nur Zählungen mit Quelle und Nenner; keine Kartenlisten
(Sammlungsbezug), keine Preise, keine Schätzwerte. Die vollständige Lückenliste
(Name, Oracle-ID, Farbidentität, Typzeile je Karte) bleibt lokal.

## Rahmen

- **Rollen:** die 17 Rollen aus `src/commander_lab/studio/roles.py` (`ROLES`,
  main @ `5b525dab`): ramp, mana_rock, mana_dork, land_ramp, card_draw,
  card_advantage, cantrip, tutor, removal, board_wipe, counterspell, bounce,
  flicker, recursion, protection, graveyard_hate, lifegain.
- **Pool-Prädikat** (an der Studio-DB nachgerechnet): `commander_legal = 1` und
  Farbidentität ⊆ {W, U, G, C} (C = Farblos-Markierung der DB).
  1.655 − 727 (legal, Identität außerhalb WUG) − 1 (nicht commander-legal)
  = **927 Pool-Karten**. Nenner Sammlung: 1.655.
- **Ist-Zustand Store:** In der Live-Studio-DB (Schema 11) sind
  `card_role` und `card_role_claim` **leer (0 Zeilen)** — die Rollen-Claims
  liegen ausschließlich als vorbereitete Datensätze der Daten-Lane vor
  (Stand 2026-11-12), sie sind noch nicht importiert.

## Quellen (drei getrennte Schichten, nie vermischt)

| Schicht | Herkunft | Stand |
|---|---|---|
| S1 Tagger-Bulk | `card_tagger_bulk_1655.csv`: Scryfall-Bulk `oracle_tags`, Subtree-Vereinigung je Kategorie-Label | Bulk-Snapshot 2026-11-12T10:00:40Z |
| S2 Tagger-Search | `card_categories_1655.csv`, layer=tagger: Scryfall-Search-API `function:<tag>` (Block B4) | 2026-11-12 |
| S3 Heuristik | `card_categories_1655.csv`, layer=heuristic: `deckbuild_studio.roles.classify_text`, `oracle-heuristic/2.0.0`, auf den Scryfall-Fakten aller 1.655 Karten (Block B4) | 2026-11-12 |

Die Kategorien der Datensätze stammen aus der 24er-Taxonomie der Daten-Lane;
17 davon sind namensgleich mit den Studio-Rollen und werden hier 1:1 gezählt.
Die übrigen 7 (anthem, card_selection, discard, mill, sacrifice_outlet, stax,
token_production) stehen nicht in `roles.py` und zählen hier nicht als Rolle
(Kontext unten).

## Ist-Abdeckung je Rolle (Karten mit dieser Rolle)

Pool (Nenner 927):

| Rolle | S1 Bulk | S2 Search | S3 Heuristik | Tagger (S1∪S2) | Gesamt |
|---|---:|---:|---:|---:|---:|
| card_advantage | 172 | 171 | 27 | 172 | **172** |
| card_draw | 139 | 139 | 141 | 139 | **149** |
| removal | 125 | 125 | 52 | 125 | **129** |
| ramp | 88 | 88 | 68 | 88 | **110** |
| lifegain | 93 | 93 | 79 | 93 | **93** |
| tutor | 65 | 65 | 24 | 65 | **65** |
| land_ramp | 40 | 40 | 38 | 40 | **61** |
| protection | 39 | 39 | 32 | 39 | **44** |
| bounce | 39 | 39 | 16 | 39 | **39** |
| recursion | 33 | 33 | 18 | 33 | **33** |
| cantrip | 25 | 25 | 19 | 25 | **30** |
| counterspell | 27 | 27 | 25 | 27 | **27** |
| mana_rock | 21 | 21 | 12 | 21 | **24** |
| mana_dork | 20 | 20 | 12 | 20 | **20** |
| board_wipe | 9 | 9 | 6 | 9 | **9** |
| flicker | 5 | 5 | 7 | 5 | **8** |
| graveyard_hate | 7 | 7 | 5 | 7 | **7** |

Karten mit mindestens einer Rolle:

| Schicht | Pool (von 927) | Sammlung (von 1.655) |
|---|---:|---:|
| S1 Tagger-Bulk | 544 (58,7 %) | 960 (58,0 %) |
| S2 Tagger-Search | 544 (58,7 %) | 960 (58,0 %) |
| S3 Heuristik | 418 (45,1 %) | 735 (44,4 %) |
| Tagger gesamt (S1∪S2) | 544 (58,7 %) | 960 (58,0 %) |
| **Alle Schichten** | **558 (60,2 %)** | **983 (59,4 %)** |

Einordnung der Issue-Ausgangszahl: Der Tagger-Bulk führt 1.033 Sammlungs-Karten
mit Claims — davon haben 960 mindestens eine der 17 Studio-Rollen, 73 nur
Kategorien außerhalb der 17. Rollen je Pool-Karte: 0×369, 1×263, 2×171, 3×94,
4×18, 5×11, 6×1 (295 Pool-Karten haben ≥ 2 Rollen).

## Lücke

**369 von 927 Pool-Karten (39,8 %) haben keine der 17 Rollen.** Zusammensetzung:

| Grund | Karten |
|---|---:|
| Taggings im Bulk vorhanden, aber außerhalb der 17 Rollen-Subtrees (häufigste Labels: „activated ability" 92, „triggered ability" 78, „evasion" 63, „alliteration" 42, „french vanilla" 40) | 322 |
| Länder laut Typzeile (davon 3 Basisländer) | 33 |
| Keinerlei Tagging im Bulk und Heuristik leer (überwiegend Vanilla-Kreaturen) | 14 |

85 der 369 haben immerhin einen Claim in der weiteren 24er-Taxonomie
(v. a. token_production, sacrifice_outlet, card_selection) — nur eben keine
Studio-Rolle.

## Schließungs-Prüfung (nur erlaubte Quellen)

Beide Wege wurden vollständig durchgerechnet, nicht geschätzt:

- **(a) Quell-Tags:** Erneute Subtree-Extraktion aus dem lokal vorliegenden
  Voll-Bulk (`oracle_tags.jsonl`, Snapshot 2026-11-12) mit den Studio-Labels
  aus `roles.py` (inkl. `SEARCH_ALIASES`: board_wipe→„sweeper",
  graveyard_hate→„hate-graveyard"; alle 17 Labels im Bulk-Vokabular gefunden).
  **Differenz zu S1: leer für alle 17 Rollen → 0 neue Claims.**
- **(b) Regelabgeleitete Merkmale:** Erneuter Lauf von `classify_text`
  (`oracle-heuristic/2.0.0`, exakt die B4-Eingaben: Oracle-Text, Typzeile,
  Manawert aus `scryfall_card`) auf allen 1.655 Karten. **Differenz zu S3:
  leer über alle 24 Kategorien → exakte Replikation, 0 neue Claims.**
  Im CPL-Repo selbst existiert keine Heuristik, die Studio-Rollen aus
  Kartenfakten ableitet (`studio/roles.py` kennt mit `ORACLE_TEXT_REVIEW` nur
  eine Herkunftsklasse für solche Dateien, keinen Erzeuger); das einzige
  bestehende, auf die CPL-Daten bereits angewandte Regelwerk ist das oben
  geprüfte.

**Ergebnis: Endstand = Ist-Stand.** Die Lücke ist aus den erlaubten Quellen
nicht weiter schließbar — sie ist eine Eigenschaft der Quellen (der Tagger
klassifiziert Vanilla- und Utility-Karten funktional nicht; die Taxonomie
kennt keine Länder-Rolle), kein Extraktions- oder Verarbeitungsdefizit.
Bewusst nicht getan: ein Live-Neuabruf des Taggers (Snapshot-Disziplin;
der sanktionierte Refresh-Pfad ist `fetch_role_file` in `roles.py`,
`otag:` je Identität) und jede Rollen-Vergabe ohne Quell-Tag oder Regel.

## Urteil zur Einstellungs-Reife („Rang in der Funktion")

Ein Rang innerhalb einer Rolle ist ein Perzentil über der Peer-Gruppe;
seine Auflösung beträgt 100/n Prozentpunkte bei n Peer-Karten im Pool.
Als Mindestgrößen werden angesetzt: **n ≥ 30 tragfähig** (≤ 3,3 Punkte je
Rangschritt), **10 ≤ n < 30 grob brauchbar**, **n < 10 kein sinnvoller Rang**
(> 10 Punkte je Schritt).

Einteilung streng nach der Gesamt-Spalte (Peer-Größe im Pool):

- **Tragfähig (≥ 30): 11 Rollen** — card_advantage (172), card_draw (149),
  removal (129), ramp (110), lifegain (93), tutor (65), land_ramp (61),
  protection (44), bounce (39), recursion (33), cantrip (30).
- **Grob brauchbar (10–29): 3 Rollen** — counterspell (27), mana_rock (24),
  mana_dork (20).
- **Nicht sinnvoll (< 10): 3 Rollen** — board_wipe (9), flicker (8),
  graveyard_hate (7).

**Fazit:** Die Einstellung „Rang in der Funktion" ist für 558 der 927
Pool-Karten (60,2 %) definiert und für 11 der 17 Rollen tragfähig.
Die im Issue genannte Voraussetzung „vollständige Rollen für den
Chulane-Pool" ist aus den erlaubten Quellen **nicht erreichbar**
(369 Karten ohne Rolle, 3 Rollen unter der Mindest-Peer-Größe). Die
Einstellung braucht daher einen definierten Fallback für Karten ohne
Rolle bzw. ohne tragfähige Peer-Gruppe (Pool-Rang oder „keine Funktion
bekannt" — als unbekannt ausgewiesen, nicht als 0). Ob stattdessen die
weitere 24er-Taxonomie der Daten-Lane als Funktionsrahmen dienen soll
(643/927 = 69,4 % Abdeckung), ist ein Taxonomie-Entscheid außerhalb
dieses Datenpakets.

## Anschluss-Hinweis (nicht Teil dieses Pakets)

Für die Umsetzung der Einstellung müssen die Claims in den Store
(`card_role_claim`/`card_role`, heute leer). Der Importweg existiert in
`roles.py` (`import_roles`, Dateiformat `studio-roles-2`): S2 als
`SCRYFALL_TAGGER_ORIGINAL` (Scope WUG), S1 als `CROSSWALK_NORMALIZED`
mit Mapping-Regel, S3 als `ORACLE_TEXT_REVIEW`. Die Umwandlung der
vorliegenden CSVs in Rollen-Dateien ist mechanisch und ohne neue
inhaltliche Entscheidung möglich.

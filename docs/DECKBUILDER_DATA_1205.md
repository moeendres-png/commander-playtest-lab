# Deckbuilder-Daten: Chulane-Ausbau, Deck-Universen und Tiers (#1205)

Stand: 2026-11-12. Alle Zahlen in diesem Dokument sind Zählungen über den unten
benannten Datenbeständen oder publizierte Quellwerte mit Provenienz. Es enthält keine
Bewertungen. Owner-Regeln: nur objektive Daten; Chulane zuerst; die Owner-Deckliste
wird an keine externe API gesendet (alle Abrufe waren karten-/commander-basierte GETs
auf öffentliche Daten, Auswertung lokal); Kohorten (EDHREC-Brackets) werden nie
vermischt.

## Was gebaut wurde

- `studio/decklist_import.py` — Import vollständiger öffentlicher Decklisten aus
  normalisierten Pro-Deck-JSONs (Formate `edhrec` und `archidekt`) in `corpus_deck` /
  `corpus_deck_card` / `corpus_cohort`. Sektionen folgen den Quelldaten (Commander,
  Main, Companion, Sideboard, Maybeboard); geteilte Zeilen einer Sektion werden wie
  beim Korpus-Part-Importer summiert. Exakte Duplikate (gleiche Kartenmultimenge) werden
  per Fingerprint in `duplicate_of` markiert und nie doppelt gezählt; Legalität der
  Listen ist `not_audited`.
- `studio/universe.py` — Deck-Universen als gespeicherte Profile (Tabelle
  `universe_profile`, Schema v9). Eine Spec wählt Decks nach Plattform, Kohorten
  (`source:*`, `bracket:*`, `variant:*`, `commander:*`), Datumsbereich und
  Mindest-Hauptdeckgröße. Inclusion ist eine reine Zählung über dem Universum
  (Treffer/Nenner/Anteil, Nenner 0 → Anteil `None`). Dazu Co-Occurrence-Zählungen und
  eine Snapshot-ID (Spec + gewählte Deck-IDs), mit der jede Zahl ihr Universum zitiert.
- `studio/tiers.py` — Tiers als reine Funktion über der Inclusion eines Universums mit
  Owner-Parametern (`min_universe`, Anteil-Schnitte, Fallback). Unterhalb der
  Mindestgröße oder ohne Nenner ist der Tier `U` (ungenügende Daten) mit Grund-Code,
  nie ein geratener Tier. Jede Tier-Zeile trägt Treffer, Nenner, Anteil, Snapshot-ID
  und Parametersatz (Aufschlüsselung). Die Default-Werte im Code sind Platzhalter,
  keine Befunde; Salt-Score und Preis sind keine Tier-Signale.
- CLI: `import-decklists`, `save-profile`, `profiles`, `universe-inclusion`, `tiers`
  (`python -m commander_lab.studio …`).

## Datenbasis (lokal beschafft, Stand 2026-11-12)

Rohdaten und Fetch-Werkzeuge liegen im lokalen Datenbestand außerhalb des Repos
(Provenienz-Manifeste `MANIFEST.md` / `decklists_manifest.json` /
`ARCHIDEKT_MANIFEST.md`); im Repo liegen Code, diese Doku und die kuratierte
Aggregat-Tabelle (unten). Gezählt und unabhängig nachgerechnet:

| Bestand | Umfang | Ergebnis |
|---|---|---|
| EDHREC-Decklisten Chulane Bracket 3 (`upgraded`) | 755 Listen (Index-Zeilen) | 755 abgerufen, 746× Summe 100, 9× Summe 101 (Companion), 65.644 Kartenzeilen |
| EDHREC-Decklisten Chulane Bracket 4 (`optimized`) | 695 Listen | 695 abgerufen, 694× Summe 100, 1× Summe 101, 62.696 Kartenzeilen |
| Archidekt-Decklisten Chulane Bracket 3 | 267 Decks | 267 abgerufen, 0 Fehler; Hauptdeck-Summe 100 bei 221 |
| Archidekt-Decklisten Chulane Bracket 4 | 261 Decks | 261 abgerufen, 0 Fehler; Hauptdeck-Summe 100 bei 225 |
| EDHREC-Kartenseiten, Chulane-Pool (801 Karten) | 801 | 801/801 AVAILABLE |
| Commander Spellbook, Pool-Karten | 801 | 801/801 gezählt; 206 Karten mit ≥ 1 Variante; 9.992 distinkte Varianten poolweit |
| Playgroup-Profil Chulane (ID 2143) | 1 Profil | Felder inventarisiert (u. a. `stats.games_won/lost`, `win_rate`, `decks_count`, `cached_elo`, `global_rank`, `top_decks`) |

Import in eine Studio-DB (End-to-End nachgerechnet): 1.978 Decks, 177.218
Kartenzeilen. Exakte Duplikate: innerhalb von EDHREC 0; von den Archidekt-Listen waren
54 (Bracket 3) und 62 (Bracket 4) exakte Duplikate einer vorher importierten Liste
(Importreihenfolge EDHREC → Archidekt) und werden in Universen nicht mitgezählt.
Universum-Nenner nach Duplikat-Ausschluss: EDHREC B3 = 755, EDHREC B4 = 695,
Archidekt B3 = 213, Archidekt B4 = 199.

## Kuratierte Aggregat-Tabelle

`data/research/chulane_decklist_inclusion_20261112.csv` — 15.038 Zeilen: je Karte und
Universum (Quelle × Bracket) `decks_with_card`, `universe_decks`, `share` und die
Snapshot-ID des Universums. Erzeugt mit `universe.inclusion` über den oben benannten
Beständen; Stichproben gegen die Rohlisten nachgerechnet (z. B. Sol Ring: EDHREC B3
544/755, EDHREC B4 573/695; Whitemane Lion: 328/755 bzw. 441/695).

## Weitere gezählte Fakten

- EDHREC zählt für Chulane selbst 9.824 Decks in der Kartenstatistik; die
  Bracket-Klassifikation (`bracket_counts`) deckt 2.286 davon ab (45/558/755/695/233).
  Bracket-getrennte Commander-Unterseiten existieren nicht (5 URL-Muster getestet,
  keines lieferte 200) → Bracket-Auswertung läuft über die Decklisten-Universen.
- Playgroup: ein öffentlicher Card-Atlas-Endpunkt je Karte wurde nicht gefunden
  (3 Muster getestet, alle 404) → Status UNKNOWN (die CPL-interne Atlas-Integration
  aus #1202 bleibt davon unberührt).
- Spellbook × Baseline: Von den 83 eindeutigen Namen des Repo-Baseline-Snapshots
  (`data/decks/deckbau/chulane_current.json`) haben 41 mindestens eine
  Spellbook-Variante, Summe der Varianten-Zugehörigkeiten 5.853. Zwei Namen stehen
  nicht in der Pool-Zählung (`Brazen Borrower` — DFC-Namensform; `Studious First-Year`).
- Co-Occurrence-Beispiel (Universum EDHREC B4): Whitemane Lion steht in 441 Decks;
  häufigstes Paar Shrieking Drake in 406 dieser Decks (Zählung, keine Deutung).

## Offene Punkte (faktisch)

- P3: Messdefinitionen für die als `NOT_MEASURED` geführten Telemetrie-Größen
  (Mana-Effizienz, Hand-Verweildauer) sind noch nicht festgelegt; ohne Definition
  bleibt der Status `NOT_MEASURED`.
- P4: Scryfall Tagger — ein offizieller Bulk-Export existiert nicht; ein zulässiger
  Importweg ist ungeklärt (Quelle bleibt REVIEW). cEDH-Meta-Abdeckung für Chulane
  wurde nicht gezählt (Quelle REVIEW).
- Einstellungs-Oberflächen: Profile wirken in dieser Stufe über CLI und die
  Bibliotheks-API (`universe.py`); die Anzeige/Auswahl in den Web-Ansichten
  (Design-Pakete U1–U3 in `docs/DECKBUILDER_TIERLIST_DESIGN.md`) ist ein Folgeschritt.
- EDHREC liefert bei schnellen Abrufen eine Soft-429-Seite mit HTTP 200; die
  Fetch-Werkzeuge erkennen sie und takten mit Cooldowns (dokumentiert im Manifest).

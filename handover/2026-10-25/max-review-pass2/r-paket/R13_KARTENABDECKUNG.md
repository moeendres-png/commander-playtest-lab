# R-13 — Kartenabdeckung: Priorisierung der 31 #979-Karten (Analyse-only)

Stand: 2026-10-25. Grundlage: #979 (offen, Claudes Lane — Fork-Push,
Repin, PB-03 und Seal brauchen Owner-Go), 195 Precon-Dateien
(`data/decks/precons/*.json`, Häufigkeiten), Fork-Tree `wt-mage-v13`
(Pin v13 `90f5c4d3f8`), Scryfall-Oracle-Texte (heute, per curl, exakte
Namen). **Kein Fork-Code in diesem Dokument** — nur die Analyse, die
Claudes Lane als Eingabe bekommt. Keine Sammlung wird gelesen oder
zitiert; alle Namen stammen aus dem #979-Body bzw. den Precon-Dateien.

## 1. Stand an Pin v13: 10 von 31 Klassen vorhanden (CODE_DERIVED, statisch)

Prüfmethode: exakte Karten-Klassen-Datei in
`wt-mage-v13/Mage.Sets/src/mage/cards/` (Name normalisiert, z. B.
`WinterCynicalOpportunist.java`). Eine Set-Datei, die den Namen nennt
(z. B. `DoctorWho.java`), zählt NICHT — sie beweist keine Klasse.
Ergebnis:

**Vorhanden (10):** Winter, Cynical Opportunist · Zinnia, Valley's
Voice · Aminatou, Veil Piercer · Dack Fayden, Helping Hand · Teferi's
Reproach · Jhoira, Weatherlight Corsair · Venser, Fervent Forger ·
Tamiyo, Upriser Crowned · The Ur-Sphinx · Jace, Multiverse Architect.

**Fehlend (21):** Susan Foreman · Missy · Cyber Conversion · Doomsday
Confluence · Death in Heaven · Rassilon, the War President · The
Cyber-Controller · Cybership · Don't Blink · The Foretold Soldier ·
River Song's Diary · Psychic Paper · The Pandorica · The War Doctor ·
The Moment · Feather, Radiant Arbiter · Immortal Obligation · Eye of
Duskmantle · Desert Warfare · Exchange of Words · Space Beleren.

**Kreuzcheck:** Die 10 vorhandenen Namen sind exakt die 4 Decks aus
dem Max-Review-v13-Vorbefund (death_toll/Winter, family_matters/Zinnia,
miracle_worker/Aminatou, multiverse_reforged/alle 7) — zwei
unabhängige statische Signale, gleiche Aussage. **Caveat:**
Klassen-Datei ≠ Import-Erfolg (Registrierung, Set-Zuordnung, Build).
Der Laufzeit-Recount (`measure_precon_imports --enumerate-missing` an
v13) bleibt Schritt 1 für Claudes Lane; bis dahin ist „4 Decks
importieren an v13" CODE_DERIVED, nicht runtime-verifiziert.

## 2. Die 31 Karten in 13 Decks (DIRECTLY_VERIFIED, Volltext-Zählung)

Jede Karte steht in genau 1 Deck-Datei, außer Psychic Paper (2 Decks)
und Desert Warfare (2 Deck-Dateien: Tricky Terrain + Collector's
Edition). Commander-Karten (Winter, Zinnia, Aminatou, Jace) sind je 2×
in 1 Deck genannt (Commander- + Listeneintrag) — ohne sie ist das Deck
unbenutzbar.

| Deck | Fehlende Karten an v13 | Schon an v13 |
|---|---|---|
| 2024_death_toll | 0 | Winter |
| 2024_family_matters | 0 | Zinnia |
| 2024_miracle_worker | 0 | Aminatou |
| 2026_multiverse_reforged | 0 | alle 7 |
| 2024_revenant_recon | 1 (Eye of Duskmantle) | — |
| 2024_tricky_terrain | 1 (Desert Warfare) | — |
| 2024_tricky_terrain_collector_s_edition | 1 (Desert Warfare) | — |
| 2023_blast_from_the_past | 1 (Susan Foreman) | — |
| 2024_blame_game | 2 (Feather, Immortal Obligation) | — |
| 2026_odds_and_ends | 2 (Exchange of Words, Space Beleren) | — |
| 2023_paradox_power | 3 (Foretold Soldier, River Song's Diary, Psychic Paper) | — |
| 2023_timey_wimey | 4 (Psychic Paper, Pandorica, War Doctor, Moment) | — |
| 2023_masters_of_evil | 8 (s. Abschnitt 4) | — |

## 3. Freischalt-Reihenfolge: Einheit ist das Deck, nicht die Karte

Eine Nicht-Commander-Karte in einem 8-Karten-Deck schaltet allein
nichts frei. Reihenfolge nach fehlenden Karten je Deck, dann nach
Mechanik-Schwierigkeit (Abschnitt 4):

1. **Ein-Karten-Decks, moderate Mechanik:** revenant_recon (Eye of
   Duskmantle — Surveil-Graveyard-Play) und tricky_terrain + CE
   (Desert Warfare — Desert-Rekursion + Token; 1 Karte, 2
   Deck-Dateien = höchster Karten-Hebel).
2. **Ein-Karten-Deck, Spezial-Mechanik:** blast_from_the_past (Susan
   Foreman — Planar-Deck/Planeswalk; Wert hoch, Aufwand hoch, s. u.).
3. **Zwei-Karten-Decks:** blame_game (Feather — Multi-Target-Copy mit
   Zahlung; Immortal Obligation — Goad via Duty-Counter).
4. **Drei-Karten-Deck:** paradox_power (Foretold Soldier — Foretell;
   River Song's Diary — Imprint + Zufalls-Cast; Psychic Paper —
   Name/Typ-Wahl; Psychic Paper dient zugleich timey_wimey).
5. **Vier-Karten-Deck:** timey_wimey (Phasing-Cluster: Pandorica,
   War Doctor, The Moment + Psychic Paper).
6. **Acht-Karten-Deck:** masters_of_evil — aber als Mechanik-Block,
   nicht als 8 Einzelkarten (Abschnitt 4).

**Karten-Hebel (Decks je Karte):** Desert Warfare 2 Deck-Dateien,
Psychic Paper 2 Decks, alle übrigen je 1 Deck. Der Cyberman-Mechanik-
Block (Abschnitt 4) bedient 5 Karten auf einmal.

## 4. Komplexitäts-Flags aus den Oracle-Texten (Scryfall, heute)

Alle 21 fehlenden Karten lösen auf Scryfall exakt auf — die
Kartene-Identität ist damit bestätigt (keine Reskin-Ambiguität wie
2026-10-22 bei RogShai; Namen = Precon-Datei-Namen = Scryfall-Namen).

- **Face-down-Cyberman-Cluster (5 Karten, 1 gemeinsamer Mechanismus):
  Missy, Cyber Conversion, Death in Heaven, The Cyber-Controller,
  Cybership** — alle erzeugen „face down, 2/2 Cyberman artifact
  creature". Der Mechanismus (verdeckte 2/2-Cyberman unter eigener
  Kontrolle) muss einmal gebaut werden; dann sind 5 der 8
  masters_of_evil-Karten mechanisch abgedeckt. Masters_of_evil ist
  damit kein 8-Karten-Projekt, sondern 1 Mechanik + 3 Restkarten
  (Doomsday Confluence — modales X; Rassilon — Conspire aus Exil;
  Don't Blink — Exil-Eintritts-Replacement).
- **Villainous Choice (Missy):** Wahl-Mechanik („jeder Gegner wählt:
  Schaden oder Draw + Chaos") — #979s Vote-Flag trifft hier in
  abgewandelter Form; Negativkontrolle nötig (Wahl muss je Gegner
  separat greifen).
- **Goad (Immortal Obligation):** Duty-Counter + Goad + Angriffs-/
  Block-Restriktionen — #979s Goad-Flag.
- **Phasing-Cluster (3 Karten):** The Pandorica, The War Doctor,
  The Moment — Phasing als Mechanismus + Zeit-Counter als Ressource.
- **Schwerste Einzelkarten:** Exchange of Words (Text-Box-Tausch
  zweier Kreaturen — Continuous Effect auf Oracle-Text-Ebene),
  Space Beleren (Sektoren-Mechanik: Alpha/Beta/Gamma, eigene
  Battlefield-Partition — kein Standard-Keyword).
- **Spezial-Decks:** Susan Foreman braucht Planar-Deck-Unterstützung
  (Planechase) — falls XMage das nicht hat, ist blast_from_the_past
  ein eigenes Projekt, kein Ein-Karten-Fix.

**Stubs sind kein akzeptabler Endzustand** (#979): Jede Karte braucht
ihre Mechanik + Negativkontrollen (z. B. Cyberman-Cluster: verdeckte
Karte darf nicht als Original spielbar sein; Goad: Angriffs-Zwang
gegen andere Spieler; Exchange: Text-Tausch endet mit Verlassen).

## 5. Empfohlene Abfolge für Claudes #979-Lane (nach Owner-Go)

1. Laufzeit-Recount an v13 (bestätigt Abschnitt 1 oder korrigiert ihn).
2. Tier-1-Karten (Eye of Duskmantle, Desert Warfare) — 3 Deck-Dateien
   mit 2 Karten.
3. Cyberman-Mechanik-Block — 5 Karten, 1 Mechanismus, schaltet
   masters_of_evil fast vollständig frei (Rest: 3 Karten).
4. Psychic Paper — schaltet paradox_power + timey_wimey je einen
   Schritt weiter (beide brauchen danach nur noch ihre
   Deck-eigenen Karten).
5. Rest nach Deck-Reihenfolge (Abschnitt 3); Space Beleren und
   Exchange of Words zuletzt (schwerste Mechanik, je 1 Deck);
   Susan Foreman separat bewerten (Planechase-Abhängigkeit).

## 6. Evidenzklassen

- Deck-Zuordnung, Häufigkeiten: DIRECTLY_VERIFIED (195 Precon-Dateien).
- v13-Klassen-Bestand: CODE_DERIVED (statische Datei-Prüfung im Fork;
  Laufzeit-Import: UNKNOWN bis Recount).
- Oracle-Texte, Mechanik-Flags: DIRECTLY_VERIFIED (Scryfall, exakte
  Namen, 2026-10-25).
- Freischalt-Reihenfolge, Abfolge-Empfehlung: Design (Analyse, keine
  Messung).
- Cast-/Verrottungsdaten für die 31 Karten: praktisch nicht existent
  (Karten importieren nicht → nie gespielt) — Priorisierung muss auf
  Häufigkeit + Commander-Status + Mechanik-Cluster basieren, nicht auf
  Cast-Daten. Das ist selbst ein Befund.

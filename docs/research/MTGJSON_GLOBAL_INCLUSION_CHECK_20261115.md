# MTGJSON-Gegenprobe für `global_inclusion` (Issue #1367)

- **Prüfskript:** `scripts/mtgjson_global_inclusion_check.py`
- **Quellstand:** main 585c9e2f2, Branch muse/1367-mtgjson-check
- **Status-Vokabular:** `OK` / `ABWEICHUNG` / `UNKNOWN`
- **Gegenstand:** Das gespeicherte Signal `edhrec_global_inclusion` wird gegen den kostenlosen MTGJSON-Bulk gegengeprüft. MTGJSON wird kein Signal und ersetzt keinen Wert; das Ergebnis ist ein reiner Datenqualitäts-Befund.

## 1. Provenienz

- **MTGJSON:** `AtomicCards.json.bz2` von https://mtgjson.com/api/v5/ (Bulk-Metadaten: Datum 2026-11-14, Version 5.3.0+20261114), 32960542 Bytes, SHA-256 `16786d88158d507bcd6e1bc9ec740c8777d16acbad2bd3323ad2464485734317`, abgerufen 2026-11-15T02:20:01Z (UTC) / 2026-11-15 03:20:01 CET (Europe/Berlin). 36446 Karten-Einträge unter 35495 Oracle-Namen, 33625 Einträge mit `edhrecRank`.
- **Scryfall (nur für den Store-Bau):** `oracle-cards.jsonl.gz`, 25488485 Bytes, SHA-256 `1fa0d3e98e6b43c6de68c05cbc440a95a64b0ea7b36373b167c8793a97f85c00` (öffentliche Oracle-Karten-Datei, wie vom Repo-Importer verlangt).
- **Unser Signal:** Repo-Datei `data/research/deckbuilder_1655/card_global_signals.csv`, per `import-all --from-repo` in einen frischen Studio-Store importiert. Ein Aufnahme-Stichtag ist in der Datei nicht verzeichnet (UNKNOWN); ihr Nenner (`potential_decks`, je Karte die Decks ihrer Farbidentität) liegt zwischen 106085 und 10542169.

## 2. Store und Äquivalenz zur Quelldatei

- Pool des Commanders: 927 Karten; davon gerankt (Index vorhanden): 922.
- Gespeicherte Zeilen `edhrec_global_inclusion`: 1655; davon Wert NULL: 1 (Nenner nicht positiv in der Quelle → unbekannt, nie 0).
- Äquivalenz Store ↔ CSV: 1654 Zeilen exakt gleich (Zähler, Nenner, Wert), 1 Zeile(n) über die NULL-Regel gleich, 0 Abweichungen.
- Die Werte der Karten unten sind die Beobachtungen, die der Index selbst verwendet (`strength_view.compute`, Standard-Einstellungen): Signalnamen werden dort über die Namensansprüche der Karten zugeordnet (Oracle-Name, Engine-Name, Vorderseite eines doppelseitigen Namens, sofern keine andere Karte diesen Namen trägt). Für dieses Signal mehrdeutig und deshalb zurückgehalten: 0 Namen.
- Die Quelldatei führt doppelseitige Karten unter ihrem Vorderseiten-Namen; 12 gerankte Karten erhalten ihren Wert über diese Zuordnung (Brazen Borrower // Petty Theft, Brigid, Clachan's Heart // Brigid, Doun's Mind, Dirgur Focusmage // Braingeyser, Emergency Phytomedic // Seed Suture, Faithful Squire // Kaiso, Memory of Loyalty, Grizzled Outcasts // Krallenhorde Wantons, Prudent Fateseer // Peer Review, Soul Seizer // Ghastly Haunting, Spellbook Seeker // Careful Study, Studious First-Year // Rampant Growth, Tam, Observant Sequencer // Deep Sight, Thraben Sentry // Thraben Militia).

## 3. Join der gerankten Karten gegen MTGJSON

- Gemeinsame Menge: **922** von 922 gerankten Karten (Join-Arten: exakt 922).
- Gerankt, aber gespeicherter Wert NULL: 0; ohne Signalzeile: 0.
- In MTGJSON vorhanden, aber ohne `edhrecRank`: 0; in MTGJSON gar nicht gefunden: 0.
- MTGJSON-interne Rang-Konflikte (Einträge eines Namens mit verschiedenen Rängen, Minimum verwendet): 0.

## 4. Rangvergleich

- **Konvention:** `edhrecRank` 1 = meistgespielte Karte (kleiner Rang = populärer); unsere Inclusion ist ein Anteil (größer = populärer). Erwartet wird daher ein stark negatives Spearman zwischen Rang und Inclusion bzw. ein stark positives zwischen den Popularitäts-Perzentilen beider Seiten (Perzentil über die gemeinsame Menge, 0 = unpopulärste, 1 = populärste Karte der Menge).
- **Spearman-Rho (edhrecRank, Inclusion)** über n = 922: **-0.9659**.
- **Spearman-Rho der Popularitäts-Perzentile:** **0.9659**.
- Perzentil-Abstand |Δ|: Median 0.0293, 788 von 922 Karten innerhalb von 0.10, **12 Karten über der Schwelle 0.25** (12 mit höherer eigener Perzentile, 0 mit niedrigerer).
- **Salt-Gegenprobe** (Salt-Spalte derselben Quelldatei gegen `edhrecSaltiness`, n = 922): Spearman 0.9997, größte absolute Differenz 0.0050 (MTGJSON rundet auf zwei Nachkommastellen).

## 5. Abweicher (|Δ Perzentil| > 0.25)

| Karte | Farbidentität | unsere Inclusion (Zähler/Nenner) | unser Perzentil | MTGJSON-Rang | MTGJSON-Perzentil | Δ |
|---|---|---|---|---|---|---|
| Vigorbloom Charm | GW | 0.0338 (11768/348372) | 0.8795 | 10972 | 0.5027 | +0.3768 |
| Transformative Commons | UG | 0.0137 (4486/326554) | 0.7546 | 16591 | 0.3800 | +0.3746 |
| Emergency Phytomedic // Seed Suture | GW | 0.0062 (2155/348372) | 0.6450 | 20633 | 0.2736 | +0.3713 |
| Tam's Resistance | GU | 0.0030 (1080/365009) | 0.5201 | 24108 | 0.1629 | +0.3572 |
| Gardenize | G | 0.0161 (10968/682008) | 0.7774 | 11441 | 0.4908 | +0.2866 |
| Loot, the Nexus | G | 0.0087 (5991/691864) | 0.6884 | 14971 | 0.4148 | +0.2736 |
| Prudent Fateseer // Peer Review | UW | 0.0032 (2153/672771) | 0.5407 | 20624 | 0.2747 | +0.2660 |
| Flickering Hound | W | 0.0322 (24603/764431) | 0.8740 | 6802 | 0.6102 | +0.2638 |
| Plan for All Outcomes | U | 0.0111 (8484/761645) | 0.7199 | 12750 | 0.4571 | +0.2628 |
| Teyo, Lightshield Expert | W | 0.0062 (4742/764431) | 0.6460 | 16362 | 0.3833 | +0.2628 |
| Saheeli, Consul of Oversight | W | 0.0042 (3127/744535) | 0.5852 | 18513 | 0.3279 | +0.2573 |
| Hexhaven Invigorator | G | 0.0271 (20952/774006) | 0.8469 | 7562 | 0.5917 | +0.2552 |

## 6. Einordnung

- **Gesamtbefund: OK** — Äquivalenz Store ↔ Quelldatei ohne Abweichung, Spearman-Rho der Popularitäts-Perzentile 0.9659 über n = 922, und kein Abweicher in der Richtung, die die Nenner-Definition nicht erklärt (Details oben). Es gibt keinen Hinweis auf einen Datenfehler im Signal; MTGJSON bleibt eine Gegenprobe und wird kein Signal.
- Alle 12 Abweicher liegen in derselben Richtung (unsere Perzentile höher als die des MTGJSON-Rangs); kein einziger in der Gegenrichtung.
- Die beiden Maße haben verschiedene Universen: Unsere Inclusion teilt durch die Decks, die die Karte legal spielen können (`potential_decks` je Farbidentität); der MTGJSON-Rang ordnet nach der absoluten Deckzahl über alle Decks. Farblich eingeschränkte Karten stehen bei uns deshalb systematisch höher, als es ihr globaler Rang sagt — positive Δ bei Abweichern ist diese Definitionsdifferenz, kein Datenfehler. Abweicher mit negativem Δ wären durch den Nenner-Effekt nicht erklärt.
- Stichtage: MTGJSON-Bulk vom 2026-11-14; der Stichtag unseres EDHREC-Exports ist in der Quelldatei nicht verzeichnet. Rangverschiebungen einzelner Karten zwischen zwei Stichtagen sind möglich und von einem Datenfehler in dieser Gegenprobe nicht zu unterscheiden.
- Ein Guard-Test (`tests/unit/test_studio_mtgjson_guard.py`) belegt, dass kein Produktions-Codepfad unter `src/commander_lab` MTGJSON nutzt; die Gegenprobe bleibt ein einmaliges Skript in `scripts/`.

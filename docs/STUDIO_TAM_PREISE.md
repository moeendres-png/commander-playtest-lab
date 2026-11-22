# TAM-Zukauf: Preise im Studio (Anleitung für den Owner)

Stand 2026-11-22, #1637 (WP-10b). Regeln: Register `OWNER_DECISIONS_STUDIO_20261118.md`, Eintrag
„Preise für TAM“ mit der Owner-Ausnahme vom 2026-11-22. Preise gibt es nur für den Commander TAM,
nur in der Zukauf-Liste und nur für Karten, die nicht in der Sammlung sind. Alle Preisdaten liegen
nur im lokalen Studio-Datenordner auf deinem PC und kommen nie ins Repository.

## Was das Studio zeigt (Vorrang von oben nach unten)

| Anzeige | Quelle | Was sie misst |
| --- | --- | --- |
| „Cardmarket DE/EX: 12,50 € (eingetragen am 22.11.2026)“ | von dir auf Cardmarket abgelesen und eingetragen | genau das, was du mit deinen Filtern gesehen hast; älter als 14 Tage: „veraltet“, zählt nicht |
| „Cardmarket ab 0,45 € (Trend 0,94 €) · ohne Filter Land/Sprache/Zustand · Stand …“ | Cardmarket-Preisführer (offizieller Download) | niedrigstes Angebot („low“, Foil oder Nicht-Foil) und Trend über alle spielbaren Drucke, **ohne** Filter Land, Sprache und Zustand; Druck und Finish des niedrigsten Werts stehen dabei; älter als 14 Tage: „veraltet“, zählt nicht |
| „Näherung aus Scryfall (…), Stand …“ | Scryfall-Bulk-Datei | Cardmarket-Trend (Foil oder Nicht-Foil); nur wenn der Preisführer die Karte nicht hat |

Summe, Sortierung und Budgetfilter der Zukauf-Liste nehmen je Karte den obersten vorhandenen Wert;
die Zeile über der Tabelle sagt, wie viele Karten welchen Wert nutzen („n von N Karten mit
eingetragenem Preis“). Ein fehlender Preis heißt „unbekannt“, nie 0 €.

Der Preisführer kennt weder das Verkäuferland noch die Sprache noch den Zustand. Wie viel ein
deutsches Angebot (Englisch/Deutsch) in Excellent mehr kostet, lässt sich ohne Angebotsdaten nicht sagen; dafür gibt es den Link und das
Eintragen von Hand.

## Einmal einrichten und aktualisieren (im Terminal, im Studio-Ordner)

1. Scryfall-Bulk-Datei „Default Cards“ herunterladen (scryfall.com/docs/api/bulk-data) und
   importieren: `python -m commander_lab.studio import-tam-prices <Datei>`. Das liefert die
   Näherung und die Zuordnung der Drucke zu Cardmarket (`cardmarket_id`).
2. Cardmarket-Preisführer holen und importieren:
   `python -m commander_lab.studio import-cardmarket-priceguide`. Der Befehl lädt die beiden
   veröffentlichten Dateien (Preisführer und Produktliste) je einmal in den Datenordner
   (`cardmarket/`); eine Kopie jünger als 24 Stunden wird wiederverwendet. Antwortet Cardmarket
   mit etwas anderem als HTTP 200 (etwa 403 oder 429), bricht er sofort ab, meldet das und fragt
   24 Stunden lang nicht neu an; dann die Dateien im Browser laden und
   `python -m commander_lab.studio import-cardmarket-priceguide --file <price_guide_1.json> --products <products_singles_1.json>`
   nutzen (ohne `--products` steht in der Liste „Namen nicht geprüft“). Download-Ordner und
   Dateien dürfen nicht im Repository liegen.
3. Im Studio: TAM-Deck öffnen, Zukauf-Modus an, „Zukauf-Liste mit Richtwerten (TAM)“.

## Genauen Preis von Hand eintragen

- Über der Tabelle stehen die Cardmarket-Filter, beschriftet etwa „Land: Deutschland · Sprache:
  Englisch, Deutsch · Mindestzustand: Excellent“; du kannst sie ändern. Belegt sind nur die
  Nummern deines Beispiel-Links; andere Zustände tragen den Zusatz „Nummer unbelegt“.
- Je Karte öffnet „Cardmarket ↗“ die Kartenseite mit diesen Filtern in einem neuen Tab deines
  Browsers. Das Studio selbst ruft diese Seite nie ab. Bei Namen, deren Cardmarket-Adresse nicht
  sicher ist (etwa „A // B“, Umlaute, Bindestriche), öffnet „Cardmarket-Suche ↗“ die Suche; die
  Filter wählst du dort.
- Den abgelesenen Preis in das Feld der Zeile tippen (12,50 oder 12.50), das Datum ist heute
  (änderbar), „Speichern“. Leer oder 0 löscht den Eintrag (dann „unbekannt“).
- Viele Preise auf einmal: eine Datei `Name;Preis;Datum` außerhalb des Repositorys anlegen und
  `python -m commander_lab.studio import-tam-cardmarket-csv <deck_id> <Datei>` ausführen.

## Stichprobe zum Abgleich (bitte einmal am PC)

Fünf Karten aus der TAM-Zukauf-Liste: eine billige (unter 1 €), zwei mittlere (5 bis 20 €), eine
teure (über 30 €) und eine, bei der Foil günstiger ist. Je Karte auf Cardmarket notieren:

| Karte | günstigstes Angebot DE-Verkäufer, mind. EX, Nicht-Foil | dasselbe Foil | Trend (Preisinfo) | Ab-Preis (Preisinfo) | Datum |
| --- | --- | --- | --- | --- | --- |
| … | | | | | |

Dann im Studio dieselben Karten ansehen: „Cardmarket ab“ und „Trend“ sollten zur Preisinfo der Seite
passen (Stand des Preisführers beachten); die Differenz zum DE/EX-Angebot ist der Aufschlag, den
der Preisführer nicht kennt. Das Ergebnis bitte in #1637 kommentieren.

## Grenzen und Risiko

- Die Nutzungsbedingungen von Cardmarket zum automatisierten Abruf sind nicht geprüft (UNBELEGT).
  Der Download ist eine veröffentlichte Datei, kein Lesen von Webseiten; das Risiko (etwa eine
  Sperre) liegt beim Owner.
- Kein Browser-Skript, kein Lesen von Cardmarket-Seiten, keine Umgehung von Bot-Schutz.
- Preise fließen nie in Wertung, Tierliste, Ranking, Vorschläge, Kürzen/Tauschen, Evidenz oder
  Simulation. Chulane bekommt nie einen Preis.

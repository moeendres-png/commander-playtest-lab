# #1561: erste Anfrage nach einem Favoriten-Klick, Messung am Owner-PC (2026-11-24)

Refs #1561, #1558. Klassifikation der Zahlen: `DIRECTLY_VERIFIED` für diese Maschine und diese
Store-Kopie, kein CI-Beleg (CI hat keinen echten Store), keine Aussage für andere Maschinen.

## Werkzeug und Herkunft

- `python scripts/studio_response_manifest.py click --store <Store-Ordner> --out <Datei außerhalb des Repos> --clicks 5`
  (neu in diesem PR, Test in `tests/unit/test_studio_response_manifest.py`). Der Store wird nur
  gelesen; gemessen wird auf einer Kopie, die Vorlage wird vor und nach dem Lauf gehasht.
- Stand: `main` `4d32d5eb5`, Linux, 16 Kerne, Python 3.14, Store-Kopie des Owner-PCs
  (`template_database_sha256` beginnt mit `13cbc99c7e8e`), keine parallele Messung.
- Ablauf: alle 28 Leseanfragen aufwärmen, dann 5 Favoriten-Schreibvorgänge (je eine andere
  Karte, `PUT /api/cards/{id}/favorite`, Wert wechselnd). Nach jedem Schreibvorgang wird jede
  Messroute einmal gefragt. Jeder Schreibvorgang hat den Änderungszähler der Datei bewegt
  (`write_effective: true`, 5 von 5); sonst wäre die Messung ungültig.

## Messwerte (n = 5 Klicks je Route)

| Route | warm | nach dem Klick (ms, 5 Werte) | Median | Antwortbytes wie vor dem ersten Klick |
|---|---|---|---|---|
| `POST /api/strength` | 45,6 ms | 37,1 / 40,2 / 37,4 / 40,9 / 38,1 | 38,1 ms | ja (5 von 5) |
| `POST /api/land-advisor` | 349,3 ms | 350,2 / 347,6 / 348,3 / 348,0 / 344,2 | 348,0 ms | ja (5 von 5) |
| `GET /api/layers` | 2,9 ms | 687,7 / 691,9 / 694,9 / 754,3 / 688,9 | 691,9 ms | nein (erwartet: enthält die Favoriten) |
| `GET /api/evidence` | 11,2 ms | 15,0 / 15,2 / 15,9 / 15,9 / 15,9 | 15,9 ms | ja (5 von 5) |

Eine frühere, getrennte Messung derselben Art (Skript außerhalb des Repos, gleiche Maschine, gleicher
Stand) gab für `strength` 39 bis 43 ms (Median 42 ms), `land-advisor` Median 350 ms, `layers`
Median 710 ms, `evidence` Median 16 ms.

Vergleich mit der Messung im Issue (Stand `51185f2d8`, 2026-11-18, andere Maschine, 254-MB-Store, durch
parallele Messung belastet, daher nicht gleichwertig): `strength` 5,17 / 5,57 / 5,58 s, `land-advisor`
2,54 / 2,56 s, `layers` 0,74 bis 1,23 s. Verbesserung kommt aus #1611, #1649, #1711, #1714; dieser PR
ändert keinen Cache-Code.

## Schreibmatrix (Warm gegen Neustart) auf `main`

`python scripts/studio_response_manifest.py writes` auf derselben Store-Kopie: Favorit, Markierung,
Label, Entwurf, Revision, Primer, Universumsprofil je einmal geschrieben; danach gleichen die 28
Leseanfragen plus 3 Beobachter-Leseanfragen des laufenden Servers (Status, Länge, SHA-256)
denen eines frisch gestarteten Servers auf derselben Datei: 7 von 7 Schreibvorgängen,
0 Abweichungen, alle Antworten stabil.

## Urteil je Akzeptanzpunkt aus dem Issue

| Punkt | Urteil |
|---|---|
| Schreibmatrix als Test | erfüllt (`tests/unit/test_studio_perf_equivalence.py`, PR #1611, #1649) |
| Negativtest Import/SQL zwischen zwei Anfragen | erfüllt (ebenda) |
| Erste `/api/strength`-Anfrage nach Favoriten-Klick unter 0,5 s (Median aus 5) | **erfüllt auf dieser Maschine: 38,1 ms (n=5)**; andere Maschinen `UNKNOWN` |
| Äquivalenznachweis, Antworten warm gegen frisch | 0 Abweichungen (Schreibmatrix oben); der Vorher/Nachher-Vergleich gegen den Stand von 2026-11-18 ist nicht mehr aussagekräftig, weil seitdem andere Pakete die Antworten legitim geändert haben |

## Offen / nicht gebaut

- Option C (Korpus-Kennzahlen als eigener `import_only`-Eintrag) und eine eigene Cache-Art für
  `/api/corpus-audit` sind für die Akzeptanz nicht mehr nötig (`strength` liegt um Faktor 13 unter der
  Grenze). Kein Code, kein Versprechen.
- `layers` (692 ms) und `pool` hängen an den Favoriten und werden nach einem Klick bewusst neu
  gerechnet.
- Auflage 2 aus dem Review von #1711 (`evidence.py` behält `with_marks=False`, neue Lesungen in
  `cache.KINDS` deklarieren) wird vom Lese-Tracer in `test_studio_perf_equivalence.py` erzwungen.

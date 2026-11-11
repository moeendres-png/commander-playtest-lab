# Commander Studio · EDHREC 1.304 fehlende historische UTC-Zeitpunkte

**Stand 11.11.2026 · Abschluss Datenprüfung + lokale, isolierte SQLite-Umsetzung · REVIEW**

## Nachgewiesenes Ergebnis

- 1.379 C079-Originalbeobachtungen: 75 ursprünglich exakt belegte UTC, 1.304 ursprüngliche Abfragezeiten auch nach vollständiger Archiv-/Logprüfung unbekannt. **Historische UTC nicht rückdatiert.**
- 20 unveränderte und SHA-verifizierte JSON-Rohantworten wurden am 11.11.2026 um 12:54:59–12:55:31 UTC erfolgreich mit HTTP 200 neu abgefragt und separat archiviert.
- 4.945 eindeutige **neue Karten-/Quellseiten-Paare** in separater Kohorte. 1.298 der betroffenen 1.304 historischen Kartennamen+Seiten sind in der neuen Aufnahme erneut vorhanden, sechs nicht gelistet = UNKNOWN, **niemals** 0 %.
- Die lokalen importierten Daten stehen in der bereitgestellten `CommanderStudio_EDHREC_C079_NEU_2026-11-11_REVIEW.sqlite3`; alle vier Tabellengruppen sind unabhängig von der produktiven `studio.sqlite3` und haben `PRAGMA integrity_check=ok`, `foreign_key_check=0`.
- Neu quelloriginal: Name, `num_decks`, `potential_decks`, Lift und unverändertes Roh-JSON mit SHA/HTTP-UTC. Neu berechnet: `inclusion_pct_derived`; Karten-`oracle_id` bleibt im neuen Datensatz NULL, bis der EDHREC-Cardview-Identifier unabhängig abgeglichen ist.
- Datenerfassung und alle Offline-Regressionstests PASS, wiederholter Import idempotent. Keine bestehenden Source-Dateien, 7 ACTIVE-Dateien, persönliche Sammlung, XMage-Pin oder der Produktions-DB überschrieben.

## Benutzung (kostenlos und offline)

Nach Download des *vollen* ursprünglichen ZIP aus Google Drive und Auschecken des GitHub-Repos:

```bash
# Installationen nicht nötig; Python >=3.12 und stdlib genügen.
python scripts/studio_edhrec_provenance/edhrec_provenance.py \
  --db /ABSOLUTER/PFAD/AUSSERHALB/DES/REPOS/edhrec_provenance.sqlite3 \
  import-review STUDIO_EDHREC_C079_HISTORIE_UND_NEU_2026-11-11_VERIFIZIERT.zip

python scripts/studio_edhrec_provenance/edhrec_provenance.py \
  --db /ABSOLUTER/PFAD/AUSSERHALB/DES/REPOS/edhrec_provenance.sqlite3 status

python scripts/studio_edhrec_provenance/edhrec_provenance.py \
  --db /ABSOLUTER/PFAD/AUSSERHALB/DES/REPOS/edhrec_provenance.sqlite3 card "Fellwar Stone"
```

Die zur direkten Verwendung bereitgestellte SQLite-Datei macht `import-review` optional. Der Programmcode erlaubt außerdem `import-new <FOLDER|ZIP>` für **spätere** frische HTTP-Rohsätze und versieht diese mit separaten unveränderbaren Event-IDs. Kein Netzwerkzugriff beim Import. Der Collector hat einen expliziten manuellen GitHub-Actions-Workflow.

## Grenzen und spätere Studio-Anbindung

Die SQLite-Datei ist ein vollständig reproduziertes, filter- und abfragbares **Forschungs-Review-Artefakt**. Sie ist bewusst nicht die produktive `studio.sqlite3`. Eine spätere Anzeige im Studio-Dashboard muss die Trennung `LEGACY_C079`/`NEW_HTTP_CAPTURED` im UI sichtbar machen, Oracle-IDs unabhängig crosswalken und darf Bestands-/Deckdaten nicht berühren. Ein Green-Test für Datenimport ist **kein** XMage-Spiel-/Rules-Nachweis.

Das historische Datum wurde nicht „repariert“: Ohne ursprüngliche, exakt der damals gespeicherten Beobachtung zuordenbare HTTP-Protokollierung bleibt das unbekannt. Die künftigen neuen Beobachtungen sind dagegen vollständig zeitgestempelt und nachweisbar.

**Provenienzquelle und Originaldaten:** https://drive.google.com/drive/folders/1kAFbIlvD6Qv1rcJRSMbILaNeOgd6PkWy

**Rohbeleg und Collector:** https://github.com/moeendres-png/commander-playtest-lab/actions/runs/43024442970

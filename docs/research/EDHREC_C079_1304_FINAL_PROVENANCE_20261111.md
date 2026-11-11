# EDHREC Chulane C079 – historische Quellen und neue HTTP-200-Snapshots (11.11.2026)

**Status:** Historischer Quellen-Audit abgeschlossen; neue Datenerfassung ist REVIEW (`automatic_import=false`). Primärbelege liegen auf Google Drive, nur überprüfbarer Code und ein kompakter öffentlicher Hash-/Zeitindex im GitHub-Repository.

## Nachgewiesene Fakten

| Beleg | Anzahl |
|---|---:|
| Historische C079-Karten-/Themenseiten-Beobachtungen | 1.379 |
| Historische Beobachtungen mit exakt zugeordneter UTC | 75 |
| Historische Beobachtungen ohne originale individuelle HTTP-Uhrzeit | **1.304** |
| Betroffene historische ungefilterte Themenseiten | 20 |
| Werte + URL mit ursprünglichem Archiv-HTML exakt abgeglichen | **1.304 / 1.304** |
| SHA-verifizierte historische Rohdateien | 544 |
| Originaler HTTP200-/Roh-SHA-Beweis für die 20 konkreten C079-Seiten | **0** |
| Neue, selbständige Quell-Events mit HTTP 200 | **20** |
| Kartenname-/Themenseiten-Paare im neuen Snapshot | 4.945 |
| Frühere Karten-/Seiten-Paare auch im neuen Snapshot | 1.298 |
| Aktuell nicht gelistete historische Paare | **6 (UNKNOWN, nicht 0 %)** |

Die 20 neu aufgenommenen Quellen stammen aus dem Fenster **2026-11-11T12:54:59.352Z–12:55:31.966Z**. Ihre UTC-Uhrzeiten sind **nicht** die damals verlorenen C079-Zeitpunkte. Die 75 vorhandenen historischen Zeiten bleiben unverändert, die anderen 1.304 `snapshot_utc` müssen unbekannt bleiben. Zeitangaben aus anderen Datengenerationen, Archiv-Uploads und Webseiten-Zwischenspeichern sind kein Beleg für den ursprünglichen HTTP-Abruf.

## Quellen und Prüfnachweise

- Vollständiges 24-Dateien-Prüfpaket mit SHA-256: https://drive.google.com/file/d/1eX670LPagB4K6Sp2t1XrzwaUhuo_LgbB/view
- Audit-Ordner: https://drive.google.com/drive/folders/1kAFbIlvD6Qv1rcJRSMbILaNeOgd6PkWy
- Einzeln entpackte originale HTTP-JSON-Antworten (20): https://drive.google.com/drive/folders/1J3au0H6Rj-OCY8DpyauwrSb4-yjPnIak
- Per-HTTP-Request-UTC-/Status-/SHA-Belege (20): https://drive.google.com/drive/folders/1Ry1py7awQHgmBG3F4MhPhWbFof-BPOpw
- Quellevent-Dateimanifest: https://drive.google.com/file/d/1_gjmtw_rgE-lA4wqVVvRwAhyA_8She9f/view
- Ursprünglicher Live-Abruf (grüne GitHub Actions): https://github.com/moeendres-png/commander-playtest-lab/actions/runs/43024442970
- Einzeln geprüfte 1.379 Historie-Zeilen: https://drive.google.com/file/d/1_5rp7FnIDKRRUfknJxWTJYQi7JG_dNWG/view
- Öffentlicher Event-Hash-/Zeitindex ohne Sammlungsdaten: `data/studio_public/edhrec_chulane_20261111_review_manifest.json`.

## Codevertrag: nur neue HTTP-Zeitpunkte

Der Collector erzeugt Event-IDs, originale JSON-Bytes, URL, HTTP-Status, SHA-256, Byte- und Rubriken-Zähler sowie **getrennte** `request_start_utc` und `response_complete_utc`. Vor jedem Studio-Import prüft `src/commander_lab/studio/edhrec_capture_proof.py` den tatsächlichen Rohbeleg, jede Event-Metadatendatei sowie das Event-Fingerprint. Fehlender oder veränderter Beleg führt zum Abbruch vor SQL.

Die Studio-CLI `import-edhrec-manifest` speichert pro HTTP-Event einen eigenen `source_id` (auch wenn zwei Antwortdateien byteidentisch sind) und pro UTC-Datum/Themenseite eine separate Kohorte. Idempotenter Reimport; kein Überschreiben anderer Eventquellen oder historischer C079-Reihen. Fehlende Karten der sichtbaren API-Cardlist sind `UNKNOWN` und **niemals** ein 0-%-Nachweis. Inclusion = berechnete Zähler/Nenner-Quote; Lift ist keine Siegquote. Oracle-ID nur mit unabhängigem Scryfall-Crosswalk.

Der neue EDHREC-HTTP-Collector wird **nur manuell** per Workflow angestoßen und kann neue Ereignisse mit eigener Zeitbeweiskette erzeugen. Er importiert keine neue Datengeneration automatisch in den produktiven Studio-Bestand. Tests sind in `tests/unit/test_studio_edhrec_snapshot_import.py` und `tests/unit/test_studio_edhrec_proof_validation.py`; ein tatsächlicher 20-Seiten-Liveimport nach SQLite-In-Memory wurde als eigene CI-Prüfung ausgeführt.

**Fazit:** Die historischen 1.304 verlorenen Uhrzeiten sind aus dem vorhandenen Material nicht rekonstruierbar. Der Provenienz-Audit und die neue unabhängige UTC-belegte Quellenkohorte sind eine sichere, überprüfbare Lösung, aber keine rückwirkende historische Reparatur.

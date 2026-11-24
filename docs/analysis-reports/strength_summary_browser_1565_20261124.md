# #1565: Browser-Vorher/Nachher-Abnahme `/api/strength` (`detail: "summary"` + Kartenmodal) (2026-11-24)

Refs #1565, #1558, #1794.

## Messaufbau

- **Browser:** Google Chrome `157.0.8103.80` (echter Browser, headless via DevTools Protocol mit `Network`-Überwachung gegen echten lokalen Studio-HTTP-Server).
- **Datenbasis:** isolierte temporäre SQLite-Backup-Kopie des lokalen Owner-Studio-Stores (`232 MB`, Chulane-Pool `927` eigene Karten, `3.798` Quelldecks); der Original-Store wurde nicht beschrieben, keine Store-Kopie oder Rohdaten im Repository.
- **Stände:**
  - Vorher: `b298a4ed5` (unmittelbar vor PR #1794; `app.js` lädt `/api/strength` vollständig).
  - Nachher: `main` `aa7a4b57e` (mit PR #1794; `app.js` lädt `/api/strength` mit `detail: "summary"` und holt beim Öffnen des Kartenmodals die Einzelkarte via `detail: "full", card_id`).
- **Ablauf:** je Stand ein Warm-up-Lauf (verworfen), danach gemessener Warm-Lauf auf `index.html` bis zur vollständig gerenderten Builder-Liste, anschließend Klick auf die erste Karte (`td.name` / `span.nm`) bis zum vollständig gerenderten Kartenmodal (`#modal-box`, nach Abschluss von „Lädt Signale …“).

## 1. Bytes und Ladezeit (Startseite `index.html` + Kartenmodal, warm)

| Kennzahl | Vorher (`b298a4ed5`) | Nachher (`main` `aa7a4b57e`) | Veränderung |
|---|---:|---:|---:|
| Gesamt-Bytes Startseite (`index.html` + alle API/Assets) | 11.065.788 B (10,55 MB) | 2.634.035 B (2,51 MB) | **−76,2 % (−8,04 MB)** |
| `POST /api/strength` (Listen-Aufruf) | 8.586.033 B (8,19 MB) | 130.762 B (127,7 KB) | **−98,48 % (−8,06 MB)** |
| `POST /api/strength` Antwortzeit (warm, Browser-Netzwerk) | 96 ms | 54 ms | **−43,8 % (−42 ms)** |
| Kartenmodal-Nachladen (`detail: "full", card_id`) | 0 B (war bereits im 8,59-MB-Block) | 8.779 B (8,6 KB) | +8,6 KB bei Klick |
| Kartenmodal Öffnen bis gerendert | 326 ms | 331 ms | +5 ms (im Rauschen) |

*(Kalt-Lauf vor Warm-up zur Einordnung: Gesamt-Bytes `11,02 MB → 2,73 MB`, `/api/strength` `8,59 MB → 130,8 KB`, `readyAtMs` `7.869 ms → 7.440 ms`.)*

## 2. Inhaltliche Gleichheit im Browser (Builder-Liste und Kartenmodal)

- **Gerenderte Zeilen in der Builder-Liste:** `39 == 39` (`True`).
- **Stichprobe der ersten 20 gerenderten Zeilen (Kartenname, Index, Tier, Kennzahlen):** `20/20` zeichengenau identisch (`listSample exact match: True`).
- **Gerenderter Kartenmodal-Text (`#modal-box`, `2.000` normalisierte Zeichen inkl. Stärke-Index-Aufschlüsselung und Signalkomponenten):** zeichengenau identisch (`modalText exact match: True`).

## Grenzen / `UNKNOWN`
- Gemessen auf der Startseite `index.html` (Builder, Chulane-Pool, 1 Tab); `tierliste.html` nutzt unverändert `detail: "full"` (wie in PR #1794 vorgesehen).

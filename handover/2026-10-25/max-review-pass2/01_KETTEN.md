# Max-Review Pass 2 — Ketten-Tabellen

Alle Ketten: Real-Pod, Treiber `~/workspace/tmp/phase4b/phase4b_play.py`,
JAR `bridge_pass2.jar` (sha256 `6ba47e02…`, aus Lab `217c34d95` + Fork v13;
Bridge-Diffs für alle Base/Head-Paare leer → JAR für alle Ketten gültig).
Vergleich: semantischer Hash (Prompt + gewählte Labels + Outcomes) und Sieger
je Seed. „ok" = Spiel lief bis zum Ende (status `ok` in der JSON).
Alle Zahlen DIRECTLY_VERIFIED aus den Ketten-Verzeichnissen
(`~/workspace/tmp/max-review/`); die Tabellen wurden für diesen Entwurf aus
den Dateien neu gerechnet und stimmen mit `pass2-notes.md` überein.

## Kette A — #1007 (Phase 5, Zahlungs-Plan), Seeds 1–24

- Base: `abort24/` (Stand `ee47312a7`, #1007-Base = #1006-Head).
- Head: `pass2-a/` (Stand `217c34d95`, #1007-Head).
- Ergebnis: 24/24 ok; Hash bit-identisch 12/24; divergiert 12/24;
  Sieger gleich 15/24.
- Divergierte Seeds: 2, 3, 4, 8, 10, 11, 12, 13, 16, 18, 20, 23.
- Sieger-Wechsel-Seeds: 2, 3, 8, 10, 12, 13, 16, 18, 20.
- Entscheidungen (Frames, requested + accepted): 171.976 (Base) → 173.700
  (Head), +1,0 %.
- Cancels (rohe Mana-Payment-Cancels): 136 (Base-Recount) → 82 (Head);
  Head: 79/82 mit genau 1 angebotener Option (erzwungen).
- Top-Cast: Bitter Downfall (29 vs 32).

## Kette B — #1006 (Phase 3, Kampf), Seeds 1–24

- Base: `pass2-b/` (Stand `54da28d63`, #1006-Base).
- Head: `abort24/` (Stand `ee47312a7`, #1006-Head).
- Ergebnis: 24/24 ok nach Retry; Hash bit-identisch 10/24; divergiert 14/24;
  Sieger gleich 24/24.
- Divergierte Seeds: 1, 2, 6, 7, 8, 11, 13, 15, 16, 17, 20, 21, 23, 24.
- Sieger-Wechsel-Seeds: keine.
- Vorfall: Seed 19 erst BRIDGE_TIMEOUT; Retry ok, Hash bit-identisch zur
  Baseline, Sieger [2] = Baseline.
- Vorfall: Kette vom Runtime-Restart bei Seed 18/24 gekillt; per Resume-Skript
  neu gestartet (Seeds 1–18 übersprungen, kein Verlust, keine Duplikate).
- Blocker-Proxy (accepted-Frames, `declare_blocker` mit ≥1 gewähltem Block):
  139 (Base, 362 Entscheidungen) → 154 (Head, 373 Entscheidungen).
  Block-Runden-Metrik 19→15 aus Transkripten NICHT ableitbar (s. 00_BERICHT §3).

## Kette C — #1004 (Target-Seiten), Seeds 1–24

- Base: `pass2-c-base/` (Stand `c0e5f7f1`, #1004-Base).
- Head: `pass2-c-head/` (Stand `053708e56`, #1004-Head).
- Ergebnis: 24/24 ok; Hash bit-identisch 1/24 (nur Seed 17); divergiert 23/24;
  Sieger gleich 13/24.
- Divergierte Seeds: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
  18, 19, 20, 21, 22, 23, 24.
- Sieger-Wechsel-Seeds: 4, 5, 7, 8, 9, 10, 12, 15, 16, 22, 24.
- Vorfall: C-Base vom Runtime-Restart bei Seed 13/24 gekillt; per Resume ab
  Seed 14 neu gestartet, fertig 24/24 (13:14). C-Head fertig 24/24 (13:55).
- #1004s eigene Real-Game-Aussage: nicht geprüft (UNKNOWN, s. 00_BERICHT §4).

## Kette D — #1007 (Phase 5, Zahlungs-Plan), Seeds 25–48

- Base: `pass2-d-base/` (Stand `ee47312a7`, #1007-Base).
- Head: `pass2-d-head/` (Stand `217c34d95`, #1007-Head).
- Ergebnis: 24/24 ok; Hash bit-identisch 11/24; divergiert 13/24;
  Sieger gleich 16/24.
- Divergierte Seeds: 25, 26, 29, 30, 31, 35, 36, 38, 41, 42, 44, 46, 47.
- Sieger-Wechsel-Seeds: 26, 29, 31, 36, 41, 44, 46, 47.
- Vorfall: D-Base starb unbemerkt ~14:08 bei Seed 38/48 (kein Prozess, Log
  still); auf Nachfrage 15:31 neu gestartet, fertig 24/24 (15:42).
  D-Head gestartet 16:03, fertig 24/24.
- Zusammen mit Kette A: 48/48 ok, 23/48 bit-identisch, 25 divergieren,
  Sieger gleich 31/48 — #1007s Angabe exakt reproduziert.

## Übersicht

| Kette | PR | Seeds | ok | identisch | divergiert | Sieger gleich |
|---|---|---|---|---|---|---|
| A | #1007 | 1–24 | 24/24 | 12 | 12 | 15/24 |
| B | #1006 | 1–24 | 24/24 | 10 | 14 | 24/24 |
| C | #1004 | 1–24 | 24/24 | 1 | 23 | 13/24 |
| D | #1007 | 25–48 | 24/24 | 11 | 13 | 16/24 |
| A+D | #1007 | 1–48 | 48/48 | 23 | 25 | 31/48 |

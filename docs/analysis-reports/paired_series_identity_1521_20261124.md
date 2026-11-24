# #1521: Echt-Engine-Identitätslauf für parallele gepaarte Serien (`--mode paired`, `N = 20`) (2026-11-24)

Refs #1521, #1793, #1167.

Alle Zahlen: lokale Messung am Owner-PC (`SIMULATED_RESULT`, kein CI-Beleg, keine Qualifikation,
Zustand `BRIDGE_AHEAD_OF_QUALIFICATION`, `covered_by_sealed_epoch: false`).
Lab-Stand: `main` `aa7a4b57e`, Bridge-JAR SHA-256:
`ec53219322a25d0d7433e972051731d48115bcb4a9329b0a75713aeb3d10b938`,
Engine-Pin: `f4d12f6e8066203fba7aa38bd35ea3358117393d` (XMage 1.4.62), Java 21, Linux, 16 Kerne.
Start-Last vor dem Lauf: `1-min-loadavg = 0,26` (`< 2`).

## Befehl & Tisch

- Befehl:
  `python scripts/check_studio_series_identity.py --mode paired --jar engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar --deck data/decks/deckbau/chulane_current.json --variant-deck data/decks/precons/2014_guided_by_nature.json --seeds 1-10 --workers 2 --games-per-jvm 4 --work <tmp> --out <tmp>/paired_identity_20.json`
- Tisch: 4 Sitze (`chulane_current` bzw. `2014_guided_by_nature` gegen den `precon`-Pod aus `deckbau_eval.PODS["precon"]`), `10` Paare = **`20` Partien**, je einmal allein (`one game per JVM`) und einmal über `paired_comparison.parallel_window_player` (`workers=2`, `games_per_jvm=4`, `pool=null`).

## Ergebnis: `IDENTITY PASS` (`20 identisch von 20`)

| Kennzahl | (a) Einzeln (1 Spiel/JVM) | (b) Gepaart (`workers=2`, `games_per_jvm=4`) | Vergleich |
|---|---:|---:|---|
| Gestartet / beendet / fehlgeschlagen | 20 / 20 / 0 | 20 / 20 / 0 | `20/20` beendet |
| `semantic_transcript_sha256` identisch | — | — | **`20 identisch von 20`** |
| Siegersitz & Entscheidungszahl identisch | — | — | **`20/20`** |
| Wanduhr (Messung, kein Beleg) | 413,4 s | 180,5 s | 2,29× schneller |
| CPU-Zeit | 1.038,6 s | 484,4 s | 2,14× weniger CPU |

Alle 20 Semantik-Transkript-Präfixe (`a | b` paarweise identisch):
- Seed 1: `base 36016f9988c6b816`, `variant c3535adddf051cb2`
- Seed 2: `base 2112bef28a588586`, `variant 3a689bab254ad341`
- Seed 3: `base e87ed79cf416c98f`, `variant c9a236b49d6be494`
- Seed 4: `base a174c33661f6cf47`, `variant f585665ca64ebc35`
- Seed 5: `base 6b05af520015d29e`, `variant 0466310b8c8781d0`
- Seed 6: `base 8f16c26ffde331f2`, `variant 5c13673280b1f829`
- Seed 7: `base 05b88213f676aa7a`, `variant 88a10f5c7185b50d`
- Seed 8: `base 8aa7d38cbcbb84e4`, `variant f5c042ca1c4c32b1`
- Seed 9: `base 22701828a9ac5477`, `variant a2e606aca3e4ee01`
- Seed 10: `base 9aa504e841c11cfc`, `variant 6cb52ad54aadf874`

## Grenzen / `UNKNOWN`
- Der 160-Paare-Pilotblock aus #1521 bleibt offen (`NOT_RUN`); gemäß Owner-Entscheid 2026-11-24 (#1590, Option B) wird die reale Chulane-Paar-Streuung direkt aus der ersten Chulane-Nachtserie (`#1528`) abgelesen.
- Gemessen unter Linux; nativer Windows-Lauf bleibt `UNKNOWN` (Skript-Start unter Windows durch CI `windows-runtime` abgedeckt).

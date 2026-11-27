# `#1528` (Option A1): Vorab-Zusatzplan — Geschärfte Positivkontrolle `P27` vs. `B36` (`360` rotierte Paare)

- **Datum:** 2026-11-27 · **Refs:** `#1528`, `#1167`, `#1521`, `#1524`, `#1589`, `#1590`
- **Vorherige Dokumente:** [chulane_land_axis_plan_1528_20261124.md](chulane_land_axis_plan_1528_20261124.md) (Vorab-Plan), [chulane_land_axis_controls_1528_20261125.md](chulane_land_axis_controls_1528_20261125.md) (`N36` `PASS`, `P27` bei `N = 80` `FAIL_CLOSED`)
- **Owner-Entscheide:** 2026-11-26 (`#1528` Kommentar `7191943214`: Option A — Positivkontrolle erst schärfen) und 2026-11-27 (`#1528` Kommentar `7214899130`: **Option A1** — Budget auf `320–400` rotierte Paare auf frischen, disjunkten Seeds erhöhen, gleicher Kontrast `27` Länder).
- **Einordnung:** Vorab registrierter Zusatzplan vor dem ersten Spiel von Option A1 (`CODE_DERIVED`, noch keine A1-Partien gestartet → alle A1-Messwerte vor Lauf `NOT_RUN`). Spätere Ergebnisse tragen `SIMULATED_RESULT`, Gewicht `0`, kein Qualifikationsbeleg (`AGENTS.md` §1, §4).
- **Basisstand & Engine-Pin:** `main` @ `f13666f2c2288ab242fba7e4681a15e55ea0466b`, Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`config/rules_engines.json`), Bridge-JAR SHA-256 `33eead68b50b04ae68c966b130ffbb38b393e3eb9f2c279c55febb1d18f2802f` (`BRIDGE_AHEAD_OF_QUALIFICATION`).

---

## 1. Vorab festgelegte Konfiguration (Option A1, kein Seed-Recycling)

- **Arme (unverändert zum Vorab-Plan):**
  - **Basis `B36` (`36` Länder):** `data/decks/deckbau/chulane_current.json` (Deck-JSON SHA-256 `4ca6e965cbb7b179278cf8440b92bc10624d4a1d6da94a1740f4d0e494783d87`).
  - **Positivkontrolle `P27` (`27` Länder):** Raus `4× Forest`, `3× Island`, `2× Plains`; rein `Abbey Griffin`, `Arbalest Elite`, `Aven Fisher`, `Aven Fleetwing`, `Azure Drake`, `Bladed Sentinel`, `Blightwidow`, `Briarhorn`, `Clockwork Condor` (Deck-JSON SHA-256 `e3656db5c01fa0cc9f4de6854ce5fdc97058135c1e85f88ea312472b24490de8`).
- **Tisch (4 Sitze, fest):** Chulane-Arm gegen `precon/2026/lorehold_spirit`, `precon/2024/animated_army`, `precon/2022/token_triumph`.
- **Frischer, disjunkter Seed-Block:** `base_seed = 20000`, `pairs = 360` rotierte Paare = **`90` Seed-Cluster** (`Seeds 20000..20089`, je `4` rotierte Sitze `0..3` = **`720` Partien**). Keine Überschneidung mit `N36` (`10000..10019`), `P27_80` (`11000..11019`), `V38` (`12000+`) oder `V40` (`13000+`). Keine Zusammenlegung mit dem alten `P27`-Lauf (`80` Paare).
- **Laufparameter:** `compare-decks --pairs 360 --look-every 360 --base-seed 20000 --rotate-seats --series-id chulane-1528-p27-a1 --workers 6 --games-per-jvm 20 --record-pilot-audit`, Schalter `COMMANDER_LAB_STUDIO_SERIES_POOL = 0` (`OFF`). Festes Budget (`--look-every 360` ohne Zwischenabbruch, um die volle Cluster-Stichprobe ohne Alpha-Spending-Einbuße auszuwerten).

---

## 2. Vorab festgelegte Bestehenskriterien (`P27` Option A1)

Die Positivkontrolle `P27` gilt genau dann als **bestanden (`PASS`)**, wenn alle drei Bedingungen gemeinsam erfüllt sind:

1. **Hauptkennzahl (geclusterte Differenz `P27 − B36`):** Die gesamte `95-%`-Cluster-t-Konfidenzspanne liegt strikt unter `0,0 pp` (oberes `95-%-CI < 0,0 pp`, erwartete Nachweisgrenze ca. `~7,5–8,5 pp` bei `90` Clustern).
2. **Exakte hypergeometrische Gegenprobe (`first_dealt_hand`, `N = 99`, `n = 7`):** Kein Widerspruch gegen `K = 27` (`P27`) und `K = 36` (`B36`) (`chi2`-Test über `0–1`, `2–4`, `5+` Länder, `p >= 0,01` auf `p27_a1`).
3. **Identitätsprobe vor bzw. neben dem Lauf (`scripts/check_studio_series_identity.py --mode paired`):** Auf frischen Seeds `20000..20004` (`5` Paare = `10` Partien, `n >= 5`) identischer `semantic_transcript_sha256`, `winner_seats` und `decision_count` in **`10/10`** Partien gegen Einzel-JVMs (`PASS`).

Erst bei bestandenem Tor stehen die Hauptarme `V38`/`V40` (mit vom Owner/Lead passend gewähltem Cluster-Budget) zur Freigabe an; am Schluss bleibt der Owner-Satz „sinnvoll / nicht sinnvoll“ (`needs:owner`).

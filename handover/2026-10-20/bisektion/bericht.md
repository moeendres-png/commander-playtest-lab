# Bisektion der Fork-Patches — Ergebnis (Muse, 2026-10-20)

## Ergebnis zuerst

**Keiner der drei Hunks verursacht die Abweichungen — einzeln nicht, gemeinsam nicht.**
V4 (alle drei zurückgenommen) zeigt bit-identisch dieselbe Abweichung wie V0.
Die Ursache liegt außerhalb der Hunks: Im Fork wurden **6 existierende Karten** — die
Turbulent-Dual-Lands — durch „vereinfachte" Implementierungen ersetzt, die ihre
Mana-Fähigkeiten und ETB-Effekte verlieren. Eine davon, **Turbulent Steppe**, steckt im
Smoke-Pod (Lorehold Spirit Precon) und produziert im Fork **kein Mana**.

Evidenz-Klasse: DIRECTLY_VERIFIED (eigene Builds + Läufe, kalibriertes Setup).

## Orakel-Tabelle (Baseline-Hashes vorher exakt reproduziert)

Baseline (Pin-JAR): Seed 5 = `d87ff347…`, OK, 5765 Decisions, Winner [1] ·
Seed 10 = `5a3d66b8…`, OK

| Variante | H-PI | H-CI | H-TA | Seed 5 | Seed 10 |
|---|---|---|---|---|---|
| V0 | an | an | an | `4ca08e0e…` MISMATCH | FAILED (ENGINE_FAILURE) |
| V1 | aus | an | an | `4ca08e0e…` MISMATCH | FAILED |
| V2 | an | aus | an | `4ca08e0e…` MISMATCH | FAILED |
| V3 | an | an | aus | `4ca08e0e…` MISMATCH | FAILED |
| V4 | aus | aus | aus | `4ca08e0e…` MISMATCH | FAILED |

Seed-5-Verlauf in allen Varianten identisch: 3980 Decisions, Winner [3] (Baseline: 5765, [1]).
JAR-SHA-256: V0 `2d1bba6c…`, V1 `7f796445…`, V2 `a7647e11…`, V3 `806490f6…`, V4 `b0900e78…`
(alle verschieden; Klassen-Check: `TriggeredAbilities.class` differiert zwischen V0- und
V3-JAR — die Reverts sind nachweislich in den Builds gelandet).
Details: `ergebnisse.json`; Revert-Diffs: `v1_revert.diff` bis `v4_revert.diff`.

## Der eigentliche Befund

`git diff --name-status Pin..Fork-Head` über `Mage.Sets/src/mage/cards/`:
**48 Dateien ADDED, nur 6 MODIFIED** — und alle 6 Modifizierten sind Turbulent-Lands,
alle 6 per „Simplified implementation" ersetzt:

- TurbulentDreams, TurbulentFen, TurbulentMoor, TurbulentSprings,
  **TurbulentSteppe**, TurbulentWilderness

Beispiel TurbulentSteppe — Pin-Version (TheElk801):
`RedManaAbility` + `WhiteManaAbility` + `EntersBattlefieldTappedUnlessAbility`
(OpponentsControlEightLands). Fork-Version: nur Subtypen Mountain/Plains,
**keinerlei Fähigkeiten**.

Abgleich mit den Pod-Decks (319 distinkte Karten in rogshai_current, kaervek,
hosts_of_mordor_precon, lorehold_spirit_precon): genau **eine** geänderte Karte —
Turbulent Steppe (`.deck.cards[11]` im Lorehold-Profil). Sie liegt im Lorehold-Deck
und gibt dort in jedem Fork-Spiel kein Mana → abweichender Verlauf ab den ersten
Zügen, konsistent mit 29/35 Mismatches und der varianten-invarianten falschen Trajektorie.

## Verbleibendes Delta V4 vs. Pin (vollständige Aufzählung)

1. Die 6 ausgehöhlten Turbulent-Lands (s. o.) — **Hauptbefund**
2. 48 neue Karten-Dateien + 10 Set-Dateien (Registrierungen, u. a. Kartennummern 2000+)
3. P1 `GameState.getPlayersInRange`-Fast-Path (noch aktiv)
4. `AbilitiesImpl.singleton` + 2 Aufrufstellen in PlayerImpl (noch aktiv)

## Offen

Ob auch der **Seed-10-Crash** von den ausgehöhlten Lands stammt, ist **nicht bewiesen**
(ein mana-loses Land ändert das Spiel, muss die Engine aber nicht crashen lassen) —
Status: UNKNOWN.

**Vorgeschlagener Diskriminator V5:** Fork-Head, nur die 6 Turbulent-Dateien auf den
Pin zurückgesetzt, alles andere unverändert. Erwartung: Seed 5 kehrt zum Baseline-Hash
zurück. Seed 10 entscheidet die Crash-Zuordnung (OK = Karten waren alleinige Ursache;
weiter FAILED = separate Ursache unter Punkt 2–4 oben). Aufwand ~10 Min (Sets-Rebuild + Orakel).

## Akzeptanzkriterien — Stand

1. Schuldiger Hunk benannt: **Negativ-Ergebnis mit Hash-Evidenz** — keiner der drei
   Hunks ist der Verursacher. Die Abweichung ist stattdessen den geänderten
   Karten-Implementierungen zugeordnet (für Seed 5); Crash-Zuordnung offen (V5).
2. Abschlusskonfiguration 36 Seeds: **nicht gelaufen** — innerhalb des Hunk-Rahmens
   existiert keine saubere Konfiguration; ein 36-Seed-Lauf auf V4 würde nur einen
   bekannt-falschen Stand erneut messen. Folgt nach V5/Fix.
3. Verbleibende Abweichung offen benannt: ja (dieser Bericht).

## Laufzeiten (für die Planung nach Claudes Fix)

- Volle Modul-Kette (einmalig): ~10,5 Min; Core-Rebuild je Variante: ~21 s;
  Bridge-Package: ~60–80 s; Orakel-Lauf (2 Seeds): ~2,5–4 Min
- 36-Seed-Lauf (aus 2026-10-19): ~34 Min

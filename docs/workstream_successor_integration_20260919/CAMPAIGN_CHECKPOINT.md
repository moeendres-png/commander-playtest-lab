# Campaign Checkpoint — Commander Simulator Next (2026-09-19, post successor-integration)

## Projektziel (unverändert)

Trustworthy Full-Rules Commander-Simulator: echte Karten, 2–5P
Rules-Konformität (4P primär), autoritative Entscheidungen, deterministisches
Replay. ARCHITECTURE_FREEZE = NOT_CLAIMED. PRODUCTION_PROVIDER = NOT_SELECTED.

## Aktiver Workstream

KEINER (zuletzt: `cpl/xmage-successor-integration-20260919` @ `d38cb5b2`,
COMPLETE + versiegelt; Ownership freigegeben, Tree sauber, keine Locks).

## Verifizierte Source Locks

- Lab `origin/main` = `aebcfda3`; Integration `d38cb5b2` (3 Commits:
  `291dc89a` Prod, `009bf560` Tests, `d38cb5b2` Evidence).
- Donor `fa4cd8d1` (kumulativ WS213→WS232, read-only, unberührt).
- Engine-Pin `xmage-1.4.61` unverändert; Source-Zeiger cfc36f44→db134b97
  (Linie auf origin/mage DIRECTLY_VERIFIED).
- AKTIV anderswo (NICHT ANFASSEN): `cpl/three-deck-optimization-20260919`.

## Meilensteine dieser Kampagne (2 Workstreams)

1. Prepare-Behavior-Gate (`5fc903fc`/`c63698d1`): 2/11 konstruierbar,
   9/11 fail-closed absent, ENGINE_PIN_GAP root-caused.
2. Successor-Integration (`291dc89a`/`009bf560`/`d38cb5b2`): 2–5P,
   Replay-Tape-v1, Numerik-Lanes, Hazard-Repairs auf Main-Linie portiert;
   Bridge 153/153, Python 756, Retention 6/6, LIVE 2/3/4/5P-Gates PASS
   (natürliche Terminale, Replay-MATCH ×4, 25 753 Entscheidungen).

## Offene Abhängigkeiten / Blocker

- Merge braucht separate Autorisierung (PR von `cpl/xmage-successor-…`).
- CI-Smoke-Lane-Follow-up (Main-CI-Owner): 15 geparkte Wiring-Tests.
- Container: hypothesis/openpyxl/fastapi-Lücken (Environment-Owner).
- Sol-High-Gates: CR/Release-Notes (Prepare), Freeze/Provider-Entscheide.

## Nächste ausführbare Aktion (kleinste, verifiziert)

Koordinator entscheidet: (a) PR-Autorisierung Integrations-Branch,
(b) CI-Lane-Scope, oder (c) nächster Campaign-Workstream mit frischem
Ownership — Kandidaten: Prepare-Verhaltensrester nach Engine-Repin,
Forge-FULL107-Denominator, Sechs-Spieler-Fail-closed-Härtung. Basis immer
`aebcfda3`, nie aktive Surfaces.

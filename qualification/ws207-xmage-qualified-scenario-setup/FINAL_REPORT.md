# WS207 Final Report — XMage Qualified Scenario Setup

Qualification-setup workstream. Zero behavior credit earned or granted. No
provider ranking. No Architecture Freeze. No Full107.

## Source Lock

- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `ws207/xmage-qualified-scenario-setup-20260914`
- `AUDIT_BASE_SHA`: `1dee8b77f7243900eec5a7cc05fb1fe26467aea9` (live HEAD identical)
- XMage engine pin: `cfc36f445f917f101fa2ed588770e043f53bc44c` (preserved, no repin)
- Sealed WS90 blobs preserved (`CODE_DERIVED` via `git hash-object`):
  pack `5852965e…be8ef337`, decreq `1340f8cc…fbe2967`, H01 `eb087464…22553`
- WS205 base preserved; E02/G04 engine-core BLOCKEDs carried forward untouched.

## Work Completed

- Fresh Oracle verification + semantic equivalence proofs for the B01
  (Essence Warden) and E01 (Grizzly Bears) singleton corrections.
- 17 legal Commander deck constructions (15 setup + E02/G04 deck spares),
  all import-PROVEN in-engine (99+1, `ok` 4/4 seats).
- Qualification-only opening-hand probe + setup driver (`ws207-setup-v1`)
  with explicit per-game Rules-seed binding before `start/init`
  (production session untouched).
- WS208/WS212 impact adjudication: RandomUtil-only evidence superseded;
  deal-RNG discrimination experiment (Rules RNG drives the native shuffle);
  triple-JVM reproduction of a rare opening.
- Seed discovery over fixed recorded ranges (≈5,900 fresh-JVM probes):
  15/15 setup constructions hold an explicit-Rules-seed opening.
- Native setup-run + twin replay (500 decisions, generic boundary only) for
  all 15: 15/15 twin stream matches, 15/15 binding provenance.
- Sealed overlay/catalog/matrix/validation + successor spec; manifests resealed.

## Terminal setup classification (denominator 15; H01 one slot)

QUALIFIED_SETUP_AVAILABLE (5): A03 (9788), C01 (10704), C03 (11412),
D06 (11912), F01 (13405) — neutral predicates met natively, behavior cards
held with opening presence proven, twin match, binding proven.

UNKNOWN (8): A04 (5-mana enchantment beyond ~turn-3 budget), B01 (native
Warden cast proven offset 246; full five-Warden neutral unassembled),
E01 (Grizzly Bears undrawn), G02/G03 (12-mana Ghalta unreachable in budget;
ledger prelude unproven, zero injection used), H01 slot aggregate (CF/NH
pre-boundaries QUALIFIED 16238/16859; binding HF ordering 15258 missing
Humility in budget), I01 (Bear undrawn; Aura-controller question flagged),
J02 (Delina 5-mana beyond budget).

BLOCKED (2, carryover): E02, G04 (engine core; WS205).

`BEHAVIOR_CREDIT_CHANGE = 0`. `FULL107 = NOT_RUN`.

## New Findings

1. Explicit Rules-seed binding controls the native initial shuffle
   (DIRECTLY_VERIFIED discrimination + 3/3 reproduction); RandomUtil-only
   seeds do not (WS208 confirmed). All WS207 catalog seeds are explicit.
2. 500 native decisions ≈ 3 turns in 4-player Commander: permanents costing
   5+ mana (DS, Delina) or 12 (Ghalta) cannot assemble; 1–3 mana setup
   assembles when drawn. Budget policy is now evidence-based.
3. H01 joint openings are rare (~0.3–0.5%), assemblable with recorded
   extensions — not structurally excluded.
4. B01's native Warden cast stranded mid-stack at the uniform stop:
   setup boundaries must account for stack resolution, not just battlefield.
5. I01 WS90 Aura-controller value (P0) disagrees with Rules expectation
   (P1); flagged unmaterialized for successor adjudication.

## Changes

New package `qualification/ws207-xmage-qualified-scenario-setup/` only
(probe + setup driver + decks/prefs tooling + orchestrator + seal + tests +
15 per-construction evidence namespaces + 8 top-level evidence files).
No production, engine, WS204/WS90/WS205, or config mutation. `db/` caches
untracked, never committed.

## Tests / Evidence

- No-JVM tests: 51 passed (deck legality, prefs hold-invariants, Oracle
  constants, scan determinism rules, seed-binding regression incl.
  production-untouched + no-TestPlayer).
- WS205 driver tests (unchanged): 75 passed (subset sanity, pre-existing path).
- Deck validation: 17/17 constructions import `ok` in fresh JVMs.
- Opening scans: ≈5,900 fresh-JVM probes, explicit binding, recorded criteria.
- Setup runs: 15 primary + 15 twin fresh JVMs; 15/15 twin matches; 15/15
  binding provenance; 7 QUALIFIED (5 slots + 2 H01 sub-boundaries).
- WS17 manifest coverage test: resealed per contract (12/12 green at seal).
- Evidence classes: run facts DIRECTLY_VERIFIED; Oracle texts
  EXTERNALLY_RULE_VALIDATED (Scryfall); structural/source facts CODE_DERIVED;
  setup fixtures MODELED (deterministic fixture construction, explicitly NOT
  representative randomness); behavior UNKNOWN stays UNKNOWN.

## Remaining Blockers

8 UNKNOWN setup slots (mechanism + seeds + precise reasons above; successor
S-SETUP-1/S-PILOT-2 specified); E02/G04 engine hooks (engine workstream);
no behavior qualification executed by design.

## Outputs

`qualification/ws207-xmage-qualified-scenario-setup/`: `SOURCE_LOCK.md`,
`AUTHORITY_ADJUDICATION.md`, `SETUP_OVERLAY.json`, `SEED_CATALOG.json`,
`SETUP_MATRIX.json`, `VALIDATION.json`, `FINAL_REPORT.md`,
`SUCCESSOR_SPEC.md`, `ws207_decks.py`, `ws207_setup.py`, `ws207_seal.py`,
`driver-java/`, `tests/`, `slots/<15 constructions>/`.

## Dependencies Unblocked

An execution-ready phased-pilot successor can consume the exact WS207 setup
overlay + seed catalog (5 qualified slots + 2 H01 sub-boundaries immediately
drivable; 8 UNKNOWNs with specified completion work).

## Exact Next Action

Final `ruff`/manifest verification, focused local commits, canonical
`safe_push` dry-run → terminal handoff (no raw push, no PR, no merge).

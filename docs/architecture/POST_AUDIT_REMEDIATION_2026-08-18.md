# Post-Audit Remediation – 2026-08-18

Baseline: `main` at `4ba9fd9f5e33d41ac263843e0b3731d45c7f6e81`.

This document records the implementation state of audit findings AUD-001 through AUD-012. It is technical status/provenance, not a canonical deck or inventory source.

## Current truth boundary

- Global active own decks: `korvold/current`, `rogshai/current`.
- Runtime-loaded deck: `rogshai/current`.
- Optimization target: `rogshai/current`.
- Korvold exact current 100-card operational baseline: unresolved; archived/historical lists must not be promoted automatically.
- Kaervek: frozen opponent-only.
- Historical Korvold allocations are not released as current free inventory.
- No canonical deck, inventory, purchase or opponent observation is modified by this remediation.

## Findings

| Finding | State | Implementation |
|---|---|---|
| AUD-001 competing scope truths | REMEDIATED | Explicit global/runtime/optimization/unresolved/frozen scope; legacy `active_own_decks` is runtime compatibility only. |
| AUD-002 candidate repository not fully deck-scoped | REMEDIATED TO CURRENT OPERATIONAL BOUNDARY | Deck-scoped eligibility/availability exists; unresolved Korvold is omitted fail-closed. Runtime service remains single-loaded until a verified Korvold baseline exists. |
| AUD-003 physical candidate provenance gap | REMEDIATED ADDITIVELY | Candidate-pool, candidate and variant provenance identities bind inventory/allocation/eligibility hashes without replacing RunIdentity. |
| AUD-004 dead External-XMage runner | REMEDIATED | Real B3 JSONL process regression replaces missing Phase-8.5.1 runner. |
| AUD-005 pre-B3 current provider truth | REMEDIATED | `config/rules_engines.json` is current B3 truth; J-P3 provider decision remains historical. |
| AUD-006 duplicate generic quality gates | REMEDIATED | CI owns generic quality; J-FINAL/J-P6/Optimizer/Release retain semantic or packaging-specific gates. |
| AUD-007 stale J-FINAL RogShai-only global semantics | REMEDIATED | Semantic current-runtime acceptance; global ownership no longer inferred from runtime loading. |
| AUD-008 J-P6 holdout ambiguity | REMEDIATED | Smoke calls its caller-supplied path generic out-of-sample robustness and explicitly records sealed-holdout/confirmatory non-execution. |
| AUD-009 pin/input hardening | REMEDIATED FOR ACTIVE PATHS | Active actions are immutable SHA-pinned; XMage input requires a full 40-hex commit and resolved checkout identity. |
| AUD-010 historical automatic triggers | REMEDIATED | Forge J-P3C and J-P6 performance evidence are manual-only; historical evidence is retained. |
| AUD-011 standalone ensemble hash | REMEDIATED | Ensemble matchup/report/robust-upgrade evidence carries deterministic `ensemble_hash`. |
| AUD-012 release responsibility mixing | REMEDIATED | Release owns build/install/checksum/recovery/current-status evidence and no longer reruns full pytest. |

## Multi-deck boundary

The data/domain layer is now explicit about multiple globally active own decks, while the runtime is intentionally narrower. This is not a fabricated Korvold onboarding: until a verified current Korvold 100-card baseline is supplied by a higher-authority current source, `korvold/current` remains `unresolved_operational_baseline` and cannot be runtime-loaded.

The next safe onboarding step, after resolving that baseline, is to add its exact manifest/deck hash and then exercise the existing deck-scoped candidate/allocation APIs with two simultaneous runtime contexts. No archived Korvold list is an acceptable substitute.

## External-engine boundary

XMage B0–B3 are preserved. The real regression proves only the B3 surface:

- real deck import;
- Commander/Partner game construction;
- 2–5 player construction;
- real game start;
- bounded lifecycle.

It explicitly fails if legal-action enumeration, action submission, event logs, replay or deterministic seed control become advertised without a separately authorized later phase. `NO_PROVIDER_READY` remains true.

## Evidence and holdout boundary

- Structural results remain `structural_model_estimates`.
- Tactical Oracle is not external-rules-engine evidence.
- J-P5 sealed holdout artifacts remain immutable historical evidence.
- Normal acceptance does not consume the sealed Optimizer-v2 holdout or confirmatory partition.
- Recommendations remain non-applying; canonical deck mutation requires separate explicit user authorization.

## Cleanup decisions

No repository file was deleted solely because it was old or duplicated. Historical J-P3/J-P5 evidence remains provenance. Release archive types were retained because the audit did not establish a safe consumer-independent deletion case. Duplicate rule fixtures likewise remain until a complete reference audit proves a safe consolidation.

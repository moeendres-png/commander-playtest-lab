# AF11 — Coordinator adjudication: single-provider topology (XMage)

Date: 2026-10-09. Authority: Coordinator, AGENTS.md §8 (Owner delegation). The Owner released
this change explicitly in the session ("AF11-Assembler-Änderung freigegeben").
Machine record: `AF11_COORDINATOR_ADJUDICATION.json` (this directory).

## Gate

AF11 `INTEROP_LICENSE_TOPOLOGY`: "Actual integration topology satisfies WS-09; Forge remains a
genuine separate process/service" (`architecture_freeze_gate_catalog_v2.json`). The WS-09
handoff text is not in the repository; its recoverable semantics are G12 `INTEROP_LICENSE`
(`qualification/obligations/FULL_RULES_REQUIREMENTS_CONTRACT_v1.json`): technical
interoperability and licensing compatibility for the actual integration/distribution model,
with Forge across a genuine separate-process/service boundary.

## Why it was UNKNOWN

The facts held in every epoch, but the policy question was open: in the dual-candidate
topology one adapter would have served two decision-identity shapes. The readiness records
(`XMAGE_FREEZE_READINESS.json` AF11) named the missing proof: a single-provider topology,
recorded with its licence topology and process boundary, and AF11 re-verified against it.
The Owner selected XMage (ADR `docs/engine_strategy_20261009/ENGINE_STRATEGY_ADR.md`). The
selection took effect at sealed epoch `8398b69bc6a9-8a004769ee19`, where XMage passes AF00–AF10.

## Measured facts

| Fact | Source |
|---|---|
| XMage driven as an external JVM over stdin/stdout JSONL; adapter `engine-bridge/src/main/java/org/commanderlab/xmage` | runtime identity, every epoch |
| No engine code in the Lab process | assembler embedded-engine check |
| XMage is MIT | `LICENSE` at the pin; `config/rules_engines.json` |
| Bridge runtime classpath: 28 jars, all MIT, Apache-2.0, BSD-3-Clause, ISC, MPL-2.0 OR EPL-1.0 (h2), or EPL-2.0 (JUnit); no GPL/LGPL/AGPL | `engine-bridge/target/cp-wsr22.txt`, POM/manifest licence fields |
| Lab is `LicenseRef-Proprietary` | `pyproject.toml` |
| Forge (GPL-3.0) runs only as its own process (`forge-protocol2-bridge`) | runtime identity |

## Decisions

1. **Separate-process topology: satisfied.** The selected provider is reached only through an
   external process.
2. **Provider-specific decision-identity shim: satisfied.** With one provider the adapter serves
   one shape. The shim carries only the provider's own published identity (AF04 PASS). It
   reconstructs no legality and fabricates no option.
3. **Provider licence compatibility: satisfied.** MIT permits use, modification and
   redistribution in proprietary software with the notice included. The classpath carries no
   strong copyleft.
4. **Forge separate process: satisfied.** Forge is not part of the production integration. As
   a bounded reference it runs only as its own process. No Forge code is ported. The D17
   in-JVM residual risk stays **not accepted**.

## Conditions

- Any distribution of the production artifact ships the XMage MIT notice and the third-party
  notices of every jar on the provider classpath.
- Any classpath change invalidates this adjudication. The assembler reports AF11 UNKNOWN until
  the inventory is re-adjudicated.
- No Forge code enters the Lab, the XMage fork or a production artifact without a new Owner
  licence decision.

## How the verdict is derived

`scripts/assemble_current_boundary_evidence.py` `_af11_measure` / `_af11_adjudication_issues`:

- **FAIL** when a measured technical fact is violated, even if this record exists.
- **PASS** only for the selected provider, and only when all of the following hold:
  - every fact holds;
  - this record validates against the source lock: provider and Lab licences, the four
    decisions, the Forge role, D17 not accepted;
  - the effective epoch is sealed with AF00–AF10 PASS;
  - this run's provider classpath equals the inventory exactly.
- **UNKNOWN** in every other case, including Forge.

Red controls: `tests/qualification/test_current_boundary_assembler_integrity.py`.

## Not claimed

- Architecture Freeze, which is a separate Owner decision.
- The Production Repository, which has not been created.
- A change to the runtime manifest: `provider_decision` stays `NO_PROVIDER_READY` until a
  Freeze workstream records it.
- A legal opinion. An external legal review before commercial distribution is an Owner
  decision.

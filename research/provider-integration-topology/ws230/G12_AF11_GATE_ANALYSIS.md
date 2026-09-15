# G12 / AF11 Gate Analysis (actual authority + what PASS needs)

Evidence class: `CODE_DERIVED`. Current verdicts (WS226, unchanged by WS230): **G12 UNKNOWN (both XMage and Forge), AF11 UNKNOWN (all candidates)**. No PASS claimed or manufactured.

## 1. Actual authority (reconstructed)

- **G12** (`FULL_RULES_REQUIREMENTS_CONTRACT_v1.json`): "technical interoperability and licensing compatibility for actual integration/distribution model." Required, all production evidence blocked until PASS (via G13 rollup).
- **AF11** (`architecture_freeze_gate_catalog_v1.json`): "Actual integration topology satisfies WS-09; Forge remains a genuine separate process/service." Required; `NOT_APPLICABLE` invalid.
- **G↔AF relation** (`G_AF_MAPPING.json`): G12/AF11 share one direct bundle with **zero fixtures** ("same-concern-no-fixtures"). The join is explicit in `EVIDENCE_JOIN_CONTRACT.json`, not via fixture coverage. Symmetric bar: "Production topology unselected ⇒ UNKNOWN for all (symmetric rule: the same 'actual topology' standard applies to every candidate)."
- **WS-09 content**: canonical handoff bytes unrecovered (only the SHA in `WS17_SOURCE_LOCK.json`). The operative WS-09 rule surviving in normative text is: *Forge must remain across a genuine separate-process/service boundary* (G12 semantics line; AF11 description; `integrations/forge/README.md`; `docs/engine_setup.md`). WS230 claims nothing stronger about WS-09.
- **Supporting vs satisfying** (WS226): WS217/WS227 separate-process seam proof is *supporting, not satisfying* evidence for AF11. Forge AF11 reason string: "Separate-process boundary preserved as positive; gate needs declared production topology (same bar as XMage)."

## 2. Why PASS is impossible before provider selection (answer to the topology-vs-selection question)

The gate phrase is "ACTUAL integration/distribution model." An actual model exists only when a provider is selected AND a topology for it is declared (local child vs localhost service vs container vs sidecar — see `TOPOLOGY_OPTIONS.json`). Until then there is no actual model whose interoperability + licensing compatibility can be proven. Therefore:

- **G12/AF11 cannot reach PASS before provider selection.** This is structural, not a backlog accident. WS230 records it explicitly.
- Per-candidate admissibility (`XMAGE_ADMISSIBLE_TOPOLOGY`, `FORGE_ADMISSIBLE_TOPOLOGY`) CAN be derived now (done: child/localhost/container/sidecar admissible per candidate; Forge in-process forbidden; remotes not cleared). Admissibility ≠ PASS.

## 3. Exact gate transition that allows later qualification

For the chosen candidate, a topology-qualification successor MUST present, per declared topology:

1. **Declared model record**: candidate + topology + IPC + source/build identity (both identities for Forge) + distribution model + license-obligation record (see `TOPOLOGY_OPTIONS.json` rows; license matrix `LICENSE_TEXT_SUPPORTS_MODEL` + legal-review receipt).
2. **Runtime interoperability proof**: AF01 handshake PASS on that exact topology + at least one full game lifecycle per mandatory cardinality on that topology + clean shutdown/relaunch (no stale state across games).
3. **Isolation proof**: crash/timeout/desync/orphan negatives on that topology (see `TOPOLOGY_RUNTIME_TEST_PLAN.json`); Forge: fresh-JVM-per-game + SHA binding + single-flight evidence; XMage: fresh-JVM (full-game lane) evidence.
4. **Hidden-info boundary evidence**: actor-scoping re-proven through the deployed IPC (no new leakage via service/container/sidecar plumbing).
5. **License-compatibility record**: corresponding-source availability + notice placement for the distributed artifact (Forge container/sidecar); MIT attribution for XMage; legal-review sign-off recorded (not a code PASS, a review receipt).
6. **Forge-only**: demonstration that the deployed artifact is a genuine separate process/service (OS-process boundary, own lifecycle, kill-the-child-survives-the-parent test, no in-process calls).

Only then may G12/AF11 move UNKNOWN → PASS for that candidate/topology. Any other candidate/topology stays UNKNOWN. No global PASS from one topology's proof.

## 4. AF11 vs G12 split (why both exist)

- AF11 is candidate-scoped and Forge-specific in its second clause (the separate-process rule binds Forge even if XMage were selected — a selected XMage model must still keep any Forge differential backend across the boundary).
- G12 is admission-scoped (no production game evidence counts until the actual model's interop+licensing is proven).
- A successor satisfies both with one evidence bundle referenced from both gates (the WS226 direct-bundle join already anticipates this shape).

---
name: failure-classification
description: Classify a failure into one canonical class with evidence, never upgrading UNKNOWN without proof.
---

# Failure Classification

Canonical classes: `ENGINE_DEFECT`, `PROVIDER_ADAPTER_DEFECT`, `HARNESS_DEFECT`,
`FIXTURE_DEFECT`, `EVIDENCE_PIPELINE_DEFECT`, `INFRASTRUCTURE_DEFECT`,
`UPSTREAM_DEFECT`, `UNKNOWN`.

## Procedure

1. Collect the exact failing command, exit status, log excerpt, and source SHA.
2. Separate layers: Rules Core semantics, provider adapter translation, harness and
   runner behavior, fixture and test expectations, infrastructure (CI, runners,
   caches, network), upstream dependencies.
3. Assign the most specific class supported by direct evidence. Prefer the
   deterministic helper `tools/foundry/cluster_failures.py` to group repeated
   signatures before judging causality.
4. Never convert `UNKNOWN` into a more specific class without evidence. Ambiguous
   engine-vs-adapter-vs-harness causality stays `UNKNOWN` with the competing
   hypotheses listed.
5. Record the classification, the evidence for it, and what single observation would
   discriminate the remaining hypotheses.
6. Reaching and persisting a technical root-cause result is the job, not an
   escalation. A classification is a technical decision when existing project
   policy determines the allowed semantics; only a Rules, evidence-policy,
   architecture, scope, provider, or freeze question becomes an `AUTHORITY_GATE`.
   Persist the result in `.foundry/WORKSTREAM_STATE.yaml` (`root_cause_class`,
   `first_failing_boundary`, `technical_decisions`) and continue.

## Rules

- Classification assists reasoning; it never grants Qualification PASS.
- Cluster membership is not a root cause. Each cluster keeps its original record IDs
  and raw evidence references.

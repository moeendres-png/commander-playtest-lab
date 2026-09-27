# Differential rule cases

- `rules_cases.json` contains the original Phase-6 external release-gate smoke cases.
- `project_critical_interactions.json` contains the Phase-8 catalog with 73 project-critical interactions.

The Phase-8 catalog is first evaluated by the bounded local tactical oracle. It is then sent to an installed XMage or Forge JSONL bridge when configured. Only matching external observations receive `rules_engine_validated` status.

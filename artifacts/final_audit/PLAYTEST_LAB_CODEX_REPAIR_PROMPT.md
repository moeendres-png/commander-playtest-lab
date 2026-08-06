# CODEX PROMPT — Remaining external-engine, QA and optional infrastructure work

Work in the final `commander-playtest-lab` repository artifact. Start by verifying that HEAD descends from audited code commit `f5a17fe` and package version `1.10.2`. Create a new branch; do not change canonical deck lists, inventory, allocation or purchases.

## A. External engine (`BLOCK-EXT-001`)

1. Install/verify Java and Maven or Docker in a networked environment.
2. Re-verify current official XMage and Forge releases rather than trusting historical pins.
3. Build or supply a real provider-specific JSONL bridge compatible with protocol 1.0.0.
4. Execute real gates: process start, provider/version handshake, deck import, four-player Commander, legal actions, action submission, illegal-action rejection, event log, replay, Partner, Commander Tax, Commander Damage, stack and priority.
5. Never promote Tactical Oracle or mocks to `external_rules_engine`.
6. Add regression/integration tests and retain raw external logs.

## B. Development and security tools (`BLOCK-QA-001`)

Install pinned, compatible versions and execute with recorded exit codes:

```bash
ruff check .
ruff format --check .
mypy src/commander_lab
pytest -q
python -m compileall -q src tests
pip check
pip-audit
```

Run Hypothesis state-machine tests, mutmut or equivalent mutation testing, a secret scanner, CycloneDX SBOM generation and license review. Do not label an unavailable tool as passed.

## C. Parquet (`BLOCK-PARQUET-001`)

Decide whether Parquet is a required supported surface. If yes, add a pinned `pyarrow` or `fastparquet` dependency and a fresh-environment 1,000-row write/read round-trip test. If no, remove or clearly mark the path optional.

## D. MCP (`BLOCK-MCP-001`)

Only if the user confirms MCP is required, add an MCP transport that reuses the existing 92-tool registry. Test initialize/list/call/error lifecycle and preserve FastAPI behavior. Do not call the current HTTP server an MCP server.

## Required commits

1. External engine/bridge and tests.
2. Static/security/fuzz/mutation fixes.
3. Optional Parquet/MCP changes, separately.
4. Documentation, manifests and Drive handoff.

## Acceptance

- No critical or high bug remains.
- Full suite passes with only explicitly justified external skips.
- External claims are backed by a real provider process.
- Reproducibility and seed/log hashes remain unchanged for fixed inputs.
- Wheel/source/bundle/repository artifacts are built and uploaded; Drive round-trip hash verification passes.

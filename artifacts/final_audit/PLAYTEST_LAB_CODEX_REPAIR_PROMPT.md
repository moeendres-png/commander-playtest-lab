# CODEX PROMPT — Remaining external-engine, QA and optional infrastructure work

Restore the final `commander-playtest-lab` repository from one of these verified Drive sources:

- Stable `00_LATEST` repository ID: `1QrPVlbP4CNfvwtzl0dv6lVXmG5ayHSA5`
- Final-audit repository ID: `1nK9kIeJic7A93wBUkG-Lam3KQH71fLkw`
- Final-audit bundle ID: `1pchdkQACw7k_vCLXYUICWZSfhuyBwRKV`
- Final-audit source ID: `1Xu-N9NUyeyaEqYNJYYytwqkZkmccTJy1`

Verify SHA-256 against `FINAL_SHA256SUMS.txt`. Start from commit `9721332308dd058bf4aa92ad8be66a9733a5ccd7` or a docs-only descendant that still contains audited code commit `f5a17fe6a8f8baf2f1793f782445f4da2a3e75d6`. Package version is `1.10.2`. Create branch `codex/post-final-audit-open-blockers`. Do not change canonical deck lists, inventory, allocation or purchases.

## A. External engine — `BLOCK-EXT-001`

1. Use a networked environment with Java plus Maven or Docker, or verified offline engine sources/binaries.
2. Re-verify current official XMage and Forge releases; do not trust historical pins without source verification.
3. Build a real provider-specific JSONL bridge compatible with protocol 1.0.0.
4. Execute real gates: process start, provider/version handshake, deck import, four-player Commander, legal actions, action submission, illegal-action rejection, event log, replay, Partner, Commander Tax, Commander Damage, stack and priority.
5. Never promote Tactical Oracle, fake bridges or fixtures to `external_rules_engine`.
6. Add integration/regression tests and retain raw provider logs and replay evidence.

## B. Static, security, fuzz and mutation audit — `BLOCK-QA-001`

Install pinned compatible tools and record every command and exit code:

```bash
ruff check .
ruff format --check .
mypy src/commander_lab
pytest -q
python -m compileall -q src tests
pip check
pip-audit
```

Add Hypothesis state-machine tests, mutation testing, secret scanning, CycloneDX SBOM generation and license review. Treat unavailable tools as blocked, never passed. Investigate the current global-environment `pip check` Pillow/MoviePy conflict in an isolated project virtual environment before attributing it to this package.

## C. Parquet — `BLOCK-PARQUET-001`

Decide whether Parquet is a supported surface. If yes, add a pinned compatible `pyarrow` or `fastparquet` dependency and a fresh-environment 1,000-row write/read round-trip test. If no, explicitly mark Parquet optional and ensure callers receive a structured dependency error.

## D. True MCP transport — `BLOCK-MCP-001`

Only implement after explicit user confirmation. Reuse the existing 92-tool registry and test initialize/list/call/error lifecycle without changing FastAPI behavior. Do not call the existing HTTP Function Tool server an MCP server.

## Required commits

1. External engine/bridge and tests.
2. Static/security/fuzz/mutation fixes.
3. Optional Parquet changes.
4. Optional MCP changes, separately and only after approval.
5. Documentation, manifests and Drive handoff.

## Acceptance

- No critical or high product bug remains.
- Full test suite passes with only explicitly justified external skips.
- External claims are backed by a real provider process and raw evidence.
- Fixed inputs retain identical deterministic seeds, results and event-log hashes.
- Repository, bundle, source, wheel and validation artifacts are built.
- Work performs a genuine Drive upload/re-download SHA-256 round-trip.

# Phase 12.19 – Quality, Security and Performance

## Status

`quality_security_performance_completed_with_limitations`

The complete project suite passed with **266 passed, 1 skipped, 0 failed**. The single skip is the real external-provider differential test, which remains blocked because no verified XMage or Forge runtime is available.

## Real tool execution

| Check | Result |
|---|---|
| `pytest -q` | `passed` — 266 passed, 1 skipped, 0 failed |
| `python -m compileall -q src tests` | `passed` |
| `git diff --check` | `passed` |
| `git fsck --full` | `passed` |
| `pip check` | `failed` — global `moviepy` requires Pillow <12, while the runtime has Pillow 12.2.0; not introduced by project dependencies |
| Ruff / mypy / Hypothesis / mutmut / pip-audit / CycloneDX / pip-licenses | `blocked` — package index unavailable/incomplete |

The deterministic property, mutation-guard, fuzz and regression fallback group passed 14/14. It is evidence for project regressions, but it is not represented as actual Hypothesis or mutmut execution.

## Security and supply chain

- Internal tracked-file secret scan: 720 text files, 0 findings.
- Fallback CycloneDX-shaped SBOM and license inventory generated from `importlib.metadata`; official CycloneDX and pip-licenses runs remain blocked.
- Direct runtime dependency lock captured in `requirements/runtime.lock`.
- Current upstream quality-tool pins captured separately; they were not installed or claimed as executed.
- CI now contains a pinned security job for pip-audit 2.10.1, cyclonedx-bom 7.3.0 and pip-licenses 5.5.5 in a network-enabled runner.

## Performance

- Structural goldfish: 1 game 0.030 s; 100 games 1.179 s; 1,000 games 10.585 s.
- Four-player 50 games: one worker 3.413 s; two workers 57.841 s in this container.
- Mulligan 500×2 policies: 4.331 s; paired 50-game comparison: 5.599 s.
- MCP initialize and tools/list passed in-process.
- XMage and Forge timings are `blocked`; Parquet is `unused`.

No optimization was applied because the measured two-worker path was substantially slower and no semantic-preserving improvement was demonstrated.

No canonical deck, inventory, or allocation data was changed.

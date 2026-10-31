"""#992: the sequential runner must not retain full batch records in memory.

Discriminating test, Python-only, no JVM: a scripted batch runner feeds
``run_sequential_blocks`` 800 seeds of records whose ``result_payload`` carries
a 50 KB padding string (standing in for the real multi-MB transcript that
``aggregate_comparison`` never reads). ``tracemalloc`` snapshots at each block
entry show the retained heap:

- BEFORE the fix the snapshots grow linearly with the retained records
  (~80 MB over 160 looks) and the memory assertion below FAILS.
- AFTER the fix (records slimmed at ingest to the aggregate inputs only)
  the snapshots stay flat (small constant per record) and the test PASSES.

The aggregate-equality assertion guards the slimming: the sequential run's
comparison must stay byte-identical to a direct ``aggregate_comparison`` over
the full records, so a future aggregate input added to the slim whitelist
(or removed from it) fails here instead of silently changing verdicts.
"""

from __future__ import annotations

import tracemalloc

from commander_lab.engine.rules.full_game_comparison import (
    aggregate_comparison,
    plan_comparison_cases,
    sequential_look_alphas,
    sequential_look_seed_counts,
    sequential_looks_planned,
)
from tests.unit.test_sequential_deck_comparison import (
    _alternating,
    _records_for,
    _report,
    _script_module,
    _spec,
)

PADDING = 50_000  # bytes of fake transcript per record
SEEDS = tuple(range(1, 801))
LOOK_EVERY = 5
# The bound proves the transcript bulk is dropped, not that retention is zero:
# each slim record still costs ~4.4 KB (two pydantic models + small payload),
# so 1600 records retain ~7 MB by design. Measured: pre-fix 86.3 MB,
# post-fix 7.0 MB. The threshold sits between them with margin on both sides.
MAX_GROWTH_BYTES = 10_000_000


class _PaddedBlocks:
    """Fake batch runner: padded records + a tracemalloc snapshot per block.

    Deliberately retains NOTHING: retaining the padded records here would
    measure the test's own heap, not the runner's. The byte-identity
    reference is built separately from unpadded records (the aggregate
    never reads the padding, so the dumps must match).
    """

    def __init__(self) -> None:
        self.snapshots: list[int] = []

    def __call__(self, cases):  # type: ignore[no-untyped-def]
        current, _peak = tracemalloc.get_traced_memory()
        self.snapshots.append(current)
        padded = []
        for record in _records_for(cases, _alternating):
            assert record.result is not None
            padded.append(
                record.model_copy(
                    update={
                        "result": record.result.model_copy(
                            update={
                                "result_payload": {
                                    **record.result.result_payload,
                                    "padding": "x" * PADDING,
                                }
                            }
                        )
                    }
                )
            )
        return _report(padded)


def test_sequential_runner_memory_stays_flat() -> None:
    tracemalloc.start()
    try:
        cli = _script_module()
        spec = _spec(SEEDS, rotate=False)
        cases = plan_comparison_cases(spec)
        blocks = _PaddedBlocks()
        comparison, combined, sequential = cli.run_sequential_blocks(
            spec, cases, blocks, look_every=LOOK_EVERY
        )
    finally:
        tracemalloc.stop()
    looks = sequential_looks_planned(len(SEEDS), LOOK_EVERY)
    assert len(blocks.snapshots) == looks  # no early stop: all 800 seeds played
    assert sequential["looks_used"] == looks
    assert sequential["stopped_early"] is False
    assert combined.total_cases == 1600
    growth = blocks.snapshots[-1] - blocks.snapshots[0]
    assert growth < MAX_GROWTH_BYTES, (
        f"retained heap grew by {growth} bytes over {looks} looks "
        f"(first snapshot {blocks.snapshots[0]}, last {blocks.snapshots[-1]}); "
        "run_sequential_blocks still retains full records"
    )
    # Byte-identical aggregate: sequential slim path == direct full aggregate.
    # Built from unpadded records: the aggregate never reads the padding.
    reference = aggregate_comparison(
        spec,
        _report(_records_for(cases, _alternating)),
        significance_level=sequential_look_alphas(
            0.05, sequential_look_seed_counts(len(SEEDS), LOOK_EVERY)
        )[-1],
    )
    assert comparison.model_dump(mode="json") == reference.model_dump(mode="json")

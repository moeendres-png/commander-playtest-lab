from __future__ import annotations

from .models import (
    CandidateValidationReport,
    DeckCandidateSet,
    PreSimulationInvariantReport,
    SimulationCandidateQueue,
    SimulationCandidateQueueEntry,
)


def build_simulation_queue(
    candidate_set: DeckCandidateSet,
    validation_report: CandidateValidationReport,
) -> tuple[SimulationCandidateQueue, PreSimulationInvariantReport]:
    by_id = {candidate.candidate_id: candidate for candidate in candidate_set.candidates}
    queue_entries: list[SimulationCandidateQueueEntry] = []
    for result in validation_report.results:
        if result.hard_validity != "PASS" or result.duplicate_identical_deck:
            continue
        candidate = by_id[result.candidate_id]
        assert candidate.deck_hash is not None
        queue_entries.append(
            SimulationCandidateQueueEntry(
                candidate_id=candidate.candidate_id,
                candidate_label=candidate.candidate_label,
                deck_hash=candidate.deck_hash,
                commander_names=candidate.commander_names,
                mainboard=dict(candidate.mainboard),
                physical_printings=candidate.physical_printings,
                source_candidate_set=candidate_set.candidate_set_id,
                source_candidate_ids=result.source_candidate_ids,
                current_control=candidate.current_control,
                design_policy=candidate.design_policy,
                design_philosophy=candidate.design_philosophy,
                design_hypothesis=candidate.design_hypothesis,
                packages=candidate.packages,
                metadata=dict(candidate.metadata),
                diagnostic_metadata=dict(result.diagnostic_metadata),
            )
        )

    input_count = validation_report.hard_valid_unique_count
    output_count = len(queue_entries)
    if input_count != output_count:
        raise ValueError(
            "lossless candidate handoff violated: "
            f"hard-valid unique input={input_count}, queue output={output_count}"
        )
    expected_ids = {
        result.candidate_id
        for result in validation_report.results
        if result.hard_validity == "PASS" and not result.duplicate_identical_deck
    }
    queued_ids = {entry.candidate_id for entry in queue_entries}
    every_queued = expected_ids == queued_ids
    if not every_queued:
        raise ValueError("lossless candidate handoff violated: candidate-id set mismatch")

    queue = SimulationCandidateQueue(
        source_candidate_set=candidate_set.candidate_set_id,
        input_hard_valid_unique_count=input_count,
        output_simulation_queue_count=output_count,
        candidates=tuple(queue_entries),
        lossless_handoff=True,
    )
    invariant = PreSimulationInvariantReport(
        candidate_set_id=candidate_set.candidate_set_id,
        input_hard_valid_unique_count=input_count,
        output_simulation_queue_count=output_count,
        lossless_handoff=True,
        every_hard_valid_unique_candidate_queued=every_queued,
        no_pre_simulation_heuristic_can_remove=True,
    )
    return queue, invariant


__all__ = ["build_simulation_queue"]

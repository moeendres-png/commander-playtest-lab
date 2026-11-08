# Decision-report storage

`pilot_decision_report._play` retained every complete observation and answer in a
list until the game ended. A six-player measurement accumulated several GiB of
Python request objects and required a controlled resource stop. Its incomplete
trace and unknown result are not successful full-game evidence.

The report now stores snapshots in a temporary SQLite sequence, compressing
individual JSON records. The existing summarizer reads that sequence directly.
Per-seat summaries use views of record indices, preserving indices relative to
each seat for cancellation attribution. Request payloads no longer accumulate
as live Python objects; indices, counters, individual decoded records, and the
runner's existing state still require memory. This is not a constant-memory
claim for the entire simulator.

Batches commit during recording, before summary generation, and on close. Normal
cleanup removes temporary storage after summarization, including the failed-game
path. Storage errors propagate instead of producing a partial success. Abrupt
process termination does not prove that the uncommitted tail was persisted.
This change does not add permanent raw-record retention to the CLI.

The append-only sink remains compatible with callers using an in-memory list.
Summary fields, per-card versions, seat counters, game outcomes and Rules Core
decisions are unchanged. The batch-per-JVM path retains its existing explicit
absence of per-decision measurement.

Validation:

- 81 guarded report/store/Any-ratchet tests passed. Controls include mixed seats,
  intervening choices and payment cancellation, snapshot isolation, last-batch
  persistence after close/reopen, indexed views, and cleanup after a game error.
- Ruff lint/format and strict mypy over 349 source files passed.
- Two complete public-precon games exercised the productive `_play` path with
  the disk sink, not an external `recording([])` helper. P4a/seed 1 completed
  2,897 decisions and P4b/seed 1 completed 3,009. Both semantic hashes and all
  global and per-seat report values match the existing recorded references;
  `pilot_s` timing is excluded from equality. No playing-strength or speed
  improvement is claimed.

Source locks, deck order and comparison results are in
`measurements-2026-11-05/decision-store-summary.json`. The pinned engine, bridge
JAR and pilot source are unchanged. Raw fixtures and measurement scripts remain
outside the repository. Local tests and game setup reject excluded collection
paths, including resolved symlinks.

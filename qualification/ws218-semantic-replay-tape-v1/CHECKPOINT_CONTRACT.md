# WS218 CHECKPOINT_CONTRACT

Checkpoints are evidence, never state injection. Each binds seed, RNG
calls, turn, phase/step (where stable), decision/event offsets, semantic +
public + principal digests (`TapeCheckpoint`; terminal adds seat-mapped
five-field outcomes). Capture points: initial (first native decision,
post-shuffle binding proof), per-step post (next pending pre-state or
terminal), terminal (result + outcomes). Replay starts from normal
construction and progresses by native decisions only. Forbidden (scanned,
absent): zone/life/counter/damage/ledger/stack/outcome writes,
`sa.resolve`/AbilitySub substitutes, snapshot restore. No future
snapshot/restore API is claimed or used.

Machine companion: `CHECKPOINT_CONTRACT.json`.

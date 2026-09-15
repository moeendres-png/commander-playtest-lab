# WS220 Foundry / OpenCode Audit

Questions: does the machinery improve correctness? where is overhead?
what can be delegated? what stays Coordinator-owned?

## Verdict: SUBSTANTIVE SAFETY, MEASURABLE OVERHEAD, KNOWN LEVERS

Safety that works: single-writer flock + 11-gate safe_push (only remote-write
path); schema-2.0 state with ancestry proofs; reference-root discipline;
drift_check as live gate; policy-stable/state-volatile split; skills lazy;
14/15 foundry-execution docs already on-demand. The 11 P1 findings above were
all expressible *because* the machinery preserves seals, locks, and
dispositions — the audit trail works.

Overhead (F-EFF-01, P3): ~33KB always-on core with acknowledged
implementer↔AGENTS↔ROUTING duplication (~2–4KB trimmable, cache-eligible
anyway). Real lever is dynamic context (/work+capsule, already built, 82%
structural win). Do NOT cut authority prose for savings.

Reliability gap (F-FOUNDRY-01, P2): resumption is well-specified but UNKNOWN
(no live trial, no committed token data, benchmark NOT_RUN). A 6.6M-line
project with procedural-only anti-rework guards needs one instrumented trial.

Writer-lock note: ~70 live worktrees make the exactly-one-owner gate
operationally brittle (safe refusals on multi-checked-out branches). Safe,
but expect friction; the merge train (S14) reduces it.

Pre-push hook is L3-partial by construction; real gates are safe_push +
branch protection — verify the latter are enabled on the remote (human step,
flagged in GITHUB_REMOTE_GATES as DOCUMENTED_HUMAN_ACTION_REQUIRED).

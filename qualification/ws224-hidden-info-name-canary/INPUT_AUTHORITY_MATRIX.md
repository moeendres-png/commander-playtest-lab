# WS224 INPUT_AUTHORITY_MATRIX

| Input | Authority | Role in WS224 | Trust basis |
|---|---|---|---|
| WS220 `FINDINGS.json` F-HIDE-02 + `BATCH2_NOTES.md` C2 | Coordinator-committed audit (`1a6ffcda`) | Defines the gap (UUID oracle name-blind) and the repair surface | `DIRECTLY_VERIFIED` (git-show object reads) |
| WS215 `HIDDEN_INFO_CARDINALITY` (+ 9985-frame UUID oracle) | Sealed qualification | Retained UUID dimension; both dimensions must be green | Provenance; re-proven live (WS224 Java UUID assertions + original test green) |
| WS218 `HIDDEN_INFORMATION_REPLAY` + sealed 2P–5P tapes + 19-case tamper matrix | Sealed qualification | Replay privacy baseline; tapes rescanned (structure), tamper diagnostics rescanned | Provenance; WS224 rescan evidence |
| `XmageFullGameStateRedactor` / `XmageFullGameActionProjection` / `XmageFullGameDecisionController` / `XmageFullGamePlayer` / `XmageFullGameSession` / `XmageFullGameJsonlBridge` | Current source (audit-base tree) | Leak-surface inventory S01–S06, S08–S11, S15–S16 | `CODE_DERIVED` + live negative proof |
| `full_game.py` policy/projection/transcript + `semantic_replay/*` | Current source | Surfaces S07, S09, S12–S14 | `CODE_DERIVED` + synthetic + live proof |
| `rogshai_current.json` / `ws215_lions.json` test decks | Pinned test fixtures | Live canary hosts (real-card identities); driver decklists | Test-only use; never production/user decks |
| 66 committed `primary.json` artifacts | Historical evidence | Read-only scan + disposition; never rewritten | Provenance only; classifications are WS224's |
| Engine-internal GameLog/stderr history | XMage internals | S16 | `UNKNOWN` (honest; sampled stderr clean) |
| Official CR/Oracle text | None consulted | No Rules question arose; no behavior changed | N/A (`BEHAVIOR_CREDIT_CHANGE = 0`) |

# XMage Full-Game Closeout

## Release contract

The implementation is mergeable only when all of the following are true on the final PR head:

- repository CI, Ruff, format, strict MyPy, full pytest, compile and security gates pass;
- Windows Runtime Hygiene passes;
- Core Workflow Acceptance passes;
- legacy External XMage Integration passes unchanged;
- dedicated XMage Full Game Conformance passes against pinned XMage commit `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`;
- a real four-player technical fixture reaches XMage Game Over in two fresh JVMs;
- same-seed semantic replay matches;
- hidden-information boundary verification passes;
- no fallback to Structural, Tactical, XMage AI, random or silent defaults is observed;
- no official gameplay evidence or sealed holdout is consumed;
- no canonical deck, inventory, allocation, purchase or opponent truth is changed.

## Evidence classification

All games executed by the release gate are `technical_conformance_only`. Their winners, turn counts or decisions are **not** deck-strength evidence and may not be consumed by an optimizer, challenger selection, holdout decision or canonical deck update.

## Post-merge closeout

After merge, both exact-main workflows must be verified against the merged commit:

1. `XMage Full Game Conformance` — real pinned-engine technical game-over/replay evidence.
2. `Exact Main Recovery` — source archive, wheel, git bundle, architecture artifacts, checksums and fresh-bundle-clone validation.

The final Drive copy must be the exact recovery/conformance output from the merged `main`, not a pre-merge branch artifact, and must be raw-read-back verified before the task is reported complete.

## Claims intentionally not made

- Bit-exact replay is not claimed merely because same-seed semantic replay passes.
- The full-game technical fixture is not an observed opponent deck.
- The migration does not prove pilot optimality.
- The migration does not turn Structural or Tactical outputs into empirical or external-rules evidence.
- A successful technical fixture does not authorize reuse of any previously consumed sealed holdout.

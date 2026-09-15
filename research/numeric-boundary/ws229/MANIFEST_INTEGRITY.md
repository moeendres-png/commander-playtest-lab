# WS229 MANIFEST_INTEGRITY (GREEN)

## Invariant

Same-commit qualification-manifest invariant (WS221 S4): a committed edit
to a seal-covered artifact must refresh its hash manifest in the same
commit.

## Assessment

WS229 touches NO file under `qualification/**`, no seal-covered artifact,
and no standing input:

- Implementation: `src/commander_lab/**`, `engine-bridge/**`.
- Tests: `tests/unit/**`, `engine-bridge/src/test/**`.
- Evidence: `research/numeric-boundary/ws229/**` (research namespace is
  outside both hash manifests by construction).
- Generated lane outputs (`artifacts/xmage-full-game/XMAGE_FULL_GAME_*`)
  are run-scoped strays, removed before the terminal commit (not sealed
  artifacts; the sealed records live in the evidence namespace).

Therefore no manifest refresh is required and none was performed
(no historical artifact altered, no file excluded, comparison logic
untouched).

## Proof (DIRECTLY_VERIFIED, terminal tree)

- `tests/qualification/test_ws17_qualification.py`: 12/12 PASS
  (byte hashes verify; coverage sets exact; negative control intact).
- `test_manifest_covers_post_ws17_seal_files`: PASS.
- `test_manifest_mismatch_is_rejected`: PASS.
- Standing/authority suites (`test_ws225_standing`, `test_ws222_authority`,
  `test_ws221_evidence_vocab` manifest rows): PASS.

MANIFEST_INTEGRITY = GREEN.

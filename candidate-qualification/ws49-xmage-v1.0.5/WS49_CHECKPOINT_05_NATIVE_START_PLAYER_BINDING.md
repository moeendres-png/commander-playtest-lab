# WS-49 CHECKPOINT 05 — NATIVE STARTING-PLAYER BINDING REMEDIATION

Status: **PERSISTED / NO PASS CREDIT GRANTED**

## Exact failure evidence

- provider head: `00505b17f1c08ecf32b17fa1dd073a242f7a84c1`
- workflow run: `34275581472`
- job: `102227651642`
- outcome: failure; `100/107` native setup-ready and `7/107` fail-closed

The build and bridge completed successfully before the probe.  Every failed
row was a NATURAL_GAME_START row:

- `PLAYER_COUNT_2P`, `PLAYER_COUNT_3P`, `PLAYER_COUNT_4P`, `PLAYER_COUNT_5P`
- `PILOT_MULLIGAN`, `WS05-CMD-MULL-2`, `WS05-CMD-MULL-4`

The first native decision was correctly emitted as a required
`choose_object` decision.  The provider rejected it because it incorrectly
expected canonical `P1..Pn` values as option IDs.  XMage correctly emitted
opaque player object IDs, with stable native labels `WS26 Seat 1..n`.

This is a provider semantic-selector defect, not a contract, build, or XMage
Rules result.

## Bounded remediation

The NATURAL_GAME_START selector now:

1. verifies the exact decision signature;
2. verifies the complete native offer set as labels `WS26 Seat 1..n` plus
   matching native metadata;
3. maps the immutable configuration datum canonical `P1` to native
   `WS26 Seat 1`; and
4. submits only the native option ID belonging to that validated offer.

It does not select by option position, UUID value, GUI default, AI, or a
fallback.  All mulligan choices remain required to match the immutable
explicit per-player plan.

## Source locks unchanged

- WS-47: `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8`
- WS-47 tree: `f596c54d2cb229b9827c6c94a278175e8312c65c`
- v1.0.5 SHA-256: `0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3`
- denominator: `107`
- XMage: `0c1f455ea8c8fa48ab9d638ad5068ec242800428`
- XMage tree: `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`

## Next automatic action

Run a fresh exact-head Full107 construction sequence.  G49-07 remains
`NOT_CLOSED`; G49-08 through G49-14 remain `NOT_RUN`.

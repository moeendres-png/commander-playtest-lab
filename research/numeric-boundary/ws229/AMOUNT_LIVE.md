# AMOUNT_LIVE (P-A2 live half: DIRECTLY_VERIFIED)

## 1. Live-callback traversal (XmageNumericDomainWs229Test)

`amountSmallAndLargeSpanSubmitInteriorValuesLive`: REAL `getAmount`
callbacks through the real bridge player + controller + native submission.

- Frame 1: `amount`, context `{numeric_min: 1, numeric_max: 5}`, zero
  options. Submitted 4. Callback returned 4.
- Frame 2: `amount`, context `{numeric_min: 1, numeric_max: 40}`, zero
  options. Submitted 18 (interior — unofferable under the old {1,20,40}
  collapse). Callback returned 18; engine consumed it.

## 2. Lab half (test_ws229_numeric_domain.py)

Benefit [1,5]->5, [1,40]->40; malformed fog (string/bool/float/missing/
reversed bounds) fail closed; non-integer pilot return fails closed.
Shared scalar path with announce_x (one chooser), so the live-callback
proof transfers by construction; the amount-framed malformed lane is
additionally pinned at transport
(`malformedScalarSubmissionsRejected`: "many" and 2.5 rejected, lawful 4
accepted and consumed).

## 3. Negatives (N-15)

Out-of-domain + malformed rows executed at controller transport,
projection, and Lab (see NEGATIVE_MATRIX_RESULTS).

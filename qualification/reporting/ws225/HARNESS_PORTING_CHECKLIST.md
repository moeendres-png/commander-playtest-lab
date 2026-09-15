# Harness-Porting Checklist (actionable; machine companion: HARNESS_PORTING_CHECKLIST.json)

For adding a future engine. Answer every item with the engine's own mechanism;
reviewers check answers against the stage contract, never against an incumbent
implementation. Minimizes accidental XMage-shaped assumptions (H12).

- **H01 — RSP interfaces.** Named adapter command, protocol version, schema
  digests; handshake transcript location; truthful capability advertisement
  and how misadvertisement fails closed.
- **H02 — Projections.** Seat/actor projection function; per-principal
  redaction rules; metadata channels enumerated as the leakage boundary;
  honeycard sentinel placement.
- **H03 — Decision families.** Full discretionary-family inventory
  (priority, target, choose-object, target-amount, mulligan, choose-use,
  choice, pile, mana-payment, announce-x, multi-amount, replacement-effect,
  trigger-order, choose-mode, choose-ability, declare-attacker,
  declare-blocker, concede — or engine equivalents) with the engine seam per
  family; the seven prohibited shortcuts proven unsatisfying.
- **H04 — Identity binding.** Engine commit/tree/version + adapter
  commit/tree + license SPDX + blob digests + card-DB/Oracle snapshot
  identity in one SOURCE_LOCK record; rebuild procedure.
- **H05 — Rules RNG.** Named algorithms; root-seed input; Rules-vs-pilot
  attribution log (RulesRngTape shape); deterministic seed-derivation rule;
  explicit-seed fail-closed behavior.
- **H06 — Hidden-info proof.** Actor-scoped observation proof per hidden zone
  (hand, library, face-down, manifest); reveal/look audience logs; transcript
  redaction check; honeycard negative runs.
- **H07 — Process isolation.** One game per clean process; fresh-process
  procedure; no shared mutable state across games; atomic artifact writes;
  process identity excluded from semantic hashes.
- **H08 — Replay hooks.** Decision/event/RNG tape schemas; checkpoint/restore
  points; clean-process replay consumer; divergence taxonomy; tamper matrix
  (dropped/reordered/mutated/forged tape actions fail closed and leak-free).
- **H09 — Fixture driving.** RUN_FIXTURE mapping per category; frozen seed
  policy (424242 + distinct-seed twins); actor/viewer binding; artifact-hash
  capture.
- **H10 — Fail-closed wiring.** Unknown/unsupported decisions, stale
  revisions, malformed requests, and over-scope shapes fail closed with named
  errors — never default, skip, or random.
- **H11 — Evidence sealing.** Per-fixture rows (verdict + evidence_class +
  reason + artifact_hashes) under evidence-vocab-v1; legacy prose only via
  versioned map; manifest-hash refresh in the same commit as any
  seal-covered edit.
- **H12 — De-XMage-shaping review.** Confirm no XMage Java API names, Forge
  controller class names, UUID-format mandates, single-engine RNG method, or
  single-engine callback taxonomy leaked into the adapter contract.

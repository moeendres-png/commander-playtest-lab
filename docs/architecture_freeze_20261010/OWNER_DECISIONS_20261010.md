# Owner decisions for the Architecture Freeze — 2026-10-10

Status: **RECORDED, FREEZE NOT YET SIGNED.** The Owner made these decisions in the
Coordinator session on 2026-10-10. The Coordinator records them here. They take effect
as stated below. The Freeze itself is claimed only when the Owner signs the final ADR
(§ Signature). Until then `ARCHITECTURE_FREEZE = NOT_CLAIMED` and
`provider_decision = NO_PROVIDER_READY`.

Refs #662, #255.

## D1. Rules core and production provider: XMage

XMage is the single Rules core and the production provider, provided both
preconditions below hold. Forge stays a reference column only.

Preconditions, both met:
- (a) PB-03 on current `main` confirms freeze eligibility. Run 38066157470 on `main@f881d56f`
  produced sealed epoch `f881d56fb33f-aef9f7f660b4`, which is eligible.
- (b) The protocol schema identity is bound to the real blob (#693).

## D2. D17 in-JVM residual risk: accepted as a bounded, compensated limitation

For the Freeze, the residual risk of the Lab's adapter code running inside the
engine's JVM is accepted as a bounded limitation. It holds only under these
conditions, which bind every production and qualification run:
1. Pilots always run out of process (AF11: one provider process per game, pilot
   external).
2. No third-party or pilot code runs inside the engine JVM. Only the Lab's own
   reviewed adapter code does, under the AF05 hidden-information proofs.

Stronger isolation is a post-Freeze gate. It must hold before any untrusted pilot is
admitted.

## D3. Production base: fork pin

- Engine: `moeendres-png/mage@b479fe74fd1eaf899ff16c6a9203e74a91c0f339` (MIT).
- Artifact: `mage-1.4.61.jar`, SHA-256
  `ebcb7006e4e90237e82a5e27eca5dd260dfc4e9f1cf7aa851de9356740c02f2d`. These are the exact bytes the Freeze-basis epoch `f881d56fb33f-aef9f7f660b4`
  built and qualified.
  - *Coordinator correction:* the decision was stated with `3bede866…`, the jar of the
    earlier epoch `85dbcb1ac475-9824c55d5ef2`.
  - The jar build of `b479fe74` is not byte-reproducible. The production base keeps
    this artifact, and any rebuild is re-qualified before use.
- Production code lives in a private production repository. The fork is kept minimal,
  and its diff to upstream is documented so that repins stay feasible.

## D4. Protocol schema identity: delegated to the Coordinator, done

Bound to `git-blob:9818d20ee1309e4fde522ffbfe5340eea5145d73` and read from the
epoch's producing tree (#693).

## D5. Application runtime switch: after signature

After the Owner signs, the application runtime moves from the B4-D compatibility
bridge to the proven full-game lane. Gate for the switch:
- `engine-verify` reports `healthy` on the full-game lane;
- the derived `current_runtime.required_missing_capabilities` is empty;
- H4 is green.

## Signature

- [ ] Owner signs the final ADR (`ARCHITECTURE_FREEZE = CLAIMED`, with date).

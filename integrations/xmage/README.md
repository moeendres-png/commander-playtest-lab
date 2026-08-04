# XMage bridge integration point

Pinned upstream: `xmage_1.4.60V3` / commit
`06d166b098ad36b277edef01116472203d5a047e`.

This directory intentionally contains no fabricated XMage bridge binary. A real
binding must call XMage's actual test/server APIs and expose protocol 1.0.0. It
must identify as `engine=xmage` and `runtime_kind=external_rules_engine`.
Run `scripts/verify_engine.sh` before retaining any result.

# J-P3B XMage Raw Evidence Index

Status: `FROZEN_AFTER_REAL_XMAGE_EXECUTION`

This directory is the repository index for the immutable external raw-evidence packages. Full logs/binaries are preserved as GitHub Actions artifacts and Drive roundtrip copies rather than duplicated into Git history.

## Frozen identities

```text
provider = XMage
provider_release = xmage_1.4.60V3
provider_commit = 06d166b098ad36b277edef01116472203d5a047e
provider_tree = f4cadfdddd9271d71103a2e092a5a27f64089305
contract_hash = 89e0813ec66787328dd4b204f57cb5c404694dec29d249fbbb8785fad0a6d2c6
scoring_hash = 67bc2d99e604f22c3a0d6cc3e00682fe9ac5cb86faccae979418eb2cf40d6227
fixture_hash = cfea9c136b9126c4d367b0c91ebfe4089a47490c7d60dfae5e78dd307eb47dbb
```

## Real runtime evidence

- GitHub Actions run: `31398027517`
- provider-controller evidence commit: `52fb1654d22d128d9962741f9908e92f5d4781ad`
- artifact: `9066656227` / `J_P3_XMAGE_RAW_EVIDENCE`
- artifact ZIP SHA-256: `9f49cae416d384490e8fe77da6b782f2ae5c8732f78778c3919df143b5e09926`
- artifact size: `63302` bytes
- internal manifest SHA-256: `02f6553fa099f38814bbb9f7a4e6818f158bf42d8ce94e75df4ecc2f57c7a2f5`
- Drive ID: `1SYlE4AVJqCw9REOVCaCmrFHNoSJtjPx9`
- Drive readback size: `63302` bytes
- Drive readback SHA-256: `9f49cae416d384490e8fe77da6b782f2ae5c8732f78778c3919df143b5e09926`

The runtime package contains acquisition/build/server/remote-controller logs, exact source identity, host/JVM/Maven identity, process lifecycle, remote SessionImpl probe, native remote interface source captures, SHA256SUMS, and the generated XmageRemoteProbe controller source/class.

Observed real runtime facts include: exact frozen source checkout, successful Maven build, real `mage.server.Main` start, `SessionImpl` remote connect with `connected=true` and `server_ready=true`, native game/deck type reads including Commander Free For All, remote Commander table creation/removal, and bounded process shutdown.

The remote probe also invoked `sendPlayerAction` against a deliberately non-existent game UUID. Its transport return is **not** classified as semantic illegal-action rejection evidence and is not used as a valid gameplay-action PASS.

## Native fixture evidence

- GitHub Actions run: `31399104522`
- fixture workflow commit: `09132ca8b43b9c61d92343b290cce4b2b8047fbe`
- artifact: `9067034754` / `J_P3_XMAGE_FIXTURE_EVIDENCE`
- artifact ZIP SHA-256: `fa2cff928f75d74b519eb7984d0bb272809c30a9c0f8a2ce59debed1884b8d18`
- artifact size: `34682` bytes
- internal manifest SHA-256: `669ec1a30603b17e77152f60e26e481ac49a00cd67655d70cc08170c17484025`
- Drive ID: `197zw-jJt4YPQwKY2oID9tukg1S1bXtVI`

Executed provider-native tests:

1. `P3-FX-001 commander_cast`: XMage `CastCommanderTest#testCastCommander` — PASS.
2. `P3-FX-002 commander_tax`: XMage `CommandersCastTest#test_CastToBattlefieldTwoTimes` on the native four-player Commander test base — PASS for repeat-cast/tax semantics, but not the frozen fixture's exact third-cast `+4` assertion; therefore the frozen fixture is classified `PARTIAL`.
3. `P3-FX-003 partner_commanders`: XMage `CastBGPartnerCommanderTest#testCastBothPartnerCommanders` — provider-native test PASS; because the executed pair is not specifically Ishai/Rograkh, the frozen fixture is classified `PARTIAL`.

The remaining frozen fixtures are `NOT_RUN` in P3B. They are not silently treated as unsupported or passed.

## Truth boundary

`real_xmage_executed = true` is supported by real provider execution.

This evidence does **not** establish a complete external gameplay bridge: no real four-player Ishai/Rograkh match was driven end-to-end through the remote controller, no machine-listable legal-action surface was captured for a live game, no valid gameplay action was submitted against a live choice state, no semantic illegal/stale-action rejection was captured, and provider replay was not exercised.

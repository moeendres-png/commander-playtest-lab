# AF11: Coordinator re-adjudication for XMage pin 456b0e22, XMage-only topology

**Date:** 2026-10-21.

**Authority:** Coordinator, AGENTS.md §8 (Owner delegation).

**Machine record:** `AF11_COORDINATOR_ADJUDICATION.json` (this directory).

**Supersedes, for the new pin only:** `qualification/af11-xmage-only-topology-20261021/` (`769e6ebb`). That record remains the adjudication of every epoch run on `769e6ebb`.

## Why a new record

Repin v11 (#955) moved the pin to `456b0e22` (moeendres-png/mage, three engine commits on `769e6ebb`, engine version 1.4.62). The prior record says a pin change invalidates it. PB-03 run 39668803187 on main `f14a1911` (epoch `f14a1911e69c-e841aec870e9`, sealed by the PR that carries this record) reports FULL107 107/107 and AF00–AF10 PASS, and AF11 UNKNOWN because the adjudication covered the earlier pin.

## What changed

- **Engine pin:** `git diff --shortstat 769e6ebb 456b0e22` is 7 files, 277 insertions, 13 deletions: the Protector of the Wastes and Tempt with Reflections card fixes, lazy trigger copies in `GameState`/`GameImpl`, and their tests. No upstream merge, no perf port. The diff contains no `pom.xml` and no `LICENSE` file; XMage stays MIT.
- **Lab dependencies (engine-bridge/pom.xml):** no commit since the v10 sealed main `d012424b5`; `xmage.version` stays 1.4.62. The classpath inventory is the 28-jar one recorded for `043579bb`, unchanged because no engine or bridge `pom.xml` changed. Measured on the sealed epoch: the launch classpath recorded in `MIDGAME_REPLAY_TWIN_EXECUTIONS.json` (PB-03 run 39668803187) lists exactly these 28 jars. The assembler compares the inventory with the run's classpath on each run.

## Decision

The three decisions hold for `456b0e22`:
- separate-process topology;
- provider-specific decision-identity shim;
- provider licence compatibility.

Forge keeps the role `REMOVED`. The effective epoch is `f14a1911e69c-e841aec870e9`. The assembler still verifies on each run that the pin equals the executed engine, the classpath inventory matches, the entry point matches, and the effective epoch is sealed with AF00–AF10 PASS. Anything else stays UNKNOWN.

## Not claimed

No Architecture Freeze change, no production repository, no legal opinion.

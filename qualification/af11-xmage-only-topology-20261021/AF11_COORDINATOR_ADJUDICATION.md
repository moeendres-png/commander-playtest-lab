# AF11: Coordinator re-adjudication for XMage pin 769e6ebb, XMage-only topology

**Date:** 2026-10-21.

**Authority:** Coordinator, AGENTS.md §8 (Owner delegation).

**Machine record:** `AF11_COORDINATOR_ADJUDICATION.json` (this directory).

**Supersedes, for the new pin only:** `qualification/af11-xmage-only-topology-20261020/` (`043579bb`). That record remains the adjudication of every epoch run on `043579bb`.

## Why a new record

Repin v10 (#936) moved the pin to `769e6ebb` (moeendres-png/mage, four determinism commits on `043579bb`, engine version 1.4.62). The prior record says a pin change invalidates it. PB-03 run 39502644797 on main `31713288` (epoch `31713288501c-b4a3ceb4273f`, sealed by the PR that carries this record) reports FULL107 107/107 and AF00–AF10 PASS, and AF11 UNKNOWN because the adjudication covered the earlier pin.

## What changed

- **Engine pin:** `git diff --shortstat 043579bb 769e6ebb` is 117 files, 239 insertions, 139 deletions: the Rules-RNG repair (technical winner, Pool of Vigorous Growth), enum-ordered counter-type loops, `HashSet` to `LinkedHashSet` in 113 files, and the Pia Nalaar energy guard. No upstream merge, no perf port. The diff contains no `pom.xml` and no `LICENSE` file; XMage stays MIT.
- **Lab dependencies (engine-bridge/pom.xml):** no commit since the v9 sealed main `4463c5d3`; `xmage.version` stays 1.4.62. The classpath inventory is the 28-jar one recorded for `043579bb`, unchanged because no engine or bridge `pom.xml` changed. Measured on the sealed epoch: the launch classpath recorded in `MIDGAME_REPLAY_TWIN_EXECUTIONS.json` (PB-03 run 39502644797) lists exactly these 28 jars. The assembler compares the inventory with the run's classpath on each run.

## Decision

The three decisions hold for `769e6ebb`:
- separate-process topology;
- provider-specific decision-identity shim;
- provider licence compatibility.

Forge keeps the role `REMOVED`. The effective epoch is `31713288501c-b4a3ceb4273f`. The assembler still verifies on each run that the pin equals the executed engine, the classpath inventory matches, the entry point matches, and the effective epoch is sealed with AF00–AF10 PASS. Anything else stays UNKNOWN.

## Not claimed

No Architecture Freeze change, no production repository, no legal opinion.

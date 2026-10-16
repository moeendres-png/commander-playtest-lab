# AF11: Coordinator re-adjudication for XMage pin 16e57239, XMage-only topology

**Date:** 2026-10-16.

**Authority:** Coordinator, AGENTS.md §8 (Owner delegation).

**Machine record:** `AF11_COORDINATOR_ADJUDICATION.json` (this directory).

**Supersedes, for the new pin only:** `qualification/af11-xmage-only-topology-20261013/` (`38cb21a8`). That record remains the adjudication of every epoch run on `38cb21a8`.

## Why a new record

Repin v7 (#801) moved the pin to `16e57239` (moeendres-png/mage#60). The prior record says a pin change invalidates it. PB-03 run 38882608818 on main `f6006484` (epoch `f6006484d5ea-378a5e0008c5`, sealed by #807) reports FULL107 107/107 and AF00–AF10 PASS, and AF11 UNKNOWN because the adjudication covered the earlier pin.

## What changed

- **Engine pin:** `git diff --stat 38cb21a8 16e57239` changes one file, `Mage/src/main/java/mage/game/GameImpl.java` (63 insertions, 3 deletions; lazy card copy in `createSimulationForPlayableCalc`). No pom.xml or other build file changed in the fork.
- **Lab dependencies (engine-bridge/pom.xml):** JUnit 5.8.1 to 5.13.4 (test scope, EPL-2.0) and gson 2.13.2 to 2.14.0 (runtime, Apache-2.0).
- **Classpath inventory:** taken from the sealed run itself. The assembler recorded the difference to the prior inventory in `AF00_AF11_XMAGE.json` of the effective epoch: gson 2.14.0, error_prone_annotations 2.48.0 (Apache-2.0, replaces 2.41.0), junit-jupiter 5.13.4 (four jars), junit-platform-commons and engine 1.13.4, opentest4j 1.3.0. Every licence is inside the adjudicated allowlist; none is GPL, LGPL or AGPL.

## Decision

The three decisions hold for `16e57239`:
- separate-process topology;
- provider-specific decision-identity shim;
- provider licence compatibility.

Forge keeps the role `REMOVED`. The effective epoch is `f6006484d5ea-378a5e0008c5`. The assembler still verifies on each run that the pin equals the executed engine, the classpath inventory matches, the entry point matches, and the effective epoch is sealed with AF00–AF10 PASS. Anything else stays UNKNOWN.

## Not claimed

No Architecture Freeze change, no production repository, no legal opinion.

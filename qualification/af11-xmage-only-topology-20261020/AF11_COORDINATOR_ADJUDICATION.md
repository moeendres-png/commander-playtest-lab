# AF11: Coordinator re-adjudication for XMage pin 043579bb, XMage-only topology

**Date:** 2026-10-20.

**Authority:** Coordinator, AGENTS.md §8 (Owner delegation).

**Machine record:** `AF11_COORDINATOR_ADJUDICATION.json` (this directory).

**Supersedes, for the new pin only:** `qualification/af11-xmage-only-topology-20261017/` (`348b37db`). That record remains the adjudication of every epoch run on `348b37db`.

## Why a new record

Repin v9 (#923) moved the pin to `043579bb` (moeendres-png/mage#64, engine version 1.4.62). The prior record says a pin change invalidates it. PB-03 run 39410096746 on main `63f6aebf` (epoch `63f6aebfdea5-17e95be8d3a0`, sealed by the PR that carries this record) reports FULL107 107/107 and AF00–AF10 PASS, and AF11 UNKNOWN because the adjudication covered the earlier pin.

## What changed

- **Engine pin:** `git diff --shortstat 348b37db 043579bb` is 1424 files, 48378 insertions, 6485 deletions: 688 upstream commits (magefree/mage master `fab0f23b`, version 1.4.62) merged into the fork line, 18 conflict files resolved, 7 post-merge edits. 40 `pom.xml` files changed: the module version, the JavaFX client dependency (Mage.Client only, not on the bridge classpath) and the test-scoped `assertj-core`. `LICENSE.txt` is unchanged; XMage stays MIT.
- **Lab dependencies (engine-bridge/pom.xml):** only `xmage.version` moved to 1.4.62. The classpath inventory is the one recorded for `348b37db`, with the five `mage-*.jar` names at 1.4.62: measured with `mvn dependency:build-classpath` (default scope, as the PB-03 workflow builds its classpath manifest, so the JUnit test jars are included) in `engine-bridge` against the 1.4.62 artifacts built from `043579bb`, 28 jars (gson 2.14.0, JUnit 5.13.4, error_prone_annotations 2.48.0 and the rest). The assembler compares the inventory with the sealed run's classpath on each run.

## Decision

The three decisions hold for `043579bb`:
- separate-process topology;
- provider-specific decision-identity shim;
- provider licence compatibility.

Forge keeps the role `REMOVED`. The effective epoch is `63f6aebfdea5-17e95be8d3a0`. The assembler still verifies on each run that the pin equals the executed engine, the classpath inventory matches, the entry point matches, and the effective epoch is sealed with AF00–AF10 PASS. Anything else stays UNKNOWN.

## Not claimed

No Architecture Freeze change, no production repository, no legal opinion.

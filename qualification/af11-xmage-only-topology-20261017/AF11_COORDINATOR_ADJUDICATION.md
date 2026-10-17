# AF11: Coordinator re-adjudication for XMage pin 348b37db, XMage-only topology

**Date:** 2026-10-17.

**Authority:** Coordinator, AGENTS.md §8 (Owner delegation).

**Machine record:** `AF11_COORDINATOR_ADJUDICATION.json` (this directory).

**Supersedes, for the new pin only:** `qualification/af11-xmage-only-topology-20261016/` (`16e57239`). That record remains the adjudication of every epoch run on `16e57239`.

## Why a new record

Repin v8 (#889) moved the pin to `348b37db` (moeendres-png/mage#61). The prior record says a pin change invalidates it. PB-03 run 39041500332 on main `205a9045` (epoch `205a90455343-7396ba38359a`, sealed by the PR that carries this record) reports FULL107 107/107 and AF00–AF10 PASS, and AF11 UNKNOWN because the adjudication covered the earlier pin.

## What changed

- **Engine pin:** `git diff --stat 16e57239 348b37db` changes the engine file `Mage/src/main/java/mage/abilities/effects/common/BecomePreparedSourceEffect.java` (the prepare spell copy of a creature that enters prepared is linked with its final zone change counter), two card/set files in `Mage.Sets` (seven Secrets of Strixhaven prepare creatures enabled; Coercive Impetus +1/+1) and tests. No pom.xml or other build file changed in the fork.
- **Lab dependencies (engine-bridge/pom.xml):** unchanged. The classpath inventory is the one recorded for `16e57239` (gson 2.14.0, JUnit 5.13.4, error_prone_annotations 2.48.0 and the rest); the assembler compares it with the sealed run's classpath on each run.

## Decision

The three decisions hold for `348b37db`:
- separate-process topology;
- provider-specific decision-identity shim;
- provider licence compatibility.

Forge keeps the role `REMOVED`. The effective epoch is `205a90455343-7396ba38359a`. The assembler still verifies on each run that the pin equals the executed engine, the classpath inventory matches, the entry point matches, and the effective epoch is sealed with AF00–AF10 PASS. Anything else stays UNKNOWN.

## Not claimed

No Architecture Freeze change, no production repository, no legal opinion.

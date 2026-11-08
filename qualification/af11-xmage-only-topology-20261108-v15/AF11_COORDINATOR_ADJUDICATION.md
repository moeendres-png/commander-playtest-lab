# AF11: Coordinator re-adjudication for XMage pin f4d12f6e80, XMage-only topology

**Date:** 2026-11-08.

**Authority:** Coordinator, AGENTS.md §8 (Owner delegation).

**Machine record:** `AF11_COORDINATOR_ADJUDICATION.json` (this directory).

**Supersedes, for the new pin only:** `qualification/af11-xmage-only-topology-20261030-v14/` (`2ec507b721`). That record remains the adjudication of every epoch run on `2ec507b721`.

## Why a new record

Repin v15 moved the pin to `f4d12f6e80` (moeendres-png/mage, engine version 1.4.62). The prior record says a change of the engine pin or of the provider classpath jar set invalidates it, and both changed. PB-03 run 42508483426 on main `e1352f1d2c23` (epoch `e1352f1d2c23-1d2de8f805a8`, sealed by the PR that carries this record) reports FULL107 107/107 and AF00-AF10 PASS, and AF11 UNKNOWN because the adjudication covered the earlier pin.

## What changed

- **Engine pin:** `git diff --shortstat 2ec507b721 f4d12f6e80` is 98 files, 1173 insertions, 292 deletions: twelve upstream XMage commits (ten engine and card fixes and two Verify test fixes), the cancelled-payment fix, the Guava and jsoup versions in the root `pom.xml`, and two adaptations of fork code. The diff lists no `LICENSE` file; XMage stays MIT. None of the changes touches licence, topology or the process boundary.
- **Provider classpath:** still 28 jars, but not the inventory of the prior record. Guava 33.4.8-jre to 33.7.2-jre and jsoup 1.21.2 to 1.23.2 come with this pin, with Guava's error_prone_annotations 2.50.0, j2objc-annotations 3.1 and jspecify 1.0.1. gson 2.15.0 and JUnit 6.1.3 (with the junit-platform jars) come from the Lab `engine-bridge/pom.xml`, changed by dependency updates on 2026-11-01 and 2026-11-03, after the prior record. The licences of the changed jars were read from their published POMs: Apache-2.0 (Guava, gson, error_prone_annotations, j2objc-annotations, jspecify), MIT (jsoup), EPL-2.0 (JUnit Jupiter and Platform). Every licence is inside the adjudicated allowlist and none is strong copyleft. Measured on the sealed epoch: the launch classpath recorded in `MIDGAME_REPLAY_TWIN_EXECUTIONS.json` (PB-03 run 42508483426) lists exactly the 28 jars of the record. The assembler compares the inventory with the run's classpath on each run.

## Decision

The three decisions hold for `f4d12f6e80`:
- separate-process topology;
- provider-specific decision-identity shim;
- provider licence compatibility.

Forge keeps the role `REMOVED`. The effective epoch is `e1352f1d2c23-1d2de8f805a8`. The assembler still verifies on each run that the pin equals the executed engine, the classpath inventory matches, the entry point matches, and the effective epoch is sealed with AF00-AF10 PASS. Anything else stays UNKNOWN.

## Not claimed

No Architecture Freeze change, no production repository, no legal opinion.

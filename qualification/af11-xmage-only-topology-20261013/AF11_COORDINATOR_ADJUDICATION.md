# AF11: Coordinator re-adjudication for XMage pin 38cb21a8, XMage-only topology

**Date:** 2026-10-13.

**Authority:** Coordinator, AGENTS.md §8 (Owner delegation). The Owner named this session the sole writer.

**Machine record:** `AF11_COORDINATOR_ADJUDICATION.json` (this directory).

**Supersedes, for the new pin only:** `qualification/af11-single-provider-topology-20261011/` (`3cbf7741`). That record remains the adjudication of every epoch run on `3cbf7741`.

## Why a new record

Two things changed since the prior record:

- **The pin moved.** Repin v6 (#763) moved the pin to `38cb21a8` (moeendres-png/mage#58 and #59). The prior record says a pin change invalidates it. Consequently, PB-03 run 38411201926 on main `33bd77b2` (epoch `33bd77b254a6-a53ec66c9061`, sealed by #766) reports AF11 UNKNOWN, with FULL107 107/107 and AF00–AF10 PASS.
- **Forge was removed.** The Owner removed Forge on 2026-10-13 (`docs/owner_decision_20261013_forge_removal/`). The prior record's fourth decision, "Forge separate process", no longer has a subject.

## What changed between the pins

`git diff --stat 3cbf7741 38cb21a8` changes the following:
- engine-module Java sources (8 files);
- card and set classes;
- tests and notes.

It changes no `pom.xml` and no other build file. `engine-bridge/pom.xml` is unchanged since the prior adjudication. So no dependency, notice, licence, jar set, adapter, entry point or process boundary changed for XMage.

## Decision

These three decisions hold for `38cb21a8`:
- separate-process topology;
- provider-specific decision-identity shim;
- provider licence compatibility.

The record gives Forge the role `REMOVED`. A record that still gives Forge any other role is not accepted by the assembler. With Forge gone, no GPL component is part of the process topology. The former Forge condition is therefore vacuous, not relaxed.

The effective epoch is `33bd77b254a6-a53ec66c9061`. The assembler still verifies every fact on each run:
- the pin equals the executed engine;
- the classpath inventory matches;
- the entry point matches;
- the effective epoch is sealed, with AF00–AF10 PASS.

Anything else stays UNKNOWN.

## Not claimed

As before: no Architecture Freeze change, no production repository, no legal opinion.

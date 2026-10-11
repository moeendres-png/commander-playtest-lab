# AF11 — Coordinator re-adjudication for XMage pin 3cbf7741

Date: 2026-10-11. Authority: Coordinator, AGENTS.md §8 (Owner delegation). The Owner named this
session Coordinator and sole writer on 2026-10-11. The repin itself is Owner-merged (moeendres-png/mage#57,
Lab #723). The effective epoch below is named by the Coordinator; the Owner's #255 condition is unchanged.
Machine record: `AF11_COORDINATOR_ADJUDICATION.json` (this directory).
Supersedes for the new pin only: `qualification/af11-single-provider-topology-20261009/`
(b479fe74). That record remains the adjudication of every epoch run on b479fe74.

## Why a new record

The 2026-10-09 record's second condition says a change to the XMage engine pin invalidates it.
Repin v5 (#723, Lab #720) moved the pin to `3cbf7741` (moeendres-png/mage#57). PB-03 run
38153464865 on main `efac7185` (epoch `efac71856819-40de89f6e188`) therefore reports AF11
UNKNOWN, with FULL107 107/107 and AF00–AF10 PASS.

## What changed between the pins

`git diff --stat b479fe74 3cbf7741` touches exactly two files: `GameImpl.java` (deterministic
order of one owner's commander-zone questions) and its test base. No dependency, notice,
licence, jar set, adapter, entry point or process boundary changed.

## Decision

The four decisions of the prior record (separate-process topology, provider-specific decision
identity shim, provider licence compatibility, Forge separate process) hold unchanged for
`3cbf7741`. The effective epoch is `efac71856819-40de89f6e188`. The assembler still verifies
every fact per run (pin equal to the executed engine, classpath inventory, entry point, sealed
effective epoch with AF00–AF10 PASS); anything else stays UNKNOWN.

## Not claimed

As before: no Architecture Freeze change, no production repository, no legal opinion.

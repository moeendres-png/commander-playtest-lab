# Java libraries in the bridge jar (2026-10-31)

Refs #1070. Report only: `scripts/report_java_dependencies.py` and a hand-made advisory table. No
bridge, fork, pin or sealed record changes, nothing goes into CI.

## 1. Why

`pip-audit` (the `security` job) reads Python packages. The bridge jar carries about twenty Java
libraries shaded into it, and nothing compared them with any advisory list. A review on
2026-10-30/31 read the jar and the public advisory databases once by hand; this change keeps the
result in the repository and makes the comparison repeatable.

## 2. What the report says for `bridge_v14.jar` (table of 2026-10-31)

| Library in the jar | Version | Status | Advisory (fixed in) | Reachable from the bridge |
|---|---|---|---|---|
| `com.google.guava:guava` | 33.4.8-jre | ADVISORY_OPEN | HIGH, deserialization of `CompactHashMap`/`CompactHashSet` (33.7.2) | not shown: needs untrusted Java serialization, the bridge speaks JSONL |
| `org.jsoup:jsoup` | 1.21.2 | ADVISORY_OPEN | HIGH XML tree builder (1.23.2), MODERATE cleaner (1.23.1) | not shown: two data collectors in the fork, not the bridge |
| `com.h2database:h2` | 1.4.197 | ADVISORY_OPEN | two CRITICAL, both H2 console (2.0.206, 2.1.210) | no: nothing starts the console |
| seven more (gson, reload4j, slf4j, ormlite, error_prone) | | CHECKED_CLEAN | none known on 2026-10-31 | |
| `failureaccess`, `listenablefuture`, `j2objc-annotations`, protobuf | | UNKNOWN | not looked up (protobuf leaves no version metadata in the jar) | |

"Not shown" is a grep result on 2026-10-31, not a proof. UNKNOWN is not a pass.

## 3. The H2 server (measured, `AUTO_SERVER=TRUE`)

The fork opens the card database as `jdbc:h2:file:./db/cards.h2;AUTO_SERVER=TRUE`. The script
checks the constant in `mage/cards/repository/DatabaseUtils.class` and prints the fact when it is
there. Measured with this jar on 2026-10-31: a JVM that opens the repository listens on all
network interfaces (`lsof`: `*:<port>`). A caller who reaches the port needs the key that sits in
`db/cards.h2.lock.db`; a wrong database name is refused, the key as the name and the default user
without a password is accepted (`SELECT H2VERSION()` answered 1.4.197). So the exposure is for
everybody who can read the database directory, not for anybody on the network. Not tested: guessing
the key, and what a connected caller can run.

Mitigation without an engine change: `-Dh2.bindAddress=127.0.0.1` in the JVM call. That changes the
qualified launch plan, so it belongs to a requalification chain with the owner's go, not here.

## 4. Use and limits

```bash
python3 scripts/report_java_dependencies.py --jar path/to/bridge.jar [--json out.json] [--strict]
```

- Exit code 0 unless `--strict`; then 1 for any ADVISORY_OPEN or UNKNOWN library.
- The table is `data/security/java_dependency_advisories.json`. It was filled by hand on
  2026-10-31 and ages: the report prints its age and warns after 30 days. Refreshing it needs a
  network lookup (deps.dev, osv.dev), which this script does not do.
- Versions are compared by their leading numbers (`33.4.8-jre` is 33.4.8). A table entry has an
  upper bound only (`fixed_in`), no lower bound.
- A library with no `pom.properties` is not seen, except H2 (version literal in
  `org/h2/engine/Constants.class`) and protobuf (reported with an unknown version).
- Raising Guava and jsoup is a fork change plus repin plus requalification: the owner's decision.

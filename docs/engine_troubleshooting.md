# Engine troubleshooting

## `mvn: command not found`

Use the repository wrapper when available. Otherwise run:

```bash
./scripts/bootstrap_maven.sh 3.9.16
export MAVEN_HOME="$PWD/.tools/apache-maven-3.9.16"
export PATH="$MAVEN_HOME/bin:$PATH"
```

The helper verifies the official SHA-512 sidecar.

## DNS or GitHub failure

Typical error:

```text
curl: (6) Could not resolve host: github.com
```

Check DNS, proxy and firewall settings. On an offline machine, download the
pinned source elsewhere, transfer it without modification and set
`ENGINE_SOURCE_PATH`. Record a source hash and verify the Git commit when `.git`
is available.

## Maven Central unavailable

A source checkout is not enough; Maven dependencies must also be available. Use
a networked build machine, an approved Maven mirror, or transfer a complete
verified Maven cache/build artifact. Do not mark a partial build as successful.

## Incompatible Java

Forge requires Java 17 or newer. The common project baseline is JDK 21. Confirm:

```bash
java -version
javac -version
```

Set `JAVA_HOME` to the JDK, not a JRE.

## Docker unavailable

Use the direct local bootstrap. Docker is optional and its absence must not be
reported as a successful container integration.

## `degraded` after handshake

Inspect the process-state JSON and logs under `artifacts/engine_setup/logs`.
Common causes:

- bridge reports `tactical_oracle` instead of `external_rules_engine`;
- provider mismatch;
- missing legal-action or event-log capability;
- protocol version mismatch;
- upstream engine started but provider bridge did not.

## Port occupied

Change `ENGINE_PORT` or stop the conflicting service. The JSONL stdio bridge does
not require a port unless a provider implementation additionally exposes one.

# Web research

Research was restricted to official documentation, repositories, standards-oriented project documentation and official release pages.

## High-value findings

- XMage remains suitable as an external Commander/tactical oracle, but the repository does not expose a stable ready-made JSONL action API; a provider-specific Java bridge remains necessary.
- Forge remains a secondary differential backend because its CLI/AI path is useful but AI quality and GPL integration constraints limit its role.
- Ruff supports one configuration for lint and format; `ruff check` and `ruff format --check` should be CI gates.
- mypy strict mode is an appropriate target for public production interfaces, but adoption should be incremental for an existing codebase.
- Hypothesis stateful testing can generate and shrink sequences of legal/illegal state transitions; it is a high-value future dependency.
- OpenAI Agents SDK supports function tools, sessions, tracing, usage accounting and guardrails; deterministic game logs must remain separate from model traces.
- GitHub Actions should pin action revisions, set timeouts and upload artifacts/checksums for external-engine evidence.

## Sources reviewed

- Official XMage and Forge repositories/releases.
- Official OpenAI Agents SDK documentation for tools, sessions, tracing, guardrails and usage.
- Official Ruff, mypy and Hypothesis documentation.
- Official GitHub Actions repositories/releases for checkout, setup-python, setup-java and upload-artifact.

The current sandbox could browse these sources through the web research tool, but local DNS and package-manager access remained unavailable to the subprocess environment.

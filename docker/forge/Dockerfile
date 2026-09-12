FROM eclipse-temurin:21-jdk
# WS-A1D-H4F dual-identity authority: ENGINE_* identify the Rules-Core pin
# (config/rules_engines.json secondary_engine), BRIDGE_* identify the exact
# candidate materialization source actually cloned and built
# (secondary_engine.bridge_source). All five are REQUIRED build args resolved
# at build time from the sole pin authority via
# scripts/docker_build_engine.sh, which derives them through
# scripts/docker_resolve_engine_pin.py. There are intentionally no defaults:
# a build without canonical authority fails closed below instead of
# materializing a stale engine, and both clone source and Rules linkage are
# part of engine identity.
ARG ENGINE_REPOSITORY
ARG ENGINE_COMMIT
ARG ENGINE_PROTOCOL_VERSION
ARG BRIDGE_REPOSITORY
ARG BRIDGE_COMMIT
LABEL org.commander-lab.engine-provider="forge"
WORKDIR /opt
RUN set -eu; \
  if [ -z "${ENGINE_REPOSITORY:-}" ]; then echo "ENGINE_REPOSITORY build arg is required (use scripts/docker_build_engine.sh forge)" >&2; exit 1; fi; \
  if [ -z "${ENGINE_COMMIT:-}" ]; then echo "ENGINE_COMMIT build arg is required (use scripts/docker_build_engine.sh forge)" >&2; exit 1; fi; \
  if [ -z "${ENGINE_PROTOCOL_VERSION:-}" ]; then echo "ENGINE_PROTOCOL_VERSION build arg is required (use scripts/docker_build_engine.sh forge)" >&2; exit 1; fi; \
  if [ -z "${BRIDGE_REPOSITORY:-}" ]; then echo "BRIDGE_REPOSITORY build arg is required (use scripts/docker_build_engine.sh forge)" >&2; exit 1; fi; \
  if [ -z "${BRIDGE_COMMIT:-}" ]; then echo "BRIDGE_COMMIT build arg is required (use scripts/docker_build_engine.sh forge)" >&2; exit 1; fi; \
  if ! printf '%s' "$ENGINE_COMMIT" | grep -Eq '^[0-9a-f]{40}$'; then echo "ENGINE_COMMIT is not a full 40-hex SHA" >&2; exit 1; fi; \
  if ! printf '%s' "$ENGINE_REPOSITORY" | grep -Eq '^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$'; then echo "ENGINE_REPOSITORY is not a valid engine repository: $ENGINE_REPOSITORY" >&2; exit 1; fi; \
  if ! printf '%s' "$ENGINE_REPOSITORY" | grep -Eqi 'forge'; then echo "forge image requires a forge repository: $ENGINE_REPOSITORY" >&2; exit 1; fi; \
  if printf '%s' "$ENGINE_REPOSITORY" | grep -Eqi 'mage'; then echo "forge image refuses an xmage repository: $ENGINE_REPOSITORY" >&2; exit 1; fi; \
  if ! printf '%s' "$BRIDGE_COMMIT" | grep -Eq '^[0-9a-f]{40}$'; then echo "BRIDGE_COMMIT is not a full 40-hex SHA" >&2; exit 1; fi; \
  if ! printf '%s' "$BRIDGE_REPOSITORY" | grep -Eq '^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$'; then echo "BRIDGE_REPOSITORY is not a valid engine repository: $BRIDGE_REPOSITORY" >&2; exit 1; fi; \
  if ! printf '%s' "$BRIDGE_REPOSITORY" | grep -Eqi 'forge'; then echo "forge image requires a forge bridge repository: $BRIDGE_REPOSITORY" >&2; exit 1; fi; \
  if printf '%s' "$BRIDGE_REPOSITORY" | grep -Eqi 'mage'; then echo "forge image refuses an xmage bridge repository: $BRIDGE_REPOSITORY" >&2; exit 1; fi; \
  apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates maven python3 && rm -rf /var/lib/apt/lists/*; \
  git clone "$BRIDGE_REPOSITORY" engine-source; \
  git -C engine-source checkout --detach "${BRIDGE_COMMIT}"; \
  test "$(git -C engine-source rev-parse HEAD)" = "${BRIDGE_COMMIT}"; \
  git -C engine-source merge-base --is-ancestor "${ENGINE_COMMIT}" HEAD || { echo "materialization HEAD does not descend from the Rules-Core pin ${ENGINE_COMMIT}" >&2; exit 1; }; \
  git -C engine-source diff --name-only "${ENGINE_COMMIT}" HEAD > /tmp/h4f-surface.txt; \
  if grep -qEv '^(forge-protocol2-bridge/|pom\.xml$)' /tmp/h4f-surface.txt; then echo "unapproved Rules-Core drift outside the qualified H4F surface:" >&2; cat /tmp/h4f-surface.txt >&2; exit 1; fi; \
  printf '{"provider":"forge","repository":"%s","commit":"%s","protocol_version":"%s","bridge_repository":"%s","bridge_commit":"%s","rules_core_base_commit":"%s","bridge_module":"forge-protocol2-bridge"}\n' "$ENGINE_REPOSITORY" "$ENGINE_COMMIT" "$ENGINE_PROTOCOL_VERSION" "$BRIDGE_REPOSITORY" "$BRIDGE_COMMIT" "$ENGINE_COMMIT" > /opt/engine-provenance.json; \
  cat /opt/engine-provenance.json; \
  cd engine-source && (test ! -x ./mvnw || ./mvnw -DskipTests install) \
  && (test -x ./mvnw || mvn -DskipTests install); \
  mkdir -p /opt/forge-bridge; \
  cd /opt/engine-source && mvn -q -pl forge-protocol2-bridge dependency:build-classpath -Dmdep.outputFile=/opt/forge-bridge/cp.txt -DincludeScope=runtime
WORKDIR /workspace
COPY scripts/engine_container_entrypoint.sh /usr/local/bin/engine-entrypoint
COPY docker/forge/forge-bridge.sh /usr/local/bin/forge-bridge
RUN chmod +x /usr/local/bin/forge-bridge
HEALTHCHECK --interval=10s --timeout=3s --retries=6 CMD /workspace/scripts/verify_engine.sh || exit 1
ENTRYPOINT ["/usr/local/bin/engine-entrypoint"]

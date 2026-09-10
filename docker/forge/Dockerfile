FROM eclipse-temurin:21-jdk
# WS-A1D pin authority: ENGINE_REPOSITORY / ENGINE_COMMIT / ENGINE_PROTOCOL_VERSION
# are REQUIRED build args resolved at build time from config/rules_engines.json
# (the sole pin authority) via scripts/docker_build_engine.sh, which derives them
# through scripts/docker_resolve_engine_pin.py. There are intentionally no
# defaults: a build without canonical authority fails closed below instead of
# materializing a stale engine, and the clone source is part of engine identity.
ARG ENGINE_REPOSITORY
ARG ENGINE_COMMIT
ARG ENGINE_PROTOCOL_VERSION
LABEL org.commander-lab.engine-provider="forge"
WORKDIR /opt
RUN set -eu; \
  if [ -z "${ENGINE_REPOSITORY:-}" ]; then echo "ENGINE_REPOSITORY build arg is required (use scripts/docker_build_engine.sh forge)" >&2; exit 1; fi; \
  if [ -z "${ENGINE_COMMIT:-}" ]; then echo "ENGINE_COMMIT build arg is required (use scripts/docker_build_engine.sh forge)" >&2; exit 1; fi; \
  if [ -z "${ENGINE_PROTOCOL_VERSION:-}" ]; then echo "ENGINE_PROTOCOL_VERSION build arg is required (use scripts/docker_build_engine.sh forge)" >&2; exit 1; fi; \
  if ! printf '%s' "$ENGINE_COMMIT" | grep -Eq '^[0-9a-f]{40}$'; then echo "ENGINE_COMMIT is not a full 40-hex SHA" >&2; exit 1; fi; \
  if ! printf '%s' "$ENGINE_REPOSITORY" | grep -Eq '^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$'; then echo "ENGINE_REPOSITORY is not a valid engine repository: $ENGINE_REPOSITORY" >&2; exit 1; fi; \
  if ! printf '%s' "$ENGINE_REPOSITORY" | grep -Eqi 'forge'; then echo "forge image requires a forge repository: $ENGINE_REPOSITORY" >&2; exit 1; fi; \
  if printf '%s' "$ENGINE_REPOSITORY" | grep -Eqi 'mage'; then echo "forge image refuses an xmage repository: $ENGINE_REPOSITORY" >&2; exit 1; fi; \
  apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates maven python3 && rm -rf /var/lib/apt/lists/*; \
  git clone "$ENGINE_REPOSITORY" engine-source; \
  git -C engine-source checkout --detach "${ENGINE_COMMIT}"; \
  test "$(git -C engine-source rev-parse HEAD)" = "${ENGINE_COMMIT}"; \
  printf '{"provider":"forge","repository":"%s","commit":"%s","protocol_version":"%s"}\n' "$ENGINE_REPOSITORY" "$ENGINE_COMMIT" "$ENGINE_PROTOCOL_VERSION" > /opt/engine-provenance.json; \
  cat /opt/engine-provenance.json; \
  cd engine-source && (test ! -x ./mvnw || ./mvnw -DskipTests package) \
  && (test -x ./mvnw || mvn -DskipTests package)
WORKDIR /workspace
COPY scripts/engine_container_entrypoint.sh /usr/local/bin/engine-entrypoint
HEALTHCHECK --interval=10s --timeout=3s --retries=6 CMD /workspace/scripts/verify_engine.sh || exit 1
ENTRYPOINT ["/usr/local/bin/engine-entrypoint"]

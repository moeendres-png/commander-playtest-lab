FROM eclipse-temurin:21-jdk
ARG ENGINE_COMMIT=852066bf4f761b302ed17cb011999d8a8fe08ad6
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates maven python3 && rm -rf /var/lib/apt/lists/*
WORKDIR /opt
RUN git clone https://github.com/Card-Forge/forge.git engine-source \
 && git -C engine-source checkout --detach ${ENGINE_COMMIT} \
 && test "$(git -C engine-source rev-parse HEAD)" = "${ENGINE_COMMIT}" \
 && cd engine-source && (test ! -x ./mvnw || ./mvnw -DskipTests package) \
 && (test -x ./mvnw || mvn -DskipTests package)
WORKDIR /workspace
COPY scripts/engine_container_entrypoint.sh /usr/local/bin/engine-entrypoint
HEALTHCHECK --interval=10s --timeout=3s --retries=6 CMD /workspace/scripts/verify_engine.sh || exit 1
ENTRYPOINT ["/usr/local/bin/engine-entrypoint"]

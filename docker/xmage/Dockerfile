FROM eclipse-temurin:21-jdk
ARG ENGINE_COMMIT=06d166b098ad36b277edef01116472203d5a047e
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates maven python3 && rm -rf /var/lib/apt/lists/*
WORKDIR /opt
RUN git clone https://github.com/magefree/mage.git engine-source \
 && git -C engine-source checkout --detach ${ENGINE_COMMIT} \
 && test "$(git -C engine-source rev-parse HEAD)" = "${ENGINE_COMMIT}" \
 && cd engine-source && mvn -DskipTests package
WORKDIR /workspace
COPY scripts/engine_container_entrypoint.sh /usr/local/bin/engine-entrypoint
HEALTHCHECK --interval=10s --timeout=3s --retries=6 CMD /workspace/scripts/verify_engine.sh || exit 1
ENTRYPOINT ["/usr/local/bin/engine-entrypoint"]

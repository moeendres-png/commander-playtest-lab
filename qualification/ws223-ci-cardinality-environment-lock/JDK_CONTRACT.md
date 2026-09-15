# WS223 JDK Contract

## Authority chain

1. Bytecode floor: `engine-bridge/pom.xml` → `maven.compiler.release = 17`.
   Any JDK ≥ 17 runs the bridge; nothing may target above 17 without a
   recorded reason.
2. CI JVM lanes (`xmage-full-game-conformance`, `external-engine-integration`,
   `h4-docker-materialization`): Eclipse Temurin 17 via `actions/setup-java`
   (`distribution: temurin`, `java-version: "17"`). Major pinned; patch
   floats with the action and is recorded per-run in the environment receipt.
   Exact-patch pinning was rejected: it rots into stale-security runs while
   adding no semantic guarantee beyond the `release=17` floor.
3. Containers (`docker/xmage/Dockerfile`, `docker/forge/Dockerfile`):
   Eclipse Temurin 21 (superset runtime; bytecode remains `release=17`).
   Major retained by the zero-change principle: no evidence requires a
   container downgrade, and the full-XMage-source image build is unverified
   on 17. Digest-pinned (see CONTAINER_IDENTITY).

## Coherence argument

Both majors satisfy the single authoritative floor (17). Skew is explicit
and visible (receipt records the actual `java -version` of every run),
never silent. Downgrading containers to 17, or CI to 21, without a real
image-build + bridge-verify trial would be an arbitrary uniformity change
and is recorded as a future advisory, not done here.

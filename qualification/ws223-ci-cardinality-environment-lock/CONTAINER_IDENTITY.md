# WS223 Container Identity Contract (2026-09-21)

Recorded container-base digest for the WS223 environment-identity battery:

- Digest: `sha256:1f79c73404fb0cccf9a3459eda22892f368d994b1028d6fb1ae871c1f49749a6`
- Tag: `eclipse-temurin:21-jdk`
- Applies to: `docker/xmage/Dockerfile`, `docker/forge/Dockerfile`
  (both `FROM eclipse-temurin:21-jdk@<digest>` plus
  `org.commander-lab.base-image-digest` / `base-image-tag` labels).
- Domain split (WS-A1D/WS223): base-image digests live here; engine pins
  remain REQUIRED build args resolved from `config/rules_engines.json`
  (sole pin authority) with intentionally no defaults.

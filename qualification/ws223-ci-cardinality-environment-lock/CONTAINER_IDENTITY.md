# WS223 Container Identity

## Pinned identity (both `docker/xmage/Dockerfile` and `docker/forge/Dockerfile`)

```
FROM eclipse-temurin:21-jdk@sha256:1f79c73404fb0cccf9a3459eda22892f368d994b1028d6fb1ae871c1f49749a6
```

- Digest class: multi-arch manifest-list digest observed 2026-09-15 via the
  Docker Hub registry API for tag `eclipse-temurin:21-jdk` (tag last pushed
  2026-09-10T02:17:05Z — drift within the last week, demonstrating the float).
- The observed bytes are NEWER than every `21.0.11_*` version tag, so no
  human-readable version tag exists for them; the tag is kept as annotation
  (`LABEL org.commander-lab.base-image-tag`) while the digest governs.
- Byte-change from the pre-WS223 float: zero (digest resolves today's bytes).
- `docker-compose.engine.yml` needs no change (build args are engine pins,
  unaffected).

## Re-verification (no daemon required)

```
GET https://hub.docker.com/v2/repositories/library/eclipse-temurin/tags/21-jdk
→ .digest must equal the pinned digest; any mismatch is base-image drift
  and fails this contract until the digest + LABELs are bumped together.
```

## Bump procedure

Never move the tag alone. Resolve the new manifest digest, update both
Dockerfiles' `FROM` + all three `LABEL`s + this file, and re-run the H4
materialization lane (image build is the only full proof).
